"""Quick-analysis orchestration; never calls the regular object creation path."""
from __future__ import annotations
import json
from quick_extract import extract_page, merge_fields, field, now
from quick_pdf import notification_preview
from rechenkern import schnellanalyse
from listing_import import ListingError

ASSUMPTIONS = ('Kostenmodus: Pauschal, 20 % der Kaltmiete für nicht umlagefähige Kosten, Rücklage und sonstige Kosten. '
               'Belegte Kosten separat, nicht zusätzlich abgezogen. Darlehen = max(0, Kaufpreis - Eigenkapital). '
               'Erwerbsnebenkosten, Leerstand und Steuern nicht berücksichtigt.')


def validate_profile(profile):
    if profile is None:
        return None
    if not isinstance(profile, dict) or not profile.get('name') or profile.get('ekModus') not in ('betrag','anteil'):
        raise ValueError('Analyseprofil benötigt Name und EK-Modus betrag/anteil')
    for key in ('zins','tilgung', 'ek' if profile['ekModus'] == 'betrag' else 'ekAnteil'):
        value = profile.get(key)
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not __import__('math').isfinite(value) or value < 0:
            raise ValueError('Profilwert fehlt/ungültig: ' + key)
    if profile['ekModus'] == 'anteil' and profile['ekAnteil'] > 100:
        raise ValueError('EK-Anteil muss zwischen 0 und 100 liegen')
    # Only calculation parameters are persisted, never arbitrary config/secrets.
    return {key:profile[key] for key in ('name','zins','tilgung','ekModus','ek','ekAnteil') if key in profile}


def analyze(observation, listing_adapter, rent_adapter):
    entry = json.loads(observation['evidence_json'])
    profile = validate_profile(json.loads(observation['profile_json'] or 'null'))
    error, page_values = None, {}
    try:
        final, page = listing_adapter.fetch(entry['url'])
        from quick_extract import normalize_url
        identity = normalize_url(final)
        if not identity or identity['portal'] != entry['portal'] or identity['portal_id'] != entry['portal_id']:
            raise ListingError('Weiterleitung liefert eine andere Anzeige')
        page_values = extract_page(page, identity['url'])
        fetch_status = 'Öffentliche Anzeige abgerufen' if not observation['is_test'] else 'TEST: lokale Anzeigenfixture gelesen'
    except ListingError as exc:
        error = 'Anzeigenabruf fehlgeschlagen/blockiert – manuell wiederholbar'
        fetch_status = error
        retryable_fetch = not any(code in str(exc) for code in ('HTTP 401','HTTP 403'))
    fields, conflicts = merge_fields(entry['fields'], page_values)
    for key in ('portal','portal_id','url'):
        fields['listing_' + key] = field(entry[key], '', 'message:' + observation['external_message_id'],
                                         'Normalisierter Anzeigenlink: ' + entry['url'], 'ABGELEITET',
                                         'Portal und Anzeigen-ID aus URL; Trackingparameter entfernt')
    reference = None
    # A conflict in actual rent must not silently turn into an ordinary market-based
    # analysis. Reference scenarios stay explicit and never populate cold_rent.
    if fields['cold_rent']['value'] is None:
        reference = rent_adapter.estimate(fields)
    cold = fields['cold_rent']['value']
    label = 'Tatsächliche Kaltmiete laut Quelle' if cold is not None else 'Kaltmiete unbekannt'
    if reference:
        label = 'Bewertung auf Basis geschätzter Marktmiete – ausschließlich Marktmietszenario'
        fields['market_cold_rent'] = field(reference['monthly'],'EUR/Monat',reference['sources'][0]['url'],
                                          reference['method'],'ABGELEITET',
                                          f"Median {reference['eur_m2']} €/m² × Wohnfläche {fields['area']['value']} m²")
        fields['market_eur_m2'] = field(reference['eur_m2'],'EUR/m²',reference['sources'][0]['url'],
                                      reference['method'],'ABGELEITET','Belegte Test-Angebotsmieten; n=' + str(reference['sample_size']))
    selected_rent = cold if cold is not None else reference['monthly'] if reference else None
    values = {'kaufpreis':fields['price']['value'], 'kaltmiete':selected_rent,
              'zins':None,'tilgung':None,'ek':None,'ekAnteil':None,'ekModus':'betrag'}
    if profile:
        values.update({key:value for key,value in profile.items() if key != 'name'})
        for key in ('zins','tilgung','ek' if profile['ekModus'] == 'betrag' else 'ekAnteil'):
            fields['profile_' + key] = field(profile[key], 'EUR' if key == 'ek' else '%',
                                             'profile:' + profile['name'],'Explizites Analyseprofil','ANNAHME')
    calculation = schnellanalyse(values)
    fields['model_cost_percent'] = field(calculation['basis']['pauschaleKostenProzent'], '%',
                                         'assets/schnellanalyse_core.js', 'PAUSCHALE_KOSTEN_PROZENT', 'ANNAHME',
                                         'Gemeinsame Kostenpauschale; keine belegte Objektkostenangabe')
    fields['model_price_factor'] = field(calculation['szenarioFaktor'], '',
                                         'Analyseauftrag / assets/schnellanalyse_core.js', 'SZENARIO_FAKTOR', 'ANNAHME',
                                         'Szenario-Kaufpreis = belegter Kaufpreis × 0,90')
    area = fields['area']['value']
    for variant in ('basis','szenario'):
        metrics = calculation[variant]
        price = metrics['kaufpreis']
        metrics['kp_pro_m2'] = price / area if price is not None and area else None
        metrics['ekProzent'] = metrics['ek'] / price * 100 if metrics['ek'] is not None and price else None
        metrics['zins'], metrics['tilgung'] = values['zins'], values['tilgung']
    missing = []
    for key, title in (('price','Kaufpreis'),('area','Wohnfläche'),('postal_code','PLZ'),('rental_status','Vermietungsstatus')):
        if fields[key]['value'] is None:
            missing.append(title)
    if cold is None:
        missing.append('Ist-Kaltmiete' if fields['rental_status']['value'] == 'vermietet' else 'tatsächliche Kaltmiete')
    if cold is None and not reference:
        missing.append('Mietreferenz fehlt')
    if not profile:
        missing.append('Finanzierungsprofil')
    result = {'fields':fields, 'conflicts':conflicts, 'missing':missing, 'calculation':calculation,
              'rent_reference':reference, 'rent_reference_status': 'Belegte Test-Angebotsreferenzen' if reference else 'nicht benötigt (Ist-Miete vorhanden)' if cold is not None else 'Mietreferenz fehlt – ' + rent_adapter.status,
              'rent_label':label, 'rent_basis':'actual' if cold is not None else 'market' if reference else 'unknown',
              'actual_cashflow':calculation['basis']['cashflowMonat'] if cold is not None else None,
              'profile_name':profile['name'] if profile else None, 'assumptions':ASSUMPTIONS,
              'fetch_status':fetch_status, 'retryable_fetch':retryable_fetch if error else False,
              'url':entry['url'], 'is_test':bool(observation['is_test'])}
    result['notification_preview'] = notification_preview(result)
    return result, error
