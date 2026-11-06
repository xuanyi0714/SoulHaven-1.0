(function () {
  'use strict';
  window.SoulHavenReveal = function () {
    return new Promise(function (resolve) {
      var previous = document.activeElement, dialog = document.createElement('dialog'); dialog.className = 'state-reveal';
      dialog.setAttribute('aria-labelledby', 'stateRevealTitle'); dialog.setAttribute('aria-describedby', 'stateRevealDescription');
      dialog.innerHTML = '<div class="state-reveal__sky" aria-hidden="true"><span>☾</span><i>✧</i><i>✦</i><i>✧</i></div>' +
        '<p class="state-reveal__eyebrow">A LITTLE CLOSER TO THE HEART</p><h2 id="stateRevealTitle">轻轻翻开，心底的那一页</h2>' +
        '<p class="state-reveal__handwriting">有些心意，藏在星光没有照见的地方。</p>' +
        '<div id="stateRevealDescription" class="state-reveal__note"><p>这里会看见 TA <strong>真实的心情、好感度和细微感受</strong>，也许与表面流露的样子不同。</p><p>提前读懂这些心事，可能会少一点相处中的神秘与惊喜。如果你愿意，我们就轻轻走近；也可以让心意慢慢被发现。</p></div>' +
        '<div class="state-reveal__actions"><button type="button" data-reveal="cancel" autofocus>把惊喜留给以后</button><button type="button" data-reveal="confirm">我愿意，轻轻看看 <span aria-hidden="true">✧</span></button></div><p class="state-reveal__footer">每一次靠近，都由你来决定。</p>';
      var accepted = false, finished = false;
      function finish() { if (finished) return; finished = true; dialog.remove(); if (previous && previous.isConnected) previous.focus(); resolve(accepted); }
      dialog.querySelector('[data-reveal="cancel"]').onclick = function () { dialog.close(); finish(); };
      dialog.querySelector('[data-reveal="confirm"]').onclick = function () { accepted = true; dialog.close(); finish(); };
      dialog.addEventListener('close', finish, {once:true});
      document.body.appendChild(dialog); dialog.showModal();
    });
  };
})();
