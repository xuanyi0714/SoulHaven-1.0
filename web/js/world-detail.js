(function () {
  "use strict";
  const key = new URLSearchParams(location.search).get("world");
  function paragraph(text) { const p = document.createElement("p"); p.textContent = text; return p; }
  function renderCore(lines) { const target = document.getElementById("detailCore"); (lines.length ? lines : ["暂无常驻设定。"]).forEach(text => target.appendChild(paragraph(text))); }
  function renderEntries(id, entries, field, empty) {
    const target = document.getElementById(id); if (!entries.length) { target.appendChild(paragraph(empty)); return; }
    entries.forEach(entry => {
      const block = document.createElement("div"); block.className = "detail-entry";
      if (typeof entry === "string") block.appendChild(paragraph(entry));
      else { const title = document.createElement("h3"); title.textContent = entry.title; block.appendChild(title); entry[field].split("\n").filter(Boolean).forEach(text => block.appendChild(paragraph(text))); }
      target.appendChild(block);
    });
  }
  async function load() {
    if (!key) { document.getElementById("detailIntro").textContent = "找不到这个世界，请返回世界设定。"; return; }
    try {
      const response = await fetch("/api/worlds/" + encodeURIComponent(key), {cache:"no-store"});
      if (!response.ok) throw new Error("无法加载");
      const data = await response.json();
      document.querySelector(".detail-scene").style.backgroundImage = `url("${data.cover_url}?v=${Date.now()}")`;
      document.title = data.name + " · 灵栖"; document.getElementById("detailTitle").textContent = data.name;
      document.getElementById("detailKind").textContent = key === "reality" ? "DEFAULT WORLD · 默认世界观" : "WORLD ARCHIVE · 世界设定";
      document.getElementById("detailIntro").textContent = "常驻设定与目录会随角色进入聊天上下文；详细资料可在配置记忆模型后按需查询。";
      document.getElementById("editWorld").href = "/static/html/world.html?edit=" + encodeURIComponent(key);
      renderCore(data.core); renderEntries("detailEntries", data.details, "content", "暂无详细资料。"); renderEntries("detailDirectory", data.directory, "hint", "暂无目录。");
      document.getElementById("detailContents").hidden = false;
    } catch (error) { document.getElementById("detailIntro").textContent = "世界设定加载失败，请返回后重试。"; document.getElementById("editWorld").hidden = true; }
  }
  load();
}());
