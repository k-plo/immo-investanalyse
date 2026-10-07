#!/usr/bin/env python3
"""Lokaler Webserver fuer die Immobilien-Portfolio-App."""
from __future__ import annotations

import json
import sqlite3
import sys
import os
import re
import threading
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from db_store import RevisionConflict, get_object, import_listing, new_candidates, portfolio_rows, save_object, set_archive_status, set_photo
from listing_import import ListingError
from quick_store import QuickStore
from quick_adapters import parse_eml
from quick_extract import message_entries
from quick_worker import load_config, DEFAULT_OUTPUT
from quick_settings import AutomationControl

BASE = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("IMMO_DB_PATH", BASE / "immo_datenbank.db"))
DEFAULT_PORT = 8000
CONTROL_LOCK = threading.Lock()


class PortfolioHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(BASE), **kwargs)

    def quick_control(self):
        with CONTROL_LOCK:
            if not hasattr(self.server, 'qa_control'):
                self.server.qa_control = AutomationControl(QuickStore(DB_PATH), DEFAULT_OUTPUT)
            return self.server.qa_control

    def send_json(self, payload: object, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def local_origin(self) -> bool:
        origin = self.headers.get("Origin")
        if not origin:
            return True
        parsed = urlparse(origin)
        return parsed.scheme == "http" and parsed.hostname in ("127.0.0.1", "localhost") and parsed.port == self.server.server_port

    def read_json(self, max_bytes: int = 1_200_000) -> object:
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            raise ValueError("application/json erforderlich")
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > max_bytes:
            raise ValueError("Ungültige Datenmenge")
        return json.loads(self.rfile.read(length))

    def do_GET(self) -> None:
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path == '/api/quick-analyses/settings':
            try:
                self.send_json(self.quick_control().view())
            except (ValueError, OSError, TypeError):
                self.send_json({'error':'Agent-Einstellungen nicht lesbar; private Konfiguration prüfen'},400)
            return
        if path == '/api/quick-analyses':
            payload = QuickStore(DB_PATH).dashboard()
            try:
                config = load_config(allow_missing=True)
                payload['connections'] = self.quick_control().connections(config)
            except (ValueError, OSError, TypeError):
                payload['connections'] = {'settings':'Agent-Konfiguration nicht lesbar; Einstellungen prüfen'}
            self.send_json(payload)
            return
        if path.startswith('/api/quick-analyses/pdf/'):
            aid = path.rsplit('/',1)[-1]
            try:
                record = QuickStore(DB_PATH).analysis(aid)
                name = record['pdf_name'] or ''
                if record['pdf_status'] != 'erstellt' or not re.fullmatch(r'schnellanalyse-[a-f0-9-]+\.pdf', name):
                    raise ValueError('PDF nicht verfügbar')
                content = (DEFAULT_OUTPUT / name).read_bytes()
            except (ValueError, OSError):
                self.send_json({'error':'PDF nicht verfügbar'},404)
                return
            self.send_response(200)
            self.send_header('Content-Type','application/pdf')
            self.send_header('Content-Disposition', f'attachment; filename="{name}"')
            self.send_header('Content-Length',str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return
        if path == "/api/health":
            self.send_json({"ok": True, "service": "immo-portfolio", "api_version": 4,
                            "time": datetime.now(timezone.utc).isoformat()})
            return
        if path == "/api/portfolio":
            try:
                self.send_json({"items": portfolio_rows()})
            except sqlite3.Error as error:
                self.send_json({"error": f"Datenbankfehler: {error}"}, status=500)
            return
        if path == "/api/new-candidates":
            self.send_json({"items": new_candidates()})
            return
        if path.startswith("/api/objects/"):
            name = unquote(path.removeprefix("/api/objects/"))
            if not name or "/" in name or "\\" in name:
                self.send_json({"error": "Ungültiger Objektname"}, 400)
                return
            try:
                obj = get_object(name)
                if obj is None:
                    self.send_json({"error": "Objekt nicht in der Datenbank"}, 404)
                else:
                    self.send_json(obj)
            except (sqlite3.Error, ValueError) as error:
                self.send_json({"error": str(error)}, 500)
            return
        if path.startswith("/api/export/"):
            name = unquote(path.removeprefix("/api/export/"))
            obj = get_object(name) if name and "/" not in name and "\\" not in name else None
            if obj is None:
                self.send_json({"error": "Objekt nicht in der Datenbank"}, 404)
                return
            self.send_json({"_object_id": obj["id"], "_revision": obj["revision"], **obj["state"]})
            return
        if path == "/":
            self.path = "/portfolio.html"
        decoded = unquote(path)
        components = Path(decoded).parts
        resolved = Path(self.translate_path(self.path)).resolve()
        if not resolved.is_relative_to(BASE.resolve()) or any(part.startswith('.') and part not in ('/','.') for part in components) or re.search(r'(?:credentials|secret|token)|\.(?:db|sqlite)(?:-(?:wal|shm|journal))?(?:$|/)|\.(?:eml|pem|key)(?:$|/)', decoded, re.I) or decoded.startswith('/ausgaben/schnellanalysen'):
            self.send_error(403, 'Privater Projektinhalt')
            return
        super().do_GET()

    def do_HEAD(self) -> None:
        self.send_error(405, 'GET verwenden')

    def do_PUT(self) -> None:
        path = urlparse(self.path).path.rstrip("/")
        if not path.startswith("/api/objects/"):
            self.send_json({"error": "Unbekannter Endpunkt"}, 404)
            return
        if not self.local_origin():
            self.send_json({"error": "Fremder Ursprung"}, 403)
            return
        try:
            data = self.read_json()
            name = unquote(path.removeprefix("/api/objects/"))
            if not name or "/" in name or "\\" in name:
                raise ValueError("Ungültiger Objektname")
            saved = save_object(name, data["state"], data["revision"])
            self.send_json(saved)
        except RevisionConflict as error:
            self.send_json({"error": str(error)}, 409)
        except KeyError:
            self.send_json({"error": "Objekt nicht in der Datenbank"}, 404)
        except (ValueError, TypeError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, 400)
        except sqlite3.Error as error:
            self.send_json({"error": str(error)}, 500)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path in ('/api/quick-analyses/settings','/api/quick-analyses/gmail-client','/api/quick-analyses/control'):
            if not self.local_origin():
                self.send_json({'error':'Fremder Ursprung'},403)
                return
            try:
                data = self.read_json(120_000)
                if not isinstance(data,dict):
                    raise ValueError('Ungültige Eingaben')
                control = self.quick_control()
                if path.endswith('/settings'):
                    result = control.save(data)
                elif path.endswith('/gmail-client'):
                    result = control.upload_client(data.get('client'))
                else:
                    action = data.get('action')
                    if action in ('install-gmail','authorize-gmail'):
                        result = control.start_operation(action)
                    elif action in ('start-worker','check-once'):
                        result = control.start_worker(once=action=='check-once')
                    elif action == 'stop-worker':
                        result = control.stop_worker()
                    else:
                        raise ValueError('Unbekannte Aktion')
                self.send_json(result)
            except (ValueError, KeyError, TypeError) as error:
                self.send_json({'error':str(error)},400)
            except (OSError, sqlite3.Error):
                self.send_json({'error':'Einstellungen/Prozess konnten nicht gespeichert oder gestartet werden'},400)
            return
        if path in ('/api/quick-analyses/import-eml','/api/quick-analyses/retry'):
            if not self.local_origin():
                self.send_json({'error':'Fremder Ursprung'},403)
                return
            try:
                data = self.read_json()
                store = QuickStore(DB_PATH)
                if path.endswith('/retry'):
                    store.retry(int(data['job_id']))
                    self.send_json({'status':'Wiederholung eingereiht; separater Worker verarbeitet den Job'})
                else:
                    eml = data['eml']
                    if not isinstance(eml,str) or len(eml) > 1_000_000:
                        raise ValueError('Ungültige EML-Datei')
                    message = parse_eml(eml.encode('utf-8'))
                    config = load_config(allow_missing=True)
                    count = store.ingest('local',message,message_entries(message),config.get('profile'))
                    self.send_json({'offers':count,'status':'Testimport gespeichert; separaten Worker starten'})
            except (ValueError, KeyError, TypeError) as error:
                self.send_json({'error':str(error)},400)
            return
        if path != "/api/import-listing" and not (path.startswith("/api/objects/") and path.endswith(("/archive", "/reactivate", "/photo"))):
            self.send_json({"error": "Unbekannter Endpunkt"}, 404)
            return
        if not self.local_origin():
            self.send_json({"error": "Fremder Ursprung"}, 403)
            return
        try:
            data = self.read_json(8_000_000 if path.endswith("/photo") else 1_200_000)
            if not isinstance(data, dict):
                raise ValueError("JSON-Objekt erwartet")
            if path == "/api/import-listing":
                result = import_listing(data.get("url"))
                self.send_json(result, 200 if result["existing"] else 201)
            elif path.endswith("/photo"):
                public_id = unquote(path.split("/")[3])
                result = set_photo(public_id, data.get("data"), data.get("mime"), data.get("revision"))
                self.send_json(result)
            else:
                public_id = unquote(path.split("/")[3])
                result = set_archive_status(public_id, path.endswith("/archive"), data.get("revision"))
                self.send_json(result)
        except RevisionConflict as error:
            self.send_json({"error": str(error)}, 409)
        except KeyError:
            self.send_json({"error": "Objekt nicht in der Datenbank"}, 404)
        except (ValueError, TypeError, ListingError) as error:
            self.send_json({"error": str(error)}, 400)
        except sqlite3.Error as error:
            self.send_json({"error": f"Datenbankfehler: {error}"}, 500)

    def log_message(self, format: str, *args: object) -> None:
        sys.stdout.write(f"[portfolio] {format % args}\n")
        sys.stdout.flush()


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT
    QuickStore(DB_PATH).migrate()
    server = ThreadingHTTPServer(("127.0.0.1", port), PortfolioHandler)
    print(f"Immobilien-Portfolio: http://127.0.0.1:{port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer beendet.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
