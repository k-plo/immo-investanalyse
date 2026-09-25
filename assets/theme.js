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
      button.textContent = mode === 'dark' ? '☀ Hellmodus' : '☾ Dunkelmodus';
      button.setAttribute('aria-label', mode === 'dark' ? 'Hellmodus aktivieren' : 'Dunkelmodus aktivieren');
      button.setAttribute('aria-pressed', String(mode === 'dark'));
    }
  };
  apply(choice || (system.matches ? 'dark' : 'light'));
  document.addEventListener('DOMContentLoaded', () => {
    const controls = document.createElement('div');
    controls.className = 'appearance-controls';
    button = document.createElement('button');
    button.type = 'button';
    button.className = 'theme-toggle';
    button.addEventListener('click', () => {
      choice = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
      try { localStorage.setItem(key, choice); } catch (_) {}
      apply(choice);
    });
    controls.append(button);
    const print = document.querySelector('body > .print-btn');
    if (print) controls.append(print);
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
