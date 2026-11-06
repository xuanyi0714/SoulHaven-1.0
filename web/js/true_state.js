(function () {
  'use strict';
  var role = new URLSearchParams(location.search).get('character'), $ = function (id) { return document.getElementById(id); };
  var accepted = false, busy = false;
  if (!role) { $('trueStateStatus').textContent = '请从角色聊天页面打开心底星图。'; $('revealTrueState').hidden = true; return; }
  var endpoint = '/api/characters/' + encodeURIComponent(role);
  $('backToChat').href = '/chat.html?character=' + encodeURIComponent(role); $('stateVoiceLink').href += '?character=' + encodeURIComponent(role);
  var portrait = $('characterPortrait'); portrait.onload = function () { portrait.hidden = false; $('portraitFallback').hidden = true; }; portrait.onerror = function () { portrait.hidden = true; $('portraitFallback').hidden = false; }; portrait.src = endpoint + '/images/calm.png';
  function load() {
    if (!accepted || busy) return;
    busy = true; $('refreshTrueState').disabled = true; $('trueStateStatus').textContent = '正在轻轻翻开，心底的那一页…';
    fetch(endpoint + '/true-state', {method:'POST', cache:'no-store', headers:{'Content-Type':'application/json'},body:JSON.stringify({acknowledged:true})}).then(function (r) { if (!r.ok) throw new Error(); return r.json(); }).then(function (data) {
      var s = data.state, ui = window.SoulHavenFeelings, primary = $('primaryStateMetrics');
      primary.replaceChildren(); primary.appendChild(ui.card('affection', '此刻的好感度', String(s.affection_level), s.affection_level, s.affection_reason, '把每一次靠近，写进心的年轮。', 'A PLACE FOR YOU'));
      primary.appendChild(ui.card('mood', '真实主要心情 · ' + s.inner_mood_intensity + ' / 100', s.inner_mood, s.inner_mood_intensity, s.mood_reason, '表面未曾说尽的，月光都知道。', 'THE FEELING WITHIN'));
      ui.secondary($('secondaryStateMetrics'), s.secondary_feelings); $('stateAttitude').textContent = s.attitude_to_user;
      $('trueStateContent').hidden = false; $('revealTrueState').hidden = true; $('refreshTrueState').hidden = false;
      $('portraitName').textContent = data.name; $('stateSubtitle').textContent = '「' + data.name + '」的真实心情与关系温度 · 来自最近一次保存的状态'; document.title = data.name + '的心底星图 · 灵栖';
      $('trueStateStatus').textContent = '这里是 TA 此刻真实的内心，不一定与外在流露相同。情绪会随故事改变，数字不替代彼此的理解。';
      $('stateUpdatedAt').textContent = s.updated_at ? '心意留存于 ' + s.updated_at.replace('T',' ').replace('+08:00','') + ' · 北京时间' : '故事刚刚开始，心意会慢慢留下痕迹。';
    }).catch(function () { $('trueStateStatus').textContent = '这一页暂时没能读到，稍后轻轻刷新试试。'; $('refreshTrueState').hidden = false; }).finally(function () { busy = false; $('refreshTrueState').disabled = false; });
  }
  function reveal() { window.SoulHavenReveal().then(function (yes) { if (yes) { accepted = true; load(); } }); }
  $('revealTrueState').onclick = reveal; $('refreshTrueState').onclick = load;
  var consent = false;
  try { var key = 'soulhaven-state-consent:' + role, when = Number(sessionStorage.getItem(key)); sessionStorage.removeItem(key); consent = when > 0 && Date.now() - when >= 0 && Date.now() - when < 30000; } catch (ignore) {}
  if (consent) { accepted = true; load(); }
})();
