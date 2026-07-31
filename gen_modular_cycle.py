"""
gen_modular_cycle.py
Generates public/modular_cycle.html with two tabs:
  Tab A: Serial Cycle — draw_serial % 43 grouping, top 28 by frequency
  Tab B: Filtered Serial Cycle — same, but numbers from the 10 worst-K draws removed
"""
import psycopg2, json, os, statistics
from collections import Counter, defaultdict

DB_URL = os.environ["DATABASE_URL"]

N_PICKS = 28
BT_DRAWS = 1000
WORST_K_COUNT = 10  # number of worst-performing K values to filter out

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

# ── Step 1: Score each K value (individual) for >=6 hit rate over last BT_DRAWS ──
print("Scoring 43 K values...")
k_scores = {}
test_start = max(0, N - BT_DRAWS)
for k in range(1, 44):
    hits6 = 0
    valid = 0
    for i in range(test_start, N):
        back = i - k
        if back < 0:
            continue
        valid += 1
        matches = len(draws[back]["all"] & draws[i]["all"])
        if matches >= 6:
            hits6 += 1
    k_scores[k] = (hits6 / valid * 100) if valid > 0 else 0.0

sorted_k = sorted(k_scores.keys(), key=lambda k: k_scores[k])
worst_ks = sorted_k[:WORST_K_COUNT]   # 10 worst
best_ks  = sorted_k[-WORST_K_COUNT:]  # 10 best (for reference)
print(f"Worst {WORST_K_COUNT} K values: {worst_ks}  (lowest >=6 hit rates)")
print(f"Best  {WORST_K_COUNT} K values: {best_ks}")

# ── Serial mod 43 prediction helpers ──
def get_freq(idx):
    """Return Counter of number frequencies from past same-mod draws."""
    s = draws[idx]["s"]
    target_mod = s % 43
    past = [j for j in mod_groups[target_mod] if j < idx]
    if not past:
        return Counter(), []
    freq = Counter()
    for j in past:
        for n in draws[j]["all"]:
            freq[n] += 1
    return freq, past

def predict_base(idx, n_picks):
    freq, past = get_freq(idx)
    if not freq:
        return [], freq
    ranked = sorted(freq.keys(), key=lambda x: (-freq[x], x))
    return ranked[:n_picks], freq

def predict_filtered(idx, n_picks, worst_k_list):
    """Serial mod 43, but exclude numbers from worst-K draws."""
    freq, past = get_freq(idx)
    if not freq:
        return [], freq, set()
    # Bad numbers: appear in the worst-K source draws
    bad = set()
    for k in worst_k_list:
        back = idx - k
        if back >= 0:
            bad |= draws[back]["all"]
    ranked = sorted(freq.keys(), key=lambda x: (-freq[x], x))
    filtered = [n for n in ranked if n not in bad]
    # Fallback: if not enough, pull from bad (sorted by freq)
    if len(filtered) < n_picks:
        filtered += [n for n in ranked if n in bad]
    return filtered[:n_picks], freq, bad

# ── Backtest Tab A: Base serial mod 43 ──
print("Backtesting Tab A (serial mod 43)...")
bt_a, mc_a = [], []
for i in range(test_start, N):
    d = draws[i]
    pred, freq = predict_base(i, N_PICKS)
    if not pred:
        mc_a.append(0)
        bt_a.append({"s": d["s"], "d": d["d"], "actual": sorted(d["all"]),
                     "hitNums": [], "matches": 0, "pred": []})
        continue
    hits = set(pred) & d["all"]
    mc_a.append(len(hits))
    bt_a.append({"s": d["s"], "d": d["d"], "actual": sorted(d["all"]),
                 "hitNums": sorted(hits), "matches": len(hits), "pred": pred})

# ── Backtest Tab B: Filtered (remove worst-K numbers) ──
print("Backtesting Tab B (filtered)...")
bt_b, mc_b = [], []
for i in range(test_start, N):
    d = draws[i]
    pred, freq, bad = predict_filtered(i, N_PICKS, worst_ks)
    if not pred:
        mc_b.append(0)
        bt_b.append({"s": d["s"], "d": d["d"], "actual": sorted(d["all"]),
                     "hitNums": [], "matches": 0, "pred": [], "bad": []})
        continue
    hits = set(pred) & d["all"]
    mc_b.append(len(hits))
    bt_b.append({"s": d["s"], "d": d["d"], "actual": sorted(d["all"]),
                 "hitNums": sorted(hits), "matches": len(hits),
                 "pred": pred, "bad": sorted(bad)})

def stats(mc):
    avg = statistics.mean(mc)
    rand = N_PICKS * 7 / 43
    return {
        "avg": round(avg, 2),
        "rand": round(rand, 2),
        "lift": round((avg / rand - 1) * 100, 1),
        "c0": sum(1 for m in mc if m == 0),
        "c3": sum(1 for m in mc if m >= 3),
        "c4": sum(1 for m in mc if m >= 4),
        "c5": sum(1 for m in mc if m >= 5),
        "c6": sum(1 for m in mc if m >= 6),
        "c7": sum(1 for m in mc if m >= 7),
    }

sa = stats(mc_a)
sb = stats(mc_b)
print(f"Tab A: 6+ hits {sa['c6']}/1000  avg {sa['avg']}")
print(f"Tab B: 6+ hits {sb['c6']}/1000  avg {sb['avg']}")

# ── Next draw prediction ──
# Tab A
freq_next = Counter()
for j in mod_groups[next_mod]:
    for n in draws[j]["all"]:
        freq_next[n] += 1
next_pred_a = [n for n, _ in freq_next.most_common(N_PICKS)]
next_src_count = len(mod_groups[next_mod])

# Tab B
bad_next = set()
for k in worst_ks:
    back = N - 1 - k + 1  # draws[-1] is latest, next is index N (not yet in DB)
    back = (N - 1) - k + 1  # index for draw that would be k steps before next
    back = N - k  # next serial index is N (after all N draws), so k back = N - k
    if 0 <= back < N:
        bad_next |= draws[back]["all"]
ranked_next = sorted(freq_next.keys(), key=lambda x: (-freq_next[x], x))
next_pred_b = [n for n in ranked_next if n not in bad_next]
if len(next_pred_b) < N_PICKS:
    next_pred_b += [n for n in ranked_next if n in bad_next]
next_pred_b = next_pred_b[:N_PICKS]

# Frequency tiers for coloring
def freq_tiers(pred, fq):
    max_f = max(fq.values()) if fq else 1
    def tier(n):
        f = fq.get(n, 0)
        if f >= max_f * 0.7: return 2
        if f >= max_f * 0.4: return 1
        return 0
    return {str(n): tier(n) for n in pred}

def build_data(pred, fq, bt_rows, st, src_count, tab_bad_next=None, include_bad=False):
    return {
        "nPicks": N_PICKS,
        "nextSerial": next_serial,
        "nextMod": next_mod,
        "sourceCount": src_count,
        "prediction": pred,
        "freqMap": {str(n): fq.get(n, 0) for n in pred},
        "freqTier": freq_tiers(pred, fq),
        "badNums": sorted(tab_bad_next) if tab_bad_next else [],
        "btDraws": BT_DRAWS,
        "avgMatches": st["avg"],
        "randBaseline": st["rand"],
        "liftPct": st["lift"],
        "cnt0": st["c0"],
        "cnt3plus": st["c3"],
        "cnt4plus": st["c4"],
        "cnt5plus": st["c5"],
        "cnt6plus": st["c6"],
        "cnt7plus": st["c7"],
        "btResults": [
            {"s": r["s"], "d": r["d"], "actual": r["actual"],
             "hitNums": r["hitNums"], "matches": r["matches"],
             "pred": r.get("pred", []),
             **({"bad": r.get("bad", [])} if include_bad else {})}
            for r in reversed(bt_rows[-100:])
        ]
    }

DA = build_data(next_pred_a, freq_next, bt_a, sa, next_src_count)
DB_data = build_data(next_pred_b, freq_next, bt_b, sb, next_src_count, bad_next, include_bad=True)

WORST_K_SCORES = {k: round(k_scores[k], 2) for k in worst_ks}

PAGE_DATA = {
    "tabA": DA,
    "tabB": DB_data,
    "worstKs": sorted(worst_ks),
    "worstKScores": WORST_K_SCORES,
    "latestSerial": latest["s"],
    "latestDate": latest["d"],
}

data_json = json.dumps(PAGE_DATA, ensure_ascii=False)
TIER_COLORS = ["#38bdf8", "#a78bfa", "#fbbf24"]
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
  min-width:175px;padding:6px;box-shadow:0 12px 32px rgba(0,0,0,.7);z-index:10000}}
.nav-group:hover .nav-dropdown{{display:block}}
.nav-dropdown a{{display:flex;align-items:center;gap:8px;padding:8px 12px;
  border-radius:6px;color:#94a3b8;text-decoration:none;font-size:.82rem;
  white-space:nowrap;transition:.12s}}
.nav-dropdown a:hover,.nav-dropdown a.active{{color:#f1f5f9;background:#1e293b}}
.nav-dd-label{{font-size:.68rem;font-weight:700;color:#475569;padding:6px 12px 2px;
  text-transform:uppercase;letter-spacing:.06em}}
.nav-divider{{height:1px;background:#1e293b;margin:4px 0}}
/* ── LAYOUT ── */
main{{max-width:1100px;margin:0 auto;padding:24px 20px}}
h1{{font-size:1.4rem;font-weight:800;color:#f1f5f9;margin-bottom:4px}}
.subtitle{{font-size:.85rem;color:#64748b;margin-bottom:20px}}
/* ── TABS ── */
.tabs{{display:flex;gap:4px;margin-bottom:24px;border-bottom:1px solid #1e293b;padding-bottom:0}}
.tab-btn{{padding:10px 20px;border-radius:8px 8px 0 0;font-size:.85rem;font-weight:600;
  cursor:pointer;color:#64748b;background:transparent;border:1px solid transparent;
  border-bottom:none;transition:.15s;margin-bottom:-1px}}
.tab-btn:hover{{color:#94a3b8;background:#1e293b}}
.tab-btn.active{{color:#f1f5f9;background:#1e293b;border-color:#334155;border-bottom:1px solid #1e293b}}
.tab-pane{{display:none}}
.tab-pane.active{{display:block}}
/* ── CARDS ── */
.sec{{margin-bottom:28px}}
.sec-title{{font-size:.78rem;font-weight:700;color:#94a3b8;text-transform:uppercase;
  letter-spacing:.06em;margin-bottom:12px}}
.stats-strip{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin-bottom:24px}}
.stat-card{{background:#1e293b;border-radius:10px;padding:14px 16px;text-align:center}}
.stat-card .sv{{font-size:1.6rem;font-weight:800}}
.stat-card .sl{{font-size:.72rem;color:#64748b;margin-top:2px}}
.stat-card .sd{{font-size:.78rem;margin-top:4px;color:#64748b}}
.method-card{{background:#1e293b;border-radius:12px;padding:16px 20px;margin-bottom:20px}}
.method-card.a{{border-left:4px solid #38bdf8}}
.method-card.b{{border-left:4px solid #f59e0b}}
.method-card .mc-title{{font-size:.78rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px}}
.method-card.a .mc-title{{color:#38bdf8}}
.method-card.b .mc-title{{color:#f59e0b}}
.method-card .mc-body{{font-size:.85rem;color:#94a3b8;line-height:1.6}}
/* ── K TAGS ── */
.k-tags{{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}}
.k-tag{{padding:3px 10px;border-radius:6px;font-size:.75rem;font-weight:700;background:#1a2744;color:#f87171}}
/* ── BALLS ── */
.legend{{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:12px}}
.legend-item{{display:flex;align-items:center;gap:6px;font-size:.78rem;color:#94a3b8}}
.legend-dot{{width:12px;height:12px;border-radius:50%}}
.ball-grid{{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:16px}}
.ball{{width:44px;height:44px;border-radius:50%;display:flex;align-items:center;
  justify-content:center;font-size:.9rem;font-weight:800;color:#fff;
  border:2px solid rgba(255,255,255,.15);cursor:default;transition:.12s}}
.ball:hover{{transform:scale(1.08)}}
.ball.filtered-out{{opacity:.25;border-style:dashed}}
/* ── TABLE ── */
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
.pm-excluded{{background:#1e293b;color:#334155;opacity:.35}}
.pm-hit-excluded{{background:linear-gradient(135deg,#dc2626 50%,#475569 50%);color:#fff;box-shadow:0 0 0 2px #f87171;opacity:.75}}
.pred-row td{{background:#0c1420;border-bottom:2px solid #1e293b}}
/* ── COMPARE BANNER ── */
.compare-banner{{display:flex;gap:10px;margin-bottom:24px;flex-wrap:wrap}}
.cmp-box{{flex:1;min-width:140px;background:#1e293b;border-radius:10px;padding:14px 16px;text-align:center}}
.cmp-box .cv{{font-size:1.5rem;font-weight:800}}
.cmp-box .cl{{font-size:.72rem;color:#64748b;margin-top:2px}}
.cmp-arrow{{display:flex;align-items:center;font-size:1.4rem;color:#64748b;padding:0 4px}}
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
  <p class="subtitle">Draw serial % 43 grouping &middot; <span id="srcCount"></span> source draws &middot; predict {N_PICKS} numbers</p>

  <!-- Tabs -->
  <div class="tabs">
    <button class="tab-btn active" onclick="switchTab('a',this)">&#128308; Serial Cycle</button>
    <button class="tab-btn" onclick="switchTab('b',this)">&#128993; Filtered &minus; Worst {WORST_K_COUNT}K</button>
  </div>

  <!-- ── TAB A ── -->
  <div class="tab-pane active" id="pane-a">
    <div class="method-card a">
      <div class="mc-title">Method: Serial Cycle</div>
      <div class="mc-body" id="descA"></div>
    </div>

    <div class="sec">
      <div class="sec-title">Backtest Performance &mdash; last {BT_DRAWS} draws</div>
      <div class="stats-strip" id="statsA"></div>
    </div>

    <div class="sec">
      <div class="sec-title">Predicted {N_PICKS} Numbers for Draw #<span id="nextSA"></span></div>
      <div class="legend" id="legA"></div>
      <div class="ball-grid" id="ballsA"></div>
    </div>

    <div class="sec">
      <div class="sec-title">Backtest &mdash; Last 100 Draws (newest first)</div>
      <table class="bt-table"><thead><tr>
        <th>Draw</th><th>Date</th><th>Actual Numbers</th><th>Hits</th><th></th>
      </tr></thead><tbody id="btA"></tbody></table>
    </div>
  </div>

  <!-- ── TAB B ── -->
  <div class="tab-pane" id="pane-b">
    <div class="method-card b">
      <div class="mc-title">Method: Filtered &minus; Worst {WORST_K_COUNT}K Removed</div>
      <div class="mc-body" id="descB"></div>
      <div class="k-tags" id="worstKTags"></div>
    </div>

    <!-- Compare banner -->
    <div class="compare-banner">
      <div class="cmp-box">
        <div class="cv" style="color:#38bdf8" id="cmpA6"></div>
        <div class="cl">Serial Cycle 6+ hits</div>
      </div>
      <div class="cmp-arrow">&#8594;</div>
      <div class="cmp-box">
        <div class="cv" id="cmpB6"></div>
        <div class="cl">Filtered 6+ hits</div>
      </div>
      <div class="cmp-box" style="border-left:3px solid #64748b">
        <div class="cv" id="cmpDiff"></div>
        <div class="cl">Change</div>
      </div>
    </div>

    <div class="sec">
      <div class="sec-title">Backtest Performance &mdash; last {BT_DRAWS} draws</div>
      <div class="stats-strip" id="statsB"></div>
    </div>

    <div class="sec">
      <div class="sec-title">Predicted {N_PICKS} Numbers for Draw #<span id="nextSB"></span></div>
      <p style="font-size:.78rem;color:#64748b;margin-bottom:10px">
        Dimmed numbers were excluded (appear in worst-K source draws) but added back as fill if needed.
      </p>
      <div class="legend" id="legB"></div>
      <div class="ball-grid" id="ballsB"></div>
    </div>

    <div class="sec">
      <div class="sec-title">Backtest &mdash; Last 100 Draws (newest first)</div>
      <table class="bt-table"><thead><tr>
        <th>Draw</th><th>Date</th><th>Actual Numbers</th><th>Hits</th><th></th>
      </tr></thead><tbody id="btB"></tbody></table>
    </div>
  </div>
</main>

<script>
const PD = {data_json};
const DA = PD.tabA, DB = PD.tabB;
const TIER_COLORS = {json.dumps(TIER_COLORS)};
const TIER_LABELS = {json.dumps(TIER_LABELS)};

// ── Tab switching ──
function switchTab(t, btn) {{
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('pane-'+t).classList.add('active');
}}

// ── Shared helpers ──
function renderStats(containerId, D, accentColor) {{
  const strip = document.getElementById(containerId);
  [
    {{label:'6+ hit draws', val:D.cnt6plus, sub:`5+: ${{D.cnt5plus}}  7: ${{D.cnt7plus}}`, color:accentColor}},
    {{label:'0 hit draws',  val:D.cnt0, sub:`out of ${{D.btDraws}}`, color:'#fb923c'}},
    {{label:'Avg matches',  val:D.avgMatches.toFixed(2), sub:`Random: ${{D.randBaseline.toFixed(2)}}`,
      color: D.avgMatches >= D.randBaseline ? '#4ade80' : '#fb923c'}},
    {{label:'Lift vs random', val:(D.liftPct>0?'+':'')+D.liftPct+'%', sub:`vs baseline`, color: D.liftPct>=0?'#4ade80':'#fb923c'}},
  ].forEach(s => {{
    strip.innerHTML += `<div class="stat-card">
      <div class="sv" style="color:${{s.color}}">${{s.val}}</div>
      <div class="sl">${{s.label}}</div><div class="sd">${{s.sub}}</div></div>`;
  }});
}}

function renderLegend(id) {{
  const el = document.getElementById(id);
  TIER_LABELS.forEach((lbl,i) => {{
    el.innerHTML += `<div class="legend-item">
      <div class="legend-dot" style="background:${{TIER_COLORS[i]}}"></div>${{lbl}}</div>`;
  }});
}}

function renderBalls(id, D, badSet) {{
  const el = document.getElementById(id);
  D.prediction.forEach(n => {{
    const tier = D.freqTier[String(n)] || 0;
    const color = TIER_COLORS[tier];
    const isBad = badSet && badSet.has(n);
    el.innerHTML += `<div class="ball${{isBad?' filtered-out':''}}"
      style="background:${{color}}" title="${{isBad?'⚠ from worst-K draw — filtered':'Freq: '}}${{D.freqMap[String(n)]||0}}">${{n}}</div>`;
  }});
}}

function renderTable(id, D) {{
  const el = document.getElementById(id);
  D.btResults.forEach(r => {{
    const m = r.matches;
    const cls = m>=7?'m-max':m>=6?'m-high':m>=5?'m-mid':'m-low';
    const hitSet  = new Set(r.hitNums);
    const badSet  = new Set(r.bad || []);
    const actual  = r.actual.map(n => {{
      const isHit = hitSet.has(n);
      const bg = isHit ? '#4ade80' : '#1e293b';
      const col = isHit ? '#000' : '#94a3b8';
      return `<span class="hit-ball" style="background:${{bg}};color:${{col}}">${{n}}</span>`;
    }}).join('');
    // Predicted sub-row balls
    const predBalls = (r.pred||[]).map(n => {{
      const isHit = hitSet.has(n);
      const isBad = badSet.has(n);
      let cls = 'pred-mini';
      if (isHit && isBad) cls += ' pm-hit-excluded';
      else if (isHit)     cls += ' pm-hit';
      else if (isBad)     cls += ' pm-excluded';
      else                cls += ' pm-selected';
      return `<span class="${{cls}}">${{n}}</span>`;
    }}).join('');
    el.innerHTML += `
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
}}

// ── Tab A ──
document.getElementById('srcCount').textContent = DA.sourceCount;
document.getElementById('nextSA').textContent = DA.nextSerial;
document.getElementById('descA').textContent =
  `Next draw is #${{DA.nextSerial}} (serial % 43 = ${{DA.nextMod}}). Pool from ${{DA.sourceCount}} past draws with same remainder. Rank by frequency, pick top ${{DA.nPicks}}.`;
renderStats('statsA', DA, '#38bdf8');
renderLegend('legA');
renderBalls('ballsA', DA, null);
renderTable('btA', DA);

// ── Tab B ──
document.getElementById('nextSB').textContent = DB.nextSerial;
document.getElementById('descB').textContent =
  `Same as Serial Cycle, but numbers that appear in draws at the ${{PD.worstKs.length}} worst-performing K distances are removed first. This avoids picking numbers that historically come from low-hit-rate positions.`;

// Worst K tags
const wkEl = document.getElementById('worstKTags');
PD.worstKs.forEach(k => {{
  const rate = PD.worstKScores[String(k)];
  wkEl.innerHTML += `<span class="k-tag">K=${{k}} (${{rate.toFixed(1)}}%)</span>`;
}});

// Compare banner
const diff = DB.cnt6plus - DA.cnt6plus;
document.getElementById('cmpA6').textContent = DA.cnt6plus;
document.getElementById('cmpB6').textContent = DB.cnt6plus;
document.getElementById('cmpB6').style.color = diff > 0 ? '#4ade80' : diff < 0 ? '#f87171' : '#94a3b8';
document.getElementById('cmpDiff').textContent = (diff > 0 ? '+' : '') + diff;
document.getElementById('cmpDiff').style.color = diff > 0 ? '#4ade80' : diff < 0 ? '#f87171' : '#94a3b8';

renderStats('statsB', DB, '#f59e0b');
renderLegend('legB');
const badSet = new Set(DB.badNums);
renderBalls('ballsB', DB, badSet);
renderTable('btB', DB);
</script>
</body>
</html>"""

out_path = os.path.join(os.path.dirname(__file__), "public", "modular_cycle.html")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(HTML)
print(f"Written: {out_path} ({len(HTML):,} bytes)")
print(f"Tab A: 6+ hits {sa['c6']}/1000  avg {sa['avg']}")
print(f"Tab B: 6+ hits {sb['c6']}/1000  avg {sb['avg']}")
print(f"Worst K values: {sorted(worst_ks)}")
