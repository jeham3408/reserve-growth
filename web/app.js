/* Reserve growth explorer. No build step, no dependencies: plain JS + inline SVG.
   Data: data/norway.json and data/uk.json, produced by pipeline/. */
'use strict';

const NS = 'http://www.w3.org/2000/svg';
const $ = (s) => document.querySelector(s);
const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const UP = 1.25, DOWN = 0.8;

function h(tag, attrs = {}, text) {
  const e = document.createElement(tag);
  for (const k in attrs) { if (k === 'class') e.className = attrs[k]; else e.setAttribute(k, attrs[k]); }
  if (text !== undefined) e.textContent = text;
  return e;
}
function s(tag, attrs = {}, parent, text) {
  const e = document.createElementNS(NS, tag);
  for (const k in attrs) e.setAttribute(k, attrs[k]);
  if (text !== undefined) e.textContent = text;
  if (parent) parent.appendChild(e);
  return e;
}
const nf = (v, d = 1) => (v == null || isNaN(v)) ? 'n/a' : Number(v).toLocaleString('en-GB', { minimumFractionDigits: d, maximumFractionDigits: d });
const pct = (v) => (v == null || isNaN(v)) ? 'n/a' : Math.round(v * 100) + ' %';
const chg = (af) => (af == null || isNaN(af)) ? 'n/a' : (af >= 1 ? '+' : '−') + Math.round(Math.abs(af - 1) * 100) + ' %';
const cls = (af) => af == null ? 'na' : af >= UP ? 'up' : af <= DOWN ? 'down' : 'flat';
const colour = (c) => css(c === 'up' ? '--up' : c === 'down' ? '--down' : '--flat');
const quantile = (arr, p) => { const a = arr.slice().sort((x, y) => x - y); if (!a.length) return NaN; const i = (a.length - 1) * p, lo = Math.floor(i); return a[lo] + (a[Math.min(lo + 1, a.length - 1)] - a[lo]) * (i - lo); };
const title = (name) => name; // Sodir field names are shown exactly as published

/* ---------- tooltip ---------- */
const tip = $('#tip');
function showTip(evt, head, rows) {
  tip.textContent = '';
  tip.appendChild(h('div', {}, head)).style.fontWeight = '600';
  for (const [k, v] of rows) {
    const r = h('div');
    r.appendChild(h('b', {}, v));
    r.appendChild(h('span', { class: 'k' }, ' ' + k));
    tip.appendChild(r);
  }
  tip.style.opacity = 1;
  const pad = 14, w = tip.offsetWidth, hh = tip.offsetHeight;
  let x = evt.clientX + pad, y = evt.clientY + pad;
  if (x + w > innerWidth - 6) x = evt.clientX - w - pad;
  if (y + hh > innerHeight - 6) y = evt.clientY - hh - pad;
  tip.style.left = Math.max(6, x) + 'px'; tip.style.top = Math.max(6, y) + 'px';
}
const hideTip = () => { tip.style.opacity = 0; };
addEventListener('scroll', hideTip, { passive: true });
const sgn = (v, d = 2) => (v < 0 ? '−' : v > 0 ? '+' : '') + Math.abs(v).toFixed(d);

/* ---------- chart frame ---------- */
function frame(el, m) {
  el.textContent = '';
  const W = Math.max(300, el.clientWidth);
  const H = Math.max(230, Math.min(+el.dataset.h || 320, W * 1.05));
  const svg = s('svg', { viewBox: `0 0 ${W} ${H}`, width: W, height: H, role: 'img' }, el);
  return { svg, W, H, x0: m.l, x1: W - m.r, y0: m.t, y1: H - m.b, iw: W - m.l - m.r, ih: H - m.t - m.b };
}
const lin = (d0, d1, r0, r1) => (v) => r0 + (v - d0) / (d1 - d0) * (r1 - r0);
const log = (d0, d1, r0, r1) => (v) => r0 + (Math.log(v) - Math.log(d0)) / (Math.log(d1) - Math.log(d0)) * (r1 - r0);
const ratioLabel = (v) => v === 1 ? '±0' : v < 1 ? '−' + Math.round((1 - v) * 100) + ' %' : '+' + Math.round((v - 1) * 100) + ' %';
function niceStep(range, target) { const raw = range / target, p = Math.pow(10, Math.floor(Math.log10(raw))); const f = raw / p; return (f < 1.5 ? 1 : f < 3 ? 2 : f < 7 ? 5 : 10) * p; }

let NO, UK, HD, UE, byName = {};
const state = { mode: 'pre', field: 'GRANE', feature: 'size_class', horizon: 5, funnelK: 3 };

/* =====================================================================  1. spaghetti */
function spaghettiSeries() {
  if (state.mode === 'pre') {
    // base = last estimate before the start-up year, plotted at x = -1
    return NO.fields.filter(f => f.pre != null && f.t0 > 2004).map(f => {
      const pts = [[-1, 1, f.t0 - 1, f.pre]];
      f.y.forEach((yr, i) => { if (yr >= f.t0) pts.push([yr - f.t0, f.oe[i] / f.pre, yr, f.oe[i]]); });
      return { f, pts, last: pts[pts.length - 1][1] };
    }).filter(sr => sr.pts.length > 1);
  }
  if (state.mode === 'start') {
    return NO.fields.filter(f => f.cohort).map(f => {
      const pts = [];
      f.y.forEach((yr, i) => { if (yr >= f.by) pts.push([yr - f.t0, f.oe[i] / f.b, yr, f.oe[i]]); });
      return { f, pts, last: pts[pts.length - 1][1] };
    });
  }
  return NO.fields.filter(f => f.pre2004).map(f => {
    const i0 = f.y.indexOf(2004), b = f.oe[i0];
    const pts = f.y.map((yr, i) => [yr, f.oe[i] / b, yr, f.oe[i]]);
    return { f, pts, last: pts[pts.length - 1][1] };
  });
}
function drawSpaghetti() {
  const el = $('#spaghetti'), mode = state.mode, rel = mode !== 'mid';
  const series = spaghettiSeries();
  const narrow = el.clientWidth < 560;
  const fr = frame(el, { l: 52, r: narrow ? 14 : 118, t: 12, b: 40 });
  const { svg } = fr;
  const xd = mode === 'pre' ? [-1, 21] : mode === 'start' ? [0, 21] : [2004, 2025];
  const all = series.flatMap(sr => sr.pts.map(p => p[1]));
  const yd = rel ? [0.1, 4.6] : [Math.min(0.45, Math.min(...all) * 0.95), Math.max(2.2, Math.max(...all) * 1.05)];
  const X = lin(xd[0], xd[1], fr.x0, fr.x1), Y = log(yd[0], yd[1], fr.y1, fr.y0);
  for (const v of [0.125, 0.25, 0.5, 1, 2, 4].filter(v => v >= yd[0] && v <= yd[1])) {
    s('line', { x1: fr.x0, x2: fr.x1, y1: Y(v), y2: Y(v), stroke: css(v === 1 ? '--ink3' : '--grid'), 'stroke-width': 1 }, svg);
    s('text', { x: fr.x0 - 8, y: Y(v) + 4, 'text-anchor': 'end' }, svg, ratioLabel(v));
  }
  const xt = mode === 'pre' ? [-1, 0, 3, 5, 10, 15, 20] : mode === 'start' ? [0, 3, 5, 10, 15, 20] : [2004, 2010, 2015, 2020, 2025];
  for (const v of xt) if (v !== -1) s('text', { x: X(v), y: fr.y1 + 18, 'text-anchor': 'middle' }, svg, String(v));
  if (mode === 'pre') {
    s('line', { x1: X(0), x2: X(0), y1: fr.y0, y2: fr.y1, stroke: css('--ink3'), 'stroke-dasharray': '3 3' }, svg);
    s('text', { x: X(0) + 5, y: fr.y0 + 10, class: 'axis-title' }, svg, 'end of start-up year');
  }
  s('text', { x: (fr.x0 + fr.x1) / 2, y: fr.H - 4, 'text-anchor': 'middle', class: 'axis-title' }, svg,
    mode === 'pre' && !narrow ? 'Years after production start (the line starts at the estimate one year before)' : rel ? 'Years after production start' : 'Resource account (31 December each year)');
  // band + median
  let curve;
  if (mode === 'start') curve = NO.curve.filter(c => c.n >= 8).map(c => ({ x: c.k, lo: c.p10, hi: c.p90, med: c.median, n: c.n }));
  else {
    curve = [];
    for (let x = xd[0]; x <= (rel ? 20 : 2025); x++) {
      const v = series.map(sr => { const p = sr.pts.find(q => q[0] === x); return p ? p[1] : null; }).filter(q => q != null);
      if (v.length >= 8) curve.push({ x, lo: quantile(v, .1), hi: quantile(v, .9), med: quantile(v, .5), n: v.length });
    }
  }
  const band = curve.map(c => `${X(c.x)},${Y(c.hi)}`).concat(curve.slice().reverse().map(c => `${X(c.x)},${Y(c.lo)}`)).join(' ');
  s('polygon', { points: band, fill: css('--band'), opacity: .75 }, svg);
  const gl = s('g', { fill: 'none', 'stroke-linejoin': 'round', 'stroke-linecap': 'round' }, svg);
  const paths = series.map(sr => {
    const d = sr.pts.map((p, i) => (i ? 'L' : 'M') + X(p[0]).toFixed(1) + ' ' + Y(Math.max(p[1], yd[0])).toFixed(1)).join('');
    return s('path', { d, stroke: colour(cls(sr.last)), 'stroke-width': 1.4, opacity: .62 }, gl);
  });
  s('path', { d: curve.map((c, i) => (i ? 'L' : 'M') + X(c.x) + ' ' + Y(c.med)).join(''), fill: 'none', stroke: css('--ink'), 'stroke-width': 2.6, 'stroke-linejoin': 'round' }, svg);
  if (!narrow) {
    const sorted = series.slice().sort((a, b) => b.last - a.last);
    const pick = rel ? sorted.slice(0, 4).concat(sorted.slice(-3), series.filter(q => ['JOHAN SVERDRUP', 'ORMEN LANGE'].includes(q.f.name)))
      : sorted.slice(0, 4).concat(sorted.slice(-2), series.filter(q => ['EKOFISK', 'TROLL'].includes(q.f.name)));
    const labs = [...new Set(pick)].map(sr => ({ sr, y: Y(Math.max(sr.last, yd[0])), x: X(sr.pts[sr.pts.length - 1][0]) })).sort((a, b) => a.y - b.y);
    for (let i = 1; i < labs.length; i++) if (labs[i].y - labs[i - 1].y < 13) labs[i].y = labs[i - 1].y + 13;
    for (const l of labs) {
      s('line', { x1: l.x + 2, x2: fr.x1 + 6, y1: Y(Math.max(l.sr.last, yd[0])), y2: l.y, stroke: css('--ink3'), 'stroke-width': .6 }, svg);
      s('text', { x: fr.x1 + 9, y: l.y + 4, class: 'val' }, svg, l.sr.f.name.length > 15 ? l.sr.f.name.slice(0, 14) + '…' : l.sr.f.name);
    }
  }
  const mi = Math.min(curve.length - 1, rel ? 12 : 16);
  s('text', { x: X(curve[mi].x), y: Y(curve[mi].med) - 8, class: 'lab', 'text-anchor': 'middle' }, svg, 'median');
  const dot = s('circle', { r: 4.5, fill: css('--ink'), stroke: css('--surface'), 'stroke-width': 2, visibility: 'hidden' }, svg);
  const hit = s('rect', { x: fr.x0, y: fr.y0, width: fr.iw, height: fr.ih, fill: 'transparent' }, svg);
  let cur = -1;
  const pick = (evt) => {
    const r = svg.getBoundingClientRect(), k = fr.W / r.width, px = (evt.clientX - r.left) * k, py = (evt.clientY - r.top) * k;
    let best = 1e9, bi = -1, bp = null;
    series.forEach((sr, i) => sr.pts.forEach(p => { const d = (X(p[0]) - px) ** 2 + (Y(Math.max(p[1], yd[0])) - py) ** 2; if (d < best) { best = d; bi = i; bp = p; } }));
    if (bi < 0) return;
    if (cur !== bi) { paths.forEach((p, i) => { p.setAttribute('opacity', i === bi ? 1 : .18); p.setAttribute('stroke-width', i === bi ? 3 : 1.2); }); cur = bi; }
    dot.setAttribute('cx', X(bp[0])); dot.setAttribute('cy', Y(Math.max(bp[1], yd[0]))); dot.setAttribute('visibility', 'visible');
    const f = series[bi].f;
    showTip(evt, f.name, [[`estimate in ${bp[2]} (million Sm³ o.e.)`, nf(bp[3], 1)],
      [mode === 'pre' ? `vs estimate before start-up (${f.t0 - 1}: ${nf(f.pre, 1)})` : mode === 'start' ? `vs first estimate (${f.by}: ${nf(f.b, 1)})` : 'vs the 2004 estimate', chg(bp[1])],
      ['production start', String(f.t0)]]);
    return f;
  };
  hit.addEventListener('pointermove', pick);
  hit.addEventListener('pointerleave', () => { hideTip(); dot.setAttribute('visibility', 'hidden'); paths.forEach(p => { p.setAttribute('opacity', .62); p.setAttribute('stroke-width', 1.4); }); cur = -1; });
  hit.addEventListener('click', (evt) => { const f = pick(evt); if (f) { selectField(f.name); $('#s-field').scrollIntoView({ behavior: 'smooth', block: 'start' }); } });
  hit.style.cursor = 'pointer';

  const hl = NO.headline, m = NO.midlife, o = HD.overall;
  $('#spaghetti-sub').textContent = mode === 'pre'
    ? `${series.length} fields that started producing in 2005 or later. ±0 is the last estimate made before the start-up year, the number the field was started on. A line that ends at +100 % has doubled.`
    : mode === 'start'
      ? `${series.length} fields that started in 2004 or later and have at least four annual estimates. Here ±0 is the estimate at the end of the start-up year, so the revision made in the start-up year itself is left out.`
      : `${series.length} fields that were already producing before 2004. The table starts in 2004, so these lines begin in the middle of each field's life: the early revisions are not included.`;
  $('#spaghetti-cap').textContent = mode === 'pre'
    ? `Three years after start-up (${o.y3.n} fields) the median field is at ${chg(o.y3.median)} (90 % interval ${chg(o.y3.ci90[0])} to ${chg(o.y3.ci90[1])}): ${o.y3.n_down} fields are down 20 % or more and ${o.y3.n_up} are up 25 % or more. Weighted by volume the change is ${chg(o.y3.volume_weighted)}. ${o.start_year_step.n_changed_20pct} fields moved by more than 20 % already in the start-up year. Hover a line for the field, click to open it below.`
    : mode === 'start'
      ? `Five years after start-up (${hl.af5.n} fields) the median field is at ${chg(hl.af5.median)} (90 % interval ${chg(hl.af5.median_ci90[0])} to ${chg(hl.af5.median_ci90[1])}), with ${hl.af5.n_down} fields down 20 % or more and ${hl.af5.n_up} up 25 % or more. Starting the clock after the start-up year hides the early downgrades, which is why this view looks more balanced than the first one.`
      : `Sum of these ${m.n} fields: ${nf(m.sum_2004, 0)} million Sm³ o.e. in 2004 and ${nf(m.sum_last, 0)} now (${chg(m.weighted)}). Of the ${m.n_still_producing} that still produce, only ${pct(m.share_below_1_still_producing)} are below their 2004 estimate. Flat lines are fields that had already shut down.`;
  const lg = $('#spaghetti-legend'); lg.textContent = '';
  const li = (cl, style, text) => { const sp = h('span'); const i = h('i', { class: cl }); i.setAttribute('style', style); sp.appendChild(i); sp.appendChild(document.createTextNode(text)); lg.appendChild(sp); };
  li('', `border-color:${css('--up')}`, 'now up 25 % or more');
  li('', `border-color:${css('--flat')}`, 'within −20 % / +25 %');
  li('', `border-color:${css('--down')}`, 'now down 20 % or more');
  li('', `border-color:${css('--ink')}`, 'median field');
  li('box', `background:${css('--band')}`, 'middle 80 % of fields (at least 8 fields)');
}

function revisionTables() {
  const el = $('#rev-tables'); el.textContent = '';
  const cols = [['name', 'Field', 0], ['t0', 'Start', 0], ['base_oe', 'First estimate', 1], ['last_oe', 'Latest', 1], ['abs_change', 'Change (MSm³ o.e.)', 1], ['af5', 'After 5 y', 2], ['af_last', 'Now', 2], ['concept', 'Concept', 0]];
  const mk = (ttl, rows) => {
    el.appendChild(h('h4', {}, ttl));
    const t = h('table'), tr = h('tr');
    cols.forEach(c => tr.appendChild(h('th', { class: c[2] ? 'n' : '' }, c[1]))); t.appendChild(tr);
    rows.forEach(r => { const row = h('tr'); cols.forEach(c => { const v = r[c[0]]; row.appendChild(h('td', { class: c[2] ? 'n' : '' }, c[2] === 1 ? nf(v, 1) : c[2] === 2 ? chg(v) : String(v ?? ''))); }); t.appendChild(row); });
    el.appendChild(t);
  };
  mk('Largest upward revisions since start-up (per cent)', NO.tables.largest_up_ratio);
  mk('Largest downward revisions since start-up (per cent)', NO.tables.largest_down_ratio);
  mk('Largest upward revisions in volume', NO.tables.largest_up_volume);
  mk('Largest downward revisions in volume', NO.tables.largest_down_volume);
}

/* =====================================================================  2. field explorer */
function selectField(name) {
  const key = (name || '').trim().toUpperCase();
  if (!byName[key]) return false;
  state.field = key; $('#field-search').value = key; drawField(); return true;
}
function drawField() {
  const f = byName[state.field];
  const head = $('#field-head'); head.textContent = '';
  head.appendChild(h('h3', {}, f.name));
  const first = f.oe[0], last = f.oe[f.oe.length - 1];
  let line = `${f.area || 'Area n/a'} · ${f.hc || 'type n/a'} · production start ${f.t0 ?? 'n/a'} · ${f.status || ''}. `;
  if (f.b) line += `First estimate at start-up (${f.by}): ${nf(f.b, 1)} million Sm³ o.e.; latest (${f.y[f.y.length - 1]}): ${nf(last, 1)} (${chg(f.afl)}).`;
  else line += `Estimates ${f.y[0]}–${f.y[f.y.length - 1]}: ${nf(first, 1)} → ${nf(last, 1)} million Sm³ o.e.`;
  head.appendChild(h('p', {}, line));

  // cumulative production by year
  const cum = {}; let c = 0;
  f.py.forEach((yr, i) => { c += f.p[i]; cum[yr] = c; });
  const xs = [Math.min(f.y[0], f.t0 || f.y[0]), 2025];
  if (xs[1] - xs[0] < 4) xs[0] = xs[1] - 4;
  const el = $('#field-est');
  const fr = frame(el, { l: 46, r: 14, t: 12, b: 36 });
  const { svg } = fr;
  const cumPts = []; let lastCum = 0;
  const firstP = f.py.length ? f.py[0] : null;
  for (let yr = xs[0]; yr <= xs[1]; yr++) { if (cum[yr] != null) lastCum = cum[yr]; else if (firstP != null && yr > firstP) { /* keep last */ } else if (firstP == null || yr < firstP) continue; cumPts.push([yr, cum[yr] != null ? cum[yr] : lastCum]); }
  if (firstP != null && firstP < xs[0]) { /* production before the first estimate year */ }
  const ymax = Math.max(...f.oe, ...cumPts.map(p => p[1]), 0.001) * 1.12;
  const X = lin(xs[0], xs[1], fr.x0, fr.x1), Y = lin(0, ymax, fr.y1, fr.y0);
  const st = niceStep(ymax, 4);
  for (let v = 0; v <= ymax; v += st) { s('line', { x1: fr.x0, x2: fr.x1, y1: Y(v), y2: Y(v), stroke: css('--grid') }, svg); s('text', { x: fr.x0 - 8, y: Y(v) + 4, 'text-anchor': 'end' }, svg, nf(v, st < 1 ? (st < 0.1 ? 2 : 1) : 0)); }
  const xstep = (xs[1] - xs[0]) > 12 ? 5 : 2;
  for (let yr = Math.ceil(xs[0] / xstep) * xstep; yr <= xs[1]; yr += xstep) s('text', { x: X(yr), y: fr.y1 + 18, 'text-anchor': 'middle' }, svg, String(yr));
  s('text', { x: fr.x0, y: fr.H - 4, class: 'axis-title' }, svg, 'million Sm³ oil equivalents');
  if (f.t0 && f.t0 >= xs[0] && f.t0 <= xs[1]) {
    s('line', { x1: X(f.t0), x2: X(f.t0), y1: fr.y0, y2: fr.y1, stroke: css('--ink3'), 'stroke-dasharray': '3 3' }, svg);
    s('text', { x: X(f.t0) + 5, y: fr.y0 + 10, class: 'axis-title' }, svg, 'start-up');
  }
  if (cumPts.length > 1) s('path', { d: cumPts.map((p, i) => (i ? 'L' : 'M') + X(p[0]) + ' ' + Y(p[1])).join(''), fill: 'none', stroke: css('--ink3'), 'stroke-width': 2, 'stroke-linejoin': 'round' }, svg);
  s('path', { d: f.y.map((yr, i) => (i ? 'L' : 'M') + X(yr) + ' ' + Y(f.oe[i])).join(''), fill: 'none', stroke: css('--up'), 'stroke-width': 2.4, 'stroke-linejoin': 'round' }, svg);
  f.y.forEach((yr, i) => s('circle', { cx: X(yr), cy: Y(f.oe[i]), r: 3, fill: css('--up'), stroke: css('--surface'), 'stroke-width': 1.5 }, svg));
  const hair = s('line', { y1: fr.y0, y2: fr.y1, stroke: css('--ink3'), visibility: 'hidden' }, svg);
  const hit = s('rect', { x: fr.x0, y: fr.y0, width: fr.iw, height: fr.ih, fill: 'transparent' }, svg);
  hit.addEventListener('pointermove', (evt) => {
    const r = svg.getBoundingClientRect(), px = (evt.clientX - r.left) * fr.W / r.width;
    const yr = Math.round(xs[0] + (px - fr.x0) / fr.iw * (xs[1] - xs[0]));
    const i = f.y.indexOf(yr); const cp = cumPts.find(p => p[0] === yr);
    hair.setAttribute('x1', X(yr)); hair.setAttribute('x2', X(yr)); hair.setAttribute('visibility', 'visible');
    const rows = [];
    if (i >= 0) { rows.push(['estimated recoverable in total', nf(f.oe[i], 2)]); if (f.b && yr >= f.by) rows.push(['vs first estimate', chg(f.oe[i] / f.b)]); }
    if (cp) rows.push(['produced so far', nf(cp[1], 2)]);
    if (!rows.length) rows.push(['', 'no data']);
    showTip(evt, `${f.name} · ${yr}`, rows);
  });
  hit.addEventListener('pointerleave', () => { hideTip(); hair.setAttribute('visibility', 'hidden'); });
  const lg = $('#field-legend'); lg.textContent = '';
  [['--up', 'estimated total recoverable'], ['--ink3', 'produced so far (cumulative)']].forEach(([c, t]) => { const sp = h('span'); const i = h('i'); i.setAttribute('style', `border-color:${css(c)}`); sp.appendChild(i); sp.appendChild(document.createTextNode(t)); lg.appendChild(sp); });

  // production bars
  const el2 = $('#field-prod');
  const fr2 = frame(el2, { l: 46, r: 14, t: 12, b: 36 });
  const yrs = f.py.filter(y => y <= 2025), vals = f.p.slice(0, yrs.length);
  if (!yrs.length) { s('text', { x: fr2.x0, y: fr2.y0 + 20 }, fr2.svg, 'No production reported under this field name.'); }
  else {
    const x0 = Math.min(yrs[0], 2021), x1 = 2025, pm = Math.max(...vals, 0.001) * 1.12;
    const X2 = lin(x0 - .5, x1 + .5, fr2.x0, fr2.x1), Y2 = lin(0, pm, fr2.y1, fr2.y0), bw = Math.max(1.5, fr2.iw / (x1 - x0 + 1) - 2);
    const st2 = niceStep(pm, 4);
    for (let v = 0; v <= pm; v += st2) { s('line', { x1: fr2.x0, x2: fr2.x1, y1: Y2(v), y2: Y2(v), stroke: css('--grid') }, fr2.svg); s('text', { x: fr2.x0 - 8, y: Y2(v) + 4, 'text-anchor': 'end' }, fr2.svg, nf(v, st2 < 1 ? (st2 < 0.1 ? 2 : 1) : 0)); }
    const xst = (x1 - x0) > 30 ? 10 : (x1 - x0) > 12 ? 5 : 2;
    for (let yr = Math.ceil(x0 / xst) * xst; yr <= x1; yr += xst) s('text', { x: X2(yr), y: fr2.y1 + 18, 'text-anchor': 'middle' }, fr2.svg, String(yr));
    s('text', { x: fr2.x0, y: fr2.H - 4, class: 'axis-title' }, fr2.svg, 'million Sm³ o.e. per year (2026 not shown: incomplete)');
    yrs.forEach((yr, i) => {
      const hgt = Math.max(0, fr2.y1 - Y2(vals[i])), rr = Math.min(3, bw / 2, hgt);
      const x = X2(yr) - bw / 2, y = Y2(vals[i]);
      const b = s('path', { d: `M${x} ${fr2.y1}V${y + rr}q0 ${-rr} ${rr} ${-rr}h${bw - 2 * rr}q${rr} 0 ${rr} ${rr}V${fr2.y1}z`, fill: css('--up') }, fr2.svg);
      b.addEventListener('pointermove', (e) => { b.setAttribute('opacity', .7); showTip(e, `${f.name} · ${yr}`, [['million Sm³ o.e. produced', nf(vals[i], 2)]]); });
      b.addEventListener('pointerleave', () => { b.setAttribute('opacity', 1); hideTip(); });
    });
  }
  // facts
  const facts = $('#field-facts'); facts.textContent = '';
  const add = (k, v) => { const d = h('div'); d.appendChild(h('span', {}, k)); d.appendChild(document.createTextNode(v)); facts.appendChild(d); };
  add('After 1 / 3 / 5 years, from the end of the start-up year', `${chg(f.af1)} / ${chg(f.af3)} / ${chg(f.af5)}`);
  if (f.pre != null) add(`After 1 / 3 / 5 years, from the estimate before start-up (${nf(f.pre, 1)})`, `${chg(f.afp1)} / ${chg(f.afp3)} / ${chg(f.afp5)}`);
  add('Now vs first estimate at start-up', chg(f.afl));
  if (f.afpdo != null) add('Now vs estimate before start-up (approx. PDO)', chg(f.afpdo));
  if (f.af04 != null && f.pre2004) add('Now vs the 2004 estimate', chg(f.af04));
  add('Development concept', f.concept || 'n/a');
  if (f.ndev0 != null) add('Wells: exploration before start / development at start / drilled later', `${f.nexp} / ${f.ndev0} / ${f.ndevl}`);
  add('Operator at start-up', f.op0 || 'n/a');
  add('Reservoir', `${f.lith || 'n/a'}, ${f.age || 'n/a'}${f.rd ? ', about ' + nf(f.rd, 0) + ' m deep' : ''}`);
  add('Water depth', f.wd ? nf(f.wd, 0) + ' m' : 'n/a');
  add('Discovered / PDO approved', `${f.disc ?? 'n/a'} / ${f.pdo ?? 'n/a'}`);
  add('In place (2025 snapshot)', f.inplace ? nf(f.inplace, 1) + ' million Sm³ o.e.' : 'n/a');
  add('Latest estimate ÷ in place', f.rfl ? pct(f.rfl) : 'n/a');
  if (f.url) { const d = h('div'); d.appendChild(h('span', {}, 'Source')); const a = h('a', { href: f.url, rel: 'noopener' }, 'Sodir FactPages'); d.appendChild(a); facts.appendChild(d); }
}

/* =====================================================================  3. strip plot (shared) */
function strip(el, rows, o) {
  const narrow = el.clientWidth < 560;
  const rowH = (o.rowH || 62) + (narrow ? 16 : 0), head = narrow ? 38 : 24;
  el.dataset.h = String(rows.length * rowH + 46);
  const fr = frame(el, { l: 8, r: 14, t: 6, b: 40 });
  fr.svg.setAttribute('viewBox', `0 0 ${fr.W} ${rows.length * rowH + 46}`); fr.svg.setAttribute('height', rows.length * rowH + 46);
  const H = rows.length * rowH + 46, y1 = H - 40;
  const { svg } = fr;
  const X = log(o.domain[0], o.domain[1], fr.x0 + 4, fr.x1 - 4);
  if (o.band) s('rect', { x: X(o.band[0]), y: 0, width: X(o.band[1]) - X(o.band[0]), height: y1, fill: css('--band'), opacity: .45 }, svg);
  for (const v of (narrow && o.ticksNarrow ? o.ticksNarrow : o.ticks)) {
    s('line', { x1: X(v), x2: X(v), y1: 0, y2: y1, stroke: css(v === 1 ? '--ink3' : '--grid') }, svg);
    s('text', { x: X(v), y: y1 + 16, 'text-anchor': 'middle' }, svg, o.tickFmt(v));
  }
  s('text', { x: (fr.x0 + fr.x1) / 2, y: H - 4, 'text-anchor': 'middle', class: 'axis-title' }, svg, o.xTitle);
  const dots = [];
  rows.forEach((row, ri) => {
    const top = ri * rowH, mid = top + head + (rowH - head) * 0.48, R = narrow ? 3.4 : 4.4;
    s('text', { x: fr.x0 + 2, y: top + 15, class: 'val' }, svg, narrow && row.short ? row.short : row.label);
    if (row.sub) s('text', narrow ? { x: fr.x0 + 2, y: top + 30 } : { x: fr.x1 - 2, y: top + 15, 'text-anchor': 'end' }, svg, row.sub);
    // simple beeswarm
    const placed = [];
    row.pts.slice().sort((a, b) => a.v - b.v).forEach(p => {
      const x = X(Math.min(Math.max(p.v, o.domain[0]), o.domain[1]));
      let off = 0, k = 0;
      const clash = (yy) => placed.some(q => (q.x - x) ** 2 + (q.y - yy) ** 2 < (2 * R + 0.6) ** 2);
      while (clash(mid + off) && k < 40) { k++; off = (k % 2 ? 1 : -1) * Math.ceil(k / 2) * (R + 0.6); }
      const y = Math.max(top + head + 2, Math.min(top + rowH - 6, mid + off));
      placed.push({ x, y });
      const c = s('circle', { cx: x, cy: y, r: R, fill: colour(p.cls), stroke: css('--surface'), 'stroke-width': 1 }, svg);
      dots.push({ x, y, p, c, row });
    });
    if (row.median != null) {
      if (row.ci && row.ci[0] != null && !isNaN(row.ci[0])) s('line', { x1: X(Math.max(row.ci[0], o.domain[0])), x2: X(Math.min(row.ci[1], o.domain[1])), y1: top + rowH - 3, y2: top + rowH - 3, stroke: css('--ink'), 'stroke-width': 2.5, 'stroke-linecap': 'round' }, svg);
      s('line', { x1: X(row.median), x2: X(row.median), y1: top + head, y2: top + rowH - 1, stroke: css('--ink'), 'stroke-width': 2 }, svg);
    }
    if (ri) s('line', { x1: fr.x0, x2: fr.x1, y1: top, y2: top, stroke: css('--line') }, svg);
  });
  const hit = s('rect', { x: 0, y: 0, width: fr.W, height: y1, fill: 'transparent' }, svg);
  let cur = null;
  hit.addEventListener('pointermove', (evt) => {
    const r = svg.getBoundingClientRect(), k = fr.W / r.width, px = (evt.clientX - r.left) * k, py = (evt.clientY - r.top) * k;
    let best = 900, hitd = null;
    for (const d of dots) { const dd = (d.x - px) ** 2 + (d.y - py) ** 2; if (dd < best) { best = dd; hitd = d; } }
    if (cur && cur !== hitd) { cur.c.setAttribute('stroke', css('--surface')); cur.c.setAttribute('stroke-width', 1); }
    cur = hitd;
    if (!hitd) { hideTip(); return; }
    hitd.c.setAttribute('stroke', css('--ink')); hitd.c.setAttribute('stroke-width', 2);
    showTip(evt, hitd.p.name, o.tip(hitd.p, hitd.row));
  });
  hit.addEventListener('pointerleave', () => { hideTip(); if (cur) { cur.c.setAttribute('stroke', css('--surface')); cur.c.setAttribute('stroke-width', 1); cur = null; } });
}

function drawDrivers() {
  const d = NO.drivers.categorical.find(x => x.feature === state.feature && x.horizon === state.horizon);
  const rows = d.groups.map(g => ({
    label: `${g.group === 'true' || g.group === 'True' ? 'Yes' : g.group === 'false' || g.group === 'False' ? 'No' : g.group}  (${g.n} fields)`,
    sub: `median ${chg(g.median_af)} · ${pct(g.share_large)} revised a lot`,
    median: g.median_af, ci: g.n >= 5 ? g.ci90 : null,
    pts: g.values.map((v, i) => ({ v, name: g.names[i], cls: cls(v) })),
  }));
  strip($('#strip'), rows, {
    domain: [0.1, 4], ticks: [0.125, 0.25, 0.5, 0.8, 1, 1.25, 2, 4], ticksNarrow: [0.125, 0.25, 0.5, 1, 2, 4], tickFmt: ratioLabel, band: [DOWN, UP],
    xTitle: $('#strip').clientWidth < 560 ? `Estimate after ${state.horizon} years vs first estimate` : `Estimate ${state.horizon} years after start-up, compared with the first estimate`,
    tip: (p) => [[`after ${state.horizon} years`, chg(p.v)], ['first estimate, million Sm³ o.e.', nf(byName[p.name]?.b, 1)]],
  });
  const t = d.test;
  $('#strip-cap').textContent = `Each dot is one field; the vertical mark is the group median and the thick bar under it a 90 % bootstrap interval. The shaded zone is −20 % to +25 %. ` +
    (t ? `${t.test}: p = ${nf(t.p, 2)} for a difference in direction and p = ${nf(t.p_magnitude, 2)} for a difference in the size of the change. ` : '') + NO.drivers.note;
}

function drawForest() {
  const el = $('#forest');
  const rowsD = NO.drivers.numeric.filter(x => x.horizon === state.horizon);
  el.dataset.h = String(rowsD.length * 48 + 40);
  const fr = frame(el, { l: 8, r: 12, t: 4, b: 34 });
  const H = rowsD.length * 48 + 40; fr.svg.setAttribute('viewBox', `0 0 ${fr.W} ${H}`); fr.svg.setAttribute('height', H);
  const { svg } = fr, y1 = H - 34;
  const X = lin(-0.75, 0.75, fr.x0 + 4, fr.x1 - 4);
  for (const v of [-0.5, -0.25, 0, 0.25, 0.5]) { s('line', { x1: X(v), x2: X(v), y1: 0, y2: y1, stroke: css(v === 0 ? '--ink3' : '--grid') }, svg); s('text', { x: X(v), y: y1 + 15, 'text-anchor': 'middle' }, svg, (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v).toFixed(2).replace(/0$/, '')); }
  s('text', { x: (fr.x0 + fr.x1) / 2, y: H - 3, 'text-anchor': 'middle', class: 'axis-title' }, svg, 'Spearman rank correlation');
  rowsD.forEach((r, i) => {
    const top = i * 48;
    s('text', { x: fr.x0 + 2, y: top + 14, class: 'val' }, svg, r.label);
    [['signed', top + 27, true], ['magnitude', top + 38, false]].forEach(([k, y, filled]) => {
      const q = r[k];
      const g = s('g', {}, svg);
      s('line', { x1: X(q.ci90[0]), x2: X(q.ci90[1]), y1: y, y2: y, stroke: css(filled ? '--ink' : '--ink3'), 'stroke-width': 2, 'stroke-linecap': 'round' }, g);
      s('circle', { cx: X(q.rho), cy: y, r: 4, fill: filled ? css('--ink') : css('--surface'), stroke: css(filled ? '--ink' : '--ink3'), 'stroke-width': 2 }, g);
      const hit = s('rect', { x: fr.x0, y: y - 5, width: fr.iw, height: 10, fill: 'transparent' }, g);
      hit.addEventListener('pointermove', (e) => showTip(e, r.label, [[filled ? 'with direction (up or down)' : 'with size of change (either way)', sgn(q.rho)], ['90 % interval', `${sgn(q.ci90[0])} to ${sgn(q.ci90[1])}`], ['fields', String(q.n)]]));
      hit.addEventListener('pointerleave', hideTip);
    });
  });
  $('#forest-h').textContent = String(state.horizon);
  const lg = $('#forest-legend'); lg.textContent = '';
  const a = h('span'); const i1 = h('i', { class: 'dot' }); i1.setAttribute('style', `background:${css('--ink')}`); a.appendChild(i1); a.appendChild(document.createTextNode('direction: higher value → revised up')); lg.appendChild(a);
  const b = h('span'); const i2 = h('i', { class: 'dot' }); i2.setAttribute('style', `background:${css('--surface')};outline:2px solid ${css('--ink3')};outline-offset:-2px`); b.appendChild(i2); b.appendChild(document.createTextNode('size: higher value → larger change either way')); lg.appendChild(b);
}

/* =====================================================================  3. second pass: size, timing, drilling */
function scatterHover(svg, fr, dots, tipFn) {
  const hit = s('rect', { x: fr.x0, y: fr.y0, width: fr.iw, height: fr.ih, fill: 'transparent' }, svg);
  let cur = null;
  hit.addEventListener('pointermove', (evt) => {
    const r = svg.getBoundingClientRect(), k = fr.W / r.width, px = (evt.clientX - r.left) * k, py = (evt.clientY - r.top) * k;
    let best = 1600, hd = null;
    for (const d of dots) { const dd = (d.x - px) ** 2 + (d.y - py) ** 2; if (dd < best) { best = dd; hd = d; } }
    if (cur && cur !== hd) { cur.c.setAttribute('stroke', css('--surface')); cur.c.setAttribute('stroke-width', 1.2); }
    cur = hd;
    if (!hd) { hideTip(); return; }
    hd.c.setAttribute('stroke', css('--ink')); hd.c.setAttribute('stroke-width', 2);
    const [head, rows] = tipFn(hd.p); showTip(evt, head, rows);
  });
  hit.addEventListener('pointerleave', () => { hideTip(); if (cur) { cur.c.setAttribute('stroke', css('--surface')); cur.c.setAttribute('stroke-width', 1.2); cur = null; } });
}

function drawFunnel() {
  const el = $('#funnel'), k = state.funnelK, key = 'afp' + k, bbl = NO.meta.sm3_to_bbl;
  const pts = HD.size.points.filter(p => p[key] != null).map(p => ({ ...p, mm: p.size * bbl, v: p[key] }));
  const narrow = el.clientWidth < 560;
  const fr = frame(el, { l: 52, r: 16, t: 26, b: 42 });
  const { svg } = fr, xd = [0.7, 4000], yd = [0.1, 4.6];
  const X = log(xd[0], xd[1], fr.x0, fr.x1), Y = log(yd[0], yd[1], fr.y1, fr.y0);
  s('rect', { x: fr.x0, y: Y(UP), width: fr.iw, height: Y(DOWN) - Y(UP), fill: css('--band'), opacity: .45 }, svg);
  for (const v of [0.125, 0.25, 0.5, 1, 2, 4]) {
    s('line', { x1: fr.x0, x2: fr.x1, y1: Y(v), y2: Y(v), stroke: css(v === 1 ? '--ink3' : '--grid') }, svg);
    s('text', { x: fr.x0 - 8, y: Y(v) + 4, 'text-anchor': 'end' }, svg, ratioLabel(v));
  }
  for (const v of [1, 10, 100, 1000]) {
    s('line', { x1: X(v), x2: X(v), y1: fr.y0, y2: fr.y1, stroke: css('--grid') }, svg);
    s('text', { x: X(v), y: fr.y1 + 18, 'text-anchor': 'middle' }, svg, v === 1000 ? '1 000' : String(v));
  }
  s('line', { x1: X(100), x2: X(100), y1: fr.y0 - 14, y2: fr.y1, stroke: css('--ink3'), 'stroke-dasharray': '4 3' }, svg);
  s('text', { x: (fr.x0 + fr.x1) / 2, y: fr.H - 4, 'text-anchor': 'middle', class: 'axis-title' }, svg,
    narrow ? 'Estimate before start-up, million barrels o.e.' : 'Estimate before start-up, million barrels of oil equivalents (log scale)');
  const a = HD.size.at[String(k)];
  s('text', { x: X(100) - 8, y: fr.y0 - 6, 'text-anchor': 'end', class: 'val' }, svg, narrow ? `small: ±${pct(a.small.typical_change)}` : `under 100 million barrels: typically ±${pct(a.small.typical_change)}`);
  s('text', { x: X(100) + 8, y: fr.y0 - 6, class: 'val' }, svg, narrow ? `larger: ±${pct(a.large.typical_change)}` : `larger fields: typically ±${pct(a.large.typical_change)}`);
  const dots = pts.map(p => {
    const x = X(p.mm), y = Y(Math.max(p.v, yd[0]));
    const c = s('circle', { cx: x, cy: y, r: narrow ? 4.2 : 5.2, fill: colour(cls(p.v)), stroke: css('--surface'), 'stroke-width': 1.2 }, svg);
    return { x, y, p, c };
  });
  if (!narrow) {
    const big = pts.slice().sort((p, q) => q.mm - p.mm).slice(0, 2);
    const lab = pts.slice().sort((p, q) => p.v - q.v).slice(0, 3).concat(pts.slice().sort((p, q) => q.v - p.v).slice(0, 2));
    [...new Set(lab)].forEach(p => s('text', { x: X(p.mm) + 8, y: Y(Math.max(p.v, yd[0])) + 4, class: 'lab' }, svg, p.name));
    big.forEach((p, i) => s('text', { x: X(p.mm) - 8, y: Y(Math.max(p.v, yd[0])) + (i ? 18 : -9), 'text-anchor': 'end', class: 'lab' }, svg, p.name));
  }
  scatterHover(svg, fr, dots, (p) => [p.name, [[`after ${k} year${k > 1 ? 's' : ''}`, chg(p.v)], ['million barrels o.e. before start-up', nf(p.mm, 0)], ['start-up', String(p.t0)], ['concept', p.tieback ? 'satellite / tie-back' : 'own facility']]]);
  const st = HD.size.steps, w = HD.watkins, early = st[4], late = st[5];
  $('#funnel-cap').textContent = `Each dot is a field: how far its estimate had moved ${k} year${k > 1 ? 's' : ''} after start-up, against the size of the estimate before start-up. ` +
    `The ${a.small.n} fields under 100 million barrels had typically moved ${pct(a.small.typical_change)} and ${pct(a.small.share_down)} were down 20 % or more; the ${a.large.n} larger fields had typically moved ${pct(a.large.typical_change)} and ${pct(a.large.share_down)} were down 20 % or more ` +
    `(p = ${nf(a.p_magnitude, 2)} for the size of the change, p = ${nf(a.p_direction, 2)} for the direction). ` +
    `The gap opens early: up to the end of year 1 small fields typically moved ${pct(early.small_typical)} and larger ones ${pct(early.large_typical)} (p = ${nf(early.p, 2)}); from year 1 to year 5 they move alike (${pct(late.small_typical)} and ${pct(late.large_typical)}). ` +
    `The same pattern is in Watkins' ${w.n} UK and Norwegian fields that started 1971–1995: the smaller the field, the larger the revision (p = ${nf(w.magnitude_p, 3)}), with no difference in direction. ` +
    `It holds with the line drawn at 200 or 300 million barrels (p = ${nf(HD.robustness.size_thresholds_mmboe[2].p, 3)} and ${nf(HD.robustness.size_thresholds_mmboe[3].p, 3)}), and is weaker among fields that are still producing (rank correlation ${sgn(HD.robustness.size_rho_3y_fields_still_producing.rho)}, p = ${nf(HD.robustness.size_rho_3y_fields_still_producing.p, 2)}): part of the effect is small fields that were cut hard and then shut down.`;
}

function drawTiming() {
  const el = $('#timing'), T = HD.timing;
  const fr = frame(el, { l: 46, r: 14, t: 12, b: 40 });
  const { svg } = fr, X = lin(-1, T.min_years_followed, fr.x0, fr.x1), Y = lin(-0.3, 1.3, fr.y1, fr.y0);
  for (const v of [0, 0.5, 1]) { s('line', { x1: fr.x0, x2: fr.x1, y1: Y(v), y2: Y(v), stroke: css(v === 0 ? '--ink3' : '--grid') }, svg); s('text', { x: fr.x0 - 8, y: Y(v) + 4, 'text-anchor': 'end' }, svg, pct(v)); }
  const narrowT = el.clientWidth < 420;
  for (let k = -1; k <= T.min_years_followed; k++) { if (narrowT && k === -1) continue; s('text', { x: X(k), y: fr.y1 + 18, 'text-anchor': k === -1 ? 'start' : 'middle' }, svg, k === -1 ? 'before' : k === 0 ? 'start' : String(k)); }
  s('text', { x: (fr.x0 + fr.x1) / 2, y: fr.H - 4, 'text-anchor': 'middle', class: 'axis-title' }, svg, 'Years after production start');
  const series = [['down', '--down'], ['up', '--up']].map(([key, col]) => ({ key, col, pts: [{ k: -1, median: 0, p25: 0, p75: 0 }].concat(T.path[key]) }));
  for (const sr of series) {
    const cl = (v) => Math.max(-0.3, Math.min(1.3, v));
    const band = sr.pts.map(p => `${X(p.k)},${Y(cl(p.p75))}`).concat(sr.pts.slice().reverse().map(p => `${X(p.k)},${Y(cl(p.p25))}`)).join(' ');
    s('polygon', { points: band, fill: css(sr.col), opacity: .14 }, svg);
    s('path', { d: sr.pts.map((p, i) => (i ? 'L' : 'M') + X(p.k) + ' ' + Y(cl(p.median))).join(''), fill: 'none', stroke: css(sr.col), 'stroke-width': 2.4, 'stroke-linejoin': 'round' }, svg);
    sr.pts.forEach(p => s('circle', { cx: X(p.k), cy: Y(cl(p.median)), r: 3.2, fill: css(sr.col), stroke: css('--surface'), 'stroke-width': 1.2 }, svg));
  }
  s('text', { x: X(T.min_years_followed) - 4, y: Y(1) - 10, 'text-anchor': 'end', class: 'lab' }, svg, 'ended down');
  s('text', { x: X(T.min_years_followed) - 4, y: Y(T.path.up[4].median) + 26, 'text-anchor': 'end', class: 'lab' }, svg, 'ended up');
  const hair = s('line', { y1: fr.y0, y2: fr.y1, stroke: css('--ink3'), visibility: 'hidden' }, svg);
  const hit = s('rect', { x: fr.x0, y: fr.y0, width: fr.iw, height: fr.ih, fill: 'transparent' }, svg);
  hit.addEventListener('pointermove', (evt) => {
    const r = svg.getBoundingClientRect(), px = (evt.clientX - r.left) * fr.W / r.width;
    const k = Math.max(0, Math.min(T.min_years_followed, Math.round(-1 + (px - fr.x0) / fr.iw * (T.min_years_followed + 1))));
    hair.setAttribute('x1', X(k)); hair.setAttribute('x2', X(k)); hair.setAttribute('visibility', 'visible');
    showTip(evt, k === 0 ? 'End of the start-up year' : `${k} year${k > 1 ? 's' : ''} after start-up`,
      [['of the eventual downgrade in place', pct(T.path.down[k].median)], ['of the eventual upgrade in place', pct(T.path.up[k].median)]]);
  });
  hit.addEventListener('pointerleave', () => { hideTip(); hair.setAttribute('visibility', 'hidden'); });
  const lg = $('#timing-legend'); lg.textContent = '';
  [['--down', `ended 20 % or more down (${T.n_down} fields)`], ['--up', `ended 25 % or more up (${T.n_up} fields)`]].forEach(([c, t]) => { const sp = h('span'); const i = h('i'); i.setAttribute('style', `border-color:${css(c)}`); sp.appendChild(i); sp.appendChild(document.createTextNode(t)); lg.appendChild(sp); });
  $('#timing-cap').textContent = `How much of a field's eventual change was already in the estimate, year by year (median, with the middle half shaded). Fields followed for at least ${T.min_years_followed} years, measured from the estimate before start-up. ` +
    `One year after start-up, the fields that ended down had ${pct(T.share_of_final_change_after_year1.down)} of their loss in the books; the fields that ended up had ${pct(Math.max(0, T.share_of_final_change_after_year1.up))} of their gain, and after three years still only ${pct(T.share_of_final_change_after_year3.up)} (p < 0.001). The largest single revision comes in year ${nf(T.year_of_largest_step_median.down, 0)} for the losers and year ${nf(T.year_of_largest_step_median.up, 0)} for the winners. Of the ${T.after_year3.down_at_year3.n} fields that were down 20 % or more at year 3, ${T.after_year3.down_at_year3.still_down} were still down at the latest estimate.`;
}

function drawDrill() {
  const el = $('#drill'), D = HD.drilling.old_fields, N = HD.drilling.new_fields;
  const fr = frame(el, { l: 52, r: 14, t: 12, b: 40 });
  const { svg } = fr, pts = D.points, t = (v) => Math.log(1 + v);
  const xmax = Math.max(...pts.map(p => p.rel)) * 1.05, yd = [0.7, Math.max(4.4, Math.max(...pts.map(p => p.af)) * 1.08)];
  const X = lin(0, t(xmax), fr.x0 + 6, fr.x1), Y = log(yd[0], yd[1], fr.y1, fr.y0);
  for (const v of [1, 1.5, 2, 3, 4].filter(v => v <= yd[1])) { s('line', { x1: fr.x0, x2: fr.x1, y1: Y(v), y2: Y(v), stroke: css(v === 1 ? '--ink3' : '--grid') }, svg); s('text', { x: fr.x0 - 8, y: Y(v) + 4, 'text-anchor': 'end' }, svg, ratioLabel(v)); }
  for (const v of [0, 0.5, 1, 2, 4, 8].filter(v => v <= xmax)) { s('line', { x1: X(t(v)), x2: X(t(v)), y1: fr.y0, y2: fr.y1, stroke: css('--grid') }, svg); s('text', { x: X(t(v)), y: fr.y1 + 18, 'text-anchor': 'middle' }, svg, v === 0 ? 'none' : String(v)); }
  s('text', { x: (fr.x0 + fr.x1) / 2, y: fr.H - 4, 'text-anchor': 'middle', class: 'axis-title' }, svg, 'New wells 2005–2025 per well drilled before 2005');
  const dots = pts.map(p => {
    const x = X(t(p.rel)), y = Y(Math.max(yd[0], p.af));
    const c = s('circle', { cx: x, cy: y, r: 4.6, fill: p.producing ? colour(cls(p.af)) : css('--surface'), stroke: p.producing ? css('--surface') : css('--flat'), 'stroke-width': p.producing ? 1.2 : 1.6 }, svg);
    return { x, y, p, c };
  });
  pts.slice().sort((a, b) => b.af - a.af).slice(0, 3).forEach(p => s('text', { x: X(t(p.rel)) - 8, y: Y(p.af) + 4, 'text-anchor': 'end', class: 'lab' }, svg, p.name));
  scatterHover(svg, fr, dots, (p) => [p.name, [['change in the estimate 2004–2025', chg(p.af)], ['wells 2005–2025', String(p.wells_new)], ['wells before 2005', String(p.wells_old)], ['status', p.producing ? 'producing' : 'not producing']]]);
  const lg = $('#drill-legend'); lg.textContent = '';
  const add = (style, text) => { const sp = h('span'); const i = h('i', { class: 'dot' }); i.setAttribute('style', style); sp.appendChild(i); sp.appendChild(document.createTextNode(text)); lg.appendChild(sp); };
  add(`background:${css('--up')}`, 'producing field (colour = growth class)');
  add(`background:${css('--surface')};outline:2px solid ${css('--flat')};outline-offset:-2px`, 'no longer producing');
  const tc = D.terciles_producing;
  const ck = D.checks;
  $('#drill-cap').textContent = `The ${D.n_all} fields that were on stream before 2004: growth in the estimate 2004–2025 against how much they kept drilling. Among the ${D.n_producing} still producing, the third that drilled least grew ${chg(tc[0].median_growth)}, the middle third ${chg(tc[1].median_growth)} and the third that drilled most ${chg(tc[2].median_growth)} (rank correlation ${sgn(D.rho_producing.rho)}, p = ${nf(D.rho_producing.p, 3)}). ` +
    `Two cautions. Small older fields grew most in per cent and also have the most new wells per old well, so with field size held constant the drilling effect is no longer clear (p = ${nf(ck.regression_with_size.log_rel.p, 2)}); and fields that had new deposits added grew as well (rank correlation ${sgn(ck.rho_discoveries_added.rho)}). ` +
    `For the new fields the result holds with size held constant: those with wells drilled after year 1 grew ${chg(N.with_later_wells.median_later_change)} from year 1 to today (${N.with_later_wells.n} fields), those without ${chg(N.no_later_wells.median_later_change)} (${N.no_later_wells.n} fields, p = ${nf(N.regression_p, 2)}).`;
}

function hardText() {
  const o = HD.overall, S = HD.size, T = HD.timing, D = HD.drilling, m1 = NO.models, a3 = S.at['3'];
  $('#hard-sub').textContent = `Second pass. The change is now measured from the last estimate before the start-up year (${HD.meta.n} fields with three years of follow-up), and wells are counted per field from Sodir's wellbore tables. Seven hypotheses were written down before testing; three held.`;
  const box = $('#hard-findings'); box.textContent = '';
  const add = (big, ttl, txt) => { const d = h('div', { class: 'finding' }); d.appendChild(h('span', { class: 'big' }, big)); d.appendChild(h('b', {}, ttl)); d.appendChild(h('p', {}, txt)); box.appendChild(d); };
  const nTieSmall = S.points.filter(p => p.size < S.threshold_msm3 && p.tieback).length;
  add(`×${nf(S.ratio_typical_3y.ratio, 1)}`, 'Small satellite fields are revised twice as much',
    `Three years after start-up, fields under 100 million barrels had typically moved ${pct(a3.small.typical_change)}, larger fields ${pct(a3.large.typical_change)} (ratio ${nf(S.ratio_typical_3y.ratio, 1)}, 90 % interval ${nf(S.ratio_typical_3y.ci90[0], 1)}–${nf(S.ratio_typical_3y.ci90[1], 1)}). ${pct(a3.small.share_down)} of the small fields were down 20 % or more, against ${pct(a3.large.share_down)} of the larger. ${nTieSmall} of the ${S.n_small} small fields are tie-backs to another field's facility, so size and concept cannot be told apart.`);
  const a3y = T.after_year3;
  add(pct(T.share_of_final_change_after_year1.down), 'Downgrades come fast, upgrades come slowly',
    `Fields that ended 20 % or more down had ${pct(T.share_of_final_change_after_year1.down)} of the loss in the estimate one year after start-up. None of the ${T.n_up} fields that ended 25 % or more up had reached half of their gain by then, and after three years they had ${pct(T.share_of_final_change_after_year3.up)} of it. Of the ${a3y.not_down_at_year3.n} fields that were not down 20 % three years after start-up, ${a3y.not_down_at_year3.ended_down} ended that low and ${a3y.not_down_at_year3.ended_up} ended 25 % or more up.`);
  const tc = D.old_fields.terciles_producing;
  const nw = D.new_fields;
  add(chg(nw.with_later_wells.median_later_change), 'Upgrades follow continued drilling',
    `New fields where wells were drilled after year 1 grew ${chg(nw.with_later_wells.median_later_change)} from year 1 to today (${nw.with_later_wells.n} fields); those without later wells ${chg(nw.no_later_wells.median_later_change)} (${nw.no_later_wells.n} fields; p = ${nf(nw.regression_p, 2)} with field size held constant). Among the ${D.old_fields.n_producing} older fields still producing, the third that drilled most relative to before grew ${chg(tc[2].median_growth)}, the third that drilled least ${chg(tc[0].median_growth)}. Reserves are booked when wells are decided, so this describes how growth happens, not a cause.`);

  const mb = $('#model-box'); mb.textContent = '';
  mb.appendChild(h('p', { class: 'sub' }, 'Logistic regression, 5-fold cross-validation repeated 40 times. AUC 0.5 is a coin toss; the last column is what shuffled labels reach 95 % of the time.'));
  const t = h('table'), tr = h('tr'); ['Outcome and inputs', 'Fields', 'Share', 'AUC', 'Chance, 95 %'].forEach((x, i) => tr.appendChild(h('th', { class: i ? 'n' : '' }, x))); t.appendChild(tr);
  const row = (label, n, rate, auc, nul) => { const r = h('tr'); r.appendChild(h('td', {}, label)); [String(n), pct(rate), nf(auc, 2), nf(nul, 2)].forEach(v => r.appendChild(h('td', { class: 'n' }, v))); t.appendChild(r); };
  HD.models.forEach(r => row(r.label, r.n, r.base_rate, r.cv_auc, r.null_auc_p95));
  row('First pass, for comparison: large revision within 3 years measured from the end of the start-up year, ten inputs', m1[2].n, m1[2].base_rate, m1[2].logit_cv_auc_mean, m1[2].permutation_null_auc_p95);
  const w = h('div', { class: 'tablewrap' }); w.appendChild(t); mb.appendChild(w);
  mb.appendChild(h('p', { class: 'caption' }, `With size and concept alone the model reaches AUC ${nf(HD.models[0].cv_auc, 2)} (permutation p = ${nf(HD.models[0].permutation_p, 2)}): better than chance, far from reliable. Adding wells and depth does not help. Knowing that a field is a small tie-back tells you its estimate is uncertain, not which way it will go.`));

  $('#nothold-sub').textContent = 'These comparisons are from the first pass, measured from the end of the start-up year. Oil or gas, area, operator and reservoir age show no clear difference in either pass.';
  const nh = $('#nothold'); nh.textContent = '';
  const ul = h('ul');
  const O = Object.fromEntries(HD.other.map(r => [r.label, r])), C = Object.fromEntries(HD.categories.map(r => [r.label, r]));
  const ex = O['…per 100 MMboe of first estimate'], dep = O['Reservoir depth'], ws = HD.wells_at_start, hp = C["High pressure / HPHT (today's text)"], cx = C["Complex / segmented (today's text)"], tb = C['Satellite / tie-back'];
  [`Appraisal: fields with more exploration and appraisal wells per barrel before start-up were not revised less (rank correlation with the size of the change ${sgn(ex.magnitude_3y.rho)}, p = ${nf(ex.magnitude_3y.p, 2)}). The explanation “small fields are under-appraised” is not supported by the well counts.`,
    `Few wells at start-up: fields with three or fewer wells had typically moved ${pct(ws.few.typical_change)} against ${pct(ws.more.typical_change)} for the rest (p = ${nf(ws.p_magnitude, 2)}). Same direction as size, not clear on its own.`,
    `Deep reservoirs lean down after three years (rank correlation ${sgn(dep.direction_3y.rho)}, p = ${nf(dep.direction_3y.p, 2)}) but not after five (${sgn(dep.direction_5y.rho)}, p = ${nf(dep.direction_5y.p, 2)}).`,
    `High pressure (${hp.yes.n} fields): median ${chg(hp.yes.median)} against ${chg(hp.no.median)}, p = ${nf(hp.p_direction, 2)}. Described as complex (${cx.yes.n} fields): ${chg(cx.yes.median)} against ${chg(cx.no.median)}, p = ${nf(cx.p_direction, 2)}.`,
    `Direction: small fields lean down (median ${chg(a3.small.median)} against ${chg(a3.large.median)} after three years), but that difference is not statistically clear (p = ${nf(a3.p_direction, 2)}). What is clear is the size of the change.`,
    `Tie-backs had typically moved ${pct(tb.yes.typical_change)} and own-facility fields ${pct(tb.no.typical_change)} (p = ${nf(tb.p_magnitude, 2)}). With size, wells and concept in one regression no single one stands out: they describe the same fields.`,
  ].forEach(x => ul.appendChild(h('li', {}, x)));
  nh.appendChild(ul);

  const cl = $('#claims'); cl.textContent = '';
  const claim = (ttl, verdict, paras) => { const d = h('div', { class: 'claim' }); d.appendChild(h('h4', {}, ttl)); d.appendChild(h('span', { class: 'verdict' }, verdict)); paras.forEach(x => d.appendChild(h('p', {}, x))); cl.appendChild(d); };
  const W = UK.watkins, ch = UK.norway_chain, g = NO.literature.geoexpro_small_fields, c = NO.literature.chalk;
  claim('“Norwegian fields grow more than British ones” (Watkins 2000)', 'Reproduced, and it continued – for the old fields',
    [`Recomputed from his tables: ×${nf(W.Norway.weighted_af, 2)} for ${W.Norway.n} Norwegian and ×${nf(W.UK.weighted_af, 2)} for ${W.UK.n} UK oil fields from start-up to 1996.`,
      `Following ${ch.all.n} of the Norwegian fields into Sodir's table: ×${nf(ch.all.af_1996, 2)} by 1996, ×${nf(ch.all.af_2004, 2)} by 2004 and ×${nf(ch.all.af_latest, 2)} today. Fields that started after 2004 show no such growth so far (median ${chg(o.y5.median)} after five years from the estimate before start-up).`]);
  claim('“Small fields started after 2010 shrink” (GEO ExPro 2021)', 'Holds for 2010 and later; the firm part is the spread',
    [`Start-up 2010 or later, first Sodir estimate against the latest: ${g.small.n} fields under 100 MMboe have a median of ${chg(g.small.median)}, ${pct(g.small.share_down_20)} are down 20 % or more and ${g.small.down_60_names.length} lost 60 % or more. The ${g.not_small.n} larger fields have a median of ${chg(g.not_small.median)} (p = ${nf(g.mannwhitney_p, 3)}).`,
      `For start-ups in 2004–2009 the small fields grew instead (median ${chg(g.same_test_start_2004_2009.small.median)}, ${g.same_test_start_2004_2009.small.n} fields). Across all start-ups since 2005 the robust result is that small fields move about twice as much, in both directions.`]);
  const chalkRows = ch.rows.filter(r => /Chalk/.test(r.formation) && r.af_latest != null && !r.note);
  claim('“Chalk fields grow the most”', 'True for the giants before 2004, not since',
    [`From start-up to today the ${ch.chalk.n} chalk fields in Watkins' list grew ×${nf(ch.chalk.af_latest, 2)} in total against ×${nf(ch.sandstone.af_latest, 2)} for sandstone. That is Ekofisk, Valhall, Eldfisk and Hod; ${chalkRows.filter(r => r.af_latest < 1).length} of the ${chalkRows.length} chalk fields ended below their first estimate, and the median chalk field is at ${chg(ch.chalk.median_af_latest)}.`,
      `Since 2004 the producing chalk fields are flat in total (${chg(c.chalk_producing.weighted)}, ${c.chalk_producing.n} fields) while producing sandstone fields grew ${chg(c.sandstone_producing.weighted)} (${c.sandstone_producing.n} fields).`]);
}

/* =====================================================================  4. UK */
function drawUK() {
  const I = UK.indicator, a = I.uk_vs_brown_book_2001, n = I.norway_same_indicator;
  const ukf = {}; UK.fields.forEach(f => { ukf[f.field] = f; });
  const c1 = (v) => v > 1 ? 'up' : 'flat';
  const ptsUK = a.values.map((v, i) => ({ v, name: a.names[i], cls: c1(v), f: ukf[a.names[i]] }));
  const ceased = ptsUK.filter(p => p.f && p.f.ceased);
  const ptsNO = n.values.map((v, i) => ({ v, name: n.names[i], cls: c1(v) }));
  const rows = [
    { short: `UK oil fields (${a.n})`, label: `UK: produced to 2026 ÷ estimate in the 2001 edition (${a.n} fields)`, sub: `${pct(a.share_above_1)} above 1 · median ${nf(a.median, 2)}`, median: a.median, ci: a.median_ci90, pts: ptsUK },
    { short: `…of which have stopped (${ceased.length})`, label: `…of which have stopped producing (${ceased.length} fields)`, sub: `${pct(a.ceased.share_above_1)} above 1 · median ${nf(a.ceased.median, 2)}`, median: a.ceased.median, ci: a.ceased.median_ci90, pts: ceased },
    { short: `Norway, same indicator (${n.n})`, label: `Norway: produced to 2025 ÷ estimate 2004 (${n.n} fields)`, sub: `${pct(n.share_above_1)} above 1 · median ${nf(n.median, 2)}`, median: n.median, ci: n.median_ci90, pts: ptsNO },
  ];
  strip($('#uk-strip'), rows, {
    rowH: 96, domain: [0.5, 4], ticks: [0.5, 0.75, 1, 1.5, 2, 3], tickFmt: (v) => '×' + v, xTitle: $('#uk-strip').clientWidth < 560 ? 'Oil produced so far ÷ old lifetime estimate' : 'Oil produced so far ÷ the old estimate of everything the field would ever produce',
    tip: (p) => { const r = [['produced ÷ old estimate', '×' + nf(p.v, 2)]]; if (p.f) { r.push(['estimate c. 2001, million tonnes', nf(p.f.bb_oil_mt, 1)]); r.push(['produced to 2026, million tonnes', nf(p.f.cum_oil_mt, 1)]); r.push(['status (NSTA)', (p.f.nsta_status || 'n/a').toLowerCase()]); } return r; },
  });
  $('#uk-sub').textContent = `What is open for the UK: the estimate at start-up and in 1996 for ${UK.meta.watkins_uk} oil fields (Watkins 2000), the operator's estimate per field in four annual Brown Book web editions (end of 1997 to end of 2000, ${UE.meta.n_oil_fields} offshore oil fields, from the Internet Archive), and monthly production per field from the regulator (1975–2026). Nothing per field is published after that. Three tests are possible with this.`;
  $('#uk-cap').textContent = `An indirect test that also works for fields still producing: has the field already produced more than the estimate in the 2001 edition? A dot to the right of ×1 proves that estimate was too low; a dot to the left proves nothing while the field still produces. For fields that have stopped, the middle 80 % landed between ×${nf(a.ceased.p10, 2)} and ×${nf(a.ceased.p90, 2)}. The Norwegian row uses the same indicator, so the two are comparable; for Norway the real revision of the same fields is known: median ${chg(n.true_af.median)}.`;
  const lg = $('#uk-legend'); lg.textContent = '';
  [['--up', 'has already produced more than the old estimate'], ['--flat', 'has not (yet)']].forEach(([c, t]) => { const sp = h('span'); const i = h('i', { class: 'dot' }); i.setAttribute('style', `background:${css(c)}`); sp.appendChild(i); sp.appendChild(document.createTextNode(t)); lg.appendChild(sp); });

  // chain bars
  const ch = UK.norway_chain.all, el = $('#chain');
  const fr = frame(el, { l: 8, r: 8, t: 26, b: 40 });
  const bars = [['at start-up', ch.initial, 1], ['1996', ch.y1996, ch.af_1996], ['2004', ch.y2004, ch.af_2004], ['2025', ch.latest, ch.af_latest]];
  const bw = Math.min(90, fr.iw / 4 - 16), Y = lin(0, ch.latest * 1.16, fr.y1, fr.y0);
  bars.forEach((b, i) => {
    const cx = fr.x0 + fr.iw * (i + 0.5) / 4, y = Y(b[1]), x = cx - bw / 2, rr = 4;
    s('path', { d: `M${x} ${fr.y1}V${y + rr}q0 ${-rr} ${rr} ${-rr}h${bw - 2 * rr}q${rr} 0 ${rr} ${rr}V${fr.y1}z`, fill: css('--up') }, fr.svg);
    const two = fr.W < 480;
    s('text', { x: cx, y: y - (two && i ? 21 : 7), 'text-anchor': 'middle', class: 'val' }, fr.svg, `${nf(b[1] / 1000, 1)} bn bbl` + (i && !two ? ` · ×${nf(b[2], 2)}` : ''));
    if (two && i) s('text', { x: cx, y: y - 7, 'text-anchor': 'middle', class: 'val' }, fr.svg, `×${nf(b[2], 2)}`);
    s('text', { x: cx, y: fr.y1 + 17, 'text-anchor': 'middle' }, fr.svg, b[0]);
  });
  s('line', { x1: fr.x0, x2: fr.x1, y1: fr.y1, y2: fr.y1, stroke: css('--ink3') }, fr.svg);
  s('text', { x: (fr.x0 + fr.x1) / 2, y: fr.H - 4, 'text-anchor': 'middle', class: 'axis-title' }, fr.svg, 'Estimated recoverable oil, sum of the same fields');
  $('#chain-sub').textContent = `${ch.n} Norwegian oil fields from Watkins' table that can be followed in Sodir's data. Start-up and 1996 are his figures (from the directorate's annual reports), 2004 and 2025 are Sodir's oil estimates converted at 6.2898 barrels per Sm³. Statfjord and Troll are left out because the two sources define them differently.`;

  const W = UK.watkins, b = I.uk_vs_watkins_1996, d = I.uk_1996_to_2001, mm = UK.matching, box = $('#uk-box'); box.textContent = '';
  const ul = h('ul'), O = UE.outcome, R = UE.revisions, wk = HD.watkins.by_sector.UK;
  [`Start-up estimates leaned low: the ${O.n} fields that have ceased produced ${chg(O.all.median)} relative to the start-up estimate (median, 90 % interval ${chg(O.all.ci90[0])} to ${chg(O.all.ci90[1])}), and ${pct(O.all.share_up)} of them 25 % or more above it. The typical miss was ${pct(O.all.typical_change)}.`,
    `The first years are the unstable ones: over 1997–2000 young fields were revised ${nf(R.groups.young.typical_change / R.groups.mature.typical_change, 1)} times as much as mature ones (${pct(R.groups.young.typical_change)} against ${pct(R.groups.mature.typical_change)}, p ${R.p_young_vs_mature_magnitude < 0.001 ? '< 0.001' : '= ' + nf(R.p_young_vs_mature_magnitude, 3)}).`,
    `Size, the Norwegian result, gets mixed support: in Watkins' ${wk.n} UK fields the revision to 1996 is larger the smaller the field, once time on stream is accounted for (p = ${nf(wk.p, 3)}); in the Brown Book editions small fields moved ${pct(R.groups.all_small.typical_change)} and larger ones ${pct(R.groups.all_large.typical_change)} (p = ${nf(R.p_small_vs_large_magnitude_all, 2)}); in the outcome test there is no difference (${pct(O.small.typical_change)} against ${pct(O.large.typical_change)}).`,
    `Start-up to 1996 (Watkins, ${W.UK.n} fields): ×${nf(W.UK.weighted_af, 2)} in total, but the median field only ×${nf(W.UK.median_af, 2)}; ${pct(W.UK.share_up)} grew 25 % or more and ${pct(W.UK.share_down)} shrank 20 % or more.`,
    `Estimate in the 2001 edition against production to 2026 (${a.n} fields): ${pct(a.share_above_1)} have already produced more.`,
    `Check of the name matching: for ${mm.check_cum_production_1996.n} fields, production to 1996 in the regulator's data is ×${nf(mm.check_cum_production_1996.median_ratio_pprs_over_watkins, 2)} of Watkins' figure (median). ${mm.n_unmatched} of ${mm.n_names} field names have no rows in the production service and are left out.`,
  ].forEach(t => ul.appendChild(h('li', {}, t)));
  box.appendChild(ul);

  const tw = $('#uk-tables'); tw.textContent = '';
  tw.appendChild(h('h4', {}, `Not matched to the production service (${mm.unmatched.length})`));
  const t1 = h('table'); const hr = h('tr'); ['Field', 'In source', 'Closest names in the production service'].forEach(x => hr.appendChild(h('th', {}, x))); t1.appendChild(hr);
  mm.unmatched.forEach(u => { const r = h('tr'); [u.field, u.source, u.closest_pprs_names || '–'].forEach(v => r.appendChild(h('td', {}, v))); t1.appendChild(r); });
  tw.appendChild(t1);
  tw.appendChild(h('p', { class: 'caption' }, `Left out because the production series is incomplete: ${mm.dropped_incomplete_pprs_coverage.join(', ')}.`));
  tw.appendChild(h('h4', {}, 'Matched fields'));
  const t2 = h('table'); const hr2 = h('tr'); [['Field', 0], ['Start-up est. (mmbbl)', 1], ['1996 (mmbbl)', 1], ['c. 2001 (Mt)', 1], ['Produced to 2026 (Mt)', 1], ['Produced ÷ c. 2001', 1], ['Status', 0]].forEach(x => hr2.appendChild(h('th', { class: x[1] ? 'n' : '' }, x[0]))); t2.appendChild(hr2);
  UK.fields.filter(f => f.nsta_names).forEach(f => { const r = h('tr'); r.appendChild(h('td', {}, f.field)); [f.w_initial_mmbbl, f.w_1996_mmbbl, f.bb_oil_mt, f.cum_oil_mt].forEach(v => r.appendChild(h('td', { class: 'n' }, v == null ? '–' : nf(v, 1)))); r.appendChild(h('td', { class: 'n' }, f.ratio_bb2001 == null ? '–' : '×' + nf(f.ratio_bb2001, 2))); r.appendChild(h('td', {}, (f.nsta_status || '').toLowerCase())); t2.appendChild(r); });
  tw.appendChild(t2);
}

/* =====================================================================  4b. UK editions and realised outcome */
function drawUKOutcome() {
  const el = $('#uk-outcome'), O = UE.outcome, pts = O.points;
  const narrow = el.clientWidth < 560;
  const fr = frame(el, { l: 52, r: 16, t: 26, b: 42 });
  const { svg } = fr, xd = [0.7, 3000], yd = [0.3, 5];
  const X = log(xd[0], xd[1], fr.x0, fr.x1), Y = log(yd[0], yd[1], fr.y1, fr.y0);
  s('rect', { x: fr.x0, y: Y(UP), width: fr.iw, height: Y(DOWN) - Y(UP), fill: css('--band'), opacity: .45 }, svg);
  for (const v of [0.5, 1, 2, 4]) { s('line', { x1: fr.x0, x2: fr.x1, y1: Y(v), y2: Y(v), stroke: css(v === 1 ? '--ink3' : '--grid') }, svg); s('text', { x: fr.x0 - 8, y: Y(v) + 4, 'text-anchor': 'end' }, svg, ratioLabel(v)); }
  for (const v of [1, 10, 100, 1000]) { s('line', { x1: X(v), x2: X(v), y1: fr.y0, y2: fr.y1, stroke: css('--grid') }, svg); s('text', { x: X(v), y: fr.y1 + 18, 'text-anchor': 'middle' }, svg, v === 1000 ? '1 000' : String(v)); }
  s('line', { x1: X(100), x2: X(100), y1: fr.y0 - 14, y2: fr.y1, stroke: css('--ink3'), 'stroke-dasharray': '4 3' }, svg);
  s('text', { x: (fr.x0 + fr.x1) / 2, y: fr.H - 4, 'text-anchor': 'middle', class: 'axis-title' }, svg, narrow ? 'Estimate at start-up, million barrels' : 'Estimate at start-up, million barrels of oil (log scale)');
  s('text', { x: X(100) - 8, y: fr.y0 - 6, 'text-anchor': 'end', class: 'val' }, svg, narrow ? `small: ±${pct(O.small.typical_change)}` : `under 100 million barrels: typically ±${pct(O.small.typical_change)} off`);
  s('text', { x: X(100) + 8, y: fr.y0 - 6, class: 'val' }, svg, narrow ? `larger: ±${pct(O.large.typical_change)}` : `larger fields: typically ±${pct(O.large.typical_change)} off`);
  const dots = pts.map(p => { const x = X(Math.max(xd[0], p.size_mmbbl)), y = Y(Math.min(yd[1], Math.max(yd[0], p.ratio))); return { x, y, p, c: s('circle', { cx: x, cy: y, r: narrow ? 4.2 : 5.2, fill: colour(cls(p.ratio)), stroke: css('--surface'), 'stroke-width': 1.2 }, svg) }; });
  if (!narrow) {
    const lab = pts.slice().sort((a, b) => b.ratio - a.ratio).slice(0, 3).concat(pts.slice().sort((a, b) => a.ratio - b.ratio).slice(0, 2), pts.slice().sort((a, b) => b.size_mmbbl - a.size_mmbbl).slice(0, 2));
    [...new Set(lab)].forEach(p => { const right = X(p.size_mmbbl) > fr.x0 + fr.iw * 0.72; s('text', { x: X(Math.max(xd[0], p.size_mmbbl)) + (right ? -8 : 8), y: Y(Math.min(yd[1], Math.max(yd[0], p.ratio))) + 4, 'text-anchor': right ? 'end' : 'start', class: 'lab' }, svg, p.name); });
  }
  scatterHover(svg, fr, dots, (p) => [p.name, [['produced in total ÷ estimate at start-up', chg(p.ratio)], ['estimate at start-up, million barrels', nf(p.size_mmbbl, 0)], ['on stream', `${p.start}–${p.last_oil_year}`], ['estimate from', p.source]]]);
  $('#uk-outcome-cap').textContent = `For a field that has stopped producing there is nothing left to estimate: total production is the answer. Each dot is one of ${O.n} UK oil fields that have ceased, showing total production against the estimate at start-up (${O.n_watkins} from Watkins' table of start-ups before 1997, ${O.n_editions} from the first Brown Book edition that lists the field). ` +
    `The median field produced ${chg(O.all.median)} relative to the start-up estimate (90 % interval ${chg(O.all.ci90[0])} to ${chg(O.all.ci90[1])}); ${pct(O.all.share_up)} ended 25 % or more above it and ${pct(O.all.share_down)} 20 % or more below. The typical miss was ${pct(O.all.typical_change)}: ${pct(O.small.typical_change)} for the ${O.small.n} fields under 100 million barrels and ${pct(O.large.typical_change)} for the ${O.large.n} larger ones (p = ${nf(O.p_magnitude, 2)}), so this test shows no size effect. Fields that have ceased are not a random sample of all fields, and Watkins' estimates under 5 million barrels are left out because his table is rounded to whole millions.`;
}

function drawUKAnnual() {
  const el = $('#uk-annual'), R = UE.revisions;
  const series = UE.fields.filter(f => f.y.length >= 2).map(f => ({ f, pts: f.y.map((y, i) => [y, f.mt[i] / f.mt[0], f.mt[i]]), last: f.mt[f.mt.length - 1] / f.mt[0] }));
  const fr = frame(el, { l: 52, r: 14, t: 12, b: 40 });
  const { svg } = fr, yd = [0.35, 3], X = lin(1997, 2000, fr.x0 + 4, fr.x1 - 4), Y = log(yd[0], yd[1], fr.y1, fr.y0);
  for (const v of [0.5, 1, 2]) { s('line', { x1: fr.x0, x2: fr.x1, y1: Y(v), y2: Y(v), stroke: css(v === 1 ? '--ink3' : '--grid') }, svg); s('text', { x: fr.x0 - 8, y: Y(v) + 4, 'text-anchor': 'end' }, svg, ratioLabel(v)); }
  for (const v of [1997, 1998, 1999, 2000]) s('text', { x: X(v), y: fr.y1 + 18, 'text-anchor': v === 1997 ? 'start' : v === 2000 ? 'end' : 'middle' }, svg, String(v));
  s('text', { x: (fr.x0 + fr.x1) / 2, y: fr.H - 4, 'text-anchor': 'middle', class: 'axis-title' }, svg, 'Estimate at the end of the year');
  const cl = (v) => Math.min(yd[1], Math.max(yd[0], v));
  const gl = s('g', { fill: 'none', 'stroke-linejoin': 'round', 'stroke-linecap': 'round' }, svg);
  const paths = series.map(sr => s('path', { d: sr.pts.map((p, i) => (i ? 'L' : 'M') + X(p[0]).toFixed(1) + ' ' + Y(cl(p[1])).toFixed(1)).join(''), stroke: colour(cls(sr.last)), 'stroke-width': 1.4, opacity: .62 }, gl));
  const dot = s('circle', { r: 4.5, fill: css('--ink'), stroke: css('--surface'), 'stroke-width': 2, visibility: 'hidden' }, svg);
  const hit = s('rect', { x: fr.x0, y: fr.y0, width: fr.iw, height: fr.ih, fill: 'transparent' }, svg);
  let cur = -1;
  hit.addEventListener('pointermove', (evt) => {
    const r = svg.getBoundingClientRect(), k = fr.W / r.width, px = (evt.clientX - r.left) * k, py = (evt.clientY - r.top) * k;
    let best = 1e9, bi = -1, bp = null;
    series.forEach((sr, i) => sr.pts.forEach(p => { const d = (X(p[0]) - px) ** 2 + (Y(cl(p[1])) - py) ** 2; if (d < best) { best = d; bi = i; bp = p; } }));
    if (bi < 0) return;
    if (cur !== bi) { paths.forEach((p, i) => { p.setAttribute('opacity', i === bi ? 1 : .18); p.setAttribute('stroke-width', i === bi ? 3 : 1.2); }); cur = bi; }
    dot.setAttribute('cx', X(bp[0])); dot.setAttribute('cy', Y(cl(bp[1]))); dot.setAttribute('visibility', 'visible');
    const f = series[bi].f;
    showTip(evt, f.name, [[`million tonnes of oil, end of ${bp[0]}`, nf(bp[2], 2)], [`vs end of ${f.y[0]} (${nf(f.mt[0], 2)})`, chg(bp[1])], ['production start', f.start == null ? 'n/a' : String(f.start)]]);
  });
  hit.addEventListener('pointerleave', () => { hideTip(); dot.setAttribute('visibility', 'hidden'); paths.forEach(p => { p.setAttribute('opacity', .62); p.setAttribute('stroke-width', 1.4); }); cur = -1; });
  const st = R.steps.find(x => x.from === 1997 && x.to === 2000), g = R.groups, ck = UE.meta.update2002_check;
  $('#uk-annual-cap').textContent = `${series.length} UK offshore oil fields with an estimate in at least two of the four editions, each relative to its first listed estimate (operator's estimate of recoverable oil originally present, million tonnes). ` +
    (st ? `From the end of 1997 to the end of 2000, ${pct(st.share_changed_10pct)} of ${st.n} fields were revised by more than 10 %. ` : '') +
    `Fields in their first years moved ${nf(g.young.typical_change / g.mature.typical_change, 1)} times as much as mature ones: typically ${pct(g.young.typical_change)} for the ${g.young.n} fields on stream three years or less when first listed, against ${pct(g.mature.typical_change)} for the ${g.mature.n} older fields (p ${R.p_young_vs_mature_magnitude < 0.001 ? '< 0.001' : '= ' + nf(R.p_young_vs_mature_magnitude, 3)}). Small fields moved ${pct(g.all_small.typical_change)} and larger ones ${pct(g.all_large.typical_change)} (p = ${nf(R.p_small_vs_large_magnitude_all, 2)}). ` +
    `The series stops in 2000: the 2002 web update repeats the 2001 figures (${ck.n_identical} of ${ck.n_compared} fields identical).`;
}

/* =====================================================================  method */
function method() {
  const el = $('#method'); el.textContent = '';
  const ck = NO.checks, M = NO.meta;
  const sec = (ttl, items) => { el.appendChild(h('h3', {}, ttl)); const ul = h('ul'); items.forEach(t => { const li = h('li'); if (Array.isArray(t)) { li.appendChild(document.createTextNode(t[0])); li.appendChild(h('a', { href: t[1], rel: 'noopener' }, t[2])); if (t[3]) li.appendChild(document.createTextNode(t[3])); } else li.textContent = t; ul.appendChild(li); }); el.appendChild(ul); };
  sec('Sources and licences', [
    ['Norway: Sodir FactPages tables field_reserves, field_production_yearly, field_activity_status_hst, field, field_in_place_volumes, field_description, field_operator_hst, discovery, facility_fixed and wellbore_exploration_all, downloaded 19 November 2026. Sodir states that its open data is published under the Norwegian Licence for Open Government Data (NLOD): ', 'https://www.sodir.no/en/facts/data-and-analyses/open-data/', 'sodir.no open data', '.'],
    ['UK production: NSTA “UKCS hydrocarbon field production reports (PPRS)” and “Offshore hydrocarbon fields” feature services. The fields layer is marked “NSTA Open User Licence” in its metadata; the production layer states no licence in its metadata. ', 'https://services-eu1.arcgis.com/OZMfUznmLTnWccBc/arcgis/rest/services', 'NSTA ArcGIS services', '.'],
    ['UK estimates 1997–2000: field pages of the DTI “Brown Book” (Development of UK Oil and Gas Resources), web editions 1998, 1999, 2000 and 2001 on dbd-data.co.uk and the 2002 update on og.dti.gov.uk, read from the Internet Archive. Crown copyright; the archived pages state no licence. ', 'https://web.archive.org/web/2003*/dbd-data.co.uk/bb2001/*', 'Wayback Machine', '.'],
    ['Watkins, G.C. (2000), “Characteristics of North Sea oil reserve appreciation”, MIT CEEPR WP 00-008, Tables D-1 and D-2. Copyright of the author; we use the published numbers and do not redistribute the paper. ', 'https://ceepr.mit.edu/wp-content/uploads/2023/02/2000-008.pdf', 'PDF', '.'],
    ['GEO ExPro (11 May 2021), “The size of small fields tends to be overestimated” (analysis by A. Wittemann): ', 'https://geoexpro.com/the-size-of-small-fields-tends-to-be-overestimated/', 'article', '.'],
  ]);
  sec('Definitions', [
    `Estimate = “originally recoverable” oil equivalents per field in each annual resource account (column fldRecoverableOE, version ${M.years[0]}–${M.years[1]}, as of 31 December). It includes what has already been produced.`,
    'Start-up year = first date with status “Producing” in the field status history. Two bases are used for new fields. Base A: the last estimate before the start-up year (account as of 31 December of the year before), the number the field was started on; this is the main one. Base B: the estimate at the end of the start-up year, which was used in the first pass and leaves out the revision made in the start-up year. For fields on stream before 2004 the base is the 2004 estimate, so they enter mid-life.',
    'Typical change = the median absolute change on a ratio scale (a field at −30 % and one at +43 % count the same). Wells are counted from Sodir\'s wellbore tables by field name: exploration and appraisal wells finished before the start-up year, production and injection wells finished by the start-up year, and wellbores finished later.',
    `“Revised a lot” = outside −20 % to +25 % (0.80–1.25, symmetric on a ratio scale). “Small” = under 100 million barrels o.e. (${nf(M.small_msm3, 1)} million Sm³), as in the GEO ExPro article.`,
    'Tie-back = a field with no surface facility of its own in Sodir\'s facility table (three manual corrections, listed in the pipeline). Reservoir age, rock type, depth and “complex” come from Sodir\'s current field descriptions, which are written with hindsight.',
  ]);
  const pub = ck.published_totals.map(p => `${p.year}: our sum of field rows gives ${nf(p.our_sold_pct, 1)} % sold and ${nf(p.our_reserves_pct, 1)} % remaining reserves of Sodir's total of ${nf(p.published_total_resources, 0)} million Sm³ o.e.; Sodir states about ${p.published_sold_pct} % and ${p.published_reserves_pct} %. Production ${nf(p.our_production, 1)} against ${p.published_production} published`).join('. ');
  sec('Checks we ran', [
    `Grane oil: ${nf(ck.grane_oil['2004'], 2)} million Sm³ in 2004 and ${nf(ck.grane_oil['2025'], 2)} in 2025, as expected (120.31 and 150.78).`,
    pub + '.',
    `Cumulative production exceeds the latest recoverable estimate for ${ck.production_exceeds_recoverable.length} fields: ${ck.production_exceeds_recoverable.map(r => `${r.name} (×${nf(r.ratio, 2)})`).join(', ')}. Sleipner Øst is a booking effect: summed over ${ck.sleipner_area.fields.join(', ')}, the production table gives ${nf(ck.sleipner_area.production_table_sum, 0)} and recoverable minus remaining gives ${nf(ck.sleipner_area.recoverable_minus_remaining_sum, 0)} million Sm³ o.e. The others are within 10 %.`,
    `Watkins' tables re-read from the PDF reproduce his factors (${nf(UK.watkins.UK.weighted_af, 2)} and ${nf(UK.watkins.Norway.weighted_af, 2)}); Piper is ${nf(UK.watkins.check_piper.initial, 0)} → ${nf(UK.watkins.check_piper.last, 0)} million barrels.`,
    `Repeating the headline with the 2024 accounts as the last year gives a median of ${chg(ck.robustness.latest_using_2024_accounts.median)} against ${chg(NO.headline.latest.median)} with 2025.`,
  ]);
  sec('Limits', [
    'Only 22 annual accounts exist as open data. Revisions between discovery and 2004, and the appraisal history before start-up, are not visible.',
    `The start-up group is ${HD.meta.n}–${M.cohort_n} fields. The first pass ran ${NO.drivers.n_tests} group tests and found nothing clear. The second pass changed the base to the estimate before start-up and tested seven hypotheses written down in advance (in pipeline/analyse_hard_question.py): size, appraisal wells, wells at start-up, later drilling, depth and pressure, timing, and the same size effect in Watkins' fields. Size (for the size of the change), timing and later drilling held; the others did not on their own. Changing the base after seeing the first result is a choice the reader should know about, which is why both are shown.`,
    'Size and development concept describe nearly the same fields (small fields are tie-backs with few wells), so the data cannot say which of them matters.',
    'A change in the estimate is not always a mis-estimate: new wells, added deposits, injection projects, price and shut-down decisions all move it. The data do not say why an estimate changed.',
    'In-place volumes are a single 2025 snapshot, so recovery-factor results are partly circular.',
    ck.sodir_notice_2026_02_26,
    `UK: annual estimates per field are open for four year-ends only (1997–2000), plus Watkins' start-up and 1996 figures. The outcome test covers the ${UE.outcome.n} fields that have ceased and have a complete production series; fields still producing are not in it. The regulator's production service lacks some older fields (${UE.outcome.dropped_incomplete_production.length} more were dropped for incomplete series), and one reporting name can cover later satellites. Brown Book tonnes and Watkins' barrels are never mixed within one ratio.`,
    'Volumes are oil equivalents for Norway and oil only for the UK and for the Watkins comparison.',
  ]);
}

/* =====================================================================  boot */
function tiles() {
  const o = HD.overall, S = HD.size, T = HD.timing, el = $('#tiles'); el.textContent = '';
  const add = (b, t) => { const d = h('div', { class: 'tile' }); d.appendChild(h('b', {}, b)); d.appendChild(h('span', {}, t)); el.appendChild(d); };
  add(chg(o.y3.median), `median change three years after start-up, from the estimate before start-up (${o.y3.n} new fields, 90 % interval ${chg(o.y3.ci90[0])} to ${chg(o.y3.ci90[1])})`);
  add(pct(o.y3.share_large), `of new fields were revised by more than −20 % / +25 % within three years (${o.y3.n_down} down, ${o.y3.n_up} up)`);
  add('×' + nf(S.ratio_typical_3y.ratio, 1), `small fields (under 100 million barrels) are revised about twice as much as larger fields`);
  add(pct(T.share_of_final_change_after_year1.down), `of a downgrade is in the estimate after one year; upgrades build slowly and follow new wells`);
  document.querySelectorAll('[data-v]').forEach(e => { const k = e.dataset.v; e.textContent = k === 'n_fields' ? NO.meta.n_fields : k === 'n_years' ? (NO.meta.years[1] - NO.meta.years[0] + 1) : `${NO.meta.years[0]}–${NO.meta.years[1]}`; });
}
function drawAll() { drawSpaghetti(); drawField(); drawFunnel(); drawTiming(); drawDrill(); drawDrivers(); drawForest(); drawUKOutcome(); drawUKAnnual(); drawUK(); }

async function main() {
  [NO, UK, HD, UE] = await Promise.all(['norway', 'uk', 'hard', 'uk_editions'].map(n => fetch(`data/${n}.json`).then(r => r.json())));
  NO.fields.forEach(f => { byName[f.name] = f; });
  const dl = $('#field-list'); NO.fields.forEach(f => dl.appendChild(h('option', { value: f.name })));
  const chips = $('#field-chips'); ['GRANE', 'EDVARD GRIEG', 'OSELVAR', 'VEGA', 'JOHAN SVERDRUP', 'EKOFISK'].forEach(n => { const b = h('button', { class: 'chip', type: 'button' }, n); b.addEventListener('click', () => selectField(n)); chips.appendChild(b); });
  const inp = $('#field-search'); inp.value = state.field;
  const tryPick = () => { if (!selectField(inp.value)) { const q = inp.value.trim().toUpperCase(); const hit = q && NO.fields.find(f => f.name.startsWith(q)); if (hit && q.length >= 3) selectField(hit.name); } };
  inp.addEventListener('change', tryPick); inp.addEventListener('keydown', e => { if (e.key === 'Enter') tryPick(); });
  inp.addEventListener('input', () => { if (byName[inp.value.trim().toUpperCase()]) selectField(inp.value); });
  document.querySelectorAll('.seg').forEach(b => b.addEventListener('click', () => { state.mode = b.dataset.mode; document.querySelectorAll('.seg').forEach(x => { x.classList.toggle('on', x === b); x.setAttribute('aria-pressed', x === b); }); drawSpaghetti(); }));
  const sel = $('#drv-feature'); const seen = new Set();
  NO.drivers.categorical.forEach(d => { if (!seen.has(d.feature)) { seen.add(d.feature); sel.appendChild(h('option', { value: d.feature }, d.label)); } });
  sel.value = state.feature;
  sel.addEventListener('change', () => { state.feature = sel.value; drawDrivers(); });
  $('#drv-h').addEventListener('change', (e) => { state.horizon = +e.target.value; drawDrivers(); drawForest(); });
  $('#funnel-k').addEventListener('change', (e) => { state.funnelK = +e.target.value; drawFunnel(); });
  tiles(); hardText(); revisionTables(); method(); drawAll();
  let to; addEventListener('resize', () => { clearTimeout(to); to = setTimeout(drawAll, 150); });
  matchMedia('(prefers-color-scheme: dark)').addEventListener('change', drawAll);
  document.body.dataset.ready = '1';
}
main().catch(err => { const p = h('p', { class: 'note' }, 'Could not load the files in data/. Serve this folder over HTTP, for example: python3 -m http.server 8000 --bind 127.0.0.1 (' + err.message + ')'); document.querySelector('main').prepend(p); });
