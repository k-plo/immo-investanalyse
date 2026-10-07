# Automatische Schnellanalysen

Implementiert auf Basis von `portfolio-current-sync`, Commit `a6ea2ee`.
Feature-Branch: `codex/automatische-schnellanalysen`. Vom Nutzer am 07.10.2026
festgelegtes Übergabeziel: `origin/portfolio-current-sync`. Der Git-Zustandsbericht
weiter unten beschreibt die Betriebsprüfung vom 06.10.2026 vor dem Commit;
den aktuellen Stand zeigen `git status` und `git log`. Abweichende historische
Branch- und JSON-Sync-Angaben in README/Status sind keine alternative Ausgangsbasis.

## Einrichtung im Portfolio ohne Textkonfiguration

Seit 07.10.2026 befindet sich in **Schnellanalysen · Agent** das aufklappbare Menü
**⚙ Agent einrichten / Einstellungen**. Es speichert Formulareingaben privat und
startet den vorhandenen Worker auf ausdrücklichen Klick als separaten Prozess.
Das Öffnen des Menüs und seine Statusabfragen lösen keine Verarbeitung aus.
Python ≥ 3.10 und Node ≥ 18 müssen im PATH liegen. Für den lokalen Ablauf werden
keine zusätzlichen Python-Pakete benötigt; die Gmail-Komponenten lassen sich im
Menü in eine private virtuelle Python-Umgebung installieren. Auf Linux muss
Python mit `venv`/`ensurepip` verfügbar sein. Die Einrichtung wurde unter Linux
mit Chromium geprüft; Windows/macOS-Befehle sind unterstützt, aber nicht dort getestet.

**Portfolio starten**, aus dem bestehenden Checkout, falls noch kein Server läuft:

```bash
python3 tools/local_server.py 8000
```

Windows/PowerShell:

```powershell
py -3 tools/local_server.py 8000
```

Dann **http://127.0.0.1:8000/portfolio.html#qaSettings** öffnen. Bei einem bereits
laufenden Server mit API-Version kleiner als 4 diesen zuerst im bisherigen
Terminal mit Strg+C beenden und neu starten. Ohne Demo-Umgebung nutzt dieser
Start die bestehende Repository-DB; er führt nur die additive Migration aus.

### Schritt für Schritt: echte Suchalarme

1. **Finanzierung:** „Finanzierungsprofil verwenden“ wählen; Profilname, eigenes
   Eigenkapital (Betrag oder Prozent), Sollzins und anfängliche Tilgung eintragen.
   Kein Profil ist vorbelegt. Ohne Profil gibt es belegte Objektkennzahlen und
   PDFs, aber keinen Finanzierungs-Cashflow. Kostenmodus bleibt die sichtbare
   Annahme 20 % der Kaltmiete; Erwerbsnebenkosten, Steuern und Leerstand fehlen.
2. **E-Mail-Eingang:** „Gmail-Suchalarme“ auswählen. Die tatsächliche Absenderadresse
   aus einer Alarm-Mail, optional einen Betreffteil, einen bewussten Startzeitpunkt
   und Prüfintervall eintragen. Frühere Mails werden nicht ungefragt übernommen.
   Für den ersten Test im zusätzlichen Suchfilter `rfc822msgid:HEADER-ID` mit der
   tatsächlichen Message-ID genau einer neuen Alarm-Mail verwenden; Zeitpunkt
   unmittelbar davor wählen. Danach **Einstellungen speichern**.
3. **Google Cloud:** Gmail API aktivieren, OAuth-Consent für das eigene Konto
   einrichten (bei privatem Gmail External + eigener Testnutzer), unter Clients
   einen **Desktop app**-Client erstellen und die JSON-Datei herunterladen.
   Im Menü **Google-Desktop-OAuth-Datei auswählen**. Das ist die von Google
   erzeugte Datei; keine JSON-Konfiguration selbst schreiben.
   [Offizielle Google-Anleitung](https://developers.google.com/workspace/gmail/api/quickstart/python),
   geprüft am 07.10.2026. Die Datei gehört außerhalb des Repositories.
4. **Gmail-Komponenten einrichten** klicken. Dieser ausdrückliche Schritt benötigt
   Internet zu PyPI und richtet die private Python-Venv ein. Auf „Komponenten bereit“
   warten; dann **Mit Google anmelden**. Im geöffneten Google-Browserfenster das
   eigene Konto auswählen und lesenden Zugriff erlauben. Der Code fordert nur
   `gmail.readonly` an, mit dynamischer Redirect-URI
   `http://localhost:<freier-Port>/`; kein Dashboard-Web-App-Redirect einzutragen.
   Der Anmeldedialog hat fünf Minuten Zeitlimit. Wird kein Browser geöffnet,
   erneut auf einem Rechner mit Desktop-Browser versuchen.
5. **Jetzt einmal prüfen** starten. Das holt passende Mails und verarbeitet die
   fälligen Analyse-/PDF-Jobs. Anschließend **Schnellanalysen aktualisieren**.
   „Verbunden“ erscheint erst nach einem erfolgreichen Gmail-API-Abruf mit genau
   der aktuellen Konfiguration; ein gespeicherter Token allein bestätigt das nicht.
   Erwartung beim Ein-Mail-Test: genau diese Nachricht und ihre Angebote, PDF(s),
   kein Telegram-Versand. Erneutes Prüfen erzeugt keine Nachrichtenduplikate.
6. Wenn der Test stimmt: Worker stoppen/Prozessende abwarten, normalen gezielten
   Suchfilter speichern und **Worker starten**. Der Worker prüft im eingestellten
   Intervall, auch bei geschlossenem Browser. Der Rechner muss eingeschaltet bleiben;
   nach einem Rechnerneustart hier erneut starten. Ein OS-Autostartdienst ist noch
   nicht installiert. Gmail und echte Portal-Layouts wurden noch nicht live abgenommen.

**Ergebnisse ansehen:** Karten zeigen Kennzahlen/Bewertung und getrennte Analyse-,
PDF- und Versandstatus. **Details, Quellen und Annahmen** zeigt das gespeicherte
Profil, beide Szenarien, Belege, Mietreferenzen, Widersprüche und fehlende Angaben.
**PDF herunterladen** lädt das zu diesem Ergebnis gehörende Dokument.
**Schritt wiederholen** reiht nur den betreffenden fehlgeschlagenen Schritt ein;
Worker starten oder „Jetzt einmal prüfen“ führt ihn aus. Ein einmaliger Durchlauf
wartet nicht auf noch nicht fällige Backoff-Wiederholungen. Blockierte Anzeigen
können weiterhin blockiert sein; andere Angebote werden unabhängig verarbeitet.

### EML statt Gmail und sichere Demo

Für eine echte lokal gespeicherte Mail **Lokale EML-Dateien / Dashboard-Import**
auswählen und speichern. **Lokaler Testimport (.eml)** öffnet den Dateidialog.
Alternativ den im Menü angezeigten privaten Eingangsordner bei Bedarf anlegen und Dateien dort ablegen.
Dann **Jetzt einmal prüfen** oder **Worker starten**. Für echte Mails verwendet
normale Konfiguration öffentlich abrufbare Anzeigen. Lokale EMLs tragen derzeit
auch bei echten Nachrichten das Testkennzeichen; sie lösen keinen automatischen
Telegram-Liveversand aus. Weder Gmail-Anmeldung noch KI-Schlüssel sind nötig.

**Die mitgelieferten Fixtures ausschließlich mit neuer temporärer DB und den
lokalen Test-Anzeigen/Mietreferenzen verwenden.** Die folgenden Befehle bereiten
alles vor; keine Datei von Hand bearbeiten. Beispiel Linux/macOS:

```bash
export IMMO_DEMO_DIR="$(mktemp -d)"
export IMMO_DB_PATH="$IMMO_DEMO_DIR/demo.db"
export IMMO_QUICK_OUTPUT="$IMMO_DEMO_DIR/pdfs"
export IMMO_QUICK_HOME="$IMMO_DEMO_DIR/private"
export IMMO_QUICK_CONFIG="$IMMO_QUICK_HOME/automation.json"
python3 - <<'PYDEMO'
import json, os
from pathlib import Path
home = Path(os.environ['IMMO_QUICK_HOME'])
home.mkdir(mode=0o700)
fixture = Path('tests/fixtures/quick_analysis').resolve()
config = json.loads((fixture / 'config.json').read_text())
config['local'].update(mail_directory=str(home / 'inbox'), listing_directory=str(fixture), rent_file=str(fixture / 'rents.json'), notification=False, auto_deliver_test=False)
path = Path(os.environ['IMMO_QUICK_CONFIG'])
path.write_text(json.dumps(config, ensure_ascii=False, indent=2))
path.chmod(0o600)
PYDEMO
python3 tools/db_manager.py init
python3 tools/local_server.py 8765
```

Windows/PowerShell, aus dem bestehenden Checkout:

```powershell
$env:IMMO_DEMO_DIR = Join-Path ([IO.Path]::GetTempPath()) ([Guid]::NewGuid().ToString())
$env:IMMO_DB_PATH = Join-Path $env:IMMO_DEMO_DIR 'demo.db'
$env:IMMO_QUICK_OUTPUT = Join-Path $env:IMMO_DEMO_DIR 'pdfs'
$env:IMMO_QUICK_HOME = Join-Path $env:IMMO_DEMO_DIR 'private'
$env:IMMO_QUICK_CONFIG = Join-Path $env:IMMO_QUICK_HOME 'automation.json'
New-Item -ItemType Directory -Path $env:IMMO_QUICK_HOME -Force | Out-Null
$fixture = (Resolve-Path 'tests/fixtures/quick_analysis').Path
$config = Get-Content (Join-Path $fixture 'config.json') -Raw | ConvertFrom-Json
$config.local.mail_directory = Join-Path $env:IMMO_QUICK_HOME 'inbox'
$config.local.listing_directory = $fixture
$config.local.rent_file = Join-Path $fixture 'rents.json'
$config.local.notification = $false
$config.local.auto_deliver_test = $false
$config | ConvertTo-Json -Depth 10 | Set-Content -Encoding utf8 $env:IMMO_QUICK_CONFIG
py -3 tools/db_manager.py init
py -3 tools/local_server.py 8765
```

Öffnen: **http://127.0.0.1:8765/portfolio.html#qaSettings**. Menü öffnen, vorhandenes
**TEST-Profil** prüfen (30.000 € festes EK, 4 % Zins, 2 % Tilgung), lokal bleiben,
**Einstellungen speichern**. Über **Lokaler Testimport (.eml)**
`tests/fixtures/quick_analysis/emails/01-single.eml` wählen und **Jetzt einmal prüfen**
klicken. Danach aktualisieren: eine TEST-Karte, Basis-Cashflow −150 €/Monat,
bei −10 % Preis 0 €/Monat, PDF „erstellt“, Telegram „nicht verbunden“.
0 € besteht das strikte Ziel > 0 € nicht. PDFs liegen im temporären `pdfs`-Ordner.
`02-multiple.eml` enthält zusätzliche künstliche Fälle; `rents.json` enthält
**ausschließlich erfundene TEST-Mietangebote**, keine echte Scout-Datenquelle.
Demo-Konfigurationen mit Test-Anzeigen/Mietreferenzen lassen sich im Menü nicht
auf Gmail umstellen; für Livebetrieb eine eigene normale private Konfiguration nutzen.

Der Server bleibt für Bedienung/Download offen. Ein separat geöffnetes
Worker-Terminal ist beim Menüstart nicht erforderlich; das Menü startet denselben
`quick_worker.py` im Hintergrund. Vor Ende **Worker stoppen**, auf „Worker gestoppt“
warten, danach Server-Terminal Strg+C. Auch bei geschlossenem Server läuft ein
schon gestarteter Worker weiter; nach Serverneustart erkennt das Menü ihn wieder.
Für Autostart nach Rechnerneustart ist weiterhin eine Dienstinstallation nötig.

### Private Speicherung und optionale Dienste

Standardordner ohne Umgebungsüberschreibung:

| System | Privater Ordner |
|---|---|
| Linux | `$XDG_CONFIG_HOME/immo-investanalyse`, sonst `~/.config/immo-investanalyse` |
| macOS | `~/Library/Application Support/immo-investanalyse` |
| Windows | `%LOCALAPPDATA%/immo-investanalyse` |

Darin: `automation.json` (Profile/Filter/Pfade), `gmail/client.json`,
`gmail/token.json`, optional `telegram/secret.json`, private Venv und
Prozessstatus/Logs unter `runtime/`. Token/Client-Secret werden nie als
Formularwerte zurückgeliefert und nicht in SQLite/Git gespeichert. POSIX-Dateien
0600, neue private Ordner 0700; Windows benötigt passende Benutzer-ACLs.
`IMMO_QUICK_HOME` überschreibt den privaten Ordner;
`--config`/`IMMO_QUICK_CONFIG` bleiben für vorhandene CLI-Nutzung unterstützt.
Ohne explizite Konfiguration liest auch der CLI-Worker die privat gespeicherten
Menüeinstellungen. Die Oberfläche sperrt Änderungen solange Worker oder
Gmail-Einrichtung läuft. „Einstellungen speichern“ setzt `worker_host` auf diesen
Rechner; nur diesen Rechner für den automatischen Git-DB-Betrieb verwenden.

Bei Google External + Testing kann `gmail.readonly` eine erneute Anmeldung nach
sieben Tagen erfordern. Der Worker erneuert gültige Refresh-Tokens automatisch;
Widerruf oder Adminregeln erfordern erneute Anmeldung.
[Google-Tokenlaufzeiten](https://developers.google.com/identity/protocols/oauth2#expiration).
Keine unbegrenzte Anmeldung oder erfolgreiche Live-Verbindung wird behauptet.

**Telegram ist optional:** Bot bei BotFather anlegen und eigene numerische Chat-ID
ermitteln (siehe Abschnitt unten). Im Menü Token/Chat-ID eintragen. Echten Versand
nur ausdrücklich aktivieren; für automatische Zustellung zusätzlich „Neue
Gmail-Analysen … automatisch senden“ und einen bewussten Startzeitpunkt setzen.
Speichern deaktiviert beide lokalen Test-Versandflags. Bereits offene Versandjobs
blockieren die Live-Aktivierung und den Menü-Workerstart, bis sie ausdrücklich
geprüft wurden; bestehende Analysen werden nicht nachträglich gesammelt eingereiht.
Der bestehende CLI-Einzelversand bleibt für bewusstes Testen verfügbar. Ein
Bot-Erstellungs-/Chat-ID-Assistent und ein Versandtestknopf sind nicht implementiert.

**ImmobilienScout24:** Live-Mietreferenzadapter weiterhin nicht implementiert;
autorisierte Datenquelle und Adapterentwicklung fehlen. Ohne belegte Kaltmiete
bleiben mietabhängige Kennzahlen unbekannt; Teilanalyse und PDF entstehen trotzdem.
**KI:** Kein Modellaufruf und kein KI-Konto nötig. Parser extrahieren explizite
Angaben; vorhandener deterministischer JS-Rechenkern berechnet die Kennzahlen.

## Umfang und Datenfluss

`quick_adapters.MailAdapter` → `quick_extract.message_entries` →
`QuickStore.ingest` → persistente Analysejobs → `quick_analysis.analyze` →
`rechenkern.schnellanalyse` → SQLite-Ergebnis → separater PDF-Job → optionaler
Versandjob. Dashboard und PDF verwenden dasselbe gespeicherte `result_json`.

Der reguläre Import `db_store.import_listing` erzeugt Ordner und Übersichten und
wird hier niemals aufgerufen. Wiederverwendet wird ausschließlich
`listing_import.fetch_public` mit URL-Prüfung, begrenzten Antworten, validierten
Weiterleitungen und 12 Sekunden Abrufzeitlimit je Anfrage sowie dessen
HTML-/JSON-LD-Parser. Es gibt keine Fotos, Objektordner, Objekt-HTMLs, fünf
Analysedateien oder Übernahme ins Portfolio. Die einzige objektspezifische
Ausgabe ist eine PDF im gemeinsamen Verzeichnis `ausgaben/schnellanalysen/`.

Die Kategorie steht im Generator und bleibt nach `portfolio_generator.py` erhalten.
`/api/portfolio`, reguläre Summen und Ratings lesen weiterhin ausschließlich die
bisherigen Tabellen. Neue Schnittstellen: `GET /api/quick-analyses`,
`GET /api/quick-analyses/pdf/<ID>`, `POST /api/quick-analyses/import-eml` und
`POST /api/quick-analyses/retry`. Zusätzlich: `GET/POST /api/quick-analyses/settings`,
`POST /api/quick-analyses/gmail-client` und `POST /api/quick-analyses/control` mit
festen Aktionen `install-gmail`, `authorize-gmail`, `start-worker`, `check-once`,
`stop-worker`. Öffnen/Aktualisieren erzeugt keine Jobs.
Der Server läuft jetzt auf Loopback und meldet API-Version 4; das PowerShell-
Startskript erkennt ältere laufende Server. DB-Dateien, SQLite-Nebenfiles,
versteckte Pfade, EMLs und typische Geheimnisdateien werden nicht statisch
herausgegeben. PDF-Downloads laufen über die Datenbank-ID.

## Was aktuell tatsächlich passiert

**Es läuft kein KI-Modell.** Es gibt keinen KI-Anbieter, Modellnamen, API-Key oder
KI-Aufruf. „Agent“ ist die Bezeichnung der automatisierten Verarbeitung.
`quick_adapters.parse_eml` liest MIME/Text/HTML; `quick_extract.message_entries`
ordnet erkannte Anzeigenlinks ihren E-Mail-Blöcken zu. `extract_page` liest
JSON-LD und explizit beschriftete HTML-Felder. Das ist regelbasierte Extraktion,
keine allgemeine Sprachverständnisfunktion. Ungewöhnliche Portal-Layouts,
verkürzte Links und freie Formulierungen können unvollständig erkannt werden.

Heute kommt eine E-Mail über eine lokale `.eml`-Datei hinein: entweder über
**Lokaler Testimport (.eml)** in der Dashboard-Kategorie oder über den konfigurierten
Eingangsordner. Der Dashboard-Import speichert die erkannten Angebote direkt;
der Worker scannt beim Ordnerimport `*.eml` ohne Unterverzeichnisse. Der Worker
führt anschließend die getrennten Analyse-, PDF- und Versandjobs aus. Ohne Worker
bleibt ein Import in der Warteschlange. Der Server berechnet keine Angebote.

`quick_analysis.analyze` öffnet Anzeigen über den ausgewählten Listing-Adapter:
in der Demo lokale HTML-Fixtures, im normalen Betrieb öffentliches HTML über
`PublicListingAdapter`/`listing_import.fetch_public`. Kein Login, kein Captcha-Bypass,
kein kostenpflichtiger KI-Zugang. Angaben stammen ausschließlich aus E-Mail und
Anzeige. Mietreferenzen stammen derzeit nur aus ausdrücklich künstlichen
Testreferenzen; `ScoutRentAdapter.estimate` liefert im normalen Betrieb `None`.

Fehlende Werte bleiben unbekannt. Widersprüchliche Angaben werden mit beiden
Quellkandidaten gespeichert; das betroffene Feld wird nicht zur Berechnung benutzt.
20 % Mietkostenpauschale und Finanzierungsprofil sind sichtbar gekennzeichnete
Modellannahmen. `rechenkern.schnellanalyse` führt den vorhandenen
`assets/schnellanalyse_core.js` mit Node aus; es existiert kein zweiter Satz Formeln.

SQLite speichert Nachrichten-IDs, Anzeigenidentitäten, Beobachtungen, Ergebnisrevisionen,
Quellen und Jobs in `qa_*`-Tabellen. Standarddatei ist `immo_datenbank.db` im
Repository; für alle nachstehenden Übungen verwenden wir eine **neue temporäre DB**.
PDFs liegen gemeinsam in `ausgaben/schnellanalysen/` oder `IMMO_QUICK_OUTPUT`.
`quick_pdf.render_pdf` liest das gespeicherte Ergebnis, berechnet nichts neu.
`local_server.py` liefert Ergebnis und PDF an `assets/quick_analyses.js` aus.
`portfolio_generator.py` enthält die Kategorie ebenfalls, sodass sie nach
Regeneration erhalten bleibt. Es entstehen keine Objektordner oder Vollanalysen;
reguläre Portfolio-Summen und Ratings enthalten keine Schnellanalysen.

Der Worker ist **separat startbar, aber kein installierter Autostartdienst**.
Beim Betriebscheck am 06.10.2026 lief weder `quick_worker.py` noch `local_server.py`.
Ein Browser ist nur für Bedienung/Anzeige nötig, nicht für die Verarbeitung.
„Letzte Workerabfrage“ ist ein gespeicherter Zeitpunkt, kein Nachweis eines noch
laufenden Prozesses. Das Einstellungsmenü erkennt den gestarteten Prozess über private Prozessdaten;
„Verbunden“ für Gmail setzt einen erfolgreichen API-Abruf mit der aktuellen
Konfiguration voraus. Telegram-Aktivierung ist kein Versandnachweis; dafür gilt
nur der gespeicherte Beleg je Analyse. Scout bleibt ohne Liveadapter nicht verbunden.

## Erste lokale Nutzung: Linux/macOS

Geprüft wurde **Linux**, Python 3.14.7, Node 26.8.2 und Chromium.
macOS und Windows wurden nicht ausgeführt; deren Befehle sind aus den unterstützten
CLI-Aufrufen abgeleitet. Mindestlaufzeit laut Implementierung: Python ≥ 3.10,
Node ≥ 18, beide im PATH. Python und Node über die offiziellen Installer von
[python.org](https://www.python.org/downloads/) und
[nodejs.org](https://nodejs.org/en/download) installieren, falls sie fehlen.
Für die lokale Verarbeitung und PDF gibt es **keine zusätzlichen Python-Pakete**.
Die Gmail-Pakete werden erst bei bewusster OAuth-Einrichtung benötigt.

Alle Befehle aus dem bestehenden Repository-Verzeichnis ausführen.
Auf dieser Linux-Maschine:

```bash
cd /home/kev/Work/immo-investanalyse
python3 --version
node --version
```

Auf macOS stattdessen zuerst in den eigenen Checkout wechseln. Der folgende Block
legt eine leere DB, einen leeren Eingangsordner und eine angepasste Demo-Konfiguration
außerhalb des Repositories an. Er kopiert **keine vorhandenen Immobilien**.

```bash
export IMMO_DEMO_DIR="$(mktemp -d)"
export IMMO_DB_PATH="$IMMO_DEMO_DIR/demo.db"
export IMMO_QUICK_OUTPUT="$IMMO_DEMO_DIR/pdfs"
export IMMO_QUICK_CONFIG="$IMMO_DEMO_DIR/demo.json"
mkdir -p "$IMMO_DEMO_DIR/inbox"
python3 - <<'PYCONFIG'
import json, os, shlex
from pathlib import Path
fixture = Path('tests/fixtures/quick_analysis').resolve()
config = json.loads((fixture / 'config.json').read_text())
config['local']['mail_directory'] = str(Path(os.environ['IMMO_DEMO_DIR']) / 'inbox')
config['local']['listing_directory'] = str(fixture)
config['local']['rent_file'] = str(fixture / 'rents.json')
Path(os.environ['IMMO_QUICK_CONFIG']).write_text(json.dumps(config, ensure_ascii=False, indent=2))
activation = Path(os.environ['IMMO_DEMO_DIR']) / 'environment.sh'
keys = ('IMMO_DEMO_DIR', 'IMMO_DB_PATH', 'IMMO_QUICK_OUTPUT', 'IMMO_QUICK_CONFIG')
activation.write_text(''.join('export ' + k + '=' + shlex.quote(os.environ[k]) + '\n' for k in keys))
print('Zweites Terminal: . ' + shlex.quote(str(activation)))
print('Demo-Konfiguration: ' + os.environ['IMMO_QUICK_CONFIG'])
PYCONFIG
python3 tools/db_manager.py init
cp tests/fixtures/quick_analysis/emails/01-single.eml "$IMMO_DEMO_DIR/inbox/"
python3 tools/quick_worker.py --once
python3 tools/local_server.py 8765
```

Der Server bleibt im Vordergrund. Öffne
**http://127.0.0.1:8765/portfolio.html** und scrolle zur separaten Kategorie
**Schnellanalysen · Agent**. Diese Kategorie ist nicht der bisherige Link zur
manuellen `schnellanalyse.html`. Der reguläre Portfolio-Bereich bleibt in dieser
leeren Demo leer. Erwartet: **eine** Karte „Agent · TEST“, PDF „erstellt“, Versand
`lokal_getestet`. Testobjekt: 300.000 €, 100 m², 1.500 € Monatskaltmiete;
TEST-Profil: 30.000 € festes EK, 4 % Zins, 2 % Tilgung. Basis-Cashflow −150 €/Monat;
bei −10 % Preis 0 €/Monat. 0 € erfüllt das strikte Ziel > 0 € nicht.
`lokal_getestet` ist kein Telegram-Versandnachweis.

Für interaktive weitere Importe den Worker in einem **zweiten Terminal** starten:
erst in denselben Checkout wechseln, dann die oben ausgegebene Zeile
`. /tmp/.../environment.sh` mit dem tatsächlich erzeugten Pfad ausführen, dann:

```bash
python3 tools/quick_worker.py
```

Die Demo prüft alle 30 Sekunden, mit höchstens zwei parallelen Jobs.
Für Einzeldurchläufe genügt stattdessen `python3 tools/quick_worker.py --once`.
Einmalige CLI-Verarbeitung braucht keinen Server; Dashboard-Import mit unmittelbar
anschließender Hintergrundverarbeitung braucht **Server und Worker gleichzeitig**.
Ein `--once`-Durchlauf wartet nicht auf künftig fällige Backoff-Wiederholungen.

Im Dashboard:

1. **Details, Quellen und Annahmen** aufklappen: Finanzierung, beide Szenarien,
   Datenherkunft und fehlende Werte. Darunter **Mietreferenzen**, **Widersprüche und
   alternative Angaben** sowie **Telegram-Nachrichtenvorschau · kein Versand**.
2. **PDF herunterladen** lädt die zu dieser Analyse gespeicherte zweitseitige PDF.
3. **Lokaler Testimport (.eml)** öffnet den Dateidialog. Für mehrere Angebote
   `tests/fixtures/quick_analysis/emails/02-multiple.eml` wählen. Es werden fünf
   Angebote unabhängig eingereiht, einschließlich eines absichtlich blockierten.
   Bei laufendem Worker anschließend **Schnellanalysen aktualisieren** drücken.
   Die Seite aktualisiert sich nicht regelmäßig von selbst.
4. Die bereits importierte `01-single.eml` erneut auswählen: 0 neue Angebote.
   Derselbe Message-ID wird nicht nochmals verarbeitet. Andere Nachrichten
   derselben Anzeige können neue Beobachtungen auslösen; nur geänderte Ergebnisse
   erzeugen eine Revision. Preisänderungen sind kein neues Objekt.
5. Beim blockierten TEST-Angebot wird eine Teilanalyse samt PDF gespeichert und
   ein technischer Fehler separat angezeigt. **Schritt wiederholen** reiht nur
   dessen fehlgeschlagenen Job erneut ein. Ein weiterhin blockierter Abruf kann
   weiterhin fehlschlagen; andere Angebote werden trotzdem verarbeitet.

CLI-Status im zweiten Terminal mit derselben Umgebung (Server muss laufen):

```bash
curl --fail --silent http://127.0.0.1:8765/api/quick-analyses | python3 -m json.tool
```

`items` enthält Analyse-/PDF-/Versandstatus, UUID und Ergebnis; `jobs` enthält
`id`, `kind`, `state`, `attempts`, `error`; `worker` enthält den letzten Poll.
Für einen konkreten fehlgeschlagenen Job dessen numerische ID verwenden:

```bash
# 123 durch eine tatsächliche jobs[].id mit failed/uncertain ersetzen:
python3 tools/quick_worker.py --retry 123
python3 tools/quick_worker.py --once
```

`--retry` startet keine Verarbeitung. Bei laufendem Worker genügt das Einreihen.
PDF-/Versandfehler starten die Analyse nicht erneut. `uncertain` kann Doppelversand
bedeuten: vor einer bewussten Wiederholung den Telegram-Chat prüfen.

Sicher beenden: im Worker-Terminal **Strg+C**, laufende Jobs und Prozessende
abwarten; anschließend **Strg+C** im Server-Terminal. Keine Hintergrunddienste
wurden durch diese Anleitung installiert. Nach einem harten Abbruch bleiben Jobs
in SQLite; Analyse/PDF werden nach Ablauf der 300-Sekunden-Lease erneut übernommen,
unter Beachtung der Versuchslimits. Unterbrochener Versand wird `unklar`, nicht
automatisch nochmals gesendet. Den temporären Ordner für spätere Betrachtung
behalten; nach dem Stoppen bei Bedarf die vier `IMMO_*`-Variablen aus der Shell
entfernen. Ohne diese Variablen greifen neue Prozesse auf die Repository-DB zu.

### Kurzer CLI-Einstieg mit einer Test-E-Mail

Wer keine separate Demo-Konfiguration erzeugen möchte, kann die unveränderte
Fixture-Konfiguration verwenden und den Eingangsordner bei **jedem Workerstart**
explizit überschreiben. Dann bleibt der Test auf eine Mail begrenzt:

```bash
export IMMO_DEMO_DIR="$(mktemp -d)"
export IMMO_DB_PATH="$IMMO_DEMO_DIR/demo.db"
export IMMO_QUICK_OUTPUT="$IMMO_DEMO_DIR/pdfs"
export IMMO_QUICK_CONFIG="$PWD/tests/fixtures/quick_analysis/config.json"
mkdir -p "$IMMO_DEMO_DIR/inbox"
cp tests/fixtures/quick_analysis/emails/01-single.eml "$IMMO_DEMO_DIR/inbox/"
python3 tools/db_manager.py init
python3 tools/quick_worker.py --import-eml "$IMMO_DEMO_DIR/inbox" --once
python3 tools/local_server.py 8765
```

Für Dauerbetrieb im zweiten Terminal dieselben vier Variablen mit den tatsächlichen
Pfaden setzen und `python3 tools/quick_worker.py --import-eml "$IMMO_DEMO_DIR/inbox"`
starten. Ohne diesen Schalter würde die unveränderte Fixture-Konfiguration alle
mitgelieferten E-Mails scannen. Zur Profiländerung eine private Konfigurationskopie
verwenden; keine Fixtures oder Repository-Datenbank bearbeiten.

## Erste lokale Nutzung: Windows/PowerShell

Python mit Launcher `py` und Node im PATH installieren. Diesen Block in PowerShell
**im eigenen bestehenden Checkout** ausführen; `py -3` bei Bedarf durch den dort
vorhandenen Python-Aufruf ersetzen. Die Befehle wurden nicht auf Windows getestet.

```powershell
py -3 --version
node --version
$env:IMMO_DEMO_DIR = Join-Path ([IO.Path]::GetTempPath()) ("immo-demo-" + [guid]::NewGuid())
$env:IMMO_DB_PATH = Join-Path $env:IMMO_DEMO_DIR 'demo.db'
$env:IMMO_QUICK_OUTPUT = Join-Path $env:IMMO_DEMO_DIR 'pdfs'
$env:IMMO_QUICK_CONFIG = Join-Path $env:IMMO_DEMO_DIR 'demo.json'
New-Item -ItemType Directory -Path (Join-Path $env:IMMO_DEMO_DIR 'inbox') -Force | Out-Null
$fixture = (Resolve-Path 'tests/fixtures/quick_analysis').Path
$config = Get-Content (Join-Path $fixture 'config.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$config.local.mail_directory = Join-Path $env:IMMO_DEMO_DIR 'inbox'
$config.local.listing_directory = $fixture
$config.local.rent_file = Join-Path $fixture 'rents.json'
$utf8 = New-Object System.Text.UTF8Encoding($false)
[IO.File]::WriteAllText($env:IMMO_QUICK_CONFIG, ($config | ConvertTo-Json -Depth 10), $utf8)
$keys = 'IMMO_DEMO_DIR','IMMO_DB_PATH','IMMO_QUICK_OUTPUT','IMMO_QUICK_CONFIG'
$lines = foreach ($key in $keys) {
  '$env:' + $key + " = '" + ([Environment]::GetEnvironmentVariable($key)).Replace("'", "''") + "'"
}
$activation = Join-Path $env:IMMO_DEMO_DIR 'environment.ps1'
[IO.File]::WriteAllText($activation, ($lines -join [Environment]::NewLine), $utf8)
Write-Host ('Zweites Terminal: . "' + $activation + '"')
py -3 tools/db_manager.py init
Copy-Item 'tests/fixtures/quick_analysis/emails/01-single.eml' (Join-Path $env:IMMO_DEMO_DIR 'inbox')
py -3 tools/quick_worker.py --once
py -3 tools/local_server.py 8765
```

Im zweiten PowerShell-Terminal im Checkout die ausgegebene Zeile
`. "C:\...\environment.ps1"` mit dem tatsächlichen Pfad ausführen, dann:

```powershell
py -3 tools/quick_worker.py
```

Anzeige, Upload und Download erfolgen unter derselben URL und mit denselben
Buttons wie oben. Status und Wiederholung:

```powershell
$status = Invoke-RestMethod 'http://127.0.0.1:8765/api/quick-analyses'
$status.items | Select-Object id, analysis_status, pdf_status, delivery_status
$status.jobs | Format-Table id, kind, state, attempts, error
# Tatsächliche fehlgeschlagene Job-ID einsetzen:
py -3 tools/quick_worker.py --retry 123
py -3 tools/quick_worker.py --once
```

Beide Vordergrundprozesse mit Strg+C beenden und Prozessende abwarten.
`start_portfolio.ps1` ist der vorhandene alternative Starter für Server und Chrome
auf Port 8000, erwartet `python3` und startet **keinen Worker**. Für diese isolierte
Demo verwenden wir bewusst den Vordergrundserver auf 8765; ein bereits laufender
Server könnte eine andere DB/Konfiguration verwenden.

## Finanzierungsprofil einrichten

Die unter `IMMO_QUICK_CONFIG` angegebene JSON-Datei enthält den Block `profile`.
Die Demo liefert ausschließlich das oben genannte **TEST-Profil, kein Bankangebot**.
Vor Verwendung für echte Angebote eigene ausdrücklich gewählte Werte eintragen,
z.B. festes Eigenkapital:

```json
{"name":"Mein ausdrücklich konfiguriertes Profil","ekModus":"betrag","ek":30000,"zins":4,"tilgung":2}
```

Diese Zahlen sind Beispiele, keine Empfehlung. Prozentuales Eigenkapital:

```json
{"name":"Mein Prozentprofil","ekModus":"anteil","ekAnteil":20,"zins":4,"tilgung":2}
```

`zins`/`tilgung` sind Prozentwerte pro Jahr; `ek` ist EUR, `ekAnteil` Prozent.
Ein vorhandenes Profil muss vollständig sein. `profile: null` erlaubt eine
Teilanalyse: belegte Objektkennzahlen werden berechnet, Finanzierungs-Cashflow
bleibt nicht berechenbar. Profildaten werden beim Import je Beobachtung eingefroren.
Änderungen berechnen alte Ergebnisse nicht rückwirkend neu. Nach Änderungen
Server und Worker neu starten; insbesondere der Worker lädt seine Konfiguration
nur beim Start. Derselbe bekannte Message-ID erzeugt auch nach Profiländerung
keinen neuen Import. Eine Bedienfunktion zur gezielten Neuberechnung vorhandener
Analysen mit einem neuen Profil ist noch nicht implementiert.

## Echte EML ohne Gmail importieren

Keine Demo-Konfiguration hierfür weiterverwenden: deren `listing_directory` und
`rent_file` würden weiterhin künstliche Anzeigen und Referenzen wählen.
Erstelle außerhalb des Repositories eine **separate** JSON-Konfiguration, zum Beispiel:

```json
{
  "interval": 60, "concurrency": 1, "max_attempts": 3, "backoff": 30,
  "profile": null,
  "local": {"mail_directory": "/ABSOLUTER/PRIVATER/PFAD/eingang"},
  "gmail": {"enabled": false},
  "telegram": {"enabled": false}
}
```

Der Eingangspfad muss existieren. Unter Windows einen tatsächlichen Pfad mit
`C:/Users/.../eingang` oder JSON-escaped Backslashes eintragen. Das Fehlen von
`local.listing_directory`, `local.rent_file`, `local.notification` und
`local.auto_deliver_test` wählt öffentlichen Anzeigenabruf, keine Testreferenzen
und keinen Versand. `profile` optional wie oben ausdrücklich konfigurieren.

Neue leere DB und gemeinsames Ausgabeverzeichnis außerhalb des Repositories
wählen und **in beiden Terminals** die drei Variablen setzen. Beispiel Linux/macOS
(nach Anlegen der privaten Konfigurationsdatei, Pfade anpassen):

```bash
export IMMO_DB_PATH=/ABSOLUTER/PRIVATER/PFAD/eml.db
export IMMO_QUICK_OUTPUT=/ABSOLUTER/PRIVATER/PFAD/pdfs
export IMMO_QUICK_CONFIG=/ABSOLUTER/PRIVATER/PFAD/eml.json
python3 tools/db_manager.py init
python3 tools/local_server.py 8765
# Zweites Terminal, gleiche Variablen und Checkout:
python3 tools/quick_worker.py
```

Windows verwendet entsprechend `$env:IMMO_DB_PATH = 'C:/.../eml.db'`,
`$env:IMMO_QUICK_OUTPUT = 'C:/.../pdfs'`, `$env:IMMO_QUICK_CONFIG = 'C:/.../eml.json'`
und `py -3` für dieselben Skripte. Den bisherigen Demo-Server zuvor beenden.

Echte Nachricht im Mailprogramm als vollständige `.eml` speichern (in Gmail:
Original anzeigen → Original herunterladen). Über **Lokaler Testimport (.eml)**
auswählen oder in den konfigurierten Eingang legen. Alternativ ein eigener Ordner:

```bash
python3 tools/quick_worker.py --import-eml /ABSOLUTER/PRIVATER/PFAD/eingang --once
```

`--import-eml` erwartet einen **Ordner**, keine einzelne Datei, und deaktiviert
Gmail für diesen Aufruf. Im Dateiscan wird die Originaldatei binär gelesen.
Der Dashboard-Upload verwendet `file.text()`/UTF-8 und ist auf 1 MB begrenzt;
der Dateiscan auf 2 MB. Für nicht UTF-8-kodierte historische EMLs den Ordnerimport
bevorzugen. Anhänge werden nicht ausgewertet.

**Aktuelle Einschränkung:** Auch eine echte EML wird beim lokalen Import als
`is_test=true` und „Agent · TEST“ markiert. Ihre Daten können trotzdem aus einer
echten Anzeige stammen. Der Abrufstatustext nennt für solche Imports irreführend
„lokale Anzeigenfixture“, obwohl ohne Fixture-Konfiguration öffentlicher Abruf
stattfindet. Quellen/Adapterkonfiguration sind hierfür maßgeblich. Eine eigene
Live-EML-Kennzeichnung und korrekte Adapteranzeige sind noch Entwicklungsarbeit.
Automatischer Telegram-Versand über `auto_send_new` erfasst diese lokalen Imports
nicht. Fehlt Ist-Miete, gibt es ohne Testreferenzen derzeit keine Marktmietzahl:
„Mietreferenz fehlt“, Teilanalyse und PDF bleiben möglich. Der manuelle Dashboard-
Upload wendet keine Mailfilter an; Ordnerimport nutzt `local.filters` mit
`senders`, `subjects`, `start_at`. Das ist keine Gmail-Verbindung.

## Tests und weitere Testfälle

```bash
node tests/test_schnellanalyse.js
python3 -m unittest discover -s tests -v
```

Alle Python-Tests verwenden synthetische Daten und temporäre DBs. Optional die
komplette mitgelieferte Testsammlung statt des Einzelangebots importieren:

```bash
python3 tools/quick_worker.py --import-eml tests/fixtures/quick_analysis/emails --once
```

Nur mit der **Demo-Konfiguration** ausführen. In einer frischen DB ergeben sich
sechs Anzeigenidentitäten, sieben Revisionen und sieben PDFs, einschließlich
Konflikten, HTML-Mail, fehlender Miete/Referenz und lokalem Versandtest.
Alle Adressen, URLs, Angebote und Mietreferenzen sind künstliche **TESTDATEN**;
Scout-URLs in `rents.json` sind kein Nachweis echter Mietangebote.
Für die Preisrevision die Demo-Konfiguration privat kopieren,
`local.listing_directory` auf den absoluten Pfad von
`tests/fixtures/quick_analysis/changed` setzen, dann:

```bash
python3 tools/quick_worker.py --config /ABSOLUTER/PRIVATER/PFAD/geaendert.json --import-eml tests/fixtures/quick_analysis/revisions --once
```

Optionaler Browser-Abnahmetest (separate Testabhängigkeit, Chromium erforderlich):

```bash
npm install --prefix /tmp/immo-browser-tools playwright
PLAYWRIGHT_MODULE=/tmp/immo-browser-tools/node_modules/playwright node tests/test_quick_browser.cjs
```

`IMMO_CHROMIUM` überschreibt `/usr/bin/chromium`. Der Test prüft
1440/768/390/320 px, Themes, Quellen, Download und Duplikate mit eigener temporärer
DB. Optional `pdftotext`/`pdftoppm` zur unabhängigen PDF-Prüfung nutzen.

## Berechnung und Datenqualität

Die vorhandene `assets/schnellanalyse_core.js` bleibt die einzige Quelle der
Schnellcheck-Formeln und Zielwerte. `tools/rechenkern.py:schnellanalyse` ruft
sie mit Node ohne Shell auf; 15 Sekunden Zeitlimit. Paritätstests prüfen den
Browseraufruf und den Python-Aufruf mit festen/prozentualen EK-Profilen und
vergleichen die Annuität mit `rechenkern.annuitaetenrate`. Der bestehende
Vollanalyse-Rechenkern hat weiterhin sein anderes Erwerbskosten-/Kostenmodell.

* Kaltmiete pro Monat × 12, Rendite bezogen auf den reinen Kaufpreis.
* Laufende Kosten: **Modellannahme 20 % der Kaltmiete**. Belegtes Hausgeld,
  nicht umlagefähige Anteile und Rücklagen werden separat angezeigt und nicht
  zusätzlich abgezogen. Ein tatsächlicher Einzelkostenmodus ist hier nicht aktiv.
* Darlehen = max(0, Kaufpreis − Eigenkapital); Rate aus Sollzins + anfänglicher Tilgung.
* Minus-10-%-Szenario: Miete/Kosten und festes EK unverändert;
  prozentuales EK wird mit dem neuen Preis neu berechnet.
* Cashflow **vor Steuern**; Erwerbskosten, Leerstand und Steuerwirkung fehlen
  im Schnellcheck-Modell und sind ausdrücklich nicht enthalten.
* Ziele strikt vor Rundung: Rendite > 5 %, Cashflow > 0 €, Faktor < 20.
  Mindestens ein bekanntes Kriterium fällt durch → nicht bestanden;
  alle erfüllt → bestanden; sonst unvollständig. Rendite und Faktor sind abhängig.

Extraktion: dokumentierte JSON-LD-Gesamtpreise in EUR, Wohnfläche mit passender
Einheit und explizite deutsche Feldbezeichnungen in HTML/Text. Grundstück,
Warmmiete, Jahres-/Monatsmiete und Kostenanteile werden getrennt gespeichert.
Generische `size`-Werte werden nicht als Wohnfläche übernommen. EUR/m²-Preise,
Miete je Einheit und Jahresmiete werden nicht als Gesamtpreis/Monatsmiete gelesen.
Belegte Jahreskaltmiete wird mit dokumentiertem `/12` abgeleitet. Unbekannte
Werte bleiben `null`, inklusive unbekannter Finanzierung. E-Mail-Angebotsblöcke
werden dem jeweiligen Link zugeordnet; nicht eindeutig zuordenbare Angaben
bleiben offen. Keine Zahl stammt aus Modellwissen.

Jeder Inputwert enthält Wert, Einheit, BELEGT/ABGELEITET/ANNAHME/UNBEKANNT,
Quelle, Abrufzeit, Textstelle/Quellfeld und Ableitungsbasis. Alternativen werden
als Kandidaten gespeichert. Bei Widerspruch wird das Feld gesperrt und der
Konflikt angezeigt. BELEGT bedeutet Quellenangabe, nicht bestätigte Unterlage.
Anzeigen-/E-Mail-Anweisungen werden niemals ausgeführt; es gibt keinen
Toolzugriff aus Quelltext und keine promptgesteuerte Extraktion. Live-Portal-
Layouts und ungewöhnliche Freitextformate wurden noch nicht abgenommen.

## Mietreferenzen

`RentReferenceAdapter` ist austauschbar. `ScoutRentAdapter` ist eine deaktivierte
Schnittstelle und liefert **keine Livezahlen**. Ein verfügbarer Scout-Vertrag,
autorisierter Zugang und eine implementierte/abgenommene Datenanbindung fehlen.
Kein Captcha- oder Login-Bypass. Fehlende Referenz ergibt „Mietreferenz fehlt“,
Teilberechnung und PDF mit nicht berechenbaren mietabhängigen Kennzahlen.

`LocalRentAdapter` prüft ausdrücklich dokumentierte Test-Angebote:
Scout-URL/ID, identische PLZ, räumliche Ebene PLZ, passende Objektart,
vorhandenen Stadtteil/Zustand, Fläche ±25 %, Nettokaltmiete und Quellbeleg mit
Datenstand/Abrufzeit. URL-Duplikate werden entfernt. Median der EUR/m²-Werte
× belegte Wohnfläche; Auswahl, Stichprobengröße und jede Quelle werden gespeichert.
Stadtmittelwerte werden nicht zu PLZ-Werten erklärt. Angebotsmieten sind kein
Mietspiegel. Marktmiete befüllt niemals `cold_rent`/Ist-Cashflow; bei vermieteten
Objekten ohne Ist-Miete gibt es ausschließlich ein gekennzeichnetes Marktszenario.

## Gmail später ausdrücklich aktivieren

**Implementiert, extern ungetestet:** Desktop-OAuth-Anmeldung, Token-Erneuerung,
lesende REST-Aufrufe `messages.list`/`messages.get`, gezielte Suche, Pagination,
Startzeitpunkt, lokale Absender-/Betreffprüfung und persistenter Synchronisationsstand.
Kein Push, keine E-Mail-Modifikation. Die folgenden Schritte wurden nicht gegen
ein Google-Konto ausgeführt. Offizielle Gmail-/OAuth-Dokumentation zuletzt am 07.10.2026 geprüft:
[Python/Desktop-Client](https://developers.google.com/workspace/gmail/api/quickstart/python),
[Installed-App-OAuth](https://developers.google.com/identity/protocols/oauth2/native-app),
[run_local_server](https://googleapis.dev/python/google-auth-oauthlib/latest/reference/google_auth_oauthlib.flow.html),
[Gmail-Suche](https://developers.google.com/workspace/gmail/api/guides/filtering),
[Scope](https://developers.google.com/workspace/gmail/api/auth/scopes),
[Tokenlaufzeiten](https://developers.google.com/identity/protocols/oauth2#expiration).

1. Google-Cloud-Projekt anlegen und **Gmail API** aktivieren. In Google Auth Platform
   Branding, Audience und Data Access konfigurieren. Für privates Gmail External
   wählen, im Testmodus das eigene Konto als Testnutzer hinzufügen; Internal ist
   nur innerhalb der geeigneten Workspace-Organisation verfügbar.
2. OAuth-Client vom Typ **Desktop app** erstellen und Client-JSON herunterladen.
   Die Datei außerhalb des Repositories ablegen. Kein Web-App-Client und keine
   Dashboard-Redirect-URI verwenden. Der Code ruft
   `InstalledAppFlow.run_local_server(port=0, timeout_seconds=300, access_type='offline', prompt='consent')`
   auf: Redirect **`http://localhost:<dynamischer-freier-Port>/`**. Er wird vom
   lokalen OAuth-Hilfsserver gewählt, unabhängig von Dashboard-Port 8765/8000.
3. Es wird ausschließlich **`https://www.googleapis.com/auth/gmail.readonly`**
   angefordert; der gespeicherte Token muss genau diese Scope-Liste enthalten.
   Googles Einstufung als restricted scope und gegebenenfalls Verifikation/
   Organisationsfreigabe beachten. Eine persönliche Testeinrichtung ist kein
   Nachweis einer für andere Nutzer freigegebenen Anwendung.
4. Pakete in einer privaten Python-Umgebung außerhalb des Webroots installieren:

```bash
python3 -m venv "$HOME/.local/share/immo-investanalyse/venv"
. "$HOME/.local/share/immo-investanalyse/venv/bin/activate"
python3 -m pip install -r tools/requirements-gmail.txt
```

PowerShell, nachdem der private übergeordnete Ordner angelegt wurde:

```powershell
$private = Join-Path $env:LOCALAPPDATA 'immo-investanalyse'
New-Item -ItemType Directory -Path $private -Force | Out-Null
py -3 -m venv (Join-Path $private 'venv')
& (Join-Path $private 'venv/Scripts/python.exe') -m pip install -r tools/requirements-gmail.txt
```

Die jeweilige Venv-Python-Datei für Anmeldung und Worker verwenden. Zugangsdaten
gehören nicht ins Repository, nicht in SQLite und nicht in den Chat. Der Code
verwirft Pfade, die in den Webroot auflösen. Private Ordner/Dateien unter POSIX
auf 0700/0600 begrenzen; Windows-Zugriff über Benutzerprofil und passende ACLs
begrenzen, POSIX-`chmod` ist dort kein gleichwertiger ACL-Schutz.

In einer **separaten privaten Betriebskonfiguration ohne Demo-Adapter**:

```json
"gmail": {
  "enabled": false,
  "start_at": "2026-10-06T12:00:00+02:00",
  "query": "subject:Suchalarm",
  "senders": ["TATSAECHLICHER-ABSENDER@PORTAL-DOMAIN"],
  "subjects": ["TATSAECHLICHER BETREFFTEIL"],
  "client_path": "/PRIVAT/gmail-client.json",
  "token_path": "/PRIVAT/gmail-token.json"
}
```

Block in das vollständige Konfigurations-JSON einfügen, echten Startzeitpunkt,
Pfade und Filter ersetzen. `query` ist Gmail-Suchsyntax; `senders` sind genaue
E-Mail-Adressen, `subjects` sind Teilstrings. Ein passend eingerichteter Portal-
Suchalarm und dessen tatsächliches E-Mail-Format wurden hier noch nicht geprüft.
Die API-Suche ergänzt `after:<Unix-Zeit>` und konfigurierte `from:`-Adressen;
Betreffprüfung findet zusätzlich lokal statt. Keine Übergabe des Posteingangs an KI.

**Anmeldung ist eine ausdrückliche externe Aktion**, kein lokal getesteter Schritt:

```bash
python3 tools/quick_worker.py --config /PRIVAT/automation.json --gmail-authorize
```

Unter Windows denselben Aufruf mit der privaten Venv-Python-Datei und tatsächlichem
Konfigurationspfad ausführen. Im Browser eigenes Konto auswählen und zustimmen.
Der Code schreibt Access-/Refresh-Token nach `gmail.token_path`, nicht in SQLite.
Danach `gmail.enabled: true` setzen und Prozesse mit dieser Konfiguration neu starten.
Ohne Token verarbeitet der Gmail-Adapter nichts; in aktiviertem Gmail-Modus wird
nicht parallel der lokale Eingangsordner gescannt. Ein Dashboard-EML-Upload bleibt
möglich, oder `--import-eml` wählt ausdrücklich den lokalen Modus.

**Gezielter erster Live-Test, erst nach bewusster Freigabe:** Telegram deaktiviert
lassen, frische temporäre DB verwenden. Startzeit unmittelbar vor genau einer
neuen Suchalarm-Mail setzen. Aus „Original anzeigen“ deren Header-`Message-ID`
übernehmen und `query` vorübergehend auf `rfc822msgid:<HEADER-ID>` beschränken
(die Platzhalter ersetzen; dies ist nicht die interne Gmail-Nachrichten-ID).
Mit dem konfigurierten Absender/Betreff muss diese eine Mail übereinstimmen.
`python3 tools/quick_worker.py --once` liest sie; `/api/quick-analyses` und
`qa_messages.adapter='gmail'` in der temporären DB prüfen. Eine Mail kann mehrere
Angebote erzeugen. Den Aufruf wiederholen: keine doppelte Nachrichtenverarbeitung.
Danach erst den regulären gezielten Filter setzen. Der Checkpoint wird nach
vollständig beendetem Scan geschrieben, mit einem Tag Überlappung; Message-IDs
verhindern Wiederverarbeitung. Ein Gmail-Fehler ist im Workerstatus sichtbar,
verändert aber keine Nachricht. Die Dashboard-Verbindungsbeschriftung zeigt
nach dem erfolgreichen API-Abruf den zur aktuellen Konfiguration passenden Verbindungsstatus.

Der Worker erneuert abgelaufene Access-Tokens über den Refresh-Token und schreibt
die Token-Datei neu. Bei **External + Testing** läuft der Refresh-Token mit
`gmail.readonly` laut Google nach sieben Tagen ab. Widerruf, Passwortwechsel,
Nichtnutzung und Konten-/Adminbeschränkungen können ebenfalls erneute Anmeldung
erfordern. Für Dauerbetrieb den passenden Veröffentlichungs-/Freigabestatus klären;
kein unbegrenzt gültiges Token versprechen. Der interaktive OAuth-Dialog hat fünf Minuten Zeitlimit und muss vom Nutzer abgeschlossen werden; er ist kein unbeaufsichtigter Worker-Autostart.

## Telegram später ausdrücklich aktivieren

**Implementiert, extern ungetestet:** `TelegramAdapter.send` verwendet die offizielle
Bot API `sendDocument`, PDF plus Caption (auf 1.024 Zeichen gekürzt), feste erlaubte
numerische Chat-ID, 25 Sekunden Timeout, `retry_after` bei Rate Limit und persistente
Versandbestätigung. Die komplette Nachrichtenvorschau ist im Dashboard gespeichert;
sehr lange Vorschauen werden in Telegram abgeschnitten. Kein Empfangsbot/Webhook
und kein Chat-ID-Einrichtungsassistent im Repository.
Offizielle Quellen am 06.10.2026 geprüft:
[Bot erstellen](https://core.telegram.org/bots/tutorial#obtain-your-bot-token),
[getUpdates](https://core.telegram.org/bots/api#getupdates),
[sendDocument](https://core.telegram.org/bots/api#senddocument).

1. In Telegram beim offiziellen **@BotFather** `/newbot` verwenden, Namen vergeben
   und Token privat sichern. Dem eigenen neuen Bot im gewünschten privaten Chat
   `/start` schicken. Bot darf nicht nur über BotFather existieren, sondern muss
   den Zielchat erreichen können. Für einen einfachen ersten Test privater Chat
   statt Gruppen-/Kanal-Spezialfällen verwenden.
2. Mit der offiziellen Bot-API-Methode `getUpdates` die neue Nachricht abrufen und
   die Zahl in `result[].message.chat.id` ablesen. Das ist **nicht** der Botname,
   Benutzername oder die Bot-ID vor dem Doppelpunkt im Token. Eine vorhandene
   Webhook-Konfiguration verhindert `getUpdates`; mit `getWebhookInfo` prüfen und
   nicht ungefragt eine andere Bot-Integration löschen. Es gibt hierfür noch
   keinen Repository-CLI-Befehl. Diese API-Abfrage künftig selbst bewusst ausführen;
   keine tokenhaltige URL im Chat oder in protokollierten Shellbefehlen hinterlegen.
3. Private JSON-Datei außerhalb des Projekts anlegen, mit den tatsächlichen Werten:

```json
{"bot_token":"ECHTER-BOT-TOKEN","allowed_chat_id":"ECHTE-NUMERISCHE-CHAT-ID"}
```

Die Chat-ID lässt sich später mit diesem **bewusst externen, hier nicht ausgeführten**
Python-Aufruf ermitteln. Die private JSON-Datei muss bereits den echten Bot-Token
enthalten; `allowed_chat_id` wird danach mit der ermittelten Zahl ergänzt. Unter
Linux/macOS im privaten Venv ausführen:

```bash
python3 - /ABSOLUTER/PRIVATER/PFAD/telegram.json <<'PYCHAT'
import json, sys, urllib.request
from pathlib import Path
secret = json.loads(Path(sys.argv[1]).expanduser().read_text())
try:
    with urllib.request.urlopen('https://api.telegram.org/bot' + secret['bot_token'] + '/getUpdates?timeout=0', timeout=20) as response:
        data = json.load(response)
    if not data.get('ok'):
        raise ValueError()
except Exception:
    raise SystemExit('Chat-ID-Abruf fehlgeschlagen; Token, Netz oder bestehenden Webhook prüfen.') from None
for update in data.get('result', []):
    message = update.get('message') or update.get('channel_post')
    if message:
        print(message['chat']['id'], message['chat'].get('type'), message['chat'].get('title', 'privater Chat'))
PYCHAT
```

Für PowerShell denselben Python-Inhalt als private `.py`-Datei speichern und mit
der Venv-Python-Datei ausführen, wobei der private JSON-Pfad als erstes Argument
nach dem Skriptpfad folgt; Bash-Heredoc-Syntax ist keine PowerShell-Syntax.
Ein leeres Ergebnis bedeutet: noch keine passende unbestätigte Nachricht; dem
Bot zuerst `/start` schicken. Niemals Token oder vollständige API-URL ausgeben.

4. In einer privaten Konfiguration zunächst
   `"telegram": {"enabled": false, "secret_path": "/PRIVAT/telegram.json", "auto_send_new": false}`.
   Zugriffsrechte wie bei Gmail einschränken. **Nie einfach Telegram in der
   mitgelieferten Demo-Konfiguration einschalten:** deren
   `local.notification: true` + `local.auto_deliver_test: true` reiht neue
   TEST-PDFs automatisch zum Versand ein; mit aktiviertem Telegram würde dieser
   Job den echten Telegram-Adapter verwenden. Beide Test-Versandflags entfernen
   oder auf `false` setzen, bevor echter Telegram-Versand aktiviert wird.

**Genau einen Versand mit PDF bewusst testen:** separate frische temporäre DB,
leerer Mailordner, Gmail deaktiviert, `local.notification: false`,
`local.auto_deliver_test: false`, Telegram noch deaktiviert. Genau eine lokale
EML importieren und `--once` ausführen: eine Analyse/PDF, kein Versandauftrag.
Für einen künstlichen TEST-Angebotsabruf dürfen die lokalen Listing-/Miet-Fixtures
weiterhin gewählt werden; nur die beiden Versandflags müssen ausgeschaltet sein.
Analyse-UUID aus `/api/quick-analyses` nehmen. Danach ausdrücklich
`telegram.enabled: true`, `auto_send_new: false` setzen. Mit dieser Umgebung:

```bash
# ANALYSE-UUID durch genau diese neue items[].id ersetzen:
python3 tools/quick_worker.py --deliver ANALYSE-UUID
python3 tools/quick_worker.py --once
```

Dies sind künftig **echte Versandaktionen**, hier nicht ausgeführt. `--deliver`
reiht nur den Auftrag ein; der nächste Worker verarbeitet ihn. Im Zielchat die PDF
öffnen und in SQLite/API `delivery_status: versendet` sowie Message-ID/Chat-ID/Datum
im `delivery_receipt` prüfen. Der API-Dashboard-Datensatz enthält derzeit nicht
das Receipt selbst; dieses liegt in `qa_analyses.delivery_receipt` als JSON.
Timeout/unklare Antwort oder Neustart während Versand → `unklar`, keine automatische
Wiederholung; vor manuellem Retry den Chat prüfen. Kein Exactly-once-Versprechen.

**Schutz vor alten Ergebnissen:** Aktivierung allein scannt alte Analysen nicht
zum Versand. `queue_delivery` verweigert bereits `versendet`/`lokal_getestet`;
unklare Zustellung erfordert den bewussten Retry des vorhandenen Jobs.
`auto_send_new: true` benötigt zusätzlich `send_start_at` mit Zeitzone und gilt
nur bei PDF-Erstellung für nicht als Test markierte Nachrichten mit Eingangs-
und Analysezeit ab diesem Datum. Vor Aktivierung bestehende `send`-Jobs auf
`ready`/`running` prüfen: solche bereits eingereihten Aufträge verarbeitet ein
Worker mit aktiviertem Telegram. Für den ersten Test deshalb frische DB und
keine automatischen Versandflags benutzen. Es gibt keine pauschale Garantie,
dass ein beliebiger vorhandener Test-Versandjob trotz Adapterwechsel lokal bleibt.

## ImmobilienScout24: notwendige Entwicklungsarbeit

Ein öffentlicher **Verkaufsanzeigenabruf** ist implementiert; er ist kein
Mietreferenzzugriff. `ScoutRentAdapter.estimate` ist nur die vorbereitete Schnittstelle
und liefert immer `None`. Es gibt derzeit weder Scout-OAuth-/API-Anbindung noch
Live-Mietsuche, konfigurierbaren Scout-Key oder importierbare Live-Referenzdatei.
`LocalRentAdapter` ist ausschließlich der geprüfte Testadapter mit künstlichen
Referenzen. Ein Schlüssel allein aktiviert deshalb keine Mietreferenzfunktion.

Zuerst geeigneten rechtmäßigen Datenzugang mit Mietreferenzen, Quellenbeleg,
Datenstand und ausreichender räumlicher Zuordnung klären. Das offizielle
[Scout-Developer-Portal](https://api.immobilienscout24.de/) beschreibt verschiedene
API-Produkte; daraus folgt kein bestätigter Zugriff dieses Projekts auf allgemeine
PLZ-Mietangebote. Anschließend passenden Adapter implementieren und seine Felder,
Berechtigungen, Fehlerfälle und Herkunft live abnehmen. Bis dahin: keine erfundene
Marktmiete; bei fehlender Kaltmiete Teilanalyse, „Mietreferenz fehlt“ und nicht
berechenbare mietabhängige Kennzahlen, trotzdem PDF. Eine belegte Ist-Miete aus
E-Mail/Anzeige benötigt den Referenzadapter nicht.

## Warteschlange, Wiederholung und dauerhafter Betrieb

Jobs: `analysis`, `pdf`, `send`; Zustände `ready` (erkannt/ausstehend), `running`
(in Verarbeitung), `done`, `failed`, `uncertain`. Analysequalität
vollständig/teilweise, PDF-Status und Versandstatus sind unabhängig.
Atomare Jobübernahme mit `BEGIN IMMEDIATE`, UUID-Lease und 300 Sekunden Laufzeit;
veraltete Worker dürfen keinen neu übernommenen Job überschreiben. Jobs derselben
Anzeige werden nicht gleichzeitig analysiert. Begrenzte Parallelität 1–4 Threads,
standardmäßig drei Versuche mit exponentiellem Backoff (30/60 Sekunden).
401/403 erzeugen sofort eine gespeicherte Teilanalyse/PDF mit manueller
Wiederholung; temporäre Abruffehler werden begrenzt wiederholt und anschließend
ebenfalls als Teilanalyse gespeichert. Node-/Konfigurationsfehler bleiben sichtbar.

```bash
python3 tools/quick_worker.py --retry JOB-ID
# Danach verarbeitet der laufende Worker oder ein --once-Durchlauf den Schritt.
```

Der Dashboard-Button wiederholt ausschließlich den betroffenen fehlgeschlagenen
Schritt. PDF-/Versandfehler verursachen keine erneute Analyse. Unklare Zustellung
verlangt eine bewusste Wiederholung. Auf SIGINT/SIGTERM beendet sich der Worker
nach laufenden Jobs; es ist weder Dashboard noch Editor/Chat erforderlich.

Ein dauerhafter Worker benötigt einen eingeschalteten Rechner, Python/Node im
Dienst-PATH, schreibbaren DB-/Ausgabepfad und später Internetzugang. Für einen
Dienst/Supervisor `python3 /ABSOLUTER/REPOPFAD/tools/quick_worker.py` als eigenen
Prozess mit `WorkingDirectory` auf dem Repository, `IMMO_QUICK_CONFIG`, optional
`IMMO_DB_PATH`/`IMMO_QUICK_OUTPUT` und automatischem Neustart verwenden. Keine
Dienstinstallation oder Autostartaktivierung wurde hier durchgeführt.

**Festgelegter Automationsrechner zunächst: `omarchy`, Linux-Arbeitsplatz mit
Checkout `/home/kev/Work/immo-investanalyse`.** Kein zweiter Rechner darf
unabhängige Worker-Schreibvorgänge auf seine Git-Kopie dieser DB ausführen.
`worker_host` kann den Worker zusätzlich auf genau diesen Hostnamen begrenzen.
Atomare Leases gelten für dieselbe SQLite-Datei, nicht für Git-Kopien auf anderen Hosts.

## Migration und Git-Synchronisation

`tools/migrations/001_quick_analysis.sql` ergänzt ausschließlich `qa_*`-Tabellen.
Serverstart, Workerstart und `db_manager.py init` führen die idempotente Migration
aus; bestehende Objekte, Kalkulationen und Ratings bleiben erhalten. Die
Entwicklungstests verwenden temporäre Datenbanken. Bei der anschließenden lokalen
Inbetriebnahme des echten Servers am 07.10.2026 wurde die additive Migration in
der Repository-DB ausgeführt; reguläre Datensätze blieben unverändert. Diese
Laufzeitänderung gehört nicht zum Code-Commit des Einstellungsmenüs.

Vor Git-Synchronisation Worker **und** Server sauber beenden, auf Prozessende
warten, `python3 tools/db_manager.py check` ausführen und erst dann die DB
committen/pullen/pushen. Niemals zwei unterschiedliche DB-Binärstände mergen.
Bei Hostwechsel den alten Worker stoppen und den neuen Betriebsrechner bewusst
festlegen. Tokendateien und private Konfiguration werden nicht über Git verteilt.
SQLite-Journal/WAL/SHM-Dateien gehören nicht in Git.

PDFs sind Laufzeitartefakte und werden standardmäßig ignoriert. Nach Git-Transfer
ist der PDF-Pfad in der DB erhalten, die Datei möglicherweise nicht vorhanden:
auf dem Betriebsrechner die PDF-Ausgaben separat kopieren oder mit
`python3 tools/quick_worker.py --rebuild-pdf ANALYSE-UUID` gezielt neu einreihen
und anschließend den Worker starten. Ausgabeverzeichnis für Server und Worker identisch setzen. Verlorene
PDFs werden durch den Download-Endpunkt als nicht verfügbar gemeldet; das
gespeicherte Ergebnis bleibt erhalten. Ein hart unterbrochener PDF-Job kann eine
nicht referenzierte PDF im gemeinsamen Verzeichnis hinterlassen; keine Objektordner.

## KI, Kosten und nachgewiesener Stand

Kein Live-KI-Anbieter, kein Modell, kein API-Key und keine KI-Kosten: Extraktion
ist deterministisch; Badge **Agent** bezeichnet den automatisierten Ablauf.
Eine spätere KI-Ergänzung muss ein getrenntes Datenextraktionsinterface mit
Schema-/Quellenvalidierung, ausdrücklicher Modellkonfiguration und Kostenlimit
bekommen. Die Rechenformeln bleiben deterministisch. Aktuell wird kein Inhalt
an eine KI oder einen kostenpflichtigen Dienst übergeben.

Lokal abgenommen: EML → unabhängige Angebote → Quelle/Referenz → gemeinsamer
Rechenkern → persistente Revision/Jobs → zweitseitige PDF → Dashboard → lokaler
Versandtest, einschließlich Fehler-, Neustart- und Parallelitätsfälle.

Vorbereitet: Gmail OAuth und lesende API, Telegram Bot API, austauschbarer
Scout-Mietadapter. **Keine** Gmail-Verbindung, Scout-Livequelle, Telegram-
Zustellung oder Live-Portalextraktion wurde in diesem Auftrag nachgewiesen.
Es fehlen OAuth-Projekt/Client/Token, echte Alarmfilter, freigegebenes Profil,
Scout-Zugang mit geeigneter Implementierung und Telegram-Token/Chat-ID.

Bestehender, außerhalb dieser Erweiterung liegender Fehler: Im Ausgangsbranch
ist `db_manager.py:export_json` durch ein literales `\n` in der vorausgehenden
Kommentarzeile nicht als Funktion definiert; der historische `export-json`-
CLI-Zweig kann daher nicht funktionieren. Das wurde anhand des Ausgangscommits
und der AST-Funktionsliste bestätigt. Der bestehende Server-Endpunkt
`/api/export/<ID>` ist davon unabhängig. Die Schnellanalysen nutzen diesen
CLI-Export nicht; der Fehler wurde hier nicht nebenbei repariert.

## Offene Arbeiten in Betriebsreihenfolge

| Komponente | Aktueller Stand | Konkrete nächste Handlung | Erforderlicher Zugang | Überprüfbares Erfolgskriterium |
|---|---|---|---|---|
| Lokaler Ablauf | Implementiert und unter Linux lokal geprüft | Demo mit eigener temporärer DB ausführen | Python/Node, keine Konten | Eine TEST-EML erzeugt Karte, gespeicherte Kennzahlen, zweitseitige PDF und lokalen Testbeleg |
| Finanzierungsprofil | Formular und Berechnung implementiert/lokal geprüft; bisher TEST-Profil | Eigene EK-/Zins-/Tilgungswerte im Menü speichern | Eigene Finanzierungsentscheidung, ggf. Bankangebot | Neue Analyse speichert gewähltes Profil; Basis/−10 % nachvollziehbar |
| Echte Alarmfilter/Portalformate | Konfigurationsfilter und Parser implementiert; echte Formate extern ungetestet | Einen echten Alarm als EML prüfen, Absender/Betreff/Linklayout abgleichen, Parser bei Bedarf erweitern | Tatsächliche Suchalarm-Mail; öffentliche Anzeige | Genau enthaltene Angebote, nachvollziehbare Felder, keine irrelevanten Links |
| Gmail-OAuth | Code und Menüassistent implementiert, extern ungetestet | Cloud/Desktop-Client im Menü hochladen, anmelden und gezielten Ein-Mail-Test durchführen | Google-Konto, Cloud-Projekt, OAuth-Client/Token | Eine neue Mail mit adapter=gmail, Duplikat unterdrückt, keine Mailänderung |
| Scout-Mietreferenzen | Schnittstelle und Testadapter vorbereitet; Liveadapter noch nicht implementiert | Geeigneten Zugang klären, Adapter entwickeln und abnehmen | Autorisierte Datenquelle/Vertrag und eventuell API-Zugang | Fehlende Ist-Miete ergibt gekennzeichnete Schätzung mit echten Vergleichsquellen; Ausfall bleibt unbekannt |
| Telegram | API-Sendecode implementiert, extern ungetestet; lokal deaktiviert | Bot/Chat-ID privat konfigurieren, Testflags entfernen, genau einen bewussten PDF-Versand testen | Bot-Token und erlaubte Chat-ID | PDF im richtigen Chat und persistenter echter Versandbeleg; kein Altbestand-Sammelversand |
| Dauerhafter Worker | Menü-Start/Stop, Polling/Queue/Hostbegrenzung lokal geprüft; kein Autostartdienst installiert | Einen Betriebsrechner festlegen, Dienst/Supervisor mit richtigen Pfaden installieren | Lokaler Benutzer-/Dienstzugriff; später Internet | Worker verarbeitet bei geschlossenem Browser/Editor und nach Neustart; saubere Stop-/Sync-Prozedur |
| Live-Status und lokale EML-Kennzeichnung | Gmail-Status nach erfolgreichem Scan implementiert/lokal simuliert geprüft; lokale EML weiterhin TEST | Reale EML-Kennzeichnung und Abruftext korrigieren; Gmail live abnehmen | Echte Alarm-Mail/Google-Zugang | Herkunft/Status stimmen mit tatsächlicher Quelle und bestätigtem Abruf überein |
| KI-Extraktion | Noch nicht implementiert, derzeit nicht erforderlich | Nur bei Bedarf schema-/quellenvalidierte Schnittstelle mit Modell-/Kostenkonfiguration entwickeln | Falls gewählt Anbieter/API-Key | Expliziter Modellaufruf, validierte Datenherkunft und Kostenlimit; Rechenkern unverändert |
| Git-Commit/Push | Übergabe aus dem lokalen Feature-Branch direkt nach `portfolio-current-sync` vereinbart; historischer Stand unten | Aktuellen Git-Stand prüfen, neuere Remote-Commits erhalten, ohne Force-Push übertragen | Eigene Autorangaben; GitHub-Schreibzugriff | Remote-Ziel enthält Implementierung, Betriebsanleitung und bestehende Portfolio-Commits |

## Historischer Git-Zustand der Betriebsprüfung vom 06.10.2026

Am Beginn der Betriebsprüfung am 06.10.2026 lag HEAD weiterhin auf `a6ea2ee`,
identisch zur Ausgangsbasis `origin/portfolio-current-sync`. Der lokale Branch
`codex/automatische-schnellanalysen` existiert; `git ls-remote --heads origin
codex/automatische-schnellanalysen` lieferte keinen Remote-Branch. 43 Dateien waren
bereits gestaged; es gab keine ungestagten Änderungen. `user.name` und `user.email`
waren nicht gesetzt, also wurde keine Autoridentität ergänzt und kein Commit
oder Push ausgeführt. Diese Betriebsanleitung und der README-Link werden für die
Review **zusätzlich ungestaged** geändert; der vorhandene Index bleibt erhalten.

Ein lokaler Branch ist ein Zeiger auf den aktuellen Commit. „Gestaged“ ist der
für einen nächsten Commit vorgemerkte Dateiinhalt, noch kein neuer Commit.
Ein Commit speichert einen lokalen Snapshot mit tatsächlichem Autor; Push
überträgt ihn nach GitHub und legt dort gegebenenfalls den Branch an.
Die ungestagten Dokumentationsänderungen müssen vor einem vollständigen Commit
zusätzlich aufgenommen werden. Eigene Werte einsetzen, nicht die Platzhalter:

```bash
git status --short --branch
git config user.name "DEIN TATSAECHLICHER NAME"
git config user.email "DEINE TATSAECHLICHE AUTOR-E-MAIL"
git add README.md docs/AUTOMATISCHE_SCHNELLANALYSEN.md
git diff --cached --check
git diff --cached --stat
git commit -m "Automatische Schnellanalysen mit lokalem Worker und Betriebsanleitung"
# Neuere Änderungen auf dem vereinbarten Zielbranch übernehmen:
git fetch origin
git merge origin/portfolio-current-sync
# Anschließend relevante Tests ausführen und das Ergebnis prüfen.
# Bewusst ausführen, mit GitHub-Schreibzugriff, ohne Force-Push:
git push origin HEAD:refs/heads/portfolio-current-sync
```

Keine Tests oder Zugangsdaten in die versionierte DB übernehmen. Commit/Push
sind in der hier dokumentierten Betriebsprüfung vom 06.10.2026 nicht ausgeführt worden.

## Ergebnis des dokumentierten lokalen Beispielablaufs

Erneut geprüft am 06.10.2026 mit einer frischen DB unter
`/tmp/tmp.KFUBEboPtx/demo.db`, PDFs unter `/tmp/tmp.KFUBEboPtx/pdfs`:

- Die Linux-Befehle aus „Erste lokale Nutzung“ wurden aus der Dokumentation
  übernommen und ausgeführt: ein Angebot, ein gespeichertes Ergebnis, eine PDF,
  `lokal_getestet`, kein reguläres Objekt.
- Auch der kurze CLI-Einstieg wurde wörtlich mit einer zweiten neuen DB
  `/tmp/tmp.6Mz86xUKOp/demo.db` geprüft: eine Analyse, ein korrekter PDF-Download,
  Basis-Cashflow −150 € und Szenario 0 €, kein Jobstart durch GET.
- Der Server auf `127.0.0.1:8765` und ein separat gestarteter Dauerworker verwendeten
  dieselbe Umgebung. Browser-Upload der Einzelmail: 0 neue Angebote; Upload der
  Mehrfachmail: 5 weitere Angebote, insgesamt 6 Karten/PDFs. Keine Browserfehler.
- Quellen-/Annahmenansicht, PDF-Download und manuelle Wiederholung des absichtlich
  blockierten Jobs wurden im Browser geprüft; anschließend CLI `--retry 7` und
  `--once`. Weiterhin 6 Analysen/6 PDFs, der absichtlich blockierte Job erneut
  `failed`. Wiederholung behebt keine weiterhin bestehende HTTP-403-Blockade.
- Test-Marktmiete: 660 €/Monat aus zwei künstlichen Vergleichsangeboten;
  Ist-Cashflow bleibt unbekannt. PDF: zwei A4-Seiten, Text und gerenderte Seiten
  für Ist-Miete/Marktszenario geprüft, Quellenlinks im PDF vorhanden.
- 44 Python-Tests und 14 JavaScript-Rechentests bestanden. Separater Chromium-Test:
  1440/768/390/320 px, 7 Schnellanalysen plus 1 künstliches reguläres Objekt,
  keine JavaScript-Fehler. Die 7 statt 6 Ergebnisse stammen aus der kompletten
  Fixturesammlung einschließlich zusätzlicher Konfliktrevision.
- Repository-DB vor/nach: Git-Objekthash
  `e6e96415785dfd86dcc5b65daf36a5fd67030d9f`, identisch zur Ausgangsbasis.
  Keine Änderungen unter `objekte/`; keine vorhandenen Immobilien als Testdaten.
  Testprozesse werden nach Prüfung beendet; keine Gmail-/Telegram-/Scout-Verbindung.

Die temporären Artefakte sind kein dauerhaft installierter Betrieb. Windows und
macOS sowie echte Portal-Layouts und externe APIs wurden nicht live geprüft.

## Abnahme des Einstellungsmenüs (07.10.2026)

- 56 Python-Tests und 14 JavaScript-Rechentests bestanden. Die neuen Akzeptanztests mit privaten temporären Ordnern/DBs prüfen: Formularvalidierung,
  private OAuth-Datei, keine Geheimnisse in Antworten/DB, keine GET-Nebenwirkungen,
  blockierte Altbestand-Aktivierung, kein Gmail mit Test-Anzeigen/Mietreferenzen,
  tatsächlicher separater Workerstart, Stop nach Controller-Neustart und EML→PDF.
- Chromium: Menü bei 1440/768/390/320 px in beiden Themes, deutsche Zahlen
  `30.000`/`4,60`, Speichern, Start/Stop und neue TEST-EML→Einzelprüfung→PDF-Download.
  Neue TEST-Analyse: Basis-Cashflow −285 €/Monat (4,6 % Zins, 2 % Tilgung);
  bestehende sieben Schnellanalysen und ein synthetischer Portfolio-Datensatz
  unverändert. Keine echte Gmail-/Telegram-/Scout-Verbindung.
- Komponenteninstallation und Google-Anmeldung wurden mit lokal simulierten
  Prozessstarts geprüft, nicht tatsächlich gegen PyPI/Google ausgeführt.
  Windows/macOS und echte Anzeigenlayouts weiterhin extern ungetestet.
