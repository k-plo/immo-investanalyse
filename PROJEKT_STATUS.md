# 📋 Projekt-Status – Immobilien-Investment-Analyse

> **Zweck dieser Datei:** Laufender Bearbeitungsstand des Projekts. Wird nach **jeder** Bearbeitungs-Session vom Agent aktualisiert (User-Wunsch vom 18.09.2026).
> **Konventionen & Lessons Learned:** siehe `README.md` (Prozess) + Agent-Memory (`/memories/repo/immo-workspace.md`).

---

## 🕐 Letzter Stand

**Datum:** 25.09.2026
**Letzte Aktion:** Lokaler Bugfix-Durchlauf für Rechenkern, HTML-Kalkulation und DB-Sync. Projektpfade sind nun plattformunabhängig; SQLite-Sync und Portfolio-Generator laufen im aktuellen Projektordner. JSON-Schemata werden kompatibel verarbeitet, Finanzierungsnebenkosten/Sonderumlagen eingerechnet, dynamische Listen vollständig synchronisiert, DB-Restore und Hash-Konsistenzprüfung vervollständigt sowie importierte HTML-Inhalte abgesichert.

---

## 📁 Objekte (Stand 25.09.2026)

| Objekt | Ordner | Status | Rating | Bemerkung |
|---|---|---|---|---|
| **Haarhausen** | `objekte/_ARCHIV/Haarhausen/` | 🗄️ Analysiert, archiviert | **C (61)** | Aus aktivem Portfolio ausgeblendet; State und Analyse bleiben erhalten |
| **Kerstenhausen** | `objekte/Kerstenhausen/` | ✅ Analysiert, Übersicht aktiv | **C (56)** | KP 152.100 € · BruttoR 7,89 % · CF −53 €/M · KM 1.000 € · 🔴 Grundbuch/Miete weiterhin zu klären |
| **Arnsbach** | `objekte/Arnsbach/` | 🟡 Analysiert, Übersicht aktiv | **D (47)** | KP 159.000 € · BruttoR 7,92 % · CF −188 €/M · Grundbuch- und WEG-Risiken offen |
| _VORLAGE | `objekte/_VORLAGE/` | Vorlage für neue Objekte | – | Übersicht + Analyse-MDs generisch |

---

## ✅ Was gebaut ist (chronologisch)

### Infrastruktur (16.09.)
- README-Prozess (16-stufiger Workflow), `_VORLAGE`-Struktur, `tools/kalkulation.html` (offline Tool), `tools/rechenkern.py` (identische Logik in Python, gegenseitig verifiziert)

### Objekt-Analysen (16.–17.09.)
- **Arnsbach** (16.09. analysiert, am 23.09. wieder unter `objekte/Arnsbach/` eingeordnet): Analyse-Dateien 01–05 neu abgelegt. Grundbuchrisiken von nominal ca. 114.724 €, Sanierungs- und WEG-Kosten offen; Mietorientierung 1.050 € nur als Hypothese. Status 🟡
- **Haarhausen** (17.09.): EFH BJ 1900, ⚡ Elektroheizung kritisch (Klasse G, ~17.000 €/Jahr Heizstrom ohne PV!), Status 🟢 WEITER PRÜFEN

### Objekt-Übersichten (Hybrid-Dateien, 17.09.)
- `<Objektname>_Übersicht.html` direkt im Objektordner: Eingaben oben, Ergebnisse live darunter
- **Verbindliche Regel (23.09.):** Jede neue Objektanalyse erzeugt immer die fünf Analyse-Dateien unter `analyse/` **plus** eine eigene `<Objektname>_Übersicht.html` direkt im Objektordner. Bei vorhandenen belastbaren Eingabewerten wird zusätzlich die passende `<Objektname>_Übersicht_State.json` angelegt; fehlende Werte bleiben leer bzw. ausstehend.
- **Arnsbach nachgezogen (23.09.):** `objekte/Arnsbach/Arnsbach_Übersicht.html` und `Arnsbach_Übersicht_State.json` erstellt; bekannte Werte aus Exposé/Analyse eingetragen, Miet-, WEG- und Finanzierungswerte bewusst offen gelassen.
- **Arnsbach Werte ergänzt (23.09.):** Kaltmiete 1.050 €/M als abgeleitete Orientierung, Zins 3,96 % für 10 Jahre Sollzinsbindung nach Dr.-Klein-Recherche vom 23.09.2026 sowie Nutzer-Vorgaben direkt in Übersicht, State und `03_kalkulation.json` eingetragen. Hausgeld, nicht umlagefähige Kosten, Renovierung und Sanierung bleiben offen.
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

### Portfolio-Erweiterung (23.09.)
- 🆕 **Neue Objekte analysieren**: Button prüft den festen Ordner `objekte/`, überspringt bereits importierte Objektordner mit State-JSON und erkennt neue Ordner mit Unterlagen. Der vorhandene Dokumenten-/KI-Analyseprozess muss weiterhin manuell durchgeführt werden; nach Erstellung des State-JSON übernimmt „Aktualisieren“ den bestehenden Importpfad.
- 🏡 **Objektbezogene Kartendetails**: Häuser zeigen die positive Grundstücksfläche aus `analyse/03_kalkulation.json`; Wohnungen zeigen stattdessen den Objekttyp, damit WEG-Gesamtflächen nicht irreführend als eigene Grundstücksfläche erscheinen.
- 💰 **Preiskennzahlen**: Kaufpreis und Gesamtinvestition zeigen zusätzlich den jeweiligen Wert pro Wohnfläche. Die bestehende Mietpreis-€/m²-Anzeige bleibt erhalten.
- 🧹 **Kartenbereinigung**: „Letzte Änderung“ und Stellplätze werden nicht mehr in den Karten angezeigt; Datenbankfelder und Importdaten bleiben unverändert.
- 🔧 **Generator/Validierung**: `tools/portfolio_generator.py` und `tools/db_manager.py` kompilieren fehlerfrei; `portfolio.html` wurde erfolgreich neu generiert und ohne HTML-/JavaScript-Diagnosefehler geprüft.
- 🔄 **Portfolio-Auto-Sync (23.09.)**: `portfolio.html` gleicht beim Öffnen automatisch mit dem bereits freigegebenen Objektordner ab; `tools/portfolio_generator.py` erzeugt diesen Mechanismus bei jeder Neugenerierung mit. Neue Objekte mit State-JSON können dadurch nicht mehr nur wegen einer veralteten statischen Portfolio-Datei fehlen.
- 🔄 **Live-Synchronisation (24.09.)**: Ursache der Abweichungen war der parallele browsergebundene `localStorage`-State gegenüber der statischen DB-Kopie in `portfolio.html`. Übersichten senden ihren State jetzt per `BroadcastChannel`; das Portfolio aktualisiert die betroffene Karte sofort und übernimmt beim Start vorhandene States mit Objektordner-Kennung. Generator und Vorlage enthalten denselben Datenfluss.
- 🗄️ **Archivieren (24.09.)**: Jede Objektübersicht hat neben den vorhandenen Kopf-Buttons einen Archivieren-Button. Nach Bestätigung wird der komplette Ordner rekursiv nach `objekte/_ARCHIV/<Name>/` kopiert und erst danach aus dem aktiven Ordner entfernt. Der DB-Sync erkennt den Archivpfad, setzt `status='archiviert'`, `prune` schützt ihn und der Portfolio-Generator filtert ihn aus. Archivierte Übersichten bleiben unverändert und werden nicht von aktiven Formatänderungen erfasst.
- ↩️ **Reaktivieren (24.09.)**: Übersichten im `_ARCHIV`-Pfad schalten denselben Button automatisch auf „Reaktivieren“. Der vollständige Ordner wird nach Prüfung eines freien aktiven Pfads zurückverschoben; der Archivordner wird erst nach erfolgreichem Kopieren entfernt.
- 🧮 **Einheitliche Portfolio-Rechnung (23.09.)**: `db_manager.py`, der Live-Rechner in `portfolio.html` und die Objektübersicht verwenden dieselben Formeln. Nach Nutzerentscheidung werden leere Eingabefelder in allen drei Rechenpfaden als 0 behandelt; Arnsbach und die Vorlage schreiben Änderungen zusätzlich automatisch in den State-JSON.

### Lokale Stabilisierung (25.09.)
- 🛠️ **Plattformunabhängige Pfade:** Python-Tools und Extraktionshelfer leiten den Projektordner aus `__file__` ab; keine fest codierten Windows-Pfade mehr.
- 🗄️ **DB-Sync/Restore:** SQLite speichert Roh-State und JSON-Hash, importiert auch dynamische offene Punkte/Schritte und exportiert nur bei exaktem Objektnamen an den gespeicherten Pfad zurück. `check` vergleicht nun tatsächlich Datei- und DB-Hash.
- 🧮 **Rechenkern/HTML:** Flache und verschachtelte JSON-Dateien sind kompatibel. Finanzierungsnebenkosten und geplante Sonderumlagen fließen in Gesamtinvestition, Darlehen und Rate ein.
- 🔐 **Sichere Darstellung:** Importierte Texte und Portfolio-Metadaten werden nicht mehr ungefiltert als ausführbares HTML eingesetzt.
- ✅ **Verifikation:** Lokaler Sync mit Arnsbach, Kerstenhausen und archiviertem Haarhausen; Python-/JavaScript-Syntax, Rechenwirkung, dynamische Listen, Restore und Konsistenzprüfung getestet.

---

## 🔧 Bekannte Eigenheiten / Wichtige Regeln

- **Designstandard (25.09.):** Portfolio, aktive Objektübersichten und `_VORLAGE` verwenden das gemeinsame responsive Navy-/Petrol-Design aus `assets/dashboard.css`. Pflege über `tools/design_sync.py` und anschließende Portfolio-Generierung. Verbindliche Struktur und Abnahme: `DESIGN_GUIDE.md`. Archivierte Übersichten bleiben unverändert. Tabellen sind separat scrollbar; Styles werden für eigenständige HTML-Dateien eingebettet. Beim visuellen Test wurde zusätzlich ein blockierender Zugriff auf das nicht vorhandene `nkAnteile` in Kerstenhausen durch die äquivalente Prozentrechnung ersetzt.

- **📐 Standard-Analyse-Struktur (21.09., verbindlich für NEUE Objekte):** genau 5 Dateien in `objekte/<Name>/analyse/` – `01_datenbasis.md` · `02_dokumentenpruefung.md` · `03_kalkulation.json` · `04_investmentbericht.md` · `05_mietempfehlung.md`. Muster = Haarhausen. `03_kalkulation.json` im Haarhausen-Schema (Metadaten adresse/objektart/baujahr/zimmer/stellplaetze im `objekt`-Block sind Pflicht – DB + Portfolio lesen sie daraus). ⚠️ Bestehende Dateien NICHT ändern (User-Wunsch 21.09.) – Kerstenhausen hat bewusst kein 05 + eigenes JSON-Schema, bleibt so
- **NIEMALS `localStorage.clear()`** auf User-Daten (hat einmal User-State zerstört)
- Chrome: Directory-Handle-Berechtigungen verfallen nach Browser-Neustart → 1 kurze Nachfrage nötig (nicht umgehbar)
- Übersichten schreiben State-JSON nur bei Eingabe-Events; ohne Ordner-Berechtigung läuft Auto-Sync still ins Leere
- JS-Falle: deutsche Anführungszeichen „…" in JS-Strings → SyntaxError; einfache '…' verwenden
- Playwright-Tests: input-Events nach value-Setzung manuell dispatchen; Script-Scope-Funktionen sind nicht auf `window`
- **Dynamische Tag-Texte unter Eingabefeldern: VERWORFEN** (18.09.) – statische, editierbare Tags genügen; nicht wieder vorschlagen
- **📈 Zins-Recherche-Regel** (18.09., Goldene Regel 12 in README.md): KEINE Beispiel-/Werbezahlen von Vergleichsportalen (CHECK24-Beispielrechnungen) als Kalkulationsbasis! Stattdessen echte Marktkonditionen recherchieren (konkrete Angebote: Vergleich.de/Dr. Klein, FMH, Bankkonditionen), Spanne bestes–schlechtestes dokumentieren + Bindungsdauer nennen. Realität 18.09.: 4,67–5,55 % (12/20 J.) vs. CHECK24-Beispiel 3,02–3,77 % (10 J.). Bei Recalc > 7 Tage alt: frisch prüfen; innerhalb 7 Tage: Wert weiterverwenden. Immer Datum + Quelle in der Datenqualität-Tabelle
- **🧾 Werte-Eintragsregel (23.09., verbindlich):** Recherchierte Werte werden immer direkt in die entsprechenden Eingabefelder sowie State-/Kalkulationsdateien eingetragen. Kaltmiete und Zins erhalten Quelle, Datum und Status; Instandhaltung wird künftig objektbezogen nach Baualter, Zustand und Sanierungsbedarf bewertet. Leerstand 4 Wochen/Jahr, EK 20.000 € und Tilgung 2,0 % bleiben Nutzer-Vorgaben. Unbekannte objektbezogene Werte bleiben leer/ausstehend.

---

## ⏭️ Offene Punkte / Nächste Schritte

- [ ] **Gombeth:** 🔴 gültigen Kaufpreis bestätigen (109.000 € vs. 134.000 €) · 🔴 zwei Versicherungsfälle und Kostenfolgen klären · 🔴 Mietvertrag/Mietkonto prüfen · 🔴 WEG-Unterlagen, Hausgeld und Rücklage anfordern · 🟠 Grundbuch/Teilungserklärung prüfen · 🟡 Besichtigung nach ca. 10.10.2026
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

*Diese Datei wird nach jeder Session aktualisiert. Letztes Update: 23.09.2026*
