"""
gen_modular_cycle.py
Generates public/modular_cycle.html
Serial Cycle Predict: group draws by (draw_serial % 43).
For draw S, pool all past draws where serial % 43 == S % 43.
Rank by frequency, predict top 28 numbers.
"""
import psycopg2, json, os, statistics
from collections import Counter, defaultdict

DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://neondb_owner:npg_QbHpRZW8of3C@ep-hidden-wind-a1q0el7s-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"
)

N_PICKS = 28
BT_DRAWS = 1000

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
next_mod = next_serial % 43

# Group draw indices by serial % 43
mod_groups = defaultdict(list)
for i, d in enumerate(draws):
    mod_groups[d["s"] % 43].append(i)

def predict_serial_mod(idx, n_picks):
    """Pool numbers from all past draws with same serial%43. Rank by freq."""
    s = draws[idx]["s"]
    target_mod = s % 43
    past = [j for j in mod_groups[target_mod] if j < idx]
    if not past:
        return [], Counter(), []
    freq = Counter()
    for j in past:
        for n in draws[j]["all"]:
            freq[n] += 1
    top = [n for n, _ in freq.most_common(n_picks)]
    return top, freq, past

# --- Prediction for next draw ---
next_past = [j for j in mod_groups[next_mod]]  # includes latest draw
freq_next = Counter()
for j in next_past:
    for n in draws[j]["all"]:
        freq_next[n] += 1
next_pred = [n for n, _ in freq_next.most_common(N_PICKS)]
next_source_count = len(next_past)

# --- Backtest ---
bt_results = []
match_counts = []
for i in range(max(0, N - BT_DRAWS), N):
    d = draws[i]
    pred, freq, past = predict_serial_mod(i, N_PICKS)
    if not pred:
        match_counts.append(0)
        bt_results.append({"s": d["s"], "d": d["d"], "actual": sorted(d["all"]),
                           "hitNums": [], "matches": 0})
        continue
    pred_set = set(pred)
    hits = pred_set & d["all"]
    matches = len(hits)
    match_counts.append(matches)
    bt_results.append({
        "s": d["s"], "d": d["d"],
        "actual": sorted(d["all"]),
        "hitNums": sorted(hits),
        "matches": matches
    })

avg_matches = statistics.mean(match_counts)
rand_baseline = N_PICKS * 7 / 43
cnt_4plus = sum(1 for m in match_counts if m >= 4)
cnt_5plus = sum(1 for m in match_counts if m >= 5)
cnt_6plus = sum(1 for m in match_counts if m >= 6)
cnt_7plus = sum(1 for m in match_counts if m >= 7)
dist = [match_counts.count(i) for i in range(N_PICKS + 1)]

# Frequency color: divide into 3 tiers
max_freq = max(freq_next.values()) if freq_next else 1
def freq_tier(n):
    f = freq_next.get(n, 0)
    if f >= max_freq * 0.7: return 2
    if f >= max_freq * 0.4: return 1
    return 0

DATA = {
    "modVal": next_mod,
    "nPicks": N_PICKS,
    "latestSerial": latest["s"],
    "latestDate": latest["d"],
    "nextSerial": next_serial,
    "nextMod": next_mod,
    "sourceCount": next_source_count,
    "prediction": next_pred,
    "freqMap": {str(n): freq_next.get(n, 0) for n in next_pred},
    "freqTier": {str(n): freq_tier(n) for n in next_pred},
    "btDraws": BT_DRAWS,
    "avgMatches": round(avg_matches, 2),
    "randBaseline": round(rand_baseline, 2),
    "liftPct": round((avg_matches / rand_baseline - 1) * 100, 1),
    "cnt4plus": cnt_4plus,
    "cnt5plus": cnt_5plus,
    "cnt6plus": cnt_6plus,
    "cnt7plus": cnt_7plus,
    "matchDist": dist[:9],
    "btResults": [
        {"s": r["s"], "d": r["d"], "actual": r["actual"],
         "hitNums": r["hitNums"], "matches": r["matches"]}
        for r in reversed(bt_results[-100:])
    ]
}

data_json = json.dumps(DATA, ensure_ascii=False)

TIER_COLORS = ["#38bdf8", "#a78bfa", "#fbbf24"]  # low, mid, high freq
TIER_LABELS = ["Lower freq", "Mid freq", "High freq"]

HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Serial Cycle Predict — Loto 6</title>
<style>
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
main{{max-width:1100px;margin:0 auto;padding:24px 20px}}
h1{{font-size:1.4rem;font-weight:800;color:#f1f5f9;margin-bottom:4px}}
.subtitle{{font-size:.85rem;color:#64748b;margin-bottom:24px}}
.sec{{margin-bottom:28px}}
.sec-title{{font-size:.78rem;font-weight:700;color:#94a3b8;text-transform:uppercase;
  letter-spacing:.06em;margin-bottom:12px}}
.stats-strip{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin-bottom:24px}}
.stat-card{{background:#1e293b;border-radius:10px;padding:14px 16px;text-align:center}}
.stat-card .sv{{font-size:1.6rem;font-weight:800}}
.stat-card .sl{{font-size:.72rem;color:#64748b;margin-top:2px}}
.stat-card .sd{{font-size:.78rem;margin-top:4px;color:#64748b}}
.legend{{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:16px}}
.legend-item{{display:flex;align-items:center;gap:6px;font-size:.78rem;color:#94a3b8}}
.legend-dot{{width:12px;height:12px;border-radius:50%}}
.ball-grid{{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:16px}}
.ball{{width:44px;height:44px;border-radius:50%;display:flex;align-items:center;
  justify-content:center;font-size:.9rem;font-weight:800;color:#fff;position:relative;
  border:2px solid rgba(255,255,255,.15);cursor:default}}
.ball:hover{{transform:scale(1.08)}}
.method-card{{background:#1e293b;border-radius:12px;padding:16px 20px;margin-bottom:20px;
  border-left:4px solid #38bdf8}}
.method-card .mc-title{{font-size:.78rem;font-weight:700;color:#38bdf8;text-transform:uppercase;
  letter-spacing:.06em;margin-bottom:8px}}
.method-card .mc-body{{font-size:.85rem;color:#94a3b8;line-height:1.6}}
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
  <h1>&#128260; Serial Cycle Predict</h1>
  <p class="subtitle" id="sub"></p>

  <div class="method-card">
    <div class="mc-title">Method</div>
    <div class="mc-body" id="methodDesc"></div>
  </div>

  <div class="sec">
    <div class="sec-title">Backtest Performance (last <span id="btN"></span> draws)</div>
    <div class="stats-strip" id="statsStrip"></div>
  </div>

  <div class="sec">
    <div class="sec-title">Predicted <span id="npicks"></span> Numbers for Draw #<span id="nextS"></span></div>
    <div class="legend" id="legend"></div>
    <div class="ball-grid" id="balls"></div>
  </div>

  <div class="sec">
    <div class="sec-title">Backtest — Last 100 Draws (newest first)</div>
    <table class="bt-table">
      <thead><tr>
        <th>Draw</th><th>Date</th><th>Actual Numbers</th><th>Hits</th><th>&#8203;</th>
      </tr></thead>
      <tbody id="btBody"></tbody>
    </table>
  </div>
</main>

<script>
const D = {data_json};
const TIER_COLORS = {json.dumps(TIER_COLORS)};
const TIER_LABELS = {json.dumps(TIER_LABELS)};

document.getElementById('sub').textContent =
  `Draw serial % 43 = ${{D.nextMod}} · ${{D.sourceCount}} source draws · predict ${{D.nPicks}} numbers · ${{D.btDraws}}-draw backtest`;
document.getElementById('methodDesc').textContent =
  `Next draw is #${{D.nextSerial}}. ${{D.nextSerial}} ÷ 43 has remainder ${{D.nextMod}}. ` +
  `We find all ${{D.sourceCount}} past draws with the same remainder, count number frequency across them, ` +
  `and predict the top ${{D.nPicks}} most frequent numbers.`;
document.getElementById('btN').textContent = D.btDraws;
document.getElementById('nextS').textContent = D.nextSerial;
document.getElementById('npicks').textContent = D.nPicks;

// Stats
const statsData = [
  {{label:'6+ hit draws', val:D.cnt6plus, sub:`out of ${{D.btDraws}} draws`, color:'#fbbf24'}},
  {{label:'5+ hit draws', val:D.cnt5plus, sub:`4+ hits: ${{D.cnt4plus}}`, color:'#a78bfa'}},
  {{label:'7-hit draws', val:D.cnt7plus, sub:'all 7 matched', color:'#34d399'}},
  {{label:'Avg matches/draw', val:D.avgMatches.toFixed(2), sub:`Random: ${{D.randBaseline.toFixed(2)}}`, color: D.avgMatches >= D.randBaseline ? '#4ade80' : '#fb923c'}},
];
const strip = document.getElementById('statsStrip');
statsData.forEach(s => {{
  strip.innerHTML += `<div class="stat-card">
    <div class="sv" style="color:${{s.color}}">${{s.val}}</div>
    <div class="sl">${{s.label}}</div>
    <div class="sd">${{s.sub}}</div>
  </div>`;
}});

// Legend
const leg = document.getElementById('legend');
TIER_LABELS.forEach((lbl, i) => {{
  leg.innerHTML += `<div class="legend-item">
    <div class="legend-dot" style="background:${{TIER_COLORS[i]}}"></div>
    ${{lbl}}
  </div>`;
}});

// Balls
const ballGrid = document.getElementById('balls');
D.prediction.forEach(n => {{
  const tier = D.freqTier[String(n)] || 0;
  const freq = D.freqMap[String(n)] || 0;
  const color = TIER_COLORS[tier];
  ballGrid.innerHTML += `<div class="ball" style="background:${{color}}" title="Appears ${{freq}}x in source draws">
    ${{n}}
  </div>`;
}});

// Backtest table
const tbody = document.getElementById('btBody');
D.btResults.forEach(r => {{
  const m = r.matches;
  const cls = m >= 7 ? 'm-max' : m >= 6 ? 'm-high' : m >= 5 ? 'm-mid' : 'm-low';
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
print(f"N_PICKS={N_PICKS}, avg_matches={avg_matches:.4f}, rand_baseline={rand_baseline:.4f}")
print(f"6+ hits: {cnt_6plus}/1000  5+ hits: {cnt_5plus}/1000  4+: {cnt_4plus}/1000")
