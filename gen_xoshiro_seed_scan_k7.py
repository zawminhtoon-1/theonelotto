"""
gen_xoshiro_seed_scan_k7.py
--------------------------------
Static report page for the K=7 xoshiro256** backtest scan: seeds
0-10,000, draws #1000-2127 (1128 draws), same algorithm/formula as the
K=21/K=26/K=33 scans.

K=7 is a small enough pick that hit6b (6-hit+bonus) is 0 for literally
every seed, and hit6 is 0 for 99.9% of seeds -- there's essentially no
per-seed signal at those thresholds. The real (and only) meaningful
signal at this K is the full 0-6 hit-count distribution, shown
prominently and first on this page, ahead of the best/worst-seed cards
(which are kept for consistency with the other xoshiro pages, but
honestly labeled given how tie-heavy they are here).

Reads live from loto6_local.db's seed_hit_xoshiro_k7 table (populated
by load_xoshiro_seed_scan_k7_to_db.py) -- NOT to be confused with the
older, unrelated seed_hit_k7 table (Python random.Random, per-draw
schema, different scan entirely).

Output: public/xoshiro_seed_scan_k7.html
Run: python gen_xoshiro_seed_scan_k7.py
"""
import sqlite3, json, re, math, os
from collections import Counter

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
DB_PATH = BASE + r"\loto6_local.db"
ENV_LOCAL = BASE + r"\.env.local"
HTML_OUT = BASE + r"\public\xoshiro_seed_scan_k7.html"
TABLE = "seed_hit_xoshiro_k7"

K_PICKS = 7
LOTO6_MAX = 43
DRAW_START, DRAW_END = 1000, 2127
N_DRAWS = DRAW_END - DRAW_START + 1  # 1128
TOP_N = 25

# ── Load aggregates + top-N from SQLite ──────────────────────────────────────
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute(f"SELECT COUNT(*) FROM {TABLE}")
num_seeds = cur.fetchone()[0]
if num_seeds != 10_001:
    raise SystemExit(f"Expected 10,001 rows in {TABLE}, found {num_seeds}")

cur.execute(f"SELECT seed, hit6b_count, hit6_count, hit5_count FROM {TABLE}")
all_rows = cur.fetchall()

cur.execute(f"""SELECT seed, hit6b_count, hit6_count, hit5_count FROM {TABLE}
                ORDER BY hit6b_count DESC, hit6_count DESC, hit5_count DESC, seed ASC LIMIT {TOP_N}""")
top_best = cur.fetchall()

cur.execute(f"""SELECT seed, hit6b_count, hit6_count, hit5_count FROM {TABLE}
                ORDER BY hit6b_count ASC, hit6_count ASC, hit5_count ASC, seed ASC LIMIT {TOP_N}""")
top_worst = cur.fetchall()

cur.execute(f"""SELECT SUM(hit0_count), SUM(hit1_count), SUM(hit2_count), SUM(hit3_count),
                       SUM(hit4_count), SUM(hit5_count), SUM(hit6_count)
                FROM {TABLE}""")
global_dist7 = list(cur.fetchone())
total_evals = num_seeds * N_DRAWS

cur.execute(f"SELECT COUNT(*) FROM {TABLE} WHERE hit6_count > 0")
seeds_with_any_hit6 = cur.fetchone()[0]
cur.execute(f"SELECT COUNT(*) FROM {TABLE} WHERE hit6b_count > 0")
seeds_with_any_hit6b = cur.fetchone()[0]

conn.close()
best = top_best[0]
worst = top_worst[0]

# ── Analytical hypergeometric baselines ──────────────────────────────────────
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
analytical_dist7 = [hyper_pmf(h, LOTO6_MAX, 6, K_PICKS) * total_evals for h in range(7)]

print(f"Loaded {num_seeds:,} seeds from {TABLE}")
print(f"Best: seed={best[0]} hit6b={best[1]} hit6={best[2]} hit5={best[3]}")
print(f"Worst: seed={worst[0]} hit6b={worst[1]} hit6={worst[2]} hit5={worst[3]}")
print(f"Global 0-6 distribution: {global_dist7}")
print(f"Seeds with any hit6: {seeds_with_any_hit6} / {num_seeds}  |  any hit6b: {seeds_with_any_hit6b} / {num_seeds}")

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
def render_rows(rows, highlight_seed=None, badge_label="BEST"):
    html = ""
    for rank, (seed, hit6b, hit6, hit5) in enumerate(rows, 1):
        badge = f' <span class="badge">{badge_label}</span>' if seed == highlight_seed else ''
        html += f"""<tr class="dr" onclick="openSeedDetail({seed})">
  <td class="tc">{rank}</td>
  <td class="tc">{seed:,}{badge}</td>
  <td class="tr">{hit6b}</td>
  <td class="tr">{hit6}</td>
  <td class="tr">{hit5}</td>
</tr>"""
    return html

rows_best_html = render_rows(top_best, highlight_seed=best[0], badge_label="BEST")
rows_worst_html = render_rows(top_worst, highlight_seed=worst[0], badge_label="WORST")

dist_labels_json = json.dumps(['0','1','2','3','4','5','6'])
dist_values_json = json.dumps(global_dist7)
dist_analytical_json = json.dumps([round(v) for v in analytical_dist7])

page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Xoshiro Seed Scan K=7 (0–10,000) — Loto 6</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>

*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0a0f1e;color:#e2e8f0;font-family:system-ui,sans-serif;padding-top:60px;min-height:100vh}}
.wrap{{max-width:1200px;margin:0 auto;padding:24px 16px}}
h1{{font-size:1.4rem;font-weight:700;color:#f1f5f9;margin-bottom:4px}}
.subtitle{{font-size:.85rem;color:#64748b;margin-bottom:20px}}

.note{{background:#0d1526;border:1px solid #1e293b;border-radius:10px;padding:14px 18px;
  font-size:.8rem;color:#94a3b8;margin-bottom:20px;line-height:1.6}}
.note.warn{{border-color:#f59e0b55;background:#1c1206}}
.note.warn strong{{color:#fbbf24}}
.note p+p{{margin-top:8px}}
.note code{{background:#0a0f1e;padding:1px 5px;border-radius:4px;font-size:.85em}}

.stats-row{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:24px}}
.stat-card{{background:#0d1526;border:1px solid #1e293b;border-radius:10px;padding:14px 18px;flex:1;min-width:160px}}
.stat-card .lbl{{font-size:.72rem;color:#64748b;text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px}}
.stat-card .val{{font-size:1.4rem;font-weight:700;color:#f1f5f9}}
.stat-card .sub{{font-size:.78rem;color:#94a3b8;margin-top:2px}}

.section{{background:#0d1526;border:1px solid #1e293b;border-radius:12px;padding:20px;margin-bottom:24px}}
.section.highlight{{border-color:#38bdf855}}
.section h2{{font-size:1rem;font-weight:700;color:#f1f5f9;margin-bottom:4px}}
.section .desc{{font-size:.8rem;color:#64748b;margin-bottom:16px}}
.chart-wrap{{height:320px;position:relative}}

.two-col{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
@media (max-width: 980px){{.two-col{{grid-template-columns:1fr}}}}

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
.modal-box{{background:#0a0f1e;border:1px solid #1e293b;border-radius:12px;width:100%;max-width:1000px;max-height:85vh;display:flex;flex-direction:column}}
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
  <h1>🔎 Xoshiro Seed Scan — K=7 (0–10,000)</h1>
  <p class="subtitle">{num_seeds:,} seeds · K={K_PICKS} picks · {N_DRAWS} draws (#{DRAW_START}–{DRAW_END}) · xoshiro256** (SplitMix64-seeded)</p>

  <div class="note warn">
    <p><strong>Read this before the stat cards below.</strong> K=7 is a much smaller pick than the K=21/26/33 scans elsewhere
    on this site — with only 7 numbers guessed out of 43, getting all 6 winners (let alone the bonus too) is extremely rare.
    In this scan: <strong>hit6b (6-hit + bonus) is 0 for every single one of the {num_seeds:,} seeds</strong> — it never happened once.
    hit6 is 0 for {num_seeds - seeds_with_any_hit6:,} of {num_seeds:,} seeds ({(num_seeds-seeds_with_any_hit6)/num_seeds*100:.1f}%) — only
    {seeds_with_any_hit6} seeds ever landed a single 6-hit draw, and none landed more than one. The "best"/"worst" seed cards and
    tables below are kept for consistency with the other xoshiro pages, but at this K they mostly reflect noise and tie-breaking,
    not a meaningful ranking.</p>
    <p>The <strong>real signal at K=7 is the full 0–6 hit-count distribution</strong> below — shown first, and it matches the
    analytical (pure-chance) hypergeometric expectation almost exactly at every bucket, which is itself the honest finding:
    xoshiro256** behaves like a well-mixed PRNG here too, same as every other scan on this site.</p>
  </div>

  <div class="section highlight">
    <h2>Full 0–6 hit-count distribution</h2>
    <p class="desc">Aggregated across all {total_evals:,} seed × draw evaluations ({num_seeds:,} seeds × {N_DRAWS} draws). This is where K=7's actual signal lives.</p>
    <div class="chart-wrap"><canvas id="distChart"></canvas></div>
  </div>

  <div class="lookup">
    <span class="lbl">🔍 Seed detail lookup</span>
    <input id="seedLookupInput" type="number" min="0" step="1" placeholder="Enter any seed number..." onkeydown="if(event.key==='Enter')lookupSeed()">
    <button onclick="lookupSeed()">View {N_DRAWS}-draw breakdown</button>
    <span class="hint">e.g. try {best[0]:,} — or any seed. Computed live in your browser.</span>
    <span id="lookupErr" class="err" style="display:none"></span>
  </div>

  <div class="stats-row">
    <div class="stat-card">
      <div class="lbl">Best seed (hit6b→hit6→hit5)</div>
      <div class="val">#{best[0]:,}</div>
      <div class="sub">hit6b {best[1]} · hit6 {best[2]} · hit5 {best[3]} — 1 of only {seeds_with_any_hit6} seeds with any 6-hit draw</div>
    </div>
    <div class="stat-card">
      <div class="lbl">Worst seed</div>
      <div class="val">#{worst[0]:,}</div>
      <div class="sub">hit6b {worst[1]} · hit6 {worst[2]} · hit5 {worst[3]} — tied with {num_seeds - seeds_with_any_hit6 - 1:,}+ other seeds at zero</div>
    </div>
    <div class="stat-card">
      <div class="lbl">Seeds with any hit6</div>
      <div class="val">{seeds_with_any_hit6}</div>
      <div class="sub">of {num_seeds:,} ({seeds_with_any_hit6/num_seeds*100:.2f}%)</div>
    </div>
    <div class="stat-card">
      <div class="lbl">Seeds with any hit6b</div>
      <div class="val">{seeds_with_any_hit6b}</div>
      <div class="sub">of {num_seeds:,} — never happened</div>
    </div>
  </div>

  <div class="two-col">
    <div class="section">
      <h2>Top {TOP_N} seeds (ranked: hit6b → hit6 → hit5)</h2>
      <p class="desc">Click a row for the full {N_DRAWS}-draw breakdown. Heavily tied at this K — see note above.</p>
      <div class="tbl-wrap">
        <table>
          <thead><tr><th class="tc">#</th><th class="tc">Seed</th><th>hit6b</th><th>hit6</th><th>hit5</th></tr></thead>
          <tbody>{rows_best_html}</tbody>
        </table>
      </div>
    </div>
    <div class="section">
      <h2>Bottom {TOP_N} seeds (lowest hit6b → hit6 → hit5)</h2>
      <p class="desc">Click a row for the full {N_DRAWS}-draw breakdown. Most of the population ties at all-zero.</p>
      <div class="tbl-wrap">
        <table>
          <thead><tr><th class="tc">#</th><th class="tc">Seed</th><th>hit6b</th><th>hit6</th><th>hit5</th></tr></thead>
          <tbody>{rows_worst_html}</tbody>
        </table>
      </div>
    </div>
  </div>

  <p class="footer">
    Xoshiro256** (seeded via SplitMix64): picks = partial Fisher-Yates(range(1,44), {K_PICKS}) with combined seed = seed×10⁷ + draw_serial.
    Algorithm verified against independent reference sources — see <a href="/xoshiro_seed_backtest.html" style="color:#64748b">the 0–1000 seed page</a>.<br>
    Data read live from <code>{TABLE}</code> in <code>loto6_local.db</code> — not to be confused with the older, unrelated
    <code>seed_hit_k7</code> table (a different scan entirely, using Python's <code>random.Random</code>, not xoshiro256**).<br>
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
new Chart(document.getElementById('distChart').getContext('2d'), {{
  type: 'bar',
  data: {{
    labels: {dist_labels_json},
    datasets: [
      {{ label: 'Actual (K=7 scan)', data: {dist_values_json}, backgroundColor: 'rgba(56,189,248,0.65)', borderColor: '#38bdf8', borderWidth: 1 }},
      {{ label: 'Analytical (pure chance)', data: {dist_analytical_json}, type: 'line', borderColor: '#fbbf24', borderDash: [5,3], borderWidth: 2, pointRadius: 3, pointBackgroundColor: '#fbbf24', fill: false, tension: 0 }}
    ]
  }},
  options: {{
    responsive: true, maintainAspectRatio: false,
    scales: {{
      y: {{ type: 'logarithmic', ticks: {{ color: '#64748b' }}, grid: {{ color: '#1e293b' }}, title: {{ display: true, text: '# of draws (log scale)', color: '#64748b' }} }},
      x: {{ ticks: {{ color: '#64748b' }}, grid: {{ display: false }}, title: {{ display: true, text: 'Hits per draw (0-6)', color: '#64748b' }} }}
    }},
    plugins: {{
      legend: {{ labels: {{ color: '#94a3b8' }} }},
      tooltip: {{ callbacks: {{ label: function(ctx) {{ return ctx.dataset.label + ': ' + ctx.parsed.y.toLocaleString(); }} }} }}
    }}
  }}
}});
</script>
<script>
// ── Seed-detail modal: picks computed LIVE for any seed via the same
// verified xoshiro256** implementation used elsewhere on the site.
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
  const arr = Array.from({{length: 43}}, (_, i) => i + 1);
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
  let hit6b = 0, hit6 = 0, hit5 = 0;
  const distCount = [0,0,0,0,0,0,0];
  const htmlParts = [];
  [...DRAWS].reverse().forEach(row => {{
    const picks = xoshiroPredict(seed, row.s, K);
    const actualSet = new Set(row.a);
    const picksSet = new Set(picks);
    const hits = picks.filter(p => actualSet.has(p)).length;
    const bh   = picksSet.has(row.b);
    distCount[hits]++;
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
    'hit6b: <b>' + hit6b + '</b> &nbsp;·&nbsp; hit6: <b>' + hit6 + '</b> &nbsp;·&nbsp; hit5: <b>' + hit5 + '</b>' +
    ' &nbsp;·&nbsp; 0-hit draws: <b>' + distCount[0] + '</b> &nbsp;·&nbsp; 1-hit: <b>' + distCount[1] + '</b>';
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
