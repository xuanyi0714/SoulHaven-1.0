(function () {
  "use strict";
  const topbar = document.querySelector(".topbar");
  function updateTopbarHeight() {
    document.documentElement.style.setProperty("--topbar-height", (topbar.getBoundingClientRect().height + (parseFloat(getComputedStyle(topbar).top) || 0)) + "px");
  }
  updateTopbarHeight();
  if (window.ResizeObserver) new ResizeObserver(updateTopbarHeight).observe(topbar);
  else window.addEventListener("resize", updateTopbarHeight);
  const name = new URLSearchParams(location.search).get("character");
  const endpoint = "/api/characters/" + encodeURIComponent(name || "");
  const labels = {name:"名字",English_name:"英文名",gender:"性别",brief:"角色简介",base_info:"角色基本描述",age:"年龄",height:"身高",weight:"体重",hometown:"家乡",current_location:"当前所在地",initial_relationship:"与用户的初始关系",dialogue_examples:"对话示例",speaking_style:"说话风格",personality_traits:"重要性格特点",opening_line:"开场白"};
  const optional = ["gender","brief","age","height","weight","hometown","current_location","initial_relationship","dialogue_examples","speaking_style","personality_traits","opening_line"];
  const wide = ["brief","base_info","initial_relationship","dialogue_examples","speaking_style","personality_traits","opening_line"];
  const $ = id => document.getElementById(id);
  let original, editing = false, saving = false, destination = null;
  function current() {
    const data = structuredClone(original);
    document.querySelectorAll("[data-field]").forEach(el => { const key = el.dataset.field; if (el.dataset.json === "true") data[key] = JSON.parse(el.value); else if (el.value || Object.hasOwn(data,key)) data[key] = el.value || null; });
    return data;
  }
  function dirty() { if (!editing) return false; try { return JSON.stringify(current()) !== JSON.stringify(original); } catch (_) { return true; } }
  function render() {
    $("editButton").hidden = editing; $("cancelButton").hidden = !editing; $("saveButton").hidden = !editing; $("saveReminder").hidden = !editing;
    $("profileName").textContent = original.name || "角色档案"; $("englishName").textContent = name;
    const fields = $("fields"); fields.replaceChildren();
    const keys = [...new Set([...Object.keys(labels), ...Object.keys(original)])];
    keys.filter(key => key !== "English_name" && (editing || (original[key] !== undefined && original[key] !== null && original[key] !== ""))).forEach(key => {
      const container = document.createElement("div"); container.className = "field" + (wide.includes(key) || typeof original[key] === "object" ? " wide" : "");
      const label = document.createElement("label"); label.textContent = labels[key] || key; container.append(label);
      if (editing) {
        const complex = original[key] !== undefined && original[key] !== null && typeof original[key] !== "string";
        const el = document.createElement(wide.includes(key) || complex ? "textarea" : "input"); el.id = "field-" + key; label.htmlFor = el.id; el.dataset.field = key;
        if (complex) { el.dataset.json = "true"; el.value = JSON.stringify(original[key], null, 2); } else el.value = original[key] || "";
        if (key === "name" || key === "base_info") el.required = true; if (key === "brief") el.maxLength = 500;
        container.append(el);
      } else { const value = document.createElement("div"); value.className = "field-value"; value.textContent = typeof original[key] === "string" ? original[key] : JSON.stringify(original[key], null, 2); container.append(value); }
      fields.append(container);
    });
  }
  async function save() {
    if (saving || !$('profileForm').reportValidity()) return false;
    let data; try { data = current(); } catch (_) { $("status").textContent = "请检查自定义字段的 JSON 格式。"; return false; }
    saving = true; $("saveButton").disabled = $("saveLeaveButton").disabled = true;
    try { const response = await fetch(endpoint, {method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify(data)}); const result = await response.json(); if (!response.ok) throw new Error(result.error || "保存失败"); original = data; editing = false; render(); $("status").textContent = "角色档案已保存。"; return true; }
    catch (error) { $("status").textContent = error.message || "保存失败，请重试。"; return false; }
    finally { saving = false; $("saveButton").disabled = $("saveLeaveButton").disabled = false; }
  }
  function leave() { const target = destination; destination = null; $("leaveDialog").close(); if (target === "cancel") { editing = false; render(); } else if (target) { editing = false; location.href = target; } }
  $("editButton").addEventListener("click", () => { editing = true; $("status").textContent = ""; render(); });
  $("cancelButton").addEventListener("click", () => { destination = "cancel"; if (dirty()) $("leaveDialog").showModal(); else leave(); });
  $("profileForm").addEventListener("submit", e => { e.preventDefault(); save(); });
  $("stayButton").addEventListener("click", () => { destination = null; $("leaveDialog").close(); });
  $("discardButton").addEventListener("click", leave);
  $("saveLeaveButton").addEventListener("click", async () => { if (await save()) leave(); });
  document.addEventListener("click", e => { const link = e.target.closest("a[href]"); if (!link || !dirty() || e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || link.target === "_blank") return; e.preventDefault(); destination = link.href; $("leaveDialog").showModal(); });
  window.addEventListener("beforeunload", e => { if (dirty()) { e.preventDefault(); e.returnValue = ""; } });
  if (!name) { $("status").textContent = "没有指定角色，请返回角色档案选择。"; $("editButton").hidden = true; return; }
  $("wallpaper").style.backgroundImage = 'url("' + endpoint + '/images/calm.png")';
  fetch(endpoint, {cache:"no-store"}).then(response => { if (!response.ok) throw new Error("无法读取角色档案，请返回角色列表重试。"); return response.json(); }).then(data => { original = data.description; $("status").textContent = ""; $("profileForm").hidden = false; render(); }).catch(error => { $("status").textContent = error.message; $("editButton").hidden = true; });
}());
