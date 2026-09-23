#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Immobilien-Datenbank-Manager (SQLite).

Funktionen:
  init            – DB-Schema anlegen (idempotent)
  import-json     – Objekt-State-JSON in die DB importieren (Upsert)
  sync-json       – JSON-Dateien aller Objektordner einlesen -> DB aktualisieren
  export-json     – DB -> JSON-Dateien schreiben (Fail-Safe-Restore)
  check           – Konsistenzprüfung DB vs. JSON (Prüfsummen)
  rating          – Ratings neu berechnen
  list            – Objekte mit Kerndaten + Rating anzeigen
  prune           – DB-Einträge ohne Objektordner löschen (mit Abfrage)

Verwendung:
  python db_manager.py import-json <pfad-zur-json>
  python db_manager.py sync-json <objekte-root>
  python db_manager.py export-json <objektname>
  python db_manager.py check
  python db_manager.py rating
  python db_manager.py list
  python db_manager.py prune [--yes]
"""
import json
import sqlite3
import sys
import hashlib
from pathlib import Path
from datetime import datetime

BASE = Path(r"c:\Users\User\Meine Ablage\Immo\VS Code\Immo")
DB_PATH = BASE / "immo_datenbank.db"

# ---------------------------------------------------------------- Schema ---
SCHEMA = """
CREATE TABLE IF NOT EXISTS objekte (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    adresse TEXT,
    objektart TEXT,
    baujahr REAL,
    zimmer REAL,
    stellplaetze REAL,
    kaufpreis REAL,
    wohnflaeche REAL,
    preis_pro_m2 REAL,
    status TEXT,
    html_pfad TEXT,
    json_pfad TEXT,
    erstellt_am TEXT,
    geaendert_am TEXT
);
CREATE TABLE IF NOT EXISTS kalkulation (
    objekt_id INTEGER PRIMARY KEY REFERENCES objekte(id) ON DELETE CASCADE,
    preis REAL, flaeche REAL, renovierung REAL, sanierung REAL,
    grESt REAL, notar REAL, makler REAL, sonstige REAL,
    kaltmiete REAL, hausgeld REAL, hausgeldNichtUml REAL,
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
    return conn

def now():
    return datetime.now().isoformat(timespec="seconds")

def init_db():
    conn = db()
    conn.executescript(SCHEMA)
    conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('version', '1')")
    conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('erstellt', ?)", (now(),))
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
              "makler", "kaltmiete", "hausgeld", "hausgeldNichtUml", "instand",
              "leerstand", "ek", "zins", "tilgung"]
    belegt = {"preis", "flaeche", "grESt", "notar", "makler", "zins"}
    gefuellt = sum(1 for f in felder if state.get(f) not in (None, "", "0") or f in belegt)
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
    brutto = None
    # Bruttorendite aus Kalkulation ableiten (KM*12/preis)
    km, preis = f(state.get("kaltmiete")), f(state.get("preis"))
    if km and preis:
        brutto = km * 12 / preis * 100
    cf_nach = None
    # CF nach Finanzierung grob rekonstruieren (vereinfacht, ohne Hausgeld-Logik):
    # Hier nutzen wir die gespeicherten Werte, falls vorhanden
    n1, p1 = note_rendite(brutto)
    # Cashflow: aus Rate und CF-vor (Vereinfachung: CF-nach = KM*12*lf - Rate)
    ek, tilg, zins = f(state.get("ek")), f(state.get("tilgung")), f(state.get("zins"))
    lf = 1 - (f(state.get("leerstand")) or 0) / 52
    hg = f(state.get("hausgeldNichtUml")) or 0
    inst = (f(state.get("instand")) or 0) / 100
    hg_total = f(state.get("hausgeld")) or 0
    if km and preis and ek is not None and zins is not None and tilg is not None:
        nk_proz = (d := f(state.get("grESt")) or 0) + (f(state.get("notar")) or 0) + (f(state.get("makler")) or 0)
        fix = (f(state.get("renovierung")) or 0) + (f(state.get("sanierung")) or 0) + (f(state.get("sonstige")) or 0)
        netto_jahr = km * 12 * lf - hg * 12 - (0 if hg_total > 0 else km * 12 * 0.03) - km * 12 * inst
        cf_vor = netto_jahr / 12
        gesamt = preis * (1 + nk_proz / 100) + fix
        darlehen = max(0, gesamt - ek)
        rate = darlehen * (zins + tilg) / 100 / 12
        cf_nach = cf_vor - rate
    n2, p2 = note_cashflow(cf_nach)
    coc = None
    if ek and cf_nach is not None:
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
        "gesamtinvest": (gesamt if (km and preis and ek is not None and zins is not None and tilg is not None) else None),
    }

def f(x):
    try:
        return float(x) if x not in (None, "") else None
    except (ValueError, TypeError):
        return None

# ---------------------------------------------------------------- Import ---
def import_json(path: str) -> None:
    """Importiert ein State-JSON in die DB (Upsert)."""
    p = Path(path)
    state = json.loads(p.read_text(encoding="utf-8"))
    name = p.parent.name  # Objektordner-Name
    # Objekt-Metadaten aus der 03_kalkulation.json lesen (Objektart, Baujahr, Zimmer …)
    meta = {}
    kal_path = p.parent / "analyse" / "03_kalkulation.json"
    if kal_path.exists():
        try:
            kal_meta = json.loads(kal_path.read_text(encoding="utf-8"))
            meta = kal_meta.get("objekt", {})
        except Exception:
            pass
    conn = db()
    conn.execute("INSERT OR IGNORE INTO objekte (name, erstellt_am) VALUES (?, ?)", (name, now()))
    obj_id = conn.execute("SELECT id FROM objekte WHERE name = ?", (name,)).fetchone()[0]
    # HTML-Dateiname: aus dem State-JSON ableiten (STATE_DATEINAME ohne "_State.json")
    # oder: tatsächliche HTML-Datei im Objektordner suchen (endet auf "_Übersicht.html")
    html_name = None
    for h in p.parent.glob("*_Übersicht.html"):
        html_name = h.name
        break
    if not html_name:
        html_name = f"{name}_Übersicht.html"  # Fallback
    conn.execute("""UPDATE objekte SET kaufpreis=?, wohnflaeche=?, preis_pro_m2=?,
                    adresse=?, objektart=?, baujahr=?, zimmer=?, stellplaetze=?,
                    html_pfad=?, json_pfad=?, geaendert_am=? WHERE id=?""",
                 (f(state.get("preis")), f(state.get("flaeche")),
                  (f(state.get("preis")) / f(state.get("flaeche"))) if f(state.get("preis")) and f(state.get("flaeche")) else None,
                  meta.get("adresse", ""), meta.get("objektart", ""),
                  f(meta.get("baujahr")), f(meta.get("zimmer")), f(meta.get("stellplaetze")),
                  f"objekte/{name}/{html_name}",
                  str(p), now(), obj_id))
    # Rating VOR der Kalkulation berechnen (brutto_rendite/cf_nach/coc werden
    # dort mitgespeichert, damit portfolio.html sie anzeigen kann)
    risiken_state = [(r[0], r[1], r[2], r[3]) for r in state.get("_risiken", [])]
    rating = berechne_rating(state, risiken_state)
    # Kalkulation (brutto_rendite/cf_nach/coc aus dem Rating übernehmen,
    # damit portfolio.html sie anzeigen kann – vorher immer "–")
    conn.execute("""INSERT OR REPLACE INTO kalkulation
                    (objekt_id, preis, flaeche, renovierung, sanierung, grESt, notar, makler, sonstige,
                     kaltmiete, hausgeld, hausgeldNichtUml, instand, leerstand, ek, zins, tilgung,
                     gesamtinvest, brutto_rendite, cf_nach, coc, geaendert_am)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                 (obj_id, f(state.get("preis")), f(state.get("flaeche")), f(state.get("renovierung")),
                  f(state.get("sanierung")), f(state.get("grESt")), f(state.get("notar")),
                  f(state.get("makler")), f(state.get("sonstige")), f(state.get("kaltmiete")),
                  f(state.get("hausgeld")), f(state.get("hausgeldNichtUml")), f(state.get("instand")),
                  f(state.get("leerstand")), f(state.get("ek")), f(state.get("zins")),
                  f(state.get("tilgung")), rating.get("gesamtinvest"), rating.get("brutto_rendite"), rating.get("cf_nach"),
                  rating.get("coc"), now()))
    # Risiken
    conn.execute("DELETE FROM risiken WHERE objekt_id = ?", (obj_id,))
    for i, r in enumerate(state.get("_risiken", [])):
        conn.execute("INSERT INTO risiken (objekt_id, text, kategorie, ampel, begruendung, reihenfolge) VALUES (?,?,?,?,?,?)",
                     (obj_id, r[0], r[1], r[2], r[3], i))
    # Offene Punkte + nächste Schritte
    for tab, prefix in (("offene_punkte", "op"), ("naechste_schritte", "ns")):
        conn.execute(f"DELETE FROM {tab} WHERE objekt_id = ?", (obj_id,))
        i = 1
        while True:
            txt_key, chk_key = f"p_{prefix}{i}t", f"p_{prefix}{i}"
            if txt_key not in state:
                break
            conn.execute(f"INSERT INTO {tab} (objekt_id, text, erledigt, reihenfolge) VALUES (?,?,?,?)",
                         (obj_id, state[txt_key], 1 if state.get(chk_key) else 0, i))
            i += 1
    # Chancen
    conn.execute("""INSERT OR REPLACE INTO chancen (objekt_id, nachgewiesen, hypothese) VALUES (?,?,?)""",
                 (obj_id, state.get("p_chancenNachgewiesen", ""), state.get("p_chancenHypothese", "")))
    # Rating speichern (bereits oben berechnet)
    conn.execute("""INSERT OR REPLACE INTO rating
                    (objekt_id, brutto_note, cf_note, coc_note, risiko_note, datenqualitaet_note,
                     punkte, gesamt_rating, berechnet_am) VALUES (?,?,?,?,?,?,?,?,?)""",
                 (obj_id, rating["brutto_note"], rating["cf_note"], rating["coc_note"],
                  rating["risiko_note"], rating["datenqualitaet_note"],
                  rating["punkte"], rating["gesamt_rating"], now()))
    conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('letzte_sync', ?)", (now(),))
    conn.commit()
    conn.close()
    print(f"✓ Importiert: {name} → Rating {rating['gesamt_rating']} ({rating['punkte']} Pkt.)")

def sync_json(objekte_root: str) -> None:
    """Liest alle State-JSONs aus den Objektordnern und importiert sie."""
    root = Path(objekte_root)
    gefunden = 0
    for ordner in sorted(root.iterdir()):
        if not ordner.is_dir() or ordner.name.startswith("_"):
            continue
        for j in ordner.glob("*_Übersicht_State.json"):
            import_json(str(j))
            gefunden += 1
    print(f"✓ {gefunden} Objekt(e) synchronisiert.")

def export_json(objektname: str) -> None:
    """Schreibt die DB-Daten eines Objekts zurück ins JSON (Fail-Safe-Restore)."""
    conn = db()
    row = conn.execute("SELECT id FROM objekte WHERE name LIKE ?", (f"%{objektname}%",)).fetchone()
    if not row:
        print(f"✗ Objekt '{objektname}' nicht gefunden.")
        return
    obj_id = row["id"]
    obj = conn.execute("SELECT * FROM objekte WHERE id = ?", (obj_id,)).fetchone()
    kal = conn.execute("SELECT * FROM kalkulation WHERE objekt_id = ?", (obj_id,)).fetchone()
    state = {"_tool": "immo-db-export", "_version": 1}
    for feld in ("preis", "flaeche", "renovierung", "sanierung", "grESt", "notar", "makler",
                 "sonstige", "kaltmiete", "hausgeld", "hausgeldNichtUml", "instand",
                 "leerstand", "ek", "zins", "tilgung"):
        state[feld] = kal[feld] if kal[feld] is not None else ""
    risiken = conn.execute("SELECT text, kategorie, ampel, begruendung FROM risiken WHERE objekt_id = ? ORDER BY reihenfolge", (obj_id,)).fetchall()
    state["_risiken"] = [list(r) for r in risiken]
    out = BASE / "objekte" / objektname / f"{objektname}_Übersicht_State.json"
    out.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"✓ Exportiert: {out}")
    conn.close()

def check() -> None:
    """Konsistenzprüfung: DB vs. JSON-Prüfsummen."""
    conn = db()
    objekte = conn.execute("SELECT id, name, json_pfad FROM objekte").fetchall()
    print("KONSISTENZPRÜFUNG")
    for o in objekte:
        p = Path(o["json_pfad"])
        if not p.exists():
            print(f"  ⚠️ {o['name']}: JSON fehlt ({p})")
            continue
        j_hash = hashlib.sha256(p.read_bytes()).hexdigest()[:12]
        kal = conn.execute("SELECT geaendert_am FROM kalkulation WHERE objekt_id = ?", (o["id"],)).fetchone()
        print(f"  ✓ {o['name']}: JSON vorhanden (Hash {j_hash}), DB-Stand {kal['geaendert_am'] if kal else '–'}")
    conn.close()

def list_objekte() -> None:
    conn = db()
    rows = conn.execute("""
        SELECT o.name, o.kaufpreis, o.preis_pro_m2, o.status,
               k.brutto_rendite, k.cf_nach, r.gesamt_rating, r.punkte
        FROM objekte o
        LEFT JOIN kalkulation k ON k.objekt_id = o.id
        LEFT JOIN rating r ON r.objekt_id = o.id
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
    """sync-json + portfolio_generator in einem Aufruf."""
    sync_json(str(BASE / "objekte"))
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
    verwaist = [r for r in rows if not (objekte_root / r["name"]).is_dir()]
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
        init_db()
    if cmd == "init":
        init_db()
    elif cmd == "import-json" and len(sys.argv) > 2:
        init_db()
        import_json(sys.argv[2])
    elif cmd == "sync-json" and len(sys.argv) > 2:
        init_db()
        sync_json(sys.argv[2])
    elif cmd == "sync":
        init_db()
        sync_portfolio()
    elif cmd == "export-json" and len(sys.argv) > 2:
        export_json(sys.argv[2])
    elif cmd == "check":
        check()
    elif cmd == "list":
        list_objekte()
    elif cmd == "rating":
        print("Rating wird bei jedem import-json automatisch neu berechnet.")
    elif cmd == "prune":
        prune(auto_yes="--yes" in sys.argv)
    else:
        print(__doc__)

if __name__ == "__main__":
    main()