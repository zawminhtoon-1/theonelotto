"""
Generate state_machine.html — 1-step AND 2-step Sum-bucket Markov prediction for Loto 6.

States (5 sum buckets):
  S0: sum <= 90   (very low)
  S1: 91-120      (low)
  S2: 121-150     (medium)
  S3: 151-180     (high)
  S4: sum > 180   (very high)

1-step: state[i-1] → predict state[i]
2-step: (state[i-2], state[i-1]) → predict state[i]
"""
import psycopg2, json, collections

OUT_PATH = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto\public\state_machine.html"
DB_URL = "postgresql://neondb_owner:npg_QbHpRZW8of3C@ep-hidden-wind-a1q0el7s-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"

BUCKETS = [
    (0,   90,  "Very Low",  "≤90",   "#6366f1"),
    (91,  120, "Low",       "91–120", "#3b82f6"),
    (121, 150, "Medium",    "121–150","#22c55e"),
    (151, 180, "High",      "151–180","#f59e0b"),
    (181, 999, "Very High", ">180",   "#ef4444"),
]
N = 5

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

# ═══════════════════════════════════════════════════════════════════
# 1-STEP MARKOV
# ═══════════════════════════════════════════════════════════════════
trans1 = [[0]*N for _ in range(N)]
for i in range(1, T):
    trans1[draws[i-1]["state"]][draws[i]["state"]] += 1

trans1_prob = []
for row in trans1:
    total = sum(row)
    trans1_prob.append([round(c/total, 4) if total else 0 for c in row])

# Numbers that follow each state (1-step)
pred1_freq = [[0]*43 for _ in range(N)]
pred1_count = [0]*N
for i in range(1, T):
    ps = draws[i-1]["state"]
    for n in draws[i]["n"]:
        pred1_freq[ps][n-1] += 1
    pred1_count[ps] += 1

def top6_from_freq(freq):
    return sorted([ranked+1 for ranked in sorted(range(43), key=lambda x: -freq[x])[:6]])

cs1 = draws[-1]["state"]
row1 = trans1_prob[cs1]
ns1 = row1.index(max(row1))
pred1_current = top6_from_freq(pred1_freq[cs1])

print(f"1-step: current={BUCKETS[cs1][2]}, next={BUCKETS[ns1][2]}, pred={pred1_current}")

# Bucket counts
bucket_counts = [sum(1 for d in draws if d["state"]==s) for s in range(N)]
bucket_pcts = [round(c/T*100, 1) for c in bucket_counts]

# State num freq (what numbers appear IN each state)
state_num_freq = [[0]*43 for _ in range(N)]
for d in draws:
    for n in d["n"]:
        state_num_freq[d["state"]][n-1] += 1

# ═══════════════════════════════════════════════════════════════════
# 2-STEP MARKOV  (pair (s_{i-2}, s_{i-1}) → s_i)
# ═══════════════════════════════════════════════════════════════════
# super-state index = prev*N + curr  (0..24)
SS = N * N  # 25

# All-time transition: super_state → next_state count
trans2 = [[0]*N for _ in range(SS)]
pred2_freq = [[0]*43 for _ in range(SS)]
pred2_count = [0]*SS

for i in range(2, T):
    ss = draws[i-2]["state"] * N + draws[i-1]["state"]
    ns = draws[i]["state"]
    trans2[ss][ns] += 1
    for n in draws[i]["n"]:
        pred2_freq[ss][n-1] += 1
    pred2_count[ss] += 1

trans2_prob = []
for row in trans2:
    total = sum(row)
    trans2_prob.append([round(c/total, 4) if total else 0 for c in row])

# Current 2-step super-state
ss_current = draws[-2]["state"] * N + draws[-1]["state"]
row2 = trans2_prob[ss_current]
ns2 = row2.index(max(row2)) if any(row2) else cs1
pred2_current = top6_from_freq(pred2_freq[ss_current])
pair_label = f"{BUCKETS[draws[-2]['state']][2]} → {BUCKETS[draws[-1]['state']][2]}"

print(f"2-step: pair=({pair_label}), next={BUCKETS[ns2][2]} ({max(row2)*100:.1f}%), pred={pred2_current}")

# ═══════════════════════════════════════════════════════════════════
# BACKTESTS (walk-forward, last 1000 draws)
# ═══════════════════════════════════════════════════════════════════
BT_DRAWS = 1000
test_start = T - BT_DRAWS

def run_backtest(step):
    """step=1 or 2"""
    wf_pred_freq = [[0]*43 for _ in range(SS if step==2 else N)]

    # Seed with pre-test history
    seed_start = 2 if step == 2 else 1
    for i in range(seed_start, test_start):
        if step == 1:
            key = draws[i-1]["state"]
        else:
            key = draws[i-2]["state"] * N + draws[i-1]["state"]
        for n in draws[i]["n"]:
            wf_pred_freq[key][n-1] += 1

    results = []
    hit_dist = [0]*7
    total_hits = 0

    for i in range(test_start, T):
        if step == 1:
            key = draws[i-1]["state"]
        else:
            if i < 2:
                key = 0
            else:
                key = draws[i-2]["state"] * N + draws[i-1]["state"]

        freq = wf_pred_freq[key]
        pred = top6_from_freq(freq)

        actual_set = set(draws[i]["n"])
        hits = sorted(set(pred) & actual_set)
        hc = len(hits)
        hit_dist[hc] += 1
        total_hits += hc

        results.append({
            "s": draws[i]["s"], "d": draws[i]["d"],
            "n": draws[i]["n"], "sum": draws[i]["sum"],
            "state": draws[i]["state"],
            "pr": pred, "h": hits, "hc": hc,
        })

        # Update walk-forward
        for n in draws[i]["n"]:
            wf_pred_freq[key][n-1] += 1

    avg_hits = total_hits / BT_DRAWS
    rand_avg = 6 * 6 / 43
    lift = avg_hits / rand_avg
    return results, hit_dist, round(avg_hits, 4), round(rand_avg, 4), round(lift, 4)

print("Backtesting 1-step...")
bt1, hd1, avg1, rand_avg, lift1 = run_backtest(1)
print(f"  avg={avg1}, lift={lift1}x, dist={hd1}")

print("Backtesting 2-step...")
bt2, hd2, avg2, _, lift2 = run_backtest(2)
print(f"  avg={avg2}, lift={lift2}x, dist={hd2}")

# Recent state sequence (last 50)
recent_states = [{"s": d["s"], "d": d["d"], "sum": d["sum"], "state": d["state"]} for d in draws[-50:]]

# 2-step top-6 per super-state (for display)
top6_per_ss = []
for ss in range(SS):
    top6_per_ss.append(top6_from_freq(pred2_freq[ss]))

# ─── Serialize ────────────────────────────────────────────────────
DATA = {
    "buckets": [{"label": b[2], "range": b[3], "color": b[4]} for b in BUCKETS],
    "bucketCounts": bucket_counts,
    "bucketPcts": bucket_pcts,
    "totalDraws": T,
    "latestSerial": draws[-1]["s"],
    "latestDate": draws[-1]["d"],
    # 1-step
    "s1": {
        "transProb": trans1_prob,
        "predFreq": pred1_freq,
        "currentState": cs1,
        "currentSum": draws[-1]["sum"],
        "likelyNext": ns1,
        "pred": pred1_current,
        "avgHits": avg1,
        "randAvg": rand_avg,
        "lift": lift1,
        "hdist": hd1,
        "bt": list(reversed(bt1))[:150],
    },
    # 2-step
    "s2": {
        "transProb": trans2_prob,
        "predFreq": pred2_freq,
        "top6PerSS": top6_per_ss,
        "pred2Count": pred2_count,
        "ssCurrent": ss_current,
        "prevState": draws[-2]["state"],
        "currState": draws[-1]["state"],
        "pairLabel": pair_label,
        "likelyNext": ns2,
        "likelyNextPct": round(max(row2)*100, 1),
        "pred": pred2_current,
        "avgHits": avg2,
        "randAvg": rand_avg,
        "lift": lift2,
        "hdist": hd2,
        "bt": list(reversed(bt2))[:150],
    },
    "recentStates": recent_states,
    "stateNumFreq": state_num_freq,
}
DATA_JSON = json.dumps(DATA, separators=(",", ":"))
print(f"\nJSON size: {len(DATA_JSON):,} bytes")

# ═══════════════════════════════════════════════════════════════════
# HTML
# ═══════════════════════════════════════════════════════════════════
NAV_HTML = """<nav class="site-nav">
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
</nav>"""

HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>State Machine — Loto 6</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:system-ui,sans-serif;background:#0f172a;color:#e2e8f0;min-height:100vh;padding-top:52px}}

/* ── NAV ── */
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
  border-radius:6px;color:#94a3b8;text-decoration:none;font-size:.82rem;white-space:nowrap;transition:.12s}}
.nav-dropdown a:hover,.nav-dropdown a.active{{color:#f1f5f9;background:#1e293b}}
.nav-dd-label{{font-size:.68rem;font-weight:700;color:#475569;padding:6px 12px 2px;text-transform:uppercase;letter-spacing:.06em}}
.nav-divider{{height:1px;background:#1e293b;margin:4px 0}}

/* ── LAYOUT ── */
main{{max-width:1200px;margin:0 auto;padding:24px 20px}}
h1{{font-size:1.4rem;font-weight:800;color:#f1f5f9;margin-bottom:4px}}
.subtitle{{font-size:.85rem;color:#64748b;margin-bottom:24px}}
.sec{{margin-bottom:32px}}
.sec-title{{font-size:.78rem;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:.06em;margin-bottom:10px}}

/* ── TABS ── */
.tabs{{display:flex;gap:6px;margin-bottom:24px;border-bottom:1px solid #1e293b;padding-bottom:0}}
.tab{{padding:8px 20px;cursor:pointer;font-size:.85rem;font-weight:600;color:#64748b;
  border-radius:8px 8px 0 0;border:1px solid transparent;border-bottom:none;transition:.15s;
  margin-bottom:-1px}}
.tab:hover{{color:#94a3b8;background:#1e293b22}}
.tab.active{{color:#38bdf8;background:#0d1526;border-color:#1e293b;border-bottom:1px solid #0d1526}}
.tab-panel{{display:none}}.tab-panel.active{{display:block}}

/* ── HERO CARD ── */
.hero{{background:#1e293b;border-radius:14px;padding:20px 24px;margin-bottom:20px;display:flex;gap:20px;flex-wrap:wrap;align-items:center}}
.hero-main{{flex:1;min-width:180px}}
.hero-main h2{{font-size:1.05rem;font-weight:800;margin-bottom:3px}}
.hero-main p{{font-size:.8rem;color:#64748b}}
.flow{{display:flex;align-items:center;gap:10px;flex-wrap:wrap}}
.flow-box{{background:#0f172a;border-radius:10px;padding:10px 18px;text-align:center;min-width:110px}}
.flow-box .fv{{font-size:1.2rem;font-weight:800}}
.flow-box .fl{{font-size:.7rem;color:#64748b;margin-top:2px}}
.flow-arr{{font-size:1.2rem;color:#334155;text-align:center}}
.flow-pct{{font-size:.72rem;color:#64748b}}

/* ── COMBO BALLS ── */
.combo-row{{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:16px}}
.cball{{width:50px;height:50px;border-radius:50%;display:flex;align-items:center;justify-content:center;
  font-size:1.1rem;font-weight:800;box-shadow:0 2px 10px #0004}}

/* ── COMPARISON BANNER ── */
.compare-banner{{background:linear-gradient(135deg,#1e293b,#0f172a);border:1px solid #334155;
  border-radius:12px;padding:16px 20px;margin-bottom:24px;display:flex;gap:20px;flex-wrap:wrap}}
.cmp-col{{flex:1;min-width:160px;text-align:center}}
.cmp-label{{font-size:.72rem;color:#64748b;margin-bottom:6px;font-weight:600;text-transform:uppercase;letter-spacing:.05em}}
.cmp-val{{font-size:1.4rem;font-weight:800}}
.cmp-sub{{font-size:.72rem;color:#64748b;margin-top:2px}}
.cmp-divider{{width:1px;background:#1e293b;flex-shrink:0}}
.badge{{display:inline-block;padding:2px 8px;border-radius:4px;font-size:.72rem;font-weight:700}}
.badge-green{{background:#14532d;color:#4ade80}}.badge-amber{{background:#451a03;color:#fbbf24}}
.badge-red{{background:#450a0a;color:#f87171}}

/* ── MATRIX ── */
.matrix-wrap{{overflow-x:auto;margin-bottom:8px}}
.matrix{{border-collapse:collapse;font-size:.78rem;width:100%}}
.matrix th,.matrix td{{padding:7px 10px;border:1px solid #1e293b;text-align:center}}
.matrix th{{background:#0f172a;color:#94a3b8;font-size:.7rem}}
.matrix .rh{{font-weight:700;text-align:left;white-space:nowrap;min-width:90px}}
.pc{{border-radius:3px;font-weight:600}}

/* ── BUCKET GRID ── */
.bucket-grid{{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin-bottom:16px}}
.bucket-card{{background:#1e293b;border-radius:10px;padding:12px;border-top:3px solid}}
.bucket-card h4{{font-size:.78rem;font-weight:700;margin-bottom:6px}}
.b-nums{{display:flex;flex-wrap:wrap;gap:3px;margin-top:6px}}
.bnum{{width:26px;height:26px;border-radius:5px;display:flex;align-items:center;justify-content:center;
  font-size:.7rem;font-weight:700;background:#0f172a;color:#64748b}}
.bnum.top{{border:1px solid}}

/* ── 2-STEP MATRIX (25 rows) ── */
.ss-matrix{{border-collapse:collapse;font-size:.74rem;width:100%}}
.ss-matrix th,.ss-matrix td{{padding:5px 8px;border:1px solid #1e293b;text-align:center}}
.ss-matrix th{{background:#0f172a;color:#64748b;font-size:.68rem}}
.ss-matrix .rh{{text-align:left;white-space:nowrap;font-weight:600;min-width:130px}}
.ss-matrix tr.ss-active td{{outline:2px solid #38bdf8;outline-offset:-1px}}

/* ── SEQ ── */
.seq{{display:flex;gap:3px;flex-wrap:wrap;margin-bottom:8px}}
.sq{{width:14px;height:14px;border-radius:3px;cursor:pointer;transition:.15s}}
.sq:hover{{transform:scale(1.4)}}

/* ── STATS ── */
.stats-row{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px}}
.sbox{{background:#1e293b;border-radius:8px;padding:9px 16px;min-width:100px}}
.sbox .sv{{font-size:1.25rem;font-weight:800;color:#f1f5f9}}
.sbox .sl{{font-size:.7rem;color:#64748b;margin-top:1px}}

/* ── DIST ── */
.dist-row{{display:flex;gap:4px;align-items:flex-end;height:60px;margin-bottom:4px}}
.dbw{{display:flex;flex-direction:column;align-items:center;flex:1}}
.db{{width:100%;border-radius:3px 3px 0 0;min-height:2px}}
.dl{{font-size:.65rem;color:#64748b;margin-top:2px}}
.db0{{background:#ef4444}}.db1{{background:#f97316}}.db2{{background:#eab308}}
.db3{{background:#22c55e}}.db4{{background:#06b6d4}}.db5{{background:#8b5cf6}}.db6{{background:#ec4899}}

/* ── BT TABLE ── */
.bt-wrap{{max-height:460px;overflow-y:auto;border-radius:8px}}
.bt-tbl{{width:100%;border-collapse:collapse;font-size:.78rem}}
.bt-tbl th{{background:#1e293b;padding:6px 8px;color:#94a3b8;font-size:.7rem;font-weight:600;
  text-align:left;position:sticky;top:0;z-index:2}}
.bt-tbl td{{padding:5px 7px;border-bottom:1px solid #0f172a;vertical-align:middle}}
.bt-tbl tr.hit td:first-child{{border-left:3px solid #22c55e}}
.bt-tbl tr.miss td:first-child{{border-left:3px solid #ef444455}}
.ball{{display:inline-flex;align-items:center;justify-content:center;width:24px;height:24px;
  border-radius:50%;font-size:.7rem;font-weight:700;margin:1px;background:#1e3a5f;color:#93c5fd}}
.ball.bh{{border:2px solid #22c55e}}
.pch{{display:inline-flex;align-items:center;justify-content:center;min-width:24px;height:20px;
  border-radius:4px;font-size:.7rem;font-weight:700;padding:0 4px;margin:1px}}
.pc-hit{{background:#14532d;color:#4ade80;border:1px solid #4ade80}}
.pc-miss{{background:#1e293b;color:#64748b;border:1px solid #334155}}
</style>
</head>
<body>
{NAV_HTML}
<main>
  <h1>🔄 State Machine Prediction</h1>
  <p class="subtitle">Sum-bucket Markov chain — compares 1-step and 2-step memory on all {T} draws.</p>

  <!-- Comparison banner -->
  <div class="compare-banner" id="cmpBanner"></div>

  <!-- Tabs -->
  <div class="tabs">
    <div class="tab active" onclick="switchTab('s1',this)">1-Step Markov</div>
    <div class="tab" onclick="switchTab('s2',this)">2-Step Markov</div>
    <div class="tab" onclick="switchTab('seq',this)">State Sequence</div>
  </div>

  <!-- 1-step panel -->
  <div class="tab-panel active" id="panel-s1">
    <div class="sec">
      <div class="sec-title">Current State → Next</div>
      <div class="hero" id="hero1"></div>
      <div class="sec-title">Prediction for Draw #<span id="nd1"></span></div>
      <div class="combo-row" id="combo1"></div>
    </div>
    <div class="sec">
      <div class="sec-title">Transition Matrix (row = current → col = next)</div>
      <div class="matrix-wrap"><table class="matrix" id="mat1"></table></div>
    </div>
    <div class="sec">
      <div class="sec-title">Top Follow-On Numbers per State</div>
      <div class="bucket-grid" id="bg1"></div>
    </div>
    <div class="sec">
      <div class="sec-title">Walk-Forward Backtest — 1000 Draws</div>
      <div class="stats-row" id="stats1"></div>
      <div class="sec-title">Hit Distribution</div>
      <div class="dist-row" id="dist1"></div>
      <div class="dist-row" id="dlbl1" style="height:auto"></div>
    </div>
    <div class="sec">
      <div class="sec-title">Recent Draws</div>
      <div class="bt-wrap"><table class="bt-tbl">
        <thead><tr><th>Draw</th><th>Date</th><th>Sum</th><th>State</th><th>Actual</th><th>Predicted</th><th>Hits</th></tr></thead>
        <tbody id="bt1"></tbody>
      </table></div>
    </div>
  </div>

  <!-- 2-step panel -->
  <div class="tab-panel" id="panel-s2">
    <div class="sec">
      <div class="sec-title">Last 2 States → Predicted Next</div>
      <div class="hero" id="hero2"></div>
      <div class="sec-title">Prediction for Draw #<span id="nd2"></span></div>
      <div class="combo-row" id="combo2"></div>
    </div>
    <div class="sec">
      <div class="sec-title">2-Step Transition Matrix (25 super-states × 5 outcomes)</div>
      <p style="font-size:.78rem;color:#64748b;margin-bottom:8px">Highlighted row = current super-state</p>
      <div class="matrix-wrap"><table class="ss-matrix" id="mat2"></table></div>
    </div>
    <div class="sec">
      <div class="sec-title">Top Follow-On Numbers per Super-State (pair → next draw numbers)</div>
      <div id="sg2" style="display:grid;grid-template-columns:repeat(5,1fr);gap:8px"></div>
    </div>
    <div class="sec">
      <div class="sec-title">Walk-Forward Backtest — 1000 Draws</div>
      <div class="stats-row" id="stats2"></div>
      <div class="sec-title">Hit Distribution</div>
      <div class="dist-row" id="dist2"></div>
      <div class="dist-row" id="dlbl2" style="height:auto"></div>
    </div>
    <div class="sec">
      <div class="sec-title">Recent Draws</div>
      <div class="bt-wrap"><table class="bt-tbl">
        <thead><tr><th>Draw</th><th>Date</th><th>Sum</th><th>State</th><th>Actual</th><th>Predicted</th><th>Hits</th></tr></thead>
        <tbody id="bt2"></tbody>
      </table></div>
    </div>
  </div>

  <!-- Sequence panel -->
  <div class="tab-panel" id="panel-seq">
    <div class="sec">
      <div class="sec-title">Last 50 Draws — State Sequence</div>
      <div class="seq" id="seqDots"></div>
      <div style="display:flex;gap:12px;flex-wrap:wrap;margin-top:8px" id="seqLeg"></div>
    </div>
    <div class="sec">
      <div class="sec-title">Bucket Distribution</div>
      <div class="bucket-grid" id="bgDist"></div>
    </div>
  </div>
</main>

<script>
const D = {DATA_JSON};
const BC = D.buckets.map(b=>b.color);
const BL = D.buckets.map(b=>b.label);
const N = 5;

function hexRgba(h,a){{
  const r=parseInt(h.slice(1,3),16),g=parseInt(h.slice(3,5),16),b=parseInt(h.slice(5,7),16);
  return `rgba(${{r}},${{g}},${{b}},${{a}})`;
}}
function stateBadge(s,extra){{
  return `<span style="font-size:.72rem;padding:2px 6px;border-radius:4px;background:${{hexRgba(BC[s],.18)}};color:${{BC[s]}}">${{BL[s]}}${{extra||''}}</span>`;
}}

function switchTab(id,el){{
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  document.querySelectorAll('.tab-panel').forEach(p=>p.classList.remove('active'));
  el.classList.add('active');
  document.getElementById('panel-'+id).classList.add('active');
}}

// ── Comparison banner ─────────────────────────────────────────────
function liftBadge(l){{
  const cls = l>1.05?'badge-green':l>0.99?'badge-amber':'badge-red';
  return `<span class="badge ${{cls}}">${{l.toFixed(3)}}×</span>`;
}}
document.getElementById('cmpBanner').innerHTML = `
  <div class="cmp-col">
    <div class="cmp-label">Method</div>
    <div class="cmp-val" style="font-size:1rem">Metric</div>
  </div><div class="cmp-divider"></div>
  <div class="cmp-col">
    <div class="cmp-label">1-Step Markov</div>
    <div class="cmp-val">${{D.s1.avgHits.toFixed(3)}}</div>
    <div class="cmp-sub">avg hits/draw ${{liftBadge(D.s1.lift)}}</div>
  </div><div class="cmp-divider"></div>
  <div class="cmp-col">
    <div class="cmp-label">2-Step Markov</div>
    <div class="cmp-val">${{D.s2.avgHits.toFixed(3)}}</div>
    <div class="cmp-sub">avg hits/draw ${{liftBadge(D.s2.lift)}}</div>
  </div><div class="cmp-divider"></div>
  <div class="cmp-col">
    <div class="cmp-label">Random Baseline</div>
    <div class="cmp-val">${{D.s1.randAvg.toFixed(3)}}</div>
    <div class="cmp-sub">avg hits/draw</div>
  </div>`;

// ── Hero builder ──────────────────────────────────────────────────
function buildHero(el, cs, ns, nsPct, sumVal, extra) {{
  el.innerHTML = `
    <div class="hero-main">
      <h2 id="heroTitle">Draw #${{D.latestSerial}}: sum ${{sumVal}} → ${{stateBadge(cs)}}</h2>
      <p>${{extra||''}}Most likely next state: ${{stateBadge(ns)}} (${{nsPct}}%)</p>
    </div>
    <div class="flow">
      <div class="flow-box"><div class="fv" style="color:${{BC[cs]}}">${{BL[cs]}}</div><div class="fl">current</div></div>
      <div style="text-align:center"><div class="flow-arr">→</div><div class="flow-pct">${{nsPct}}%</div></div>
      <div class="flow-box"><div class="fv" style="color:${{BC[ns]}}">${{BL[ns]}}</div><div class="fl">predicted next</div></div>
    </div>`;
}}

// 1-step hero
const cs1=D.s1.currentState, ns1=D.s1.likelyNext;
const ns1Pct=Math.round(D.s1.transProb[cs1][ns1]*100);
buildHero(document.getElementById('hero1'),cs1,ns1,ns1Pct,D.s1.currentSum,'');
document.getElementById('nd1').textContent=D.latestSerial+1;

// 2-step hero
const cs2=D.s2.currState,ps2=D.s2.prevState,ns2=D.s2.likelyNext;
const ns2Pct=D.s2.likelyNextPct;
document.getElementById('hero2').innerHTML = `
  <div class="hero-main">
    <h2>Draw #${{D.latestSerial-1}} ${{stateBadge(ps2)}} → Draw #${{D.latestSerial}} ${{stateBadge(cs2)}}</h2>
    <p>2-step pair predicts next: ${{stateBadge(ns2)}} (${{ns2Pct}}%)</p>
  </div>
  <div class="flow">
    <div class="flow-box"><div class="fv" style="color:${{BC[ps2]}};font-size:.9rem">${{BL[ps2]}}</div><div class="fl">#${{D.latestSerial-1}}</div></div>
    <div class="flow-arr">→</div>
    <div class="flow-box"><div class="fv" style="color:${{BC[cs2]}};font-size:.9rem">${{BL[cs2]}}</div><div class="fl">#${{D.latestSerial}}</div></div>
    <div style="text-align:center"><div class="flow-arr">→</div><div class="flow-pct">${{ns2Pct}}%</div></div>
    <div class="flow-box"><div class="fv" style="color:${{BC[ns2]}};font-size:.9rem">${{BL[ns2]}}</div><div class="fl">predicted</div></div>
  </div>`;
document.getElementById('nd2').textContent=D.latestSerial+1;

// ── Combo rows ────────────────────────────────────────────────────
function buildCombo(el, pred, nsColor, nsLabel) {{
  el.innerHTML = pred.map(n=>
    `<div class="cball" style="background:linear-gradient(135deg,${{nsColor}}99,${{nsColor}}33)">${{n}}</div>`
  ).join('') + `<span style="color:#64748b;font-size:.8rem;margin-left:8px">→ "${{nsLabel}}" state distribution</span>`;
}}
buildCombo(document.getElementById('combo1'), D.s1.pred, BC[ns1], BL[ns1]);
buildCombo(document.getElementById('combo2'), D.s2.pred, BC[ns2], BL[ns2]);

// ── 1-step matrix ─────────────────────────────────────────────────
(function(){{
  const tbl=document.getElementById('mat1');
  let h='<tr><th style="text-align:left">From↓ To→</th>';
  D.buckets.forEach((b,i)=>h+=`<th style="color:${{b.color}}">${{b.label}}</th>`);
  h+='</tr>';
  let body='';
  D.s1.transProb.forEach((row,ri)=>{{
    const maxP=Math.max(...row);
    body+=`<tr><td class="rh" style="color:${{BC[ri]}}">${{BL[ri]}}<br><span style="font-size:.68rem;color:#64748b">${{D.buckets[ri].range}}</span></td>`;
    row.forEach((p,ci)=>{{
      const bg=p===maxP?hexRgba(BC[ri],.35):hexRgba(BC[ci],p/maxP*.25+.05);
      body+=`<td class="pc" style="background:${{bg}};color:${{p===maxP?'#f1f5f9':'#94a3b8'}}">${{(p*100).toFixed(1)}}%</td>`;
    }});
    body+='</tr>';
  }});
  tbl.innerHTML=h+body;
}})();

// ── 1-step bucket grid ────────────────────────────────────────────
(function(){{
  const bg=document.getElementById('bg1');
  D.buckets.forEach((b,si)=>{{
    const freq=D.s1.predFreq[si];
    const top=top6FromFreq(freq);
    const card=document.createElement('div');
    card.className='bucket-card'; card.style.borderColor=b.color;
    card.innerHTML=`<h4 style="color:${{b.color}}">${{b.label}} <span style="font-size:.68rem;color:#64748b">${{b.range}}</span></h4>
      <div style="font-size:.7rem;color:#64748b">${{D.bucketCounts[si]}} draws (${{D.bucketPcts[si]}}%)</div>
      <div class="b-nums">${{top.map(n=>`<div class="bnum top" style="background:${{hexRgba(b.color,.12)}};color:${{b.color}};border-color:${{b.color}}55">${{n}}</div>`).join('')}}</div>`;
    bg.appendChild(card);
  }});
}})();

// ── 2-step matrix (25 rows) ───────────────────────────────────────
(function(){{
  const tbl=document.getElementById('mat2');
  let h='<tr><th class="rh">From pair (prev→curr)</th>';
  D.buckets.forEach((b,i)=>h+=`<th style="color:${{b.color}}">${{b.label}}</th>`);
  h+='</tr>';
  let body='';
  for(let ss=0;ss<25;ss++){{
    const prev=Math.floor(ss/N), curr=ss%N;
    const row=D.s2.transProb[ss];
    const maxP=Math.max(...row);
    const isActive=ss===D.s2.ssCurrent;
    body+=`<tr class="${{isActive?'ss-active':''}}"><td class="rh" style="color:${{BC[curr]}}">
      <span style="color:${{BC[prev]}}">${{BL[prev]}}</span> → ${{BL[curr]}}
      <span style="font-size:.65rem;color:#475569;margin-left:4px">(${{D.s2.pred2Count[ss]}} obs)</span>
      ${{isActive?'<span style="color:#38bdf8;font-size:.65rem"> ◀ current</span>':''}}
    </td>`;
    row.forEach((p,ci)=>{{
      const bg=p===maxP&&maxP>0?hexRgba(BC[ci],.35):hexRgba(BC[ci],p>0?(p/Math.max(maxP,.001))*.2+.03:0);
      body+=`<td class="pc" style="background:${{bg}};color:${{p===maxP&&p>0?'#f1f5f9':'#64748b'}}">${{maxP>0?(p*100).toFixed(1):'—'}}${{p>0?'%':''}}</td>`;
    }});
    body+='</tr>';
  }}
  tbl.innerHTML=h+body;
}})();

// ── 2-step super-state bucket grid ───────────────────────────────
(function(){{
  const sg=document.getElementById('sg2');
  for(let ss=0;ss<25;ss++){{
    const prev=Math.floor(ss/N), curr=ss%N;
    const cnt=D.s2.pred2Count[ss];
    const top=D.s2.top6PerSS[ss];
    const isActive=ss===D.s2.ssCurrent;
    const card=document.createElement('div');
    card.style.cssText=`background:#1e293b;border-radius:8px;padding:10px;border-top:3px solid ${{BC[curr]}};${{isActive?'outline:2px solid #38bdf8;':''}}`;
    card.innerHTML=`<div style="font-size:.72rem;font-weight:700;color:${{BC[curr]}};margin-bottom:2px">
      <span style="color:${{BC[prev]}}">${{BL[prev].slice(0,3)}}</span>→${{BL[curr].slice(0,3)}}
      ${{isActive?'<span style="color:#38bdf8">◀</span>':''}}
    </div>
    <div style="font-size:.68rem;color:#64748b;margin-bottom:4px">${{cnt}} obs</div>
    <div class="b-nums">${{top.map(n=>`<div class="bnum top" style="background:${{hexRgba(BC[curr],.12)}};color:${{BC[curr]}};border-color:${{BC[curr]}}55">${{n}}</div>`).join('')}}</div>`;
    sg.appendChild(card);
  }}
}})();

// ── Stats & dist helper ───────────────────────────────────────────
function buildStats(elId,data){{
  document.getElementById(elId).innerHTML=`
    <div class="sbox"><div class="sv">${{data.avgHits.toFixed(3)}}</div><div class="sl">Avg hits/draw</div></div>
    <div class="sbox"><div class="sv">${{data.randAvg.toFixed(3)}}</div><div class="sl">Random baseline</div></div>
    <div class="sbox"><div class="sv">${{data.lift.toFixed(3)}}×</div><div class="sl">Lift vs random</div></div>
    <div class="sbox"><div class="sv">1000</div><div class="sl">Draws tested</div></div>`;
}}
function buildDist(distId,lblId,hdist){{
  const maxD=Math.max(...hdist), tot=hdist.reduce((a,b)=>a+b,0);
  document.getElementById(distId).innerHTML=hdist.map((c,h)=>
    `<div class="dbw"><div class="db db${{h}}" style="height:${{maxD?Math.round(c/maxD*56):0}}px" title="${{h}} hits: ${{c}}"></div></div>`
  ).join('');
  document.getElementById(lblId).innerHTML=hdist.map((c,h)=>
    `<div class="dbw"><div class="dl" style="font-weight:700;color:#e2e8f0">${{h}}</div><div class="dl">${{tot?Math.round(c/tot*1000)/10:0}}%</div></div>`
  ).join('');
}}

buildStats('stats1',D.s1); buildDist('dist1','dlbl1',D.s1.hdist);
buildStats('stats2',D.s2); buildDist('dist2','dlbl2',D.s2.hdist);

// ── BT tables ─────────────────────────────────────────────────────
function buildBT(tbodyId,bt){{
  const tbody=document.getElementById(tbodyId);
  bt.slice(0,100).forEach(e=>{{
    const aSet=new Set(e.n), pSet=new Set(e.pr);
    const tr=document.createElement('tr'); tr.className=e.hc>0?'hit':'miss';
    const balls=e.n.map(n=>`<span class="ball ${{pSet.has(n)?'bh':''}}">${{n}}</span>`).join('');
    const chips=e.pr.map(n=>`<span class="pch ${{aSet.has(n)?'pc-hit':'pc-miss'}}">${{n}}</span>`).join('');
    tr.innerHTML=`<td>#${{e.s}}</td><td>${{e.d}}</td><td>${{e.sum}}</td><td>${{stateBadge(e.state)}}</td><td>${{balls}}</td><td>${{chips}}</td>
      <td style="color:${{e.hc>0?'#22c55e':'#94a3b8'}};font-weight:700">${{e.hc}}</td>`;
    tbody.appendChild(tr);
  }});
}}
buildBT('bt1',D.s1.bt); buildBT('bt2',D.s2.bt);

// ── State sequence ─────────────────────────────────────────────────
(function(){{
  const wrap=document.getElementById('seqDots');
  D.recentStates.forEach(rs=>{{
    const d=document.createElement('div');
    d.className='sq'; d.style.background=BC[rs.state];
    d.title=`#${{rs.s}} (${{rs.d}}): sum=${{rs.sum}}, ${{BL[rs.state]}}`;
    wrap.appendChild(d);
  }});
  const leg=document.getElementById('seqLeg');
  D.buckets.forEach((b,i)=>{{
    leg.innerHTML+=`<span style="display:flex;align-items:center;gap:5px;font-size:.75rem;color:#94a3b8">
      <span style="width:12px;height:12px;border-radius:3px;background:${{b.color}};flex-shrink:0"></span>${{b.label}} (${{b.range}})
    </span>`;
  }});
}})();

// ── Bucket dist panel ─────────────────────────────────────────────
(function(){{
  const bg=document.getElementById('bgDist');
  D.buckets.forEach((b,i)=>{{
    const card=document.createElement('div');
    card.className='bucket-card'; card.style.borderColor=b.color;
    card.innerHTML=`<h4 style="color:${{b.color}}">${{b.label}}</h4>
      <div style="font-size:.7rem;color:#64748b">${{b.range}}</div>
      <div style="font-size:1.5rem;font-weight:800;margin-top:8px">${{D.bucketCounts[i]}}</div>
      <div style="font-size:.7rem;color:#64748b">draws (${{D.bucketPcts[i]}}%)</div>`;
    bg.appendChild(card);
  }});
}})();

// ── util ──────────────────────────────────────────────────────────
function top6FromFreq(freq){{
  return [...freq.keys()].sort((a,b)=>freq[b]-freq[a]).slice(0,6).map(i=>i+1).sort((a,b)=>a-b);
}}
</script>
</body>
</html>"""

with open(OUT_PATH, "w", encoding="utf-8") as f:
    f.write(HTML)
print(f"\nWritten: {OUT_PATH} ({len(HTML):,} bytes)")
