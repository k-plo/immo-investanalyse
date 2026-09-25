#!/usr/bin/env python3
"""Lokaler Webserver fuer die Immobilien-Portfolio-App."""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

BASE = Path(__file__).resolve().parent.parent
DB_PATH = BASE / "immo_datenbank.db"
DEFAULT_PORT = 8000


def portfolio_rows() -> list[dict[str, object]]:
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT o.name, o.adresse, o.objektart, o.baujahr, o.zimmer,
                   o.stellplaetze, o.kaufpreis, o.wohnflaeche, o.status,
                   o.html_pfad, o.json_pfad, o.geaendert_am,
                   k.gesamtinvest, k.brutto_rendite, k.netto_rendite,
                   k.cf_nach, k.coc, k.kaltmiete, k.ek, k.zins, k.tilgung,
                   k.rate, r.gesamt_rating, r.punkte
            FROM objekte o
            LEFT JOIN kalkulation k ON k.objekt_id = o.id
            LEFT JOIN rating r ON r.objekt_id = o.id
            WHERE COALESCE(o.status, 'aktiv') <> 'archiviert'
            ORDER BY r.punkte DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


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

    def do_GET(self) -> None:
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path == "/api/health":
            self.send_json({"ok": True, "service": "immo-portfolio", "time": datetime.now(timezone.utc).isoformat()})
            return
        if path == "/api/portfolio":
            try:
                self.send_json({"items": portfolio_rows()})
            except sqlite3.Error as error:
                self.send_json({"error": f"Datenbankfehler: {error}"}, status=500)
            return
        if path == "/":
            self.path = "/portfolio.html"
        super().do_GET()

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
