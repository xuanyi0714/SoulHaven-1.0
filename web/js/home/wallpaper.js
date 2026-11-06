(function () {
    'use strict';
    var layer = document.querySelector('.home-backdrop');
    var video = document.querySelector('.home-wallpaper');
    if (!layer || !video) return;
    var reduced = matchMedia('(prefers-reduced-motion: reduce)');
    var narrow = matchMedia('(max-width: 600px)');
    var pointer = matchMedia('(hover: hover) and (pointer: fine)');
    var x = 0, y = 0, targetX = 0, targetY = 0, frame = 0;
    var failed = false;
    video.muted = true;

    function allowed() { return !reduced.matches && !narrow.matches; }
    function parallax() { return allowed() && pointer.matches && !document.hidden; }

    function tick() {
        x += (targetX - x) * 0.085;
        y += (targetY - y) * 0.085;
        layer.style.transform = 'perspective(1400px) translate3d(' + (-x * 8) + 'px,' + (-y * 6) + 'px,0) rotateX(' + (y * 0.45) + 'deg) rotateY(' + (-x * 0.55) + 'deg) scale(1.045)';
        frame = Math.abs(targetX - x) + Math.abs(targetY - y) > 0.001 ? requestAnimationFrame(tick) : 0;
    }

    function aim(nextX, nextY) {
        if (!parallax()) return;
        targetX = nextX; targetY = nextY;
        if (!frame) frame = requestAnimationFrame(tick);
    }

    function sync() {
        var moving = parallax();
        layer.classList.toggle('has-parallax', moving);
        if (!moving) {
            cancelAnimationFrame(frame); frame = 0;
            x = y = targetX = targetY = 0;
            layer.style.transform = '';
        }
        if (!allowed() || document.hidden || failed) {
            video.pause();
            if (!allowed() || failed) video.classList.remove('is-playing');
            return;
        }
        if (!video.getAttribute('src')) video.src = '/static/videos/home_breeze.mp4?v=continuous-5';
        var play = video.play();
        if (play) play.catch(function () { video.classList.remove('is-playing'); });
    }

    document.addEventListener('pointermove', function (event) {
        if (event.pointerType === 'mouse') aim(Math.max(-1, Math.min(1, event.clientX / innerWidth * 2 - 1)), Math.max(-1, Math.min(1, event.clientY / innerHeight * 2 - 1)));
    }, {passive: true});
    document.documentElement.addEventListener('pointerleave', function () { aim(0, 0); });
    window.addEventListener('blur', function () { aim(0, 0); });
    window.addEventListener('resize', function () { aim(0, 0); });
    video.addEventListener('playing', function () { if (allowed()) video.classList.add('is-playing'); });
    video.addEventListener('error', function () { failed = true; sync(); });
    [reduced, narrow, pointer].forEach(function (query) { query.addEventListener('change', sync); });
    document.addEventListener('visibilitychange', sync);
    window.addEventListener('pagehide', function () { video.pause(); cancelAnimationFrame(frame); frame = 0; });
    window.addEventListener('pageshow', sync);
    sync();
})();
