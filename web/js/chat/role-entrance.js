/* Full portrait -> fitted chat scene -> controls -> recent history. */
(function () {
  "use strict";
  var app = document.querySelector(".app");
  var chat = document.getElementById("chatView");
  var preference = window.matchMedia("(prefers-reduced-motion: reduce)");
  var active = null;
  function stop() { if (active) active(true); }
  window.addEventListener("lingqi:role-exit", stop);
  window.addEventListener("lingqi:skip-entrance", stop);
  window.addEventListener("resize", stop);
  window.addEventListener("keydown", function (event) { if (event.key === "Escape") stop(); });
  preference.addEventListener("change", function (event) { if (event.matches) stop(); });

  window.addEventListener("lingqi:role-enter", function (event) {
    stop();
    if (preference.matches || !chat.animate) { app.dataset.roleEntrance = "complete"; return; }
    var finished = false, animations = [], originalInert = app.inert;
    var layer = document.createElement("div");
    layer.className = "role-portrait-layer";
    layer.setAttribute("aria-hidden", "true");
    layer.style.backgroundImage = 'linear-gradient(#f8f5ff33,#f8f5ff33),url("' + event.detail.portrait.url + '")';
    document.body.appendChild(layer);
    app.dataset.roleEntrance = "waiting";
    app.inert = true;
    function finish(cancelled) {
      if (finished) return;
      finished = true;
      animations.forEach(function (animation) { animation.cancel(); });
      layer.remove(); app.inert = originalInert;
      app.dataset.roleEntrance = "complete";
      if (active === finish) active = null;
      if (!cancelled && app.dataset.view === "role") document.getElementById("chatInput").focus({ preventScroll: true });
    }
    active = finish;
    function animate(element, frames, delay, duration, fill, easing) {
      var animation = element.animate(frames, { delay: delay, duration: duration, easing: easing || "cubic-bezier(.22, 1, .36, 1)", fill: fill || "backwards" });
      animations.push(animation);
      return animation;
    }
    function reveal(element, delay, duration, x, y) {
      animate(element, [{ opacity: 0, transform: "translate("+x+"px,"+y+"px)" }, { opacity: 1, transform: "translate(0,0)" }], delay, duration);
    }
    Promise.race([event.detail.portrait.ready, new Promise(function (resolve) { setTimeout(function () { resolve(false); }, 1500); })]).then(function (loaded) {
      if (finished) return;
      if (!loaded || app.dataset.view !== "role") { finish(false); return; }
      var bounds = chat.getBoundingClientRect();
      var picture = animate(layer, [
        { left: "0px", top: "0px", width: innerWidth+"px", height: innerHeight+"px" },
        { left: bounds.left+"px", top: bounds.top+"px", width: bounds.width+"px", height: bounds.height+"px" }
      ], 180, 480, "both");
      picture.finished.then(function () { layer.remove(); }, function () {});
      reveal(document.getElementById("sidebar"), 600, 350, -14, 0);
      reveal(document.getElementById("rightSidebar"), 600, 350, 14, 0);
      reveal(chat.querySelector(".chat-header"), 850, 260, 0, -8);
      reveal(chat.querySelector(".composer-wrap"), 850, 260, 0, 8);
      animate(document.getElementById("messageList"), [
        { opacity: 0, transform: "translateY(90px)" },
        { opacity: 1, transform: "translateY(0)" }
      ], 1200, 1500, "backwards", "ease-in-out");
      app.dataset.roleEntrance = "playing";
      Promise.allSettled(animations.map(function (animation) { return animation.finished; })).then(function () { finish(false); });
    });
  });
}());
