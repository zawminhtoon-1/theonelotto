"""
gen_random_seed_backtest.py
---------------------------
Static report page for the Random Seed Backtest: seeds -1,236,700 to
1,236,700 (2,473,401 seeds -- a 100x expansion of the previous
-12,376..12,376 range), K=17 picks via Python's seeded random.Random
(seed*10_000_000+draw_serial -> sorted(rng.sample(range(1,44), 17))),
draws #1001-2129 (1129 draws).

DB-backed design (mirrors the seed_hit_xoshiro_k33/k35/k38 pages): at
this scale, embedding every seed as an HTML table row would produce a
~730MB page that will not load in a browser (the old 24,753-seed version
was ~8MB). Instead this generator reads only aggregate stats and a
top-25 ranked table from loto6_local.db's seed_hit_random_k17 table
(populated by random_seed_scan_k17_full.py). Arbitrary-seed lookups
(including negative seeds, per the K=35 page's precedent) are handled by
a client-side "seed detail lookup" box that recomputes any seed's 17
picks per draw LIVE in the browser, via a bit-exact JavaScript port of
CPython's actual Mersenne Twister seeding (random_seed's abs-value +
init_by_array) and its real random.sample() pool-method algorithm --
verified against 65+ independently Python-computed reference cases
(including negative seeds and both range boundaries) before ever being
trusted, and re-verified live for the historically-buggy seed #294/draw
#2123 case. This port previously replaced an unrelated, incompatible
PRNG (mulberry32 + a hand-rolled Fisher-Yates) that used to run in the
modal, which caused the table and modal to disagree.

"Best seed" ranking: highest hit6b (6-hit + bonus) count first, tiebreak
highest hit6 (6-hit, any bonus), tiebreak highest hit5 (exactly 5-hit) --
the same convention used on every xoshiro seed-scan page on this site.

Output: public/random_seed_backtest.html
Run: python gen_random_seed_backtest.py
"""
import sqlite3, json, re, random, math, os
from collections import Counter

BASE      = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
ENV_LOCAL = BASE + r"\.env.local"
DB_PATH   = BASE + r"\loto6_local.db"
HTML_OUT  = BASE + r"\public\random_seed_backtest.html"
TABLE     = "seed_hit_random_k17"

K_PICKS   = 17
DRAW_START, DRAW_END = 1001, 2129
N_DRAWS   = DRAW_END - DRAW_START + 1  # 1129
SEED_LO, SEED_HI = -1_236_700, 1_236_700
LOTO6_MAX = 43
TOP_N = 25
BASELINE = K_PICKS * 6 / LOTO6_MAX  # expected hits by pure chance

def random_predict(seed, draw_serial, k=K_PICKS):
    rng = random.Random(seed * 10_000_000 + draw_serial)
    return sorted(rng.sample(range(1, LOTO6_MAX + 1), k))

# ── Load aggregates + top-N from SQLite ──────────────────────────────────────
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute(f"SELECT COUNT(*) FROM {TABLE}")
num_seeds = cur.fetchone()[0]
expected_seeds = SEED_HI - SEED_LO + 1
if num_seeds != expected_seeds:
    raise SystemExit(f"Expected {expected_seeds:,} rows in {TABLE}, found {num_seeds:,}")

cur.execute(f"""SELECT seed, hit6b_count, hit6_count, hit5_count, hit4_count, hit0_count, total_hits, bonus_hits
                FROM {TABLE} ORDER BY hit6b_count DESC, hit6_count DESC, hit5_count DESC, seed ASC LIMIT {TOP_N}""")
top_ranked = cur.fetchall()
best = top_ranked[0]

cur.execute(f"""SELECT seed, hit0_count, hit6b_count, hit6_count, hit5_count, total_hits, bonus_hits
                FROM {TABLE} ORDER BY hit0_count DESC, seed ASC LIMIT 1""")
worst_coverage = cur.fetchone()

cur.execute(f"SELECT AVG(hit0_count) FROM {TABLE}")
hit0_mean = cur.fetchone()[0]

cur.execute(f"""SELECT seed, hit6_count, total_hits FROM {TABLE}
                ORDER BY hit6_count DESC, seed ASC LIMIT 1""")
best_hit6_row = cur.fetchone()

cur.execute(f"SELECT hit6b_count, hit6_count, hit5_count, hit0_count FROM {TABLE}")
dist_rows = cur.fetchall()
conn.close()

hit6b_dist = Counter(r[0] for r in dist_rows)
hit6_dist  = Counter(r[1] for r in dist_rows)
hit5_dist  = Counter(r[2] for r in dist_rows)
hit0_dist  = Counter(r[3] for r in dist_rows)

def dist_labels_values(dist):
    labels = list(range(min(dist), max(dist) + 1))
    values = [dist.get(n, 0) for n in labels]
    return labels, values

hit6b_labels, hit6b_values = dist_labels_values(hit6b_dist)
hit6_labels, hit6_values   = dist_labels_values(hit6_dist)
hit5_labels, hit5_values   = dist_labels_values(hit5_dist)
hit0_labels, hit0_values   = dist_labels_values(hit0_dist)

print(f"Loaded {num_seeds:,} seeds from {TABLE}")
print(f"Best (hit6b>hit6>hit5): seed={best[0]:,} hit6b={best[1]} hit6={best[2]} hit5={best[3]} hit4={best[4]} hit0={best[5]}")
print(f"Worst-coverage: seed={worst_coverage[0]:,} hit0={worst_coverage[1]} (mean hit0 across all seeds: {hit0_mean:.2f})")

# ── Load the exact #1001-2129 draw window from the production DB, for the
# client-side seed-detail lookup / next-draw prediction. ────────────────────
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
print(f"Loaded {len(DRAWS)} draw records for the client-side lookup (#{DRAWS[0]['s']}-{DRAWS[-1]['s']}).")

next_serial = DRAWS[-1]['s'] + 1
next_picks = random_predict(best[0], next_serial)

# ── Top-N table rows ──────────────────────────────────────────────────────
def render_rows(rows, highlight_seed=None):
    html = ""
    for rank, (seed, hit6b, hit6, hit5, hit4, hit0, total_hits, bonus_hits) in enumerate(rows, 1):
        avg = total_hits / N_DRAWS
        lift = (avg / BASELINE - 1) * 100
        lift_color = "#22c55e" if lift > 0 else "#ef4444"
        badge = ' <span class="badge">BEST</span>' if seed == highlight_seed else ''
        html += f"""<tr class="dr" onclick="openSeedDetail({seed})">
  <td class="tc">{rank}</td>
  <td class="tc">{seed:,}{badge}</td>
  <td class="tr">{hit6b}</td>
  <td class="tr">{hit6}</td>
  <td class="tr">{hit5}</td>
  <td class="tr">{hit4}</td>
  <td class="tr">{hit0}</td>
  <td class="tr">{avg:.4f}</td>
  <td class="tr" style="color:{lift_color}">{lift:+.1f}%</td>
  <td class="tr">{bonus_hits}</td>
</tr>"""
    return html

rows_html = render_rows(top_ranked, highlight_seed=best[0])

hit6b_labels_json = json.dumps(hit6b_labels)
hit6b_values_json = json.dumps(hit6b_values)
hit6_labels_json = json.dumps(hit6_labels)
hit6_values_json = json.dumps(hit6_values)
hit5_labels_json = json.dumps(hit5_labels)
hit5_values_json = json.dumps(hit5_values)
hit0_labels_json = json.dumps(hit0_labels)
hit0_values_json = json.dumps(hit0_values)

page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Random Seed Backtest (±1,236,700) — Loto 6</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0a0f1e;color:#e2e8f0;font-family:system-ui,sans-serif;padding-top:60px;min-height:100vh}}
.wrap{{max-width:1200px;margin:0 auto;padding:24px 16px}}
h1{{font-size:1.4rem;font-weight:700;color:#f1f5f9;margin-bottom:4px}}
.subtitle{{font-size:.85rem;color:#64748b;margin-bottom:20px}}

.note{{background:#0d1526;border:1px solid #1e293b;border-radius:10px;padding:14px 18px;
  font-size:.8rem;color:#94a3b8;margin-bottom:20px;line-height:1.6}}
.note strong{{color:#e2e8f0}}

.lookup{{background:#0d1526;border:1px solid #f59e0b55;border-radius:10px;padding:14px 18px;margin-bottom:24px;display:flex;gap:10px;align-items:center;flex-wrap:wrap}}
.lookup .lbl{{font-size:.72rem;color:#f59e0b;text-transform:uppercase;letter-spacing:.06em;font-weight:700;margin-right:4px}}
.lookup input{{background:#0a0f1e;border:1px solid #334155;border-radius:7px;padding:8px 12px;
  color:#e2e8f0;font-size:.85rem;width:180px}}
.lookup button{{background:#d97706;border:none;color:#fff;padding:8px 16px;border-radius:7px;
  cursor:pointer;font-size:.83rem;font-weight:600}}
.lookup button:hover{{background:#b45309}}
.lookup .hint{{font-size:.78rem;color:#64748b}}
.lookup .err{{font-size:.78rem;color:#f87171}}

.stats-row{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:24px}}
.stat-card{{background:#0d1526;border:1px solid #1e293b;border-radius:10px;padding:14px 18px;flex:1;min-width:150px}}
.stat-card .lbl{{font-size:.72rem;color:#64748b;text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px}}
.stat-card .val{{font-size:1.4rem;font-weight:700;color:#f1f5f9}}
.stat-card .sub{{font-size:.78rem;color:#94a3b8;margin-top:2px}}

.next-pred{{background:#0d1526;border:1px solid #f59e0b55;border-radius:10px;padding:16px 18px;margin-bottom:24px}}
.next-pred .lbl{{font-size:.72rem;color:#f59e0b;text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px}}
.balls{{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}}
.ball{{width:34px;height:34px;border-radius:50%;background:#1e3a5f;display:flex;align-items:center;
  justify-content:center;font-weight:700;font-size:.85rem;color:#93c5fd;border:1px solid #2563eb55}}

.section{{background:#0d1526;border:1px solid #1e293b;border-radius:12px;padding:20px;margin-bottom:24px}}
.section h2{{font-size:1rem;font-weight:700;color:#f1f5f9;margin-bottom:4px}}
.section .desc{{font-size:.8rem;color:#64748b;margin-bottom:16px}}
.chart-wrap{{height:230px;position:relative}}

.four-col{{display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:16px}}
@media (max-width: 1200px){{.four-col{{grid-template-columns:1fr 1fr}}}}
@media (max-width: 640px){{.four-col{{grid-template-columns:1fr}}}}

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

#seedModal{{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.82);z-index:20000;align-items:flex-start;justify-content:center;padding:60px 16px 20px}}
.modal-box{{background:#0a0f1e;border:1px solid #1e293b;border-radius:12px;width:100%;max-width:1000px;max-height:85vh;display:flex;flex-direction:column}}
.modal-hdr{{display:flex;justify-content:space-between;align-items:center;padding:14px 18px;border-bottom:1px solid #1e293b;flex-shrink:0;gap:16px;flex-wrap:wrap}}
.modal-hdr h2{{font-size:.95rem;font-weight:700;color:#f1f5f9;margin:0}}
.modal-hdr .modal-stats{{font-size:.78rem;color:#94a3b8}}
.modal-close{{background:#1e293b;border:none;color:#94a3b8;padding:5px 14px;border-radius:6px;cursor:pointer;font-size:.83rem}}
.modal-close:hover{{background:#334155;color:#f1f5f9}}
.modal-body{{overflow-y:auto;flex:1}}
.modal-table{{width:100%;border-collapse:collapse;font-size:.78rem}}
.modal-table thead{{position:sticky;top:0;background:#0a0f1e;z-index:1}}
.modal-table th{{padding:9px 12px;color:#64748b;text-align:left;border-bottom:1px solid #1e293b;font-weight:600;font-size:.72rem;text-transform:uppercase;letter-spacing:.04em;white-space:nowrap}}
.modal-table td{{padding:6px 10px;border-bottom:1px solid #0f172a;vertical-align:middle}}
.modal-table tr:hover td{{background:#0f172a}}
.nb{{display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;border-radius:50%;background:#1e293b;color:#64748b;font-size:.7rem;font-weight:700;margin:1px}}
.nm{{background:#14532d;color:#86efac}}
.nb-b{{background:#451a03;color:#fde68a;border:1px solid #92400e}}
.nb-bh{{background:#7c2d12;color:#fed7aa}}

.footer{{margin-top:28px;font-size:.78rem;color:#475569;padding-bottom:20px;line-height:1.6}}
</style>
</head>
<body>

<script src="/site-nav.js"></script>
<div class="wrap">
  <h1>🎲 Random Seed Backtest (seeds -1,236,700 to 1,236,700)</h1>
  <p class="subtitle">{num_seeds:,} seeds · K={K_PICKS} picks · {N_DRAWS} draws (#{DRAW_START}–{DRAW_END}) · random baseline ≈ {BASELINE:.3f} avg hits</p>

  <div class="note">
    <strong>DB-backed design:</strong> this range is a 100x expansion of the previous ±12,376 scan. Embedding every
    seed as an HTML row (the old page's approach, ~8MB for 24,753 rows) would produce a ~730MB page at this scale,
    which will not load in a browser. Aggregate stats and the top {TOP_N} table below are read from
    <code>{TABLE}</code> in <code>loto6_local.db</code>; any other seed can be inspected via the lookup box, computed
    live in your browser. <strong>PRNG mismatch bug (previously documented) fixed:</strong> the lookup/modal runs a
    bit-exact JavaScript port of CPython's actual Mersenne Twister seeding (<code>random_seed</code>'s abs-value +
    <code>init_by_array</code>) and its real <code>random.sample()</code> pool-method algorithm — verified against
    65+ independently Python-computed reference cases (including negative seeds and both range boundaries) before
    use. It previously ran an unrelated PRNG (mulberry32 + a hand-rolled Fisher-Yates), which disagreed with the
    table for the same seed.
  </div>

  <div class="lookup">
    <span class="lbl">🔍 Seed detail lookup</span>
    <input id="seedLookupInput" type="number" step="1" placeholder="Enter any seed (negative OK)..." onkeydown="if(event.key==='Enter')lookupSeed()">
    <button onclick="lookupSeed()">View {N_DRAWS}-draw breakdown</button>
    <span class="hint">e.g. try {best[0]:,} (the top-ranked seed) or {worst_coverage[0]:,} (worst coverage) — or any seed in {SEED_LO:,} to {SEED_HI:,}. Computed live in your browser.</span>
    <span id="lookupErr" class="err" style="display:none"></span>
  </div>

  <div class="stats-row">
    <div class="stat-card">
      <div class="lbl">Best seed (hit6b→hit6→hit5)</div>
      <div class="val">#{best[0]:,}</div>
      <div class="sub">hit6b {best[1]} · hit6 {best[2]} · hit5 {best[3]}</div>
    </div>
    <div class="stat-card">
      <div class="lbl">Most 6-hit draws</div>
      <div class="val">{best_hit6_row[1]}</div>
      <div class="sub">seed #{best_hit6_row[0]:,}</div>
    </div>
    <div class="stat-card">
      <div class="lbl">Worst coverage (0-hit)</div>
      <div class="val">#{worst_coverage[0]:,}</div>
      <div class="sub">{worst_coverage[1]} zero-hit draws (mean {hit0_mean:.1f})</div>
    </div>
    <div class="stat-card">
      <div class="lbl">Baseline (pure chance)</div>
      <div class="val">{BASELINE:.3f}</div>
      <div class="sub">{K_PICKS} picks × 6 / 43</div>
    </div>
    <div class="stat-card">
      <div class="lbl">Seeds tested</div>
      <div class="val">{num_seeds:,}</div>
      <div class="sub">{SEED_LO:,} to {SEED_HI:,}</div>
    </div>
  </div>

  <div class="next-pred">
    <div class="lbl">🏆 Best seed #{best[0]:,} — predicted picks for draw #{next_serial}</div>
    <div class="balls">
      {''.join(f'<div class="ball">{n}</div>' for n in next_picks)}
    </div>
  </div>

  <div class="four-col">
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
    <div class="section">
      <h2>0-hit distribution</h2>
      <p class="desc">Zero-hit (worst coverage) draw count across all {num_seeds:,} seeds.</p>
      <div class="chart-wrap"><canvas id="hit0Chart"></canvas></div>
    </div>
  </div>

  <div class="section">
    <h2>Top {TOP_N} seeds (ranked: hit6b → hit6 → hit5)</h2>
    <p class="desc">Click a row for the full {N_DRAWS}-draw breakdown.</p>
    <div class="tbl-wrap">
      <table>
        <thead><tr>
          <th class="tc">#</th><th class="tc">Seed</th><th>hit6b</th><th>hit6</th><th>hit5</th>
          <th>4-hits</th><th>0-hits</th><th>Avg hits</th><th>Lift%</th><th>Bonus hits</th>
        </tr></thead>
        <tbody id="tbody">{rows_html}</tbody>
      </table>
    </div>
  </div>

  <p class="footer">
    Seeded random: picks = sorted(random.Random(seed×10⁷+draw_serial).sample(range(1,44), {K_PICKS})).<br>
    Each (seed, draw) pair is independent and deterministic. Lift = % above pure-chance baseline ({BASELINE:.3f} avg hits).<br>
    Seed range includes negative seeds; Python's random.Random(x) takes abs(x) before seeding Mersenne Twister, so the
    combined value (seed×10⁷+draw_serial, which can itself be negative) is what gets absolute-valued — verified this
    still produces seed-distinct sequences (not mirrored positive/negative pairs) since draw_serial is small relative
    to seed×10⁷.<br>
    Data read live from <code>{TABLE}</code> in <code>loto6_local.db</code> (populated by
    <code>random_seed_scan_k17_full.py</code>). Draw records for #{DRAW_START}–{DRAW_END} sourced directly from the
    production database, verified for exactly {N_DRAWS} consecutive rows with no gaps before scanning.<br>
    Formula-based only · Not financial advice · Loto 6 is random.
  </p>

  <div id="seedModal">
    <div class="modal-box">
      <div class="modal-hdr">
        <h2 id="modalTitle">Seed detail</h2>
        <div class="modal-stats" id="modalStats"></div>
        <button class="modal-close" onclick="document.getElementById('seedModal').style.display='none'">✕ Close</button>
      </div>
      <div class="modal-body">
        <table class="modal-table">
          <thead><tr>
            <th>Draw</th><th>Date</th>
            <th>Actual (6) + bonus</th>
            <th>Picks ({K_PICKS})</th>
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
        x: {{ ticks: {{ color: '#64748b', maxTicksLimit: 10 }}, grid: {{ display: false }} }}
      }}
    }}
  }});
}}
mkChart('hit6bChart', {hit6b_labels_json}, {hit6b_values_json}, '#38bdf8');
mkChart('hit6Chart', {hit6_labels_json}, {hit6_values_json}, '#22c55e');
mkChart('hit5Chart', {hit5_labels_json}, {hit5_values_json}, '#f59e0b');
mkChart('hit0Chart', {hit0_labels_json}, {hit0_values_json}, '#f87171');
</script>
<script>
// ── Seed-detail lookup: picks computed LIVE for any seed (including
// negative) via a bit-exact CPython MT19937 port -- not limited to the
// top-{TOP_N} table.
const DRAWS = {js_draws};
const SEED_LO = {SEED_LO}, SEED_HI = {SEED_HI};

// ── CPython-compatible MT19937 port (bit-exact random.Random + random.sample) ──
// Verified against 65+ independently Python-computed reference cases
// (including negative seeds and both range boundaries) before use here.
function imul32(a, b) {{ return Math.imul(a, b) >>> 0; }}
const MT_N = 624, MT_M = 397;
const MATRIX_A = 0x9908b0df, UPPER_MASK = 0x80000000, LOWER_MASK = 0x7fffffff;
function MT19937() {{ this.mt = new Uint32Array(MT_N); this.mti = MT_N + 1; }}
MT19937.prototype.initGenrand = function (s) {{
  this.mt[0] = s >>> 0;
  for (let i = 1; i < MT_N; i++) {{
    const prev = this.mt[i - 1] ^ (this.mt[i - 1] >>> 30);
    this.mt[i] = (imul32(1812433253, prev) + i) >>> 0;
  }}
  this.mti = MT_N;
}};
MT19937.prototype.initByArray = function (initKey) {{
  this.initGenrand(19650218);
  let i = 1, j = 0, k = Math.max(MT_N, initKey.length);
  for (; k; k--) {{
    const prev = this.mt[i - 1] ^ (this.mt[i - 1] >>> 30);
    this.mt[i] = ((this.mt[i] ^ imul32(prev, 1664525)) + initKey[j] + j) >>> 0;
    i++; j++;
    if (i >= MT_N) {{ this.mt[0] = this.mt[MT_N - 1]; i = 1; }}
    if (j >= initKey.length) j = 0;
  }}
  for (k = MT_N - 1; k; k--) {{
    const prev = this.mt[i - 1] ^ (this.mt[i - 1] >>> 30);
    this.mt[i] = ((this.mt[i] ^ imul32(prev, 1566083941)) - i) >>> 0;
    i++;
    if (i >= MT_N) {{ this.mt[0] = this.mt[MT_N - 1]; i = 1; }}
  }}
  this.mt[0] = 0x80000000;
}};
MT19937.prototype.genrandUint32 = function () {{
  const mag01 = [0, MATRIX_A]; let y;
  if (this.mti >= MT_N) {{
    let kk;
    for (kk = 0; kk < MT_N - MT_M; kk++) {{
      y = (this.mt[kk] & UPPER_MASK) | (this.mt[kk + 1] & LOWER_MASK);
      this.mt[kk] = this.mt[kk + MT_M] ^ (y >>> 1) ^ mag01[y & 1];
    }}
    for (; kk < MT_N - 1; kk++) {{
      y = (this.mt[kk] & UPPER_MASK) | (this.mt[kk + 1] & LOWER_MASK);
      this.mt[kk] = this.mt[kk + (MT_M - MT_N)] ^ (y >>> 1) ^ mag01[y & 1];
    }}
    y = (this.mt[MT_N - 1] & UPPER_MASK) | (this.mt[0] & LOWER_MASK);
    this.mt[MT_N - 1] = this.mt[MT_M - 1] ^ (y >>> 1) ^ mag01[y & 1];
    this.mti = 0;
  }}
  y = this.mt[this.mti++];
  y ^= (y >>> 11); y ^= (y << 7) & 0x9d2c5680; y ^= (y << 15) & 0xefc60000; y ^= (y >>> 18);
  return y >>> 0;
}};
function pythonSeedKey(seedBigInt) {{
  let n = seedBigInt < 0n ? -seedBigInt : seedBigInt;
  if (n === 0n) return [0];
  let bits = 0; {{ let tmp = n; while (tmp > 0n) {{ bits++; tmp >>= 1n; }} }}
  const keymax = Math.floor((bits - 1) / 32) + 1;
  const words = [];
  for (let i = 0; i < keymax; i++) {{ words.push(Number(n & 0xffffffffn)); n >>= 32n; }}
  return words;
}}
function pythonRandomSeed(combinedBigInt) {{
  const key = pythonSeedKey(combinedBigInt);
  const mt = new MT19937(); mt.initByArray(key); return mt;
}}
function bitLength(n) {{ return 32 - Math.clz32(n); }}
function getrandbits(mt, k) {{ return mt.genrandUint32() >>> (32 - k); }}
function randbelow(mt, n) {{
  if (n <= 0) return 0;
  const k = bitLength(n); let r = getrandbits(mt, k);
  while (r >= n) r = getrandbits(mt, k);
  return r;
}}
function pythonSample(mt, n, k) {{
  const pool = Array.from({{ length: n }}, (_, i) => i + 1);
  const result = new Array(k);
  for (let i = 0; i < k; i++) {{
    const j = randbelow(mt, n - i);
    result[i] = pool[j]; pool[j] = pool[n - i - 1];
  }}
  return result;
}}
function randomPredict(seed, drawSerial, k) {{
  const combined = BigInt(seed) * 10000000n + BigInt(drawSerial);
  const mt = pythonRandomSeed(combined);
  return pythonSample(mt, 43, k).sort((a, b) => a - b);
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
  const seed = parseInt(raw, 10);
  if (seed < SEED_LO || seed > SEED_HI) {{
    errEl.textContent = 'Seed must be between ' + SEED_LO.toLocaleString() + ' and ' + SEED_HI.toLocaleString() + '.';
    errEl.style.display = 'inline';
    return;
  }}
  openSeedDetail(seed);
}}

function openSeedDetail(seed) {{
  const K = {K_PICKS};
  document.getElementById('modalTitle').textContent = 'Seed #' + seed.toLocaleString() + ' — ' + DRAWS.length + ' draws (K=' + K + ')';

  let hit6b = 0, hit6 = 0, hit5 = 0, hit4 = 0, hit0 = 0, bonusHits = 0, totalHits = 0;
  const htmlParts = [];
  [...DRAWS].reverse().forEach(row => {{
    const picks = randomPredict(seed, row.s, K);
    const actualSet = new Set(row.a);
    const picksSet = new Set(picks);
    const hits = picks.filter(p => actualSet.has(p)).length;
    const bh   = picksSet.has(row.b);
    totalHits += hits;
    if (bh) {{ bonusHits++; if (hits === 6) hit6b++; }}
    if (hits === 6) hit6++; else if (hits === 5) hit5++; else if (hits === 4) hit4++; else if (hits === 0) hit0++;

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
      '<td style="text-align:center;font-weight:700;color:' + hc + '">' + hits + (bh ? '<span style="color:#f59e0b;font-size:.7rem">+B</span>' : '') + '</td></tr>'
    );
  }});
  const avg = (totalHits / DRAWS.length).toFixed(4);
  document.getElementById('modalStats').innerHTML =
    'hit6b: <b>' + hit6b + '</b> &nbsp;·&nbsp; hit6: <b>' + hit6 + '</b> &nbsp;·&nbsp; hit5: <b>' + hit5 + '</b> &nbsp;·&nbsp; avg: <b>' + avg + '</b> &nbsp;·&nbsp; 4-hit: <b>' + hit4 + '</b> &nbsp;·&nbsp; 0-hit: <b>' + hit0 + '</b> &nbsp;·&nbsp; bonus: <b>' + bonusHits + '</b>';
  document.getElementById('modalTbody').innerHTML = htmlParts.join('');
  document.getElementById('seedModal').style.display = 'flex';
}}

document.getElementById('seedModal').addEventListener('click', function(e) {{
  if (e.target === this) this.style.display = 'none';
}});
document.addEventListener('keydown', function(e) {{
  if (e.key === 'Escape') document.getElementById('seedModal').style.display = 'none';
}});
</script>
</body>
</html>"""

with open(HTML_OUT, 'w', encoding='utf-8') as f:
    f.write(page)
print(f"\nWrote {HTML_OUT} ({len(page)//1024} KB)")
print(f"Best seed: #{best[0]:,} hit6b={best[1]} hit6={best[2]} hit5={best[3]}")
print(f"Worst-coverage seed: #{worst_coverage[0]:,} hit0={worst_coverage[1]}")
print(f"Predicted picks for draw #{next_serial}: {next_picks}")
