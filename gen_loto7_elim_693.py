"""
gen_loto7_elim_693.py
--------------------------
Generates the Loto7 draw #693 elimination page's Base stage --
mirroring the Loto6 elimination-page pattern (e.g.
xoshiro_elim_2130.html): shows the Base pool, the universe count, and
a paginated/filterable/CSV-downloadable combo browser over all
C(25,7) combinations. No elimination passes yet, per explicit
instruction -- this establishes the Base only.

Reads loto7_elim_693_meta.json (small: base pool, counts). The large
combo list lives separately at public/loto7_elim_693_combos.json and
is fetched client-side, not inlined.

Output: public/loto7_elim_693.html
Run: python gen_loto7_elim_693.py
"""
import json

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
META_PATH = BASE + r"\loto7_elim_693_meta.json"
HTML_OUT = BASE + r"\public\loto7_elim_693.html"

with open(META_PATH, encoding='utf-8') as f:
    meta = json.load(f)

TARGET_SERIAL = meta['targetSerial']
base = meta['base']
universe_count = meta['universeCount']
method_names = meta['methodNames']
method_k = meta['methodK']
method_picks = meta['methodPicks']
removed_by_methods = meta['removedByMethods']
final_remaining_pass1 = meta['finalRemainingPass1']
pass1_pct = final_remaining_pass1 / universe_count * 100

pass2_method_names = meta['pass2MethodNames']
pass2_k = meta['pass2K']
pass2_picks = meta['pass2Picks']
removed_by_pass2 = meta['removedByPass2']
final_remaining_pass2 = meta['finalRemainingPass2']
pass2_pct = final_remaining_pass2 / universe_count * 100
pass2_pct_of_pass1 = final_remaining_pass2 / final_remaining_pass1 * 100

historical_draw_count = meta['historicalDrawCount']
removed_historical = meta['removedHistorical']
final_remaining = meta['finalRemaining']
final_pct = final_remaining / universe_count * 100
pass3_pct_of_pass2 = final_remaining / final_remaining_pass2 * 100

methods_rows_html = ""
for name, pool in zip(method_names, method_picks):
    balls = "".join(f'<span class="nb" style="width:26px;height:26px;font-size:.7rem">{n}</span>' for n in pool)
    methods_rows_html += f"""<tr><td class="mname">{name}</td><td><div class="balls">{balls}</div></td></tr>"""

pass2_rows_html = ""
for name, pool in zip(pass2_method_names, pass2_picks):
    balls = "".join(f'<span class="nb" style="width:26px;height:26px;font-size:.7rem">{n}</span>' for n in pool)
    pass2_rows_html += f"""<tr><td class="mname">{name}</td><td><div class="balls">{balls}</div></td></tr>"""

if removed_historical:
    pass3_rows_html = ""
    for combo in removed_historical:
        balls = "".join(f'<span class="nb" style="width:26px;height:26px;font-size:.7rem">{n}</span>' for n in combo)
        pass3_rows_html += f"""<tr><td><div class="balls">{balls}</div></td></tr>"""
else:
    pass3_rows_html = """<tr><td>None &mdash; no Pass-2-remaining combo matched a historical winning combo.</td></tr>"""

page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Loto 7 — Draw #{TARGET_SERIAL} Elimination</title>
<style>

*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0f172a;color:#f1f5f9;font-family:system-ui,sans-serif;padding:24px;min-height:100vh}}
.wrap{{max-width:1200px;margin:0 auto}}
h1{{font-size:1.4rem;font-weight:700;color:#f1f5f9;margin-bottom:4px}}
.subtitle{{font-size:.85rem;color:#94a3b8;margin-bottom:20px}}

.section{{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:20px;margin-bottom:20px}}
.section h2{{font-size:1rem;font-weight:700;color:#f1f5f9;margin-bottom:4px}}
.section .desc{{font-size:.8rem;color:#94a3b8;margin-bottom:14px}}

.balls{{display:flex;flex-wrap:wrap;gap:5px}}
.nb{{display:inline-flex;align-items:center;justify-content:center;width:30px;height:30px;
  border-radius:50%;font-size:.78rem;font-weight:700;background:#312e5f;color:#c4b5fd;
  border:1px solid #7c3aed55;flex-shrink:0}}

.stats-row{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px}}
.stat-card{{background:#0f172a;border:1px solid #334155;border-radius:10px;padding:14px 18px;flex:1;min-width:150px}}
.stat-card .lbl{{font-size:.7rem;color:#94a3b8;text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px}}
.stat-card .val{{font-size:1.35rem;font-weight:700;color:#f1f5f9}}
.stat-card .sub{{font-size:.75rem;color:#94a3b8;margin-top:2px}}
.stat-card.final .val{{color:#38bdf8}}

.note{{background:#0f172a;border:1px solid #334155;border-radius:10px;padding:14px 18px;
  font-size:.8rem;color:#94a3b8;margin-bottom:20px;line-height:1.6}}
.note p+p{{margin-top:8px}}
.note code{{background:#0a0f1e;padding:1px 5px;border-radius:4px;font-size:.85em}}

.elim-flow{{font-size:1rem;color:#e2e8f0;text-align:center;padding:16px;background:#0f172a;
  border:1px solid #334155;border-radius:10px;font-weight:600;letter-spacing:.02em;margin-top:16px}}
.elim-flow .arrow{{color:#94a3b8;margin:0 10px}}
.elim-flow .n{{color:#f1f5f9}}
.elim-flow .final{{color:#38bdf8}}

details{{background:#0f172a;border:1px solid #334155;border-radius:10px;padding:12px 16px}}
summary{{cursor:pointer;font-size:.85rem;font-weight:600;color:#e2e8f0;user-select:none}}
summary:hover{{color:#f1f5f9}}
.methods-table{{width:100%;border-collapse:collapse;font-size:.82rem;margin-top:12px}}
.methods-table td{{padding:7px 10px;border-bottom:1px solid #334155;vertical-align:middle}}
.methods-table td.mname{{color:#94a3b8;white-space:nowrap;font-weight:600;width:160px}}

.lookup{{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:14px}}
.lookup .btn{{padding:6px 14px;background:#0f172a;border:1px solid #334155;border-radius:7px;
  color:#94a3b8;font-size:.8rem;cursor:pointer}}
.lookup .btn:hover{{color:#f1f5f9}}
.lookup .btn.primary{{background:#7c3aed;border-color:#7c3aed;color:#fff}}
.lookup .btn.primary:hover{{background:#6d28d9}}
.lookup .btn:disabled{{opacity:.4;cursor:default}}
.filter-grid{{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:10px}}
.num-btn{{display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;
  border-radius:50%;font-size:.72rem;font-weight:700;color:#fff;background:#312e5f;
  border:none;cursor:pointer;opacity:.65;transition:all .12s;flex-shrink:0}}
.num-btn:hover{{opacity:.9}}
.num-btn.active{{opacity:1;box-shadow:0 0 0 2px #0f172a,0 0 0 4px #38bdf8;transform:scale(1.08)}}
.page-info{{font-size:.8rem;color:#94a3b8}}
.tbl-wrap{{overflow-x:auto;border-radius:10px;border:1px solid #334155}}
table.combos{{width:100%;border-collapse:collapse;font-size:.83rem}}
table.combos th{{background:#0f172a;padding:8px 12px;text-align:left;color:#94a3b8;
  font-weight:600;font-size:.7rem;text-transform:uppercase;letter-spacing:.05em;
  border-bottom:1px solid #334155}}
table.combos td{{padding:6px 12px;border-bottom:1px solid #0f172a}}
table.combos tr:hover td{{background:#111827}}
#loadingMsg{{padding:30px;text-align:center;color:#94a3b8;font-size:.85rem}}

.footer{{margin-top:28px;font-size:.78rem;color:#64748b;padding-bottom:20px;line-height:1.6}}
</style>
</head>
<body>

<div class="wrap">
  <h1>✂️ Loto 7 — Draw #{TARGET_SERIAL} Elimination</h1>
  <p class="subtitle">Base = ARIMA(2,1,0)'s K={base['k']} prediction pool for draw #{TARGET_SERIAL} &mdash; Pass 1 = 16 methods' K={method_k} picks &mdash; Pass 2 = 4 methods' K={pass2_k} picks &mdash; Pass 3 = historical repeat filter</p>

  <div class="note">
    <p>Base is <strong style="color:#f1f5f9">ARIMA(2,1,0)'s K={base['k']} pick</strong> for draw #{TARGET_SERIAL} (not yet drawn) &mdash;
    read from <a href="/loto7/predictions" style="color:#a78bfa">the live /loto7/predictions page</a>'s data (ARIMA's native
    K={base['nativeK']} pool, normalized to K={base['k']} via <code>topKNums()</code>, the same generic cross-method-consensus
    trim/pad function used throughout this site &mdash; the same method that made ARIMA the top-ranked method at K=25 on
    <a href="/loto7_backtest100_multik.html" style="color:#a78bfa">the 100-draw multi-K backtest</a>). This defines the working
    universe: all C({base['k']},7) = {universe_count:,} seven-number combinations drawable from this {base['k']}-number pool.</p>
    <p><strong style="color:#f1f5f9">Pass 1</strong> is each of the 16 prediction methods' K={method_k} pick for draw
    #{TARGET_SERIAL} (native K=15 pool normalized to K={method_k} via the same <code>topKNums()</code>), checked
    <strong>independently</strong> &mdash; NOT a union of raw numbers. Any Base combo fully contained within ANY single
    one of these 16 K={method_k} sets gets removed &mdash; same per-method containment pattern used on the Loto6
    elimination pages (e.g. <a href="/xoshiro_elim_2130.html" style="color:#a78bfa">xoshiro_elim_2130.html</a>'s Pass 1),
    leaving {final_remaining_pass1:,}.</p>
    <p><strong style="color:#f1f5f9">Pass 2</strong> is {len(pass2_method_names)} specific methods' K={pass2_k} pick for draw
    #{TARGET_SERIAL} &mdash; {', '.join(pass2_method_names)} &mdash; checked <strong>independently</strong>, same as Pass 1
    (not a union). Any Pass-1-remaining combo fully contained within ANY single one of these {len(pass2_method_names)}
    K={pass2_k} sets gets removed, leaving {final_remaining_pass2:,}.</p>
    <p><strong style="color:#f1f5f9">Pass 3 (final)</strong> is a historical repeat filter, same "zero repeats in history"
    pattern used on the Loto6 elimination pages. Any Pass-2-remaining combo that exactly matches one of Loto7's
    {historical_draw_count:,} historical actual winning combos (draws #1&ndash;{TARGET_SERIAL-1}, main 7 numbers only,
    bonus ignored) gets removed, leaving {final_remaining:,}.</p>
  </div>

  <div class="section">
    <h2>Base — ARIMA(2,1,0) K={base['k']}</h2>
    <p class="desc">Native K={base['nativeK']} pick normalized to K={base['k']} via cross-method-consensus trim/pad.</p>
    <div class="balls">{"".join(f'<span class="nb">{n}</span>' for n in base['pool'])}</div>
  </div>

  <div class="section">
    <h2>Pass 1 — 16 prediction methods, K={method_k} pick for draw #{TARGET_SERIAL}</h2>
    <p class="desc">Each method's native K=15 pool normalized to K={method_k}, checked independently against the Base pool.</p>
    <details>
      <summary>Show all 16 methods' K={method_k} picks</summary>
      <table class="methods-table">
        <tbody>{methods_rows_html}</tbody>
      </table>
    </details>
  </div>

  <div class="section">
    <h2>Pass 2 — {len(pass2_method_names)} methods, K={pass2_k} pick for draw #{TARGET_SERIAL}</h2>
    <p class="desc">{', '.join(pass2_method_names)} &mdash; native K=15 pools normalized to K={pass2_k}, checked independently against what's left after Pass 1.</p>
    <table class="methods-table">
      <tbody>{pass2_rows_html}</tbody>
    </table>
  </div>

  <div class="section">
    <h2>Pass 3 (final) — historical repeat filter</h2>
    <p class="desc">Any Pass-2-remaining combo that exactly matches one of Loto7's {historical_draw_count:,} historical actual winning combos (draws #1&ndash;{TARGET_SERIAL-1}, main 7 numbers only, bonus ignored) is removed. {len(removed_historical)} matched.</p>
    <table class="methods-table">
      <tbody>{pass3_rows_html}</tbody>
    </table>
  </div>

  <div class="section">
    <h2>Elimination summary</h2>
    <div class="stats-row">
      <div class="stat-card">
        <div class="lbl">Universe (Base)</div>
        <div class="val">{universe_count:,}</div>
        <div class="sub">C({base['k']},7)</div>
      </div>
      <div class="stat-card">
        <div class="lbl">Removed by 16 methods (Pass 1)</div>
        <div class="val">{removed_by_methods:,}</div>
        <div class="sub">contained in ANY method's K={method_k}</div>
      </div>
      <div class="stat-card">
        <div class="lbl">After Pass 1</div>
        <div class="val">{final_remaining_pass1:,}</div>
        <div class="sub">{pass1_pct:.1f}% of universe retained</div>
      </div>
      <div class="stat-card">
        <div class="lbl">Removed by {len(pass2_method_names)} methods (Pass 2)</div>
        <div class="val">{removed_by_pass2:,}</div>
        <div class="sub">contained in ANY method's K={pass2_k}</div>
      </div>
      <div class="stat-card">
        <div class="lbl">After Pass 2</div>
        <div class="val">{final_remaining_pass2:,}</div>
        <div class="sub">{pass2_pct:.1f}% of universe &middot; {pass2_pct_of_pass1:.1f}% of Pass-1 output</div>
      </div>
      <div class="stat-card">
        <div class="lbl">Removed by historical filter (Pass 3)</div>
        <div class="val">{len(removed_historical):,}</div>
        <div class="sub">exact match to a real drawn combo</div>
      </div>
      <div class="stat-card final">
        <div class="lbl">Final remaining</div>
        <div class="val">{final_remaining:,}</div>
        <div class="sub">{final_pct:.1f}% of universe &middot; {pass3_pct_of_pass2:.1f}% of Pass-2 output</div>
      </div>
    </div>
    <div class="elim-flow">
      <span class="n">{universe_count:,}</span>
      <span class="arrow">&rarr;</span>
      <span class="n">{final_remaining_pass1:,}</span> <span style="color:#94a3b8;font-size:.7rem">(Pass 1)</span>
      <span class="arrow">&rarr;</span>
      <span class="n">{final_remaining_pass2:,}</span> <span style="color:#94a3b8;font-size:.7rem">(Pass 2)</span>
      <span class="arrow">&rarr;</span>
      <span class="n final">{final_remaining:,}</span> <span style="color:#94a3b8;font-size:.7rem">(Pass 3)</span>
    </div>
  </div>

  <div class="section">
    <h2>Browse remaining combinations</h2>
    <p class="desc">Fetched from a separate JSON asset (not inlined — {final_remaining:,} rows is too large for the page itself).</p>
    <div id="loadingMsg">Loading {final_remaining:,} combinations…</div>
    <div id="comboUI" style="display:none">
      <div class="lookup">
        <button class="btn" onclick="clearFilter()">Clear filter</button>
        <button class="btn primary" onclick="downloadCSV()">⬇ Download CSV</button>
        <span id="filterInfo" class="page-info"></span>
      </div>
      <div class="filter-grid" id="filterGrid"></div>
      <div class="tbl-wrap">
        <div class="lookup" style="justify-content:space-between;padding:10px 12px;margin-bottom:0">
          <span id="pageInfo" class="page-info"></span>
          <div style="display:flex;gap:6px">
            <button class="btn" id="firstBtn" onclick="goPage(0)">&laquo; First</button>
            <button class="btn" id="prevBtn" onclick="goPage(curPage-1)">&lsaquo; Prev</button>
            <button class="btn" id="nextBtn" onclick="goPage(curPage+1)">Next &rsaquo;</button>
            <button class="btn" id="lastBtn" onclick="goPage(totalPages()-1)">Last &raquo;</button>
          </div>
        </div>
        <table class="combos">
          <thead><tr><th>#</th><th>Combination</th></tr></thead>
          <tbody id="comboBody"></tbody>
        </table>
      </div>
    </div>
  </div>

  <p class="footer">
    Base = ARIMA(2,1,0)'s K={base['k']} pick, normalized via <code>topKNums()</code> (cross-method-consensus trim/pad,
    same function used throughout this site). Universe = all C({base['k']},7) combinations drawable from that pool.
    Pass 1 removes any combo fully contained within ANY single one of the 16 methods' K={method_k} picks, checked
    independently, leaving {final_remaining_pass1:,}. Pass 2 then removes any of those fully contained within ANY
    single one of {len(pass2_method_names)} methods' K={pass2_k} picks ({', '.join(pass2_method_names)}), also
    checked independently, leaving {final_remaining_pass2:,}. Pass 3 (final) removes any of those that exactly
    matches one of Loto7's {historical_draw_count:,} historical actual winning combos (draws #1&ndash;{TARGET_SERIAL-1}),
    leaving {final_remaining:,}.<br>
    16 methods: Poly Regression, Moving Avg-37, Exp-Weighted Avg, Frequency, Markov Chain, ARIMA(2,1,0), Random Forest,
    RL (Linear Q), HMM, k-NN, Modular Cycle, Apriori, Monte Carlo, Naive Bayes, Weighted MA-37, LSTM — same 16 used
    throughout <a href="/loto7_backtest.html" style="color:#64748b">loto7_backtest.html</a> /
    <a href="/loto7/predictions" style="color:#64748b">predictions</a>.<br>
    Formula-based only · Not financial advice · Loto 7 is random.
  </p>
</div>

<script>
const POOL_BASE = {json.dumps(base['pool'])};
let REMAINING = [];
let filtered = [];
const PAGE_SIZE = 100;
let curPage = 0;
const selectedNums = new Set();

fetch('/loto7_elim_{TARGET_SERIAL}_combos.json')
  .then(r => r.json())
  .then(data => {{
    REMAINING = data;
    filtered = REMAINING;
    document.getElementById('loadingMsg').style.display = 'none';
    document.getElementById('comboUI').style.display = 'block';
    buildFilterGrid();
    render();
  }})
  .catch(err => {{
    document.getElementById('loadingMsg').textContent = 'Failed to load combinations: ' + err;
  }});

function getBallColor(n) {{
  if (n <= 6) return '#e74c3c';
  if (n <= 11) return '#e67e22';
  if (n <= 16) return '#2ecc71';
  if (n <= 21) return '#3498db';
  if (n <= 26) return '#9b59b6';
  if (n <= 31) return '#16a085';
  return '#e91e8c';
}}
function buildFilterGrid() {{
  const grid = document.getElementById('filterGrid');
  grid.innerHTML = POOL_BASE.map(n =>
    '<button class="num-btn" data-n="' + n + '" style="background:' + getBallColor(n) + '" onclick="toggleNum(' + n + ')">' + n + '</button>'
  ).join('');
}}
function toggleNum(n) {{
  if (selectedNums.has(n)) selectedNums.delete(n); else selectedNums.add(n);
  document.querySelector('.num-btn[data-n="' + n + '"]').classList.toggle('active', selectedNums.has(n));
  applyFilter();
}}
function clearFilter() {{
  selectedNums.clear();
  document.querySelectorAll('.num-btn.active').forEach(b => b.classList.remove('active'));
  applyFilter();
}}
function applyFilter() {{
  filtered = selectedNums.size === 0 ? REMAINING : REMAINING.filter(c => {{
    for (const n of selectedNums) if (!c.includes(n)) return false;
    return true;
  }});
  document.getElementById('filterInfo').textContent = selectedNums.size === 0 ? '' :
    (filtered.length.toLocaleString() + ' / ' + REMAINING.length.toLocaleString() + ' combos contain ' + [...selectedNums].sort((a,b)=>a-b).join(', '));
  curPage = 0;
  render();
}}
function totalPages() {{ return Math.max(1, Math.ceil(filtered.length / PAGE_SIZE)); }}
function goPage(p) {{ curPage = Math.max(0, Math.min(p, totalPages()-1)); render(); }}
function render() {{
  const start = curPage * PAGE_SIZE;
  const pageRows = filtered.slice(start, start + PAGE_SIZE);
  document.getElementById('comboBody').innerHTML = pageRows.map((c, i) => {{
    const balls = c.map(n => '<span class="nb" style="width:26px;height:26px;font-size:.72rem;background:' + getBallColor(n) + '33;color:#e2e8f0;border:1px solid ' + getBallColor(n) + '">' + n + '</span>').join('');
    return '<tr><td>' + (start+i+1) + '</td><td><div class="balls">' + balls + '</div></td></tr>';
  }}).join('');
  document.getElementById('pageInfo').textContent =
    filtered.length === 0 ? 'No combinations match' :
    'Showing ' + (start+1) + '-' + Math.min(start+PAGE_SIZE, filtered.length) + ' of ' + filtered.length.toLocaleString() + ' (page ' + (curPage+1) + ' / ' + totalPages() + ')';
  document.getElementById('firstBtn').disabled = curPage === 0;
  document.getElementById('prevBtn').disabled = curPage === 0;
  document.getElementById('nextBtn').disabled = curPage >= totalPages()-1;
  document.getElementById('lastBtn').disabled = curPage >= totalPages()-1;
}}
function downloadCSV() {{
  const rows = filtered.length > 0 ? filtered : REMAINING;
  let csv = 'n1,n2,n3,n4,n5,n6,n7\\n' + rows.map(c => c.join(',')).join('\\n');
  const blob = new Blob([csv], {{type: 'text/csv'}});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'loto7_draw_{TARGET_SERIAL}_remaining_combos.csv';
  a.click();
  URL.revokeObjectURL(url);
}}
</script>
</body>
</html>"""

with open(HTML_OUT, 'w', encoding='utf-8') as f:
    f.write(page)
print(f"Wrote {HTML_OUT} ({len(page)//1024} KB)")
