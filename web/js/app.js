(function () {
  "use strict";

  var API_CHARACTERS = "/api/characters";  // 角色接口地址
  var API_CHAT = "/api/chat";  // 聊天接口地址
  var MAX_ROLE_IMAGE_BYTES = 10 * 1024 * 1024;
  var MAX_ROLE_IMAGE_PIXELS = 25000000;
  var EMOTION_IMAGES = [
    ["happy", "开心"], ["sad", "难过"], ["scrare", "害怕"],
    ["angry", "生气"], ["shy", "害羞"], ["weak", "虚弱"],
    ["tired", "疲劳"], ["nervous", "紧张"], ["surprised", "惊讶"],
    ["confused", "困惑"]
  ];
  var VALID_EMOTIONS = ["calm"].concat(EMOTION_IMAGES.map(function (item) { return item[0]; }));
  var RECOGNITION_TIME_STORAGE_KEY = "soulhaven.recognitionTime";  // 感知时间开关的本地存储键
  var DEEP_THINKING_STORAGE_KEY = "soulhaven.deepThinking";  // 深度思考开关的本地存储键

  var EMBEDDING_PROVIDER_DEFAULTS = {  // Embedding 提供商默认地址和模型提示
    ollama: {
      baseUrl: "http://127.0.0.1:11434",
      modelHint: "例如：nomic-embed-text",
      hint: "本地 Ollama 不需要 Embedding API Key；请先 ollama pull 对应的嵌入模型。",
    },
    aliyun: {
      baseUrl: "https://dashscope.aliyuncs.com/compatible-mode/v1",
      modelHint: "例如：text-embedding-v4",
      hint: "阿里云百炼使用同一个 API Key；Embedding 模型名请按百炼控制台填写。",
    },
    volcengine: {
      baseUrl: "https://ark.cn-beijing.volces.com/api/v3",
      modelHint: "例如：doubao-embedding",
      hint: "火山引擎方舟的 Embedding 模型名或推理接入点请按控制台填写。",
    },
    zhipu: {
      baseUrl: "https://open.bigmodel.cn/api/paas/v4",
      modelHint: "例如：embedding-3",
      hint: "智谱 Embedding 使用 BigModel 的 API Key。",
    },
    qianfan: {
      baseUrl: "https://qianfan.baidubce.com/v2",
      modelHint: "例如：embedding-v1",
      hint: "百度千帆使用 OpenAI 兼容地址；模型名请按千帆控制台填写。",
    },
    tencent: {
      baseUrl: "https://api.hunyuan.cloud.tencent.com/v1",
      modelHint: "例如：hunyuan-embedding",
      hint: "腾讯云混元使用 OpenAI 兼容地址；模型名请按混元控制台填写。",
    },
    other: {
      baseUrl: "",
      modelHint: "例如：text-embedding-3-small",
      hint: "自定义 OpenAI 兼容接口：Base URL 通常以 /v1 结尾，模型名和 API Key 由服务商提供。",
    },
  };

  var mobileLayout = window.matchMedia("(max-width: 900px) and (pointer: coarse)");
  var mobileRoles = document.getElementById("mobileRoles");
  var mobileMood = document.getElementById("mobileMood");
  var mobileMore = document.getElementById("mobileChatMore");
  var chatMain = document.getElementById("chatMain");
  var chatDrawerBackdrop = document.getElementById("chatDrawerBackdrop");
  var chatApp = chatMain.closest(".app");
  var desktopSidebarState;
  var sidebar = document.getElementById("sidebar");
  var sidebarToggle = document.getElementById("sidebarToggle");
  var rightSidebar = document.getElementById("rightSidebar");
  var rightSidebarToggle = document.getElementById("rightSidebarToggle");
  var rightSidebarBody = document.getElementById("rightSidebarBody");
  var brand = document.getElementById("brand");
  var backButton = document.getElementById("backButton");
  var rolesView = document.getElementById("rolesView");
  var sessionsView = document.getElementById("sessionsView");
  var roleList = document.getElementById("roleList");
  var welcomeView = document.getElementById("welcomeView");
  var welcomeMark = document.getElementById("welcomeMark");
  var welcomeTitle = document.getElementById("welcomeTitle");
  var welcomeHint = document.getElementById("welcomeHint");
  var chatView = document.getElementById("chatView");
  var summaryOverlay = document.getElementById("summaryOverlay");
  var chatAvatar = document.getElementById("chatAvatar");
  var chatRoleName = document.getElementById("chatRoleName");
  var chatRoleMeta = document.getElementById("chatRoleMeta");
  var sessionRoleAvatar = document.getElementById("sessionRoleAvatar");
  var sessionRoleName = document.getElementById("sessionRoleName");
  var messageList = document.getElementById("messageList");
  var chatEmpty = document.getElementById("chatEmpty");
  var historyLoader = document.getElementById("historyLoader");
  var loadOlderButton = document.getElementById("loadOlderMessages");
  var historyLoadStatus = document.getElementById("historyLoadStatus");
  var historyBefore = null, historyLoading = false;
  var chatForm = document.getElementById("chatForm");
  var chatInput = document.getElementById("chatInput");
  var sendButton = document.getElementById("sendButton");
  var continueSayButton = document.getElementById("continueSayButton");
  var clearHistoryButton = document.getElementById("clearHistoryButton");
  var rebuildMemoryButton = document.getElementById("rebuildMemoryButton");
  var clearDialog = document.getElementById("clearHistoryDialog");
  var clearForm = document.getElementById("clearHistoryForm");
  var clearConfirmation = document.getElementById("clearHistoryConfirmation");
  var confirmClearButton = document.getElementById("confirmClearHistory");
  var cancelClearButton = document.getElementById("cancelClearHistory");
  var clearError = document.getElementById("clearHistoryError");
  var clearTarget = null;
  var clearPhrase = "我确认要清空聊天记录";
  var summarizeButton = document.getElementById("summarizeButton");
  var deepThinkingToggle = document.getElementById("deepThinkingToggle");
  var recognitionTimeToggle = document.getElementById("recognitionTimeToggle");
  var segmentedReplyToggle = document.getElementById("segmentedReplyToggle");
  var segmentedReplyStatus = document.getElementById("segmentedReplyStatus");

  var createRoleButton = document.getElementById("createRoleButton");
  var createRoleModal = document.getElementById("createRoleModal");
  var closeCreateRoleModal = document.getElementById("closeCreateRoleModal");
  var cancelCreateRole = document.getElementById("cancelCreateRole");
  var createRoleForm = document.getElementById("createRoleForm");
  var createRoleSubmit = document.getElementById("createRoleSubmit");
  var createRoleError = document.getElementById("createRoleError");
  var roleName = document.getElementById("roleName");
  var englishName = document.getElementById("englishName");
  var roleGender = document.getElementById("roleGender");
  var roleImage = document.getElementById("roleImage");
  var roleImagePreview = document.getElementById("roleImagePreview");
  var roleImageStatus = document.getElementById("roleImageStatus");
  var roleImageError = document.getElementById("roleImageError");
  var clearRoleImageButton = document.getElementById("clearRoleImage");
  var provider = document.getElementById("provider");
  var temperature = document.getElementById("temperature");
  var modelName = document.getElementById("modelName");
  var characterDescription = document.getElementById("characterDescription");
  var characterBrief = document.getElementById("characterBrief");
  var openingLine = document.getElementById("openingLine");
  var apiKeyField = document.getElementById("apiKeyField");
  var apiKey = document.getElementById("apiKey");
  var baseUrlField = document.getElementById("baseUrlField");
  var baseUrl = document.getElementById("baseUrl");
  var ollamaHint = document.getElementById("ollamaHint");
  var embeddingEnabled = document.getElementById("embeddingEnabled");
  var embeddingFields = document.getElementById("embeddingFields");
  var embeddingProvider = document.getElementById("embeddingProvider");
  var embeddingModel = document.getElementById("embeddingModel");
  var embeddingApiKeyField = document.getElementById("embeddingApiKeyField");
  var embeddingApiKey = document.getElementById("embeddingApiKey");
  var embeddingBaseUrl = document.getElementById("embeddingBaseUrl");
  var embeddingModelHint = document.getElementById("embeddingModelHint");
  var embeddingHint = document.getElementById("embeddingHint");
  var advancedFields = document.getElementById("advancedFields");
  var searchEnabled = document.getElementById("searchEnabled");
  var searchFields = document.getElementById("searchFields");
  var searchProvider = document.getElementById("searchProvider");
  var searchApiKey = document.getElementById("searchApiKey");
  var searchBaseUrlField = document.getElementById("searchBaseUrlField");
  var searchBaseUrl = document.getElementById("searchBaseUrl");
  var searchHeaderField = document.getElementById("searchHeaderField");
  var searchHeader = document.getElementById("searchHeader");
  var age = document.getElementById("age");
  var height = document.getElementById("height");
  var weight = document.getElementById("weight");
  var hometown = document.getElementById("hometown");
  var currentLocation = document.getElementById("currentLocation");
  var initialRelationship = document.getElementById("initialRelationship");
  var dialogueExamples = document.getElementById("dialogueExamples");
  var dialoguePairs = document.getElementById("dialoguePairs");
  var addDialoguePair = document.getElementById("addDialoguePair");
  var speakingStyle = document.getElementById("speakingStyle");
  var personalityTraits = document.getElementById("personalityTraits");
  var toast = document.getElementById("toast");
  

  var state = {
    characters: [],
    currentRole: null,
    sending: false,
    summarizing: false,
    clearing: false,
    viewToken: 0,
    controller: null,
    deepThinking: true,
    recognitionTime: true,
    savingReplySettings: false,
    sessionDirty: false,
  };
  var toastTimer = null;
  var backgroundRequest = 0;

  function setSidebarCollapsed(isCollapsed) {
    sidebar.classList.toggle("is-collapsed", isCollapsed);

    var actionName = isCollapsed ? "展开侧边栏" : "收起侧边栏";
    sidebarToggle.setAttribute("aria-label", actionName);
    sidebarToggle.setAttribute("title", actionName);
    sidebarToggle.setAttribute("aria-expanded", String(!isCollapsed));
  }

  function setMobileDrawer(drawer, restoreFocus) {
    var previous = chatApp.dataset.drawer;
    if (drawer) window.dispatchEvent(new Event("lingqi:skip-welcome"));
    chatApp.dataset.drawer = drawer;
    chatDrawerBackdrop.hidden = !drawer;
    chatMain.inert = Boolean(drawer);
    mobileRoles.setAttribute("aria-expanded", String(drawer === "roles"));
    mobileMood.setAttribute("aria-expanded", String(drawer === "mood"));

    if (drawer === "roles") sidebarToggle.focus();
    else if (drawer === "mood") rightSidebarToggle.focus();
    else if (restoreFocus && previous) (previous === "roles" ? mobileRoles : mobileMood).focus();
  }

  function setMobileActions(open) {
    mobileMore.setAttribute("aria-expanded", String(open));
  }

  function updateChatViewport() {
    var viewport = window.visualViewport;
    var useVisualViewport = mobileLayout.matches && viewport && viewport.scale === 1;
    var style = document.documentElement.style;
    var atBottom = mobileLayout.matches && !chatView.hidden &&
      messageList.scrollHeight - messageList.clientHeight - messageList.scrollTop < 32;
    style.setProperty("--chat-viewport-height", useVisualViewport ? viewport.height + "px" : "");
    style.setProperty("--chat-viewport-top", useVisualViewport ? viewport.offsetTop + "px" : "");
    if (atBottom) scrollToBottom();
  }

  function updateChatLayout() {
    if (mobileLayout.matches) {
      desktopSidebarState = [sidebar.classList.contains("is-collapsed"), rightSidebar.classList.contains("is-collapsed")];
      setSidebarCollapsed(false);
      setRightSidebarCollapsed(false);
    } else if (desktopSidebarState) {
      setSidebarCollapsed(desktopSidebarState[0]);
      setRightSidebarCollapsed(desktopSidebarState[1]);
      desktopSidebarState = null;
    }
    setMobileDrawer("");
    setMobileActions(false);
    updateChatViewport();
    if (mobileLayout.matches) resizeChatInput();
  }

  function initialOf(name) {
    if (!name) {
      return "角";
    }
    return Array.from(name)[0] || "角";
  }

  function showToast(message, isError) {
    toast.textContent = message;
    toast.classList.toggle("toast--error", Boolean(isError));
    toast.hidden = false;
    window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(function () {
      toast.hidden = true;
    }, 3600);
  }

  function apiRequest(url, options) {
    return fetch(url, options).then(function (response) {
      return response.text().then(function (text) {
        var data = {};
        if (text) {
          try {
            data = JSON.parse(text);
          } catch (error) {
            data = {};
          }
        }

        if (!response.ok) {
          var message =
            data && data.error
              ? data.error
              : "请求失败（HTTP " + response.status + "）";
          var requestError = new Error(message);
          requestError.status = response.status;
          throw requestError;
        }

        return data;
      });
    });
  }

  function errorText(error) {
    if (error && error.name === "TypeError") {
      return "无法连接后端服务，请确认 Flask 已启动";
    }
    return (error && error.message) || "请求失败";
  }

  function readStoredBoolean(storageKey, defaultValue) {
    try {
      var stored = window.localStorage.getItem(storageKey);
      if (stored === "true" || stored === "false") {
        return stored === "true";
      }
    } catch (error) {
      // 隐私模式或本地存储被禁用时使用默认值。
    }
    return defaultValue;
  }

  function saveStoredBoolean(storageKey, value) {
    try {
      window.localStorage.setItem(storageKey, value ? "true" : "false");
    } catch (error) {
      // 本地存储不可用时只影响下次启动的默认值。
    }
  }

  function readStoredRecognitionTime() {
    return readStoredBoolean(RECOGNITION_TIME_STORAGE_KEY, true);
  }

  function saveRecognitionTime(value) {
    saveStoredBoolean(RECOGNITION_TIME_STORAGE_KEY, value);
  }

  function setRecognitionTime(value, shouldPersist) {
    state.recognitionTime = Boolean(value);
    recognitionTimeToggle.checked = state.recognitionTime;
    if (shouldPersist) {
      saveRecognitionTime(state.recognitionTime);
    }
  }

  function readStoredDeepThinking() {
    return readStoredBoolean(DEEP_THINKING_STORAGE_KEY, true);
  }

  function saveDeepThinking(value) {
    saveStoredBoolean(DEEP_THINKING_STORAGE_KEY, value);
  }

  function setDeepThinking(value, shouldPersist) {
    state.deepThinking = Boolean(value);
    deepThinkingToggle.checked = state.deepThinking;
    if (shouldPersist) {
      saveDeepThinking(state.deepThinking);
    }
  }

  function cancelPendingChat() {
    if (state.controller) {
      state.controller.abort();
      state.controller = null;
    }
    state.sending = false;
    setSegmentedWaiting(false);
    setSummarizing(false);
  }

  function setSegmentedWaiting(waiting) {
    chatInput.disabled = waiting || state.summarizing;
    chatInput.placeholder = waiting ? "等待角色说完话哦~" : "给角色发送消息...";
    segmentedReplyStatus.hidden = !waiting;
  }

  function clearRoleBackground(invalidate) {
    if (invalidate !== false) backgroundRequest += 1;
    chatView.classList.remove("chat--with-image");
    chatView.style.removeProperty("--character-image");
  }

  function loadRoleBackground(character, token, emotion) {
    // 旧图片加载结果不能覆盖较新一轮的选择或其他角色。
    var selected = VALID_EMOTIONS.indexOf(emotion) >= 0 ? emotion : "calm";
    var request = ++backgroundRequest;
    var settle;
    var ready = new Promise(function (resolve) { settle = resolve; });
    var base = API_CHARACTERS + "/" + encodeURIComponent(character.english_name) + "/images/";
    var url = base + selected + ".png?view=" + token + "-" + request;
    function tryImage(choice) {
      var image = new Image();
      var imageUrl = base + choice + ".png?view=" + token + "-" + request;
      image.onload = function () {
        if (token !== state.viewToken || request !== backgroundRequest || !image.naturalWidth || !image.naturalHeight) {
          settle(false); return;
        }
        chatView.style.setProperty("--character-image", 'url("' + imageUrl + '")');
        chatView.classList.add("chat--with-image");
        settle(true);
      };
      image.onerror = function () {
        if (token !== state.viewToken || request !== backgroundRequest) { settle(false); return; }
        if (choice !== "calm") { tryImage("calm"); return; }
        clearRoleBackground(false);
        settle(false);
      };
      image.src = imageUrl;
    }
    tryImage(selected);
    return { ready: ready, url: url };
  }

  function showHome(hint) {
    setMobileDrawer("", true);
    setMobileActions(false);
    window.dispatchEvent(new Event("lingqi:role-exit"));
    resetHistoryPaging();
    cancelPendingChat();
    state.viewToken += 1;
    state.currentRole = null;
    var homeUrl = new URL(location.href);
    homeUrl.searchParams.delete('character');
    history.replaceState(null, '', homeUrl.pathname + homeUrl.search + homeUrl.hash);
    state.sessionDirty = false;
    clearRoleBackground();

    sidebar.closest(".app").dataset.view = "home";
    rightSidebar.hidden = true;
    sidebar.dataset.view = "home";
    rolesView.hidden = false;
    sessionsView.hidden = true;
    brand.hidden = false;
    backButton.hidden = true;

    welcomeView.hidden = false;
    chatView.hidden = true;
    welcomeMark.textContent = "✦";
    welcomeMark.classList.remove("welcome-mark--role");
    welcomeTitle.textContent = "在这里，\n遇见另一种日常。";
    welcomeHint.textContent = hint || "把今天的故事，讲给在意的人听。";

    messageList.querySelectorAll(".message").forEach(function (node) {
      node.remove();
    });
    chatEmpty.hidden = true;
    chatInput.value = "";
    resizeChatInput();
  }

  function showRole(character) {
    setMobileDrawer("");
    setMobileActions(false);
    cancelPendingChat();
    state.viewToken += 1;
    var token = state.viewToken;
    state.currentRole = character;
    segmentedReplyToggle.checked = character.segmented_reply === true;
    var roleUrl = new URL(location.href);
    roleUrl.searchParams.set('character', character.english_name);
    history.replaceState(null, '', roleUrl.pathname + roleUrl.search + roleUrl.hash);
    state.sessionDirty = false;
    clearRoleBackground();
    var portrait = loadRoleBackground(character, token, "calm");
    refreshRoleState();
    resetHistoryPaging();

    window.dispatchEvent(new Event("lingqi:skip-welcome"));
    sidebar.closest(".app").dataset.view = "role";
    rightSidebar.hidden = false;
    sidebar.dataset.view = "role";
    rolesView.hidden = true;
    sessionsView.hidden = false;
    brand.hidden = true;
    backButton.hidden = false;

    welcomeView.hidden = true;
    chatView.hidden = false;

    var initial = initialOf(character.name);
    sessionRoleAvatar.textContent = initial;
    applyPortrait(sessionRoleAvatar, character);
    sessionRoleName.textContent = character.name;
    chatAvatar.textContent = initial;
    applyPortrait(chatAvatar, character);
    chatRoleName.textContent = character.name;
    chatRoleMeta.textContent = character.gender
      ? character.gender + " · 当前角色"
      : "当前角色";

    messageList.querySelectorAll(".message").forEach(function (node) {
      node.remove();
    });
    chatEmpty.hidden = false;
    chatEmpty.textContent = "正在加载消息...";
    sendButton.disabled = true;
    continueSayButton.disabled = true;
    chatInput.value = "";
    resizeChatInput();
    if (mobileLayout.matches) mobileRoles.focus();
    else chatInput.focus();

    apiRequest(
      API_CHARACTERS +  // 角色接口地址
        "/" +
        encodeURIComponent(character.english_name) +
        "/messages?limit=100"
    )
      .then(function (data) {
        if (token !== state.viewToken) {
          return;
        }
        var messages = Array.isArray(data.messages) ? data.messages : [];
        renderHistory(messages);
        updateHistoryPaging(data);
      })
      .catch(function (error) {
        if (token !== state.viewToken) {
          return;
        }
        chatEmpty.hidden = false;
        chatEmpty.textContent = "消息加载失败，请稍后重试";
        showToast(errorText(error), true);
      })
      .finally(function () {
        if (token !== state.viewToken || state.summarizing || state.clearing) return;
        sendButton.disabled = false;
        continueSayButton.disabled = false;
      });
    window.dispatchEvent(new CustomEvent("lingqi:role-enter", { detail: { token: token, portrait: portrait } }));
  }

  function resetHistoryPaging() {
    historyBefore = null; historyLoading = false;
    historyLoader.hidden = true; loadOlderButton.disabled = false;
    loadOlderButton.textContent = "加载更多对话"; historyLoadStatus.textContent = "";
  }
  function updateHistoryPaging(data) {
    historyBefore = data.has_more ? data.next_before : null;
    historyLoader.hidden = historyBefore === null;
  }
  function loadOlderMessages() {
    if (historyLoading || historyBefore === null || !state.currentRole) return;
    var token = state.viewToken;
    var url = API_CHARACTERS + "/" + encodeURIComponent(state.currentRole.english_name) + "/messages?limit=100&before=" + historyBefore;
    historyLoading = true; loadOlderButton.disabled = true;
    loadOlderButton.textContent = "正在加载…"; historyLoadStatus.textContent = "";
    apiRequest(url).then(function (data) {
      if (token !== state.viewToken) return;
      var anchor = messageList.querySelector(".message");
      var oldTop = anchor ? anchor.getBoundingClientRect().top : 0;
      var fragment = document.createDocumentFragment();
      (data.messages || []).forEach(function (message) {
        fragment.appendChild(appendMessage(message.role, message.content || "", false, message.reasoning_content || ""));
      });
      messageList.insertBefore(fragment, anchor || chatEmpty);
      updateHistoryPaging(data);
      if (anchor) messageList.scrollTop += anchor.getBoundingClientRect().top - oldTop;
    }).catch(function (error) {
      if (token === state.viewToken) historyLoadStatus.textContent = errorText(error);
    }).finally(function () {
      if (token !== state.viewToken) return;
      historyLoading = false; loadOlderButton.disabled = false;
      loadOlderButton.textContent = "加载更多对话";
    });
  }
  loadOlderButton.addEventListener("click", loadOlderMessages);

  function renderHistory(messages) {
    messageList.querySelectorAll(".message").forEach(function (node) {
      node.remove();
    });

    if (!messages.length) {
      chatEmpty.hidden = false;
      chatEmpty.textContent =
        "开始和「" + (state.currentRole ? state.currentRole.name : "角色") + "」聊天吧";
      return;
    }

    chatEmpty.hidden = true;
    messages.forEach(function (message) {
      if (message.role === "user" || message.role === "assistant") {
        appendMessage(
          message.role,
          message.content || "",
          false,
          message.reasoning_content || ""
        );
      }
    });
    scrollToBottom();
  }

  function parseJsonPayload(content) {
    var text = String(content == null ? "" : content).trim();
    var fenced = text.match(/^```(?:json)?\s*([\s\S]*?)\s*```$/i);
    if (fenced) {
      text = fenced[1].trim();
    }
    if (text.charAt(0) !== "{") {
      var objectStart = text.indexOf("{");
      if (objectStart === -1) {
        return null;
      }
      text = text.slice(objectStart);
    }

    try {
      var payload = JSON.parse(text);
      return payload && typeof payload === "object" && !Array.isArray(payload)
        ? payload
        : null;
    } catch (error) {
      // 模型偶尔会在 JSON 前后带说明文字，尝试截取最外层对象。
    }

    var start = text.indexOf("{");
    var end = text.lastIndexOf("}");
    if (start === -1 || end <= start) {
      return null;
    }
    try {
      var embedded = JSON.parse(text.slice(start, end + 1));
      return embedded && typeof embedded === "object" && !Array.isArray(embedded)
        ? embedded
        : null;
    } catch (error) {
      return null;
    }
  }

  function extractFinalReply(content) {
    var text = String(content == null ? "" : content);
    var marker = "# 最终回复";
    var index = text.lastIndexOf(marker);
    if (index === -1) {
      return text;
    }
    return text
      .slice(index + marker.length)
      .replace(/^\s*\n?/, "")
      .trim();
  }

  function normalizeAssistantContent(content, reasoningContent) {
    var text = String(content == null ? "" : content);
    var reasoning = String(reasoningContent == null ? "" : reasoningContent);
    var payload = parseJsonPayload(text);

    if (payload) {
      if (typeof payload.content === "string") {
        text = payload.content;
      }
      if (!reasoning && typeof payload.reasoning_content === "string") {
        reasoning = payload.reasoning_content;
      }
    }

    return {
      content: extractFinalReply(text),
      reasoning: reasoning,
    };
  }

  var reasoningDialog = document.getElementById("reasoningDialog");
  var requestedReasoning = null;
  reasoningDialog.addEventListener("close", function () {
    if (reasoningDialog.returnValue === "show" && requestedReasoning && requestedReasoning.isConnected) {
      requestedReasoning.open = true;
    }
    requestedReasoning = null;
  });

  function appendReasoning(bubble, reasoning, label) {
    var details = document.createElement("details");
    details.className = "message__reasoning";

    var summary = document.createElement("summary");
    summary.textContent = label || "思考内容";
    summary.addEventListener("click", function (event) {
      if (summary.hasAttribute("aria-disabled")) {
        event.preventDefault();
        return;
      }
      if (details.open) return;
      event.preventDefault();
      if (reasoningDialog.open) return;
      requestedReasoning = details;
      reasoningDialog.returnValue = "";
      reasoningDialog.showModal();
    });

    var body = document.createElement("div");
    body.className = "message__reasoning-text";
    body.textContent = reasoning;

    details.appendChild(summary);
    details.appendChild(body);
    bubble.appendChild(details);
    return { details: details, summary: summary, body: body };
  }

  function appendMessage(role, content, shouldScroll, reasoningContent) {
    chatEmpty.hidden = true;

    var normalized = role === "assistant"
      ? normalizeAssistantContent(content, reasoningContent)
      : {
          content: String(content == null ? "" : content),
          reasoning: "",
        };

    var row = document.createElement("div");
    row.className = "message message--" + role;

    var bubble = document.createElement("div");
    bubble.className = "message__bubble";
    bubble.textContent = normalized.content;
    if (role === "assistant" && normalized.reasoning.trim()) {
      appendReasoning(bubble, normalized.reasoning);
    }
    row.appendChild(bubble);

    messageList.appendChild(row);

    if (shouldScroll !== false) {
      scrollToBottom();
    }
    return row;
  }

  function appendPendingReply(streaming, thinking) {
    var label = thinking ? "正在思考…" : "正在回复…";
    var row = appendMessage("assistant", "", false);
    var bubble = row.firstElementChild;
    var reasoning = appendReasoning(bubble, "", label);
    reasoning.details.classList.add("message__reasoning--leading");
    var reply = document.createElement("div");
    bubble.appendChild(reply);
    reasoning.body.textContent = "等待模型返回思考内容…";
    var thought = "";
    if (!streaming) {
      reasoning.summary.setAttribute("aria-disabled", "true");
    }
    function dismissPrompt() {
      if (reasoningDialog.open && requestedReasoning === reasoning.details) {
        reasoningDialog.close("cancel");
      }
    }
    scrollToBottom();
    return {
      update: function (event) {
        if (event.type === "start") {
          thought = "";
          reasoning.summary.textContent = label;
          reasoning.body.textContent = "等待模型返回思考内容…";
          reply.textContent = "";
        } else if (event.type === "reasoning") {
          thought += event.text;
          reasoning.body.textContent = thought;
        } else if (event.type === "content") {
          reasoning.summary.textContent = thought ? "思考完成" : "正在回复…";
          reply.appendChild(document.createTextNode(event.text));
        }
      },
      finish: function (data) {
        var normalized = normalizeAssistantContent(data.content, data.reasoning_content);
        if (normalized.reasoning.trim()) {
          reasoning.summary.removeAttribute("aria-disabled");
          reasoning.summary.textContent = "思考完成 · 查看思考内容";
          reasoning.body.textContent = normalized.reasoning;
        } else {
          dismissPrompt();
          reasoning.details.remove();
        }
        reply.textContent = normalized.content || "（没有收到回复）";
      },
      remove: function () {
        dismissPrompt();
        row.remove();
      },
    };
  }

  async function streamRequest(url, options, onEvent) {
    var response = await fetch(url, options);
    if (!response.ok) {
      var errorData = await response.json().catch(function () { return {}; });
      throw new Error(errorData.error || "请求失败（HTTP " + response.status + "）");
    }
    var reader = response.body.getReader();
    var decoder = new TextDecoder();
    var buffer = "";
    try {
      while (true) {
        var chunk = await reader.read();
        if (chunk.done) throw new Error("连接已中断，未收到完整回复");
        buffer += decoder.decode(chunk.value, { stream: true });
        var lines = buffer.split("\n");
        buffer = lines.pop();
        for (var line of lines) {
          if (!line.trim()) continue;
          var event = JSON.parse(line);
          if (event.type === "done") return event;
          if (event.type === "error") throw new Error(event.error);
          onEvent(event);
        }
      }
    } finally {
      await reader.cancel().catch(function () {});
      reader.releaseLock();
    }
  }

  function scrollToBottom() {
    messageList.scrollTop = messageList.scrollHeight;
  }

  function resizeChatInput() {
    chatInput.style.height = "auto";
    chatInput.style.height = Math.min(chatInput.scrollHeight, 160) + "px";
  }

  function applyPortrait(element, character) {
    var image = document.createElement("img");
    image.alt = "";
    image.loading = "eager";
    image.addEventListener("load", function () {
      Array.from(element.childNodes).forEach(function (node) {
        if (node.nodeType === Node.TEXT_NODE) node.remove();
      });
    });
    image.src = API_CHARACTERS + "/" + encodeURIComponent(character.english_name) + "/images/calm.png";
    image.addEventListener("error", function () { image.remove(); });
    element.appendChild(image);
  }

  function renderRoleList() {
    roleList.querySelectorAll("[data-role-item]").forEach(function (node) {
      node.remove();
    });

    state.characters.forEach(function (character) {
      var button = document.createElement("button");
      button.type = "button";
      button.className = "list-item role-item";
      button.dataset.roleItem = "true";
      button.title =
        "打开角色：" + character.name + "（" + character.english_name + "）";
      button.innerHTML =
        '<span class="avatar" aria-hidden="true"></span>' +
        '<span class="list-item__label"></span>' +
        '<svg class="list-item__chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
        '<path d="m9 18 6-6-6-6"></path>' +
        "</svg>";

      button.querySelector(".avatar").textContent = initialOf(character.name);
      applyPortrait(button.querySelector(".avatar"), character);
      button.querySelector(".list-item__label").textContent = character.name;
      button.addEventListener("click", function () {
        requestLeave(function () {
          showRole(character);
        });
      });

      roleList.appendChild(button);
    });
  }

  function loadCharacters() {
    return apiRequest(API_CHARACTERS)  // 角色接口地址
      .then(function (data) {
        state.characters = Array.isArray(data.characters)
          ? data.characters
          : [];
        renderRoleList();
      })
      .catch(function (error) {
        showToast(errorText(error), true);
      });
  }

  function updateProviderFields() {
    var isOllama = provider.value === "ollama";
    var isOther = provider.value === "other";
    var isClaudeOther = provider.value === "claude_other";
    var isCustom = isOther || isClaudeOther;

    apiKeyField.hidden = isOllama;
    baseUrlField.hidden = !isCustom;
    ollamaHint.hidden = !isOllama;

    apiKey.required = !isOllama;
    baseUrl.required = isCustom;
  }

  function getEmbeddingConfig() {
    return (
      EMBEDDING_PROVIDER_DEFAULTS[embeddingProvider.value] ||
      EMBEDDING_PROVIDER_DEFAULTS.other
    );
  }

  function updateEmbeddingFields(forceBaseUrl) {
    var enabled = embeddingEnabled.checked;
    var config = getEmbeddingConfig();
    var fields = [
      embeddingProvider,
      embeddingModel,
      embeddingApiKey,
      embeddingBaseUrl,
    ];

    embeddingFields.hidden = !enabled;
    fields.forEach(function (field) {
      field.disabled = !enabled;
    });

    if (!enabled) {
      embeddingProvider.required = false;
      embeddingModel.required = false;
      embeddingApiKey.required = false;
      embeddingBaseUrl.required = false;
      return;
    }

    var isOllama = embeddingProvider.value === "ollama";
    embeddingProvider.required = true;
    embeddingModel.required = true;
    embeddingBaseUrl.required = true;
    embeddingApiKey.required = !isOllama;
    embeddingApiKeyField.hidden = isOllama;
    embeddingApiKey.disabled = isOllama;

    if (forceBaseUrl || !embeddingBaseUrl.value.trim()) {
      embeddingBaseUrl.value = config.baseUrl;
    }

    embeddingModel.placeholder = config.modelHint;
    embeddingModelHint.textContent = config.modelHint;
    embeddingHint.textContent = config.hint;
  }

  function resetRoleImage(field, clearInput) {
    field.token += 1;
    field.file = null;
    field.poster = null;
    if (field.videoPreview) { field.videoPreview.remove(); field.videoPreview = null; }
    if (field.videoUrl) { URL.revokeObjectURL(field.videoUrl); field.videoUrl = null; }
    field.checking = false;
    if (field.previewUrl) URL.revokeObjectURL(field.previewUrl);
    field.previewUrl = null;
    if (clearInput !== false) field.input.value = "";
    field.preview.hidden = true;
    field.preview.removeAttribute("src");
    field.status.hidden = true;
    field.status.textContent = "";
    field.error.hidden = true;
    field.error.textContent = "";
    field.input.removeAttribute("aria-invalid");
    field.clear.hidden = true;
  }

  function showRoleImageError(field, message) {
    field.error.textContent = message;
    field.error.hidden = false;
    field.input.setAttribute("aria-invalid", "true");
    field.status.hidden = true;
  }

  function previewRoleImage(field) {
    var file = field.input.files[0];
    resetRoleImage(field, false);
    if (!file) return;
    field.clear.hidden = false;
    if (!/\.(png|jpe?g|gif|mp4)$/i.test(file.name)) { showRoleImageError(field, "请选择 PNG、JPG、GIF 或 MP4 文件。"); return; }
    if (!file.size || file.size > MAX_ROLE_IMAGE_BYTES) { showRoleImageError(field, "文件不能为空，且不能超过 10MB。"); return; }
    var token = field.token;
    field.checking = true; field.status.hidden = false; field.status.textContent = "正在检查文件…";
    var video = /\.mp4$/i.test(file.name);
    var check = video ? window.SoulMedia.poster(file) : Promise.resolve(null);
    check.then(function (poster) {
      if (token !== field.token) return;
      var url = URL.createObjectURL(poster || file);
      field.previewUrl = url;
      var image = new Image(); image.src = url;
      return image.decode().then(function () {
        if (token !== field.token) return;
        if (!image.naturalWidth || !image.naturalHeight || image.naturalWidth * image.naturalHeight > MAX_ROLE_IMAGE_PIXELS) throw new Error("图片无法读取或超过 2500 万像素。");
        field.file = file; field.poster = poster; field.preview.src = url; field.preview.hidden = false;
        if (video) {
          var player = document.createElement("video"); player.className = field.preview.className; player.controls = true; player.muted = true; player.loop = true; player.playsInline = true;
          field.videoUrl = URL.createObjectURL(file); player.src = field.videoUrl; field.preview.hidden = true; field.preview.after(player); field.videoPreview = player;
        }
        field.status.textContent = "已选择：" + file.name + (video ? "（视频预览帧）" : "");
      });
    }).catch(function (error) {
      if (token === field.token) showRoleImageError(field, error.message || "文件无法读取，请重新选择。");
    }).finally(function () { if (token === field.token) field.checking = false; });
  }

  function makeImageField(emotion, input, preview, status, error, clear) {
    var field = { emotion: emotion, input: input, preview: preview, status: status,
      error: error, clear: clear, token: 0, file: null, previewUrl: null, checking: false };
    input.addEventListener("change", function () { previewRoleImage(field); });
    clear.addEventListener("click", function () { resetRoleImage(field); });
    return field;
  }

  var imageFields = [makeImageField("calm", roleImage, roleImagePreview, roleImageStatus, roleImageError, clearRoleImageButton)];
  EMOTION_IMAGES.forEach(function (item) {
    var emotion = item[0], label = item[1];
    var card = document.createElement("div");
    card.className = "emotion-image";
    card.innerHTML = '<div class="emotion-image__title">' + label + '<small>' + emotion + '</small></div>' +
      '<img class="emotion-image__preview" alt="' + label + '形象预览" hidden>' +
      '<input class="emotion-image__input" id="emotion-' + emotion + '" type="file" accept=".png,.jpg,.jpeg,.gif,.mp4,image/png,image/jpeg,image/gif,video/mp4" aria-label="' + label + '形象素材" aria-describedby="emotion-error-' + emotion + '">' +
      '<label class="emotion-image__picker" for="emotion-' + emotion + '">选择图片或视频</label>' +
      '<span class="emotion-image__status" role="status" aria-live="polite" hidden></span>' +
      '<button class="emotion-image__clear" type="button" hidden>移除素材</button>' +
      '<p class="form-error" id="emotion-error-' + emotion + '" role="alert" hidden></p>';
    document.getElementById("emotionImageFields").appendChild(card);
    imageFields.push(makeImageField(emotion, card.querySelector("input"), card.querySelector("img"),
      card.querySelector(".emotion-image__status"), card.querySelector(".form-error"), card.querySelector("button")));
  });

  addDialoguePair.addEventListener("click", function () {
    var row = document.createElement("fieldset");
    row.className = "dialogue-example";
    row.innerHTML = '<legend>对话示例</legend>' +
      '<label class="field"><span class="field__label">用户输入</span><textarea class="field__input field__textarea" data-example-user rows="2" placeholder="用户会说什么？"></textarea></label>' +
      '<label class="field"><span class="field__label">角色回答</span><textarea class="field__input field__textarea" data-example-answer rows="2" placeholder="角色会如何回答？"></textarea></label>' +
      '<button class="dialogue-example__remove" type="button">移除此条</button>';
    row.querySelector("button").addEventListener("click", function () { row.remove(); });
    dialoguePairs.appendChild(row);
    row.querySelector("[data-example-user]").focus();
  });

  function updateSearchFields() {
    var enabled = searchEnabled.checked;
    var custom = enabled && searchProvider.value === "custom";
    searchFields.hidden = !enabled;
    searchProvider.disabled = !enabled;
    searchApiKey.disabled = !enabled;
    searchApiKey.required = enabled;
    searchBaseUrlField.hidden = !custom;
    searchBaseUrl.disabled = !custom;
    searchBaseUrl.required = custom;
    searchHeaderField.hidden = !custom;
    searchHeader.disabled = !custom;
  }

  function resetCreateForm() {
    createRoleForm.reset();
    dialoguePairs.replaceChildren();
    document.getElementById("forgettingHelp").open = false;
    imageFields.forEach(function (field) { resetRoleImage(field); });
    advancedFields.open = false;
    createRoleError.hidden = true;
    createRoleError.textContent = "";
    updateProviderFields();
    updateEmbeddingFields(true);
    updateSearchFields();
  }

  var roleWorld = document.getElementById("roleWorld"), availableWorlds = [];
  function loadRoleWorlds() {
    return apiRequest("/api/worlds").then(function (data) {
      availableWorlds = data.worlds;
      roleWorld.replaceChildren();
      availableWorlds.forEach(function (world) { var option = document.createElement("option"); option.value = world.id; option.textContent = world.name; roleWorld.appendChild(option); });
      roleWorld.value = "reality";
    }).catch(function () { createRoleError.textContent = "世界观列表加载失败，请关闭后重试。"; createRoleError.hidden = false; });
  }

  function openCreateModal() {
    window.dispatchEvent(new Event("lingqi:skip-welcome"));
    var notice = document.getElementById('createNotice');
    if (!notice.open) notice.showModal();
  }

  document.getElementById('cancelCreateNotice').addEventListener('click', function () {
    document.getElementById('createNotice').close();
  });
  document.getElementById('acceptCreateNotice').addEventListener('click', function () {
    document.getElementById('createNotice').close();
    resetCreateForm();
    loadRoleWorlds();
    createRoleModal.hidden = false;
    document.body.classList.add("modal-open");
    window.setTimeout(function () {
      if (mobileLayout.matches) closeCreateRoleModal.focus({ preventScroll: true });
      else roleName.focus();
    }, 0);
  });

  function closeCreateModal() {
    createRoleModal.hidden = true;
    document.body.classList.remove("modal-open");
    resetCreateForm();
  }

  function setCreateSubmitting(isSubmitting) {
    createRoleSubmit.disabled = isSubmitting;
    addDialoguePair.disabled = isSubmitting;
    dialoguePairs.querySelectorAll("textarea, button").forEach(function (element) { element.disabled = isSubmitting; });
    imageFields.forEach(function (field) { field.input.disabled = isSubmitting; field.clear.disabled = isSubmitting; });
    createRoleSubmit.querySelector(".button-label").textContent = isSubmitting
      ? "创建中..."
      : "创建角色";
  }

  function setSummarizing(isSummarizing) {
    state.summarizing = isSummarizing;
    summarizeButton.disabled = isSummarizing;
    summarizeButton.textContent = isSummarizing ? "总结中..." : "总结";
    sendButton.disabled = isSummarizing || state.sending || state.clearing;
    continueSayButton.disabled = sendButton.disabled;
    clearHistoryButton.disabled = sendButton.disabled;
    rebuildMemoryButton.disabled = sendButton.disabled;
    segmentedReplyToggle.disabled = isSummarizing || state.sending || state.clearing || state.savingReplySettings;
    // 总结期间不允许继续输入/发送，避免前端排队请求和后端总结互相覆盖。
    chatInput.disabled = isSummarizing;
    summaryOverlay.hidden = !isSummarizing;
    chatView.setAttribute("aria-busy", isSummarizing ? "true" : "false");
  }

  function summarizeHistory(onSuccess, options) {
    if (!state.currentRole || state.sending || state.summarizing || state.clearing || state.savingReplySettings) {
      return;
    }

    var settings = options || {};
    // 总结只压缩模型上下文；不重新拉取/重绘历史，前端已有记录保持不动。
    var leaveOnError = Boolean(settings.leaveOnError);
    var role = state.currentRole;
    var token = state.viewToken;
    var afterSummary = typeof onSuccess === "function" ? onSuccess : null;
    var controller = new AbortController();
    state.controller = controller;
    setSummarizing(true);

    apiRequest(
      API_CHARACTERS +  // 角色接口地址
        "/" +
        encodeURIComponent(role.english_name) +
        "/summarize",
      {
        method: "POST",
        signal: controller.signal,
      }
    )
      .then(function (data) {
        if (
          token !== state.viewToken ||
          !state.currentRole ||
          state.currentRole.english_name !== role.english_name
        ) {
          return;
        }

        state.sessionDirty = false;
        showToast(data.message || "历史总结完成");
        if (afterSummary) {
          afterSummary();
        }
      })
      .catch(function (error) {
        if (error.name === "AbortError") {
          return;
        }
        if (
          token !== state.viewToken ||
          !state.currentRole ||
          state.currentRole.english_name !== role.english_name
        ) {
          return;
        }
        showToast(errorText(error), true);
        // 离开页面时即使总结失败也继续离开：每轮原始对话已经写入 JSON，
        // 不会因为摘要失败而丢聊天记录。
        if (leaveOnError && afterSummary) {
          afterSummary();
        }
      })
      .finally(function () {
        if (state.controller === controller) {
          state.controller = null;
          setSummarizing(false);
        }
      });
  }

  function requestLeave(onLeave) {
    var afterLeave = typeof onLeave === "function" ? onLeave : null;

    if (!state.currentRole) {
      if (afterLeave) {
        afterLeave();
      }
      return;
    }

    if (state.clearing) { showToast("正在清空聊天记录，请稍候", true); return; }
    if (state.savingReplySettings) { showToast("正在保存分段回复设置，请稍候", true); return; }
    if (state.sending) {
      showToast("正在等待角色回复，请稍候再离开", true);
      return;
    }
    if (state.summarizing) {
      return;
    }

    // 没有本轮新对话时不需要再生成一次摘要。
    if (!state.sessionDirty) {
      if (afterLeave) {
        afterLeave();
      }
      return;
    }

    summarizeHistory(afterLeave, {
      leaveOnError: true,
    });
  }

  function sendMessage(event, continueOnly) {
    event.preventDefault();

    if (sendButton.disabled || state.sending || state.summarizing || state.clearing || state.savingReplySettings || !state.currentRole) {
      return;
    }

    var text = chatInput.value.trim();
    if (!continueOnly && !text) {
      chatInput.focus();
      return;
    }

    var role = state.currentRole;
    var token = state.viewToken;
    var controller = new AbortController();
    state.controller = controller;
    state.sending = true;
    var segmented = !continueOnly && role.segmented_reply === true;
    var thinking = state.deepThinking;
    var completedSegments = 0;
    sendButton.disabled = true;
    summarizeButton.disabled = true;
    continueSayButton.disabled = true;
    clearHistoryButton.disabled = true;
    rebuildMemoryButton.disabled = true;
    segmentedReplyToggle.disabled = true;
    if (segmented) setSegmentedWaiting(true);

    if (!continueOnly) {
      appendMessage("user", text);
      chatInput.value = "";
      resizeChatInput();
    }
    var streaming = role.stream_output === true;
    var loadingRow = appendPendingReply(streaming, thinking);
    var url = continueOnly ? API_CHARACTERS + "/" + encodeURIComponent(role.english_name) + "/continue" : API_CHAT;
    var options = {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        english_name: role.english_name,
        message: continueOnly ? undefined : text,
        deep_thinking: thinking,
        recognition_time: state.recognitionTime,
        segmented_reply: continueOnly ? undefined : segmented,
      }),
      signal: controller.signal,
    };
    var pending = streaming || segmented
      ? streamRequest(url + "/stream", options, function (event) {
          if (token !== state.viewToken) return;
          var nearBottom = messageList.scrollHeight - messageList.scrollTop - messageList.clientHeight < 96;
          if (event.type === "segment_start") {
            if (!loadingRow) loadingRow = appendPendingReply(streaming, thinking);
          } else if (event.type === "segment_done") {
            loadingRow.finish(event);
            loadingRow = null;
            completedSegments += 1;
            state.sessionDirty = true;
            loadRoleBackground(role, token, event.the_choice_of_emotion);
          } else if (loadingRow) {
            loadingRow.update(event);
          }
          if (nearBottom) scrollToBottom();
        })
      : apiRequest(url, options);
    pending
      .then(function (data) {
        if (
          token !== state.viewToken ||
          !state.currentRole ||
          state.currentRole.english_name !== role.english_name
        ) {
          return;
        }

        var nearBottom = messageList.scrollHeight - messageList.scrollTop - messageList.clientHeight < 96;
        if (loadingRow) loadingRow.finish(data);
        loadingRow = null;
        if (nearBottom) scrollToBottom();
        // 只有模型成功回复并已写入后端归档，才标记有待总结的新轮次。
        state.sessionDirty = true;
        loadRoleBackground(role, token, data.the_choice_of_emotion);
        refreshRoleState();
      })
      .catch(function (error) {
        if (error.name === "AbortError") {
          return;
        }
        if (
          token !== state.viewToken ||
          !state.currentRole ||
          state.currentRole.english_name !== role.english_name
        ) {
          return;
        }

        if (loadingRow) loadingRow.remove();
        if (completedSegments) refreshRoleState();
        showToast(
          (completedSegments ? "回复中断，已保留说完的内容：" : continueOnly ? "继续说失败：" : "请求失败，本轮未发送成功：") + errorText(error),
          true
        );
        if (!mobileLayout.matches) chatInput.focus();
      })
      .finally(function () {
        if (state.controller === controller) {
          state.controller = null;
          state.sending = false;
          setSegmentedWaiting(false);
          sendButton.disabled = false;
          summarizeButton.disabled = false;
          continueSayButton.disabled = false;
          clearHistoryButton.disabled = false;
          rebuildMemoryButton.disabled = false;
          segmentedReplyToggle.disabled = state.savingReplySettings;
          if (!mobileLayout.matches) chatInput.focus();
        }
      });
  }

  continueSayButton.addEventListener("click", function (event) { sendMessage(event, true); });
  function updateClearConfirmation() {
    confirmClearButton.disabled = state.clearing || clearConfirmation.value !== clearPhrase;
  }
  clearConfirmation.addEventListener("input", updateClearConfirmation);
  clearHistoryButton.addEventListener("click", function () {
    if (!state.currentRole || state.sending || state.summarizing || state.clearing) return;
    clearTarget = state.currentRole;
    document.getElementById("clearHistoryTitle").textContent = "清空与「" + clearTarget.name + "」的聊天记录？";
    clearConfirmation.value = ""; clearError.textContent = ""; updateClearConfirmation();
    clearDialog.showModal(); clearConfirmation.focus();
  });
  cancelClearButton.addEventListener("click", function () { if (!state.clearing) clearDialog.close(); });
  clearDialog.addEventListener("cancel", function (event) { if (state.clearing) event.preventDefault(); });
  clearForm.addEventListener("submit", function (event) {
    event.preventDefault();
    if (state.clearing || !clearTarget || clearConfirmation.value !== clearPhrase) return;
    var role = clearTarget, token = state.viewToken;
    state.clearing = true; clearError.textContent = "";
    clearConfirmation.disabled = true; cancelClearButton.disabled = true;
    confirmClearButton.disabled = true; confirmClearButton.textContent = "正在清空…";
    sendButton.disabled = continueSayButton.disabled = clearHistoryButton.disabled = summarizeButton.disabled = true;
    apiRequest(API_CHARACTERS + "/" + encodeURIComponent(role.english_name) + "/clear", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ confirmation: clearPhrase })
    }).then(function (data) {
      if (token === state.viewToken && state.currentRole === role) {
        state.viewToken += 1; state.sessionDirty = false;
        resetHistoryPaging(); renderHistory(Array.isArray(data.messages) ? data.messages : []);
      }
      clearDialog.close(); showToast(data.message || "聊天记录已清空");
    }).catch(function (error) { clearError.textContent = errorText(error); }).finally(function () {
      state.clearing = false; clearConfirmation.disabled = false; cancelClearButton.disabled = false;
      confirmClearButton.textContent = "确认清空"; updateClearConfirmation();
      sendButton.disabled = continueSayButton.disabled = clearHistoryButton.disabled = summarizeButton.disabled = state.sending || state.summarizing;
    });
  });

  var rebuildDialog = document.getElementById('rebuildMemoryDialog');
  rebuildMemoryButton.addEventListener('click', function () {
    if (!state.currentRole || state.sending || state.summarizing || state.clearing) return;
    document.getElementById('rebuildMemoryTitle').textContent = '重新整理「' + state.currentRole.name + '」的记忆？';
    rebuildDialog.showModal();
  });
  document.getElementById('cancelRebuildMemory').addEventListener('click', function () { rebuildDialog.close(); });
  document.getElementById('confirmRebuildMemory').addEventListener('click', function () {
    if (!state.currentRole || state.sending || state.summarizing || state.clearing) return;
    var role = state.currentRole, title = summaryOverlay.querySelector('.summary-overlay__title'), note = summaryOverlay.querySelector('.summary-overlay__note');
    var oldTitle = title.textContent, oldNote = note.textContent;
    rebuildDialog.close(); title.textContent = '正在整理记忆'; note.textContent = '正在根据已有记录重新生成记忆，请稍候。';
    summaryOverlay.setAttribute('aria-label', '正在整理记忆'); setSummarizing(true);
    apiRequest(API_CHARACTERS + '/' + encodeURIComponent(role.english_name) + '/rebuild-memory', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({confirmed:true})})
      .then(function (data) { showToast('记忆已整理：摘要 ' + data.digest_count + ' 条，对话 ' + data.original_count + ' 条'); })
      .catch(function (error) { showToast(errorText(error), true); })
      .finally(function () { setSummarizing(false); title.textContent = oldTitle; note.textContent = oldNote; summaryOverlay.setAttribute('aria-label', '模型正在总结'); });
  });

  function setRightSidebarCollapsed(isCollapsed) {
    rightSidebar.classList.toggle("is-collapsed", isCollapsed);
    rightSidebarBody.hidden = isCollapsed;
    var actionName = isCollapsed ? "展开右侧栏" : "收起右侧栏";
    rightSidebarToggle.setAttribute("aria-label", actionName);
    rightSidebarToggle.setAttribute("title", actionName);
    rightSidebarToggle.setAttribute("aria-expanded", String(!isCollapsed));
  }

  function refreshRoleState() {
    var role = state.currentRole, token = state.viewToken;
    if (!role) return;
    document.getElementById('externalMood').textContent = '平静';
    document.getElementById('externalMoodIntensity').value = 50;
    document.getElementById('externalMoodIntensityText').textContent = '50 / 100';
    document.getElementById('moodSyncStatus').textContent = '初始心情 · 正在同步';
    apiRequest(API_CHARACTERS + '/' + encodeURIComponent(role.english_name) + '/state').then(function (data) {
      if (token !== state.viewToken) return;
      var intensity = Number(data.external_mood_intensity);
      intensity = Number.isFinite(intensity) && intensity >= 1 && intensity <= 100 ? intensity : 50;
      document.getElementById('externalMood').textContent = data.external_mood || '平静';
      document.getElementById('externalMoodIntensity').value = intensity;
      document.getElementById('externalMoodIntensityText').textContent = intensity + ' / 100';
      document.getElementById('moodSyncStatus').textContent = '此刻流露的心情';
    }).catch(function () { if (token === state.viewToken) document.getElementById('moodSyncStatus').textContent = '暂未同步，显示初始心情'; });
  }

  document.getElementById('sendInnerVoiceButton').addEventListener('click', function () {
    if (!state.currentRole || state.sending || state.summarizing || state.clearing) return;
    var role = state.currentRole;
    var title = summaryOverlay.querySelector('.summary-overlay__title');
    var note = summaryOverlay.querySelector('.summary-overlay__note');
    var oldTitle = title.textContent, oldNote = note.textContent;
    title.textContent = '角色正在写下心声';
    note.textContent = '完成后会提醒你，请稍后点击“查看心声”阅读。';
    summaryOverlay.setAttribute('aria-label', '角色正在写下心声');
    document.body.classList.add('inner-voice-busy');
    setSummarizing(true);
    apiRequest(API_CHARACTERS + '/' + encodeURIComponent(role.english_name) + '/inner-voices', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'}).then(function () {
      showToast('心声已发送，请点击“查看心声”阅读');
      if (state.currentRole === role) refreshRoleState();
    }).catch(function (error) { showToast(errorText(error), true); }).finally(function () {
      setSummarizing(false);
      document.body.classList.remove('inner-voice-busy');
      title.textContent = oldTitle; note.textContent = oldNote;
      summaryOverlay.setAttribute('aria-label', '模型正在总结');
    });
  });
  document.getElementById('viewInnerVoiceButton').addEventListener('click', function () {
    if (!state.currentRole || state.sending || state.summarizing || state.clearing) return;
    window.open('/static/html/inner_voice.html?character=' + encodeURIComponent(state.currentRole.english_name), '_blank', 'noopener');
  });

  document.getElementById('viewTrueStateButton').addEventListener('click', function () {
    if (!state.currentRole || state.sending || state.summarizing || state.clearing) return;
    var role = state.currentRole;
    window.SoulHavenReveal().then(function (accepted) {
      if (!accepted || state.currentRole !== role) return;
      try { sessionStorage.setItem('soulhaven-state-consent:' + role.english_name, String(Date.now())); } catch (ignore) {}
      location.href = '/static/html/true_state.html?character=' + encodeURIComponent(role.english_name);
    });
  });

  if (!mobileLayout.matches && window.matchMedia("(max-width: 720px)").matches) {
    setSidebarCollapsed(true);
    setRightSidebarCollapsed(true);
  }
  updateChatLayout();
  mobileLayout.addEventListener("change", updateChatLayout);
  if (window.visualViewport) {
    window.visualViewport.addEventListener("resize", updateChatViewport);
    window.visualViewport.addEventListener("scroll", updateChatViewport);
  }
  mobileRoles.addEventListener("click", function () { setMobileDrawer("roles"); });
  mobileMood.addEventListener("click", function () { setMobileDrawer("mood"); });
  chatDrawerBackdrop.addEventListener("click", function () { setMobileDrawer("", true); });
  mobileMore.addEventListener("click", function () {
    setMobileActions(mobileMore.getAttribute("aria-expanded") === "false");
  });
  chatInput.addEventListener("focus", function () { setMobileActions(false); });

  rightSidebarToggle.addEventListener("click", function () {
    if (mobileLayout.matches) setMobileDrawer("", true);
    else setRightSidebarCollapsed(!rightSidebar.classList.contains("is-collapsed"));
  });

  sidebarToggle.addEventListener("click", function () {
    if (mobileLayout.matches) setMobileDrawer("", true);
    else setSidebarCollapsed(!sidebar.classList.contains("is-collapsed"));
  });

  backButton.addEventListener("click", function () {
    requestLeave(showHome);
  });

  function sendSummaryBeacon(event) {
    // 进入往返缓存时页面还可能恢复，不在此时总结，避免恢复后状态错位。
    if (event && event.persisted) {
      return;
    }
    if (
      !state.currentRole ||
      !state.sessionDirty ||
      state.sending ||
      state.summarizing ||
      state.clearing
    ) {
      return;
    }

    var url =
      API_CHARACTERS +  // 角色接口地址
      "/" +
      encodeURIComponent(state.currentRole.english_name) +
      "/summarize";

    try {
      if (navigator.sendBeacon && navigator.sendBeacon(url)) {
        return;
      }
    } catch (error) {
      // sendBeacon 不可用时退回 keepalive fetch。
    }

    fetch(url, {
      method: "POST",
      keepalive: true,
    }).catch(function () {
      // 页面已经离开，无法再向用户展示错误；每轮 JSON 已经独立落盘。
    });
  }

  // 关闭/刷新页面时只能尽力通知后端总结，不能等待异步结果。
  window.addEventListener("pagehide", sendSummaryBeacon);

  createRoleButton.addEventListener("click", openCreateModal);
  document.getElementById("welcomeCreateButton").addEventListener("click", openCreateModal);
  closeCreateRoleModal.addEventListener("click", closeCreateModal);
  cancelCreateRole.addEventListener("click", closeCreateModal);

  createRoleModal.addEventListener("click", function (event) {
    if (event.target && event.target.getAttribute("data-close-modal") === "true") {
      closeCreateModal();
    }
  });

  document.addEventListener("keydown", function (event) {
    if (event.key !== "Escape" || event.defaultPrevented) return;
    if (!createRoleModal.hidden) {
      closeCreateModal();
    } else if (!document.querySelector("dialog[open]")) {
      if (chatApp.dataset.drawer) setMobileDrawer("", true);
      else if (mobileMore.getAttribute("aria-expanded") === "true") {
        setMobileActions(false);
        mobileMore.focus();
      }
    }
  });

  provider.addEventListener("change", updateProviderFields);
  embeddingEnabled.addEventListener("change", function () {
    updateEmbeddingFields(false);
  });
  embeddingProvider.addEventListener("change", function () {
    updateEmbeddingFields(true);
  });
  searchEnabled.addEventListener("change", updateSearchFields);
  searchProvider.addEventListener("change", updateSearchFields);
  createRoleForm.addEventListener("invalid", function (event) {
    if (searchFields.contains(event.target)) advancedFields.open = true;
  }, true);
  summarizeButton.addEventListener("click", summarizeHistory);
  deepThinkingToggle.addEventListener("change", function () {
    setDeepThinking(deepThinkingToggle.checked, true);
  });
  recognitionTimeToggle.addEventListener("change", function () {
    setRecognitionTime(recognitionTimeToggle.checked, true);
  });
  segmentedReplyToggle.addEventListener("change", function () {
    var role = state.currentRole;
    if (!role || state.sending || state.summarizing || state.clearing || state.savingReplySettings) {
      segmentedReplyToggle.checked = Boolean(role && role.segmented_reply);
      return;
    }
    var enabled = segmentedReplyToggle.checked;
    state.savingReplySettings = true;
    segmentedReplyToggle.disabled = sendButton.disabled = continueSayButton.disabled = true;
    apiRequest(API_CHARACTERS + "/" + encodeURIComponent(role.english_name) + "/reply-settings", {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ segmented_reply: enabled }),
    }).then(function (data) {
      role.segmented_reply = data.segmented_reply;
    }).catch(function (error) {
      if (state.currentRole === role) segmentedReplyToggle.checked = role.segmented_reply === true;
      showToast("分段回复设置保存失败：" + errorText(error), true);
    }).finally(function () {
      state.savingReplySettings = false;
      segmentedReplyToggle.disabled = sendButton.disabled = continueSayButton.disabled = state.sending || state.summarizing || state.clearing;
    });
  });

  createRoleForm.addEventListener("submit", function (event) {
    event.preventDefault();

    if (!createRoleForm.reportValidity()) {
      return;
    }

    var invalidImage = imageFields.find(function (field) { return field.checking || !field.error.hidden; });
    if (invalidImage) {
      createRoleError.textContent = invalidImage.checking
        ? "正在检查素材，请稍候再创建角色。"
        : "请重新选择有效素材，或移除素材后创建角色。";
      createRoleError.hidden = false;
      if (invalidImage.emotion !== "calm") advancedFields.open = true;
      invalidImage.input.focus();
      return;
    }

    var dialogueLines = [];
    var incompleteExample = false;
    dialoguePairs.querySelectorAll(".dialogue-example").forEach(function (row, index) {
      var user = row.querySelector("[data-example-user]");
      var answer = row.querySelector("[data-example-answer]");
      if (!user.value.trim() || !answer.value.trim()) {
        if (!incompleteExample) {
          incompleteExample = true;
          (user.value.trim() ? answer : user).focus();
        }
        return;
      }
      dialogueLines.push("示例 " + (index + 1) + "\n用户：" + user.value.trim() + "\n角色：" + answer.value.trim());
    });
    if (incompleteExample) {
      createRoleError.textContent = "请填写每条示例的用户输入和角色回答，或移除不需要的示例。";
      createRoleError.hidden = false;
      return;
    }

    createRoleError.hidden = true;
    if (!characterBrief.value.trim()) {
      createRoleError.textContent = "请填写角色简介。";
      createRoleError.hidden = false;
      characterBrief.focus();
      return;
    }
    var selectedWorld = availableWorlds.find(function (world) { return world.id === roleWorld.value; });
    if (!selectedWorld) { createRoleError.textContent = "请等待世界观列表加载，或关闭窗口后重试。"; createRoleError.hidden = false; return; }
    if (!embeddingEnabled.checked && selectedWorld.directory.length && selectedWorld.details.length && !window.confirm("未配置记忆模型，角色无法检索该世界观的详细资料，可能忽略其中的信息。建议启用记忆模型。仍要创建吗？")) return;
    createRoleError.textContent = "";
    setCreateSubmitting(true);

    var selectedProvider = provider.value;
    var embeddingOn = embeddingEnabled.checked;
    var selectedEmbeddingProvider = embeddingOn
      ? embeddingProvider.value
      : "";
    var embeddingIsOllama = selectedEmbeddingProvider === "ollama";
    var payload = {
      name: roleName.value.trim(),
      english_name: englishName.value.trim(),
      world_id: roleWorld.value,
      gender: roleGender.value.trim(),
      base_info: characterDescription.value.trim(),
      brief: characterBrief.value.trim(),
      opening_line: openingLine.value.trim(),
      age: age.value.trim(),
      height: height.value.trim(),
      weight: weight.value.trim(),
      hometown: hometown.value.trim(),
      current_location: currentLocation.value.trim(),
      initial_relationship: initialRelationship.value.trim(),
      dialogue_examples: [dialogueExamples.value.trim()].concat(dialogueLines).filter(Boolean).join("\n\n"),
      speaking_style: speakingStyle.value.trim(),
      personality_traits: personalityTraits.value.trim(),
      provider: selectedProvider,
      temperature: Number(temperature.value),
      stream_output: createRoleForm.elements.stream_output.value === "on",
      model: modelName.value.trim(),
      api_key: selectedProvider === "ollama" ? "" : apiKey.value.trim(),
      base_url: selectedProvider === "other" || selectedProvider === "claude_other"
        ? baseUrl.value.trim()
        : "",
      embedding_enabled: embeddingOn,
      search_enabled: searchEnabled.checked,
      search_provider: searchProvider.disabled ? "" : searchProvider.value,
      search_api_key: searchApiKey.disabled ? "" : searchApiKey.value.trim(),
      search_base_url: searchBaseUrl.disabled ? "" : searchBaseUrl.value.trim(),
      search_header: searchHeader.disabled ? "" : searchHeader.value.trim(),
      embedding_probabilistic_forgetting: embeddingOn && document.getElementById("probabilisticForgetting").checked,
      embedding_provider: selectedEmbeddingProvider,
      embedding_model: embeddingOn ? embeddingModel.value.trim() : "",
      embedding_api_key: embeddingOn && !embeddingIsOllama
        ? embeddingApiKey.value.trim()
        : "",
      embedding_base_url: embeddingOn
        ? embeddingBaseUrl.value.trim()
        : "",
    };

    var requestOptions = {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    };
    if (imageFields.some(function (field) { return field.file; })) {
      var formData = new FormData();
      formData.append("data", JSON.stringify(payload));
      imageFields.forEach(function (field) {
        if (field.file) {
          var key = field.emotion === "calm" ? "image" : "image_" + field.emotion;
          formData.append(key, field.file);
          if (field.poster) formData.append(key + "_poster", field.poster, "poster.png");
        }
      });
      // 浏览器负责 multipart boundary，不能手动设置 Content-Type。
      requestOptions = { method: "POST", body: formData };
    }

    apiRequest(API_CHARACTERS, requestOptions)
      .then(function (data) {
        closeCreateModal();
        showToast("角色创建成功");
        return loadCharacters().then(function () {
          var created = state.characters.find(function (character) {
            return character.english_name === payload.english_name;
          });
          showRole(created || data.character);
        });
      })
      .catch(function (error) {
        createRoleError.textContent = errorText(error);
        createRoleError.hidden = false;
      })
      .finally(function () {
        setCreateSubmitting(false);
      });
  });

  chatForm.addEventListener("submit", sendMessage);

  chatInput.addEventListener("input", resizeChatInput);

  chatInput.addEventListener("paste", function (event) {
    var clipboard = event.clipboardData;
    if (!clipboard) return;

    var hasFile = clipboard.files.length > 0 || Array.from(clipboard.items).some(function (item) {
      return item.kind === "file";
    });
    if (!hasFile) return;

    if (!clipboard.getData("text/plain")) event.preventDefault();
    showToast("图片和文件的上传与解析功能还在开发中。");
  });

  chatInput.addEventListener("keydown", function (event) {
    if (
      event.key === "Enter" &&
      !mobileLayout.matches &&
      !event.shiftKey &&
      !event.isComposing
    ) {
      event.preventDefault();
      chatForm.requestSubmit();
    }
  });

  setDeepThinking(readStoredDeepThinking(), false);
  setRecognitionTime(readStoredRecognitionTime(), false);
  updateEmbeddingFields(true);
  updateSearchFields();
  var pageUrl = new URL(window.location.href);
  var requestedRole = pageUrl.searchParams.get('character');
  loadCharacters().then(function () {
    if (!requestedRole) return;
    var role = state.characters.find(function (item) { return item.english_name === requestedRole; });
    if (role) showRole(role);
    else showToast('这个角色暂时无法打开，请从左侧重新选择。', true);
  });
  if (pageUrl.searchParams.get("create") === "1") {
    pageUrl.searchParams.delete("create");
    window.history.replaceState(null, "", pageUrl.pathname + pageUrl.search + pageUrl.hash);
    window.setTimeout(openCreateModal, 0);
  }
})();
