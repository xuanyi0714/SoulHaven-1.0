(function () {
  "use strict";
  const dialog = document.getElementById("worldEditor"), form = document.getElementById("worldForm");
  const entries = document.getElementById("worldEntries"), template = document.getElementById("worldEntryTemplate");
  const coverInput = document.getElementById("worldCover"), coverPreview = document.getElementById("worldCoverPreview");
  const coverStatus = document.getElementById("worldCoverStatus"), removeCover = document.getElementById("removeWorldCover");
  const status = document.getElementById("worldFormStatus"), wait = document.getElementById("worldWait"), toast = document.getElementById("worldToast");
  let coverUrl = "", coverPoster = null, coverChecking = false, coverToken = 0, coverVideoUrl = "", coverPlayer = null, editingId = null, dirty = false;
  function clearCover() {
    coverToken++; coverPoster = null; coverChecking = false;
    if (coverPlayer) { coverPlayer.remove(); coverPlayer = null; }
    if (coverVideoUrl) { URL.revokeObjectURL(coverVideoUrl); coverVideoUrl = ""; }
    if (coverUrl) URL.revokeObjectURL(coverUrl);
    coverUrl = ""; coverInput.value = ""; coverPreview.removeAttribute("src");
    coverPreview.hidden = true; removeCover.hidden = true; coverStatus.textContent = "支持 PNG、JPEG、WebP、GIF、MP4，最大 10MB。";
  }
  coverInput.addEventListener("change", async () => {
    const file = coverInput.files[0];
    if (!file) { clearCover(); return; }
    if (!/\.(png|jpe?g|webp|gif|mp4)$/i.test(file.name) || !file.size || file.size > 10 * 1024 * 1024) { clearCover(); coverStatus.textContent = "请选择不超过 10MB 的图片、GIF 或 MP4 视频。"; return; }
    const token = ++coverToken; coverChecking = true; coverStatus.textContent = "正在检查文件…";
    try {
      const poster = /\.mp4$/i.test(file.name) ? await window.SoulMedia.poster(file) : null;
      if (token !== coverToken) return;
      if (coverUrl) URL.revokeObjectURL(coverUrl);
      if (coverPlayer) { coverPlayer.remove(); coverPlayer = null; }
      if (coverVideoUrl) { URL.revokeObjectURL(coverVideoUrl); coverVideoUrl = ""; }
      coverPoster = poster; coverUrl = URL.createObjectURL(poster || file);
      const image = new Image(); image.src = coverUrl; await image.decode();
      if (token !== coverToken) return;
      if (!image.naturalWidth || !image.naturalHeight || image.naturalWidth * image.naturalHeight > 25000000) throw new Error("画面不能超过 2500 万像素。");
      coverPreview.src = coverUrl; coverPreview.hidden = false;
      if (poster) { coverPlayer = document.createElement("video"); coverPlayer.className = coverPreview.className; coverPlayer.controls = true; coverPlayer.muted = true; coverPlayer.loop = true; coverPlayer.playsInline = true; coverVideoUrl = URL.createObjectURL(file); coverPlayer.src = coverVideoUrl; coverPreview.after(coverPlayer); coverPreview.hidden = true; }
      removeCover.hidden = false; coverStatus.textContent = file.name + (poster ? "（视频预览帧）" : ""); dirty = true;
    } catch (error) { if (token === coverToken) { clearCover(); coverStatus.textContent = error.message || "无法读取文件。"; } }
    finally { if (token === coverToken) coverChecking = false; }
  });
  removeCover.addEventListener("click", () => { clearCover(); dirty = true; });
  form.addEventListener("input", () => { dirty = true; });
  function closeEditor() { if (dirty && !window.confirm("还有未保存的内容，确定关闭吗？")) return; dialog.close(); }
  function showToast(text) { toast.textContent = text; toast.hidden = false; window.setTimeout(() => { toast.hidden = true; }, 6000); }
  function addEntry(data) {
    const entry = template.content.firstElementChild.cloneNode(true);
    if (data) { entry.querySelector(".editor-entry__title").value = data.title; entry.querySelector(".editor-entry__content").value = data.content; }
    entry.querySelector(".editor-entry__remove").addEventListener("click", () => {
      const filled = Array.from(entry.querySelectorAll("input, textarea")).some(field => field.value.trim());
      if (!filled || window.confirm("确定移除这条资料吗？")) { entry.remove(); dirty = true; }
    });
    entries.append(entry); return entry;
  }
  function worldCard(world) {
    const card = document.createElement("a"); card.className = "world-card";
    card.href = "/static/html/world-detail.html?world=" + encodeURIComponent(world.id);
    const art = document.createElement("div"); art.className = "world-card__art"; art.style.backgroundImage = `linear-gradient(rgba(27,36,31,.16),rgba(27,36,31,.16)), url("${world.cover_url}?v=${Date.now()}")`;
    const body = document.createElement("div"); body.className = "world-card__body";
    const tag = document.createElement("span"); tag.className = "world-card__tag"; tag.textContent = world.id === "reality" ? "默认世界观" : world.id === "jianghu" ? "示例世界观 · 古风武侠" : world.id === "vampire" ? "示例世界观 · 血族" : world.id === "space" ? "示例世界观 · 未来星际" : "我的世界";
    const title = document.createElement("span"); title.className = "world-card__title"; title.textContent = world.name;
    const description = document.createElement("span"); description.className = "world-card__description"; description.textContent = world.core.join(" ").slice(0, 65) + (world.core.join(" ").length > 65 ? "…" : "");
    const more = document.createElement("span"); more.className = "world-card__more"; more.textContent = "查看世界设定 →";
    body.append(tag, title, description, more); card.append(art, body); return card;
  }
  async function loadWorlds() {
    try {
      const response = await fetch("/api/worlds", {cache: "no-store"}); if (!response.ok) throw new Error();
      const data = await response.json(), grid = document.querySelector(".world-archive__grid");
      grid.querySelectorAll(".world-card").forEach(card => card.remove()); data.worlds.forEach(world => grid.appendChild(worldCard(world)));
    } catch (error) { showToast("世界观列表加载失败，请刷新重试。"); }
  }
  async function editWorld(id) {
    try {
      const response = await fetch("/api/worlds/" + encodeURIComponent(id), {cache:"no-store"});
      const world = await response.json(); if (!response.ok) throw new Error(world.error || "无法读取世界观");
      editingId = id; document.getElementById("editorTitle").textContent = "编辑世界观";
      document.getElementById("worldName").value = world.name; document.getElementById("worldCore").value = world.core.join("\n\n");
      document.getElementById("worldDirectory").value = world.directory.map(item => typeof item === "string" ? item : item.title + "：" + item.hint).join("\n");
      world.details.forEach(addEntry); dirty = false; dialog.showModal();
    } catch (error) { showToast(error.message || "世界观加载失败。"); }
  }
  document.getElementById("openWorldEditor").addEventListener("click", () => { editingId = null; document.getElementById("editorTitle").textContent = "新建世界观"; dialog.showModal(); });
  document.getElementById("closeWorldEditor").addEventListener("click", closeEditor);
  document.getElementById("cancelWorldEditor").addEventListener("click", closeEditor);
  dialog.addEventListener("cancel", event => { event.preventDefault(); closeEditor(); });
  dialog.addEventListener("close", () => { form.reset(); entries.replaceChildren(); clearCover(); dirty = false; status.textContent = ""; if (editingId) history.replaceState(null, "", "/static/html/world.html"); editingId = null; });
  document.getElementById("addWorldEntry").addEventListener("click", () => { dirty = true; addEntry().querySelector("input").focus(); });
  form.addEventListener("submit", async event => {
    event.preventDefault();
    if (coverChecking) { status.textContent = "请等待背景检查完成。"; return; }
    const details = Array.from(entries.children).map(entry => ({title: entry.querySelector(".editor-entry__title").value.trim(), content: entry.querySelector(".editor-entry__content").value.trim()}));
    if (details.some(item => !item.title || !item.content)) { status.textContent = "请填写每条资料的标题和正文，或移除空条目。"; return; }
    const data = {name: document.getElementById("worldName").value.trim(), core: document.getElementById("worldCore").value.trim(), details, directory: document.getElementById("worldDirectory").value.trim()};
    if (!data.name || !data.core) { status.textContent = "请填写世界名称和常驻设定。"; return; }
    const isEdit = !!editingId; const payload = new FormData(); payload.append("data", JSON.stringify(data)); if (coverInput.files[0]) { payload.append("cover", coverInput.files[0]); if (coverPoster) payload.append("cover_poster", coverPoster, "poster.png"); }
    wait.hidden = false; document.getElementById("saveWorld").disabled = true;
    try {
      const response = await fetch(isEdit ? "/api/worlds/" + encodeURIComponent(editingId) : "/api/worlds", {method: isEdit ? "PUT" : "POST", body: payload});
      const result = await response.json(); if (!response.ok) throw new Error(result.error || "保存失败");
      dirty = false; dialog.close(); await loadWorlds();
      showToast(result.warning || (result.without_embedding && result.without_embedding.length ? "世界已保存。部分角色未配置记忆模型，无法检索详细资料。" : "世界观已保存。"));
    } catch (error) { status.textContent = error.message || "保存失败，请重试。"; }
    finally { wait.hidden = true; document.getElementById("saveWorld").disabled = false; }
  });
  loadWorlds(); const edit = new URLSearchParams(location.search).get("edit"); if (edit) editWorld(edit);
}());
