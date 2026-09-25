# Designstandard für Immobilienanalysen

Stand: 25.09.2026. Gilt für Portfolio, aktive Objektübersichten und neue Objekte.
Archivierte HTML-Dateien bleiben eigenständige historische Momentaufnahmen.

## Vorlage und Pflege

Neue Übersichten immer aus `objekte/_VORLAGE/Objektname_Übersicht.html` erstellen.
Die Vorlage in `objekte/<Name>/<Name>_Übersicht.html` kopieren, objektspezifische
Überschrift, Metadaten, Ausgangswerte und belegte Inhalte nach dem bestehenden
Analyseprozess anpassen. IDs, Persistenzschlüssel, Formeln und Eventhandler nicht
für Designänderungen umbenennen oder ersetzen. Fehlende Werte nicht erfinden.

`assets/dashboard.css` ist die gemeinsame visuelle Quelle. Die bestehende
Basisgestaltung bleibt als Rückfallebene erhalten. Der gemeinsame Styleblock
überschreibt sie und wird direkt in jede HTML-Datei eingebettet: keine externen
Fonts, CDN-Abhängigkeiten oder beim Archivieren brechenden Stylesheet-Pfade.
Die zweitseitige Druckzusammenfassung liegt in `assets/print_report.css` und
`assets/print_report.js`. Der vorhandene Druckknopf erzeugt sie aus den aktuellen
Eingaben; `#print-report` an der Objekt-URL baut dieselbe Ansicht ohne Dialog
für die PDF-Qualitätsprüfung auf. Seite 1 enthält die wichtigsten Kennzahlen,
objektspezifische Prüfpunkte und Verkäuferfragen sowie handschriftliche Notizen.
Die Prüfpunkte und Fragen stehen im JSON-Block `inspectionData` der jeweiligen
Übersicht (`checks`: maximal 3, `questions`: maximal 4). Pro neuem Objekt anhand
der belegten Chancen/Risiken und Unterlagen konkretisieren; keine Fakten erfinden
und keine längeren Fließtexte eintragen. Die zwei vorrangigen rot/orange bewerteten
Risiken werden zusätzlich automatisch als Prüfpunkte übernommen. Seite 2 enthält
die Zehnjahresrechnung mit Grafik und Jahrestabelle. Sie nutzt konstante Nominalwerte, einen festen
Zins und eine monatliche Tilgung bis zur vollständigen Rückzahlung. Leere
Eingaben werden ausdrücklich als 0-Annahme gekennzeichnet.

Nach CSS-Änderungen vom Projektordner aus ausführen:

```sh
python3 tools/design_sync.py
python3 tools/portfolio_generator.py
```

Der erste Befehl aktualisiert aktive Übersichten und die Vorlage, nicht das Archiv.
Er umschließt statische Tabellen mit horizontal scrollbareren Regionen und lässt
JavaScript unverändert. Der zweite generiert das Portfolio aus der vorhandenen DB.
`portfolio.html` und `SHARED-DESIGN`-Blöcke niemals manuell gestalten.
Für neue HTML-Tabellen dieselbe `.table-scroll`-Hülle verwenden; bestehende Hüllen
nicht verschachteln. CSS-Änderungen nach diesen Befehlen sind reproduzierbar.

## Verbindliche Struktur

- Portfolio: Titel und Datenstand → vorhandene Filter/Aktionen → Objektkarten → Hinweise.
- Karte: Name/Rating → Adresse → Eckdaten → Kaufpreis/Gesamtinvest/Bruttorendite/Cashflow → Miete/Finanzierung.
- Objekt: Titel/Metadaten → Anzeigenlink und Aktionen → Eingaben → Kennzahlen/Status → Analyseabschnitte 1–7 → Chancen, Risiken, offene Punkte, nächste Schritte, Datenqualität, Nutzungshinweise (8–13).
- Keine erfundenen Charts, zusätzlichen Kennzahlen, ausgeblendeten Eingaben oder neuen Navigationskonzepte. Darstellung und Rechenmodell getrennt halten.

## Visuelle Regeln

- Heller graugrüner Hintergrund, weiße Flächen, dunkle Navy-Schrift und Petrol für Aktionen; Tokens in `:root` verwenden.
- Rot/Gelb/Grün ausschließlich mit vorhandener Risiko-/Bewertungssemantik verwenden. Ratings behalten ihre bisherigen Farben.
- Maximal 1240 px Inhaltsbreite, 20 px Kartenradius, dezente Konturen und Schatten. Keine dekorativen Stockfotos.
- Systemschrift ohne Downloads; große Kennzahlen mit tabellarischen Ziffern. Begleittexte mindestens 10–12 px, normale Inhalte 13–14 px, mobile Eingaben 16 px.
- Bestehende editierbare Quell-Tags bleiben statisch editierbar. Keine dynamischen Tags einführen.
- Bedienelemente mindestens 44 px hoch; kleine Listen-Löschaktionen 32 px. Fokus sichtbar lassen und reduzierte Bewegung respektieren.

## Responsive und Abnahme

- Über 760 px: zwei Portfoliokarten nebeneinander; darunter eine Karte.
- Objekte: vier Eingabe-/KPI-Spalten auf Desktop, zwei bis 1050 px. Auf sehr schmalen Geräten Aktionsbuttons und Finanzierung untereinander.
- Tabellen innerhalb `.table-scroll` horizontal scrollen, niemals die ganze Seite. Hülle per Tab erreichbar; Tabellenüberschriften und numerische Ausrichtung behalten.
- Tooltips auf schmalen Displays als viewportgebundene Hinweise, damit sie nicht außerhalb des Bildschirms liegen.
- PDF-Druck: höchstens zwei A4-Seiten mit Investment-Überblick, Besichtigungsfragen,
  Zehnjahresgrafik, Jahrestabelle und Notizfeld; Browser-Kopf-/Fußzeilen in der Druckmaske
  deaktivieren, falls der Browser sie zusätzlich einblendet.
- Auto-Sync darf bei Eingaben niemals eine Ordnerauswahl/Berechtigungsfrage öffnen.
  Die State-JSON wird nur mit bereits freigegebenem Handle geschrieben. Neue oder
  abgelaufene Berechtigungen ausschließlich über „Ordner verbinden“ einholen;
  „State speichern“ ist ein bewusster Download für Backup/Weitergabe.
- Prüfen: 1440, 768, 390 und 320 px; Portfoliofilter und Objektwechsel; gefüllte KPI-/Ergebnistabellen beider aktiver Objekte; Konsolenfehler. Keine echten Nutzerwerte, Checklisten oder Sync-Berechtigungen für einen reinen Design-Test verändern.
- Keine GitHub-Aktionen: alle Änderungen lokal im Projektordner.
