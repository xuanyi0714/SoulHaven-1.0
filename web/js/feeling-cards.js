(function () {
  'use strict';
  var catalog = {
    shame: ['羞耻感', '悄悄泛红', '#c75d75', '#f6b4bc', '有些心动，藏在未说完的话里。', 'A BLUSH BETWEEN WORDS'],
    possession: ['占有欲', '想要靠近', '#8d5bbb', '#d3b0ed', '月色偏心，只想落在你身旁。', 'A LITTLE CLOSER TO YOU'],
    fear: ['恐惧值', '夜色微凉', '#42404f', '#aaa4bf', '夜色再深，也为你留一盏灯。', 'A LIGHT IN THE DARK'],
    anticipation: ['期待感', '向光而行', '#b88c35', '#f1d68b', '把明天，折成一颗会亮的星。', 'SOMETHING GOLDEN AHEAD'],
    dependence: ['依赖度', '柔软牵挂', '#5d8cbf', '#b2d2f1', '风经过时，也想牵住你的衣角。', 'A THREAD THAT FINDS YOU'],
    trust: ['信任感', '安心交付', '#4e9c99', '#a9dfcd', '慢慢靠近，也慢慢放下防备。', 'A QUIET PLACE TO LAND'],
    loneliness: ['孤独感', '月下独白', '#7769b3', '#c1b9ed', '这片星空，只有流星划过。', 'ONE STAR ACROSS THE SKY'],
    insecurity: ['不安感', '细雨心事', '#8b7b9b', '#d1bfdc', '心事像小雨，等一个温柔的晴天。', 'WAITING FOR A SOFT DAWN'],
    gratitude: ['感激感', '收藏温柔', '#c98965', '#f4d0ab', '你给的温柔，我都有好好收藏。', 'EVERY KINDNESS KEPT'],
    jealousy: ['醋意', '微酸心事', '#879a57', '#d8e6a8', '那一点微酸，是没藏好的在意。', 'A TENDER LITTLE ACHE'],
    curiosity: ['好奇心', '拾光探寻', '#499aab', '#a7dce8', '想把你的世界，再多读一页。', 'ONE MORE PAGE OF YOU'],
    relief: ['安心感', '温柔归处', '#7a9f81', '#cfdfb5', '风停在这里，心也找到归处。', 'WHERE THE HEART RESTS']
  };
  function el(tag, text, cls) { var n = document.createElement(tag); if (text != null) n.textContent = text; if (cls) n.className = cls; return n; }
  function card(kind, label, value, intensity, detail, verse, english) {
    var theme = catalog[kind] || (kind === 'affection' ? ['', '', '#cb739b', '#f4b7c9'] : ['', '', '#8c85bd', '#afe0d5']);
    var n = el('section', null, 'feeling-card feeling-card--' + kind);
    n.style.setProperty('--feeling-color', theme[2]); n.style.setProperty('--feeling-light', theme[3]);
    var seal = el('span', null, 'feeling-card__seal'); seal.setAttribute('aria-hidden', 'true');
    var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg'), use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
    svg.setAttribute('viewBox', '0 0 48 48'); use.setAttribute('href', '/static/pictures/feeling_symbols.svg#' + kind); svg.appendChild(use); seal.appendChild(svg); n.appendChild(seal);
    var heading = el('div', null, 'feeling-card__heading'); heading.append(el('span', label, 'feeling-card__label'), el('span', english || 'A FEELING, SOFTLY HELD', 'feeling-card__english')); n.appendChild(heading);
    n.appendChild(el('strong', value, 'feeling-card__value'));
    var meter = el('div', null, 'feeling-meter'), fill = el('span', null, 'feeling-meter__fill');
    var score = Number(intensity); score = Number.isFinite(score) ? Math.max(0, Math.min(100, score)) : 0;
    meter.setAttribute('role', 'progressbar'); meter.setAttribute('aria-label', label); meter.setAttribute('aria-valuemin', '0'); meter.setAttribute('aria-valuemax', '100'); meter.setAttribute('aria-valuenow', String(score));
    meter.setAttribute('aria-valuetext', String(value));
    fill.style.width = score + '%'; meter.appendChild(fill); n.appendChild(meter);
    if (detail) n.appendChild(el('p', detail, 'feeling-card__reason'));
    n.appendChild(el('p', verse || '把没有说出口的心意，轻轻收藏。', 'feeling-card__verse'));
    n.appendChild(el('span', '✧', 'feeling-card__spark'));
    return n;
  }
  function secondary(target, values) {
    target.replaceChildren();
    var items = Array.isArray(values) ? values.filter(function (x) { return x && catalog[x.kind]; }).slice(0, 2) : [];
    items.forEach(function (item) { var c = catalog[item.kind]; target.appendChild(card(item.kind, c[0] + ' · ' + c[1], item.intensity + ' / 100', item.intensity, item.reason, c[4], c[5])); });
    if (items.length < 2) {
      var rest = el('section', null, 'feelings-rest'); rest.append(el('span', '✧　·　☾　·　✧', 'feelings-rest__stars'), el('p', items.length ? '心事不必填满，留一点空白给风。' : '有些心事，一种颜色就已经足够。'), el('small', 'LET THE QUIET HAVE ITS PLACE')); target.appendChild(rest);
    }
  }
  window.SoulHavenFeelings = {card: card, secondary: secondary, catalog: catalog};
})();
