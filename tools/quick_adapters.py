"""Swappable mail, listing, rent-reference and notification adapters.

Live adapters are explicitly disabled by default. No AI or paid service is used.
"""
from __future__ import annotations
import base64
import email.policy
import json
import re
import socket
import statistics
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from email.parser import BytesParser
from pathlib import Path
from typing import Protocol
from listing_import import fetch_public, ListingError
from quick_extract import normalize_url

BASE = Path(__file__).resolve().parents[1]
GMAIL_SCOPE = 'https://www.googleapis.com/auth/gmail.readonly'


def external_secret(path):
    resolved = Path(path).expanduser().resolve()
    if resolved.is_relative_to(BASE):
        raise ValueError('Zugangsdaten müssen außerhalb des ausgelieferten Projektverzeichnisses liegen')
    return resolved


def timestamp(value):
    parsed = datetime.fromisoformat(str(value).replace('Z','+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Startzeitpunkt benötigt eine Zeitzone')
    return parsed.timestamp()


def parse_eml(raw, message_id=None, received_at=None, is_test=True):
    msg = BytesParser(policy=email.policy.default).parsebytes(raw)
    texts, htmls = [], []
    for part in msg.walk():
        if part.is_multipart() or part.get_content_disposition() == 'attachment':
            continue
        if part.get_content_type() in ('text/plain','text/html'):
            content = part.get_content()
            (htmls if part.get_content_type() == 'text/html' else texts).append(content)
    try:
        date = email.utils.parsedate_to_datetime(msg['Date']) if msg.get('Date') else datetime.now(timezone.utc)
    except (ValueError, TypeError):
        date = datetime.now(timezone.utc)
    if date.tzinfo is None:
        date = date.replace(tzinfo=timezone.utc)
    return {'id': message_id or str(msg.get('Message-ID') or __import__('hashlib').sha256(raw).hexdigest()),
            'received_at': received_at or date.astimezone(timezone.utc).isoformat(),
            'sender': str(msg.get('From','')), 'subject': str(msg.get('Subject','')),
            'text':'\n'.join(texts), 'html':'\n'.join(htmls), 'is_test':is_test}


class MailAdapter(Protocol):
    name: str
    status: str
    def messages(self, cursor: str | None, known_ids=None): ...


class LocalMailAdapter:
    name = 'local'
    status = 'Lokaler Testimport'

    def __init__(self, directory, filters=None):
        self.directory = Path(directory)
        self.filters = filters or {}

    def messages(self, cursor=None, known_ids=None):
        for path in sorted(self.directory.glob('*.eml')):
            if path.stat().st_size > 2_000_000:
                raise ValueError('EML-Testdatei zu groß')
            msg = parse_eml(path.read_bytes())
            if msg['id'] in (known_ids or set()):
                continue
            if self.filters.get('start_at') and timestamp(msg['received_at']) < timestamp(self.filters['start_at']):
                continue
            if relevant(msg, self.filters):
                yield msg


def relevant(msg, filters):
    address = email.utils.parseaddr(msg['sender'])[1].lower()
    senders = filters.get('senders', [])
    subjects = filters.get('subjects', [])
    return (not senders or address in [s.lower() for s in senders]) and (not subjects or any(s.lower() in msg['subject'].lower() for s in subjects))


class GmailAdapter:
    name = 'gmail'
    def __init__(self, config=None):
        self.config = config or {}
        self.enabled = self.config.get('enabled') is True
        self.status = 'Nicht verbunden'
        self.credentials = None
        if self.enabled:
            if not self.config.get('start_at') or not self.config.get('query'):
                raise ValueError('Gmail benötigt Startzeitpunkt und gezielte Suchabfrage')
            timestamp(self.config['start_at'])
            token = external_secret(self.config['token_path'])
            if token.exists():
                from google.oauth2.credentials import Credentials
                if set(json.loads(token.read_text()).get('scopes',[])) != {GMAIL_SCOPE}:
                    raise ValueError('OAuth-Token muss ausschließlich gmail.readonly verwenden')
                self.credentials = Credentials.from_authorized_user_file(str(token), [GMAIL_SCOPE])
                self.token_path = token
                self.status = 'Konfiguriert – Liveprüfung ausstehend'

    def _get(self, endpoint, params):
        if not self.credentials.valid:
            from google.auth.transport.requests import Request
            request = Request()
            self.credentials.refresh(lambda *args, **kwargs: request(*args, **{**kwargs,'timeout':20}))
            self.token_path.write_text(self.credentials.to_json())
            self.token_path.chmod(0o600)
        url = 'https://gmail.googleapis.com/gmail/v1/users/me/' + endpoint + '?' + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={'Authorization':'Bearer ' + self.credentials.token})
        try:
            with urllib.request.urlopen(req, timeout=20) as res:
                return json.loads(res.read(5_000_000))
        except (urllib.error.URLError, ValueError):
            raise RuntimeError('Gmail-Abruf fehlgeschlagen; OAuth/Netz prüfen') from None

    def messages(self, cursor=None, known_ids=None):
        if self.credentials is None:
            return
        start = timestamp(self.config['start_at'])
        # One-day overlap prevents missing equally dated messages. Durable message IDs
        # suppress reprocessing. Checkpoint advances only with committed ingestion.
        if cursor:
            start = max(start, timestamp(cursor) - 86400)
        query = self.config['query'] + ' after:' + str(int(start))
        if self.config.get('senders'):
            query += ' {' + ' '.join('from:' + s for s in self.config['senders']) + '}'
        token = None
        while True:
            params = {'q':query, 'maxResults':100, 'includeSpamTrash':'false'}
            if token:
                params['pageToken'] = token
            batch = self._get('messages', params)
            for item in batch.get('messages', []):
                if item['id'] in (known_ids or set()):
                    continue
                raw = self._get('messages/' + item['id'], {'format':'raw'})
                received = datetime.fromtimestamp(int(raw['internalDate']) / 1000, timezone.utc).isoformat()
                if timestamp(received) < timestamp(self.config['start_at']):
                    continue
                msg = parse_eml(base64.urlsafe_b64decode(raw['raw'] + '==='), item['id'], received, False)
                if relevant(msg, self.config):
                    yield msg
            token = batch.get('nextPageToken')
            if not token:
                break


def authorize_gmail(config):
    """Explicit CLI action only; never triggered by opening the dashboard."""
    from google_auth_oauthlib.flow import InstalledAppFlow
    client = external_secret(config['client_path'])
    token = external_secret(config['token_path'])
    flow = InstalledAppFlow.from_client_secrets_file(str(client), [GMAIL_SCOPE])
    credentials = flow.run_local_server(port=0, access_type='offline', prompt='consent')
    token.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    token.write_text(credentials.to_json())
    token.chmod(0o600)


class ListingAdapter(Protocol):
    def fetch(self, url: str): ...


class PublicListingAdapter:
    def fetch(self, url):
        final, page, content_type = fetch_public(url)
        if 'html' not in content_type.lower():
            raise ListingError('Anzeige liefert kein HTML')
        return final, page


class LocalListingAdapter:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.manifest = json.loads((self.directory / 'listings.json').read_text())

    def fetch(self, url):
        item = self.manifest.get(url)
        if not item or 'error' in item:
            raise ListingError('TEST: Anzeigenabruf blockiert (HTTP 403)')
        file = (self.directory / item['file']).resolve()
        if not file.is_relative_to(self.directory.resolve()):
            raise ValueError('Fixture-Pfad außerhalb des Testverzeichnisses')
        return url, file.read_bytes()


class RentReferenceAdapter(Protocol):
    def estimate(self, fields: dict): ...


class ScoutRentAdapter:
    status = 'Mietreferenz fehlt – ImmobilienScout24-Zugang nicht verbunden'
    def estimate(self, fields):
        return None


class LocalRentAdapter:
    status = 'ImmobilienScout24-Testreferenzen (kein Livezugriff)'
    def __init__(self, path):
        self.references = json.loads(Path(path).read_text())

    def estimate(self, fields):
        def val(key):
            return fields[key]['value']
        if not val('postal_code') or not val('area') or fields['area']['origin'] != 'BELEGT':
            return None
        selected, seen = [], set()
        for item in self.references:
            identity = normalize_url(item.get('url',''))
            if not identity or identity['portal'] != 'ImmobilienScout24' or identity['url'] in seen:
                continue
            if str(item.get('postal_code')) != str(val('postal_code')) or item.get('spatial_level') != 'PLZ':
                continue
            if val('property_type') and item.get('property_type') != val('property_type'):
                continue
            if any(val(k) and item.get(k) != val(k) for k in ('district','condition')):
                continue
            area, rent = item.get('area'), item.get('cold_rent')
            if not isinstance(area, (int,float)) or not isinstance(rent, (int,float)) or area <= 0 or rent <= 0:
                continue
            if not .75 * val('area') <= area <= 1.25 * val('area') or not item.get('evidence') or not item.get('as_of') or not item.get('retrieved_at'):
                continue
            seen.add(identity['url'])
            selected.append({**item, 'url':identity['url'], 'eur_m2':rent / area})
        if not selected:
            return None
        rate = statistics.median(item['eur_m2'] for item in selected)
        return {'origin':'ABGELEITET', 'is_test':True, 'eur_m2':rate, 'monthly':rate * val('area'),
                'method':'Median der Nettokalt-Angebotsmieten je m² × belegte Wohnfläche; kein Mietspiegel',
                'selection':'Gleiche PLZ, Objektart, vorhandener Stadtteil/Zustand; Fläche ±25 %; URL-Duplikate entfernt',
                'sample_size':len(selected), 'postal_code':val('postal_code'), 'spatial_level':'PLZ', 'sources':selected}


class UncertainDelivery(Exception):
    pass


class RateLimited(Exception):
    def __init__(self, seconds):
        self.seconds = max(1, min(int(seconds), 3600))


class NotificationAdapter(Protocol):
    status: str
    def send(self, message: str, pdf: Path, key: str): ...


class DisabledTelegramAdapter:
    status = 'Telegram nicht verbunden'
    def send(self, message, pdf, key):
        return {'status':'nicht_verbunden', 'receipt':None}


class LocalNotificationAdapter:
    status = 'Lokaler Versandtest – kein Telegram-Versand'
    def __init__(self, fail=False):
        self.fail = fail
    def send(self, message, pdf, key):
        if self.fail:
            raise RuntimeError('TEST: Versandfehler')
        if not pdf.is_file():
            raise ValueError('PDF fehlt')
        return {'status':'lokal_getestet', 'receipt':{'adapter':'local', 'test':True, 'key':key}}


class TelegramAdapter:
    status = 'Konfiguriert – Liveprüfung ausstehend'
    def __init__(self, config):
        if config.get('enabled') is not True:
            raise ValueError('Telegram-Versandmodus nicht ausdrücklich aktiviert')
        secrets = json.loads(external_secret(config['secret_path']).read_text())
        self.token, self.chat_id = secrets['bot_token'], str(secrets['allowed_chat_id'])
        if not re.fullmatch(r'\d+:[A-Za-z0-9_-]+', self.token) or not re.fullmatch(r'-?\d+', self.chat_id):
            raise ValueError('Telegram-Zugangsdaten ungültig')

    def send(self, message, pdf, key):
        # Bot API does not guarantee exactly-once. A timeout or lost response is
        # recorded as uncertain and must be checked by the operator.
        boundary = 'immo' + key.replace('-','')
        chunks = []
        for name, value in (('chat_id', self.chat_id), ('caption', message[:1024])):
            chunks.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
        chunks += [f'--{boundary}\r\nContent-Disposition: form-data; name="document"; filename="schnellanalyse.pdf"\r\nContent-Type: application/pdf\r\n\r\n'.encode(), pdf.read_bytes(), f'\r\n--{boundary}--\r\n'.encode()]
        request = urllib.request.Request('https://api.telegram.org/bot' + self.token + '/sendDocument',
                                         data=b''.join(chunks), headers={'Content-Type':'multipart/form-data; boundary=' + boundary})
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                result = json.loads(response.read(1_000_000))
        except urllib.error.HTTPError as error:
            if error.code == 429:
                try:
                    raise RateLimited(json.loads(error.read()).get('parameters',{}).get('retry_after',30))
                except (ValueError, KeyError):
                    raise RateLimited(30) from None
            if error.code >= 500:
                raise UncertainDelivery('Telegram-Serverantwort unklar') from None
            raise RuntimeError('Telegram lehnt Versand ab; Konfiguration prüfen') from None
        except (urllib.error.URLError, socket.timeout, TimeoutError, ValueError):
            raise UncertainDelivery('Telegram-Zustellung nach Verbindungsfehler unklar') from None
        if result.get('ok') is not True:
            raise UncertainDelivery('Telegram-Bestätigung fehlt')
        confirmation = result['result']
        return {'status':'versendet', 'receipt':{'message_id':confirmation['message_id'], 'date':confirmation['date'], 'chat_id':str(confirmation['chat']['id'])}}
