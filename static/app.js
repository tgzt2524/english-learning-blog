/**
 * English Learning Blog — Social Features JS
 */
(function () {
  'use strict';

  // ── Theme Toggle ────────────────────────────────────────────────
  const themeToggle = document.getElementById('themeToggle');
  const html = document.documentElement;
  if (themeToggle) {
    const icon = themeToggle.querySelector('i');
    const saved = localStorage.getItem('theme');
    if (saved) {
      html.setAttribute('data-theme', saved);
      if (icon) icon.className = saved === 'dracula' ? 'fa-solid fa-sun text-lg' : 'fa-solid fa-moon text-lg';
    }
    themeToggle.addEventListener('click', () => {
      const next = html.getAttribute('data-theme') === 'dracula' ? 'cupcake' : 'dracula';
      html.setAttribute('data-theme', next);
      localStorage.setItem('theme', next);
      if (icon) icon.className = next === 'dracula' ? 'fa-solid fa-sun text-lg' : 'fa-solid fa-moon text-lg';
    });
  }

  // ── Toast auto-dismiss ───────────────────────────────────────────
  document.querySelectorAll('.toast .alert').forEach(alert => {
    setTimeout(() => {
      alert.style.opacity = '0'; alert.style.transform = 'translateX(20px)';
      alert.style.transition = 'opacity 0.3s, transform 0.3s';
      setTimeout(() => alert.remove(), 300);
    }, 4000);
  });

})();
