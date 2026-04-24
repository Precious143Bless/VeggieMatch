/**
 * VeggieMatch – Countdown Timer
 * Updates all .vm-timer elements with live countdowns.
 * Marks timers as "urgent" (red) when under 30 minutes.
 */
(function () {
  'use strict';

  function formatCountdown(ms) {
    if (ms <= 0) return 'Expired';

    const totalSec = Math.floor(ms / 1000);
    const hours    = Math.floor(totalSec / 3600);
    const minutes  = Math.floor((totalSec % 3600) / 60);
    const seconds  = totalSec % 60;

    if (hours > 0) {
      return `${hours}h ${String(minutes).padStart(2, '0')}m`;
    }
    return `${String(minutes).padStart(2, '0')}m ${String(seconds).padStart(2, '0')}s`;
  }

  function updateTimers() {
    const timers = document.querySelectorAll('.vm-timer[data-expiry]');
    const now    = Date.now();

    timers.forEach(function (el) {
      const expiry = new Date(el.dataset.expiry).getTime();
      const diff   = expiry - now;

      el.textContent = formatCountdown(diff);

      // Under 30 minutes → urgent styling
      if (diff <= 30 * 60 * 1000) {
        el.classList.add('urgent');
      } else {
        el.classList.remove('urgent');
      }
    });
  }

  // Run immediately then every second
  updateTimers();
  setInterval(updateTimers, 1000);
})();
