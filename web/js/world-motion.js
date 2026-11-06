(function () {
  "use strict";
  const video = document.querySelector(".world-scene__video");
  if (!video) return;
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
  let failed = false;
  function sync() {
    if (reduced.matches || document.hidden || failed) {
      video.pause();
      if (reduced.matches || failed) video.classList.remove("is-playing");
      return;
    }
    if (!video.getAttribute("src")) video.src = "/static/videos/world_breeze.mp4";
    const playback = video.play();
    if (playback) playback.catch(() => video.classList.remove("is-playing"));
  }
  video.addEventListener("playing", () => { if (!reduced.matches && !failed) video.classList.add("is-playing"); });
  video.addEventListener("error", () => { failed = true; sync(); });
  reduced.addEventListener("change", sync);
  document.addEventListener("visibilitychange", sync);
  window.addEventListener("pagehide", () => video.pause());
  window.addEventListener("pageshow", sync);
  sync();
}());
