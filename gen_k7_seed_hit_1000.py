"""
gen_k7_seed_hit_1000.py
------------------------
Static report page for the 1000-draw K=7 seed-hit scan (draws #1124-2123,
seeds -1,000,000 to 1,000,000). Reads directly from loto6_local.db's
seed_hit_k7 table (populated by scratch_seed_hit_k7_1000draws.py in an
earlier session) rather than hand-transcribing results.

Output: public/k7_seed_hit_1000.html
"""
import sqlite3, json

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
DB_PATH = BASE + r"\loto6_local.db"
HTML_OUT = BASE + r"\public\k7_seed_hit_1000.html"

SEED_START, SEED_END = -1_000_000, 1_000_000
COMPARISON_100_COVERED = 88  # earlier standalone 100-draw sample (#2024-2123) at same +-1,000,000 range

# ── Load data from SQLite ──────────────────────────────────────────────────────
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
cur.execute("""
    SELECT draw_serial, hitting_seed, covered, n1,n2,n3,n4,n5,n6
    FROM seed_hit_k7
    ORDER BY draw_serial
""")
rows = cur.fetchall()
conn.close()

if len(rows) != 1000:
    raise SystemExit(f"Expected 1000 rows in seed_hit_k7, found {len(rows)}")

DRAW_START = rows[0][0]
DRAW_END = rows[-1][0]
total = len(rows)
covered_rows = [r for r in rows if r[2] == 1]
missed_rows = [r for r in rows if r[2] == 0]
covered_count = len(covered_rows)
missed_count = len(missed_rows)
covered_pct = covered_count / total * 100
missed_pct = missed_count / total * 100

# ── Blocks of 100 draws for the grouped grid ───────────────────────────────────
BLOCK_SIZE = 100
blocks = []
for i in range(0, total, BLOCK_SIZE):
    chunk = rows[i:i + BLOCK_SIZE]
    b_start, b_end = chunk[0][0], chunk[-1][0]
    b_covered = sum(1 for r in chunk if r[2] == 1)
    blocks.append((b_start, b_end, chunk, b_covered))

# Cross-check: does the last block (2024-2123) match the known standalone 100-draw result?
last_block = blocks[-1]
cross_check_match = (last_block[0], last_block[1], last_block[3]) == (2024, 2123, COMPARISON_100_COVERED)

def render_block(b_start, b_end, chunk, b_covered):
    cells = ""
    for r in chunk:
        draw_serial, hitting_seed, covered, n1, n2, n3, n4, n5, n6 = r
        if covered:
            cls = "cell hit"
            title = f"Draw #{draw_serial} \u2014 covered, seed {hitting_seed:+d}"
        else:
            cls = "cell miss"
            title = f"Draw #{draw_serial} \u2014 MISSED"
        cells += f'<div class="{cls}" title="{title}"></div>'
    b_missed = len(chunk) - b_covered
    return f"""
    <div class="block">
      <div class="block-hdr">
        <span class="block-range">#{b_start}\u2013{b_end}</span>
        <span class="block-stat hit-stat">{b_covered} covered</span>
        <span class="block-stat miss-stat">{b_missed} missed</span>
      </div>
      <div class="block-grid">{cells}</div>
    </div>"""

blocks_html = "".join(render_block(*b) for b in blocks)

# ── Histogram of hitting seed values (covered draws only) ─────────────────────
BIN_WIDTH = 100_000
bins = {}
for r in covered_rows:
    seed = r[1]
    binkey = seed // BIN_WIDTH
    bins[binkey] = bins.get(binkey, 0) + 1

bin_keys = list(range(SEED_START // BIN_WIDTH, (SEED_END // BIN_WIDTH) + 1))
hist_labels = [f"{k*BIN_WIDTH:,}" for k in bin_keys]
hist_values = [bins.get(k, 0) for k in bin_keys]

neg_total = sum(v for k, v in zip(bin_keys, hist_values) if k < 0)
pos_total = sum(v for k, v in zip(bin_keys, hist_values) if k >= 0)

hist_labels_json = json.dumps(hist_labels)
hist_values_json = json.dumps(hist_values)

page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>K=7 Seed-Hit Scan (1000 draws) \u2014 Loto 6</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
/* ====== SHARED FIXED NAV (dropdown) ====== */
/* ========================================= */

*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0a0f1e;color:#e2e8f0;font-family:system-ui,sans-serif;padding-top:60px;min-height:100vh}}
.wrap{{max-width:1200px;margin:0 auto;padding:24px 16px}}
h1{{font-size:1.4rem;font-weight:700;color:#f1f5f9;margin-bottom:4px}}
.subtitle{{font-size:.85rem;color:#64748b;margin-bottom:20px}}

.stats-row{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:24px}}
.stat-card{{background:#0d1526;border:1px solid #1e293b;border-radius:10px;padding:14px 18px;flex:1;min-width:160px}}
.stat-card .lbl{{font-size:.72rem;color:#64748b;text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px}}
.stat-card .val{{font-size:1.5rem;font-weight:700;color:#f1f5f9}}
.stat-card .sub{{font-size:.78rem;color:#94a3b8;margin-top:2px}}
.stat-card.warn{{border-color:#f59e0b55}}
.stat-card.warn .val{{color:#f59e0b}}

.section{{background:#0d1526;border:1px solid #1e293b;border-radius:12px;padding:20px;margin-bottom:24px}}
.section h2{{font-size:1rem;font-weight:700;color:#f1f5f9;margin-bottom:4px}}
.section .desc{{font-size:.8rem;color:#64748b;margin-bottom:16px}}
.chart-wrap{{height:300px;position:relative}}

.block{{margin-bottom:14px}}
.block-hdr{{display:flex;align-items:center;gap:10px;margin-bottom:6px;font-size:.75rem}}
.block-range{{color:#94a3b8;font-weight:600;min-width:110px}}
.block-stat{{padding:1px 8px;border-radius:5px;font-weight:600}}
.hit-stat{{background:#14532d33;color:#86efac}}
.miss-stat{{background:#450a0a33;color:#fca5a5}}
.block-grid{{display:grid;grid-template-columns:repeat(50,1fr);gap:2px}}
.cell{{aspect-ratio:1;border-radius:2px;cursor:default}}
.cell.hit{{background:#22c55e}}
.cell.hit:hover{{background:#4ade80;transform:scale(1.4);position:relative;z-index:2}}
.cell.miss{{background:#ef4444}}
.cell.miss:hover{{background:#f87171;transform:scale(1.4);position:relative;z-index:2}}

.legend{{display:flex;gap:18px;flex-wrap:wrap;margin-top:14px;font-size:.78rem;color:#94a3b8}}
.legend .sw{{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:6px;vertical-align:-1px}}
.legend .sw.hit{{background:#22c55e}}
.legend .sw.miss{{background:#ef4444}}

.callout{{background:#0c2340;border:1px solid #38bdf855;border-radius:10px;padding:14px 18px;margin-top:16px}}
.callout .lbl{{font-size:.72rem;color:#38bdf8;text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px;font-weight:700}}
.callout p{{font-size:.83rem;color:#e2e8f0;line-height:1.5}}
.callout p + p{{margin-top:8px}}

.footer{{margin-top:28px;font-size:.78rem;color:#475569;padding-bottom:20px;line-height:1.6}}

@media (max-width: 700px) {{
  .block-grid{{grid-template-columns:repeat(25,1fr)}}
}}
</style>
</head>
<body>

<script src="/site-nav.js"></script>
<div class="wrap">
  <h1>\U0001f5fa K=7 Seed-Hit Scan \u2014 1000 Draws</h1>
  <p class="subtitle">Draws #{DRAW_START}\u2013{DRAW_END} ({total} draws) \u00b7 K=7 picks \u00b7 seeds {SEED_START:,} to {SEED_END:,} ({SEED_END-SEED_START+1:,} values) \u00b7 formula random.Random(seed\u00d710\u2077+draw_serial).sample(range(1,44),7)</p>

  <div class="stats-row">
    <div class="stat-card">
      <div class="lbl">Draws scanned</div>
      <div class="val">{total:,}</div>
      <div class="sub">#{DRAW_START}\u2013{DRAW_END}</div>
    </div>
    <div class="stat-card">
      <div class="lbl">Covered</div>
      <div class="val">{covered_count}</div>
      <div class="sub">{covered_pct:.1f}% of draws</div>
    </div>
    <div class="stat-card warn">
      <div class="lbl">Missed</div>
      <div class="val">{missed_count}</div>
      <div class="sub">{missed_pct:.1f}% of draws</div>
    </div>
    <div class="stat-card">
      <div class="lbl">Seed range</div>
      <div class="val">\u00b11.0M</div>
      <div class="sub">{SEED_END-SEED_START+1:,} seeds tested</div>
    </div>
  </div>

  <div class="section">
    <h2>Coverage grid \u2014 all {total} draws, grouped by 100</h2>
    <p class="desc">Each cell is one draw. Hover for the draw number and (if covered) its first-hitting seed. Grouped into {len(blocks)} blocks of {BLOCK_SIZE} consecutive draws for readability.</p>
    {blocks_html}
    <div class="legend">
      <span><span class="sw hit"></span>Covered ({covered_count})</span>
      <span><span class="sw miss"></span>Missed ({missed_count})</span>
    </div>
  </div>

  <div class="section">
    <h2>Distribution of hitting seeds (covered draws)</h2>
    <p class="desc">Histogram of the {covered_count} recorded first-hitting seeds, binned in {BIN_WIDTH:,}-wide buckets across the full \u00b11,000,000 range.</p>
    <div class="chart-wrap"><canvas id="histChart"></canvas></div>
    <p class="desc" style="margin-top:12px;margin-bottom:0">
      Negative-seed bins account for <strong style="color:#e2e8f0">{neg_total}</strong> of the {covered_count} hits ({neg_total/covered_count*100:.1f}%),
      positive-seed bins for <strong style="color:#e2e8f0">{pos_total}</strong> ({pos_total/covered_count*100:.1f}%).
      This lean toward negative seeds is a <strong>scan-order artifact</strong>, not a property of the RNG: each draw's "hitting seed" is the
      <em>first</em> one found scanning ascending from \u2212{abs(SEED_START):,}, so a negative seed is recorded whenever it happens to
      work before any positive seed is even tried \u2014 it says nothing about which seeds are more likely to hit.
    </p>
  </div>

  <div class="callout">
    <div class="lbl">\U0001f4ca 1000-draw result vs. the earlier 100-draw sample</div>
    <p>This full run across draws #{DRAW_START}\u2013{DRAW_END} ({total} draws) landed at <strong>{covered_pct:.1f}% coverage</strong> ({covered_count}/{total}).
    An earlier standalone scan of just the last 100 draws (#2024\u20132123) at this same \u00b11,000,000 seed range found <strong>{COMPARISON_100_COVERED}% coverage</strong> ({COMPARISON_100_COVERED}/100)
    \u2014 the two results sit in a similar band, suggesting ~88\u201392% coverage is roughly what this seed range delivers regardless of which 100\u2011ish draw window is sampled.</p>
    <p>{"As a cross-check: the last block of this 1000-draw run (#2024\u20132123) independently reproduced exactly " + str(last_block[3]) + "/100 covered \u2014 an exact match with that earlier standalone scan, confirming both runs are consistent." if cross_check_match else f"Note: the last block of this run (#2024\u20132123) shows {last_block[3]}/100 covered, which differs slightly from the earlier standalone scan's {COMPARISON_100_COVERED}/100 \u2014 worth double-checking if that matters for your analysis."}</p>
  </div>

  <p class="footer">
    Coverage = whether any seed in the tested range produced a 7-number pick containing all 6 of the draw's actual winning numbers.<br>
    Data read live from <code>seed_hit_k7</code> in <code>loto6_local.db</code>, populated by a parallelized background scan (7 workers, ~22 minutes) in a prior session.<br>
    Formula-based only \u00b7 Not financial advice \u00b7 Loto 6 is random.
  </p>
</div>

<script>
new Chart(document.getElementById('histChart').getContext('2d'), {{
  type: 'bar',
  data: {{
    labels: {hist_labels_json},
    datasets: [{{
      label: 'Hitting seeds',
      data: {hist_values_json},
      backgroundColor: function(ctx) {{
        const label = ctx.chart.data.labels[ctx.dataIndex];
        const val = parseInt(String(label).replace(/,/g, ''), 10);
        return val < 0 ? 'rgba(239,68,68,0.65)' : 'rgba(56,189,248,0.65)';
      }},
      borderColor: function(ctx) {{
        const label = ctx.chart.data.labels[ctx.dataIndex];
        const val = parseInt(String(label).replace(/,/g, ''), 10);
        return val < 0 ? '#ef4444' : '#38bdf8';
      }},
      borderWidth: 1,
    }}]
  }},
  options: {{
    responsive: true,
    maintainAspectRatio: false,
    plugins: {{
      legend: {{ display: false }},
      tooltip: {{
        callbacks: {{
          title: function(items) {{
            const start = parseInt(String(items[0].label).replace(/,/g, ''), 10);
            return 'Seed ' + start.toLocaleString() + ' to ' + (start + {BIN_WIDTH - 1}).toLocaleString();
          }},
          label: function(ctx) {{ return ctx.parsed.y + ' hits'; }}
        }}
      }}
    }},
    scales: {{
      y: {{
        beginAtZero: true,
        ticks: {{ color: '#64748b' }},
        grid: {{ color: '#1e293b' }},
        title: {{ display: true, text: '# of hitting seeds', color: '#64748b' }}
      }},
      x: {{
        ticks: {{ color: '#64748b', maxRotation: 60, minRotation: 60, autoSkip: true, maxTicksLimit: 20 }},
        grid: {{ display: false }},
        title: {{ display: true, text: 'Seed bucket start', color: '#64748b' }}
      }}
    }}
  }}
}});
</script>
</body>
</html>"""

with open(HTML_OUT, 'w', encoding='utf-8') as f:
    f.write(page)
print(f"Wrote {HTML_OUT} ({len(page)//1024} KB)")
print(f"Total: {total}  Covered: {covered_count} ({covered_pct:.2f}%)  Missed: {missed_count} ({missed_pct:.2f}%)")
print(f"Cross-check last block (#2024-2123): {last_block[3]}/100 vs known {COMPARISON_100_COVERED}/100 -> match={cross_check_match}")
