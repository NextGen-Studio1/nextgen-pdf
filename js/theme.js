/**
 * NextGen PDF — Theme Manager
 * Unifies Dark/Light mode state management, UI icon updates,
 * local storage persistence, and cross-tab synchronization.
 */
(function () {
  'use strict';

  const STORAGE_KEY = 'nextgen-theme';
  const ALT_STORAGE_KEY = 'theme';

  function getSavedTheme() {
    return localStorage.getItem(STORAGE_KEY) || localStorage.getItem(ALT_STORAGE_KEY);
  }

  function getSystemThemePreference() {
    return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches
      ? 'dark'
      : 'light';
  }

  function getCurrentTheme() {
    return getSavedTheme() || getSystemThemePreference();
  }

  function applyTheme(theme) {
    const validTheme = theme === 'dark' ? 'dark' : 'light';
    const root = document.documentElement;

    root.setAttribute('data-theme', validTheme);
    if (validTheme === 'dark') {
      root.classList.add('dark');
      root.classList.remove('light');
    } else {
      root.classList.add('light');
      root.classList.remove('dark');
    }

    updateToggleButtons(validTheme);
    return validTheme;
  }

  function updateToggleButtons(theme) {
    const isDark = theme === 'dark';
    const icon = isDark ? '☀' : '☾';
    const label = isDark ? 'Switch to Light Mode' : 'Switch to Dark Mode';

    const buttons = document.querySelectorAll(
      '[data-theme-toggle], .theme-btn, #theme-toggle, .theme-toggle-btn'
    );
    buttons.forEach((btn) => {
      btn.textContent = icon;
      btn.setAttribute('aria-label', label);
      btn.setAttribute('title', label);
    });
  }

  function setTheme(theme) {
    const activeTheme = applyTheme(theme);
    try {
      localStorage.setItem(STORAGE_KEY, activeTheme);
      localStorage.setItem(ALT_STORAGE_KEY, activeTheme);
    } catch (e) {
      console.warn('Storage permission issue setting theme:', e);
    }
  }

  function toggleTheme() {
    const current = getCurrentTheme();
    const next = current === 'dark' ? 'light' : 'dark';
    setTheme(next);
  }

  // Immediate execution to prevent Flash of Unstyled Text/Theme (FOUC)
  applyTheme(getCurrentTheme());

  // Attach event listeners when DOM is interactive
  function initListeners() {
    updateToggleButtons(getCurrentTheme());

    document.addEventListener('click', function (e) {
      const toggleBtn = e.target.closest(
        '[data-theme-toggle], .theme-btn, #theme-toggle, .theme-toggle-btn'
      );
      if (toggleBtn) {
        e.preventDefault();
        toggleTheme();
      }
    });

    // Sync state across multiple tabs
    window.addEventListener('storage', function (e) {
      if (e.key === STORAGE_KEY || e.key === ALT_STORAGE_KEY) {
        if (e.newValue) applyTheme(e.newValue);
      }
    });

    // Respond to system preference changes if no manual override
    if (window.matchMedia) {
      window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function (e) {
        if (!getSavedTheme()) {
          applyTheme(e.matches ? 'dark' : 'light');
        }
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initListeners);
  } else {
    initListeners();
  }

  // Global API Exposure
  window.NextGenTheme = {
    getTheme: getCurrentTheme,
    setTheme: setTheme,
    toggleTheme: toggleTheme,
    apply: applyTheme,
  };
})();
