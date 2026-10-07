#!/usr/bin/env python3
"""Explicit dashboard-triggered installation/OAuth actions, never automatic on GET."""
import argparse
import os
import subprocess
import venv
from quick_settings import BASE, private_write, read_json, venv_python
from quick_adapters import authorize_gmail, external_secret
from quick_store import now


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('install-gmail', 'authorize-gmail'))
    parser.add_argument('--home', required=True)
    parser.add_argument('--config', required=True)
    args = parser.parse_args()
    home = external_secret(args.home)
    receipt = home / 'runtime' / (args.action + '.json')
    def state(status, message):
        private_write(receipt, {'state': status, 'message': message, 'pid': os.getpid(), 'updated_at': now()})
    state('running', 'Gmail-Komponenten werden installiert' if args.action == 'install-gmail' else 'Google-Anmeldung im Browser abschließen')
    try:
        if args.action == 'install-gmail':
            venv.EnvBuilder(with_pip=True).create(home / 'venv')
            subprocess.run([str(venv_python(home)), '-m', 'pip', 'install', '-r', str(BASE / 'tools/requirements-gmail.txt')], check=True, timeout=240)
            subprocess.run([str(venv_python(home)), '-c', 'import google_auth_oauthlib, google.auth'], check=True, timeout=15)
            state('done', 'Gmail-Komponenten sind eingerichtet')
        else:
            config = read_json(external_secret(args.config), {})
            authorize_gmail(config['gmail'])
            state('done', 'Google-Anmeldung abgeschlossen; Gmail-Quelle speichern und Worker starten')
    except Exception:
        # Never persist exceptions containing credentials, token URLs or raw server responses.
        state('error', 'Einrichtung fehlgeschlagen. Desktop-Client/Google-Freigabe und Internet prüfen; Anmeldung hat 5 Minuten Zeitlimit' if args.action == 'authorize-gmail' else 'Installation fehlgeschlagen. Python-Venv/pip und Internet prüfen')
        raise SystemExit(1) from None


if __name__ == '__main__':
    main()
