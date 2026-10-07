/* Schnellanalyse – reine, testbare Berechnungslogik.
 * Keine DOM-Abhängigkeit, kein Netzzugriff, keine Speicherung.
 * Formeln identisch zur bestehenden Logik in tools/db_manager.py / tools/rechenkern.py:
 *   Bruttomietrendite = jährliche Kaltmiete / Kaufpreis
 *   Kaufpreisfaktor  = Kaufpreis / jährliche Kaltmiete
 *   Darlehen         = Kaufpreis − Eigenkapital
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

  var SZENARIO_FAKTOR = 0.90;            // Verhandlungsszenario: Kaufpreis 10 % niedriger
  var PAUSCHALE_KOSTEN_PROZENT = 20.0;   // Pauschale für nicht umlagefähige Kosten, Rücklage und sonstige Kosten in % der Kaltmiete
  var EK_MODUS_ANTEIL = 'anteil';        // Eigenkapital als Prozent des Kaufpreises
  var EK_MODUS_BETRAG = 'betrag';        // Eigenkapital als fester Betrag

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
      zins: num(input.zins),
      tilgung: num(input.tilgung),
      ekModus: input.ekModus === EK_MODUS_BETRAG ? EK_MODUS_BETRAG : EK_MODUS_ANTEIL,
      ek: num(input.ek),
      ekAnteil: num(input.ekAnteil)
    };

    if (values.kaufpreis === null) errors.kaufpreis = 'Kaufpreis ist ein Pflichtfeld.';
    else if (values.kaufpreis <= 0) errors.kaufpreis = 'Kaufpreis muss größer als 0 sein.';

    if (values.kaltmiete === null) errors.kaltmiete = 'Kaltmiete ist ein Pflichtfeld.';
    else if (values.kaltmiete < 0) errors.kaltmiete = 'Kaltmiete darf nicht negativ sein.';

    if (values.zins === null) errors.zins = 'Sollzinssatz ist ein Pflichtfeld.';
    else if (values.zins < 0) errors.zins = 'Sollzinssatz darf nicht negativ sein.';

    if (values.tilgung === null) errors.tilgung = 'Anfängliche Tilgung ist ein Pflichtfeld.';
    else if (values.tilgung < 0) errors.tilgung = 'Tilgung darf nicht negativ sein.';

    if (values.ekModus === EK_MODUS_ANTEIL) {
      if (values.ekAnteil === null) errors.ekAnteil = 'Eigenkapital-Anteil ist ein Pflichtfeld.';
      else if (values.ekAnteil < 0 || values.ekAnteil > 100) errors.ekAnteil = 'Eigenkapital-Anteil muss zwischen 0 und 100 % liegen.';
    } else {
      if (values.ek === null) errors.ek = 'Eigenkapital ist ein Pflichtfeld.';
      else if (values.ek < 0) errors.ek = 'Eigenkapital darf nicht negativ sein.';
    }

    return {
      ok: Object.keys(errors).length === 0,
      errors: errors,
      values: values
    };
  }

  // Eigenkapital je Szenario. Fester Betrag bleibt unverändert; ein prozentualer
  // Anteil skaliert mit dem (ggf. reduzierten) Kaufpreis.
  function ekFuer(values, kaufpreis) {
    if (values.ekModus === EK_MODUS_BETRAG) return Math.max(0, values.ek || 0);
    return Math.max(0, kaufpreis * (values.ekAnteil || 0) / 100);
  }

  // Darlehen = Kaufpreis − Eigenkapital.
  function darlehenFuer(values, kaufpreis) {
    return Math.max(0, kaufpreis - ekFuer(values, kaufpreis));
  }

  // Reine Kennzahlenberechnung für EINEN Kaufpreis.
  function berechne(values, kaufpreis) {
    var kaltmiete = values.kaltmiete;
    var zins = values.zins;
    var tilgung = values.tilgung;

    var jahresKaltmiete = kaltmiete === null ? null : kaltmiete * 12;
    var bruttoRendite = kaufpreis > 0 && jahresKaltmiete !== null ? jahresKaltmiete / kaufpreis * 100 : null;
    var kaufpreisfaktor = jahresKaltmiete > 0 ? kaufpreis / jahresKaltmiete : null;

    var ekBekannt = (values.ekModus === EK_MODUS_BETRAG ? values.ek : values.ekAnteil) !== null;
    var ek = kaufpreis !== null && ekBekannt ? ekFuer(values, kaufpreis) : null;
    var darlehen = ek === null ? null : Math.max(0, kaufpreis - ek);
    var rate = darlehen === null || zins === null || tilgung === null ? null : darlehen * (zins + tilgung) / 100 / 12;
    var zinsMonat = darlehen === null || zins === null ? null : darlehen * zins / 100 / 12;
    var tilgungMonat = darlehen === null || tilgung === null ? null : darlehen * tilgung / 100 / 12;
    // Pauschale Kosten (nicht umlagefähig + Rücklage + sonstige) als % der Kaltmiete.
    var pauschaleKosten = kaltmiete === null ? null : kaltmiete * PAUSCHALE_KOSTEN_PROZENT / 100;
    var cashflow = kaltmiete === null || rate === null ? null : kaltmiete - pauschaleKosten - rate;

    return {
      kaufpreis: kaufpreis,
      kaltmiete: kaltmiete,
      jahresKaltmiete: jahresKaltmiete,
      bruttoRendite: bruttoRendite,
      kaufpreisfaktor: kaufpreis === null ? null : kaufpreisfaktor,
      pauschaleKostenProzent: PAUSCHALE_KOSTEN_PROZENT,
      pauschaleKostenMonat: pauschaleKosten,
      ek: ek,
      darlehen: darlehen,
      zinsMonat: zinsMonat,
      tilgungMonat: tilgungMonat,
      rateMonat: rate,
      cashflowMonat: cashflow,
      cashflowJahr: cashflow === null ? null : cashflow * 12
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
    var gesamt = [rendite, cashflow, faktor].indexOf(false) >= 0 ? 'nicht bestanden' : alle ? 'bestanden' : 'unvollständig';
    return {
      bruttoRendite: rendite,
      cashflow: cashflow,
      kaufpreisfaktor: faktor,
      bestanden: alle,
      gesamt: gesamt,
      text: 'Schnellcheck ' + gesamt
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
    if (!check.ok && !(raw && raw._teilanalyse)) return { ok: false, errors: check.errors, values: check.values };
    // Ungültig ist ebenso wenig berechenbar wie fehlend. Keine Null-Euro-Ersatzwerte.
    Object.keys(check.errors).forEach(function (key) { check.values[key] = null; });

    var v = check.values;
    var basis = berechne(v, v.kaufpreis);
    var szenarioKaufpreis = v.kaufpreis === null ? null : v.kaufpreis * SZENARIO_FAKTOR;
    var szenario = berechne(v, szenarioKaufpreis);

    return {
      ok: true,
      errors: {},
      values: v,
      schwellen: SCHWELLEN,
      ekModus: v.ekModus,
      szenarioFaktor: SZENARIO_FAKTOR,
      basis: basis,
      szenario: szenario,
      status: { basis: statusFuer(basis), szenario: statusFuer(szenario) },
      vergleich: {
        bruttoRendite: delta(basis.bruttoRendite, szenario.bruttoRendite),
        kaufpreisfaktor: delta(basis.kaufpreisfaktor, szenario.kaufpreisfaktor),
        cashflowMonat: delta(basis.cashflowMonat, szenario.cashflowMonat),
        ek: delta(basis.ek, szenario.ek),
        darlehen: delta(basis.darlehen, szenario.darlehen),
        kaufpreis: delta(basis.kaufpreis, szenario.kaufpreis)
      }
    };
  }

  var api = {
    SCHWELLEN: SCHWELLEN,
    SZENARIO_FAKTOR: SZENARIO_FAKTOR,
    PAUSCHALE_KOSTEN_PROZENT: PAUSCHALE_KOSTEN_PROZENT,
    EK_MODUS_ANTEIL: EK_MODUS_ANTEIL,
    EK_MODUS_BETRAG: EK_MODUS_BETRAG,
    validate: validate,
    berechne: berechne,
    statusFuer: statusFuer,
    analyse: analyse
  };

  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (root) root.Schnellanalyse = api;
})(typeof window !== 'undefined' ? window : null);
