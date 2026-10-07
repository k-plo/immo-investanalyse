#!/usr/bin/env python3
"""Independent persistent polling worker. python3 tools/quick_worker.py --help"""
from __future__ import annotations
import argparse
import json
import os
import signal
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from quick_adapters import (LocalMailAdapter, GmailAdapter, LocalListingAdapter, PublicListingAdapter,
                            LocalRentAdapter, ScoutRentAdapter, DisabledTelegramAdapter,
                            LocalNotificationAdapter, TelegramAdapter, UncertainDelivery, RateLimited,
                            authorize_gmail, timestamp)
from quick_analysis import analyze, validate_profile
from quick_extract import message_entries
from quick_pdf import render_pdf
from quick_store import QuickStore, dump, now

BASE = Path(__file__).resolve().parents[1]
DEFAULT_DB = Path(os.environ.get('IMMO_DB_PATH', BASE / 'immo_datenbank.db'))
DEFAULT_OUTPUT = Path(os.environ.get('IMMO_QUICK_OUTPUT', BASE / 'ausgaben/schnellanalysen'))


def load_config(path=None):
    path = path or os.environ.get('IMMO_QUICK_CONFIG')
    config = json.loads(Path(path).expanduser().read_text()) if path else {}
    config['profile'] = validate_profile(config.get('profile'))
    for key, default, low, high in (('interval',60,1,86400),('concurrency',1,1,4),('max_attempts',3,1,10),('backoff',30,0,3600)):
        value = config.get(key,default)
        if not isinstance(value,int) or isinstance(value,bool) or not low <= value <= high:
            raise ValueError('Ungültige Worker-Konfiguration: ' + key)
        config[key] = value
    return config


def make_adapters(config):
    local = config.get('local',{})
    mail = GmailAdapter(config.get('gmail')) if config.get('gmail',{}).get('enabled') else LocalMailAdapter(local.get('mail_directory', BASE / 'eingang/schnellanalysen'), local.get('filters'))
    # Local fixtures must be explicitly selected; ordinary EML import uses public
    # listing retrieval unless the configured adapter is local.
    listing = LocalListingAdapter(local['listing_directory']) if local.get('listing_directory') else PublicListingAdapter()
    rent = LocalRentAdapter(local['rent_file']) if local.get('rent_file') else ScoutRentAdapter()
    telegram = config.get('telegram',{})
    if telegram.get('auto_send_new') and not telegram.get('send_start_at'):
        raise ValueError('Automatischer Versand benötigt einen expliziten Versand-Startzeitpunkt')
    notification = (TelegramAdapter(telegram) if telegram.get('enabled') else
                    LocalNotificationAdapter(local.get('delivery_fail',False)) if local.get('notification') else DisabledTelegramAdapter())
    return mail, listing, rent, notification


class Worker:
    def __init__(self, store, output, config=None, adapters=None, pdf_renderer=render_pdf):
        self.store, self.output = store, Path(output)
        self.config = config or load_config()
        if self.config.get('worker_host') and self.config['worker_host'] != socket.gethostname():
            raise ValueError('Worker für einen anderen Betriebsrechner konfiguriert')
        self.mail, self.listing, self.rent, self.notification = adapters or make_adapters(self.config)
        self.pdf_renderer = pdf_renderer
        self.stop = threading.Event()
        self.poll_error = None

    def poll(self):
        count = 0
        checkpoint = now()
        try:
            for msg in self.mail.messages(self.store.cursor(self.mail.name), self.store.known_messages(self.mail.name)):
                if self.stop.is_set():
                    break
                count += self.store.ingest(self.mail.name, msg, message_entries(msg), self.config.get('profile'), advance_cursor=self.mail.name != 'gmail')
            if self.mail.name == 'gmail' and not self.stop.is_set() and self.mail.credentials is not None:
                # Do not advance a Gmail checkpoint until every result page committed.
                # A failure halfway through the initial backlog must not skip older mail.
                self.store.checkpoint(self.mail.name, checkpoint)
            self.poll_error = None
        except Exception:
            # External exception messages can contain tokens or private URLs.
            self.poll_error = 'E-Mail-Abruf fehlgeschlagen; Konfiguration und Verbindung prüfen'
        self.store.runtime({'mail':self.mail.status,'notification':self.notification.status,'poll_error':self.poll_error})
        return count

    def process(self, job):
        try:
            if job['kind'] == 'analysis':
                result, error = analyze(self.store.observation(job['target']), self.listing, self.rent)
                if error and result['retryable_fetch'] and job['attempts'] < self.config['max_attempts']:
                    self.store.fail(job, error, self.config['max_attempts'], self.config['backoff'])
                    return
                self.store.save_analysis(job, self.store.observation(job['target']), result, error)
            elif job['kind'] == 'pdf':
                record = self.store.analysis(job['target'])
                self.output.mkdir(parents=True, exist_ok=True)
                # Token-specific staging prevents a worker with an expired lease from
                # overwriting an already finished PDF. Public filenames are DB-selected.
                name = f"schnellanalyse-{job['target']}-{job['lease_token']}.pdf"
                self.pdf_renderer(record['result'], self.output / name)
                telegram = self.config.get('telegram',{})
                local = self.config.get('local',{})
                is_test = record['result']['is_test']
                auto_delivery = (is_test and local.get('notification') is True and local.get('auto_deliver_test') is True) or (
                    not is_test and telegram.get('enabled') is True and telegram.get('auto_send_new') is True and
                    timestamp(record['result']['received_at']) >= timestamp(telegram['send_start_at']) and
                    timestamp(record['analyzed_at']) >= timestamp(telegram['send_start_at']))
                self.store.finish_step(job, queue_delivery=bool(auto_delivery), pdf_status='erstellt', pdf_name=name)
            else:
                record = self.store.analysis(job['target'])
                if record['delivery_status'] in ('versendet','lokal_getestet'):
                    self.store.finish_step(job, delivery_status=record['delivery_status'])
                    return
                if record['pdf_status'] != 'erstellt' or not record['pdf_name']:
                    raise ValueError('PDF fehlt')
                # No implicit bulk sending when live mode is activated later.
                outcome = self.notification.send(record['result']['notification_preview'], self.output / record['pdf_name'], job['target'])
                self.store.finish_step(job, delivery_status=outcome['status'], delivery_receipt=dump(outcome['receipt']) if outcome['receipt'] else None)
        except UncertainDelivery:
            self.store.fail(job, 'Zustellung unklar – vor Wiederholung im Chat prüfen', uncertain=True)
        except RateLimited as error:
            self.store.fail(job, 'Telegram Rate Limit', self.config['max_attempts'], backoff=error.seconds)
        except Exception:
            self.store.fail(job, {'analysis':'Analysefehler – Node und Quelldaten prüfen',
                                 'pdf':'PDF-Erstellung fehlgeschlagen', 'send':'Versand fehlgeschlagen'}[job['kind']],
                            self.config['max_attempts'], self.config['backoff'])

    def drain(self):
        """Finite pass: process due jobs, with bounded threads and bounded retries."""
        with ThreadPoolExecutor(max_workers=self.config['concurrency']) as executor:
            while not self.stop.is_set():
                jobs = [job for _ in range(self.config['concurrency']) if (job := self.store.claim(max_attempts=self.config['max_attempts']))]
                if not jobs:
                    break
                for future in [executor.submit(self.process, job) for job in jobs]:
                    future.result()

    def run(self, once=False):
        while not self.stop.is_set():
            count = self.poll()
            self.drain()
            print(f"Schnellanalysen: {count} Angebot(e) erkannt · {self.mail.status} · {self.notification.status}" +
                  (' · ' + self.poll_error if self.poll_error else ''), flush=True)
            if once:
                return
            self.stop.wait(self.config['interval'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, default=DEFAULT_DB)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--import-eml', type=Path, help='Expliziter lokaler EML-Ordner, Testdaten')
    parser.add_argument('--retry', type=int, help='Nur den fehlgeschlagenen Job zurücksetzen')
    parser.add_argument('--deliver', help='Versand genau dieser Analyse explizit einreihen')
    parser.add_argument('--rebuild-pdf', help='PDF dieser Analyse aus gespeicherten Daten neu erstellen')
    parser.add_argument('--gmail-authorize', action='store_true', help='Expliziten OAuth-Einrichtungsdialog starten')
    args = parser.parse_args()
    config = load_config(args.config)
    if args.gmail_authorize:
        authorize_gmail(config['gmail'])
        return
    args.db.parent.mkdir(parents=True, exist_ok=True)
    store = QuickStore(args.db)
    store.migrate()
    if args.retry:
        store.retry(args.retry)
        return
    if args.deliver:
        store.queue_delivery(args.deliver)
        return
    if args.rebuild_pdf:
        store.rebuild_pdf(args.rebuild_pdf)
        return
    if args.import_eml:
        config.setdefault('local',{})['mail_directory'] = str(args.import_eml)
        config.setdefault('gmail',{})['enabled'] = False
    worker = Worker(store, args.output, config)
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: worker.stop.set())
    worker.run(args.once)


if __name__ == '__main__':
    main()
