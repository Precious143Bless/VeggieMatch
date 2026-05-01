// timer.js — countdown timers + auto-remove expired cards + expiry warning SMS

(function () {
  // Track which post IDs have already had their warning SMS fired this session
  const _warned = new Set();

  function formatTime(seconds) {
    if (seconds <= 0) return 'Expired';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    if (h > 0) return `${h}h ${m}m`;
    if (m > 0) return `${m}m ${s}s`;
    return `${s}s`;
  }

  function csrf() {
    const m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? m[1] : '';
  }

  /**
   * Fire a one-time expiry warning SMS for a post.
   * The server guards against double-sends via expiry_notified flag.
   */
  function fireExpiryWarning(postId) {
    if (_warned.has(postId)) return;
    _warned.add(postId);
    fetch(`/post/${postId}/notify-expiry/`, {
      method: 'POST',
      headers: { 'X-CSRFToken': csrf() },
    }).catch(() => {}); // fire-and-forget
  }

  function tick() {
    const now = Date.now();

    document.querySelectorAll('.vm-timer[data-expiry]').forEach(el => {
      const expiry  = new Date(el.dataset.expiry).getTime();
      const seconds = Math.max(0, Math.floor((expiry - now) / 1000));

      // Total listing duration (seconds) derived from created_at → expiry_time
      const created   = el.dataset.created ? new Date(el.dataset.created).getTime() : 0;
      const totalSecs = created ? Math.round((expiry - created) / 1000) : 0;

      // Warning threshold: 30 min for normal listings, 30 sec for listings ≤ 1 min
      const warnAt = totalSecs > 0 && totalSecs <= 60 ? 30 : 1800;

      el.textContent = formatTime(seconds);

      // ── Colour urgency ────────────────────────────────────────────────────
      if (seconds <= 0) {
        el.style.color      = '#c62828';
        el.style.fontWeight = '700';
      } else if (seconds <= 30) {
        el.style.color      = '#c62828';
        el.style.fontWeight = '700';
        el.style.animation  = 'vmTimerPulse 0.8s ease-in-out infinite';
      } else if (seconds < 300) {   // < 5 mins
        el.style.color      = '#e65100';
        el.style.fontWeight = '700';
        el.style.animation  = '';
      } else if (seconds < 1800) {  // < 30 mins
        el.style.color      = '#f57c00';
        el.style.fontWeight = '';
        el.style.animation  = '';
      } else {
        el.style.color      = '';
        el.style.fontWeight = '';
        el.style.animation  = '';
      }

      // ── Fire expiry warning SMS once when threshold is crossed ────────────
      const postId = el.dataset.postId;
      if (postId && seconds > 0 && seconds <= warnAt) {
        fireExpiryWarning(postId);
      }

      // ── Auto-remove the card when expired (active listings only) ──────────
      if (seconds <= 0) {
        const card = el.closest('.vm-post-card');
        if (card) {
          card.style.transition = 'opacity 1.2s';
          card.style.opacity    = '0';
          setTimeout(() => {
            card.remove();
            const pill = document.getElementById('countPill');
            if (pill) pill.textContent = document.querySelectorAll('.vm-post-card').length;
          }, 1200);
        }
      }
    });
  }

  tick();
  setInterval(tick, 1000);
})();
