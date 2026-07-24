"""
Generate pos_predict.html — Position 1-6 with multi-strategy comparison.

Strategies:
  freq_k2    — simple frequency, K=2  (baseline)
  freq_k3    — simple frequency, K=3
  recency_k2 — exponential-decay weighted, K=2
  recency_k3 — exponential-decay weighted, K=3
  overdue_k2 — frequency × overdue factor, K=2
  overdue_k3 — frequency × overdue factor, K=3
  adaptive   — recency + adaptive K
  adb        — A+B+D: proximity-feedback scoring + adaptive drift correction
               Optimised: precomputed Gaussian lookup + W-vector trick (O(window + 43²))
"""
import psycopg2, json, collections, math

DB_URL  = "postgresql://neondb_owner:npg_QbHpRZW8of3C@ep-hidden-wind-a1q0el7s-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"
OUT_PATH = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto\public\pos_predict.html"

BT_DRAWS    = 1000
CMP_WINDOW  = 200
WINDOWS     = [50, 100, 200, 500, 0]
HALF_LIFE   = 50.0
SIGMA       = 3.5
DRIFT_ALPHA = 0.20
PROX_WEIGHT = 0.5   # weight of proximity vs exact-match

# Precompute Gaussian by distance: GAUSS[d] = exp(-d^2 / 2σ^2)
GAUSS = [math.exp(-(d * d) / (2 * SIGMA * SIGMA)) for d in range(44)]

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
    {"key": "adb",        "label": "ABD (prox+drift)",    "k": None},
]

def adaptive_k(pos_idx): return 2 if pos_idx in [0, 5] else 3

# ── Prediction functions ───────────────────────────────────────────────────────
def predict_freq(history, pos_idx, k):
    freq = collections.Counter(d["n"][pos_idx] for d in history)
    return [n for n, _ in freq.most_common(k)]

def predict_recency(history, pos_idx, k):
    n = len(history)
    scores = {}
    for i, d in enumerate(history):
        w = 2 ** (-(n-1-i) / HALF_LIFE)
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

def predict_adb(history, pos_idx, k, drift=0.0):
    """
    Optimised proximity+drift scoring.
    Step 1: build W[v] = recency-weighted count for each position value v  O(n)
    Step 2: score[n] = Σ_v W[v] * GAUSS[|n-v|]                           O(43²)
    Step 3: apply drift shift                                               O(43)
    Total: O(n + 43²) vs naïve O(n × 43)
    """
    n = len(history)
    if n < 3:
        return predict_freq(history, pos_idx, k)

    # Step 1: weighted count per value
    W = [0.0] * 44
    for i, d in enumerate(history):
        rw = 2 ** (-(n-1-i) / HALF_LIFE)
        v  = d["n"][pos_idx]
        W[v] += rw

    # Step 2: Gaussian proximity score for each candidate
    scores = [0.0] * 44
    for cand in range(1, 44):
        s = 0.0
        for v in range(1, 44):
            if W[v] > 0:
                d_dist = abs(cand - v)
                s += W[v] * (1.0 if cand == v else PROX_WEIGHT * GAUSS[d_dist])
        scores[cand] = s

    # Step 3: apply drift shift
    if abs(drift) >= 0.5:
        d_int = round(drift)
        shifted = [0.0] * 44
        for cand in range(1, 44):
            target = max(1, min(43, cand + d_int))
            shifted[target] += scores[cand]
        scores = shifted

    return sorted(range(1, 44), key=lambda x: -scores[x])[:k]

def predict(strategy_key, history, pos_idx, drift=0.0):
    if len(history) < 5:
        return predict_freq(history, pos_idx, 2)
    if   strategy_key == "freq_k2":    return predict_freq(history,    pos_idx, 2)
    elif strategy_key == "freq_k3":    return predict_freq(history,    pos_idx, 3)
    elif strategy_key == "recency_k2": return predict_recency(history, pos_idx, 2)
    elif strategy_key == "recency_k3": return predict_recency(history, pos_idx, 3)
    elif strategy_key == "overdue_k2": return predict_overdue(history, pos_idx, 2)
    elif strategy_key == "overdue_k3": return predict_overdue(history, pos_idx, 3)
    elif strategy_key == "adaptive":   return predict_recency(history, pos_idx, adaptive_k(pos_idx))
    elif strategy_key == "adb":        return predict_adb(history,     pos_idx, adaptive_k(pos_idx), drift)
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

# ── Strategy comparison backtest ───────────────────────────────────────────────
print(f"\nRunning strategy comparison (window={CMP_WINDOW})...")
cmp_results = {s["key"]: {} for s in STRATEGIES}
final_drifts = {}

for pi in range(6):
    hits  = {s["key"]: 0 for s in STRATEGIES}
    total = {s["key"]: 0 for s in STRATEGIES}
    drift_val = 0.0

    for i in range(test_start, T):
        train  = draws[max(0, i-CMP_WINDOW):i]
        actual = draws[i]["n"][pi]
        if len(train) < 5:
            continue

        for s in STRATEGIES:
            d  = drift_val if s["key"] == "adb" else 0.0
            pr = predict(s["key"], train, pi, d)
            if actual in pr: hits[s["key"]] += 1
            total[s["key"]] += 1

        # Update ABD drift
        adb_pr = predict("adb", train, pi, drift_val)
        if adb_pr:
            closest  = min(adb_pr, key=lambda p: abs(p - actual))
            drift_val = DRIFT_ALPHA * (actual - closest) + (1-DRIFT_ALPHA) * drift_val

    final_drifts[pi] = round(drift_val, 3)

    for s in STRATEGIES:
        h  = hits[s["key"]]
        t  = total[s["key"]]
        k  = s["k"] if s["k"] else adaptive_k(pi)
        hr = h / t if t else 0
        rand = k / 43
        lift = hr / rand if rand else 0
        train_now = draws[max(0, T-CMP_WINDOW):]
        d_now = final_drifts[pi] if s["key"] == "adb" else 0.0
        pred_now = predict(s["key"], train_now, pi, d_now)
        cmp_results[s["key"]][pi] = {
            "hitRate": round(hr,4), "lift": round(lift,4),
            "hits": h, "total": t, "pred": pred_now, "k": k,
        }

    print(f"  Pos{pi+1} done -- drift={final_drifts[pi]:+.2f}" +
          "".join(f"  {s['label'][:10]}:{cmp_results[s['key']][pi]['lift']:.2f}x" for s in STRATEGIES))

# ── Best strategy per position ─────────────────────────────────────────────────
best_strategy = []
for pi in range(6):
    best_key = max(STRATEGIES, key=lambda s: cmp_results[s["key"]][pi]["lift"])["key"]
    best_strategy.append(best_key)
    b = cmp_results[best_key][pi]
    print(f"Pos {pi+1} BEST: {best_key}  hit={b['hitRate']:.3f}  lift={b['lift']:.3f}x  pred={b['pred']}")

# ── Per-position detail (best strategy, all windows) ──────────────────────────
print("\nBuilding per-position detail...")

def compute_detail(pos_idx, best_key):
    bt      = {w: [] for w in WINDOWS}
    total_h = {w: 0 for w in WINDOWS}

    for i in range(test_start, T):
        actual = draws[i]["n"][pos_idx]
        for w in WINDOWS:
            train = draws[:i] if w == 0 else draws[max(0, i-w):i]
            if len(train) < 5:
                continue
            pred     = predict(best_key, train, pos_idx)
            hit      = actual in pred
            min_dist = min(abs(actual - p) for p in pred) if pred else 99
            if hit: total_h[w] += 1
            bt[w].append({"s": draws[i]["s"], "d": draws[i]["d"],
                          "v": actual, "pr": pred, "hit": hit, "md": min_dist})

    current, stats = {}, {}
    for w in WINDOWS:
        train    = draws if w == 0 else draws[max(0, T-w):]
        d_val    = final_drifts[pos_idx] if best_key == "adb" else 0.0
        current[str(w)] = predict(best_key, train, pos_idx, d_val)
        tot  = len(bt[w])
        hr   = total_h[w] / tot if tot else 0
        k    = cmp_results[best_key][pos_idx]["k"]
        rand = k / 43
        lift = hr / rand if rand else 0
        tol  = {str(t): sum(1 for e in bt[w] if e["md"] <= t) for t in [0,1,2,3]}
        stats[str(w)] = {"hitRate": round(hr,4), "rand": round(rand,4),
                         "lift": round(lift,4), "hits": total_h[w], "total": tot,
                         "k": k, "tol": tol}

    freq_all = [0]*43
    for d in draws:
        freq_all[d["n"][pos_idx]-1] += 1
    history = [{"s": d["s"], "v": d["n"][pos_idx]} for d in draws[-30:]]

    return {"windows": WINDOWS,
            "bt":      {str(w): list(reversed(bt[w]))[:120] for w in WINDOWS},
            "current": current, "stats": stats,
            "freqAll": freq_all, "history": history,
            "drift":   final_drifts[pos_idx]}

POS_DATA = [compute_detail(pi, best_strategy[pi]) for pi in range(6)]

# ── Serialize ──────────────────────────────────────────────────────────────────
DATA = {
    "strategies":   STRATEGIES,
    "posMeta":      POS_META,
    "posData":      POS_DATA,
    "cmp":          cmp_results,
    "bestStrategy": best_strategy,
    "finalDrifts":  final_drifts,
    "totalDraws":   T,
    "btDraws":      BT_DRAWS,
    "cmpWindow":    CMP_WINDOW,
    "latestSerial": draws[-1]["s"],
    "latestDate":   draws[-1]["d"],
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
.site-nav{{position:fixed;top:0;left:0;right:0;height:52px;background:#0a0f1e;border-bottom:1px solid #1e293b;
  display:flex;align-items:center;padding:0 20px;z-index:9999;box-shadow:0 2px 16px rgba(0,0,0,.6)}}
.site-nav .nav-logo{{font-size:1rem;font-weight:800;color:#f1f5f9;text-decoration:none;white-space:nowrap;margin-right:24px}}
.site-nav .nav-logo span{{color:#38bdf8}}
.nav-groups{{display:flex;gap:4px;align-items:center}}
.nav-group{{position:relative}}
.nav-group-btn{{display:flex;align-items:center;gap:5px;padding:7px 14px;border-radius:7px;cursor:pointer;
  font-size:.82rem;font-weight:600;color:#94a3b8;border:1px solid transparent;transition:.15s;white-space:nowrap}}
.nav-group-btn:hover,.nav-group:hover .nav-group-btn{{color:#f1f5f9;background:#1e293b;border-color:#334155}}
.nav-group-btn .arrow{{font-size:.6rem;opacity:.6;transition:transform .2s}}
.nav-group:hover .nav-group-btn .arrow{{transform:rotate(180deg)}}
.nav-dropdown{{display:none;position:absolute;top:calc(100% + 6px);left:0;background:#0d1526;
  border:1px solid #1e293b;border-radius:10px;min-width:175px;padding:6px;
  box-shadow:0 12px 32px rgba(0,0,0,.7);z-index:10000}}
.nav-group:hover .nav-dropdown{{display:block}}
.nav-dropdown a{{display:flex;align-items:center;gap:8px;padding:8px 12px;border-radius:6px;
  color:#94a3b8;text-decoration:none;font-size:.82rem;white-space:nowrap;transition:.12s}}
.nav-dropdown a:hover,.nav-dropdown a.active{{color:#f1f5f9;background:#1e293b}}
.nav-dd-label{{font-size:.68rem;font-weight:700;color:#475569;padding:6px 12px 2px;text-transform:uppercase;letter-spacing:.06em}}
.nav-divider{{height:1px;background:#1e293b;margin:4px 0}}
main{{max-width:1100px;margin:0 auto;padding:24px 20px}}
h1{{font-size:1.4rem;font-weight:800;color:#f1f5f9;margin-bottom:4px}}
.subtitle{{font-size:.85rem;color:#64748b;margin-bottom:20px}}
.sec{{margin-bottom:28px}}
.sec-title{{font-size:.78rem;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:.06em;margin-bottom:10px}}
/* summary strip */
.cmp-strip{{display:grid;grid-template-columns:repeat(6,1fr);gap:8px;margin-bottom:24px}}
.cmp-card{{background:#1e293b;border-radius:10px;padding:12px;text-align:center;border-top:3px solid;cursor:pointer;transition:.15s}}
.cmp-card:hover{{background:#263548}}
.cmp-card h3{{font-size:.82rem;font-weight:700;margin-bottom:4px}}
.cmp-card .cv{{font-size:1.1rem;font-weight:800}}
.cmp-card .cl{{font-size:.7rem;color:#64748b;margin-top:1px}}
.cmp-card .balls{{display:flex;justify-content:center;gap:4px;margin-top:8px;flex-wrap:wrap}}
.sm-ball{{width:30px;height:30px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:.76rem;font-weight:800;color:#fff}}
/* comparison table */
.cmp-table{{width:100%;border-collapse:collapse;font-size:.78rem}}
.cmp-table th,.cmp-table td{{padding:7px 10px;border:1px solid #1e293b;text-align:center}}
.cmp-table th{{background:#0f172a;color:#94a3b8;font-size:.7rem}}
.cmp-table .rh{{text-align:left;font-weight:600;color:#e2e8f0;min-width:140px}}
.cmp-table .best{{font-weight:800}}
.cmp-table .adb-row td{{border-top:2px solid #38bdf833}}
/* tabs */
.pos-tabs{{display:flex;border-bottom:2px solid #1e293b;overflow-x:auto;scrollbar-width:none}}
.pos-tabs::-webkit-scrollbar{{display:none}}
.pos-tab{{padding:10px 20px;cursor:pointer;font-size:.84rem;font-weight:700;color:#64748b;
  border-radius:8px 8px 0 0;border:1px solid transparent;border-bottom:none;
  transition:.15s;white-space:nowrap;margin-bottom:-2px;flex-shrink:0}}
.pos-tab.active{{color:#f1f5f9;border-color:#1e293b;border-bottom:2px solid #0f172a}}
.pos-panel{{display:none;padding-top:20px}}.pos-panel.active{{display:block}}
.win-tabs{{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:16px}}
.win-btn{{padding:5px 14px;border-radius:6px;cursor:pointer;font-size:.8rem;color:#94a3b8;border:1px solid #334155;background:#1e293b;transition:.15s}}
.win-btn:hover{{color:#e2e8f0}}
.win-btn.active{{color:#fff}}
.info-row{{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px;align-items:center}}
.badge{{padding:4px 12px;border-radius:8px;font-size:.78rem;font-weight:700}}
.bg{{background:#0c2e1f;color:#4ade80;border:1px solid #4ade8033}}
.bb{{background:#0c2240;color:#38bdf8;border:1px solid #38bdf833}}
.ba{{background:#2d1800;color:#fbbf24;border:1px solid #fbbf2433}}
.picks-row{{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-bottom:20px}}
.pick-ball{{width:56px;height:56px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:1.15rem;font-weight:800;color:#fff}}
.pick-lbl{{font-size:.72rem;color:#94a3b8;margin-top:4px;text-align:center}}
.stats-row{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px}}
.stat-box{{background:#1e293b;border-radius:8px;padding:9px 16px;min-width:100px}}
.stat-box .sv{{font-size:1.25rem;font-weight:800}}
.stat-box .sl{{font-size:.7rem;color:#64748b;margin-top:1px}}
/* tolerance bars */
.tol-bars{{display:flex;flex-direction:column;gap:7px;margin-bottom:16px}}
.tol-row{{display:flex;align-items:center;gap:10px}}
.tol-lbl{{font-size:.75rem;color:#94a3b8;width:62px;flex-shrink:0}}
.tol-track{{flex:1;height:22px;background:#1e293b;border-radius:4px;overflow:hidden}}
.tol-fill{{height:100%;border-radius:4px;display:flex;align-items:center;padding-left:8px;font-size:.72rem;font-weight:700;color:#fff;white-space:nowrap;transition:width .4s}}
.tol-pct{{font-size:.75rem;color:#94a3b8;width:50px;text-align:right}}
/* freq grid */
.freq-grid{{display:flex;flex-wrap:wrap;gap:4px;margin-bottom:20px}}
.freq-cell{{width:40px;height:40px;border-radius:6px;display:flex;flex-direction:column;align-items:center;justify-content:center;cursor:default;border:2px solid transparent}}
.freq-cell.pick{{box-shadow:0 0 8px rgba(255,255,255,.2)}}
.fc-num{{font-size:.8rem;font-weight:800}}.fc-cnt{{font-size:.62rem;opacity:.7}}
/* sparkline */
.spark{{display:flex;gap:3px;align-items:flex-end;height:52px;padding:4px 0;margin-bottom:6px}}
.spark-bar{{border-radius:2px 2px 0 0;flex:1;background:#334155;min-height:3px}}
/* bt table */
.bt-wrap{{max-height:440px;overflow-y:auto;border-radius:8px}}
.bt-tbl{{width:100%;border-collapse:collapse;font-size:.8rem}}
.bt-tbl th{{background:#1e293b;padding:6px 8px;color:#94a3b8;font-size:.72rem;font-weight:600;text-align:left;position:sticky;top:0;z-index:2}}
.bt-tbl td{{padding:5px 8px;border-bottom:1px solid #0f172a;vertical-align:middle}}
.bt-tbl tr:hover td{{background:#1e3a5f22}}
.bt-tbl tr.d0 td:first-child{{border-left:3px solid #22c55e}}
.bt-tbl tr.d1 td:first-child{{border-left:3px solid #38bdf8}}
.bt-tbl tr.d2 td:first-child{{border-left:3px solid #f59e0b}}
.bt-tbl tr.dmiss td:first-child{{border-left:3px solid #ef444444}}
.v-ball{{display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;border-radius:50%;font-size:.78rem;font-weight:700}}
.v-ball.d0{{background:#0c2e1f;color:#4ade80;border:2px solid #22c55e}}
.v-ball.d1{{background:#0c2240;color:#38bdf8;border:2px solid #38bdf8}}
.v-ball.d2{{background:#2d1800;color:#fbbf24;border:2px solid #f59e0b}}
.v-ball.dmiss{{background:#1e3a5f;color:#93c5fd}}
.pchip{{display:inline-flex;align-items:center;justify-content:center;min-width:26px;height:20px;border-radius:4px;font-size:.75rem;font-weight:700;padding:0 4px;margin:1px}}
.pc-hit{{background:#14532d;color:#4ade80;border:1px solid #4ade80}}
.pc-near{{background:#0c2240;color:#38bdf8;border:1px solid #38bdf8}}
.pc-miss{{background:#1e293b;color:#64748b;border:1px solid #334155}}
.dist-badge{{font-size:.7rem;font-weight:700;padding:2px 6px;border-radius:4px}}
@media(max-width:640px){{.cmp-strip{{grid-template-columns:repeat(3,1fr)}}.pos-tab{{padding:8px 12px;font-size:.78rem}}}}
</style>
</head>
<body>
{NAV_HTML}
<main>
  <h1>📊 Position Prediction</h1>
  <p class="subtitle">8 strategies compared · {BT_DRAWS}-draw walk-forward backtest · window={CMP_WINDOW} · ABD = Gaussian proximity + adaptive drift correction</p>

  <div class="sec">
    <div class="sec-title">Best Predictions for Draw #<span id="nd"></span></div>
    <div class="cmp-strip" id="cmpStrip"></div>
  </div>

  <div class="sec">
    <div class="sec-title">Strategy Comparison — Lift vs Random</div>
    <div style="overflow-x:auto"><table class="cmp-table" id="cmpTbl"></table></div>
    <p style="font-size:.72rem;color:#64748b;margin-top:6px">Green = best per position. ABD row uses drift-corrected proximity scoring.</p>
  </div>

  <div class="pos-tabs" id="posTabs"></div>
  <div id="posPanels"></div>
</main>

<script>
const D = {DATA_JSON};
function hx(h,a){{const r=parseInt(h.slice(1,3),16),g=parseInt(h.slice(3,5),16),b=parseInt(h.slice(5,7),16);return `rgba(${{r}},${{g}},${{b}},${{a}})`;}}

document.getElementById('nd').textContent = D.latestSerial+1;

// Summary strip
const strip = document.getElementById('cmpStrip');
D.posMeta.forEach((pm,pi)=>{{
  const bk=D.bestStrategy[pi], res=D.cmp[bk][pi];
  const bl=D.strategies.find(s=>s.key===bk).label;
  const c=document.createElement('div');
  c.className='cmp-card'; c.style.borderColor=pm.color;
  c.innerHTML=`<h3 style="color:${{pm.color}}">${{pm.short}}</h3>
    <div class="cv">${{(res.hitRate*100).toFixed(1)}}%</div>
    <div class="cl">${{res.lift.toFixed(2)}}× · K=${{res.k}}</div>
    <div style="font-size:.68rem;color:#475569;margin-top:4px">${{bl}}</div>
    <div class="balls">${{res.pred.map(n=>`<div class="sm-ball" style="background:${{hx(pm.color,.75)}}">${{n}}</div>`).join('')}}</div>`;
  c.onclick=()=>activatePos(pi); strip.appendChild(c);
}});

// Comparison table
(function(){{
  const tbl=document.getElementById('cmpTbl');
  const bestLift=D.posMeta.map((_,pi)=>Math.max(...D.strategies.map(s=>D.cmp[s.key][pi].lift)));
  let h='<tr><th class="rh">Strategy</th>';
  D.posMeta.forEach(pm=>h+=`<th style="color:${{pm.color}}">${{pm.short}}</th>`);
  h+='</tr>';
  let body='';
  D.strategies.forEach(s=>{{
    const isAdb=s.key==='adb';
    body+=`<tr class="${{isAdb?'adb-row':''}}"><td class="rh" style="${{isAdb?'color:#38bdf8':''}}">${{s.label}}</td>`;
    D.posMeta.forEach((pm,pi)=>{{
      const r=D.cmp[s.key][pi], isBest=Math.abs(r.lift-bestLift[pi])<0.0002;
      const alpha=bestLift[pi]>1?Math.max(0,(r.lift-1)/(bestLift[pi]-1))*.22:0;
      const bg=isBest?hx(pm.color,.35):hx(pm.color,alpha);
      body+=`<td class="${{isBest?'best':''}}" style="background:${{bg}};color:${{isBest?'#f1f5f9':'#94a3b8'}}">
        ${{(r.hitRate*100).toFixed(1)}}%<br><span style="font-size:.68rem">${{r.lift.toFixed(2)}}× K=${{r.k}}</span></td>`;
    }});
    body+='</tr>';
  }});
  tbl.innerHTML=h+body;
}})();

// Tabs
const tabsEl=document.getElementById('posTabs'), panelsEl=document.getElementById('posPanels');
function activatePos(pi){{
  document.querySelectorAll('.pos-tab').forEach((t,i)=>{{t.classList.toggle('active',i===pi);t.style.borderTopColor=i===pi?D.posMeta[i].color:'transparent';t.style.color=i===pi?D.posMeta[i].color:'';}});
  document.querySelectorAll('.pos-panel').forEach((p,i)=>p.classList.toggle('active',i===pi));
}}

D.posMeta.forEach((pm,pi)=>{{
  const pd=D.posData[pi],bk=D.bestStrategy[pi];
  const bl=D.strategies.find(s=>s.key===bk).label, bK=D.cmp[bk][pi].k;
  const drift=D.finalDrifts[pi];
  const ds=drift>0?'+':'', dc=Math.abs(drift)<1?'bg':Math.abs(drift)<3?'ba':'ba';

  const tab=document.createElement('div');
  tab.className='pos-tab'+(pi===0?' active':'');
  tab.textContent=pm.short;
  if(pi===0){{tab.style.borderTopColor=pm.color;tab.style.color=pm.color;}}
  tab.onclick=()=>activatePos(pi); tabsEl.appendChild(tab);

  const panel=document.createElement('div');
  panel.className='pos-panel'+(pi===0?' active':'');
  panel.innerHTML=`
    <div class="sec">
      <div class="sec-title" style="color:${{pm.color}}">${{pm.label}} — ${{pm.desc}}</div>
      <div class="info-row">
        <span class="badge bg">✦ Best: ${{bl}} · K=${{bK}}</span>
        <span class="badge ${{dc}}">⇄ Drift: ${{ds}}${{drift.toFixed(2)}} numbers</span>
      </div>
      <div class="win-tabs" id="wt-${{pi}}"></div>
    </div>
    <div class="sec">
      <div class="sec-title">Prediction for Draw #${{D.latestSerial+1}}</div>
      <div class="picks-row" id="pk-${{pi}}"></div>
    </div>
    <div class="sec">
      <div class="sec-title">Tolerance Analysis (A) — how close are predictions to actual?</div>
      <div id="tol-${{pi}}"></div>
    </div>
    <div class="sec">
      <div class="sec-title">All-time Frequency at ${{pm.label}}</div>
      <div class="freq-grid" id="fq-${{pi}}"></div>
    </div>
    <div class="sec">
      <div class="sec-title">Recent 30-Draw Sequence</div>
      <div class="spark" id="sp-${{pi}}"></div>
      <div style="font-size:.72rem;color:#64748b;margin-top:4px">Highlighted = current prediction</div>
    </div>
    <div class="sec">
      <div class="sec-title">Backtest Stats</div>
      <div class="stats-row" id="st-${{pi}}"></div>
    </div>
    <div class="sec">
      <div class="sec-title">Recent Draws &nbsp;
        <span style="color:#22c55e;font-size:.8rem">■ Exact</span> &nbsp;
        <span style="color:#38bdf8;font-size:.8rem">■ ±1</span> &nbsp;
        <span style="color:#f59e0b;font-size:.8rem">■ ±2</span> &nbsp;
        <span style="color:#64748b;font-size:.8rem">■ Miss</span>
      </div>
      <div class="bt-wrap"><table class="bt-tbl">
        <thead><tr><th>Draw</th><th>Date</th><th>Actual</th><th>Predicted</th><th>Distance</th></tr></thead>
        <tbody id="bt-${{pi}}"></tbody>
      </table></div>
    </div>`;
  panelsEl.appendChild(panel);
  renderPos(pi,pd.windows[1]);
}});

function renderPos(pi,aw){{
  const pm=D.posMeta[pi],pd=D.posData[pi],wk=String(aw),bk=D.bestStrategy[pi];
  const ps=new Set(pd.current[wk]||[]),st=pd.stats[wk]||{{}};

  // Window buttons
  const wt=document.getElementById(`wt-${{pi}}`); wt.innerHTML='';
  pd.windows.forEach(w=>{{
    const b=document.createElement('div');
    b.className='win-btn'+(w===aw?' active':'');
    if(w===aw) b.style.cssText=`background:${{hx(pm.color,.2)}};border-color:${{pm.color}};color:${{pm.color}}`;
    b.textContent=w===0?'All-time':'Last '+w;
    b.onclick=()=>renderPos(pi,w); wt.appendChild(b);
  }});

  // Picks
  const picks=pd.current[wk]||[];
  document.getElementById(`pk-${{pi}}`).innerHTML=
    picks.map((n,i)=>`<div style="text-align:center">
      <div class="pick-ball" style="background:${{hx(pm.color,.7+i*.1)}}">${{n}}</div>
      <div class="pick-lbl">Pick ${{i+1}}</div></div>`).join('')+
    `<span style="color:#64748b;font-size:.82rem;margin-left:10px">draw #${{D.latestSerial+1}}<br>${{aw===0?'All-time':'Last '+aw}}</span>`;

  // Tolerance bars
  const tol=st.tol||{{}}, tot=st.total||1;
  const TC=['#22c55e','#38bdf8','#f59e0b','#f97316'],TL=['Exact (±0)','±1','±2','±3'];
  document.getElementById(`tol-${{pi}}`).innerHTML='<div class="tol-bars">'+
    [0,1,2,3].map((t,idx)=>{{
      const cnt=tol[String(t)]||0, pct=tot?(cnt/tot*100):0;
      return `<div class="tol-row">
        <div class="tol-lbl">${{TL[idx]}}</div>
        <div class="tol-track"><div class="tol-fill" style="width:${{pct.toFixed(1)}}%;background:${{TC[idx]}}">${{pct>=8?pct.toFixed(1)+'%':''}}</div></div>
        <div class="tol-pct">${{pct.toFixed(1)}}%</div></div>`;
    }}).join('')+'</div>'+
    `<p style="font-size:.72rem;color:#475569">Out of ${{tot}} backtested draws</p>`;

  // Freq grid
  const mf=Math.max(...pd.freqAll);
  document.getElementById(`fq-${{pi}}`).innerHTML=pd.freqAll.map((cnt,i)=>{{
    const n=i+1,ip=ps.has(n);
    const bg=hx(pm.color,0.08+0.72*(cnt/mf));
    const bdr=ip?`border-color:${{pm.color}};box-shadow:0 0 8px ${{hx(pm.color,.35)}}`:'';
    return `<div class="freq-cell${{ip?' pick':''}}" style="background:${{bg}};${{bdr}}" title="#${{n}}: ${{cnt}} times">
      <div class="fc-num">${{n}}</div><div class="fc-cnt">${{cnt}}</div></div>`;
  }}).join('');

  // Sparkline
  const h=pd.history,mv=Math.max(...h.map(x=>x.v)),nv=Math.min(...h.map(x=>x.v)),rng=mv-nv||1;
  document.getElementById(`sp-${{pi}}`).innerHTML=h.map(x=>{{
    const ht=Math.round(6+((x.v-nv)/rng)*40),col=ps.has(x.v)?pm.color:'#334155';
    return `<div class="spark-bar" style="height:${{ht}}px;background:${{col}}" title="#${{x.s}}: ${{x.v}}"></div>`;
  }}).join('');

  // Stats
  document.getElementById(`st-${{pi}}`).innerHTML=`
    <div class="stat-box"><div class="sv" style="color:#f1f5f9">${{(st.hitRate*100||0).toFixed(1)}}%</div><div class="sl">Exact hit (K=${{st.k||2}})</div></div>
    <div class="stat-box"><div class="sv" style="color:#f1f5f9">${{(st.rand*100||0).toFixed(1)}}%</div><div class="sl">Random baseline</div></div>
    <div class="stat-box"><div class="sv" style="color:#f1f5f9">${{(st.lift||0).toFixed(3)}}×</div><div class="sl">Lift</div></div>
    <div class="stat-box"><div class="sv" style="color:#4ade80">${{(st.tol&&st.tol['1']||0)}} / ${{st.total||0}}</div><div class="sl">Within ±1</div></div>
    <div class="stat-box"><div class="sv" style="color:#38bdf8">${{(st.tol&&st.tol['2']||0)}} / ${{st.total||0}}</div><div class="sl">Within ±2</div></div>`;

  // BT table
  const tbody=document.getElementById(`bt-${{pi}}`); tbody.innerHTML='';
  (pd.bt[wk]||[]).slice(0,100).forEach(e=>{{
    const md=e.md!==undefined?e.md:Math.min(...(e.pr||[]).map(p=>Math.abs(p-e.v)));
    const dc=md===0?'d0':md===1?'d1':md===2?'d2':'dmiss';
    const tr=document.createElement('tr'); tr.className=dc;
    const ball=`<span class="v-ball ${{dc}}">${{e.v}}</span>`;
    const chips=(e.pr||[]).map(n=>{{
      const d2=Math.abs(n-e.v);
      return `<span class="pchip ${{d2===0?'pc-hit':d2<=1?'pc-near':'pc-miss'}}">${{n}}</span>`;
    }}).join(' ');
    const dtxt=md===0?'✓ Exact':md===1?'±1 Near':md===2?'±2 Near':`±${{md}} Miss`;
    const dcol=md===0?'#22c55e':md===1?'#38bdf8':md===2?'#f59e0b':'#64748b';
    tr.innerHTML=`<td>#${{e.s}}</td><td>${{e.d}}</td><td>${{ball}}</td><td>${{chips}}</td>
      <td><span class="dist-badge" style="background:${{hx(dcol,.15)}};color:${{dcol}}">${{dtxt}}</span></td>`;
    tbody.appendChild(tr);
  }});
}}
</script>
</body>
</html>"""

with open(OUT_PATH, "w", encoding="utf-8") as f:
    f.write(HTML)
print(f"\nWritten: {OUT_PATH} ({len(HTML):,} bytes)")
