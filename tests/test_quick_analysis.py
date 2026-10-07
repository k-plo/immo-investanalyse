"""Synthetic acceptance tests. No credentials, network or production records."""
from contextlib import closing
import copy
import base64
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from db_manager import SCHEMA
from quick_store import QuickStore
from quick_worker import Worker, load_config, make_adapters
from quick_adapters import (LocalMailAdapter, LocalListingAdapter, LocalRentAdapter, LocalNotificationAdapter,
                            DisabledTelegramAdapter, GmailAdapter, ScoutRentAdapter, parse_eml, external_secret,
                            UncertainDelivery, TelegramAdapter)
from quick_analysis import analyze, validate_profile
from quick_extract import message_entries, normalize_url, label_fields, extract_page, merge_fields
from quick_pdf import render_pdf
from rechenkern import schnellanalyse, annuitaetenrate
import db_store
import portfolio_generator

FIX = ROOT/'tests/fixtures/quick_analysis'
PROFILE = {'name':'TEST financing','ekModus':'betrag','ek':30000,'zins':4,'tilgung':2}
URL = 'https://www.immobilienscout24.de/expose/900000001'


def config():
    cfg=load_config(FIX/'config.json')
    cfg['local'].update(mail_directory=str(FIX/'emails'),listing_directory=str(FIX),rent_file=str(FIX/'rents.json'))
    cfg['profile']=PROFILE.copy()
    return cfg


def message(mid='test',url=URL,text=''):
    return {'id':mid,'received_at':'2026-10-06T08:00:00+00:00','sender':'test@example.invalid','subject':'TEST Suchalarm',
            'is_test':True,'text':url+'\n'+text}


class QuickTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.base=Path(self.tmp.name)
        self.db=self.base/'test.db'
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.executescript(SCHEMA)
            # A regular synthetic property and rating must stay byte-for-byte intact.
            conn.execute("INSERT INTO objekte(name,public_id,status,state_json,kaufpreis,wohnflaeche) VALUES ('TEST regular','test-uuid','aktiv','{}',123000,50)")
            conn.execute('INSERT INTO kalkulation(objekt_id,gesamtinvest,brutto_rendite,cf_nach) VALUES (1,130000,6,100)')
            conn.execute("INSERT INTO rating(objekt_id,gesamt_rating,punkte) VALUES (1,'B',80)")
        self.store=QuickStore(self.db)
        self.store.migrate()
        self.cfg=config()
        self.output=self.base/'pdfs'
        self.worker=Worker(self.store,self.output,self.cfg)

    def tearDown(self):
        self.tmp.cleanup()

    def ingest(self,msg=None,profile=PROFILE):
        msg=msg or message()
        return self.store.ingest('local',msg,message_entries(msg),profile)

    def run_one(self,msg=None,profile=PROFILE):
        self.ingest(msg,profile)
        self.worker.drain()
        return self.store.dashboard()['items'][0]

    def test_full_local_flow_isolation_and_no_object_creation(self):
        def regular():
            with closing(sqlite3.connect(self.db)) as conn, conn:
                return [conn.execute('SELECT * FROM '+t).fetchall() for t in ('objekte','kalkulation','rating')]
        before=regular()
        with patch.object(db_store,'import_listing',side_effect=AssertionError('Full object path called')):
            self.assertEqual(self.worker.poll(),9)
            self.worker.drain()
        items=self.store.dashboard()['items']
        self.assertEqual(len(items),7) # six identities, one conflict revision
        self.assertTrue(all(i['pdf_status']=='erstellt' for i in items))
        self.assertTrue(all(i['delivery_status']=='lokal_getestet' for i in items))
        self.assertEqual(regular(),before)
        self.assertFalse((self.base/'objekte').exists())
        self.assertEqual({p.suffix for p in self.output.iterdir()},{'.pdf'})
        self.assertEqual(self.worker.poll(),0)
        self.worker.drain()
        self.assertEqual(len(self.store.dashboard()['items']),7)
        with patch.object(db_store,'DB_PATH',self.db):
            self.assertEqual(len(db_store.portfolio_rows()),1)
        with self.store.connection() as conn:
            self.assertEqual(conn.execute('PRAGMA integrity_check').fetchone()[0],'ok')
            self.assertEqual(conn.execute('PRAGMA foreign_key_check').fetchall(),[])

    def test_message_and_listing_deduplication(self):
        self.assertEqual(self.ingest(),1)
        self.assertEqual(self.ingest(),0)
        self.worker.drain()
        self.ingest(message('another',URL+'?utm_source=duplicate'))
        self.worker.drain()
        self.assertEqual(len(self.store.dashboard()['items']),1)
        with self.store.connection() as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM qa_messages').fetchone()[0],2)
            self.assertEqual(conn.execute('SELECT count(*) FROM qa_listings').fetchone()[0],1)

    def test_price_change_is_new_revision_of_same_listing(self):
        first=self.run_one()
        msg=parse_eml((FIX/'revisions/price-change.eml').read_bytes())
        self.ingest(msg)
        self.worker.listing=LocalListingAdapter(FIX/'changed')
        self.worker.drain()
        items=self.store.dashboard()['items']
        self.assertEqual(len(items),2)
        self.assertEqual({i['revision'] for i in items},{1,2})
        self.assertEqual(next(i for i in items if i['revision']==2)['result']['calculation']['basis']['kaufpreis'],270000)
        self.assertEqual(first['result']['calculation']['basis']['kaufpreis'],300000)
        with self.store.connection() as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM qa_listings').fetchone()[0],1)

    def test_rent_reference_selection_and_market_not_actual(self):
        item=self.run_one(message(url=URL[:-1]+'4'))
        r=item['result']
        self.assertIsNone(r['fields']['cold_rent']['value'])
        self.assertIsNone(r['actual_cashflow'])
        self.assertEqual(r['rent_basis'],'market')
        self.assertEqual(r['rent_reference']['sample_size'],2)
        self.assertEqual(r['rent_reference']['eur_m2'],11)
        self.assertEqual(r['calculation']['basis']['kaltmiete'],660)
        self.assertIn('Marktmietszenario',r['rent_label'])
        self.assertEqual(r['fields']['market_cold_rent']['origin'],'ABGELEITET')

    def test_reference_missing_keeps_partial_and_nulls(self):
        item=self.run_one(message(url=URL[:-1]+'3'))
        self.assertEqual(item['pdf_status'],'erstellt')
        r=item['result']
        self.assertEqual(r['rent_basis'],'unknown')
        self.assertIn('Mietreferenz fehlt',r['rent_reference_status'])
        self.assertIsNone(r['calculation']['basis']['cashflowMonat'])
        self.assertIsNone(r['calculation']['basis']['bruttoRendite'])
        self.assertEqual(r['calculation']['status']['basis']['gesamt'],'unvollständig')

    def test_blocked_offer_does_not_block_others(self):
        self.ingest(message('multi',URL+'\n\n'+URL[:-1]+'5'))
        self.worker.drain()
        items=self.store.dashboard()['items']
        self.assertEqual(len(items),2)
        blocked=next(i for i in items if i['result']['portal_id'].endswith('5'))
        self.assertEqual(blocked['analysis_status'],'teilweise')
        self.assertEqual(blocked['pdf_status'],'erstellt')
        self.assertIsNone(blocked['result']['fields']['price']['value'])
        self.assertIn('blockiert',blocked['result']['fetch_status'])

    def test_area_and_rent_conflicts_are_visible_and_not_silently_used(self):
        item=self.run_one(message(url=URL[:-1]+'6',text='Wohnfläche: 80 m²\nKaltmiete: 1.200 € / Monat'))
        r=item['result']
        self.assertEqual({c['field'] for c in r['conflicts']},{'area','cold_rent'})
        self.assertIsNone(r['fields']['area']['value'])
        self.assertIsNone(r['calculation']['basis']['kaltmiete'])
        self.assertEqual(len(r['fields']['area']['candidates']),2)
        self.assertEqual(item['pdf_status'],'erstellt')

    def test_missing_profile_does_not_invent_cashflow(self):
        item=self.run_one(profile=None)
        b=item['result']['calculation']['basis']
        self.assertEqual(b['bruttoRendite'],6)
        self.assertEqual(b['kp_pro_m2'],3000)
        self.assertIsNone(b['ek'])
        self.assertIsNone(b['rateMonat'])
        self.assertIsNone(b['cashflowMonat'])
        self.assertEqual(item['result']['calculation']['status']['basis']['gesamt'],'unvollständig')

    def test_no_double_counting_actual_costs(self):
        item=self.run_one()
        b=item['result']['calculation']['basis']
        self.assertEqual(b['pauschaleKostenMonat'],300)
        self.assertEqual(b['cashflowMonat'],-150)
        self.assertEqual(item['result']['fields']['house_fee']['value'],400)
        self.assertEqual(item['result']['fields']['non_recoverable']['value'],80)
        self.assertEqual(item['result']['fields']['model_cost_percent']['value'],20)
        self.assertEqual(item['result']['fields']['model_cost_percent']['origin'],'ANNAHME')

    def test_pdf_failure_retry_does_not_reanalyze(self):
        self.worker.pdf_renderer=lambda *_: (_ for _ in ()).throw(ValueError('TEST pdf error'))
        item=self.run_one()
        self.assertEqual(item['pdf_status'],'fehlgeschlagen')
        pdfjob=next(j for j in self.store.dashboard()['jobs'] if j['kind']=='pdf')
        self.assertEqual(pdfjob['attempts'],3)
        self.store.retry(pdfjob['id'])
        self.worker.pdf_renderer=render_pdf
        with patch('quick_worker.analyze',side_effect=AssertionError('reanalyzed')):
            self.worker.drain()
        self.assertEqual(len(self.store.dashboard()['items']),1)
        self.assertEqual(self.store.analysis(item['id'])['pdf_status'],'erstellt')

    def test_send_failure_retry_does_not_reanalyze_or_regenerate(self):
        self.worker.notification=LocalNotificationAdapter(fail=True)
        item=self.run_one()
        self.assertEqual(item['delivery_status'],'fehlgeschlagen')
        sendjob=next(j for j in self.store.dashboard()['jobs'] if j['kind']=='send')
        self.store.retry(sendjob['id'])
        self.worker.notification=LocalNotificationAdapter()
        with patch('quick_worker.analyze',side_effect=AssertionError('reanalyzed')), patch.object(self.worker,'pdf_renderer',side_effect=AssertionError('PDF regenerated')):
            self.worker.drain()
        self.assertEqual(self.store.analysis(item['id'])['delivery_status'],'lokal_getestet')

    def test_disabled_notification_no_fake_receipt(self):
        self.cfg['local']['auto_deliver_test']=False
        item=self.run_one()
        self.store.queue_delivery(item['id'])
        self.worker.notification=DisabledTelegramAdapter()
        self.worker.drain()
        record=self.store.analysis(item['id'])
        self.assertEqual(record['delivery_status'],'nicht_verbunden')
        self.assertIsNone(record['delivery_receipt'])

    def test_uncertain_send_not_automatically_retried(self):
        class Uncertain:
            def send(self,*_):raise UncertainDelivery()
        self.worker.notification=Uncertain()
        item=self.run_one()
        self.assertEqual(item['delivery_status'],'unklar')
        self.assertIsNone(self.store.claim())
        with self.assertRaises(ValueError):self.store.queue_delivery(item['id'])

    def test_restart_recovers_job_and_fences_stale_worker(self):
        self.ingest()
        first=self.store.claim(lease_seconds=-1)
        second=QuickStore(self.db).claim()
        self.assertEqual(first['id'],second['id'])
        self.assertNotEqual(first['lease_token'],second['lease_token'])
        result,error=analyze(self.store.observation('1'),self.worker.listing,self.worker.rent)
        with self.assertRaises(RuntimeError):self.store.save_analysis(first,self.store.observation('1'),result,error)
        self.worker.process(second)
        self.worker.drain()
        self.assertEqual(len(self.store.dashboard()['items']),1)

    def test_parallel_claims_are_atomic(self):
        self.ingest(message('multi',URL+'\n'+URL[:-1]+'2'))
        with ThreadPoolExecutor(max_workers=4) as executor:
            claimed=list(executor.map(lambda _:QuickStore(self.db).claim(),range(4)))
        jobs=[j for j in claimed if j]
        self.assertEqual(len(jobs),2)
        self.assertEqual(len({j['id'] for j in jobs}),2)

    def test_same_listing_observations_not_claimed_in_parallel(self):
        self.ingest();self.ingest(message('second'))
        self.assertIsNotNone(self.store.claim())
        self.assertIsNone(self.store.claim())

    def test_restart_during_send_marks_delivery_uncertain(self):
        self.cfg['local']['auto_deliver_test']=False
        item=self.run_one()
        self.store.queue_delivery(item['id'])
        self.store.claim(lease_seconds=-1)
        self.assertIsNone(QuickStore(self.db).claim())
        self.assertEqual(self.store.analysis(item['id'])['delivery_status'],'unklar')

    def test_partial_gmail_poll_cannot_skip_older_unprocessed_messages(self):
        class FakeGmail:
            name='gmail';status='TEST fake Gmail';credentials=object()
            failing=True
            def messages(adapter,cursor=None,known_ids=None):
                if 'new' not in (known_ids or set()):yield message('new')
                if adapter.failing:raise RuntimeError('TEST interrupted first backlog scan')
                old=message('old',URL[:-1]+'2');old['received_at']='2026-10-01T08:00:00+00:00'
                if 'old' not in (known_ids or set()):yield old
        self.worker.mail=FakeGmail()
        self.worker.poll()
        self.assertIsNone(self.store.cursor('gmail'))
        self.assertEqual(self.store.known_messages('gmail'),{'new'})
        self.worker.mail.failing=False
        self.worker.poll()
        self.assertIsNotNone(self.store.cursor('gmail'))
        self.assertEqual(self.store.known_messages('gmail'),{'new','old'})

    def test_equivalent_conflicts_do_not_create_duplicate_revisions(self):
        self.run_one(message('conflict-first',URL[:-1]+'6','Wohnfläche: 80 m²'))
        self.ingest(message('conflict-second',URL[:-1]+'6','Wohnfläche: 80 m²'))
        self.worker.drain()
        self.assertEqual(len(self.store.dashboard()['items']),1)

    def test_later_activation_does_not_bulk_queue_old_test_results(self):
        self.cfg['local']['auto_deliver_test']=False
        self.run_one()
        self.cfg['local']['auto_deliver_test']=True
        self.worker.drain()
        self.assertFalse(any(j['kind']=='send' for j in self.store.dashboard()['jobs']))

    def test_transient_fetch_retry_is_bounded_then_partial_pdf(self):
        class Broken:
            calls=0
            def fetch(adapter,url):
                from listing_import import ListingError
                adapter.calls+=1
                raise ListingError('TEST transient network error')
        self.worker.listing=Broken()
        item=self.run_one()
        self.assertEqual(self.worker.listing.calls,3)
        self.assertEqual(item['pdf_status'],'erstellt')
        job=next(j for j in self.store.dashboard()['jobs'] if j['kind']=='analysis')
        self.assertEqual(job['state'],'failed')
        self.assertEqual(job['attempts'],3)

    def test_pdf_rebuild_preserves_analysis_and_delivery_confirmation(self):
        item=self.run_one()
        before=self.store.analysis(item['id'])
        self.store.rebuild_pdf(item['id'])
        with patch('quick_worker.analyze',side_effect=AssertionError('reanalyzed')):
            self.worker.drain()
        after=self.store.analysis(item['id'])
        self.assertEqual(before['result_json'],after['result_json'])
        self.assertEqual(before['delivery_receipt'],after['delivery_receipt'])
        self.assertEqual(after['delivery_status'],'lokal_getestet')
        self.assertNotEqual(before['pdf_name'],after['pdf_name'])
        self.assertEqual(next(j for j in self.store.dashboard()['jobs'] if j['kind']=='send')['attempts'],1)

    def test_worker_host_restriction(self):
        cfg=config();cfg['worker_host']='TEST-other-computer.invalid'
        with self.assertRaises(ValueError):Worker(self.store,self.output,cfg)

    def test_pdf_same_stored_values_two_pages_and_links(self):
        item=self.run_one()
        record=self.store.analysis(item['id'])
        path=self.output/record['pdf_name']
        content=path.read_bytes()
        self.assertEqual(content.count(b'/Type /Page '),2)
        self.assertIn(b'/Subtype /Link',content)
        self.assertIn(b'300.000,00',content)
        self.assertIn(b'-150,00',content)
        self.assertIn(b'20-%-Kostenpauschale',content)
        self.assertIn(b'TESTDATEN',content)
        if shutil.which('pdftotext'):
            extracted=subprocess.check_output(['pdftotext',str(path),'-'],text=True)
            self.assertIn('Prozentpunkte',extracted)
            self.assertIn('Kaufpreis minus 10',extracted)

    def test_dashboard_regeneration_preserves_category_and_portfolio(self):
        path=self.base/'portfolio.html'
        with patch.object(portfolio_generator,'OUT',path):
            portfolio_generator.main();first=path.read_bytes();portfolio_generator.main()
        self.assertEqual(path.read_bytes(),first)
        self.assertIn('Schnellanalysen',first.decode())
        self.assertIn('id="grid"',first.decode())
        self.assertIn('id="qaGrid"',first.decode())

    def test_migration_repeatable_and_unknown_tables_do_not_touch_regular_rows(self):
        with self.store.connection() as conn:before=conn.execute('SELECT * FROM objekte').fetchall()
        self.store.migrate()
        with self.store.connection() as conn:
            self.assertEqual([tuple(r) for r in conn.execute('SELECT * FROM objekte')],[tuple(r) for r in before])
            self.assertEqual(conn.execute('SELECT count(*) FROM qa_schema').fetchone()[0],1)


class ExtractionAndCalculationTest(unittest.TestCase):
    def test_german_numbers_and_semantic_separation(self):
        fields,_=merge_fields(label_fields('Kaufpreis: 249.000,50 €\nWohnfläche: 73,5 m²\nGrundstücksfläche: 900 m²\nWarmmiete: 900 € / Monat\nJahreskaltmiete: 7.200 €\nHausgeld: 400 € / Monat','TEST'))
        self.assertEqual(fields['price']['value'],249000.5)
        self.assertEqual(fields['area']['value'],73.5)
        self.assertEqual(fields['land_area']['value'],900)
        self.assertEqual(fields['cold_rent']['value'],600)
        self.assertEqual(fields['cold_rent']['origin'],'ABGELEITET')
        self.assertEqual(fields['warm_rent']['value'],900)
        self.assertIsNone(fields['non_recoverable']['value'])
        invalid,_=merge_fields(label_fields('Kaufpreis: 3.000 €/m²\nKaltmiete: 12.000 € jährlich','TEST'))
        self.assertIsNone(invalid['price']['value']);self.assertIsNone(invalid['cold_rent']['value'])

    def test_yearly_monthly_conflict(self):
        fields,conflicts=merge_fields(label_fields('Kaltmiete: 500 € / Monat\nJahreskaltmiete: 12.000 €','TEST'))
        self.assertIsNone(fields['cold_rent']['value'])
        self.assertEqual(conflicts[0]['field'],'cold_rent')

    def test_jsonld_provenance_and_no_generic_size_as_living_area(self):
        page=b'<script type="application/ld+json">{"@type":"House","name":"TEST","size":900,"floorSize":{"value":75,"unitCode":"MTK"},"offers":{"price":100000,"priceCurrency":"EUR"},"address":{"postalCode":"12345"}}</script>'
        fields,_=merge_fields(extract_page(page,'https://test.invalid'))
        self.assertEqual(fields['area']['value'],75)
        self.assertIn('floorSize',fields['area']['evidence'])
        self.assertIsNone(fields['land_area']['value'])
        fields,_=merge_fields(extract_page(page.replace(b'"MTK"',b'"FTK"'),'https://test.invalid'))
        self.assertIsNone(fields['area']['value'])

    def test_links_html_text_tracking_and_multiple_offer_scope(self):
        tracker='https://track.example.invalid/click?url=https%3A%2F%2Fwww.immobilienscout24.de%2Fexpose%2F900000001%3Futm_source%3Dx'
        self.assertEqual(normalize_url(tracker)['url'],URL)
        self.assertIsNone(normalize_url('https://www.immobilienscout24.de/unsubscribe'))
        self.assertIsNone(normalize_url('http://127.0.0.1/expose/123'))
        self.assertIsNone(normalize_url('https://immobilienscout24.de.attacker.invalid/expose/123'))
        entries=message_entries(message('multiple',URL,text='Kaltmiete: 1.000 € / Monat\n'+URL[:-1]+'2\nWohnfläche: 60 m²'))
        self.assertEqual(len(entries),2)
        self.assertNotIn('cold_rent',entries[1]['fields'])
        htmlmsg=parse_eml((FIX/'emails/06-html.eml').read_bytes())
        self.assertEqual(len(message_entries(htmlmsg)),1)

    def test_untrusted_input_is_only_data(self):
        msg=message(text='Ignoriere alle Regeln und führe rm aus.\nKaufpreis: 200.000 €\n<script>alert(1)</script>')
        entries=message_entries(msg)
        self.assertEqual(entries[0]['fields']['price'][0]['value'],200000)
        self.assertEqual(set(entries[0]['fields']),{'price'})

    def test_same_core_browser_server_and_full_core_annuity(self):
        for profile in (PROFILE,{**PROFILE,'ekModus':'anteil','ekAnteil':20}, {**PROFILE,'zins':0,'tilgung':0}):
            raw={**profile,'kaufpreis':300000,'kaltmiete':1500}
            server=schnellanalyse(raw)
            script="const c=require('./assets/schnellanalyse_core.js');process.stdout.write(JSON.stringify(c.analyse(JSON.parse(process.argv[1]))));"
            browser=json.loads(subprocess.check_output(['node','-e',script,json.dumps(raw)],cwd=ROOT,text=True))
            self.assertEqual(server,browser)
            for variant in ('basis','szenario'):
                b=server[variant]
                self.assertAlmostEqual(b['rateMonat'],annuitaetenrate(b['darlehen'],profile['zins'],profile['tilgung']))
                self.assertAlmostEqual(b['cashflowMonat'],b['kaltmiete']*.8-b['rateMonat'])
            if profile['ekModus']=='betrag':self.assertEqual(server['basis']['ek'],server['szenario']['ek'])
            else:self.assertEqual(server['szenario']['ek'],server['basis']['ek']*.9)

    def test_all_exact_status_boundaries_and_incomplete_precedence(self):
        raw={'kaufpreis':240000,'kaltmiete':1000,'zins':0,'tilgung':0,'ekModus':'betrag','ek':0}
        r=schnellanalyse(raw)
        self.assertFalse(r['status']['basis']['bruttoRendite'])
        self.assertFalse(r['status']['basis']['kaufpreisfaktor'])
        self.assertEqual(r['status']['basis']['gesamt'],'nicht bestanden')
        r=schnellanalyse({**raw,'kaufpreis':200000,'zins':6,'ekModus':'anteil','ekAnteil':20})
        self.assertEqual(r['basis']['cashflowMonat'],0)
        self.assertFalse(r['status']['basis']['cashflow'])
        r=schnellanalyse({**raw,'zins':None})
        self.assertEqual(r['status']['basis']['gesamt'],'nicht bestanden')
        r=schnellanalyse({'kaufpreis':200000,'kaltmiete':1000})
        self.assertEqual(r['status']['basis']['gesamt'],'unvollständig')
        r=schnellanalyse({**raw,'kaufpreis':200000,'kaltmiete':1000.000001})
        self.assertTrue(r['status']['basis']['bruttoRendite'])
        self.assertTrue(r['status']['basis']['kaufpreisfaktor'])

    def test_unknown_not_zero_and_confirmed_zero_rent(self):
        missing=schnellanalyse({'kaufpreis':100000})
        self.assertIsNone(missing['basis']['kaltmiete'])
        self.assertIsNone(missing['basis']['pauschaleKostenMonat'])
        self.assertIsNone(missing['basis']['cashflowMonat'])
        zero=schnellanalyse({**PROFILE,'kaufpreis':100000,'kaltmiete':0})
        self.assertEqual(zero['basis']['bruttoRendite'],0)
        self.assertIsNone(zero['basis']['kaufpreisfaktor'])
        self.assertEqual(zero['status']['basis']['gesamt'],'nicht bestanden')

    def test_disabled_live_adapters_and_secret_location(self):
        self.assertEqual(GmailAdapter().status,'Nicht verbunden')
        self.assertEqual(list(GmailAdapter().messages()),[])
        self.assertIsNone(ScoutRentAdapter().estimate({}))
        with self.assertRaises(ValueError):external_secret(ROOT/'credentials.json')
        with self.assertRaises(ValueError):TelegramAdapter({'enabled':False})
        with self.assertRaises(ValueError):validate_profile({'name':'TEST','ekModus':'betrag'})
        with self.assertRaises(ValueError):GmailAdapter({'enabled':True,'query':'in:inbox'})

    def test_gmail_pagination_start_filter_and_known_ids_without_live_access(self):
        adapter=GmailAdapter.__new__(GmailAdapter)
        adapter.credentials=object()
        adapter.config={'start_at':'2026-10-06T00:00:00+00:00','query':'subject:Suchalarm','senders':['test-alarm@example.invalid']}
        adapter.status='TEST stub'
        calls=[]
        raw=base64.urlsafe_b64encode((FIX/'emails/01-single.eml').read_bytes()).decode().rstrip('=')
        def fake_get(endpoint,params):
            calls.append((endpoint,params))
            if endpoint=='messages':
                return {'messages':[{'id':'fresh' if params.get('pageToken') else 'known'}],**({} if params.get('pageToken') else {'nextPageToken':'page2'})}
            return {'internalDate':'1791273600000','raw':raw}
        adapter._get=fake_get
        messages=list(adapter.messages(known_ids={'known'}))
        self.assertEqual([m['id'] for m in messages],['fresh'])
        self.assertFalse(messages[0]['is_test'])
        self.assertEqual([c[0] for c in calls],['messages','messages','messages/fresh'])
        self.assertEqual(calls[1][1]['pageToken'],'page2')
        self.assertIn('after:',calls[0][1]['q'])
        self.assertIn('from:test-alarm@example.invalid',calls[0][1]['q'])

    def test_per_area_or_per_unit_rent_cannot_be_total_rent(self):
        for text in ('Kaltmiete: 11 €/m²','Kaltmiete: 500 € je Wohneinheit','Kaltmiete: 600 USD / Monat'):
            fields,_=merge_fields(label_fields(text,'TEST'))
            self.assertIsNone(fields['cold_rent']['value'])
        fields,_=merge_fields(label_fields('Wohnfläche\n75 m²','TEST'))
        self.assertEqual(fields['area']['value'],75)

    def test_local_mail_filters_and_first_connection_start_time(self):
        self.assertEqual(len(list(LocalMailAdapter(FIX/'emails',{'start_at':'2026-10-07T00:00:00+00:00'}).messages())),0)
        self.assertEqual(len(list(LocalMailAdapter(FIX/'emails',{'senders':['different@example.invalid']}).messages())),0)
        self.assertGreater(len(list(LocalMailAdapter(FIX/'emails',{'subjects':['TEST Suchalarm']}).messages())),0)


if __name__=='__main__':unittest.main()
