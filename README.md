<p align="center">
  <img src="assets/kp-immobilien-logo.png" alt="KP Immobilien" width="220">
</p>

<h1 align="center">Immobilien-Investment-Analyse</h1>

<p align="center">
  <em>Nachvollziehbare Immobilienanalyse, Kalkulation und Portfolioverwaltung</em>
</p>

<p align="center">
  <a href="https://github.com/k-plo/immo-investanalyse/tree/codex/portfolio-current-sync"><img src="https://img.shields.io/badge/Branch-codex%2Fportfolio--current--sync-116d72?style=flat-square" alt="Aktiver Branch"></a>
  <img src="https://img.shields.io/badge/Datenbank-SQLite-116d72?style=flat-square" alt="SQLite">
  <img src="https://img.shields.io/badge/Quelle-Datenbank%20priorit%C3%A4r-116d72?style=flat-square" alt="Datenbank als Quelle">
</p>

> Diese README ist die zentrale Arbeitsanleitung für das Projekt. Sie beschreibt Datenfluss, Ordnerstruktur, Analyseformat und den sicheren Ablauf auf mehreren Rechnern.

## Schnellstart

```bash
git clone https://github.com/k-plo/immo-investanalyse.git
cd immo-investanalyse
git switch --track origin/codex/portfolio-current-sync
python3 tools/local_server.py
```

Danach im Browser [http://127.0.0.1:8000/portfolio.html](http://127.0.0.1:8000/portfolio.html) öffnen. Unter Windows kann alternativ `start_portfolio.ps1` verwendet werden.

### Inhaltsübersicht

- [Portfolio und Datenbank](#0-portfolio-übersicht--datenbank)
- [Arbeitsprozess](#1-so-arbeitest-du-mit-mir-prozess)
- [Ordnerstruktur](#2-ordnerstruktur)
- [Dokumenten-Checkliste](#3-dokumenten-checkliste-was-in-den-ordner-gehört)
- [Datenqualität](#4-datenqualität--verbindliche-kennzeichnung)
- [Investmentbericht](#5-investmentbericht--standardformat)
- [Kalkulationstool](#6-kalkulationstool)
- [Goldene Regeln](#7-goldene-regeln-gelten-für-jede-analyse)

> **Ziel:** Aus einem Immobilienordner (Exposé, Grundbuch, Mietverträge, WEG-Unterlagen …) entsteht ein strukturierter, nachvollziehbarer Investmentbericht – plus ein Kalkulationstool für Wirtschaftlichkeit, Finanzierung und Stress-Tests.

---

## 0. Portfolio-Übersicht & Datenbank (NEU)

**`portfolio.html`** (im Workspace-Root) zeigt **alle analysierten Objekte auf einen Blick**: Kacheln mit Kerndaten, **Rating A–F**, Filter nach Rating, Portfolio-Summen.

**Datenhaltung:** `immo_datenbank.db` (SQLite) ist die einzige Laufzeitquelle für Portfolio und Objektübersichten. Jede Immobilie hat eine unveränderliche `public_id` (UUID), unabhängig von Ort und Anzeigenname. Der Ordnername ist nur ein eindeutiger technischer Pfad. State-JSON wird nicht mehr eingelesen; der Download ist ausschließlich ein Export. `localStorage` wird nur noch für die Hell-/Dunkelmodus-Präferenz verwendet.

Änderungen in einer Objektübersicht werden automatisch über den lokalen Server in einer SQLite-Transaktion gespeichert. Jede Speicherung erhöht die Revision; bei konkurrierender Bearbeitung wird ein Konflikt gemeldet statt stillschweigend überschrieben. Das Portfolio lädt seine Karten bei jedem Öffnen und Aktualisieren aus `/api/portfolio`. Ohne laufenden Projektserver gibt es keinen Bearbeitungs-Fallback.

**Mehrere Rechner mit Git:** Vor dem Bearbeiten `git pull --ff-only`; nach dem Bearbeiten den Server schließen, `python3 tools/db_manager.py check` ausführen, die Datenbankdatei und zugehörige Objektdateien committen und pushen. Auf dem zweiten Rechner erneut pullen. SQLite-Dateien lassen sich in Git nicht sinnvoll zeilenweise mergen: dieselbe DB darf nicht gleichzeitig auf zwei Rechnern bearbeitet werden. Die `-wal`/`-shm`-Dateien gehören nicht ins Repository.

**Objektbilder:** Titelbilder liegen direkt im jeweiligen Objektordner, zum Beispiel `objekte/Arnsbach/titelbild.webp`, und werden mit Git versioniert. Die Datenbank enthält nur den Projektpfad zum Bild. Deshalb müssen Bilddatei und Datenbankänderung gemeinsam committed werden. Die Übersichten funktionieren auf anderen Rechnern nur über den lokalen Projektserver, nicht beim direkten Öffnen per `file://`.

**Empfohlener Synchronisationsablauf:**

```bash
git switch codex/portfolio-current-sync
git pull --ff-only
# Änderungen lokal durchführen und Server anschließend beenden
python3 tools/db_manager.py check
git add immo_datenbank.db objekte/ assets/ portfolio.html tools/
git commit -m "Analyse aktualisieren"
git push origin codex/portfolio-current-sync
```

**Lokale Web-App starten:**

```powershell
.\start_portfolio.ps1
```

Das Skript startet mit `python3` den dependency-freien lokalen Python-Server auf `http://127.0.0.1:8000/` und öffnet die Portfolioübersicht direkt in Chrome. Der Server stellt außerdem DB-Objekt-, Export- und Anzeigenimport-Endpunkte bereit. Nach Codeänderungen muss ein alter Serverprozess neu gestartet werden.

**DB-Befehle:**
| Befehl | Wirkung |
|---|---|
| `python tools/db_manager.py sync` | Portfolio-Hülle neu generieren, ohne JSON-Import |
| `python tools/db_manager.py list` | Objekte mit Kerndaten + Rating anzeigen |
| `python tools/db_manager.py check` | SQLite-Integrität, Fremdschlüssel und Objekt-IDs prüfen |
| `python tools/db_manager.py export-json <name> <ziel.json>` | Eine DB-Revision als JSON exportieren; DB bleibt unverändert |
| `python tools/portfolio_generator.py` | portfolio.html neu generieren |

**Rating (A–F):** Bruttorendite 25 % · Cashflow 25 % · EK-Rendite 15 % · Risiko-Ampeln 20 % · Datenqualität 15 %

**Anzeigenlink importieren:** Der Button im Portfolio versucht öffentlich lesbare HTML-/JSON-LD-Angaben (z. B. Titel, Kaufpreis, Wohnfläche, Adresse) und ein verfügbares Anzeigenfoto zu übernehmen. Es entsteht sofort ein Objektordner, ein DB-Eintrag mit UUID und eine interaktive Übersicht. Der Status bleibt „Quellenprüfung offen“: fehlende Mietdaten, Unterlagen, Rechte, Zustand und Kosten werden nicht erfunden. Verweigert eine Plattform den Abruf (z. B. HTTP 403), wird nur ein leerer, klar als „Abruf blockiert“ gekennzeichneter Datensatz mit Link und ID angelegt; die Analyse muss dann anhand von Unterlagen ergänzt werden. Captchas oder Login-Schranken werden nicht umgangen. Fotos werden nur angezeigt, wenn tatsächlich ein Bild importiert wurde; Dokument-Scans dienen nicht als Ersatzfoto. Über „🖼️ Objektfoto hinzufügen“ kann für jedes Objekt ein echtes Foto lokal hinterlegt werden; dieses erscheint in der Übersicht und verschwommen hinter der Portfolio-Karte.

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

**Verbindliche Regel für vollständige neue Analysen:** Eine vollständige Analyse umfasst die fünf Dateien unter `analyse/`, die interaktive Übersicht und einen DB-Datensatz mit UUID. Ein Anzeigenlink erzeugt zunächst nur eine gekennzeichnete Voranalyse; die vollständige Dokumentenprüfung folgt danach. Fehlende Werte bleiben leer bzw. „ausstehend"; es werden keine Zahlen erfunden.

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

**Standard-Analyse-Struktur (User-Vorgabe 21.09.2026, verbindlich für alle neuen Objekte):**

Jede Objekt-Analyse besteht aus genau **5 Dateien** in `objekte/<Name>/analyse/`:

| Datei | Inhalt |
|---|---|
| `01_datenbasis.md` | Alle Objektdaten mit Kennzeichnung (BELEGT/ABGELEITET/ANNAHME/UNBEKANNT) + Quellen + Widersprüche + fehlende Infos (priorisiert) |
| `02_dokumentenpruefung.md` | Dokumentenbewertung, Grundbuchanalyse, Flächenprüfung, technische Due Diligence, Mietverhältnis, Chancen, Risikoanalyse, Fragenliste |
| `03_kalkulation.json` | Export/Analysedokument im Haarhausen-Schema; die Web-App liest daraus keine Laufzeitwerte mehr. Verbindliche Objektmetadaten werden in SQLite gepflegt. |
| `04_investmentbericht.md` | Investment-Report (Objekt, Wirtschaftlichkeit, Chancen, Risiken, Dokumentenstatus, Due Diligence, Verhandlung) + INVESTMENT-STATUS (Ampel) |
| `05_mietempfehlung.md` | Mietempfehlung mit Herleitung (Regionalvergleich), objektspezifische Faktoren, Tragfähigkeit mit Nutzer-Vorgaben, Szenarien, Quellen, nächste Schritte |

**Referenz/Muster = `objekte/Haarhausen/analyse/`** – Aufbau, Abschnitte und Kennzeichnung daran orientieren. Bestehende Analysen (z. B. Kerstenhausen) bleiben unverändert.

**Die interaktive Übersicht** (`<Objektname>_Übersicht.html`) liegt direkt im Objektordner. Zahlen oben ändern → alles rechnet live und wird in SQLite gespeichert. „💾 State speichern (Download)" ist nur ein optionaler Export; die JSON gehört nicht in den normalen Sync-Workflow.

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

### Schnellanalyse (~2 Minuten)

**`schnellanalyse.html`** (vom Portfolio-Button „⚡ Schnellanalyse" aus erreichbar) bewertet ein Immobilienangebot direkt im Browser: Kaufpreis, monatliche Kaltmiete und Finanzierung. Nicht umlagefähige Kosten, Rücklage und sonstige Kosten werden pauschal mit 20 % der Kaltmiete angesetzt (zentral in `assets/schnellanalyse_core.js`, in der Oberfläche ausgewiesen). Ausgegeben werden Bruttomietrendite, Kaufpreisfaktor, Cashflow nach Finanzierung und ein Gesamtstatus – jeweils für die Basisvariante und ein Szenario „Kaufpreis 10 % niedriger" samt Vergleich. Die Zielwerte (Rendite > 5 %, Cashflow > 0 €, Faktor < 20; exakte Grenzwerte gelten als nicht erfüllt) liegen zentral in `assets/schnellanalyse_core.js`. Das Eigenkapital ist als fester Betrag oder als prozentualer Anteil des Kaufpreises wählbar; daraus ergibt sich das Darlehen (Kaufpreis − Eigenkapital). Die gewählte Annahme wird angezeigt und im Szenario beibehalten. Die Seite rechnet nur temporär und speichert nichts. Tests: `node tests/test_schnellanalyse.js`.

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
13. **Recherchierte Werte direkt eintragen:** Kaltmiete und Zins werden nach der Recherche unmittelbar in die Übersicht, State-Datei und Kalkulations-JSON übernommen und mit Quelle, Datum und Status gekennzeichnet. Instandhaltung wird objektbezogen nach Baualter, Zustand und Sanierungsbedarf als €/m²/Jahr bewertet. Verbindliche Nutzer-Vorgaben sind Hausgeld 35 € pro Monat, falls keine andere Angabe vorliegt, Leerstand 2 %, Eigenkapital 20.000 € und Tilgung 1,0 %. Diese Werte werden direkt in die Eingabefelder, State-Dateien und Kalkulations-JSON eingetragen. Nach Nutzerentscheidung vom 23.09.2026 werden leere Eingabefelder rechnerisch als 0 behandelt; sie gelten dadurch nicht automatisch als belegte Fakten.
