/* Portfolio cards use only the local SQLite API, never State-JSON or browser storage. */
(() => {
  let activeFilter = 'alle';
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[char]));
  const eur = value => value == null ? '–' : Number(value).toLocaleString('de-DE', {maximumFractionDigits:0}) + ' €';
  const pct = value => value == null ? '–' : Number(value).toLocaleString('de-DE', {minimumFractionDigits:2, maximumFractionDigits:2}) + ' %';
  const factorNumber = (price, rent) => price == null || rent == null || Number(rent) <= 0 ? null : Number(price) / (Number(rent) * 12);
  const factor = (price, rent) => {
    const value = factorNumber(price, rent);
    return value == null ? '–' : value.toLocaleString('de-DE', {minimumFractionDigits:2, maximumFractionDigits:2});
  };
  const bruttoRenditeClass = value => value == null ? '' : Number(value) >= 5 ? 'pos' : 'neg';
  const perM2 = (value, area) => value == null || !area ? '–' : eur(value / area);
  function detail(item) {
    const etage = String(item.etage || '').trim();
    if (etage) return '🧭 ' + etage;
    return '';
  }
  function card(item) {
    const hideDerived = item.analysis_status === 'abruf_blockiert';
    const file = (item.html_pfad || '').split('/').pop();
    const href = 'objekte/' + encodeURIComponent(item.name) + '/' + encodeURIComponent(file);
    const rentPerArea = item.kaltmiete != null && item.wohnflaeche
      ? '≈ ' + (item.kaltmiete / item.wohnflaeche).toLocaleString('de-DE', {minimumFractionDigits:2, maximumFractionDigits:2}) + ' €/m²' : '';
    const factorValue = factorNumber(item.kaufpreis, item.kaltmiete);
    const factorClass = factorValue == null ? '' : factorValue <= 20 ? 'pos' : 'neg';
    const photo = item.image_path && /^\/objekte\/[a-z0-9äöüß_-]+\/titelbild\.(jpg|png|webp|avif)$/i.test(item.image_path)
      ? `<div class="karte-photo-bg" style="background-image:url('${esc(item.image_path)}')"></div>` : '';
    return `<a class="karte${photo ? ' has-photo' : ''}" data-status="${esc(item.status_stufe ?? 0)}" href="${href}">${photo}
      <div class="karte-head"><div class="karte-title"><div class="karte-name">${esc(item.display_name || item.name)}</div></div><span class="status-badge">${esc(item.status_label || 'Gefunden')}</span></div>
      <div class="karte-details"><span>📐 ${item.wohnflaeche == null ? '–' : Math.round(item.wohnflaeche)} m²</span><span>📅 BJ ${item.baujahr == null ? '–' : Math.round(item.baujahr)}</span><span>🛏 ${item.zimmer == null ? '–' : Math.round(item.zimmer)} Zi.</span><span>${esc(detail(item))}</span></div>
      <div class="karte-kpis"><div><span class="l">Kaufpreis</span><span class="v">${eur(item.kaufpreis)}</span><span class="s">${perM2(item.kaufpreis,item.wohnflaeche)} /m²</span></div>
      <div><span class="l">Gesamtinvest</span><span class="v">${hideDerived ? '–' : eur(item.gesamtinvest)}</span><span class="s">${hideDerived ? 'Unterlagen offen' : perM2(item.gesamtinvest,item.wohnflaeche) + ' /m²'}</span></div>
      <div><span class="l">Miete/Monat</span><span class="v">${eur(item.kaltmiete)}</span><span class="s">${rentPerArea}</span></div>
      <div><span class="l">Faktor</span><span class="v ${factorClass}">${factor(item.kaufpreis,item.kaltmiete)}</span></div>
      <div><span class="l">BruttoR</span><span class="v ${hideDerived ? '' : bruttoRenditeClass(item.brutto_rendite)}">${hideDerived ? '–' : pct(item.brutto_rendite)}</span></div>
      <div><span class="l">CF/M</span><span class="v">${hideDerived ? '–' : eur(item.cf_nach)}</span></div></div></a>`;
  }
  function applyFilter() {
    document.querySelectorAll('#grid .karte').forEach(element => {
      element.style.display = activeFilter === 'alle' || String(element.dataset.status) === activeFilter ? '' : 'none';
    });
  }
  window.filtern = (stufe, button) => {
    activeFilter = stufe;
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
  window.neueObjekteAnalysieren = async button => {
    button.disabled = true;
    try {
      const response = await fetch('/api/new-candidates', {cache:'no-store'});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const {items} = await response.json();
      alert(items.length
        ? 'Neue Objektordner mit Unterlagen:\n\n' + items.map(item => `${item.name} (${item.documents} Unterlagen)`).join('\n') + '\n\nBitte den Dokumenten-Analyseprozess starten; die neue Analyse muss einen DB-Datensatz mit Objekt-ID anlegen.'
        : 'Keine neuen Objektordner mit Unterlagen gefunden. Bereits in SQLite erfasste Objekte werden übersprungen.');
    } catch (error) { alert('Ordnerprüfung fehlgeschlagen: ' + error.message); }
    finally { button.disabled = false; }
  };
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
