"""
precompute_xoshiro_elim_2129.py
-----------------------------------
REBUILT to match #2130's design: this page's original Base (single-
source xoshiro256** K=38, seed #692,809) predates the Modular Cycle
intersection concept. Base is now Modular Cycle K=33 (intersected)
with xoshiro K=38 seed #692,809, same architecture as
precompute_xoshiro_elim_2130.py, adapted for #2129 -- which has
already happened for real, so every walk-forward-trained component
(Modular Cycle, the 16 methods, the Worst Combo pick) is explicitly
trained on draws #1-2128 ONLY (never #2129 itself, to avoid leaking
the answer), while the historical-repeat-filter pass correctly DOES
include #2129 in its historical set (it's a real, confirmed draw by
now).

Base pool: Modular Cycle's K=33 pick (walk-forward, trained on draws
           #1-2128 only, native K=28 normalized to K=33 via
           topKNums()) INTERSECTED with xoshiro256** K=38 seed
           #692,809's pick for draw #2129.

Pass 1:    each of the 16 prediction methods' K=19 pick for #2129,
           computed walk-forward (trained on draws #1-2128 only,
           append_backtest.py's method definitions) then normalized to
           K=19 via topKNums(). Any Base combo fully contained within
           ANY single one of these 16 sets gets removed.

Pass 2:    the top 1000 worst-coverage seeds (highest 0-hit count)
           from seed_hit_random_k17, K=15 picks for draw #2129.

Pass 3:    xoshiro256** K=21 seeds 0, 1, 2, draw #2129.

Pass 4:    historical repeat filter -- exact match to a real 6-number
           winning combo from draws #1-2129 (#2129 IS included, since
           it has already happened).

Pass 5:    the Worst Combo (Anti-Pick) K=15 pick for draw #2129 (MA-43
           + Exp-weighted + Random Forest + kNN + Apriori consensus).
           Since #2129 already happened, /predictions no longer shows
           this pick (it now targets #2130), so it's recomputed here
           by faithfully replicating page.tsx's actual client-side JS
           methods in Python (confirmed DIFFERENT from the simplified
           ports in append_backtest.py used for Pass 1/Base: page.tsx's
           RF is a bagged-OLS ensemble via Gauss-Jordan-solved normal
           equations with a deterministic LCG bootstrap seed=42, not
           sklearn RandomForestRegressor; its Apriori is 1-item+2-item
           sequential association, not simple pair co-occurrence),
           walk-forward trained on draws #1-2128 only.

Self-checks the xoshiro implementation against a known-good value
before trusting Base's xoshiro component.

Outputs:
  xoshiro_elim_2129_meta.json          -- small: pools, method picks, counts
  public/xoshiro_elim_2129_combos.json -- large: remaining combo list
                                          (fetched client-side, not inlined)

Run: python precompute_xoshiro_elim_2129.py
"""
import json, os, re, itertools, time, warnings, sqlite3, random as pyrandom
import numpy as np
import psycopg2
from collections import Counter, defaultdict
from math import comb

warnings.filterwarnings('ignore')

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
ENV_LOCAL = BASE + r"\.env.local"
DB_PATH = BASE + r"\loto6_local.db"
META_OUT = BASE + r"\xoshiro_elim_2129_meta.json"
COMBOS_OUT = BASE + r"\public\xoshiro_elim_2129_combos.json"

LOTO6_MAX = 43
TARGET_SERIAL = 2129
TRAIN_THROUGH = TARGET_SERIAL - 1   # 2128 -- walk-forward cutoff, never includes #2129
K_XO = 38
K_MC = 33
K_METHODS = 19
K_DEFAULT = 15
K_RANDOM = 15
N_WORST_SEEDS = 1000
RANDOM_TABLE = "seed_hit_random_k17"
K_PASS3 = 21
PASS3_SEEDS = [0, 1, 2]

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

# ── Self-check against known-good value before trusting the xoshiro side ────
_KNOWN_XO_2129 = [2,3,4,5,6,7,8,9,11,12,13,14,15,16,17,18,19,20,21,22,24,25,27,28,29,30,31,32,33,34,35,36,38,39,40,41,42,43]
_check = xoshiro_predict(SEED_XO, TARGET_SERIAL, K_XO)
assert _check == _KNOWN_XO_2129, f"Self-check FAILED: {_check}"
print(f"Self-check OK: xoshiro seed {SEED_XO} K={K_XO} draw #{TARGET_SERIAL} matches known-good value.")

xo_pool = xoshiro_predict(SEED_XO, TARGET_SERIAL, K_XO)
print(f"Xoshiro K={K_XO} seed #{SEED_XO} pick for draw #{TARGET_SERIAL}: {xo_pool}")

# ── Fetch training draws (#1-2128 ONLY -- #2129 must never leak into any
# walk-forward-trained component) and the full historical set (#1-2129,
# which DOES include #2129 since it has already happened). ──────────────────
if 'DATABASE_URL' not in os.environ:
    with open(ENV_LOCAL, encoding='utf-8') as f:
        env_text = f.read()
    m = re.search(r'DATABASE_URL=(.+)', env_text)
    os.environ['DATABASE_URL'] = m.group(1).strip()

conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()
cur.execute(
    "SELECT draw_serial, num1,num2,num3,num4,num5,num6, bonus "
    "FROM loto6_results WHERE draw_serial <= %s ORDER BY draw_serial", (TRAIN_THROUGH,)
)
db_rows = cur.fetchall()
cur.execute(
    "SELECT draw_serial, num1,num2,num3,num4,num5,num6 "
    "FROM loto6_results WHERE draw_serial <= %s ORDER BY draw_serial", (TARGET_SERIAL,)
)
hist_rows = cur.fetchall()
conn.close()
print(f"\nFetched {len(db_rows)} TRAINING draws (#{db_rows[0][0]}-{db_rows[-1][0]}) -- walk-forward, excludes #{TARGET_SERIAL}.")
if db_rows[-1][0] != TRAIN_THROUGH:
    raise SystemExit(f"Expected latest training draw #{TRAIN_THROUGH}, found #{db_rows[-1][0]}.")
print(f"Fetched {len(hist_rows)} HISTORICAL draws (#{hist_rows[0][0]}-{hist_rows[-1][0]}) -- includes #{TARGET_SERIAL} for Pass 4.")
if hist_rows[-1][0] != TARGET_SERIAL:
    raise SystemExit(f"Expected historical set through #{TARGET_SERIAL}, found #{hist_rows[-1][0]}.")

all_serials = [r[0] for r in db_rows]
all_main6   = [sorted([r[1],r[2],r[3],r[4],r[5],r[6]]) for r in db_rows]
all_allnums = [sorted([r[1],r[2],r[3],r[4],r[5],r[6],r[7]]) for r in db_rows]

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

print(f"\nComputing 16 methods' native pools for draw #{TARGET_SERIAL} (trained on draws #1-{TRAIN_THROUGH} ONLY)...")
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

# ── Base: Modular Cycle K=33 (normalized) ∩ xoshiro K=38 seed #692,809 ───────
modcycle_native = base_pools[10]
mc_pool = top_k_nums(modcycle_native, base_pools, K_MC)
print(f"\nModular Cycle native pick (K={len(modcycle_native)}): {modcycle_native}")
print(f"Modular Cycle normalized to K={K_MC}: {mc_pool}")

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
print(f"\n=== Pass 1 ===")
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
remaining = []
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
    remaining.append(tuple(sorted(base_pool[p] for p in combo_positions)))

elapsed = time.time() - t0
final_remaining_pass1 = len(remaining)
print(f"Enumerated {universe_count:,} combos in {elapsed:.1f}s")
print(f"  Removed by ANY of the 16 methods' K={K_METHODS} containment: {removed_by_methods:,}")
print(f"  Final remaining: {final_remaining_pass1:,}")

# ── Pass 2: top N_WORST_SEEDS worst-coverage seeds (highest 0-hit count in
# seed_hit_random_k17), K=K_RANDOM picks for #TARGET_SERIAL ─────────────────
print(f"\n=== Pass 2 ===")
conn2 = sqlite3.connect(DB_PATH)
cur2 = conn2.cursor()
cur2.execute(f"""SELECT seed, hit0_count FROM {RANDOM_TABLE}
                 ORDER BY hit0_count DESC, seed ASC LIMIT {N_WORST_SEEDS}""")
worst_seeds = cur2.fetchall()
conn2.close()
if len(worst_seeds) != N_WORST_SEEDS:
    raise SystemExit(f"Expected {N_WORST_SEEDS} worst-coverage seeds, got {len(worst_seeds)}")
print(f"Top {N_WORST_SEEDS} worst-coverage seeds from {RANDOM_TABLE}: hit0 range {worst_seeds[0][1]} to {worst_seeds[-1][1]}")

def random_predict_pass2(seed, draw_serial, k=K_RANDOM):
    rng = pyrandom.Random(seed * 10_000_000 + draw_serial)
    return sorted(rng.sample(range(1, LOTO6_MAX + 1), k))

random_picks = [random_predict_pass2(seed, TARGET_SERIAL) for seed, _ in worst_seeds]
random_masks = [restricted_mask(set(p)) for p in random_picks]
overlaps2 = [bin(m).count('1') for m in random_masks]
print(f"Overlap with {K_BASE}-pool across the {N_WORST_SEEDS} K={K_RANDOM} picks: min={min(overlaps2)} max={max(overlaps2)} avg={sum(overlaps2)/len(overlaps2):.1f}")

t0 = time.time()
remaining_after2 = []
removed_by_random = 0
for combo in remaining:
    combo_mask = 0
    for n in combo:
        combo_mask |= (1 << pos_of[n])
    hit = False
    for mmask in random_masks:
        if (combo_mask & ~mmask) & FULLBASE == 0:
            hit = True
            break
    if hit:
        removed_by_random += 1
    else:
        remaining_after2.append(combo)
elapsed2 = time.time() - t0
final_remaining_pass2 = len(remaining_after2)
print(f"Pass 2 elimination in {elapsed2:.1f}s")
print(f"  Removed by ANY of the {N_WORST_SEEDS} worst-coverage seeds' K={K_RANDOM} containment: {removed_by_random:,}")
print(f"  Before Pass 2: {final_remaining_pass1:,}  ->  After Pass 2: {final_remaining_pass2:,}")

# ── Pass 3: xoshiro256** K=21 seeds 0, 1, 2 ─────────────────────────────────
print(f"\n=== Pass 3 ===")
pass3_picks = [xoshiro_predict(seed, TARGET_SERIAL, K_PASS3) for seed in PASS3_SEEDS]
pass3_masks = []
for seed, pick in zip(PASS3_SEEDS, pass3_picks):
    mmask = restricted_mask(set(pick))
    overlap = bin(mmask).count('1')
    pass3_masks.append(mmask)
    print(f"  seed={seed}: {pick}  [overlap with {K_BASE}-pool: {overlap}]")

t0 = time.time()
remaining_after3 = []
removed_by_pass3 = 0
for combo in remaining_after2:
    combo_mask = 0
    for n in combo:
        combo_mask |= (1 << pos_of[n])
    hit = False
    for mmask in pass3_masks:
        if (combo_mask & ~mmask) & FULLBASE == 0:
            hit = True
            break
    if hit:
        removed_by_pass3 += 1
    else:
        remaining_after3.append(combo)
elapsed3 = time.time() - t0
final_remaining_pass3 = len(remaining_after3)
print(f"Pass 3 elimination in {elapsed3:.1f}s")
print(f"  Removed by ANY of the {len(PASS3_SEEDS)} xoshiro K={K_PASS3} seeds' containment: {removed_by_pass3:,}")
print(f"  Before Pass 3: {final_remaining_pass2:,}  ->  After Pass 3: {final_remaining_pass3:,}")

# ── Pass 4: historical repeat filter, draws #1-2129 (2129 IS included) ─────
print(f"\n=== Pass 4 ===")
historical_combos = [sorted(r[1:7]) for r in hist_rows]
historical_set = set(tuple(c) for c in historical_combos)
print(f"Historical winning combos: {len(historical_set):,} (from draws #1-{TARGET_SERIAL}, includes #{TARGET_SERIAL} itself)")

remaining_after4 = []
removed_historical = []
for combo in remaining_after3:
    if combo in historical_set:
        removed_historical.append(combo)
    else:
        remaining_after4.append(combo)
final_remaining_pass4 = len(remaining_after4)
print(f"  Removed (exact match to a historical winning combo): {len(removed_historical):,}")
if removed_historical:
    print(f"  Matched: {removed_historical}")
print(f"  Before Pass 4: {final_remaining_pass3:,}  ->  After Pass 4: {final_remaining_pass4:,}")

# ── Pass 5: Worst Combo (Anti-Pick) K=15 for #TARGET_SERIAL -- page.tsx's
# actual JS methods faithfully replicated in Python, walk-forward through
# #TRAIN_THROUGH only (#TARGET_SERIAL must not leak into training). ─────────
print(f"\n=== Pass 5 ===")
nums = train_main6
n_draws = len(nums)

def solve_ls(X, y):
    cols = len(X[0])
    A = [[sum(row[i]*row[j] for row in X) for j in range(cols)] for i in range(cols)]
    bv = [sum(X[r][i]*y[r] for r in range(len(X))) for i in range(cols)]
    aug = [A[i] + [bv[i]] for i in range(cols)]
    for col in range(cols):
        max_row = col
        for r in range(col+1, cols):
            if abs(aug[r][col]) > abs(aug[max_row][col]):
                max_row = r
        aug[col], aug[max_row] = aug[max_row], aug[col]
        if abs(aug[col][col]) < 1e-12:
            continue
        for r in range(cols):
            if r == col:
                continue
            f = aug[r][col] / aug[col][col]
            for c in range(col, cols+1):
                aug[r][c] -= f * aug[col][c]
    return [0.0 if abs(aug[i][i]) < 1e-12 else aug[i][cols] / aug[i][i] for i in range(cols)]

def rf_pred_page(series):
    LAGS, N_BAGS = 8, 30
    s = series[-80:]
    if len(s) < LAGS + 5:
        return max(1, min(LOTO6_MAX, round(sum(s)/len(s))))
    X, yv = [], []
    for i in range(LAGS, len(s)):
        X.append([1] + s[i-LAGS:i])
        yv.append(s[i])
    n = len(yv)
    x_new = [1] + s[-LAGS:]
    seed = 42
    def rnd_int(maxv):
        nonlocal seed
        seed = (seed * 1664525 + 1013904223) % (2**31)
        return seed % maxv
    preds = []
    for _bag in range(N_BAGS):
        idx = [rnd_int(n) for _ in range(n)]
        Xb = [X[i] for i in idx]
        yb = [yv[i] for i in idx]
        try:
            c = solve_ls(Xb, yb)
            preds.append(sum(x_new[i]*c[i] for i in range(len(x_new))))
        except Exception:
            preds.append(sum(yv)/n)
    return max(1, min(LOTO6_MAX, round(sum(preds)/len(preds))))

def make_unique_page(seed_nums, freq):
    seen = set()
    result = []
    for n in seed_nums:
        clamped = max(1, min(LOTO6_MAX, n))
        if clamped not in seen:
            seen.add(clamped)
            result.append(clamped)
    ordered = sorted(freq.keys(), key=lambda n: -freq.get(n, 0))
    for n in ordered:
        if len(result) >= 15:
            break
        if n not in seen:
            seen.add(n)
            result.append(n)
    return sorted(result[:15])

def knn_pred_page(all_draws, k=10):
    N = LOTO6_MAX
    if len(all_draws) < k + 2:
        freq = {}
        for d in all_draws:
            for n in d:
                freq[n] = freq.get(n, 0) + 1
        return make_unique_page([], freq)
    last_draw = all_draws[-1]
    last_set = set(last_draw)
    sims = []
    for i in range(len(all_draws) - 1):
        d_set = set(all_draws[i])
        inter = len(d_set & last_set)
        union = len(d_set | last_set)
        sims.append((inter/union if union > 0 else 0, i))
    sims.sort(key=lambda x: -x[0])
    scores = [0.0]*N
    for sim, idx in sims[:k]:
        for n in all_draws[idx+1]:
            scores[n-1] += sim
    ranked = sorted(range(1, N+1), key=lambda n: -scores[n-1])
    return sorted(ranked[:15])

def apriori_pred_page(all_draws, min_sup_frac=0.05):
    N = LOTO6_MAX
    T = len(all_draws)
    if T < 2:
        return []
    sup1 = [0.0]*N
    seq1 = [0.0]*(N*N)
    pair_cnt = [0.0]*(N*N)
    seq2 = [0.0]*(N*N*N)
    for t in range(T):
        cur = all_draws[t]
        nxt = all_draws[t+1] if t < T-1 else None
        for ni in cur:
            sup1[ni-1] += 1
        for i in range(len(cur)):
            if nxt:
                for c in nxt:
                    seq1[(cur[i]-1)*N + (c-1)] += 1
            for j in range(i+1, len(cur)):
                a, b = cur[i]-1, cur[j]-1
                pair_cnt[a*N+b] += 1
                pair_cnt[b*N+a] += 1
                if nxt:
                    for c in nxt:
                        seq2[a*N*N + b*N + (c-1)] += 1
                        seq2[b*N*N + a*N + (c-1)] += 1
    min_sup = min_sup_frac * T
    last_draw = all_draws[-1]
    last_set = set(last_draw)
    score = [0.0]*N
    for ni in last_draw:
        n = ni - 1
        if sup1[n] < min_sup:
            continue
        for c in range(N):
            if (c+1) in last_set:
                continue
            score[c] += seq1[n*N+c] / max(sup1[n], 1)
    for i in range(len(last_draw)):
        for j in range(i+1, len(last_draw)):
            a, b = last_draw[i]-1, last_draw[j]-1
            p_cnt = pair_cnt[a*N+b]
            if p_cnt < min_sup:
                continue
            for c in range(N):
                if (c+1) in last_set:
                    continue
                score[c] += 2.0 * seq2[a*N*N + b*N + c] / max(p_cnt, 1)
    ranked = sorted(range(1, N+1), key=lambda n: -score[n-1])
    return sorted(ranked[:15])

freq_all = {}
for d in nums:
    for n in d:
        freq_all[n] = freq_all.get(n, 0) + 1

last43 = nums[-43:]
ma43_raw = []
for p in range(6):
    vals = [d[p] for d in last43]
    ma43_raw.append(max(1, min(LOTO6_MAX, round(sum(vals)/len(vals)))))
ma43_pick = make_unique_page(ma43_raw, freq_all)

lam = 0.95
wts_pg = [lam**(n_draws-1-i) for i in range(n_draws)]
ws_pg = sum(wts_pg)
expw_raw = []
for p in range(6):
    v = sum(wts_pg[i]*nums[i][p] for i in range(n_draws)) / ws_pg
    expw_raw.append(max(1, min(LOTO6_MAX, round(v))))
expw_pick = make_unique_page(expw_raw, freq_all)

rf_raw = [rf_pred_page([d[p] for d in nums]) for p in range(6)]
rf_pick = make_unique_page(rf_raw, freq_all)

knn_pick = knn_pred_page(nums, k=10)
apriori_pick = apriori_pred_page(nums, min_sup_frac=0.05)

print(f"MA43     (label 2):  {ma43_pick}")
print(f"ExpW     (label 3):  {expw_pick}")
print(f"RF       (label 7):  {rf_pick}")
print(f"kNN      (label 10): {knn_pick}")
print(f"Apriori  (label 12): {apriori_pick}")

worst_count = {}
for pick in (ma43_pick, expw_pick, rf_pick, knn_pick, apriori_pick):
    for n in pick:
        worst_count[n] = worst_count.get(n, 0) + 1
ranked = sorted(worst_count.items(), key=lambda item: (-item[1], item[0]))
pass5_pick = sorted(n for n, _ in ranked[:15])
print(f"\nWorst Combo (Anti-Pick) K=15 pick for draw #{TARGET_SERIAL}: {pass5_pick}")

pass5_mask = restricted_mask(set(pass5_pick))
pass5_overlap = bin(pass5_mask).count('1')
print(f"Overlap with {K_BASE}-pool: {pass5_overlap}")

t0 = time.time()
remaining_after5 = []
removed_by_pass5 = 0
for combo in remaining_after4:
    combo_mask = 0
    for n in combo:
        combo_mask |= (1 << pos_of[n])
    if (combo_mask & ~pass5_mask) & FULLBASE == 0:
        removed_by_pass5 += 1
    else:
        remaining_after5.append(combo)
elapsed5 = time.time() - t0
final_remaining = len(remaining_after5)
print(f"Pass 5 elimination in {elapsed5:.1f}s")
print(f"  Removed (contained within the Worst Combo K=15 pick): {removed_by_pass5:,}")
print(f"  Before Pass 5: {final_remaining_pass4:,}  ->  After Pass 5: {final_remaining:,}")

print(f"\nFull elimination sequence: {universe_count:,} -> {final_remaining_pass1:,} (Pass 1) -> {final_remaining_pass2:,} (Pass 2) -> "
      f"{final_remaining_pass3:,} (Pass 3) -> {final_remaining_pass4:,} (Pass 4) -> {final_remaining:,} (Pass 5)")

# ── Save outputs ──────────────────────────────────────────────────────────
meta = {
    'targetSerial': TARGET_SERIAL,
    'xo': {'seed': SEED_XO, 'k': K_XO, 'pool': xo_pool},
    'mc': {'k': K_MC, 'pool': mc_pool},
    'base': {'k': K_BASE, 'pool': base_pool},
    'methodNames': METHOD_NAMES,
    'methodBasePools': base_pools,
    'methodPicks': method_picks_19,
    'methodK': K_METHODS,
    'universeCount': universe_count,
    'removedByMethods': removed_by_methods,
    'finalRemainingPass1': final_remaining_pass1,
    'methodOverlaps': [bin(m).count('1') for m in method_masks],
    'randomK': K_RANDOM,
    'randomSeeds': [{'seed': seed, 'hit0': hit0, 'pick': pick}
                     for (seed, hit0), pick in zip(worst_seeds, random_picks)],
    'removedByRandom': removed_by_random,
    'finalRemainingPass2': final_remaining_pass2,
    'randomOverlaps': overlaps2,
    'pass3K': K_PASS3,
    'pass3Seeds': [{'seed': seed, 'pick': pick} for seed, pick in zip(PASS3_SEEDS, pass3_picks)],
    'removedByPass3': removed_by_pass3,
    'finalRemainingPass3': final_remaining_pass3,
    'pass3Overlaps': [bin(m).count('1') for m in pass3_masks],
    'historicalDrawCount': len(hist_rows),
    'historicalCombos': historical_combos,
    'removedHistorical': [list(c) for c in removed_historical],
    'finalRemainingPass4': final_remaining_pass4,
    'pass5K': 15,
    'pass5Pick': pass5_pick,
    'pass5Overlap': pass5_overlap,
    'removedByPass5': removed_by_pass5,
    'finalRemaining': final_remaining,
}
with open(META_OUT, 'w', encoding='utf-8') as f:
    json.dump(meta, f, indent=2)
print(f"\nSaved {META_OUT}")

with open(COMBOS_OUT, 'w', encoding='utf-8') as f:
    json.dump(remaining_after5, f, separators=(',', ':'))
print(f"Saved {COMBOS_OUT} ({len(remaining_after5):,} combos, {os.path.getsize(COMBOS_OUT)//1024:,} KB)")
