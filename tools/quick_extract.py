"""Conservative, deterministic extraction. Source text is data, never instructions."""
from __future__ import annotations
import html
import re
from html.parser import HTMLParser
from urllib.parse import urlsplit, parse_qs, unquote
from listing_import import ListingParser, _nodes, _number
from quick_store import now

# Field names, units and explicit German labels. No inference from nearby numbers.
SPECS = {
 'title': ('', ['Titel']), 'locality': ('', ['Ort', 'Stadt']), 'postal_code': ('', ['PLZ']),
 'district': ('', ['Stadtteil']), 'address': ('', ['Adresse']),
 'price': ('EUR', ['Kaufpreis']), 'area': ('m²', ['Wohnfläche']),
 'land_area': ('m²', ['Grundstücksfläche']), 'rooms': ('', ['Zimmer']),
 'units': ('', ['Wohneinheiten']), 'property_type': ('', ['Objektart']),
 'year_built': ('Jahr', ['Baujahr']), 'condition': ('', ['Zustand']),
 'rental_status': ('', ['Vermietungsstatus']),
 'cold_rent': ('EUR/Monat', ['Monatliche Kaltmiete', 'Kaltmiete monatlich', 'Nettokaltmiete', 'Ist-Kaltmiete', 'Kaltmiete']),
 'annual_cold_rent': ('EUR/Jahr', ['Jahreskaltmiete', 'Jahresnettokaltmiete']),
 'warm_rent': ('EUR/Monat', ['Warmmiete']), 'house_fee': ('EUR/Monat', ['Hausgeld']),
 'non_recoverable': ('EUR/Monat', ['Nicht umlagefähige Kosten', 'Hausgeld nicht umlagefähig']),
 'reserve_contribution': ('EUR/Monat', ['Rücklagenbeitrag']), 'reserve': ('EUR', ['Rücklage']),
 'commission': ('%', ['Käuferprovision']), 'acquisition_costs': ('EUR', ['Weitere Erwerbskosten']),
 'energy': ('kWh/(m²·a)', ['Energiekennwert', 'Endenergiebedarf', 'Endenergieverbrauch']),
 'energy_class': ('', ['Energieklasse']), 'heating': ('', ['Heizung']),
 'other': ('', ['Weitere Angaben']),
}
NUMERIC = {key for key, (unit, _) in SPECS.items() if unit} | {'rooms','units'}


class TextParser(HTMLParser):
    def __init__(self, links=False):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skip = 0
        self.links = links

    def handle_starttag(self, tag, attrs):
        if tag in ('script','style'):
            self.skip += 1
        if self.skip:
            return
        if tag in ('br','p','div','li','tr','section','article','h1','h2','dt','dd'):
            self.parts.append('\n')
        if tag == 'a' and self.links:
            href = dict(attrs).get('href','')
            self.parts.append('\n' + href + '\n')

    def handle_endtag(self, tag):
        if tag in ('script','style'):
            self.skip = max(0, self.skip - 1)
        elif tag in ('p','div','li','tr','section','article','h1','h2','dt','dd'):
            self.parts.append('\n')

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def plain(value, links=False):
    parser = TextParser(links)
    parser.feed(value)
    return html.unescape(''.join(parser.parts))


def normalize_url(value):
    """Recognize portal IDs; strip tracking. Nested targets decoded, never executed."""
    value = html.unescape(value).strip().rstrip('.,);')
    for _ in range(3):
        parsed = urlsplit(value)
        if parsed.scheme not in ('http','https') or parsed.username or parsed.password or parsed.port not in (None,80,443):
            return None
        host = (parsed.hostname or '').lower().rstrip('.')
        path = unquote(parsed.path)
        patterns = (
            ('immobilienscout24.de', r'/expose/(\d+)', 'ImmobilienScout24', 'https://www.immobilienscout24.de/expose/'),
            ('immowelt.de', r'/(?:expose|exposedetail)/([a-zA-Z0-9-]+)', 'Immowelt', 'https://www.immowelt.de/expose/'),
            ('kleinanzeigen.de', r'/s-anzeige/[^/]+/(\d+)(?:-\d+-\d+)?', 'Kleinanzeigen', 'https://www.kleinanzeigen.de/s-anzeige/angebot/'),
            ('ohne-makler.net', r'/(?:immobilie|expose)/(\d+)', 'Ohne Makler', 'https://www.ohne-makler.net/immobilie/'),
        )
        for domain, pattern, portal, prefix in patterns:
            match = re.fullmatch(pattern + r'/?', path, re.I)
            if (host == domain or host.endswith('.' + domain)) and match:
                pid = match[1].lower()
                return {'url': prefix + pid, 'portal': portal, 'portal_id': pid}
        query = parse_qs(parsed.query)
        target = next((query[k][0] for k in ('url','target','redirect','redirectUrl','u') if query.get(k)), None)
        if not target:
            return None
        value = target
    return None


def field(value=None, unit='', source=None, evidence=None, origin=None, basis=None, retrieved_at=None):
    return {'value': value, 'unit': unit, 'origin': origin or ('BELEGT' if value is not None else 'UNBEKANNT'),
            'source': source, 'retrieved_at': retrieved_at or now(), 'evidence': evidence, 'basis': basis}


def label_fields(text, source, retrieved_at=None):
    values = {}
    for key, (unit, labels) in SPECS.items():
        label = '|'.join(re.escape(x) for x in labels)
        matches = list(re.finditer(r'(?im)^\s*(?:' + label + r')[ \t]*(?:[:=][ \t]*|\n[ \t]*)([^\n]+)', text))
        for match in matches:
            raw = match[1].strip()
            # Period and unit conflicts are rejected rather than quietly reinterpreted.
            if key in ('cold_rent','warm_rent','house_fee','non_recoverable','reserve_contribution') and re.search(r'jahr|jähr|p\.?\s*a\.?|/a\b', raw, re.I):
                continue
            if key in ('cold_rent','warm_rent') and re.search(r'/\s*m[²2]|pro\s*m[²2]|(?:je|pro)\s+(?:Wohnung|Einheit|Wohneinheit)', raw, re.I):
                continue
            if key in NUMERIC and re.search(r'\$|USD|CHF|GBP', raw, re.I):
                continue
            if key == 'price' and re.search(r'/\s*m|pro\s*m', raw, re.I):
                continue
            if key in NUMERIC:
                if raw.startswith('-'):
                    continue
                val = _number(raw)
                if val is None or (key in ('price','area','land_area') and val <= 0):
                    continue
            else:
                val = raw[:1000]
            values.setdefault(key, []).append(field(val, unit, source, match[0].strip(), retrieved_at=retrieved_at))
    return values


def extract_page(page, source):
    parser = ListingParser()
    parser.feed(page.decode('utf-8', errors='replace'))
    nodes = list(_nodes(parser.jsonld))
    listing_node = next((n for n in nodes if str(n.get('@type','')).lower() == 'realestatelisting'), {})
    node = next((n for n in nodes if str(n.get('@type','')).lower() in ('house','apartment','residence','singlefamilyresidence')), listing_node)
    retrieved = now()
    text = plain(page.decode('utf-8', errors='replace')) + '\n' + str(node.get('description') or '')
    values = label_fields(text, source, retrieved)

    def add(key, value, evidence):
        if value not in (None,''):
            values.setdefault(key, []).append(field(value, SPECS[key][0], source, evidence, retrieved_at=retrieved))

    add('title', node.get('name') or parser.meta.get('og:title') or parser.title or None, 'JSON-LD.name / og:title / title')
    offer = node.get('offers') or listing_node.get('offers') or {}
    if isinstance(offer, list):
        offer = offer[0] if len(offer) == 1 else {}
    if isinstance(offer, dict) and offer.get('priceCurrency') == 'EUR' and not offer.get('priceSpecification'):
        price = _number(offer.get('price'))
        if price and price > 0:
            add('price', price, 'JSON-LD.offers.price (EUR, Gesamtpreis)')
    size = node.get('floorSize')
    if isinstance(size, dict) and (size.get('unitCode') or size.get('unitText')) in ('MTK','SQM','m2','m²'):
        area = _number(size)
        if area and area > 0:
            add('area', area, 'JSON-LD.floorSize.value (Wohnfläche, m²)')
    add('rooms', _number(node.get('numberOfRooms')), 'JSON-LD.numberOfRooms')
    address = node.get('address') or {}
    if isinstance(address, dict):
        for key, prop in (('postal_code','postalCode'),('locality','addressLocality'),('address','streetAddress')):
            add(key, address.get(prop), 'JSON-LD.address.' + prop)
    return values


def merge_fields(*sources):
    result, conflicts = {}, []
    for key, (unit, _) in SPECS.items():
        candidates = [item for source in sources for item in source.get(key, [])]
        unique = {str(item['value']) for item in candidates}
        if len(unique) > 1:
            conflicts.append({'field': key, 'candidates': candidates})
            result[key] = field(unit=unit, evidence='Widerspruch – Wert nicht verwendet')
        else:
            result[key] = dict(candidates[0]) if candidates else field(unit=unit)
        result[key]['candidates'] = candidates
    if result['annual_cold_rent']['value'] is not None:
        annual = result['annual_cold_rent']
        derived = annual['value'] / 12
        monthly = result['cold_rent']
        if monthly['value'] is None and not monthly['candidates']:
            result['cold_rent'] = field(derived, 'EUR/Monat', annual['source'], annual['evidence'], 'ABGELEITET',
                                        'Belegte Jahreskaltmiete / 12', annual['retrieved_at'])
        elif monthly['value'] is not None and abs(monthly['value'] - derived) > .01:
            conflicts.append({'field':'cold_rent', 'candidates':[monthly, annual]})
            result['cold_rent'] = field(unit='EUR/Monat', evidence='Jahres-/Monatsmiete widersprüchlich')
    return result, conflicts


def message_entries(message):
    text = message.get('text') or plain(message.get('html',''), links=True)
    if message.get('text') and message.get('html'):
        # HTML can contain additional offers. Identical URLs are deduplicated below.
        text += '\n' + plain(message['html'], links=True)
    matches = list(re.finditer(r'https?://[^\s<>"\']+', text))
    entries = {}
    for index, match in enumerate(matches):
        try:
            identity = normalize_url(match[0])
        except ValueError:
            continue
        if not identity:
            continue
        end = matches[index+1].start() if index+1 < len(matches) else len(text)
        # Assign only the block following this offer's link. Never copy one offer's
        # rent/area to the other offers. Single-offer preamble is also eligible.
        start = 0 if len(matches) == 1 else match.end()
        evidence = label_fields(text[start:end], 'message:' + message['id'], now())
        if identity['url'] in entries:
            previous = entries[identity['url']]['fields']
            for key, candidates in evidence.items():
                previous.setdefault(key, []).extend(candidates)
        else:
            entries[identity['url']] = {**identity, 'fields': evidence}
    return list(entries.values())
