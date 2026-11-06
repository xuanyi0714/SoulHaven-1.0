(function () {
  'use strict';
  var checks = new Map();
  var reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  function videoUrl(url) {
    try {
      var parsed = new URL(url, location.href), match;
      if (parsed.origin !== location.origin) return null;
      match = parsed.pathname.match(/^\/api\/characters\/([^/]+)\/images\/([^/]+)\.png$/);
      if (match) return '/api/characters/' + match[1] + '/images/' + match[2] + '/video' + parsed.search;
      match = parsed.pathname.match(/^\/api\/worlds\/([^/]+)\/cover$/);
      if (match) return '/api/worlds/' + match[1] + '/video' + parsed.search;
    } catch (_) {}
    return null;
  }
  function exists(url) {
    if (!checks.has(url)) checks.set(url, fetch(url, {method:'HEAD', cache:'no-store'}).then(function (r) { return r.ok; }).catch(function () { return false; }));
    return checks.get(url);
  }
  function apply(target, url, image) {
    var video = videoUrl(url);
    if (target.dataset.soulMedia === (video || 'none')) return;
    target.dataset.soulMedia = video || 'none';
    if (target._soulVideo) { target._soulVideo.remove(); target._soulVideo = null; }
    if (!video || reducedMotion.matches) return;
    exists(video).then(function (yes) {
      if (!yes || reducedMotion.matches || target.dataset.soulMedia !== video || !target.isConnected) return;
      var parent = image ? target.parentElement : target;
      if (!parent) return;
      var el = document.createElement('video');
      el.className = 'soul-media-video' + (image ? ' soul-media-video--image' : ' soul-media-video--background');
      el.muted = true; el.defaultMuted = true; el.loop = true; el.autoplay = true; el.playsInline = true;
      el.setAttribute('aria-hidden', 'true'); el.src = video;
      el.addEventListener('error', function () { el.remove(); });
      if (getComputedStyle(parent).position === 'static') parent.style.position = 'relative';
      parent.classList.add('soul-media-container');
      if (image) parent.appendChild(el); else parent.insertBefore(el, parent.firstChild);
      target._soulVideo = el;
      var promise = el.play(); if (promise) promise.catch(function () { el.remove(); });
    });
  }
  function scan(el) {
    if (!el || el.nodeType !== 1 || el.matches('.soul-media-video')) return;
    if (el.tagName === 'IMG' && el.getAttribute('src')) apply(el, el.src, true);
    var style = el.getAttribute('style') || '';
    var found = style.match(/url\(["']?([^"')]+)["']?\)/);
    if (found) apply(el, found[1], false);
    else if (el.dataset.soulMedia && el.tagName !== 'IMG') apply(el, '', false);
    el.querySelectorAll('img[src], [style]').forEach(function (child) {
      if (child.tagName === 'IMG') apply(child, child.src, true);
      else { var m = (child.getAttribute('style') || '').match(/url\(["']?([^"')]+)["']?\)/); if (m) apply(child, m[1], false); }
    });
  }
  var css = document.createElement('style');
  css.textContent = '.soul-media-container{isolation:isolate}.soul-media-video{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;pointer-events:none}.soul-media-video--background{z-index:-1}.soul-media-video--image{z-index:1}@media(prefers-reduced-motion:reduce){.soul-media-video{display:none}}';
  document.head.appendChild(css);
  function start() {
    scan(document.body);
    new MutationObserver(function (records) { records.forEach(function (r) { if (r.type === 'attributes') scan(r.target); else r.addedNodes.forEach(scan); }); }).observe(document.body, {subtree:true, childList:true, attributes:true, attributeFilter:['src','style']});
    reducedMotion.addEventListener('change', function () {
      document.querySelectorAll('[data-soul-media]').forEach(function (target) {
        if (target._soulVideo) { target._soulVideo.remove(); target._soulVideo = null; }
        delete target.dataset.soulMedia;
      });
      scan(document.body);
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
  window.SoulMedia = {
    poster: function (file) {
      return new Promise(function (resolve, reject) {
        var url = URL.createObjectURL(file), video = document.createElement('video');
        var settled = false;
        var timer = setTimeout(function () { finish(new Error('视频读取超时')); }, 15000);
        function finish(error, blob) { if (settled) return; settled = true; clearTimeout(timer); video.removeAttribute('src'); video.load(); URL.revokeObjectURL(url); if (error) reject(error); else resolve(blob); }
        video.muted = true; video.preload = 'auto'; video.playsInline = true;
        video.onerror = function () { finish(new Error('视频无法解码，请选择浏览器支持的 MP4 视频。')); };
        video.onloadeddata = function () {
          if (!video.videoWidth || !video.videoHeight || video.videoWidth * video.videoHeight > 25000000) { finish(new Error('视频画面不能超过 2500 万像素。')); return; }
          var scale = Math.min(1, 1600 / Math.max(video.videoWidth, video.videoHeight));
          var canvas = document.createElement('canvas'); canvas.width = Math.round(video.videoWidth * scale); canvas.height = Math.round(video.videoHeight * scale);
          canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);
          canvas.toBlob(function (blob) { if (blob) finish(null, blob); else finish(new Error('无法生成视频预览。')); }, 'image/png');
        };
        video.src = url;
      });
    }
  };
}());
