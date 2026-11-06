/* A primary mouse click completes the current entrance without activating a covered control. */
(function () {
  'use strict';
  var root = document.documentElement;
  var cssNames = new Set(['archive-rise-in', 'archive-soft-in', 'detail-rise-in']);
  function activeCss() {
    return document.getAnimations ? document.getAnimations().filter(function (animation) {
      return cssNames.has(animation.animationName) && animation.playState !== 'finished' && animation.playState !== 'idle';
    }) : [];
  }
  function hasEntrance() {
    var app = document.querySelector('.app');
    return root.classList.contains('home-pending') || root.classList.contains('welcome-pending') ||
      /^(waiting|playing)$/.test(root.dataset.homeEntrance || '') ||
      (app && (/^(waiting|playing)$/.test(app.dataset.entrance || '') || /^(waiting|playing)$/.test(app.dataset.roleEntrance || ''))) || activeCss().length > 0;
  }
  function finish() {
    if (!hasEntrance()) return false;
    root.classList.add('entrance-skipped');
    root.classList.remove('home-pending', 'welcome-pending');
    window.dispatchEvent(new Event('lingqi:skip-entrance'));
    activeCss().forEach(function (animation) { animation.cancel(); });
    document.querySelectorAll('.character-card--enter, .archive-pagination--enter').forEach(function (element) {
      element.classList.remove('character-card--enter', 'archive-pagination--enter');
      element.style.removeProperty('--entry-order');
    });
    return true;
  }
  window.addEventListener('click', function (event) {
    if (event.button !== 0 || event.detail === 0 || !finish()) return;
    event.preventDefault();
    event.stopImmediatePropagation();
  }, true);
  window.addEventListener('keydown', function (event) { if (event.key === 'Escape') finish(); });
})();
