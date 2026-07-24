"""
Generate pos_predict.html — Position 1-6 with multi-strategy comparison.

Strategies compared (backtest window=200 for all):
  A) freq_k2    — simple frequency, pick 2       (current baseline)
  B) freq_k3    — simple frequency, pick 3
  C) recency_k2 — exponential-decay weighted, pick 2  (half-life=50)
  D) recency_k3 — exponential-decay weighted, pick 3
  E) overdue_k2 — frequency × overdue-factor, pick 2
  F) overdue_k3 — frequency × overdue-factor, pick 3
  G) adaptive   — recency + adaptive K (K=2 for pos1&6, K=3 for pos2-5)
"""
import psycopg2, json, collections, math

DB_URL  = "postgresql://neondb_owner:npg_QbHpRZW8of3C@ep-hidden-wind-a1q0el7s-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"
OUT_PATH = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto\public\pos_predict.html"

BT_DRAWS     = 1000
CMP_WINDOW   = 200        # window used for strategy comparison
WINDOWS      = [50, 100, 200, 500, 0]
HALF_LIFE    = 50.0       # recency half-life in draws

POS_META = [
    {"idx": 0, "label": "Position 1", "short": "Pos 1", "desc": "Smallest number drawn",  "color": "#6366f1"},
    {"idx": 1, "label": "Position 2", "short": "Pos 2", "desc": "2nd smallest number",    "color": "#3b82f6"},
    {"idx": 2, "label": "Position 3", "short": "Pos 3", "desc": "3rd number (mid-low)",   "color": "#14b8a6"},
    {"idx": 3, "label": "Position 4", "short": "Pos 4", "desc": "4th number (mid-high)",  "color": "#22c55e"},
    {"idx": 4, "label": "Position 5", "short": "Pos 5", "desc": "5th largest number",     "color": "#f59e0b"},
    {"idx": 5, "label": "Position 6", "short": "Pos 6", "desc": "Largest number drawn",   "color": "#ef4444"},
]

STRATEGIES = [
    {"key": "freq_k2",    "label": "Freq K=2 (baseline)", "k": 2},
    {"key": "freq_k3",    "label": "Freq K=3",            "k": 3},
    {"key": "recency_k2", "label": "Recency K=2",         "k": 2},
    {"key": "recency_k3", "label": "Recency K=3",         "k": 3},
    {"key": "overdue_k2", "label": "Overdue K=2",         "k": 2},
    {"key": "overdue_k3", "label": "Overdue K=3",         "k": 3},
    {"key": "adaptive",   "label": "Adaptive K (rec.)",   "k": None},
]

def adaptive_k(pos_idx): return 2 if pos_idx in [0, 5] else 3

def predict_freq(history, pos_idx, k):
    freq = collections.Counter(d["n"][pos_idx] for d in history)
    return [n for n, _ in freq.most_common(k)]

def predict_recency(history, pos_idx, k, hl=HALF_LIFE):
    n = len(history)
    scores = {}
    for i, d in enumerate(history):
        age = n - 1 - i
        w = 2 ** (-age / hl)
        num = d["n"][pos_idx]
        scores[num] = scores.get(num, 0) + w
    return sorted(scores, key=lambda x: -scores[x])[:k]

def predict_overdue(history, pos_idx, k):
    n = len(history)
    last_seen, freq = {}, {}
    for i, d in enumerate(history):
        num = d["n"][pos_idx]
        last_seen[num] = i
        freq[num] = freq.get(num, 0) + 1
    scores = {}
    for num in range(1, 44):
        f = freq.get(num, 0)
        if f == 0:
            continue
        avg_gap = n / f
        draws_since = n - 1 - last_seen.get(num, -avg_gap)
        scores[num] = f * (1 + draws_since / avg_gap)
    return sorted(scores, key=lambda x: -scores[x])[:k]

def predict(strategy_key, history, pos_idx):
    if len(history) < 5:
        return predict_freq(history, pos_idx, 2)
    if   strategy_key == "freq_k2":    return predict_freq(history,    pos_idx, 2)
    elif strategy_key == "freq_k3":    return predict_freq(history,    pos_idx, 3)
    elif strategy_key == "recency_k2": return predict_recency(history, pos_idx, 2)
    elif strategy_key == "recency_k3": return predict_recency(history, pos_idx, 3)
    elif strategy_key == "overdue_k2": return predict_overdue(history, pos_idx, 2)
    elif strategy_key == "overdue_k3": return predict_overdue(history, pos_idx, 3)
    elif strategy_key == "adaptive":   return predict_recency(history, pos_idx, adaptive_k(pos_idx))
    return predict_freq(history, pos_idx, 2)

# ── Fetch draws ────────────────────────────────────────────────────────────────
print("Fetching draws...")
conn = psycopg2.connect(DB_URL)
cur  = conn.cursor()
cur.execute("SELECT draw_serial, draw_date, num1,num2,num3,num4,num5,num6 FROM loto6_results ORDER BY draw_serial")
rows = cur.fetchall()
conn.close()

draws = [{"s": r[0], "d": str(r[1])[:10] if r[1] else "",
          "n": sorted([r[2],r[3],r[4],r[5],r[6],r[7]])} for r in rows]
T = len(draws)
test_start = T - BT_DRAWS
print(f"Total: {T} draws, testing last {BT_DRAWS}")

# ── Strategy comparison backtest (fixed CMP_WINDOW) ────────────────────────────
print(f"\nRunning strategy comparison (window={CMP_WINDOW})...")
# cmp[strategy_key][pos_idx] = {hitRate, lift, hits, total, pred, k}
cmp_results = {s["key"]: {} for s in STRATEGIES}

for pi in range(6):
    pos_idx = pi
    for s in STRATEGIES:
        hits = 0
        total = 0
        for i in range(test_start, T):
            w = CMP_WINDOW
            train = draws[max(0, i-w):i]
            if len(train) < 5:
                continue
            pred = predict(s["key"], train, pos_idx)
            actual = draws[i]["n"][pos_idx]
            hit = actual in pred
            if hit: hits += 1
            total += 1
        k = s["k"] if s["k"] else adaptive_k(pos_idx)
        hit_rate = hits / total if total else 0
        rand     = k / 43
        lift     = hit_rate / rand if rand else 0
        # current prediction using all pre-test history + CMP_WINDOW
        train_now = draws[max(0, T-CMP_WINDOW):]
        pred_now  = predict(s["key"], train_now, pos_idx)
        cmp_results[s["key"]][pi] = {
            "hitRate": round(hit_rate, 4),
            "lift":    round(lift, 4),
            "hits":    hits,
            "total":   total,
            "pred":    pred_now,
            "k":       k,
        }
        print(f"  {s['label']:25s} Pos{pi+1}: hit={hit_rate:.3f} lift={lift:.3f}x pred={pred_now}")

# ── Find best strategy per position ───────────────────────────────────────────
best_strategy = []
for pi in range(6):
    best_key = max(STRATEGIES, key=lambda s: cmp_results[s["key"]][pi]["lift"])["key"]
    best_strategy.append(best_key)
    best = cmp_results[best_key][pi]
    print(f"\nPos {pi+1} BEST: {best_key}  hit={best['hitRate']:.3f}  lift={best['lift']:.3f}x  pred={best['pred']}")

# ── Per-position detailed data (using best strategy, all windows) ───────────────
print("\nBuilding per-position data...")

def compute_position_detail(pos_idx, best_strat_key):
    bt      = {w: [] for w in WINDOWS}
    hdist   = {w: [0]*7 for w in WINDOWS}
    total_h = {w: 0 for w in WINDOWS}

    for i in range(test_start, T):
        actual = draws[i]["n"][pos_idx]
        for w in WINDOWS:
            train = draws[:i] if w == 0 else draws[max(0, i-w):i]
            if len(train) < 5:
                continue
            pred = predict(best_strat_key, train, pos_idx)
            hit  = actual in pred
            hc   = 1 if hit else 0
            hdist[w][hc] += 1
            total_h[w]   += hc
            bt[w].append({"s": draws[i]["s"], "d": draws[i]["d"],
                          "v": actual, "pr": pred, "hit": hit})

    current, stats = {}, {}
    for w in WINDOWS:
        train = draws if w == 0 else draws[max(0, T-w):]
        current[str(w)] = predict(best_strat_key, train, pos_idx)
        tot      = sum(hdist[w][:2])
        hit_rate = total_h[w] / tot if tot else 0
        k        = cmp_results[best_strat_key][pos_idx]["k"]
        rand     = k / 43
        lift     = hit_rate / rand if rand else 0
        stats[str(w)] = {"hitRate": round(hit_rate,4), "rand": round(rand,4),
                          "lift": round(lift,4), "hits": total_h[w], "total": tot, "k": k}

    # All-time freq and recent history
    freq_all = [0]*43
    for d in draws:
        freq_all[d["n"][pos_idx] - 1] += 1
    history = [{"s": d["s"], "v": d["n"][pos_idx]} for d in draws[-30:]]

    return {
        "windows":  WINDOWS,
        "bt":       {str(w): list(reversed(bt[w]))[:150] for w in WINDOWS},
        "hdist":    {str(w): hdist[w] for w in WINDOWS},
        "current":  current,
        "stats":    stats,
        "freqAll":  freq_all,
        "history":  history,
    }

POS_DATA = [compute_position_detail(pi, best_strategy[pi]) for pi in range(6)]

# ── Serialize ──────────────────────────────────────────────────────────────────
DATA = {
    "strategies": STRATEGIES,
    "posMeta":    POS_META,
    "posData":    POS_DATA,
    "cmp":        cmp_results,
    "bestStrategy": best_strategy,
    "totalDraws": T,
    "btDraws":    BT_DRAWS,
    "cmpWindow":  CMP_WINDOW,
    "latestSerial": draws[-1]["s"],
    "latestDate": draws[-1]["d"],
}
DATA_JSON = json.dumps(DATA, separators=(",",":"))
print(f"\nJSON size: {len(DATA_JSON):,} bytes")

# ── HTML ────────────────────────────────────────────────────────────────────────
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
        <a href="/state_machine.html">🔄 State Machine</a>
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
        <a href="/pos_predict.html" class="active">📊 Pos 1–6 Predict</a>
      </div>
    </div>
  </div>
</nav>"""

HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Position Prediction — Loto 6</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:system-ui,sans-serif;background:#0f172a;color:#e2e8f0;min-height:100vh;padding-top:52px}}

/* ── NAV ── */
.site-nav{{position:fixed;top:0;left:0;right:0;height:52px;background:#0a0f1e;
  border-bottom:1px solid #1e293b;display:flex;align-items:center;padding:0 20px;
  gap:0;z-index:9999;box-shadow:0 2px 16px rgba(0,0,0,.6)}}
.site-nav .nav-logo{{font-size:1rem;font-weight:800;color:#f1f5f9;text-decoration:none;white-space:nowrap;margin-right:24px;flex-shrink:0}}
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
  border-radius:6px;color:#94a3b8;text-decoration:none;font-size:.82rem;white-space:nowrap;transition:.12s}}
.nav-dropdown a:hover,.nav-dropdown a.active{{color:#f1f5f9;background:#1e293b}}
.nav-dd-label{{font-size:.68rem;font-weight:700;color:#475569;padding:6px 12px 2px;text-transform:uppercase;letter-spacing:.06em}}
.nav-divider{{height:1px;background:#1e293b;margin:4px 0}}

/* ── LAYOUT ── */
main{{max-width:1100px;margin:0 auto;padding:24px 20px}}
h1{{font-size:1.4rem;font-weight:800;color:#f1f5f9;margin-bottom:4px}}
.subtitle{{font-size:.85rem;color:#64748b;margin-bottom:20px}}
.sec{{margin-bottom:28px}}
.sec-title{{font-size:.78rem;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:.06em;margin-bottom:10px}}

/* ── STRATEGY COMPARISON TABLE ── */
.cmp-table{{width:100%;border-collapse:collapse;font-size:.78rem;margin-bottom:8px}}
.cmp-table th,.cmp-table td{{padding:7px 10px;border:1px solid #1e293b;text-align:center}}
.cmp-table th{{background:#0f172a;color:#94a3b8;font-size:.7rem;font-weight:600}}
.cmp-table .row-head{{text-align:left;font-weight:600;color:#e2e8f0;white-space:nowrap;min-width:140px}}
.cmp-table .best-cell{{font-weight:800;border-radius:4px}}
.cmp-table .strategy-row:hover td{{background:#1e293b33}}

/* ── SUMMARY STRIP ── */
.cmp-strip{{display:grid;grid-template-columns:repeat(6,1fr);gap:8px;margin-bottom:24px}}
.cmp-card{{background:#1e293b;border-radius:10px;padding:12px;text-align:center;border-top:3px solid;cursor:pointer;transition:.15s}}
.cmp-card:hover{{background:#263548}}
.cmp-card h3{{font-size:.82rem;font-weight:700;margin-bottom:4px}}
.cmp-card .cv{{font-size:1.1rem;font-weight:800}}
.cmp-card .cl{{font-size:.7rem;color:#64748b;margin-top:1px}}
.cmp-card .pn{{font-size:.7rem;margin-top:8px;color:#94a3b8}}
.cmp-card .balls{{display:flex;justify-content:center;gap:4px;margin-top:6px;flex-wrap:wrap}}
.sm-ball{{width:30px;height:30px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:.76rem;font-weight:800;color:#fff}}

/* ── TABS ── */
.pos-tabs{{display:flex;gap:0;margin-bottom:0;border-bottom:2px solid #1e293b;overflow-x:auto;scrollbar-width:none}}
.pos-tabs::-webkit-scrollbar{{display:none}}
.pos-tab{{padding:10px 20px;cursor:pointer;font-size:.84rem;font-weight:700;color:#64748b;
  border-radius:8px 8px 0 0;border:1px solid transparent;border-bottom:none;
  transition:.15s;white-space:nowrap;margin-bottom:-2px;flex-shrink:0}}
.pos-tab:hover{{color:#94a3b8}}
.pos-tab.active{{color:#f1f5f9;border-color:#1e293b;border-bottom:2px solid #0f172a}}
.pos-panel{{display:none;padding-top:20px}}.pos-panel.active{{display:block}}

/* ── INNER WINDOW TABS ── */
.win-tabs{{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:16px}}
.win-btn{{padding:5px 14px;border-radius:6px;cursor:pointer;font-size:.8rem;color:#94a3b8;
  border:1px solid #334155;background:#1e293b;transition:.15s}}
.win-btn:hover{{color:#e2e8f0;background:#334155}}
.win-btn.active{{color:#fff}}

/* ── BEST STRATEGY BADGE ── */
.best-badge{{display:inline-flex;align-items:center;gap:6px;padding:5px 12px;border-radius:8px;
  font-size:.78rem;font-weight:700;background:#0c2e1f;color:#4ade80;border:1px solid #4ade8055;margin-bottom:14px}}

/* ── PICKS ── */
.picks-row{{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-bottom:20px}}
.pick-ball{{width:56px;height:56px;border-radius:50%;display:flex;align-items:center;justify-content:center;
  font-size:1.15rem;font-weight:800;box-shadow:0 2px 12px #0006;color:#fff}}
.pick-lbl{{font-size:.72rem;color:#94a3b8;margin-top:4px;text-align:center}}

/* ── STATS ── */
.stats-row{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px}}
.stat-box{{background:#1e293b;border-radius:8px;padding:9px 16px;min-width:100px}}
.stat-box .sv{{font-size:1.25rem;font-weight:800;color:#f1f5f9}}
.stat-box .sl{{font-size:.7rem;color:#64748b;margin-top:1px}}

/* ── FREQ GRID ── */
.freq-grid{{display:flex;flex-wrap:wrap;gap:4px;margin-bottom:20px}}
.freq-cell{{width:40px;height:40px;border-radius:6px;display:flex;flex-direction:column;
  align-items:center;justify-content:center;cursor:default;border:2px solid transparent;transition:.15s}}
.freq-cell.pick{{box-shadow:0 0 8px rgba(255,255,255,.2)}}
.fc-num{{font-size:.8rem;font-weight:800}}
.fc-cnt{{font-size:.62rem;opacity:.7}}

/* ── SPARKLINE ── */
.spark{{display:flex;gap:3px;align-items:flex-end;height:52px;padding:4px 0;margin-bottom:6px}}
.spark-bar{{border-radius:2px 2px 0 0;flex:1;background:#334155;min-height:3px;cursor:pointer}}

/* ── BT TABLE ── */
.bt-wrap{{max-height:440px;overflow-y:auto;border-radius:8px}}
.bt-tbl{{width:100%;border-collapse:collapse;font-size:.8rem}}
.bt-tbl th{{background:#1e293b;padding:6px 8px;color:#94a3b8;font-size:.72rem;font-weight:600;
  text-align:left;position:sticky;top:0;z-index:2}}
.bt-tbl td{{padding:5px 8px;border-bottom:1px solid #0f172a;vertical-align:middle}}
.bt-tbl tr.hit td:first-child{{border-left:3px solid #22c55e}}
.bt-tbl tr.miss td:first-child{{border-left:3px solid #ef444488}}
.bt-tbl tr:hover td{{background:#1e3a5f22}}
.v-ball{{display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;
  border-radius:50%;font-size:.78rem;font-weight:700;background:#1e3a5f;color:#93c5fd}}
.v-ball.bh{{border:2px solid #22c55e;background:#0c2e1f;color:#4ade80}}
.pchip{{display:inline-flex;align-items:center;justify-content:center;min-width:26px;height:20px;
  border-radius:4px;font-size:.75rem;font-weight:700;padding:0 4px;margin:1px}}
.pc-hit{{background:#14532d;color:#4ade80;border:1px solid #4ade80}}
.pc-miss{{background:#1e293b;color:#64748b;border:1px solid #334155}}

@media(max-width:640px){{
  .cmp-strip{{grid-template-columns:repeat(3,1fr)}}
  .pos-tab{{padding:8px 12px;font-size:.78rem}}
  .cmp-table{{font-size:.72rem}}
}}
</style>
</head>
<body>
{NAV_HTML}
<main>
  <h1>📊 Position Prediction</h1>
  <p class="subtitle">7 strategies compared via walk-forward backtest ({BT_DRAWS} draws, window={CMP_WINDOW}). Best strategy auto-selected per position.</p>

  <!-- Summary strip -->
  <div class="sec">
    <div class="sec-title">Best Predictions for Draw #<span id="nextDraw"></span></div>
    <div class="cmp-strip" id="cmpStrip"></div>
  </div>

  <!-- Strategy comparison table -->
  <div class="sec">
    <div class="sec-title">Strategy Comparison — Lift vs Random (window={CMP_WINDOW})</div>
    <div style="overflow-x:auto"><table class="cmp-table" id="cmpTable"></table></div>
    <p style="font-size:.72rem;color:#64748b;margin-top:6px">
      Green = best per position. K=picks per draw. Lift = hit_rate ÷ random_baseline (K/43).
    </p>
  </div>

  <!-- Position tabs -->
  <div class="pos-tabs" id="posTabs"></div>
  <div id="posPanels"></div>
</main>

<script>
const D = {DATA_JSON};

function hexRgba(h, a) {{
  const r=parseInt(h.slice(1,3),16),g=parseInt(h.slice(3,5),16),b=parseInt(h.slice(5,7),16);
  return `rgba(${{r}},${{g}},${{b}},${{a}})`;
}}

document.getElementById('nextDraw').textContent = D.latestSerial + 1;

// ── Summary strip ─────────────────────────────────────────────────
const strip = document.getElementById('cmpStrip');
D.posMeta.forEach((pm, pi) => {{
  const bestKey = D.bestStrategy[pi];
  const res = D.cmp[bestKey][pi];
  const card = document.createElement('div');
  card.className = 'cmp-card';
  card.style.borderColor = pm.color;
  card.innerHTML = `
    <h3 style="color:${{pm.color}}">${{pm.short}}</h3>
    <div class="cv">${{(res.hitRate*100).toFixed(1)}}%</div>
    <div class="cl">${{res.lift.toFixed(2)}}× lift · K=${{res.k}}</div>
    <div class="pn">Best: ${{D.strategies.find(s=>s.key===bestKey).label}}</div>
    <div class="balls">${{res.pred.map(n=>`<div class="sm-ball" style="background:${{hexRgba(pm.color,.75)}}">${{n}}</div>`).join('')}}</div>`;
  card.onclick = () => activatePos(pi);
  strip.appendChild(card);
}});

// ── Strategy comparison table ─────────────────────────────────────
(function(){{
  const tbl = document.getElementById('cmpTable');
  // Best lift per position
  const bestLift = D.posMeta.map((_,pi) =>
    Math.max(...D.strategies.map(s => D.cmp[s.key][pi].lift))
  );

  let head = '<tr><th class="row-head">Strategy</th>';
  D.posMeta.forEach(pm => head += `<th style="color:${{pm.color}}">${{pm.short}}</th>`);
  head += '</tr>';

  let body = '';
  D.strategies.forEach(s => {{
    body += `<tr class="strategy-row"><td class="row-head">${{s.label}}</td>`;
    D.posMeta.forEach((pm, pi) => {{
      const r = D.cmp[s.key][pi];
      const isBest = Math.abs(r.lift - bestLift[pi]) < 0.0001;
      const alpha = Math.max(0, (r.lift - 1) / (bestLift[pi] - 1 + .001));
      const bg = isBest ? hexRgba(pm.color, .35) : hexRgba(pm.color, alpha * .2);
      body += `<td class="${{isBest?'best-cell':''}}" style="background:${{bg}};color:${{isBest?'#f1f5f9':'#94a3b8'}}">
        ${{(r.hitRate*100).toFixed(1)}}%<br>
        <span style="font-size:.68rem;opacity:.8">${{r.lift.toFixed(2)}}× K=${{r.k}}</span>
      </td>`;
    }});
    body += '</tr>';
  }});
  tbl.innerHTML = head + body;
}})();

// ── Tabs & panels ─────────────────────────────────────────────────
const tabsEl   = document.getElementById('posTabs');
const panelsEl = document.getElementById('posPanels');

function activatePos(pi) {{
  document.querySelectorAll('.pos-tab').forEach((t,i) => {{
    t.classList.toggle('active', i===pi);
    t.style.borderTopColor = i===pi ? D.posMeta[i].color : 'transparent';
    t.style.color = i===pi ? D.posMeta[i].color : '';
  }});
  document.querySelectorAll('.pos-panel').forEach((p,i) => p.classList.toggle('active', i===pi));
}}

D.posMeta.forEach((pm, pi) => {{
  const pd = D.posData[pi];
  const bestKey = D.bestStrategy[pi];
  const bestLabel = D.strategies.find(s=>s.key===bestKey).label;
  const bestK = D.cmp[bestKey][pi].k;

  // Tab
  const tab = document.createElement('div');
  tab.className = 'pos-tab' + (pi===0?' active':'');
  tab.textContent = pm.short;
  if(pi===0) {{ tab.style.borderTopColor=pm.color; tab.style.color=pm.color; }}
  tab.onclick = () => activatePos(pi);
  tabsEl.appendChild(tab);

  // Panel
  const panel = document.createElement('div');
  panel.className = 'pos-panel' + (pi===0?' active':'');
  panel.innerHTML = `
    <div class="sec">
      <div class="sec-title" style="color:${{pm.color}}">${{pm.label}} — ${{pm.desc}}</div>
      <div class="best-badge">✦ Best strategy: ${{bestLabel}} (K=${{bestK}})</div>
      <div class="win-tabs" id="wtabs-${{pi}}"></div>
    </div>
    <div class="sec">
      <div class="sec-title">Prediction for Draw #${{D.latestSerial+1}}</div>
      <div class="picks-row" id="picks-${{pi}}"></div>
    </div>
    <div class="sec">
      <div class="sec-title">All-time Frequency at ${{pm.label}}</div>
      <div class="freq-grid" id="freq-${{pi}}"></div>
    </div>
    <div class="sec">
      <div class="sec-title">Recent 30-Draw Sequence</div>
      <div class="spark" id="spark-${{pi}}"></div>
      <div style="font-size:.72rem;color:#64748b">Highlighted = current prediction pick</div>
    </div>
    <div class="sec">
      <div class="sec-title">Backtest Stats (best strategy)</div>
      <div class="stats-row" id="stats-${{pi}}"></div>
    </div>
    <div class="sec">
      <div class="sec-title">Recent Draw Results</div>
      <div class="bt-wrap"><table class="bt-tbl">
        <thead><tr><th>Draw</th><th>Date</th><th>Actual ${{pm.short}}</th><th>Predicted</th><th>Result</th></tr></thead>
        <tbody id="btbody-${{pi}}"></tbody>
      </table></div>
    </div>`;
  panelsEl.appendChild(panel);

  renderPos(pi, pd.windows[1]);
}});

function renderPos(pi, activeW) {{
  const pm = D.posMeta[pi];
  const pd = D.posData[pi];
  const wKey = String(activeW);
  const bestKey = D.bestStrategy[pi];
  const pickSet = new Set(pd.current[wKey] || []);

  // Window buttons
  const wtabs = document.getElementById(`wtabs-${{pi}}`);
  wtabs.innerHTML = '';
  pd.windows.forEach(w => {{
    const b = document.createElement('div');
    b.className = 'win-btn' + (w===activeW?' active':'');
    if(w===activeW) b.style.cssText=`background:${{hexRgba(pm.color,.25)}};border-color:${{pm.color}};color:${{pm.color}}`;
    b.textContent = w===0 ? 'All-time' : 'Last '+w;
    b.onclick = () => renderPos(pi, w);
    wtabs.appendChild(b);
  }});

  // Picks
  const picks = pd.current[wKey] || [];
  document.getElementById(`picks-${{pi}}`).innerHTML =
    picks.map((n,i) => `<div style="text-align:center">
      <div class="pick-ball" style="background:${{hexRgba(pm.color,.7+i*.1)}}">${{n}}</div>
      <div class="pick-lbl">Pick ${{i+1}}</div>
    </div>`).join('') +
    `<span style="color:#64748b;font-size:.82rem;margin-left:10px">for draw #${{D.latestSerial+1}}<br>
    (${{activeW===0?'All-time':'Last '+activeW}} window)</span>`;

  // Freq grid
  const maxF = Math.max(...pd.freqAll);
  document.getElementById(`freq-${{pi}}`).innerHTML = pd.freqAll.map((cnt,i) => {{
    const n = i+1, isPick = pickSet.has(n);
    const bg = hexRgba(pm.color, 0.08 + 0.72*(cnt/maxF));
    const border = isPick ? `border-color:${{pm.color}};box-shadow:0 0 8px ${{hexRgba(pm.color,.4)}}` : '';
    return `<div class="freq-cell${{isPick?' pick':''}}" style="background:${{bg}};${{border}}" title="#${{n}}: ${{cnt}} times">
      <div class="fc-num">${{n}}</div><div class="fc-cnt">${{cnt}}</div>
    </div>`;
  }}).join('');

  // Sparkline
  const hist = pd.history;
  const maxV = Math.max(...hist.map(h=>h.v)), minV = Math.min(...hist.map(h=>h.v));
  const range = maxV - minV || 1;
  document.getElementById(`spark-${{pi}}`).innerHTML = hist.map(h => {{
    const ht = Math.round(6 + ((h.v-minV)/range)*40);
    const col = pickSet.has(h.v) ? pm.color : '#334155';
    return `<div class="spark-bar" style="height:${{ht}}px;background:${{col}}" title="#${{h.s}}: ${{pm.short}}=${{h.v}}"></div>`;
  }}).join('');

  // Stats
  const stats = pd.stats[wKey] || {{}};
  document.getElementById(`stats-${{pi}}`).innerHTML = `
    <div class="stat-box"><div class="sv">${{(stats.hitRate*100||0).toFixed(1)}}%</div><div class="sl">Hit rate (K=${{stats.k||2}})</div></div>
    <div class="stat-box"><div class="sv">${{(stats.rand*100||0).toFixed(1)}}%</div><div class="sl">Random baseline</div></div>
    <div class="stat-box"><div class="sv">${{(stats.lift||0).toFixed(3)}}×</div><div class="sl">Lift vs random</div></div>
    <div class="stat-box"><div class="sv">${{stats.hits||0}}</div><div class="sl">Hits / ${{stats.total||0}} draws</div></div>`;

  // BT table
  const tbody = document.getElementById(`btbody-${{pi}}`);
  tbody.innerHTML = '';
  (pd.bt[wKey] || []).slice(0, 100).forEach(e => {{
    const tr = document.createElement('tr');
    tr.className = e.hit ? 'hit' : 'miss';
    const ball = `<span class="v-ball${{e.hit?' bh':''}}">${{e.v}}</span>`;
    const chips = (e.pr||[]).map(n =>
      `<span class="pchip ${{n===e.v?'pc-hit':'pc-miss'}}">${{n}}</span>`
    ).join(' ');
    tr.innerHTML = `<td>#${{e.s}}</td><td>${{e.d}}</td><td>${{ball}}</td><td>${{chips}}</td>
      <td style="color:${{e.hit?'#22c55e':'#ef4444'}};font-weight:700">${{e.hit?'✓':'✗'}}</td>`;
    tbody.appendChild(tr);
  }});
}}
</script>
</body>
</html>"""

with open(OUT_PATH, "w", encoding="utf-8") as f:
    f.write(HTML)
print(f"\nWritten: {OUT_PATH} ({len(HTML):,} bytes)")
