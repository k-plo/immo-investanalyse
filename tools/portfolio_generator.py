#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Portfolio-Generator: Liest die SQLite-DB und erzeugt portfolio.html.

Verwendung:
    python portfolio_generator.py
"""
import sqlite3
from datetime import datetime
from pathlib import Path

BASE = Path(r"c:\Users\User\Meine Ablage\Immo\VS Code\Immo")
DB_PATH = BASE / "immo_datenbank.db"
OUT = BASE / "portfolio.html"

RATING_FARBE = {"A": "#1a7f4b", "B": "#2e7d32", "C": "#b9770e", "D": "#c25e12", "F": "#c0392b"}
RATING_BG = {"A": "#e2f5ea", "B": "#e8f5e9", "C": "#fdf3dd", "D": "#fdeadd", "F": "#fde2e0"}

def eur(v):
    if v is None:
        return "–"
    return f"{v:,.0f} €".replace(",", "X").replace(".", ",").replace("X", ".")

def pct(v):
    if v is None:
        return "–"
    return f"{v:.2f} %".replace(".", ",")

def fmt(v, d=0):
    if v is None:
        return "–"
    return f"{v:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")

def jahr(v):
    """Jahreszahl OHNE Tausenderpunkt (1900 statt 1.900)."""
    if v is None:
        return "–"
    return str(int(v))

def mieteProM2(o):
    """Miete €/m² als Zusatz unter Miete/Monat."""
    km, fl = o["kaltmiete"], o["wohnflaeche"]
    if km is None or not fl:
        return ""
    return f"≈ {km / fl:.2f} €/m²".replace(".", ",")

def eurProM2(value, flaeche):
    """Preiswert pro m²; bei unvollständigen Daten kein irreführendes Ergebnis."""
    if value is None or flaeche is None or flaeche <= 0:
        return "–"
    return eur(value / flaeche)

def objektDetails(objektart, grundstueck):
    """Zeigt Grundstück bei grundstücksbezogenen Objekten, sonst den Objekttyp."""
    art = (objektart or "").lower()
    if any(begriff in art for begriff in ("wohnung", "etw", "apartment")):
      return f"🏢 {objektart}"
    if grundstueck is not None and grundstueck > 0:
        return f"🌳 {fmt(grundstueck, 0)} m²"
    return f"🏠 {objektart}" if objektart else ""

def main():
    generated_iso = datetime.now().isoformat(timespec="seconds")
    generated_str = datetime.now().strftime("%d.%m.%Y %H:%M")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    objekte = conn.execute("""
        SELECT o.*, k.brutto_rendite, k.netto_rendite, k.cf_nach, k.coc,
               k.max_preis, k.spielraum, k.break_even_miete, k.gesamtinvest,
               k.kaltmiete, k.ek, k.zins, k.tilgung, k.rate,
               r.gesamt_rating, r.punkte, o.geaendert_am
        FROM objekte o
        LEFT JOIN kalkulation k ON k.objekt_id = o.id
        LEFT JOIN rating r ON r.objekt_id = o.id
        ORDER BY r.punkte DESC
    """).fetchall()

    karten = []
    for o in objekte:
        g = o["gesamt_rating"] or "?"
        farbe = RATING_FARBE.get(g, "#5a6a85")
        bg = RATING_BG.get(g, "#e8ecf3")
        meta = {}
        try:
            import json
            meta_path = Path(o["json_pfad"]).parent / "analyse" / "03_kalkulation.json"
            if meta_path.exists():
                meta = json.loads(meta_path.read_text(encoding="utf-8")).get("objekt", {})
        except (OSError, ValueError, TypeError):
            pass
        details = objektDetails(o["objektart"], meta.get("grundstuecksflaeche_m2"))
        karten.append(f"""
    <div class="karte" onclick="window.location.href=encodeURIComponent('objekte/{o['name']}/{Path(o['html_pfad']).name if o['html_pfad'] else ''}').replace(/%2F/g, '/')" style="cursor:pointer">
      <div class="karte-head">
        <div class="karte-name">{o['name']}</div>
        <div class="rating-badge" style="background:{bg};color:{farbe}">{g}</div>
      </div>
      <div class="karte-sub">{o['objektart'] or ''} · {o['adresse'] or ''}</div>
      <div class="karte-details">
        <span>📐 {fmt(o['wohnflaeche'], 0)} m²</span>
        <span>📅 BJ {jahr(o['baujahr'])}</span>
        <span>🛏 {fmt(o['zimmer'], 0)} Zi.</span>
        <span>{details}</span>
      </div>
      <div class="karte-kpis">
        <div><span class="l">Kaufpreis</span><span class="v">{eur(o['kaufpreis'])}</span><span class="s">{eurProM2(o['kaufpreis'], o['wohnflaeche'])} /m²</span></div>
        <div><span class="l">Gesamtinvest</span><span class="v">{eur(o['gesamtinvest'])}</span><span class="s">{eurProM2(o['gesamtinvest'], o['wohnflaeche'])} /m²</span></div>
        <div><span class="l">BruttoR</span><span class="v">{pct(o['brutto_rendite'])}</span></div>
        <div><span class="l">CF/M</span><span class="v">{eur(o['cf_nach'])}</span></div>
      </div>
      <div class="karte-fin">
        <div><span class="l">Miete/Monat</span><span class="v">{eur(o['kaltmiete'])}</span><span class="s">{mieteProM2(o)}</span></div>
        <div><span class="l">Finanzierung</span><span class="v">{eur(o['ek'])} EK · {pct(o['zins'])} · {pct(o['tilgung'])} Tilg.</span></div>
      </div>
    </div>""")

    html = f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Immobilien-Portfolio</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: "Segoe UI", Arial, sans-serif; font-size: 13px; color: #1a2332; background: #e8edf4; padding: 24px 14px 60px; }}
  .wrap {{ max-width: 1100px; margin: 0 auto; }}
  h1 {{ font-size: 26px; margin-bottom: 4px; }}
  .sub {{ color: #5a6a85; font-size: 12px; margin-bottom: 18px; }}
  .filter {{ display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; }}
  .filter button {{ background: #fff; border: 1px solid #c9d4e6; border-radius: 20px; padding: 6px 14px; font-size: 12px; cursor: pointer; }}
  .filter button.aktiv {{ background: #1a4fa0; color: #fff; border-color: #1a4fa0; }}
  .filter button.sync {{ background: #1a4fa0; color: #fff; border-color: #1a4fa0; margin-left: auto; font-weight: 600; }}
  .filter button.sync:disabled {{ opacity: .55; cursor: wait; }}
  .filter button.analyse {{ flex-basis: 100%; text-align: left; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 16px; }}
  .karte {{ background: #fff; border-radius: 12px; padding: 18px 20px; box-shadow: 0 3px 12px rgba(15,20,32,.10); transition: transform .15s; }}
  .karte:hover {{ transform: translateY(-3px); box-shadow: 0 6px 18px rgba(15,20,32,.15); }}
  .karte-head {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; }}
  .karte-name {{ font-size: 15px; font-weight: 700; }}
  .rating-badge {{ font-size: 20px; font-weight: 800; border-radius: 10px; padding: 6px 14px; }}
  .karte-sub {{ color: #5a6a85; font-size: 11px; margin: 4px 0 10px; }}
  .karte-details {{ display: flex; gap: 14px; flex-wrap: wrap; font-size: 11px; color: #3a4a65; margin-bottom: 10px; }}
  .karte-kpis {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 10px; }}
  .karte-kpis div {{ background: #f8fafd; border: 1px solid #e3eaf4; border-radius: 8px; padding: 7px 9px; }}
  .karte-kpis span {{ display: block; }}
  .karte-kpis .l {{ font-size: 8.5px; color: #5a6a85; text-transform: uppercase; letter-spacing: .04em; }}
  .karte-kpis .v {{ font-size: 14px; font-weight: 700; margin-top: 2px; }}
  .karte-fin {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 10px; }}
  .karte-fin div {{ background: #f4f8fd; border: 1px solid #e3eaf4; border-radius: 8px; padding: 7px 9px; }}
  .karte-fin span {{ display: block; }}
  .karte-fin .l {{ font-size: 8.5px; color: #5a6a85; text-transform: uppercase; letter-spacing: .04em; }}
  .karte-fin .v {{ font-size: 12px; font-weight: 600; margin-top: 2px; }}
  .karte-fin .s {{ font-size: 9px; color: #5a6a85; margin-top: 1px; }}
  .karte-datum {{ font-size: 9px; color: #a5b1c4; margin-top: 6px; }}
  footer {{ margin-top: 24px; color: #7a879c; font-size: 10px; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>🏠 Immobilien-Portfolio</h1>
  <div class="sub" id="stand">Übersicht aller analysierten Objekte · Stand: {generated_str} · Quelle: immo_datenbank.db</div>

  <div class="filter">
    <button class="aktiv" onclick="filtern('alle', this)">Alle</button>
    <button onclick="filtern('A', this)">Rating A</button>
    <button onclick="filtern('B', this)">Rating B</button>
    <button onclick="filtern('C', this)">Rating C</button>
    <button onclick="filtern('DF', this)">Rating D/F</button>
    <button class="sync" onclick="portfolioAktualisieren(this)">🔄 Aktualisieren</button>
    <button class="analyse" onclick="neueObjekteAnalysieren(this)">➕ Neue Objekte analysieren</button>
  </div>

  <div class="grid" id="grid">
    {''.join(karten)}
  </div>

  <footer>
    ⚠️ Modellrechnungen – keine rechtliche, steuerliche oder finanzielle Beratung. 🔄 <b>Aktualisieren</b> liest die Objektordner live im Browser: gelöschte Ordner verschwinden, geänderte Werte + Ratings erscheinen sofort. <code>python tools/db_manager.py sync</code> aktualisiert zusätzlich DB + diese Datei.
  </footer>
</div>
<script>
const GENERATED_ISO = "{generated_iso}";
function filtern(rating, btn) {{
  document.querySelectorAll('.filter button').forEach(b => b.classList.remove('aktiv'));
  btn.classList.add('aktiv');
  document.querySelectorAll('.karte').forEach(k => {{
    const badge = k.querySelector('.rating-badge');
    const r = badge ? badge.textContent.trim() : '';
    k.style.display = (rating === 'alle' || (rating === 'DF' ? ['D','F'].includes(r) : r === rating)) ? '' : 'none';
  }});
}}

// ---------- Live-Aktualisierung (File System Access API) ----------
// Liest die State-JSONs der Objektordner direkt im Browser und berechnet
// Rating + KPIs identisch zu db_manager.py neu. Kein Python nötig.
const RATING_FARBE = {{ A: "#1a7f4b", B: "#2e7d32", C: "#b9770e", D: "#c25e12", F: "#c0392b" }};
const RATING_BG = {{ A: "#e2f5ea", B: "#e8f5e9", C: "#fdf3dd", D: "#fdeadd", F: "#fde2e0" }};
const AMPEL_PUNKTE = {{ "🟢": 100, "🟡": 70, "🟠": 40, "🔴": 10 }};

function num(x) {{
  if (x === null || x === undefined || x === "") return null;
  const v = parseFloat(x);
  return isNaN(v) ? null : v;
}}
function eurJs(v) {{
  if (v === null || v === undefined) return "–";
  return v.toLocaleString("de-DE", {{ maximumFractionDigits: 0 }}) + " €";
}}
function pctJs(v) {{
  if (v === null || v === undefined) return "–";
  return v.toLocaleString("de-DE", {{ minimumFractionDigits: 2, maximumFractionDigits: 2 }}) + " %";
}}
function mieteProM2Js(o) {{
  if (o.kaltmiete == null || !o.wohnflaeche) return "";
  return "≈ " + (o.kaltmiete / o.wohnflaeche).toLocaleString("de-DE", {{ minimumFractionDigits: 2, maximumFractionDigits: 2 }}) + " €/m²";
}}
function eurProM2Js(value, flaeche) {{
  if (value === null || value === undefined || flaeche === null || flaeche === undefined || flaeche <= 0) return "–";
  return eurJs(value / flaeche);
}}
function objektDetailsJs(objektart, grundstueck) {{
  const art = (objektart || "").toLowerCase();
  if (["wohnung", "etw", "apartment"].some(begriff => art.includes(begriff))) return "🏢 " + objektart;
  if (grundstueck !== null && grundstueck !== undefined && grundstueck > 0) return "🌳 " + Math.round(grundstueck).toLocaleString("de-DE") + " m²";
  return objektart ? "🏠 " + objektart : "";
}}
function noteRendite(v) {{
  if (v === null) return ["F", 0];
  if (v >= 8) return ["A", 100];
  if (v >= 6) return ["B", 80];
  if (v >= 4) return ["C", 60];
  if (v >= 2) return ["D", 35];
  return ["F", 0];
}}
function noteCashflow(v) {{
  if (v === null) return ["F", 0];
  if (v >= 100) return ["A", 100];
  if (v >= 0) return ["B", 75];
  if (v >= -50) return ["C", 45];
  if (v >= -150) return ["D", 20];
  return ["F", 0];
}}
function noteCoc(v) {{
  if (v === null) return ["F", 0];
  if (v >= 15) return ["A", 100];
  if (v >= 8) return ["B", 80];
  if (v >= 3) return ["C", 55];
  return ["F", 0];
}}
function noteRisiko(ampeln) {{
  if (!ampeln.length) return ["C", 55];
  const p = ampeln.reduce((s, a) => s + (AMPEL_PUNKTE[a] ?? 55), 0) / ampeln.length;
  if (p >= 85) return ["A", p];
  if (p >= 65) return ["B", p];
  if (p >= 45) return ["C", p];
  if (p >= 40) return ["D", p];
  return ["F", p];
}}
function noteDatenqualitaet(s) {{
  const felder = ["preis", "flaeche", "renovierung", "sanierung", "grESt", "notar",
    "makler", "kaltmiete", "hausgeld", "hausgeldNichtUml", "instand",
    "leerstand", "ek", "zins", "tilgung"];
  const belegt = new Set(["preis", "flaeche", "grESt", "notar", "makler", "zins"]);
  const gefuellt = felder.filter(f => (s[f] !== null && s[f] !== undefined && s[f] !== "" && s[f] !== "0") || belegt.has(f)).length;
  let p = gefuellt / felder.length * 100;
  const offeneRot = Object.keys(s).filter(k => k.startsWith("p_op") && k.endsWith("t")
    && String(s[k]).includes("🔴") && !s[k.slice(0, -1)]).length;
  p = Math.max(0, p - offeneRot * 5);
  if (p >= 85) return ["A", p];
  if (p >= 65) return ["B", p];
  if (p >= 45) return ["C", p];
  if (p >= 25) return ["D", p];
  return ["F", p];
}}
function berechneRatingJs(s, risiken) {{
  const km = num(s.kaltmiete), preis = num(s.preis);
  const felder = ["preis", "flaeche", "renovierung", "sanierung", "grESt", "notar",
    "makler", "sonstige", "kaltmiete", "hausgeld", "hausgeldNichtUml",
    "instand", "leerstand", "ek", "zins", "tilgung"];
  const wert = feld => num(s[feld]) ?? 0;
  const brutto = preis > 0 ? km * 12 / preis * 100 : null;
  const ek = num(s.ek), zins = num(s.zins), tilg = num(s.tilgung);
  const lf = 1 - wert("leerstand") / 52;
  const hg = wert("hausgeldNichtUml");
  const hgTotal = wert("hausgeld");
  const inst = wert("instand") / 100;
  let cfNach = null, coc = null, gesamtinvest = null;
  if (preis > 0 && wert("flaeche") > 0) {{
    const nk = wert("grESt") + wert("notar") + wert("makler");
    const fix = wert("renovierung") + wert("sanierung") + wert("sonstige");
    const nettoJahr = km * 12 * lf - hg * 12 - (hgTotal > 0 ? 0 : km * 12 * 0.03) - km * 12 * inst;
    const cfVor = nettoJahr / 12;
    const gesamt = preis * (1 + nk / 100) + fix;
    const darlehen = Math.max(0, gesamt - ek);
    const rate = darlehen * (zins + tilg) / 100 / 12;
    cfNach = cfVor - rate;
    if (ek) {{
      const zinsJahr = darlehen * zins / 100;
      const tilgJahr = Math.max(0, rate * 12 - zinsJahr);
      coc = (cfNach * 12 + tilgJahr) / ek * 100;
    }}
  }}
  const [n1, p1] = noteRendite(brutto);
  const [n2, p2] = noteCashflow(cfNach);
  const [n3, p3] = noteCoc(coc);
  const [n4, p4] = noteRisiko(risiken.map(r => r[2]));
  const [n5, p5] = noteDatenqualitaet(s);
  const punkte = p1 * 0.25 + p2 * 0.25 + p3 * 0.15 + p4 * 0.20 + p5 * 0.15;
  const g = punkte >= 85 ? "A" : punkte >= 70 ? "B" : punkte >= 55 ? "C" : punkte >= 40 ? "D" : "F";
  return {{ brutto, cfNach, coc, punkte, g, gesamtinvest }};
}}
function karteHtml(o) {{
  const farbe = RATING_FARBE[o.g] || "#5a6a85";
  const bg = RATING_BG[o.g] || "#e8ecf3";
  const jahrTxt = o.baujahr != null ? String(Math.round(o.baujahr)) : "–";
  const zi = o.zimmer != null ? Math.round(o.zimmer) : "–";
  const wm = o.wohnflaeche != null ? Math.round(o.wohnflaeche) : "–";
  const href = encodeURIComponent('objekte/' + o.name + '/' + (o.htmlName || '')).replace(/%2F/g, '/');
  return `
    <div class="karte" onclick="window.location.href='${{href}}'" style="cursor:pointer">
      <div class="karte-head">
        <div class="karte-name">${{o.name}}</div>
        <div class="rating-badge" style="background:${{bg}};color:${{farbe}}">${{o.g}}</div>
      </div>
      <div class="karte-sub">${{o.objektart || ''}} · ${{o.adresse || ''}}</div>
      <div class="karte-details">
        <span>📐 ${{wm}} m²</span>
        <span>📅 BJ ${{jahrTxt}}</span>
        <span>🛏 ${{zi}} Zi.</span>
        <span>${{objektDetailsJs(o.objektart, o.grundstuecksflaeche)}}</span>
      </div>
      <div class="karte-kpis">
        <div><span class="l">Kaufpreis</span><span class="v">${{eurJs(o.kaufpreis)}}</span><span class="s">${{eurProM2Js(o.kaufpreis, o.wohnflaeche)}} /m²</span></div>
        <div><span class="l">Gesamtinvest</span><span class="v">${{eurJs(o.gesamtinvest)}}</span><span class="s">${{eurProM2Js(o.gesamtinvest, o.wohnflaeche)}} /m²</span></div>
        <div><span class="l">BruttoR</span><span class="v">${{pctJs(o.brutto)}}</span></div>
        <div><span class="l">CF/M</span><span class="v">${{eurJs(o.cfNach)}}</span></div>
      </div>
      <div class="karte-fin">
        <div><span class="l">Miete/Monat</span><span class="v">${{eurJs(o.kaltmiete)}}</span><span class="s">${{mieteProM2Js(o)}}</span></div>
        <div><span class="l">Finanzierung</span><span class="v">${{eurJs(o.ek)}} EK · ${{pctJs(o.zins)}} · ${{pctJs(o.tilgung)}} Tilg.</span></div>
      </div>
    </div>`;
}}
async function neueObjekteAnalysieren(btn) {{
  if (!window.showDirectoryPicker) {{
    alert("Dein Browser unterstützt die Ordnerauswahl nicht. Bitte Chrome oder Edge verwenden.");
    return;
  }}
  btn.disabled = true;
  try {{
    const root = await getRootDir();
    const objekteDir = await root.getDirectoryHandle("objekte", {{ create: false }});
    const neu = [];
    for await (const [name, handle] of objekteDir.entries()) {{
      if (handle.kind !== "directory" || name.startsWith("_")) continue;
      let hatState = false, unterlagen = [];
      for await (const [fn, fh] of handle.entries()) {{
        if (fh.kind === "file" && fn.endsWith("_Übersicht_State.json")) hatState = true;
        if (fh.kind === "directory" && fn === "unterlagen") {{
          for await (const [docName, docHandle] of fh.entries()) if (docHandle.kind === "file") unterlagen.push(docName);
        }}
      }}
      if (!hatState && unterlagen.length) neu.push(name + " (" + unterlagen.length + " Unterlage(n))");
    }}
    if (!neu.length) {{
      alert("Keine neuen Objektordner mit Unterlagen gefunden. Bereits importierte Objekte werden über ihr State-JSON übersprungen.");
    }} else {{
      alert("Neue Objektordner erkannt:\\n\\n" + neu.join("\\n") + "\\n\\nBitte den bestehenden Dokumenten-/KI-Analyseprozess für diese Ordner durchführen. Nach dem erzeugten State-JSON übernimmt 'Aktualisieren' den bestehenden Import-, Berechnungs- und Ratingpfad.");
    }}
  }} catch (e) {{
    if (e.name !== "AbortError") alert("Ordnerprüfung fehlgeschlagen: " + e.message);
  }} finally {{
    btn.disabled = false;
  }}
}}

async function portfolioAktualisieren(btn) {{
  if (!window.showDirectoryPicker) {{
    alert("Dein Browser unterstützt die File System Access API nicht (nur Chrome/Edge).\\n\\nAlternativ: python tools/db_manager.py sync im Terminal.");
    return;
  }}
  btn.disabled = true;
  const alt = btn.textContent;
  btn.textContent = "⏳ Lese Ordner …";
  try {{
    const root = await getRootDir();
    const objekteDir = await root.getDirectoryHandle("objekte", {{ create: false }});
    const objekte = [];
    for await (const [name, handle] of objekteDir.entries()) {{
      if (handle.kind !== "directory" || name.startsWith("_")) continue;
      let state = null, meta = {{}}, htmlName = null;
      try {{
        for await (const [fn, fh] of handle.entries()) {{
          if (fh.kind === "file" && fn.endsWith("_Übersicht_State.json")) {{
            state = JSON.parse(await fh.getFile().then(f => f.text()));
          }}
          if (fh.kind === "file" && fn.endsWith("_Übersicht.html")) htmlName = fn;
        }}
        const kal = await handle.getDirectoryHandle("analyse", {{ create: false }});
        for await (const [fn, fh] of kal.entries()) {{
          if (fn === "03_kalkulation.json") {{
            meta = (JSON.parse(await fh.getFile().then(f => f.text())).objekt) || {{}};
          }}
        }}
      }} catch (e) {{ /* Ordner ohne State überspringen */ }}
      if (!state) continue;
      const risiken = state._risiken || [];
      const r = berechneRatingJs(state, risiken);
      const preis = num(state.preis), fl = num(state.flaeche);
      objekte.push({{
        name, htmlName,
        objektart: meta.objektart || "", adresse: meta.adresse || "",
        grundstuecksflaeche: num(meta.grundstuecksflaeche_m2),
        baujahr: num(meta.baujahr), zimmer: num(meta.zimmer), stellplaetze: num(meta.stellplaetze),
        kaufpreis: preis, wohnflaeche: fl,
        gesamtinvest: r.gesamtinvest,
        brutto: r.brutto, cfNach: r.cfNach,
        kaltmiete: num(state.kaltmiete), ek: num(state.ek), zins: num(state.zins), tilgung: num(state.tilgung),
        g: r.g, punkte: r.punkte,
        geaendert: state._synced_am || state.geaendert_am || null
      }});
    }}
    objekte.sort((a, b) => b.punkte - a.punkte);
    document.getElementById("grid").innerHTML = objekte.map(karteHtml).join("");
    document.getElementById("stand").innerHTML =
      "Übersicht aller analysierten Objekte · Live-Stand: " + new Date().toLocaleString("de-DE", {{ dateStyle: "short", timeStyle: "short" }}) +
      " · " + objekte.length + " Objekt(e) · Quelle: Objektordner (live gelesen)";
    if (!objekte.length) {{
      document.getElementById("grid").innerHTML = '<div style="color:#5a6a85;padding:20px">Keine Objekte mit State-JSON gefunden.</div>';
    }}
    btn.textContent = "✓ Aktualisiert";
  }} catch (e) {{
    if (e.name === "AbortError") {{ btn.textContent = alt; }}
    else {{
      alert("Aktualisierung fehlgeschlagen: " + e.message + "\\n\\nBitte den IMMO-Hauptordner wählen (der mit 'objekte' und 'tools').");
      btn.textContent = alt;
    }}
  }}
  btn.disabled = false;
}}

// ---------- Ordner-Handle merken (IndexedDB, gleiche DB wie die Übersichten) ----------
// Nach einmaliger Freigabe läuft "Aktualisieren" ohne erneute Ordner-Auswahl.
const IDB_NAME = "immo-fs-handles";
function idbOpen() {{
  return new Promise((res, rej) => {{
    const req = indexedDB.open(IDB_NAME, 1);
    req.onupgradeneeded = () => req.result.createObjectStore("handles");
    req.onsuccess = () => res(req.result);
    req.onerror = () => res(null);
  }});
}}
async function idbSet(key, val) {{
  const db = await idbOpen();
  if (!db) return;
  return new Promise((res) => {{
    const tx = db.transaction("handles", "readwrite");
    tx.objectStore("handles").put(val, key);
    tx.oncomplete = res;
  }});
}}
async function idbGet(key) {{
  const db = await idbOpen();
  if (!db) return null;
  return new Promise((res) => {{
    const req = db.transaction("handles").objectStore("handles").get(key);
    req.onsuccess = () => res(req.result || null);
    req.onerror = () => res(null);
  }});
}}
let rootHandle = null;
async function getRootDir() {{
  if (rootHandle) return rootHandle;
  // 1. Gespeicherten Handle aus IndexedDB laden (gleicher Key wie Übersichten)
  const saved = await idbGet("immo-root");
  if (saved) {{
    const perm = await saved.queryPermission({{ mode: "read" }});
    if (perm === "granted") {{ rootHandle = saved; return rootHandle; }}
    // Berechtigung weg (z. B. nach Browser-Neustart): einmalig neu anfragen
    const req = await saved.requestPermission({{ mode: "read" }});
    if (req === "granted") {{ rootHandle = saved; return rootHandle; }}
  }}
  // 2. Neuen Handle anfordern – User muss den IMMO-Hauptordner wählen
  const h = await window.showDirectoryPicker({{ id: "immo-root", mode: "read", startIn: "documents" }});
  await h.getDirectoryHandle("objekte", {{ create: false }}); // wirft, wenn falscher Ordner
  rootHandle = h;
  await idbSet("immo-root", h);
  return rootHandle;
}}
async function autoPortfolioAktualisieren() {{
  if (!window.showDirectoryPicker) return;
  try {{
    const saved = await idbGet("immo-root");
    if (!saved || await saved.queryPermission({{ mode: "read" }}) !== "granted") return;
    await portfolioAktualisieren(document.querySelector("button.sync"));
  }} catch (e) {{ /* Manuelle Aktualisierung bleibt verfügbar. */ }}
}}
autoPortfolioAktualisieren();
</script>
</body>
</html>"""
    OUT.write_text(html, encoding="utf-8")
    print(f"✓ portfolio.html generiert ({len(objekte)} Objekte)")
    conn.close()

if __name__ == "__main__":
    main()