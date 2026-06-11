/**
 * English Learning Blog — Frontend Magic
 * Scroll progress, dark mode, micro-interactions
 */

(function () {
  'use strict';

  // ── Scroll Progress Bar ──────────────────────────────────────────────
  const progressBar = document.getElementById('scrollProgress');
  if (progressBar) {
    window.addEventListener('scroll', function () {
      const scrollTop = window.scrollY;
      const docHeight = document.documentElement.scrollHeight - window.innerHeight;
      const progress = docHeight > 0 ? (scrollTop / docHeight) * 100 : 0;
      progressBar.style.width = progress + '%';
    });
  }

  // ── Dark Mode Toggle ──────────────────────────────────────────────────
  const themeToggle = document.getElementById('themeToggle');
  if (themeToggle) {
    // Load saved preference
    const saved = localStorage.getItem('theme');
    if (saved === 'dark') {
      document.body.classList.add('dark');
      themeToggle.textContent = '☀️';
    }

    themeToggle.addEventListener('click', function () {
      document.body.classList.toggle('dark');
      const isDark = document.body.classList.contains('dark');
      localStorage.setItem('theme', isDark ? 'dark' : 'light');
      themeToggle.textContent = isDark ? '☀️' : '🌙';

      // Bouncy animation
      themeToggle.style.transform = 'scale(1.3) rotate(20deg)';
      setTimeout(function () {
        themeToggle.style.transform = '';
      }, 200);
    });
  }

  // ── Scroll-triggered reveal (fallback for animation-timeline) ────────
  if (!CSS.supports('animation-timeline: view()')) {
    const observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.style.opacity = '1';
            entry.target.style.transform = 'translateY(0) rotate(0deg)';
          }
        });
      },
      { threshold: 0.1 }
    );

    document.querySelectorAll('.post-card, .comment-item').forEach(function (el) {
      el.style.opacity = '0';
      el.style.transform = 'translateY(30px)';
      el.style.transition = 'opacity 0.5s ease-out, transform 0.5s ease-out';
      observer.observe(el);
    });
  }

  // ── Logo Easter Egg ──────────────────────────────────────────────────
  const logo = document.querySelector('.logo');
  if (logo) {
    const emojis = ['📚', '📖', '📝', '🎓', '✨', '💡', '🔤', '🌍'];
    let clicks = 0;
    logo.addEventListener('click', function (e) {
      clicks++;
      if (clicks >= 5) {
        clicks = 0;
        const randomEmoji = emojis[Math.floor(Math.random() * emojis.length)];
        const oldText = logo.textContent;
        logo.textContent = randomEmoji + ' ' + oldText.slice(2);
        logo.style.transform = 'scale(1.2) rotate(5deg)';
        setTimeout(function () {
          logo.style.transform = '';
        }, 300);
      }
    });
  }

  // ── Flash message auto-dismiss ────────────────────────────────────────
  document.querySelectorAll('.flash').forEach(function (flash) {
    setTimeout(function () {
      flash.style.opacity = '0';
      flash.style.transform = 'translateY(-10px)';
      flash.style.transition = 'opacity 0.3s, transform 0.3s';
      setTimeout(function () {
        if (flash.parentNode) flash.parentNode.removeChild(flash);
      }, 300);
    }, 4000);
  });

  // ── Random card tilt on homepage ─────────────────────────────────────
  document.querySelectorAll('.post-card').forEach(function (card, i) {
    // Add slight random rotation (keeps within the CSS-defined rotation)
    var tilt = (Math.random() - 0.5) * 1.2;
    card.style.transform = 'rotate(' + tilt + 'deg)';
  });

})();
