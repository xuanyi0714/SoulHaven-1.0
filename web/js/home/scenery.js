(function () {
    'use strict';
    var layer = document.querySelector('.home-backdrop');
    var video = document.querySelector('.home-wallpaper');
    if (!layer || !video) return;
    var reduced = matchMedia('(prefers-reduced-motion: reduce)');
    var narrow = matchMedia('(max-width: 600px)');
    var scene = document.createElement('div');
    scene.className = 'home-scenery';
    var crown = document.createElement('canvas');
    crown.className = 'home-tree-crown';
    crown.width = 180; crown.height = 100;
    var sun = document.createElement('div');
    sun.className = 'home-sunlight';
    scene.append(crown, sun); layer.appendChild(scene);
    var ctx = crown.getContext('2d');
    var button = document.querySelector('.start[data-home-action]');
    if (button) button.classList.add('home-sun-rim');
    var mask = document.createElement('canvas');
    mask.width = 180; mask.height = 100;
    var mc = mask.getContext('2d');
    // The crown above the skyline only: no railing, buildings, trunk or people.
    mc.filter = 'blur(3px)';
    mc.fillStyle = '#fff';
    mc.beginPath();
    [[15,57],[36,39],[50,22],[82,12],[119,24],[153,33],
        [159,56],[137,73],[105,78],[70,78],[37,75],[17,69]].forEach(function (p, i) {
        if (i) mc.lineTo(p[0], p[1]); else mc.moveTo(p[0], p[1]);
    });
    mc.closePath(); mc.fill();
    var frame = 0, previous = 0, elapsed = 0, fitted = false;
    function fit() {
        scene.style.setProperty('--scene-scale', Math.max(layer.clientWidth / 1920, layer.clientHeight / 1080));
        fitted = true;
    }
    function active() {
        return !reduced.matches && !narrow.matches && !document.hidden && !video.paused && video.readyState >= 2;
    }
    function tick(now) {
        frame = 0;
        if (!active()) { sync(); return; }
        if (!previous) previous = now;
        var delta = now - previous;
        if (delta >= 40) {
            elapsed += Math.min(delta, 100); previous = now;
            var t = elapsed / 1000;
            if (!fitted) fit();
            ctx.clearRect(0, 0, 180, 100);
            // Sample the live frame so the patch never freezes the video underneath.
            for (var y = 0; y < 100; y += 2) {
                var bend = Math.sin(Math.PI * y / 100);
                var dx = (Math.sin(t * 1.35) * 3.4 + Math.sin(t * 2.1 + y * .035) * 1.1) * bend;
                ctx.drawImage(video, 635 - dx, 450 + y, 180, 2, 0, y, 180, 2);
            }
            ctx.globalCompositeOperation = 'destination-in';
            ctx.drawImage(mask, 0, 0);
            ctx.globalCompositeOperation = 'source-over';
            // A broad, slow swell, deliberately independent of the video loop.
            var light = Math.pow((1 + Math.sin(t * Math.PI * 2 / 9.7 - 1.8)) / 2, 3);
            scene.style.setProperty('--sun-strength', (.08 + light * .68).toFixed(3));
            if (button) button.style.setProperty('--sun-rim', (light * .85).toFixed(3));
        }
        frame = requestAnimationFrame(tick);
    }
    function sync() {
        var running = active();
        scene.classList.toggle('is-active', running);
        if (running && !frame) { previous = 0; frame = requestAnimationFrame(tick); }
        if (!running) {
            cancelAnimationFrame(frame); frame = 0; previous = 0;
            if (button) button.style.setProperty('--sun-rim', '0');
        }
    }
    window.addEventListener('resize', fit);
    document.addEventListener('visibilitychange', sync);
    ['playing', 'pause', 'error', 'emptied'].forEach(function (event) { video.addEventListener(event, sync); });
    [reduced, narrow].forEach(function (query) { query.addEventListener('change', sync); });
    window.addEventListener('pagehide', function () { cancelAnimationFrame(frame); frame = 0; });
    window.addEventListener('pageshow', sync);
    fit(); sync();
})();
