// NextGen PDF — Firebase Console & Analytics Integration
(function () {
  const config = window.FIREBASE_CONFIG;
  if (!config || !config.apiKey) {
    console.log('[Firebase] Unconfigured. Fill in FIREBASE_CONFIG in js/config.js to enable Firebase Console tracking.');
    return;
  }

  // Load Firebase App & Analytics SDK v10 (Modular via ESM / Script imports)
  const firebaseAppScript = document.createElement('script');
  firebaseAppScript.type = 'module';
  firebaseAppScript.textContent = `
    import { initializeApp } from 'https://www.gstatic.com/firebasejs/10.9.0/firebase-app.js';
    import { getAnalytics, logEvent } from 'https://www.gstatic.com/firebasejs/10.9.0/firebase-analytics.js';
    import { getPerformance } from 'https://www.gstatic.com/firebasejs/10.9.0/firebase-performance.js';

    try {
      const app = initializeApp(window.FIREBASE_CONFIG);
      const analytics = getAnalytics(app);
      const perf = getPerformance(app);

      window.nextgenAnalytics = { app, analytics, perf, logEvent: (name, params) => logEvent(analytics, name, params) };
      console.log('[Firebase] Successfully initialized Firebase Console & Analytics.');
      logEvent(analytics, 'page_view', { page_title: document.title, page_location: window.location.href });
    } catch (err) {
      console.error('[Firebase] Initialization error:', err);
    }
  `;
  document.head.appendChild(firebaseAppScript);
})();
