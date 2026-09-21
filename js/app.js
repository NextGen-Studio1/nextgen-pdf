const root = document.documentElement;
const saved = localStorage.getItem('nextgen-theme');
if (saved) root.dataset.theme = saved;

function updateThemeIcon() {
  const b = document.querySelector('[data-theme-toggle]');
  if (b) b.textContent = root.dataset.theme === 'dark' ? '☀' : '☾';
}

document.addEventListener('DOMContentLoaded', () => {
  updateThemeIcon();
  document.querySelector('[data-theme-toggle]')?.addEventListener('click', () => {
    root.dataset.theme = root.dataset.theme === 'dark' ? 'light' : 'dark';
    localStorage.setItem('nextgen-theme', root.dataset.theme);
    updateThemeIcon();
  });

  const mobBtn = document.querySelector('[data-mobile-toggle]');
  const navMenu = document.querySelector('.nav nav');
  mobBtn?.addEventListener('click', () => {
    navMenu?.classList.toggle('is-open');
  });
});
