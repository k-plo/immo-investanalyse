/* Schnellcheck-Karten: leichtgewichtige Erstbewertung, nur SQLite-API, keine Objektübersicht. */
(() => {
  const byId = new Map();
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[char]));
  const num = value => value === null || value === undefined || value === '' ? null : Number(value);
  const eur = value => value == null ? '–' : Number(value).toLocaleString('de-DE', {maximumFractionDigits:0}) + ' €';
  const pct = value => value == null ? '–' : Number(value).toLocaleString('de-DE', {minimumFractionDigits:2, maximumFractionDigits:2}) + ' %';
  const faktorFmt = value => value == null ? '–' : Number(value).toLocaleString('de-DE', {minimumFractionDigits:2, maximumFractionDigits:2});
  const perM2 = (value, area) => value == null || !area ? '' : '≈ ' + (value / area).toLocaleString('de-DE', {minimumFractionDigits:2, maximumFractionDigits:2}) + ' €/m²';
  const kennzahlen = c => {
    const ist = num(c.kaltmiete_ist), pot = num(c.kaltmiete_pot), preis = num(c.kaufpreis);
    const basis = ist != null ? ist : pot;
    const rendite = basis != null && preis > 0 ? basis * 12 / preis * 100 : null;
    const faktor = basis != null && basis > 0 && preis != null ? preis / (basis * 12) : null;
    return {rendite, faktor, ausPotenzial: ist == null && pot != null};
  };
  const chip = (icon, value) => `<span>${icon} ${esc(value == null || value === '' ? '–' : value)}</span>`;
  const editField = (c, field, label, type) =>
    `<label>${label}<input type="${type || 'text'}" data-field="${field}" value="${esc(c[field] ?? '')}" onchange="scFieldSave(this)"></label>`;
  function card(c) {
    const k = kennzahlen(c);
    const name = (c.strasse || c.hausnummer) ? `${c.strasse || ''} ${c.hausnummer || ''}`.trim() : (c.titel || 'Schnellcheck');
    const ortsteil = [c.ort, c.stadtteil].filter(x => x && String(x).trim()).join(' · ');
    const renditeClass = k.rendite == null ? '' : k.rendite >= 5 ? 'pos' : 'neg';
    const faktorClass = k.faktor == null ? '' : k.faktor >= 20 ? 'neg' : 'pos';
    const basisHinweis = k.ausPotenzial ? '<span class="s">Basis: pot. Miete</span>' : '';
    const uebersicht = c.objekt_pfad
      ? `<a class="btn secondary sc-link" href="/${esc(c.objekt_pfad)}">Übersicht öffnen ↗</a>`
      : `<button type="button" onclick="schnellcheckUebersicht('${esc(c.public_id)}', this)" title="Legt Objektordner und vollständige Übersicht an">🏠 Übersicht anlegen</button>`;
    const quelle = c.source_url ? ` · <a href="${esc(c.source_url)}" target="_blank" rel="noopener noreferrer">Anzeige ↗</a>` : '';
    return `<div class="karte sc-karte" data-id="${esc(c.public_id)}">
      <div class="karte-head"><div class="karte-title"><div class="karte-name">${esc(name)}</div></div><span class="status-badge">Schnellcheck</span></div>
      <div class="karte-sub">${esc(ortsteil || 'Adresse ergänzen (✏️ Details)')}</div>
      <div class="karte-details">${chip('📐', c.wohnflaeche == null ? null : Math.round(c.wohnflaeche) + ' m²')}${chip('🛏', c.zimmer == null ? null : c.zimmer + ' Zi.')}${chip('🧭', c.geschoss)}${chip('📅', c.baujahr == null ? null : 'BJ ' + Math.round(c.baujahr))}${chip('⚡', c.energieklasse)}</div>
      <div class="karte-kpis sc-kpis">
        <div><span class="l">Kaufpreis</span><span class="v">${eur(num(c.kaufpreis))}</span><span class="s">${perM2(num(c.kaufpreis), num(c.wohnflaeche))}</span></div>
        <div><span class="l">KM ist</span><span class="v">${eur(num(c.kaltmiete_ist))}</span><span class="s">${perM2(num(c.kaltmiete_ist), num(c.wohnflaeche))}</span></div>
        <div><span class="l">KM pot</span><span class="v">${eur(num(c.kaltmiete_pot))}</span><span class="s">${perM2(num(c.kaltmiete_pot), num(c.wohnflaeche))}</span></div>
        <div><span class="l">BruttoR</span><span class="v ${renditeClass}">${pct(k.rendite)}</span>${basisHinweis}</div>
        <div><span class="l">Faktor</span><span class="v ${faktorClass}">${faktorFmt(k.faktor)}</span>${basisHinweis}</div>
      </div>
      <div class="sc-edit" hidden>
        ${editField(c, 'ort', 'Ort')}${editField(c, 'stadtteil', 'Stadtteil')}
        ${editField(c, 'strasse', 'Straße')}${editField(c, 'hausnummer', 'Hausnr.')}
        ${editField(c, 'kaufpreis', 'Kaufpreis (€)', 'number')}${editField(c, 'wohnflaeche', 'Wohnfläche (m²)', 'number')}
        ${editField(c, 'zimmer', 'Zimmer', 'number')}${editField(c, 'geschoss', 'Geschoss')}
        ${editField(c, 'baujahr', 'Baujahr', 'number')}${editField(c, 'energieklasse', 'Energieklasse')}
      </div>
      <div class="sc-actions">
        ${uebersicht}
        <button type="button" class="btn secondary" onclick="const e=this.closest('.sc-karte').querySelector('.sc-edit');e.hidden=!e.hidden">✏️ Details</button>
        <button type="button" class="btn secondary sc-del" title="Schnellcheck löschen" onclick="schnellcheckLoeschen('${esc(c.public_id)}')">🗑</button>
      </div>
      <div class="karte-datum">angelegt ${esc((c.erstellt_am || '').slice(0, 10))}${quelle}</div>
    </div>`;
  }
  async function api(method, url, body) {
    const response = await fetch(url, {
      method, cache: 'no-store',
      headers: body ? {'Content-Type': 'application/json'} : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
    return data;
  }
  window.schnellcheckAktualisieren = async button => {
    if (button) button.disabled = true;
    try {
      const {items} = await api('GET', '/api/schnellchecks');
      byId.clear();
      items.forEach(item => byId.set(item.public_id, item));
      const grid = document.getElementById('scGrid');
      grid.innerHTML = items.length ? items.map(card).join('')
        : '<p class="sub">Noch keine Schnellchecks. Oben per Link den ersten Check anlegen.</p>';
      const stand = document.getElementById('scStand');
      if (stand) stand.textContent = `${items.length} Schnellcheck(s) · Bruttorendite ≥ 5 % = grün · Faktor < 20 = grün · Keine Objektübersicht nötig`;
    } catch (error) {
      document.getElementById('scGrid').innerHTML = `<p class="sub">Schnellchecks nicht ladbar: ${esc(error.message)}</p>`;
    } finally {
      if (button) button.disabled = false;
    }
  };
  window.schnellcheckImport = async event => {
    event.preventDefault();
    const form = event.currentTarget;
    const button = form.querySelector('button[type="submit"]');
    const status = document.getElementById('scImportStatus');
    button.disabled = true;
    status.textContent = 'Anzeige wird gelesen (nur Schnellcheck-Kennzahlen) …';
    try {
      const data = await api('POST', '/api/schnellcheck', {url: document.getElementById('scUrl').value.trim()});
      status.textContent = data.status;
      form.reset();
      await window.schnellcheckAktualisieren();
    } catch (error) {
      status.textContent = `Schnellcheck nicht möglich: ${error.message}. Felder können nach dem Anlegen manuell ergänzt werden.`;
    } finally {
      button.disabled = false;
    }
  };
  window.scFieldSave = async input => {
    const id = input.closest('.sc-karte').dataset.id;
    const item = byId.get(id);
    if (!item) return;
    try {
      await api('PUT', `/api/schnellcheck/${id}`, {fields: {[input.dataset.field]: input.value}, revision: item.revision});
      await window.schnellcheckAktualisieren();
    } catch (error) {
      alert('Speichern fehlgeschlagen: ' + error.message);
      await window.schnellcheckAktualisieren();
    }
  };
  window.schnellcheckUebersicht = async (id, button) => {
    button.disabled = true;
    button.textContent = '⏳ Übersicht wird angelegt …';
    try {
      const data = await api('POST', `/api/schnellcheck/${id}/uebersicht`, {});
      await window.schnellcheckAktualisieren();
      if (data.path) window.open(data.path, '_blank');
    } catch (error) {
      alert('Übersicht konnte nicht angelegt werden: ' + error.message);
      button.disabled = false;
      button.textContent = '🏠 Übersicht anlegen';
    }
  };
  window.schnellcheckLoeschen = async id => {
    const item = byId.get(id);
    if (!item || !confirm('Schnellcheck wirklich löschen?')) return;
    try {
      await api('DELETE', `/api/schnellcheck/${id}`, {revision: item.revision});
      await window.schnellcheckAktualisieren();
    } catch (error) {
      alert('Löschen fehlgeschlagen: ' + error.message);
    }
  };
  window.schnellcheckAktualisieren();
})();
