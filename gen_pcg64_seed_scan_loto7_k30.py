"""
gen_pcg64_seed_scan_loto7_k30.py
--------------------------------------
Static report page for the Loto7 PCG64 K=30 backtest scan -- the PCG64
companion to the Loto7 xoshiro256** K=25/K=28/K=30 scans, and the
Loto7 counterpart to the Loto6 PCG64 K=38 scan (same page structure:
progress banner, five hit-tier distributions, top-25 table, and a
live client-side seed-detail lookup with a bit-exact BigInt PCG64
port -- no in-sample/out-of-sample breakdown yet, unlike the completed
xoshiro K=30 page, since this scan is still mid-flight).

Seed range -5,000,000 to 5,000,000 (10,000,001 seeds, matching the
Loto6 PCG64 K=38 scan's wider range), draws #1-650 (650 draws, matching
the existing Loto7 xoshiro K=30 scan's convention -- NOT the Loto6
PCG64 scan's #1-2050), ranked by hit7b (7-hit + either bonus) desc,
tiebreak hit7 desc, hit6 desc, hit5 desc, hit4 desc.

Designed to be regenerated INCREMENTALLY after every stage of the
10-stage scan completes -- reads whatever coverage is currently in
loto7_local.db's seed_hit_pcg64_k30 table (populated by
load_pcg64_seed_scan_loto7_k30_to_db.py) and renders a "scan in
progress" banner with the current stage count / seed coverage /
percentage when incomplete, switching to a "scan complete" framing
once all 10 stages have landed. SEED_LO/SEED_HI/num_seeds are read
live from the DB, not hardcoded.

Output: public/pcg64_seed_scan_loto7_k30.html
Run: python gen_pcg64_seed_scan_loto7_k30.py
"""
import sqlite3, json, re, math, os
from collections import Counter

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
DB_PATH = BASE + r"\loto7_local.db"
ENV_LOCAL = BASE + r"\.env.local"
HTML_OUT = BASE + r"\public\pcg64_seed_scan_loto7_k30.html"
TABLE = "seed_hit_pcg64_k30"

K_PICKS = 30
LOTO7_MAX = 37
DRAW_START, DRAW_END = 1, 650
N_DRAWS = DRAW_END - DRAW_START + 1  # 650
FULL_SEED_LO, FULL_SEED_HI = -5_000_000, 5_000_000
FULL_EXPECTED = FULL_SEED_HI - FULL_SEED_LO + 1
N_STAGES = 10
TOP_N = 25

# ── Load aggregates + top-N from SQLite (whatever coverage exists so far) ───
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute(f"SELECT COUNT(*) FROM {TABLE}")
num_seeds = cur.fetchone()[0]
if num_seeds == 0:
    raise SystemExit(f"{TABLE} is empty -- run load_pcg64_seed_scan_loto7_k30_to_db.py first.")
cur.execute(f"SELECT MIN(seed), MAX(seed) FROM {TABLE}")
SEED_LO, SEED_HI = cur.fetchone()

is_complete = (num_seeds == FULL_EXPECTED and SEED_LO == FULL_SEED_LO and SEED_HI == FULL_SEED_HI)
pct_complete = num_seeds / FULL_EXPECTED * 100
n_stages_done = round(num_seeds / 1_000_000) if not is_complete else N_STAGES

cur.execute(f"SELECT seed, hit7b_count, hit7_count, hit6_count, hit5_count, hit4_count FROM {TABLE}")
all_rows = cur.fetchall()

cur.execute(f"""SELECT seed, hit7b_count, hit7_count, hit6_count, hit5_count, hit4_count FROM {TABLE}
                ORDER BY hit7b_count DESC, hit7_count DESC, hit6_count DESC, hit5_count DESC, hit4_count DESC, seed ASC LIMIT {TOP_N}""")
top_ranked = cur.fetchall()

conn.close()
best = top_ranked[0]

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
p_hit7b = p_hit7_only * (1 - p_neither_bonus)  # hit7b = full 7-match AND at least one of the 2 bonus numbers also picked
p_hit6 = hyper_pmf(6, LOTO7_MAX, 7, K_PICKS)
p_hit5 = hyper_pmf(5, LOTO7_MAX, 7, K_PICKS)
p_hit4 = hyper_pmf(4, LOTO7_MAX, 7, K_PICKS)

exp_hit7b = p_hit7b * N_DRAWS
exp_hit7 = p_hit7_only * N_DRAWS
exp_hit6 = p_hit6 * N_DRAWS
exp_hit5 = p_hit5 * N_DRAWS
exp_hit4 = p_hit4 * N_DRAWS

print(f"Loaded {num_seeds:,} seeds from {TABLE} (seeds {SEED_LO:,} to {SEED_HI:,})")
print(f"Coverage: {pct_complete:.1f}% of full {FULL_EXPECTED:,}-seed range -- {'COMPLETE' if is_complete else f'IN PROGRESS ({n_stages_done}/{N_STAGES} stages)'}")
print(f"Best so far: seed={best[0]:,} hit7b={best[1]} hit7={best[2]} hit6={best[3]} hit5={best[4]} hit4={best[5]}")
print(f"Analytical expectation: hit7b~={exp_hit7b:.4f} hit7~={exp_hit7:.2f} hit6~={exp_hit6:.2f} hit5~={exp_hit5:.2f} hit4~={exp_hit4:.2f} (of {N_DRAWS} draws)")

# ── Load the exact #1-650 draw window from the production DB, for the
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
    "SELECT draw_serial, draw_date, num1,num2,num3,num4,num5,num6,num7, bonus1, bonus2 "
    "FROM loto7_results WHERE draw_serial BETWEEN %s AND %s ORDER BY draw_serial",
    (DRAW_START, DRAW_END),
)
pg_rows = pgcur.fetchall()
pg.close()
if len(pg_rows) != N_DRAWS:
    raise SystemExit(f"Draw window mismatch: got {len(pg_rows)} rows, expected {N_DRAWS}")
DRAWS = [{'s': r[0], 'd': r[1].isoformat(), 'a': list(r[2:9]), 'b1': r[9], 'b2': r[10]} for r in pg_rows]
js_draws = json.dumps(DRAWS, separators=(',', ':'))
print(f"Loaded {len(DRAWS)} draw records for the client-side modal (#{DRAWS[0]['s']}-{DRAWS[-1]['s']}).")

# ── Table rows ────────────────────────────────────────────────────────────
def render_rows(rows, highlight_seed=None):
    html = ""
    for rank, (seed, hit7b, hit7, hit6, hit5, hit4) in enumerate(rows, 1):
        badge = ' <span class="badge">BEST</span>' if seed == highlight_seed else ''
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

rows_html = render_rows(top_ranked, highlight_seed=best[0])

if is_complete:
    progress_note_html = (
        f'<p><strong style="color:#4ade80">✅ Scan complete.</strong> All {num_seeds:,} seeds '
        f'({FULL_SEED_LO:,} to {FULL_SEED_HI:,}) have been scanned against all {N_DRAWS} draws.</p>'
    )
    title_suffix = ""
else:
    progress_note_html = (
        f'<p><strong style="color:#fbbf24">⏳ Scan in progress:</strong> {n_stages_done}/{N_STAGES} stages complete '
        f'&mdash; {num_seeds:,} of {FULL_EXPECTED:,} seeds scanned so far ({pct_complete:.1f}%), covering '
        f'{SEED_LO:,} to {SEED_HI:,}. Full range: {FULL_SEED_LO:,} to {FULL_SEED_HI:,}. This page updates '
        f'automatically as further stages complete &mdash; the best/worst seeds and stats below reflect only '
        f'the range scanned so far, not the eventual full range.</p>'
    )
    title_suffix = " — IN PROGRESS"

page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>PCG64 Seed Scan K=30 (±5,000,000){title_suffix} — Loto 7</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>

*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0a0f1e;color:#e2e8f0;font-family:system-ui,sans-serif;padding-top:60px;min-height:100vh}}
.wrap{{max-width:1200px;margin:0 auto;padding:24px 16px}}
h1{{font-size:1.4rem;font-weight:700;color:#f1f5f9;margin-bottom:4px}}
.subtitle{{font-size:.85rem;color:#64748b;margin-bottom:20px}}

.note{{background:#0d1526;border:1px solid #1e293b;border-radius:10px;padding:14px 18px;
  font-size:.8rem;color:#94a3b8;margin-bottom:20px;line-height:1.6}}
.note p+p{{margin-top:8px}}
.note code{{background:#0a0f1e;padding:1px 5px;border-radius:4px;font-size:.85em}}

.progress-note{{border-radius:10px;padding:14px 18px;font-size:.82rem;margin-bottom:20px;line-height:1.6}}
.progress-note.in-progress{{background:#1c1608;border:1px solid #fbbf2455;color:#e2e8f0}}
.progress-note.complete{{background:#0a1c0f;border:1px solid #4ade8055;color:#e2e8f0}}

.stats-row{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:24px}}
.stat-card{{background:#0d1526;border:1px solid #1e293b;border-radius:10px;padding:14px 18px;flex:1;min-width:160px}}
.stat-card .lbl{{font-size:.72rem;color:#64748b;text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px}}
.stat-card .val{{font-size:1.4rem;font-weight:700;color:#f1f5f9}}
.stat-card .sub{{font-size:.78rem;color:#94a3b8;margin-top:2px}}

.section{{background:#0d1526;border:1px solid #1e293b;border-radius:12px;padding:20px;margin-bottom:24px}}
.section h2{{font-size:1rem;font-weight:700;color:#f1f5f9;margin-bottom:4px}}
.section .desc{{font-size:.8rem;color:#64748b;margin-bottom:16px}}
.chart-wrap{{height:260px;position:relative}}

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

<script src="/site-nav.js"></script>
<div class="wrap">
  <h1>🎯 PCG64 Seed Scan — Loto 7 K=30 (seeds -5,000,000 to 5,000,000)</h1>
  <p class="subtitle">{num_seeds:,} seeds scanned so far · K={K_PICKS} picks · {N_DRAWS} draws (#{DRAW_START}–{DRAW_END}) · PCG64 (O'Neill XSL-RR 128/64, SplitMix64-expanded)</p>

  <div class="progress-note {'complete' if is_complete else 'in-progress'}">
    {progress_note_html}
  </div>

  <div class="note">
    <p>PCG64 companion to <a href="/xoshiro_seed_scan_loto7_k30.html" style="color:#a78bfa">the Loto7 xoshiro256** K=30 scan</a>
    &mdash; testing whether swapping the underlying <strong>PRNG family</strong> (not just K) changes anything descriptively,
    and the Loto7 counterpart to <a href="/pcg64_seed_scan_k38.html" style="color:#a78bfa">the Loto6 PCG64 K=38 scan</a>.
    Same draw window #{DRAW_START}&ndash;{DRAW_END} ({N_DRAWS} draws) and combined-seed formula
    (<code>seed&times;10,000,000 + draw_serial</code>) as the xoshiro K=30 scan, but a much wider seed range &mdash;
    {FULL_SEED_LO:,} to {FULL_SEED_HI:,} ({FULL_EXPECTED:,} values, split into {N_STAGES} stages of ~1,000,000 each,
    matching the Loto6 PCG64 K=38 scan's range and staging convention rather than the xoshiro scan's narrower &plusmn;1,000,000).</p>
    <p><strong style="color:#e2e8f0">How the seed becomes picks:</strong> the combined seed is expanded into PCG64's raw
    128-bit <code>{{state, inc}}</code> via SplitMix64 run four times (the same expansion primitive the xoshiro scans use
    for their 256-bit state, just producing 128+128 bits instead of 4&times;64 &mdash; this site's own seeding convention,
    chosen to stay JS-portable). Each next-value call then runs O'Neill's standard PCG64 XSL-RR construction: a 128-bit LCG
    advance (<code>state = state&times;0x2360ed051fc65da44385df649fccf645 + inc (mod 2&sup1;&sup2;&sup8;)</code>) followed
    by a 64-bit xor-shift + random-rotate output permutation. K={K_PICKS} picks come from the same partial Fisher-Yates over
    range(1,38) (37-number pool, not 44) as every other Loto7 scan on this site.</p>
    <p><strong style="color:#e2e8f0">Verification:</strong> the pure-Python core (already proven bit-exact against
    <code>numpy.random.Generator(PCG64())</code> for the Loto6 pool_max=43 case) was <strong>re-verified</strong> for this
    pool_max=37/K=30 configuration specifically &mdash; direct low-level state injection (bypassing SeedSequence) driving
    NumPy's actual bit generator and replicating the identical Fisher-Yates loop on its raw 64-bit words, confirmed
    matching exactly before this scan was ever run. Self-checked per stage against independently-computed known-good
    reference vectors (including negative seeds) before scaling, same discipline as every other scan on this site.</p>
    <p>Five metrics tracked per seed: <b>hit7b</b> = draws where the {K_PICKS} picks contain all 7 main winning numbers
    <em>and</em> at least one of the 2 bonus numbers (either bonus, same convention as the xoshiro K=30 Loto7 page);
    <b>hit7</b> = all 7 main numbers (any bonus); <b>hit6</b>/<b>hit5</b>/<b>hit4</b> = exactly 6/5/4 of 7. At K={K_PICKS}
    (a {K_PICKS}-of-{LOTO7_MAX} pool, ~{K_PICKS/LOTO7_MAX*100:.0f}% coverage) chance rates run fairly high &mdash;
    hypergeometric expectation is hit7b&asymp;{exp_hit7b:.2f}, hit7&asymp;{exp_hit7:.1f}, hit6&asymp;{exp_hit6:.1f},
    hit5&asymp;{exp_hit5:.1f}, hit4&asymp;{exp_hit4:.1f} per seed (of {N_DRAWS} draws) &mdash; all five tiers are tracked for
    the same ranking convention: highest hit7b, tiebreak hit7, hit6, hit5, hit4.</p>
  </div>

  <div class="lookup">
    <span class="lbl">🔍 Seed detail lookup</span>
    <input id="seedLookupInput" type="number" step="1" placeholder="Enter any seed (negative OK)..." onkeydown="if(event.key==='Enter')lookupSeed()">
    <button onclick="lookupSeed()">View {N_DRAWS}-draw breakdown</button>
    <span class="hint">e.g. try {best[0]:,} (the top-ranked seed so far) — or any seed, positive or negative, even outside the scanned range. Computed live in your browser.</span>
    <span id="lookupErr" class="err" style="display:none"></span>
  </div>

  <div class="stats-row">
    <div class="stat-card">
      <div class="lbl">Best seed (ranked, so far)</div>
      <div class="val">#{best[0]:,}</div>
      <div class="sub">hit7b {best[1]} · hit7 {best[2]} · hit6 {best[3]} · hit5 {best[4]} · hit4 {best[5]}</div>
    </div>
    <div class="stat-card">
      <div class="lbl">Expected hit7b (chance)</div>
      <div class="val">{exp_hit7b:.3f}</div>
      <div class="sub">hypergeometric, per seed</div>
    </div>
    <div class="stat-card">
      <div class="lbl">Expected hit7 (chance)</div>
      <div class="val">{exp_hit7:.2f}</div>
      <div class="sub">hypergeometric, per seed</div>
    </div>
    <div class="stat-card">
      <div class="lbl">Expected hit6 / hit5 / hit4</div>
      <div class="val">{exp_hit6:.0f} / {exp_hit5:.0f} / {exp_hit4:.0f}</div>
      <div class="sub">hypergeometric, per seed</div>
    </div>
    <div class="stat-card">
      <div class="lbl">Seeds scanned so far</div>
      <div class="val">{num_seeds:,}</div>
      <div class="sub">{SEED_LO:,} to {SEED_HI:,} ({pct_complete:.1f}% of full range)</div>
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
      <p class="desc">All 7 main (any bonus).</p>
      <div class="chart-wrap"><canvas id="hit7Chart"></canvas></div>
    </div>
    <div class="section">
      <h2>hit6</h2>
      <p class="desc">Exactly 6 of 7.</p>
      <div class="chart-wrap"><canvas id="hit6Chart"></canvas></div>
    </div>
    <div class="section">
      <h2>hit5</h2>
      <p class="desc">Exactly 5 of 7.</p>
      <div class="chart-wrap"><canvas id="hit5Chart"></canvas></div>
    </div>
    <div class="section">
      <h2>hit4</h2>
      <p class="desc">Exactly 4 of 7.</p>
      <div class="chart-wrap"><canvas id="hit4Chart"></canvas></div>
    </div>
  </div>

  <div class="section">
    <h2>Top {TOP_N} seeds so far (ranked: hit7b → hit7 → hit6 → hit5 → hit4)</h2>
    <p class="desc">Click a row for the full {N_DRAWS}-draw breakdown. Rankings will be re-evaluated as remaining stages land.</p>
    <div class="tbl-wrap">
      <table>
        <thead><tr><th class="tc">#</th><th class="tc">Seed</th><th>hit7b</th><th>hit7</th><th>hit6</th><th>hit5</th><th>hit4</th></tr></thead>
        <tbody>{rows_html}</tbody>
      </table>
    </div>
  </div>

  <p class="footer">
    PCG64 (O'Neill XSL-RR 128/64, seeded via SplitMix64-expanded {{state,inc}}): picks = partial Fisher-Yates(range(1,38), {K_PICKS})
    with combined seed = seed×10⁷ + draw_serial. Core algorithm re-verified bit-exact against <code>numpy.random.Generator(PCG64())</code>
    for this pool_max={LOTO7_MAX}/K={K_PICKS} configuration via direct low-level state injection (bypassing SeedSequence) before this scan ran.<br>
    Data read live from <code>{TABLE}</code> in <code>loto7_local.db</code>. Draw records for #{DRAW_START}–{DRAW_END}
    sourced directly from the production database, verified for exactly {N_DRAWS} consecutive rows with no gaps.<br>
    Formula-based only · Not financial advice · Loto 7 is random.
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
            <div class="nbhd-stat"><div class="lbl">Local rank (hit7b)</div><div class="val" id="nbhdRank">-</div></div>
            <div class="nbhd-stat"><div class="lbl">hit7b range</div><div class="val" id="nbhdRange">-</div></div>
            <div class="nbhd-stat"><div class="lbl">hit7b mean / median</div><div class="val" id="nbhdMeanMed">-</div></div>
            <div class="nbhd-stat"><div class="lbl">hit7b stdev</div><div class="val" id="nbhdStdev">-</div></div>
          </div>
          <div class="nbhd-chart-wrap"><canvas id="nbhdChart"></canvas></div>
          <p id="nbhdNote" class="nbhd-note"></p>
        </div>
      </div>
      <div class="modal-body">
        <table class="modal-table">
          <thead><tr>
            <th>Draw</th><th>Date</th>
            <th>Actual (7) + bonuses</th>
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
mkChart('hit7bChart', {json.dumps(hit7b_labels)}, {json.dumps(hit7b_values)}, '#a78bfa');
mkChart('hit7Chart', {json.dumps(hit7_labels)}, {json.dumps(hit7_values)}, '#38bdf8');
mkChart('hit6Chart', {json.dumps(hit6_labels)}, {json.dumps(hit6_values)}, '#22c55e');
mkChart('hit5Chart', {json.dumps(hit5_labels)}, {json.dumps(hit5_values)}, '#f59e0b');
mkChart('hit4Chart', {json.dumps(hit4_labels)}, {json.dumps(hit4_values)}, '#e879f9');
</script>
<script>
// ── Seed-detail modal: picks computed LIVE for any seed (including negative,
// and including seeds outside the currently-scanned range) via a bit-exact
// BigInt PCG64 port -- not limited to seeds in the top-{TOP_N} table.
const DRAWS = {js_draws};

const MASK64 = (1n << 64n) - 1n;
const MASK128 = (1n << 128n) - 1n;
const PCG_MULT_128 = 0x2360ed051fc65da44385df649fccf645n;

function splitmix64Next(z) {{
  z = (z + 0x9E3779B97F4A7C15n) & MASK64;
  let zz = z;
  zz = ((zz ^ (zz >> 30n)) * 0xBF58476D1CE4E5B9n) & MASK64;
  zz = ((zz ^ (zz >> 27n)) * 0x94D049BB133111EBn) & MASK64;
  zz = zz ^ (zz >> 31n);
  return [z, zz];
}}
function expandSeedToPcgState(combined) {{
  let z = combined & MASK64;
  const outs = [];
  for (let i = 0; i < 4; i++) {{
    const [nz, o] = splitmix64Next(z);
    z = nz;
    outs.push(o);
  }}
  const state = ((outs[0] << 64n) | outs[1]) & MASK128;
  const inc = (((outs[2] << 64n) | outs[3]) | 1n) & MASK128;
  return [state, inc];
}}
function rotr64(v, rot) {{
  rot &= 63n;
  const shift = (64n - rot) % 64n;
  return ((v >> rot) | (v << shift)) & MASK64;
}}
function pcg64Next(state, inc) {{
  state = (state * PCG_MULT_128 + inc) & MASK128;
  const xored = (state >> 64n) ^ (state & MASK64);
  const rot = (state >> 122n) & 0x3fn;
  const out = rotr64(xored, rot);
  return [state, out];
}}
function pcg64Predict(seed, drawSerial, k) {{
  const combined = (BigInt(seed) * 10000000n + BigInt(drawSerial)) & MASK64;
  let [state, inc] = expandSeedToPcgState(combined);
  const arr = Array.from({{length: {LOTO7_MAX}}}, (_, i) => i + 1);
  const n = arr.length;
  const order = [];
  for (let i = n - 1; i >= n - k; i--) {{
    const [ns, r] = pcg64Next(state, inc);
    state = ns;
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
  let hit7b = 0, hit7 = 0, hit6 = 0, hit5 = 0, hit4 = 0;
  const htmlParts = [];
  [...DRAWS].reverse().forEach(row => {{
    const picks = pcg64Predict(seed, row.s, K);
    const actualSet = new Set(row.a);
    const picksSet = new Set(picks);
    const hits = picks.filter(p => actualSet.has(p)).length;
    const bh1 = picksSet.has(row.b1);
    const bh2 = picksSet.has(row.b2);
    if (hits === 7) {{ hit7++; if (bh1 || bh2) hit7b++; }}
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
      '<td style="text-align:center;font-weight:700;color:' + hc + '">' + hits + ((bh1||bh2) ? '<span style="color:#a78bfa;font-size:.7rem">+B</span>' : '') + '</td></tr>'
    );
  }});

  document.getElementById('modalTitle').textContent = 'Seed #' + seed.toLocaleString() + ' — ' + DRAWS.length + ' draws (K=' + K + ')';
  document.getElementById('modalStats').innerHTML =
    'hit7b: <b>' + hit7b + '</b> &nbsp;·&nbsp; hit7: <b>' + hit7 + '</b> &nbsp;·&nbsp; hit6: <b>' + hit6 + '</b> &nbsp;·&nbsp; hit5: <b>' + hit5 + '</b> &nbsp;·&nbsp; hit4: <b>' + hit4 + '</b>';
  document.getElementById('modalTbody').innerHTML = htmlParts.join('');
  document.getElementById('seedModal').style.display = 'flex';
}}

// ── Local neighborhood (±100 seeds): computed live in the browser, on
// demand, for whichever seed the modal currently has open.
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
      let hit7b = 0, hit7 = 0, hit6 = 0;
      for (const row of DRAWS) {{
        const picks = pcg64Predict(s, row.s, K);
        const actualSet = new Set(row.a);
        const picksSet = new Set(picks);
        const hits = picks.filter(p => actualSet.has(p)).length;
        if (hits === 7) {{ hit7++; if (picksSet.has(row.b1) || picksSet.has(row.b2)) hit7b++; }}
        else if (hits === 6) {{ hit6++; }}
      }}
      results.push({{ seed: s, hit7b, hit7, hit6 }});
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
  const h7b = results.map(r => r.hit7b);
  const sorted = [...h7b].sort((a, b) => a - b);
  const min = sorted[0], max = sorted[n - 1];
  const mean = h7b.reduce((a, b) => a + b, 0) / n;
  const median = n % 2 === 1 ? sorted[(n - 1) / 2] : (sorted[n / 2 - 1] + sorted[n / 2]) / 2;
  const variance = h7b.reduce((a, b) => a + (b - mean) * (b - mean), 0) / (n - 1);
  const stdev = Math.sqrt(variance);

  const ranked = [...results].sort((a, b) =>
    b.hit7b - a.hit7b || b.hit7 - a.hit7 || b.hit6 - a.hit6 || a.seed - b.seed);
  const rankIdx = ranked.findIndex(r => r.seed === seed) + 1;
  const target = results.find(r => r.seed === seed);
  const sigma = stdev > 0 ? (target.hit7b - mean) / stdev : 0;

  document.getElementById('nbhdRank').textContent = '#' + rankIdx + ' of ' + n;
  document.getElementById('nbhdRange').textContent = min + ' – ' + max;
  document.getElementById('nbhdMeanMed').textContent = mean.toFixed(1) + ' / ' + median;
  document.getElementById('nbhdStdev').textContent = stdev.toFixed(2);

  let note = 'Seed #' + seed.toLocaleString() + ' ranks #' + rankIdx + ' of ' + n +
    ' in its own ±' + NBHD_RADIUS + ' neighborhood (hit7b=' + target.hit7b + ', ' +
    (sigma >= 0 ? '+' : '') + sigma.toFixed(1) + 'σ vs the local mean).';
  if (rankIdx === 1 && n > 1) {{
    const second = ranked[1];
    const gap = target.hit7b - second.hit7b;
    note += ' It leads the 2nd-best local seed (#' + second.seed.toLocaleString() + ', hit7b=' + second.hit7b + ') by ' + gap +
      (gap > stdev * 2
        ? ' — an isolated spike, not surrounded by similarly strong neighbors.'
        : ' — part of a cluster of comparably strong neighboring seeds.');
  }}
  document.getElementById('nbhdNote').textContent = note;

  resultsEl.style.display = 'block';

  const labels = results.map(r => (r.seed - seed > 0 ? '+' : '') + (r.seed - seed));
  const values = results.map(r => r.hit7b);
  const colors = results.map(r => r.seed === seed ? '#fbbf24' : '#a78bfa77');
  const borders = results.map(r => r.seed === seed ? '#fbbf24' : '#a78bfa');
  if (nbhdChart) nbhdChart.destroy();
  nbhdChart = new Chart(document.getElementById('nbhdChart').getContext('2d'), {{
    type: 'bar',
    data: {{ labels: labels, datasets: [{{ label: 'hit7b', data: values, backgroundColor: colors, borderColor: borders, borderWidth: 1 }}] }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      plugins: {{
        legend: {{ display: false }},
        tooltip: {{
          callbacks: {{
            title: function(items) {{ return 'seed offset ' + items[0].label; }},
            label: function(ctx) {{ return 'hit7b: ' + ctx.parsed.y; }}
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
</body>
</html>"""

with open(HTML_OUT, 'w', encoding='utf-8') as f:
    f.write(page)
print(f"\nWrote {HTML_OUT} ({len(page)//1024} KB)")
