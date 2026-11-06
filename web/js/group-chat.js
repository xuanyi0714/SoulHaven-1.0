(function () {
  'use strict';
  var dialog = document.createElement('dialog');
  dialog.className = 'soul-group-dialog';
  dialog.setAttribute('aria-labelledby', 'soulGroupTitle');
  dialog.setAttribute('aria-describedby', 'soulGroupDescription');
  dialog.innerHTML = '<span class="soul-group-star" aria-hidden="true">✦</span><h2 id="soulGroupTitle">敬请期待</h2><p id="soulGroupDescription">与多位角色一起聊天的功能正在准备中。</p><form method="dialog"><button type="submit">知道啦</button></form>';
  var style = document.createElement('style');
  style.textContent = '.soul-group-dialog{width:min(390px,calc(100% - 40px));padding:30px;border:1px solid #fff;border-radius:24px;background:#faf9ff;color:#373456;text-align:center;box-shadow:0 18px 60px #26204b40}.soul-group-dialog::backdrop{background:#27233f80}.soul-group-star{color:#8992ff;font-size:32px}.soul-group-dialog h2{margin:8px 0;font-size:24px}.soul-group-dialog p{margin:12px 0 24px;line-height:1.6}.soul-group-dialog button{border:0;border-radius:99px;padding:10px 32px;background:#6875ed;color:white;font:inherit;cursor:pointer}.soul-group-dialog button:focus-visible{outline:3px solid #8992ff;outline-offset:4px}';
  document.head.appendChild(style);
  document.body.appendChild(dialog);
  document.addEventListener('click', function (event) {
    var entry = event.target.closest('[data-group-chat]');
    if (entry) { event.preventDefault(); dialog.showModal(); }
  });
}());
