/* Full wallpaper -> navigation and copy -> rising panel -> cards -> actions. */
(function () {
    "use strict";
    var root = document.documentElement;
    var preference = window.matchMedia("(prefers-reduced-motion: reduce)");
    var animations = [];
    var elements = [];
    var finished = false;

    function finish() {
        if (finished) return;
        finished = true;
        root.classList.remove("home-pending");
        root.dataset.homeEntrance = "complete";
        animations.forEach(function (animation) { animation.cancel(); });
        elements.forEach(function (entry) { entry.element.inert = entry.inert; });
    }

    if (!root.classList.contains("home-pending")) { finish(); return; }
    root.dataset.homeEntrance = "waiting";
    window.addEventListener("keydown", function (event) { if (event.key === "Escape") finish(); });
    window.addEventListener("pagehide", finish);
    window.addEventListener("lingqi:skip-entrance", finish);
    window.addEventListener("resize", finish);
    preference.addEventListener("change", function (event) { if (event.matches) finish(); });

    function reveal(element, delay, duration, distance, frames) {
        var entry = { element: element, inert: element.inert };
        elements.push(entry);
        element.inert = true;
        var animation = element.animate(frames || [
            { opacity: 0, visibility: "visible", transform: "translateY(" + distance + "px)" },
            { opacity: 1, visibility: "visible", transform: "translateY(0)" }
        ], { delay: delay, duration: duration, fill: "both", easing: "cubic-bezier(.22,.61,.36,1)" });
        animations.push(animation);
        animation.finished.then(function () { element.inert = entry.inert; }, function () {});
    }

    var wallpaper = new Image();
    wallpaper.src = "/static/pictures/main.png";
    var ready = wallpaper.decode ? wallpaper.decode().catch(function () {}) : Promise.resolve();
    Promise.race([ready, new Promise(function (resolve) { window.setTimeout(resolve, 1500); })]).then(function () {
        if (finished) return;
        try {
            [
                ["navigation", 0, 640, 20],
                ["label", 600, 650, 30],
                ["title", 1050, 800, 42],
                ["tagline", 1550, 750, 30],
                ["description", 1950, 750, 26]
            ].forEach(function (stage) {
                reveal(document.querySelector('[data-home-reveal="' + stage[0] + '"]'), stage[1], stage[2], stage[3]);
            });
            var panel = document.getElementById("bottom");
            var distance = Math.max(72, window.innerHeight - panel.parentElement.getBoundingClientRect().top + 24);
            var below = "translateY(" + distance + "px)";
            reveal(panel, 2700, 900, 0, [
                { opacity: 1, visibility: "hidden", transform: below, offset: 0 },
                { opacity: 1, visibility: "visible", transform: below, offset: .001 },
                { opacity: 1, visibility: "visible", transform: "translateY(0)", offset: 1 }
            ]);
            document.querySelectorAll('[data-home-reveal="feature"]').forEach(function (card, index) {
                reveal(card, 3620 + index * 110, 650, 42);
            });
            document.querySelectorAll("[data-home-action]").forEach(function (button) {
                reveal(button, 4520, 680, 18);
            });
            root.dataset.homeEntrance = "playing";
            Promise.allSettled(animations.map(function (animation) { return animation.finished; })).then(finish);
        } catch (error) {
            finish();
        }
    });
}());
