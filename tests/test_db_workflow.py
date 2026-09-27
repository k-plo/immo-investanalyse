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
from listing_import import extract_listing, validate_url, ListingError


PAGE = b'''<html><head><title>Haus in Neustadt</title>
<meta property="og:image" content="https://bilder.example.org/haus.png">
<script type="application/ld+json">{"@type":"House","name":"Haus in Neustadt","address":{"streetAddress":"Hauptstr. 1","postalCode":"12345","addressLocality":"Neustadt"},"floorSize":{"value":120},"numberOfRooms":4,"offers":{"price":"249.000"}}</script>
</head><body></body></html>'''
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/l0cAAAAASUVORK5CYII=')


class DbWorkflowTest(unittest.TestCase):
    def test_listing_parser_and_private_url_rejection(self):
        item = extract_listing(PAGE, 'https://example.org/anzeige/1')
        self.assertEqual(item['price'], 249000)
        self.assertEqual(item['area'], 120)
        self.assertEqual(item['locality'], 'Neustadt')
        with self.assertRaises(ListingError):
            validate_url('http://127.0.0.1:8000/private')

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


if __name__ == '__main__':
    unittest.main()
