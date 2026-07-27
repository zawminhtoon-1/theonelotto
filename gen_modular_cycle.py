"""
gen_modular_cycle.py
Generates public/modular_cycle.html
Multi-K prediction: pool 28 numbers from the 4 best-performing
K distances (K=23, K=10, K=5, K=1) — 7 numbers each.
"""
import psycopg2, json, os, statistics
from math import comb

DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://neondb_owner:npg_QbHpRZW8of3C@ep-hidden-wind-a1q0el7s-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"
)

# Best K combo for >=6 hit rate (found by find_best_k_combo.py)
K_VALUES = [23, 40, 38, 33]
N_PICKS = 28
BT_DRAWS = 1000  # backtest window

conn = psycopg2.connect(DB_URL)
cur = conn.cursor()
cur.execute("""
    SELECT draw_serial, draw_date, num1, num2, num3, num4, num5, num6, bonus
    FROM loto6_results ORDER BY draw_serial
""")
rows = cur.fetchall()
conn.close()

draws = []
for r in rows:
    nums = sorted([r[2], r[3], r[4], r[5], r[6], r[7]])
    draws.append({
        "s": r[0],
        "d": str(r[1])[:10] if r[1] else "",
        "n": nums,
        "b": r[8],
        "all": set(nums + [r[8]])
    })

N = len(draws)
latest = draws[-1]
next_serial = latest["s"] + 1

def predict_multi_k(idx, k_values, n_picks):
    """Pool numbers from draws at each K distance. Returns top n_picks by frequency."""
    freq = {}
    k_map = {}  # number -> which K index contributed it first
    for ki, k in enumerate(k_values):
        back = idx - k
        if back < 0:
            continue
        d = draws[back]
        for num in d["all"]:  # 7 numbers: 6 main + bonus
            if num not in freq:
                freq[num] = 0
                k_map[num] = ki
            freq[num] += 1
    ranked = sorted(freq.keys(), key=lambda x: (-freq[x], x))
    return ranked[:n_picks], freq, k_map

# --- Prediction for next draw ---
next_pred, next_freq, next_k_map = predict_multi_k(N, K_VALUES, N_PICKS)

# --- Backtest: last BT_DRAWS draws ---
bt_results = []
match_counts = []
for i in range(max(0, N - BT_DRAWS), N):
    d = draws[i]
    pred, freq, kmap = predict_multi_k(i, K_VALUES, N_PICKS)
    pred_set = set(pred)
    matches = len(pred_set & d["all"])
    match_counts.append(matches)
    bt_results.append({
        "s": d["s"],
        "d": d["d"],
        "actual": sorted(d["all"]),
        "pred_set": sorted(pred_set),
        "matches": matches,
        "hit_nums": sorted(pred_set & d["all"])
    })

avg_matches = statistics.mean(match_counts)
# Random baseline: E[matches] = 28 * 7 / 43 = 4.558...
rand_baseline = N_PICKS * 7 / 43
dist = [match_counts.count(i) for i in range(N_PICKS + 1)]
# Counts (raw)
cnt_1plus = sum(1 for m in match_counts if m >= 1)
cnt_4plus = sum(1 for m in match_counts if m >= 4)
cnt_5plus = sum(1 for m in match_counts if m >= 5)
cnt_6plus = sum(1 for m in match_counts if m >= 6)
cnt_7plus = sum(1 for m in match_counts if m >= 7)
# Percentages (for reference)
hit_1plus = cnt_1plus / len(match_counts) * 100
hit_4plus = cnt_4plus / len(match_counts) * 100
hit_5plus = cnt_5plus / len(match_counts) * 100
hit_6plus = cnt_6plus / len(match_counts) * 100

# Build data payload
DATA = {
    "kValues": K_VALUES,
    "nPicks": N_PICKS,
    "latestSerial": latest["s"],
    "latestDate": latest["d"],
    "nextSerial": next_serial,
    "prediction": next_pred,
    "kMap": {str(n): next_k_map.get(n, 0) for n in next_pred},
    "freqMap": {str(n): next_freq.get(n, 0) for n in next_pred},
    "btDraws": BT_DRAWS,
    "avgMatches": round(avg_matches, 2),
    "randBaseline": round(rand_baseline, 2),
    "liftPct": round((avg_matches / rand_baseline - 1) * 100, 1),
    "cnt1plus": cnt_1plus,
    "cnt4plus": cnt_4plus,
    "cnt5plus": cnt_5plus,
    "cnt6plus": cnt_6plus,
    "cnt7plus": cnt_7plus,
    "hit1plus": round(hit_1plus, 1),
    "hit4plus": round(hit_4plus, 1),
    "hit5plus": round(hit_5plus, 1),
    "hit6plus": round(hit_6plus, 1),
    "matchDist": dist[:10],
    "btResults": [
        {
            "s": r["s"], "d": r["d"],
            "actual": r["actual"],
            "hitNums": r["hit_nums"],
            "matches": r["matches"]
        }
        for r in reversed(bt_results[-100:])  # last 100, newest first
    ],
    # Source draws for next prediction
    "sourceDraws": [
        {
            "ki": ki,
            "k": k,
            "idx": N - k,
            "serial": draws[N - k]["s"] if N - k >= 0 else None,
            "date": draws[N - k]["d"] if N - k >= 0 else "",
            "nums": draws[N - k]["n"] if N - k >= 0 else [],
            "bonus": draws[N - k]["b"] if N - k >= 0 else None
        }
        for ki, k in enumerate(K_VALUES) if N - k >= 0
    ]
}

data_json = json.dumps(DATA, ensure_ascii=False)

# K colors and labels
CYCLE_COLORS = ["#38bdf8", "#a78bfa", "#34d399", "#fb923c"]
CYCLE_LABELS = [f"K={k}" for k in K_VALUES]

HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Multi-K Cycle Predict — Loto 6</title>
<style>
/* ====== SHARED FIXED NAV ====== */
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:system-ui,sans-serif;background:#0f172a;color:#e2e8f0;min-height:100vh;padding-top:60px}}
.site-nav{{position:fixed;top:0;left:0;right:0;height:52px;background:#0a0f1e;
  border-bottom:1px solid #1e293b;display:flex;align-items:center;padding:0 20px;
  gap:0;z-index:9999;box-shadow:0 2px 16px rgba(0,0,0,.6)}}
.site-nav .nav-logo{{font-size:1rem;font-weight:800;color:#f1f5f9;text-decoration:none;
  white-space:nowrap;margin-right:24px;flex-shrink:0}}
.site-nav .nav-logo span{{color:#38bdf8}}
.nav-groups{{display:flex;gap:4px;align-items:center}}
.nav-group{{position:relative}}
.nav-group-btn{{display:flex;align-items:center;gap:5px;padding:7px 14px;border-radius:7px;
  cursor:pointer;font-size:.82rem;font-weight:600;color:#94a3b8;
  border:1px solid transparent;transition:.15s;white-space:nowrap;user-select:none}}
.nav-group-btn:hover,.nav-group:hover .nav-group-btn{{color:#f1f5f9;background:#1e293b;border-color:#334155}}
.nav-group-btn .arrow{{font-size:.6rem;opacity:.6;transition:transform .2s}}
.nav-group:hover .nav-group-btn .arrow{{transform:rotate(180deg)}}
.nav-dropdown{{display:none;position:absolute;top:calc(100% + 6px);left:0;
  background:#0d1526;border:1px solid #1e293b;border-radius:10px;
  min-width:175px;padding:6px;box-shadow:0 12px 32px rgba(0,0,0,.7);z-index:10000}}
.nav-group:hover .nav-dropdown{{display:block}}
.nav-dropdown a{{display:flex;align-items:center;gap:8px;padding:8px 12px;
  border-radius:6px;color:#94a3b8;text-decoration:none;font-size:.82rem;
  white-space:nowrap;transition:.12s}}
.nav-dropdown a:hover,.nav-dropdown a.active{{color:#f1f5f9;background:#1e293b}}
.nav-dd-label{{font-size:.68rem;font-weight:700;color:#475569;padding:6px 12px 2px;
  text-transform:uppercase;letter-spacing:.06em}}
.nav-divider{{height:1px;background:#1e293b;margin:4px 0}}
/* ====== PAGE STYLES ====== */
main{{max-width:1100px;margin:0 auto;padding:24px 20px}}
h1{{font-size:1.4rem;font-weight:800;color:#f1f5f9;margin-bottom:4px}}
.subtitle{{font-size:.85rem;color:#64748b;margin-bottom:24px}}
.sec{{margin-bottom:28px}}
.sec-title{{font-size:.78rem;font-weight:700;color:#94a3b8;text-transform:uppercase;
  letter-spacing:.06em;margin-bottom:12px}}
/* Stats strip */
.stats-strip{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin-bottom:24px}}
.stat-card{{background:#1e293b;border-radius:10px;padding:14px 16px;text-align:center}}
.stat-card .sv{{font-size:1.6rem;font-weight:800;color:#38bdf8}}
.stat-card .sl{{font-size:.72rem;color:#64748b;margin-top:2px}}
.stat-card .sd{{font-size:.78rem;margin-top:4px}}
.good{{color:#4ade80}}.warn{{color:#fb923c}}.muted{{color:#64748b}}
/* Ball grid */
.ball-grid{{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:16px}}
.ball{{width:44px;height:44px;border-radius:50%;display:flex;align-items:center;
  justify-content:center;font-size:.9rem;font-weight:800;color:#fff;position:relative;
  border:2px solid rgba(255,255,255,.15);transition:.15s;cursor:default}}
.ball:hover{{transform:scale(1.08)}}
.ball .cyc{{position:absolute;bottom:-2px;right:-2px;width:14px;height:14px;
  border-radius:50%;font-size:.5rem;display:flex;align-items:center;justify-content:center;
  font-weight:800;border:1.5px solid #0f172a}}
/* Source draws */
.src-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px;margin-bottom:20px}}
.src-card{{background:#1e293b;border-radius:10px;padding:14px;border-left:4px solid}}
.src-card .sc-label{{font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px}}
.src-card .sc-info{{font-size:.75rem;color:#64748b;margin-bottom:8px}}
.src-balls{{display:flex;flex-wrap:wrap;gap:5px}}
.sm-ball{{width:34px;height:34px;border-radius:50%;display:flex;align-items:center;
  justify-content:center;font-size:.78rem;font-weight:800;color:#fff}}
/* Legend */
.legend{{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:20px}}
.legend-item{{display:flex;align-items:center;gap:6px;font-size:.78rem;color:#94a3b8}}
.legend-dot{{width:12px;height:12px;border-radius:50%}}
/* Backtest table */
.bt-table{{width:100%;border-collapse:collapse;font-size:.78rem}}
.bt-table th{{background:#0f172a;color:#64748b;padding:7px 10px;text-align:left;
  border-bottom:2px solid #1e293b;font-weight:600}}
.bt-table td{{padding:6px 10px;border-bottom:1px solid #1a2744}}
.bt-table tr:hover td{{background:#1a2234}}
.match-badge{{display:inline-flex;align-items:center;justify-content:center;
  width:24px;height:24px;border-radius:6px;font-weight:700;font-size:.8rem}}
.m-low{{background:#1e3a5f;color:#60a5fa}}
.m-mid{{background:#1a4731;color:#4ade80}}
.m-high{{background:#4a1d96;color:#c4b5fd}}
.m-max{{background:#78350f;color:#fbbf24}}
.hit-ball{{width:28px;height:28px;border-radius:50%;display:inline-flex;align-items:center;
  justify-content:center;font-size:.72rem;font-weight:800;margin:1px}}
</style>
</head>
<body>
<nav class="site-nav">
  <a class="nav-logo" href="/">Loto<span>6</span></a>
  <div class="nav-groups">
    <div class="nav-group">
      <div class="nav-group-btn">Data <span class="arrow">&#9660;</span></div>
      <div class="nav-dropdown">
        <div class="nav-dd-label">Results</div>
        <a href="/">&#127968; Latest Draw</a>
        <a href="/history">&#128203; History</a>
        <a href="/numbers">&#128290; Numbers</a>
      </div>
    </div>
    <div class="nav-group">
      <div class="nav-group-btn">Predict <span class="arrow">&#9660;</span></div>
      <div class="nav-dropdown">
        <div class="nav-dd-label">Prediction Tools</div>
        <a href="/predictions">&#127919; Predictions</a>
        <a href="/backtest.html">&#128202; Backtest</a>
        <a href="/combo_evo.html">&#129516; Combo Evo</a>
        <div class="nav-divider"></div>
        <div class="nav-dd-label">Strategy</div>
        <a href="/overdue.html">&#9203; Overdue</a>
        <a href="/miss_analysis.html">&#10060; Miss Analysis</a>
        <a href="/state_machine.html">&#128260; State Machine</a>
        <a href="/modular_cycle.html" class="active">&#128260; Modular Cycle</a>
      </div>
    </div>
    <div class="nav-group">
      <div class="nav-group-btn">Analyze <span class="arrow">&#9660;</span></div>
      <div class="nav-dropdown">
        <div class="nav-dd-label">Pattern Analysis</div>
        <a href="/special.html">&#11088; Special</a>
        <a href="/consecutive.html">&#128279; Consecutive</a>
        <div class="nav-divider"></div>
        <div class="nav-dd-label">Position</div>
        <a href="/position.html">&#128205; Position Freq</a>
        <a href="/pos_predict.html">&#128202; Pos 1&#8211;6 Predict</a>
      </div>
    </div>
  </div>
</nav>

<main>
  <h1>&#128260; Multi-K Cycle Predict</h1>
  <p class="subtitle" id="sub"></p>

  <div class="sec">
    <div class="sec-title">Performance Stats (last <span id="btN"></span> draws)</div>
    <div class="stats-strip" id="statsStrip"></div>
  </div>

  <div class="sec">
    <div class="sec-title">Predicted 28 Numbers for Draw #<span id="nextS"></span></div>
    <div class="legend" id="legend"></div>
    <div class="ball-grid" id="balls"></div>
  </div>

  <div class="sec">
    <div class="sec-title">Source Draws (K=23, 40, 38, 33 draws back from draw #<span id="latS"></span>)</div>
    <div class="src-grid" id="srcGrid"></div>
  </div>

  <div class="sec">
    <div class="sec-title">Backtest — Last 50 Draws (newest first)</div>
    <table class="bt-table">
      <thead><tr>
        <th>Draw</th><th>Date</th><th>Actual Numbers</th><th>Hits</th><th>Matches</th>
      </tr></thead>
      <tbody id="btBody"></tbody>
    </table>
  </div>
</main>

<script>
const D = {data_json};
const CYCLE_COLORS = {json.dumps(CYCLE_COLORS)};
const CYCLE_LABELS = {json.dumps(CYCLE_LABELS)};

document.getElementById('sub').textContent =
  `Predict ${{D.nPicks}} numbers using 4 best K values (${{CYCLE_LABELS.join(', ')}} draws back) · ${{D.btDraws}}-draw backtest`;
document.getElementById('btN').textContent = D.btDraws;
document.getElementById('nextS').textContent = D.nextSerial;
document.getElementById('latS').textContent = D.latestSerial;

// Stats
const statsData = [
  {{label:'6+ hit draws', val:D.cnt6plus, sub:`out of ${{D.btDraws}} draws`, color:'#fbbf24'}},
  {{label:'5+ hit draws', val:D.cnt5plus, sub:`4+ hits: ${{D.cnt4plus}}`, color:'#a78bfa'}},
  {{label:'7-hit draws', val:D.cnt7plus, sub:'all 7 matched', color:'#34d399'}},
  {{label:'Avg matches/draw', val:D.avgMatches.toFixed(2), sub:`Random: ${{D.randBaseline.toFixed(2)}}`, color: D.avgMatches > D.randBaseline ? '#4ade80' : '#fb923c'}},
];
const strip = document.getElementById('statsStrip');
statsData.forEach(s => {{
  strip.innerHTML += `<div class="stat-card">
    <div class="sv" style="color:${{s.color}}">${{s.val}}</div>
    <div class="sl">${{s.label}}</div>
    <div class="sd muted">${{s.sub}}</div>
  </div>`;
}});

// Legend
const leg = document.getElementById('legend');
CYCLE_LABELS.forEach((lbl,i) => {{
  leg.innerHTML += `<div class="legend-item">
    <div class="legend-dot" style="background:${{CYCLE_COLORS[i]}}"></div>
    ${{lbl}} draws back
  </div>`;
}});
leg.innerHTML += `<div class="legend-item">
  <div class="legend-dot" style="background:#475569"></div>
  Multiple cycles
</div>`;

// Balls
const ballGrid = document.getElementById('balls');
D.prediction.forEach(n => {{
  const ki = D.kMap[String(n)] !== undefined ? D.kMap[String(n)] : 0;
  const freq = D.freqMap[String(n)] || 1;
  const color = freq > 1 ? '#475569' : CYCLE_COLORS[ki % CYCLE_COLORS.length];
  const kLabel = D.kValues[ki];
  ballGrid.innerHTML += `<div class="ball" style="background:${{color}}" title="K=${{kLabel}}, appears ${{freq}}x">
    ${{n}}
    <div class="cyc" style="background:${{CYCLE_COLORS[ki%CYCLE_COLORS.length]}};color:#fff">${{kLabel}}</div>
  </div>`;
}});

// Source draws
const srcGrid = document.getElementById('srcGrid');
D.sourceDraws.forEach((sd,i) => {{
  const color = CYCLE_COLORS[sd.ki % CYCLE_COLORS.length];
  const label = `K=${{sd.k}}`;
  const allNums = [...sd.nums, sd.bonus];
  const ballsHtml = allNums.map((n,j) => {{
    const isBonus = j === allNums.length - 1;
    const bg = isBonus ? '#f59e0b' : color;
    return `<div class="sm-ball" style="background:${{bg}}">${{n}}</div>`;
  }}).join('');
  srcGrid.innerHTML += `<div class="src-card" style="border-color:${{color}}">
    <div class="sc-label" style="color:${{color}}">${{label}} draws back</div>
    <div class="sc-info">Draw #${{sd.serial}} &nbsp;·&nbsp; ${{sd.date}}</div>
    <div class="src-balls">${{ballsHtml}}</div>
  </div>`;
}});

// Backtest table
const tbody = document.getElementById('btBody');
D.btResults.forEach(r => {{
  const m = r.matches;
  const cls = m >= 6 ? 'm-max' : m >= 5 ? 'm-high' : m >= 4 ? 'm-mid' : 'm-low';
  const hitSet = new Set(r.hitNums);
  const actualHtml = r.actual.map(n => {{
    const isHit = hitSet.has(n);
    const isBonus = r.actual.indexOf(n) === 6;
    const bg = isHit ? (isBonus ? '#f59e0b' : '#4ade80') : '#1e293b';
    const color = isHit ? '#000' : '#94a3b8';
    return `<span class="hit-ball" style="background:${{bg}};color:${{color}}">${{n}}</span>`;
  }}).join('');
  tbody.innerHTML += `<tr>
    <td style="color:#64748b">#${{r.s}}</td>
    <td style="color:#475569">${{r.d}}</td>
    <td>${{actualHtml}}</td>
    <td>${{r.hitNums.join(', ')||'-'}}</td>
    <td><span class="match-badge ${{cls}}">${{m}}</span></td>
  </tr>`;
}});
</script>
</body>
</html>"""

out_path = os.path.join(os.path.dirname(__file__), "public", "modular_cycle.html")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(HTML)
print(f"Written: {out_path} ({len(HTML):,} bytes)")
print(f"K_VALUES={K_VALUES}, N_PICKS={N_PICKS}, avg_matches={avg_matches:.4f}, rand_baseline={rand_baseline:.4f}")
print(f"Lift: {(avg_matches/rand_baseline-1)*100:+.2f}%  >=4hits: {hit_4plus:.1f}%  >=6hits: {hit_6plus:.1f}%")
