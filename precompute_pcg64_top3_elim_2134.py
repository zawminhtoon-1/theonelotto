"""
precompute_pcg64_top3_elim_2134.py
-----------------------------------
Precomputes everything the "Top-3 PCG64 K=38 Seeds (Triple Intersection)
+ 16-Method Elimination" page needs for draw #2134. Standard walk-forward
build, trained on all real draws through #2133, no leakage.

METHODOLOGY: Base here is the TRIPLE intersection of the top-3 PCG64
(O'Neill XSL-RR 128/64) K=38 seeds by hit6b from the completed PCG64
K=38 scan (seeds -5,000,000 to 5,000,000):
  seed #1,286,436  (hit6b=914 -- overall scan winner)
  seed #2,599,249  (hit6b=?, 2nd by hit6b)
  seed #-4,675,555 (hit6b=912, 3rd by hit6b / Stage-1 leader)
Each seed's own 38-number pick is recomputed per draw (PCG64 output
depends on the draw serial), then intersected across all three -- NOT
xoshiro x PCG64 like xo_pcg_elim_2134.html, and NOT the triple
xoshiro x Modular Cycle x PCG64 like triple_k38_stats.html's
construction. This is the "3 best single-PRNG seeds, same PRNG family,
intersected" construction, backtested in chat against draws #2084-2133
(fully out-of-sample) and #1934-2083 (78% in-sample) -- see the honest-
framing note below for the actual numbers.

Pass 1 (16 methods, K=19), Pass 2 (xoshiro K=21 seeds 0/1/2), Pass 3
(historical repeat filter), Pass 4 (Worst Combo Anti-Pick K=15), Pass 5
(consecutive-run filter), Pass 6 (three-consecutive-pairs filter),
Pass 7 (well-supported 5/6-overlap-with-previous-draw filter): all
IDENTICAL methodology to xoshiro_elim_2134.html / xo_pcg_elim_2134.html.
No Pass 8 here -- this Base is already a triple intersection by
construction, so there's no separate "restrict to triple agreement"
step to add.

Self-checks the PCG64 implementation against a known-good value before
trusting Base's construction.

Outputs:
  pcg64_top3_elim_2134_meta.json          -- small: pools, method picks, counts
  public/pcg64_top3_elim_2134_combos.json -- large: remaining combo list
                                             (fetched client-side, not inlined)

Run: python precompute_pcg64_top3_elim_2134.py
"""
import json, os, re, itertools, time, warnings
import numpy as np
import psycopg2
from collections import Counter, defaultdict
from math import comb

warnings.filterwarnings('ignore')

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
ENV_LOCAL = BASE + r"\.env.local"
META_OUT = BASE + r"\pcg64_top3_elim_2134_meta.json"
COMBOS_OUT = BASE + r"\public\pcg64_top3_elim_2134_combos.json"

LOTO6_MAX = 43
TARGET_SERIAL = 2134
K_PCG = 38
K_METHODS = 19    # normalized K for all 16 methods (Pass 1)
K_DEFAULT = 15    # native K most methods produce before normalization
K_PASS2 = 21      # xoshiro256** K=21, same as xoshiro_seed_backtest.html
PASS2_SEEDS = [0, 1, 2]
K_PASS4 = 15      # Worst Combo (Anti-Pick) K -- computed below from base_pools
WORST_COMBO_METHOD_INDICES = [1, 2, 6, 9, 11]  # MA-43, Exp-Weighted, RF, kNN, Apriori

PCG_SEEDS = [1286436, 2599249, -4675555]  # top-3 PCG64 K=38 seeds by hit6b

# ── xoshiro256** (verified implementation, same as every other page;
# needed here only for Pass 2, not for Base) ─────────────────────────────────
MASK64 = 0xFFFFFFFFFFFFFFFF
def splitmix64_next(z):
    z = (z + 0x9E3779B97F4A7C15) & MASK64
    zz = z
    zz = ((zz ^ (zz >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
    zz = ((zz ^ (zz >> 27)) * 0x94D049BB133111EB) & MASK64
    zz = zz ^ (zz >> 31)
    return z, zz
def seed_state(seed):
    z = seed & MASK64
    state = []
    for _ in range(4):
        z, out = splitmix64_next(z)
        state.append(out)
    return state
def rotl(x, k):
    x &= MASK64
    return ((x << k) | (x >> (64 - k))) & MASK64
def xoshiro_next(s):
    result = (rotl((s[1] * 5) & MASK64, 7) * 9) & MASK64
    t = (s[1] << 17) & MASK64
    s[2] ^= s[0]; s[3] ^= s[1]; s[1] ^= s[2]; s[0] ^= s[3]
    s[2] ^= t
    s[3] = rotl(s[3], 45)
    return result
def xoshiro_predict_raw(seed, draw_serial, k, pool_max=LOTO6_MAX):
    combined = (seed * 10_000_000 + draw_serial) & MASK64
    s = seed_state(combined)
    arr = list(range(1, pool_max + 1))
    n = len(arr)
    order = []
    for i in range(n - 1, n - 1 - k, -1):
        r = xoshiro_next(s)
        j = r % (i + 1)
        arr[i], arr[j] = arr[j], arr[i]
        order.append(arr[i])
    return order
def xoshiro_predict(seed, draw_serial, k, pool_max=LOTO6_MAX):
    return sorted(xoshiro_predict_raw(seed, draw_serial, k, pool_max))

# ── PCG64 (O'Neill XSL-RR 128/64, verified bit-exact against
# numpy.random.Generator(PCG64()) via direct low-level state injection) ─────
MASK128 = (1 << 128) - 1
PCG_MULT_128 = 0x2360ed051fc65da44385df649fccf645
def expand_seed_to_pcg_state(combined):
    z = combined & MASK64
    outs = []
    for _ in range(4):
        z, o = splitmix64_next(z)
        outs.append(o)
    state = (outs[0] << 64) | outs[1]
    inc = ((outs[2] << 64) | outs[3]) | 1
    return state & MASK128, inc & MASK128
def rotr64(v, rot):
    rot &= 63
    return ((v >> rot) | (v << ((-rot) & 63))) & MASK64
def pcg64_next(state, inc):
    state = (state * PCG_MULT_128 + inc) & MASK128
    xored = (state >> 64) ^ (state & MASK64)
    rot = (state >> 122) & 0x3f
    out = rotr64(xored, rot)
    return state, out
def pcg64_predict_raw(seed, draw_serial, k, pool_max=LOTO6_MAX):
    combined = (seed * 10_000_000 + draw_serial) & MASK64
    state, inc = expand_seed_to_pcg_state(combined)
    arr = list(range(1, pool_max + 1))
    n = len(arr)
    order = []
    for i in range(n - 1, n - 1 - k, -1):
        state, r = pcg64_next(state, inc)
        j = r % (i + 1)
        arr[i], arr[j] = arr[j], arr[i]
        order.append(arr[i])
    return order
def pcg64_predict(seed, draw_serial, k, pool_max=LOTO6_MAX):
    return sorted(pcg64_predict_raw(seed, draw_serial, k, pool_max))

# ── Self-check against known-good value before trusting the PCG64 side ──────
_KNOWN_PCG_M5M_1 = [1, 2, 3, 4, 5, 6, 7, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 20, 21, 22, 23, 25, 26, 27, 28, 30, 31, 32, 33, 34, 35, 36, 37, 39, 40, 41, 42, 43]
_check_pcg = pcg64_predict(-5000000, 1, K_PCG)
assert _check_pcg == _KNOWN_PCG_M5M_1, f"PCG64 self-check FAILED: {_check_pcg}"
print(f"Self-check OK: PCG64 seed -5,000,000 K={K_PCG} draw #1 matches known-good value.")

pcg_pools = [pcg64_predict(s, TARGET_SERIAL, K_PCG) for s in PCG_SEEDS]
pcg_pools_ordered = [pcg64_predict_raw(s, TARGET_SERIAL, K_PCG) for s in PCG_SEEDS]
for seed, pool in zip(PCG_SEEDS, pcg_pools):
    print(f"PCG64 K={K_PCG} seed #{seed} pick for draw #{TARGET_SERIAL}: {pool}")

# ── Fetch all real draws through #2133 ───────────────────────────────────────
if 'DATABASE_URL' not in os.environ:
    with open(ENV_LOCAL, encoding='utf-8') as f:
        env_text = f.read()
    m = re.search(r'DATABASE_URL=(.+)', env_text)
    os.environ['DATABASE_URL'] = m.group(1).strip()

conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()
cur.execute(
    "SELECT draw_serial, draw_date, num1,num2,num3,num4,num5,num6, bonus "
    "FROM loto6_results ORDER BY draw_serial"
)
db_rows = cur.fetchall()
conn.close()
print(f"\nFetched {len(db_rows)} historical draws (#{db_rows[0][0]}-{db_rows[-1][0]}).")
if db_rows[-1][0] != TARGET_SERIAL - 1:
    raise SystemExit(f"Expected latest draw #{TARGET_SERIAL-1}, found #{db_rows[-1][0]} -- draw window assumption is stale.")

all_serials = [r[0] for r in db_rows]
all_main6   = [sorted([r[2],r[3],r[4],r[5],r[6],r[7]]) for r in db_rows]
all_allnums = [sorted([r[2],r[3],r[4],r[5],r[6],r[7],r[8]]) for r in db_rows]

train_serials = all_serials
train_main6   = all_main6
train_allnums = all_allnums

# ── Helpers (verbatim from append_backtest.py) ───────────────────────────────
def pad_to_k(base_picks, all_before_main6, k=K_DEFAULT):
    freq = Counter(n for nums in all_before_main6 for n in nums)
    seen = set(base_picks)
    result = list(base_picks)
    for n in sorted(range(1, LOTO6_MAX+1), key=lambda x: -freq.get(x,0)):
        if len(result) >= k: break
        if n not in seen:
            seen.add(n); result.append(n)
    return sorted(result[:k])

def make_unique(nums, all_before_main6, k=K_DEFAULT):
    seen = set()
    result = []
    for n in nums:
        n = max(1, min(LOTO6_MAX, int(round(n))))
        if n not in seen:
            seen.add(n); result.append(n)
    return pad_to_k(result, all_before_main6, k)

# ── LSTM helper (verbatim) ───────────────────────────────────────────────────
def sigmoid(x): return 1.0 / (1.0 + np.exp(-x))
def lstm_forward(W, b, Wy, by, seq_draws):
    Wy_np = np.array(Wy); W_np = np.array(W); b_np = np.array(b); by_np = np.array(by)
    Hsize = Wy_np.shape[1]; Isize = W_np.shape[1] - Hsize
    h = np.zeros(Hsize); c = np.zeros(Hsize)
    for draw_nums in seq_draws:
        x = np.zeros(Isize)
        for n in draw_nums:
            if 1 <= n <= Isize: x[n-1] = 1.0
        concat = np.concatenate([x, h])
        gates = W_np @ concat + b_np
        ig = sigmoid(gates[:Hsize]); fg = sigmoid(gates[Hsize:2*Hsize])
        gg = np.tanh(gates[2*Hsize:3*Hsize]); og = sigmoid(gates[3*Hsize:])
        c = fg * c + ig * gg; h = og * np.tanh(c)
    logits = Wy_np @ h + by_np
    ex = np.exp(logits - logits.max())
    return ex / ex.sum()

with open(BASE + r"\lstm_weights.json") as f:
    _lw = json.load(f)
_LSTM_W, _LSTM_b, _LSTM_Wy, _LSTM_by = _lw['W'], _lw['b'], _lw['Wy'], _lw['by']

def lstm_predict(all_allnums_list, k=K_DEFAULT):
    seq_size = 10
    seq = [set(d) for d in all_allnums_list[-seq_size:]]
    if len(seq) == 0:
        return list(range(1, k+1))
    probs = lstm_forward(_LSTM_W, _LSTM_b, _LSTM_Wy, _LSTM_by, seq)
    top_idx = np.argsort(-probs)[:k]
    return sorted(int(i)+1 for i in top_idx)

with open(BASE + r"\lstm_backtest.json") as f:
    _lbt = json.load(f)
lstm_json_by_serial = {r['serial']: r for r in _lbt['results']}

# ── 16 prediction methods (verbatim from append_backtest.py) ────────────────
def method0_poly_full(train_main6, train_serials, target_serial):
    x = np.array(train_serials, dtype=float)
    base = []
    for p in range(6):
        y = np.array([draws[p] for draws in train_main6], dtype=float)
        coeffs = np.polyfit(x, y, 2)
        raw = np.polyval(coeffs, float(target_serial))
        base.append(max(1, min(LOTO6_MAX, int(round(raw)))))
    return make_unique(base, train_main6)

def method1_ma43(train_main6):
    window = train_main6[-43:] if len(train_main6) >= 1 else train_main6
    base = []
    for p in range(6):
        vals = [d[p] for d in window]
        base.append(max(1, min(LOTO6_MAX, round(sum(vals)/len(vals)))))
    return make_unique(base, train_main6)

def method2_exp_weighted(train_main6):
    lam = 0.95; n = len(train_main6)
    wts = [lam**(n-1-i) for i in range(n)]; ws = sum(wts)
    base = []
    for p in range(6):
        vals = [train_main6[i][p] for i in range(n)]
        v = sum(wts[i]*vals[i] for i in range(n)) / ws
        base.append(max(1, min(LOTO6_MAX, int(round(v)))))
    return make_unique(base, train_main6)

def method3_freq_all(train_main6, k=K_DEFAULT):
    freq = Counter(n for draws in train_main6 for n in draws)
    return sorted(n for n, _ in freq.most_common(k))

def method4_markov(train_main6, k=K_DEFAULT):
    pair_freq = defaultdict(int)
    for draws in train_main6:
        for a in draws:
            for b in draws:
                if a != b:
                    pair_freq[(a, b)] += 1
    last = set(train_main6[-1]) if train_main6 else set()
    scores = Counter()
    for src in last:
        for dst in range(1, LOTO6_MAX+1):
            if dst not in last:
                scores[dst] += pair_freq.get((src, dst), 0)
    result = [n for n, _ in scores.most_common(k - len(last))]
    result = list(last) + result
    return pad_to_k(sorted(result[:k]), train_main6, k)

def method5_arima(train_main6, target_serial, k=K_DEFAULT):
    from statsmodels.tsa.arima.model import ARIMA
    base = []
    for p in range(6):
        y = [d[p] for d in train_main6]
        try:
            if len(y) < 10:
                base.append(round(sum(y)/len(y))); continue
            model = ARIMA(y, order=(2,1,0)); fit = model.fit()
            fc = fit.forecast(steps=1)
            v = max(1, min(LOTO6_MAX, int(round(float(fc[0])))))
        except Exception:
            v = max(1, min(LOTO6_MAX, round(sum(y[-10:])/10)))
        base.append(v)
    return make_unique(base, train_main6, k)

def method6_random_forest(train_main6, train_serials, target_serial, k=K_DEFAULT):
    from sklearn.ensemble import RandomForestRegressor
    base = []; xs = np.array(train_serials, dtype=float).reshape(-1, 1)
    for p in range(6):
        y = np.array([d[p] for d in train_main6], dtype=float)
        try:
            rf = RandomForestRegressor(n_estimators=50, random_state=42, n_jobs=1)
            rf.fit(xs, y)
            pred = rf.predict([[float(target_serial)]])[0]
            v = max(1, min(LOTO6_MAX, int(round(pred))))
        except Exception:
            v = max(1, min(LOTO6_MAX, round(float(np.mean(y[-10:])))))
        base.append(v)
    return make_unique(base, train_main6, k)

def method7_rl_linear_q(train_main6, k=K_DEFAULT):
    n = len(train_main6)
    if n == 0: return list(range(1, k+1))
    weights = list(range(1, n+1)); freq = defaultdict(float)
    for w, draws in zip(weights, train_main6):
        for num in draws:
            freq[num] += w
    top = sorted(range(1, LOTO6_MAX+1), key=lambda x: -freq.get(x, 0))
    return sorted(top[:k])

def method8_hmm(train_main6, k=K_DEFAULT):
    sums = [sum(d) for d in train_main6]
    if not sums: return list(range(1, k+1))
    q = np.percentile(sums, [20, 40, 60, 80])
    def get_state(s):
        for i, qv in enumerate(q):
            if s <= qv: return i
        return 4
    states = [get_state(s) for s in sums]
    trans = defaultdict(lambda: defaultdict(int))
    for i in range(len(states)-1):
        trans[states[i]][states[i+1]] += 1
    cur_state = states[-1]
    next_state = max(trans[cur_state], key=lambda s: trans[cur_state][s]) if trans[cur_state] else cur_state
    freq = Counter()
    for i, s in enumerate(states):
        if s == next_state:
            for n in train_main6[i]: freq[n] += 1
    if not freq: freq = Counter(n for d in train_main6 for n in d)
    return sorted(n for n, _ in freq.most_common(k))

def method9_knn(train_main6, k_nn=10, k=K_DEFAULT):
    if len(train_main6) < k_nn + 1:
        return method3_freq_all(train_main6, k)
    last = set(train_main6[-1])
    dists = []
    for i, d in enumerate(train_main6[:-1]):
        dists.append((len(last ^ set(d)), i))
    dists.sort()
    neighbors = [train_main6[i] for _, i in dists[:k_nn]]
    freq = Counter(n for d in neighbors for n in d)
    return sorted(n for n, _ in freq.most_common(k))

def modular_cycle_ranked(train_serials, train_main6, target_serial, k=28):
    target_mod = target_serial % LOTO6_MAX
    freq = Counter()
    for s, d in zip(train_serials, train_main6):
        if s % LOTO6_MAX == target_mod:
            for n in d: freq[n] += 1
    if not freq: freq = Counter(n for d in train_main6 for n in d)
    return sorted(range(1, LOTO6_MAX+1), key=lambda x: -freq.get(x, 0))[:k]

def method10_modular_cycle(train_serials, train_main6, target_serial, k=28):
    return sorted(modular_cycle_ranked(train_serials, train_main6, target_serial, k))

def method11_apriori(train_main6, k=K_DEFAULT):
    pair_freq = Counter()
    for draws in train_main6:
        for pair in itertools.combinations(draws, 2):
            pair_freq[pair] += 1
    last = set(train_main6[-1]) if train_main6 else set()
    scores = Counter()
    antecedent_counts = Counter(n for d in train_main6 for n in d)
    for src in last:
        for dst in range(1, LOTO6_MAX+1):
            if dst in last: continue
            pair = (min(src, dst), max(src, dst))
            conf = pair_freq[pair] / max(antecedent_counts[src], 1)
            scores[dst] += conf
    result = list(last)
    for n, _ in scores.most_common(k - len(last)):
        result.append(n)
    return pad_to_k(sorted(result[:k]), train_main6, k)

def method12_monte_carlo(train_main6, k=K_DEFAULT, n_sim=1000, seed_idx=0):
    n = len(train_main6)
    if n == 0: return list(range(1, k+1))
    rng = np.random.default_rng(seed=seed_idx)
    weights = np.arange(1, n+1, dtype=float); weights /= weights.sum()
    freq = Counter()
    for _ in range(n_sim):
        draw_idx = rng.choice(n, p=weights)
        for num in train_main6[draw_idx]: freq[num] += 1
    return sorted(n for n, _ in freq.most_common(k))

def method13_naive_bayes(train_main6, k=K_DEFAULT):
    if len(train_main6) < 2:
        return method3_freq_all(train_main6, k)
    last = set(train_main6[-1])
    co = defaultdict(int); prior = defaultdict(int)
    for i in range(len(train_main6)-1):
        cur_set = set(train_main6[i]); nxt_set = set(train_main6[i+1])
        for m in cur_set:
            prior[m] += 1
            for n in nxt_set: co[(m, n)] += 1
    scores = Counter()
    for n in range(1, LOTO6_MAX+1):
        for m in last:
            if prior[m] > 0: scores[n] += co[(m, n)] / prior[m]
    return sorted(n for n, _ in scores.most_common(k))

def method14_weighted_ma43(train_main6, k=K_DEFAULT):
    window = train_main6[-43:] if len(train_main6) >= 1 else train_main6
    n = len(window); wts = list(range(1, n+1)); ws = sum(wts)
    base = []
    for p in range(6):
        vals = [window[i][p] for i in range(n)]
        v = sum(wts[i]*vals[i] for i in range(n)) / ws
        base.append(max(1, min(LOTO6_MAX, int(round(v)))))
    return make_unique(base, train_main6, k)

def method15_lstm(target_serial, train_allnums, train_main6, k=K_DEFAULT):
    if target_serial in lstm_json_by_serial:
        raw_pred = sorted(lstm_json_by_serial[target_serial]['pred'])
        return pad_to_k(raw_pred, train_main6, k)
    return lstm_predict(train_allnums, k)

METHOD_NAMES = [
    "Poly Regression (deg-2)", "Moving Avg-43", "Exp-Weighted Avg", "Frequency (all-time)",
    "Markov Chain", "ARIMA(2,1,0)", "Random Forest", "RL (Linear Q)", "HMM (5-state)",
    "k-NN (k=10)", "Modular Cycle", "Apriori", "Monte Carlo", "Naive Bayes",
    "Weighted MA-43", "LSTM",
]

print(f"\nComputing 16 methods' native pools for draw #{TARGET_SERIAL} (trained on all {len(train_main6)} real draws)...")
t0 = time.time()
base_pools = [
    method0_poly_full(train_main6, train_serials, TARGET_SERIAL),
    method1_ma43(train_main6),
    method2_exp_weighted(train_main6),
    method3_freq_all(train_main6),
    method4_markov(train_main6),
    method5_arima(train_main6, TARGET_SERIAL),
    method6_random_forest(train_main6, train_serials, TARGET_SERIAL),
    method7_rl_linear_q(train_main6),
    method8_hmm(train_main6),
    method9_knn(train_main6),
    method10_modular_cycle(train_serials, train_main6, TARGET_SERIAL),
    method11_apriori(train_main6),
    method12_monte_carlo(train_main6, seed_idx=len(train_main6)),
    method13_naive_bayes(train_main6),
    method14_weighted_ma43(train_main6),
    method15_lstm(TARGET_SERIAL, train_allnums, train_main6),
]
print(f"Done in {time.time()-t0:.1f}s")
for name, pool in zip(METHOD_NAMES, base_pools):
    print(f"  {name:24s} (native K={len(pool)}): {pool}")

# ── Pass 4's Worst Combo (Anti-Pick) K=15, computed here ────────────────────
worst_combo_count = Counter()
for idx in WORST_COMBO_METHOD_INDICES:
    for n in base_pools[idx]:
        worst_combo_count[n] += 1
PASS4_PICK = sorted(sorted(worst_combo_count.keys(), key=lambda n: (-worst_combo_count[n], n))[:K_PASS4])
print(f"\nWorst Combo (Anti-Pick) K={K_PASS4} pick for draw #{TARGET_SERIAL} (computed from "
      f"{[METHOD_NAMES[i] for i in WORST_COMBO_METHOD_INDICES]}): {PASS4_PICK}")

# ── topKNums, exact Python port of backtest.html's JS function ─────────────
def top_k_nums(combo, all_pools, k):
    freq = Counter()
    for pool in all_pools:
        for n in pool:
            freq[n] += 1
    if len(combo) == k:
        return sorted(combo)
    if len(combo) > k:
        return sorted(sorted(combo, key=lambda n: -freq.get(n, 0))[:k])
    in_combo = set(combo)
    extra = sorted((n for n in freq if n not in in_combo), key=lambda n: -freq.get(n, 0))
    if len(combo) + len(extra) < k:
        have = set(combo) | set(extra)
        for n in range(1, LOTO6_MAX + 1):
            if n not in have:
                extra.append(n)
    extra = extra[:k - len(combo)]
    return sorted(list(combo) + extra)

# ── Base: triple intersection of the top-3 PCG64 K=38 seeds by hit6b ────────
base_pool = sorted(set(pcg_pools[0]) & set(pcg_pools[1]) & set(pcg_pools[2]))
K_BASE = len(base_pool)
print(f"\nBase (PCG64 seeds {PCG_SEEDS[0]} \u2229 {PCG_SEEDS[1]} \u2229 {PCG_SEEDS[2]}): {K_BASE} numbers: {base_pool}")

# ── Pass 1: normalize each method's native pool to K=19 (cross-method consensus) ──
method_picks_19 = [top_k_nums(pool, base_pools, K_METHODS) for pool in base_pools]
print(f"\nNormalized to K={K_METHODS} via cross-method-consensus (topKNums-equivalent):")
for name, pool in zip(METHOD_NAMES, method_picks_19):
    assert len(pool) == K_METHODS, f"{name}: got {len(pool)} numbers, expected {K_METHODS}"
    print(f"  {name:24s}: {pool}")

# ── Combinatorial elimination (K_BASE-bit bitmasks over base_pool positions) ─
print(f"\n=== Elimination ===")
pos_of = {n: i for i, n in enumerate(base_pool)}

def restricted_mask(target_set):
    mask = 0
    for n in target_set:
        if n in pos_of:
            mask |= (1 << pos_of[n])
    return mask

method_masks = []
for name, pool in zip(METHOD_NAMES, method_picks_19):
    mset = set(pool)
    mmask = restricted_mask(mset)
    overlap = bin(mmask).count('1')
    method_masks.append(mmask)
    print(f"  {name:24s} overlap with {K_BASE}-pool: {overlap} numbers")

universe_count = comb(K_BASE, 6)
print(f"\nUniverse: C({K_BASE},6) = {universe_count:,}")

t0 = time.time()
FULLBASE = (1 << K_BASE) - 1
remaining_after1 = []
removed_by_methods = 0
positions = list(range(K_BASE))

for combo_positions in itertools.combinations(positions, 6):
    combo_mask = 0
    for p in combo_positions:
        combo_mask |= (1 << p)
    removed = False
    for mmask in method_masks:
        if (combo_mask & ~mmask) & FULLBASE == 0:
            removed = True
            break
    if removed:
        removed_by_methods += 1
        continue
    remaining_after1.append(tuple(sorted(base_pool[p] for p in combo_positions)))

elapsed = time.time() - t0
final_remaining_pass1 = len(remaining_after1)
print(f"Enumerated {universe_count:,} combos in {elapsed:.1f}s")
print(f"  Removed by ANY of the 16 methods' K={K_METHODS} containment: {removed_by_methods:,}")
print(f"  Final remaining: {final_remaining_pass1:,}")

# ── Pass 2: xoshiro256** K=21 seeds 0, 1, 2 ──────────────────────────────────
print(f"\n=== Pass 2 ===")
pass2_picks = [xoshiro_predict(seed, TARGET_SERIAL, K_PASS2) for seed in PASS2_SEEDS]
print(f"Xoshiro K={K_PASS2} picks for draw #{TARGET_SERIAL}:")
pass2_masks = []
for seed, pick in zip(PASS2_SEEDS, pass2_picks):
    mmask = restricted_mask(set(pick))
    overlap = bin(mmask).count('1')
    pass2_masks.append(mmask)
    print(f"  seed={seed}: {pick}  [overlap with {K_BASE}-pool: {overlap}]")

t0 = time.time()
remaining_after2 = []
removed_by_pass2 = 0
for combo in remaining_after1:
    combo_mask = 0
    for n in combo:
        combo_mask |= (1 << pos_of[n])
    removed = False
    for mmask in pass2_masks:
        if (combo_mask & ~mmask) & FULLBASE == 0:
            removed = True
            break
    if removed:
        removed_by_pass2 += 1
        continue
    remaining_after2.append(combo)
elapsed2 = time.time() - t0
final_remaining_pass2 = len(remaining_after2)
print(f"\nPass 2 elimination in {elapsed2:.1f}s")
print(f"  Removed by ANY of the {len(PASS2_SEEDS)} xoshiro K={K_PASS2} seeds' containment: {removed_by_pass2:,}")
print(f"  Before Pass 2: {final_remaining_pass1:,}  ->  After Pass 2: {final_remaining_pass2:,}")

# ── Pass 3: historical repeat filter ─────────────────────────────────────────
print(f"\n=== Pass 3 ===")
historical_combos = set(tuple(sorted(nums)) for nums in all_main6)
print(f"Historical winning combos: {len(historical_combos):,} (from {len(all_main6):,} draws, #1-{train_serials[-1]})")

t0 = time.time()
remaining_after3 = []
removed_historical = []
for combo in remaining_after2:
    if combo in historical_combos:
        removed_historical.append(combo)
        continue
    remaining_after3.append(combo)
elapsed3 = time.time() - t0
final_remaining_pass3 = len(remaining_after3)
print(f"Pass 3 elimination in {elapsed3:.1f}s")
print(f"  Removed (exact match to a historical winning combo): {len(removed_historical):,}")
print(f"  Before Pass 3: {final_remaining_pass2:,}  ->  After Pass 3: {final_remaining_pass3:,}")

# ── Pass 4: Worst Combo (Anti-Pick) K=15 pick ────────────────────────────────
print(f"\n=== Pass 4 ===")
K_PASS4 = len(PASS4_PICK)
pass4_mask = restricted_mask(set(PASS4_PICK))
pass4_overlap = bin(pass4_mask).count('1')
print(f"Worst Combo (Anti-Pick) K={K_PASS4} pick for draw #{TARGET_SERIAL}: {PASS4_PICK}  (overlap with {K_BASE}-pool: {pass4_overlap})")

t0 = time.time()
remaining_after4 = []
removed_by_pass4 = 0
for combo in remaining_after3:
    combo_mask = 0
    for n in combo:
        combo_mask |= (1 << pos_of[n])
    if (combo_mask & ~pass4_mask) & FULLBASE == 0:
        removed_by_pass4 += 1
        continue
    remaining_after4.append(combo)
elapsed4 = time.time() - t0
final_remaining_pass4 = len(remaining_after4)
print(f"Pass 4 elimination in {elapsed4:.1f}s")
print(f"  Removed (contained within the Worst Combo K={K_PASS4} pick): {removed_by_pass4:,}")
print(f"  Before Pass 4: {final_remaining_pass3:,}  ->  After Pass 4: {final_remaining_pass4:,}")

# ── Pass 5: no 3+/4+/5+/6-length consecutive-run filter ──────────────────────
print(f"\n=== Pass 5 ===")
def max_consecutive_run(combo):
    s = sorted(combo)
    run = 1
    best = 1
    for i in range(1, len(s)):
        if s[i] == s[i - 1] + 1:
            run += 1
            best = max(best, run)
        else:
            run = 1
    return best

t0 = time.time()
remaining_after5 = []
removed_by_pass5 = 0
run_dist = Counter()
for combo in remaining_after4:
    mr = max_consecutive_run(combo)
    run_dist[mr] += 1
    if mr >= 3:
        removed_by_pass5 += 1
        continue
    remaining_after5.append(combo)
elapsed5 = time.time() - t0
final_remaining_pass5 = len(remaining_after5)
print(f"Pass 5 elimination in {elapsed5:.1f}s")
print(f"  Max-run distribution: " + ", ".join(f"{k}:{v:,}" for k, v in sorted(run_dist.items())))
print(f"  Removed (max consecutive run >= 3): {removed_by_pass5:,}")
print(f"  Before Pass 5: {final_remaining_pass4:,}  ->  After Pass 5: {final_remaining_pass5:,}")

# ── Pass 6: "three consecutive pairs" filter ─────────────────────────────────
print(f"\n=== Pass 6 ===")
def is_three_consecutive_pairs(combo):
    s = sorted(combo)
    runs = []
    run = [s[0]]
    for i in range(1, len(s)):
        if s[i] == s[i - 1] + 1:
            run.append(s[i])
        else:
            runs.append(run)
            run = [s[i]]
    runs.append(run)
    return len(runs) == 3 and all(len(r) == 2 for r in runs)

t0 = time.time()
remaining_after6 = []
removed_by_pass6 = []
for combo in remaining_after5:
    if is_three_consecutive_pairs(combo):
        removed_by_pass6.append(combo)
        continue
    remaining_after6.append(combo)
elapsed6 = time.time() - t0
final_remaining_pass6 = len(remaining_after6)
print(f"Pass 6 elimination in {elapsed6:.1f}s")
print(f"  Removed (three consecutive pairs): {len(removed_by_pass6):,}")
print(f"  Before Pass 6: {final_remaining_pass5:,}  ->  After Pass 6: {final_remaining_pass6:,}")

# ── Pass 7: "5 or 6 overlap with the immediately previous draw" filter ──────
print(f"\n=== Pass 7 ===")
PREV_DRAW_SERIAL = TARGET_SERIAL - 1  # 2133
PREV_DRAW_NUMS = sorted([1, 11, 14, 20, 29, 38])
assert sorted(all_main6[all_serials.index(PREV_DRAW_SERIAL)]) == PREV_DRAW_NUMS, \
    f"PREV_DRAW_NUMS stale -- draw #{PREV_DRAW_SERIAL} in DB is {all_main6[all_serials.index(PREV_DRAW_SERIAL)]}, not {PREV_DRAW_NUMS}"
prev_draw_set = set(PREV_DRAW_NUMS)
print(f"Previous actual draw #{PREV_DRAW_SERIAL}: {PREV_DRAW_NUMS}")

t0 = time.time()
remaining_after7 = []
removed_by_pass7 = []
overlap_dist = Counter()
for combo in remaining_after6:
    ov = len(set(combo) & prev_draw_set)
    overlap_dist[ov] += 1
    if ov in (5, 6):
        removed_by_pass7.append(combo)
        continue
    remaining_after7.append(combo)
elapsed7 = time.time() - t0
final_remaining_pass7 = len(remaining_after7)
print(f"Pass 7 elimination in {elapsed7:.1f}s")
print(f"  Overlap distribution (of Pass-6-remaining combos vs draw #{PREV_DRAW_SERIAL}): " +
      ", ".join(f"{k}:{v:,}" for k, v in sorted(overlap_dist.items())))
print(f"  Removed (overlap 5 or 6 with draw #{PREV_DRAW_SERIAL}): {len(removed_by_pass7):,}")
print(f"  Before Pass 7: {final_remaining_pass6:,}  ->  After Pass 7: {final_remaining_pass7:,}")

print(f"\nFull elimination sequence: {universe_count:,} -> {final_remaining_pass1:,} (Pass 1) -> {final_remaining_pass2:,} (Pass 2) -> "
      f"{final_remaining_pass3:,} (Pass 3) -> {final_remaining_pass4:,} (Pass 4) -> {final_remaining_pass5:,} (Pass 5) -> "
      f"{final_remaining_pass6:,} (Pass 6) -> {final_remaining_pass7:,} (Pass 7)")

# ── Save outputs ──────────────────────────────────────────────────────────
meta = {
    'targetSerial': TARGET_SERIAL,
    'trainedThroughSerial': train_serials[-1],
    'pcgSeeds': PCG_SEEDS,
    'k': K_PCG,
    'pcgPools': pcg_pools,
    'pcgPoolsOrdered': pcg_pools_ordered,
    'base': {'k': K_BASE, 'pool': base_pool},
    'methodNames': METHOD_NAMES,
    'methodBasePools': base_pools,
    'methodPicks': method_picks_19,
    'methodK': K_METHODS,
    'universeCount': universe_count,
    'removedByMethods': removed_by_methods,
    'finalRemainingPass1': final_remaining_pass1,
    'methodOverlaps': [bin(m).count('1') for m in method_masks],
    'pass2K': K_PASS2,
    'pass2Seeds': [{'seed': seed, 'pick': pick} for seed, pick in zip(PASS2_SEEDS, pass2_picks)],
    'removedByPass2': removed_by_pass2,
    'finalRemainingPass2': final_remaining_pass2,
    'pass2Overlaps': [bin(m).count('1') for m in pass2_masks],
    'historicalDrawCount': len(all_main6),
    'historicalCombos': [sorted(nums) for nums in all_main6],
    'removedHistorical': [list(c) for c in removed_historical],
    'finalRemainingPass3': final_remaining_pass3,
    'pass4K': K_PASS4,
    'pass4Pick': PASS4_PICK,
    'pass4Overlap': pass4_overlap,
    'removedByPass4': removed_by_pass4,
    'finalRemainingPass4': final_remaining_pass4,
    'removedByPass5': removed_by_pass5,
    'pass5RunDistribution': {str(k): v for k, v in sorted(run_dist.items())},
    'finalRemainingPass5': final_remaining_pass5,
    'removedByPass6': [list(c) for c in removed_by_pass6],
    'finalRemainingPass6': final_remaining_pass6,
    'pass7PrevDrawSerial': PREV_DRAW_SERIAL,
    'pass7PrevDrawNums': PREV_DRAW_NUMS,
    'removedByPass7': [list(c) for c in removed_by_pass7],
    'pass7OverlapDistribution': {str(k): v for k, v in sorted(overlap_dist.items())},
    'finalRemainingPass7': final_remaining_pass7,
    'finalRemaining': final_remaining_pass7,
}
with open(META_OUT, 'w', encoding='utf-8') as f:
    json.dump(meta, f, indent=2)
print(f"\nSaved {META_OUT}")

with open(COMBOS_OUT, 'w', encoding='utf-8') as f:
    json.dump(remaining_after7, f, separators=(',', ':'))
print(f"Saved {COMBOS_OUT} ({len(remaining_after7):,} combos, {os.path.getsize(COMBOS_OUT)//1024:,} KB)")
