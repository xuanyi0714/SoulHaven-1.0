/* One welcome entrance per page load. View changes and reduced motion finish immediately. */
(function () {
  "use strict";
  var root = document.documentElement;
  var app = document.querySelector(".app");
  var home = document.querySelector(".world-home");
  var star = home.querySelector(".world-home__star");
  var surface = home.querySelector(".world-home__surface");
  var archive = document.querySelector(".world-archive");
  var hero = document.querySelector(".welcome-hero");
  var sidebar = document.getElementById("sidebar");
  var backdrop = document.querySelector(".welcome-backdrop");
  var roleList = document.getElementById("roleList");
  var preference = window.matchMedia("(prefers-reduced-motion: reduce)");
  var mobileImage = document.getElementById("welcomeImageMobile");
  var narrow = window.matchMedia(mobileImage.media);
  var video = backdrop.querySelector(".welcome-wallpaper");
  var videoFailed = false;
  var animations = [];
  var finished = false;
  var guarded = [home, archive, hero, sidebar];
  var originalInert = guarded.map(function (element) { return element.inert; });
  var ease = "cubic-bezier(.22, 1, .36, 1)";
  app.dataset.entrance = "waiting";

  function canPlayWallpaper() {
    return app.dataset.view === "home" && !preference.matches && !narrow.matches && !videoFailed;
  }

  function syncWallpaper() {
    var allowed = canPlayWallpaper();
    if (!allowed || document.hidden) {
      video.pause();
      if (!allowed) video.classList.remove("is-playing");
      return;
    }
    if (!video.getAttribute("src")) video.src = video.dataset.src;
    video.play().catch(function () { video.classList.remove("is-playing"); });
  }

  video.addEventListener("playing", function () {
    if (canPlayWallpaper()) video.classList.add("is-playing");
  });
  video.addEventListener("error", function () {
    videoFailed = true;
    syncWallpaper();
  });
  preference.addEventListener("change", syncWallpaper);
  narrow.addEventListener("change", syncWallpaper);
  document.addEventListener("visibilitychange", syncWallpaper);
  window.addEventListener("pagehide", function () { video.pause(); });
  window.addEventListener("pageshow", syncWallpaper);
  new MutationObserver(syncWallpaper).observe(app, { attributes: true, attributeFilter: ["data-view"] });
  syncWallpaper();

  function unlock(element) {
    var index = guarded.indexOf(element);
    element.inert = originalInert[index];
  }
  function finish() {
    if (finished) return;
    finished = true;
    root.classList.remove("welcome-pending");
    animations.forEach(function (animation) { animation.cancel(); });
    guarded.forEach(unlock);
    app.dataset.entrance = "complete";
  }
  function animate(element, frames, delay, duration, unlockAfter) {
    var animation = element.animate(frames, { delay: delay, duration: duration, easing: ease, fill: "backwards" });
    animations.push(animation);
    animation.finished.then(function () { if (unlockAfter) unlock(unlockAfter); }, function () {});
    return animation;
  }
  function appear(element, delay, duration, x, y, unlockAfter) {
    return animate(element, [
      { opacity: 0, transform: "translate(" + x + "px," + y + "px)" },
      { opacity: 1, transform: "translate(0,0)" }
    ], delay, duration, unlockAfter);
  }
  function writeTitle() {
    var delay = 3330;
    hero.querySelectorAll(".welcome-title__letters > g").forEach(function (glyph) {
      glyph.querySelectorAll(".welcome-title__stroke").forEach(function (stroke) {
        var duration = 55 + Math.min(115, stroke.getTotalLength() * 1.25);
        animate(stroke, [
          { strokeDashoffset: 1, opacity: 0 },
          { offset: .04, opacity: 1 },
          { strokeDashoffset: 0, opacity: 1 }
        ], delay, duration);
        delay += duration * .33;
      });
      animate(glyph.querySelector(".welcome-title__mask-fill"), [
        { opacity: 0 },
        { opacity: 1 }
      ], delay + 35, 105);
      delay += 34;
    });
  }
  function begin() {
    if (finished) return;
    if (preference.matches || app.dataset.view !== "home" || !surface.animate) { finish(); return; }
    guarded.forEach(function (element) { element.inert = true; });
    var bounds = surface.getBoundingClientRect();
    var starBounds = star.getBoundingClientRect();
    var origin = starBounds.left + starBounds.width / 2 - bounds.left;
    // The two clipping edges start at the actual star center, including on narrow screens.
    animate(star, [
      { opacity: 0, filter: "brightness(1)", transform: "scale(.6)" },
      { offset: .38, opacity: 1, filter: "brightness(2.6)", transform: "scale(1.28)" },
      { opacity: 1, filter: "brightness(1)", transform: "scale(1)" }
    ], 400, 900);
    animate(surface, [
      { clipPath: "inset(0px " + (bounds.width-origin) + "px 0px " + origin + "px round 999px)", opacity: .3 },
      { clipPath: "inset(0px 0px 0px 0px round 999px)", opacity: 1 }
    ], 1150, 1050, home);
    animate(home.querySelector(".world-home__words"), [
      { opacity: 0, clipPath: "inset(0 100% 0 0)" },
      { opacity: 1, clipPath: "inset(0 0 0 0)" }
    ], 1300, 950);
    appear(home.querySelector(".world-home__arrow"), 1800, 450, -5, 0);
    appear(archive, 2300, 750, 0, 12, archive);
    appear(hero, 3100, 1000, 0, 22, hero);
    writeTitle();
    appear(document.querySelector(".welcome-footnote"), 3400, 900, 0, 8);
    // Reveal the sidebar and resize the wallpaper along the same moving edge.
    animate(backdrop, [{ left: "0px" }, { left: sidebar.getBoundingClientRect().width + "px" }], 4200, 850);
    animate(sidebar, [
      { clipPath: "inset(0 100% 0 0)" },
      { clipPath: "inset(0 0 0 0)" }
    ], 4200, 850, sidebar);
    appear(roleList, 5100, 800, 0, 8);
    roleList.querySelectorAll("[data-role-item]").forEach(function (item, index) {
      appear(item, 5100 + Math.min(index, 5)*90, 750, -8, 0);
    });
    root.classList.remove("welcome-pending");
    app.dataset.entrance = "playing";
    Promise.allSettled(animations.map(function (animation) { return animation.finished; })).then(finish);
  }

  window.addEventListener("lingqi:skip-welcome", finish);
  window.addEventListener("lingqi:skip-entrance", finish);
  window.addEventListener("resize", function () { if (app.dataset.entrance === "playing") finish(); });
  window.addEventListener("keydown", function (event) { if (event.key === "Escape") finish(); });
  preference.addEventListener("change", function (event) { if (event.matches) finish(); });
  // Decode the chosen wallpaper before starting, without trapping the interface on a failed load.
  var image = new Image();
  image.src = narrow.matches ? mobileImage.href : document.getElementById("welcomeImage").href;
  if (preference.matches || root.classList.contains('entrance-skipped')) { finish(); return; }
  Promise.race([
    image.decode().catch(function () {}),
    new Promise(function (resolve) { setTimeout(resolve, 2500); })
  ]).then(function () { requestAnimationFrame(function () { requestAnimationFrame(begin); }); });
}());
