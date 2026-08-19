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
import psycopg2, json, collections, math, os

DB_URL  = os.environ["DATABASE_URL"]
OUT_PATH = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto\public\pos_predict.html"

BT_DRAWS    = 1000
CMP_WINDOW  = 200
WINDOWS     = [0]   # all-time only
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
    {"key": "freq_k1",      "label": "Freq K=1",            "k": 1},
    {"key": "freq_k2",      "label": "Freq K=2 (baseline)", "k": 2},
    {"key": "freq_k3",      "label": "Freq K=3",            "k": 3},
    {"key": "recency_k1",   "label": "Recency K=1",         "k": 1},
    {"key": "recency_k2",   "label": "Recency K=2",         "k": 2},
    {"key": "recency_k3",   "label": "Recency K=3",         "k": 3},
    {"key": "overdue_k2",   "label": "Overdue K=2",         "k": 2},
    {"key": "overdue_k3",   "label": "Overdue K=3",         "k": 3},
    {"key": "adaptive",     "label": "Adaptive K (rec.)",   "k": None},
    {"key": "adb",          "label": "ABD (prox+drift)",    "k": None},
    {"key": "markov2_k1",   "label": "Markov-2 K=1",        "k": 1},
    {"key": "markov2_k2",   "label": "Markov-2 K=2",        "k": 2},
    {"key": "markov2_k3",   "label": "Markov-2 K=3",        "k": 3},
    {"key": "transform_k1", "label": "Transform K=1 (x=43)","k": 1},
    {"key": "transform_k2", "label": "Transform K=2 (x=43)","k": 2},
    {"key": "transform_k3", "label": "Transform K=3 (x=43)","k": 3},
]

def adaptive_k(pos_idx):
    if pos_idx in [0, 5]: return 2   # Pos1, Pos6 — concentrated, K=2
    if pos_idx == 2:       return 1   # Pos3 — single pick
    return 3                           # Pos2, Pos4, Pos5

# ── Prediction functions ───────────────────────────────────────────────────────
def _transform_formulas(x=43):
    """
    Enumerate candidate formulas of the form f(v) using variable x=43.
    Returns list of (label, func) where func(v_prev) -> predicted_next.
    Operations: +, -, *, / with x and its fractions.
    """
    F = []
    # ── Direct x-based ────────────────────────────────────────────────────────
    F.append(('43-v',        lambda v, x=x: x - v))          # mirror
    F.append(('v+43',        lambda v, x=x: v + x))
    F.append(('v-43',        lambda v, x=x: v - x))
    F.append(('v*2-43',      lambda v, x=x: 2*v - x))
    F.append(('43*2-v',      lambda v, x=x: 2*x - v))
    F.append(('(v+43)//2',   lambda v, x=x: (v + x) // 2))
    F.append(('v+(43-v)//2', lambda v, x=x: v + (x - v) // 2))
    F.append(('v+(43-v)//3', lambda v, x=x: v + (x - v) // 3))
    # ── v ± round(43/n) for n = 1..15 ─────────────────────────────────────────
    for n in range(1, 16):
        r = round(x / n)
        if r == 0: continue
        F.append((f'v+43/{n}', lambda v, r=r: v + r))
        F.append((f'v-43/{n}', lambda v, r=r: v - r))
    # ── v ± (43 % n) ──────────────────────────────────────────────────────────
    for n in range(2, 12):
        r = x % n
        if r == 0: continue
        F.append((f'v+43%{n}', lambda v, r=r: v + r))
        F.append((f'v-43%{n}', lambda v, r=r: v - r))
    # ── v * (43/43) family ────────────────────────────────────────────────────
    F.append(('v*43//v',     lambda v, x=x: x if v != 0 else v))   # always 43
    F.append(('v//43*43',    lambda v, x=x: (v // x) * x or v))
    return F

_TRANSFORM_F = _transform_formulas()  # build once at module load

def predict_transform(history, pos_idx, k):
    """
    Formula-transform predictor: scores each formula f(v_prev)->v_curr
    across history, then applies top-weighted formulas to latest value.
    """
    if len(history) < 5:
        return predict_freq(history, pos_idx, k)

    hits = [0] * len(_TRANSFORM_F)
    for i in range(1, len(history)):
        v_prev = history[i-1]["n"][pos_idx]
        v_curr = history[i]["n"][pos_idx]
        for fi, (_, fn) in enumerate(_TRANSFORM_F):
            try:
                if fn(v_prev) == v_curr:
                    hits[fi] += 1
            except Exception:
                pass

    v_last = history[-1]["n"][pos_idx]
    scores = collections.Counter()
    for fi, (_, fn) in enumerate(_TRANSFORM_F):
        if hits[fi] == 0:
            continue
        try:
            candidate = fn(v_last)
            if 1 <= candidate <= 43:
                scores[candidate] += hits[fi]
        except Exception:
            pass

    if not scores:
        return predict_freq(history, pos_idx, k)
    return [n for n, _ in scores.most_common(k)]

def predict_markov2(history, pos_idx, k):
    """
    Order-2 Markov chain: predict next value given last two values at pos_idx.
    Falls back to order-1, then frequency if state unseen.
    """
    if len(history) < 3:
        return predict_freq(history, pos_idx, k)

    # Build order-2 transition table: (v_{t-2}, v_{t-1}) -> Counter(v_t)
    trans2 = {}
    trans1 = {}
    for i in range(1, len(history)):
        p1 = history[i-1]["n"][pos_idx]
        c  = history[i]["n"][pos_idx]
        if p1 not in trans1:
            trans1[p1] = collections.Counter()
        trans1[p1][c] += 1
        if i >= 2:
            p2 = history[i-2]["n"][pos_idx]
            key2 = (p2, p1)
            if key2 not in trans2:
                trans2[key2] = collections.Counter()
            trans2[key2][c] += 1

    # Current state
    prev2 = history[-2]["n"][pos_idx]
    prev1 = history[-1]["n"][pos_idx]
    key2  = (prev2, prev1)

    if key2 in trans2 and trans2[key2]:
        return [n for n, _ in trans2[key2].most_common(k)]
    if prev1 in trans1 and trans1[prev1]:     # order-1 fallback
        return [n for n, _ in trans1[prev1].most_common(k)]
    return predict_freq(history, pos_idx, k)  # frequency fallback
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
    if   strategy_key == "freq_k1":    return predict_freq(history,     pos_idx, 1)
    elif strategy_key == "freq_k2":    return predict_freq(history,     pos_idx, 2)
    elif strategy_key == "freq_k3":    return predict_freq(history,     pos_idx, 3)
    elif strategy_key == "recency_k1": return predict_recency(history,  pos_idx, 1)
    elif strategy_key == "recency_k2": return predict_recency(history,  pos_idx, 2)
    elif strategy_key == "recency_k3": return predict_recency(history,  pos_idx, 3)
    elif strategy_key == "overdue_k2": return predict_overdue(history,  pos_idx, 2)
    elif strategy_key == "overdue_k3": return predict_overdue(history,  pos_idx, 3)
    elif strategy_key == "adaptive":   return predict_recency(history,  pos_idx, adaptive_k(pos_idx))
    elif strategy_key == "adb":        return predict_adb(history,      pos_idx, adaptive_k(pos_idx), drift)
    elif strategy_key == "markov2_k1":  return predict_markov2(history,   pos_idx, 1)
    elif strategy_key == "markov2_k2":  return predict_markov2(history,   pos_idx, 2)
    elif strategy_key == "markov2_k3":  return predict_markov2(history,   pos_idx, 3)
    elif strategy_key == "transform_k1":return predict_transform(history, pos_idx, 1)
    elif strategy_key == "transform_k2":return predict_transform(history, pos_idx, 2)
    elif strategy_key == "transform_k3":return predict_transform(history, pos_idx, 3)
    return predict_freq(history, pos_idx, 2)

# ── Fetch draws ────────────────────────────────────────────────────────────────
print("Fetching draws...")
conn = psycopg2.connect(DB_URL)
cur  = conn.cursor()
cur.execute("SELECT draw_serial, draw_date, num1,num2,num3,num4,num5,num6, bonus FROM loto6_results ORDER BY draw_serial")
rows = cur.fetchall()
conn.close()

draws = [{"s": r[0], "d": str(r[1])[:10] if r[1] else "",
          "n": sorted([r[2],r[3],r[4],r[5],r[6],r[7]]),
          "b": r[8]} for r in rows]
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
    bt      = []
    total_h = 0

    for i in range(test_start, T):
        actual = draws[i]["n"][pos_idx]
        train  = draws[:i]
        if len(train) < 5:
            continue
        d_val    = final_drifts[pos_idx] if best_key == "adb" else 0.0
        pred     = predict(best_key, train, pos_idx, d_val)
        hit      = actual in pred
        min_dist = min(abs(actual - p) for p in pred) if pred else 99
        if hit: total_h += 1
        bt.append({"s": draws[i]["s"], "d": draws[i]["d"],
                   "v": actual, "pr": pred, "hit": hit, "md": min_dist})

    d_val   = final_drifts[pos_idx] if best_key == "adb" else 0.0
    current = predict(best_key, draws, pos_idx, d_val)
    tot     = len(bt)
    hr      = total_h / tot if tot else 0
    k       = cmp_results[best_key][pos_idx]["k"]
    rand    = k / 43
    lift    = hr / rand if rand else 0
    tol     = {str(t): sum(1 for e in bt if e["md"] <= t) for t in [0,1,2,3]}
    stats   = {"hitRate": round(hr,4), "rand": round(rand,4),
               "lift": round(lift,4), "hits": total_h, "total": tot,
               "k": k, "tol": tol}

    freq_all = [0]*43
    for d in draws:
        freq_all[d["n"][pos_idx]-1] += 1
    history = [{"s": d["s"], "v": d["n"][pos_idx]} for d in draws[-30:]]

    return {"current": current, "stats": stats,
            "bt": list(reversed(bt))[:120],
            "freqAll": freq_all, "history": history,
            "drift": final_drifts[pos_idx]}

POS_DATA = [compute_detail(pi, best_strategy[pi]) for pi in range(6)]

# ── Combined backtest — all K picks per position ───────────────────────────────
# Pos1,2,5,6 → K=2 picks each; Pos3,4 → K=3 picks each  = 14 candidates total
print("\nBuilding combined combo backtest (all-K per position)...")
combo_bt    = []
match_dist  = [0] * 7   # 0..6 matches

for i in range(test_start, T):
    actual = draws[i]["n"]
    train  = draws[:i]
    if len(train) < 5:
        continue
    combo_by_pos = []
    for pos_idx in range(6):
        bk    = best_strategy[pos_idx]
        d_val = final_drifts[pos_idx] if bk == "adb" else 0.0
        pred  = predict(bk, train, pos_idx, d_val)
        combo_by_pos.append(pred)   # all K picks
    all_picks = list(dict.fromkeys(n for picks in combo_by_pos for n in picks))  # flat, deduped
    matches = len(set(all_picks) & set(actual))
    match_dist[min(matches, 6)] += 1
    combo_bt.append({"s": draws[i]["s"], "d": draws[i]["d"],
                     "actual": actual, "byPos": combo_by_pos,
                     "picks": all_picks, "matches": matches})

# Current prediction — all K per position, using all draws
combo_now_by_pos = []
for pos_idx in range(6):
    bk    = best_strategy[pos_idx]
    d_val = final_drifts[pos_idx] if bk == "adb" else 0.0
    pred  = predict(bk, draws, pos_idx, d_val)
    combo_now_by_pos.append(pred)
combo_now_flat = list(dict.fromkeys(n for picks in combo_now_by_pos for n in picks))

total_combo   = len(combo_bt)
avg_matches   = sum(k * match_dist[k] for k in range(7)) / total_combo if total_combo else 0
n_picks       = sum(len(p) for p in combo_now_by_pos)
rand_expected = n_picks * 6 / 43   # expected for picking n_picks from 43 vs lottery 6

print(f"  Picks per ticket: {n_picks}  (unique: {len(combo_now_flat)})")
print(f"  Avg matches: {avg_matches:.3f}  (random baseline: {rand_expected:.3f})")
print(f"  Match dist: {match_dist}")
print(f"  Combo now by pos: {combo_now_by_pos}")

# ── Bonus prediction ───────────────────────────────────────────────────────────
# For each draw i, look at draw[i-1].bonus → track which numbers appeared in draw[i]
# Given the last bonus number, predict which numbers are most likely next draw
print("\nBuilding bonus prediction...")

BONUS_K = 6

def predict_bonus(history, bonus_val, k=BONUS_K):
    """Top-k numbers that appeared most often after bonus_val."""
    freq = collections.Counter()
    for i in range(1, len(history)):
        if history[i-1]["b"] == bonus_val:
            for n in history[i]["n"]:
                freq[n] += 1
    if not freq:
        # No data for this bonus → fallback to overall frequency
        for d in history:
            for n in d["n"]:
                freq[n] += 1
    return [n for n, _ in freq.most_common(k)]

# All-time conditional frequency table: bonus_freq_all[b][n] = count
bonus_freq_all = {}
for i in range(1, T):
    b = draws[i-1]["b"]
    if b not in bonus_freq_all:
        bonus_freq_all[b] = [0] * 44   # index 0 unused, 1..43 are numbers
    for n in draws[i]["n"]:
        bonus_freq_all[b][n] += 1

# Walk-forward backtest
bonus_bt       = []
bonus_match_dist = [0] * 7
for i in range(test_start, T):
    train       = draws[:i]
    actual      = draws[i]["n"]
    last_bonus  = draws[i-1]["b"]
    if len(train) < 5:
        continue
    pred    = predict_bonus(train, last_bonus, BONUS_K)
    matches = len(set(pred) & set(actual))
    bonus_match_dist[min(matches, 6)] += 1
    bonus_bt.append({"s": draws[i]["s"], "d": draws[i]["d"],
                     "actual": actual, "bonus": last_bonus,
                     "pred": pred, "matches": matches})

bonus_total = len(bonus_bt)
bonus_avg   = sum(k * bonus_match_dist[k] for k in range(7)) / bonus_total if bonus_total else 0
bonus_rand  = BONUS_K * 6 / 43

# Current prediction using the very last bonus
last_bonus_val      = draws[-1]["b"]
bonus_current_pred  = predict_bonus(draws, last_bonus_val, BONUS_K)

# Frequency list by bonus for the heatmap display: {b_str: [freq_1..freq_43]}
bonus_freq_list = {}
for b in range(1, 44):
    if b in bonus_freq_all:
        bonus_freq_list[str(b)] = bonus_freq_all[b][1:]  # drop index-0 placeholder
    else:
        bonus_freq_list[str(b)] = [0] * 43

print(f"  Last bonus: {last_bonus_val}  Current pred: {bonus_current_pred}")
print(f"  Avg matches: {bonus_avg:.3f}  (random baseline: {bonus_rand:.3f})")
print(f"  Match dist: {bonus_match_dist}")

# ── Serialize ──────────────────────────────────────────────────────────────────
DATA = {
    "strategies":    STRATEGIES,
    "posMeta":       POS_META,
    "posData":       POS_DATA,
    "cmp":           cmp_results,
    "bestStrategy":  best_strategy,
    "finalDrifts":   final_drifts,
    "totalDraws":    T,
    "btDraws":       BT_DRAWS,
    "cmpWindow":     CMP_WINDOW,
    "latestSerial":  draws[-1]["s"],
    "latestDate":    draws[-1]["d"],
    "comboNowByPos": combo_now_by_pos,
    "comboNowFlat":  combo_now_flat,
    "comboBt":       list(reversed(combo_bt))[:200],
    "matchDist":     match_dist,
    "avgMatches":    round(avg_matches, 4),
    "randExpected":  round(rand_expected, 4),
    "comboTotal":    total_combo,
    "nPicks":        n_picks,
    "bonusPred": {
        "lastBonus":   last_bonus_val,
        "current":     bonus_current_pred,
        "bt":          list(reversed(bonus_bt))[:200],
        "matchDist":   bonus_match_dist,
        "avgMatches":  round(bonus_avg, 4),
        "randExpected":round(bonus_rand, 4),
        "total":       bonus_total,
        "k":           BONUS_K,
        "freqByBonus": bonus_freq_list,
    },
}
DATA_JSON = json.dumps(DATA, separators=(",",":"))
print(f"\nJSON size: {len(DATA_JSON):,} bytes")

# ── HTML ────────────────────────────────────────────────────────────────────────
NAV_HTML = """<script src="/site-nav.js"></script>"""

HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Position Prediction — Loto 6</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:system-ui,sans-serif;background:#0f172a;color:#e2e8f0;min-height:100vh;padding-top:52px}}
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
/* match bars */
.match-bars{{display:flex;gap:6px;align-items:flex-end;height:120px;margin-bottom:8px}}
.match-bar-col{{display:flex;flex-direction:column;align-items:center;gap:4px;flex:1}}
.match-bar{{width:100%;border-radius:4px 4px 0 0;min-height:4px;transition:height .4s}}
.match-bar-lbl{{font-size:.7rem;color:#94a3b8}}
.match-bar-cnt{{font-size:.72rem;font-weight:700}}
/* combo balls row */
.combo-row{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:20px}}
.c-ball{{width:52px;height:52px;border-radius:50%;display:flex;flex-direction:column;align-items:center;justify-content:center;font-size:1.1rem;font-weight:800;color:#fff}}
.c-ball-lbl{{font-size:.7rem;color:#94a3b8;margin-top:3px;text-align:center}}
/* combo bt table */
.act-ball{{display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;border-radius:50%;font-size:.75rem;font-weight:700}}
.act-ball.hit{{background:#14532d;color:#4ade80;border:2px solid #22c55e}}
.act-ball.miss{{background:#1e293b;color:#64748b}}
.pred-ball{{display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;border-radius:50%;font-size:.75rem;font-weight:700}}
.pred-ball.hit{{background:#14532d;color:#4ade80;border:2px solid #22c55e}}
.pred-ball.miss{{background:#1e293b;color:#475569}}
.match-badge{{display:inline-flex;align-items:center;justify-content:center;padding:2px 8px;border-radius:6px;font-size:.75rem;font-weight:700}}
@media(max-width:640px){{.cmp-strip{{grid-template-columns:repeat(3,1fr)}}.pos-tab{{padding:8px 12px;font-size:.78rem}}}}
</style>
</head>
<body>
{NAV_HTML}
<main>
  <h1>📊 Position Prediction</h1>
  <p class="subtitle">8 strategies compared · {BT_DRAWS}-draw walk-forward backtest · all-time history · ABD = Gaussian proximity + adaptive drift correction</p>

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
const TAB_COLORS=['#6366f1','#3b82f6','#14b8a6','#22c55e','#f59e0b','#ef4444','#a855f7','#e879f9'];
function activatePos(pi){{
  document.querySelectorAll('.pos-tab').forEach((t,i)=>{{
    t.classList.toggle('active',i===pi);
    const col=TAB_COLORS[i]||'#a855f7';
    t.style.borderTopColor=i===pi?col:'transparent';
    t.style.color=i===pi?col:'';
  }});
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
      <div class="sec-title">Pick Distance from Actual — last 100 draws</div>
      <div id="dc-${{pi}}" style="width:100%;overflow:hidden;margin-bottom:6px"></div>
      <div style="display:flex;gap:16px;font-size:.7rem;margin-bottom:6px">
        <span style="color:#38bdf8">— Pick 1</span>
        <span style="color:#f59e0b;border-bottom:2px dashed #f59e0b;line-height:1">— Pick 2</span>
        <span style="color:#22c55e">● Exact hit</span>
      </div>
      <div class="stats-row" id="dcs-${{pi}}"></div>
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
  renderPos(pi);
}});

function renderPos(pi){{
  const pm=D.posMeta[pi],pd=D.posData[pi],bk=D.bestStrategy[pi];
  const ps=new Set(pd.current||[]),st=pd.stats||{{}};

  // (no window buttons — all-time only)
  // Picks
  const picks=pd.current||[];
  document.getElementById(`pk-${{pi}}`).innerHTML=
    picks.map((n,i)=>`<div style="text-align:center">
      <div class="pick-ball" style="background:${{hx(pm.color,.7+i*.1)}}">${{n}}</div>
      <div class="pick-lbl">Pick ${{i+1}}</div></div>`).join('')+
    `<span style="color:#64748b;font-size:.82rem;margin-left:10px">draw #${{D.latestSerial+1}}<br>All-time history</span>`;

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

  // Distance chart — pick 1 and pick 2 distance from actual, last 100 draws
  (function(){{
    const bte=(pd.bt||[]).slice(0,100).reverse(); // chronological, last 100
    if(!bte.length) return;
    const d1=bte.map(e=>Math.abs(((e.pr||[])[0]||0)-e.v));
    const d2=bte.map(e=>e.pr&&e.pr[1]!=null?Math.abs(e.pr[1]-e.v):null);
    const hasD2=d2.some(x=>x!=null);
    const W=1000,H=88,maxD=Math.max(...d1,...d2.filter(x=>x!=null),5);
    const n=bte.length;
    const cx=(i)=>Math.round(i/(n-1||1)*W);
    const cy=(d)=>Math.round(H-(d/maxD)*H);
    // Pick 1 line (solid blue)
    let segs1='';
    for(let i=1;i<n;i++){{
      segs1+=`<line x1="${{cx(i-1)}}" y1="${{cy(d1[i-1])}}" x2="${{cx(i)}}" y2="${{cy(d1[i])}}" stroke="#38bdf8" stroke-width="2" stroke-linecap="round"/>`;
    }}
    // Pick 2 line (dashed amber)
    let segs2='';
    if(hasD2){{
      for(let i=1;i<n;i++){{
        if(d2[i]!=null&&d2[i-1]!=null){{
          segs2+=`<line x1="${{cx(i-1)}}" y1="${{cy(d2[i-1])}}" x2="${{cx(i)}}" y2="${{cy(d2[i])}}" stroke="#f59e0b" stroke-width="1.5" stroke-dasharray="5,3" stroke-linecap="round"/>`;
        }}
      }}
    }}
    // Exact hit dots (where d1=0 or d2=0)
    const dots=bte.map((_,i)=>{{
      const hit1=d1[i]===0,hit2=d2[i]===0;
      return (hit1?`<circle cx="${{cx(i)}}" cy="${{H}}" r="4" fill="#22c55e"/>`:'')
            +(hit2&&!hit1?`<circle cx="${{cx(i)}}" cy="${{H}}" r="3" fill="#22c55e88"/>`:``);
    }}).join('');
    document.getElementById(`dc-${{pi}}`).innerHTML=
      `<svg viewBox="0 0 ${{W}} ${{H+4}}" width="100%" height="90px" preserveAspectRatio="none" style="display:block">
        <line x1="0" y1="${{H}}" x2="${{W}}" y2="${{H}}" stroke="#22c55e22" stroke-width="1"/>
        <line x1="0" y1="${{cy(2)}}" x2="${{W}}" y2="${{cy(2)}}" stroke="#38bdf811" stroke-width="1" stroke-dasharray="4,4"/>
        ${{segs2}}${{segs1}}${{dots}}
      </svg>`;
    // Stats comparison
    const avgD1=(d1.reduce((a,b)=>a+b,0)/n);
    const avgD2=hasD2?(d2.filter(x=>x!=null).reduce((a,b)=>a+b,0)/d2.filter(x=>x!=null).length):null;
    const ex1=d1.filter(d=>d===0).length, ex2=d2.filter(d=>d===0).length;
    const w2_1=d1.filter(d=>d<=2).length, w2_2=d2.filter(d=>d!=null&&d<=2).length;
    const p1wins=bte.filter((_,i)=>d2[i]!=null&&d1[i]<d2[i]).length;
    const p2wins=bte.filter((_,i)=>d2[i]!=null&&d2[i]<d1[i]).length;
    document.getElementById(`dcs-${{pi}}`).innerHTML=`
      <div class="stat-box"><div class="sv" style="color:#38bdf8">${{avgD1.toFixed(1)}}</div><div class="sl">Pick 1 avg dist</div></div>
      ${{hasD2?`<div class="stat-box"><div class="sv" style="color:#f59e0b">${{avgD2.toFixed(1)}}</div><div class="sl">Pick 2 avg dist</div></div>`:''}}`+
      `<div class="stat-box"><div class="sv" style="color:#22c55e">${{ex1}} / ${{n}}</div><div class="sl">Pick 1 exact</div></div>
      ${{hasD2?`<div class="stat-box"><div class="sv" style="color:#22c55e">${{ex2}} / ${{n}}</div><div class="sl">Pick 2 exact</div></div>`:''}}`+
      `<div class="stat-box"><div class="sv" style="color:#38bdf8">${{w2_1}} / ${{n}}</div><div class="sl">Pick 1 ≤±2</div></div>
      ${{hasD2?`<div class="stat-box"><div class="sv" style="color:#f59e0b">${{w2_2}} / ${{n}}</div><div class="sl">Pick 2 ≤±2</div></div>`:''}}`+
      `${{hasD2?`<div class="stat-box"><div class="sv" style="color:#f1f5f9">${{p1wins}}/${{p2wins}}</div><div class="sl">P1/P2 closer</div></div>`:''}}`
      ;
  }})();

  // Stats
  document.getElementById(`st-${{pi}}`).innerHTML=`
    <div class="stat-box"><div class="sv" style="color:#f1f5f9">${{(st.hitRate*100||0).toFixed(1)}}%</div><div class="sl">Exact hit (K=${{st.k||2}})</div></div>
    <div class="stat-box"><div class="sv" style="color:#f1f5f9">${{(st.rand*100||0).toFixed(1)}}%</div><div class="sl">Random baseline</div></div>
    <div class="stat-box"><div class="sv" style="color:#f1f5f9">${{(st.lift||0).toFixed(3)}}×</div><div class="sl">Lift</div></div>
    <div class="stat-box"><div class="sv" style="color:#4ade80">${{(st.tol&&st.tol['1']||0)}} / ${{st.total||0}}</div><div class="sl">Within ±1</div></div>
    <div class="stat-box"><div class="sv" style="color:#38bdf8">${{(st.tol&&st.tol['2']||0)}} / ${{st.total||0}}</div><div class="sl">Within ±2</div></div>`;

  // BT table
  const tbody=document.getElementById(`bt-${{pi}}`); tbody.innerHTML='';
  (pd.bt||[]).slice(0,100).forEach(e=>{{
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

// ── Combined tab ──────────────────────────────────────────────────────────────
(function(){{
  const tab=document.createElement('div');
  tab.className='pos-tab'; tab.textContent='Combined';
  tab.onclick=()=>activatePos(6); tabsEl.appendChild(tab);
  const PC=D.posMeta.map(m=>m.color);

  const panel=document.createElement('div');
  panel.className='pos-panel';
  panel.innerHTML=`
    <div class="sec">
      <div class="sec-title" style="color:#a855f7">Combined — all K picks per position (${{D.nPicks}} candidates)</div>
      <div class="info-row">
        <span class="badge" style="background:#1e0a3c;color:#c084fc;border:1px solid #c084fc55">Avg matches: ${{D.avgMatches.toFixed(3)}} / draw</span>
        <span class="badge" style="background:#1e293b;color:#64748b;border:1px solid #33415533">Random (${{D.nPicks}} picks): ${{D.randExpected.toFixed(3)}}</span>
        <span class="badge ${{D.avgMatches>D.randExpected?'bg':'ba'}}">${{(D.avgMatches/D.randExpected).toFixed(3)}}x lift</span>
      </div>
    </div>
    <div class="sec">
      <div class="sec-title">Candidates for Draw #${{D.latestSerial+1}}</div>
      <div id="comboNow"></div>
    </div>
    <div class="sec">
      <div class="sec-title">Match Count Distribution — last ${{D.comboTotal}} draws</div>
      <div class="match-bars" id="matchBars"></div>
      <div style="display:flex;gap:6px;justify-content:center;margin-bottom:4px">
        ${{[0,1,2,3,4,5,6].map(k=>`<div style="flex:1;text-align:center;font-size:.7rem;color:#64748b">${{k}} match</div>`).join('')}}
      </div>
    </div>
    <div class="sec">
      <div class="sec-title">Backtest Stats</div>
      <div class="stats-row" id="comboStats"></div>
    </div>
    <div class="sec">
      <div class="sec-title">Recent Draws</div>
      <div class="bt-wrap"><table class="bt-tbl">
        <thead><tr><th>Draw</th><th>Date</th><th>Candidates (by pos)</th><th>Actual</th><th>Matches</th></tr></thead>
        <tbody id="comboBt"></tbody>
      </table></div>
    </div>`;
  panelsEl.appendChild(panel);

  // Candidates grouped by position
  const nowEl=document.getElementById('comboNow');
  D.comboNowByPos.forEach((picks,pi)=>{{
    const row=document.createElement('div');
    row.style.cssText='display:flex;align-items:center;gap:8px;margin-bottom:6px';
    row.innerHTML=`<span style="font-size:.75rem;color:#64748b;width:38px;flex-shrink:0">P${{pi+1}}</span>`+
      picks.map(n=>`<span class="pred-ball hit" style="background:${{hx(PC[pi],.7)}};border:none;width:28px;height:28px">${{n}}</span>`).join('');
    nowEl.appendChild(row);
  }});

  // Match distribution bars
  const maxCnt=Math.max(...D.matchDist,1);
  document.getElementById('matchBars').innerHTML=D.matchDist.map((cnt,k)=>{{
    const pct=(cnt/D.comboTotal*100);
    const ht=Math.max(4,Math.round((cnt/maxCnt)*108));
    const col=k===0?'#334155':k===1?'#1e3a5f':k===2?'#0c2e1f':k===3?'#14532d':k>=4?'#166534':'#134e4a';
    const tcol=k>=2?'#4ade80':'#64748b';
    return `<div class="match-bar-col">
      <div class="match-bar-cnt" style="color:${{tcol}}">${{cnt}}</div>
      <div class="match-bar" style="height:${{ht}}px;background:${{col}}"></div>
      <div class="match-bar-lbl">${{pct.toFixed(1)}}%</div>
    </div>`;
  }}).join('');

  // Stats
  const at2=D.matchDist.slice(2).reduce((a,b)=>a+b,0);
  const at3=D.matchDist.slice(3).reduce((a,b)=>a+b,0);
  document.getElementById('comboStats').innerHTML=`
    <div class="stat-box"><div class="sv" style="color:#c084fc">${{D.avgMatches.toFixed(3)}}</div><div class="sl">Avg matches/draw</div></div>
    <div class="stat-box"><div class="sv" style="color:#64748b">${{D.randExpected.toFixed(3)}}</div><div class="sl">Random (${{D.nPicks}} picks)</div></div>
    <div class="stat-box"><div class="sv" style="color:#f1f5f9">${{(D.avgMatches/D.randExpected).toFixed(3)}}x</div><div class="sl">Lift</div></div>
    <div class="stat-box"><div class="sv" style="color:#4ade80">${{at2}} / ${{D.comboTotal}}</div><div class="sl">≥2 matches</div></div>
    <div class="stat-box"><div class="sv" style="color:#22c55e">${{at3}} / ${{D.comboTotal}}</div><div class="sl">≥3 matches</div></div>`;

  // BT rows
  const tbody=document.getElementById('comboBt');
  D.comboBt.forEach(e=>{{
    const mc=e.matches;
    const tr=document.createElement('tr');
    const mcol=mc===0?'#64748b':mc===1?'#38bdf8':mc===2?'#f59e0b':mc>=3?'#22c55e':'#64748b';
    // Show by-position candidates
    const predCols=(e.byPos||[e.picks]).map((picks,pi)=>{{
      const col=PC[pi]||'#6366f1';
      return picks.map(n=>{{
        const isHit=e.actual.includes(n);
        return `<span class="pred-ball" style="background:${{hx(col,isHit?.8:.3)}};border:none;width:22px;height:22px;font-size:.68rem;${{isHit?'':'opacity:.45'}}">${{n}}</span>`;
      }}).join('');
    }}).join('<span style="color:#334155;padding:0 2px">|</span>');
    const actBalls=e.actual.map(n=>{{
      const isHit=(e.picks||e.combo||[]).includes(n);
      return `<span class="act-ball ${{isHit?'hit':'miss'}}">${{n}}</span>`;
    }}).join(' ');
    tr.innerHTML=`<td>#${{e.s}}</td><td>${{e.d}}</td><td style="white-space:nowrap">${{predCols}}</td><td>${{actBalls}}</td>
      <td><span class="match-badge" style="background:${{hx(mcol,.15)}};color:${{mcol}}">${{mc}} hit${{mc!==1?'s':''}}</span></td>`;
    tbody.appendChild(tr);
  }});
}})();

// ── Bonus tab ─────────────────────────────────────────────────────────────────
(function(){{
  const BP = D.bonusPred;
  const tab = document.createElement('div');
  tab.className = 'pos-tab'; tab.textContent = '🎯 Bonus';
  tab.onclick = () => activatePos(7); tabsEl.appendChild(tab);

  const panel = document.createElement('div');
  panel.className = 'pos-panel';
  panel.innerHTML = `
    <div class="sec">
      <div class="sec-title" style="color:#e879f9">Bonus → Next Draw Prediction</div>
      <div class="info-row">
        <span class="badge" style="background:#2d0a3c;color:#e879f9;border:1px solid #e879f955">
          Last bonus: <strong>#${{BP.lastBonus}}</strong>
        </span>
        <span class="badge ${{BP.avgMatches>BP.randExpected?'bg':'ba'}}">
          Avg matches: ${{BP.avgMatches.toFixed(3)}} / draw
        </span>
        <span class="badge" style="background:#1e293b;color:#64748b;border:1px solid #33415533">
          Random (${{BP.k}} picks): ${{BP.randExpected.toFixed(3)}}
        </span>
        <span class="badge ${{BP.avgMatches>BP.randExpected?'bg':'ba'}}">${{(BP.avgMatches/BP.randExpected).toFixed(3)}}x lift</span>
      </div>
      <p style="font-size:.75rem;color:#475569;margin-top:6px">
        Conditional frequency: numbers that appeared most often in the draw after each bonus value was drawn.
        Walk-forward backtest predicts top ${{BP.k}} numbers using only history before each draw.
      </p>
    </div>
    <div class="sec">
      <div class="sec-title">Predicted Numbers for Draw #${{D.latestSerial+1}}</div>
      <p style="font-size:.75rem;color:#64748b;margin-bottom:10px">
        Based on last draw's bonus number: <strong style="color:#e879f9">${{BP.lastBonus}}</strong>
      </p>
      <div class="picks-row" id="bpPicks"></div>
    </div>
    <div class="sec">
      <div class="sec-title">Match Distribution — last ${{BP.total}} draws</div>
      <div class="match-bars" id="bpMatchBars"></div>
      <div style="display:flex;gap:6px;justify-content:center;margin-bottom:4px">
        ${{[0,1,2,3,4,5,6].map(k=>`<div style="flex:1;text-align:center;font-size:.7rem;color:#64748b">${{k}} match</div>`).join('')}}
      </div>
    </div>
    <div class="sec">
      <div class="sec-title">Backtest Stats</div>
      <div class="stats-row" id="bpStats"></div>
    </div>
    <div class="sec">
      <div class="sec-title">Frequency Heatmap — numbers after bonus <span id="bpHeatLbl" style="color:#e879f9"></span></div>
      <p style="font-size:.72rem;color:#64748b;margin-bottom:8px">Click a bonus ball to see which numbers followed it most often.</p>
      <div style="display:flex;flex-wrap:wrap;gap:4px;margin-bottom:10px" id="bpBonusSel"></div>
      <div class="freq-grid" id="bpHeatGrid"></div>
    </div>
    <div class="sec">
      <div class="sec-title">Recent Draws</div>
      <div class="bt-wrap"><table class="bt-tbl">
        <thead><tr><th>Draw</th><th>Date</th><th>Prev Bonus</th><th>Predicted (top ${{BP.k}})</th><th>Actual</th><th>Matches</th></tr></thead>
        <tbody id="bpBt"></tbody>
      </table></div>
    </div>`;
  panelsEl.appendChild(panel);

  // Current predictions
  document.getElementById('bpPicks').innerHTML =
    BP.current.map((n,i) =>
      `<div style="text-align:center">
        <div class="pick-ball" style="background:${{hx('#e879f9',.5+i*.08)}}">${{n}}</div>
        <div class="pick-lbl">Pick ${{i+1}}</div>
      </div>`
    ).join('') +
    `<span style="color:#64748b;font-size:.82rem;margin-left:10px">draw #${{D.latestSerial+1}}<br>Bonus was ${{BP.lastBonus}}</span>`;

  // Match bars
  const maxBM = Math.max(...BP.matchDist, 1);
  document.getElementById('bpMatchBars').innerHTML = BP.matchDist.map((cnt,k) => {{
    const pct = (cnt / BP.total * 100);
    const ht  = Math.max(4, Math.round((cnt / maxBM) * 108));
    const col = k===0?'#334155':k===1?'#1e3a5f':k===2?'#0c2e1f':k===3?'#14532d':k>=4?'#166534':'#134e4a';
    const tcol = k>=2?'#4ade80':'#64748b';
    return `<div class="match-bar-col">
      <div class="match-bar-cnt" style="color:${{tcol}}">${{cnt}}</div>
      <div class="match-bar" style="height:${{ht}}px;background:${{col}}"></div>
      <div class="match-bar-lbl">${{pct.toFixed(1)}}%</div>
    </div>`;
  }}).join('');

  // Stats
  const at2 = BP.matchDist.slice(2).reduce((a,b)=>a+b,0);
  const at3 = BP.matchDist.slice(3).reduce((a,b)=>a+b,0);
  document.getElementById('bpStats').innerHTML = `
    <div class="stat-box"><div class="sv" style="color:#e879f9">${{BP.avgMatches.toFixed(3)}}</div><div class="sl">Avg matches/draw</div></div>
    <div class="stat-box"><div class="sv" style="color:#64748b">${{BP.randExpected.toFixed(3)}}</div><div class="sl">Random (${{BP.k}} picks)</div></div>
    <div class="stat-box"><div class="sv" style="color:#f1f5f9">${{(BP.avgMatches/BP.randExpected).toFixed(3)}}x</div><div class="sl">Lift</div></div>
    <div class="stat-box"><div class="sv" style="color:#4ade80">${{at2}} / ${{BP.total}}</div><div class="sl">≥2 matches</div></div>
    <div class="stat-box"><div class="sv" style="color:#22c55e">${{at3}} / ${{BP.total}}</div><div class="sl">≥3 matches</div></div>`;

  // Heatmap
  function renderHeatmap(b) {{
    document.getElementById('bpHeatLbl').textContent = '#' + b;
    const freqs = BP.freqByBonus[String(b)] || Array(43).fill(0);
    const maxF  = Math.max(...freqs, 1);
    const curSet = new Set(BP.current);
    document.getElementById('bpHeatGrid').innerHTML = freqs.map((cnt,i) => {{
      const n = i + 1;
      const ip = curSet.has(n) && b === BP.lastBonus;
      const bg = hx('#e879f9', 0.06 + 0.74 * (cnt / maxF));
      const bdr = ip ? `border-color:#e879f9;box-shadow:0 0 8px ${{hx('#e879f9',.35)}}` : '';
      return `<div class="freq-cell${{ip?' pick':''}}" style="background:${{bg}};${{bdr}}" title="#${{n}}: appeared ${{cnt}}x after bonus ${{b}}">
        <div class="fc-num">${{n}}</div><div class="fc-cnt">${{cnt}}</div></div>`;
    }}).join('');
  }}

  // Bonus selector balls
  const selEl = document.getElementById('bpBonusSel');
  for (let b = 1; b <= 43; b++) {{
    const btn = document.createElement('div');
    btn.className = 'freq-cell' + (b === BP.lastBonus ? ' pick' : '');
    const isLast = b === BP.lastBonus;
    btn.style.cssText = `background:${{hx('#e879f9', isLast?0.4:0.1)}};cursor:pointer;width:36px;height:36px;${{isLast?'border-color:#e879f9;box-shadow:0 0 8px '+hx('#e879f9',.4):''}}`;
    btn.innerHTML = `<div class="fc-num">${{b}}</div>`;
    btn.title = `Bonus ${{b}}`;
    btn.onclick = () => renderHeatmap(b);
    selEl.appendChild(btn);
  }}
  renderHeatmap(BP.lastBonus);  // default to last bonus

  // BT rows
  const tbody = document.getElementById('bpBt');
  BP.bt.forEach(e => {{
    const mc  = e.matches;
    const tr  = document.createElement('tr');
    const mcol = mc===0?'#64748b':mc===1?'#38bdf8':mc===2?'#f59e0b':mc>=3?'#22c55e':'#64748b';
    const predBalls = e.pred.map(n => {{
      const hit = e.actual.includes(n);
      return `<span class="pred-ball ${{hit?'hit':'miss'}}" style="width:24px;height:24px;font-size:.72rem">${{n}}</span>`;
    }}).join(' ');
    const actBalls = e.actual.map(n => {{
      const hit = e.pred.includes(n);
      return `<span class="act-ball ${{hit?'hit':'miss'}}">${{n}}</span>`;
    }}).join(' ');
    const bBall = `<span class="v-ball" style="background:#2d0a3c;color:#e879f9;border:2px solid #e879f9">${{e.bonus}}</span>`;
    tr.innerHTML = `<td>#${{e.s}}</td><td>${{e.d}}</td><td>${{bBall}}</td>
      <td style="white-space:nowrap">${{predBalls}}</td><td style="white-space:nowrap">${{actBalls}}</td>
      <td><span class="match-badge" style="background:${{hx(mcol,.15)}};color:${{mcol}}">${{mc}} hit${{mc!==1?'s':''}}</span></td>`;
    tbody.appendChild(tr);
  }});
}})();
</script>
</body>
</html>"""

with open(OUT_PATH, "w", encoding="utf-8") as f:
    f.write(HTML)
print(f"\nWritten: {OUT_PATH} ({len(HTML):,} bytes)")
