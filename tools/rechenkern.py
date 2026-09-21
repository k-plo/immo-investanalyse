#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Immobilien-Rechenkern – nachvollziehbare Berechnungen zur Investmentanalyse.

Zweck: Dieselbe Logik wie tools/kalkulation.html, aber in Klartext-Ausgabe,
damit jede Zahl im Investmentbericht prüfbar ist.

Verwendung:
    python rechenkern.py                          # nutzt Beispieldaten
    python rechenkern.py 03_kalkulation.json      # nutzt Objekt-JSON (Vorlage: objekte/_VORLAGE/analyse/03_kalkulation.json)

Hinweis: Modellrechnung – keine rechtliche, steuerliche oder finanzielle Beratung.
"""
import json
import sys
from pathlib import Path

# ---------------------------------------------------------------- Eingaben ---
def default_data() -> dict:
    """Beispieldaten (ANNAHME) – durch belegte Werte aus den Unterlagen ersetzen."""
    return {
        "objekt": {"name": "Beispielobjekt", "wohnflaeche_m2": 72.4},
        "kauf": {
            "angebotspreis_eur": 189000.0,
            "grunderwerbsteuer_prozent": 6.0,   # ANNAHME (Bundesland unbekannt)
            "notar_prozent": 2.0,               # ANNAHME (Notar+Grundbuch zusammen)
            "grundbuch_prozent": 0.0,
            "makler_prozent": 3.57,             # ANNAHME (Käuferanteil)
            "renovierung_eur": 10000.0,
            "sanierung_eur": 0.0,
            "sonstige_erwerbskosten_eur": 0.0,
        },
        "miete": {
            "kaltmiete_monatlich_eur": 850.0,
            "leerstand_wochen_pro_jahr": 0.0,
            "marktuebliche_miete_eur": 0.0,
            "mietrueckstaende_eur": 0.0,
        },
        "laufende_kosten": {
            "hausgeld_monatlich_eur": 250.0,
            "nicht_umlagefaehige_kosten_monatlich_eur": 60.0,
            "verwaltung_prozent_von_miete": 0.0,   # bei ETW im Hausgeld
            "instandhaltung_prozent_von_miete": 10.0,
        },
        "finanzierung": {
            "eigenkapital_eur": 50000.0,
            "zinssatz_prozent": 3.5,
            "tilgung_prozent": 2.0,
            "zinsbindung_jahre": 10,
            "finanzierungsnebenkosten_eur": 0.0,
        },
        "weg": {"instandhaltungsruecklage_eur": 0.0, "geplante_sonderumlagen_eur": 0.0},
        "annahmen": ["Alle Werte sind Beispiel-Annahmen – durch BELEGT-Werte ersetzen."],
        "quellen": [],
        "widersprueche": [],
    }

def load_data(path: str | None) -> dict:
    if not path:
        return default_data()
    p = Path(path)
    if not p.exists():
        print(f"⚠️  Datei nicht gefunden: {p} – nutze Beispieldaten.")
        return default_data()
    with p.open(encoding="utf-8") as f:
        data = json.load(f)
    # Fehlende Abschnitte ergänzen, damit der Kern robust bleibt
    base = default_data()
    for k, v in base.items():
        if k not in data:
            data[k] = v
        elif isinstance(v, dict):
            for k2, v2 in v.items():
                data[k].setdefault(k2, v2)
    return data

# ---------------------------------------------------------------- Rechenkern ---
def annuitaetenrate(darlehen: float, zins_p: float, tilgung_p: float) -> float:
    """Monatliche Rate = Darlehen * (Zins + Tilgung) / 100 / 12."""
    return darlehen * (zins_p + tilgung_p) / 100.0 / 12.0

def berechne(d: dict) -> dict:
    kauf, miete, lk, fin = d["kauf"], d["miete"], d["laufende_kosten"], d["finanzierung"]
    flaeche = (d.get("objekt") or {}).get("wohnflaeche_m2") or 0.0
    preis = kauf["angebotspreis_eur"]
    r: dict = {}

    # --- Ausstehende Werte prüfen (Variante A: keine erfundenen Zahlen) ---
    fehlend = []
    if kauf.get("renovierung_eur") is None:
        fehlend.append("Renovierung")
    if kauf.get("sanierung_eur") is None:
        fehlend.append("Sanierung")
    if miete.get("kaltmiete_monatlich_eur") is None:
        fehlend.append("Kaltmiete")
    if miete.get("leerstand_wochen_pro_jahr") is None:
        fehlend.append("Leerstand")
    if lk.get("hausgeld_monatlich_eur") is None:
        fehlend.append("Hausgeld")
    if lk.get("nicht_umlagefaehige_kosten_monatlich_eur") is None:
        fehlend.append("Hausgeld (nicht umlagefähig)")
    if lk.get("instandhaltung_prozent_von_miete") is None:
        fehlend.append("Instandhaltung %")
    if fin.get("eigenkapital_eur") is None:
        fehlend.append("Eigenkapital")
    if fin.get("tilgung_prozent") is None:
        fehlend.append("Tilgung")
    r["fehlend"] = fehlend
    r["berechenbar"] = len(fehlend) == 0
    if not r["berechenbar"]:
        return r

    # --- Erwerb ---
    r["grESt"] = preis * kauf["grunderwerbsteuer_prozent"] / 100.0
    r["notar_grundbuch"] = preis * (kauf["notar_prozent"] + kauf.get("grundbuch_prozent", 0.0)) / 100.0
    r["makler"] = preis * kauf["makler_prozent"] / 100.0
    r["nebenkosten"] = r["grESt"] + r["notar_grundbuch"] + r["makler"] + kauf["sonstige_erwerbskosten_eur"]
    r["gesamtinvest"] = preis + r["nebenkosten"] + kauf["renovierung_eur"] + kauf["sanierung_eur"]
    r["kp_pro_m2"] = preis / flaeche if flaeche else 0.0
    r["gi_pro_m2"] = r["gesamtinvest"] / flaeche if flaeche else 0.0

    # --- Miete & laufende Kosten ---
    jahres_kalt = miete["kaltmiete_monatlich_eur"] * 12.0
    leerstand_faktor = 1.0 - miete["leerstand_wochen_pro_jahr"] / 52.0
    r["miete_effektiv"] = jahres_kalt * leerstand_faktor
    hg = lk["hausgeld_monatlich_eur"]
    hg_nicht_uml = lk["nicht_umlagefaehige_kosten_monatlich_eur"]
    r["hausgeld_umlagefaehig_jahr"] = max(0.0, hg - hg_nicht_uml) * 12.0  # trägt der Mieter
    r["hausgeld_nicht_uml_jahr"] = hg_nicht_uml * 12.0
    r["verwaltung_jahr"] = 0.0 if hg > 0 else jahres_kalt * lk["verwaltung_prozent_von_miete"] / 100.0
    r["instandhaltung_jahr"] = jahres_kalt * lk["instandhaltung_prozent_von_miete"] / 100.0
    r["netto_miete"] = (r["miete_effektiv"] - r["hausgeld_nicht_uml_jahr"]
                        - r["verwaltung_jahr"] - r["instandhaltung_jahr"])

    # --- Renditen ---
    r["brutto_rendite"] = jahres_kalt / preis * 100.0 if preis else 0.0
    r["netto_rendite"] = r["netto_miete"] / preis * 100.0 if preis else 0.0

    # --- Finanzierung ---
    ek = fin["eigenkapital_eur"]
    r["darlehen"] = max(0.0, r["gesamtinvest"] - ek)
    r["rate_monat"] = annuitaetenrate(r["darlehen"], fin["zinssatz_prozent"], fin["tilgung_prozent"])
    r["zins_jahr"] = r["darlehen"] * fin["zinssatz_prozent"] / 100.0
    r["cashflow_vor_monat"] = r["netto_miete"] / 12.0
    r["cashflow_nach_monat"] = r["cashflow_vor_monat"] - r["rate_monat"]
    r["cashflow_nach_jahr"] = r["cashflow_nach_monat"] * 12.0
    r["tilgungsanteil_jahr"] = max(0.0, r["rate_monat"] * 12.0 - r["zins_jahr"])
    r["ek_rendite"] = ((r["cashflow_nach_jahr"] + r["tilgungsanteil_jahr"]) / ek * 100.0) if ek else 0.0

    # --- Break-Even ---
    fix = r["hausgeld_nicht_uml_jahr"] + r["verwaltung_jahr"] + r["instandhaltung_jahr"]
    r["break_even_miete"] = (r["rate_monat"] * 12.0 + fix) / leerstand_faktor / 12.0 if leerstand_faktor > 0 else 0.0

    # --- Stress-Tests (jeweils einzeln) ---
    rate = r["rate_monat"]
    def netto(km_jahr: float, inst_faktor: float = 1.0, lf: float = leerstand_faktor) -> float:
        return km_jahr * lf - r["hausgeld_nicht_uml_jahr"] - r["verwaltung_jahr"] - r["instandhaltung_jahr"] * inst_faktor

    r["stress"] = [
        ("1) Miete −10 %", netto(jahres_kalt * 0.9) / 12.0 - rate),
        ("2) Leerstand +2 Monate", netto(jahres_kalt, lf=1.0 - (miete["leerstand_wochen_pro_jahr"] + 8.7) / 52.0) / 12.0 - rate),
        ("3) Instandhaltung +50 %", netto(jahres_kalt, inst_faktor=1.5) / 12.0 - rate),
        ("4) Zins +2,0 %-Punkte", r["cashflow_vor_monat"] - annuitaetenrate(r["darlehen"], fin["zinssatz_prozent"] + 2.0, fin["tilgung_prozent"])),
        ("5) Sanierung +10 % KP (finanziert)", r["cashflow_vor_monat"] - annuitaetenrate(r["darlehen"] + preis * 0.10, fin["zinssatz_prozent"], fin["tilgung_prozent"])),
        ("6) Wert −10 % (Einmaleffekt)", r["cashflow_nach_monat"]),
    ]

    # --- Szenarien A/B/C ---
    ek_quote_b = ek / r["gesamtinvest"] if r["gesamtinvest"] else 0.0
    def szenario(name: str, quote: float) -> dict:
        e = r["gesamtinvest"] * quote
        darl = max(0.0, r["gesamtinvest"] - e)
        rate = annuitaetenrate(darl, fin["zinssatz_prozent"], fin["tilgung_prozent"])
        cf = r["cashflow_vor_monat"] - rate
        cf_jahr = cf * 12.0
        tilg = max(0.0, rate * 12.0 - darl * fin["zinssatz_prozent"] / 100.0)
        return {"name": name, "ek_quote": quote * 100.0, "ek": e, "darlehen": darl,
                "rate": rate, "cashflow": cf, "ek_rendite": (cf_jahr + tilg) / e * 100.0 if e else 0.0}
    r["szenarien"] = [
        szenario("A – konservativ", min(1.0, ek_quote_b + 0.15)),
        szenario("B – ausgewogen (Eingaben)", ek_quote_b),
        szenario("C – hoher FK-Anteil", max(0.0, ek_quote_b - 0.15)),
    ]
    return r

# ---------------------------------------------------------------- Ausgabe ---
def eur(v) -> str:
    if v is None:
        return "–"
    return f"{v:,.0f} €".replace(",", "X").replace(".", ",").replace("X", ".")

def pct(v) -> str:
    if v is None:
        return "–"
    return f"{v:.2f} %".replace(".", ",")

def report(d: dict, r: dict) -> str:
    o = d.get("objekt", {})
    lines = []
    add = lines.append
    add("=" * 72)
    add(f"RECHENKERN-REPORT – {o.get('name', 'Objekt')}")
    add("=" * 72)
    add("")
    if not r.get("berechenbar"):
        add("⚪ ZU WENIG DATEN – Berechnung ausstehend")
        add("")
        add(f"Es fehlen noch {len(r['fehlend'])} Eingabe(n):")
        for f in r["fehlend"]:
            add(f"  • {f}")
        add("")
        add("Erst wenn alle Werte vorliegen, werden Rendite, Cashflow und")
        add("Maximalpreis berechnet. Keine erfundenen Zahlen – die Analyse")
        add("wartet auf belastbare Werte (Variante A).")
        add("")
        if d.get("annahmen"):
            add("HINWEISE / AUSSTEHENDE WERTE")
            for a in d["annahmen"]:
                add(f"  • {a}")
            add("")
        add("Hinweis: Modellrechnung – keine rechtliche, steuerliche oder finanzielle Beratung.")
        return "\n".join(lines)
    add("ERWERB")
    lines = []
    add = lines.append
    add("=" * 72)
    add(f"RECHENKERN-REPORT – {o.get('name', 'Objekt')}")
    add("=" * 72)
    add("")
    add("ERWERB")
    add(f"  Kaufpreis (Angebot)          {eur(d['kauf']['angebotspreis_eur'])}   [BELEGT/ANNAHME]")
    add(f"  + Grunderwerbsteuer          {eur(r['grESt'])}   ({d['kauf']['grunderwerbsteuer_prozent']} %)")
    add(f"  + Notar/Grundbuch            {eur(r['notar_grundbuch'])}   ({d['kauf']['notar_prozent']} %)")
    add(f"  + Makler                     {eur(r['makler'])}   ({d['kauf']['makler_prozent']} %)")
    add(f"  + Renovierung                {eur(d['kauf']['renovierung_eur'])}")
    add(f"  + Sanierung                  {eur(d['kauf']['sanierung_eur'])}")
    add(f"  + Sonstige Erwerbskosten     {eur(d['kauf']['sonstige_erwerbskosten_eur'])}")
    add(f"  = GESAMTINVESTITION          {eur(r['gesamtinvest'])}")
    if o.get("wohnflaeche_m2"):
        add(f"    Kaufpreis/m²: {eur(r['kp_pro_m2'])} · Gesamtinvest/m²: {eur(r['gi_pro_m2'])}")
    add("")
    add("RENDITE & CASHFLOW")
    add(f"  Kaltmiete/Jahr (effektiv)    {eur(r['miete_effektiv'])}   (Leerstand {d['miete']['leerstand_wochen_pro_jahr']} Wo.)")
    add(f"  − Hausgeld nicht umlagefähig {eur(r['hausgeld_nicht_uml_jahr'])}")
    add(f"  − Verwaltung                 {eur(r['verwaltung_jahr'])}")
    add(f"  − Instandhaltung             {eur(r['instandhaltung_jahr'])}")
    add(f"  = Netto-Mieteinnahmen/Jahr   {eur(r['netto_miete'])}")
    add(f"  Bruttomietrendite            {pct(r['brutto_rendite'])}")
    add(f"  Nettomietrendite             {pct(r['netto_rendite'])}")
    add(f"  Cashflow vor Finanzierung    {eur(r['cashflow_vor_monat'])}/Monat")
    add(f"  Finanzierungsrate            {eur(r['rate_monat'])}/Monat  (Darlehen {eur(r['darlehen'])})")
    cf = r["cashflow_nach_monat"]
    add(f"  Cashflow nach Finanzierung   {eur(cf)}/Monat  ({'POSITIV' if cf >= 0 else 'NEGATIV – Zuzahlung'})")
    add(f"  EK-Rendite (inkl. Tilgung)   {pct(r['ek_rendite'])}")
    add(f"  Break-Even-Kaltmiete         {eur(r['break_even_miete'])}/Monat")
    add("")
    add("FINANZIERUNGSSZENARIEN")
    add(f"  {'Szenario':<26}{'EK-Quote':>9}{'Rate/M':>10}{'CF/M':>10}{'EK-Rendite':>11}")
    for s in r["szenarien"]:
        add(f"  {s['name']:<26}{pct(s['ek_quote']):>9}{eur(s['rate']):>10}"
            f"{eur(s['cashflow']):>10}{pct(s['ek_rendite']):>11}"
            f"   (EK {eur(s['ek'])}, Darlehen {eur(s['darlehen'])})")
    add("")
    add("STRESS-TESTS (jeweils einzeln, Cashflow/Monat)")
    for name, cf_s in r["stress"]:
        flag = "🔴" if cf_s < -50 else ("🟠" if cf_s < 0 else ("🟡" if cf_s < r["cashflow_nach_monat"] - 100 else "🟢"))
        add(f"  {flag} {name:<38}{eur(cf_s):>12}  (Δ {eur(cf_s - r['cashflow_nach_monat'])})")
    add("")
    if d.get("annahmen"):
        add("ANNAHMEN")
        for a in d["annahmen"]:
            add(f"  • {a}")
        add("")
    if d.get("widersprueche"):
        add("⚠️  WIDERSPRÜCHE")
        for w in d["widersprueche"]:
            add(f"  • {w}")
        add("")
    add("Hinweis: Modellrechnung – keine rechtliche, steuerliche oder finanzielle Beratung.")
    return "\n".join(lines)

def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else None
    d = load_data(path)
    r = berechne(d)
    print(report(d, r))

if __name__ == "__main__":
    main()