/* Portfolio cards use only the local SQLite API, never State-JSON or browser storage. */
(() => {
  const ratingColor = {A:'#1a7f4b', B:'#2e7d32', C:'#b9770e', D:'#c25e12', F:'#c0392b'};
  const ratingBg = {A:'#e2f5ea', B:'#e8f5e9', C:'#fdf3dd', D:'#fdeadd', F:'#fde2e0'};
  let activeFilter = 'alle';
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[char]));
  const eur = value => value == null ? '–' : Number(value).toLocaleString('de-DE', {maximumFractionDigits:0}) + ' €';
  const pct = value => value == null ? '–' : Number(value).toLocaleString('de-DE', {minimumFractionDigits:2, maximumFractionDigits:2}) + ' %';
  const perM2 = (value, area) => value == null || !area ? '–' : eur(value / area);
  function detail(item) {
    const type = (item.objektart || '').toLowerCase();
    if (['wohnung', 'etw', 'apartment'].some(word => type.includes(word))) return '🏢 ' + item.objektart;
    if (item.grundstuecksflaeche > 0) return '🌳 ' + Math.round(item.grundstuecksflaeche).toLocaleString('de-DE') + ' m²';
    return item.objektart ? '🏠 ' + item.objektart : '';
  }
  function card(item) {
    const rating = item.gesamt_rating || '?';
    const preliminary = ['quellenpruefung_offen','abruf_blockiert'].includes(item.analysis_status);
    const file = (item.html_pfad || '').split('/').pop();
    const href = 'objekte/' + encodeURIComponent(item.name) + '/' + encodeURIComponent(file);
    const rentPerArea = item.kaltmiete != null && item.wohnflaeche
      ? '≈ ' + (item.kaltmiete / item.wohnflaeche).toLocaleString('de-DE', {minimumFractionDigits:2, maximumFractionDigits:2}) + ' €/m²' : '';
    const photo = item.image_path && /^\/objekte\/[a-z0-9äöüß_-]+\/titelbild\.(jpg|png|webp|avif)$/i.test(item.image_path)
      ? `<div class="karte-photo-bg" style="background-image:url('${esc(item.image_path)}')"></div>` : '';
    return `<a class="karte${photo ? ' has-photo' : ''}" data-rating="${esc(rating)}" href="${href}" style="display:block;text-decoration:none;color:inherit">${photo}
      <div class="karte-head"><div class="karte-name">${esc(item.display_name || item.name)}</div><div class="rating-badge" style="background:${ratingBg[rating] || '#e8ecf3'};color:${ratingColor[rating] || '#5a6a85'}">${preliminary ? 'Vorprüfung' : esc(rating)}</div></div>
      <div class="karte-sub">${esc(item.objektart)} · ${esc(item.adresse)}<br><small>Objekt-ID: ${esc(item.public_id)}</small></div>
      <div class="karte-details"><span>📐 ${item.wohnflaeche == null ? '–' : Math.round(item.wohnflaeche)} m²</span><span>📅 BJ ${item.baujahr == null ? '–' : Math.round(item.baujahr)}</span><span>🛏 ${item.zimmer == null ? '–' : Math.round(item.zimmer)} Zi.</span><span>${esc(detail(item))}</span></div>
      <div class="karte-kpis"><div><span class="l">Kaufpreis</span><span class="v">${eur(item.kaufpreis)}</span><span class="s">${perM2(item.kaufpreis,item.wohnflaeche)} /m²</span></div>
      <div><span class="l">Gesamtinvest</span><span class="v">${preliminary ? '–' : eur(item.gesamtinvest)}</span><span class="s">${preliminary ? 'Unterlagen offen' : perM2(item.gesamtinvest,item.wohnflaeche) + ' /m²'}</span></div>
      <div><span class="l">BruttoR</span><span class="v">${preliminary ? '–' : pct(item.brutto_rendite)}</span></div><div><span class="l">CF/M</span><span class="v">${preliminary ? '–' : eur(item.cf_nach)}</span></div></div>
      <div class="karte-fin"><div><span class="l">Miete/Monat</span><span class="v">${eur(item.kaltmiete)}</span><span class="s">${rentPerArea}</span></div>
      <div><span class="l">Finanzierung</span><span class="v">${eur(item.ek)} EK · ${pct(item.zins)} · ${pct(item.tilgung)} Tilg.</span></div></div></a>`;
  }
  function applyFilter() {
    document.querySelectorAll('#grid .karte').forEach(element => {
      const rating = element.dataset.rating || element.querySelector('.rating-badge')?.textContent.trim();
      element.style.display = activeFilter === 'alle' || (activeFilter === 'DF' ? ['D','F'].includes(rating) : rating === activeFilter) ? '' : 'none';
    });
  }
  window.filtern = (rating, button) => {
    activeFilter = rating;
    document.querySelectorAll('.filter button').forEach(element => element.classList.remove('aktiv'));
    button.classList.add('aktiv');
    applyFilter();
  };
  window.portfolioAktualisieren = async button => {
    if (button) button.disabled = true;
    try {
      const response = await fetch('/api/portfolio', {cache:'no-store'});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const {items} = await response.json();
      document.getElementById('grid').innerHTML = items.length ? items.map(card).join('') : '<p>Keine aktiven Objekte in der Datenbank.</p>';
      document.getElementById('stand').textContent = `Übersicht aller analysierten Objekte · ${items.length} Objekt(e) · DB-Stand: ${new Date().toLocaleString('de-DE')}`;
      applyFilter();
    } catch (error) {
      document.getElementById('grid').textContent = 'Datenbank nicht erreichbar. Bitte den lokalen Projektserver starten.';
      document.getElementById('stand').textContent = 'Keine Daten geladen: ' + error.message;
    } finally {
      if (button) button.disabled = false;
    }
  };
  window.neueObjekteAnalysieren = () => alert('Neue Objekte müssen im DB-gestützten Analyseprozess angelegt werden. State-JSON-Dateien werden nicht mehr als Quelle importiert.');
  window.importListing = async event => {
    event.preventDefault();
    const form = event.currentTarget;
    const button = form.querySelector('button[type="submit"]');
    const status = document.getElementById('importStatus');
    button.disabled = true;
    status.textContent = 'Anzeige wird gelesen und als Voranalyse angelegt …';
    try {
      const response = await fetch('/api/import-listing', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({url:document.getElementById('listingUrl').value.trim()})
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || `HTTP ${response.status}`);
      status.textContent = `${result.status} · Objekt-ID: ${result.id}`;
      await window.portfolioAktualisieren();
      if (result.path) {
        const link = document.createElement('a');
        link.href = result.path;
        link.textContent = 'Objektübersicht öffnen ↗';
        status.append(' ', link);
      }
    } catch(error) {
      status.textContent = `Import nicht möglich: ${error.message}. Bitte Link oder Unterlagen manuell prüfen.`;
    } finally {
      button.disabled = false;
    }
  };
  if ('BroadcastChannel' in window) {
    const channel = new BroadcastChannel('immo-db-revision');
    channel.onmessage = () => window.portfolioAktualisieren();
  }
  window.portfolioAktualisieren();
})();
