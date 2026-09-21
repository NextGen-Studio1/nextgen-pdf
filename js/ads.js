// NextGen PDF — Google AdSense & Monetization Integration
(function () {
  const adsConfig = window.ADSENSE_CONFIG || {};
  if (!adsConfig.enabled) return;

  const publisherId = adsConfig.publisherId ? adsConfig.publisherId.trim() : '';

  // Inject AdSense Script if Publisher ID is configured
  if (publisherId) {
    const adScript = document.createElement('script');
    adScript.async = true;
    adScript.src = `https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${publisherId}`;
    adScript.crossOrigin = 'anonymous';
    document.head.appendChild(adScript);
  }

  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.ad-container').forEach(container => {
      const slotId = container.dataset.adSlot || '1234567890';
      const adFormat = container.dataset.adFormat || 'auto';

      if (publisherId) {
        container.innerHTML = `
          <div class="ad-label">ADVERTISEMENT</div>
          <ins class="adsbygoogle"
               style="display:block"
               data-ad-client="${publisherId}"
               data-ad-slot="${slotId}"
               data-ad-format="${adFormat}"
               data-full-width-responsive="true"></ins>
        `;
        try {
          (window.adsbygoogle = window.adsbygoogle || []).push({});
        } catch (e) {
          console.warn('[AdSense] Slot push notice:', e);
        }
      } else if (adsConfig.testMode) {
        container.innerHTML = `
          <div class="ad-placeholder">
            <span class="ad-label">ADVERTISEMENT PLACEHOLDER</span>
            <div class="ad-preview-text">Google AdSense Banner Slot (${adFormat})</div>
            <small>Set <code>publisherId</code> in <code>js/config.js</code> to display live ads.</small>
          </div>
        `;
      }
    });
  });
})();
