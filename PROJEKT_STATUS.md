# 📋 Projekt-Status – Immobilien-Investment-Analyse

> **Zweck dieser Datei:** Laufender Bearbeitungsstand des Projekts. Wird nach **jeder** Bearbeitungs-Session vom Agent aktualisiert (User-Wunsch vom 18.09.2026).
> **Konventionen & Lessons Learned:** siehe `README.md` (Prozess) + Agent-Memory (`/memories/repo/immo-workspace.md`).

---

## 🕐 Letzter Stand

**Datum:** 18.09.2026
**Letzte Aktion:** Portfolio-Button „Aktualisieren" mit Handle-Merken (IndexedDB) versehen – keine erneute Ordner-Freigabe mehr nötig (nur 1× nach Browser-Neustart eine kurze Berechtigungs-Nachfrage).

---

## 📁 Objekte (Stand 18.09.2026)

| Objekt | Ordner | Status | Rating | Bemerkung |
|---|---|---|---|---|
| **Haarhausen** | `objekte/Haarhausen/` | ✅ Analysiert, Übersicht aktiv | **B (82)** | KP 179.000 € · BruttoR 9,12 % · CF +140 €/M · KM 1.360 € · EK 20.000 € |
| **Kerstenhausen** | `objekte/Kerstenhausen/` | ✅ Analysiert (18.09.), Übersicht aktiv | **D (41)** | KP 152.100 € · BruttoR 6,31 % · CF −350 €/M · KM 800 € (ANNAHME) · Status 🟠 VERHANDELN · 🔴 Grundbuch/Miete fehlen |
| ~~Arnsbach (Kerstenhausener Str.)~~ | ❌ gelöscht (18.09.) | aus DB per `prune` entfernt | war B (83) | Analyse-Daten ggf. aus Chat-Transkript rekonstruierbar |
| _VORLAGE | `objekte/_VORLAGE/` | Vorlage für neue Objekte | – | Übersicht + Analyse-MDs generisch |

---

## ✅ Was gebaut ist (chronologisch)

### Infrastruktur (16.09.)
- README-Prozess (16-stufiger Workflow), `_VORLAGE`-Struktur, `tools/kalkulation.html` (offline Tool), `tools/rechenkern.py` (identische Logik in Python, gegenseitig verifiziert)

### Objekt-Analysen (16.–17.09.)
- **Arnsbach** (16.09., 17.09. gelöscht): Vollanalyse mit Grundbuch-Risiken (≈114.724 € Belastungen!), Mietempfehlung 1.050 € (ABGELEITET), Status 🟡
- **Haarhausen** (17.09.): EFH BJ 1900, ⚡ Elektroheizung kritisch (Klasse G, ~17.000 €/Jahr Heizstrom ohne PV!), Status 🟢 WEITER PRÜFEN

### Objekt-Übersichten (Hybrid-Dateien, 17.09.)
- `<Objektname>_Übersicht.html` direkt im Objektordner: Eingaben oben, Ergebnisse live darunter
- Auto-Sync: State-JSON in den Objektordner per File System Access API (Handle in IndexedDB `immo-fs-handles`/`immo-root`)
- Tooltips (TIPS-Objekt), Risiko-Tabelle editierbar, localStorage-Autosave, Reset/Export
- ✏️ **Editierbare Erklärungs-Tags** (18.09.): die 16 `.tag`-Spans unter den Eingabefeldern sind `contenteditable` + `data-persist="tag-<feld>"` → Quellen/Notizen direkt editierbar, ohne Hervorhebung; Persistenz über das data-persist-Muster (localStorage + State-JSON + DB-Sync)
- 🧹 **Vorlage komplett blanko** (18.09.): alle Haarhausen-Reste aus `objekte/_VORLAGE/Objektname_Übersicht.html` entfernt (Elektroheizung-Box, dq-Zeilen mit ES450/697 m²/BJ 1900/Heizstrom, CHECK24-/58.000 €-/893 €-Bezüge, Exposé-Seitenangaben) → generische Platzhalter „Quelle eintragen"; nur die NUTZER-VORGABEN bleiben als Defaults (grESt 6, notar 2, instand 10, leerstand 4, ek 20000, tilgung 2)

### Portfolio & DB (17.09.)
- `immo_datenbank.db` (SQLite) + `portfolio.html` (generiert) + `tools/db_manager.py`
- **Ein Befehl für alles:** `python tools/db_manager.py sync` (JSON→DB→portfolio.html)
- Rating A–F: BruttoR 25 % + CF 25 % + CoC 15 % + Risiko-Ampeln 20 % + Datenqualität 15 %
- `prune`-Befehl (18.09.): löscht DB-Einträge ohne Objektordner (`prune [--yes]`)

### Portfolio-Features (18.09.)
- 🔄 **Aktualisieren-Button**: liest Objektordner LIVE im Browser (kein Python nötig), berechnet Rating identisch zu db_manager.py in JS
- 🔑 **Handle-Merken**: Directory-Handle in IndexedDB (gleiche DB/Key wie Übersichten) → kein Picker mehr bei jedem Klick
- 📅 **BJ-Fix**: 1900 statt 1.900 (jahr()-Helper)
- 💾 **BruttoR/CF in DB**: import_json speichert sie jetzt in kalkulation-Tabelle (vorher immer „–")

---

## 🔧 Bekannte Eigenheiten / Wichtige Regeln

- **NIEMALS `localStorage.clear()`** auf User-Daten (hat einmal User-State zerstört)
- Chrome: Directory-Handle-Berechtigungen verfallen nach Browser-Neustart → 1 kurze Nachfrage nötig (nicht umgehbar)
- Übersichten schreiben State-JSON nur bei Eingabe-Events; ohne Ordner-Berechtigung läuft Auto-Sync still ins Leere
- JS-Falle: deutsche Anführungszeichen „…" in JS-Strings → SyntaxError; einfache '…' verwenden
- Playwright-Tests: input-Events nach value-Setzung manuell dispatchen; Script-Scope-Funktionen sind nicht auf `window`
- **Dynamische Tag-Texte unter Eingabefeldern: VERWORFEN** (18.09.) – statische, editierbare Tags genügen; nicht wieder vorschlagen
- **📈 Zins-Recherche-Regel** (18.09., Goldene Regel 12 in README.md): KEINE Beispiel-/Werbezahlen von Vergleichsportalen (CHECK24-Beispielrechnungen) als Kalkulationsbasis! Stattdessen echte Marktkonditionen recherchieren (konkrete Angebote: Vergleich.de/Dr. Klein, FMH, Bankkonditionen), Spanne bestes–schlechtestes dokumentieren + Bindungsdauer nennen. Realität 18.09.: 4,67–5,55 % (12/20 J.) vs. CHECK24-Beispiel 3,02–3,77 % (10 J.). Bei Recalc > 7 Tage alt: frisch prüfen; innerhalb 7 Tage: Wert weiterverwenden. Immer Datum + Quelle in der Datenqualität-Tabelle

---

## ⏭️ Offene Punkte / Nächste Schritte

- [ ] **Kerstenhausen:** 🔴 Grundbuchauszug anfordern · 🔴 Miet-/Nutzungssituation + Einliegerwohnung klären · 🟠 Besichtigung (Renovierungsumfang, Öl-Tank) · 🟠 Baujahr/Wohnfläche-Widersprüche klären · 🟡 Bankgespräch mit frischen Zinsen (Live-Recherche 18.09. deutet auf > 4,5 %)
- [ ] Optional: Sync-Status-Indikator in den Übersichten (zeigt, ob Auto-Sync wirklich geschrieben hat)

**❌ Verworfen (nicht wieder vorschlagen):**
- ~~Dynamische Tag-Texte unter den Eingabefeldern („Deine Eingabe · ursprünglich: X")~~ – User 18.09.: „so wie jetzt reicht es" – die statischen, editierbaren Tags genügen

---

## 🗂️ Wichtige Dateien

| Datei | Zweck |
|---|---|
| `README.md` | Prozessanleitung (16 Stufen, Checklisten, Goldene Regeln) |
| `portfolio.html` | Portfolio-Übersicht (generiert – nicht manuell editieren!) |
| `immo_datenbank.db` | SQLite-Zentralbank |
| `tools/db_manager.py` | DB-Manager: `sync` / `prune` / `list` / `check` / `export-json` |
| `tools/portfolio_generator.py` | Generiert portfolio.html aus der DB |
| `tools/kalkulation.html` | Generisches Kalkulationstool (für neue Objekte vor der Übersicht) |
| `tools/rechenkern.py` | Python-Rechenkern (identische Logik, Klartext-Report) |
| `objekte/<Name>/<Name>_Übersicht.html` | Hybrid-Übersicht pro Objekt (Eingaben + Ergebnisse + Auto-Sync) |
| `objekte/<Name>/analyse/` | Analyse-Dokumente (01–05) |
| `objekte/<Name>/unterlagen/` | Original-Dokumente |

---

*Diese Datei wird nach jeder Session aktualisiert. Letztes Update: 18.09.2026*