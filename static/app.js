/**
 * English Learning Blog — Frontend Logic
 * Theme toggle, toast auto-dismiss, post interactions
 */

(function () {
  'use strict';

  // ── Theme Toggle (daisyUI cupcake ↔ dracula) ─────────────────────────
  const themeToggle = document.getElementById('themeToggle');
  const html = document.documentElement;
  const icon = themeToggle ? themeToggle.querySelector('i') : null;

  // Load saved preference
  const saved = localStorage.getItem('theme');
  if (saved) {
    html.setAttribute('data-theme', saved);
    if (icon) {
      icon.className = saved === 'dracula'
        ? 'fa-solid fa-sun text-lg'
        : 'fa-solid fa-moon text-lg';
    }
  }

  if (themeToggle && icon) {
    themeToggle.addEventListener('click', function () {
      const current = html.getAttribute('data-theme');
      const next = current === 'dracula' ? 'cupcake' : 'dracula';
      html.setAttribute('data-theme', next);
      localStorage.setItem('theme', next);
      icon.className = next === 'dracula'
        ? 'fa-solid fa-sun text-lg'
        : 'fa-solid fa-moon text-lg';
    });
  }

  // ── Toast auto-dismiss ─────────────────────────────────────────────────
  document.querySelectorAll('.toast .alert').forEach(function (alert) {
    setTimeout(function () {
      alert.style.opacity = '0';
      alert.style.transform = 'translateX(20px)';
      alert.style.transition = 'opacity 0.3s, transform 0.3s';
      setTimeout(function () {
        if (alert.parentNode) alert.remove();
      }, 300);
    }, 4000);
  });

})();
