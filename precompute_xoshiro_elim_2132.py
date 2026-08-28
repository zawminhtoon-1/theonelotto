"""
precompute_xoshiro_elim_2132.py
-----------------------------------
Precomputes everything the "Xoshiro K=38 x Modular Cycle K=33 + 16-Method
Elimination" page needs for draw #2132 -- the true next-upcoming Loto6
draw (#2131 is now the latest real/confirmed draw, having landed since
xoshiro_elim_2131.html was built). Standard walk-forward build, same
methodology as #2130/#2131, trained on all real draws through #2131,
no leakage.

Rebuilt (2026-08-28) to REMOVE the old Pass 2 (top 1000 worst-coverage
random seeds, K=15, from seed_hit_random_k17) entirely from the pipeline,
per explicit user request. Downstream passes renumbered:
  old Pass 1 (16 methods)                -> Pass 1 (unchanged)
  old Pass 2 (1000 worst-coverage seeds) -> REMOVED
  old Pass 3 (xoshiro K=21 seeds 0/1/2)  -> Pass 2
  old Pass 4 (historical repeat filter)  -> Pass 3
  old Pass 5 (Worst Combo Anti-Pick)     -> Pass 4
  old Pass 6 (consecutive-run filter)    -> Pass 5
  old Pass 7 (three-consecutive-pairs)   -> Pass 6 (final)

Base pool: Modular Cycle's K=33 pick (walk-forward, trained on all real
           draws through #2131, native K=28 pick normalized to K=33 via
           topKNums()) INTERSECTED with xoshiro256** K=38 seed #692,809's
           pick (current overall best K=38 seed, full 0-1,000,000 scan)
           -- both for draw #2132. Universe = C(K_BASE,6), K_BASE being
           whatever the intersection size comes out to.

Pass 1:    each of the 16 prediction methods' K=19 pick for #2132,
           computed walk-forward (trained on all real draws through
           #2131, append_backtest.py's method definitions) then
           normalized to K=19 via the same topKNums() cross-method-
           consensus trim/pad port. Any Base combo fully contained
           within ANY single one of these 16 sets gets removed.

Pass 2:    xoshiro256** K=21 seeds 0, 1, and 2 -- the same K=21
           algorithm used on xoshiro_seed_backtest.html. Each seed's
           K=21 pick for draw #2132 is computed with the same verified
           xoshiro256** implementation used for Base's xoshiro side.
           Any Pass-1-remaining combo fully contained within ANY single
           one of these 3 picks gets removed.

Pass 3:    historical repeat filter (same "zero repeats in history"
           pattern used in the earlier #2124 elimination flow). Any
           Pass-2-remaining combo that exactly matches an actual
           6-number winning combo from draws #1 through #2131 gets
           removed.

Pass 4:    the "Worst Combo (Anti-Pick)" K=15 pick -- MA-43 + Exp-weighted
           + Random Forest + kNN + Apriori Association Rules consensus,
           for draw #2132. Any Pass-3-remaining combo fully contained
           within this 15-number pick gets removed. Computed directly
           here (not screenshotted off /predictions, to keep this script
           self-contained and reproducible, same convention as #2131's
           build) from base_pools[1] (MA-43), base_pools[2] (Exp-weighted),
           base_pools[6] (Random Forest), base_pools[9] (kNN), and
           base_pools[11] (Apriori) -- the same 5 methods, same Python
           implementations (verbatim from append_backtest.py, already
           used above for Pass 1's 16 methods), same union-count-desc-
           then-ascending-number
           combining rule as PredictionsView.tsx's worstComboNums.

Pass 5:    no 3+/4+/5+/6-length consecutive-run filter. Removes any
           Pass-4-remaining combo whose sorted main numbers contain a
           run of 3 or more consecutive integers (e.g. 5,6,7).
           Historical basis: across all real Loto6 draws, only 5.96%
           have a max run of exactly 3, 0.66% exactly 4, and 0 have
           ever had a run of 5 or 6 -- runs of 3+ are collectively rare
           (6.62% of real draws) and this pass removes combos matching
           that same rare pattern.

Pass 6:    "three consecutive pairs" filter (final). Removes any
           Pass-5-remaining combo whose sorted main numbers decompose
           into exactly three consecutive pairs (each run of exactly 2,
           no run of 3+, no isolated singles) -- e.g. 1,2,9,10,15,16.
           Historical basis: only 3 of all 2,131 real Loto6 draws
           (0.141%) match this exact pattern (#172, #775, #1394).

Self-checks the xoshiro implementation against a known-good value before
trusting Base's xoshiro component.

Outputs:
  xoshiro_elim_2132_meta.json          -- small: pools, method picks, counts
  public/xoshiro_elim_2132_combos.json -- large: remaining combo list
                                          (fetched client-side, not inlined)

Run: python precompute_xoshiro_elim_2132.py
"""
import json, os, re, itertools, time, warnings
import numpy as np
import psycopg2
from collections import Counter, defaultdict
from math import comb

warnings.filterwarnings('ignore')

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
ENV_LOCAL = BASE + r"\.env.local"
META_OUT = BASE + r"\xoshiro_elim_2132_meta.json"
COMBOS_OUT = BASE + r"\public\xoshiro_elim_2132_combos.json"

LOTO6_MAX = 43
TARGET_SERIAL = 2132
K_XO = 38
K_MC = 33
K_METHODS = 19   # normalized K for all 16 methods (this page's Pass 1)
K_DEFAULT = 15   # native K most methods produce before normalization
K_PASS2 = 21     # xoshiro256** K=21, same as xoshiro_seed_backtest.html
PASS2_SEEDS = [0, 1, 2]
K_PASS4 = 15     # Worst Combo (Anti-Pick) K -- computed below from base_pools
                 # (MA-43 + Exp-weighted + Random Forest + kNN + Apriori
                 # consensus), NOT hardcoded -- see Pass 4 docstring above.
WORST_COMBO_METHOD_INDICES = [1, 2, 6, 9, 11]  # MA-43, Exp-Weighted, RF, kNN, Apriori

SEED_XO = 692809   # best K=38 seed (0-1,000,000 scan)

# ── xoshiro256** (verified implementation, same as every other page) ────────
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
    """Generation order -- the order the partial Fisher-Yates shuffle finalizes
    each position (i = n-1 first, down to i = n-k last), NOT sorted. Same
    convention as xoshiro_seed_scan_k38.html's seed-detail picks (built by
    appending arr[i] right after each swap, in loop order -- NOT the plain
    arr[n-k:] slice, which comes out reversed relative to this)."""
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

# ── Self-check against known-good value before trusting the xoshiro side ────
# Fixed anchor point (draw #2129, independently verified earlier this
# session) -- NOT meant to shift with TARGET_SERIAL each build.
_KNOWN_2129 = [2,3,4,5,6,7,8,9,11,12,13,14,15,16,17,18,19,20,21,22,24,25,27,28,29,30,31,32,33,34,35,36,38,39,40,41,42,43]
_check = xoshiro_predict(SEED_XO, 2129, K_XO)
assert _check == _KNOWN_2129, f"Self-check FAILED: {_check}"
print(f"Self-check OK: xoshiro seed {SEED_XO} K={K_XO} draw #2129 matches known-good value.")

xo_pool = xoshiro_predict(SEED_XO, TARGET_SERIAL, K_XO)
xo_pool_ordered = xoshiro_predict_raw(SEED_XO, TARGET_SERIAL, K_XO)
print(f"Xoshiro K={K_XO} seed #{SEED_XO} pick for draw #{TARGET_SERIAL}: {xo_pool}")
print(f"  (generation order): {xo_pool_ordered}")

# ── Fetch all real draws through #2131 ───────────────────────────────────────
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
    """Generation order -- the mod-43 cycle's own frequency ranking (highest
    count first, ties broken by ascending number), NOT sorted ascending.
    This IS the order the method actually produced the pick in, before
    method10_modular_cycle's final sort() throws it away."""
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

# ── Pass 4's Worst Combo (Anti-Pick) K=15, computed here (see docstring) ────
# instead of read off /predictions -- same 5-method consensus (MA-43 +
# Exp-Weighted + Random Forest + kNN + Apriori), same combining rule as
# PredictionsView.tsx's worstComboNums: union count across the 5 methods'
# native pools, sorted by count desc then number asc (JS Object.entries on
# integer-like keys iterates ascending regardless of insertion order, and
# Array.sort is stable -- replicated here via the (-count, n) sort key).
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

def top_k_nums_extend_ordered(combo_ordered, all_pools, k):
    """Same padding logic as top_k_nums's extend branch (len(combo) < k), but
    preserves generation order instead of the final sort(): returns
    combo_ordered followed by the padding numbers in their own selection
    order (highest cross-method frequency first). Extend-only -- callers
    must ensure len(combo_ordered) < k."""
    freq = Counter()
    for pool in all_pools:
        for n in pool:
            freq[n] += 1
    in_combo = set(combo_ordered)
    extra = sorted((n for n in freq if n not in in_combo), key=lambda n: -freq.get(n, 0))
    if len(combo_ordered) + len(extra) < k:
        have = set(combo_ordered) | set(extra)
        for n in range(1, LOTO6_MAX + 1):
            if n not in have:
                extra.append(n)
    extra = extra[:k - len(combo_ordered)]
    return list(combo_ordered) + extra

# ── Base: Modular Cycle K=33 (normalized) ∩ xoshiro K=38 seed #692,809 ───────
modcycle_native = base_pools[10]
modcycle_native_ordered = modular_cycle_ranked(train_serials, train_main6, TARGET_SERIAL, k=28)
mc_pool = top_k_nums(modcycle_native, base_pools, K_MC)
mc_pool_ordered = top_k_nums_extend_ordered(modcycle_native_ordered, base_pools, K_MC)
print(f"\nModular Cycle native pick (K={len(modcycle_native)}): {modcycle_native}")
print(f"  (generation order): {modcycle_native_ordered}")
print(f"Modular Cycle normalized to K={K_MC}: {mc_pool}")
print(f"  (generation order): {mc_pool_ordered}")
assert sorted(mc_pool_ordered) == mc_pool, "mc_pool_ordered is not a reordering of mc_pool!"

base_pool = sorted(set(mc_pool) & set(xo_pool))
K_BASE = len(base_pool)
print(f"\nBase (Modular Cycle K={K_MC} ∩ xoshiro K={K_XO}): {K_BASE} numbers: {base_pool}")

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
print(f"\nElimination sequence: {universe_count:,} -> {final_remaining_pass1:,} remaining")

# ── Pass 2: xoshiro256** K=21 seeds 0, 1, 2 (same algorithm as
# xoshiro_seed_backtest.html). Any Pass-1-remaining combo fully contained
# within ANY of these 3 picks is removed. ───────────────────────────────────
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
print(f"\nFull elimination sequence: {universe_count:,} -> {final_remaining_pass1:,} (Pass 1) -> {final_remaining_pass2:,} (Pass 2)")

# ── Pass 3: historical repeat filter (same "zero repeats in history" pattern
# used in the earlier #2124 elimination flow). Any Pass-2-remaining combo
# that exactly matches an actual 6-number winning combo from draws #1
# through #2131 is removed. ──────────────────────────────────────────────────
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
if removed_historical:
    print(f"  Matched historical combos: {removed_historical}")
print(f"  Before Pass 3: {final_remaining_pass2:,}  ->  After Pass 3: {final_remaining_pass3:,}")
print(f"\nFull elimination sequence: {universe_count:,} -> {final_remaining_pass1:,} (Pass 1) -> {final_remaining_pass2:,} (Pass 2) -> "
      f"{final_remaining_pass3:,} (Pass 3)")

# ── Pass 4: Worst Combo (Anti-Pick) K=15 pick. Any Pass-3-remaining combo
# fully contained within this pick is removed. ──────────────────────────────
print(f"\n=== Pass 4 ===")
K_PASS4 = len(PASS4_PICK)
print(f"Worst Combo (Anti-Pick) K={K_PASS4} pick for draw #{TARGET_SERIAL}: {PASS4_PICK}")
pass4_mask = restricted_mask(set(PASS4_PICK))
pass4_overlap = bin(pass4_mask).count('1')
print(f"  overlap with {K_BASE}-pool: {pass4_overlap}")

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
print(f"\nFull elimination sequence: {universe_count:,} -> {final_remaining_pass1:,} (Pass 1) -> {final_remaining_pass2:,} (Pass 2) -> "
      f"{final_remaining_pass3:,} (Pass 3) -> {final_remaining_pass4:,} (Pass 4)")

# ── Pass 5: no 3+/4+/5+/6-length consecutive-run filter. Removes any
# Pass-4-remaining combo whose sorted main numbers contain a run of 3 or
# more consecutive integers (e.g. 5,6,7). Historical basis: across all
# real Loto6 draws, only ~5.96% have a max run of exactly 3, ~0.66%
# exactly 4, and 0 have ever had a run of 5 or 6 -- runs of 3+ are
# collectively rare (6.62% of real draws) and this pass removes combos
# matching that same rare pattern. ───────────────────────────────────────
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
print(f"  Max-run distribution (of Pass-4-remaining combos): " + ", ".join(f"{k}:{v:,}" for k, v in sorted(run_dist.items())))
print(f"  Removed (max consecutive run >= 3): {removed_by_pass5:,}")
print(f"  Before Pass 5: {final_remaining_pass4:,}  ->  After Pass 5: {final_remaining_pass5:,}")
print(f"\nFull elimination sequence: {universe_count:,} -> {final_remaining_pass1:,} (Pass 1) -> {final_remaining_pass2:,} (Pass 2) -> "
      f"{final_remaining_pass3:,} (Pass 3) -> {final_remaining_pass4:,} (Pass 4) -> {final_remaining_pass5:,} (Pass 5)")

# ── Pass 6: "three consecutive pairs" filter (final). Removes any
# Pass-5-remaining combo whose sorted main numbers decompose into exactly
# three consecutive pairs (each run of exactly 2, no run of 3+, no
# isolated singles) -- e.g. 1,2,9,10,15,16. Historical basis: only 3 of
# all 2,131 real Loto6 draws (0.141%) match this exact pattern (#172,
# #775, #1394). ──────────────────────────────────────────────────────────
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
print(f"  Removed (three consecutive pairs, e.g. 1,2,9,10,15,16): {len(removed_by_pass6):,}")
if removed_by_pass6[:10]:
    print(f"  First 10 removed: {removed_by_pass6[:10]}")
print(f"  Before Pass 6: {final_remaining_pass5:,}  ->  After Pass 6: {final_remaining_pass6:,}")
print(f"\nFull elimination sequence: {universe_count:,} -> {final_remaining_pass1:,} (Pass 1) -> {final_remaining_pass2:,} (Pass 2) -> "
      f"{final_remaining_pass3:,} (Pass 3) -> {final_remaining_pass4:,} (Pass 4) -> {final_remaining_pass5:,} (Pass 5) -> "
      f"{final_remaining_pass6:,} (Pass 6)")

# ── Save outputs ──────────────────────────────────────────────────────────
meta = {
    'targetSerial': TARGET_SERIAL,
    'trainedThroughSerial': train_serials[-1],  # 2131 -- equals TARGET_SERIAL-1 for this standard walk-forward build
    'xo': {'seed': SEED_XO, 'k': K_XO, 'pool': xo_pool, 'poolOrdered': xo_pool_ordered},
    'mc': {'k': K_MC, 'pool': mc_pool, 'poolOrdered': mc_pool_ordered},
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
    'finalRemaining': final_remaining_pass6,
}
with open(META_OUT, 'w', encoding='utf-8') as f:
    json.dump(meta, f, indent=2)
print(f"\nSaved {META_OUT}")

with open(COMBOS_OUT, 'w', encoding='utf-8') as f:
    json.dump(remaining_after6, f, separators=(',', ':'))
print(f"Saved {COMBOS_OUT} ({len(remaining_after6):,} combos, {os.path.getsize(COMBOS_OUT)//1024:,} KB)")
