"""
gen_xoshiro_seed_scan_loto7_k25.py
--------------------------------------
Static report page for Loto7's first xoshiro256** seed scan: seeds
0-10,000, K=25 picks, backtested against the FIRST 500 Loto7 draws
(#1-500) -- mirroring the Loto6 xoshiro K-value scan pages
(gen_xoshiro_seed_scan_k33.py) but reparameterized for Loto7's 37-
number pool and 2 bonus numbers.

Reads live from loto7_local.db's seed_hit_xoshiro_k25 table for
aggregates and the top-N table. Draw records for the client-side
seed-detail modal are pulled directly from loto7_results (Neon
Postgres), same live-lookup pattern as the Loto6 page.

Ranking (hit7b -> hit7 -> hit6 -> hit5 -> hit4): hit7b = all 7 main
numbers hit AND at least one of the 2 bonus numbers also in the pick
-- "either bonus", matching the convention already established for
Loto7 on precompute_loto7_backtest100_multik.py.

Output: public/xoshiro_seed_scan_loto7_k25.html
Run: python gen_xoshiro_seed_scan_loto7_k25.py
"""
import sqlite3, json, re, math, os
from collections import Counter

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
DB_PATH = BASE + r"\loto7_local.db"
ENV_LOCAL = BASE + r"\.env.local"
HTML_OUT = BASE + r"\public\xoshiro_seed_scan_loto7_k25.html"
TABLE = "seed_hit_xoshiro_k25"

K_PICKS = 25
LOTO7_MAX = 37
DRAW_START, DRAW_END = 1, 500
N_DRAWS = DRAW_END - DRAW_START + 1  # 500
NUM_SEEDS_EXPECTED = 10_001
TOP_N = 25

# ── Load aggregates + top-N from SQLite ──────────────────────────────────────
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute(f"SELECT COUNT(*) FROM {TABLE}")
num_seeds = cur.fetchone()[0]
if num_seeds != NUM_SEEDS_EXPECTED:
    raise SystemExit(f"Expected {NUM_SEEDS_EXPECTED:,} rows in {TABLE}, found {num_seeds}")

cur.execute(f"SELECT seed, hit7b_count, hit7_count, hit6_count, hit5_count, hit4_count FROM {TABLE}")
all_rows = cur.fetchall()

cur.execute(f"""SELECT seed, hit7b_count, hit7_count, hit6_count, hit5_count, hit4_count FROM {TABLE}
                ORDER BY hit7b_count DESC, hit7_count DESC, hit6_count DESC, hit5_count DESC, hit4_count DESC, seed ASC LIMIT {TOP_N}""")
top_ranked = cur.fetchall()

conn.close()
best = top_ranked[0]
top3 = top_ranked[:3]

# ── Aggregate distributions ──────────────────────────────────────────────────
hit7b_dist = Counter(r[1] for r in all_rows)
hit7_dist  = Counter(r[2] for r in all_rows)
hit6_dist  = Counter(r[3] for r in all_rows)
hit5_dist  = Counter(r[4] for r in all_rows)
hit4_dist  = Counter(r[5] for r in all_rows)

def dist_arrays(dist):
    labels = list(range(min(dist), max(dist) + 1))
    values = [dist.get(n, 0) for n in labels]
    return labels, values

hit7b_labels, hit7b_values = dist_arrays(hit7b_dist)
hit7_labels, hit7_values = dist_arrays(hit7_dist)
hit6_labels, hit6_values = dist_arrays(hit6_dist)
hit5_labels, hit5_values = dist_arrays(hit5_dist)
hit4_labels, hit4_values = dist_arrays(hit4_dist)

# ── Analytical hypergeometric baselines (pure-chance expectation) ───────────
def hyper_pmf(x, pool, success, draws):
    return (math.comb(success, x) * math.comb(pool - success, draws - x)) / math.comb(pool, draws)

p_hit7_only = hyper_pmf(7, LOTO7_MAX, 7, K_PICKS)
remaining_pool = LOTO7_MAX - 7
remaining_picks = K_PICKS - 7
p_neither_bonus = math.comb(remaining_pool - 2, remaining_picks) / math.comb(remaining_pool, remaining_picks)
p_hit7b = p_hit7_only * (1 - p_neither_bonus)
p_hit6 = hyper_pmf(6, LOTO7_MAX, 7, K_PICKS)
p_hit5 = hyper_pmf(5, LOTO7_MAX, 7, K_PICKS)
p_hit4 = hyper_pmf(4, LOTO7_MAX, 7, K_PICKS)

exp_hit7b = p_hit7b * N_DRAWS
exp_hit7 = p_hit7_only * N_DRAWS
exp_hit6 = p_hit6 * N_DRAWS
exp_hit5 = p_hit5 * N_DRAWS
exp_hit4 = p_hit4 * N_DRAWS

print(f"Loaded {num_seeds:,} seeds from {TABLE}")
print(f"Best: seed={best[0]} hit7b={best[1]} hit7={best[2]} hit6={best[3]} hit5={best[4]} hit4={best[5]}")
print(f"Analytical expectation: hit7b~={exp_hit7b:.3f} hit7~={exp_hit7:.2f} hit6~={exp_hit6:.2f} "
      f"hit5~={exp_hit5:.2f} hit4~={exp_hit4:.2f} (of {N_DRAWS} draws)")
print(f"Top 3: {[(r[0], r[1], r[2], r[3], r[4], r[5]) for r in top3]}")

# ── Load draw window #1-500 from the production DB, for the client-side
# seed-detail modal. ────────────────────────────────────────────────────────
if 'DATABASE_URL' not in os.environ:
    with open(ENV_LOCAL, encoding='utf-8') as f:
        env_text = f.read()
    m = re.search(r'DATABASE_URL=(.+)', env_text)
    os.environ['DATABASE_URL'] = m.group(1).strip()

import psycopg2
pg = psycopg2.connect(os.environ['DATABASE_URL'])
pgcur = pg.cursor()
pgcur.execute(
    "SELECT draw_serial, draw_date, num1,num2,num3,num4,num5,num6,num7, bonus1, bonus2 "
    "FROM loto7_results WHERE draw_serial BETWEEN %s AND %s ORDER BY draw_serial",
    (DRAW_START, DRAW_END),
)
pg_rows = pgcur.fetchall()
pg.close()
if len(pg_rows) != N_DRAWS:
    raise SystemExit(f"Draw window mismatch: got {len(pg_rows)} rows, expected {N_DRAWS}")
DRAWS = [{'s': r[0], 'd': r[1].isoformat() if r[1] else None, 'a': list(r[2:9]), 'b1': r[9], 'b2': r[10]} for r in pg_rows]
js_draws = json.dumps(DRAWS, separators=(',', ':'))
print(f"Loaded {len(DRAWS)} draw records for the client-side modal (#{DRAWS[0]['s']}-{DRAWS[-1]['s']}).")

# ── Table rows ────────────────────────────────────────────────────────────
def render_rows(rows, highlight_seed=None, top3_seeds=()):
    html = ""
    for rank, (seed, hit7b, hit7, hit6, hit5, hit4) in enumerate(rows, 1):
        badge = ' <span class="badge">BEST</span>' if seed == highlight_seed else (' <span class="badge3">TOP 3</span>' if seed in top3_seeds and seed != highlight_seed else '')
        html += f"""<tr class="dr" onclick="openSeedDetail({seed})">
  <td class="tc">{rank}</td>
  <td class="tc">{seed:,}{badge}</td>
  <td class="tr">{hit7b}</td>
  <td class="tr">{hit7}</td>
  <td class="tr">{hit6}</td>
  <td class="tr">{hit5}</td>
  <td class="tr">{hit4}</td>
</tr>"""
    return html

top3_seed_set = set(r[0] for r in top3)
rows_html = render_rows(top_ranked, highlight_seed=best[0], top3_seeds=top3_seed_set)

top3_summary_html = ""
for i, row in enumerate(top3, 1):
    top3_summary_html += f"""<div class="stat-card{' final' if i == 1 else ''}">
      <div class="lbl">#{i} seed</div>
      <div class="val">#{row[0]:,}</div>
      <div class="sub">hit7b {row[1]} &middot; hit7 {row[2]} &middot; hit6 {row[3]} &middot; hit5 {row[4]} &middot; hit4 {row[5]}</div>
    </div>"""

page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Xoshiro Seed Scan K=25 (0-10,000) — Loto 7</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>

*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0a0f1e;color:#e2e8f0;font-family:system-ui,sans-serif;padding-top:60px;min-height:100vh}}
.wrap{{max-width:1200px;margin:0 auto;padding:24px 16px}}
h1{{font-size:1.4rem;font-weight:700;color:#f1f5f9;margin-bottom:4px}}
.subtitle{{font-size:.85rem;color:#64748b;margin-bottom:20px}}

.note{{background:#0d1526;border:1px solid #1e293b;border-radius:10px;padding:14px 18px;
  font-size:.8rem;color:#94a3b8;margin-bottom:20px;line-height:1.6}}

.stats-row{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:24px}}
.stat-card{{background:#0d1526;border:1px solid #1e293b;border-radius:10px;padding:14px 18px;flex:1;min-width:160px}}
.stat-card.final{{border-color:#a78bfa88}}
.stat-card .lbl{{font-size:.72rem;color:#64748b;text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px}}
.stat-card .val{{font-size:1.4rem;font-weight:700;color:#f1f5f9}}
.stat-card .sub{{font-size:.78rem;color:#94a3b8;margin-top:2px}}

.section{{background:#0d1526;border:1px solid #1e293b;border-radius:12px;padding:20px;margin-bottom:24px}}
.section h2{{font-size:1rem;font-weight:700;color:#f1f5f9;margin-bottom:4px}}
.section .desc{{font-size:.8rem;color:#64748b;margin-bottom:16px}}
.chart-wrap{{height:230px;position:relative}}

.five-col{{display:grid;grid-template-columns:repeat(5,1fr);gap:14px}}
@media (max-width: 1100px){{.five-col{{grid-template-columns:repeat(3,1fr)}}}}
@media (max-width: 700px){{.five-col{{grid-template-columns:1fr}}}}

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
.badge3{{background:#a78bfa;color:#2e1065;font-size:9px;padding:2px 6px;border-radius:4px;margin-left:4px;font-weight:700}}

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

.footer{{margin-top:28px;font-size:.78rem;color:#475569;padding-bottom:20px;line-height:1.6}}
</style>
</head>
<body>

<div class="wrap">
  <h1>🎯 Xoshiro Seed Scan — Loto 7 K=25 (0–10,000)</h1>
  <p class="subtitle">{num_seeds:,} seeds &middot; K={K_PICKS} picks (pool 1&ndash;{LOTO7_MAX}) &middot; {N_DRAWS} draws (#{DRAW_START}&ndash;{DRAW_END}) &middot; xoshiro256** (SplitMix64-seeded)</p>

  <div class="note">
    First xoshiro256** seed scan for Loto7 &mdash; starting range, seeds 0&ndash;10,000, likely to be extended later
    (same iterative pattern as the Loto6 xoshiro scans, e.g. <a href="/xoshiro_seed_scan_k33.html" style="color:#a78bfa">the K=33 Loto6 scan</a>,
    which started at 0&ndash;1,000 and grew to 0&ndash;1,000,000). Same xoshiro256**/SplitMix64 algorithm and combined-seed
    formula (<code>seed&times;10,000,000 + draw_serial</code>) reused exactly from the Loto6 scans, reparameterized for
    Loto7's 37-number pool (not 43) and K={K_PICKS} picks (not 33). Backtested against the <b>FIRST</b> {N_DRAWS} Loto7
    draws (#{DRAW_START}&ndash;{DRAW_END}) &mdash; not the most recent.
    <br><br>
    Loto7 draws 7 main numbers plus <b>2</b> bonus numbers (not 1, confirmed from the <code>loto7_results</code> schema).
    Five metrics tracked per seed, matching the ranking convention already established for Loto7 on
    <a href="/loto7_backtest100_multik.html" style="color:#a78bfa">the 100-draw multi-K backtest</a> (one tier deeper
    than Loto6's hit6b&rarr;hit6&rarr;hit5, since Loto7 has 7 main numbers): <b>hit7b</b> = draws where the {K_PICKS}
    picks contain all 7 main winning numbers <em>and</em> at least one of the two bonus numbers ("either bonus", not
    "both"); <b>hit7</b> = all 7 main numbers hit (any bonus); <b>hit6</b>/<b>hit5</b>/<b>hit4</b> = exactly 6, 5, or 4
    of the 7 main numbers hit. Ranking: highest hit7b, tiebreak hit7, then hit6, then hit5, then hit4.
  </div>

  <div class="lookup">
    <span class="lbl">🔍 Seed detail lookup</span>
    <input id="seedLookupInput" type="number" min="0" step="1" placeholder="Enter any seed number..." onkeydown="if(event.key==='Enter')lookupSeed()">
    <button onclick="lookupSeed()">View {N_DRAWS}-draw breakdown</button>
    <span class="hint">e.g. try {best[0]:,} (the top-ranked seed) — or any seed 0–10,000. Computed live in your browser.</span>
    <span id="lookupErr" class="err" style="display:none"></span>
  </div>

  <div class="section">
    <h2>Best 3 seeds</h2>
    <p class="desc">Ranked hit7b &rarr; hit7 &rarr; hit6 &rarr; hit5 &rarr; hit4.</p>
    <div class="stats-row">{top3_summary_html}</div>
  </div>

  <div class="stats-row">
    <div class="stat-card">
      <div class="lbl">Expected hit7b (chance)</div>
      <div class="val">{exp_hit7b:.2f}</div>
      <div class="sub">hypergeometric, per seed</div>
    </div>
    <div class="stat-card">
      <div class="lbl">Expected hit7 (chance)</div>
      <div class="val">{exp_hit7:.1f}</div>
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
      <div class="sub">seeds 0–10,000</div>
    </div>
  </div>

  <div class="five-col">
    <div class="section">
      <h2>hit7b</h2>
      <p class="desc">7-hit + either bonus.</p>
      <div class="chart-wrap"><canvas id="hit7bChart"></canvas></div>
    </div>
    <div class="section">
      <h2>hit7</h2>
      <p class="desc">All 7 main, any bonus.</p>
      <div class="chart-wrap"><canvas id="hit7Chart"></canvas></div>
    </div>
    <div class="section">
      <h2>hit6</h2>
      <p class="desc">Exactly 6 of 7 main.</p>
      <div class="chart-wrap"><canvas id="hit6Chart"></canvas></div>
    </div>
    <div class="section">
      <h2>hit5</h2>
      <p class="desc">Exactly 5 of 7 main.</p>
      <div class="chart-wrap"><canvas id="hit5Chart"></canvas></div>
    </div>
    <div class="section">
      <h2>hit4</h2>
      <p class="desc">Exactly 4 of 7 main.</p>
      <div class="chart-wrap"><canvas id="hit4Chart"></canvas></div>
    </div>
  </div>

  <div class="section">
    <h2>Top {TOP_N} seeds (ranked: hit7b → hit7 → hit6 → hit5 → hit4)</h2>
    <p class="desc">Click a row for the full {N_DRAWS}-draw breakdown.</p>
    <div class="tbl-wrap">
      <table>
        <thead><tr><th class="tc">#</th><th class="tc">Seed</th><th>hit7b</th><th>hit7</th><th>hit6</th><th>hit5</th><th>hit4</th></tr></thead>
        <tbody>{rows_html}</tbody>
      </table>
    </div>
  </div>

  <p class="footer">
    Xoshiro256** (seeded via SplitMix64): picks = partial Fisher-Yates(range(1,{LOTO7_MAX+1}), {K_PICKS}) with combined seed
    = seed×10⁷ + draw_serial &mdash; bit-identical algorithm and formula to
    <a href="/xoshiro_seed_scan_k33.html" style="color:#64748b">the Loto6 xoshiro scans</a>, reparameterized for
    Loto7's pool size and K.<br>
    Data read live from <code>{TABLE}</code> in <code>loto7_local.db</code>. Draw records for #{DRAW_START}–{DRAW_END}
    sourced directly from the production database (<code>loto7_results</code>).<br>
    Formula-based only · Not financial advice · Loto 7 is random.
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
            <th>Actual (7) + bonus</th>
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
mkChart('hit7bChart', {json.dumps(hit7b_labels)}, {json.dumps(hit7b_values)}, '#a78bfa');
mkChart('hit7Chart', {json.dumps(hit7_labels)}, {json.dumps(hit7_values)}, '#38bdf8');
mkChart('hit6Chart', {json.dumps(hit6_labels)}, {json.dumps(hit6_values)}, '#22c55e');
mkChart('hit5Chart', {json.dumps(hit5_labels)}, {json.dumps(hit5_values)}, '#f59e0b');
mkChart('hit4Chart', {json.dumps(hit4_labels)}, {json.dumps(hit4_values)}, '#fb7185');
</script>
<script>
// ── Seed-detail modal: picks computed LIVE for any seed via the same
// verified xoshiro256** implementation (bit-exact BigInt port), reparameterized
// for Loto7's 37-number pool -- not limited to seeds in the top-{TOP_N} table.
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
  const arr = Array.from({{length: {LOTO7_MAX}}}, (_, i) => i + 1);
  const n = arr.length;
  for (let i = n - 1; i >= n - k; i--) {{
    const r = xoshiroNext(s);
    const j = Number(r % BigInt(i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }}
  return arr.slice(n - k).sort((a, b) => a - b);
}}

function lookupSeed() {{
  const input = document.getElementById('seedLookupInput');
  const errEl = document.getElementById('lookupErr');
  const raw = input.value.trim();
  errEl.style.display = 'none';
  if (raw === '' || !/^\\d+$/.test(raw)) {{
    errEl.textContent = 'Enter a non-negative whole number.';
    errEl.style.display = 'inline';
    return;
  }}
  openSeedDetail(parseInt(raw, 10));
}}

function openSeedDetail(seed) {{
  const K = {K_PICKS};
  let hit7b = 0, hit7 = 0, hit6 = 0, hit5 = 0, hit4 = 0;
  const htmlParts = [];
  [...DRAWS].reverse().forEach(row => {{
    const picks = xoshiroPredict(seed, row.s, K);
    const actualSet = new Set(row.a);
    const picksSet = new Set(picks);
    const hits = picks.filter(p => actualSet.has(p)).length;
    const bh = picksSet.has(row.b1) || picksSet.has(row.b2);
    if (hits === 7) {{ hit7++; if (bh) hit7b++; }}
    else if (hits === 6) {{ hit6++; }}
    else if (hits === 5) {{ hit5++; }}
    else if (hits === 4) {{ hit4++; }}

    const actualHtml = row.a.map(n =>
      '<span class="nb nm">' + n + '</span>'
    ).join('') + '<span class="nb nb-b">' + row.b1 + '</span>' + '<span class="nb nb-b">' + row.b2 + '</span>';

    const picksHtml = picks.map(n =>
      '<span class="nb' + (actualSet.has(n) ? ' nm' : '') + ((n === row.b1 || n === row.b2) ? ' nb-bh' : '') + '">' + n + '</span>'
    ).join('');

    const hc = hits >= 6 ? '#22c55e' : hits >= 5 ? '#4ade80' : hits >= 4 ? '#fbbf24' : hits >= 3 ? '#fb923c' : '#475569';
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
    'hit7b: <b>' + hit7b + '</b> &nbsp;·&nbsp; hit7: <b>' + hit7 + '</b> &nbsp;·&nbsp; hit6: <b>' + hit6 + '</b> &nbsp;·&nbsp; hit5: <b>' + hit5 + '</b> &nbsp;·&nbsp; hit4: <b>' + hit4 + '</b>';
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
