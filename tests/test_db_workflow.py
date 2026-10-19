import base64
import json
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import db_store
import rent_research
from db_manager import berechne_rating
from listing_import import (extract_energy_certificate_facts, extract_extra_facts, extract_listing,
                            validate_url, ListingError)


PAGE = b'''<html><head><title>Haus in Neustadt</title>
<meta property="og:image" content="https://bilder.example.org/haus.png">
<script type="application/ld+json">{"@type":"House","name":"Haus in Neustadt","address":{"streetAddress":"Hauptstr. 1","postalCode":"12345","addressLocality":"Neustadt"},"floorSize":{"value":120},"numberOfRooms":4,"offers":{"price":"249.000"}}</script>
</head><body></body></html>'''
SC_PAGE = b'''<html><head><title>ETW Kassel-Wehlheiden</title>
<script type="application/ld+json">{"@type":"Apartment","name":"ETW Kassel","description":"Gepflegte Wohnung, Baujahr: 1965, Energieeffizienzklasse D, 2. OG, Kaltmiete: 620 EUR","address":{"streetAddress":"Frankfurter Str. 12","postalCode":"34121","addressLocality":"Kassel-Wehlheiden"},"floorSize":{"value":75},"numberOfRooms":3,"offers":{"price":"189.000"}}</script>
</head><body><div data-testid="aviv.CDP.Contacting.ProviderSection"><div data-testid="aviv.CDP.Contacting.ProviderSection.IntermediaryCard"><div data-testid="aviv.CDP.Contacting.ProviderSection.IntermediaryCard.Logo"><a aria-label="Mustermann Immobilien GmbH"></a></div><span>Mustermann Immobilien GmbH</span><span>Herr Max Mustermann</span><span>Dein Kontakt</span></div></div></body></html>'''
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/l0cAAAAASUVORK5CYII=')


class DbWorkflowTest(unittest.TestCase):
    def test_missing_interest_never_becomes_zero_percent_financing(self):
        result = berechne_rating({'preis':'179000','flaeche':'88','kaltmiete':'645','zins':'','tilgung':'2'}, [])
        self.assertIsNone(result['cf_nach'])
        self.assertEqual(result['gesamt_rating'], '?')

    def test_listing_parser_and_private_url_rejection(self):
        item = extract_listing(PAGE, 'https://example.org/anzeige/1')
        self.assertEqual(item['price'], 249000)
        self.assertEqual(item['area'], 120)
        self.assertEqual(item['locality'], 'Neustadt')
        with self.assertRaises(ListingError):
            validate_url('http://127.0.0.1:8000/private')

    def test_listing_parser_extra_facts(self):
        item = extract_listing(SC_PAGE, 'https://example.org/anzeige/9')
        self.assertEqual(item['strasse'], 'Frankfurter Str.')
        self.assertEqual(item['hausnummer'], '12')
        self.assertEqual(item['ort'], 'Kassel')
        self.assertEqual(item['stadtteil'], 'Wehlheiden')
        self.assertEqual(item['baujahr'], 1965)
        self.assertEqual(item['energieklasse'], 'D')
        self.assertEqual(item['geschoss'], '2. OG')
        self.assertEqual(item['kaltmiete'], 620)
        self.assertEqual(item['maklerfirma'], 'Mustermann Immobilien GmbH')
        self.assertEqual(item['ansprechpartner'], 'Max Mustermann')

    def test_annual_cold_rent_is_converted_to_monthly_amount(self):
        facts = extract_extra_facts('Mietfläche ca. 24 m² - jährliche Kaltmiete € 3.600,-')
        self.assertEqual(facts['kaltmiete'], 300)

    def test_energy_certificate_address_and_embedded_living_area(self):
        state = json.dumps({
            'documents': {'display': True, 'files': [{
                'url': 'https://mms.immowelt.de/energy.pdf',
                'title': 'Energieausweis Franzgraben 35-37 Kassel.pdf',
            }]},
            'Baujahr': 1993,
            'Wohnflaeche': 33.16,
        }, ensure_ascii=False, separators=(',', ':'))
        page = f'<script>window.state={json.dumps(state, ensure_ascii=False)};</script>'.encode('utf-8')
        pdf_url = 'https://mms.immowelt.de/energy.pdf'
        with (
            patch('listing_import.fetch_public', return_value=(pdf_url, b'%PDF-test', 'application/pdf')),
            patch('listing_import._read_pdf_text', return_value=(
                'Franzgraben35-37 ; 34125 Kassel\nAdresse\nGebäudeteil\n1993')),
        ):
            listing = extract_listing(page, 'https://www.immowelt.de/expose/test')
            certificate = extract_energy_certificate_facts(page)
        self.assertEqual(listing['area'], 33.16)
        self.assertEqual(listing['baujahr'], 1993)
        self.assertEqual(certificate['strasse'], 'Franzgraben')
        self.assertEqual(certificate['hausnummer'], '35-37')
        self.assertEqual(certificate['plz'], '34125')
        self.assertEqual(certificate['ort'], 'Kassel')

    def test_same_town_distinct_ids_and_revision_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / 'objekte' / '_VORLAGE').mkdir(parents=True)
            shutil.copy2(ROOT / 'objekte' / '_VORLAGE' / 'Objektname_Übersicht.html',
                         base / 'objekte' / '_VORLAGE' / 'Objektname_Übersicht.html')
            db_path = base / 'immo_datenbank.db'
            shutil.copy2(ROOT / 'immo_datenbank.db', db_path)

            def fake_fetch(url, limit=3_000_000):
                if 'bilder.' in url:
                    return url, PNG, 'image/png'
                return url, PAGE, 'text/html; charset=utf-8'

            with patch.object(db_store, 'BASE', base), patch.object(db_store, 'DB_PATH', db_path), patch.object(db_store, 'validate_url', side_effect=lambda url: url), patch.object(db_store, 'fetch_public', side_effect=fake_fetch):
                first = db_store.import_listing('https://example.org/anzeige/1')
                second = db_store.import_listing('https://example.org/anzeige/2')
                self.assertNotEqual(first['id'], second['id'])
                self.assertNotEqual(first['name'], second['name'])
                self.assertEqual(db_store.get_object(first['id'])['display_name'], 'Haus in Neustadt')
                self.assertTrue(db_store.get_object(first['id'])['image_path'].endswith('.png'))
                state = db_store.get_object(first['id'])['state']
                self.assertEqual(state['preis'], '249000.0')
                self.assertEqual(db_store.save_object(first['id'], state, 1)['revision'], 2)
                with self.assertRaises(db_store.RevisionConflict):
                    db_store.save_object(first['id'], state, 1)
                photo = db_store.set_photo(first['id'], base64.b64encode(PNG).decode(), 'image/png', 2)
                self.assertEqual(photo['revision'], 3)
                self.assertTrue((base / photo['image_path'].lstrip('/')).exists())
                archived = db_store.set_archive_status(first['id'], True, 3)
                self.assertEqual(archived['status'], 'archiviert')
                self.assertTrue((base / 'objekte' / '_ARCHIV' / first['name']).exists())
                reactivated = db_store.set_archive_status(first['id'], False, 4)
                self.assertEqual(reactivated['status'], 'aktiv')
                with sqlite3.connect(db_path) as conn:
                    self.assertEqual(conn.execute('PRAGMA integrity_check').fetchone()[0], 'ok')

            with patch.object(db_store, 'BASE', base), patch.object(db_store, 'DB_PATH', db_path), patch.object(db_store, 'validate_url', side_effect=lambda url: url), patch.object(db_store, 'fetch_public', side_effect=ListingError('Anzeige nicht abrufbar (HTTP 403)')):
                blocked = db_store.import_listing('https://example.org/anzeige/3')
                self.assertIn('Abruf blockiert', blocked['status'])
                self.assertEqual(db_store.get_object(blocked['id'])['analysis_status'], 'abruf_blockiert')


class SchnellcheckTest(unittest.TestCase):
    def test_kassel_address_range_requires_one_residential_zone(self):
        rows = [{"2000": 8.0, "wohnflaeche": 33}]
        addresses = [
            {"straße": "Franzgraben", "nr": "35", "wohnlage": "einfach"},
            {"straße": "Franzgraben", "nr": "37", "wohnlage": "einfach"},
        ]
        with patch.object(rent_research, '_kassel_data', return_value=(addresses, {
            'uF': rows, 'cF': rows, 'mF': rows, 'fF': rows,
        })):
            result = rent_research._kassel_official_mean({
                'ort': 'Kassel', 'strasse': 'Franzgraben', 'hausnummer': '35-37',
                'area': 33.16, 'baujahr': 1993,
            })
        self.assertEqual(result, (8.3256, 'einfach'))

        addresses[1]['wohnlage'] = 'mittel'
        with patch.object(rent_research, '_kassel_data', return_value=(addresses, {
            'uF': rows, 'cF': rows, 'mF': rows, 'fF': rows,
        })):
            self.assertIsNone(rent_research._kassel_official_mean({
                'ort': 'Kassel', 'strasse': 'Franzgraben', 'hausnummer': '35-37',
                'area': 33.16, 'baujahr': 1993,
            }))

    def test_kassel_official_mietspiegel_is_preferred_when_address_is_known(self):
        rows = [{"1949": 10.0, "1960": 9.0, "1977": 7.55, "wohnflaeche": 44}]
        addresses = [{"straße": "Teststraße", "nr": "1A", "wohnlage": "mittel"}]
        with patch.object(rent_research, '_kassel_data', return_value=(addresses, {
            'uF': rows, 'cF': rows, 'mF': rows, 'fF': rows,
        })):
            result = rent_research.research_potential_rent(
                {'ort': 'Kassel', 'strasse': 'Teststr.', 'hausnummer': '1a',
                 'area': 43.6, 'baujahr': 1963}, b'', 'https://example.org/anzeige')
        self.assertEqual(result['kaltmiete_pot'], 342.58)
        self.assertIn('Kasseler Mietspiegel 2026', result['miete_pot_quelle'])
        self.assertIn('Wohnlage mittel', result['miete_pot_quelle'])

    def test_regional_rent_research_uses_market_page_and_area(self):
        listing_page = b'''<script type="application/ld+json">{"@type":"BreadcrumbList","itemListElement":[{"position":1,"item":{"@id":"https://www.immowelt.de/suche/kaufen/wohnung/hessen/kassel-34127/ad08de2795"}}]}</script>'''
        market_page = '<div>Wohnung Preis pro Quadratmeter 8,87 €</div><p>Geschätzter Preis aktualisiert am 01. Oktober 2026.</p>'.encode('utf-8')
        market_url = 'https://www.immowelt.de/immobilienpreise/mietpreise/hessen/kassel-34127/ad08de2795'
        with patch.object(rent_research, 'fetch_public', return_value=(market_url, market_page, 'text/html')):
            result = rent_research.research_potential_rent(
                {'area': 43.6, 'ort': 'Kassel', 'stadtteil': 'Nord-Holland'}, listing_page,
                'https://www.immowelt.de/expose/example')
        self.assertEqual(result['kaltmiete_pot'], 386.73)
        self.assertIn('Kassel (Stadt)', result['miete_pot_quelle'])
        self.assertIn('01. Oktober 2026', result['miete_pot_quelle'])

    def test_create_update_uebersicht_delete(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            base = Path(tmp)
            (base / 'objekte' / '_VORLAGE').mkdir(parents=True)
            shutil.copy2(ROOT / 'objekte' / '_VORLAGE' / 'Objektname_Übersicht.html',
                         base / 'objekte' / '_VORLAGE' / 'Objektname_Übersicht.html')
            db_path = base / 'immo_datenbank.db'
            shutil.copy2(ROOT / 'immo_datenbank.db', db_path)

            def fake_fetch(url, limit=3_000_000):
                return url, SC_PAGE, 'text/html; charset=utf-8'

            patches = (patch.object(db_store, 'BASE', base), patch.object(db_store, 'DB_PATH', db_path),
                       patch.object(db_store, 'validate_url', side_effect=lambda url: url),
                       patch.object(db_store, 'fetch_public', side_effect=fake_fetch),
                       patch.object(db_store, 'research_potential_rent', return_value={
                           'kaltmiete_pot': 650, 'miete_pot_quelle': 'Automatische regionale Mietrecherche'}))
            with patches[0], patches[1], patches[2], patches[3], patches[4]:
                # Die kopierte Echt-DB kann bereits Schnellchecks enthalten -> Tabelle leeren
                with db_store.connection() as conn:
                    conn.execute('DELETE FROM schnellcheck')
                    conn.commit()
                check = db_store.create_schnellcheck('https://example.org/anzeige/9')
                self.assertFalse(check['existing'])
                self.assertEqual(check['kaufpreis'], 189000)
                self.assertEqual(check['strasse'], 'Frankfurter Str.')
                self.assertEqual(check['ort'], 'Kassel')
                self.assertEqual(check['energieklasse'], 'D')
                self.assertEqual(check['maklerfirma'], 'Mustermann Immobilien GmbH')
                self.assertEqual(check['ansprechpartner'], 'Max Mustermann')
                self.assertEqual(check['kaltmiete_ist'], 620)
                self.assertEqual(check['kaltmiete_pot'], 650)
                self.assertEqual(check['miete_pot_quelle'], 'Automatische regionale Mietrecherche')
                self.assertIsNone(check['objekt_id'])

                duplicate = db_store.create_schnellcheck('https://example.org/anzeige/9')
                self.assertTrue(duplicate['existing'])

                updated = db_store.update_schnellcheck(
                    check['public_id'], {'kaltmiete_pot': '780', 'miete_pot_quelle': 'Kasseler Mietspiegel, Mittelwert'}, 0)
                self.assertEqual(updated['kaltmiete_pot'], 780)
                self.assertEqual(updated['revision'], 1)
                with self.assertRaises(db_store.RevisionConflict):
                    db_store.update_schnellcheck(check['public_id'], {'kaltmiete_pot': 800}, 0)
                with self.assertRaises(ValueError):
                    db_store.update_schnellcheck(check['public_id'], {'unbekanntes_feld': 1}, 1)

                uebersicht = db_store.schnellcheck_uebersicht(check['public_id'])
                self.assertFalse(uebersicht['existing'])
                linked = db_store.update_schnellcheck(check['public_id'], {'stadtteil': 'Wehlheiden'}, 2)
                self.assertIsNotNone(linked['objekt_id'])
                again = db_store.schnellcheck_uebersicht(check['public_id'])
                self.assertTrue(again['existing'])
                state = db_store.get_object(uebersicht['id'])['state']
                self.assertEqual(state['kaltmiete'], '780.0')

                rows = db_store.schnellcheck_rows()
                self.assertEqual(len(rows), 1)
                self.assertTrue(rows[0]['objekt_pfad'])
                result = db_store.delete_schnellcheck(check['public_id'], 3)
                self.assertTrue(result['deleted'])
                self.assertEqual(db_store.schnellcheck_rows(), [])

            with patch.object(db_store, 'BASE', base), patch.object(db_store, 'DB_PATH', db_path), \
                    patch.object(db_store, 'validate_url', side_effect=lambda url: url), \
                    patch.object(db_store, 'fetch_public', side_effect=ListingError('Anzeige nicht abrufbar (HTTP 403)')):
                blocked = db_store.create_schnellcheck('https://example.org/anzeige/10')
                self.assertIn('blockiert', blocked['status'])
                self.assertIsNone(blocked['kaufpreis'])

    def test_create_schnellcheck_uses_certificate_address_and_saves_provenance(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            base = Path(tmp)
            (base / 'objekte' / '_VORLAGE').mkdir(parents=True)
            shutil.copy2(ROOT / 'objekte' / '_VORLAGE' / 'Objektname_Übersicht.html',
                         base / 'objekte' / '_VORLAGE' / 'Objektname_Übersicht.html')
            db_path = base / 'immo_datenbank.db'
            shutil.copy2(ROOT / 'immo_datenbank.db', db_path)
            pdf_source = 'Energieausweis: https://mms.immowelt.de/energy.pdf'
            patches = (
                patch.object(db_store, 'BASE', base),
                patch.object(db_store, 'DB_PATH', db_path),
                patch.object(db_store, 'validate_url', side_effect=lambda url: url),
                patch.object(db_store, 'fetch_public', return_value=(
                    'https://example.org/anzeige/11', SC_PAGE, 'text/html; charset=utf-8')),
                patch.object(db_store, 'extract_energy_certificate_facts', return_value={
                    'strasse': 'Franzgraben', 'hausnummer': '35-37', 'plz': '34125',
                    'ort': 'Kassel', 'energy_certificate_address': 'Franzgraben 35-37, 34125 Kassel',
                    'energy_certificate_source': pdf_source,
                }),
                patch.object(db_store, 'research_potential_rent', return_value={
                    'kaltmiete_pot': 275.39, 'miete_pot_quelle': 'Kasseler Mietspiegel 2026: Wohnlage einfach'}),
            )
            with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
                with db_store.connection() as conn:
                    conn.execute('DELETE FROM schnellcheck')
                    conn.commit()
                check = db_store.create_schnellcheck('https://example.org/anzeige/11')
            self.assertEqual(check['strasse'], 'Franzgraben')
            self.assertEqual(check['hausnummer'], '35-37')
            self.assertEqual(check['plz'], '34125')
            self.assertEqual(check['kaltmiete_pot'], 275.39)
            self.assertIn('laut Energieausweis: Franzgraben 35-37, 34125 Kassel', check['miete_pot_quelle'])
            self.assertIn(pdf_source, check['miete_pot_quelle'])


if __name__ == '__main__':
    unittest.main()
