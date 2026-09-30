"""Startet den lokalen Portfolio-Server und öffnet die Portfolioansicht in Chrome."""
from __future__ import annotations

import ctypes
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path


PORT = 8000


def project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def show_error(message: str) -> None:
    ctypes.windll.user32.MessageBoxW(0, message, "Immobilien-Portfolio", 0x10)


def server_version() -> int:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/health", timeout=1) as response:
            if response.status != 200:
                return 0
            import json
            return int(json.loads(response.read()).get("api_version", 0))
    except (OSError, ValueError):
        return 0


def chrome_path() -> Path | None:
    command = shutil.which("chrome.exe")
    if command:
        return Path(command)
    candidates = (
        Path.cwd() / "chrome.exe",
        Path(sys.prefix) / "Google/Chrome/Application/chrome.exe",
        Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
        Path("C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"),
        Path.home() / "AppData/Local/Google/Chrome/Application/chrome.exe",
    )
    return next((candidate for candidate in candidates if candidate.is_file()), None)


def start_server(root: Path):
    tools = root / "tools"
    sys.path.insert(0, str(tools))
    import db_manager
    import db_store
    import local_server

    db_path = root / "immo_datenbank.db"
    db_manager.BASE = root
    db_manager.DB_PATH = db_path
    db_store.BASE = root
    db_store.DB_PATH = db_path
    local_server.BASE = root
    local_server.DB_PATH = db_path

    server = local_server.ThreadingHTTPServer(("127.0.0.1", PORT), local_server.PortfolioHandler)
    thread = threading.Thread(target=server.serve_forever, name="portfolio-server", daemon=True)
    thread.start()
    return server


def main() -> None:
    root = project_root()
    if not (root / "portfolio.html").is_file() or not (root / "immo_datenbank.db").is_file():
        show_error("portfolio.html oder immo_datenbank.db wurde neben der Anwendung nicht gefunden.")
        return

    version = server_version()
    if version == 1:
        show_error(f"Auf Port {PORT} läuft noch ein alter Portfolio-Server. Bitte ihn zuerst beenden.")
        return
    server = None
    if version < 2:
        try:
            server = start_server(root)
            for _ in range(30):
                time.sleep(0.2)
                if server_version() >= 2:
                    break
            else:
                raise RuntimeError("Der Portfolio-Server wurde nicht rechtzeitig gestartet.")
        except Exception as error:
            if server:
                server.server_close()
            show_error(str(error))
            return

    chrome = chrome_path()
    if chrome is None:
        if server:
            server.shutdown()
        show_error("Google Chrome wurde nicht gefunden. Bitte Chrome installieren oder chrome.exe zum PATH hinzufügen.")
        return

    subprocess.Popen([str(chrome), "--new-window", f"http://127.0.0.1:{PORT}/"], cwd=str(root))
    try:
        while server is not None:
            time.sleep(3600)
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()