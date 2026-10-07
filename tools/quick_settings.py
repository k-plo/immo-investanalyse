"""Local dashboard settings and explicit controls for the existing quick worker.

Only paths and analysis parameters enter automation.json. Credentials and process
state stay in a private directory outside the HTTP document root and Git.
"""
from __future__ import annotations
import ctypes
import importlib.util
import json
import os
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path
from quick_adapters import GMAIL_SCOPE, external_secret, timestamp
from quick_analysis import validate_profile
from quick_store import now

BASE = Path(__file__).resolve().parents[1]


def private_home():
    if os.environ.get('IMMO_QUICK_HOME'):
        path = Path(os.environ['IMMO_QUICK_HOME'])
    elif os.name == 'nt':
        path = Path(os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData/Local'))) / 'immo-investanalyse'
    elif sys.platform == 'darwin':
        path = Path.home() / 'Library/Application Support/immo-investanalyse'
    else:
        path = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))) / 'immo-investanalyse'
    return external_secret(path)


def configuration_path(path=None):
    return Path(path or os.environ.get('IMMO_QUICK_CONFIG') or private_home() / 'automation.json').expanduser().resolve()


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8-sig'))
    except FileNotFoundError:
        return default


def private_directory(path):
    """Protect every newly created directory, preserving existing parent permissions."""
    path = external_secret(path)
    missing = []
    parent = path
    while not parent.exists():
        missing.append(parent)
        parent = parent.parent
    for directory in reversed(missing):
        directory.mkdir(mode=0o700, exist_ok=True)
    return path


def private_write(path, value):
    path = external_secret(path)
    private_directory(path.parent)
    # Never chmod a caller's existing parent directory (e.g. /tmp).
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as temp:
        temporary = Path(temp.name)
        try:
            json.dump(value, temp, ensure_ascii=False, indent=2, allow_nan=False)
            temp.flush()
            os.fsync(temp.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        temporary.chmod(0o600)
        os.replace(temporary, path)
        path.chmod(0o600)
    finally:
        temporary.unlink(missing_ok=True)


def mail_signature(config):
    import hashlib
    gmail = config.get('gmail', {})
    data = {k: gmail.get(k) for k in ('enabled', 'query', 'senders', 'subjects', 'start_at', 'token_path', 'connection_generation')}
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def process_alive(pid):
    if not isinstance(pid, int) or pid <= 0:
        return False
    if os.name == 'nt':
        kernel = ctypes.windll.kernel32
        kernel.OpenProcess.restype = ctypes.c_void_p
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            return bool(kernel.GetExitCodeProcess(ctypes.c_void_p(handle), ctypes.byref(code))) and code.value == 259
        finally:
            kernel.CloseHandle(ctypes.c_void_p(handle))
    if sys.platform.startswith('linux'):
        try:
            if Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()[0] == 'Z':
                return False
        except (FileNotFoundError, PermissionError, IndexError):
            pass
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def venv_python(home):
    return home / 'venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')


def current_oauth_available():
    return importlib.util.find_spec('google_auth_oauthlib') is not None


class AutomationControl:
    def __init__(self, store, output, home=None, config_path=None):
        self.store = store
        self.output = Path(output).resolve()
        self.home = external_secret(home) if home else private_home()
        self.config_path = configuration_path(config_path)
        self.lock = threading.RLock()
        self.children = {}

    def config(self):
        data = read_json(self.config_path, {})
        if not isinstance(data, dict):
            raise ValueError('Die bestehende Agent-Konfiguration ist kein JSON-Objekt')
        data.setdefault('local', {}).setdefault('mail_directory', str(self.home / 'inbox'))
        return data

    def runtime(self):
        if not self.store.path.exists():
            return None
        try:
            with self.store.connection() as conn:
                row = conn.execute("SELECT value,updated_at FROM qa_runtime WHERE key='worker'").fetchone()
                return {'status': json.loads(row[0]), 'updated_at': row[1]} if row else None
        except sqlite3.OperationalError:
            return None

    def worker_status(self):
        metadata = read_json(self.home / 'runtime/worker.json', {})
        # Reap processes owned by this server before checking persistent PID state.
        for child in list(self.children.values()):
            child.poll()
        managed = metadata.get('db') == str(self.store.path.resolve())
        running = managed and process_alive(metadata.get('pid'))
        runtime = self.runtime()
        if not running and runtime:
            state = runtime['status']
            if state.get('state') == 'running' and state.get('host') == socket.gethostname() and process_alive(state.get('pid')):
                return {'running': True, 'managed': False, 'stopping': False, 'label': 'Worker läuft außerhalb dieses Menüs', 'last_poll': runtime['updated_at']}
        stopping = bool(running and (self.home / 'runtime' / (metadata['run_id'] + '.stop')).exists())
        return {'running': bool(running), 'managed': bool(managed and running), 'stopping': stopping,
                'label': 'Worker wird beendet' if stopping else 'Worker läuft' if running else 'Worker gestoppt',
                'last_poll': runtime['updated_at'] if runtime else None}

    def operation(self, action):
        state = read_json(self.home / 'runtime' / (action + '.json'), {})
        child = self.children.get(action)
        if child:
            result = child.poll()
            if result is not None and state.get('state') in ('queued', 'running'):
                state = {'state': 'error', 'message': 'Einrichtung wurde unterbrochen; bitte erneut starten', 'updated_at': now()}
        elif (state.get('state') == 'running' and not process_alive(state.get('pid'))) or (state.get('state') == 'queued' and time.time() - timestamp(state['updated_at']) > 10):
            state = {'state': 'error', 'message': 'Einrichtung wurde unterbrochen; bitte erneut starten', 'updated_at': now()}
        return {k: state.get(k) for k in ('state', 'message', 'updated_at')}

    def oauth_ready(self):
        return current_oauth_available() or (venv_python(self.home).is_file() and self.operation('install-gmail').get('state') == 'done')

    def token_present(self, config):
        path = config.get('gmail', {}).get('token_path')
        if not path:
            return False
        try:
            token = read_json(external_secret(path), {})
            return set(token.get('scopes', [])) == {GMAIL_SCOPE} and bool(token.get('refresh_token'))
        except (ValueError, OSError, TypeError):
            return False

    def pending_sends(self):
        try:
            with self.store.connection() as conn:
                return conn.execute("SELECT COUNT(*) FROM qa_jobs WHERE kind='send' AND state IN ('ready','running')").fetchone()[0]
        except sqlite3.OperationalError:
            return 0

    def connections(self, config=None):
        config = config if config is not None else self.config()
        gmail = config.get('gmail', {})
        runtime = self.runtime()
        status = 'Nicht verbunden'
        if self.token_present(config):
            status = 'Anmeldung eingerichtet – Gmail-Abruf noch nicht geprüft'
            if gmail.get('enabled') and runtime and runtime['status'].get('mail_signature') == mail_signature(config):
                if runtime['status'].get('mail_scan_ok') and runtime['status'].get('mail_source') == 'gmail':
                    status = 'Verbunden – letzter Gmail-Abruf ' + (runtime['status'].get('last_mail_scan_at') or runtime['updated_at'])
                elif runtime['status'].get('poll_error'):
                    status = 'Gmail-Abruf fehlgeschlagen – Anmeldung/Filter prüfen'
        telegram = config.get('telegram', {})
        return {'gmail': status, 'telegram': 'Telegram aktiviert – tatsächliche Bestätigung je Analyse prüfen' if telegram.get('enabled') else 'Telegram nicht verbunden',
                'rent': 'Mietreferenz fehlt – Scout-Liveadapter nicht implementiert'}

    def view(self):
        config = self.config()
        gmail, local, telegram = (config.get(k, {}) for k in ('gmail', 'local', 'telegram'))
        secret = {}
        if telegram.get('secret_path'):
            try:
                secret = read_json(external_secret(telegram['secret_path']), {})
            except (ValueError, OSError):
                pass
        client = gmail.get('client_path')
        try:
            client_ready = bool(client and external_secret(client).is_file())
        except ValueError:
            client_ready = False
        return {'settings': {'profile': validate_profile(config.get('profile')), 'source': 'gmail' if gmail.get('enabled') else 'local',
                    'interval': config.get('interval', 60), 'concurrency': config.get('concurrency', 1),
                    'mail_directory': local.get('mail_directory', str(self.home / 'inbox')),
                    'query': gmail.get('query', ''), 'senders': gmail.get('senders', []), 'subjects': gmail.get('subjects', []),
                    'start_at': gmail.get('start_at'), 'telegram_enabled': telegram.get('enabled', False),
                    'auto_send_new': telegram.get('auto_send_new', False), 'send_start_at': telegram.get('send_start_at'),
                    'chat_id': str(secret.get('allowed_chat_id', '')), 'telegram_token_saved': bool(secret.get('bot_token'))},
                'gmail': {'client_ready': client_ready, 'token_ready': self.token_present(config), 'dependencies_ready': self.oauth_ready()},
                'operations': {action: self.operation(action) for action in ('install-gmail', 'authorize-gmail')},
                'worker': self.worker_status(), 'connections': self.connections(config),
                'pending_sends': self.pending_sends(), 'node_ready': bool(shutil.which('node')),
                'configuration_saved': self.config_path.is_file(),
                'private_storage': not self.config_path.is_relative_to(BASE)}

    def idle(self):
        if self.worker_status()['running']:
            raise ValueError('Worker zuerst stoppen und sein Prozessende abwarten')
        if any(self.operation(a).get('state') in ('running', 'queued') for a in ('install-gmail', 'authorize-gmail')):
            raise ValueError('Die laufende Gmail-Einrichtung zuerst abschließen')

    def save(self, values):
        if not isinstance(values, dict):
            raise ValueError('Ungültige Einstellungen')
        allowed = {'profile', 'source', 'interval', 'concurrency', 'mail_directory', 'query', 'senders', 'subjects', 'start_at',
                   'telegram_enabled', 'auto_send_new', 'send_start_at', 'chat_id', 'bot_token'}
        if set(values) - allowed:
            raise ValueError('Unbekannte Einstellung')
        with self.lock:
            self.idle()
            external_secret(self.config_path)
            config = self.config()
            candidate = values.get('profile')
            if candidate is not None and (not isinstance(candidate,dict) or not isinstance(candidate.get('name'),str) or not 1 <= len(candidate['name'].strip()) <= 120):
                raise ValueError('Profilname mit höchstens 120 Zeichen eintragen')
            profile = validate_profile(candidate)
            source = values.get('source', 'local')
            if source not in ('gmail', 'local'):
                raise ValueError('Ungültige E-Mail-Quelle')
            gmail = dict(config.get('gmail', {}))
            for key in ('senders', 'subjects'):
                items = values.get(key, [])
                if not isinstance(items, list) or len(items) > 30 or any(not isinstance(s, str) or not s.strip() or len(s) > 300 or '\n' in s or '\r' in s for s in items):
                    raise ValueError('Ungültige E-Mail-Filter')
                gmail[key] = [s.strip() for s in items]
            if any(not re.fullmatch(r'[A-Za-z0-9.!#$%&\'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', s) for s in gmail['senders']):
                raise ValueError('Absender als vollständige E-Mail-Adresse eintragen')
            query = values.get('query', '').strip()
            if len(query) > 1000 or '\n' in query or '\r' in query:
                raise ValueError('Ungültiger Gmail-Suchfilter')
            start_at = values.get('start_at')
            if start_at:
                timestamp(start_at)
            targeted = query and query.lower() not in ('in:inbox','in:anywhere','is:unread','*')
            if source == 'gmail' and (not start_at or (not gmail['senders'] and not targeted)):
                raise ValueError('Für Gmail Startzeitpunkt und Absender oder gezielten Suchfilter festlegen')
            gmail.update(enabled=source == 'gmail', query=query or 'in:inbox', start_at=start_at)
            local = dict(config.get('local', {}))
            if source == 'gmail' and (local.get('listing_directory') or local.get('rent_file')):
                raise ValueError('Test-Anzeigen/Mietreferenzen sind konfiguriert. Für Gmail eine getrennte private Betriebskonfiguration verwenden')
            directory = external_secret(values.get('mail_directory') or self.home / 'inbox')
            local.update(mail_directory=str(directory), notification=False, auto_deliver_test=False)
            telegram = dict(config.get('telegram', {}))
            for key in ('telegram_enabled', 'auto_send_new'):
                if not isinstance(values.get(key, False), bool):
                    raise ValueError('Ungültiger Versandmodus')
            enabled = values.get('telegram_enabled', False)
            auto = values.get('auto_send_new', False)
            send_start = values.get('send_start_at')
            if send_start:
                timestamp(send_start)
            if auto and (not enabled or not send_start):
                raise ValueError('Automatischer Telegram-Versand benötigt Aktivierung und Startzeitpunkt')
            if enabled and self.pending_sends():
                raise ValueError('Es gibt bereits offene Versandaufträge. Vor Aktivierung diese Aufträge ausdrücklich prüfen; kein Altbestand-Versand aus diesem Menü')
            secret_path = self.home / 'telegram/secret.json'
            previous = {}
            if telegram.get('secret_path'):
                previous = read_json(external_secret(telegram['secret_path']), {})
            token = values.get('bot_token') or previous.get('bot_token', '')
            chat = str(values.get('chat_id', '')).strip()
            if (token or enabled) and (not re.fullmatch(r'\d+:[A-Za-z0-9_-]+', token) or not re.fullmatch(r'-?\d+', chat)):
                raise ValueError('Telegram benötigt gültigen Bot-Token und numerische erlaubte Chat-ID')
            telegram.update(enabled=enabled, auto_send_new=auto, send_start_at=send_start)
            config.update(profile=profile, interval=values.get('interval', 60), concurrency=values.get('concurrency', 1),
                          worker_host=socket.gethostname(), local=local, gmail=gmail, telegram=telegram)
            from quick_worker import validate_config
            validate_config(config)
            if token:
                private_write(secret_path, {'bot_token': token, 'allowed_chat_id': chat})
                telegram['secret_path'] = str(secret_path)
            private_write(self.config_path, config)
            return self.view()

    def upload_client(self, client):
        with self.lock:
            self.idle()
            external_secret(self.config_path)
            installed = client.get('installed') if isinstance(client, dict) else None
            if not isinstance(installed, dict) or not isinstance(installed.get('client_id'), str) or not installed['client_id'].endswith('.apps.googleusercontent.com') or not installed.get('client_secret'):
                raise ValueError('Die heruntergeladene Google-OAuth-Datei muss ein Desktop-Client sein')
            if installed.get('auth_uri') not in ('https://accounts.google.com/o/oauth2/auth', 'https://accounts.google.com/o/oauth2/v2/auth') or installed.get('token_uri') not in ('https://oauth2.googleapis.com/token', 'https://accounts.google.com/o/oauth2/token'):
                raise ValueError('Die OAuth-Datei enthält keine unterstützten Google-Endpunkte')
            config = self.config()
            token = self.home / 'gmail/token.json'
            private_write(self.home / 'gmail/client.json', {'installed': installed})
            # Replacing a client invalidates only our managed token, never a caller's other file.
            token.unlink(missing_ok=True)
            config.setdefault('gmail', {}).update(client_path=str(self.home / 'gmail/client.json'), token_path=str(token), connection_generation=uuid.uuid4().hex)
            private_write(self.config_path, config)
            return self.view()

    def start_operation(self, action):
        if action not in ('install-gmail', 'authorize-gmail'):
            raise ValueError('Unbekannte Einrichtungsaktion')
        with self.lock:
            self.idle()
            if action == 'authorize-gmail' and not self.view()['gmail']['client_ready']:
                raise ValueError('Zuerst die Google-Desktop-OAuth-Datei auswählen')
            if action == 'authorize-gmail' and not self.oauth_ready():
                raise ValueError('Zuerst Gmail-Komponenten einrichten')
            if action == 'authorize-gmail':
                config = self.config()
                config['gmail']['connection_generation'] = uuid.uuid4().hex
                private_write(self.config_path, config)
            interpreter = venv_python(self.home) if action == 'authorize-gmail' and venv_python(self.home).is_file() else Path(sys.executable)
            private_write(self.home / 'runtime' / (action + '.json'), {'state': 'queued', 'message': 'Einrichtung startet', 'updated_at': now()})
            try:
                self.spawn(action, [str(interpreter), str(BASE / 'tools/quick_setup.py'), action, '--home', str(self.home), '--config', str(self.config_path)])
            except OSError:
                private_write(self.home / 'runtime' / (action + '.json'), {'state':'error','message':'Einrichtung konnte nicht gestartet werden','updated_at':now()})
                raise ValueError('Einrichtung konnte nicht gestartet werden') from None
            return self.view()

    def spawn(self, key, command, env=None):
        path = self.home / 'runtime' / (key + '.log')
        private_directory(path.parent)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        path.chmod(0o600)
        with os.fdopen(fd, 'ab') as output:
            child = subprocess.Popen(command, cwd=BASE, env=env, stdin=subprocess.DEVNULL,
                                     stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
        self.children[key] = child
        return child

    def start_worker(self, once=False):
        with self.lock:
            self.idle()
            if not self.config_path.is_file():
                raise ValueError('Einstellungen zuerst speichern')
            if not shutil.which('node'):
                raise ValueError('Node.js fehlt auf diesem Rechner')
            from quick_worker import load_config
            config = load_config(self.config_path)
            gmail = config.get('gmail', {})
            if config.get('worker_host') and config['worker_host'] != socket.gethostname():
                raise ValueError('Dieser Rechner ist nicht als Worker-Rechner konfiguriert')
            if gmail.get('enabled') and not self.token_present(config):
                raise ValueError('Zuerst mit Google anmelden')
            if gmail.get('enabled') and not self.oauth_ready():
                raise ValueError('Gmail-Komponenten fehlen')
            if config.get('telegram', {}).get('enabled') and self.pending_sends():
                raise ValueError('Bereits eingereihte Versandaufträge vor Start ausdrücklich prüfen')
            run_id = uuid.uuid4().hex
            env = dict(os.environ, IMMO_QUICK_RUN_ID=run_id, IMMO_QUICK_STOP_FILE=str(self.home / 'runtime' / (run_id + '.stop')),
                       IMMO_QUICK_HOME=str(self.home))
            interpreter = venv_python(self.home) if gmail.get('enabled') and venv_python(self.home).is_file() else Path(sys.executable)
            command = [str(interpreter), str(BASE / 'tools/quick_worker.py'), '--config', str(self.config_path), '--db', str(self.store.path.resolve()), '--output', str(self.output)]
            if once:
                command.append('--once')
            child = self.spawn('worker', command, env)
            private_write(self.home / 'runtime/worker.json', {'pid': child.pid, 'run_id': run_id, 'db': str(self.store.path.resolve()), 'started_at': now()})
            return self.view()

    def stop_worker(self):
        with self.lock:
            worker = self.worker_status()
            if worker['running'] and not worker['managed']:
                raise ValueError('Diesen extern gestarteten Worker in seinem Terminal beenden')
            metadata = read_json(self.home / 'runtime/worker.json', {})
            if worker['running']:
                path = self.home / 'runtime' / (metadata['run_id'] + '.stop')
                path.touch(mode=0o600)
            return self.view()
