(function () {
  var root = document.getElementById('campusbot');
  if (!root) return;
  var toggle = root.querySelector('.cb-toggle'), panel = root.querySelector('.cb-panel');
  var log = root.querySelector('.cb-log'), opts = root.querySelector('.cb-opts');
  var form = root.querySelector('.cb-form'), input = root.querySelector('.cb-input');
  var KEY = 'chub-bot';
  var NOME = (root.getAttribute('data-nome') || '').trim();
  var MENU = [
    { label: 'Ver chamados', value: 'cmd:chamados' }, { label: 'Nova requisição', value: 'cmd:nova' },
    { label: 'Consultar estoque', value: 'cmd:estoque' }, { label: 'Ver salas', value: 'cmd:salas' },
    { label: 'Últimos logs', value: 'cmd:logs' }
  ];
  var estado = null, historico = [], aberto = false, enviando = false;

  function salvar() {
    try { sessionStorage.setItem(KEY, JSON.stringify({ estado: estado, historico: historico.slice(-40), aberto: aberto })); } catch (e) {}
  }
  function el(tag, cls, txt) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (txt != null) n.textContent = txt;
    return n;
  }
  function rolar() { log.scrollTop = log.scrollHeight; }

  function pintarCard(c) {
    var box = el('div', 'cb-card');
    if (c.img) { var im = el('img'); im.src = c.img; im.alt = ''; box.appendChild(im); }
    var body = el('div', 'cb-card-body');
    var top = el('div', 'cb-card-top');
    top.appendChild(el('span', null, c.titulo));
    if (c.badge) top.appendChild(el('span', 'cb-badge cb-' + c.badge.tom, c.badge.texto));
    body.appendChild(top);
    (c.linhas || []).forEach(function (l) { body.appendChild(el('div', 'cb-card-line', l)); });
    if (c.acoes && c.acoes.length) {
      var ac = el('div', 'cb-card-actions');
      c.acoes.forEach(function (o) {
        var b = el('button', null, o.label); b.type = 'button';
        b.addEventListener('click', function () { enviar(o.value, o.label); });
        ac.appendChild(b);
      });
      body.appendChild(ac);
    }
    if (c.href) { var a = el('a', null, 'Abrir'); a.href = c.href; body.appendChild(a); }
    box.appendChild(body);
    log.appendChild(box);
  }
  function pintarOpcoes(r) {
    opts.textContent = '';
    (r.options || []).forEach(function (o) {
      var b = el('button', null, o.label); b.type = 'button';
      b.addEventListener('click', function () { enviar(o.value, o.label); });
      opts.appendChild(b);
    });
    (r.links || []).forEach(function (l) { var a = el('a', null, l.label); a.href = l.href; opts.appendChild(a); });
  }
  function pintar(item) {
    if (item.role === 'user') { log.appendChild(el('div', 'cb-msg cb-user', item.text)); return; }
    log.appendChild(el('div', 'cb-msg cb-bot', item.reply));
    (item.cards || []).forEach(pintarCard);
  }
  function renderTudo() {
    log.textContent = '';
    historico.forEach(pintar);
    var ult = historico.length && historico[historico.length - 1];
    if (ult && ult.role === 'bot') pintarOpcoes(ult); else opts.textContent = '';
    rolar();
  }
  function enviar(valor, rotulo) {
    if (!valor || enviando) return;
    enviando = true;
    if (rotulo !== undefined || valor.indexOf('cmd:') !== 0) {
      historico.push({ role: 'user', text: rotulo || valor });
      pintar(historico[historico.length - 1]);
    }
    opts.textContent = '';
    input.value = '';
    var typing = el('div', 'cb-msg cb-bot', '…'); log.appendChild(typing); rolar();
    fetch('/chatbot', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: valor, state: estado }) })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (r) {
        typing.remove();
        estado = r.state || null;
        r.role = 'bot'; historico.push(r); pintar(r); pintarOpcoes(r);
        input.placeholder = r.placeholder || 'Digite uma mensagem…';
        salvar(); rolar(); enviando = false;
      })
      .catch(function () {
        typing.remove();
        log.appendChild(el('div', 'cb-msg cb-bot', 'Não consegui falar com o servidor. Tente novamente.'));
        enviando = false;
      });
  }
  // Menu inicial montado no navegador: abrir o chat não gasta requisição nem consulta ao banco.
  function saudar() {
    var r = { role: 'bot', state: null, placeholder: null, cards: [], links: [], options: MENU,
      reply: 'Olá, ' + (NOME || 'tudo bem') + '! Sou o CampusBot. Posso mostrar chamados, abrir uma requisição, consultar estoque e salas.' };
    estado = null; historico.push(r); pintar(r); pintarOpcoes(r);
    input.placeholder = 'Digite uma mensagem…';
    salvar(); rolar();
  }
  function abrir(v) {
    aberto = v; panel.hidden = !v;
    toggle.setAttribute('aria-expanded', String(v));
    if (v) { if (!historico.length) saudar(); input.focus(); rolar(); }
    salvar();
  }

  try {
    var salvo = JSON.parse(sessionStorage.getItem(KEY) || 'null');
    if (salvo) { estado = salvo.estado; historico = salvo.historico || []; aberto = !!salvo.aberto; }
  } catch (e) {}
  renderTudo();
  if (aberto) { panel.hidden = false; toggle.setAttribute('aria-expanded', 'true'); }

  toggle.addEventListener('click', function () { abrir(panel.hidden); });
  root.querySelector('.cb-close').addEventListener('click', function () { abrir(false); toggle.focus(); });
  root.querySelector('.cb-clear').addEventListener('click', function () {
    historico = []; estado = null; log.textContent = ''; opts.textContent = ''; saudar();
  });
  form.addEventListener('submit', function (e) { e.preventDefault(); var v = input.value.trim(); if (v) enviar(v); });
  root.addEventListener('keydown', function (e) { if (e.key === 'Escape' && !panel.hidden) { abrir(false); toggle.focus(); } });
})();
