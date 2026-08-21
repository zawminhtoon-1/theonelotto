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
</style>
</head>
<body>

<h1>🎯 Loto 7 — 100-Draw Multi-K Backtest</h1>
<p class="subtitle">Walk-forward evaluation &middot; Draws #{draw_lo}&ndash;#{draw_hi} &middot; {T} draws &middot; {N_METHODS} methods &middot; K = 7 / 9 / 13 / 17</p>

<div class="note">
  <p>Same architecture as <a href="/backtest.html" style="color:#7dd3fc">Loto6's backtest.html</a>: each method's native
  K=15 candidate pool is computed once per draw, walk-forward (trained on only draws strictly before each target &mdash;
  no lookahead; LSTM additionally trains online after each prediction). The K toggle below then derives K=7/9/13/17 views
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
  <button class="kbtn" data-k="7" onclick="setK(7)">K = 7</button>
  <button class="kbtn" data-k="9" onclick="setK(9)">K = 9</button>
  <button class="kbtn" data-k="13" onclick="setK(13)">K = 13</button>
  <button class="kbtn" data-k="17" onclick="setK(17)">K = 17</button>
</div>

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

<script>
const METHODS = {json.dumps(METHOD_NAMES)};
const COLORS  = {json.dumps(COLORS)};
const DATA    = {json.dumps(DATA, separators=(',', ':'))};
const LOTO7_MAX = {LOTO7_MAX};
const T = {T};

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

setK(7);
</script>
</body>
</html>"""

with open(HTML_OUT, 'w', encoding='utf-8') as f:
    f.write(page)
print(f"Wrote {HTML_OUT} ({len(page)//1024} KB)")
