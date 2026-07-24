"""
Generate state_machine.html — Sum-bucket Markov chain prediction for Loto 6.

States (5 sum buckets):
  S0: sum <= 90   (very low)
  S1: 91-120      (low)
  S2: 121-150     (medium)
  S3: 151-180     (high)
  S4: sum > 180   (very high)

For each draw, look at the previous draw's state → learn transitions.
Prediction: current state → most likely next state → top-6 numbers from that state.
Backtest: walk-forward 1000 draws.
"""
import psycopg2, json, collections

OUT_PATH = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto\public\state_machine.html"

DB_URL = "postgresql://neondb_owner:npg_QbHpRZW8of3C@ep-hidden-wind-a1q0el7s-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"

BUCKETS = [
    (0,   90,  "Very Low",  "≤90",  "#6366f1"),
    (91,  120, "Low",       "91–120","#3b82f6"),
    (121, 150, "Medium",    "121–150","#22c55e"),
    (151, 180, "High",      "151–180","#f59e0b"),
    (181, 999, "Very High", ">180",  "#ef4444"),
]

def get_state(s):
    for i, (lo, hi, *_) in enumerate(BUCKETS):
        if lo <= s <= hi:
            return i
    return 4

print("Fetching draws...")
conn = psycopg2.connect(DB_URL)
cur = conn.cursor()
cur.execute("SELECT draw_serial, draw_date, num1,num2,num3,num4,num5,num6 FROM loto6_results ORDER BY draw_serial")
rows = cur.fetchall()
conn.close()

draws = [{"s": r[0], "d": str(r[1])[:10] if r[1] else "",
          "n": sorted([r[2],r[3],r[4],r[5],r[6],r[7]]),
          "sum": r[2]+r[3]+r[4]+r[5]+r[6]+r[7]} for r in rows]
T = len(draws)
for d in draws:
    d["state"] = get_state(d["sum"])
print(f"Total draws: {T}, latest: {draws[-1]['s']} ({draws[-1]['d']})")

# ── Transition matrix (all-time) ──────────────────────────────────────────────
N_STATES = 5
trans = [[0]*N_STATES for _ in range(N_STATES)]   # trans[from][to]
for i in range(1, T):
    trans[draws[i-1]["state"]][draws[i]["state"]] += 1

# Normalize to probabilities
trans_prob = []
for row in trans:
    total = sum(row)
    trans_prob.append([round(c/total, 4) if total else 0 for c in row])

print("Transition matrix (counts):")
for i, row in enumerate(trans):
    print(f"  {BUCKETS[i][2]:10s} ->", row, " most likely:", BUCKETS[trans_prob[i].index(max(trans_prob[i]))][2])

# ── Number frequency per state (what numbers appear when in state S) ──────────
state_num_freq = [[0]*43 for _ in range(N_STATES)]
for d in draws:
    for n in d["n"]:
        state_num_freq[d["state"]][n-1] += 1

# ── Number frequency in draws that FOLLOW state S (for prediction) ──────────
# pred_num_freq[s] = frequency of each number in draws that come AFTER a draw in state s
pred_num_freq = [[0]*43 for _ in range(N_STATES)]
pred_count = [0]*N_STATES
for i in range(1, T):
    prev_state = draws[i-1]["state"]
    for n in draws[i]["n"]:
        pred_num_freq[prev_state][n-1] += 1
    pred_count[prev_state] += 1

# Top-6 prediction per state (numbers most likely to follow each state)
def top6_for_state(s, exclude=None):
    freq = pred_num_freq[s]
    ranked = sorted(range(43), key=lambda i: -freq[i])
    result = []
    for i in ranked:
        n = i+1
        if exclude and n in exclude:
            continue
        result.append(n)
        if len(result) == 6:
            break
    return result

# ── Walk-forward backtest (last 1000 draws) ───────────────────────────────────
BT_DRAWS = 1000
test_start = T - BT_DRAWS

# Build walk-forward transition and freq tables incrementally
wf_trans = [[0]*N_STATES for _ in range(N_STATES)]
wf_pred_freq = [[0]*43 for _ in range(N_STATES)]
wf_pred_cnt = [0]*N_STATES

# Seed with pre-test history
for i in range(1, test_start):
    ps = draws[i-1]["state"]
    wf_trans[ps][draws[i]["state"]] += 1
    for n in draws[i]["n"]:
        wf_pred_freq[ps][n-1] += 1
    wf_pred_cnt[ps] += 1

BT = []
HIT_DIST = [0]*7
TOTAL_HITS = 0

print(f"Backtesting {BT_DRAWS} draws...")
for i in range(test_start, T):
    d = draws[i]
    prev_state = draws[i-1]["state"] if i > 0 else 0

    # Predict: top-6 from wf_pred_freq[prev_state]
    freq = wf_pred_freq[prev_state]
    ranked = sorted(range(43), key=lambda x: -freq[x])
    pred = sorted([ranked[j]+1 for j in range(6)])

    actual_set = set(d["n"])
    pred_set = set(pred)
    hits = sorted(pred_set & actual_set)
    hc = len(hits)
    HIT_DIST[hc] += 1
    TOTAL_HITS += hc

    # Most likely next state
    row = wf_trans[prev_state]
    total_row = sum(row)
    likely_next = row.index(max(row)) if total_row else prev_state

    BT.append({
        "s": d["s"], "d": d["d"],
        "n": d["n"], "sum": d["sum"],
        "state": d["state"],
        "prevState": prev_state,
        "likelyNext": likely_next,
        "pr": pred, "h": hits, "hc": hc,
    })

    # Update walk-forward tables
    wf_trans[prev_state][d["state"]] += 1
    for n in d["n"]:
        wf_pred_freq[prev_state][n-1] += 1
    wf_pred_cnt[prev_state] += 1

avg_hits = TOTAL_HITS / BT_DRAWS
rand_avg = 6*6/43
lift = avg_hits / rand_avg

print(f"Avg hits: {avg_hits:.4f}  Random: {rand_avg:.4f}  Lift: {lift:.3f}x")
print(f"Hit dist: {HIT_DIST}")

# Current state and prediction
current_state = draws[-1]["state"]
current_pred = top6_for_state(current_state)
trans_row = trans_prob[current_state]
likely_next_state = trans_row.index(max(trans_row))

print(f"\nCurrent draw #{draws[-1]['s']}: sum={draws[-1]['sum']}, state={BUCKETS[current_state][2]}")
print(f"Most likely next state: {BUCKETS[likely_next_state][2]} ({max(trans_row)*100:.1f}%)")
print(f"Prediction for draw #{draws[-1]['s']+1}: {current_pred}")

# ── Recent state sequence (last 50) ──────────────────────────────────────────
recent_states = [{"s": d["s"], "d": d["d"], "sum": d["sum"], "state": d["state"]} for d in draws[-50:]]

# ── Bucket stats ──────────────────────────────────────────────────────────────
bucket_counts = [sum(1 for d in draws if d["state"]==s) for s in range(N_STATES)]
bucket_pcts = [round(c/T*100, 1) for c in bucket_counts]

# ── Serialize data ────────────────────────────────────────────────────────────
DATA = {
    "buckets": [{"label": b[2], "range": b[3], "color": b[4]} for b in BUCKETS],
    "transCounts": trans,
    "transProb": trans_prob,
    "stateNumFreq": state_num_freq,   # what numbers appear IN each state
    "predNumFreq": pred_num_freq,     # what numbers follow each state
    "predCount": pred_count,
    "currentState": current_state,
    "currentSum": draws[-1]["sum"],
    "likelyNextState": likely_next_state,
    "currentPred": current_pred,
    "topPredPerState": [top6_for_state(s) for s in range(N_STATES)],
    "recentStates": recent_states,
    "bucketCounts": bucket_counts,
    "bucketPcts": bucket_pcts,
    "bt": list(reversed(BT))[:200],
    "hdist": HIT_DIST,
    "avgHits": round(avg_hits, 4),
    "randAvg": round(rand_avg, 4),
    "lift": round(lift, 4),
    "btDraws": BT_DRAWS,
    "totalDraws": T,
    "latestSerial": draws[-1]["s"],
    "latestDate": draws[-1]["d"],
}

DATA_JSON = json.dumps(DATA, separators=(",", ":"))
print(f"\nJSON size: {len(DATA_JSON):,} bytes")

# ── Generate HTML ─────────────────────────────────────────────────────────────
NAV_HTML = """
<nav class="site-nav">
  <a class="nav-logo" href="/">🎱 The<span>One</span>Lotto</a>
  <div class="nav-groups">
    <div class="nav-group">
      <div class="nav-group-btn">Data <span class="arrow">▼</span></div>
      <div class="nav-dropdown">
        <div class="nav-dd-label">Results</div>
        <a href="/">🏠 Latest Draw</a>
        <a href="/history">📋 History</a>
        <a href="/numbers">🔢 Numbers</a>
      </div>
    </div>
    <div class="nav-group">
      <div class="nav-group-btn">Predict <span class="arrow">▼</span></div>
      <div class="nav-dropdown">
        <div class="nav-dd-label">Prediction Tools</div>
        <a href="/predictions">🎯 Predictions</a>
        <a href="/backtest.html">📊 Backtest</a>
        <a href="/combo_evo.html">🧬 Combo Evo</a>
        <div class="nav-divider"></div>
        <div class="nav-dd-label">Strategy</div>
        <a href="/overdue.html">⏳ Overdue</a>
        <a href="/miss_analysis.html">❌ Miss Analysis</a>
        <a href="/state_machine.html" class="active">🔄 State Machine</a>
      </div>
    </div>
    <div class="nav-group">
      <div class="nav-group-btn">Analyze <span class="arrow">▼</span></div>
      <div class="nav-dropdown">
        <div class="nav-dd-label">Pattern Analysis</div>
        <a href="/special.html">⭐ Special</a>
        <a href="/consecutive.html">🔗 Consecutive</a>
        <div class="nav-divider"></div>
        <div class="nav-dd-label">Position</div>
        <a href="/position.html">📍 Position Freq</a>
        <a href="/position.html#pos1pred">🎯 Pos-1 Predict</a>
      </div>
    </div>
  </div>
</nav>
"""

HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>State Machine — Loto 6</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:system-ui,sans-serif;background:#0f172a;color:#e2e8f0;min-height:100vh;padding-top:52px}}

/* ====== SHARED FIXED NAV ====== */
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
  min-width:170px;padding:6px;box-shadow:0 12px 32px rgba(0,0,0,.7);z-index:10000}}
.nav-group:hover .nav-dropdown{{display:block}}
.nav-dropdown a{{display:flex;align-items:center;gap:8px;padding:8px 12px;
  border-radius:6px;color:#94a3b8;text-decoration:none;font-size:.82rem;
  white-space:nowrap;transition:.12s}}
.nav-dropdown a:hover,.nav-dropdown a.active{{color:#f1f5f9;background:#1e293b}}
.nav-dd-label{{font-size:.68rem;font-weight:700;color:#475569;padding:6px 12px 2px;
  text-transform:uppercase;letter-spacing:.06em}}
.nav-divider{{height:1px;background:#1e293b;margin:4px 0}}
/* ============================== */

main{{max-width:1200px;margin:0 auto;padding:24px 20px}}
h1{{font-size:1.4rem;font-weight:800;color:#f1f5f9;margin-bottom:4px}}
.subtitle{{font-size:.85rem;color:#64748b;margin-bottom:24px}}

.section{{margin-bottom:32px}}
.section-title{{font-size:.8rem;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:.06em;margin-bottom:12px}}

/* State badges */
.state-badge{{display:inline-flex;align-items:center;gap:6px;padding:5px 14px;border-radius:8px;font-size:.82rem;font-weight:700;border:1px solid}}

/* Current state card */
.state-hero{{background:#1e293b;border-radius:14px;padding:24px;margin-bottom:24px;display:flex;gap:24px;flex-wrap:wrap;align-items:center}}
.state-hero-main{{flex:1;min-width:200px}}
.state-hero-main h2{{font-size:1.1rem;font-weight:800;margin-bottom:4px}}
.state-hero-main p{{font-size:.82rem;color:#64748b}}
.state-flow{{display:flex;align-items:center;gap:12px;flex-wrap:wrap}}
.flow-box{{background:#0f172a;border-radius:10px;padding:12px 20px;text-align:center;min-width:120px}}
.flow-box .fv{{font-size:1.3rem;font-weight:800}}
.flow-box .fl{{font-size:.72rem;color:#64748b;margin-top:2px}}
.flow-arrow{{font-size:1.4rem;color:#334155}}
.flow-pct{{font-size:.78rem;color:#64748b;text-align:center}}

/* Prediction combo */
.combo-row{{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:16px}}
.combo-ball{{width:52px;height:52px;border-radius:50%;display:flex;align-items:center;justify-content:center;
  font-size:1.1rem;font-weight:800;box-shadow:0 2px 10px #0004}}

/* Transition matrix */
.matrix-wrap{{overflow-x:auto}}
.matrix{{border-collapse:collapse;font-size:.8rem}}
.matrix th,.matrix td{{padding:8px 12px;border:1px solid #1e293b;text-align:center}}
.matrix th{{background:#0f172a;color:#94a3b8;font-size:.72rem}}
.matrix .row-header{{font-weight:700;text-align:left;white-space:nowrap;color:#e2e8f0}}
.matrix .prob-cell{{border-radius:4px;font-weight:600}}

/* Bucket frequency grid */
.bucket-grid{{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:20px}}
.bucket-card{{background:#1e293b;border-radius:10px;padding:14px;border-top:3px solid}}
.bucket-card h4{{font-size:.8rem;font-weight:700;margin-bottom:8px}}
.bucket-stat{{font-size:.72rem;color:#64748b;margin-bottom:4px}}
.bucket-nums{{display:flex;flex-wrap:wrap;gap:3px;margin-top:8px}}
.bnum{{width:28px;height:28px;border-radius:6px;display:flex;align-items:center;justify-content:center;font-size:.72rem;font-weight:700;background:#0f172a;color:#94a3b8}}
.bnum.top{{background:#1e3a5f;color:#38bdf8;border:1px solid #38bdf855}}

/* Sparkline/sequence */
.seq-wrap{{display:flex;gap:3px;flex-wrap:wrap;margin-bottom:8px}}
.seq-dot{{width:14px;height:14px;border-radius:3px;cursor:pointer;transition:.15s}}
.seq-dot:hover{{transform:scale(1.3)}}

/* Stats row */
.stats-row{{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:20px}}
.stat-box{{background:#1e293b;border-radius:8px;padding:10px 18px;min-width:110px}}
.stat-box .sv{{font-size:1.3rem;font-weight:800;color:#f1f5f9}}
.stat-box .sl{{font-size:.72rem;color:#64748b;margin-top:2px}}

/* Hit distribution */
.dist-row{{display:flex;gap:4px;align-items:flex-end;height:64px;margin-bottom:4px}}
.dist-bar-wrap{{display:flex;flex-direction:column;align-items:center;flex:1}}
.dist-bar{{width:100%;border-radius:3px 3px 0 0;min-height:2px}}
.dist-bar.d0{{background:#ef4444}}.dist-bar.d1{{background:#f97316}}
.dist-bar.d2{{background:#eab308}}.dist-bar.d3{{background:#22c55e}}
.dist-bar.d4{{background:#06b6d4}}.dist-bar.d5{{background:#8b5cf6}}
.dist-bar.d6{{background:#ec4899}}
.dist-label{{font-size:.65rem;color:#64748b;margin-top:2px}}

/* Backtest table */
.bt-wrap{{max-height:480px;overflow-y:auto;border-radius:8px}}
.bt-tbl{{width:100%;border-collapse:collapse;font-size:.8rem}}
.bt-tbl th{{background:#1e293b;padding:6px 8px;color:#94a3b8;font-size:.72rem;font-weight:600;text-align:left;position:sticky;top:0;z-index:2}}
.bt-tbl td{{padding:5px 8px;border-bottom:1px solid #0f172a;vertical-align:middle}}
.bt-tbl tr:hover td{{background:#1e3a5f22}}
.bt-tbl tr.hit td:first-child{{border-left:3px solid #22c55e}}
.bt-tbl tr.miss td:first-child{{border-left:3px solid #ef444488}}
.ball{{display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;
  border-radius:50%;font-size:.72rem;font-weight:700;margin:1px;background:#1e3a5f;color:#93c5fd}}
.ball.b-hit{{border:2px solid #22c55e}}
.pred-chip{{display:inline-flex;align-items:center;justify-content:center;min-width:26px;height:22px;
  border-radius:5px;font-size:.72rem;font-weight:700;padding:0 5px;margin:1px}}
.pc-hit{{background:#14532d;color:#4ade80;border:1px solid #4ade80}}
.pc-miss{{background:#1e293b;color:#64748b;border:1px solid #334155}}

@media(max-width:640px){{
  .bucket-grid{{grid-template-columns:1fr 1fr}}
  .state-flow{{flex-direction:column;align-items:flex-start}}
}}
</style>
</head>
<body>
{NAV_HTML}
<main>
  <h1>🔄 State Machine Prediction</h1>
  <p class="subtitle">Sum-bucket Markov chain — each draw's total sum defines its state, transition probabilities predict the next state's number distribution.</p>

  <!-- Current State Hero -->
  <div class="section">
    <div class="section-title">Current State → Prediction</div>
    <div class="state-hero">
      <div class="state-hero-main">
        <h2 id="heroTitle">Loading...</h2>
        <p id="heroSub"></p>
      </div>
      <div class="state-flow" id="stateFlow"></div>
    </div>
    <div class="section-title">Predicted Numbers for Draw #<span id="nextDrawNum"></span></div>
    <div class="combo-row" id="comboRow"></div>
  </div>

  <!-- Transition Matrix -->
  <div class="section">
    <div class="section-title">Transition Matrix (row = current state → col = next state)</div>
    <div class="matrix-wrap"><table class="matrix" id="transMatrix"></table></div>
  </div>

  <!-- Bucket Stats -->
  <div class="section">
    <div class="section-title">Bucket Profiles — Top Numbers per State</div>
    <div class="bucket-grid" id="bucketGrid"></div>
  </div>

  <!-- State Sequence -->
  <div class="section">
    <div class="section-title">Recent 50-Draw State Sequence</div>
    <div class="seq-wrap" id="seqWrap"></div>
    <div style="display:flex;gap:12px;flex-wrap:wrap;margin-top:8px" id="seqLegend"></div>
  </div>

  <!-- Backtest -->
  <div class="section">
    <div class="section-title">Walk-Forward Backtest — Last 1000 Draws</div>
    <div class="stats-row" id="btStats"></div>
    <div class="section-title" style="margin-top:4px">Hit Distribution</div>
    <div class="dist-row" id="distRow"></div>
    <div class="dist-row" id="distLabels" style="height:auto"></div>
  </div>

  <!-- Table -->
  <div class="section">
    <div class="section-title">Recent Draws</div>
    <div class="bt-wrap"><table class="bt-tbl">
      <thead><tr><th>Draw</th><th>Date</th><th>Sum</th><th>State</th><th>Actual</th><th>Predicted</th><th>Hits</th></tr></thead>
      <tbody id="btBody"></tbody>
    </table></div>
  </div>
</main>

<script>
const D = {DATA_JSON};

const BUCKET_COLORS = D.buckets.map(b => b.color);

function hexToRgba(hex, a) {{
  const r = parseInt(hex.slice(1,3),16), g = parseInt(hex.slice(3,5),16), b = parseInt(hex.slice(5,7),16);
  return `rgba(${{r}},${{g}},${{b}},${{a}})`;
}}

// ── Hero ────────────────────────────────────────────────────────────────────
const cs = D.currentState, ns = D.likelyNextState;
document.getElementById('heroTitle').textContent =
  `Draw #${{D.latestSerial}} — Sum ${{D.currentSum}} → "${{D.buckets[cs].label}}" (${{D.buckets[cs].range}})`;
document.getElementById('heroSub').textContent =
  `Most likely next state: "${{D.buckets[ns].label}}" (${{Math.round(D.transProb[cs][ns]*100)}}% probability)`;
document.getElementById('nextDrawNum').textContent = D.latestSerial + 1;

const flow = document.getElementById('stateFlow');
flow.innerHTML = `
  <div class="flow-box">
    <div class="fv" style="color:${{BUCKET_COLORS[cs]}}">${{D.buckets[cs].label}}</div>
    <div class="fl">Current state<br>sum ${{D.currentSum}}</div>
  </div>
  <div style="text-align:center">
    <div class="flow-arrow">→</div>
    <div class="flow-pct">${{Math.round(D.transProb[cs][ns]*100)}}%</div>
  </div>
  <div class="flow-box">
    <div class="fv" style="color:${{BUCKET_COLORS[ns]}}">${{D.buckets[ns].label}}</div>
    <div class="fl">Predicted next<br>state</div>
  </div>`;

// Combo
const combo = D.currentPred;
const cr = document.getElementById('comboRow');
cr.innerHTML = combo.map((n,i) =>
  `<div class="combo-ball" style="background:linear-gradient(135deg,${{BUCKET_COLORS[ns]}}99,${{BUCKET_COLORS[ns]}}44)">${{n}}</div>`
).join('') + `<span style="color:#64748b;font-size:.82rem;margin-left:8px">based on → "${{D.buckets[ns].label}}" state distribution</span>`;

// ── Transition Matrix ────────────────────────────────────────────────────────
const tbl = document.getElementById('transMatrix');
let thead = '<tr><th style="text-align:left">From \\ To</th>';
D.buckets.forEach((b,i) => {{ thead += `<th style="color:${{b.color}}">${{b.label}}</th>`; }});
thead += '</tr>';
let tbody2 = '';
D.transProb.forEach((row, ri) => {{
  tbody2 += `<tr><td class="row-header" style="color:${{BUCKET_COLORS[ri]}}">${{D.buckets[ri].label}}<br><span style="font-size:.68rem;color:#64748b">${{D.buckets[ri].range}}</span></td>`;
  const maxP = Math.max(...row);
  row.forEach((p, ci) => {{
    const alpha = p === 0 ? 0 : 0.1 + 0.7*(p/maxP);
    const bg = p === maxP ? hexToRgba(BUCKET_COLORS[ri], 0.35) : hexToRgba(BUCKET_COLORS[ci], alpha*0.4);
    tbody2 += `<td class="prob-cell" style="background:${{bg}};color:${{p===maxP?'#f1f5f9':'#94a3b8'}}">${{(p*100).toFixed(1)}}%</td>`;
  }});
  tbody2 += '</tr>';
}});
tbl.innerHTML = thead + tbody2;

// ── Bucket Profiles ─────────────────────────────────────────────────────────
const bg = document.getElementById('bucketGrid');
D.buckets.forEach((b, si) => {{
  const freq = D.predNumFreq[si];
  const cnt = D.predCount[si];
  const maxF = Math.max(...freq);
  const top6 = [...freq.keys()].sort((a,x) => freq[x]-freq[a]).slice(0,12).map(i => i+1);
  const card = document.createElement('div');
  card.className = 'bucket-card';
  card.style.borderColor = b.color;
  card.innerHTML = `
    <h4 style="color:${{b.color}}">${{b.label}} <span style="font-size:.68rem;color:#64748b">${{b.range}}</span></h4>
    <div class="bucket-stat">${{D.bucketCounts[si]}} draws (${{D.bucketPcts[si]}}%)</div>
    <div class="bucket-stat">Top numbers after this state:</div>
    <div class="bucket-nums">${{top6.map(n => `<div class="bnum top" style="background:${{hexToRgba(b.color,.15)}};color:${{b.color}};border-color:${{b.color}}55">${{n}}</div>`).join('')}}</div>`;
  bg.appendChild(card);
}});

// ── State Sequence ───────────────────────────────────────────────────────────
const sw = document.getElementById('seqWrap');
D.recentStates.forEach(rs => {{
  const dot = document.createElement('div');
  dot.className = 'seq-dot';
  dot.style.background = BUCKET_COLORS[rs.state];
  dot.title = `#${{rs.s}} (${{rs.d}}): sum=${{rs.sum}}, ${{D.buckets[rs.state].label}}`;
  sw.appendChild(dot);
}});
const leg = document.getElementById('seqLegend');
D.buckets.forEach((b,i) => {{
  leg.innerHTML += `<span style="display:flex;align-items:center;gap:5px;font-size:.75rem;color:#94a3b8">
    <span style="width:12px;height:12px;border-radius:3px;background:${{b.color}};flex-shrink:0"></span>${{b.label}} (${{b.range}})
  </span>`;
}});

// ── Backtest Stats ───────────────────────────────────────────────────────────
document.getElementById('btStats').innerHTML = `
  <div class="stat-box"><div class="sv">${{D.avgHits.toFixed(3)}}</div><div class="sl">Avg hits / draw</div></div>
  <div class="stat-box"><div class="sv">${{D.randAvg.toFixed(3)}}</div><div class="sl">Random baseline</div></div>
  <div class="stat-box"><div class="sv">${{D.lift.toFixed(3)}}×</div><div class="sl">Lift vs random</div></div>
  <div class="stat-box"><div class="sv">${{D.btDraws}}</div><div class="sl">Draws tested</div></div>`;

const hdist = D.hdist;
const maxD = Math.max(...hdist);
const btTotal = hdist.reduce((a,b)=>a+b,0);
document.getElementById('distRow').innerHTML = hdist.map((cnt,h) => {{
  const ht = maxD ? Math.round(cnt/maxD*60) : 0;
  return `<div class="dist-bar-wrap"><div class="dist-bar d${{h}}" style="height:${{ht}}px" title="${{h}} hits: ${{cnt}}"></div></div>`;
}}).join('');
document.getElementById('distLabels').innerHTML = hdist.map((cnt,h) =>
  `<div class="dist-bar-wrap"><div class="dist-label" style="font-weight:700;color:#e2e8f0">${{h}}</div><div class="dist-label">${{btTotal?Math.round(cnt/btTotal*1000)/10:0}}%</div></div>`
).join('');

// ── Backtest Table ───────────────────────────────────────────────────────────
const tbody = document.getElementById('btBody');
D.bt.slice(0,120).forEach(e => {{
  const actualSet = new Set(e.n);
  const predSet = new Set(e.pr);
  const tr = document.createElement('tr');
  tr.className = e.hc > 0 ? 'hit' : 'miss';
  const balls = e.n.map(n => `<span class="ball${{predSet.has(n)?' b-hit':''}}">${{n}}</span>`).join('');
  const chips = e.pr.map(n => `<span class="pred-chip ${{actualSet.has(n)?'pc-hit':'pc-miss'}}">${{n}}</span>`).join('');
  const sbadge = `<span style="font-size:.72rem;padding:2px 6px;border-radius:4px;background:${{hexToRgba(BUCKET_COLORS[e.state],.2)}};color:${{BUCKET_COLORS[e.state]}}">${{D.buckets[e.state].label}}</span>`;
  const pbadge = `<span style="font-size:.72rem;padding:2px 6px;border-radius:4px;background:${{hexToRgba(BUCKET_COLORS[e.prevState],.15)}};color:${{BUCKET_COLORS[e.prevState]}}">${{D.buckets[e.prevState].label}}</span>`;
  tr.innerHTML = `<td>#${{e.s}}</td><td>${{e.d}}</td><td>${{e.sum}}</td><td>${{sbadge}}</td><td>${{balls}}</td><td>${{chips}}</td><td style="color:${{e.hc>0?'#22c55e':'#94a3b8'}};font-weight:700">${{e.hc}}</td>`;
  tbody.appendChild(tr);
}});
</script>
</body>
</html>"""

with open(OUT_PATH, "w", encoding="utf-8") as f:
    f.write(HTML)
print(f"Written: {OUT_PATH} ({len(HTML):,} bytes)")
