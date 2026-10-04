#!/usr/bin/env node
'use strict';
/* Tests der Schnellanalyse-Berechnungslogik (assets/schnellanalyse_core.js).
 * Ausführen: node tests/test_schnellanalyse.js
 */
const path = require('path');
const core = require(path.join(__dirname, '..', 'assets', 'schnellanalyse_core.js'));

let passed = 0;
let failed = 0;
function test(name, fn) {
  try { fn(); passed++; console.log('✓ ' + name); }
  catch (error) { failed++; console.error('✗ ' + name + '\n    ' + error.message); }
}
function assertEqual(actual, expected, message) {
  if (actual !== expected) throw new Error((message || 'assertEqual') + ': ' + actual + ' !== ' + expected);
}
function assertClose(actual, expected, eps, message) {
  if (actual === null || actual === undefined) throw new Error((message || 'assertClose') + ': Wert ist ' + actual);
  if (Math.abs(actual - expected) > eps) throw new Error((message || 'assertClose') + ': ' + actual + ' !≈ ' + expected);
}
function assertTrue(value, message) { if (!value) throw new Error((message || 'assertTrue') + ': ' + value); }
function assertFalse(value, message) { if (value) throw new Error((message || 'assertFalse') + ': ' + value); }

// Beispiel: nicht umlagefähige Kosten, Rücklage und sonstige Kosten sind
// pauschal 20 % der Kaltmiete (1.500 € → 300 €).
const BEISPIEL = {
  kaufpreis: 300000, kaltmiete: 1500,
  zins: 4, tilgung: 2, finanzierungsart: core.FINANZIERUNGS_BETRAG, darlehen: 270000
};

// 1) Bruttomietrendite
test('Bruttomietrendite Basis = 6,00 %', () => {
  const a = core.analyse(BEISPIEL);
  assertTrue(a.ok);
  assertClose(a.basis.bruttoRendite, 6.0, 1e-9);
});

// 2) Kaufpreisfaktor
test('Kaufpreisfaktor Basis = 16,67', () => {
  const a = core.analyse(BEISPIEL);
  assertClose(a.basis.kaufpreisfaktor, 300000 / 18000, 1e-9);
});

// 3) Cashflow nach Finanzierung (inkl. 20-%-Kostenpauschale)
test('Cashflow nach Finanzierung (Rate 1.350 €, Pauschale 300 €) = −150 €/Monat', () => {
  const a = core.analyse(BEISPIEL);
  assertClose(a.basis.pauschaleKostenMonat, 300, 1e-9, 'Pauschale');
  assertClose(a.basis.rateMonat, 1350, 1e-9, 'Rate');
  assertClose(a.basis.cashflowMonat, -150, 1e-9, 'Cashflow');
  assertClose(a.basis.cashflowJahr, -1800, 1e-9, 'Cashflow/Jahr');
});

// 4) Statusgrenzen – exakte Grenzwerte gelten als NICHT erfüllt
test('Rendite genau 5,00 % gilt als nicht erfüllt', () => {
  const a = core.analyse({ ...BEISPIEL, kaufpreis: 240000, kaltmiete: 1000 });
  assertClose(a.basis.bruttoRendite, 5.0, 1e-9);
  assertFalse(a.status.basis.bruttoRendite, 'exakt 5 %');
});
test('Cashflow genau 0 € gilt als nicht erfüllt', () => {
  // Pauschale 20 % von 1.000 € = 200 €; Rate = 160.000 × 6 % / 12 = 800 € → Cashflow 0 €.
  const a = core.analyse({ kaufpreis: 200000, kaltmiete: 1000, zins: 6, tilgung: 0,
    finanzierungsart: core.FINANZIERUNGS_ANTEIL, finanzierungsanteil: 80 });
  assertClose(a.basis.cashflowMonat, 0, 1e-9);
  assertFalse(a.status.basis.cashflow, 'exakt 0 €');
});
test('Faktor genau 20 gilt als nicht erfüllt', () => {
  const a = core.analyse({ ...BEISPIEL, kaufpreis: 240000, kaltmiete: 1000 });
  assertClose(a.basis.kaufpreisfaktor, 20.0, 1e-9);
  assertFalse(a.status.basis.kaufpreisfaktor, 'exakt 20');
});

// 5) 10-%-Preisnachlass
test('Szenario-Kaufpreis = 270.000 €, Rendite 6,67 %, Faktor 15,00', () => {
  const a = core.analyse(BEISPIEL);
  assertClose(a.szenario.kaufpreis, 270000, 1e-9);
  assertClose(a.szenario.bruttoRendite, 18000 / 270000 * 100, 1e-9);
  assertClose(a.szenario.kaufpreisfaktor, 15.0, 1e-9);
});
test('Szenario lässt Miete und Kostenpauschale unverändert', () => {
  const a = core.analyse(BEISPIEL);
  assertClose(a.szenario.kaltmiete, a.basis.kaltmiete, 1e-9);
  assertClose(a.szenario.pauschaleKostenMonat, a.basis.pauschaleKostenMonat, 1e-9);
});

// 6) Feste Darlehenssumme bleibt im Szenario unverändert
test('Fester Darlehensbetrag im Szenario unverändert (270.000 €)', () => {
  const a = core.analyse(BEISPIEL);
  assertEqual(a.finanzierungsart, core.FINANZIERUNGS_BETRAG);
  assertClose(a.szenario.darlehen, 270000, 1e-9);
  assertClose(a.vergleich.darlehen.absolut, 0, 1e-9);
});

// 7) Prozentualer Finanzierungsanteil skaliert im Szenario
test('Prozentualer Finanzierungsanteil (90 %) skaliert im Szenario', () => {
  const a = core.analyse({ ...BEISPIEL, finanzierungsart: core.FINANZIERUNGS_ANTEIL, finanzierungsanteil: 90 });
  assertClose(a.basis.darlehen, 270000, 1e-9, 'Basis-Darlehen');
  assertClose(a.szenario.darlehen, 243000, 1e-9, 'Szenario-Darlehen');
  assertClose(a.szenario.rateMonat, 243000 * 0.06 / 12, 1e-9, 'Szenario-Rate');
  assertClose(a.vergleich.darlehen.absolut, -27000, 1e-9);
});

// 8) Eingabevalidierung
test('Validierung: Kaufpreis 0, negative Kaltmiete, negativer Zins, fehlende Pflichtfelder', () => {
  const zero = core.analyse({ ...BEISPIEL, kaufpreis: 0 });
  assertFalse(zero.ok);
  assertTrue(!!zero.errors.kaufpreis);

  const negative = core.analyse({ ...BEISPIEL, kaltmiete: -100 });
  assertFalse(negative.ok);
  assertTrue(!!negative.errors.kaltmiete);

  const negZins = core.analyse({ ...BEISPIEL, zins: -1 });
  assertFalse(negZins.ok);
  assertTrue(!!negZins.errors.zins);

  const missing = core.analyse({ kaufpreis: 300000 });
  assertFalse(missing.ok);
  assertTrue(!!missing.errors.kaltmiete && !!missing.errors.zins && !!missing.errors.tilgung);

  const badAnteil = core.analyse({ ...BEISPIEL, finanzierungsart: core.FINANZIERUNGS_ANTEIL, finanzierungsanteil: 150 });
  assertFalse(badAnteil.ok);
  assertTrue(!!badAnteil.errors.finanzierungsanteil);
});

// 9) Vollständiger Schnellcheck – bestanden und nicht bestanden
test('Schnellcheck bestanden (alle drei Kriterien erfüllt)', () => {
  const a = core.analyse({ kaufpreis: 200000, kaltmiete: 1000, zins: 3, tilgung: 1,
    finanzierungsart: core.FINANZIERUNGS_ANTEIL, finanzierungsanteil: 50 });
  assertTrue(a.ok);
  assertTrue(a.status.basis.bruttoRendite && a.status.basis.cashflow && a.status.basis.kaufpreisfaktor);
  assertTrue(a.status.basis.bestanden);
  assertEqual(a.status.basis.text, 'Schnellcheck bestanden');
});
test('Schnellcheck nicht bestanden (Cashflow negativ)', () => {
  const a = core.analyse(BEISPIEL);
  assertFalse(a.status.basis.bestanden);
  assertEqual(a.status.basis.text, 'Schnellcheck nicht bestanden');
});

// Zusatz: Kostenpauschale zentral und korrekt angewandt
test('Kostenpauschale = 20 % der Kaltmiete', () => {
  assertEqual(core.PAUSCHALE_KOSTEN_PROZENT, 20);
  const a = core.analyse(BEISPIEL);
  assertClose(a.basis.pauschaleKostenMonat, a.basis.kaltmiete * 0.20, 1e-9);
  assertClose(a.basis.pauschaleKostenProzent, 20, 1e-9);
  // Cashflow = Kaltmiete − Pauschale − Rate
  assertClose(a.basis.cashflowMonat, a.basis.kaltmiete - a.basis.pauschaleKostenMonat - a.basis.rateMonat, 1e-9);
});

console.log('\n' + passed + ' bestanden, ' + failed + ' fehlgeschlagen.');
process.exit(failed === 0 ? 0 : 1);
