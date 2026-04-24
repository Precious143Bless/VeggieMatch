// timer.js — countdown timers + auto-remove expired cards

(function () {
  function formatTime(seconds) {
    if (seconds <= 0) return 'Expired';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    if (h > 0) return `${h}h ${m}m`;
    if (m > 0) return `${m}m ${s}s`;
    return `${s}s`;
  }

  function tick() {
    const now = Date.now();
    document.querySelectorAll('.vm-timer[data-expiry]').forEach(el => {
      const expiry  = new Date(el.dataset.expiry).getTime();
      const seconds = Math.max(0, Math.floor((expiry - now) / 1000));
      el.textContent = formatTime(seconds);

      // Colour urgency
      if (seconds <= 0) {
        el.style.color = '#c62828';
      } else if (seconds < 300) {       // < 5 mins
        el.style.color = '#e65100';
        el.style.fontWeight = '700';
      } else if (seconds < 1800) {      // < 30 mins
        el.style.color = '#f57c00';
      }

      // Auto-remove the card when expired (home page active listings only)
      if (seconds <= 0) {
        const card = el.closest('.vm-post-card');
        if (card) {
          // Fade out then remove
          card.style.transition = 'opacity 1.2s';
          card.style.opacity    = '0';
          setTimeout(() => {
            card.remove();
            // Update the count pill if present
            const pill = document.getElementById('countPill');
            if (pill) {
              const remaining = document.querySelectorAll('.vm-post-card:not([style*="opacity: 0"])').length;
              pill.textContent = remaining;
            }
          }, 1200);
        }
      }
    });
  }

  // Run immediately then every second
  tick();
  setInterval(tick, 1000);
})();
