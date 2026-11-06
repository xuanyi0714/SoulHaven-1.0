/* Local archive scenery, no service calls or animation dependencies. */
(function () {
  "use strict";
  var root = document.getElementById("main");
  if (!root) return;

  var scene = document.createElement("div");
  scene.className = "archive-scene";
  scene.setAttribute("aria-hidden", "true");
  var pedestal = document.createElement("img");
  pedestal.className = "archive-scene__pedestal";
  pedestal.alt = "";
  var foliage = document.createElement("canvas");
  foliage.className = "archive-scene__trees";
  var treeContext = foliage.getContext("2d");
  var lights = document.createElement("canvas");
  lights.className = "archive-scene__lights";
  scene.append(pedestal, foliage, lights);
  root.prepend(scene);

  var ctx = lights.getContext("2d");
  if (!ctx) { scene.remove(); return; }
  var preference = window.matchMedia("(prefers-reduced-motion: reduce)");
  var paused = preference.matches;
  var width = 0, height = 0, pixelRatio = 1, scale = 1, offset = 0;
  var frame = 0, last = null, elapsed = 0, drawn = -1;
  var loaded = false;
  var sourceWidth = 1672, sourceHeight = 941;
  var image = new Image();
  var treeImage = new Image(), roomImage = new Image(), treesReady = false;
  // Transparent sprite crops, vase split, destination rectangle, wind phase.
  // Architecture exists only in the stationary room image, never in these sprites.
  var trees = [
    { source: [0,150,215,615], split: 623, target: [0,165,140,400], phase: 0 },
    { source: [345,390,180,365], split: 624, target: [347,338,140,290], phase: 1.7 },
    { source: [1025,385,195,370], split: 624, target: [1050,340,148,288], phase: 3.1 },
    { source: [1220,268,155,375], split: 516, target: [1220,278,112,257], phase: 4.6 }
  ];

  function drawTrees(seconds) {
    if (!treeContext || !treesReady) return;
    treeContext.setTransform(1,0,0,1,0,0);
    treeContext.clearRect(0,0,foliage.width,foliage.height);
    treeContext.setTransform(pixelRatio*scale,0,0,pixelRatio*scale,pixelRatio*offset,0);
    trees.forEach(function (tree) {
      var s=tree.source, d=tree.target;
      var topHeight=tree.split-s[1], canopyHeight=d[3]*topHeight/s[3];
      var baseY=d[1]+canopyHeight;
      // Vase and base remain fixed. Only the transparent canopy shears around its stem.
      treeContext.drawImage(treeImage,s[0],tree.split,s[2],s[3]-topHeight,
        d[0],baseY,d[2],d[3]-canopyHeight);
      var breeze=.043*Math.sin(seconds*(1.18+tree.phase*.035)+tree.phase)
        +.009*Math.sin(seconds*2.1+tree.phase*.7);
      treeContext.save();
      treeContext.translate(d[0]+d[2]*.5,baseY);
      treeContext.transform(1,0,breeze,1,0,0);
      treeContext.drawImage(treeImage,s[0],s[1],s[2],topHeight,
        -d[2]*.5,-canopyHeight,d[2],canopyHeight+.3);
      treeContext.restore();
    });
  }

  // Anchors coincide with the warm glints already painted in characters.png.
  // Every light has a different phase and period; never a full-screen flash.
  var anchors = [
    [37, 29], [78, 184], [136, 216], [215, 282], [270, 348],
    [288, 357], [303, 321], [338, 286], [365, 306], [405, 271],
    [492, 298], [539, 71], [624, 130], [686, 237], [733, 223],
    [1192, 236], [1195, 259], [1181, 322], [1218, 307], [1243, 333],
    [1308, 339], [1319, 394], [1364, 141], [1437, 287], [1558, 391],
    [1617, 191], [1641, 338], [303, 650], [367, 699], [440, 727],
    [544, 666], [663, 710], [900, 680], [1032, 758], [1207, 670],
    [1330, 711], [1484, 649], [1567, 787]
  ];

  function glow(x, y, radius, alpha, cool) {
    var color = cool ? "204,205,255" : "255,214,150";
    var gradient = ctx.createRadialGradient(x, y, 0, x, y, radius);
    gradient.addColorStop(0, "rgba(255,255,255," + alpha + ")");
    gradient.addColorStop(.18, "rgba(" + color + "," + alpha * .85 + ")");
    gradient.addColorStop(1, "rgba(" + color + ",0)");
    ctx.fillStyle = gradient; ctx.fillRect(x-radius, y-radius, radius*2, radius*2);
  }

  function star(x, y, radius, alpha) {
    ctx.save(); ctx.translate(x, y);
    ctx.fillStyle = "rgba(255,250,229," + alpha + ")";
    ctx.beginPath();
    ctx.moveTo(0, -radius); ctx.quadraticCurveTo(radius*.12, -radius*.12, radius*.7, 0);
    ctx.quadraticCurveTo(radius*.12, radius*.12, 0, radius);
    ctx.quadraticCurveTo(-radius*.12, radius*.12, -radius*.7, 0);
    ctx.quadraticCurveTo(-radius*.12, -radius*.12, 0, -radius);
    ctx.fill(); ctx.restore();
  }

  function draw(seconds) {
    drawTrees(seconds);
    ctx.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
    ctx.clearRect(0, 0, width, height);
    ctx.globalCompositeOperation = "source-over";
    // Slow breathing light on the windows and floor, not an exposure flicker.
    var wash = ctx.createRadialGradient(width*.46, height*.37, 0, width*.46, height*.37, width*.54);
    wash.addColorStop(0, "rgba(255,240,201," + (.035 + .065*(.5+.5*Math.sin(seconds*.64))) + ")");
    wash.addColorStop(1, "rgba(255,240,201,0)");
    ctx.fillStyle = wash; ctx.fillRect(0, 0, width, height);
    anchors.forEach(function (point, i) {
      var pulse = Math.pow(.5+.5*Math.sin(seconds*(1.07+(i%7)*.137)+i*2.399), 4);
      var x = offset + point[0]*scale, y = point[1]*scale;
      if (x < -30 || x > width+30 || y > height+30) return;
      var r = Math.min(7, Math.max(3, scale*3.4)) * (.55+.8*pulse);
      glow(x, y, r*4.8, pulse*.82, i%4===0);
      star(x, y, r, pulse*.98);
    });
    // A few drifting motes also fill the center on narrow crops.
    var count = width < 600 ? 12 : 24;
    for (var i=0; i<count; i++) {
      var cycle = (seconds*(.014+(i%4)*.002)+i*.6180339)%1;
      var x = ((i*.7548777)%1)*width + Math.sin(seconds*.47+i*1.7)*17;
      var y = height*(1.03-cycle*1.1);
      var alpha = Math.sin(cycle*Math.PI)*(.25+.5*Math.pow(.5+.5*Math.sin(seconds*1.2+i*2.1),2));
      glow(x,y,9,alpha*.45,i%3===0);
      ctx.fillStyle = "rgba(255,241,194,"+alpha+")";
      ctx.beginPath(); ctx.arc(x,y,1.3+(i%3)*.45,0,Math.PI*2); ctx.fill();
    }
  }

  function resize() {
    width = scene.clientWidth; height = scene.clientHeight;
    if (!width || !height) return;
    // Viewport-sized transparent layers; no displacement of the stationary room.
    pixelRatio = Math.min(window.devicePixelRatio || 1, 1.5, 2048/Math.max(width,height));
    lights.width = Math.round(width*pixelRatio); lights.height = Math.round(height*pixelRatio);
    foliage.width = lights.width; foliage.height = lights.height;
    scale = Math.max(width/sourceWidth, height/sourceHeight);
    offset = (width-sourceWidth*scale)*.5;
    if (loaded) draw(elapsed);
  }

  function tick(now) {
    frame = 0;
    if (paused || document.hidden || !loaded) return;
    if (last !== null) elapsed += Math.min((now-last)/1000, .1);
    last = now;
    if (elapsed-drawn >= 1/30) { draw(elapsed); drawn = elapsed; }
    frame = requestAnimationFrame(tick);
  }

  function schedule() {
    if (frame) cancelAnimationFrame(frame);
    frame = 0; last = null;
    scene.dataset.paused = String(paused);
    if (!paused && !document.hidden && loaded) frame = requestAnimationFrame(tick);
  }

  preference.addEventListener("change", function (event) { paused = event.matches; schedule(); });
  window.addEventListener("resize", resize);
  document.addEventListener("visibilitychange", schedule);
  window.addEventListener("pagehide", function () {
    if (frame) cancelAnimationFrame(frame);
    frame = 0; last = null;
  });
  window.addEventListener("pageshow", schedule);
  image.onload = function () {
    loaded = true;
    root.classList.add("archive-scene-ready");
    resize(); schedule();
  };
  image.onerror = function () { scene.remove(); };
  image.src = "/static/pictures/characters.png";
  function loadLayer(asset, url) {
    return new Promise(function (resolve,reject) {
      asset.onload=resolve; asset.onerror=reject; asset.src=url;
    });
  }
  if (treeContext) Promise.all([
    loadLayer(treeImage,"/static/pictures/archive_trees.png"),
    loadLayer(roomImage,"/static/pictures/archive_room.png"),
    loadLayer(pedestal,"/static/pictures/archive_pedestal.svg")
  ]).then(function () {
    treesReady=true;
    scene.style.backgroundImage='url("/static/pictures/archive_room.png")';
    scene.dataset.trees="ready";
    if (loaded) draw(elapsed);
  }).catch(function () {
    // Keep the complete original scene if either layer fails; never leave missing trees.
    scene.dataset.trees="unavailable";
  });
}());
