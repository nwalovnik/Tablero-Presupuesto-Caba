/* Navegador 2013-2026 · árbol función / jurisdicción → programa → proyecto y obra.
   Datos: navegador_data.json (data/build_navegador.py). Montos en miles de pesos
   corrientes; el valor real se expresa en pesos de 2026 con el IPC promedio anual
   del tablero. Tiene su propio selector real / nominal (arranca en real: la serie
   nominal 2013-2026 sólo muestra la inflación). */
(function () {
  'use strict';
  const $ = id => document.getElementById(id);
  const root = $('nvRoot');
  if (!root) return;

  const PAL = ['#0C2340', '#1B6EC2', '#6AADE4', '#0A8A5A', '#C06A00', '#8E44AD', '#C0392B', '#B7950B', '#138D90', '#C2185B'];
  const REST = '#CBD5E1';
  const MET = {d: 'Devengado', s: 'Sancionado', v: 'Vigente'};
  const S = {mode: 'fun', path: [], metric: 'd', yRef: 2025, yCmp: 2015, q: '', view: 'stack', tab: 'inc', sort: {c: 'ref', d: -1}, real: true};

  let N, Y, NY, YL, YP, YE, iC, iP, IPC, R;  // datos; YL = año en curso y de los pesos constantes, YP = año del proyecto
  let leafProj, progJur;             // derivados
  let chMain, chTop, CP;

  const isReal = () => S.real;
  const fac = yi => isReal() ? IPC[YL] / IPC[Y[yi]] : 1;     // a pesos 2026
  const rfac = yi => IPC[YL] / IPC[Y[yi]];
  const yIdx = y => Y.indexOf(y);

  // ── formato ──
  const nf0 = new Intl.NumberFormat('es-AR', {maximumFractionDigits: 0});
  const nf1 = new Intl.NumberFormat('es-AR', {minimumFractionDigits: 1, maximumFractionDigits: 1});
  const mill = k => k / 1e3;  // miles → millones
  function fM(k) {
    if (k == null || !isFinite(k)) return '—';
    const m = mill(k);
    if (Math.abs(m) >= 1e6) return '$ ' + nf1.format(m / 1e6) + ' bill.';
    if (Math.abs(m) >= 1e3) return '$ ' + nf1.format(m / 1e3) + ' mil M';
    return '$ ' + (Math.abs(m) < 10 ? nf1.format(m) : nf0.format(m)) + ' M';
  }
  const fTab = k => (k == null || !isFinite(k) || k === 0) ? '<span class="na">—</span>' : (Math.abs(mill(k)) < 10 ? nf1.format(mill(k)) : nf0.format(mill(k)));
  const fPct = (v, d = 1) => (v == null || !isFinite(v)) ? '—' : v > 999 ? '>+999%' : (v > 0 ? '+' : '') + v.toFixed(d).replace('.', ',') + '%';
  const cls = v => v == null || !isFinite(v) ? 'na' : v > 0.05 ? 'pos' : v < -0.05 ? 'neg' : '';
  const esc = s => String(s).replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
  const varR = (ser, a, b) => { // var real % entre índices a (base) y b
    const va = ser[a] * rfac(a), vb = ser[b] * rfac(b);
    return va > 0 && vb >= 0 ? (vb / va - 1) * 100 : null;
  };

  // ── carga ──
  root.innerHTML = '<div class="nv-load">Cargando el navegador…</div>';
  fetch('navegador_data.json').then(r => {
    if (!r.ok) throw new Error(r.status);
    return r.json();
  }).then(init).catch(e => {
    root.innerHTML = '<div class="nv-load">No se pudieron cargar los datos del navegador (' + esc(e.message) + ').</div>';
  });

  function init(data) {
    N = data; Y = N.years; NY = Y.length; YE = Y[NY - 1];
    YL = N.base || YE; YP = N.periodo[YE] === 'proyecto' ? YE : null;
    iC = Y.indexOf(YL); iP = YP ? NY - 1 : -1;
    N.leaf.forEach(l => { if (l[1] === 'Z') l[2] = 'Sin apertura por actividad u obra'; });
    IPC = {}; Object.keys(N.ipc).forEach(k => IPC[+k] = N.ipc[k]);
    progJur = N.prog.map(p => p[0]);
    leafProj = N.leaf.map(l => l[1] === 'O' ? l[0] + '|' + l[3] : null);
    const n = N.t.length;
    R = {y: new Uint8Array(n), f: new Uint8Array(n), l: new Uint32Array(n), p: new Uint32Array(n), j: new Uint8Array(n),
         s: new Float64Array(n), v: new Float64Array(n), d: new Float64Array(n)};
    N.t.forEach((r, i) => {
      R.y[i] = r[0]; R.f[i] = r[1]; R.l[i] = r[2]; R.p[i] = N.leaf[r[2]][0]; R.j[i] = progJur[R.p[i]];
      R.s[i] = r[3]; R.v[i] = r[4]; R.d[i] = r[5];
    });
    if (YP) { S.yRef = YP; S.yCmp = 2023; } else S.yRef = Math.min(S.yRef, YL - 1);
    root.innerHTML = TEMPLATE();
    bindControls();
    readHash();
    render();
    window.addEventListener('hashchange', () => { if (readHash()) render(); });
  }

  // valor de una fila de N.t para la métrica activa; en "devengado" 2026 usa la sanción
  function val(i) {
    if (S.metric === 's') return R.s[i];
    if (S.metric === 'v') return R.v[i];
    return R.y[i] === iC ? R.s[i] : R.d[i];
  }

  // ── ámbito y niveles ──
  const last = () => S.path[S.path.length - 1];
  function inScope(i) {
    for (const n of S.path) {
      if (n.t === 'fun' && R.f[i] !== n.id) return false;
      if (n.t === 'jur' && R.j[i] !== n.id) return false;
      if (n.t === 'prog' && R.p[i] !== n.id) return false;
      if (n.t === 'proj' && leafProj[R.l[i]] !== n.id) return false;
      if (n.t === 'leaf' && R.l[i] !== n.id) return false;
    }
    return true;
  }
  function childLevel() {
    const l = last();
    if (!l) return S.mode;               // 'fun' | 'jur'
    if (l.t === 'fun' || l.t === 'jur') return 'prog';
    if (l.t === 'prog') return 'item';
    if (l.t === 'proj') return 'leaf';
    return null;                          // actividad u obra: sin hijos
  }
  function childKey(i, lvl) {
    if (lvl === 'fun') return R.f[i];
    if (lvl === 'jur') return R.j[i];
    if (lvl === 'prog') return R.p[i];
    if (lvl === 'item') return leafProj[R.l[i]] || ('A' + R.l[i]);
    return R.l[i];
  }
  function nodeOf(lvl, key) {
    if (lvl === 'fun') return {t: 'fun', id: key, label: N.fun[key][1]};
    if (lvl === 'jur') return {t: 'jur', id: key, label: N.jur[key][1]};
    if (lvl === 'prog') return {t: 'prog', id: key, label: N.prog[key][1]};
    if (lvl === 'item') {
      if (typeof key === 'string' && key[0] === 'A') { const li = +key.slice(1); return {t: 'leaf', id: li, label: N.leaf[li][2]}; }
      return {t: 'proj', id: key, label: key.slice(key.indexOf('|') + 1)};
    }
    return {t: 'leaf', id: key, label: N.leaf[key][2]};
  }

  // Serie del ámbito y de sus hijos (por año, métrica activa, nominal)
  function aggregate() {
    const lvl = childLevel();
    const tot = new Float64Array(NY), kids = new Map();
    const ex = {s: 0, v: 0, d: 0};       // ejecución del último año
    for (let i = 0; i < R.y.length; i++) {
      if (!inScope(i)) continue;
      const x = val(i), yi = R.y[i];
      tot[yi] += x;
      if (yi === iC) { ex.s += R.s[i]; ex.v += R.v[i]; ex.d += R.d[i]; }
      if (lvl) {
        const k = childKey(i, lvl);
        let a = kids.get(k);
        if (!a) { a = new Float64Array(NY); kids.set(k, a); }
        a[yi] += x;
      }
    }
    return {lvl, tot, kids, ex};
  }
  function grandTotal() {
    const t = new Float64Array(NY);
    for (let i = 0; i < R.y.length; i++) t[R.y[i]] += val(i);
    return t;
  }

  // ── plantilla ──
  const yOpts = sel => Y.map(y => `<option value="${y}"${y === sel ? ' selected' : ''}>${y}${y === YL ? ' *' : y === YP ? ' (proyecto)' : ''}</option>`).join('');
  const TEMPLATE = () => `
    <div class="nv-ctrl">
      <div class="nv-cg"><label>Ver por</label><div class="nv-seg" id="nvMode"><button data-v="fun">Función</button><button data-v="jur">Jurisdicción</button></div></div>
      <div class="nv-cg"><label>Monto</label><div class="nv-seg" id="nvMet"><button data-v="d">Devengado</button><button data-v="s">Sancionado</button><button data-v="v">Vigente</button></div></div>
      <div class="nv-cg"><label>Valores</label><div class="nv-seg" id="nvUnit"><button data-v="1">Real ($ ${YL})</button><button data-v="0">Nominal</button></div></div>
      <div class="nv-cg"><label>Año</label><select class="nv-sel" id="nvYRef"></select></div>
      <div class="nv-cg"><label>Comparar con</label><select class="nv-sel" id="nvYCmp"></select></div>
      <div class="nv-cg"><label>Buscar programa, obra o actividad</label><input class="nv-inp" id="nvQ" placeholder="hospital, subte, escuela…"></div>
      <div class="nv-cg" style="margin-left:auto"><label>Descargar</label><button class="nv-btn solid" id="nvDl">⬇ Excel de esta vista</button></div>
    </div>
    <div class="nv-crumbs" id="nvCrumbs"></div>
    <div><span class="nv-title" id="nvTitle"></span><span class="nv-kind" id="nvKind"></span></div>
    <div class="nv-info" id="nvInfo"></div>
    <div class="nv-kpis" id="nvKpis"></div>
    <div class="card">
      <div class="nv-row-h"><div><h3 id="nvChTitle">Evolución</h3><div class="card-sub" id="nvChSub"></div></div>
        <div class="nv-seg" id="nvView"><button data-v="stack">Composición</button><button data-v="tot">Total</button><button data-v="share">% del total</button></div></div>
      <div class="nv-ch"><canvas id="nvChart"></canvas></div>
      <div class="nv-hint" id="nvChHint"></div>
    </div>
    <div class="card" style="margin-top:14px">
      <div class="nv-row-h"><div><h3 id="nvTblTitle"></h3><div class="card-sub" id="nvTblSub"></div></div><details class="nv-cp" id="nvCp"></details></div>
      <div class="nv-tw"><table class="nv-t" id="nvTbl"></table></div>
      <div class="nv-hint" id="nvTblHint"></div>
    </div>
    <div class="nv-g2">
      <div class="card">
        <h3 id="nvDetTitle">Composición</h3><div class="card-sub" id="nvDetSub"></div>
        <div class="nv-tabs" id="nvTabs"></div>
        <div class="nv-tw" style="max-height:420px"><table class="nv-t" id="nvDet" style="min-width:420px"></table></div>
      </div>
      <div class="card">
        <h3>Mayores subas y bajas</h3><div class="card-sub" id="nvTopSub"></div>
        <div class="nv-ch sm" id="nvTopBox"><canvas id="nvTop"></canvas></div>
      </div>
    </div>`;

  // ── controles ──
  function seg(id, key, after) {
    const el = $(id);
    el.querySelectorAll('button').forEach(b => b.onclick = () => { S[key] = b.dataset.v; after && after(); render(); });
  }
  function bindControls() {
    seg('nvMode', 'mode', () => { S.path = []; });
    seg('nvMet', 'metric');
    seg('nvView', 'view');
    $('nvUnit').querySelectorAll('button').forEach(b => b.onclick = () => { S.real = b.dataset.v === '1'; render(); });
    $('nvYRef').onchange = e => { S.yRef = +e.target.value; render(); };
    $('nvYCmp').onchange = e => { S.yCmp = +e.target.value; render(); };
    let t;
    $('nvQ').oninput = e => { clearTimeout(t); t = setTimeout(() => { S.q = e.target.value.trim(); render(); }, 180); };
    $('nvDl').onclick = download;
  }
  function syncControls() {
    [['nvMode', 'mode'], ['nvMet', 'metric'], ['nvView', 'view']].forEach(([id, k]) =>
      $(id).querySelectorAll('button').forEach(b => b.classList.toggle('on', b.dataset.v === S[k])));
    $('nvUnit').querySelectorAll('button').forEach(b => b.classList.toggle('on', (b.dataset.v === '1') === S.real));
    $('nvYRef').innerHTML = yOpts(S.yRef);
    $('nvYCmp').innerHTML = yOpts(S.yCmp);
  }

  // ── navegación ──
  function go(path, mode) {
    if (mode) S.mode = mode;
    S.path = path; S.q = ''; $('nvQ').value = '';
    S.sort = {c: 'ref', d: -1};
    writeHash();
    render();
    const top = root.getBoundingClientRect().top + window.scrollY - 90;
    if (window.scrollY > top + 200) window.scrollTo({top, behavior: 'smooth'});
  }
  function drill(node) { go(S.path.concat([node])); }

  // Estado en el hash: #nav=fun.12.p345.Px|nombre  (sirve para compartir un programa)
  function writeHash() {
    const L = {fun: 'f', jur: 'j', prog: 'p', proj: 'P', leaf: 'l'};
    const parts = [S.mode].concat(S.path.map(n => L[n.t] + (n.t === 'proj' ? encodeURIComponent(n.id) : n.id)));
    history.replaceState(null, '', '#nav=' + parts.join('.'));
  }
  function readHash() {
    const m = location.hash.match(/^#nav=([^&]+)/);
    if (!m) return false;
    const parts = m[1].split('.');
    if (parts[0] !== 'fun' && parts[0] !== 'jur') return false;
    const path = [];
    for (const p of parts.slice(1)) {
      const t = {f: 'fun', j: 'jur', p: 'prog', l: 'leaf'}[p[0]];
      if (p[0] === 'P') { const id = decodeURIComponent(p.slice(1)); path.push({t: 'proj', id, label: id.slice(id.indexOf('|') + 1)}); continue; }
      if (!t) return false;
      const id = +p.slice(1);
      const lab = t === 'fun' ? N.fun[id] && N.fun[id][1] : t === 'jur' ? N.jur[id] && N.jur[id][1] : t === 'prog' ? N.prog[id] && N.prog[id][1] : N.leaf[id] && N.leaf[id][2];
      if (!lab) return false;
      path.push({t, id, label: lab});
    }
    S.mode = parts[0]; S.path = path;
    return true;
  }

  // ── render ──
  function render() {
    if (!N) return;
    syncControls();
    const A = aggregate();
    const G = grandTotal();
    renderHead(A, G);
    renderChart(A);
    renderTable(A, G);
    renderDetail();
    renderTop(A);
  }

  const KIND = {fun: 'Función', jur: 'Jurisdicción', prog: 'Programa', proj: 'Proyecto de inversión', leaf: 'Actividad / obra'};
  const LVL_TXT = {fun: 'Funciones', jur: 'Jurisdicciones', prog: 'Programas', item: 'Proyectos, obras y actividades', leaf: 'Obras y actividades del proyecto'};
  const metLbl = () => S.metric === 'd' ? 'Devengado' : S.metric === 's' ? 'Sancionado' : 'Vigente';
  const refLbl = y => y === YP ? `Proyecto ${y}` : `${metLbl()} ${y}`;  // el año del proyecto no tiene devengado ni vigente
  const yLbl = y => y === YP ? `${y} (proy.)` : y === YL ? (S.metric === 'd' ? `${y} (sanc.)` : S.metric === 'v' ? `${y} (al ${N.periodo[y]})` : `${y}`) : `${y}`;
  const unitLbl = () => isReal() ? 'millones de pesos de ' + YL : 'millones de pesos corrientes';

  function renderHead(A, G) {
    const l = last();
    const cr = [`<button data-i="-1">${S.mode === 'fun' ? 'Todas las funciones' : 'Todas las jurisdicciones'}</button>`];
    S.path.forEach((n, i) => cr.push('<span class="sep">›</span>' + (i === S.path.length - 1 ? `<span class="cur">${esc(n.label)}</span>` : `<button data-i="${i}">${esc(n.label)}</button>`)));
    $('nvCrumbs').innerHTML = (S.path.length ? '<button class="back" data-i="' + (S.path.length - 2) + '">← Volver</button>' : '') + cr.join(' ');
    $('nvCrumbs').querySelectorAll('button').forEach(b => b.onclick = () => go(S.path.slice(0, +b.dataset.i + 1)));
    $('nvTitle').textContent = l ? l.label : 'Presupuesto de la Ciudad';
    $('nvKind').textContent = l ? (l.t === 'leaf' ? (N.leaf[l.id][1] === 'A' ? 'Actividad' : 'Obra / actividad de proyecto') : KIND[l.t]) : 'Total sin aplicaciones financieras';
    $('nvKind').style.display = '';

    // Info contextual
    const info = [];
    if (l && l.t === 'jur') {
      const h = N.jur[l.id][2];
      info.push('Código ' + N.jur[l.id][0].replace('a', '') + '. ' + (h.length > 1 ? 'Nombres: ' + h.map(x => `${esc(x[0])} (${x[1] === x[2] ? x[1] : x[1] + '-' + x[2]})`).join(' · ') : `Con datos ${h[0][1]}-${h[h.length - 1][2]}.`));
    }
    const jn = l && (l.t === 'jur' ? l.id : l.t === 'prog' ? N.prog[l.id][0] : null);
    if (jn != null && N.jur[jn][3]) info.push('⚠ ' + esc(N.jur[jn][3]));
    if (l && l.t === 'prog') {
      const p = N.prog[l.id];
      info.push('<b>' + esc(N.jur[p[0]][1]) + '</b>');
      if (p[2].length) info.push('Cambió de nombre: ' + p[2].map(x => `${esc(x[0])} (${x[1] === x[2] ? x[1] : x[1] + '-' + x[2]})`).join(' → '));
      if (p[3] >= 0) info.push(`Viene de <a data-p="${p[3]}">${esc(N.jur[N.prog[p[3]][0]][1])}</a>: antes del traspaso la serie sigue allá.`);
      if (p[4] >= 0) info.push(`Pasa a <a data-p="${p[4]}">${esc(N.jur[N.prog[p[4]][0]][1])}</a>: después del traspaso la serie sigue allá.`);
    }
    if (l && (l.t === 'proj' || l.t === 'leaf')) {
      const pi = l.t === 'proj' ? +l.id.split('|')[0] : N.leaf[l.id][0];
      info.push('Programa <a data-p="' + pi + '">' + esc(N.prog[pi][1]) + '</a> · ' + esc(N.jur[N.prog[pi][0]][1]));
      if (l.t === 'leaf' && N.leaf[l.id][3]) info.push('Proyecto: ' + esc(N.leaf[l.id][3]));
    }
    const ex = A.ex;
    if (ex.s || ex.v) info.push(`${YL}: sancionado ${fM(ex.s)} · vigente al ${N.periodo[YL]} ${fM(ex.v)} · devengado al ${N.periodo[YL]} ${fM(ex.d)}` + (ex.v > 0 ? ` (${nf0.format(ex.d / ex.v * 100)}% del vigente)` : '') + ' · nominal');
    $('nvInfo').innerHTML = info.join('<br>');
    $('nvInfo').querySelectorAll('a[data-p]').forEach(a => a.onclick = () => {
      const pi = +a.dataset.p; const j = N.prog[pi][0];
      go([{t: 'jur', id: j, label: N.jur[j][1]}, {t: 'prog', id: pi, label: N.prog[pi][1]}], 'jur');
    });

    // KPIs
    const r = yIdx(S.yRef), c = yIdx(S.yCmp), t = A.tot;
    const realSer = t.map((v, i) => v * rfac(i));
    let mx = 0; realSer.forEach((v, i) => { if (i !== iP && v > realSer[mx]) mx = i; });  // el máximo no cuenta el proyecto
    const vAnt = r > 0 ? varR(t, r - 1, r) : null, vCmp = varR(t, c, r);
    const sh = G[r] ? t[r] / G[r] * 100 : null;
    const k = (lbl, v, sub, cl, cl2) => `<div class="kpi ${cl2 || ''}"><div class="kpi-lbl">${lbl}</div><div class="kpi-val ${cl || ''}">${v}</div><div class="kpi-sub">${sub}</div></div>`;
    $('nvKpis').innerHTML =
      k(S.yRef === YP ? refLbl(YP) : `${metLbl()} ${yLbl(S.yRef)}`, fM(t[r] * fac(r)), isReal() ? 'pesos de ' + YL : 'pesos corrientes') +
      k(`Var. real vs ${Y[r - 1] || '—'}`, fPct(vAnt), 'deflactado por IPC', vAnt == null ? '' : vAnt >= 0 ? 'green' : 'red', 'k2') +
      k(`Var. real vs ${S.yCmp}`, fPct(vCmp), `${S.yCmp} → ${S.yRef}`, vCmp == null ? '' : vCmp >= 0 ? 'green' : 'red', 'k3') +
      k('Máximo real', yLbl(Y[mx]), realSer[mx] > 0 ? fM(realSer[mx]) + ' de ' + YL + (mx !== r && realSer[r] > 0 ? ` · ${S.yRef}: ${fPct((realSer[r] / realSer[mx] - 1) * 100)}` : '') : '—', '', 'k4') +
      (S.path.length ? k(`% del presupuesto ${S.yRef}`, sh == null ? '—' : nf1.format(sh) + '%', `${S.yRef === YP ? 'proyecto' : metLbl().toLowerCase()} total ${fM(G[r] * fac(r))}`) : '');
  }

  // ── gráfico principal ──
  function topKids(A, n) {
    const r = yIdx(S.yRef);
    const arr = [...A.kids.entries()].map(([k, s]) => ({k, s, w: s[r] || Math.max(...s.map((v, i) => v * rfac(i))) / rfac(r) * 0.001}));
    arr.sort((a, b) => b.w - a.w);
    return {top: arr.slice(0, n), rest: arr.slice(n)};
  }
  const HATCH = {};
  function hatch(col) {  // barras rayadas para el año del proyecto
    if (HATCH[col]) return HATCH[col];
    const c = document.createElement('canvas'); c.width = c.height = 8;
    const g = c.getContext('2d');
    g.fillStyle = col + '40'; g.fillRect(0, 0, 8, 8);
    g.strokeStyle = col; g.lineWidth = 1.6; g.beginPath();
    g.moveTo(0, 8); g.lineTo(8, 0); g.moveTo(-2, 2); g.lineTo(2, -2); g.moveTo(6, 10); g.lineTo(10, 6); g.stroke();
    return (HATCH[col] = g.createPattern(c, 'repeat'));
  }
  const barNote = () => `La barra de ${YL} va más clara: no es un cierre.` + (YP ? ` La de ${YP}, rayada: es el proyecto de presupuesto.` : '');
  const rest1 = A => A.kids.size <= 10;  // si entran todos, sin «Resto»
  function renderChart(A) {
    const lvl = A.lvl;
    const view = (S.view === 'stack' && (!lvl || A.kids.size < 2)) ? 'tot' : S.view;
    const labels = Y.map(y => y === YL || y === YP ? yLbl(y) : String(y));
    const conv = (s, i) => mill(s[i] * fac(i));
    let ds = [];
    const dim = (col, i) => i === iC ? col + '88' : i === iP ? hatch(col) : col;
    if (view === 'stack') {
      const {top, rest} = topKids(A, rest1(A) ? 10 : 9);
      top.forEach((o, i) => ds.push({label: nodeOf(lvl, o.k).label, data: Y.map((_, yi) => conv(o.s, yi)), backgroundColor: Y.map((_, yi) => dim(PAL[i % PAL.length], yi)), _col: PAL[i % PAL.length], _node: nodeOf(lvl, o.k), stack: 'a'}));
      if (rest.length) {
        const s = new Float64Array(NY); rest.forEach(o => o.s.forEach((v, i) => s[i] += v));
        ds.push({label: `Resto (${rest.length})`, data: Y.map((_, yi) => conv(s, yi)), backgroundColor: Y.map((_, yi) => dim(REST, yi)), stack: 'a'});
      }
    } else if (view === 'share') {
      const G = grandTotal();
      ds.push({label: '% del total', data: Y.map((_, i) => G[i] ? A.tot[i] / G[i] * 100 : null), backgroundColor: Y.map((_, i) => dim('#1B6EC2', i))});
    } else {
      ds.push({label: metLbl(), data: Y.map((_, i) => conv(A.tot, i)), backgroundColor: Y.map((_, i) => dim('#1B6EC2', i))});
    }
    const pct = view === 'share';
    $('nvChTitle').textContent = 'Evolución 2013-' + YE;
    $('nvChSub').textContent = (pct ? '% del presupuesto total de cada año' : `${metLbl()}, ${unitLbl()}`) + (S.metric === 'd' ? ` · ${YL}: sancionado` : S.metric === 'v' ? ` · ${YL}: vigente al ${N.periodo[YL]}` : '') + (YP ? ` · ${YP}: proyecto` : '');
    $('nvChHint').textContent = view === 'stack' ? 'Clic en un color del gráfico o en una fila de la tabla para abrir ese nivel. ' + barNote() : barNote();
    const opts = {
      responsive: true, maintainAspectRatio: false, animation: {duration: 250},
      plugins: {
        legend: {display: view === 'stack', position: 'bottom', labels: {boxWidth: 10, font: {size: 10.5}, generateLabels: ch => ch.data.datasets.map((d, i) => ({text: d.label.length > 42 ? d.label.slice(0, 40) + '…' : d.label, fillStyle: d._col || d.backgroundColor[0], strokeStyle: d._col || d.backgroundColor[0], datasetIndex: i, hidden: !ch.isDatasetVisible(i)}))}},
        tooltip: {callbacks: {label: c => ' ' + c.dataset.label.slice(0, 60) + ': ' + (pct ? nf1.format(c.raw) + '%' : '$ ' + (c.raw < 10 ? nf1.format(c.raw) : nf0.format(c.raw)) + ' M'),
          footer: items => view === 'stack' && items.length ? 'Total: $ ' + nf0.format(items[0].chart.data.datasets.reduce((a, d) => a + (d.data[items[0].dataIndex] || 0), 0)) + ' M' : ''}, mode: view === 'stack' ? 'index' : 'nearest', intersect: false}
      },
      scales: {x: {stacked: true, grid: {display: false}, ticks: {font: {size: 10.5}}},
        y: {stacked: true, beginAtZero: true, ticks: {font: {size: 10.5}, callback: v => pct ? v + '%' : nf0.format(v)}, grid: {color: '#EEF1F5'}}},
      onClick: (e, els, ch) => {
        if (view !== 'stack') return;
        const d = els.length && ch.data.datasets[els[0].datasetIndex];
        if (d && d._node) drill(d._node);
      },
      onHover: (e, els, ch) => { e.native.target.style.cursor = view === 'stack' && els.length && ch.data.datasets[els[0].datasetIndex]._node ? 'pointer' : 'default'; }
    };
    if (chMain) chMain.destroy();
    chMain = new Chart($('nvChart'), {type: 'bar', data: {labels, datasets: ds}, options: opts});
  }

  // ── tabla de hijos ──
  const CAT = () => {
    const base = [
      {k: 'sp', g: 'Resumen', def: true, l: 'Serie real 2013-' + YE},
      {k: 'ref', g: 'Resumen', def: true, l: refLbl(S.yRef)},
      {k: 'sh', g: 'Resumen', def: true, l: '% del nivel'},
      {k: 'vant', g: 'Resumen', def: true, l: 'Var. real vs año anterior'},
      {k: 'vcmp', g: 'Resumen', def: true, l: `Var. real vs ${S.yCmp}`},
      {k: 'dif', g: 'Resumen', def: false, l: `Diferencia real vs ${S.yCmp}`},
      {k: 'max', g: 'Resumen', def: false, l: 'Año de máximo real'}];
    return base.concat(Y.map(y => ({k: 'y' + y, g: 'Años', def: false, l: yLbl(y)})));
  };
  function colPicker() {
    const el = $('nvCp');
    let on;
    try { on = JSON.parse(localStorage.getItem('nv_cols') || 'null'); } catch (e) { on = null; }
    const cat = CAT();
    if (!Array.isArray(on)) on = cat.filter(c => c.def).map(c => c.k);
    const st = new Set(on);
    const save = () => { try { localStorage.setItem('nv_cols', JSON.stringify([...st])); } catch (e) {} };
    const draw = () => {
      const c2 = CAT();
      const grupos = [...new Set(c2.map(c => c.g))];
      el.innerHTML = `<summary>☰ Columnas (${c2.filter(c => st.has(c.k)).length}/${c2.length}) ▾</summary><div class="cp-panel">` +
        grupos.map(g => `<div class="cp-grp"><b>${g}</b>${c2.filter(c => c.g === g).map(c => `<label><input type="checkbox" data-k="${c.k}" ${st.has(c.k) ? 'checked' : ''}>${esc(c.l)}</label>`).join('')}</div>`).join('') +
        `<div class="cp-act"><button data-a="def">Por defecto</button><button data-a="years">Todos los años</button></div></div>`;
      el.querySelectorAll('input').forEach(i => i.onchange = () => { i.checked ? st.add(i.dataset.k) : st.delete(i.dataset.k); save(); renderTableOnly(); });
      el.querySelectorAll('.cp-act button').forEach(b => b.onclick = e => {
        e.preventDefault(); st.clear();
        (b.dataset.a === 'def' ? c2.filter(c => c.def) : c2.filter(c => c.k[0] === 'y' || c.k === 'vcmp')).forEach(c => st.add(c.k));
        save(); draw(); el.open = true; renderTableOnly();
      });
    };
    draw();
    document.addEventListener('click', e => { if (el.open && !el.contains(e.target)) el.open = false; });
    return {vis: () => CAT().filter(c => st.has(c.k)), redraw: draw};
  }
  let lastA, lastG;
  function renderTableOnly() { renderTable(lastA, lastG); }

  function spark(s) {
    const w = 96, h = 22, rs = s.map((v, i) => v * rfac(i));
    const mx = Math.max(...rs, 0);
    if (!(mx > 0)) return '';
    const x = i => (i / (NY - 1) * (w - 4) + 2).toFixed(1), y = v => (h - 2 - v / mx * (h - 4)).toFixed(1);
    let d = '', pen = false;
    for (let i = 0; i < iC; i++) { if (rs[i] > 0) { d += (pen ? 'L' : 'M') + x(i) + ' ' + y(rs[i]); pen = true; } else pen = false; }
    // año en curso (naranja) y proyecto (violeta), punteados: no son cierres
    const tail = (a, b, col) => rs[b] > 0 ? (rs[a] > 0 ? `<path d="M${x(a)} ${y(rs[a])}L${x(b)} ${y(rs[b])}" stroke="${col}" stroke-width="1.4" stroke-dasharray="2 2" fill="none"/>` : '') + `<circle cx="${x(b)}" cy="${y(rs[b])}" r="1.8" fill="${col}"/>` : '';
    return `<svg class="nv-spark" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}"><path d="${d}" stroke="#1B6EC2" stroke-width="1.6" fill="none"/>${tail(iC - 1, iC, '#C06A00')}${iP >= 0 ? tail(iC, iP, '#7B3FA0') : ''}</svg>`;
  }

  function rowsFor(A) {
    const r = yIdx(S.yRef), c = yIdx(S.yCmp), lvl = A.lvl;
    return [...A.kids.entries()].map(([k, s]) => {
      const nd = nodeOf(lvl, k);
      let sub = '', tag = '', grp = null;
      if (lvl === 'fun') grp = N.fun[k][0];
      if (lvl === 'prog') {
        const p = N.prog[k];
        if (S.mode === 'fun' || S.path.some(n => n.t === 'fun')) sub = N.jur[p[0]][1];
        const yrs = s.map((v, i) => v ? Y[i] : 0).filter(Boolean);
        if (yrs.length && (yrs[0] > Y[0] || yrs[yrs.length - 1] < YE)) sub += (sub ? ' · ' : '') + `con datos ${yrs[0]}-${yrs[yrs.length - 1]}`;
        if (p[4] >= 0) sub += (sub ? ' · ' : '') + 'pasa a ' + N.jur[N.prog[p[4]][0]][1];
        if (p[3] >= 0) sub += (sub ? ' · ' : '') + 'viene de ' + N.jur[N.prog[p[3]][0]][1];
      }
      if (lvl === 'item') tag = nd.t === 'proj' ? 'P' : N.leaf[nd.id][1] === 'Z' ? 'Z' : 'A';
      if (lvl === 'leaf') tag = N.leaf[k][1] === 'O' && norm(N.leaf[k][2]) !== norm(N.leaf[k][3]) ? 'O' : 'A';
      if (lvl === 'jur') { const h = N.jur[k][2]; if (h[0][1] > Y[0] || h[h.length - 1][2] < YE) sub = `con datos ${h[0][1]}-${h[h.length - 1][2]}`; }
      let mx = 0; s.forEach((v, i) => { if (i !== iP && v * rfac(i) > s[mx] * rfac(mx)) mx = i; });
      // en el proyecto, actividades y obras no tienen monto propio: sin variaciones (no son recortes)
      const open = !(Y[r] === YP && (lvl === 'item' || lvl === 'leaf') && tag !== 'Z');
      return {k, nd, s, sub, tag, grp, drill: nd.t !== 'leaf', inert: tag === 'Z',
        ref: open ? s[r] * fac(r) : null, sh: open && A.tot[r] ? s[r] / A.tot[r] * 100 : null,
        vant: open && r > 0 ? varR(s, r - 1, r) : null, vcmp: open ? varR(s, c, r) : null,
        dif: open ? (s[r] * rfac(r) - s[c] * rfac(c)) : null, max: s[mx] > 0 ? Y[mx] : null};
    });
  }
  const norm = t => String(t || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9]+/g, ' ').trim();
  const TAGTXT = {P: 'Proyecto', O: 'Obra', A: 'Actividad', G: 'Programa', Z: 'Proyecto 2027'};

  // Búsqueda: programas, proyectos, obras y actividades dentro del ámbito actual
  function searchRows() {
    const q = norm(S.q).split(' ').filter(Boolean);
    const r = yIdx(S.yRef), c = yIdx(S.yCmp);
    const hit = t => { const n = norm(t); return q.every(w => n.includes(w)); };
    const acc = new Map();
    const add = (key, mk, i) => {
      let o = acc.get(key);
      if (!o) { o = mk(); o.s = new Float64Array(NY); acc.set(key, o); }
      o.s[R.y[i]] += val(i);
    };
    for (let i = 0; i < R.y.length; i++) {
      if (!inScope(i)) continue;
      const p = R.p[i], l = R.l[i], lf = N.leaf[l];
      if (hit(N.prog[p][1])) add('g' + p, () => ({nd: {t: 'prog', id: p, label: N.prog[p][1]}, tag: 'G', sub: N.jur[N.prog[p][0]][1], path: () => [{t: 'jur', id: N.prog[p][0], label: N.jur[N.prog[p][0]][1]}, {t: 'prog', id: p, label: N.prog[p][1]}]}), i);
      if (lf[1] === 'Z') continue;  // fila sintética del proyecto: solo cuenta para el programa
      if (lf[1] === 'O' && hit(lf[3])) { const pk = leafProj[l]; add('P' + pk, () => ({nd: {t: 'proj', id: pk, label: lf[3]}, tag: 'P', sub: N.prog[p][1] + ' · ' + N.jur[N.prog[p][0]][1], path: () => [{t: 'jur', id: N.prog[p][0], label: N.jur[N.prog[p][0]][1]}, {t: 'prog', id: p, label: N.prog[p][1]}, {t: 'proj', id: pk, label: lf[3]}]}), i); }
      if (hit(lf[2]) && !(lf[1] === 'O' && norm(lf[2]) === norm(lf[3]))) add('L' + l, () => ({nd: {t: 'leaf', id: l, label: lf[2]}, tag: lf[1] === 'O' ? 'O' : 'A', sub: (lf[1] === 'O' ? lf[3] + ' · ' : '') + N.prog[p][1] + ' · ' + N.jur[N.prog[p][0]][1],
        path: () => { const b = [{t: 'jur', id: N.prog[p][0], label: N.jur[N.prog[p][0]][1]}, {t: 'prog', id: p, label: N.prog[p][1]}]; if (lf[1] === 'O') b.push({t: 'proj', id: leafProj[l], label: lf[3]}); b.push({t: 'leaf', id: l, label: lf[2]}); return b; }}), i);
    }
    return [...acc.values()].map(o => {
      let mx = 0; o.s.forEach((v, i) => { if (i !== iP && v * rfac(i) > o.s[mx] * rfac(mx)) mx = i; });
      const yrs = Y.filter((y, i) => o.s[i]);
      if (yrs.length) o.sub += ` · ${yrs[0] === yrs[yrs.length - 1] ? yrs[0] : yrs[0] + '-' + yrs[yrs.length - 1]}`;
      const open = !(Y[r] === YP && o.tag !== 'G');  // el proyecto no abre debajo del programa
      return Object.assign(o, {drill: true, peak: o.s[mx] * rfac(mx), ref: open ? o.s[r] * fac(r) : null, sh: null, vant: open && r > 0 ? varR(o.s, r - 1, r) : null, vcmp: open ? varR(o.s, c, r) : null, dif: open ? o.s[r] * rfac(r) - o.s[c] * rfac(c) : null, max: o.s[mx] > 0 ? Y[mx] : null});
    });
  }

  function renderTable(A, G) {
    lastA = A; lastG = G;
    if (!CP) CP = colPicker(); else CP.redraw();
    const cols = CP.vis();
    const searching = !!S.q;
    let rows = searching ? searchRows() : rowsFor(A);
    const lvl = A.lvl;
    const scopeName = last() ? last().label : (S.mode === 'fun' ? 'todas las funciones' : 'todo el presupuesto');
    $('nvTblTitle').textContent = searching ? `Resultados para «${S.q}»` : (lvl ? LVL_TXT[lvl] : 'Sin apertura');
    $('nvTblSub').textContent = searching ? `Dentro de ${scopeName}. ${rows.length} resultados, ordenados por su mayor monto real de la serie.` :
      `Montos en ${unitLbl()}; variaciones siempre reales. ` + (lvl === 'item' ? 'Los proyectos de inversión se abren en obras.' : '');
    $('nvTblHint').textContent = searching ? 'Clic en un resultado para ir a ese nivel.' :
      lvl === 'item' && YP ? `Los cuadernos del proyecto ${YP} abren hasta programa y subprograma: el monto ${YP} de cada programa va en una sola fila, sin repartir por actividad u obra.` :
      lvl === 'item' || lvl === 'leaf' ? 'Las actividades y obras no tienen más apertura: clic en un proyecto para ver sus obras.' :
      lvl ? 'Clic en una fila para abrir su detalle. Ordená con clic en el encabezado.' : '';
    if (!searching && !lvl) { $('nvTbl').innerHTML = '<tr><td class="nv-empty">Este es el último nivel de apertura del presupuesto.</td></tr>'; return; }

    // orden
    const sc = S.sort.c, sd = S.sort.d;
    // En la búsqueda, el orden por defecto es por el mayor monto real de la serie
    const key = o => searching && sc === 'ref' ? o.peak : sc === 'nm' ? norm(o.nd.label) : sc[0] === 'y' ? o.s[yIdx(+sc.slice(1))] * fac(yIdx(+sc.slice(1))) : (o[sc] == null || !isFinite(o[sc]) ? Infinity * sd : o[sc]);
    rows.sort((a, b) => { const ka = key(a), kb = key(b); return (ka < kb ? -1 : ka > kb ? 1 : 0) * sd; });
    if (searching) rows = rows.slice(0, 300);

    const hcell = (k, l) => `<th data-k="${k}">${esc(l)}${S.sort.c === k ? ' <span class="ar">' + (sd < 0 ? '↓' : '↑') + '</span>' : ''}</th>`;
    const HL = {sp: 'Serie real', ref: refLbl(S.yRef), sh: '% del nivel', vant: `Var. vs ${S.yRef - 1}`, vcmp: `Var. vs ${S.yCmp}`, dif: `Dif. vs ${S.yCmp}`, max: 'Máx. real'};
    let h = '<thead><tr>' + hcell('nm', searching ? 'Resultado' : (lvl === 'fun' ? 'Función' : lvl === 'jur' ? 'Jurisdicción' : lvl === 'prog' ? 'Programa' : 'Nombre'));
    cols.forEach(c => { h += c.k === 'sp' ? '<th class="nosort">Serie real</th>' : hcell(c.k, c.k[0] === 'y' ? yLbl(+c.k.slice(1)) : HL[c.k]); });
    h += '</tr></thead><tbody>';
    const cell = (o, c) => {
      if (c.k === 'sp') return `<td>${spark(o.s)}</td>`;
      if (c.k === 'ref') return `<td>${fTab(o.ref)}</td>`;
      if (c.k === 'sh') return `<td>${o.sh == null ? '' : nf1.format(o.sh) + '%'}</td>`;
      if (c.k === 'vant' || c.k === 'vcmp') return `<td class="${cls(o[c.k])}">${fPct(o[c.k])}</td>`;
      if (c.k === 'dif') return `<td class="${cls(o.dif)}">${o.dif ? (o.dif > 0 ? '+' : '') + fTab(o.dif) : '<span class="na">—</span>'}</td>`;
      if (c.k === 'max') return `<td>${o.max || '—'}</td>`;
      const yi = yIdx(+c.k.slice(1));
      return `<td class="${yi === iC ? 'y26' : yi === iP ? 'yp' : ''}">${fTab(o.s[yi] * fac(yi))}</td>`;
    };
    const line = (o, i) => `<tr class="${o.drill ? 'dr' : ''}"${o.inert ? '' : ` data-i="${i}"`}><td class="nm">${o.tag ? `<span class="nv-tag ${o.tag}">${TAGTXT[o.tag]}</span>` : ''}${esc(o.nd.label)}${o.sub ? `<span class="sub">${esc(o.sub)}</span>` : ''}</td>${cols.map(c => cell(o, c)).join('')}</tr>`;
    let body = '';
    if (lvl === 'fun' && !searching && sc === 'ref' && sd < 0) {
      // agrupado por finalidad
      const fins = [...new Set(rows.map(o => o.grp))].sort();
      fins.forEach(f => {
        const g = rows.filter(o => o.grp === f);
        const s = new Float64Array(NY); g.forEach(o => o.s.forEach((v, i) => s[i] += v));
        body += `<tr class="grp"><td colspan="${cols.length + 1}">${esc(N.fin[f] || 'Finalidad ' + f)} · ${fM(s[yIdx(S.yRef)] * fac(yIdx(S.yRef)))}</td></tr>`;
        g.forEach(o => body += line(o, rows.indexOf(o)));
      });
    } else rows.forEach((o, i) => body += line(o, i));
    if (!searching) {
      const t = {nd: {label: 'Total'}, s: A.tot, ref: A.tot[yIdx(S.yRef)] * fac(yIdx(S.yRef)), sh: 100, vant: yIdx(S.yRef) > 0 ? varR(A.tot, yIdx(S.yRef) - 1, yIdx(S.yRef)) : null, vcmp: varR(A.tot, yIdx(S.yCmp), yIdx(S.yRef)), dif: A.tot[yIdx(S.yRef)] * rfac(yIdx(S.yRef)) - A.tot[yIdx(S.yCmp)] * rfac(yIdx(S.yCmp)), max: null};
      body += `<tr class="tot"><td class="nm">Total (${rows.length})</td>${cols.map(c => c.k === 'sp' ? '<td></td>' : cell(t, c)).join('')}</tr>`;
    }
    $('nvTbl').innerHTML = h + body + '</tbody>';
    $('nvTbl').querySelectorAll('th[data-k]').forEach(th => th.onclick = () => {
      const k = th.dataset.k; S.sort = {c: k, d: S.sort.c === k ? -S.sort.d : (k === 'nm' ? 1 : -1)}; renderTableOnly();
    });
    $('nvTbl').querySelectorAll('tr[data-i]').forEach(tr => tr.onclick = () => {
      const o = rows[+tr.dataset.i];
      if (searching) go(o.path(), 'jur');
      else if (o.drill) drill(o.nd);
      else go(S.path.concat([o.nd]));
    });
  }

  // ── detalle: inciso, partida, fuente, UE, comuna, subprogramas ──
  const TABS = [['inc', 'Inciso'], ['ppal', 'Partida principal'], ['fte', 'Fuente'], ['ue', 'Unidad ejecutora'], ['geo', 'Comuna'], ['sprog', 'Subprogramas']];
  function renderDetail() {
    const l = last();
    const kinds = N.kinds;
    const progOK = !l || l.t === 'fun' || l.t === 'jur' || l.t === 'prog';
    const tabs = TABS.filter(t => t[0] !== 'sprog' || (l && l.t === 'prog'));
    if (!tabs.some(t => t[0] === S.tab)) S.tab = 'inc';
    $('nvTabs').innerHTML = tabs.map(t => `<button data-v="${t[0]}" class="${t[0] === S.tab ? 'on' : ''}">${t[1]}</button>`).join('');
    $('nvTabs').querySelectorAll('button').forEach(b => b.onclick = () => { S.tab = b.dataset.v; renderDetail(); });
    $('nvDetTitle').textContent = 'Composición ' + yLbl(S.yRef);
    $('nvDetSub').textContent = `${S.yRef === YP ? 'Proyecto ' + YP : metLbl()} por ${TABS.find(t => t[0] === S.tab)[1].toLowerCase()}, ${unitLbl()}; variación real contra ${S.yCmp}.`;
    if (!progOK) {
      $('nvDet').innerHTML = '<tr><td class="nv-empty">La apertura por inciso, fuente, unidad ejecutora y comuna llega hasta programa. Para ' + (l.t === 'proj' ? 'el proyecto' : 'esta actividad u obra') + ' se muestra la serie; subí un nivel para ver la composición del programa.</td></tr>';
      return;
    }
    if (S.yRef === YP && S.tab === 'geo') { $('nvDet').innerHTML = `<tr><td class="nv-empty">El proyecto ${YP} no abre el gasto por comuna. Elegí otro año de referencia para ver esta apertura.</td></tr>`; return; }
    const r = yIdx(S.yRef), c = yIdx(S.yCmp);
    const want = S.tab === 'inc' ? kinds.indexOf('ppal') : kinds.indexOf(S.tab);
    const mi = S.metric === 's' ? 5 : S.metric === 'v' ? 6 : 7;
    const acc = new Map();
    for (const b of N.b) {
      if (b[3] !== want || (b[0] !== r && b[0] !== c)) continue;
      let ok = true;
      for (const n of S.path) {
        if (n.t === 'fun' && b[1] !== n.id) { ok = false; break; }
        if (n.t === 'jur' && progJur[b[2]] !== n.id) { ok = false; break; }
        if (n.t === 'prog' && b[2] !== n.id) { ok = false; break; }
      }
      if (!ok) continue;
      const key = S.tab === 'inc' ? N.ppal[b[4]][1] : b[4];
      let a = acc.get(key); if (!a) { a = [0, 0]; acc.set(key, a); }
      const v = S.metric === 'd' && b[0] === iC ? b[5] : b[mi];
      a[b[0] === r ? 0 : 1] += v;
      if (r === c) a[1] = a[0];
    }
    const name = k => S.tab === 'inc' ? (N.inc[k] || 'Sin inciso') : S.tab === 'ppal' ? esc(N.ppal[k][0]) + ' <span class="sub">' + esc(N.inc[N.ppal[k][1]] || '') + '</span>' : esc(N[S.tab][k]);
    const rows = [...acc.entries()].filter(([, a]) => a[0] || a[1]).map(([k, a]) => ({k, a, v: a[1] > 0 ? ((a[0] * rfac(r)) / (a[1] * rfac(c)) - 1) * 100 : null}));
    rows.sort((x, y) => y.a[0] - x.a[0]);
    const tot = rows.reduce((s, o) => s + o.a[0], 0), totc = rows.reduce((s, o) => s + o.a[1], 0);
    if (!rows.length) { $('nvDet').innerHTML = `<tr><td class="nv-empty">${Y[r] === YP && S.tab === 'geo' ? `El proyecto ${YP} no abre el gasto por comuna.` : 'Sin datos para este año.'}</td></tr>`; return; }
    let h = `<thead><tr><th class="nosort">${TABS.find(t => t[0] === S.tab)[1]}</th><th class="nosort">${yLbl(S.yRef)}</th><th class="nosort">%</th><th class="nosort">${S.yCmp}</th><th class="nosort">Var. real</th></tr></thead><tbody>`;
    rows.forEach(o => {
      h += `<tr><td class="nm">${S.tab === 'ppal' ? name(o.k) : esc(S.tab === 'inc' ? name(o.k) : N[S.tab][o.k])}</td><td>${fTab(o.a[0] * fac(r))}</td><td>${tot ? nf1.format(o.a[0] / tot * 100) + '%' : ''}</td><td>${fTab(o.a[1] * fac(c))}</td><td class="${cls(o.v)}">${o.a[1] > 0 ? fPct(o.v) : (o.a[0] ? 'nuevo' : '—')}</td></tr>`;
    });
    h += `<tr class="tot"><td class="nm">Total</td><td>${fTab(tot * fac(r))}</td><td>100%</td><td>${fTab(totc * fac(c))}</td><td class="${cls(totc > 0 ? ((tot * rfac(r)) / (totc * rfac(c)) - 1) * 100 : null)}">${totc > 0 ? fPct(((tot * rfac(r)) / (totc * rfac(c)) - 1) * 100) : '—'}</td></tr>`;
    $('nvDet').innerHTML = h + '</tbody>';
  }

  // ── mayores subas y bajas entre hijos ──
  function renderTop(A) {
    const r = yIdx(S.yRef), c = yIdx(S.yCmp);
    const box = $('nvTopBox');
    if (!A.lvl || A.kids.size < 2 || r === c) {
      if (chTop) { chTop.destroy(); chTop = null; }
      $('nvTopSub').textContent = r === c ? 'Elegí un año de comparación distinto.' : 'Este nivel no tiene apertura.';
      return;
    }
    // diferencia real en $ (pesos 2026) entre el año de comparación y el de referencia
    const arr = [...A.kids.entries()].map(([k, s]) => ({k, d: s[r] * rfac(r) - s[c] * rfac(c), v: varR(s, c, r)})).filter(o => o.d);
    arr.sort((a, b) => a.d - b.d);
    const neg = arr.filter(o => o.d < 0).slice(0, 7), pos = arr.filter(o => o.d > 0).slice(-7);
    const sel = neg.concat(pos);
    $('nvTopSub').textContent = `Diferencia real ${S.yCmp} → ${yLbl(S.yRef)}, en millones de pesos de ${YL}. Clic en una barra para abrirla.`;
    box.style.height = Math.max(240, sel.length * 30 + 40) + 'px';
    const lab = o => { const t = nodeOf(A.lvl, o.k).label; return t.length > 46 ? t.slice(0, 44) + '…' : t; };
    if (chTop) chTop.destroy();
    chTop = new Chart($('nvTop'), {
      type: 'bar',
      data: {labels: sel.map(lab), datasets: [{data: sel.map(o => mill(o.d)), backgroundColor: sel.map(o => o.d < 0 ? '#C0392B' : '#0A8A5A'), _k: sel.map(o => o.k)}]},
      options: {indexAxis: 'y', responsive: true, maintainAspectRatio: false, animation: {duration: 250},
        plugins: {legend: {display: false}, tooltip: {callbacks: {label: ctx => { const o = sel[ctx.dataIndex]; return ` ${(o.d > 0 ? '+' : '') + nf0.format(mill(o.d))} M (${o.v == null ? 'nuevo' : fPct(o.v)})`; }}}},
        scales: {x: {ticks: {font: {size: 10}, callback: v => nf0.format(v)}, grid: {color: '#EEF1F5'}}, y: {ticks: {font: {size: 10.5}}, grid: {display: false}}},
        onClick: (e, els) => { if (els.length) drill(nodeOf(A.lvl, sel[els[0].index].k)); },
        onHover: (e, els) => { e.native.target.style.cursor = els.length ? 'pointer' : 'default'; }}
    });
  }

  // ── descarga ──
  function download() {
    if (typeof XLSX === 'undefined') { alert('No se cargó la librería de Excel.'); return; }
    const A = aggregate();
    const rows = S.q ? searchRows() : rowsFor(A);
    const ruta = [S.mode === 'fun' ? 'Por función' : 'Por jurisdicción'].concat(S.path.map(n => n.label)).join(' > ');
    const hdr = ['Nombre', 'Tipo / detalle'];
    Y.forEach(y => hdr.push(`${yLbl(y)} nominal`));
    Y.forEach(y => hdr.push(`${yLbl(y)} real ($ ${YL})`));
    hdr.push(`Var. real ${S.yCmp}-${S.yRef} (%)`);
    const aoa = [[`Navegador del presupuesto CABA 2013-${YE} · ${metLbl()}${S.metric === 'd' ? ` (${YL}: sancionado)` : S.metric === 'v' ? ` (${YL}: vigente al ${N.periodo[YL]})` : ''}`],
      ['Ruta: ' + ruta + (S.q ? ` · búsqueda «${S.q}»` : '')],
      ['Montos en millones de pesos. Real: pesos de ' + YL + ' con IPC promedio anual (' + YL + ' estimado' + (YP ? `; ${YP}: proyecto de presupuesto (cuadernos jurisdiccionales), deflactado con inflación ${((IPC[YP] / IPC[YL] - 1) * 100).toFixed(2).replace('.', ',')}%` : '') + '). Sin aplicaciones financieras. Fuente: BA Data (ejecución trimestral y presupuesto sancionado).'],
      [], hdr];
    const lineOf = o => {
      const L = [o.nd.label, (o.tag ? TAGTXT[o.tag] + (o.sub ? ' · ' : '') : '') + (o.sub || '')];
      Y.forEach((y, i) => L.push(+(mill(o.s[i])).toFixed(2)));
      Y.forEach((y, i) => L.push(+(mill(o.s[i] * rfac(i))).toFixed(2)));
      L.push(o.vcmp == null ? '' : +o.vcmp.toFixed(1));
      return L;
    };
    rows.sort((a, b) => b.s[yIdx(S.yRef)] - a.s[yIdx(S.yRef)]).forEach(o => aoa.push(lineOf(o)));
    if (!S.q) aoa.push(lineOf({nd: {label: 'Total'}, s: A.tot, sub: '', vcmp: varR(A.tot, yIdx(S.yCmp), yIdx(S.yRef))}));
    const wb = XLSX.utils.book_new();
    const ws = XLSX.utils.aoa_to_sheet(aoa);
    ws['!cols'] = [{wch: 60}, {wch: 40}].concat(Array(NY * 2 + 1).fill({wch: 13}));
    XLSX.utils.book_append_sheet(wb, ws, 'Vista');
    const name = (last() ? last().label : (S.mode === 'fun' ? 'funciones' : 'jurisdicciones')).replace(/[^\wáéíóúñÁÉÍÓÚÑ ]+/g, '').slice(0, 50).trim().replace(/ +/g, '_');
    XLSX.writeFile(wb, `navegador_presupuesto_${name}.xlsx`);
  }
})();
