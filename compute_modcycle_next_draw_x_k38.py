"""
compute_modcycle_next_draw_x_k38.py
--------------------------------------
Computes the "next upcoming draw" reference pool for both Modular Cycle x
K=38 intersection pages (K=28 and K=33): for draw #2130, Modular Cycle's
live walk-forward prediction (trained on all real draws through #2129,
same mechanism as precompute_xoshiro_elim_2128.py/2129.py used for their
Base/Pass pools) intersected with xoshiro K=38 seed #692,809's pick for
#2130.

Reuses append_backtest.py's method function definitions verbatim (same
copy already used in precompute_xoshiro_elim_2129.py) -- computes all 16
methods' NATIVE picks for #2130 (needed because topKNums()'s cross-method
padding logic draws from all 16 pools' combined frequency, exactly as
backtest.html does per-draw), then normalizes Modular Cycle's native
K=28 pick to both K=28 (no-op) and K=33 via that same topKNums port.

Self-checks the xoshiro implementation against a known-good value before
trusting it.

Run: python compute_modcycle_next_draw_x_k38.py
Output: modcycle_next_draw_x_k38_data.json
"""
import json, os, re, itertools, time, warnings
import numpy as np
import psycopg2
from collections import Counter, defaultdict
from math import comb

warnings.filterwarnings('ignore')

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
ENV_LOCAL = BASE + r"\.env.local"
OUT_JSON = BASE + r"\modcycle_next_draw_x_k38_data.json"

LOTO6_MAX = 43
TARGET_SERIAL = 2130
K_XO = 38
SEED_XO = 692809
K_DEFAULT = 15

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
def xoshiro_predict(seed, draw_serial, k, pool_max=LOTO6_MAX):
    combined = (seed * 10_000_000 + draw_serial) & MASK64
    s = seed_state(combined)
    arr = list(range(1, pool_max + 1))
    n = len(arr)
    for i in range(n - 1, n - 1 - k, -1):
        r = xoshiro_next(s)
        j = r % (i + 1)
        arr[i], arr[j] = arr[j], arr[i]
    return sorted(arr[n - k:])

# Self-check against the known-good reference for seed 692809, draw #2129
# (K=38) -- confirms the same formula holds before trusting draw #2130.
_KNOWN_2129 = [2,3,4,5,6,7,8,9,11,12,13,14,15,16,17,18,19,20,21,22,24,25,27,28,29,30,31,32,33,34,35,36,38,39,40,41,42,43]
_check = xoshiro_predict(SEED_XO, 2129, K_XO)
assert _check == _KNOWN_2129, f"Self-check FAILED: {_check}"
print(f"Self-check OK: xoshiro seed {SEED_XO} K={K_XO} draw #2129 matches known-good value.")

xo_pool_2130 = xoshiro_predict(SEED_XO, TARGET_SERIAL, K_XO)
print(f"Xoshiro seed {SEED_XO} K={K_XO} pick for draw #{TARGET_SERIAL}: {xo_pool_2130}")

# ── Fetch all real draws through #2129 ───────────────────────────────────────
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

def method10_modular_cycle(train_serials, train_main6, target_serial, k=28):
    target_mod = target_serial % LOTO6_MAX
    freq = Counter()
    for s, d in zip(train_serials, train_main6):
        if s % LOTO6_MAX == target_mod:
            for n in d: freq[n] += 1
    if not freq: freq = Counter(n for d in train_main6 for n in d)
    top = sorted(range(1, LOTO6_MAX+1), key=lambda x: -freq.get(x, 0))[:k]
    return sorted(top)

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

modcycle_native = base_pools[10]
print(f"\nModular Cycle native pick for #{TARGET_SERIAL} (K={len(modcycle_native)}): {modcycle_native}")

mc_28 = top_k_nums(modcycle_native, base_pools, 28)
mc_33 = top_k_nums(modcycle_native, base_pools, 33)
print(f"Modular Cycle normalized to K=28: {mc_28}")
print(f"Modular Cycle normalized to K=33: {mc_33}")

inter_28 = sorted(set(mc_28) & set(xo_pool_2130))
inter_33 = sorted(set(mc_33) & set(xo_pool_2130))
combo_28 = comb(len(inter_28), 6) if len(inter_28) >= 6 else 0
combo_33 = comb(len(inter_33), 6) if len(inter_33) >= 6 else 0
FULL_UNIVERSE = comb(43, 6)

print(f"\nIntersection (Modular Cycle K=28) x (xoshiro K=38 seed {SEED_XO}) for #{TARGET_SERIAL}:")
print(f"  {len(inter_28)} numbers: {inter_28}  -- C({len(inter_28)},6)={combo_28:,} ({combo_28/FULL_UNIVERSE*100:.2f}% of universe)")
print(f"\nIntersection (Modular Cycle K=33) x (xoshiro K=38 seed {SEED_XO}) for #{TARGET_SERIAL}:")
print(f"  {len(inter_33)} numbers: {inter_33}  -- C({len(inter_33)},6)={combo_33:,} ({combo_33/FULL_UNIVERSE*100:.2f}% of universe)")

out = {
    'targetSerial': TARGET_SERIAL,
    'xoSeed': SEED_XO, 'kXo': K_XO,
    'xoPool': xo_pool_2130,
    'modCycleNative': modcycle_native,
    'k28': {'mcPool': mc_28, 'inter': inter_28, 'comboCount': combo_28},
    'k33': {'mcPool': mc_33, 'inter': inter_33, 'comboCount': combo_33},
}
with open(OUT_JSON, 'w') as f:
    json.dump(out, f, indent=2)
print(f"\nWrote {OUT_JSON}")
