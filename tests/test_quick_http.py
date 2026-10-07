"""Real local HTTP acceptance tests with a temporary synthetic database."""
from contextlib import closing
import json
import os
import sqlite3
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import local_server
import db_store
from db_manager import SCHEMA
from quick_store import QuickStore
from quick_worker import Worker
from test_quick_analysis import config, FIX


class HttpTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.base=Path(self.tmp.name)
        self.db=self.base/'test.db'
        with closing(sqlite3.connect(self.db)) as conn, conn:conn.executescript(SCHEMA)
        self.store=QuickStore(self.db);self.store.migrate()
        self.patches=[patch.object(local_server,'DB_PATH',self.db),patch.object(db_store,'DB_PATH',self.db),
                      patch.object(local_server,'DEFAULT_OUTPUT',self.base/'pdfs'),patch.object(local_server,'load_config',return_value=config())]
        for p in self.patches:p.start()
        self.server=ThreadingHTTPServer(('127.0.0.1',0),local_server.PortfolioHandler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.url=f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join()
        for p in reversed(self.patches):p.stop()
        self.tmp.cleanup()

    def request(self,path,body=None,origin=None):
        headers={'Content-Type':'application/json'}
        if origin:headers['Origin']=origin
        req=urllib.request.Request(self.url+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
        with urllib.request.urlopen(req,timeout=5) as response:return response.status,response.read()

    def test_import_worker_pdf_download_and_no_jobs_on_get(self):
        eml=(FIX/'emails/01-single.eml').read_text()
        status,payload=self.request('/api/quick-analyses/import-eml',{'eml':eml})
        self.assertEqual(status,200);self.assertEqual(json.loads(payload)['offers'],1)
        before=self.store.dashboard()['jobs']
        for _ in range(2):self.request('/portfolio.html');self.request('/api/quick-analyses')
        self.assertEqual(before,self.store.dashboard()['jobs'])
        Worker(self.store,self.base/'pdfs',config()).drain()
        status,payload=self.request('/api/quick-analyses')
        data=json.loads(payload)
        self.assertEqual(data['connections']['gmail'],'Nicht verbunden')
        self.assertEqual(data['connections']['telegram'],'Telegram nicht verbunden')
        aid=data['items'][0]['id']
        status,content=self.request('/api/quick-analyses/pdf/'+aid)
        self.assertEqual(status,200);self.assertTrue(content.startswith(b'%PDF'))
        self.assertEqual(json.loads(self.request('/api/portfolio')[1])['items'],[])
        self.assertEqual(json.loads(self.request('/api/quick-analyses/import-eml',{'eml':eml})[1])['offers'],0)

    def test_private_static_paths_rejected(self):
        for path in ('/.git/config','/%2Egit/config','/immo_datenbank.db','/immo_datenbank.db-wal','/credentials.json','/secrets.txt','/tests/fixtures/quick_analysis/emails/01-single.eml','/ausgaben/schnellanalysen/private.pdf'):
            with self.subTest(path=path):
                with self.assertRaises(urllib.error.HTTPError) as ctx:self.request(path)
                self.assertEqual(ctx.exception.code,403);ctx.exception.close()

    def test_origin_and_invalid_retry_are_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:self.request('/api/quick-analyses/import-eml',{'eml':'TEST'},'https://attacker.invalid')
        self.assertEqual(ctx.exception.code,403);ctx.exception.close()
        with self.assertRaises(urllib.error.HTTPError) as ctx:self.request('/api/quick-analyses/retry',{'job_id':999})
        self.assertEqual(ctx.exception.code,400);ctx.exception.close()
        self.assertEqual(self.store.dashboard()['jobs'],[])


if __name__=='__main__':unittest.main()
