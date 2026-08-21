"""
gen_loto7_backtest100_multik.py
-----------------------------------
Generates the "Loto 7 — 100-Draw Multi-K Backtest" page from
loto7_backtest100_multik_data.json (produced by
precompute_loto7_backtest100_multik.py). Mirrors backtest.html's
actual live-recompute architecture: each method's native K=15 pool
per draw is embedded, and topKNums() (the same generic cross-method-
consensus trim/pad port used throughout this site) derives all K=7/
9/13/17 views live in the browser via a K-toggle -- no server-side
recomputation needed per K.

Ranking convention: within each K, methods are ranked by highest
hit7b (7-hit + either bonus number) first, then hit7 (7-hit, any
bonus), then hit6, then hit5, then hit4 -- the same hitXb-first
family used everywhere else on this site, NOT average hits.

Output: public/loto7_backtest100_multik.html
Run: python gen_loto7_backtest100_multik.py
"""
import json
from math import comb

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
DATA_PATH = BASE + r"\loto7_backtest100_multik_data.json"
HTML_OUT = BASE + r"\public\loto7_backtest100_multik.html"

with open(DATA_PATH, encoding='utf-8') as f:
    payload = json.load(f)

METHOD_NAMES = payload['methods']
COLORS = payload['colors']
K_OPTIONS = payload['kOptions']
DATA = payload['data']
LOTO7_MAX = 37
N_METHODS = len(METHOD_NAMES)
T = len(DATA)
draw_lo, draw_hi = DATA[0]['s'], DATA[-1]['s']

# ── Next upcoming draw (#691, not yet drawn) -- same native K=15 pools as
# the live /loto7/predictions page, read directly from its data file so
# this stays in sync whenever that page is regenerated. ─────────────────────
PREDICTIONS_PATH = BASE + r"\public\loto7_predictions_data.json"
with open(PREDICTIONS_PATH, encoding='utf-8') as f:
    predictions_payload = json.load(f)
NEXT_SERIAL = predictions_payload['nextSerial']
NEXT_POOLS = [c['numbers'] for c in predictions_payload['combos']]
if NEXT_SERIAL != draw_hi + 1:
    print(f"WARNING: /loto7/predictions targets #{NEXT_SERIAL} but this backtest's last draw is #{draw_hi} "
          f"(expected next = #{draw_hi + 1}). The upcoming-draw row will still show #{NEXT_SERIAL}, "
          f"just flagging the mismatch.")
if len(NEXT_POOLS) != N_METHODS:
    raise SystemExit(f"Expected {N_METHODS} method pools from predictions data, got {len(NEXT_POOLS)}")

page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Loto 7 — 100-Draw Multi-K Backtest</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
  :root {{
    --bg: #0f172a; --surface: #1e293b; --border: #334155;
    --text: #f1f5f9; --muted: #94a3b8; --accent: #38bdf8;
    --green: #4ade80; --orange: #fb923c; --red: #f87171; --yellow: #facc15;
  }}
  * {{ box-sizing: border-box; }}
  body {{ background: var(--bg); color: var(--text); font-family: system-ui,sans-serif; padding: 24px; margin: 0; }}
  h1 {{ font-size: 1.5rem; margin: 0 0 4px; }}
  .subtitle {{ color: var(--muted); font-size: .875rem; margin-bottom: 20px; }}
  .note {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
           padding: 14px 18px; font-size: .8rem; color: var(--muted); margin-bottom: 20px; line-height: 1.6; }}
  .note p+p {{ margin-top: 8px; }}
  .note code {{ background: #0a0f1e; padding: 1px 5px; border-radius: 4px; font-size: .85em; }}

  .ktoggle {{ display: flex; gap: 8px; margin-bottom: 20px; align-items: center; flex-wrap: wrap; }}
  .ktoggle .lbl {{ font-size: .78rem; color: var(--muted); text-transform: uppercase; letter-spacing: .05em; margin-right: 4px; }}
  .kbtn {{ padding: 7px 16px; background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
           color: var(--muted); font-size: .85rem; font-weight: 600; cursor: pointer; }}
  .kbtn:hover {{ color: var(--text); }}
  .kbtn.active {{ background: var(--accent); border-color: var(--accent); color: #0a0f1e; }}

  .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin-bottom: 20px; }}
  .card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 14px; }}
  .card.best {{ border-color: var(--yellow); box-shadow: 0 0 0 1px var(--yellow); }}
  .card-name {{ font-size: .72rem; color: var(--muted); text-transform: uppercase; letter-spacing: .05em; margin-bottom: 6px; }}
  .card-avg {{ font-size: 1.3rem; font-weight: 700; color: var(--accent); }}
  .card-avg .unit {{ font-size: .7rem; color: var(--muted); font-weight: 400; margin-left: 4px; }}
  .card-sub {{ font-size: .7rem; color: var(--muted); margin-top: 6px; }}

  .chart-wrap {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
                 padding: 20px; margin-bottom: 20px; }}
  .chart-wrap h2 {{ font-size: 1rem; margin: 0 0 4px; }}
  .chart-wrap .desc {{ font-size: .78rem; color: var(--muted); margin-bottom: 14px; }}

  table {{ width: 100%; border-collapse: collapse; font-size: .83rem; }}
  th {{ text-align: right; padding: 9px 10px; border-bottom: 1px solid var(--border); color: var(--muted);
        text-transform: uppercase; font-size: .68rem; letter-spacing: .05em; white-space: nowrap; }}
  th.left {{ text-align: left; }}
  td {{ padding: 9px 10px; border-bottom: 1px solid var(--border); text-align: right; }}
  td.left {{ text-align: left; }}
  tr.best td {{ color: var(--yellow); font-weight: 600; }}
  .baseline-row td {{ color: var(--muted); font-style: italic; }}

  /* Tabs */
  .tabs {{ display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; }}
  .tab  {{ padding: 8px 18px; border-radius: 6px; border: 1px solid var(--border);
           background: var(--surface); color: var(--muted); cursor: pointer; font-size: .875rem; }}
  .tab.active {{ background: var(--accent); color: #0f172a; border-color: var(--accent); font-weight: 600; }}
  .panel {{ display: none; }}
  .panel.active {{ display: block; }}

  /* Draw detail */
  .detail-wrap {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
                  padding: 16px; max-height: 620px; overflow-y: auto; overflow-x: auto; }}
  #detailTable th {{ position: sticky; top: 0; background: var(--surface); z-index: 1; }}
  #detailTable td {{ vertical-align: top; }}
  .balls {{ display: flex; flex-wrap: wrap; gap: 3px; }}
  .ball {{ display: inline-flex; align-items: center; justify-content: center;
           width: 26px; height: 26px; border-radius: 50%; font-size: .7rem; font-weight: 700;
           background: var(--border); color: var(--text); flex-shrink: 0; }}
  .ball.match  {{ background: var(--green); color: #052e16; }}
  .ball.bonus  {{ background: var(--orange); color: #431407; }}
  tr.upcoming-row {{ background: rgba(56,189,248,.08); border-bottom: 2px solid var(--accent); }}
  tr.upcoming-row td {{ color: var(--text); }}
  tr.upcoming-row td:first-child {{ font-weight: 700; color: var(--accent); }}

  /* Detail controls */
  .ctrl-row {{ display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin-bottom: 12px; }}
  .ctrl-row label {{ font-size: .8rem; color: var(--muted); }}
  select.model-sel {{
    padding: 6px 10px; background: var(--surface); border: 1px solid var(--border);
    border-radius: 6px; color: var(--text); font-size: .85rem; cursor: pointer;
  }}
  input.pos-filter {{
    width: 60px; padding: 4px 6px; background: var(--surface);
    border: 1px solid var(--border); border-radius: 6px; color: var(--text); font-size: .8rem;
  }}
  .btn-clear {{
    padding: 4px 10px; background: var(--surface); border: 1px solid var(--border);
    border-radius: 6px; color: var(--muted); font-size: .8rem; cursor: pointer;
  }}
  /* Sticky first 3 columns in compact (All Models) view */
  .sticky-cols th:nth-child(1), .sticky-cols td:nth-child(1) {{
    position: sticky; left: 0; background: var(--surface); z-index: 2; min-width: 48px;
  }}
  .sticky-cols th:nth-child(2), .sticky-cols td:nth-child(2) {{
    position: sticky; left: 48px; background: var(--surface); z-index: 2; min-width: 88px;
  }}
  .sticky-cols th:nth-child(3), .sticky-cols td:nth-child(3) {{
    position: sticky; left: 136px; background: var(--surface); z-index: 2; min-width: 230px;
    border-right: 1px solid var(--border);
  }}
  .scroll-hint {{ font-size: .75rem; color: #64748b; display: none; margin-left: auto; }}
</style>
</head>
<body>

<h1>🎯 Loto 7 — 100-Draw Multi-K Backtest</h1>
<p class="subtitle">Walk-forward evaluation &middot; Draws #{draw_lo}&ndash;#{draw_hi} &middot; {T} draws &middot; {N_METHODS} methods &middot; K = {' / '.join(str(k) for k in K_OPTIONS)}</p>

<div class="note">
  <p>Same architecture as <a href="/backtest.html" style="color:#7dd3fc">Loto6's backtest.html</a>: each method's native
  K=15 candidate pool is computed once per draw, walk-forward (trained on only draws strictly before each target &mdash;
  no lookahead; LSTM additionally trains online after each prediction). The K toggle below then derives K={'/'.join(str(k) for k in K_OPTIONS)} views
  <strong>live in your browser</strong> via <code>topKNums()</code>, the same generic cross-method-consensus trim/pad
  function used across this site &mdash; not a separate server-side computation per K.</p>
  <p><strong style="color:#e2e8f0">Ranking convention:</strong> within each K, methods are ranked by highest
  <strong>hit7b</strong> (7-hit + either bonus number) first, then highest <strong>hit7</strong> (7-hit, any bonus), then
  hit6, then hit5, then hit4 &mdash; the same hitXb-first convention used everywhere else on this site (e.g. Loto6's
  hit6b&rarr;hit6&rarr;hit5), NOT average hits.</p>
  <p>Backtest window: the last {T} real draws only (unlike <a href="/loto7_backtest.html" style="color:#7dd3fc">the
  full-history Loto7 backtest</a>, which covers all {draw_hi} draws at a fixed K=7).</p>
</div>

<div class="ktoggle">
  <span class="lbl">Pick size:</span>
  {"".join(f'<button class="kbtn" data-k="{k}" onclick="setK({k})">K = {k}</button>' for k in K_OPTIONS)}
</div>

<div class="tabs">
  <button class="tab active" onclick="switchTab('ranking',this)">Ranking</button>
  <button class="tab" onclick="switchTab('detail',this)">Draw Detail</button>
</div>

<div id="tab-ranking" class="panel active">
  <div class="cards" id="cards"></div>

  <div class="chart-wrap"><canvas id="distChart" height="110"></canvas></div>

  <div class="chart-wrap">
    <h2>Full ranking</h2>
    <p class="desc">Sorted by hit7b &rarr; hit7 &rarr; hit6 &rarr; hit5 &rarr; hit4 (descending). Not average hits.</p>
    <table>
      <thead>
        <tr>
          <th class="left">Method</th><th>hit7b</th><th>hit7</th><th>hit6</th><th>hit5</th><th>hit4</th>
          <th>Avg Hits</th><th>vs Random</th><th>Bonus Hit %</th>
        </tr>
      </thead>
      <tbody id="rankBody"></tbody>
    </table>
  </div>
</div>

<div id="tab-detail" class="panel">
  <div class="ctrl-row">
    <label>Model:</label>
    <select id="modelSelect" class="model-sel" onchange="buildDetail()">
      <option value="-1">All Models (compact)</option>
      {"".join(f'<option value="{i}">{i+1}: {name}</option>' for i, name in enumerate(METHOD_NAMES))}
    </select>
    <span id="scrollHint" class="scroll-hint">&larr; scroll right to see all {N_METHODS} models &rarr;</span>
  </div>
  <div class="ctrl-row" id="posFilterRow">
    <label>Filter actual by position:</label>
    <input id="f1" class="pos-filter" type="number" min="1" max="37" placeholder="P1" oninput="applyFilter()">
    <input id="f2" class="pos-filter" type="number" min="1" max="37" placeholder="P2" oninput="applyFilter()">
    <input id="f3" class="pos-filter" type="number" min="1" max="37" placeholder="P3" oninput="applyFilter()">
    <input id="f4" class="pos-filter" type="number" min="1" max="37" placeholder="P4" oninput="applyFilter()">
    <input id="f5" class="pos-filter" type="number" min="1" max="37" placeholder="P5" oninput="applyFilter()">
    <input id="f6" class="pos-filter" type="number" min="1" max="37" placeholder="P6" oninput="applyFilter()">
    <input id="f7" class="pos-filter" type="number" min="1" max="37" placeholder="P7" oninput="applyFilter()">
    <button class="btn-clear" onclick="clearFilters()">Clear</button>
    <span id="filterCount" style="font-size:.75rem;color:var(--muted);"></span>
  </div>
  <div class="detail-wrap">
    <table id="detailTable">
      <thead id="detailHead"></thead>
      <tbody id="detailBody"></tbody>
    </table>
  </div>
</div>

<script>
const METHODS = {json.dumps(METHOD_NAMES)};
const COLORS  = {json.dumps(COLORS)};
const DATA    = {json.dumps(DATA, separators=(',', ':'))};
const LOTO7_MAX = {LOTO7_MAX};
const T = {T};
const NEXT_SERIAL = {NEXT_SERIAL};
const NEXT_POOLS = {json.dumps(NEXT_POOLS, separators=(',', ':'))};

// ── topKNums: exact JS port used throughout this site (generic, proven for
// any target K, not just the button presets). ──────────────────────────────
function topKNums(combo, allPools, k) {{
  const freq = {{}};
  for (const pool of allPools) for (const n of pool) freq[n] = (freq[n] || 0) + 1;
  if (combo.length === k) return [...combo].sort((a,b)=>a-b);
  if (combo.length > k) {{
    return [...combo].sort((a,b) => (freq[b]||0) - (freq[a]||0)).slice(0, k).sort((a,b)=>a-b);
  }}
  const inCombo = new Set(combo);
  let extra = Object.keys(freq).map(Number).filter(n => !inCombo.has(n))
    .sort((a,b) => (freq[b]||0) - (freq[a]||0));
  if (combo.length + extra.length < k) {{
    const have = new Set([...combo, ...extra]);
    for (let n = 1; n <= LOTO7_MAX; n++) if (!have.has(n)) extra.push(n);
  }}
  extra = extra.slice(0, k - combo.length);
  return [...combo, ...extra].sort((a,b)=>a-b);
}}

function HP(k, K) {{
  // hypergeometric: P(exactly k of the 7 winning numbers in a K-pick from 37)
  const C = (n,r) => {{ if (r<0||r>n) return 0; let x=1; for (let i=0;i<r;i++) x=x*(n-i)/(i+1); return x; }};
  return C(7,k) * C(LOTO7_MAX-7, K-k) / C(LOTO7_MAX, K);
}}

function computeForK(K) {{
  const hitCounts = METHODS.map(() => [0,0,0,0,0,0,0,0]);
  const hit7bCounts = new Array(METHODS.length).fill(0);
  const bonusCounts = new Array(METHODS.length).fill(0);
  const matchSeries = METHODS.map(() => []);
  DATA.forEach(r => {{
    const actualSet = new Set(r.a);
    r.p.forEach((pool, mi) => {{
      const combo = topKNums(pool, r.p, K);
      const hits = combo.filter(n => actualSet.has(n)).length;
      hitCounts[mi][Math.min(hits,7)]++;
      matchSeries[mi].push(hits);
      const bonusHit = combo.includes(r.b1) || combo.includes(r.b2);
      if (bonusHit) bonusCounts[mi]++;
      if (hits === 7 && bonusHit) hit7bCounts[mi]++;
    }});
  }});
  const randAvg = [0,1,2,3,4,5,6,7].reduce((s,k) => s + k*HP(k,K), 0);
  // P(bonus hit) = 1 - P(neither of 2 bonus numbers in the K-pick)
  const randBonusPct = (1 - (C(LOTO7_MAX-2, K) / C(LOTO7_MAX, K))) * 100;
  const randDist = [0,1,2,3,4,5,6,7].map(k => HP(k,K) * T);
  return {{ hitCounts, hit7bCounts, bonusCounts, matchSeries, randAvg, randBonusPct, randDist }};
}}
function C(n, r) {{ if (r<0||r>n) return 0; let x=1; for (let i=0;i<r;i++) x=x*(n-i)/(i+1); return x; }}

let curK = 7;
let distChart = null;

function setK(K) {{
  curK = K;
  document.querySelectorAll('.kbtn').forEach(b => b.classList.toggle('active', +b.dataset.k === K));
  render();
  // Sync Draw Detail to the new K (same pattern as Loto6's backtest.html buildAll())
  builtModel = -999;
  if (document.querySelector('#tab-detail.active')) buildDetail();
}}

function render() {{
  const {{ hitCounts, hit7bCounts, bonusCounts, matchSeries, randAvg, randBonusPct, randDist }} = computeForK(curK);
  const avgHits = matchSeries.map(s => s.reduce((a,b)=>a+b,0) / T);
  const ranked = METHODS.map((_, mi) => mi).sort((a, b) => {{
    if (hit7bCounts[b] !== hit7bCounts[a]) return hit7bCounts[b] - hit7bCounts[a];
    if (hitCounts[b][7] !== hitCounts[a][7]) return hitCounts[b][7] - hitCounts[a][7];
    if (hitCounts[b][6] !== hitCounts[a][6]) return hitCounts[b][6] - hitCounts[a][6];
    if (hitCounts[b][5] !== hitCounts[a][5]) return hitCounts[b][5] - hitCounts[a][5];
    return hitCounts[b][4] - hitCounts[a][4];
  }});
  const bestMi = ranked[0];

  // Cards: top 5 by rank
  const cardsEl = document.getElementById('cards');
  cardsEl.innerHTML = ranked.slice(0, 5).map(mi => `
    <div class="card${{mi === bestMi ? ' best' : ''}}">
      <div class="card-name">${{METHODS[mi]}}${{mi === bestMi ? ' ★' : ''}}</div>
      <div class="card-avg">${{hit7bCounts[mi]}}<span class="unit">hit7b</span></div>
      <div class="card-sub">hit7: ${{hitCounts[mi][7]}} &middot; hit6: ${{hitCounts[mi][6]}} &middot; hit5: ${{hitCounts[mi][5]}} &middot; hit4: ${{hitCounts[mi][4]}}</div>
    </div>
  `).join('');

  // Ranking table
  const tbody = document.getElementById('rankBody');
  let rows = ranked.map(mi => {{
    const lift = (avgHits[mi] / randAvg).toFixed(2);
    return `<tr class="${{mi === bestMi ? 'best' : ''}}">
      <td class="left">${{METHODS[mi]}}</td>
      <td>${{hit7bCounts[mi]}}</td><td>${{hitCounts[mi][7]}}</td><td>${{hitCounts[mi][6]}}</td>
      <td>${{hitCounts[mi][5]}}</td><td>${{hitCounts[mi][4]}}</td>
      <td>${{avgHits[mi].toFixed(4)}}</td><td>${{lift}}&times;</td><td>${{(bonusCounts[mi]/T*100).toFixed(1)}}%</td>
    </tr>`;
  }}).join('');
  rows += `<tr class="baseline-row">
    <td class="left">Random baseline (expected)</td>
    <td>0</td><td>${{randDist[7].toFixed(2)}}</td><td>${{randDist[6].toFixed(2)}}</td>
    <td>${{randDist[5].toFixed(2)}}</td><td>${{randDist[4].toFixed(2)}}</td>
    <td>${{randAvg.toFixed(4)}}</td><td>1.00&times;</td><td>${{randBonusPct.toFixed(1)}}%</td>
  </tr>`;
  tbody.innerHTML = rows;

  // Distribution chart
  if (distChart) distChart.destroy();
  distChart = new Chart(document.getElementById('distChart').getContext('2d'), {{
    type: 'bar',
    data: {{
      labels: ['0','1','2','3','4','5','6','7'],
      datasets: [
        ...METHODS.map((name, mi) => ({{
          label: name, data: hitCounts[mi],
          backgroundColor: COLORS[mi]+'bb', borderColor: COLORS[mi], borderWidth: 1
        }})),
        {{ label: 'Random baseline', data: randDist,
          type: 'line', borderColor: '#fff', borderDash: [5,3],
          borderWidth: 2, pointRadius: 0, fill: false, tension: 0 }}
      ]
    }},
    options: {{
      responsive: true,
      plugins: {{ legend: {{ labels: {{ color: '#94a3b8', boxWidth: 12, font: {{ size: 10 }} }} }} }},
      scales: {{
        x: {{ ticks: {{ color: '#94a3b8' }}, grid: {{ color: '#334155' }},
             title: {{ display: true, text: 'Matches (out of 7)', color: '#94a3b8' }} }},
        y: {{ ticks: {{ color: '#94a3b8' }}, grid: {{ color: '#334155' }},
             title: {{ display: true, text: 'Count', color: '#94a3b8' }} }}
      }}
    }}
  }});
}}

// ── Draw Detail tab ──────────────────────────────────────────────────────
const MSHORT = {json.dumps([
    "Poly-F", "MA-37", "Exp-W", "FreqAll", "Markov", "ARIMA", "RF", "RL-Q",
    "HMM", "kNN", "ModCyc", "Apriori", "MonteCar", "NaiveBay", "WMA-37", "LSTM",
])};
const REV_DATA = [...DATA].reverse();
let builtModel = -999;

function matchColor(m) {{
  return m>=5 ? '#4ade80' : m>=4 ? '#86efac' : m>=3 ? '#facc15' : '#94a3b8';
}}

function buildDetail() {{
  const mi = parseInt(document.getElementById('modelSelect').value);
  if (mi === builtModel) {{ applyFilter(); return; }}
  builtModel = mi;

  const head = document.getElementById('detailHead');
  const body = document.getElementById('detailBody');
  body.innerHTML = '';
  const tbl  = document.getElementById('detailTable');
  const hint = document.getElementById('scrollHint');

  if (mi === -1) {{
    tbl.classList.add('sticky-cols');
    hint.style.display = 'inline';
    head.innerHTML =
      '<tr><th>#</th><th>Date</th><th>Actual</th>' +
      MSHORT.map((s,i) =>
        '<th style="color:'+COLORS[i]+';text-align:center">'+s+
        '<br><span style="font-weight:400;font-size:.7rem;color:#64748b">'+curK+'pk</span></th>'
      ).join('') + '</tr>';

    // ── Upcoming draw row (not yet drawn -- no actual result to compare
    // against, so no hit highlighting). Same native pools as the live
    // /loto7/predictions page, re-derived to the current K via topKNums(). ──
    const upTr = document.createElement('tr');
    upTr.className = 'upcoming-row';
    let upCells =
      '<td>#'+NEXT_SERIAL+'</td>' +
      '<td><em>upcoming</em></td>' +
      '<td><em style="color:#64748b">not yet drawn</em></td>';
    NEXT_POOLS.forEach(pool => {{
      const combo = topKNums(pool, NEXT_POOLS, curK);
      upCells += '<td style="text-align:center;font-size:.68rem;color:#7dd3fc;white-space:normal;min-width:110px">' +
        combo.join(', ') + '</td>';
    }});
    upTr.innerHTML = upCells;
    body.appendChild(upTr);

    REV_DATA.forEach(r => {{
      const tr = document.createElement('tr');
      tr.dataset.actual = JSON.stringify(r.a);
      const actualSet = new Set(r.a);
      let cells =
        '<td>'+r.s+'</td>' +
        '<td>'+(r.d ? r.d.slice(0,10) : '')+'</td>' +
        '<td><div class="balls">' +
        r.a.map(n=>'<span class="ball">'+n+'</span>').join('') +
        '<span class="ball bonus">'+r.b1+'★</span>' +
        '<span class="ball bonus">'+r.b2+'★</span></div></td>';
      r.p.forEach((pool,i) => {{
        const combo = topKNums(pool, r.p, curK);
        const m = combo.filter(n=>actualSet.has(n)).length;
        const bh = combo.includes(r.b1) || combo.includes(r.b2);
        cells += '<td style="text-align:center;font-weight:700;color:'+matchColor(m)+'">'+m+(bh?'✦':'')+'</td>';
      }});
      tr.innerHTML = cells;
      body.appendChild(tr);
    }});
  }} else {{
    tbl.classList.remove('sticky-cols');
    hint.style.display = 'none';
    head.innerHTML =
      '<tr><th>#</th><th>Date</th><th>Actual (7)</th>' +
      '<th>'+METHODS[mi]+' — '+curK+' picks</th>' +
      '<th style="text-align:center">Hits</th></tr>';

    // ── Upcoming draw row (same treatment as the All Models view) ───────────
    const upTrSingle = document.createElement('tr');
    upTrSingle.className = 'upcoming-row';
    const upCombo = topKNums(NEXT_POOLS[mi], NEXT_POOLS, curK);
    upTrSingle.innerHTML =
      '<td>#'+NEXT_SERIAL+'</td>' +
      '<td><em>upcoming</em></td>' +
      '<td><em style="color:#64748b">not yet drawn</em></td>' +
      '<td><div class="balls">' + upCombo.map(n=>'<span class="ball">'+n+'</span>').join('') + '</div></td>' +
      '<td style="text-align:center;color:#64748b">&mdash;</td>';
    body.appendChild(upTrSingle);

    REV_DATA.forEach(r => {{
      const tr = document.createElement('tr');
      tr.dataset.actual = JSON.stringify(r.a);
      const actualSet = new Set(r.a);
      const pool    = r.p[mi];
      const combo   = topKNums(pool, r.p, curK);
      const matched = combo.filter(n=>actualSet.has(n)).length;
      const b1Hit   = combo.includes(r.b1);
      const b2Hit   = combo.includes(r.b2);
      const predSet = new Set(combo);
      let cells =
        '<td>'+r.s+'</td>' +
        '<td>'+(r.d ? r.d.slice(0,10) : '')+'</td>' +
        '<td><div class="balls">' +
        r.a.map(n=>'<span class="ball'+(predSet.has(n)?' match':'')+'">'+n+'</span>').join('') +
        '<span class="ball'+(b1Hit?' bonus':'')+'">'+r.b1+(b1Hit?'★':'')+'</span>' +
        '<span class="ball'+(b2Hit?' bonus':'')+'">'+r.b2+(b2Hit?'★':'')+'</span></div></td>' +
        '<td><div class="balls">' +
        combo.map(n=>'<span class="ball'+(actualSet.has(n)?' match':'')+'">'+n+'</span>').join('') +
        '</div></td>' +
        '<td style="text-align:center;font-weight:700;color:'+matchColor(matched)+'">'+matched+'</td>';
      tr.innerHTML = cells;
      body.appendChild(tr);
    }});
  }}
  applyFilter();
}}

function applyFilter() {{
  const filters = [1,2,3,4,5,6,7].map(i => {{
    const v = document.getElementById('f'+i).value.trim();
    return v==='' ? null : parseInt(v);
  }});
  const rows = Array.from(document.getElementById('detailBody').rows);
  let shown = 0;
  let total = 0;
  rows.forEach(tr => {{
    if (tr.classList.contains('upcoming-row')) {{
      tr.style.display = '';  // always visible -- no actual result to filter against
      return;
    }}
    total++;
    const actual = JSON.parse(tr.dataset.actual);
    const sorted = [...actual].sort((a,b)=>a-b);
    const ok = filters.every((f,i) => f===null||sorted[i]===f);
    tr.style.display = ok ? '' : 'none';
    if (ok) shown++;
  }});
  const active = filters.some(f=>f!==null);
  document.getElementById('filterCount').textContent = active ? shown+' / '+total+' draws' : '';
}}
function clearFilters() {{
  [1,2,3,4,5,6,7].forEach(i => document.getElementById('f'+i).value='');
  applyFilter();
}}

function switchTab(name, btn) {{
  document.querySelectorAll('.panel').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  document.getElementById('tab-'+name).classList.add('active');
  btn.classList.add('active');
  if (name==='detail' && builtModel===-999) buildDetail();
}}

setK(7);
</script>
</body>
</html>"""

with open(HTML_OUT, 'w', encoding='utf-8') as f:
    f.write(page)
print(f"Wrote {HTML_OUT} ({len(page)//1024} KB)")
