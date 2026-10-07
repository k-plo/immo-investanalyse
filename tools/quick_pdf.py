"""Dependency-free two-page PDF from the stored result; no recalculation.

PDF standard fonts with WinAnsiEncoding support German text and euro amounts.
Long evidence excerpts are abbreviated here; the full provenance remains in SQLite
and the dashboard. Source URLs are clickable link annotations.
"""
from __future__ import annotations
import os
import textwrap
from pathlib import Path
from quick_extract import SPECS


def fmt(value, unit=''):
    if value is None:
        return 'nicht berechenbar'
    if isinstance(value, (int,float)):
        text = str(int(value)) if unit == 'Jahr' else f'{value:,.2f}'.replace(',', 'X').replace('.', ',').replace('X','.')
    else:
        text = str(value)
    return text + (' ' + unit if unit else '')


METRICS = (
 ('kaufpreis','Kaufpreis','€'), ('kp_pro_m2','Kaufpreis je m²','€/m²'),
 ('kaltmiete','Kaltmiete monatlich','€/Monat'), ('jahresKaltmiete','Kaltmiete jährlich','€/Jahr'),
 ('bruttoRendite','Bruttomietrendite','%'), ('kaufpreisfaktor','Kaufpreisfaktor',''),
 ('ek','Eigenkapital','€'), ('ekProzent','EK-Anteil','%'), ('darlehen','Darlehen','€'),
 ('zins','Sollzins','% p.a.'), ('tilgung','Anfängliche Tilgung','% p.a.'),
 ('zinsMonat','Zins monatlich','€'), ('tilgungMonat','Tilgung monatlich','€'),
 ('rateMonat','Rate monatlich','€'), ('pauschaleKostenMonat','20-%-Kostenpauschale','€/Monat'),
 ('cashflowMonat','Cashflow vor Steuern','€/Monat'), ('cashflowJahr','Cashflow vor Steuern jährlich','€/Jahr'),
)
FIELD_LABELS = {'listing_portal':'Portal', 'listing_portal_id':'Anzeigen-ID', 'listing_url':'Anzeigenlink',
                'profile_zins':'Profil-Sollzins', 'profile_tilgung':'Profil-Tilgung', 'profile_ek':'Profil-Eigenkapital',
                'profile_ekAnteil':'Profil-EK-Anteil', 'market_cold_rent':'Geschätzte Marktkaltmiete',
                'market_eur_m2':'Marktmietreferenz je m²', 'model_cost_percent':'Kostenpauschale (Modell)',
                'model_price_factor':'Verhandlungsszenario (Modellfaktor)'}


def notification_preview(result):
    fields, calc = result['fields'], result['calculation']
    base, scenario = calc['basis'], calc['szenario']
    val = lambda key: fields[key]['value']
    return '\n'.join([
        ('TEST · ' if result.get('is_test') else '') + str(val('title') or 'Immobilienangebot')[:70] + ' · ' + str(val('locality') or 'Ort unbekannt')[:40],
        f"Kaufpreis {fmt(base['kaufpreis'],'€')} · {fmt(val('area'),'m²')}",
        f"{'Geschätzte Marktkaltmiete (Marktmietszenario)' if result['rent_basis']=='market' else result['rent_label']}: {fmt(base['kaltmiete'],'€/Monat')}",
        f"Brutto {fmt(base['bruttoRendite'],'%')} · Faktor {fmt(base['kaufpreisfaktor'])} · CF {fmt(base['cashflowMonat'],'€/Monat')}",
        'Bewertung: ' + calc['status']['basis']['gesamt'],
        f"-10 %: {fmt(scenario['kaufpreis'],'€')} · Brutto {fmt(scenario['bruttoRendite'],'%')} · Faktor {fmt(scenario['kaufpreisfaktor'])} · CF {fmt(scenario['cashflowMonat'],'€/Monat')} · {calc['status']['szenario']['gesamt']}",
        'Offen: ' + (', '.join(result['missing']) or 'Unterlagenprüfung'),
        result['url'],
    ])


def _literal(value):
    # Latin-1 byte container, WinAnsi maps cp1252 glyphs. Escape PDF syntax.
    value = str(value).replace('−','-').replace('×','x').replace('→','->')
    return value.encode('cp1252',errors='replace').replace(b'\\',b'\\\\').replace(b'(',b'\\(').replace(b')',b'\\)').replace(b'\r',b' ').replace(b'\n',b' ')


class PDF:
    def __init__(self):
        self.objects = [b'',b'']
        self.pages = []
        self.font = self.add(b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>')
        self.bold = self.add(b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>')

    def add(self, data):
        self.objects.append(data)
        return len(self.objects)

    def page(self, lines):
        commands, annotations = [], []
        y = 803
        headings = sum(1 for _, heading, _ in lines if heading)
        line_height = min(13, (760 - headings * 8) / max(1,len(lines)))
        for text, heading, url in lines:
            size = 13 if heading else min(9,line_height - 2)
            height = line_height + 8 if heading else line_height
            if y < 40:
                raise ValueError('PDF-Inhalt überschreitet zwei Seiten')
            if '\t' in text:
                for x,cell in zip((42,278,430),text.split('\t')):
                    commands.append(f'BT /F1 {size} Tf 0.08 0.18 0.22 rg {x} {y} Td ('.encode() + _literal(cell) + b') Tj ET\n')
            else:
                commands.append(f'BT /F{2 if heading else 1} {size} Tf 0.08 0.18 0.22 rg 42 {y} Td ('.encode() + _literal(text) + b') Tj ET\n')
            if url:
                annotations.append(self.add(f'<< /Type /Annot /Subtype /Link /Rect [42 {y-3} 552 {y+11}] /Border [0 0 0] /A << /S /URI /URI ('.encode() + _literal(url) + b') >> >>'))
            y -= height
        stream = b''.join(commands)
        content = self.add(f'<< /Length {len(stream)} >>\nstream\n'.encode() + stream + b'endstream')
        annots = ' '.join(f'{item} 0 R' for item in annotations)
        page = self.add(f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 {self.font} 0 R /F2 {self.bold} 0 R >> >> /Contents {content} 0 R /Annots [{annots}] >>'.encode())
        self.pages.append(page)

    def write(self, path):
        self.objects[0] = b'<< /Type /Catalog /Pages 2 0 R >>'
        kids = ' '.join(f'{p} 0 R' for p in self.pages)
        self.objects[1] = f'<< /Type /Pages /Kids [{kids}] /Count {len(self.pages)} >>'.encode()
        data, offsets = bytearray(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n'), [0]
        for index, obj in enumerate(self.objects,1):
            offsets.append(len(data))
            data += f'{index} 0 obj\n'.encode() + obj + b'\nendobj\n'
        xref = len(data)
        data += f'xref\n0 {len(offsets)}\n0000000000 65535 f \n'.encode()
        for offset in offsets[1:]:
            data += f'{offset:010d} 00000 n \n'.encode()
        data += f'trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode()
        path = Path(path)
        temporary = path.with_suffix('.pdf.tmp')
        with temporary.open('wb') as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)


def render_pdf(result, path):
    pages = [[],[]]
    def add(page, text, heading=False, url=None, width=104, limit=None):
        lines = textwrap.wrap(str(text), width=width) or ['']
        if limit and len(lines) > limit:
            lines = lines[:limit]
            lines[-1] = lines[-1][:width-4] + ' ...'
        pages[page].extend((line, heading if i == 0 else False, url) for i,line in enumerate(lines))
    fields, calc = result['fields'], result['calculation']
    value = lambda key: fields[key]['value']
    add(0, 'Schnellanalyse · Agent' + (' · TESTDATEN' if result['is_test'] else ''), True)
    add(0, str(value('title') or 'Angebot ohne Titel')[:120], limit=2)
    add(0, f"{value('address') or ''} · {value('postal_code') or ''} {value('locality') or 'Ort unbekannt'} · {fmt(value('area'),'m²')}", limit=2)
    add(0, f"{result['portal']} · Anzeige {result['portal_id']} · Revision {result['revision']} · Analyse {result['analyzed_at']}")
    add(0, 'Anzeige öffnen: ' + result['url'], url=result['url'], limit=2)
    add(0, result['rent_label'], True)
    add(0, 'Basis und Kaufpreis minus 10 %', True)
    pages[0].append(('Kennzahl\tBasis\t-10 %',False,None))
    for key,label,unit in METRICS:
        pages[0].append((label + '\t' + fmt(calc['basis'].get(key),unit) + '\t' + fmt(calc['szenario'].get(key),unit),False,None))
    for variant in ('basis','szenario'):
        status = calc['status'][variant]
        criterion = lambda v: 'nicht berechenbar' if v is None else 'erfüllt' if v else 'nicht erfüllt'
        add(0, f"{variant}: {status['gesamt']} · Rendite {criterion(status['bruttoRendite'])} · Faktor {criterion(status['kaufpreisfaktor'])} · CF {criterion(status['cashflow'])}", limit=2)
    add(0, 'Renditeänderung: ' + fmt(calc['vergleich']['bruttoRendite']['absolut'],'Prozentpunkte'))
    add(0, 'Ziele: Rendite > 5 %, Faktor < 20, Cashflow > 0 €. Prüfung vor Rundung.')
    add(0, 'Rendite und Faktor sind mathematisch abhängig; keine unabhängigen Qualitätsbelege.')
    add(0, result['assumptions'], limit=3)
    add(0, 'Modellrechnung vor Steuern; keine vollständige Wirtschaftlichkeits- oder Unterlagenprüfung.')
    add(1, 'Quellen, Datenqualität und offene Angaben', True)
    add(1, 'Profil: ' + str(result['profile_name'] or 'fehlt') + ' · Finanzierung als ausdrücklich konfigurierte Modellannahme.')
    add(1, 'BELEGT = Anzeigen-/E-Mail-Angabe, noch keine Unterlagenbestätigung.')
    add(1, 'Alle verwendeten Felder; Belegauszüge gekürzt. Vollständige Herkunft und Alternativen im Dashboard.')
    for key, data in fields.items():
        if data['value'] is None:
            continue
        label = SPECS[key][1][0] if key in SPECS else FIELD_LABELS.get(key,key)
        add(1, f"{label}: {fmt(data['value'],data['unit'])} · {data['origin']} · {data['source'] or ''}"[:155], width=110, limit=1, url=data['source'] if str(data['source']).startswith('https://') else None)
    reference = result['rent_reference']
    if reference:
        add(1, 'Geschätzte Marktkaltmiete: Angebotsmieten, kein Mietspiegel', True)
        add(1, f"PLZ {reference['postal_code']} · n={reference['sample_size']} · {fmt(reference['eur_m2'],'€/m²')} · {reference['method']}", limit=2)
        add(1, reference['selection'], limit=2)
        for source in reference['sources'][:3]:
            add(1, f"{source['url']} · Stand {source['as_of']} · Abruf {source['retrieved_at']}", url=source['url'], limit=2)
        if len(reference['sources']) > 3:
            add(1, 'Weitere Quellen im Dashboard dokumentiert.')
    else:
        add(1, 'Mietreferenz: ' + result['rent_reference_status'], limit=2)
    add(1, 'Fehlend: ' + ', '.join(result['missing']), limit=3)
    unknown = [SPECS[key][1][0] for key in SPECS if fields[key]['value'] is None]
    add(1, 'Weitere unbekannte Angaben: ' + ', '.join(unknown), limit=3)
    add(1, 'Widersprüche: ' + (', '.join(item['field'] for item in result['conflicts']) or 'keine erkannt'), limit=2)
    add(1, 'Abrufstatus: ' + result['fetch_status'], limit=2)
    add(1, 'Belegauszüge und Abrufzeiten (Auswahl):', True)
    for key in ('price','area','cold_rent'):
        data = fields[key]
        add(1, f"{key} · {data['retrieved_at']} · {data['evidence'] or 'unbekannt'} · {data['basis'] or ''}", limit=2)
    pdf = PDF()
    for page in pages:
        pdf.page(page)
    pdf.write(path)
