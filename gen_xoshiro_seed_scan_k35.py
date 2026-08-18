"""
gen_xoshiro_seed_scan_k35.py
--------------------------------
Static report page for the K=35 xoshiro256** backtest scan: seeds
-1,623,160 to 1,623,160 (3,246,321 seeds -- the first scan on this site
to include negative seeds), draws #1000-2127 (1128 draws), ranked by
hit6b (6-hit + bonus) desc, tiebreak hit6 desc, tiebreak hit5 desc.

Reads live from loto6_local.db's seed_hit_xoshiro_k35 table (populated
by load_xoshiro_seed_scan_k35_to_db.py from the 4-stage scan:
xoshiro_seed_scan_k35_stage.py run for stages 1-4) for aggregates and
the top-N table. The 1128-draw window is embedded client-side for the
seed-detail modal, so per-draw breakdowns work for ANY seed typed in
(including negative ones), computed live via the same verified
xoshiro256** JS port used elsewhere on the site.

Output: public/xoshiro_seed_scan_k35.html
Run: python gen_xoshiro_seed_scan_k35.py
"""
import sqlite3, json, re, math, os
from collections import Counter

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
DB_PATH = BASE + r"\loto6_local.db"
ENV_LOCAL = BASE + r"\.env.local"
HTML_OUT = BASE + r"\public\xoshiro_seed_scan_k35.html"
TABLE = "seed_hit_xoshiro_k35"

K_PICKS = 35
LOTO6_MAX = 43
DRAW_START, DRAW_END = 1000, 2127
N_DRAWS = DRAW_END - DRAW_START + 1  # 1128
SEED_LO, SEED_HI = -1_623_160, 1_623_160
TOP_N = 25

# ── Load aggregates + top-N from SQLite ──────────────────────────────────────
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute(f"SELECT COUNT(*) FROM {TABLE}")
num_seeds = cur.fetchone()[0]
expected_seeds = SEED_HI - SEED_LO + 1
if num_seeds != expected_seeds:
    raise SystemExit(f"Expected {expected_seeds:,} rows in {TABLE}, found {num_seeds:,}")

cur.execute(f"SELECT seed, hit6b_count, hit6_count, hit5_count FROM {TABLE}")
all_rows = cur.fetchall()

cur.execute(f"""SELECT seed, hit6b_count, hit6_count, hit5_count FROM {TABLE}
                ORDER BY hit6b_count DESC, hit6_count DESC, hit5_count DESC, seed ASC LIMIT {TOP_N}""")
top_ranked = cur.fetchall()

conn.close()
best = top_ranked[0]

# ── Aggregate distributions ──────────────────────────────────────────────────
hit6b_dist = Counter(r[1] for r in all_rows)
hit6_dist = Counter(r[2] for r in all_rows)
hit5_dist = Counter(r[3] for r in all_rows)

hit6b_labels = list(range(min(hit6b_dist), max(hit6b_dist) + 1))
hit6b_values = [hit6b_dist.get(n, 0) for n in hit6b_labels]
hit6_labels = list(range(min(hit6_dist), max(hit6_dist) + 1))
hit6_values = [hit6_dist.get(n, 0) for n in hit6_labels]
hit5_labels = list(range(min(hit5_dist), max(hit5_dist) + 1))
hit5_values = [hit5_dist.get(n, 0) for n in hit5_labels]

# ── Analytical hypergeometric baselines (pure-chance expectation) ───────────
def hyper_pmf(x, pool, success, draws):
    return (math.comb(success, x) * math.comb(pool - success, draws - x)) / math.comb(pool, draws)
def prob_all_in(subset_size_needed, pool_max, pick_k):
    return math.comb(pool_max - subset_size_needed, pick_k - subset_size_needed) / math.comb(pool_max, pick_k)

p_hit6b = prob_all_in(7, LOTO6_MAX, K_PICKS)
p_hit6 = hyper_pmf(6, LOTO6_MAX, 6, K_PICKS)
p_hit5 = hyper_pmf(5, LOTO6_MAX, 6, K_PICKS)
exp_hit6b = p_hit6b * N_DRAWS
exp_hit6 = p_hit6 * N_DRAWS
exp_hit5 = p_hit5 * N_DRAWS

print(f"Loaded {num_seeds:,} seeds from {TABLE}")
print(f"Best: seed={best[0]:,} hit6b={best[1]} hit6={best[2]} hit5={best[3]}")
print(f"Analytical expectation: hit6b~={exp_hit6b:.2f} hit6~={exp_hit6:.2f} hit5~={exp_hit5:.2f} (of {N_DRAWS} draws)")

# ── Load the exact 1000-2127 draw window from the production DB, for the
# client-side seed-detail modal. ────────────────────────────────────────────
if 'DATABASE_URL' not in os.environ:
    with open(ENV_LOCAL, encoding='utf-8') as f:
        env_text = f.read()
    m = re.search(r'DATABASE_URL=(.+)', env_text)
    os.environ['DATABASE_URL'] = m.group(1).strip()

import psycopg2
pg = psycopg2.connect(os.environ['DATABASE_URL'])
pgcur = pg.cursor()
pgcur.execute(
    "SELECT draw_serial, draw_date, num1,num2,num3,num4,num5,num6, bonus "
    "FROM loto6_results WHERE draw_serial BETWEEN %s AND %s ORDER BY draw_serial",
    (DRAW_START, DRAW_END),
)
pg_rows = pgcur.fetchall()
pg.close()
if len(pg_rows) != N_DRAWS:
    raise SystemExit(f"Draw window mismatch: got {len(pg_rows)} rows, expected {N_DRAWS}")
DRAWS = [{'s': r[0], 'd': r[1].isoformat(), 'a': list(r[2:8]), 'b': r[8]} for r in pg_rows]
js_draws = json.dumps(DRAWS, separators=(',', ':'))
print(f"Loaded {len(DRAWS)} draw records for the client-side modal (#{DRAWS[0]['s']}-{DRAWS[-1]['s']}).")

# ── Table rows ────────────────────────────────────────────────────────────
def render_rows(rows, highlight_seed=None):
    html = ""
    for rank, (seed, hit6b, hit6, hit5) in enumerate(rows, 1):
        badge = ' <span class="badge">BEST</span>' if seed == highlight_seed else ''
        html += f"""<tr class="dr" onclick="openSeedDetail({seed})">
  <td class="tc">{rank}</td>
  <td class="tc">{seed:,}{badge}</td>
  <td class="tr">{hit6b}</td>
  <td class="tr">{hit6}</td>
  <td class="tr">{hit5}</td>
</tr>"""
    return html

rows_html = render_rows(top_ranked, highlight_seed=best[0])

hit6b_labels_json = json.dumps(hit6b_labels)
hit6b_values_json = json.dumps(hit6b_values)
hit6_labels_json = json.dumps(hit6_labels)
hit6_values_json = json.dumps(hit6_values)
hit5_labels_json = json.dumps(hit5_labels)
hit5_values_json = json.dumps(hit5_values)

page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Xoshiro Seed Scan K=35 (±1,623,160) — Loto 6</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
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

*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0a0f1e;color:#e2e8f0;font-family:system-ui,sans-serif;padding-top:60px;min-height:100vh}}
.wrap{{max-width:1200px;margin:0 auto;padding:24px 16px}}
h1{{font-size:1.4rem;font-weight:700;color:#f1f5f9;margin-bottom:4px}}
.subtitle{{font-size:.85rem;color:#64748b;margin-bottom:20px}}

.note{{background:#0d1526;border:1px solid #1e293b;border-radius:10px;padding:14px 18px;
  font-size:.8rem;color:#94a3b8;margin-bottom:20px;line-height:1.6}}

.stats-row{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:24px}}
.stat-card{{background:#0d1526;border:1px solid #1e293b;border-radius:10px;padding:14px 18px;flex:1;min-width:160px}}
.stat-card .lbl{{font-size:.72rem;color:#64748b;text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px}}
.stat-card .val{{font-size:1.4rem;font-weight:700;color:#f1f5f9}}
.stat-card .sub{{font-size:.78rem;color:#94a3b8;margin-top:2px}}

.section{{background:#0d1526;border:1px solid #1e293b;border-radius:12px;padding:20px;margin-bottom:24px}}
.section h2{{font-size:1rem;font-weight:700;color:#f1f5f9;margin-bottom:4px}}
.section .desc{{font-size:.8rem;color:#64748b;margin-bottom:16px}}
.chart-wrap{{height:260px;position:relative}}

.three-col{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px}}
@media (max-width: 980px){{.three-col{{grid-template-columns:1fr}}}}

.tbl-wrap{{overflow-x:auto;border-radius:10px;border:1px solid #1e293b}}
table{{width:100%;border-collapse:collapse;font-size:.83rem}}
thead th{{background:#0d1526;padding:9px 12px;text-align:right;color:#94a3b8;
  font-weight:600;font-size:.72rem;text-transform:uppercase;letter-spacing:.05em;
  white-space:nowrap;border-bottom:1px solid #1e293b}}
thead th.tc{{text-align:center}}
tbody tr{{border-bottom:1px solid #1e293b}}
tbody tr:hover{{background:#111827}}
tbody tr.dr{{cursor:pointer}}
tbody td{{padding:7px 12px;text-align:right;color:#cbd5e1}}
tbody td.tc{{text-align:center}}
tbody td.tr{{text-align:right}}
.badge{{background:#fef08a;color:#713f12;font-size:9px;padding:2px 6px;border-radius:4px;margin-left:4px;font-weight:700}}

.lookup{{background:#0d1526;border:1px solid #a78bfa55;border-radius:10px;padding:14px 18px;margin-bottom:24px;display:flex;gap:10px;align-items:center;flex-wrap:wrap}}
.lookup .lbl{{font-size:.72rem;color:#a78bfa;text-transform:uppercase;letter-spacing:.06em;font-weight:700;margin-right:4px}}
.lookup input{{background:#0a0f1e;border:1px solid #334155;border-radius:7px;padding:8px 12px;
  color:#e2e8f0;font-size:.85rem;width:160px}}
.lookup button{{background:#7c3aed;border:none;color:#fff;padding:8px 16px;border-radius:7px;
  cursor:pointer;font-size:.83rem;font-weight:600}}
.lookup button:hover{{background:#6d28d9}}
.lookup .hint{{font-size:.78rem;color:#64748b}}
.lookup .err{{font-size:.78rem;color:#f87171}}

#seedModal{{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.82);z-index:20000;align-items:flex-start;justify-content:center;padding:60px 16px 20px}}
.modal-box{{background:#0a0f1e;border:1px solid #1e293b;border-radius:12px;width:100%;max-width:1050px;max-height:85vh;display:flex;flex-direction:column}}
.modal-hdr{{display:flex;justify-content:space-between;align-items:center;padding:14px 18px;border-bottom:1px solid #1e293b;flex-shrink:0;gap:16px;flex-wrap:wrap}}
.modal-hdr h2{{font-size:.95rem;font-weight:700;color:#f1f5f9;margin:0}}
.modal-hdr .modal-stats{{font-size:.78rem;color:#94a3b8;display:flex;gap:14px;flex-wrap:wrap}}
.modal-hdr .modal-stats b{{color:#e2e8f0}}
.modal-close{{background:#1e293b;border:none;color:#94a3b8;padding:5px 14px;border-radius:6px;cursor:pointer;font-size:.83rem}}
.modal-close:hover{{background:#334155;color:#f1f5f9}}
.modal-body{{overflow-y:auto;flex:1}}
.modal-table{{width:100%;border-collapse:collapse;font-size:.78rem}}
.modal-table thead{{position:sticky;top:0;background:#0a0f1e;z-index:1}}
.modal-table th{{padding:9px 12px;color:#64748b;text-align:left;border-bottom:1px solid #1e293b;font-weight:600;font-size:.72rem;text-transform:uppercase;letter-spacing:.04em;white-space:nowrap}}
.modal-table td{{padding:6px 10px;border-bottom:1px solid #0f172a;vertical-align:middle}}
.modal-table tr:hover td{{background:#0f172a}}
.nb{{display:inline-flex;align-items:center;justify-content:center;width:24px;height:24px;border-radius:50%;background:#1e293b;color:#64748b;font-size:.66rem;font-weight:700;margin:1px}}
.nm{{background:#14532d;color:#86efac}}
.nb-b{{background:#451a03;color:#fde68a;border:1px solid #92400e}}
.nb-bh{{background:#7c2d12;color:#fed7aa}}

.nbhd-section{{padding:14px 18px;border-bottom:1px solid #1e293b;flex-shrink:0;background:#0d1526}}
.nbhd-hdr{{display:flex;align-items:center;gap:12px;flex-wrap:wrap}}
.nbhd-hdr h3{{font-size:.85rem;font-weight:700;color:#f1f5f9;margin:0}}
.nbhd-hdr .hint{{font-size:.74rem;color:#64748b}}
#nbhdBtn{{background:#7c3aed;border:none;color:#fff;padding:6px 14px;border-radius:7px;
  cursor:pointer;font-size:.78rem;font-weight:600}}
#nbhdBtn:hover{{background:#6d28d9}}
#nbhdBtn:disabled{{background:#4c1d95;cursor:default;opacity:.7}}
.nbhd-progress{{font-size:.78rem;color:#a78bfa}}
.nbhd-stats-row{{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px}}
.nbhd-stat{{background:#0a0f1e;border:1px solid #1e293b;border-radius:8px;padding:8px 12px;flex:1;min-width:120px}}
.nbhd-stat .lbl{{font-size:.66rem;color:#64748b;text-transform:uppercase;letter-spacing:.05em;margin-bottom:2px}}
.nbhd-stat .val{{font-size:1.05rem;font-weight:700;color:#f1f5f9}}
.nbhd-chart-wrap{{height:170px;position:relative;margin-top:12px}}
.nbhd-note{{font-size:.78rem;color:#94a3b8;margin-top:10px;line-height:1.5}}

.footer{{margin-top:28px;font-size:.78rem;color:#475569;padding-bottom:20px;line-height:1.6}}
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
        <a href="/avg_hub.html">⬡ All N-Draw Avg (2–43)</a>
        <div class="nav-divider"></div>
        <div class="nav-dd-label">N-Draw Avg Shift</div>
        <a href="/avg_shift_hub.html">⇄ All N-Shift Avg (2–43)</a>
        <div class="nav-divider"></div>
        <div class="nav-dd-label">Random Seed</div>
        <a href="/random_seed_backtest.html">🎲 Random Seed (1–3000)</a>
        <a href="/k7_seed_coverage.html">📈 K=7 Seed Coverage</a>
        <a href="/k7_seed_hit_1000.html">🗺️ K=7 Seed-Hit (1000 draws)</a>
      </div></div>
    </div>
    <div class="nav-group">
      <div class="nav-group-btn">Xoshiro Research <span class="arrow">▼</span></div>
      <div class="nav-dropdown"><div class="nav-dropdown-inner">
        <div class="nav-dd-label">Xoshiro256** Seed Scans</div>
        <a href="/xoshiro_seed_backtest.html">🌀 K=21, seeds 0–1,000</a>
        <a href="/xoshiro_seed_scan_100k.html">🔬 K=21, seeds 1–100,000</a>
        <a href="/xoshiro_seed_scan_k33.html">🎯 K=33, seeds 0–1,000,000</a>
        <a href="/xoshiro_seed_scan_k38.html">🔷 K=38, seeds 0–1,000,000</a>
        <a href="/xoshiro_seed_scan_k35.html" class="active">🟣 K=35, seeds ±1,623,160</a>
        <a href="/xoshiro_seed_scan_k7.html">🔎 K=7, seeds 0–10,000</a>
        <div class="nav-divider"></div>
        <div class="nav-dd-label">Predictions</div>
        <a href="/xoshiro_elim_2128.html">✂️ Draw #2128 Elimination</a>
        <a href="/xoshiro_elim_2129.html">✂️ Draw #2129 Elimination</a>
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
  <h1>🟣 Xoshiro Seed Scan — K=35 (seeds -1,623,160 to 1,623,160)</h1>
  <p class="subtitle">{num_seeds:,} seeds · K={K_PICKS} picks · {N_DRAWS} draws (#{DRAW_START}–{DRAW_END}) · xoshiro256** (SplitMix64-seeded)</p>

  <div class="note">
    Same xoshiro256**/SplitMix64 algorithm and combined-seed formula (<code>seed×10,000,000 + draw_serial</code>) as the
    other seed-scan pages, but with 35 picks out of 43 and the <b>first negative-seed range tested on this site</b>:
    seeds {SEED_LO:,} to {SEED_HI:,} ({num_seeds:,} values). Python's bitwise AND on negative integers correctly produces
    the standard 64-bit two's-complement wraparound needed by the formula — self-checked against the verified modular
    implementation for several negative seeds (including both range boundaries) before scaling up. Three metrics tracked
    per seed: <b>hit6b</b> = draws where the 35 picks contain all 6 main winning numbers <em>and</em> the bonus number;
    <b>hit6</b> = draws with all 6 main numbers (any bonus); <b>hit5</b> = draws with exactly 5 of 6 main numbers.
    Ranking: highest hit6b, tiebreak hit6, tiebreak hit5. Scanned in 4 stages of ~811,580 seeds each (roughly 7.8 hours
    total) — draw records pulled directly from the production database and verified for exactly {N_DRAWS} consecutive
    rows with no gaps before each stage.
  </div>

  <div class="lookup">
    <span class="lbl">🔍 Seed detail lookup</span>
    <input id="seedLookupInput" type="number" step="1" placeholder="Enter any seed (negative OK)..." onkeydown="if(event.key==='Enter')lookupSeed()">
    <button onclick="lookupSeed()">View {N_DRAWS}-draw breakdown</button>
    <span class="hint">e.g. try {best[0]:,} (the top-ranked seed) — or any seed, positive or negative. Computed live in your browser.</span>
    <span id="lookupErr" class="err" style="display:none"></span>
  </div>

  <div class="stats-row">
    <div class="stat-card">
      <div class="lbl">Best seed (ranked)</div>
      <div class="val">#{best[0]:,}</div>
      <div class="sub">hit6b {best[1]} · hit6 {best[2]} · hit5 {best[3]}</div>
    </div>
    <div class="stat-card">
      <div class="lbl">Expected hit6b (chance)</div>
      <div class="val">{exp_hit6b:.1f}</div>
      <div class="sub">hypergeometric, per seed</div>
    </div>
    <div class="stat-card">
      <div class="lbl">Expected hit6 (chance)</div>
      <div class="val">{exp_hit6:.1f}</div>
      <div class="sub">hypergeometric, per seed</div>
    </div>
    <div class="stat-card">
      <div class="lbl">Expected hit5 (chance)</div>
      <div class="val">{exp_hit5:.1f}</div>
      <div class="sub">hypergeometric, per seed</div>
    </div>
    <div class="stat-card">
      <div class="lbl">Seeds tested</div>
      <div class="val">{num_seeds:,}</div>
      <div class="sub">{SEED_LO:,} to {SEED_HI:,}</div>
    </div>
  </div>

  <div class="three-col">
    <div class="section">
      <h2>hit6b distribution</h2>
      <p class="desc">6-hit + bonus draw count across all {num_seeds:,} seeds.</p>
      <div class="chart-wrap"><canvas id="hit6bChart"></canvas></div>
    </div>
    <div class="section">
      <h2>hit6 distribution</h2>
      <p class="desc">6-hit (any bonus) draw count across all {num_seeds:,} seeds.</p>
      <div class="chart-wrap"><canvas id="hit6Chart"></canvas></div>
    </div>
    <div class="section">
      <h2>hit5 distribution</h2>
      <p class="desc">Exactly-5-hit draw count across all {num_seeds:,} seeds.</p>
      <div class="chart-wrap"><canvas id="hit5Chart"></canvas></div>
    </div>
  </div>

  <div class="section">
    <h2>Top {TOP_N} seeds (ranked: hit6b → hit6 → hit5)</h2>
    <p class="desc">Click a row for the full {N_DRAWS}-draw breakdown.</p>
    <div class="tbl-wrap">
      <table>
        <thead><tr><th class="tc">#</th><th class="tc">Seed</th><th>hit6b</th><th>hit6</th><th>hit5</th></tr></thead>
        <tbody>{rows_html}</tbody>
      </table>
    </div>
  </div>

  <p class="footer">
    Xoshiro256** (seeded via SplitMix64): picks = partial Fisher-Yates(range(1,44), {K_PICKS}) with combined seed = seed×10⁷ + draw_serial.
    Algorithm verified against independent reference sources before running — see
    <a href="/xoshiro_seed_backtest.html" style="color:#64748b">the 0–1000 seed page</a> for full verification details, plus a
    dedicated negative-seed self-check for this scan (Python's <code>&amp;</code> on negative ints correctly wraps to 64-bit
    two's complement, matching the modular reference bit-exact).<br>
    Data read live from <code>{TABLE}</code> in <code>loto6_local.db</code>. Draw records for #{DRAW_START}–{DRAW_END}
    sourced directly from the production database, verified for exactly {N_DRAWS} consecutive rows with no gaps before scanning.<br>
    Formula-based only · Not financial advice · Loto 6 is random.
  </p>

  <div id="seedModal">
    <div class="modal-box">
      <div class="modal-hdr">
        <h2 id="modalTitle">Seed detail</h2>
        <div class="modal-stats" id="modalStats"></div>
        <button class="modal-close" onclick="document.getElementById('seedModal').style.display='none'">✕ Close</button>
      </div>
      <div class="nbhd-section">
        <div class="nbhd-hdr">
          <h3>🔬 Local Neighborhood (±100 seeds)</h3>
          <button id="nbhdBtn" onclick="computeNeighborhood()">Compute ±100 seeds around this one</button>
          <span id="nbhdProgress" class="nbhd-progress" style="display:none"></span>
          <span class="hint">Recomputed live in your browser for the seed currently open — not precomputed or stored.</span>
        </div>
        <div id="nbhdResults" style="display:none">
          <div class="nbhd-stats-row">
            <div class="nbhd-stat"><div class="lbl">Local rank (hit6b)</div><div class="val" id="nbhdRank">-</div></div>
            <div class="nbhd-stat"><div class="lbl">hit6b range</div><div class="val" id="nbhdRange">-</div></div>
            <div class="nbhd-stat"><div class="lbl">hit6b mean / median</div><div class="val" id="nbhdMeanMed">-</div></div>
            <div class="nbhd-stat"><div class="lbl">hit6b stdev</div><div class="val" id="nbhdStdev">-</div></div>
          </div>
          <div class="nbhd-chart-wrap"><canvas id="nbhdChart"></canvas></div>
          <p id="nbhdNote" class="nbhd-note"></p>
        </div>
      </div>
      <div class="modal-body">
        <table class="modal-table">
          <thead><tr>
            <th>Draw</th><th>Date</th>
            <th>Actual (6) + bonus</th>
            <th>Picks ({K_PICKS}) · generation order</th>
            <th style="text-align:center">Hits</th>
          </tr></thead>
          <tbody id="modalTbody"></tbody>
        </table>
      </div>
    </div>
  </div>
</div>

<script>
function mkChart(id, labels, values, color) {{
  new Chart(document.getElementById(id).getContext('2d'), {{
    type: 'bar',
    data: {{ labels: labels, datasets: [{{ label: 'Seeds', data: values, backgroundColor: color + '55', borderColor: color, borderWidth: 1 }}] }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      plugins: {{ legend: {{ display: false }}, tooltip: {{ callbacks: {{ label: function(ctx) {{ return ctx.parsed.y.toLocaleString() + ' seeds'; }} }} }} }},
      scales: {{
        y: {{ beginAtZero: true, ticks: {{ color: '#64748b' }}, grid: {{ color: '#1e293b' }} }},
        x: {{ ticks: {{ color: '#64748b', maxTicksLimit: 12 }}, grid: {{ display: false }} }}
      }}
    }}
  }});
}}
mkChart('hit6bChart', {hit6b_labels_json}, {hit6b_values_json}, '#38bdf8');
mkChart('hit6Chart', {hit6_labels_json}, {hit6_values_json}, '#22c55e');
mkChart('hit5Chart', {hit5_labels_json}, {hit5_values_json}, '#f59e0b');
</script>
<script>
// ── Seed-detail modal: picks computed LIVE for any seed (including negative)
// via the same verified xoshiro256** implementation (bit-exact BigInt port)
// used elsewhere on the site -- not limited to seeds in the top-{TOP_N} table.
const DRAWS = {js_draws};

const MASK64 = (1n << 64n) - 1n;
function rotl(x, k) {{
  x &= MASK64;
  return ((x << BigInt(k)) | (x >> BigInt(64 - k))) & MASK64;
}}
function splitmix64Next(z) {{
  z = (z + 0x9E3779B97F4A7C15n) & MASK64;
  let zz = z;
  zz = ((zz ^ (zz >> 30n)) * 0xBF58476D1CE4E5B9n) & MASK64;
  zz = ((zz ^ (zz >> 27n)) * 0x94D049BB133111EBn) & MASK64;
  zz = zz ^ (zz >> 31n);
  return [z, zz];
}}
function seedState(seed) {{
  // BigInt & MASK64 correctly wraps negative BigInts to 64-bit two's complement, same as Python
  let z = BigInt(seed) & MASK64;
  const state = [];
  for (let i = 0; i < 4; i++) {{
    const [nz, out] = splitmix64Next(z);
    z = nz;
    state.push(out);
  }}
  return state;
}}
function xoshiroNext(s) {{
  const result = (rotl((s[1] * 5n) & MASK64, 7) * 9n) & MASK64;
  const t = (s[1] << 17n) & MASK64;
  s[2] ^= s[0]; s[3] ^= s[1]; s[1] ^= s[2]; s[0] ^= s[3];
  s[2] ^= t;
  s[3] = rotl(s[3], 45);
  return result;
}}
function xoshiroPredict(seed, drawSerial, k) {{
  const combined = (BigInt(seed) * 10000000n + BigInt(drawSerial)) & MASK64;
  const s = seedState(combined);
  const arr = Array.from({{length: 43}}, (_, i) => i + 1);
  const n = arr.length;
  // Returned in generation order (the order the partial Fisher-Yates shuffle
  // finalizes each position: i = n-1 first, down to i = n-k last) -- NOT
  // sorted. Callers that only need set-membership (hit counting) are
  // unaffected since order doesn't matter there; callers that display the
  // picks (the seed-detail modal) show the raw generation sequence.
  const order = [];
  for (let i = n - 1; i >= n - k; i--) {{
    const r = xoshiroNext(s);
    const j = Number(r % BigInt(i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
    order.push(arr[i]);
  }}
  return order;
}}

function lookupSeed() {{
  const input = document.getElementById('seedLookupInput');
  const errEl = document.getElementById('lookupErr');
  const raw = input.value.trim();
  errEl.style.display = 'none';
  if (raw === '' || !/^-?\\d+$/.test(raw)) {{
    errEl.textContent = 'Enter a whole number (negative or positive).';
    errEl.style.display = 'inline';
    return;
  }}
  openSeedDetail(parseInt(raw, 10));
}}

function openSeedDetail(seed) {{
  window.__currentModalSeed = seed;
  resetNeighborhood();
  const K = {K_PICKS};
  let hit6b = 0, hit6 = 0, hit5 = 0;
  const htmlParts = [];
  [...DRAWS].reverse().forEach(row => {{
    const picks = xoshiroPredict(seed, row.s, K);
    const actualSet = new Set(row.a);
    const picksSet = new Set(picks);
    const hits = picks.filter(p => actualSet.has(p)).length;
    const bh   = picksSet.has(row.b);
    if (hits === 6) {{ hit6++; if (bh) hit6b++; }}
    else if (hits === 5) {{ hit5++; }}

    const actualHtml = row.a.map(n =>
      '<span class="nb nm">' + n + '</span>'
    ).join('') + '<span class="nb nb-b">' + row.b + '</span>';

    const picksHtml = picks.map(n =>
      '<span class="nb' + (actualSet.has(n) ? ' nm' : '') + (n === row.b ? ' nb-bh' : '') + '">' + n + '</span>'
    ).join('');

    const hc = hits >= 5 ? '#22c55e' : hits >= 4 ? '#4ade80' : hits >= 3 ? '#fbbf24' : hits >= 2 ? '#fb923c' : '#475569';
    htmlParts.push(
      '<tr><td style="color:#64748b;white-space:nowrap">' + row.s + '</td>' +
      '<td style="color:#64748b;white-space:nowrap">' + (row.d||'') + '</td>' +
      '<td style="white-space:nowrap">' + actualHtml + '</td>' +
      '<td style="white-space:nowrap">' + picksHtml + '</td>' +
      '<td style="text-align:center;font-weight:700;color:' + hc + '">' + hits + (bh ? '<span style="color:#a78bfa;font-size:.7rem">+B</span>' : '') + '</td></tr>'
    );
  }});

  document.getElementById('modalTitle').textContent = 'Seed #' + seed.toLocaleString() + ' — ' + DRAWS.length + ' draws (K=' + K + ')';
  document.getElementById('modalStats').innerHTML =
    'hit6b: <b>' + hit6b + '</b> &nbsp;·&nbsp; hit6: <b>' + hit6 + '</b> &nbsp;·&nbsp; hit5: <b>' + hit5 + '</b>';
  document.getElementById('modalTbody').innerHTML = htmlParts.join('');
  document.getElementById('seedModal').style.display = 'flex';
}}

// ── Local neighborhood (±100 seeds): computed live in the browser, on
// demand, for whichever seed the modal currently has open. Not stored or
// precomputed for every seed -- just the same live BigInt xoshiro256** run
// used for the per-draw breakdown above, repeated for 201 nearby seeds.
let nbhdChart = null;
const NBHD_RADIUS = 100;
const NBHD_CHUNK = 10;

function resetNeighborhood() {{
  const resultsEl = document.getElementById('nbhdResults');
  const progress = document.getElementById('nbhdProgress');
  const btn = document.getElementById('nbhdBtn');
  resultsEl.style.display = 'none';
  progress.style.display = 'none';
  btn.disabled = false;
  btn.textContent = 'Compute ±100 seeds around this one';
  if (nbhdChart) {{ nbhdChart.destroy(); nbhdChart = null; }}
}}

function computeNeighborhood() {{
  const seed = window.__currentModalSeed;
  if (seed === undefined || seed === null) return;
  const K = {K_PICKS};
  const btn = document.getElementById('nbhdBtn');
  const progress = document.getElementById('nbhdProgress');
  const resultsEl = document.getElementById('nbhdResults');
  btn.disabled = true;
  progress.style.display = 'inline';
  resultsEl.style.display = 'none';

  const seeds = [];
  for (let s = seed - NBHD_RADIUS; s <= seed + NBHD_RADIUS; s++) seeds.push(s);
  const results = [];
  let idx = 0;

  function step() {{
    const end = Math.min(idx + NBHD_CHUNK, seeds.length);
    for (; idx < end; idx++) {{
      const s = seeds[idx];
      let hit6b = 0, hit6 = 0, hit5 = 0;
      for (const row of DRAWS) {{
        const picks = xoshiroPredict(s, row.s, K);
        const actualSet = new Set(row.a);
        const picksSet = new Set(picks);
        const hits = picks.filter(p => actualSet.has(p)).length;
        if (hits === 6) {{ hit6++; if (picksSet.has(row.b)) hit6b++; }}
        else if (hits === 5) {{ hit5++; }}
      }}
      results.push({{ seed: s, hit6b, hit6, hit5 }});
    }}
    progress.textContent = 'Computing... ' + idx + '/' + seeds.length;
    if (idx < seeds.length) {{
      setTimeout(step, 0);
    }} else {{
      finishNeighborhood(seed, results);
    }}
  }}
  setTimeout(step, 0);
}}

function finishNeighborhood(seed, results) {{
  const btn = document.getElementById('nbhdBtn');
  const progress = document.getElementById('nbhdProgress');
  const resultsEl = document.getElementById('nbhdResults');
  btn.disabled = false;
  btn.textContent = 'Recompute';
  progress.style.display = 'none';

  const n = results.length;
  const h6b = results.map(r => r.hit6b);
  const sorted = [...h6b].sort((a, b) => a - b);
  const min = sorted[0], max = sorted[n - 1];
  const mean = h6b.reduce((a, b) => a + b, 0) / n;
  const median = n % 2 === 1 ? sorted[(n - 1) / 2] : (sorted[n / 2 - 1] + sorted[n / 2]) / 2;
  const variance = h6b.reduce((a, b) => a + (b - mean) * (b - mean), 0) / (n - 1);
  const stdev = Math.sqrt(variance);

  const ranked = [...results].sort((a, b) =>
    b.hit6b - a.hit6b || b.hit6 - a.hit6 || b.hit5 - a.hit5 || a.seed - b.seed);
  const rankIdx = ranked.findIndex(r => r.seed === seed) + 1;
  const target = results.find(r => r.seed === seed);
  const sigma = stdev > 0 ? (target.hit6b - mean) / stdev : 0;

  document.getElementById('nbhdRank').textContent = '#' + rankIdx + ' of ' + n;
  document.getElementById('nbhdRange').textContent = min + ' – ' + max;
  document.getElementById('nbhdMeanMed').textContent = mean.toFixed(1) + ' / ' + median;
  document.getElementById('nbhdStdev').textContent = stdev.toFixed(2);

  let note = 'Seed #' + seed.toLocaleString() + ' ranks #' + rankIdx + ' of ' + n +
    ' in its own ±' + NBHD_RADIUS + ' neighborhood (hit6b=' + target.hit6b + ', ' +
    (sigma >= 0 ? '+' : '') + sigma.toFixed(1) + 'σ vs the local mean).';
  if (rankIdx === 1 && n > 1) {{
    const second = ranked[1];
    const gap = target.hit6b - second.hit6b;
    note += ' It leads the 2nd-best local seed (#' + second.seed.toLocaleString() + ', hit6b=' + second.hit6b + ') by ' + gap +
      (gap > stdev * 2
        ? ' — an isolated spike, not surrounded by similarly strong neighbors.'
        : ' — part of a cluster of comparably strong neighboring seeds.');
  }}
  document.getElementById('nbhdNote').textContent = note;

  // Reveal the container BEFORE constructing the Chart -- Chart.js measures
  // its parent at creation time, so building it while display:none is still
  // in effect would freeze the canvas at 0x0.
  resultsEl.style.display = 'block';

  const labels = results.map(r => (r.seed - seed > 0 ? '+' : '') + (r.seed - seed));
  const values = results.map(r => r.hit6b);
  const colors = results.map(r => r.seed === seed ? '#fbbf24' : '#a78bfa77');
  const borders = results.map(r => r.seed === seed ? '#fbbf24' : '#a78bfa');
  if (nbhdChart) nbhdChart.destroy();
  nbhdChart = new Chart(document.getElementById('nbhdChart').getContext('2d'), {{
    type: 'bar',
    data: {{ labels: labels, datasets: [{{ label: 'hit6b', data: values, backgroundColor: colors, borderColor: borders, borderWidth: 1 }}] }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      plugins: {{
        legend: {{ display: false }},
        tooltip: {{
          callbacks: {{
            title: function(items) {{ return 'seed offset ' + items[0].label; }},
            label: function(ctx) {{ return 'hit6b: ' + ctx.parsed.y; }}
          }}
        }}
      }},
      scales: {{
        y: {{ beginAtZero: false, ticks: {{ color: '#64748b' }}, grid: {{ color: '#1e293b' }} }},
        x: {{ ticks: {{ color: '#64748b', maxTicksLimit: 12 }}, grid: {{ display: false }} }}
      }}
    }}
  }});
}}

document.getElementById('seedModal').addEventListener('click', function(e) {{
  if (e.target === this) this.style.display = 'none';
}});
document.addEventListener('keydown', function(e) {{
  if (e.key === 'Escape') document.getElementById('seedModal').style.display = 'none';
}});
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
