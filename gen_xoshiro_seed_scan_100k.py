"""
gen_xoshiro_seed_scan_100k.py
--------------------------------
Static report page for the 100,000-seed xoshiro256** K=21 backtest scan
(draws #1127-2126, same 1000-draw window and algorithm as
xoshiro_seed_backtest.html, verified in gen_xoshiro_seed_backtest.py).

Reads live from loto6_local.db's seed_hit_xoshiro_k21 table (populated by
load_xoshiro_seed_scan_100k_to_db.py from xoshiro_seed_scan_100k.py's scan)
rather than embedding all 100,000 rows client-side -- only compact
aggregates (distribution histograms) and top-N seed tables are embedded.

Output: public/xoshiro_seed_scan_100k.html
Run: python gen_xoshiro_seed_scan_100k.py
"""
import sqlite3, json
from collections import Counter

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
DB_PATH = BASE + r"\loto6_local.db"
HTML_OUT = BASE + r"\public\xoshiro_seed_scan_100k.html"
TABLE = "seed_hit_xoshiro_k21"

K_PICKS = 21
N_DRAWS = 1000
LOTO6_MAX = 43
DRAW_START, DRAW_END = 1127, 2126
BASELINE = K_PICKS * 6 / LOTO6_MAX

# Earlier 0-1000 seed range result, for the comparison callout
PRIOR_BEST_SEED, PRIOR_BEST_AVG, PRIOR_BEST_LIFT = 168, 3.0560, 4.30
TOP_N = 25

# ── Load from SQLite ────────────────────────────────────────────────────────
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute(f"SELECT COUNT(*) FROM {TABLE}")
num_seeds = cur.fetchone()[0]
if num_seeds != 100_000:
    raise SystemExit(f"Expected 100,000 rows in {TABLE}, found {num_seeds}")

cur.execute(f"SELECT seed, avg_hits, hit6_count, hit0_count FROM {TABLE}")
all_rows = cur.fetchall()

cur.execute(f"SELECT seed, avg_hits, hit6_count, hit0_count FROM {TABLE} ORDER BY avg_hits DESC, seed ASC LIMIT {TOP_N}")
top_by_avg = cur.fetchall()

cur.execute(f"SELECT seed, avg_hits, hit6_count, hit0_count FROM {TABLE} ORDER BY hit6_count DESC, avg_hits DESC, seed ASC LIMIT {TOP_N}")
top_by_hit6 = cur.fetchall()

conn.close()

best_avg = top_by_avg[0]
best_hit6 = top_by_hit6[0]
best_lift = (best_avg[1] / BASELINE - 1) * 100

# ── Aggregate distributions (compact -- bin counts only, not raw rows) ──────
hit6_dist = Counter(r[2] for r in all_rows)
hit0_dist = Counter(r[3] for r in all_rows)

hit6_labels = list(range(0, max(hit6_dist) + 1))
hit6_values = [hit6_dist.get(n, 0) for n in hit6_labels]
hit0_labels = list(range(0, max(hit0_dist) + 1))
hit0_values = [hit0_dist.get(n, 0) for n in hit0_labels]

# ── Noise-level framing: expected max deviation via extreme-value approx ────
# Per-draw hypergeometric variance (N=43 pool, K=6 winners, n=21 picks)
var_per_draw = K_PICKS * (6/LOTO6_MAX) * ((LOTO6_MAX-6)/LOTO6_MAX) * ((LOTO6_MAX-K_PICKS)/(LOTO6_MAX-1))
sigma_avg = (var_per_draw / N_DRAWS) ** 0.5
import math
def expected_max_lift_pct(n_seeds):
    dev = sigma_avg * (2 * math.log(n_seeds)) ** 0.5
    return dev / BASELINE * 100

predicted_lift_1001 = expected_max_lift_pct(1001)
predicted_lift_100000 = expected_max_lift_pct(100_000)

print(f"Loaded {num_seeds:,} seeds from {TABLE}")
print(f"Best by avg: seed={best_avg[0]} avg={best_avg[1]:.4f} lift={best_lift:+.2f}%")
print(f"Best by hit6: seed={best_hit6[0]} hit6={best_hit6[2]} avg={best_hit6[1]:.4f}")
print(f"Noise model: predicted max lift @1001 seeds={predicted_lift_1001:.2f}% (observed {PRIOR_BEST_LIFT:.2f}%), "
      f"@100000 seeds={predicted_lift_100000:.2f}% (observed {best_lift:.2f}%)")

# ── Table rows ────────────────────────────────────────────────────────────
def render_rows(rows, highlight_seed=None):
    html = ""
    for rank, (seed, avg, hit6, hit0) in enumerate(rows, 1):
        lift = (avg / BASELINE - 1) * 100
        lift_color = "#22c55e" if lift > 0 else "#ef4444"
        badge = ' <span class="badge">BEST</span>' if seed == highlight_seed else ''
        html += f"""<tr>
  <td class="tc">{rank}</td>
  <td class="tc">{seed:,}{badge}</td>
  <td class="tr">{avg:.4f}</td>
  <td class="tr" style="color:{lift_color}">{lift:+.2f}%</td>
  <td class="tr">{hit6}</td>
  <td class="tr">{hit0}</td>
</tr>"""
    return html

rows_by_avg_html = render_rows(top_by_avg, highlight_seed=best_avg[0])
rows_by_hit6_html = render_rows(top_by_hit6, highlight_seed=best_hit6[0])

hit6_labels_json = json.dumps(hit6_labels)
hit6_values_json = json.dumps(hit6_values)
hit0_labels_json = json.dumps(hit0_labels)
hit0_values_json = json.dumps(hit0_values)

page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Xoshiro Seed Scan (1–100,000) — Loto 6</title>
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
.chart-wrap{{height:280px;position:relative}}

.two-col{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}
@media (max-width: 820px){{.two-col{{grid-template-columns:1fr}}}}

.tbl-wrap{{overflow-x:auto;border-radius:10px;border:1px solid #1e293b}}
table{{width:100%;border-collapse:collapse;font-size:.83rem}}
thead th{{background:#0d1526;padding:9px 12px;text-align:right;color:#94a3b8;
  font-weight:600;font-size:.72rem;text-transform:uppercase;letter-spacing:.05em;
  white-space:nowrap;border-bottom:1px solid #1e293b}}
thead th.tc{{text-align:center}}
tbody tr{{border-bottom:1px solid #1e293b}}
tbody tr:hover{{background:#111827}}
tbody td{{padding:7px 12px;text-align:right;color:#cbd5e1}}
tbody td.tc{{text-align:center}}
tbody td.tr{{text-align:right}}
.badge{{background:#fef08a;color:#713f12;font-size:9px;padding:2px 6px;border-radius:4px;margin-left:4px;font-weight:700}}

.callout{{background:#0c2340;border:1px solid #38bdf855;border-radius:10px;padding:14px 18px;margin-top:16px}}
.callout .lbl{{font-size:.72rem;color:#38bdf8;text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px;font-weight:700}}
.callout p{{font-size:.83rem;color:#e2e8f0;line-height:1.55}}
.callout p + p{{margin-top:8px}}
.callout code{{background:#0a0f1e;padding:1px 5px;border-radius:4px;font-size:.8em}}

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
        <a href="/xoshiro_seed_backtest.html">🌀 Xoshiro Seed (0–1000)</a>
        <a href="/xoshiro_seed_scan_100k.html" class="active">🔬 Xoshiro Seed Scan (1–100k)</a>
        <a href="/k7_seed_coverage.html">📈 K=7 Seed Coverage</a>
        <a href="/k7_seed_hit_1000.html">🗺️ K=7 Seed-Hit (1000 draws)</a>
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
  <h1>🔬 Xoshiro Seed Scan — 1 to 100,000</h1>
  <p class="subtitle">{num_seeds:,} seeds · K={K_PICKS} picks · {N_DRAWS} draws (#{DRAW_START}–{DRAW_END}) · xoshiro256** (SplitMix64-seeded) · random baseline ≈ {BASELINE:.4f} avg hits</p>

  <div class="note">
    Expanded 100x from the <a href="/xoshiro_seed_backtest.html" style="color:#a78bfa">0–1000 seed backtest</a> to seeds 1–100,000,
    using the identical, independently-verified xoshiro256**/SplitMix64 algorithm and the same seed combination formula
    (<code>seed×10,000,000 + draw_serial</code>) and partial Fisher-Yates picks over 1–43. Scanned with a 7-worker
    parallelized pass (~893s / 14.9 min). Because 100,000 rows is too much to embed client-side, this page reads
    aggregates and top-{TOP_N} tables live from the <code>{TABLE}</code> table in <code>loto6_local.db</code> at
    generation time, rather than shipping the full row set to the browser.
  </div>

  <div class="stats-row">
    <div class="stat-card">
      <div class="lbl">Best seed (avg hits)</div>
      <div class="val">#{best_avg[0]:,}</div>
      <div class="sub">avg {best_avg[1]:.4f} · {best_lift:+.2f}% vs baseline</div>
    </div>
    <div class="stat-card">
      <div class="lbl">Best seed (6-hit count)</div>
      <div class="val">#{best_hit6[0]:,}</div>
      <div class="sub">{best_hit6[2]} six-hit draws · avg {best_hit6[1]:.4f}</div>
    </div>
    <div class="stat-card">
      <div class="lbl">Baseline (pure chance)</div>
      <div class="val">{BASELINE:.4f}</div>
      <div class="sub">{K_PICKS} picks × 6 / {LOTO6_MAX}</div>
    </div>
    <div class="stat-card">
      <div class="lbl">Seeds tested</div>
      <div class="val">{num_seeds:,}</div>
      <div class="sub">seeds 1–100,000</div>
    </div>
  </div>

  <div class="callout">
    <div class="lbl">📊 vs. the earlier 0–1000 seed range</div>
    <p>Seed <strong>#{PRIOR_BEST_SEED}</strong> (best in the 0–1000 range) reached avg {PRIOR_BEST_AVG:.4f}, a <strong>{PRIOR_BEST_LIFT:+.2f}%</strong> lift over baseline.
    Testing 100x more seeds turns up a slightly better one, <strong>#{best_avg[0]:,}</strong>, at avg {best_avg[1]:.4f} ({best_lift:+.2f}% lift) —
    an improvement of only {best_avg[1]-PRIOR_BEST_AVG:.4f} avg hits ({best_lift-PRIOR_BEST_LIFT:+.2f} points of lift).</p>
    <p>This is exactly what pure sampling noise predicts, not evidence of real predictive power. Each seed's 1000-draw average has an
    expected standard deviation of ≈{sigma_avg:.4f} hits under a null hypothesis of no signal (from hypergeometric variance of matching
    {K_PICKS} picks against 6 winners, averaged over {N_DRAWS} independent draws). Extreme-value theory says the expected <em>maximum</em>
    deviation across N independently-tested seeds scales with σ·√(2·ln N): for N=1,001 that predicts a max lift of ≈{predicted_lift_1001:.2f}%
    (observed {PRIOR_BEST_LIFT:.2f}%); for N=100,000 it predicts ≈{predicted_lift_100000:.2f}% (observed {best_lift:.2f}%). Both land close to
    the observed values — casting a 100x wider net catching a slightly bigger "biggest fish" is a textbook multiple-comparisons effect, not a
    property of seed #{best_avg[0]:,} itself. xoshiro256** is a well-mixed PRNG; no seed has real predictive power over future lottery draws.</p>
    <p>Best-by-6-hit-count seed <strong>#{best_hit6[0]:,}</strong> ({best_hit6[2]} six-hit draws) again illustrates the same "one metric ≠ another"
    pattern seen throughout this site's backtests: its avg hits ({best_hit6[1]:.4f}) is barely above baseline — it front-loads hits into a handful
    of jackpot draws while missing more elsewhere, rather than being consistently better.</p>
  </div>

  <div class="two-col" style="margin-top:24px">
    <div class="section">
      <h2>6-hit draw count distribution</h2>
      <p class="desc">How many of the {N_DRAWS} draws each seed's picks matched all 6 winning numbers, across all {num_seeds:,} seeds. Only 17 seeds scored zero 6-hit draws.</p>
      <div class="chart-wrap"><canvas id="hit6Chart"></canvas></div>
    </div>
    <div class="section">
      <h2>0-hit draw count distribution</h2>
      <p class="desc">How many of the {N_DRAWS} draws each seed's picks matched none of the winning numbers, across all {num_seeds:,} seeds.</p>
      <div class="chart-wrap"><canvas id="hit0Chart"></canvas></div>
    </div>
  </div>

  <div class="two-col" style="margin-top:0">
    <div class="section">
      <h2>Top {TOP_N} seeds by avg hits</h2>
      <p class="desc">Highest average hits per draw across all {N_DRAWS} draws.</p>
      <div class="tbl-wrap">
        <table>
          <thead><tr><th class="tc">#</th><th class="tc">Seed</th><th>Avg hits</th><th>Lift %</th><th>6-hits</th><th>0-hits</th></tr></thead>
          <tbody>{rows_by_avg_html}</tbody>
        </table>
      </div>
    </div>
    <div class="section">
      <h2>Top {TOP_N} seeds by 6-hit count</h2>
      <p class="desc">Most perfect-match (all 6 numbers) draws out of {N_DRAWS}.</p>
      <div class="tbl-wrap">
        <table>
          <thead><tr><th class="tc">#</th><th class="tc">Seed</th><th>Avg hits</th><th>Lift %</th><th>6-hits</th><th>0-hits</th></tr></thead>
          <tbody>{rows_by_hit6_html}</tbody>
        </table>
      </div>
    </div>
  </div>

  <p class="footer">
    Xoshiro256** (seeded via SplitMix64): picks = partial Fisher-Yates(range(1,44), {K_PICKS}) with combined seed = seed×10⁷ + draw_serial.
    Algorithm verified against independent reference sources (rand_xoshiro Rust crate test vector, randomgen Python library with direct
    state injection) before running — see <a href="/xoshiro_seed_backtest.html" style="color:#64748b">the 0–1000 seed page</a> for full
    verification details.<br>
    Data read live from <code>{TABLE}</code> in <code>loto6_local.db</code>, populated by a parallelized background scan
    (7 workers, ~15 minutes) in a prior session.<br>
    Formula-based only · Not financial advice · Loto 6 is random.
  </p>
</div>

<script>
new Chart(document.getElementById('hit6Chart').getContext('2d'), {{
  type: 'bar',
  data: {{
    labels: {hit6_labels_json},
    datasets: [{{
      label: 'Seeds',
      data: {hit6_values_json},
      backgroundColor: 'rgba(56,189,248,0.65)',
      borderColor: '#38bdf8',
      borderWidth: 1,
    }}]
  }},
  options: {{
    responsive: true,
    maintainAspectRatio: false,
    plugins: {{
      legend: {{ display: false }},
      tooltip: {{ callbacks: {{ label: function(ctx) {{ return ctx.parsed.y.toLocaleString() + ' seeds'; }} }} }}
    }},
    scales: {{
      y: {{ beginAtZero: true, ticks: {{ color: '#64748b' }}, grid: {{ color: '#1e293b' }}, title: {{ display: true, text: '# of seeds', color: '#64748b' }} }},
      x: {{ ticks: {{ color: '#64748b', maxTicksLimit: 15 }}, grid: {{ display: false }}, title: {{ display: true, text: '6-hit draws out of {N_DRAWS}', color: '#64748b' }} }}
    }}
  }}
}});
new Chart(document.getElementById('hit0Chart').getContext('2d'), {{
  type: 'bar',
  data: {{
    labels: {hit0_labels_json},
    datasets: [{{
      label: 'Seeds',
      data: {hit0_values_json},
      backgroundColor: 'rgba(239,68,68,0.55)',
      borderColor: '#ef4444',
      borderWidth: 1,
    }}]
  }},
  options: {{
    responsive: true,
    maintainAspectRatio: false,
    plugins: {{
      legend: {{ display: false }},
      tooltip: {{ callbacks: {{ label: function(ctx) {{ return ctx.parsed.y.toLocaleString() + ' seeds'; }} }} }}
    }},
    scales: {{
      y: {{ beginAtZero: true, ticks: {{ color: '#64748b' }}, grid: {{ color: '#1e293b' }}, title: {{ display: true, text: '# of seeds', color: '#64748b' }} }},
      x: {{ ticks: {{ color: '#64748b', maxTicksLimit: 15 }}, grid: {{ display: false }}, title: {{ display: true, text: '0-hit draws out of {N_DRAWS}', color: '#64748b' }} }}
    }}
  }}
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
