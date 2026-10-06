"""SQLite-backed object state. No runtime reads from State-JSON files."""
from __future__ import annotations

import json
import html
import base64
import math
import re
import sqlite3
import shutil
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from db_manager import DB_PATH, berechne_rating
from listing_import import ListingError, extract_listing, fetch_public, validate_url

BASE = Path(__file__).resolve().parent.parent

INPUT_FIELDS = (
    "preis", "flaeche", "renovierung", "sanierung", "grESt", "notar", "makler",
    "sonstige", "kaltmiete", "hausgeld", "nebenkostenVorauszahlung",
    "hausgeldNichtUml", "instand", "leerstand", "ek", "zins", "tilgung",
)
DERIVED_FIELDS = (
    "gesamtinvest", "brutto_rendite", "netto_rendite", "cf_vor", "cf_nach",
    "rate", "coc", "darlehen", "ltv", "break_even_miete", "max_preis", "spielraum",
)


def _analysis_status(current_status: str | None, rating: dict) -> str:
    """Der Status folgt automatisch der Vollständigkeit der Bewertungsdaten."""
    if current_status == "abruf_blockiert":
        return current_status
    return "analysiert" if rating["gesamt_rating"] != "?" else "quellenpruefung_offen"


class RevisionConflict(Exception):
    pass


def connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=10000")
    return conn


def get_object(name: str) -> dict | None:
    with closing(connection()) as conn:
        row = conn.execute(
            "SELECT name, public_id, display_name, source_url, image_path, analysis_status, revision, state_json, status, geaendert_am, adresse, objektart, baujahr, wohnflaeche FROM objekte WHERE public_id=? OR name=? ORDER BY CASE WHEN public_id=? THEN 0 ELSE 1 END LIMIT 1",
            (name, name, name),
        ).fetchone()
        if row is None:
            return None
        state = json.loads(row["state_json"] or "{}")
        state = _hydrate_workflow_state(conn, row["name"], state)
    return {
        "name": row["name"], "id": row["public_id"], "display_name": row["display_name"],
        "source_url": row["source_url"], "image_path": row["image_path"],
        "analysis_status": row["analysis_status"],
        "revision": row["revision"], "status": row["status"],
        "updated_at": row["geaendert_am"], "state": state,
        "meta": {
            "adresse": row["adresse"], "objektart": row["objektart"],
            "baujahr": row["baujahr"], "wohnflaeche": row["wohnflaeche"],
        },
    }


def _hydrate_workflow_state(conn: sqlite3.Connection, object_name: str, state: dict) -> dict:
    """Merge the DB-owned risks and workflow lists into the browser state."""
    row = conn.execute("SELECT id FROM objekte WHERE name=?", (object_name,)).fetchone()
    if row is None:
        return state
    object_id = row["id"]
    risks = conn.execute(
        "SELECT text, kategorie, ampel, begruendung FROM risiken WHERE objekt_id=? ORDER BY reihenfolge",
        (object_id,),
    ).fetchall()
    if risks:
        state["_risiken"] = [list(risk) for risk in risks]
    for table, prefix, list_key in (("offene_punkte", "op", "offenePunkte"),
                                    ("naechste_schritte", "ns", "schritte")):
        rows = conn.execute(
            f"SELECT text, erledigt FROM {table} WHERE objekt_id=? ORDER BY reihenfolge",
            (object_id,),
        ).fetchall()
        if not rows:
            continue
        for key in list(state):
            if key.startswith(f"p_{prefix}") or key == f"_list_{list_key}":
                del state[key]
        items = []
        for index, item in enumerate(rows, 1):
            text = item["text"] or ""
            state[f"p_{prefix}{index}"] = bool(item["erledigt"])
            state[f"p_{prefix}{index}t"] = text
            checked = " checked" if item["erledigt"] else ""
            escaped = html.escape(text)
            items.append(
                f'<li class="chk-li"><input type="checkbox" class="chk" data-persist="{prefix}{index}"{checked}>'
                f'<span class="txt" contenteditable="true" data-persist="{prefix}{index}t">{escaped}</span>'
                '<button class="btn delete" type="button" title="Punkt löschen" aria-label="Punkt löschen" '
                'onclick="deleteListItem(this)">×</button></li>'
            )
        state[f"_list_{list_key}"] = "".join(items)
    return state


def portfolio_rows() -> list[dict]:
    with closing(connection()) as conn:
        rows = conn.execute("""
            SELECT o.name,o.public_id,o.display_name,o.source_url,o.image_path,o.analysis_status,
                   o.adresse,o.objektart,o.baujahr,o.zimmer,o.stellplaetze,
                   o.grundstuecksflaeche,o.kaufpreis,o.wohnflaeche,o.status,o.html_pfad,
                   o.revision,o.geaendert_am,k.gesamtinvest,k.brutto_rendite,k.netto_rendite,
                   k.cf_nach,k.coc,k.kaltmiete,k.ek,k.zins,k.tilgung,k.rate,
                   CASE
                       WHEN json_extract(o.state_json, '$.p_statusFinanzierung') = 1 THEN 3
                       WHEN json_extract(o.state_json, '$.p_statusBesichtigung') = 1 THEN 2
                       WHEN json_extract(o.state_json, '$.p_statusAnfrage') = 1 THEN 1
                       ELSE 0
                   END AS status_stufe
            FROM objekte o
            LEFT JOIN kalkulation k ON k.objekt_id=o.id
            WHERE COALESCE(o.status,'aktiv') <> 'archiviert'
            ORDER BY status_stufe, o.name
        """).fetchall()
    labels = {0: "Gefunden", 1: "Angefragt", 2: "Besichtigung", 3: "Finanzierungscheck"}
    result = []
    for row in rows:
        item = dict(row)
        item["status_label"] = labels.get(item["status_stufe"], "Gefunden")
        result.append(item)
    return result


def new_candidates() -> list[dict]:
    """Find folders with documents that have no DB record yet (no JSON reads)."""
    with closing(connection()) as conn:
        known = {row[0] for row in conn.execute("SELECT name FROM objekte")}
    result = []
    for folder in sorted((BASE / "objekte").iterdir()):
        if not folder.is_dir() or folder.name.startswith("_") or folder.name in known:
            continue
        documents = folder / "unterlagen"
        count = sum(1 for item in documents.iterdir() if item.is_file()) if documents.is_dir() else 0
        if count:
            result.append({"name": folder.name, "documents": count})
    return result


def _number(value: object) -> float | None:
    if value is None or value == "":
        return None
    result = float(str(value).replace(",", "."))
    if not math.isfinite(result):
        raise ValueError("Zahlen müssen endlich sein")
    return result


def save_object(name: str, state: dict, expected_revision: int) -> dict:
    if not isinstance(state, dict) or not isinstance(state.get("_objekt_ordner"), str):
        raise ValueError("Objektordner im State fehlt")
    if not isinstance(expected_revision, int) or expected_revision < 0:
        raise ValueError("Ungültige Revision")
    payload = json.dumps(state, ensure_ascii=False, allow_nan=False)
    if len(payload.encode("utf-8")) > 1_000_000:
        raise ValueError("Objekt-State ist zu groß")
    values = {key: _number(state.get(key)) for key in INPUT_FIELDS}
    risks = state.get("_risiken", [])
    if not isinstance(risks, list) or len(risks) > 200 or any(
        not isinstance(r, list) or len(r) != 4 for r in risks
    ):
        raise ValueError("Ungültige Risikoliste")
    rating = berechne_rating(state, risks)
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with closing(connection()) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT id, name, revision, analysis_status FROM objekte WHERE public_id=? OR name=? ORDER BY CASE WHEN public_id=? THEN 0 ELSE 1 END LIMIT 1", (name, name, name)).fetchone()
        if row is None:
            raise KeyError(name)
        if row["name"] != state.get("_objekt_ordner"):
            raise ValueError("Objektordner stimmt nicht mit der DB-ID überein")
        if row["revision"] != expected_revision:
            raise RevisionConflict(f"DB-Revision {row['revision']}, Browser-Revision {expected_revision}")
        object_id = row["id"]
        price, area = values["preis"], values["flaeche"]
        analysis_status = _analysis_status(row["analysis_status"], rating)
        conn.execute("""UPDATE objekte SET state_json=?,kaufpreis=?,wohnflaeche=?,
            preis_pro_m2=?,analysis_status=?,geaendert_am=?,revision=revision+1 WHERE id=?""",
            (payload, price, area, price / area if price and area else None, analysis_status, timestamp, object_id))
        derived = {key: rating[key] for key in DERIVED_FIELDS}
        columns = {**values, **derived, "geaendert_am": timestamp}
        assignments = ",".join(f'"{key}"=?' for key in columns)
        conn.execute(f"UPDATE kalkulation SET {assignments} WHERE objekt_id=?",
                     (*columns.values(), object_id))
        conn.execute("DELETE FROM risiken WHERE objekt_id=?", (object_id,))
        for index, risk in enumerate(risks):
            conn.execute("INSERT INTO risiken (objekt_id,text,kategorie,ampel,begruendung,reihenfolge) VALUES (?,?,?,?,?,?)",
                         (object_id, *[str(part) for part in risk], index))
        for table, prefix in (("offene_punkte", "op"), ("naechste_schritte", "ns")):
            conn.execute(f"DELETE FROM {table} WHERE objekt_id=?", (object_id,))
            entries = []
            for key, text in state.items():
                match = re.fullmatch(rf"p_{prefix}(.+)t", key)
                if match:
                    suffix = match.group(1)
                    order = (0, int(suffix)) if suffix.isdigit() else (1, suffix)
                    entries.append((order, suffix, str(text)))
            for index, (_, suffix, text) in enumerate(sorted(entries), 1):
                conn.execute(f"INSERT INTO {table} (objekt_id,text,erledigt,reihenfolge) VALUES (?,?,?,?)",
                             (object_id, text, int(bool(state.get(f"p_{prefix}{suffix}"))), index))
        conn.execute("""INSERT INTO chancen (objekt_id,nachgewiesen,hypothese) VALUES (?,?,?)
            ON CONFLICT(objekt_id) DO UPDATE SET nachgewiesen=excluded.nachgewiesen,hypothese=excluded.hypothese""",
            (object_id, state.get("p_chancenNachgewiesen", ""), state.get("p_chancenHypothese", "")))
        rating_columns = ("brutto_note", "cf_note", "coc_note", "risiko_note", "datenqualitaet_note", "punkte", "gesamt_rating")
        conn.execute("""INSERT INTO rating (objekt_id,brutto_note,cf_note,coc_note,risiko_note,datenqualitaet_note,punkte,gesamt_rating,berechnet_am)
            VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(objekt_id) DO UPDATE SET
            brutto_note=excluded.brutto_note,cf_note=excluded.cf_note,coc_note=excluded.coc_note,
            risiko_note=excluded.risiko_note,datenqualitaet_note=excluded.datenqualitaet_note,
            punkte=excluded.punkte,gesamt_rating=excluded.gesamt_rating,berechnet_am=excluded.berechnet_am""",
            (object_id, *[rating[key] for key in rating_columns], timestamp))
        revision = expected_revision + 1
    return {"name": name, "revision": revision, "updated_at": timestamp, "state": state}


def import_listing(url: str) -> dict:
    """Create a preliminary DB-backed object from verified public listing data."""
    final_url = validate_url(url)
    blocked = False
    try:
        final_url, page, content_type = fetch_public(final_url)
        if "html" not in content_type.lower():
            raise ListingError("Der Link liefert keine HTML-Anzeige")
        data = extract_listing(page, final_url)
        if not any((data["price"], data["area"], data["address"], data["description"])):
            blocked = True
    except ListingError as error:
        if not any(code in str(error) for code in ("HTTP 401", "HTTP 403", "HTTP 429")):
            raise
        blocked = True
    if blocked:
        domain = final_url.split("/")[2]
        data = {"title": f"Anzeige von {domain}", "description": "", "price": None,
                "area": None, "rooms": None, "address": "", "locality": "",
                "image_url": None, "source_url": final_url}
    with closing(connection()) as conn:
        existing = conn.execute("SELECT public_id,name,html_pfad FROM objekte WHERE source_url=?", (final_url,)).fetchone()
    if existing:
        return {"id": existing["public_id"], "name": existing["name"],
                "path": "/" + existing["html_pfad"], "existing": True, "status": "bereits angelegt"}
    public_id = str(uuid.uuid4())
    town = data["locality"] or "objekt"
    slug = re.sub(r"[^a-z0-9]+", "-", town.lower().encode("ascii", "ignore").decode()).strip("-") or "objekt"
    name = f"{slug}-{public_id[:8]}"
    folder = BASE / "objekte" / name
    html_name = f"{name}_Übersicht.html"
    image_path = None
    image_data = None
    if data["image_url"]:
        try:
            _, image_data, image_type = fetch_public(data["image_url"], limit=5_000_000)
            image_type = image_type.split(";", 1)[0].lower()
            ext = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "image/avif": "avif"}.get(image_type)
            if ext:
                image_path = f"/objekte/{name}/titelbild.{ext}"
            else:
                image_data = None
        except ListingError:
            image_data = None
    if folder.exists():
        raise ListingError("Objektordner existiert bereits")
    folder.mkdir()
    try:
        template = (BASE / "objekte" / "_VORLAGE" / "Objektname_Übersicht.html").read_text(encoding="utf-8")
        template = template.replace('const OBJEKT_ORDNER = "Objektname";', f'const OBJEKT_ORDNER = "{name}";')
        template = template.replace('<title>Objektname – Übersicht</title>', f'<title>{html.escape(data["title"])} – Übersicht</title>')
        template = template.replace('<h1>🏠 Objektname</h1>', f'<h1>🏠 {html.escape(data["title"])}</h1>')
        (folder / html_name).write_text(template, encoding="utf-8")
        (folder / "analyse").mkdir()
        (folder / "analyse" / "QUELLENPRUEFUNG.md").write_text(
            f'# Voranalyse – {data["title"]}\n\nQuelle: {final_url}\n\n'
            f'Anzeigenbeschreibung (ungeprüft): {data["description"] or "nicht abrufbar"}\n\n'
            'Status: unvollständig. Preis, Fläche und Adresse sind Anzeigenangaben; Unterlagen, Mietdaten, Zustand und Rechtslage sind zu verifizieren.\n',
            encoding="utf-8")
        (folder / "unterlagen").mkdir()
        if image_path and image_data:
            (folder / Path(image_path).name).write_bytes(image_data)
        state = {"_tool": "immo-objekt-uebersicht", "_version": 1, "_objekt_ordner": name,
                 "_risiken": [], "p_externeUrl": final_url,
                 "p_tag-preis": "ANGABE · Online-Anzeige (ungeprüft)",
                 "p_tag-flaeche": "ANGABE · Online-Anzeige (ungeprüft)"}
        for key in INPUT_FIELDS:
            state[key] = ""
        if data["price"] is not None:
            state["preis"] = str(data["price"])
        if data["area"] is not None:
            state["flaeche"] = str(data["area"])
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with closing(connection()) as conn, conn:
            conn.execute("""INSERT INTO objekte
                (name,public_id,display_name,source_url,analysis_status,image_path,adresse,zimmer,wohnflaeche,status,html_pfad,state_json,erstellt_am,geaendert_am,revision)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,0)""",
                (name, public_id, data["title"], final_url, "abruf_blockiert" if blocked else "quellenpruefung_offen", image_path,
                 data["address"], data["rooms"], data["area"], "aktiv", f"objekte/{name}/{html_name}",
                 json.dumps(state, ensure_ascii=False), now, now))
            object_id = conn.execute("SELECT id FROM objekte WHERE public_id=?", (public_id,)).fetchone()[0]
            conn.execute("INSERT INTO kalkulation(objekt_id) VALUES (?)", (object_id,))
        save_object(public_id, state, 0)
        return {"id": public_id, "name": name, "path": f"/objekte/{name}/{html_name}",
                "existing": False, "status": "Abruf blockiert – leeres Objekt zur manuellen Prüfung angelegt" if blocked else "Voranalyse angelegt – Quellenprüfung offen"}
    except Exception:
        with closing(connection()) as conn, conn:
            conn.execute("DELETE FROM objekte WHERE public_id=?", (public_id,))
        shutil.rmtree(folder)
        raise


def set_archive_status(public_id: str, archive: bool, expected_revision: int) -> dict:
    """Move the object folder and status as one guarded local operation."""
    with closing(connection()) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT name,status,revision,html_pfad,image_path FROM objekte WHERE public_id=?", (public_id,)).fetchone()
        if row is None:
            raise KeyError(public_id)
        if row["revision"] != expected_revision:
            raise RevisionConflict("Objekt wurde auf einem anderen Stand geändert")
        target_status = "archiviert" if archive else "aktiv"
        if row["status"] == target_status:
            return {"id": public_id, "revision": row["revision"], "status": target_status}
        name = row["name"]
        source = BASE / "objekte" / ("_ARCHIV" if not archive else "") / name
        target = BASE / "objekte" / ("_ARCHIV" if archive else "") / name
        if not source.is_dir() or target.exists():
            raise ValueError("Objektordner fehlt oder Zielordner ist bereits belegt")
        target.parent.mkdir(exist_ok=True)
        source.rename(target)
        try:
            html_file = Path(row["html_pfad"] or "").name
            relative = target.relative_to(BASE).as_posix() + "/" + html_file
            photo = "/" + target.relative_to(BASE).as_posix() + "/" + Path(row["image_path"]).name if row["image_path"] else None
            conn.execute("UPDATE objekte SET status=?,html_pfad=?,image_path=?,revision=revision+1 WHERE public_id=?",
                         (target_status, relative, photo, public_id))
        except Exception:
            target.rename(source)
            raise
        return {"id": public_id, "revision": expected_revision + 1, "status": target_status}


def set_photo(public_id: str, encoded: str, mime: str, expected_revision: int) -> dict:
    """Store a user-selected local property photo and its path in the DB."""
    extensions = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "image/avif": "avif"}
    if mime not in extensions or not isinstance(encoded, str) or len(encoded) > 8_000_000:
        raise ValueError("Nur JPEG, PNG, WebP oder AVIF bis 5 MB erlaubt")
    try:
        photo = base64.b64decode(encoded, validate=True)
    except (ValueError, base64.binascii.Error) as error:
        raise ValueError("Ungültige Bilddaten") from error
    if len(photo) > 5_000_000 or not photo:
        raise ValueError("Bild ist zu groß oder leer")
    signatures = {
        "image/jpeg": photo.startswith(b"\xff\xd8\xff"),
        "image/png": photo.startswith(b"\x89PNG\r\n\x1a\n"),
        "image/webp": photo.startswith(b"RIFF") and photo[8:12] == b"WEBP",
        "image/avif": photo[4:12] in (b"ftypavif", b"ftypavis"),
    }
    if not signatures[mime]:
        raise ValueError("Datei entspricht nicht dem Bildformat")
    with closing(connection()) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT name,status,revision FROM objekte WHERE public_id=?", (public_id,)).fetchone()
        if row is None:
            raise KeyError(public_id)
        if row["revision"] != expected_revision:
            raise RevisionConflict("Objekt wurde auf einem anderen Stand geändert")
        folder = BASE / "objekte" / ("_ARCHIV" if row["status"] == "archiviert" else "") / row["name"]
        if not folder.is_dir():
            raise ValueError("Objektordner fehlt")
        target = folder / f"titelbild.{extensions[mime]}"
        tmp = folder / f".titelbild-{public_id}.tmp"
        try:
            tmp.write_bytes(photo)
            tmp.replace(target)
            image_path = "/" + target.relative_to(BASE).as_posix()
            conn.execute("UPDATE objekte SET image_path=?,revision=revision+1 WHERE public_id=?", (image_path, public_id))
        finally:
            if tmp.exists():
                tmp.unlink()
        return {"id": public_id, "revision": expected_revision + 1, "image_path": image_path}
