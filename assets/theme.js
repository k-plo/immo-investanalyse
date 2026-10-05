/* Presentation only: separate key, no access to property state or sync. */
(() => {
  const key = 'immo-dashboard-theme';
  const system = window.matchMedia('(prefers-color-scheme: dark)');
  let choice = null;
  try { choice = localStorage.getItem(key); } catch (_) {}
  if (!['light', 'dark'].includes(choice)) choice = null;
  let button;
  const apply = mode => {
    document.documentElement.dataset.theme = mode;
    if (button) {
      const icon = mode === 'dark' ? '☀' : '☾';
      const label = mode === 'dark' ? 'Hellmodus aktivieren' : 'Dunkelmodus aktivieren';
      button.textContent = icon;
      button.setAttribute('aria-label', label);
      button.title = label;
      button.setAttribute('aria-pressed', String(mode === 'dark'));
    }
  };
  apply(choice || (system.matches ? 'dark' : 'light'));
  document.addEventListener('DOMContentLoaded', () => {
    button = document.createElement('button');
    button.type = 'button';
    button.className = 'theme-toggle';
    button.addEventListener('click', () => {
      choice = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
      try { localStorage.setItem(key, choice); } catch (_) {}
      apply(choice);
    });
    // Portfolio: Dunkelmodus-Schalter sitzt im festen Kopfbereich neben Logo und Überschrift.
    const host = document.getElementById('pfControls');
    if (host) {
      host.append(button);
      apply(document.documentElement.dataset.theme);
      return;
    }
    const controls = document.createElement('div');
    controls.className = 'appearance-controls';
    controls.append(button);
    const print = document.querySelector('body > .print-btn');
    if (print) controls.append(print);
    const portfolio = document.querySelector('.toolbar button[onclick^="zumPortfolio"]');
    if (portfolio) {
      portfolio.classList.add('portfolio-button');
      controls.prepend(portfolio);
    }
    const brand = document.querySelector('body > .portfolio-brand');
    if (brand) {
      controls.classList.add('has-brand');
      controls.append(brand);
    }
    document.body.prepend(controls);
    apply(document.documentElement.dataset.theme);
  });
  system.addEventListener('change', event => { if (!choice) apply(event.matches ? 'dark' : 'light'); });
  window.addEventListener('storage', event => {
    if (event.key !== key) return;
    choice = ['light', 'dark'].includes(event.newValue) ? event.newValue : null;
    apply(choice || (system.matches ? 'dark' : 'light'));
  });
})();
