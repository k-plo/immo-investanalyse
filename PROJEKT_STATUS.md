# 📋 Projekt-Status – Immobilien-Investment-Analyse

> **Zweck dieser Datei:** Laufender Bearbeitungsstand des Projekts. Wird nach **jeder** Bearbeitungs-Session vom Agent aktualisiert (User-Wunsch vom 18.09.2026).
> **Konventionen & Lessons Learned:** siehe `README.md` (Prozess) + Agent-Memory (`/memories/repo/immo-workspace.md`).

---

## 🕐 Aktueller Stand (19.10.2026)

**Neue Kategorie „⚡ Schnellcheck" im Portfolio:** Unterhalb des Objekt-Portfolios gibt es ein eigenes Schnellcheck-Portfolio ohne Objektordner. Der Link-Import liest Adresse, Fläche, Zimmer, Stock, Baujahr, Energieklasse, Kaufpreis und Ist-Miete. Die **pot. Kaltmiete wird beim Anlegen automatisch recherchiert**: `tools/rent_research.py` nutzt in Kassel bei vollständiger Adresse zuerst den offiziellen Mietspiegelrechner 2026 (Straße/Hausnummer → Wohnlage, Baujahr-/Flächen-Mittelwert); ohne genaue Straße folgt die regionale Immowelt-Seite aus den Orts-Breadcrumbs. In anderen Regionen wird die auflösbare Immowelt-Stadtteilseite bevorzugt, sonst die Stadtseite. Quelle, Marktstand, Recherchedatum und Rechenweg landen direkt in der Karte. Wenn keine Regionsseite auflösbar oder die Quelle blockiert ist, dokumentiert das Quellenfeld den Grund; keine unbelegte Miete wird erfunden. Bruttorendite/Faktor rechnen mit Ist-Miete, sonst Pot-Miete. Übersicht bleibt optional.

**KM-pot-Recherche Schnellcheck Treysa (18.10.2026):** Amtlichen Mietspiegel für Schwalmstadt nicht gefunden; die offizielle Kreistabelle betrifft angemessene Bruttokaltmieten (KdU), nicht die ortsübliche Marktmiete. Immowelt-Ortsseite „Mietpreise in Schwalmstadt" weist für Wohnungen einen Mittelwert von **6,98 €/m²** aus (Marktwert aktualisiert 01.10.2026; Spannweite 4,68–9,79 €/m²). Rechnung: 75,4 m² × 6,98 €/m² = **526,29 €/Monat**. KM pot direkt in Schnellcheck-Karte gespeichert, Quelle/Datum/Rechenweg ergänzt; kein amtlicher Mietspiegel, als Angebotsmarkt-Mittelwert gekennzeichnet. Quellen: [Immowelt Mietpreise Schwalmstadt](https://www.immowelt.de/immobilienpreise/mietpreise/hessen/schwalmstadt-34613/ad08de2890), [Immowelt Deutschland](https://www.immowelt.de/immobilienpreise/deutschland).

**Kassel-Nord-Holland Schnellchecks (19.10.2026):** Erstes Exposé bestätigt **300 €/Monat Ist-Kaltmiete** (6,88 €/m²); Pot-Miete **386,73 €/Monat** (8,87 €/m²) für 43,6 m². Zweites Angebot: **550 €/Monat Ist-Kaltmiete**, Pot-Miete **646,62 €/Monat** (8,87 €/m²) für 72,9 m². Beide verwenden den Immowelt-Wohnungsmittelwert Nord-Holland, Marktstand 01.10.2026, als Angebotsmarkt-Orientierung, nicht als amtlichen oder adressgenauen Vergleichswert. Quelle: [Immowelt Mietpreise Nord-Holland](https://www.immowelt.de/immobilienpreise/mietpreise/kassel-34117/nord-holland-34127/ad09de333), [erstes Exposé](https://www.immowelt.de/expose/7d546298-5363-42df-8ba3-dad57c5415e3), [zweites Exposé](https://www.immowelt.de/expose/7a4be6dc-72a7-4c22-99e2-d7d24e176cb4).

- **Technik:** neue DB-Tabelle `schnellcheck` (Migration automatisch via `ensure_runtime_schema` in `tools/db_manager.py`, aufgerufen in `tools/db_store.py:connection()`); Backend-Funktionen `create_schnellcheck` / `update_schnellcheck` / `delete_schnellcheck` / `schnellcheck_rows` / `schnellcheck_uebersicht` in `tools/db_store.py`; API-Endpunkte `GET /api/schnellchecks`, `POST /api/schnellcheck`, `PUT|DELETE /api/schnellcheck/<id>`, `POST /api/schnellcheck/<id>/uebersicht` in `tools/local_server.py`; Frontend `assets/schnellcheck.js` (v=1) + Sektion in `tools/portfolio_generator.py`. Zusatzextraktion (Straße/Hausnr.-Split, Stadtteil, Baujahr, Energieklasse, Geschoss, Kaltmiete aus Freitext) in `tools/listing_import.py` – konservativ, bestehender Import unverändert. Blockierte Anzeigen (HTTP 401/403/429) legen eine leere Karte zum manuellen Ergänzen an; Duplikate pro Link werden erkannt.
- **Immowelt-Fix (18.10.):** Immowelt blockierte den Bot-User-Agent mit HTTP 403 und rendert Daten nur per JS. Gelöst über (1) realistischen Chrome-User-Agent in `fetch_public` und (2) Fallback-Parser `extract_embedded_state`, der das im Seiten-Payload eingebettete (maskierte) JSON auswertet: Preis, Wohnfläche, Zimmer, Geschoss, Baujahr, Energieklasse (efficiencyClass.rating), Ort/Stadtteil/PLZ (address-Block) sowie Headline als Titel. Live-Test mit echtem Immowelt-Exposé erfolgreich: alle Schnellcheck-Felder korrekt befüllt (KP 159.000 €, 75,4 m², 3 Zi., 3. Geschoss, BJ 1995, Klasse D, KM ist 750 €, Schwalmstadt/Treysa).
- **Tests:** `tests/test_db_workflow.py`: 6/7 grün; der bekannte Windows-Temp-Cleanup-Fehler in `test_same_town_distinct_ids_and_revision_conflict` bleibt. `SchnellcheckTest` 3/3, `tests/test_schnellanalyse.js` 14/14. Die Kassel-Quellenpriorität ist per Test für Straßen-Wohnlage, Mietspiegeltabelle und Indexfaktor abgedeckt. Hinweis: `SchnellcheckTest` leert die kopierte `schnellcheck`-Tabelle, da die Echt-DB inzwischen echte Karten enthält.

## 🕐 Vorheriger Stand (16.10.2026)

**Neues Objekt Kassel – Franzgraben 39, Wohnung 159:** Vollständige Voranalyse aus Exposé, Wirtschaftsplan 2026 und Hausgeldabrechnung 2025 angelegt. Objektordner `objekte/Kassel_Franzgraben_39/` enthält die Übersicht, fünf Analyse-Dateien und die vorhandenen Unterlagen; SQLite-UUID `13bc1595-0aef-4b7e-bbe3-820eb74dc4fb`. Eckdaten: 85.000 €, ca. 33,16 m², studentisch gebundenes Maisonette-Apartment, Ist-Kaltmiete laut Exposé 395 €/Monat, Baujahr 1993, Energieklasse D. Startmodell mit 20.000 € EK, 4,5 % Zins, 1 % Tilgung, 2 % Leerstand und 1 €/m²/Monat Instandhaltung: Gesamtinvestition ca. 94.329 €, Rate ca. 341 €/Monat, Cashflow ca. −40 €/Monat; rechnerischer Break-even-Kaufpreis ca. 77.228 €. **Gesamtstatus ⚪ ZU WENIG DATEN**; die rechnerische Ampel „Verhandeln“ bewertet nur Modellkennzahlen. Mietvertrag/Mietkonto, Grundbuch, Baulastenauskunft, Teilungserklärung, WEG-Beschlüsse und technische Prüfung fehlen; Etagen- und Hausgeldwidersprüche offen. Keine belastbare Investmententscheidung möglich.

**Neues Objekt Kassel – Struthbachweg 39:** Voranalyse aus Makler-Exposé Nr. 00271 angelegt. Der vertippte Ausgangsordner wurde auf `objekte/Kassel_Struthbachweg/` korrigiert; vorhanden sind Übersicht, Titelbild, Exposé, Unterlagen-README und Analyse-Dateien 01–05. SQLite-Datensatz UUID `9f662367-7b93-464a-8548-f3a2a1c651a8`. Eckdaten: 69.000 €, ca. 43,62 m², 1,5 Zi., EG links, Baujahr ca. 1963, Ist-Kaltmiete laut Exposé 300 €/M, Hausgeld 234,26 €/M und Rücklage 25,45 €/M. Modell: EK 20.000 €, Zins 4,5 %, Tilgung 1 %, Instandhaltung 1 €/m²/M, Leerstand 2 %; Cashflow vor Steuern ca. −44 €/M, wobei weitere WEG-Eigentümerkosten, Verwaltung und Instandsetzungsbedarf noch fehlen. Marktvergleich 411 €/M ist nur aus dem stadtweiten Angebotsmittel abgeleitet und keine bestätigte Vergleichsmiete. Mietvertrag, WEG-Abrechnungen, Wirtschaftsplan, Energieausweis im Original und Wohnflächenberechnung fehlen.

**Neuental-Waltersbrück – Besichtigung vorbereitet:** Die druckbare A4-Checkliste `objekte/Waltersbrück_Am_Frankenhain_14/Besichtigungscheckliste_Waltersbrück.html` wurde im Aufbau der Arnsbach-Checkliste erstellt; zusätzlich liegt eine bearbeitbare Word-Fassung `objekte/Waltersbrück_Am_Frankenhain_14/Besichtigungscheckliste_Waltersbrück.docx` mit sechs Abschnitten und 33 Prüfpunkten vor. Sie priorisiert Energieklasse H/Ölheizung, Grundstücks- und Gartengrundstücksnachweise, Genehmigung und Zustand des Nebengebäudes, den Garagenwiderspruch sowie Sanierungs- und Kostenfragen. Der Anbieter-PDF-Scan bleibt manuell abzugleichen.

**Neues Objekt Baunatal – Mitte (3. OG):** Aus Kleinanzeigen-Anzeige 3529339475 als vollständige Voranalyse angelegt: Objektordner `objekte/Baunatal_Mitte/` mit Übersicht, Titelbild (`titelbild.jpg`), fünf Analyse-Dateien, Unterlagen-README, SQLite-Datensatz (ID `1d1146b9-6824-4a16-93a4-693c0f967569`) und Portfolio-Karte. Eckdaten: 159.500 € (provisionsfrei), 53 m², 2 Zi., 3. OG, BJ 1996, Balkon/Keller/Stellplatz/Einbauküche, Hausgeld 183 €, **geplante Kaltmiete 700 € (Wohnung aktuell leer)**. Kalkulation im Pauschalmodus 20 %, Zins 4,60 % (Nutzer-Vorgabe): Gesamtinvest 171.574 €, BruttoR 5,27 %, Faktor 18,99, Cashflow −147 €/M. Widerspruch dokumentiert: Ortsangabe „Mitte" vs. „am Baunsberg" (Mietanzeige desselben Anbieters). Status 🟠 VERHANDELN.

**Neues Objekt Kassel – Vorderer Westen:** Aus Immowelt-Exposé 0ef3085a-3257-4136-bb24-71143269ed91 (Online-ID 269KMHTV91PT) als vollständige Voranalyse angelegt: Objektordner `objekte/Kassel_Vorderer_Westen/` mit Übersicht, Titelbild (`titelbild.jpg` aus dem Inserat), fünf Analyse-Dateien, Unterlagen-README, SQLite-Datensatz (ID `25703334-931e-49ef-bbe9-084e5f1cf993`) und Portfolio-Karte. Eckdaten: 171.000 €, 73,5 m², 3 Zi., 1. OG, BJ 1964, Energieklasse D (Öl, Massivhaus), Garage + Balkon + Keller, **Ist-Miete 653 €/Monat (BELEGT)**, Hausgeld 640,32 €. Kalkulation im Pauschalmodus 20 %, Zins 4,60 % (Nutzer-Vorgabe): Gesamtinvest 189.032 €, BruttoR 4,58 %, Faktor 21,82, Cashflow −266 €/M. Widerspruch dokumentiert: Etage (Kachel „EG" vs. Text „1. OG" vs. Merkmal „Erdgeschoss").

## 🕐 Vorheriger Stand (06.10.2026)

**Portfolio-Karten kompakter:** Die Karten zeigen oben rechts weiterhin den Bearbeitungsstand, sind aber flacher: Die Zeilen **Objekt-ID** (`karte-sub`) und **Finanzierung** (EK · Zins · Tilgung) sind entfernt. **Miete/Monat** ist als sechste Kachel in die KPI-Reihe gewandert, die jetzt einheitlich **3 × 2** ist (Kaufpreis, Gesamtinvest, Miete/Monat, Faktor, BruttoR, CF/M). Alle Kacheln haben dasselbe, kleinere Format (`.karte-kpis` in `assets/dashboard.css`: Padding 6/8 px, Label 8 px, Wert 13 px, Zusatzzeile 9 px – inkl. `€/m²` beibehalten); Kartenpolsterung 16 → 14 px, Kartenname 19 → 16 px (mobil 20 → 17 px), Detailzeile etwas kompakter. Zusätzlich ist das Portfolio-Raster (`.grid`) auf **automatisch gefüllte, schmale Spalten** umgestellt (`repeat(auto-fill,minmax(300px,1fr))`) – statt zwei breiter Spalten jetzt bis zu drei Karten pro Zeile (ca. 404 px statt ~616 px), damit in den KPI-Kacheln rechts keine Leerfläche mehr bleibt. Stil/Farben/Hover/Foto/Dunkelmodus unverändert. Nach `python tools/portfolio_generator.py` und `python tools/design_sync.py` (letzteres schreibt nur den eingebetteten CSS-Block der Objektseiten neu). JS-Version `portfolio_db.js?v=8`. Browser-Test: 3 Spalten (1200 px) bzw. weiterhin 3 schmale Spalten (900 px), 6 Kacheln, keine Objekt-ID/Finanzierung, Werte 13 px, keine Konsolenfehler.

**Portfolio: Stock statt Objektart:** Der Typ-Tag oben auf der Karte (🏢 Wohnung / 🏠 Haus) ist entfernt; die vierte Detail-Kachel zeigt jetzt den **Stock** (z. B. `🧭 7. OG`, `🧭 3. OG / DG`) statt der Objektart. Bei **Dachgeschoss mit Etagenzahl** wird beides kombiniert („7. OG / DG", „3. OG / DG") – `_formatiere_etage(wert, objektart)` in `tools/db_manager.py` erkennt DG auch aus der Objektart. **Häuser ohne Etage** zeigen wieder die **Grundstücksfläche** (`🌳 1.520 m²`). Dafür gibt es die DB-Spalte **`objekte.etage`** (TEXT) samt Migration und dem Befehl **`python tools/db_manager.py backfill-etage`**, der die Etage aus `analyse/03_kalkulation.json` liest und auf Kurzformat bringt (EG / n. OG / DG / „n. OG / DG"). Etage wird über `/api/portfolio` (`o.etage`) und `/api/objects` (`meta.etage`) ausgeliefert. Die Meta-Zeile der Objektübersichten zeigt ebenfalls den Stock statt der Objektart (`fuellObjektMeta`, Platzhalter „Stock · Ort · …"). Hombergs Etage („1. von 3", BELEGT aus Exposé) wurde in `03_kalkulation.json` ergänzt. JS-Version `portfolio_db.js?v=10`. Browser-Test: Karten zeigen 7. OG / DG, 2. OG, 1. OG, 3. OG / DG, Haus 1.520 m², kein Typ-Tag, keine Konsolenfehler.

**Portfolio: Statusfilter + Status-Anzeige auf der Karte:** Zusätzlich zur Statussortierung zeigt jede Karte oben rechts den aktuellen Bearbeitungsstand als farbigen Badge (**Gefunden / Angefragt / Besichtigung / Finanzierungscheck**). Die Filterknopfleiste enthält wieder Filter – jetzt nach diesen vier Stufen plus „Alle": `filtern('alle'|'0'|'1'|'2'|'3')` filtert über das neue `data-status`-Attribut der Karte. Die API liefert pro Objekt `status_stufe` (0–3) und `status_label` (in `tools/db_store.py`, `portfolio_rows()`), berechnet mit derselben CASE-Logik wie die Sortierung. Karten-Badge-Farben via `.status-badge` + `[data-status="0|1|2|3"]` in `tools/portfolio_generator.py`. JS-Version `portfolio_db.js?v=7`. Browser-Test: Statuslabels korrekt (Baunatal/Fritzlar/Homberg = Gefunden, Kassel = Angefragt, Schwalmstadt/Waltersbrück = Besichtigung), Filter „Besichtigung" zeigt genau die zwei Objekte, keine Konsolenfehler.

**Portfolio nach Bearbeitungsstatus sortiert, Rating-Anzeige entfernt:** Das Portfolio (`assets/portfolio_db.js`, `tools/portfolio_generator.py`, `portfolio.html`) sortiert nicht mehr nach Rating, sondern nach dem Bearbeitungsstand der jeweiligen Übersicht. Gruppenschlüssel aus `objekte.state_json`, höchster gesetzter Haken: **Gefunden** (kein Haken) → **Angefragt** (`p_statusAnfrage`) → **Besichtigung** (`p_statusBesichtigung`) → **Finanzierungscheck** (`p_statusFinanzierung`), innerhalb der Gruppe alphabetisch. Die Sortierung liegt zentral in `tools/db_store.py` (`portfolio_rows()` via `/api/portfolio`) und gilt damit für Laden und „🔄 Aktualisieren". Rating-Badge, `data-rating` und die Rating-Filterknöpfe (Alle/A–D/F) sind aus dem Portfolio sowie die `.rating-badge`-Regel aus `assets/dashboard.css` entfernt. Die Rating-Daten selbst (Tabelle `rating`, `tools/db_manager.py`, Objektseiten) bleiben unverändert. Browser-Test: Reihenfolge Baunatal, Fritzlar, Homberg, Kassel, Schwalmstadt, Waltersbrück, keine Badges, keine Filter, keine Konsolenfehler.

**Kosten-Switch + Objekte Kassel/Schwalmstadt:** In den aktiven Objektübersichten gibt es neben „Miete und laufende Kosten" den Umschalter **„Einzeln | Pauschal"**. Pauschal rechnet die laufenden Kosten als **Prozentsatz der Kaltmiete** (vorbelegt 20 %, frei einstellbar) und ersetzt die drei Einzelfelder (Hausgeld, Instandhaltung, Leerstand); die Einzelwerte bleiben gespeichert. Einheitlich umgesetzt in Übersicht, Druckbericht (`assets/print_report.js`) und Portfolio-Rating (`tools/db_manager.py`). Neues Objekt **Kassel – Ysenburgstraße (Wesertor)** aus ohne-makler.net OM-475285 angelegt (230.000 €, 100 m², 4 Zi., Kernsanierung 2019, provisionsfrei) – Kaltmiete 950 € (Nutzer-Vorgabe), Zins 4,60 % (Nutzer-Vorgabe), **Pauschalmodus 20 %**; Analyse-Dateien 01–05, Übersicht, SQLite-Datensatz und Portfolio-Karte vorhanden. Rating **F (31,9)**, Cashflow ca. **−301 €/M** bei 20.000 € EK. Fehler in der Schwalmstadt-Übersicht behoben: `calc()` verwendete `pauschal` ohne Definition; Pauschalmodus wird nun auch dort in Cashflow und Kostenberechnung berücksichtigt. SQLite-Laden im Browser mit DB-Revision 138 ohne Dialog- oder JavaScript-Fehler verifiziert.

Die folgenden Einträge dokumentieren frühere Stände und sind nicht als aktuelle Datenquelle zu verwenden.

## 🕐 Vorheriger Stand (04.10.2026)

**Neue Funktion „Schnellanalyse":** Im Portfolio-Dashboard gibt es einen gut sichtbaren Button „⚡ Schnellanalyse – Angebot in ~2 Minuten prüfen". Er öffnet die eigenständige Seite `schnellanalyse.html`, mit der ein Immobilienangebot in wenigen Feldern bewertet wird (Kaufpreis, Kaltmiete, Finanzierung). Nicht umlagefähige Kosten, Rücklage und sonstige Kosten werden pauschal mit 20 % der Kaltmiete angesetzt (in der Oberfläche ausgewiesen und zentral in `PAUSCHALE_KOSTEN_PROZENT` definiert). Berechnet werden Bruttomietrendite, Kaufpreisfaktor, monatlicher Cashflow nach Finanzierung und ein Gesamtstatus, jeweils für die Basisvariante und ein Szenario „Kaufpreis 10 % niedriger" – inklusive Vergleichstabelle (absolute/prozentuale Verbesserung). Die Logik liegt testbar in `assets/schnellanalyse_core.js`, Zielwerte zentral in `SCHWELLEN` (Rendite > 5 %, Cashflow > 0 €, Faktor < 20; exakte Grenzwerte gelten als nicht erfüllt). Die Seite rechnet nur temporär und schreibt nichts in Datenbank oder Objektordner. Tests: `node tests/test_schnellanalyse.js` (14 Tests). Details siehe Abschnitte „Was gebaut ist" → „Schnellanalyse (04.10.)".

Die folgenden Einträge dokumentieren frühere Stände und sind nicht als aktuelle Datenquelle zu verwenden.

## 🕐 Vorheriger Stand (02.10.2026)

Neues Objekt **Baunatal – Leiselpark** (Dachgeschosswohnung, 86 m², KP 190.000 €) aus einer Kleinanzeigen-Anzeige als Voranalyse angelegt: Analyse-Dateien 01–05, Übersicht aus der aktuellen Vorlage, SQLite-Datensatz und Portfolio-Karte. Die Objektdaten-Zeile unter dem Link wird jetzt für alle aktiven Übersichten automatisch aus den DB-Metadaten gefüllt. Alle aktiven Übersichten zeigen in Abschnitt 2 zusätzlich die Zeilen Steuerwirkung und Cashflow nach Steuern (feste Modellannahmen im Tooltip: 29,93 % Grenzsteuersatz, 2 % AfA auf 80 % Gebäudeanteil).

Die folgenden Einträge dokumentieren frühere Stände und sind nicht als aktuelle Datenquelle zu verwenden.

## 🕐 Vorheriger Stand

**Datum:** 29.09.2026
**Letzte Aktion:** `Neuental-Waltersbrück – Am Frankenhain 14` aus der Anbieter-DOCX vorgeprüft; Analyse-Dateien, Übersicht, SQLite-State und Portfolio angelegt bzw. synchronisiert. Energieklasse H, Sanierungsrisiko, Gartengrundstück und Garagenwiderspruch sind kaufentscheidende offene Punkte.

---

## 📁 Objekte (Stand 25.09.2026)

| Objekt | Ordner | Status | Rating | Bemerkung |
|---|---|---|---|---|
| **Haarhausen** | `objekte/_ARCHIV/Haarhausen/` | 🗄️ Analysiert, archiviert | **C (61)** | Aus aktivem Portfolio ausgeblendet; State und Analyse bleiben erhalten |
| **Kerstenhausen** | `objekte/Kerstenhausen/` | ✅ Analysiert, Übersicht aktiv | **C (56)** | KP 152.100 € · BruttoR 7,89 % · CF −53 €/M · KM 1.000 € · 🔴 Grundbuch/Miete weiterhin zu klären |
| **Arnsbach** | `objekte/Arnsbach/` | 🟡 Analysiert, Übersicht aktiv | **D (47)** | KP 159.000 € · BruttoR 7,92 % · CF −188 €/M · Grundbuch- und WEG-Risiken offen |
| **Schwalmstadt-Treysa – Amselweg** | `objekte/_ARCHIV/Schwalmstadt-Treysa_Amselweg/` | 🗄️ Archiviert | **B (78)** | Nicht im aktiven Portfolio berücksichtigen |
| **Schwalmstadt-Treysa – Am Harthberg 6** | `objekte/Schwalmstadt-Treysa_Am_Harthberg_6/` | 🟡 Nur mit Klärung, Übersicht aktiv | **?** | KP 159.000 € · 75,44 m² · Einheit 5 bestätigt · Miete 750 € + 200 € BK · WP Vorschuss 380 €/M · Eigentümerkosten 97,85 €/M · rechnerische umlagefähige WP-Kosten 310,33 €/M (110,33 € über Vorauszahlung, ungeprüft) · vorläufiger CF −184 €/M |
| **Homberg – Magdeburger Straße 5** | `objekte/Homberg_Magdeburger_Strasse_5/` | ⚪ Erstprüfung, Übersicht aktiv | **?** | KP 148.000 € · 72 m² · Miete ca. 542 €/M · Mietstatus widersprüchlich, WEG und Finanzierung offen |
| **Neuental-Waltersbrück – Am Frankenhain 14** | `objekte/Waltersbrück_Am_Frankenhain_14/` | 🟡 Nur mit Klärung, Übersicht aktiv | **?** | KP 119.000 € · 136 m² · Energieklasse H · Marktmiete ca. 1.096 €/M nur abgeleitet · Sanierung, Grundbuch und Gartengrundstück offen |
| _VORLAGE | `objekte/_VORLAGE/` | Vorlage für neue Objekte | – | Übersicht + Analyse-MDs generisch |
| **Fritzlar – Heinrich-von-Meißen-Weg 26** | `objekte/Fritzlar_Heinrich-von-Meissen-Weg_26/` | ⚪ Voranalyse, DB integriert | **D** | KP 132.500 € · 57 m² · 2 Zi. · Hausgeld 233 € · indikativ ca. −233 €/M Cashflow bei 20.000 € EK |
| **Baunatal – Leiselpark** | `objekte/Baunatal_Leiselpark/` | ⚪ Voranalyse, DB integriert | **F** | KP 190.000 € · 86 m² · 3 Zi. · DG 7. Etage · Hausgeld 378 € · Energieklasse C · CF −384 €/M bei 20.000 € EK · Maximalpreis 118.376 € · 🔴 Grundbuch/WEG/Adresse offen |

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
- 🧹 **Vorlage komplett blanko** (18.09., aktualisiert 27.09.): alle Haarhausen-Reste aus `objekte/_VORLAGE/Objektname_Übersicht.html` entfernt; generische Platzhalter „Quelle eintragen". Defaults: grESt 6, notar 2, Hausgeld 35 EUR bei fehlender Angabe, Leerstand 2 %, EK 20.000 EUR, Tilgung 1,0 %.

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

### Neues Objekt Schwalmstadt-Treysa Amselweg (27.09.)
- Immowelt-Exposé erfasst: vermietete 4-Zimmer-Dachgeschosswohnung, 88 m², Baujahr 1995, Energieklasse C, Kaufpreis 179.000 €, Ist-Kaltmiete 645 €/M, Hausgeld 35 €/M.
- Vollständige neue Objektstruktur angelegt: Übersicht, State-JSON, Analyse-Dateien 01–05 und Quellenablage unter `unterlagen/01_expose_immowelt.txt`.
- Mietrecherche: Immowelt weist für Wohnungen in Schwalmstadt 6,96 €/m² aus (Stand 01.09.2026), rechnerisch ca. 612 €/M; Ist-Miete liegt bei 7,33 €/m².
- Erststatus ⚪ **ZU WENIG DATEN**: Grundbuch, Teilungserklärung, WEG-Abrechnungen, Mietvertrag und frisches Bankangebot fehlen.
- `db_manager.py`: fehlender SQL-Platzhalter im Kalkulations-Insert ergänzt; Sync importiert nun alle vier aktiven State-Dateien und regeneriert `portfolio.html`.

### Neues Objekt Schwalmstadt-Treysa – Am Harthberg 6 (27.09.)
- Immowelt-Exposé erfasst: 3-Zimmer-Dachgeschosswohnung in Treysa, 75,44 m², Baujahr 1995, Energieklasse D, Kaufpreis 159.000 €, Ist-Kaltmiete 750 €/M, Balkon/Keller/Gäste-WC.
- Neue Objektstruktur `objekte/Schwalmstadt-Treysa_Am_Harthberg_6/` mit Übersicht, SQLite-State, fünf Analyse-Dateien und Unterlagen-README angelegt; Adresse und Ordnername nachträglich präzisiert.
- Mietrecherche: Immowelt weist für Wohnungen in Schwalmstadt 6,96 €/m² aus (aktualisiert 01.09.2026); Ist-Miete liegt bei 9,94 €/m² und muss mit Mietvertrag verifiziert werden.
- Zinsstartwert 4,20 % für 10 Jahre aus Interhyp-Konditionsspanne 4,08–4,49 % (14.–20.09.2026) eingetragen; kein individuelles Bankangebot.
- Erststatus ⚪ **ZU WENIG DATEN**: Mietvertrag, Hausgeldaufteilung, WEG-Unterlagen, Grundbuch, genaue Adresse und Bankangebot fehlen.

### Harthberg-Unterlagenprüfung (29.09., am 15.10. überholt)
- Der damals geprüfte Makler-Unterlagensatz bezog sich laut Nutzer auf die falsche Einheit 6A/6; diese WEG-, Abrechnungs-, Teilungserklärungs- und Kostenwerte gelten nicht für Einheit 5.
- Die früher daraus übernommenen Werte (480 EUR Vorschuss, 64,88 EUR nicht umlagefähig, 50,29 EUR Rücklage, Nachzahlung 2.355,88 EUR und abgeschlossene Balkonmaßnahmen) sind aus der aktuellen Analyse entfernt bzw. als nicht anwendbar markiert.
- Die Zuordnung des damaligen Energieausweises und der WEG-Protokolle zu Einheit 5 ist offen; Mietvertrag nennt Öl-Zentralheizung, Energieausweis Gas.
- Alte Cashflow-Angabe mit 25.000 EUR EK/−156 EUR ist überholt. Maßgeblich ist der 15.10.-State mit 20.000 EUR EK, 4,80 % Zins, 0,80 EUR/m² Instandhaltung und ca. −184 EUR/M.
- Besichtigungs-Checkliste am 15.10. auf Einheit 5 und die neuen offenen Punkte umgestellt.

### Harthberg-Mietvertrag und Wirtschaftsplan (15.10.)
- Mietvertrag vom 13.02.2026 geprüft: 750 € Nettokaltmiete + 200 € Betriebskostenvorauszahlung, unbefristet ab 01.03.2026, Indexmietvereinbarung, 2.250 € Kaution; Mietkonto/Abrechnungen offen.
- Nutzer bestätigt Einheit 5 als richtige Wohnung. Früherer Makler-Unterlagensatz zu Einheit 6A/6 ist falsch zugeordnet; Werte aus Teilungserklärung/Jahresabrechnung/WEG-Protokollen dazu nicht auf Einheit 5 übertragen.
- WP 2027 Einheit 5: angepasster Vorschuss 380 €/M, 661,46 €/Jahr nicht umlagefähig und 512,76 €/Jahr Rücklagen; zusammen 97,85 €/M Eigentümerkosten. Summenabweichung (4.898,15 € errechnet vs. 4.560 € angepasst) mit Verwaltung klären.
- Einzelpositionen ergeben 3.723,93 €/Jahr bzw. 310,33 €/M umlagefähige WP-Kosten gegenüber 200 €/M Vertragsvorauszahlung. Rechnerische Differenz 110,33 €/M; keine gesicherte Nachforderung, tatsächliche Abrechnung und Umlagefähigkeit prüfen. Übersicht führt dafür jetzt ein eigenes live berechnetes, im DB-State gespeichertes Feld (DB-Revision 148).
- Vorläufiger Cashflow mit bestehendem Nutzer-State (20.000 € EK, 4,80 % Zins, 0,80 €/m² Instandhaltung) ca. −184 €/M. Interhyp-Marktvergleich 10 Jahre am 15.10.2026: effektiv 4,22–4,62 %, gespeicherte Zinseingabe bleibt unverändert.
- Heizungswiderspruch ergänzt: Mietvertrag Öl-Zentralheizung, Energieausweis Gas-Zentralheizung.

### Lokale Stabilisierung (25.09.)
- 🛠️ **Plattformunabhängige Pfade:** Python-Tools und Extraktionshelfer leiten den Projektordner aus `__file__` ab; keine fest codierten Windows-Pfade mehr.
- 🗄️ **DB-Sync/Restore:** SQLite speichert Roh-State und JSON-Hash, importiert auch dynamische offene Punkte/Schritte und exportiert nur bei exaktem Objektnamen an den gespeicherten Pfad zurück. `check` vergleicht nun tatsächlich Datei- und DB-Hash.
- 🧮 **Rechenkern/HTML:** Flache und verschachtelte JSON-Dateien sind kompatibel. Finanzierungsnebenkosten und geplante Sonderumlagen fließen in Gesamtinvestition, Darlehen und Rate ein.
- 🔐 **Sichere Darstellung:** Importierte Texte und Portfolio-Metadaten werden nicht mehr ungefiltert als ausführbares HTML eingesetzt.
- ✅ **Verifikation:** Lokaler Sync mit Arnsbach, Kerstenhausen und archiviertem Haarhausen; Python-/JavaScript-Syntax, Rechenwirkung, dynamische Listen, Restore und Konsistenzprüfung getestet.

### Schnellanalyse (04.10.)
- ⚡ **Dashboard-Button:** `tools/portfolio_generator.py` fügt im Portfolio einen hervorgehobenen Button ein, der `schnellanalyse.html` öffnet.
- 🧮 **Testbare Rechenlogik:** `assets/schnellanalyse_core.js` kapselt die Formeln (UMD, ohne DOM/Netz/Speicherung) und wird überall aus einer Quelle verwendet – Basisvariante und 10-%-Szenario nutzen dieselbe Funktion `berechne()` mit unterschiedlichem Kaufpreis (keine Duplikate).
- 🧾 **Zentrale Zielwerte:** `SCHWELLEN` = { Bruttorendite > 5,00 %, Cashflow > 0 €, Kaufpreisfaktor < 20 }. Exakte Grenzwerte gelten als nicht erfüllt. Nirgends sonst hartcodiert.
- 💰 **Formeln:** Bruttomietrendite = jährliche Kaltmiete / (reiner) Kaufpreis; Kaufpreisfaktor = Kaufpreis / jährliche Kaltmiete; Rate = Darlehen × (Zins + Tilgung) / 100 / 12 (identisch zu `rechenkern.py`/`db_manager.py`); Cashflow = Kaltmiete − 20-%-Kostenpauschale − Rate. Die Bruttorendite-Basis (reiner Kaufpreis) und die Pauschale werden in der Oberfläche ausgewiesen.
- ➕ **Kostenpauschale:** Statt einzelner Felder für nicht umlagefähige Kosten, Rücklage und sonstige Kosten werden pauschal 20 % der Kaltmiete abgezogen (`PAUSCHALE_KOSTEN_PROZENT`, zentral). Im 10-%-Szenario bleibt die Pauschale unverändert (Miete konstant).
- 🔁 **10-%-Szenario:** Szenario-Kaufpreis = 0,90 × Kaufpreis; Miete/Kosten unverändert. Das Eigenkapital ist ausdrücklich wählbar: **fester Betrag** (bleibt im Szenario unverändert) oder **Prozent des Kaufpreises** (skaliert mit dem reduzierten Kaufpreis). Das Darlehen ergibt sich in beiden Fällen als **Kaufpreis − Eigenkapital**. Die gewählte Annahme wird sichtbar angezeigt; kein stiller Wechsel.
- 🐛 **Darlehen aus Eigenkapital (04.10.):** Statt des Darlehensbetrags wird jetzt das **Eigenkapital** abgefragt (fest oder als % des Kaufpreises). Beim Moduswechsel wird der EK-Betrag aus Kaufpreis × Anteil abgeleitet (Standard 20 %, falls leer) und zieht bei Kaufpreis-/Anteilsänderung mit, solange er nicht manuell überschrieben wurde. Damit passt der Darlehensbetrag (Kaufpreis − EK) immer zur gewählten Annahme und ist nie größer als der Kaufpreis.
- 📱 **Umsetzung:** Wiederverwendung von `assets/dashboard.css` und `assets/theme.js` (Dark/Light + responsive), keine neuen Abhängigkeiten. Basis und Szenario stehen nebeneinander/untereinander plus Vergleichstabelle.
- 💾 **Keine Persistenz:** Die Schnellanalyse rechnet nur im Browser; es werden keine DB-Einträge oder Objektordner verändert. Eingaben sind optional mit Nutzer-Standardwerten vorbelegt (Tilgung 1,0 %).
- 🧪 **Tests:** `tests/test_schnellanalyse.js` (Node, 14 Tests) deckt Rendite, Faktor, Cashflow (inkl. 20-%-Pauschale), Statusgrenzen, 10-%-Nachlass, feste und prozentuale Darlehenssumme, Validierung und Gesamtstatus ab. Beispiel (KP 300.000 €, KM 1.500 €, Darlehen 270.000 €, Zins 4 %, Tilgung 2 %; Pauschale 300 €/Monat) ergibt Bruttorendite 6,00 % / Faktor 16,67 / Cashflow −150 €/M und im Szenario (270.000 €) Bruttorendite 6,67 % / Faktor 15,00.

---

## 🔧 Bekannte Eigenheiten / Wichtige Regeln

- **Designstandard (25.09.):** Portfolio, aktive Objektübersichten und `_VORLAGE` verwenden das gemeinsame responsive Navy-/Petrol-Design aus `assets/dashboard.css`. Pflege über `tools/design_sync.py` und anschließende Portfolio-Generierung. Verbindliche Struktur und Abnahme: `DESIGN_GUIDE.md`. Archivierte Übersichten bleiben unverändert. Tabellen sind separat scrollbar; Styles werden für eigenständige HTML-Dateien eingebettet. Beim visuellen Test wurde zusätzlich ein blockierender Zugriff auf das nicht vorhandene `nkAnteile` in Kerstenhausen durch die äquivalente Prozentrechnung ersetzt.
- **Live-Gesamtinvest (25.09.):** Der Portfolio-Rechner übernimmt die berechnete Gesamtinvestition jetzt in den Rückgabewert. Live-Karten aktualisieren Kaufpreis und Gesamtinvestition einschließlich €/m². Im Browser mit Kerstenhausen geprüft: 133.884 € Gesamtinvestition, 1.144 €/m².
- **Zweiseitiger PDF-Druck (25.09.):** Aktive Objektübersichten und Vorlage erzeugen über den vorhandenen Druckknopf eine kompakte A4-Zusammenfassung aus den aktuellen Eingaben. Seite 1 enthält Kennzahlen, Kosten, Risiken und ein großes Notizfeld; Seite 2 enthält eine kumulierte Zehnjahresgrafik und die Jahreswerte für Einnahmen, laufende Kosten, Kreditrate und Cashflow. Unbelegte Felder sind als rechnerische Null-Annahmen markiert. Gemeinsame Quellen: `assets/print_report.css` und `assets/print_report.js`, eingebettet durch `tools/design_sync.py`. Kerstenhausen und Arnsbach als PDF gerendert und mit je genau zwei A4-Seiten visuell geprüft.

- **📐 Standard-Analyse-Struktur (21.09., verbindlich für NEUE Objekte):** genau 5 Dateien in `objekte/<Name>/analyse/` – `01_datenbasis.md` · `02_dokumentenpruefung.md` · `03_kalkulation.json` · `04_investmentbericht.md` · `05_mietempfehlung.md`. Muster = Haarhausen. `03_kalkulation.json` im Haarhausen-Schema (Metadaten adresse/objektart/baujahr/zimmer/stellplaetze im `objekt`-Block sind Pflicht – DB + Portfolio lesen sie daraus). ⚠️ Bestehende Dateien NICHT ändern (User-Wunsch 21.09.) – Kerstenhausen hat bewusst kein 05 + eigenes JSON-Schema, bleibt so
- **NIEMALS `localStorage.clear()`** auf User-Daten (hat einmal User-State zerstört)
- Chrome: Directory-Handle-Berechtigungen können nach Browser-Neustart verfallen. Eine erneute Freigabe erfolgt nur über „Ordner verbinden“.
- Übersichten schreiben State-JSON nur bei Eingabe-Events und erteilter Ordner-Berechtigung; ohne sie bleibt der Browser-State erhalten, ohne Dialoge zu öffnen.
- JS-Falle: deutsche Anführungszeichen „…" in JS-Strings → SyntaxError; einfache '…' verwenden
- Playwright-Tests: input-Events nach value-Setzung manuell dispatchen; Script-Scope-Funktionen sind nicht auf `window`
- **Dynamische Tag-Texte unter Eingabefeldern: VERWORFEN** (18.09.) – statische, editierbare Tags genügen; nicht wieder vorschlagen
- **📈 Zins-Recherche-Regel** (18.09., Goldene Regel 12 in README.md): KEINE Beispiel-/Werbezahlen von Vergleichsportalen (CHECK24-Beispielrechnungen) als Kalkulationsbasis! Stattdessen echte Marktkonditionen recherchieren (konkrete Angebote: Vergleich.de/Dr. Klein, FMH, Bankkonditionen), Spanne bestes–schlechtestes dokumentieren + Bindungsdauer nennen. Realität 18.09.: 4,67–5,55 % (12/20 J.) vs. CHECK24-Beispiel 3,02–3,77 % (10 J.). Bei Recalc > 7 Tage alt: frisch prüfen; innerhalb 7 Tage: Wert weiterverwenden. Immer Datum + Quelle in der Datenqualität-Tabelle
- **🧾 Werte-Eintragsregel (23.09., aktualisiert 27.09., verbindlich):** Recherchierte Werte werden immer direkt in die entsprechenden Eingabefelder sowie State-/Kalkulationsdateien eingetragen. Wenn keine andere Angabe vorliegt, wird Hausgeld mit 35 EUR/Monat eingetragen. Kaltmiete und Zins erhalten Quelle, Datum und Status; Instandhaltung wird objektbezogen nach Baualter, Zustand und Sanierungsbedarf bewertet. Leerstand 2 %, EK 20.000 EUR und Tilgung 1,0 % sind verbindliche Nutzer-Vorgaben. Unbekannte objektbezogene Werte bleiben leer/ausstehend.

---

## ⏭️ Offene Punkte / Nächste Schritte

- [ ] **Fritzlar – Heinrich-von-Meißen-Weg 26:** 🔴 Grundbuch/Teilungserklärung/WEG-Unterlagen anfordern · 🔴 Energieausweis und Heizung 1995 prüfen · 🟠 Hausgeldaufteilung und Rücklage 100.000 € belegen · 🟠 Mietvergleich und Besichtigung durchführen

- [ ] **Gombeth:** 🔴 gültigen Kaufpreis bestätigen (109.000 € vs. 134.000 €) · 🔴 zwei Versicherungsfälle und Kostenfolgen klären · 🔴 Mietvertrag/Mietkonto prüfen · 🔴 WEG-Unterlagen, Hausgeld und Rücklage anfordern · 🟠 Grundbuch/Teilungserklärung prüfen · 🟡 Besichtigung nach ca. 10.10.2026
- [ ] **Kerstenhausen:** 🔴 Grundbuchauszug anfordern · 🔴 Miet-/Nutzungssituation + Einliegerwohnung klären · 🟠 Besichtigung (Renovierungsumfang, Öl-Tank) · 🟠 Baujahr/Wohnfläche-Widersprüche klären · 🟡 Bankgespräch mit frischen Zinsen (Live-Recherche 18.09. deutet auf > 4,5 %)
- [ ] **Schwalmstadt-Treysa Amselweg:** 🔴 Mietvertrag/Nebenkosten und WEG-Unterlagen anfordern · 🔴 Grundbuch/Teilungserklärung prüfen · 🔴 Bankangebot mit aktuellem Zins einholen · 🟡 Besichtigung und Balkon-/Heizungsunterlagen prüfen
- [x] Ordnerverbindung in den Übersichten zeigt beim manuellen Verbinden Erfolg oder Sync-Fehler an.

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
| `schnellanalyse.html` | Eigenständige Schnellanalyse (Basis + 10-%-Szenario, keine Speicherung) |
| `assets/schnellanalyse_core.js` | Testbare Berechnungslogik der Schnellanalyse (zentrale Zielwerte) |
| `tests/test_schnellanalyse.js` | Node-Tests der Schnellanalyse-Formeln und Statusgrenzen |
| `objekte/<Name>/<Name>_Übersicht.html` | Hybrid-Übersicht pro Objekt (Eingaben + Ergebnisse + Auto-Sync) |
| `objekte/<Name>/analyse/` | Analyse-Dokumente (01–05) |
| `objekte/<Name>/unterlagen/` | Original-Dokumente |

---

*Diese Datei wird nach jeder Session aktualisiert. Letztes Update: 27.09.2026*
