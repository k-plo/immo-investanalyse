# Immobilien-Investment-Analyse – Arbeitsanleitung

> **Ziel:** Aus einem Immobilienordner (Exposé, Grundbuch, Mietverträge, WEG-Unterlagen …) entsteht ein strukturierter, nachvollziehbarer Investmentbericht – plus ein Kalkulationstool für Wirtschaftlichkeit, Finanzierung und Stress-Tests.

---

## 0. Portfolio-Übersicht & Datenbank (NEU)

**`portfolio.html`** (im Workspace-Root) zeigt **alle analysierten Objekte auf einen Blick**: Kacheln mit Kerndaten, **Rating A–F**, Filter nach Rating, Portfolio-Summen.

**Datenhaltung (3 Ebenen):**
1. **`immo_datenbank.db`** (SQLite) – zentrale Datenbank, Single Source of Truth für die Übersicht
2. **`<Objektname>_Übersicht_State.json`** – Fail-Safe-Kopie im jeweiligen Objektordner
3. **localStorage** – Browser-Cache der Objekt-Übersichten

**Workflow nach Änderungen in einer Objekt-Übersicht:**
```
python tools/db_manager.py sync                 ← State-JSONs → DB → portfolio.html
```
Beim Öffnen von `portfolio.html` wird zusätzlich automatisch aus dem bereits freigegebenen `objekte/`-Ordner gelesen. Dadurch erscheinen neue Objekte mit vorhandener State-JSON auch ohne vorherige manuelle Neugenerierung. Nach einem Browser-Neustart kann einmalig erneut die Ordnerberechtigung nötig sein.

**DB-Befehle:**
| Befehl | Wirkung |
|---|---|
| `python tools/db_manager.py sync` | Alle State-JSONs einlesen → DB und Portfolio aktualisieren |
| `python tools/db_manager.py list` | Objekte mit Kerndaten + Rating anzeigen |
| `python tools/db_manager.py check` | Konsistenzprüfung DB vs. JSON |
| `python tools/db_manager.py export-json <name>` | DB → JSON zurück schreiben (Restore) |
| `python tools/portfolio_generator.py` | portfolio.html neu generieren |

**Rating (A–F):** Bruttorendite 25 % · Cashflow 25 % · EK-Rendite 15 % · Risiko-Ampeln 20 % · Datenqualität 15 %

---

## 1. So arbeitest du mit mir (Prozess)

```
Dokumente importieren
→ Daten extrahieren (Datenbasis + Quellenverzeichnis)
→ Widersprüche erkennen
→ Grundbuch prüfen
→ Grundriss prüfen
→ technische Risiken analysieren
→ Mietverhältnis analysieren
→ Wirtschaftlichkeit berechnen (Kalkulationstool)
→ Finanzierung simulieren (3 Szenarien)
→ Stress-Test durchführen (6 Szenarien)
→ Chancen erkennen
→ Risiken erkennen
→ fehlende Informationen identifizieren
→ Fragenliste erstellen
→ Zielkaufpreis berechnen
→ Investmentstatus bestimmen
```

**Ablauf in der Praxis:**

1. **Ordner befüllen** – Lege unter `objekte/<objektname>/unterlagen/` alle Dokumente ab (PDF, Fotos, Scans). Nutze die Vorlage `objekte/_VORLAGE/unterlagen/README.md` als Checkliste.
2. **Analyse starten** – Sag mir: *„Analysiere das Objekt `<objektname>`"*. Ich lese sämtliche Dokumente vollständig, fülle `analyse/01_datenbasis.md` (inkl. Quellenverzeichnis) und `analyse/02_dokumentenpruefung.md` aus und erstelle im Objektordner immer `<Objektname>_Übersicht.html` als interaktive Objektübersicht.
3. **Kalkulation** – Ich trage alle belegten Zahlen in `tools/kalkulation.html` ein (oder du selbst im Browser) und sichere das Ergebnis als `analyse/03_kalkulation.json` + `analyse/04_investmentbericht.md` + `analyse/05_mietempfehlung.md` (Standard-Struktur, siehe Abschnitt 2).
4. **Ergebnis** – Du erhältst den Investmentbericht im Standardformat (siehe unten) mit Ampel-Status.

**Verbindliche Regel für neue Objekte:** Eine neue Analyse umfasst immer die fünf Dateien unter `analyse/` **plus** die interaktive `<Objektname>_Übersicht.html` direkt im Objektordner. Wenn bereits belastbare Eingabewerte vorliegen, wird zusätzlich `<Objektname>_Übersicht_State.json` als Fail-Safe-Kopie angelegt. Fehlende Werte bleiben leer bzw. „ausstehend"; es werden keine Zahlen erfunden.

---

## 2. Ordnerstruktur

```
Immo/
├── README.md                      ← diese Anleitung
├── portfolio.html                 ← NEU: Hauptseite (alle Objekte auf einen Blick, generiert)
├── immo_datenbank.db              ← NEU: SQLite-Datenbank (zentrale Datenhaltung)
├── objekte/
│   ├── _VORLAGE/                  ← Vorlage für jedes neue Objekt
│   │   ├── unterlagen/            ← hier alle Dokumente ablegen
│   │   └── analyse/
│   │       ├── 01_datenbasis.md
│   │       ├── 02_dokumentenpruefung.md
│   │       ├── 03_kalkulation.json
│   │       ├── 04_investmentbericht.md
│   │       └── 05_mietempfehlung.md
│   ├── Arnsbach/
│   │   ├── Arnsbach_..._Übersicht.html      ← interaktive Übersicht
│   │   ├── Arnsbach_..._Übersicht_State.json ← Fail-Safe-Kopie
│   │   ├── unterlagen/                      ← Dokumente
│   │   └── analyse/                         ← Analyse-Dateien
│   └── Haarhausen/
│       ├── Haarhausen_Übersicht.html
│       ├── Haarhausen_Übersicht_State.json
│       ├── unterlagen/
│       └── analyse/
└── tools/
    ├── db_manager.py              ← NEU: DB-Verwaltung (sync/import/export/check/list)
    ├── portfolio_generator.py     ← NEU: erzeugt portfolio.html aus der DB
    ├── kalkulation.html           ← generisches Kalkulationstool (Browser, offline)
    └── rechenkern.py              ← gleiche Logik in Python (prüfbar/nachvollziehbar)
```

**� Standard-Analyse-Struktur (User-Vorgabe 21.09.2026, verbindlich für alle NEUEN Objekte):**

Jede Objekt-Analyse besteht aus genau **5 Dateien** in `objekte/<Name>/analyse/`:

| Datei | Inhalt |
|---|---|
| `01_datenbasis.md` | Alle Objektdaten mit Kennzeichnung (BELEGT/ABGELEITET/ANNAHME/UNBEKANNT) + Quellen + Widersprüche + fehlende Infos (priorisiert) |
| `02_dokumentenpruefung.md` | Dokumentenbewertung, Grundbuchanalyse, Flächenprüfung, technische Due Diligence, Mietverhältnis, Chancen, Risikoanalyse, Fragenliste |
| `03_kalkulation.json` | Maschinenlesbare Kalkulation im Haarhausen-Schema: `objekt` / `kauf` / `miete` (inkl. `mietempfehlung`) / `laufende_kosten` / `finanzierung` (inkl. `zinsrecherche`) / `weg` / `annahmen` / `quellen` / `widersprueche` – Metadaten (adresse, objektart, baujahr, zimmer, stellplaetze) im `objekt`-Block sind Pflicht (DB + Portfolio lesen sie daraus!) |
| `04_investmentbericht.md` | Investment-Report (Objekt, Wirtschaftlichkeit, Chancen, Risiken, Dokumentenstatus, Due Diligence, Verhandlung) + INVESTMENT-STATUS (Ampel) |
| `05_mietempfehlung.md` | Mietempfehlung mit Herleitung (Regionalvergleich), objektspezifische Faktoren, Tragfähigkeit mit Nutzer-Vorgaben, Szenarien, Quellen, nächste Schritte |

**Referenz/Muster = `objekte/Haarhausen/analyse/`** – Aufbau, Abschnitte und Kennzeichnung daran orientieren. Bestehende Analysen (z. B. Kerstenhausen) bleiben unverändert.

**�💡 Die interaktive Übersicht** (`<Objektname>_Übersicht.html`) liegt **direkt im Objektordner** (nicht in `analyse/`), damit man sie schnell findet. Sie kombiniert Kalkulationstool + Entscheidungsübersicht: Zahlen oben ändern → alles rechnet live. Änderungen werden automatisch im Browser gespeichert; für dauerhafte Sicherung „💾 State speichern (Download)" klicken – die JSON landet im Download-Ordner (Browser-Standard) und wird dann **in den Objektordner verschoben**.

---

## 3. Dokumenten-Checkliste (was in den Ordner gehört)

| Priorität | Dokument | Wofür |
|---|---|---|
| 🔴 zwingend | Exposé | Eckdaten, Angebotspreis |
| 🔴 zwingend | Grundbuchauszug (aktuell, alle Abteilungen) | Eigentum, Belastungen, Risiken |
| 🔴 zwingend | Mietverträge + Mietaufstellung | Cashflow-Basis |
| 🔴 zwingend | Teilungserklärung (bei ETW) | Sondereigentum, Rechte/Pflichten |
| 🔴 zwingend | Protokolle der letzten 3 Eigentümerversammlungen | Beschlüsse, Sonderumlagen, Sanierungsbedarf |
| 🔴 zwingend | Hausgeldabrechnung + Instandhaltungsrücklage | laufende Kosten, Rücklagenstatus |
| 🟡 wichtig | Energieausweis | Energiezustand, Sanierungsdruck |
| 🟡 wichtig | Grundrisse + Wohnflächenberechnung | Flächenprüfung, Vermietbarkeit |
| 🟡 wichtig | Flurkarte/Lageplan | Grundstück, Stellplätze |
| 🟡 wichtig | Wirtschaftsplan (aktuelles Jahr) | geplante Kosten |
| 🟡 wichtig | Nebenkostenabrechnungen (letzte 2–3 Jahre) | reale Betriebskosten |
| 🟡 wichtig | Kaufvertragsentwurf | Konditionen, Übergang Nutzen/Lasten |
| 🟢 optional | Gutachten, Rechnungen, Sanierungsangebote, Fotos/Videos | Zustandsbewertung |

---

## 4. Datenqualität – verbindliche Kennzeichnung

Jede Information wird gekennzeichnet als:

| Kennzeichen | Bedeutung |
|---|---|
| **BELEGT** | direkt aus einem Dokument ersichtlich (mit Quellenangabe) |
| **ABGELEITET** | aus vorhandenen Daten berechnet (Rechenweg wird gezeigt) |
| **ANNAHME** | notwendige Annahme mangels Daten (wird explizit genannt) |
| **UNBEKANNT** | nicht ausreichend Informationen vorhanden |

**Regeln:**
- Fehlende Daten werden **niemals erfunden**.
- Abweichende Angaben zwischen Dokumenten werden als **⚠️ Widerspruch** markiert – es wird nicht einfach ein Wert ausgewählt.
- Wenn die Datenlage keine seriöse Bewertung erlaubt, lautet das Ergebnis ausdrücklich: **„Keine belastbare Investmententscheidung möglich."** (Status ⚪ ZU WENIG DATEN)

---

## 5. Investmentbericht – Standardformat

Jedes Objekt endet in `analyse/04_investmentbericht.md` mit:

```
INVESTMENT REPORT
Objekt: Adresse / Objektart / Wohnfläche / Kaufpreis
Wirtschaftlichkeit: Gesamtinvestition / Bruttorendite / Nettorendite / Cashflow / Eigenkapitalbedarf
Chancen: (nachgewiesen vs. Hypothese getrennt)
Risiken: (🟢🟡🟠🔴 je Risiko mit Begründung)
Dokumentenstatus: Vollständigkeit / Widersprüche / fehlende Dokumente
Due-Diligence-Status: rechtlich / technisch / wirtschaftlich / Mietverhältnis / Lage
Wichtigste offene Punkte: 🔴 🟡 🟢
Verhandlung: Angebotspreis / Zielpreis / maximal sinnvoller Kaufpreis
INVESTMENT-STATUS: 🟢 WEITER PRÜFEN | 🟡 NUR MIT KLÄRUNG | 🟠 VERHANDELN | 🔴 NICHT WEITER VERFOLGEN | ⚪ ZU WENIG DATEN
```

---

## 6. Kalkulationstool

**`tools/kalkulation.html`** – im Browser öffnen (funktioniert offline, keine Installation). Eingabefelder für alle Erwerbs-, Miet-, Finanzierungs- und Kostendaten. Berechnet automatisch:

- Gesamtinvestition (Kaufpreis + Grunderwerbsteuer + Notar + Grundbuch + Makler + Renovierung)
- Brutto-/Nettomietrendite, Kaufpreis pro m², Gesamtinvestition pro m²
- Laufender Cashflow vor/nach Finanzierung, Cash-on-Cash Return, Eigenkapitalrendite
- 3 Finanzierungsszenarien (konservativ / ausgewogen / hoher Fremdkapitalanteil)
- 6 Stress-Tests (Miete niedriger, Leerstand, Instandhaltung ↑, Zins ↑, Sanierung, Wert ↓)
- Break-Even-Analyse: ab welchem Punkt wird das Investment problematisch

**`tools/rechenkern.py`** – dieselbe Logik in Python, damit jede Zahl nachvollziehbar und prüfbar ist (Ausgabe als Klartext-Report).

---

## 7. Goldene Regeln (gelten für jede Analyse)

1. Erfinde niemals Informationen.
2. Kennzeichne jede Annahme.
3. Weise auf Widersprüche zwischen Dokumenten hin.
4. Rechne Zahlen nachvollziehbar.
5. Trenne Fakten von Prognosen.
6. Sei kritisch – suche aktiv nach versteckten Kosten und Risiken.
7. Nutze die Dokumente als primäre Informationsquelle.
8. Frage nach fehlenden Informationen, bevor du eine starke Schlussfolgerung ziehst.
9. **Keine rechtliche, steuerliche oder finanzielle Beratung als Ersatz für einen qualifizierten Fachberater** (Notar, Rechtsanwalt, Steuerberater).
10. Eine hohe Rendite allein bedeutet nicht, dass ein Investment gut ist.
11. Wenn die Datenlage keine seriöse Entscheidung erlaubt: **„Keine belastbare Investmententscheidung möglich."**
12. **Zinssätze realistisch recherchieren:** Keine Beispiel-/Werbezahlen von Vergleichsportalen (z. B. CHECK24-Beispielrechnungen) als Kalkulationsbasis verwenden. Stattdessen echte Marktkonditionen recherchieren (Vergleichsportale mit konkreten Angeboten wie Vergleich.de/Dr. Klein, Bankkonditionen, FMH) und die Spanne bestes–schlechtestes Angebot dokumentieren. Beispiel: Live-Recherche 18.09.2026 ergab 4,67–5,55 % (12/20 J. Bindung) – deutlich über den CHECK24-Beispielwerten 3,02–3,77 %.
13. **Recherchierte Werte direkt eintragen:** Kaltmiete und Zins werden nach der Recherche unmittelbar in die Übersicht, State-Datei und Kalkulations-JSON übernommen und mit Quelle, Datum und Status gekennzeichnet. Instandhaltung wird objektbezogen nach Baualter, Zustand und Sanierungsbedarf als €/m²/Jahr bewertet. Verbindliche Nutzer-Vorgaben bleiben Leerstand 4 Wochen/Jahr, Eigenkapital 20.000 € und Tilgung 2,0 %. Nach Nutzerentscheidung vom 23.09.2026 werden leere Eingabefelder rechnerisch als 0 behandelt; sie gelten dadurch nicht automatisch als belegte Fakten.