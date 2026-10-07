/* Stored Agent quick checks. Loading this view never starts work. */
(() => {
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
  const fmt = (value, unit='') => value == null ? 'nicht berechenbar' :
    (typeof value === 'number' ? value.toLocaleString('de-DE',{maximumFractionDigits:2,useGrouping:unit !== 'Jahr'}) : esc(value)) + (unit ? ' ' + esc(unit) : '');
  const fieldLabels = {title:'Titel', locality:'Ort', postal_code:'PLZ', district:'Stadtteil', address:'Adresse',
    price:'Kaufpreis', area:'Wohnfläche', land_area:'Grundstück', rooms:'Zimmer', units:'Wohneinheiten',
    property_type:'Objektart', year_built:'Baujahr', condition:'Zustand', rental_status:'Vermietungsstatus',
    cold_rent:'Tatsächliche Kaltmiete', annual_cold_rent:'Jahreskaltmiete', warm_rent:'Warmmiete', house_fee:'Hausgeld',
    non_recoverable:'Nicht umlagefähige Kosten', reserve_contribution:'Rücklagenbeitrag', reserve:'Rücklage',
    commission:'Käuferprovision', acquisition_costs:'Weitere Erwerbskosten', energy:'Energiekennwert',
    energy_class:'Energieklasse', heating:'Heizung', other:'Weitere Angaben', listing_portal:'Portal',
    listing_portal_id:'Anzeigen-ID', listing_url:'Anzeigenlink', profile_zins:'Profil-Sollzins',
    profile_tilgung:'Profil-Tilgung', profile_ek:'Profil-Eigenkapital', profile_ekAnteil:'Profil-EK-Anteil',
    market_cold_rent:'Geschätzte Marktkaltmiete', market_eur_m2:'Marktmietreferenz je m²',
    model_cost_percent:'Kostenpauschale (Modell)',model_price_factor:'Verhandlungsszenario (Modellfaktor)'};
  const safeLink = url => /^https:\/\//.test(url || '') ? `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(url)}</a>` : esc(url);
  const criterion = value => value == null ? 'nicht berechenbar' : value ? 'erfüllt' : 'nicht erfüllt';
  const metrics = [
    ['kaufpreis','Kaufpreis','€'], ['kp_pro_m2','Preis je m²','€/m²'], ['kaltmiete','Kaltmiete/Monat','€'],
    ['jahresKaltmiete','Kaltmiete/Jahr','€'], ['bruttoRendite','Bruttorendite','%'], ['kaufpreisfaktor','Faktor',''],
    ['ek','Eigenkapital','€'], ['ekProzent','EK-Anteil','%'], ['darlehen','Darlehen','€'],
    ['zins','Sollzins','%'], ['tilgung','Anfängliche Tilgung','%'], ['zinsMonat','Zins/Monat','€'],
    ['tilgungMonat','Tilgung/Monat','€'], ['rateMonat','Rate/Monat','€'],
    ['pauschaleKostenMonat','20-%-Kostenpauschale','€'], ['cashflowMonat','Cashflow vor Steuern/Monat','€'], ['cashflowJahr','Cashflow vor Steuern/Jahr','€']
  ];
  function card(item, jobs) {
    const r = item.result, f = r.fields, c = r.calculation, b = c.basis, s = c.szenario;
    const status = c.status.basis.gesamt;
    const sources = Object.entries(f).map(([key, v]) => `<tr><td>${esc(fieldLabels[key] || key)}</td><td>${v.value == null ? 'unbekannt' : fmt(v.value,v.unit)}</td><td>${esc(v.origin)}</td><td>${safeLink(v.source)}<br>${esc(v.retrieved_at)}<br>${esc(v.evidence)}<br>${esc(v.basis)}</td></tr>`).join('');
    const failures = jobs.filter(j => j.result_id === item.id || j.target === item.id).filter(j => ['failed','uncertain'].includes(j.state));
    const retry = failures.map(j => `<p class="qa-error">${esc(j.kind)}: ${esc(j.error)} <button type="button" class="btn secondary" data-qa-retry="${j.id}">${j.state === 'uncertain' ? 'Nach Prüfung erneut senden' : 'Schritt wiederholen'}</button></p>`).join('');
    return `<article class="karte qa-card">
      <div class="karte-head"><h3 class="karte-name">${esc(f.title.value || 'Immobilienangebot')}</h3><span class="status-badge">Agent${r.is_test ? ' · TEST' : ''}</span></div>
      <p class="qa-meta">${esc(f.locality.value || 'Ort unbekannt')} · ${esc(r.portal)} · Eingang ${esc(r.received_at)} · Revision ${item.revision}</p>
      <div class="karte-kpis">${[['Kaufpreis',fmt(b.kaufpreis,'€')],['Wohnfläche',fmt(f.area.value,'m²')],['Kaltmiete',fmt(b.kaltmiete,'€/M')],['Bruttorendite',fmt(b.bruttoRendite,'%')],['Faktor',fmt(b.kaufpreisfaktor)],['Cashflow',fmt(b.cashflowMonat,'€/M')]].map(([label,value]) => `<div><span class="l">${label}</span><span class="v">${value}</span></div>`).join('')}</div>
      <p>${esc(r.rent_label)}</p>
      <p class="qa-assessment ${status === 'bestanden' ? 'pos' : status === 'nicht bestanden' ? 'neg' : ''}"><strong>${esc(status)}</strong></p>
      <p class="qa-meta">Rendite: ${criterion(c.status.basis.bruttoRendite)} · Faktor: ${criterion(c.status.basis.kaufpreisfaktor)} · CF: ${criterion(c.status.basis.cashflow)}</p>
      <p>−10 %: ${fmt(s.kaufpreis,'€')} · ${fmt(s.bruttoRendite,'%')} · Faktor ${fmt(s.kaufpreisfaktor)} · CF ${fmt(s.cashflowMonat,'€/M')} · ${esc(c.status.szenario.gesamt)}</p>
      <p class="qa-meta">Analyse: ${esc(item.analysis_status)} · PDF: ${esc(item.pdf_status)} · Versand: ${esc(item.delivery_status)}</p>
      <p>${safeLink(r.url)} ${item.pdf_status === 'erstellt' ? `<a class="btn secondary" href="/api/quick-analyses/pdf/${esc(item.id)}">PDF herunterladen</a>` : ''}</p>
      ${retry}
      <details><summary>Details, Quellen und Annahmen</summary>
        <p class="qa-meta">Analyse ${esc(r.analyzed_at)} · Profil: ${esc(r.profile_name || 'fehlt')}</p>
        <p>${esc(r.assumptions)}</p><p>Rendite und Faktor sind mathematisch abhängig. Keine vollständige Wirtschaftlichkeitsprüfung.</p>
        <p>Ist-Cashflow: ${fmt(r.actual_cashflow,'€/Monat')}</p>
        <div class="table-scroll" tabindex="0" role="region" aria-label="Basis und Preisnachlass"><table><thead><tr><th>Kennzahl</th><th>Basis</th><th>−10 %</th></tr></thead><tbody>${metrics.map(([key,label,unit]) => `<tr><td>${label}</td><td>${fmt(b[key],unit)}</td><td>${fmt(s[key],unit)}</td></tr>`).join('')}</tbody></table></div>
        <p>Renditeänderung: ${fmt(c.vergleich.bruttoRendite.absolut,'Prozentpunkte')}</p>
        <p>Abrufstatus: ${esc(r.fetch_status)}</p><p>Fehlende Kerndaten: ${esc(r.missing.join(', ') || 'keine')}</p>
        <details><summary>Mietreferenzen</summary><pre>${esc(JSON.stringify(r.rent_reference || r.rent_reference_status,null,2))}</pre></details>
        <details><summary>Widersprüche und alternative Angaben (${r.conflicts.length})</summary><pre>${esc(JSON.stringify(r.conflicts,null,2))}</pre></details>
        <div class="table-scroll" tabindex="0" role="region" aria-label="Datenherkunft"><table><thead><tr><th>Feld</th><th>Wert</th><th>Herkunft</th><th>Quelle / Abruf / Beleg / Basis</th></tr></thead><tbody>${sources}</tbody></table></div>
        <details><summary>Telegram-Nachrichtenvorschau · kein Versand</summary><pre>${esc(r.notification_preview)}</pre></details>
      </details></article>`;
  }
  async function refresh() {
    const grid = document.getElementById('qaGrid');
    try {
      const response = await fetch('/api/quick-analyses',{cache:'no-store'});
      if (!response.ok) throw new Error('Schnellanalysen nicht erreichbar');
      const data = await response.json();
      document.getElementById('qaConnections').textContent = Object.values(data.connections).join(' · ');
      grid.innerHTML = data.items.length ? data.items.map(i => card(i,data.jobs)).join('') : '<p>Noch keine automatischen Schnellanalysen.</p>';
      const states = {ready:'erkannt / ausstehend',running:'in Verarbeitung'};
      const pending = data.jobs.filter(j => ['ready','running'].includes(j.state));
      document.getElementById('qaJobs').textContent = pending.length + ' offene Jobs. ' + pending.map(j => `${j.kind}: ${states[j.state]}`).join(' · ') + (data.worker ? ` · Letzte Workerabfrage: ${data.worker.updated_at}` + (data.worker.status.poll_error ? ' · ' + data.worker.status.poll_error : '') : ' · Worker noch nicht gestartet');
      const orphan = data.jobs.filter(j => j.state === 'failed' && !j.result_id && !data.items.some(i => i.id === j.target));
      if (orphan.length) grid.insertAdjacentHTML('beforeend', orphan.map(j => `<p class="qa-error">Job ${j.id}: ${esc(j.error)} <button class="btn secondary" data-qa-retry="${j.id}">Schritt wiederholen</button></p>`).join(''));
    } catch (error) { grid.textContent = error.message; }
  }
  document.getElementById('qaRefresh').addEventListener('click', refresh);
  document.getElementById('qaImport').addEventListener('change', async event => {
    const file = event.target.files[0];
    if (!file) return;
    const status = document.getElementById('qaImportStatus');
    try {
      if (file.size > 1_000_000) throw new Error('EML-Datei zu groß');
      const response = await fetch('/api/quick-analyses/import-eml', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({eml:await file.text()})});
      const data = await response.json();
      if (!response.ok) throw new Error(data.error);
      status.textContent = `${data.offers} Angebot(e). ${data.status}`;
      await refresh();
    } catch(error) { status.textContent = error.message; }
    event.target.value = '';
  });
  document.getElementById('qaGrid').addEventListener('click', async event => {
    const button = event.target.closest('[data-qa-retry]');
    if (!button) return;
    if (button.textContent.includes('senden') && !confirm('Unklare Zustellung: zuerst im Telegram-Chat prüfen. Eine Wiederholung kann doppelt zustellen. Trotzdem einreihen?')) return;
    button.disabled = true;
    try {
      const response = await fetch('/api/quick-analyses/retry', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({job_id:Number(button.dataset.qaRetry)})});
      const data = await response.json();
      if (!response.ok) throw new Error(data.error);
      await refresh();
    } catch(error) { document.getElementById('qaImportStatus').textContent = error.message; button.disabled = false; }
  });
  refresh();
})();
