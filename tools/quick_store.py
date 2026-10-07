"""Persistent quick checks and fenced jobs, isolated from regular portfolio tables."""
from __future__ import annotations
import hashlib
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


class QuickStore:
    def __init__(self, path):
        self.path = Path(path)

    @contextmanager
    def connection(self):
        conn = sqlite3.connect(self.path, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys=ON')
        conn.execute('PRAGMA busy_timeout=15000')
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def migrate(self):
        with self.connection() as conn:
            conn.executescript((Path(__file__).parent / 'migrations/001_quick_analysis.sql').read_text())
            conn.execute('INSERT OR IGNORE INTO qa_schema VALUES (1,?)', (now(),))

    def ingest(self, adapter, message, entries, profile=None, cursor=None, advance_cursor=True):
        """Message, all observations, jobs and sync checkpoint commit together."""
        with self.connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute('SELECT id FROM qa_messages WHERE adapter=? AND message_id=?',
                               (adapter, message['id'])).fetchone()
            if row:
                return 0
            mid = conn.execute('INSERT INTO qa_messages(adapter,message_id,received_at,sender,subject,is_test) VALUES (?,?,?,?,?,?)',
                               (adapter, message['id'], message['received_at'], message.get('sender'),
                                message.get('subject'), int(message.get('is_test', False)))).lastrowid
            for entry in entries:
                conn.execute('INSERT OR IGNORE INTO qa_listings(portal,portal_id,canonical_url) VALUES (?,?,?)',
                             (entry['portal'], entry['portal_id'], entry['url']))
                listing = conn.execute('SELECT id FROM qa_listings WHERE (portal=? AND portal_id=?) OR canonical_url=?',
                                       (entry['portal'], entry['portal_id'], entry['url'])).fetchone()[0]
                conn.execute('INSERT OR IGNORE INTO qa_urls VALUES (?,?)', (entry['url'], listing))
                obs = conn.execute('INSERT OR IGNORE INTO qa_observations(message_id,listing_id,evidence_json,profile_json) VALUES (?,?,?,?)',
                                   (mid, listing, dump(entry), dump(profile))).lastrowid
                conn.execute('INSERT OR IGNORE INTO qa_jobs(kind,target) VALUES (?,?)', ('analysis', str(obs)))
            if advance_cursor:
                conn.execute('INSERT INTO qa_sync VALUES (?,?,?) ON CONFLICT(adapter) DO UPDATE SET cursor=MAX(qa_sync.cursor,excluded.cursor),updated_at=excluded.updated_at',
                             (adapter, str(cursor or message['received_at']), now()))
            return len(entries)

    def known_messages(self, adapter):
        with self.connection() as conn:
            return {row[0] for row in conn.execute('SELECT message_id FROM qa_messages WHERE adapter=?', (adapter,))}

    def checkpoint(self, adapter, cursor):
        with self.connection() as conn:
            conn.execute('INSERT INTO qa_sync VALUES (?,?,?) ON CONFLICT(adapter) DO UPDATE SET cursor=MAX(qa_sync.cursor,excluded.cursor),updated_at=excluded.updated_at', (adapter,cursor,now()))

    def cursor(self, adapter):
        with self.connection() as conn:
            row = conn.execute('SELECT cursor FROM qa_sync WHERE adapter=?', (adapter,)).fetchone()
            return row[0] if row else None

    def claim(self, lease_seconds=300, max_attempts=3):
        clock = time.time()
        with self.connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            # An expired send might already have arrived. Never retry it automatically.
            expired = conn.execute("SELECT target FROM qa_jobs WHERE kind='send' AND state='running' AND lease_until<?", (clock,)).fetchall()
            for row in expired:
                conn.execute("UPDATE qa_analyses SET delivery_status='unklar' WHERE id=?", (row[0],))
            conn.execute("UPDATE qa_jobs SET state='uncertain',error='Versand nach Neustart unklar' WHERE kind='send' AND state='running' AND lease_until<?", (clock,))
            exhausted = conn.execute("SELECT target FROM qa_jobs WHERE kind='pdf' AND state='running' AND lease_until<? AND attempts>=?", (clock,max_attempts)).fetchall()
            for item in exhausted:
                conn.execute("UPDATE qa_analyses SET pdf_status='fehlgeschlagen' WHERE id=?", (item[0],))
            conn.execute("UPDATE qa_jobs SET state='failed',error='Wiederholungen ausgeschöpft' WHERE state='running' AND lease_until<? AND attempts>=?", (clock, max_attempts))
            row = conn.execute("""SELECT j.* FROM qa_jobs j WHERE
                ((j.state='ready' AND j.next_run<=?) OR (j.state='running' AND j.lease_until<? AND j.attempts<?))
                AND (j.kind<>'analysis' OR NOT EXISTS (
                    SELECT 1 FROM qa_jobs active JOIN qa_observations a ON a.id=active.target
                    JOIN qa_observations candidate ON candidate.id=j.target
                    WHERE active.kind='analysis' AND active.state='running' AND active.lease_until>?
                    AND active.id<>j.id AND a.listing_id=candidate.listing_id))
                ORDER BY j.id LIMIT 1""", (clock, clock, max_attempts, clock)).fetchone()
            if row is None:
                return None
            token = str(uuid.uuid4())
            conn.execute("UPDATE qa_jobs SET state='running',attempts=attempts+1,lease_until=?,lease_token=? WHERE id=?",
                         (clock + lease_seconds, token, row['id']))
            return {**dict(row), 'attempts': row['attempts'] + 1, 'lease_token': token}

    def guarded(self, conn, job):
        row = conn.execute("SELECT id FROM qa_jobs WHERE id=? AND state='running' AND lease_token=? AND lease_until>?",
                           (job['id'], job['lease_token'], time.time())).fetchone()
        if row is None:
            raise RuntimeError('Job-Lease abgelaufen')

    def observation(self, target):
        with self.connection() as conn:
            row = conn.execute('''SELECT o.*,l.portal,l.portal_id,l.canonical_url,m.received_at,m.is_test,
                m.message_id AS external_message_id FROM qa_observations o JOIN qa_listings l ON l.id=o.listing_id
                JOIN qa_messages m ON m.id=o.message_id WHERE o.id=?''', (target,)).fetchone()
            return dict(row)

    def save_analysis(self, job, observation, result, technical_error=None):
        values = {key: val['value'] for key, val in result['fields'].items()}
        conflicts = [{'field': conflict['field'], 'values':sorted(str(c['value']) for c in conflict['candidates'])} for conflict in result['conflicts']]
        reference = result['rent_reference']
        if reference:
            reference = {**reference, 'sources':[{k:v for k,v in source.items() if k != 'retrieved_at'} for source in reference['sources']]}
        fingerprint = hashlib.sha256(dump([values, result['calculation'], reference, conflicts, result['fetch_status']]).encode()).hexdigest()
        with self.connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            self.guarded(conn, job)
            previous = conn.execute('SELECT * FROM qa_analyses WHERE listing_id=? ORDER BY revision DESC LIMIT 1', (observation['listing_id'],)).fetchone()
            if previous and previous['fingerprint'] == fingerprint:
                aid = previous['id']
            else:
                aid = str(uuid.uuid4())
                revision = previous['revision'] + 1 if previous else 1
                result.update(id=aid, revision=revision, analyzed_at=now(), portal=observation['portal'],
                              portal_id=observation['portal_id'], url=observation['canonical_url'],
                              received_at=observation['received_at'], is_test=bool(observation['is_test']))
                status = 'vollständig' if not result['missing'] and not result['conflicts'] and not technical_error else 'teilweise'
                conn.execute('''INSERT INTO qa_analyses(id,listing_id,observation_id,revision,fingerprint,result_json,analyzed_at,analysis_status)
                    VALUES (?,?,?,?,?,?,?,?)''', (aid, observation['listing_id'], observation['id'], revision, fingerprint, dump(result), result['analyzed_at'], status))
                conn.execute("INSERT INTO qa_jobs(kind,target) VALUES ('pdf',?)", (aid,))
            conn.execute("UPDATE qa_jobs SET state=?,result_id=?,error=?,lease_until=NULL WHERE id=?",
                         ('failed' if technical_error else 'done', aid, technical_error, job['id']))
            return aid

    def analysis(self, aid):
        with self.connection() as conn:
            row = conn.execute('SELECT * FROM qa_analyses WHERE id=?', (aid,)).fetchone()
            if row is None:
                raise ValueError('Schnellanalyse unbekannt')
            return {**dict(row), 'result': json.loads(row['result_json'])}

    def finish_step(self, job, queue_delivery=False, **updates):
        allowed = {'pdf_status', 'pdf_name', 'delivery_status', 'delivery_receipt'}
        if not updates or not set(updates) <= allowed:
            raise ValueError('Ungültige Statusfelder')
        with self.connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            self.guarded(conn, job)
            conn.execute('UPDATE qa_analyses SET ' + ','.join(key + '=?' for key in updates) + ' WHERE id=?', (*updates.values(), job['target']))
            conn.execute("UPDATE qa_jobs SET state='done',error=NULL,lease_until=NULL WHERE id=?", (job['id'],))
            if queue_delivery:
                existing = conn.execute("SELECT 1 FROM qa_jobs WHERE kind='send' AND target=?", (job['target'],)).fetchone()
                if not existing:
                    conn.execute("INSERT INTO qa_jobs(kind,target) VALUES ('send',?)", (job['target'],))
                    conn.execute("UPDATE qa_analyses SET delivery_status='ausstehend' WHERE id=?", (job['target'],))

    def fail(self, job, error, max_attempts=3, backoff=30, uncertain=False):
        with self.connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            try:
                self.guarded(conn, job)
            except RuntimeError:
                # A stale worker must neither overwrite another worker's state nor
                # abort unrelated work after the newer lease was already claimed.
                return False
            state = 'uncertain' if uncertain else 'ready' if job['attempts'] < max_attempts else 'failed'
            conn.execute('UPDATE qa_jobs SET state=?,error=?,next_run=?,lease_until=NULL WHERE id=?',
                         (state, error, time.time() + backoff * 2 ** (job['attempts'] - 1), job['id']))
            if job['kind'] != 'analysis':
                field = 'pdf_status' if job['kind'] == 'pdf' else 'delivery_status'
                conn.execute(f'UPDATE qa_analyses SET {field}=? WHERE id=?',
                             ('unklar' if uncertain else 'fehlgeschlagen' if state == 'failed' else 'ausstehend', job['target']))

    def retry(self, job_id):
        with self.connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute('SELECT * FROM qa_jobs WHERE id=?', (job_id,)).fetchone()
            if row is None or row['state'] not in ('failed', 'uncertain'):
                raise ValueError('Nur fehlgeschlagene/unklare Schritte können wiederholt werden')
            conn.execute("UPDATE qa_jobs SET state='ready',attempts=0,next_run=0,error=NULL,lease_token=NULL WHERE id=?", (job_id,))
            if row['kind'] in ('pdf','send'):
                field = 'pdf_status' if row['kind'] == 'pdf' else 'delivery_status'
                conn.execute(f"UPDATE qa_analyses SET {field}='ausstehend' WHERE id=?", (row['target'],))

    def queue_delivery(self, aid):
        """Explicit per-analysis opt-in, also needed for old test data."""
        with self.connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute('SELECT pdf_status,delivery_status FROM qa_analyses WHERE id=?', (aid,)).fetchone()
            if row is None or row['pdf_status'] != 'erstellt' or row['delivery_status'] in ('versendet','lokal_getestet','unklar'):
                raise ValueError('PDF fehlt oder Versand bereits bestätigt/unklar')
            existing = conn.execute("SELECT id,state FROM qa_jobs WHERE kind='send' AND target=?", (aid,)).fetchone()
            if existing and existing['state'] in ('failed','uncertain'):
                raise ValueError('Vorhandenen Versandjob gezielt wiederholen')
            if existing and existing['state'] == 'done':
                conn.execute("UPDATE qa_jobs SET state='ready',attempts=0,next_run=0,error=NULL WHERE id=?", (existing['id'],))
            else:
                conn.execute("INSERT OR IGNORE INTO qa_jobs(kind,target) VALUES ('send',?)", (aid,))
            conn.execute("UPDATE qa_analyses SET delivery_status='ausstehend' WHERE id=?", (aid,))

    def rebuild_pdf(self, aid):
        """Explicit regeneration from saved data, e.g. after transferring the DB."""
        with self.connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            if not conn.execute('SELECT id FROM qa_analyses WHERE id=?', (aid,)).fetchone():
                raise ValueError('Schnellanalyse unbekannt')
            job = conn.execute("SELECT id,state FROM qa_jobs WHERE kind='pdf' AND target=?", (aid,)).fetchone()
            if job and job['state'] in ('ready','running'):
                raise ValueError('PDF-Erstellung bereits ausstehend oder in Verarbeitung')
            if job:
                conn.execute("UPDATE qa_jobs SET state='ready',attempts=0,next_run=0,error=NULL,lease_token=NULL WHERE id=?", (job['id'],))
            else:
                conn.execute("INSERT INTO qa_jobs(kind,target) VALUES ('pdf',?)", (aid,))
            conn.execute("UPDATE qa_analyses SET pdf_status='ausstehend',pdf_name=NULL WHERE id=?", (aid,))

    def runtime(self, status):
        with self.connection() as conn:
            conn.execute("INSERT INTO qa_runtime VALUES ('worker',?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at", (dump(status), now()))

    def dashboard(self):
        if not self.path.exists():
            return {'items': [], 'jobs': [], 'worker': None}
        with self.connection() as conn:
            if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='qa_analyses'").fetchone():
                return {'items': [], 'jobs': [], 'worker': None}
            items = conn.execute('SELECT * FROM qa_analyses ORDER BY analyzed_at DESC,revision DESC').fetchall()
            jobs = conn.execute('SELECT id,kind,target,state,attempts,error,result_id FROM qa_jobs ORDER BY id DESC').fetchall()
            runtime = conn.execute("SELECT value,updated_at FROM qa_runtime WHERE key='worker'").fetchone()
            return {'worker': {'status': json.loads(runtime[0]), 'updated_at':runtime[1]} if runtime else None, 'items': [{**{k: row[k] for k in ('id','revision','analysis_status','pdf_status','delivery_status','pdf_name')},
                               'result': json.loads(row['result_json'])} for row in items], 'jobs': [dict(row) for row in jobs]}
