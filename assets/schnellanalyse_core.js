/* Schnellanalyse – reine, testbare Berechnungslogik.
 * Keine DOM-Abhängigkeit, kein Netzzugriff, keine Speicherung.
 * Formeln identisch zur bestehenden Logik in tools/db_manager.py / tools/rechenkern.py:
 *   Bruttomietrendite = jährliche Kaltmiete / Kaufpreis
 *   Kaufpreisfaktor  = Kaufpreis / jährliche Kaltmiete
 *   Rate             = Darlehen * (Zins + Tilgung) / 100 / 12
 */
(function (root) {
  'use strict';

  // Zentrale Zielwerte – nur hier definiert, nirgendwo sonst hartcodiert.
  var SCHWELLEN = Object.freeze({
    bruttoRenditeMin: 5.0,   // Bruttorendite muss GRÖSSER als 5 % sein
    cashflowMin: 0.0,        // Cashflow muss GRÖSSER als 0 € sein
    kaufpreisfaktorMax: 20.0 // Kaufpreisfaktor muss KLEINER als 20 sein
  });

  var SZENARIO_FAKTOR = 0.90;        // Verhandlungsszenario: Kaufpreis 10 % niedriger
  var FINANZIERUNGS_ANTEIL = 'anteil';
  var FINANZIERUNGS_BETRAG = 'betrag';

  function num(value) {
    if (value === null || value === undefined || value === '') return null;
    var parsed = parseFloat(String(value).replace(',', '.').replace(/\s/g, ''));
    return isFinite(parsed) ? parsed : null;
  }

  // Eingaben normalisieren und validieren. Liefert { ok, errors, values }.
  function validate(raw) {
    var input = raw || {};
    var errors = {};
    var values = {
      kaufpreis: num(input.kaufpreis),
      kaltmiete: num(input.kaltmiete),
      nichtUmlagefaehig: num(input.nichtUmlagefaehig),
      ruecklage: num(input.ruecklage),
      sonstigeKosten: num(input.sonstigeKosten),
      zins: num(input.zins),
      tilgung: num(input.tilgung),
      finanzierungsart: input.finanzierungsart === FINANZIERUNGS_BETRAG ? FINANZIERUNGS_BETRAG : FINANZIERUNGS_ANTEIL,
      darlehen: num(input.darlehen),
      finanzierungsanteil: num(input.finanzierungsanteil)
    };
    // Optional: leere optionale Kostenfelder gelten als 0 (bestehende Tool-Logik).
    values.nichtUmlagefaehig = values.nichtUmlagefaehig === null ? 0 : values.nichtUmlagefaehig;
    values.ruecklage = values.ruecklage === null ? 0 : values.ruecklage;
    values.sonstigeKosten = values.sonstigeKosten === null ? 0 : values.sonstigeKosten;

    if (values.kaufpreis === null) errors.kaufpreis = 'Kaufpreis ist ein Pflichtfeld.';
    else if (values.kaufpreis <= 0) errors.kaufpreis = 'Kaufpreis muss größer als 0 sein.';

    if (values.kaltmiete === null) errors.kaltmiete = 'Kaltmiete ist ein Pflichtfeld.';
    else if (values.kaltmiete < 0) errors.kaltmiete = 'Kaltmiete darf nicht negativ sein.';

    if (values.zins === null) errors.zins = 'Sollzinssatz ist ein Pflichtfeld.';
    else if (values.zins < 0) errors.zins = 'Sollzinssatz darf nicht negativ sein.';

    if (values.tilgung === null) errors.tilgung = 'Anfängliche Tilgung ist ein Pflichtfeld.';
    else if (values.tilgung < 0) errors.tilgung = 'Tilgung darf nicht negativ sein.';

    if (values.nichtUmlagefaehig < 0) errors.nichtUmlagefaehig = 'Nicht umlagefähige Kosten dürfen nicht negativ sein.';
    if (values.ruecklage < 0) errors.ruecklage = 'Rücklage darf nicht negativ sein.';
    if (values.sonstigeKosten < 0) errors.sonstigeKosten = 'Sonstige Kosten dürfen nicht negativ sein.';

    if (values.finanzierungsart === FINANZIERUNGS_ANTEIL) {
      if (values.finanzierungsanteil === null) errors.finanzierungsanteil = 'Finanzierungsanteil ist ein Pflichtfeld.';
      else if (values.finanzierungsanteil < 0 || values.finanzierungsanteil > 100) errors.finanzierungsanteil = 'Finanzierungsanteil muss zwischen 0 und 100 % liegen.';
    } else {
      if (values.darlehen === null) errors.darlehen = 'Darlehensbetrag ist ein Pflichtfeld.';
      else if (values.darlehen < 0) errors.darlehen = 'Darlehensbetrag darf nicht negativ sein.';
    }

    return {
      ok: Object.keys(errors).length === 0,
      errors: errors,
      values: values
    };
  }

  // Darlehen je Szenario. Fester Betrag bleibt immer unverändert; ein
  // prozentualer Anteil skaliert mit dem (ggf. reduzierten) Kaufpreis.
  function darlehenFuer(values, kaufpreis) {
    if (values.finanzierungsart === FINANZIERUNGS_BETRAG) return Math.max(0, values.darlehen || 0);
    return Math.max(0, kaufpreis * (values.finanzierungsanteil || 0) / 100);
  }

  // Reine Kennzahlenberechnung für EINEN Kaufpreis.
  function berechne(values, kaufpreis) {
    var kaltmiete = values.kaltmiete || 0;
    var nichtUmlagefaehig = values.nichtUmlagefaehig || 0;
    var ruecklage = values.ruecklage || 0;
    var sonstigeKosten = values.sonstigeKosten || 0;
    var zins = values.zins || 0;
    var tilgung = values.tilgung || 0;

    var jahresKaltmiete = kaltmiete * 12;
    var bruttoRendite = kaufpreis > 0 ? jahresKaltmiete / kaufpreis * 100 : null;
    var kaufpreisfaktor = jahresKaltmiete > 0 ? kaufpreis / jahresKaltmiete : null;

    var darlehen = darlehenFuer(values, kaufpreis);
    var rate = darlehen * (zins + tilgung) / 100 / 12;
    var zinsMonat = darlehen * zins / 100 / 12;
    var tilgungMonat = darlehen * tilgung / 100 / 12;
    var cashflow = kaltmiete - nichtUmlagefaehig - ruecklage - rate - sonstigeKosten;

    return {
      kaufpreis: kaufpreis,
      kaltmiete: kaltmiete,
      jahresKaltmiete: jahresKaltmiete,
      bruttoRendite: bruttoRendite,
      kaufpreisfaktor: kaufpreisfaktor,
      darlehen: darlehen,
      zinsMonat: zinsMonat,
      tilgungMonat: tilgungMonat,
      rateMonat: rate,
      cashflowMonat: cashflow,
      cashflowJahr: cashflow * 12
    };
  }

  // Status einer einzelnen Kennzahl gegen die zentralen Zielwerte.
  function statusBruttoRendite(wert) {
    if (wert === null) return null;
    return wert > SCHWELLEN.bruttoRenditeMin;
  }
  function statusCashflow(wert) {
    if (wert === null) return null;
    return wert > SCHWELLEN.cashflowMin;
  }
  function statusKaufpreisfaktor(wert) {
    if (wert === null) return null;
    return wert < SCHWELLEN.kaufpreisfaktorMax;
  }

  function statusFuer(ergebnis) {
    var rendite = statusBruttoRendite(ergebnis.bruttoRendite);
    var cashflow = statusCashflow(ergebnis.cashflowMonat);
    var faktor = statusKaufpreisfaktor(ergebnis.kaufpreisfaktor);
    var alle = rendite === true && cashflow === true && faktor === true;
    return {
      bruttoRendite: rendite,
      cashflow: cashflow,
      kaufpreisfaktor: faktor,
      bestanden: alle,
      text: alle ? 'Schnellcheck bestanden' : 'Schnellcheck nicht bestanden'
    };
  }

  function delta(basis, szenario) {
    if (basis === null || szenario === null) return { absolut: null, prozent: null };
    return {
      absolut: szenario - basis,
      prozent: basis !== 0 ? (szenario - basis) / basis * 100 : null
    };
  }

  // Vollständige Schnellanalyse: Basisvariante + 10-%-Szenario + Vergleich.
  function analyse(raw) {
    var check = validate(raw);
    if (!check.ok) return { ok: false, errors: check.errors, values: check.values };

    var v = check.values;
    var basis = berechne(v, v.kaufpreis);
    var szenarioKaufpreis = v.kaufpreis * SZENARIO_FAKTOR;
    var szenario = berechne(v, szenarioKaufpreis);

    return {
      ok: true,
      errors: {},
      values: v,
      schwellen: SCHWELLEN,
      finanzierungsart: v.finanzierungsart,
      szenarioFaktor: SZENARIO_FAKTOR,
      basis: basis,
      szenario: szenario,
      status: { basis: statusFuer(basis), szenario: statusFuer(szenario) },
      vergleich: {
        bruttoRendite: delta(basis.bruttoRendite, szenario.bruttoRendite),
        kaufpreisfaktor: delta(basis.kaufpreisfaktor, szenario.kaufpreisfaktor),
        cashflowMonat: delta(basis.cashflowMonat, szenario.cashflowMonat),
        darlehen: delta(basis.darlehen, szenario.darlehen),
        kaufpreis: delta(basis.kaufpreis, szenario.kaufpreis)
      }
    };
  }

  var api = {
    SCHWELLEN: SCHWELLEN,
    SZENARIO_FAKTOR: SZENARIO_FAKTOR,
    FINANZIERUNGS_ANTEIL: FINANZIERUNGS_ANTEIL,
    FINANZIERUNGS_BETRAG: FINANZIERUNGS_BETRAG,
    validate: validate,
    berechne: berechne,
    statusFuer: statusFuer,
    analyse: analyse
  };

  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (root) root.Schnellanalyse = api;
})(typeof window !== 'undefined' ? window : null);
