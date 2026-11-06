(function () {
  "use strict";
  var pageSize = 20, characters = [], page = 1, requestId = 0, firstRender = true;
  var search = document.getElementById("characterSearch");
  var grid = document.getElementById("characterGrid");
  var count = document.getElementById("archiveCount");
  var status = document.getElementById("archiveStatus");
  var pagination = document.getElementById("archivePagination");

  function makeCreateCard() {
    var card = document.createElement("a");
    card.className = "character-card character-card--create";
    card.href = "/chat.html?create=1";
    card.setAttribute("aria-label", "创建角色");
    var plus = document.createElement("span");
    plus.className = "character-card__plus";
    plus.setAttribute("aria-hidden", "true");
    plus.textContent = "+";
    var label = document.createElement("span");
    label.textContent = "创建角色";
    card.append(plus, label);
    return card;
  }

  function makeCard(character) {
    var card = document.createElement("button");
    card.type = "button";
    card.className = "character-card";
    card.setAttribute("aria-label", "查看 " + character.name + " 的角色档案");
    var cover = document.createElement("div");
    cover.className = "character-card__cover";
    var fallback = document.createElement("span");
    fallback.className = "character-card__fallback";
    fallback.textContent = (character.name || "角").trim().charAt(0) || "角";
    cover.appendChild(fallback);
    var image = document.createElement("img");
    image.alt = "";
    image.loading = "lazy";
    image.addEventListener("error", function () { image.remove(); });
    image.src = "/api/characters/" + encodeURIComponent(character.english_name) + "/images/calm.png";
    cover.appendChild(image);
    var body = document.createElement("div");
    body.className = "character-card__body";
    var english = document.createElement("p");
    english.className = "character-card__english";
    english.textContent = character.english_name;
    var name = document.createElement("h2");
    name.textContent = character.name;
    var description = document.createElement("p");
    description.className = "character-card__description";
    description.textContent = character.brief || character.base_info || "一个等待认识的灵魂。";
    var footer = document.createElement("span");
    footer.className = "character-card__footer";
    footer.textContent = "查看档案  ↗";
    body.append(english, name, description, footer);
    card.append(cover, body);
    card.addEventListener("click", function () {
      window.location.href = "/character-detail.html?character=" + encodeURIComponent(character.english_name);
    });
    return card;
  }

  function pageButton(label, target, disabled, current) {
    var button = document.createElement("button");
    button.type = "button";
    button.textContent = label;
    button.disabled = disabled;
    if (current) button.setAttribute("aria-current", "page");
    button.addEventListener("click", function () { page = target; render(); });
    return button;
  }

  function appendCard(card) {
    // Only the first result set enters; search, pagination and returning stay immediate.
    if (firstRender && !document.documentElement.classList.contains('entrance-skipped')) {
      card.style.setProperty("--entry-order", Math.min(grid.children.length, 9));
      card.classList.add("character-card--enter");
      card.addEventListener("animationend", function () {
        card.classList.remove("character-card--enter");
        card.style.removeProperty("--entry-order");
      }, { once: true });
    }
    grid.appendChild(card);
  }

  function render() {
    var query = search.value.trim().toLocaleLowerCase();
    var filtered = characters.filter(function (character) {
      return (character.name || "").toLocaleLowerCase().includes(query) ||
        (character.english_name || "").toLocaleLowerCase().includes(query);
    });
    // 第一页的创建入口占用一个格子，后续页全部用于角色。
    var pages = Math.max(1, Math.ceil((filtered.length + 1) / pageSize));
    page = Math.min(page, pages);
    count.textContent = query ? "找到 " + filtered.length + " 位角色" : "共 " + filtered.length + " 位角色";
    grid.replaceChildren();
    status.hidden = true;
    pagination.replaceChildren();
    pagination.hidden = pages <= 1;
    if (page === 1) appendCard(makeCreateCard());
    if (!filtered.length) {
      status.textContent = query ? "没有找到匹配的角色，换个名字试试。" : "还没有角色，点击加号创建一位吧。";
      status.hidden = false;
      firstRender = false;
      return;
    }
    var start = page === 1 ? 0 : (page - 1) * pageSize - 1;
    var end = page * pageSize - 1;
    filtered.slice(start, end).forEach(function (character) {
      appendCard(makeCard(character));
    });
    if (pages > 1) {
      pagination.appendChild(pageButton("上一页", page - 1, page === 1, false));
      var first = Math.max(1, Math.min(page - 2, pages - 4));
      var last = Math.min(pages, first + 4);
      for (var i = first; i <= last; i++) pagination.appendChild(pageButton(String(i), i, false, i === page));
      pagination.appendChild(pageButton("下一页", page + 1, page === pages, false));
    }
    if (firstRender && pages > 1 && !document.documentElement.classList.contains('entrance-skipped')) {
      pagination.classList.add("archive-pagination--enter");
      pagination.addEventListener("animationend", function () {
        pagination.classList.remove("archive-pagination--enter");
      }, { once: true });
    }
    firstRender = false;
  }

  function loadCharacters() {
    var currentRequest = ++requestId;
    count.textContent = "正在加载角色…";
    status.hidden = true;
    fetch("/api/characters", { cache: "no-store" })
      .then(function (response) {
        if (!response.ok) throw new Error("无法加载角色");
        return response.json();
      })
      .then(function (data) {
        if (currentRequest !== requestId) return;
        if (!Array.isArray(data.characters)) throw new Error("角色数据格式错误");
        characters = data.characters;
        render();
      })
      .catch(function () {
        if (currentRequest !== requestId) return;
        grid.replaceChildren();
        pagination.hidden = true;
        count.textContent = "角色加载失败";
        status.textContent = "暂时无法读取角色，请检查服务是否运行并刷新页面。";
        status.hidden = false;
      });
  }

  search.addEventListener("input", function () { page = 1; render(); });
  window.addEventListener("pageshow", loadCharacters);
  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "visible") loadCharacters();
  });
}());
