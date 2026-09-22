/* NextGen PDF — Shared Components & UI Utilities */

// 1. Toast Notification Manager
const Toast = {
  container: null,

  init() {
    if (!this.container) {
      this.container = document.createElement('div');
      this.container.className = 'toast-container';
      document.body.appendChild(this.container);
    }
  },

  show({ message, type = 'info', duration = 3500 }) {
    this.init();
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    const icons = {
      success: '✓',
      error: '✕',
      warning: '⚠️',
      info: 'ℹ️'
    };

    toast.innerHTML = `
      <span>${icons[type] || 'ℹ️'}</span>
      <span>${message}</span>
    `;

    this.container.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      setTimeout(() => toast.remove(), 200);
    }, duration);
  }
};

// 2. Modal Controller
const Modal = {
  open(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
      modal.classList.add('active');
    }
  },

  close(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
      modal.classList.remove('active');
    }
  }
};

// 3. Theme Toggle Manager
const ThemeManager = {
  init() {
    const savedTheme = localStorage.getItem('nextgen_theme') || 'light';
    document.documentElement.setAttribute('data-theme', savedTheme);
    this.updateToggleIcons(savedTheme);

    document.querySelectorAll('[data-theme-toggle]').forEach(btn => {
      btn.addEventListener('click', () => this.toggle());
    });
  },

  toggle() {
    const current = document.documentElement.getAttribute('data-theme');
    const next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('nextgen_theme', next);
    this.updateToggleIcons(next);
  },

  updateToggleIcons(theme) {
    document.querySelectorAll('[data-theme-toggle]').forEach(btn => {
      btn.textContent = theme === 'dark' ? '☀️' : '🌙';
    });
  }
};

// 4. MegaMenu Dropdown Toggle
const MegaMenu = {
  init() {
    const toggles = document.querySelectorAll('[data-mega-toggle]');
    toggles.forEach(toggle => {
      toggle.addEventListener('click', (e) => {
        e.stopPropagation();
        const menu = toggle.nextElementSibling || document.querySelector('.tools-mega-menu');
        if (menu) {
          menu.classList.toggle('is-active');
        }
      });
    });

    document.addEventListener('click', () => {
      document.querySelectorAll('.tools-mega-menu').forEach(m => m.classList.remove('is-active'));
    });
  }
};

document.addEventListener('DOMContentLoaded', () => {
  ThemeManager.init();
  MegaMenu.init();
});
