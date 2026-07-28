"""
gen_random_seed_backtest.py
---------------------------
For each seed 1-100, generate 15 random picks (seeded RNG) for each of
the last 1000 draws in backtest.html, compare against actual results.
Output: public/random_seed_backtest.html — sortable table ranking all 100 seeds.
"""
import json, re, random, math
from collections import defaultdict

BASE      = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
HTML_IN   = BASE + r"\public\backtest.html"
HTML_OUT  = BASE + r"\public\random_seed_backtest.html"
K_PICKS   = 15
N_DRAWS   = 1000   # last N draws from DATA
SEEDS     = range(1, 101)
LOTO6_MAX = 43

# ── Load backtest DATA ─────────────────────────────────────────────────────────
with open(HTML_IN, encoding='utf-8') as f:
    html = f.read()

m = re.search(r'const DATA\s*=\s*(\[)', html)
bs = m.start(1)
depth = 0; pos = bs
while pos < len(html):
    if html[pos] == '[': depth += 1
    elif html[pos] == ']':
        depth -= 1
        if depth == 0: be = pos + 1; break
    pos += 1
ALL_DATA = json.loads(html[bs:be])

# Use last N_DRAWS entries
DATA = ALL_DATA[-N_DRAWS:]
print(f"Loaded {len(ALL_DATA)} total entries. Using last {len(DATA)}: draws {DATA[0]['s']}-{DATA[-1]['s']}")

# ── Random prediction function ─────────────────────────────────────────────────
def random_predict(seed, draw_serial, k=K_PICKS):
    rng = random.Random(seed * 10_000_000 + draw_serial)
    return sorted(rng.sample(range(1, LOTO6_MAX + 1), k))

# ── Evaluate each seed ─────────────────────────────────────────────────────────
# Expected hits by pure chance: k * 6 / 43
BASELINE = K_PICKS * 6 / LOTO6_MAX

results = []
for seed in SEEDS:
    total_hits = 0
    bonus_hits = 0
    dist = [0] * 7   # dist[n] = draws with exactly n hits
    for row in DATA:
        actual  = set(row['a'])
        bonus   = row['b']
        picks   = random_predict(seed, row['s'])
        h       = len(actual & set(picks))
        bh      = bonus in picks
        total_hits  += h
        bonus_hits  += int(bh)
        dist[h]     += 1
    n      = len(DATA)
    avg    = total_hits / n
    lift   = (avg / BASELINE - 1) * 100   # % above/below random baseline
    results.append({
        'seed':   seed,
        'avg':    round(avg, 4),
        'lift':   round(lift, 2),
        'dist':   dist,
        'bonus':  bonus_hits,
        'hit6':   dist[6],
        'hit5':   dist[5],
        'hit4':   dist[4],
        'hit0':   dist[0],
    })
    if seed % 10 == 0:
        print(f"  Seed {seed:3d}: avg={avg:.4f} lift={lift:+.1f}% 6hits={dist[6]} 5hits={dist[5]}")

results.sort(key=lambda r: (-r['avg'], r['seed']))
best   = results[0]
worst  = results[-1]
print(f"\nBest  seed {best['seed']:3d}: avg={best['avg']:.4f} lift={best['lift']:+.1f}% 6hits={best['hit6']}")
print(f"Worst seed {worst['seed']:3d}: avg={worst['avg']:.4f} lift={worst['lift']:+.1f}% 6hits={worst['hit6']}")
print(f"Baseline avg (pure random): {BASELINE:.4f}")

# ── Build HTML ─────────────────────────────────────────────────────────────────
rows_html = ""
for rank, r in enumerate(results, 1):
    is_best  = r['seed'] == best['seed']
    dist_str = " / ".join(str(r['dist'][i]) for i in range(6, -1, -1))
    lift_color = "#22c55e" if r['lift'] > 0 else "#ef4444"
    best_badge = ' <span style="background:#fef08a;color:#713f12;font-size:10px;padding:2px 6px;border-radius:4px;margin-left:4px;">BEST</span>' if is_best else ''
    rows_html += f"""<tr class="dr" onclick="selSeed({r['seed']})">
  <td class="tc">{rank}</td>
  <td class="tc">{r['seed']}{best_badge}</td>
  <td class="tr">{r['avg']:.4f}</td>
  <td class="tr" style="color:{lift_color}">{r['lift']:+.1f}%</td>
  <td class="tr">{r['hit6']}</td>
  <td class="tr">{r['hit5']}</td>
  <td class="tr">{r['hit4']}</td>
  <td class="tr">{r['hit0']}</td>
  <td class="tr">{r['bonus']}</td>
</tr>"""

# Build JS data
js_data = json.dumps(results, separators=(',', ':'))
js_draws = json.dumps([{'s':r['s'],'d':r['d'],'a':r['a'],'b':r['b']} for r in DATA], separators=(',',':'))

# Current best-seed picks for next draw
# We don't know next serial, but we can show what draw 2122/2123 best-seed predictions were
best_seed_rows = ""
for row in DATA[-5:]:
    picks = random_predict(best['seed'], row['s'])
    h = len(set(row['a']) & set(picks))
    bh = row['b'] in picks
    bonus_txt = " +B" if bh else ""
    best_seed_rows += f"<tr><td>{row['s']}</td><td>{row['d']}</td><td>{', '.join(map(str,row['a']))} <small>b={row['b']}</small></td>"
    best_seed_rows += f"<td>{', '.join(map(str,picks))}</td><td class='tc'>{h}{bonus_txt}</td></tr>"

# Predict for next draw (approximate serial = last + 1)
next_serial = DATA[-1]['s'] + 1
next_picks = random_predict(best['seed'], next_serial)

page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Random Seed Backtest — Loto 6</title>
<style>
/* ====== SHARED FIXED NAV (dropdown) ====== */
.site-nav{{position:fixed;top:0;left:0;right:0;height:52px;background:#0a0f1e;
  border-bottom:1px solid #1e293b;display:flex;align-items:center;padding:0 20px;
  gap:0;z-index:9999;box-shadow:0 2px 16px rgba(0,0,0,.6)}}
.site-nav .nav-logo{{font-size:1rem;font-weight:800;color:#f1f5f9;text-decoration:none;
  white-space:nowrap;margin-right:24px;flex-shrink:0;letter-spacing:-.01em}}
.site-nav .nav-logo span{{color:#38bdf8}}
.nav-groups{{display:flex;gap:4px;align-items:center}}
.nav-group{{position:relative}}
.nav-group-btn{{display:flex;align-items:center;gap:5px;padding:7px 14px;border-radius:7px;
  cursor:pointer;font-size:.82rem;font-weight:600;color:#94a3b8;
  border:1px solid transparent;transition:.15s;white-space:nowrap;user-select:none}}
.nav-group-btn:hover,.nav-group:hover .nav-group-btn{{color:#f1f5f9;background:#1e293b;border-color:#334155}}
.nav-group-btn .arrow{{font-size:.6rem;opacity:.6;transition:transform .2s}}
.nav-group:hover .nav-group-btn .arrow{{transform:rotate(180deg)}}
.nav-dropdown{{display:none;position:absolute;top:100%;left:0;
  background:transparent;padding-top:6px;z-index:10000;min-width:170px}}
.nav-dropdown-inner{{background:#0d1526;border:1px solid #1e293b;border-radius:10px;
  padding:6px;box-shadow:0 12px 32px rgba(0,0,0,.7);max-height:70vh;overflow-y:auto}}
.nav-group:hover .nav-dropdown{{display:block}}
.nav-dropdown a{{display:flex;align-items:center;gap:8px;padding:8px 12px;
  border-radius:6px;color:#94a3b8;text-decoration:none;font-size:.82rem;
  white-space:nowrap;transition:.12s}}
.nav-dropdown a:hover{{color:#f1f5f9;background:#1e293b}}
.nav-dropdown a.active{{color:#38bdf8;background:#0c2340}}
.nav-dd-label{{font-size:.68rem;font-weight:700;color:#475569;padding:6px 12px 2px;
  text-transform:uppercase;letter-spacing:.06em}}
.nav-divider{{height:1px;background:#1e293b;margin:4px 0}}
/* ========================================= */

*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0a0f1e;color:#e2e8f0;font-family:system-ui,sans-serif;padding-top:60px;min-height:100vh}}
.wrap{{max-width:1100px;margin:0 auto;padding:24px 16px}}
h1{{font-size:1.4rem;font-weight:700;color:#f1f5f9;margin-bottom:4px}}
.subtitle{{font-size:.85rem;color:#64748b;margin-bottom:20px}}

.stats-row{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:24px}}
.stat-card{{background:#0d1526;border:1px solid #1e293b;border-radius:10px;padding:14px 18px;flex:1;min-width:140px}}
.stat-card .lbl{{font-size:.72rem;color:#64748b;text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px}}
.stat-card .val{{font-size:1.5rem;font-weight:700;color:#f1f5f9}}
.stat-card .sub{{font-size:.78rem;color:#94a3b8;margin-top:2px}}

.controls{{display:flex;gap:10px;align-items:center;margin-bottom:14px;flex-wrap:wrap}}
.controls input{{background:#0d1526;border:1px solid #334155;border-radius:7px;padding:7px 12px;
  color:#e2e8f0;font-size:.83rem;width:200px}}
.controls select{{background:#0d1526;border:1px solid #334155;border-radius:7px;padding:7px 12px;
  color:#e2e8f0;font-size:.83rem}}

.tbl-wrap{{overflow-x:auto;border-radius:10px;border:1px solid #1e293b}}
table{{width:100%;border-collapse:collapse;font-size:.83rem}}
thead th{{background:#0d1526;padding:10px 14px;text-align:right;color:#94a3b8;
  font-weight:600;font-size:.75rem;text-transform:uppercase;letter-spacing:.05em;
  cursor:pointer;user-select:none;white-space:nowrap;border-bottom:1px solid #1e293b}}
thead th:hover{{color:#f1f5f9}}
thead th.tc{{text-align:center}}
tbody tr{{border-bottom:1px solid #1e293b;cursor:pointer;transition:.12s}}
tbody tr:hover{{background:#111827}}
tbody tr.selected{{background:#0c2340 !important;outline:1px solid #38bdf8}}
tbody td{{padding:9px 14px;text-align:right;color:#cbd5e1}}
tbody td.tc{{text-align:center}}
tbody td.tr{{text-align:right}}
.rank1 td{{color:#fbbf24}}

.detail{{background:#0d1526;border:1px solid #1e293b;border-radius:10px;padding:18px;margin-top:24px;display:none}}
.detail h2{{font-size:1rem;font-weight:600;color:#f1f5f9;margin-bottom:12px}}
.detail table{{font-size:.8rem}}
.detail thead th{{font-size:.72rem}}

.next-pred{{background:#0d1526;border:1px solid #f59e0b55;border-radius:10px;padding:16px 18px;margin-top:16px}}
.next-pred .lbl{{font-size:.72rem;color:#f59e0b;text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px}}
.balls{{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}}
.ball{{width:34px;height:34px;border-radius:50%;background:#1e3a5f;display:flex;align-items:center;
  justify-content:center;font-weight:700;font-size:.85rem;color:#93c5fd;border:1px solid #2563eb55}}

.footer{{margin-top:28px;font-size:.78rem;color:#475569;padding-bottom:20px}}
</style>
</head>
<body>

<nav class="site-nav">
  <a class="nav-logo" href="/">🎱 The<span>One</span>Lotto</a>
  <div class="nav-groups">
    <div class="nav-group">
      <div class="nav-group-btn">Data <span class="arrow">▼</span></div>
      <div class="nav-dropdown"><div class="nav-dropdown-inner">
        <div class="nav-dd-label">Results</div>
        <a href="/">🏠 Latest Draw</a>
        <a href="/history">📋 History</a>
        <a href="/numbers">🔢 Numbers</a>
      </div></div>
    </div>
    <div class="nav-group">
      <div class="nav-group-btn">Predict <span class="arrow">▼</span></div>
      <div class="nav-dropdown"><div class="nav-dropdown-inner">
        <div class="nav-dd-label">Prediction Tools</div>
        <a href="/predictions">🎯 Predictions</a>
        <a href="/backtest.html">📊 Backtest</a>
        <a href="/combo_evo.html">🧬 Combo Evo</a>
        <div class="nav-divider"></div>
        <div class="nav-dd-label">Strategy</div>
        <a href="/overdue.html">⏳ Overdue</a>
        <a href="/state_machine.html">🔄 State Machine</a>
        <a href="/modular_cycle.html">🔁 Modular Cycle</a>
        <a href="/next_relation.html">🔗 Next Relation</a>
        <a href="/lstm_predict.html">🧠 LSTM Neural Net</a>
        <div class="nav-divider"></div>
        <div class="nav-dd-label">N-Draw Avg</div>
        <a href="/custom_avg.html">➕ 2-Draw Avg</a>
        <a href="/custom_avg3.html">➕ 3-Draw Avg</a>
        <a href="/avg_hub.html">⬡ All N-Draw Avg (2–43)</a>
        <div class="nav-divider"></div>
        <div class="nav-dd-label">N-Draw Avg Shift</div>
        <a href="/avg_shift_hub.html">⇄ All N-Shift Avg (2–43)</a>
        <div class="nav-divider"></div>
        <div class="nav-dd-label">Random Seed</div>
        <a href="/random_seed_backtest.html" class="active">🎲 Random Seed (1–100)</a>
      </div></div>
    </div>
    <div class="nav-group">
      <div class="nav-group-btn">Analyze <span class="arrow">▼</span></div>
      <div class="nav-dropdown"><div class="nav-dropdown-inner">
        <div class="nav-dd-label">Pattern Analysis</div>
        <a href="/special.html">⭐ Special</a>
        <a href="/consecutive.html">🔗 Consecutive</a>
        <div class="nav-divider"></div>
        <div class="nav-dd-label">Position</div>
        <a href="/position.html">📍 Position Freq</a>
        <a href="/pos_predict.html">📊 Pos 1–6 Predict</a>
      </div></div>
    </div>
  </div>
</nav>

<div class="wrap">
  <h1>🎲 Random Seed Backtest</h1>
  <p class="subtitle">Seeds 1–100 · {K_PICKS} picks · last {N_DRAWS} draws ({DATA[0]['s']}–{DATA[-1]['s']}) · random baseline ≈ {BASELINE:.3f} avg hits</p>

  <div class="stats-row">
    <div class="stat-card">
      <div class="lbl">Best seed</div>
      <div class="val">#{best['seed']}</div>
      <div class="sub">avg {best['avg']:.4f} hits · {best['lift']:+.1f}% vs baseline</div>
    </div>
    <div class="stat-card">
      <div class="lbl">Best 6-hit draws</div>
      <div class="val">{max(r['hit6'] for r in results)}</div>
      <div class="sub">seed #{sorted(results, key=lambda r: -r['hit6'])[0]['seed']}</div>
    </div>
    <div class="stat-card">
      <div class="lbl">Baseline (pure chance)</div>
      <div class="val">{BASELINE:.3f}</div>
      <div class="sub">{K_PICKS} picks × 6 / 43</div>
    </div>
    <div class="stat-card">
      <div class="lbl">Draws evaluated</div>
      <div class="val">{N_DRAWS}</div>
      <div class="sub">serials {DATA[0]['s']}–{DATA[-1]['s']}</div>
    </div>
  </div>

  <!-- Next-draw prediction from best seed -->
  <div class="next-pred">
    <div class="lbl">🏆 Best seed #{best['seed']} — predicted picks for draw #{next_serial}</div>
    <div class="balls">
      {''.join(f'<div class="ball">{n}</div>' for n in next_picks)}
    </div>
  </div>

  <div class="controls" style="margin-top:20px">
    <input id="filterInput" placeholder="Filter by seed number..." oninput="filterTable()">
    <select id="sortSel" onchange="sortTable(this.value)">
      <option value="rank">Sort: Rank (avg hits)</option>
      <option value="seed">Sort: Seed</option>
      <option value="hit6">Sort: 6-hit draws</option>
      <option value="hit5">Sort: 5-hit draws</option>
      <option value="hit4">Sort: 4-hit draws</option>
      <option value="hit0">Sort: 0-hit draws ↑</option>
      <option value="lift">Sort: Lift %</option>
    </select>
  </div>

  <div class="tbl-wrap">
    <table id="mainTable">
      <thead>
        <tr>
          <th class="tc" onclick="sortTable('rank')">#</th>
          <th class="tc" onclick="sortTable('seed')">Seed</th>
          <th onclick="sortTable('rank')">Avg hits ▼</th>
          <th onclick="sortTable('lift')">Lift %</th>
          <th onclick="sortTable('hit6')">6-hits</th>
          <th onclick="sortTable('hit5')">5-hits</th>
          <th onclick="sortTable('hit4')">4-hits</th>
          <th onclick="sortTable('hit0')">0-hits ↑</th>
          <th onclick="sortTable('bonus')">Bonus hits</th>
        </tr>
      </thead>
      <tbody id="tbody">
{rows_html}
      </tbody>
    </table>
  </div>

  <!-- Per-seed detail (last 5 draws) -->
  <div class="detail" id="detail">
    <h2 id="detailTitle">Seed detail</h2>
    <table>
      <thead><tr>
        <th class="tc">Draw</th><th>Date</th><th>Actual</th>
        <th>Picks (seed)</th><th class="tc">Hits</th>
      </tr></thead>
      <tbody id="detailTbody"></tbody>
    </table>
  </div>

  <p class="footer">
    Seeded random: picks = random.sample(range(1,44), 15) with seed = k×10⁷ + draw_serial.<br>
    Each (seed, draw) pair is independent and deterministic. Lift = % above pure-chance baseline ({BASELINE:.3f} avg hits).
  </p>
</div>

<script>
const DATA = {js_data};
const DRAWS = {js_draws};
const BEST_SEED = {best['seed']};
let selSeedVal = null;

function filterTable() {{
  const q = document.getElementById('filterInput').value.trim();
  document.querySelectorAll('#tbody tr').forEach(tr => {{
    const seed = tr.cells[1].textContent.trim().split(' ')[0];
    tr.style.display = (!q || seed.includes(q)) ? '' : 'none';
  }});
}}

let sortKey = 'rank'; let sortAsc = false;
function sortTable(key) {{
  sortAsc = (key === sortKey) ? !sortAsc : (key === 'hit0' || key === 'seed');
  sortKey = key;
  const tbody = document.getElementById('tbody');
  const rows = [...tbody.querySelectorAll('tr')];
  const keyMap = {{rank: 2, seed: 1, lift: 3, hit6: 4, hit5: 5, hit4: 6, hit0: 7, bonus: 8}};
  const col = keyMap[key] || 2;
  rows.sort((a, b) => {{
    const av = parseFloat(a.cells[col].textContent) || 0;
    const bv = parseFloat(b.cells[col].textContent) || 0;
    return sortAsc ? av - bv : bv - av;
  }});
  rows.forEach(r => tbody.appendChild(r));
}}

function selSeed(seed) {{
  selSeedVal = seed;
  document.querySelectorAll('#tbody tr').forEach(tr => tr.classList.remove('selected'));
  const rows = document.querySelectorAll('#tbody tr');
  rows.forEach(tr => {{
    if (tr.cells[1].textContent.trim().split(' ')[0] == seed) tr.classList.add('selected');
  }});
  const det = document.getElementById('detail');
  det.style.display = 'block';
  document.getElementById('detailTitle').textContent = 'Seed #' + seed + ' — last 20 draws';
  const tbody2 = document.getElementById('detailTbody');
  tbody2.innerHTML = '';

  // Generate picks client-side via seeded PRNG (Mulberry32)
  function mulberry32(seed) {{
    return function() {{
      seed |= 0; seed = seed + 0x6D2B79F5 | 0;
      let t = Math.imul(seed ^ seed >>> 15, 1 | seed);
      t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
      return ((t ^ t >>> 14) >>> 0) / 4294967296;
    }};
  }}
  function seededSample(rng, n, k) {{
    const arr = Array.from({{length: n}}, (_, i) => i + 1);
    for (let i = n - 1; i > 0; i--) {{
      const j = Math.floor(rng() * (i + 1));
      [arr[i], arr[j]] = [arr[j], arr[i]];
    }}
    return arr.slice(0, k).sort((a, b) => a - b);
  }}

  const last20 = DRAWS.slice(-20);
  last20.forEach(row => {{
    const rngSeed = (seed * 10_000_000 + row.s) >>> 0;
    const picks = seededSample(mulberry32(rngSeed), 43, 15);
    const hits = picks.filter(p => row.a.includes(p)).length;
    const bh   = picks.includes(row.b);
    tbody2.innerHTML += '<tr>' +
      '<td class="tc">' + row.s + '</td>' +
      '<td>' + row.d + '</td>' +
      '<td>' + row.a.join(', ') + ' <small>b=' + row.b + '</small></td>' +
      '<td>' + picks.join(', ') + '</td>' +
      '<td class="tc" style="color:' + (hits>=4?'#22c55e':hits>=2?'#fbbf24':'#94a3b8') + '">' +
        hits + (bh ? '+B' : '') + '</td>' +
    '</tr>';
  }});
}}
</script>
<script>
(function(){{
  var path = window.location.pathname;
  document.querySelectorAll('.nav-dropdown a').forEach(function(a){{
    var href = a.getAttribute('href');
    if(!href) return;
    if(href === path || (href !== '/' && path.startsWith(href.split('#')[0])))
      a.classList.add('active');
  }});
}})();
</script>
</body>
</html>"""

with open(HTML_OUT, 'w', encoding='utf-8') as f:
    f.write(page)
print(f"\nWrote {HTML_OUT} ({len(page)//1024} KB)")
print(f"Best seed: #{best['seed']} avg={best['avg']:.4f} lift={best['lift']:+.1f}% 6hits={best['hit6']}")
print(f"Predicted picks for draw #{next_serial}: {next_picks}")

