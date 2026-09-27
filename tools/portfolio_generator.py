#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Portfolio-Generator: Erzeugt die API-basierte Portfolio-Hülle.

Verwendung:
    python portfolio_generator.py
"""
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "portfolio.html"

def main():
    dashboard_css = (BASE / "assets" / "dashboard.css").read_text(encoding="utf-8")
    theme_js = (BASE / "assets" / "theme.js").read_text(encoding="utf-8")
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
  #importForm[hidden] {{ display: none !important; }}
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
<style>{dashboard_css}</style>
<script data-dashboard-theme>{theme_js}</script>
</head>
<body>
<div class="wrap">
  <h1>🏠 Immobilien-Portfolio</h1>
  <div class="sub" id="stand">Übersicht aller analysierten Objekte · Quelle: immo_datenbank.db · Live-Werte werden geladen</div>

  <div class="filter">
    <button class="aktiv" onclick="filtern('alle', this)">Alle</button>
    <button onclick="filtern('A', this)">Rating A</button>
    <button onclick="filtern('B', this)">Rating B</button>
    <button onclick="filtern('C', this)">Rating C</button>
    <button onclick="filtern('DF', this)">Rating D/F</button>
    <button class="sync" onclick="portfolioAktualisieren(this)">🔄 Aktualisieren</button>
    <button class="analyse" type="button" onclick="document.getElementById('importForm').hidden = !document.getElementById('importForm').hidden">🔗 Anzeigenlink importieren</button>
    <button class="analyse" onclick="neueObjekteAnalysieren(this)">➕ Neue Objekte analysieren</button>
  </div>
  <form id="importForm" hidden onsubmit="importListing(event)" style="margin:-6px 0 20px;display:flex;gap:8px;flex-wrap:wrap">
    <input id="listingUrl" type="url" required placeholder="https://www.immowelt.de/..." aria-label="Link zur Immobilienanzeige" style="flex:1 1 300px;min-height:44px;padding:8px 12px;border:1px solid var(--line);border-radius:10px">
    <button type="submit" class="btn">Anzeige prüfen und anlegen</button>
    <span id="importStatus" role="status" style="flex-basis:100%"></span>
  </form>

  <div class="grid" id="grid">
    <div class="sub">Lade aktuelle Objekte aus SQLite …</div>
  </div>

  <footer>
    ⚠️ Modellrechnungen – keine rechtliche, steuerliche oder finanzielle Beratung. 🔄 <b>Aktualisieren</b> liest aktuelle Werte direkt aus der Datenbank.
  </footer>
</div>
<script src="assets/portfolio_db.js"></script>
</body>
</html>"""
    OUT.write_text(html, encoding="utf-8")
    print("✓ portfolio.html generiert (API-Live-Ansicht)")

if __name__ == "__main__":
    main()
