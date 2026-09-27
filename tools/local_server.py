#!/usr/bin/env python3
"""Lokaler Webserver fuer die Immobilien-Portfolio-App."""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from db_store import RevisionConflict, get_object, import_listing, portfolio_rows, save_object, set_archive_status, set_photo
from listing_import import ListingError

BASE = Path(__file__).resolve().parent.parent
DB_PATH = BASE / "immo_datenbank.db"
DEFAULT_PORT = 8000


class PortfolioHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(BASE), **kwargs)

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
        if path == "/api/health":
            self.send_json({"ok": True, "service": "immo-portfolio", "api_version": 2,
                            "time": datetime.now(timezone.utc).isoformat()})
            return
        if path == "/api/portfolio":
            try:
                self.send_json({"items": portfolio_rows()})
            except sqlite3.Error as error:
                self.send_json({"error": f"Datenbankfehler: {error}"}, status=500)
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
        super().do_GET()

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
