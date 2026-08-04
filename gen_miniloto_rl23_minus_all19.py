"""
gen_miniloto_rl23_minus_all19.py
-----------------------------------
Generates a static report page showing a two-stage elimination for
MiniLoto draw #1398:

  1. RL (Linear Q)'s K=23 prediction combinations, MINUS the union of all
     16 methods' K=19 prediction combinations -- i.e. combos RL's wider
     pick covers that none of the 16 methods' K=19 picks already cover.
  2. From that remaining set, further remove any combo that exactly
     matches a real historical MiniLoto winning combination (draws
     #521-1397) -- same elimination spirit as the Loto6 work earlier.

Reads: miniloto_rl23_minus_all19_data.json (precomputed, both stages)
Output: public/miniloto_rl23_minus_all19.html
Run: python gen_miniloto_rl23_minus_all19.py
"""
import json

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
DATA_PATH = BASE + r"\miniloto_rl23_minus_all19_data.json"
HTML_OUT = BASE + r"\public\miniloto_rl23_minus_all19.html"

with open(DATA_PATH, encoding='utf-8') as f:
    data = json.load(f)

draw_serial = data["drawSerial"]
rlq_pool23 = data["rlqPool23"]
rlq_count = data["rlqComboCount"]
union19_count = data["union19Count"]
remaining_before_hist = data["remainingBeforeHistFilter"]
historical_match_count = data["historicalMatchCount"]
remaining_count = data["remainingCount"]
remaining_pct = data["remainingPct"]
remaining = data["remaining"]  # list of [n1,n2,n3,n4,n5] sorted, after both elimination stages

remaining_json = json.dumps(remaining, separators=(',', ':'))

html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>MiniLoto — RL(Linear Q) K=23 minus All-16 K=19</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
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
  .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; margin-bottom: 20px; }}
  .card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 14px; }}
  .card-name {{ font-size: .72rem; color: var(--muted); text-transform: uppercase; letter-spacing: .05em; margin-bottom: 6px; }}
  .card-val {{ font-size: 1.5rem; font-weight: 700; color: var(--accent); }}
  .card-val .unit {{ font-size: .7rem; color: var(--muted); font-weight: 400; margin-left: 4px; }}
  .pool-wrap {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
                padding: 16px; margin-bottom: 20px; }}
  .pool-label {{ font-size: .72rem; color: var(--muted); text-transform: uppercase; letter-spacing: .05em; margin-bottom: 10px; }}
  .balls {{ display: flex; flex-wrap: wrap; gap: 5px; }}
  .ball {{ display: inline-flex; align-items: center; justify-content: center;
           width: 30px; height: 30px; border-radius: 50%; font-size: .78rem; font-weight: 700;
           background: var(--accent); color: #0f172a; flex-shrink: 0; }}
  .ctrl-row {{ display: flex; gap: 10px; flex-wrap: wrap; align-items: center; margin-bottom: 14px; }}
  .ctrl-row label {{ font-size: .8rem; color: var(--muted); }}
  .num-btn {{ display: inline-flex; align-items: center; justify-content: center;
              width: 30px; height: 30px; border-radius: 50%; font-size: .78rem; font-weight: 700;
              color: #fff; border: none; cursor: pointer; opacity: .7; transition: all .12s; flex-shrink: 0; }}
  .num-btn:hover {{ opacity: 1; }}
  .num-btn.active {{ opacity: 1; box-shadow: 0 0 0 2px #fff, 0 0 0 4px var(--accent); transform: scale(1.1); }}
  .btn {{ padding: 5px 12px; background: var(--surface); border: 1px solid var(--border);
          border-radius: 6px; color: var(--muted); font-size: .8rem; cursor: pointer; }}
  .btn:hover {{ color: var(--text); }}
  .btn:disabled {{ opacity: .4; cursor: default; }}
  .table-wrap {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 16px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: .85rem; }}
  th {{ text-align: left; padding: 8px 6px; border-bottom: 1px solid var(--border); color: var(--muted);
        text-transform: uppercase; font-size: .68rem; letter-spacing: .05em; }}
  td {{ padding: 6px; border-bottom: 1px solid var(--border); }}
  tr:hover td {{ background: rgba(255,255,255,.04); }}
  .page-info {{ font-size: .8rem; color: var(--muted); }}
</style>
</head>
<body>

<h1>MiniLoto — RL(Linear Q) K=23 minus All-16-Methods K=19</h1>
<p class="subtitle">Draw #{draw_serial} &middot; set difference between one method's wider pick and the combined coverage of all 16 methods</p>

<div class="note">
  Two-stage elimination. Stage 1: RL (Linear Q)'s pool was padded from its stored 15 candidates up
  to 23 (cross-method consensus, same mechanism as the backtest page's live K toggle). All 16
  methods' pools were separately padded to 19 and their C(19,5) combinations merged into one union
  set; combos in RL's 23-pick C(23,5) set that overlap that union were removed. Stage 2: from what's
  left, any combo that exactly matches a real historical MiniLoto winning combination (draws
  #521&ndash;1397, checked against all 877) was also removed &mdash; same elimination spirit as the
  Loto6 work earlier this session.
</div>

<div class="cards">
  <div class="card">
    <div class="card-name">RL(Linear Q) K=23 combos</div>
    <div class="card-val">{rlq_count:,}</div>
  </div>
  <div class="card">
    <div class="card-name">All-16 K=19 union</div>
    <div class="card-val">{union19_count:,}</div>
  </div>
  <div class="card">
    <div class="card-name">After stage 1 (minus union19)</div>
    <div class="card-val">{remaining_before_hist:,}</div>
  </div>
  <div class="card">
    <div class="card-name">Removed: matched a real historical draw</div>
    <div class="card-val">{historical_match_count:,}</div>
  </div>
  <div class="card">
    <div class="card-name">Final remaining</div>
    <div class="card-val">{remaining_count:,}</div>
  </div>
  <div class="card">
    <div class="card-name">% of RL's set retained</div>
    <div class="card-val">{remaining_pct}<span class="unit">%</span></div>
  </div>
</div>

<div class="pool-wrap">
  <div class="pool-label">RL (Linear Q) — 23-number pool used</div>
  <div class="balls">
'''
for n in rlq_pool23:
    html += f'    <div class="ball">{n}</div>\n'

html += f'''  </div>
</div>

<div class="table-wrap" style="margin-bottom:20px">
  <div class="pool-label" style="margin-bottom:10px">Contains number(s) &mdash; click to toggle, multiple selections use AND logic</div>
  <div class="balls" id="filterGrid">
'''
for n in rlq_pool23:
    html += f'    <button class="num-btn" data-n="{n}" onclick="toggleNum({n})">{n}</button>\n'

html += f'''  </div>
  <div class="ctrl-row" style="margin-top:12px;margin-bottom:0">
    <button class="btn" onclick="clearFilter()">Clear</button>
    <span id="filterInfo" class="page-info"></span>
  </div>
</div>

<div class="table-wrap">
  <div class="ctrl-row" style="justify-content:space-between;margin-bottom:10px">
    <span id="pageInfo" class="page-info"></span>
    <div style="display:flex;gap:6px">
      <button class="btn" id="firstBtn" onclick="goPage(0)">&laquo; First</button>
      <button class="btn" id="prevBtn" onclick="goPage(curPage-1)">&lsaquo; Prev</button>
      <button class="btn" id="nextBtn" onclick="goPage(curPage+1)">Next &rsaquo;</button>
      <button class="btn" id="lastBtn" onclick="goPage(totalPages()-1)">Last &raquo;</button>
    </div>
  </div>
  <table>
    <thead><tr><th>#</th><th>Combination</th></tr></thead>
    <tbody id="comboBody"></tbody>
  </table>
</div>

<script>
const REMAINING = {remaining_json};
const PAGE_SIZE = 100;
let curPage = 0;
let filtered = REMAINING;

function totalPages() {{
  return Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
}}

function render() {{
  const start = curPage * PAGE_SIZE;
  const pageRows = filtered.slice(start, start + PAGE_SIZE);
  const body = document.getElementById('comboBody');
  body.innerHTML = pageRows.map((c, i) => {{
    const balls = c.map(n => '<span class="ball" style="width:26px;height:26px;font-size:.72rem">'+n+'</span>').join('');
    return '<tr><td>'+(start+i+1)+'</td><td><div class="balls">'+balls+'</div></td></tr>';
  }}).join('');
  document.getElementById('pageInfo').textContent =
    filtered.length === 0 ? 'No combinations match' :
    'Showing '+(start+1)+'-'+Math.min(start+PAGE_SIZE, filtered.length)+' of '+filtered.length.toLocaleString()+' combinations (page '+(curPage+1)+' / '+totalPages()+')';
  document.getElementById('firstBtn').disabled = curPage === 0;
  document.getElementById('prevBtn').disabled = curPage === 0;
  document.getElementById('nextBtn').disabled = curPage >= totalPages()-1;
  document.getElementById('lastBtn').disabled = curPage >= totalPages()-1;
}}

function goPage(p) {{
  curPage = Math.max(0, Math.min(p, totalPages()-1));
  render();
}}

function getBallColor(n) {{
  if (n <= 7) return '#e74c3c';
  if (n <= 13) return '#e67e22';
  if (n <= 19) return '#2ecc71';
  if (n <= 25) return '#3498db';
  return '#9b59b6';
}}
document.querySelectorAll('#filterGrid .num-btn').forEach(btn => {{
  btn.style.background = getBallColor(parseInt(btn.dataset.n, 10));
}});

const selectedNums = new Set();
function toggleNum(n) {{
  if (selectedNums.has(n)) selectedNums.delete(n);
  else selectedNums.add(n);
  document.querySelector('#filterGrid .num-btn[data-n="'+n+'"]').classList.toggle('active', selectedNums.has(n));
  applyFilter();
}}

function applyFilter() {{
  filtered = selectedNums.size === 0
    ? REMAINING
    : REMAINING.filter(c => {{ for (const n of selectedNums) if (!c.includes(n)) return false; return true; }});
  document.getElementById('filterInfo').textContent = selectedNums.size === 0 ? '' :
    (filtered.length.toLocaleString()+' / '+REMAINING.length.toLocaleString()+' combos contain '+[...selectedNums].sort((a,b)=>a-b).join(', '));
  curPage = 0;
  render();
}}

function clearFilter() {{
  selectedNums.clear();
  document.querySelectorAll('#filterGrid .num-btn.active').forEach(b => b.classList.remove('active'));
  applyFilter();
}}

render();
</script>

</body>
</html>
'''

with open(HTML_OUT, 'w', encoding='utf-8') as f:
    f.write(html)
print(f"Wrote {HTML_OUT} ({len(html)//1024} KB)")
