"""
gen_custom_avg3.py
Strategy: Three-Draw Average
Sort all 7 numbers (6 main + bonus) from each of the last three draws.
Average each position across the three draws, round to nearest integer.
Clamp to 1-43, deduplicate. These are the predicted numbers (~7 picks).
Backtest: last 1000 draws, match against 7 numbers (6 main + bonus).
"""
import psycopg2, json, os, statistics

DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://neondb_owner:npg_QbHpRZW8of3C@ep-hidden-wind-a1q0el7s-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"
)

N_PICKS  = 7
BT_DRAWS = 1000

conn = psycopg2.connect(DB_URL)
cur  = conn.cursor()
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
        "all": sorted(nums + [r[8]])  # all 7 sorted
    })

N = len(draws)
test_start = max(3, N - BT_DRAWS)  # need 3 prior draws

def avg_predict(draw_a, draw_b, draw_c):
    """
    draw_a = N-3 (oldest), draw_b = N-2, draw_c = N-1 (newest).
    Average each position across 3 draws, round to nearest integer.
    Note: (int+int+int)/3 is never exactly .5, so no expansion needed.
    Clamp to 1-43, deduplicate.
    Returns (sorted_picks, raw_info)
    """
    a = draw_a["all"]
    b = draw_b["all"]
    c = draw_c["all"]
    preds = []
    raw_info = []
    for ai, bi, ci in zip(a, b, c):
        raw = (ai + bi + ci) / 3
        v = round(raw)
        v = max(1, min(43, v))
        preds.append(v)
        raw_info.append({"raw": round(raw, 3), "nums": [v], "a": ai, "b": bi, "c": ci})
    seen = set()
    result = []
    for v in sorted(preds):
        if v not in seen:
            seen.add(v)
            result.append(v)
    return result, raw_info

# Backtest
bt_results   = []
match_counts = []
pick_counts  = []
print(f"Backtesting last {BT_DRAWS} draws")

for i in range(test_start, N):
    pred, _ = avg_predict(draws[i-3], draws[i-2], draws[i-1])
    hits = set(pred) & set(draws[i]["all"])
    mc   = len(hits)
    match_counts.append(mc)
    pick_counts.append(len(pred))
    bt_results.append({
        "s": draws[i]["s"], "d": draws[i]["d"],
        "actual": draws[i]["all"],
        "hitNums": sorted(hits), "matches": mc,
        "pred": pred,
    })

avg_picks = statistics.mean(pick_counts)
avg       = statistics.mean(match_counts)
rand      = avg_picks * 7 / 43
lift      = round((avg / rand - 1) * 100, 1)
c0 = sum(1 for m in match_counts if m == 0)
c3 = sum(1 for m in match_counts if m >= 3)
c4 = sum(1 for m in match_counts if m >= 4)
c5 = sum(1 for m in match_counts if m >= 5)
c6 = sum(1 for m in match_counts if m >= 6)
c7 = sum(1 for m in match_counts if m >= 7)

print(f"Avg: {avg:.4f}  rand: {rand:.4f}  lift: {lift:+.1f}%")
print(f"6+: {c6}  5+: {c5}  4+: {c4}  3+: {c3}  0-hit: {c0}")

# Next draw prediction
next_serial        = draws[-1]["s"] + 1
next_pred, raw_info = avg_predict(draws[-3], draws[-2], draws[-1])
src_a_nums  = draws[-3]["all"]
src_b_nums  = draws[-2]["all"]
src_c_nums  = draws[-1]["all"]

PAGE_DATA = {
    "nPicks": len(next_pred),
    "avgPicks": round(avg_picks, 1),
    "latestSerial":  draws[-1]["s"],
    "latestDate":    draws[-1]["d"],
    "prevSerial":    draws[-2]["s"],
    "prevDate":      draws[-2]["d"],
    "prev2Serial":   draws[-3]["s"],
    "prev2Date":     draws[-3]["d"],
    "nextSerial": next_serial,
    "prediction": next_pred,
    "srcA": src_a_nums,
    "srcB": src_b_nums,
    "srcC": src_c_nums,
    "rawInfo": raw_info,
    "btDraws": BT_DRAWS,
    "avgMatches": round(avg, 2),
    "randBaseline": round(rand, 2),
    "liftPct": lift,
    "cnt0": c0,
    "cnt3plus": c3, "cnt4plus": c4, "cnt5plus": c5, "cnt6plus": c6, "cnt7plus": c7,
    "btResults": [
        {"s": r["s"], "d": r["d"], "actual": r["actual"],
         "hitNums": r["hitNums"], "matches": r["matches"],
         "pred": r["pred"]}
        for r in reversed(bt_results[-100:])
    ]
}

data_json = json.dumps(PAGE_DATA, ensure_ascii=False)

HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Three-Draw Average Predict -- Loto 6</title>
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
.nav-dropdown{{display:none;position:absolute;top:100%;left:0;
  background:transparent;padding-top:6px;z-index:10000;min-width:175px}}
.nav-dropdown-inner{{background:#0d1526;border:1px solid #1e293b;border-radius:10px;
  padding:6px;box-shadow:0 12px 32px rgba(0,0,0,.7)}}
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
.subtitle{{font-size:.85rem;color:#64748b;margin-bottom:20px}}
.sec{{margin-bottom:28px}}
.sec-title{{font-size:.78rem;font-weight:700;color:#94a3b8;text-transform:uppercase;
  letter-spacing:.06em;margin-bottom:12px}}
.method-card{{background:#1e293b;border-radius:12px;padding:16px 20px;margin-bottom:20px;
  border-left:4px solid #a78bfa}}
.method-card .mc-title{{font-size:.78rem;font-weight:700;color:#a78bfa;
  text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px}}
.method-card .mc-body{{font-size:.85rem;color:#94a3b8;line-height:1.6;margin-bottom:12px}}
.avg-table{{width:100%;border-collapse:collapse;font-size:.8rem;margin-top:10px}}
.avg-table th{{color:#475569;font-size:.68rem;text-transform:uppercase;
  letter-spacing:.06em;padding:4px 8px;text-align:center;border-bottom:1px solid #334155}}
.avg-table td{{padding:6px 8px;text-align:center;border-bottom:1px solid #1e293b}}
.avg-num{{display:inline-flex;align-items:center;justify-content:center;
  width:30px;height:30px;border-radius:50%;font-weight:700;font-size:.78rem}}
.an-a{{background:#1e3a5f;color:#60a5fa}}
.an-b{{background:#1a4731;color:#4ade80}}
.an-c{{background:#3b1f4f;color:#c4b5fd}}
.an-avg{{background:#334155;color:#f1f5f9}}
.an-pred{{background:#a78bfa;color:#0f172a}}
.arrow-cell{{color:#475569;font-size:1rem}}
.stats-strip{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin-bottom:24px}}
.stat-card{{background:#1e293b;border-radius:10px;padding:14px 16px;text-align:center}}
.stat-card .sv{{font-size:1.6rem;font-weight:800}}
.stat-card .sl{{font-size:.72rem;color:#64748b;margin-top:2px}}
.stat-card .sd{{font-size:.78rem;margin-top:4px;color:#64748b}}
.ball-grid{{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:16px}}
.ball{{width:52px;height:52px;border-radius:50%;display:flex;align-items:center;
  justify-content:center;font-size:1.1rem;font-weight:800;color:#f1f5f9;
  background:#7c3aed;border:3px solid #a78bfa;cursor:default;transition:.12s}}
.ball:hover{{transform:scale(1.08)}}
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
.pred-mini{{width:26px;height:26px;border-radius:50%;display:inline-flex;align-items:center;
  justify-content:center;font-size:.68rem;font-weight:700;margin:1px;flex-shrink:0}}
.pm-hit{{background:#dc2626;color:#fff;box-shadow:0 0 0 2px #f87171}}
.pm-selected{{background:#e2e8f0;color:#0f172a}}
.pred-row td{{background:#0c1420;border-bottom:2px solid #1e293b}}
</style>
</head>
<body>
<nav class="site-nav">
  <a class="nav-logo" href="/">&#127500; The<span>One</span>Lotto</a>
  <div class="nav-groups">
    <div class="nav-group">
      <div class="nav-group-btn">Data <span class="arrow">&#9660;</span></div>
      <div class="nav-dropdown"><div class="nav-dropdown-inner">
        <div class="nav-dd-label">Results</div>
        <a href="/">&#127968; Latest Draw</a>
        <a href="/history">&#128203; History</a>
        <a href="/numbers">&#128290; Numbers</a>
      </div></div>
    </div>
    <div class="nav-group">
      <div class="nav-group-btn">Predict <span class="arrow">&#9660;</span></div>
      <div class="nav-dropdown"><div class="nav-dropdown-inner">
        <div class="nav-dd-label">Prediction Tools</div>
        <a href="/predictions">&#127919; Predictions</a>
        <a href="/backtest.html">&#128202; Backtest</a>
        <a href="/combo_evo.html">&#129516; Combo Evo</a>
        <div class="nav-divider"></div>
        <div class="nav-dd-label">Strategy</div>
        <a href="/overdue.html">&#9203; Overdue</a>
        <a href="/state_machine.html">&#128260; State Machine</a>
        <a href="/modular_cycle.html">&#128260; Modular Cycle</a>
        <a href="/next_relation.html">&#128279; Next Relation</a>
        <a href="/lstm_predict.html">&#129504; LSTM Neural Net</a>
        <a href="/custom_avg.html">&#10133; Two-Draw Avg</a>
        <a href="/custom_avg3.html" class="active">&#10133; Three-Draw Avg</a>
      </div></div>
    </div>
    <div class="nav-group">
      <div class="nav-group-btn">Analyze <span class="arrow">&#9660;</span></div>
      <div class="nav-dropdown"><div class="nav-dropdown-inner">
        <div class="nav-dd-label">Pattern Analysis</div>
        <a href="/special.html">&#11088; Special</a>
        <a href="/consecutive.html">&#128279; Consecutive</a>
        <div class="nav-divider"></div>
        <div class="nav-dd-label">Position</div>
        <a href="/position.html">&#128205; Position Freq</a>
        <a href="/pos_predict.html">&#128202; Pos 1&#8211;6 Predict</a>
      </div></div>
    </div>
  </div>
</nav>
<main>
  <h1>&#10133; Three-Draw Average Predict</h1>
  <p class="subtitle">( Draw N-3 + Draw N-2 + Draw N-1 ) &divide; 3 &rarr; <span id="nPicksSub"></span> picks &middot; {BT_DRAWS}-draw backtest</p>

  <div class="method-card">
    <div class="mc-title">Method &mdash; How the numbers are calculated</div>
    <div class="mc-body">
      Sort all 7 numbers (6 main + bonus) from each of the three most recent draws.
      Average each position across the three draws. Round to nearest integer, clamp to 1&ndash;43,
      and resolve any duplicates.
    </div>
    <table class="avg-table" id="avgTable"></table>
  </div>

  <div class="sec">
    <div class="sec-title">Backtest Performance &mdash; last {BT_DRAWS} draws</div>
    <div class="stats-strip" id="statsStrip"></div>
  </div>

  <div class="sec">
    <div class="sec-title">Predicted <span id="nPicksTitle"></span> Numbers for Draw #<span id="nextS"></span></div>
    <div class="ball-grid" id="balls"></div>
  </div>

  <div class="sec">
    <div class="sec-title">Backtest &mdash; Last 100 Draws (newest first)</div>
    <table class="bt-table">
      <thead><tr>
        <th>Draw</th><th>Date</th><th>Actual Numbers</th><th>Hits</th><th></th>
      </tr></thead>
      <tbody id="btBody"></tbody>
    </table>
  </div>
</main>
<script>
const D = {data_json};

document.getElementById('nextS').textContent = D.nextSerial;
document.getElementById('nPicksSub').textContent = D.nPicks;
document.getElementById('nPicksTitle').textContent = D.nPicks;

// Method table
const tbl = document.getElementById('avgTable');
let hdr = '<tr><th>Draw #'+D.prev2Serial+' (N-3)</th><th></th><th>Draw #'+D.prevSerial+' (N-2)</th><th></th><th>Draw #'+D.latestSerial+' (N-1)</th><th></th><th>Average</th><th>&#8594; Predict</th></tr>';
tbl.innerHTML = hdr;
D.rawInfo.forEach((row, i) => {{
  tbl.innerHTML += `<tr>
    <td><span class="avg-num an-a">${{D.srcA[i]}}</span></td>
    <td class="arrow-cell">+</td>
    <td><span class="avg-num an-b">${{D.srcB[i]}}</span></td>
    <td class="arrow-cell">+</td>
    <td><span class="avg-num an-c">${{D.srcC[i]}}</span></td>
    <td class="arrow-cell">&divide;3</td>
    <td><span class="avg-num an-avg">${{row.raw}}</span></td>
    <td><span class="avg-num an-pred">${{row.nums[0]}}</span></td>
  </tr>`;
}});

// Stats
[
  {{label:'6+ hit draws', val:D.cnt6plus, sub:`5+: ${{D.cnt5plus}}  4+: ${{D.cnt4plus}}`, color:'#fbbf24'}},
  {{label:'0 hit draws',  val:D.cnt0, sub:`out of ${{D.btDraws}}`, color:'#fb923c'}},
  {{label:'Avg matches',  val:D.avgMatches.toFixed(2), sub:`Random: ${{D.randBaseline.toFixed(2)}}`,
    color: D.avgMatches >= D.randBaseline ? '#4ade80' : '#fb923c'}},
  {{label:'Lift vs random', val:(D.liftPct>=0?'+':'')+D.liftPct+'%', sub:'vs baseline',
    color: D.liftPct>=0?'#4ade80':'#fb923c'}},
].forEach(s => {{
  document.getElementById('statsStrip').innerHTML +=
    `<div class="stat-card"><div class="sv" style="color:${{s.color}}">${{s.val}}</div>
     <div class="sl">${{s.label}}</div><div class="sd">${{s.sub}}</div></div>`;
}});

// Predicted balls
D.prediction.forEach(n => {{
  document.getElementById('balls').innerHTML +=
    `<div class="ball">${{n}}</div>`;
}});

// Backtest table
const tbody = document.getElementById('btBody');
D.btResults.forEach(r => {{
  const m   = r.matches;
  const cls = m>=7?'m-max':m>=6?'m-high':m>=5?'m-mid':'m-low';
  const hitSet = new Set(r.hitNums);
  const actual = r.actual.map(n => {{
    const h = hitSet.has(n);
    return `<span class="hit-ball" style="background:${{h?'#4ade80':'#1e293b'}};color:${{h?'#000':'#94a3b8'}}">${{n}}</span>`;
  }}).join('');
  const predBalls = (r.pred||[]).map(n => {{
    const h = hitSet.has(n);
    return `<span class="pred-mini ${{h?'pm-hit':'pm-selected'}}">${{n}}</span>`;
  }}).join('');
  tbody.innerHTML += `
    <tr>
      <td style="color:#64748b">#${{r.s}}</td>
      <td style="color:#475569">${{r.d}}</td>
      <td>${{actual}}</td>
      <td>${{r.hitNums.join(', ')||'-'}}</td>
      <td><span class="match-badge ${{cls}}">${{m}}</span></td>
    </tr>
    <tr class="pred-row">
      <td colspan="5" style="padding:4px 10px 10px">
        <div style="font-size:.65rem;color:#475569;margin-bottom:3px">Predicted:</div>
        <div style="display:flex;flex-wrap:wrap;gap:3px">${{predBalls}}</div>
      </td>
    </tr>`;
}});
</script>
</body>
</html>"""

out = os.path.join(os.path.dirname(__file__), "public", "custom_avg3.html")
with open(out, "w", encoding="utf-8") as f:
    f.write(HTML)
print(f"Written: {out} ({len(HTML):,} bytes)")
print(f"Avg: {avg:.4f}  rand: {rand:.4f}  lift: {lift:+.1f}%")
print(f"6+: {c6}  5+: {c5}  4+: {c4}  0-hit: {c0}")
print(f"Next draw #{next_serial} prediction ({len(next_pred)} picks): {next_pred}")
print(f"  Src A (#{draws[-3]['s']}): {src_a_nums}")
print(f"  Src B (#{draws[-2]['s']}): {src_b_nums}")
print(f"  Src C (#{draws[-1]['s']}): {src_c_nums}")
