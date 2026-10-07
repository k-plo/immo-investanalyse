"""Settings/control acceptance: private storage, actual subprocess, temp DB only."""
from contextlib import closing
import json
import os
import socket
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import local_server
import db_store
from db_manager import SCHEMA
from quick_store import QuickStore
from quick_settings import AutomationControl, private_write, mail_signature
from quick_worker import load_config
from test_quick_analysis import config, FIX

# Artificial client/token values, never valid live credentials.
CLIENT = {'installed': {'client_id':'TEST.apps.googleusercontent.com','client_secret':'TEST-NOT-A-CREDENTIAL',
          'auth_uri':'https://accounts.google.com/o/oauth2/auth','token_uri':'https://oauth2.googleapis.com/token'}}


class SettingsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.home = self.base/'private'
        self.cfg = self.home/'automation.json'
        self.db = self.base/'test.db'
        self.output = self.base/'pdfs'
        with closing(sqlite3.connect(self.db)) as c,c:
            c.executescript(SCHEMA)
            c.execute("INSERT INTO objekte(name,public_id,status,state_json,kaufpreis,wohnflaeche) VALUES ('TEST regular','test-settings-id','aktiv','{}',100000,50)")
        self.store = QuickStore(self.db);self.store.migrate()
        self.env = patch.dict(os.environ, {'IMMO_QUICK_HOME':str(self.home),'IMMO_QUICK_CONFIG':str(self.cfg)})
        self.env.start()
        self.control = AutomationControl(self.store,self.output)
        self.patches = [patch('quick_settings.current_oauth_available',return_value=False),patch.object(local_server,'DB_PATH',self.db),patch.object(db_store,'DB_PATH',self.db),patch.object(local_server,'DEFAULT_OUTPUT',self.output)]
        for p in self.patches:p.start()
        self.server = ThreadingHTTPServer(('127.0.0.1',0),local_server.PortfolioHandler)
        self.server.qa_control = self.control
        self.thread = threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.url = f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        try:
            self.control.stop_worker()
            for child in self.control.children.values():
                try:child.wait(timeout=5)
                except Exception:child.terminate();child.wait(timeout=5)
        finally:
            self.server.shutdown();self.server.server_close();self.thread.join()
            for p in reversed(self.patches):p.stop()
            self.env.stop();self.tmp.cleanup()

    def request(self,path,body=None,origin=None):
        headers={'Content-Type':'application/json'}
        if origin:headers['Origin']=origin
        req=urllib.request.Request(self.url+'/api/quick-analyses/'+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
        with urllib.request.urlopen(req,timeout=5) as r:return json.load(r)

    def values(self,**changes):
        values={'source':'local','profile':{'name':'TEST menu profile','ekModus':'betrag','ek':30000,'zins':4,'tilgung':2},
                'mail_directory':str(self.home/'inbox'),'interval':1,'concurrency':1,'start_at':'2026-10-07T10:00:00+02:00'}
        values.update(changes)
        return values

    def error(self,path,body,status=400,origin=None):
        with self.assertRaises(urllib.error.HTTPError) as context:self.request(path,body,origin)
        self.assertEqual(context.exception.code,status);context.exception.close()

    def wait_stopped(self):
        for _ in range(100):
            if not self.request('settings')['worker']['running']:return
            time.sleep(.05)
        self.fail('Managed worker did not stop')

    def test_read_settings_has_no_side_effects_or_secret_values(self):
        before=self.store.dashboard()['jobs']
        for _ in range(2):
            data=self.request('settings');self.request('')
            self.assertFalse(data['configuration_saved']);self.assertFalse(data['worker']['running'])
        self.assertFalse(self.home.exists());self.assertEqual(before,self.store.dashboard()['jobs'])

    def test_save_profile_and_filters_private_and_cli_uses_same_defaults(self):
        data=self.request('settings',self.values(source='gmail',senders=['alerts@example.invalid'],subjects=['TEST Suchalarm']))
        saved=json.loads(self.cfg.read_text())
        self.assertTrue(saved['gmail']['enabled']);self.assertEqual(saved['gmail']['query'],'in:inbox')
        self.assertEqual(saved['worker_host'],socket.gethostname())
        self.assertEqual(load_config()['profile']['ek'],30000)
        self.cfg.write_text(json.dumps(saved),encoding='utf-8-sig') # Windows PowerShell UTF-8 BOM
        self.assertEqual(load_config()['profile']['ek'],30000)
        self.assertEqual(self.request('settings')['settings']['profile']['ek'],30000)
        self.assertTrue(data['configuration_saved']);self.assertFalse(data['gmail']['token_ready'])
        self.assertEqual(data['connections']['gmail'],'Nicht verbunden')
        if os.name!='nt':self.assertEqual(self.cfg.stat().st_mode & 0o777,0o600)
        self.error('control',{'action':'start-worker'})

    def test_missing_profile_and_gmail_target_validation(self):
        self.request('settings',self.values(profile=None))
        self.assertIsNone(load_config()['profile'])
        self.error('settings',self.values(source='gmail',query='in:inbox'))
        self.error('settings',self.values(source='gmail',senders=['invalid']))
        self.error('settings',self.values(source='gmail',senders=['alerts@example.invalid'],start_at=None))
        self.error('settings',self.values(interval=0))
        self.error('settings',self.values(profile={'name':'TEST','ekModus':'betrag','ek':100}))
        self.error('settings',self.values(unknown='TEST'))
        self.error('settings',self.values(mail_directory=str(ROOT/'secret-inbox')))

    def test_demo_adapters_cannot_be_used_for_gmail(self):
        demo=config()
        private_write(self.cfg,demo)
        self.error('settings',self.values(source='gmail',senders=['alerts@example.invalid']))
        self.assertFalse(json.loads(self.cfg.read_text())['gmail']['enabled'])

    def test_client_upload_private_scoped_and_malicious_endpoints_rejected(self):
        self.error('gmail-client',{'client':{'web':CLIENT['installed']}})
        evil={'installed':dict(CLIENT['installed'],token_uri='https://attacker.invalid/token')}
        self.error('gmail-client',{'client':evil})
        data=self.request('gmail-client',{'client':CLIENT})
        self.assertTrue(data['gmail']['client_ready']);self.assertFalse(data['gmail']['token_ready'])
        self.assertNotIn('TEST-NOT-A-CREDENTIAL',json.dumps(data))
        self.assertEqual(json.loads((self.home/'gmail/client.json').read_text()),CLIENT)
        if os.name!='nt':self.assertEqual(self.home.stat().st_mode & 0o777,0o700)
        self.assertEqual(load_config()['gmail']['token_path'],str(self.home/'gmail/token.json'))
        self.error('control',{'action':'authorize-gmail'}) # Dependencies missing, no Google request.
        self.assertFalse((self.home/'runtime/authorize-gmail.json').exists())

    def test_no_setup_or_worker_action_from_foreign_origin(self):
        for endpoint,body in [('settings',self.values()),('gmail-client',{'client':CLIENT}),('control',{'action':'install-gmail'})]:
            self.error(endpoint,body,403,'https://attacker.invalid')
        self.assertFalse(self.home.exists())
        self.error('control',{'action':'arbitrary-command'})
        self.assertFalse(self.home.exists())

    def test_setup_only_starts_after_explicit_action(self):
        with patch.object(self.control,'spawn') as spawn:
            self.request('settings');spawn.assert_not_called()
            self.request('control',{'action':'install-gmail'})
            self.assertEqual(spawn.call_args.args[0],'install-gmail')
        self.assertEqual(self.request('settings')['operations']['install-gmail']['state'],'queued')
        self.assertFalse(self.request('settings')['gmail']['dependencies_ready'])

    def test_telegram_token_never_in_configuration_api_or_database(self):
        token='123456789:TEST_ONLY_NOT_A_REAL_BOT_TOKEN'
        data=self.request('settings',self.values(bot_token=token,chat_id='123456',telegram_enabled=True,auto_send_new=True,send_start_at='2026-10-07T10:00:00+02:00'))
        self.assertTrue(data['settings']['telegram_token_saved'])
        self.assertNotIn(token,json.dumps(data));self.assertNotIn(token,self.cfg.read_text());self.assertNotIn(token,self.db.read_bytes().decode('latin1'))
        self.assertEqual(read_secret:=json.loads((self.home/'telegram/secret.json').read_text())['bot_token'],token)
        self.assertFalse(load_config()['local']['notification']);self.assertFalse(load_config()['local']['auto_deliver_test'])
        self.request('settings',self.values(chat_id='123456',telegram_enabled=False))
        self.assertEqual(json.loads((self.home/'telegram/secret.json').read_text())['bot_token'],read_secret)

    def test_open_send_jobs_block_live_activation(self):
        with self.store.connection() as c:c.execute("INSERT INTO qa_jobs(kind,target) VALUES ('send','TEST-OLD-RESULT')")
        self.error('settings',self.values(bot_token='123456789:TEST_ONLY',chat_id='123',telegram_enabled=True))
        self.assertFalse(self.cfg.exists())

    def test_local_import_actual_managed_worker_pdf_and_portfolio_isolation(self):
        testconfig=config();testconfig['local']['mail_directory']=str(self.home/'inbox')
        private_write(self.cfg,testconfig)
        self.request('settings',self.values())
        self.request('import-eml',{'eml':(FIX/'emails/01-single.eml').read_text()})
        self.assertEqual(self.store.dashboard()['items'],[])
        data=self.request('control',{'action':'check-once'})
        self.wait_stopped()
        items=self.store.dashboard()['items'];self.assertEqual(len(items),1)
        self.assertEqual(items[0]['pdf_status'],'erstellt');self.assertEqual(items[0]['delivery_status'],'nicht_verbunden')
        self.assertEqual(items[0]['result']['calculation']['basis']['cashflowMonat'],-150)
        self.assertTrue((self.output/items[0]['pdf_name']).is_file())
        with self.store.connection() as c:
            regular=c.execute('SELECT kaufpreis,wohnflaeche FROM objekte').fetchall()
        self.assertEqual([tuple(r) for r in regular],[(100000,50)])
        self.assertFalse(self.store.dashboard()['worker']['status']['state']=='running')

    def test_start_stop_survives_controller_restart_and_disallows_live_edit(self):
        self.request('settings',self.values())
        self.request('control',{'action':'start-worker'})
        self.assertTrue(self.request('settings')['worker']['running'])
        self.error('control',{'action':'start-worker'})
        self.error('settings',self.values(interval=3))
        replacement=AutomationControl(self.store,self.output)
        self.assertTrue(replacement.view()['worker']['managed'])
        replacement.stop_worker()
        self.wait_stopped()
        self.assertFalse(self.request('settings')['worker']['running'])

    def test_connection_requires_matching_successful_gmail_scan(self):
        self.request('settings',self.values(source='gmail',senders=['alerts@example.invalid']))
        saved=load_config();saved['gmail']['token_path']=str(self.home/'gmail/token.json');private_write(self.cfg,saved)
        private_write(self.home/'gmail/token.json',{'refresh_token':'TEST-NOT-A-TOKEN','scopes':['https://www.googleapis.com/auth/gmail.readonly']})
        self.assertNotIn('Verbunden',self.control.connections()['gmail'])
        self.store.runtime({'mail_source':'gmail','mail_scan_ok':True,'mail_signature':mail_signature(saved)})
        self.assertIn('Verbunden',self.control.connections()['gmail'])
        saved['gmail']['query']='rfc822msgid:TEST@example.invalid';private_write(self.cfg,saved)
        self.assertNotIn('Verbunden',self.control.connections()['gmail'])
        self.store.runtime({'mail_source':'gmail','mail_scan_ok':True,'mail_signature':mail_signature(saved)})
        self.request('gmail-client',{'client':CLIENT})
        private_write(self.home/'gmail/token.json',{'refresh_token':'TEST-NEW-NOT-A-TOKEN','scopes':['https://www.googleapis.com/auth/gmail.readonly']})
        self.assertNotIn('Verbunden',self.control.connections()['gmail'])


if __name__=='__main__':unittest.main()
