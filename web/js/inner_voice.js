(function () {
  'use strict';
  var role = new URLSearchParams(location.search).get('character');
  var status = document.getElementById('voiceStatus'), list = document.getElementById('voiceList'), content = document.getElementById('voiceContent'), metrics = document.getElementById('voiceMetrics');
  if (!role) { status.textContent = '请从角色聊天页面打开心声。'; return; }
  document.getElementById('backToChat').href = '/chat.html?character=' + encodeURIComponent(role);
  document.getElementById('voiceTrueStateLink').href += '?character=' + encodeURIComponent(role);
  var portrait = document.getElementById('characterPortrait');
  portrait.onload = function () { portrait.hidden = false; document.getElementById('portraitFallback').hidden = true; };
  portrait.onerror = function () { portrait.hidden = true; document.getElementById('portraitFallback').hidden = false; };
  portrait.src = '/api/characters/' + encodeURIComponent(role) + '/images/calm.png';
  fetch('/api/characters', {cache: 'no-store'}).then(function (r) { if (!r.ok) throw new Error(); return r.json(); }).then(function (data) {
    var person = data.characters.find(function (item) { return item.english_name === role; });
    if (person) { document.getElementById('voiceSubtitle').textContent = '来自「' + person.name + '」的心声 · 将每一份心意，好好珍藏。'; document.title = person.name + '的心声 · 灵栖'; document.getElementById('portraitName').textContent = person.name; portrait.alt = person.name + '的角色形象'; document.getElementById('portraitFallback').textContent = person.name.slice(0, 1); }
  }).catch(function () {});
  function node(tag, text, cls) { var el = document.createElement(tag); if (text != null) el.textContent = text; if (cls) el.className = cls; return el; }
  function decoratePaper() {
    var frame = node('div', null, 'paper-ornaments'); frame.setAttribute('aria-hidden', 'true');
    ['tl', 'tr', 'bl', 'br'].forEach(function (corner) { frame.appendChild(node('span', null, 'paper-corner paper-corner--' + corner)); });
    frame.appendChild(node('span', null, 'paper-lace'));
    for (var i = 0; i < 4; i++) frame.appendChild(node('span', '✧', 'paper-glint paper-glint--' + i));
    content.appendChild(frame);
  }
  decoratePaper();
  // 仅创建受控 DOM，不将模型文本当成 HTML。支持常用 Markdown 的块与行内语法。
  function inline(parent, text) {
    var pattern = /\*\*([^*]+)\*\*|__([^_]+)__|\x60([^\x60]+)\x60|\*([^*\n]+)\*|~~([^~]+)~~|\[([^\]]+)\]\(([^\s)]+)\)/g, match, end = 0;
    while ((match = pattern.exec(text))) {
      parent.appendChild(document.createTextNode(text.slice(end, match.index)));
      var el;
      if (match[1] || match[2]) el = node('strong', match[1] || match[2]);
      else if (match[3]) el = node('code', match[3]);
      else if (match[4]) el = node('em', match[4]);
      else if (match[5]) el = node('del', match[5]);
      else {
        el = node('span', match[6]);
        try { var url = new URL(match[7], location.href); if (/^https?:$/.test(url.protocol)) { el = node('a', match[6]); el.href = url.href; el.target = '_blank'; el.rel = 'noopener noreferrer'; } } catch (ignore) {}
      }
      parent.appendChild(el); end = pattern.lastIndex;
    }
    parent.appendChild(document.createTextNode(text.slice(end)));
  }
  function markdown(target, source) {
    var lines = String(source).replace(/\r/g, '').split('\n'), i = 0;
    function special(s) { return /^(#{1,6}\s|\s*[-*+]\s|\s*\d+[.)]\s|>\s?|\x60{3}|~~~|\s*$|\s*(?:-{3,}|\*{3,})\s*$)/.test(s); }
    while (i < lines.length) {
      var line = lines[i], m, el;
      if (!line.trim()) { i++; continue; }
      if (/^(\x60{3}|~~~)/.test(line)) {
        var fence = line.slice(0,3), code = []; i++;
        while (i < lines.length && lines[i].slice(0,3) !== fence) code.push(lines[i++]);
        if (i < lines.length) i++;
        el = node('pre'); el.appendChild(node('code', code.join('\n'))); target.appendChild(el); continue;
      }
      if ((m = line.match(/^(#{1,6})\s+(.+)$/))) { el = node('h' + m[1].length); inline(el, m[2]); target.appendChild(el); i++; continue; }
      if (/^\s*(?:-{3,}|\*{3,}|_{3,})\s*$/.test(line)) { target.appendChild(node('hr')); i++; continue; }
      if (/^>/.test(line)) {
        var quote = []; while (i < lines.length && /^>/.test(lines[i])) quote.push(lines[i++].replace(/^>\s?/, ''));
        el = node('blockquote'); markdown(el, quote.join('\n')); target.appendChild(el); continue;
      }
      if (/^\s*(?:[-*+] |\d+[.)] )/.test(line)) {
        var ordered = /^\s*\d/.test(line); el = node(ordered ? 'ol' : 'ul');
        while (i < lines.length && (ordered ? /^\s*\d+[.)]\s/ : /^\s*[-*+]\s/).test(lines[i])) {
          var li = node('li'); inline(li, lines[i++].replace(/^\s*(?:[-*+]|\d+[.)])\s+/, '')); el.appendChild(li);
        }
        target.appendChild(el); continue;
      }
      if (i+1 < lines.length && line.includes('|') && /^\s*\|?\s*:?-{3,}/.test(lines[i+1])) {
        var table = node('table'), wrapper = node('div', null, 'table-scroll');
        function row(s, heading) { var tr = node('tr'); s.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').forEach(function (cell) { var td = node(heading ? 'th' : 'td'); inline(td, cell.trim()); tr.appendChild(td); }); table.appendChild(tr); }
        row(line, true); i+=2;
        while (i < lines.length && lines[i].includes('|') && lines[i].trim()) row(lines[i++], false);
        wrapper.appendChild(table); target.appendChild(wrapper); continue;
      }
      var paragraph = [line]; i++;
      while (i < lines.length && !special(lines[i])) paragraph.push(lines[i++]);
      el = node('p'); paragraph.forEach(function (part, index) { if (index) el.appendChild(node('br')); inline(el, part); }); target.appendChild(el);
    }
  }
  function metric(label, value, detail, intensity) {
    var kind = label.includes('好感度') ? 'affection' : 'mood';
    metrics.appendChild(window.SoulHavenFeelings.card(kind, label.replace(/^[♡❀]\s*/, ''), value, intensity, detail, kind === 'affection' ? '把每一次靠近，写进心的年轮。' : '心底的涟漪，月光都知道。'));
  }
  var touchReading = matchMedia('(max-width: 620px) and (pointer: coarse)');
  function showVoice(voice, button) {
    list.querySelectorAll('button').forEach(function (item) { item.setAttribute('aria-pressed', String(item === button)); });
    content.replaceChildren(); metrics.replaceChildren();
    decoratePaper();
    var letter = voice.letter, ui = window.SoulHavenFeelings, secondary = document.getElementById('voiceSecondary');
    document.getElementById('voiceSnapshotNote').hidden = false;
    if (letter && letter.affection && letter.true_mood) {
      var a = letter.affection, m = letter.true_mood;
      metrics.appendChild(ui.card('affection', '好感度 · 自上次心声以来', a.previous + ' → ' + a.current, a.current, '总变化 ' + (a.change > 0 ? '+' : '') + a.change, '每一次靠近，都有它的回声。', 'A LITTLE MORE OF US'));
      metrics.appendChild(ui.card('mood', '写信时的真实主要心情', m.name, m.intensity, '真实心情强度 ' + m.intensity + ' / 100', '心底的涟漪，月光都知道。', 'THE FEELING WITHIN'));
      ui.secondary(secondary, letter.secondary_feelings); metrics.hidden = secondary.hidden = false;
      content.appendChild(node('time', voice.created_at + ' · 北京时间', 'letter-date'));
      [['01 · WORDS FOR YOU', '想对你说的心里话', letter.heartfelt_words], ['02 · A REASON TO STAY', '关系里的回声', letter.affection_reason], ['03 · THE TRUE FEELING', '真实心情 · ' + m.name, m.reason]].forEach(function (part) {
        var section = node('section', null, 'voice-section'); section.appendChild(node('p', part[0], 'voice-section__kicker')); section.appendChild(node('h2', part[1])); markdown(section, part[2]); content.appendChild(section);
      });
      content.focus({preventScroll:true}); return;
    }
    secondary.hidden = true;
    var body = String(voice.content || ''), affection = body.match(/^好感度[：:]\s*(-?\d+(?:\.\d+)?)\s*(?:->|→)\s*(-?\d+(?:\.\d+)?)([^\n]*)$/m);
    var mood = body.match(/^真实心情[：:]\s*(.*?)；\s*强度[：:]\s*(\d+)\/100\s*$/m);
    if (affection) { metric('♡ 好感度', affection[1] + ' → ' + affection[2], '自上次心声以来', Number(affection[2])); body = body.replace(affection[0], ''); }
    if (mood) { metric('❀ 真实心情', mood[1], '心情强度 ' + mood[2] + ' / 100', Number(mood[2])); body = body.replace(mood[0], ''); }
    metrics.hidden = metrics.children.length === 0;
    content.appendChild(node('time', voice.created_at, 'letter-date'));
    markdown(content, body.replace(/^#\s*心声\s*\n/, '').trim());
    content.focus({preventScroll:true});
    if (!touchReading.matches && matchMedia('(max-width:620px)').matches) content.scrollIntoView({behavior:'smooth',block:'start'});
  }
  fetch('/api/characters/' + encodeURIComponent(role) + '/inner-voices', {cache:'no-store'}).then(function (response) { if (!response.ok) throw new Error(); return response.json(); }).then(function (data) {
    document.getElementById('voiceCount').textContent = data.voices.length + ' 封';
    status.textContent = data.voices.length ? '按时间珍藏，点击一封慢慢读。' : '信箱还空着。回到聊天中，邀请 TA 写下第一封心声吧。';
    data.voices.forEach(function (voice, index) {
      var button = node('button', null, 'letter-button'); button.type = 'button'; button.setAttribute('aria-pressed','false');
      button.appendChild(node('span', 'LETTER ' + String(data.voices.length-index).padStart(2,'0'), 'letter-number'));
      button.appendChild(node('time', voice.created_at));
      var preview = voice.letter ? voice.letter.heartfelt_words : String(voice.content).split('\n').filter(function (line) { return line.trim() && !/^(#|好感度|真实心情)/.test(line); })[0] || '有些话，想慢慢说给你听。';
      button.appendChild(node('span', preview.replace(/[*_]/g,''), 'letter-preview'));
      button.addEventListener('click', function () {
        showVoice(voice, button);
        if (touchReading.matches) {
          var reduceMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
          content.scrollIntoView({behavior: reduceMotion ? 'instant' : 'smooth', block: 'start'});
        }
      });
      list.appendChild(button);
      if (index === 0) showVoice(voice, button);
    });
  }).catch(function () { status.textContent = '来信暂时无法读取，请刷新后重试。'; });
})();
