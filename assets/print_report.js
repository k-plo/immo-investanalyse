/* A compact, two-page print summary derived from the current live calculation. */
(() => {
  const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const money = v => Number.isFinite(v) ? `${Math.round(v).toLocaleString('de-DE')} €` : '–';
  const signed = v => Number.isFinite(v) ? `${v < 0 ? '−' : ''}${money(Math.abs(v))}` : '–';
  const row = (name, value, total = false) => `<tr${total ? ' class="total"' : ''}><td>${esc(name)}</td><td>${esc(value)}</td></tr>`;
  const field = id => document.getElementById(id);
  const isEmpty = id => !field(id) || String(field(id).value).trim() === '';
  const unique = items => [...new Set(items.map(s => s.trim()).filter(Boolean))];

  function chart(years) {
    const w = 700, h = 235, left = 62, right = 16, top = 16, bottom = 32;
    const values = years.flatMap(y => [y.cumIncome, y.cumExpense, y.cumCashflow]);
    const min = Math.min(0, ...values), max = Math.max(0, ...values);
    const range = Math.max(1, max - min);
    const x = i => left + i * (w - left - right) / 10;
    const y = value => top + (max - value) * (h - top - bottom) / range;
    const grid = Array.from({length:5}, (_,i) => {
      const val = min + range * i / 4, yy = y(val);
      return `<line class="grid" x1="${left}" y1="${yy}" x2="${w-right}" y2="${yy}"/><text x="${left-7}" y="${yy+3}" text-anchor="end">${Math.round(val/1000).toLocaleString('de-DE')}k</text>`;
    }).join('');
    const path = key => `M ${x(0)} ${y(0)} ` + years.map((item, i) => `L ${x(i+1)} ${y(item[key])}`).join(' ');
    const ticks = Array.from({length:11},(_,i) => `<text x="${x(i)}" y="${h-9}" text-anchor="middle">${i}</text>`).join('');
    return `<svg class="pr-chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="Kumulierte Einnahmen, Ausgaben und Cashflow über zehn Jahre">${grid}<line x1="${left}" y1="${y(0)}" x2="${w-right}" y2="${y(0)}" stroke="#859aa2" stroke-width="1.2"/>${ticks}<path d="${path('cumIncome')}" fill="none" stroke="#177f75" stroke-width="2.7"/><path d="${path('cumExpense')}" fill="none" stroke="#b67b37" stroke-width="2.7"/><path d="${path('cumCashflow')}" fill="none" stroke="#b8474e" stroke-width="2.7"/></svg>`;
  }

  function buildReport() {
    const data = readInputs();
    const result = calc(data);
    const heading = document.querySelector('.wrap h1')?.textContent.replace(/^\s*🏠\s*/, '').trim() || 'Immobilienanalyse';
    const meta = document.querySelector('.wrap .sub')?.textContent.trim() || '';
    const date = new Date().toLocaleDateString('de-DE');
    const missing = ['renovierung','sanierung','kaltmiete','hausgeld','hausgeldNichtUml'].filter(isEmpty);
    const rentMissing = isEmpty('kaltmiete');
    const canCalculate = Boolean(result.berechenbar);
    const income = data.kaltmiete * 12 * (1 - data.leerstand / 52);
    const operating = data.hausgeldNichtUml * 12 + data.flaeche * data.instand;
    let balance = canCalculate ? result.darlehen : 0;
    let cumIncome = 0, cumExpense = 0;
    const years = Array.from({length:10}, (_,i) => {
      let debt = 0;
      for (let month = 0; month < 12 && balance > 0; month++) {
        const interest = balance * data.zins / 100 / 12;
        const payment = Math.min(result.rate, balance + interest);
        debt += payment;
        balance = Math.max(0, balance - (payment - interest));
      }
      const expense = operating + debt;
      const annual = income - expense;
      cumIncome += income;
      cumExpense += expense;
      return {year:i+1,income,operating,debt,expense,annual,cumIncome,cumExpense,cumCashflow:cumIncome-cumExpense};
    });
    const acquisition = canCalculate ? [
      row('Erwerbsnebenkosten',money(result.nk)),
      row('Renovierung und Sanierung',money(data.renovierung+data.sanierung)),
      row('Zusatzkosten gesamt',money(result.nk+data.renovierung+data.sanierung),true)
    ].join('') : row('Gesamtinvestition','Noch nicht berechenbar');
    const operations = [
      row('Kaltmiete / Monat',money(data.kaltmiete)),
      row('Leerstand / Jahr',`${data.leerstand.toLocaleString('de-DE')} Wochen`),
      row('Nicht umlagefähige Kosten / Monat',money(data.hausgeldNichtUml)),
      row('Instandhaltung / Jahr',money(data.flaeche*data.instand)),
      row('Kreditrate / Monat',canCalculate?money(result.rate):'–')
    ].join('');
    const riskCells = [...document.querySelectorAll('#tblRisiken tr')].slice(1).map(tr => {
      const cells = tr.querySelectorAll('td');
      const amp = cells[2]?.querySelector('select')?.value || cells[2]?.textContent || '';
      return {name:cells[0]?.textContent.trim() || '',amp};
    }).filter(r => r.name && /🔴|🟠/.test(r.amp)).slice(0,3).map(r => r.name);
    let inspection = {checks:[],questions:[]};
    try { inspection = JSON.parse(document.getElementById('inspectionData')?.textContent || '{}'); } catch (_) {}
    const checks = Array.isArray(inspection.checks) ? inspection.checks.slice(0,3) : [];
    const questions = Array.isArray(inspection.questions) ? inspection.questions.slice(0,4) : [];
    const visitItems = unique([...riskCells.slice(0,2), ...checks]);
    const assumptions = unique([
      `Zins ${data.zins.toLocaleString('de-DE')} % · Tilgung ${data.tilgung.toLocaleString('de-DE')} %`,
      'Zehnjahresrechnung in heutigen Euro, ohne Miet- und Kostensteigerung; Zins über zehn Jahre konstant. Kreditrate endet bei vollständiger Tilgung.',
      ...(missing.length ? [`Leere Felder als 0 € gerechnet: ${missing.map(id => FELDLABEL[id] || id).join(', ')}.`] : [])
    ]);
    const warning = !canCalculate ? 'Kaufpreis oder Wohnfläche fehlen. Eine Zehnjahresrechnung ist mit diesen Eingaben nicht möglich.' : rentMissing ? 'Kaltmiete nicht belegt. Die Grafik setzt das leere Feld rechnerisch mit 0 € an und ist keine belastbare Ertragsprognose.' :
      missing.length ? 'Einige nicht belegte Kosten sind rechnerisch mit 0 € angesetzt. Vor einer Entscheidung prüfen.' : 'Modellrechnung mit den aktuellen Eingaben.';
    const yearRows = years.map(y => `<tr><td>${y.year}</td><td>${canCalculate?money(y.income):'–'}</td><td>${canCalculate?money(y.operating):'–'}</td><td>${canCalculate?money(y.debt):'–'}</td><td>${canCalculate?signed(y.annual):'–'}</td><td>${canCalculate?signed(y.cumCashflow):'–'}</td></tr>`).join('');
    return `<div class="print-report" aria-label="Zweiseitige Investment-Zusammenfassung">
      <section class="print-sheet">
        <div class="pr-kicker">Immobilienportfolio · Investment-Überblick</div>
        <h1>${esc(heading)}</h1><p class="pr-meta">${esc(meta)} · Stand ${esc(date)}</p>
        <div class="pr-status ${missing.length?'alert':''}">${esc(warning)}</div>
        <div class="pr-kpis">
          <div class="pr-kpi"><small>Kaufpreis</small><strong>${money(data.preis)}</strong></div>
          <div class="pr-kpi"><small>Gesamtinvestition</small><strong>${canCalculate?money(result.gesamt):'–'}</strong></div>
          <div class="pr-kpi"><small>Eigenkapital</small><strong>${money(data.ek)}</strong></div>
          <div class="pr-kpi"><small>Cashflow / Monat</small><strong>${canCalculate?signed(result.cf):'–'}</strong></div>
        </div>
        <div class="pr-grid"><div class="pr-section"><h2>Investition</h2><table class="pr-table">${acquisition}</table></div>
        <div class="pr-section"><h2>Laufende Rechnung</h2><table class="pr-table">${operations}</table></div></div>
        <p class="pr-assumptions">${assumptions.map(esc).join(' · ')}</p>
        <div class="pr-inspection"><h2>Besichtigung – auf einen Blick</h2><div class="pr-visit-grid">
          <div><h3>Wichtig / vor Ort prüfen</h3><ul>${(visitItems.length?visitItems:['Zustand und Unterlagen vor Ort prüfen.']).map(v=>`<li>${esc(v)}</li>`).join('')}</ul></div>
          <div><h3>Verkäufer fragen / Unterlagen</h3><ol>${(questions.length?questions:['Welche Unterlagen und Nachweise liegen vor?']).map(v=>`<li>${esc(v)}</li>`).join('')}</ol></div>
        </div></div>
        <div class="pr-notes"><h2>Notizen zur Besichtigung</h2>${'<div class="line"></div>'.repeat(5)}</div>
        <div class="pr-foot"><span>Modellrechnung · Angaben und Belege prüfen</span><span>1 / ${canCalculate?2:1}</span></div>
      </section>
      ${canCalculate?`<section class="print-sheet">
        <div class="pr-kicker">Immobilienportfolio · Zehnjahresblick</div>
        <h1>Cashflow über 10 Jahre</h1><p class="pr-meta">${esc(heading)} · Kumulierte Beträge in Euro · Stand ${esc(date)}</p>
        <div class="pr-legend"><span><i class="pr-dot" style="background:#177f75"></i>Einnahmen</span><span><i class="pr-dot" style="background:#b67b37"></i>Ausgaben inklusive Kreditrate</span><span><i class="pr-dot" style="background:#b8474e"></i>Cashflow</span></div>
        ${canCalculate?chart(years):'<div class="pr-chart pr-chart-empty">Zehnjahresgrafik nach Eingabe von Kaufpreis und Wohnfläche verfügbar.</div>'}
        <p class="pr-note">${esc(warning)} Konstante Nominalwerte; kein Verkaufserlös, keine Steuer- oder Wertentwicklung enthalten.</p>
        <table class="pr-table pr-year-table"><thead><tr><th>Jahr</th><th>Einnahmen</th><th>Laufende Kosten</th><th>Kreditrate</th><th>Cashflow</th><th>Cashflow kumuliert</th></tr></thead><tbody>${yearRows}</tbody></table>
        <div class="pr-foot"><span>Jahreswerte auf ganze Euro gerundet · keine Prognosegarantie</span><span>2 / 2</span></div>
      </section>`:''}</div>`;
  }

  document.addEventListener('click', event => {
    if (!event.target.closest('.print-btn')) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    document.querySelector('.print-report')?.remove();
    document.body.insertAdjacentHTML('beforeend', buildReport());
    window.print();
  }, true);
  // Direct, read-only print preview for QA and repeatable PDF exports.
  if (location.hash === '#print-report') {
    document.addEventListener('DOMContentLoaded', () => {
      document.body.insertAdjacentHTML('beforeend', buildReport());
    });
  }
})();
