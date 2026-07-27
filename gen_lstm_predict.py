"""
gen_lstm_predict.py
Loads lstm_backtest.json + lstm_next_pred.json and generates public/lstm_predict.html
Run lstm_train.py first to produce those files.
"""
import json, os, statistics

BASE = os.path.dirname(__file__)

with open(os.path.join(BASE, "lstm_backtest.json"), encoding="utf-8") as f:
    bt_data = json.load(f)

with open(os.path.join(BASE, "lstm_next_pred.json"), encoding="utf-8") as f:
    next_data = json.load(f)

results  = bt_data["results"]
BT_DRAWS = bt_data["btDraws"]
N_PICKS  = bt_data["nPicks"]

next_serial = next_data["serial"]
latest_serial = next_data["latestSerial"]
latest_date   = next_data["latestDate"]
next_pred   = next_data["pred"]
next_scores = next_data["scores"]

mc = [r["matches"] for r in results]
avg = statistics.mean(mc)
rand_baseline = N_PICKS * 7 / 43
c4 = sum(1 for m in mc if m >= 4)
c5 = sum(1 for m in mc if m >= 5)
c6 = sum(1 for m in mc if m >= 6)
c7 = sum(1 for m in mc if m >= 7)

max_score = max(next_scores) if next_scores else 1.0
def score_tier(score):
    if score >= max_score * 0.7: return 2
    if score >= max_score * 0.4: return 1
    return 0

freq_tier = {str(next_pred[i]): score_tier(next_scores[i]) for i in range(len(next_pred))}
score_pct  = {str(next_pred[i]): round(next_scores[i] / max_score * 100) for i in range(len(next_pred))}

PAGE_DATA = {
    "nPicks": N_PICKS,
    "latestSerial": latest_serial,
    "latestDate": latest_date,
    "nextSerial": next_serial,
    "prediction": next_pred,
    "scorePct": score_pct,
    "freqTier": freq_tier,
    "btDraws": BT_DRAWS,
    "avgMatches": round(avg, 2),
    "randBaseline": round(rand_baseline, 2),
    "liftPct": round((avg / rand_baseline - 1) * 100, 1),
    "cnt4plus": c4, "cnt5plus": c5, "cnt6plus": c6, "cnt7plus": c7,
    "btResults": [
        {"s": r["serial"], "d": r["date"],
         "actual": r["actual"], "hitNums": r["hitNums"],
         "matches": r["matches"], "pred": r["pred"]}
        for r in reversed(results[-100:])
    ]
}

data_json = json.dumps(PAGE_DATA, ensure_ascii=False)
TIER_COLORS = ["#38bdf8", "#a78bfa", "#fbbf24"]
TIER_LABELS = ["Lower prob", "Mid prob", "High prob"]

HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>LSTM Neural Net Predict — Loto 6</title>
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
.subtitle{{font-size:.85rem;color:#64748b;margin-bottom:20px}}
.sec{{margin-bottom:28px}}
.sec-title{{font-size:.78rem;font-weight:700;color:#94a3b8;text-transform:uppercase;
  letter-spacing:.06em;margin-bottom:12px}}
.method-card{{background:#1e293b;border-radius:12px;padding:16px 20px;margin-bottom:20px;
  border-left:4px solid #a78bfa}}
.method-card .mc-title{{font-size:.78rem;font-weight:700;color:#a78bfa;
  text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px}}
.method-card .mc-body{{font-size:.85rem;color:#94a3b8;line-height:1.6}}
.arch-pills{{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}}
.arch-pill{{background:#0f172a;border:1px solid #334155;border-radius:6px;
  padding:4px 12px;font-size:.75rem;color:#94a3b8}}
.arch-pill span{{color:#a78bfa;font-weight:700}}
.stats-strip{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin-bottom:24px}}
.stat-card{{background:#1e293b;border-radius:10px;padding:14px 16px;text-align:center}}
.stat-card .sv{{font-size:1.6rem;font-weight:800}}
.stat-card .sl{{font-size:.72rem;color:#64748b;margin-top:2px}}
.stat-card .sd{{font-size:.78rem;margin-top:4px;color:#64748b}}
.legend{{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:12px}}
.legend-item{{display:flex;align-items:center;gap:6px;font-size:.78rem;color:#94a3b8}}
.legend-dot{{width:12px;height:12px;border-radius:50%}}
.ball-grid{{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:16px}}
.ball{{width:44px;height:44px;border-radius:50%;display:flex;align-items:center;
  justify-content:center;font-size:.9rem;font-weight:800;color:#fff;
  border:2px solid rgba(255,255,255,.15);cursor:default;transition:.12s}}
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
        <a href="/state_machine.html">&#128260; State Machine</a>
        <a href="/modular_cycle.html">&#128260; Modular Cycle</a>
        <a href="/next_relation.html">&#128279; Next Relation</a>
        <a href="/lstm_predict.html" class="active">&#129504; LSTM Neural Net</a>
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
  <h1>&#129504; LSTM Neural Net Predict</h1>
  <p class="subtitle">Walk-forward trained LSTM &middot; {N_PICKS} picks &middot; {BT_DRAWS}-draw backtest</p>

  <div class="method-card">
    <div class="mc-title">Method</div>
    <div class="mc-body">
      A small LSTM neural network is trained on sequences of the last 10 draws.
      It outputs a probability score for each of the 43 numbers and predicts
      the top {N_PICKS} most likely numbers for the next draw.
      Walk-forward: the model updates after each draw so it only ever
      uses past data to make predictions.
    </div>
    <div class="arch-pills">
      <div class="arch-pill">Sequence length <span>10</span></div>
      <div class="arch-pill">Hidden units <span>16</span></div>
      <div class="arch-pill">Optimizer <span>Adam</span></div>
      <div class="arch-pill">Initial training draws <span>{bt_data['initEnd']}</span></div>
    </div>
  </div>

  <div class="sec">
    <div class="sec-title">Backtest Performance &mdash; last {BT_DRAWS} draws</div>
    <div class="stats-strip" id="statsStrip"></div>
  </div>

  <div class="sec">
    <div class="sec-title">Predicted {N_PICKS} Numbers for Draw #<span id="nextS"></span></div>
    <div class="legend" id="legend"></div>
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
const TIER_COLORS = {json.dumps(TIER_COLORS)};
const TIER_LABELS = {json.dumps(TIER_LABELS)};

document.getElementById('nextS').textContent = D.nextSerial;

const statsData = [
  {{label:'6+ hit draws', val:D.cnt6plus, sub:`out of ${{D.btDraws}} draws`, color:'#fbbf24'}},
  {{label:'5+ hit draws', val:D.cnt5plus, sub:`4+ hits: ${{D.cnt4plus}}`, color:'#a78bfa'}},
  {{label:'7-hit draws',  val:D.cnt7plus, sub:'all 7 matched', color:'#34d399'}},
  {{label:'Avg matches',  val:D.avgMatches.toFixed(2),
    sub:`Random: ${{D.randBaseline.toFixed(2)}}`,
    color: D.avgMatches >= D.randBaseline ? '#4ade80' : '#fb923c'}},
];
const strip = document.getElementById('statsStrip');
statsData.forEach(s => {{
  strip.innerHTML += `<div class="stat-card">
    <div class="sv" style="color:${{s.color}}">${{s.val}}</div>
    <div class="sl">${{s.label}}</div><div class="sd">${{s.sub}}</div></div>`;
}});

const leg = document.getElementById('legend');
TIER_LABELS.forEach((lbl,i) => {{
  leg.innerHTML += `<div class="legend-item">
    <div class="legend-dot" style="background:${{TIER_COLORS[i]}}"></div>${{lbl}}</div>`;
}});

D.prediction.forEach(n => {{
  const tier = D.freqTier[String(n)] || 0;
  document.getElementById('balls').innerHTML +=
    `<div class="ball" style="background:${{TIER_COLORS[tier]}}"
      title="Prob: ${{D.scorePct[String(n)]}}%">${{n}}</div>`;
}});

const tbody = document.getElementById('btBody');
D.btResults.forEach(r => {{
  const m = r.matches;
  const cls = m>=7?'m-max':m>=6?'m-high':m>=5?'m-mid':'m-low';
  const hitSet = new Set(r.hitNums);
  const actual = r.actual.map(n => {{
    const isHit = hitSet.has(n);
    return `<span class="hit-ball" style="background:${{isHit?'#4ade80':'#1e293b'}};color:${{isHit?'#000':'#94a3b8'}}">${{n}}</span>`;
  }}).join('');
  const predBalls = (r.pred||[]).map(n => {{
    const isHit = hitSet.has(n);
    return `<span class="pred-mini ${{isHit?'pm-hit':'pm-selected'}}">${{n}}</span>`;
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
        <div style="font-size:.65rem;color:#475569;margin-bottom:3px">Predicted 28:</div>
        <div style="display:flex;flex-wrap:wrap;gap:3px">${{predBalls}}</div>
      </td>
    </tr>`;
}});
</script>
</body>
</html>"""

out = os.path.join(BASE, "public", "lstm_predict.html")
with open(out, "w", encoding="utf-8") as f:
    f.write(HTML)
print(f"Written: {out} ({len(HTML):,} bytes)")
print(f"6+ hits: {c6}/{BT_DRAWS}  avg: {avg:.4f}  rand: {rand_baseline:.4f}")
