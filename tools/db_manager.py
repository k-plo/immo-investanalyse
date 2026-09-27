#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Immobilien-Datenbank-Manager (SQLite).

Funktionen:
  init            – DB-Schema anlegen (idempotent)
  sync            – Portfolio-Hülle aus der DB neu erzeugen (kein JSON-Import)
  export-json     – DB -> expliziten JSON-Exportpfad schreiben
  check           – SQLite-Integrität, Fremdschlüssel und UUIDs prüfen
  list            – Objekte mit Kerndaten + Rating anzeigen
  prune           – DB-Einträge ohne Objektordner löschen (mit Abfrage)

Verwendung:
  python db_manager.py sync
  python db_manager.py export-json <objektname> <ziel.json>
  python db_manager.py check
  python db_manager.py rating
  python db_manager.py list
  python db_manager.py prune [--yes]
"""
import json
import sqlite3
import sys
import html
import uuid
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).resolve().parent.parent
DB_PATH = BASE / "immo_datenbank.db"

# ---------------------------------------------------------------- Schema ---
SCHEMA = """
CREATE TABLE IF NOT EXISTS objekte (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    public_id TEXT UNIQUE,
    display_name TEXT,
    source_url TEXT,
    analysis_status TEXT,
    image_path TEXT,
    adresse TEXT,
    objektart TEXT,
    baujahr REAL,
    zimmer REAL,
    stellplaetze REAL,
    kaufpreis REAL,
    wohnflaeche REAL,
    preis_pro_m2 REAL,
    grundstuecksflaeche REAL,
    status TEXT,
    html_pfad TEXT,
    json_pfad TEXT,
    json_hash TEXT,
    state_json TEXT,
    erstellt_am TEXT,
    geaendert_am TEXT,
    revision INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS kalkulation (
    objekt_id INTEGER PRIMARY KEY REFERENCES objekte(id) ON DELETE CASCADE,
    preis REAL, flaeche REAL, renovierung REAL, sanierung REAL,
    grESt REAL, notar REAL, makler REAL, sonstige REAL,
    kaltmiete REAL, hausgeld REAL, nebenkostenVorauszahlung REAL, hausgeldNichtUml REAL,
    instand REAL, leerstand REAL, ek REAL, zins REAL, tilgung REAL,
    gesamtinvest REAL, brutto_rendite REAL, netto_rendite REAL,
    cf_vor REAL, cf_nach REAL, rate REAL, coc REAL,
    darlehen REAL, ltv REAL, break_even_miete REAL,
    max_preis REAL, spielraum REAL,
    geaendert_am TEXT
);
CREATE TABLE IF NOT EXISTS risiken (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    objekt_id INTEGER REFERENCES objekte(id) ON DELETE CASCADE,
    text TEXT, kategorie TEXT, ampel TEXT, begruendung TEXT, reihenfolge INTEGER
);
CREATE TABLE IF NOT EXISTS offene_punkte (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    objekt_id INTEGER REFERENCES objekte(id) ON DELETE CASCADE,
    text TEXT, erledigt INTEGER DEFAULT 0, reihenfolge INTEGER
);
CREATE TABLE IF NOT EXISTS naechste_schritte (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    objekt_id INTEGER REFERENCES objekte(id) ON DELETE CASCADE,
    text TEXT, erledigt INTEGER DEFAULT 0, reihenfolge INTEGER
);
CREATE TABLE IF NOT EXISTS chancen (
    objekt_id INTEGER PRIMARY KEY REFERENCES objekte(id) ON DELETE CASCADE,
    nachgewiesen TEXT, hypothese TEXT
);
CREATE TABLE IF NOT EXISTS rating (
    objekt_id INTEGER PRIMARY KEY REFERENCES objekte(id) ON DELETE CASCADE,
    brutto_note TEXT, cf_note TEXT, coc_note TEXT, risiko_note TEXT,
    datenqualitaet_note TEXT, punkte REAL, gesamt_rating TEXT,
    berechnet_am TEXT
);
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY, value TEXT
);
-- --- Hinzugefügt: 2026-09-22 ---
CREATE TABLE IF NOT EXISTS notizen (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    objekt_id INTEGER REFERENCES objekte(id),
    text TEXT NOT NULL,
    erstell_am TEXT DEFAULT CURRENT_TIMESTAMP,
    geaendert_am TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS archivierungsgruenden (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);
INSERT OR IGNORE INTO archivierungsgruenden (name) VALUES
('purchase_price_too_high'), ('low_yield'), ('negative_cashflow'),
('technical_risk'), ('legal_risk'), ('location'), ('financing'),
('missing_documents'), ('sold'), ('withdrawn'), ('other');
"""

# ---------------------------------------------------------------- Helpers ---
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def now():
    return datetime.now().isoformat(timespec="seconds")

def init_db():
    conn = db()
    conn.executescript(SCHEMA)
    vorhandene_spalten = {r[1] for r in conn.execute("PRAGMA table_info(objekte)")}
    if "json_hash" not in vorhandene_spalten:
        conn.execute("ALTER TABLE objekte ADD COLUMN json_hash TEXT")
    if "state_json" not in vorhandene_spalten:
        conn.execute("ALTER TABLE objekte ADD COLUMN state_json TEXT")
    if "grundstuecksflaeche" not in vorhandene_spalten:
        conn.execute("ALTER TABLE objekte ADD COLUMN grundstuecksflaeche REAL")
    if "revision" not in vorhandene_spalten:
        conn.execute("ALTER TABLE objekte ADD COLUMN revision INTEGER NOT NULL DEFAULT 0")
    for column in ("public_id", "display_name", "source_url", "analysis_status", "image_path"):
        if column not in vorhandene_spalten:
            conn.execute(f"ALTER TABLE objekte ADD COLUMN {column} TEXT")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_objekte_public_id ON objekte(public_id)")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_objekte_source_url ON objekte(source_url)")
    for row in conn.execute("SELECT id,name FROM objekte WHERE public_id IS NULL OR public_id='' ").fetchall():
        conn.execute("UPDATE objekte SET public_id=?,display_name=COALESCE(display_name,?) WHERE id=?",
                     (str(uuid.uuid4()), row["name"], row["id"]))
    kalk_spalten = {r[1] for r in conn.execute("PRAGMA table_info(kalkulation)")}
    if "nebenkostenVorauszahlung" not in kalk_spalten:
        conn.execute("ALTER TABLE kalkulation ADD COLUMN nebenkostenVorauszahlung REAL")
    conn.execute("INSERT OR IGNORE INTO meta (key, value) VALUES ('version', '1')")
    conn.execute("INSERT OR IGNORE INTO meta (key, value) VALUES ('erstellt', ?)", (now(),))
    conn.execute("INSERT OR IGNORE INTO meta (key, value) VALUES ('letzte_initialisierung', ?)", (now(),))
    conn.commit()
    conn.close()
    print(f"✓ DB initialisiert: {DB_PATH}")

# ---------------------------------------------------------------- Rating ---
def note_rendite(v: float) -> tuple:
    """(Note, Punkte 0-100) für Rendite-Kennzahlen."""
    if v is None:
        return "F", 0
    if v >= 8: return "A", 100
    if v >= 6: return "B", 80
    if v >= 4: return "C", 60
    if v >= 2: return "D", 35
    return "F", 0

def note_cashflow(v) -> tuple:
    if v is None:
        return "F", 0
    if v >= 100: return "A", 100
    if v >= 0: return "B", 75
    if v >= -50: return "C", 45
    if v >= -150: return "D", 20
    return "F", 0

def note_coc(v) -> tuple:
    if v is None:
        return "F", 0
    if v >= 15: return "A", 100
    if v >= 8: return "B", 80
    if v >= 3: return "C", 55
    return "F", 0

AMPEL_PUNKTE = {"🟢": 100, "🟡": 70, "🟠": 40, "🔴": 10}

def note_risiko(ampeln: list) -> tuple:
    if not ampeln:
        return "C", 55  # keine Risiken erfasst = neutrale Note
    punkte = sum(AMPEL_PUNKTE.get(a, 55) for a in ampeln) / len(ampeln)
    if punkte >= 85: return "A", punkte
    if punkte >= 65: return "B", punkte
    if punkte >= 45: return "C", punkte
    if punkte >= 40: return "D", punkte
    return "F", punkte

def note_datenqualitaet(state: dict) -> tuple:
    """Anteil BELEGT/EINGABE vs. ANNAHME/UNBEKANNT + offene 🔴-Punkte."""
    felder = ["preis", "flaeche", "renovierung", "sanierung", "grESt", "notar",
              "makler", "kaltmiete", "hausgeld", "nebenkostenVorauszahlung", "hausgeldNichtUml", "instand",
              "leerstand", "ek", "zins", "tilgung"]
    gefuellt = sum(1 for f in felder if f in state and state.get(f) not in (None, ""))
    basis = len(felder)
    punkte = gefuellt / basis_len if (basis_len := len(felder)) else 0
    # Abzug für offene 🔴-Punkte
    offene_rot = sum(1 for k, v in state.items()
                     if k.startswith("p_op") and k.endswith("t") and "🔴" in str(v)
                     and not state.get(k[:-1] + "", False))
    punkte = max(0, punkte * 100 - offene_rot * 5)
    if punkte >= 85: return "A", punkte
    if punkte >= 65: return "B", punkte
    if punkte >= 45: return "C", punkte
    if punkte >= 25: return "D", punkte
    return "F", punkte

def berechne_rating(state: dict, risiken: list) -> dict:
    """Berechnet das Gesamt-Rating aus dem State-JSON."""
    def f(x):
        try:
            return float(x) if x not in (None, "") else None
        except (ValueError, TypeError):
            return None
    felder = ["preis", "flaeche", "renovierung", "sanierung", "grESt", "notar",
              "makler", "sonstige", "kaltmiete", "hausgeld", "nebenkostenVorauszahlung", "hausgeldNichtUml",
              "instand", "leerstand", "ek", "zins", "tilgung"]
    werte = {feld: f(state.get(feld)) or 0 for feld in felder}
    km, preis = werte["kaltmiete"], werte["preis"]
    brutto = km * 12 / preis * 100 if preis > 0 else None
    cf_nach = netto_rendite = cf_vor = rate = darlehen = ltv = break_even = max_preis = spielraum = None
    n1, p1 = note_rendite(brutto)
    if preis > 0 and werte["flaeche"] > 0:
        ek, tilg, zins = werte["ek"], werte["tilgung"], werte["zins"]
        lf = 1 - werte["leerstand"] / 52
        hg = werte["hausgeldNichtUml"] if state.get("hausgeldNichtUml") not in (None, "") else max(0, werte["hausgeld"] - werte["nebenkostenVorauszahlung"])
        inst_jahr = werte["flaeche"] * werte["instand"] * 12
        hg_total = werte["hausgeld"]
        nk_proz = werte["grESt"] + werte["notar"] + werte["makler"]
        fix = werte["renovierung"] + werte["sanierung"] + werte["sonstige"]
        netto_jahr = km * 12 * lf - hg * 12 - inst_jahr
        cf_vor = netto_jahr / 12
        gesamt = preis * (1 + nk_proz / 100) + fix
        darlehen = max(0, gesamt - ek)
        rate = darlehen * (zins + tilg) / 100 / 12
        cf_nach = cf_vor - rate
        netto_rendite = netto_jahr / preis * 100
        ltv = darlehen / preis * 100
        break_even = (rate * 12 + hg * 12 + inst_jahr) / lf / 12 if lf > 0 else None
        zt = (zins + tilg) / 100 / 12
        nk_faktor = 1 + nk_proz / 100
        max_preis = max(0, (cf_vor + (ek - fix) * zt) / (nk_faktor * zt)) if zt > 0 else 0
        spielraum = max_preis - preis
    n2, p2 = note_cashflow(cf_nach)
    coc = None
    if werte["ek"] and cf_nach is not None:
        zins_jahr = darlehen * zins / 100
        tilg_jahr = max(0, rate * 12 - zins_jahr)
        coc = (cf_nach * 12 + tilg_jahr) / ek * 100
    n3, p3 = note_coc(coc)
    ampeln = [r[2] for r in risiken]
    n4, p4 = note_risiko(ampeln)
    n5, p5 = note_datenqualitaet(state)
    gesamt_punkte = p1 * 0.25 + p2 * 0.25 + p3 * 0.15 + p4 * 0.20 + p5 * 0.15
    if gesamt_punkte >= 85: g = "A"
    elif gesamt_punkte >= 70: g = "B"
    elif gesamt_punkte >= 55: g = "C"
    elif gesamt_punkte >= 40: g = "D"
    else: g = "F"
    return {
        "brutto_note": n1, "cf_note": n2, "coc_note": n3,
        "risiko_note": n4, "datenqualitaet_note": n5,
        "punkte": round(gesamt_punkte, 1), "gesamt_rating": g,
        "brutto_rendite": brutto, "cf_nach": cf_nach, "coc": coc,
        "gesamtinvest": (gesamt if preis > 0 and werte["flaeche"] > 0 else None),
        "netto_rendite": netto_rendite, "cf_vor": cf_vor, "rate": rate,
        "darlehen": darlehen, "ltv": ltv, "break_even_miete": break_even,
        "max_preis": max_preis, "spielraum": spielraum,
    }

def f(x):
    try:
        return float(x) if x not in (None, "") else None
    except (ValueError, TypeError):
        return None

# Historischer JSON-Import entfernt: SQLite ist die einzige Eingabequelle.\ndef export_json(objektname: str, ziel: str) -> None:
    """Schreibt eine JSON-Kopie in einen expliziten Exportpfad; DB bleibt unverändert."""
    conn = db()
    row = conn.execute("SELECT * FROM objekte WHERE lower(name) = lower(?)", (objektname,)).fetchone()
    if not row:
        print(f"✗ Objekt '{objektname}' nicht gefunden.")
        return
    obj_id = row["id"]
    obj = row
    kal = conn.execute("SELECT * FROM kalkulation WHERE objekt_id = ?", (obj_id,)).fetchone()
    try:
        state = json.loads(obj["state_json"] or "{}")
    except (TypeError, ValueError):
        state = {}
    state.update({"_tool": "immo-db-export", "_version": 1,
                  "_objekt_ordner": obj["name"], "_object_id": obj["public_id"],
                  "_revision": obj["revision"]})
    for feld in ("preis", "flaeche", "renovierung", "sanierung", "grESt", "notar", "makler",
                 "sonstige", "kaltmiete", "hausgeld", "nebenkostenVorauszahlung", "hausgeldNichtUml", "instand",
                 "leerstand", "ek", "zins", "tilgung"):
        state[feld] = kal[feld] if kal[feld] is not None else ""
    risiken = conn.execute("SELECT text, kategorie, ampel, begruendung FROM risiken WHERE objekt_id = ? ORDER BY reihenfolge", (obj_id,)).fetchall()
    state["_risiken"] = [list(r) for r in risiken]
    for key in list(state):
        if key.startswith("p_op") or key.startswith("p_ns"):
            del state[key]
    for tab, prefix, list_key in (("offene_punkte", "op", "offenePunkte"),
                                  ("naechste_schritte", "ns", "schritte")):
        rows = conn.execute(f"SELECT text, erledigt FROM {tab} WHERE objekt_id = ? ORDER BY reihenfolge", (obj_id,)).fetchall()
        list_html = []
        for i, eintrag in enumerate(rows, 1):
            state[f"p_{prefix}{i}"] = bool(eintrag["erledigt"])
            state[f"p_{prefix}{i}t"] = eintrag["text"]
            checked = " checked" if eintrag["erledigt"] else ""
            text = html.escape(eintrag["text"] or "")
            list_html.append(
                f'<li class="chk-li"><input type="checkbox" class="chk" data-persist="{prefix}{i}"{checked}>'
                f'<span class="txt" contenteditable="true" data-persist="{prefix}{i}t">{text}</span>'
                '<button class="btn delete" type="button" title="Punkt löschen" aria-label="Punkt löschen" '
                'onclick="deleteListItem(this)">×</button></li>'
            )
        state[f"_list_{list_key}"] = "".join(list_html)
    chance = conn.execute("SELECT nachgewiesen, hypothese FROM chancen WHERE objekt_id = ?", (obj_id,)).fetchone()
    if chance:
        state["p_chancenNachgewiesen"] = chance["nachgewiesen"] or ""
        state["p_chancenHypothese"] = chance["hypothese"] or ""
    out = Path(ziel).resolve()
    if out == Path(obj["json_pfad"] or "").resolve():
        raise ValueError("Der frühere State-Pfad darf nicht als Exportziel überschrieben werden")
    payload = json.dumps(state, indent=2, ensure_ascii=False)
    out.write_text(payload, encoding="utf-8")
    print(f"✓ Exportiert: {out}")
    conn.close()

def check() -> None:
    """Prüft nur die maßgebliche SQLite-Datenbank."""
    conn = db()
    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    foreign_keys = conn.execute("PRAGMA foreign_key_check").fetchall()
    without_id = conn.execute("SELECT name FROM objekte WHERE public_id IS NULL OR public_id='' ").fetchall()
    print(f"SQLite-Integrität: {integrity}; Fremdschlüssel-Fehler: {len(foreign_keys)}; Objekte ohne ID: {len(without_id)}")
    conn.close()

def list_objekte() -> None:
    conn = db()
    rows = conn.execute("""
        SELECT o.name, o.kaufpreis, o.preis_pro_m2, o.status,
               k.brutto_rendite, k.cf_nach, r.gesamt_rating, r.punkte
        FROM objekte o
        LEFT JOIN kalkulation k ON k.objekt_id = o.id
        LEFT JOIN rating r ON r.objekt_id = o.id
        WHERE COALESCE(o.status, 'aktiv') <> 'archiviert'
        ORDER BY r.punkte DESC
    """).fetchall()
    print(f"{'Objekt':<40}{'KP':>12}{'€/m²':>9}{'BruttoR':>9}{'CF/M':>9}{'Rating':>8}")
    print("-" * 95)
    for r in rows:
        brutto = f"{r['brutto_rendite']:.2f} %" if r["brutto_rendite"] else "–"
        cf = f"{r['cf_nach']:,.0f} €" if r["cf_nach"] is not None else "–"
        kp = f"{r['kaufpreis']:,.0f} €" if r["kaufpreis"] else "–"
        pm2 = f"{r['preis_pro_m2']:,.0f} €" if r["preis_pro_m2"] else "–"
        rating = f"{r['gesamt_rating']} ({r['punkte']:.0f})" if r["gesamt_rating"] else "–"
        print(f"{(r['name'] or '')[:38]:<40}{kp:>12}{pm2:>9}{brutto:>9}{cf:>9}{rating:>8}")
    conn.close()

def sync_portfolio() -> None:
    """Erzeugt die Portfolio-Hülle aus der Datenbank, ohne JSON einzulesen."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("pg", BASE / "tools" / "portfolio_generator.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.main()

# ---------------------------------------------------------------- Backfill ---
def backfill_status():
    """Sättigt leere status-Felder mit 'aktiv' für bestehende Objekte."""
    conn = db()
    conn.execute("UPDATE objekte SET status = 'aktiv' WHERE status IS NULL")
    conn.commit()
    conn.close()
    print("✓ Backfilled: status='aktiv' für alle Objekte")

def backfill_notizen():
    """Löscht alte leere Notizen-Tabelle (falls existiert)."""
    conn = db()
    # Prüfen ob Tabelle existiert und leer ist
    cursor = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE name='notizen'", ()
    )
    exists, _ = cursor.fetchone()
    if exists:
        # Leere Notizen löschen (falls vorhanden)
        conn.execute("DELETE FROM notizen")
        conn.commit()
    conn.close()

def prune(auto_yes: bool = False) -> None:
    """
    Ablauf: Objektordner löschen -> 'python db_manager.py prune' -> 'sync'
    (sync generiert portfolio.html neu, ohne das gelöschte Objekt).
    """
    objekte_root = BASE / "objekte"
    conn = db()
    rows = conn.execute("SELECT id, name FROM objekte ORDER BY name").fetchall()
    verwaist = [r for r in rows if not (objekte_root / r["name"]).is_dir()
                and not (objekte_root / "_ARCHIV" / r["name"]).is_dir()]
    if not verwaist:
        print("✓ Keine verwaisten DB-Einträge – alle Objekte haben einen Ordner.")
        conn.close()
        return
    print("Verwaiste DB-Einträge (Ordner fehlt):")
    for r in verwaist:
        print(f"  - {r['name']}")
    if not auto_yes:
        antwort = input(f"Diese {len(verwaist)} Eintrag/Einträge inkl. Kalkulation/Risiken/Rating löschen? (j/n): ").strip().lower()
        if antwort not in ("j", "ja", "y", "yes"):
            print("Abgebrochen – nichts gelöscht.")
            conn.close()
            return
    conn.execute("PRAGMA foreign_keys = ON")
    for r in verwaist:
        conn.execute("DELETE FROM objekte WHERE id = ?", (r["id"],))
        print(f"  🗑️ Gelöscht: {r['name']}")
    conn.commit()
    conn.close()
    print("✓ DB bereinigt. Danach 'python tools/db_manager.py sync' ausführen, um portfolio.html neu zu generieren.")

# ---------------------------------------------------------------- Main ---
def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd = sys.argv[1]
    if not DB_PATH.exists() and cmd != "init":
        raise SystemExit("Datenbank fehlt. Bitte die versionierte immo_datenbank.db wiederherstellen.")
    if cmd == "init":
        init_db()
    elif cmd in ("import-json", "sync-json"):
        raise SystemExit("JSON-Import ist nach der DB-Migration deaktiviert. SQLite ist die einzige Quelle.")
    elif cmd == "sync":
        init_db()
        sync_portfolio()
    elif cmd == "export-json" and len(sys.argv) > 3:
        export_json(sys.argv[2], sys.argv[3])
    elif cmd == "check":
        check()
    elif cmd == "list":
        list_objekte()
    elif cmd == "rating":
        print("Ratings werden bei jeder DB-Speicherung automatisch neu berechnet.")
    elif cmd == "prune":
        prune(auto_yes="--yes" in sys.argv)
    else:
        print(__doc__)

if __name__ == "__main__":
    main()
