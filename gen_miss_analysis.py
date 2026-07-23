"""
Generate public/miss_analysis.html — 5-section miss analysis page.
Data source: public/backtest.html (1001 draws, 16 methods, walk-forward predictions)
"""
import json, re, sys
import numpy as np

sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

HTML_IN  = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto\public\backtest.html"
HTML_OUT = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto\public\miss_analysis.html"

# ── Load DATA ─────────────────────────────────────────────────────────────────
with open(HTML_IN, encoding='utf-8') as f:
    html = f.read()
m = re.search(r'const DATA\s*=\s*(\[)', html)
bs = m.start(1); depth=0; pos=bs
while pos < len(html):
    if html[pos]=='[': depth+=1
    elif html[pos]==']':
        depth-=1
        if depth==0: be=pos+1; break
    pos+=1
DATA = json.loads(html[bs:be])
m2 = re.search(r'const METHODS\s*=\s*(\[.*?\])', html, re.DOTALL)
METHODS = json.loads(m2.group(1))
N=16; T=len(DATA)
print(f"{T} draws, {N} methods, serials {DATA[0]['s']}-{DATA[-1]['s']}")

# ── Build matrices ────────────────────────────────────────────────────────────
picks_mat  = np.zeros((T, N, 43), dtype=np.uint8)
actual_mat = np.zeros((T, 43),    dtype=np.uint8)
serials, dates = [], []

for t, row in enumerate(DATA):
    serials.append(row['s'])
    dates.append(row.get('d','')[:10])
    for n in row['a']:     actual_mat[t, n-1] = 1
    for mi, pred in enumerate(row['p']):
        for n in pred[0]:  picks_mat[t, mi, n-1] = 1

# Consensus = how many methods pick each number per draw
consensus = picks_mat.sum(axis=1)   # (T, 43), range 0-16

# ── S1: Latest consensus (miss-risk meter) ────────────────────────────────────
latest_consensus = consensus[-1].tolist()
latest_serial    = serials[-1]
coverage         = int((consensus[-1] > 0).sum())
excl_size_latest = 43 - coverage
print(f"Latest serial {latest_serial}: coverage {coverage}/43, exclusion zone {excl_size_latest}")

# ── S2: Exclusion zone per draw ───────────────────────────────────────────────
ez_sizes = (consensus == 0).sum(axis=1)                     # (T,)
ez_hits  = ((consensus == 0) * actual_mat).sum(axis=1)      # (T,)

# Consensus top-15 score per draw (for 0-hit detection & recovery)
top15_scores = np.zeros(T, dtype=np.int32)
for t in range(T):
    idx = np.argsort(-consensus[t])[:15]
    mask = np.zeros(43, dtype=np.uint8); mask[idx] = 1
    top15_scores[t] = int((mask * actual_mat[t]).sum())

# EZ timeline data (downsample for chart — every draw)
ez_timeline = [{'s': serials[t], 'ez': int(ez_sizes[t]), 'ezh': int(ez_hits[t])} for t in range(T)]

ez_avg_hits  = round(float(ez_hits.mean()), 3)
ez_avg_size  = round(float(ez_sizes.mean()), 1)
ez_baseline  = round(float((6 * ez_sizes / 43).mean()), 3)  # expected EZ hits by chance
print(f"EZ: avg size {ez_avg_size}, avg hits {ez_avg_hits}, baseline {ez_baseline}")

# EZ hit distribution
ez_dist = np.bincount(ez_hits.clip(0,6), minlength=7).tolist()

# ── S3: Anti-prediction backtest ──────────────────────────────────────────────
anti6_hits  = np.zeros(T, dtype=np.int32)
anti15_hits = np.zeros(T, dtype=np.int32)

for t in range(T):
    sc = consensus[t].astype(np.float32) + np.arange(43) * 0.0001  # tiebreak by index
    anti_order = np.argsort(sc)   # ascending = least predicted first
    m6  = np.zeros(43, dtype=np.uint8); m6[anti_order[:6]]  = 1
    m15 = np.zeros(43, dtype=np.uint8); m15[anti_order[:15]] = 1
    anti6_hits[t]  = int((m6  * actual_mat[t]).sum())
    anti15_hits[t] = int((m15 * actual_mat[t]).sum())

anti6_dist   = np.bincount(anti6_hits,  minlength=7).tolist()
anti15_dist  = np.bincount(anti15_hits, minlength=7).tolist()
anti6_avg    = round(float(anti6_hits.mean()),  4)
anti15_avg   = round(float(anti15_hits.mean()), 4)
rand6        = round(6 * 6 / 43,  4)
rand15       = round(15 * 6 / 43, 4)
anti6_lift   = round(anti6_avg  / rand6,  3)
anti15_lift  = round(anti15_avg / rand15, 3)
print(f"Anti-6 : avg {anti6_avg} vs baseline {rand6} => {anti6_lift}x")
print(f"Anti-15: avg {anti15_avg} vs baseline {rand15} => {anti15_lift}x")

# ── S4: 0-Hit Draw Signature ──────────────────────────────────────────────────
zero_idx = np.where(top15_scores == 0)[0]
print(f"0-hit consensus draws: {len(zero_idx)}/{T}")

def profile(indices):
    if len(indices) == 0:
        return {}
    balls_list = [[n+1 for n in range(43) if actual_mat[t, n]] for t in indices]
    return {
        'count':      len(indices),
        'avg_ball':   round(float(np.mean([sum(b)/6 for b in balls_list])), 2),
        'avg_spread': round(float(np.mean([max(b)-min(b) for b in balls_list])), 2),
        'avg_odd':    round(float(np.mean([sum(1 for x in b if x%2==1) for b in balls_list])), 2),
        'avg_high':   round(float(np.mean([sum(1 for x in b if x>21) for b in balls_list])), 2),
        'avg_consec': round(float(np.mean([sum(1 for i in range(5) if b[i+1]-b[i]==1) for b in balls_list])), 2),
    }

prof_zero = profile(zero_idx)
prof_all  = profile(np.arange(T))
print("0-hit:", prof_zero)
print("All:  ", prof_all)

# Recent 0-hit draws for display (newest first)
zero_draws_display = []
for t in reversed(zero_idx[-20:]):
    nums = sorted([n+1 for n in range(43) if actual_mat[t, n]])
    zero_draws_display.append({'s': serials[t], 'd': dates[t], 'n': nums,
                                'ez': int(ez_sizes[t]), 'ezh': int(ez_hits[t])})
zero_draws_display.sort(key=lambda x: -x['s'])

# ── S5: Post-Miss Recovery ────────────────────────────────────────────────────
recovery = {}   # streak_len -> [next_draw_scores]
streak = 0
for t in range(T):
    if top15_scores[t] == 0:
        streak += 1
    else:
        if streak > 0:
            key = min(streak, 5)
            if key not in recovery: recovery[key] = []
            recovery[key].append(int(top15_scores[t]))
        streak = 0

recovery_rows = []
for n in range(1, 6):
    sc = recovery.get(n, [])
    recovery_rows.append({
        'n':     n,
        'count': len(sc),
        'avg':   round(sum(sc)/len(sc), 3) if sc else 0,
        'dist':  np.bincount(sc, minlength=7).tolist() if sc else [0]*7,
    })

consensus_avg = round(float(top15_scores.mean()), 3)
print("Recovery:", [(r['n'], r['count'], r['avg']) for r in recovery_rows])
print(f"Overall consensus avg: {consensus_avg}, rand baseline (top-15): {rand15}")

# ── Generate HTML ─────────────────────────────────────────────────────────────
J = lambda v: json.dumps(v, separators=(',',':'))

html_out = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Miss Analysis — Loto 6</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:system-ui,sans-serif;background:#0f172a;color:#e2e8f0;min-height:100vh}}
header{{background:#1e293b;padding:14px 20px;display:flex;align-items:center;gap:16px;border-bottom:1px solid #334155;flex-wrap:wrap}}
header h1{{font-size:1.2rem;font-weight:700;color:#f1f5f9}}
.back{{color:#94a3b8;font-size:.85rem;text-decoration:none}}.back:hover{{color:#38bdf8}}
.badge{{background:#1e3a5f;color:#38bdf8;border-radius:9999px;padding:2px 10px;font-size:.8rem}}
nav{{display:flex;gap:4px;padding:12px 20px;background:#1e293b;border-bottom:1px solid #334155;flex-wrap:wrap}}
.tab{{padding:6px 14px;border-radius:6px;cursor:pointer;font-size:.85rem;color:#94a3b8;border:1px solid transparent;transition:.15s}}
.tab:hover{{color:#e2e8f0;background:#334155}}.tab.active{{background:#0ea5e9;color:#fff}}
main{{padding:20px;max-width:1300px;margin:0 auto}}
.panel{{display:none}}.panel.active{{display:block}}
h2{{font-size:1.05rem;font-weight:700;color:#f1f5f9;margin-bottom:6px}}
.sub{{font-size:.82rem;color:#64748b;margin-bottom:16px;line-height:1.5}}
.kpi-row{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:20px}}
.kpi{{background:#1e293b;border-radius:10px;padding:12px 16px;min-width:120px;flex:1}}
.kpi .val{{font-size:1.4rem;font-weight:800;color:#f1f5f9}}
.kpi .lbl{{font-size:.72rem;color:#64748b;margin-top:2px}}
.kpi .sub2{{font-size:.72rem;color:#94a3b8;margin-top:1px}}
.good{{color:#4ade80}}.warn{{color:#facc15}}.bad{{color:#f87171}}.blue{{color:#38bdf8}}.orange{{color:#fb923c}}
.chart-box{{background:#1e293b;border-radius:10px;padding:16px;margin-bottom:18px}}
.chart-box h3{{font-size:.88rem;font-weight:700;color:#cbd5e1;margin-bottom:10px}}
.chart-wrap{{position:relative}}
.ball{{display:inline-flex;align-items:center;justify-content:center;
  width:26px;height:26px;border-radius:50%;font-size:.72rem;font-weight:700;margin:1px}}
.b-norm{{background:#1e3a5f;color:#93c5fd}}
.b-hi{{background:#b91c1c;color:#fca5a5;border:1.5px solid #ef4444}}
.dist-row{{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px}}
.dist-card{{background:#1e293b;border-radius:8px;padding:10px 14px;text-align:center;min-width:72px}}
.dist-card .dn{{font-size:1.15rem;font-weight:800}}.dist-card .dl{{font-size:.7rem;color:#64748b;margin-top:2px}}
.tbl-wrap{{max-height:400px;overflow-y:auto;border-radius:8px;margin-bottom:16px}}
.dtbl{{width:100%;border-collapse:collapse;font-size:.82rem}}
.dtbl th{{background:#1e293b;padding:7px 8px;text-align:left;color:#64748b;font-size:.75rem;position:sticky;top:0;z-index:2}}
.dtbl td{{padding:6px 8px;border-bottom:1px solid #0f172a;vertical-align:middle}}
.dtbl tr:hover td{{background:#1e3a5f22}}
.profile-cmp{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:18px}}
.profile-box{{background:#1e293b;border-radius:10px;padding:16px}}
.profile-box h4{{font-size:.82rem;font-weight:700;margin-bottom:10px;color:#94a3b8}}
.profile-row{{display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid #0f172a;font-size:.82rem}}
.profile-row:last-child{{border:none}}
.profile-row .pl{{color:#64748b}}.profile-row .pv{{font-weight:700}}
/* Miss risk gauge */
.gauge-wrap{{position:relative;width:200px;height:110px;margin:0 auto 12px}}
.gauge-label{{text-align:center;font-size:1.5rem;font-weight:800;margin-top:-8px}}
.gauge-sub{{text-align:center;font-size:.8rem;color:#64748b;margin-bottom:12px}}
/* Ball grid for consensus */
.cns-grid{{display:flex;flex-wrap:wrap;gap:4px;margin-bottom:16px}}
.cns-ball{{display:inline-flex;flex-direction:column;align-items:center;width:36px}}
.cns-ball .num{{width:30px;height:30px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:.75rem;font-weight:700;margin-bottom:2px}}
.cns-ball .cnt{{font-size:.65rem;color:#64748b}}
</style>
</head>
<body>
<header>
  <a href="/" class="back">&#8592; Home</a>
  <h1>Miss Analysis</h1>
  <span class="badge">{T} draws backtested</span>
</header>
<nav>
  <div class="tab active" onclick="showTab('risk',this)">Miss-Risk Meter</div>
  <div class="tab" onclick="showTab('excl',this)">Exclusion Zone</div>
  <div class="tab" onclick="showTab('anti',this)">Anti-Prediction</div>
  <div class="tab" onclick="showTab('sig',this)">0-Hit Signature</div>
  <div class="tab" onclick="showTab('rec',this)">Post-Miss Recovery</div>
</nav>
<main>

<!-- TAB 1: MISS-RISK METER -->
<div id="tab-risk" class="panel active">
  <h2>Miss-Risk Meter</h2>
  <p class="sub">Consensus for draw #{latest_serial} — each number's score = how many of 16 methods included it in their top-15 picks.
  Numbers with score 0 form the <strong>exclusion zone</strong>: not predicted by any method.
  A tight consensus (small coverage) means more numbers are completely unguarded — higher miss risk.</p>
  <div class="kpi-row">
    <div class="kpi"><div class="val blue">{coverage}</div><div class="lbl">Numbers covered</div><div class="sub2">picked by ≥1 method</div></div>
    <div class="kpi"><div class="val orange">{excl_size_latest}</div><div class="lbl">Exclusion zone size</div><div class="sub2">not picked by any method</div></div>
    <div class="kpi"><div class="val" id="riskPct"></div><div class="lbl">Miss-risk estimate</div><div class="sub2">P(all 6 in excl zone)</div></div>
    <div class="kpi"><div class="val" id="ezHitRate"></div><div class="lbl">EZ historical hit rate</div><div class="sub2">backtest avg</div></div>
  </div>
  <div class="chart-box">
    <h3>Consensus score per number (draw #{latest_serial} predictions)</h3>
    <div class="chart-wrap" style="height:200px"><canvas id="cnsChart"></canvas></div>
  </div>
  <p style="font-size:.8rem;color:#64748b">
    Bars coloured: dark = score 0 (exclusion zone) &#183; mid = picked by 1-7 methods &#183; bright = picked by 8+ methods (consensus core).
    The actual draw #{latest_serial} result: <span id="actualResult"></span>
  </p>
</div>

<!-- TAB 2: EXCLUSION ZONE -->
<div id="tab-excl" class="panel">
  <h2>Exclusion Zone Analysis</h2>
  <p class="sub">For each of {T} backtest draws, numbers not picked by any of 16 methods form the exclusion zone.
  Tracks how many of the 6 actual drawn balls fell inside the exclusion zone — if the rate exceeds random chance, the models have a systematic blind spot.</p>
  <div class="kpi-row">
    <div class="kpi"><div class="val">{ez_avg_size}</div><div class="lbl">Avg exclusion zone size</div><div class="sub2">numbers unpredicted</div></div>
    <div class="kpi"><div class="val orange" id="ezHitsKpi">{ez_avg_hits}</div><div class="lbl">Avg EZ hits per draw</div><div class="sub2">actual balls in EZ</div></div>
    <div class="kpi"><div class="val">{ez_baseline}</div><div class="lbl">Expected by chance</div><div class="sub2">6 × EZ_size / 43</div></div>
    <div class="kpi"><div class="val" id="ezLift"></div><div class="lbl">Lift vs random</div><div class="sub2">> 1.0 = blind spot confirmed</div></div>
  </div>
  <div class="chart-box">
    <h3>EZ hit count distribution (how many actual balls landed in exclusion zone per draw)</h3>
    <div class="dist-row" id="ezDistRow"></div>
  </div>
  <div class="chart-box">
    <h3>EZ hits per draw over time</h3>
    <div class="chart-wrap" style="height:160px"><canvas id="ezTimeChart"></canvas></div>
  </div>
</div>

<!-- TAB 3: ANTI-PREDICTION -->
<div id="tab-anti" class="panel">
  <h2>Anti-Prediction Backtest</h2>
  <p class="sub">Instead of picking the most-predicted numbers, pick the <em>least</em>-predicted — those with the lowest consensus score across all 16 methods.
  If the models systematically over-concentrate on the wrong numbers, the inverse strategy would outperform random baseline.</p>
  <div class="kpi-row">
    <div class="kpi"><div class="val" id="a6avg"></div><div class="lbl">Anti-6 avg hits</div><div class="sub2">baseline {rand6}</div></div>
    <div class="kpi"><div class="val" id="a6lift"></div><div class="lbl">Anti-6 lift</div><div class="sub2">vs random</div></div>
    <div class="kpi"><div class="val" id="a15avg"></div><div class="lbl">Anti-15 avg hits</div><div class="sub2">baseline {rand15}</div></div>
    <div class="kpi"><div class="val" id="a15lift"></div><div class="lbl">Anti-15 lift</div><div class="sub2">vs random</div></div>
  </div>
  <div class="chart-box">
    <h3>Anti-6 pick hit distribution ({T} draws)</h3>
    <div class="dist-row" id="anti6DistRow"></div>
  </div>
  <div class="chart-box">
    <h3>Anti-15 pick hit distribution ({T} draws)</h3>
    <div class="dist-row" id="anti15DistRow"></div>
  </div>
  <div class="chart-box">
    <h3>Cumulative avg hits: Anti-15 vs consensus top-15 vs random baseline</h3>
    <div class="chart-wrap" style="height:180px"><canvas id="antiCumChart"></canvas></div>
  </div>
</div>

<!-- TAB 4: 0-HIT SIGNATURE -->
<div id="tab-sig" class="panel">
  <h2>0-Hit Draw Signature</h2>
  <p class="sub">Draws where the all-16-method consensus top-15 scored 0 hits. Are these draws structurally different from average?</p>
  <div class="kpi-row">
    <div class="kpi"><div class="val bad" id="zeroCount"></div><div class="lbl">0-hit consensus draws</div><div class="sub2">out of {T}</div></div>
    <div class="kpi"><div class="val" id="zeroRate"></div><div class="lbl">Miss rate</div><div class="sub2">% of draws</div></div>
    <div class="kpi"><div class="val" id="zeroCsAvg">{consensus_avg}</div><div class="lbl">Overall avg score</div><div class="sub2">consensus top-15</div></div>
  </div>
  <div class="profile-cmp" id="profileCmp"></div>
  <div class="chart-box">
    <h3>Recent 0-hit draws</h3>
    <div class="tbl-wrap"><table class="dtbl">
      <thead><tr><th>Draw</th><th>Date</th><th>Actual balls</th><th>EZ hits</th></tr></thead>
      <tbody id="zeroDtbl"></tbody>
    </table></div>
  </div>
</div>

<!-- TAB 5: POST-MISS RECOVERY -->
<div id="tab-rec" class="panel">
  <h2>Post-Miss Recovery</h2>
  <p class="sub">After N consecutive 0-hit draws (consensus top-15 vs actual), what score does the very next draw achieve?
  If recovery is above average, misses cluster and then revert. If flat, misses are purely random with no memory.</p>
  <div class="kpi-row">
    <div class="kpi"><div class="val">{consensus_avg}</div><div class="lbl">Overall avg score</div><div class="sub2">all {T} draws</div></div>
    <div class="kpi"><div class="val" id="recAvg1"></div><div class="lbl">Avg after 1 miss</div><div class="sub2">immediate reversion</div></div>
    <div class="kpi"><div class="val" id="recAvg2"></div><div class="lbl">Avg after 2 misses</div><div class="sub2">2-streak recovery</div></div>
  </div>
  <div class="chart-box">
    <h3>Avg score on next draw, grouped by consecutive miss streak length before it</h3>
    <div class="chart-wrap" style="height:200px"><canvas id="recChart"></canvas></div>
  </div>
  <div id="recDetails"></div>
</div>

</main>
<script>
// ── Embedded data ──────────────────────────────────────────────────────────
const LATEST_CNS   = {J(latest_consensus)};
const LATEST_S     = {latest_serial};
const EZ_DATA      = {J(ez_timeline)};
const EZ_AVG_HITS  = {ez_avg_hits};
const EZ_BASELINE  = {ez_baseline};
const EZ_DIST      = {J(ez_dist)};
const ANTI6_DIST   = {J(anti6_dist)};
const ANTI15_DIST  = {J(anti15_dist)};
const ANTI6_AVG    = {anti6_avg};
const ANTI15_AVG   = {anti15_avg};
const ANTI6_LIFT   = {anti6_lift};
const ANTI15_LIFT  = {anti15_lift};
const RAND6        = {rand6};
const RAND15       = {rand15};
const ANTI6_HITS   = {J(anti6_hits.tolist())};
const ANTI15_HITS  = {J(anti15_hits.tolist())};
const TOP15_SCORES = {J(top15_scores.tolist())};
const SERIALS      = {J(serials)};
const PROF_ZERO    = {J(prof_zero)};
const PROF_ALL     = {J(prof_all)};
const ZERO_DRAWS   = {J(zero_draws_display)};
const RECOVERY     = {J(recovery_rows)};
const CNS_AVG      = {consensus_avg};
// Actual result for draw LATEST_S
const LATEST_ACTUAL= {J([DATA[-1]['a']])};

const DIST_COLORS=['#475569','#64748b','#38bdf8','#818cf8','#4ade80','#facc15','#f97316'];
const HIT_LABELS  =['0-hit','1-hit','2-hit','3-hit','4-hit','5-hit','6-hit'];

// ── Tab switching ──────────────────────────────────────────────────────────
const built={{}};
function showTab(id,el){{
  document.querySelectorAll('.panel').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('nav .tab').forEach(t=>t.classList.remove('active'));
  document.getElementById('tab-'+id).classList.add('active');
  if(el) el.classList.add('active');
  if(!built[id]){{ built[id]=true; builders[id]&&builders[id](); }}
}}

// ── Section 1: Miss-Risk Meter ─────────────────────────────────────────────
function buildRisk(){{
  const ez = LATEST_CNS.filter(v=>v===0).length;
  // P(all 6 from EZ) = C(ez,6)/C(43,6) — approximation
  function comb(n,k){{if(k>n)return 0;let r=1;for(let i=0;i<k;i++)r=r*(n-i)/(i+1);return r;}}
  const risk = ez>=6 ? (comb(ez,6)/comb(43,6)*100).toFixed(2)+'%' : '<0.01%';
  document.getElementById('riskPct').textContent = risk;
  document.getElementById('riskPct').className = 'val '+(ez>15?'bad':ez>10?'warn':'good');
  document.getElementById('ezHitRate').textContent = EZ_AVG_HITS.toFixed(3);
  document.getElementById('ezHitRate').className   = 'val '+(EZ_AVG_HITS>EZ_BASELINE?'bad':'good');

  // Actual result for latest draw
  const actual = LATEST_ACTUAL[0];
  const actualSet = new Set(actual);
  const inEZ = actual.filter(n=>LATEST_CNS[n-1]===0);
  document.getElementById('actualResult').innerHTML =
    actual.map(n=>`<span class="ball ${{LATEST_CNS[n-1]===0?'b-hi':'b-norm'}}">${{n}}</span>`).join('')+
    ` (${{inEZ.length}} in exclusion zone)`;

  // Chart
  const labels = Array.from({{length:43}},(_,i)=>i+1);
  const data   = LATEST_CNS;
  const bkgs   = data.map(v=>v===0?'#1e293b':v>=8?'#fb923c88':'#38bdf888');
  const borders= data.map(v=>v===0?'#334155':v>=8?'#f97316':'#0ea5e9');
  new Chart(document.getElementById('cnsChart').getContext('2d'),{{
    type:'bar',
    data:{{labels,datasets:[{{data,backgroundColor:bkgs,borderColor:borders,borderWidth:1,borderRadius:2}}]}},
    options:{{responsive:true,maintainAspectRatio:false,
      plugins:{{legend:{{display:false}},tooltip:{{callbacks:{{title:c=>`Number ${{c[0].label}}`,label:c=>`Picked by ${{c[0].parsed.y}}/16 methods`}}}}}},
      scales:{{
        x:{{ticks:{{color:'#64748b',font:{{size:9}}}},grid:{{display:false}}}},
        y:{{min:0,max:16,ticks:{{color:'#64748b',stepSize:4}},grid:{{color:'#334155'}}}}
      }}
    }}
  }});
}}

// ── Section 2: Exclusion Zone ──────────────────────────────────────────────
function buildExcl(){{
  const lift = (EZ_AVG_HITS/EZ_BASELINE).toFixed(3);
  document.getElementById('ezLift').textContent = lift+'x';
  document.getElementById('ezLift').className   = 'val '+(lift>1.05?'bad':lift<0.95?'good':'warn');

  // Distribution cards
  const dr=document.getElementById('ezDistRow');
  EZ_DIST.forEach((cnt,h)=>{{
    if(h>6)return;
    const c=document.createElement('div'); c.className='dist-card';
    c.innerHTML=`<div class="dn" style="color:${{DIST_COLORS[h]}}">${{cnt}}</div><div class="dl">${{h}} ball${{h!==1?'s':''}} in EZ</div>`;
    dr.appendChild(c);
  }});

  // Timeline chart
  const labels=EZ_DATA.map(d=>d.s);
  new Chart(document.getElementById('ezTimeChart').getContext('2d'),{{
    type:'bar',
    data:{{labels,datasets:[
      {{label:'EZ hits',data:EZ_DATA.map(d=>d.ezh),backgroundColor:'#fb923c88',borderColor:'#f97316',borderWidth:0,barPercentage:1.0,categoryPercentage:1.0}},
    ]}},
    options:{{responsive:true,maintainAspectRatio:false,
      plugins:{{legend:{{labels:{{color:'#94a3b8',font:{{size:11}}}}}},tooltip:{{callbacks:{{title:c=>`Draw ${{c[0].label}}`,label:c=>`${{c[0].parsed.y}} actual ball(s) in exclusion zone`}}}}}},
      scales:{{
        x:{{ticks:{{display:false}},grid:{{display:false}}}},
        y:{{min:0,max:6,ticks:{{color:'#64748b',stepSize:1}},grid:{{color:'#334155'}}}}
      }}
    }}
  }});
}}

// ── Section 3: Anti-Prediction ─────────────────────────────────────────────
function buildAnti(){{
  document.getElementById('a6avg').textContent  = ANTI6_AVG;
  document.getElementById('a6avg').className    = 'val '+(ANTI6_LIFT>1.05?'good':ANTI6_LIFT<0.95?'bad':'warn');
  document.getElementById('a6lift').textContent = ANTI6_LIFT+'x';
  document.getElementById('a6lift').className   = 'val '+(ANTI6_LIFT>1.05?'good':ANTI6_LIFT<0.95?'bad':'warn');
  document.getElementById('a15avg').textContent  = ANTI15_AVG;
  document.getElementById('a15avg').className    = 'val '+(ANTI15_LIFT>1.05?'good':ANTI15_LIFT<0.95?'bad':'warn');
  document.getElementById('a15lift').textContent = ANTI15_LIFT+'x';
  document.getElementById('a15lift').className   = 'val '+(ANTI15_LIFT>1.05?'good':ANTI15_LIFT<0.95?'bad':'warn');

  function distCards(id, dist){{
    const dr=document.getElementById(id);
    dist.forEach((cnt,h)=>{{
      if(h>6)return;
      const c=document.createElement('div'); c.className='dist-card';
      c.innerHTML=`<div class="dn" style="color:${{DIST_COLORS[h]}}">${{cnt}}</div><div class="dl">${{h}}-hit</div>`;
      dr.appendChild(c);
    }});
  }}
  distCards('anti6DistRow',  ANTI6_DIST);
  distCards('anti15DistRow', ANTI15_DIST);

  // Cumulative chart
  let a15sum=0, cnsSum=0;
  const cnsLabels=[], a15Cum=[], cnsCum=[], randLine=[];
  ANTI15_HITS.forEach((v,i)=>{{
    a15sum+=v; cnsSum+=TOP15_SCORES[i];
    cnsLabels.push(SERIALS[i]);
    a15Cum.push(+(a15sum/(i+1)).toFixed(3));
    cnsCum.push(+(cnsSum/(i+1)).toFixed(3));
    randLine.push(+RAND15.toFixed(3));
  }});
  new Chart(document.getElementById('antiCumChart').getContext('2d'),{{
    type:'line',
    data:{{labels:cnsLabels,datasets:[
      {{label:'Anti-15',data:a15Cum,borderColor:'#fb923c',backgroundColor:'transparent',borderWidth:2,pointRadius:0,tension:.3}},
      {{label:'Consensus top-15',data:cnsCum,borderColor:'#38bdf8',backgroundColor:'transparent',borderWidth:2,pointRadius:0,tension:.3}},
      {{label:'Random baseline',data:randLine,borderColor:'#475569',backgroundColor:'transparent',borderWidth:1,borderDash:[4,3],pointRadius:0}},
    ]}},
    options:{{responsive:true,maintainAspectRatio:false,
      plugins:{{legend:{{labels:{{color:'#94a3b8',font:{{size:11}}}}}},tooltip:{{mode:'index',intersect:false}}}},
      scales:{{x:{{ticks:{{display:false}},grid:{{display:false}}}},y:{{ticks:{{color:'#64748b'}},grid:{{color:'#334155'}}}}}}
    }}
  }});
}}

// ── Section 4: 0-Hit Signature ─────────────────────────────────────────────
function buildSig(){{
  document.getElementById('zeroCount').textContent = PROF_ZERO.count||0;
  document.getElementById('zeroRate').textContent  = PROF_ZERO.count ? ((PROF_ZERO.count/TOP15_SCORES.length)*100).toFixed(1)+'%' : '0%';

  const fields=[
    ['avg_ball',   'Avg ball value',       'Higher = draws skewed toward large numbers'],
    ['avg_spread', 'Avg spread (max-min)', 'Higher = more dispersed draws'],
    ['avg_odd',    'Avg odd count',        'Out of 6 balls'],
    ['avg_high',   'Avg high count (>21)', 'Above midpoint of 1-43'],
    ['avg_consec', 'Avg consecutive pairs','Adjacent numbers in same draw'],
  ];
  const cmp=document.getElementById('profileCmp');
  ['0-Hit Draws ('+PROF_ZERO.count+')', 'All '+TOP15_SCORES.length+' Draws'].forEach((title,idx)=>{{
    const prof=idx===0?PROF_ZERO:PROF_ALL;
    const box=document.createElement('div'); box.className='profile-box';
    box.innerHTML=`<h4>${{title}}</h4>`+
      fields.map(([k,lbl,hint])=>{{
        const val=prof[k]||0;
        const other=idx===0?(PROF_ALL[k]||0):(PROF_ZERO[k]||0);
        const diff=val-other;
        const cls=idx===0?(Math.abs(diff)<0.15?'':'diff'+(diff>0?' warn':' blue')):'';
        return `<div class="profile-row"><span class="pl" title="${{hint}}">${{lbl}}</span><span class="pv ${{cls}}">${{val}}</span></div>`;
      }}).join('');
    cmp.appendChild(box);
  }});

  // Table of 0-hit draws
  const tbody=document.getElementById('zeroDtbl');
  ZERO_DRAWS.forEach(r=>{{
    const tr=document.createElement('tr');
    tr.innerHTML=`<td style="color:#64748b;font-size:.8rem">#${{r.s}}</td>
      <td style="color:#475569;font-size:.78rem">${{r.d||'—'}}</td>
      <td>${{r.n.map(n=>`<span class="ball b-norm">${{n}}</span>`).join('')}}</td>
      <td><span style="color:${{r.ezh>0?'#fb923c':'#475569'}};font-weight:700">${{r.ezh}}</span></td>`;
    tbody.appendChild(tr);
  }});
}}

// ── Section 5: Post-Miss Recovery ─────────────────────────────────────────
function buildRec(){{
  if(RECOVERY.length>=1) document.getElementById('recAvg1').textContent=RECOVERY[0].avg;
  if(RECOVERY.length>=2) document.getElementById('recAvg2').textContent=RECOVERY[1].avg;

  // Avg recovery chart
  const labels=RECOVERY.map(r=>r.n===5?'5+ misses':r.n+' miss'+(r.n>1?'es':''));
  const avgs  =RECOVERY.map(r=>r.avg);
  const counts=RECOVERY.map(r=>r.count);
  new Chart(document.getElementById('recChart').getContext('2d'),{{
    type:'bar',
    data:{{labels,datasets:[
      {{label:'Avg score after miss streak',data:avgs,backgroundColor:'#818cf888',borderColor:'#818cf8',borderWidth:1,borderRadius:4,yAxisID:'y'}},
      {{label:'Overall avg',data:Array(labels.length).fill(CNS_AVG),type:'line',borderColor:'#38bdf8',borderWidth:1,borderDash:[4,3],pointRadius:0,yAxisID:'y'}},
    ]}},
    options:{{responsive:true,maintainAspectRatio:false,
      plugins:{{
        legend:{{labels:{{color:'#94a3b8',font:{{size:11}}}}}},
        tooltip:{{callbacks:{{
          title:c=>`After ${{c[0].label}}`,
          label:c=>c.dataset.label+': '+c.parsed.y+(c.datasetIndex===0?' avg hits':'')
        }}}}
      }},
      scales:{{
        x:{{ticks:{{color:'#94a3b8'}},grid:{{display:false}}}},
        y:{{ticks:{{color:'#64748b'}},grid:{{color:'#334155'}},title:{{display:true,text:'Avg hits (consensus top-15)',color:'#64748b',font:{{size:10}}}}}}
      }}
    }}
  }});

  // Detail cards
  const det=document.getElementById('recDetails');
  RECOVERY.forEach(r=>{{
    if(r.count===0)return;
    const d=document.createElement('div');
    d.style.cssText='background:#1e293b;border-radius:10px;padding:14px;margin-bottom:10px';
    d.innerHTML=`<div style="font-size:.88rem;font-weight:700;color:#94a3b8;margin-bottom:8px">After ${{r.n==='5'||r.n>=5?'5+':r.n}} consecutive miss${{r.n>1?'es':''}} — next draw (${{r.count}} cases)</div>`+
      `<div style="display:flex;gap:16px;flex-wrap:wrap;font-size:.82rem">
        <span>Avg score: <strong style="color:#818cf8">${{r.avg}}</strong></span>
        <span>vs overall: <strong style="color:#38bdf8">${{CNS_AVG}}</strong></span>
        <span>Diff: <strong style="color:${{r.avg>CNS_AVG?'#4ade80':'#f87171'}}">${{r.avg>CNS_AVG?'+':''}}${{(r.avg-CNS_AVG).toFixed(3)}}</strong></span>
      </div>`;
    det.appendChild(d);
  }});
}}

const builders={{
  'risk': buildRisk,
  'excl': buildExcl,
  'anti': buildAnti,
  'sig':  buildSig,
  'rec':  buildRec,
}};

// Build first tab immediately
buildRisk(); built['risk']=true;
</script>
</body>
</html>"""

with open(HTML_OUT, 'w', encoding='utf-8') as f:
    f.write(html_out)
print(f"Saved {HTML_OUT} ({len(html_out)//1024} KB)")
