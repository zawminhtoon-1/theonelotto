"""
precompute_xoshiro_elim_2128.py
-----------------------------------
Precomputes everything the new "Xoshiro + 16-Method Elimination" page
needs for draw #2128 (the next upcoming Loto6 draw):

  Block 1: xoshiro256** K=33 pick, seed #118,590 (best K=33 seed, full
           0-1,000,000 scan) -- 33-number pool, universe = C(33,6).
  Block 2: xoshiro256** K=26 pick, seed #13,117 (worst K=26 seed, 0-100,000
           scan).
  Block 3: each of the 16 prediction methods' K=21 pick for #2128,
           computed the same way append_backtest.py computes them
           (walk-forward, trained on ALL real draws through #2127), then
           normalized to exactly K=21 via the SAME cross-method-consensus
           trim/pad algorithm as backtest.html's topKNums() JS function
           (mirrored here in Python since #2128 has no stored per-draw
           pool to feed the live JS version, which only operates on
           already-generated historical rows).

Elimination: starting from Block 1's C(33,6) = 1,107,568 six-number
combinations, remove any combo fully contained within Block 2's 26-set,
then remove any combo fully contained within ANY individual one of the
16 methods' K=21 sets (union of the 16 individual removal sets). Uses
33-bit integer bitmasks for the containment checks (fast: combo removed
by set S iff combo_mask & ~S_mask_restricted_to_pool == 0).

Self-checks the xoshiro implementation against known-good values (from
prior chat lookups) before trusting Block 1/2's output.

Outputs:
  xoshiro_elim_2128_meta.json   -- small: blocks, method picks, counts
  public/xoshiro_elim_2128_combos.json -- large: remaining combo list
                                          (fetched client-side, not inlined)

Run: python precompute_xoshiro_elim_2128.py
"""
import json, os, re, itertools, time, warnings
import numpy as np
import psycopg2
from collections import Counter, defaultdict

warnings.filterwarnings('ignore')

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
ENV_LOCAL = BASE + r"\.env.local"
META_OUT = BASE + r"\xoshiro_elim_2128_meta.json"
COMBOS_OUT = BASE + r"\public\xoshiro_elim_2128_combos.json"

LOTO6_MAX = 43
TARGET_SERIAL = 2128
K_METHODS = 21   # normalized K for all 16 methods
K_DEFAULT = 15   # native K most methods produce before normalization

SEED_BLOCK1, K_BLOCK1 = 118590, 33   # best K=33 seed (0-1,000,000 scan)
SEED_BLOCK2, K_BLOCK2 = 13117, 26    # worst K=26 seed (0-100,000 scan)

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

# ── Self-check against known-good chat-computed values before trusting ──────
_KNOWN_BLOCK1 = [1,2,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,20,22,23,24,25,26,29,31,33,34,35,37,38,40,41,43]
_check1 = xoshiro_predict(SEED_BLOCK1, TARGET_SERIAL, K_BLOCK1)
assert _check1 == _KNOWN_BLOCK1, f"Block1 self-check FAILED: {_check1}"
print(f"Self-check: Block1 (seed={SEED_BLOCK1}, K={K_BLOCK1}, draw={TARGET_SERIAL}) matches known-good value. OK.")

block1_pool33 = xoshiro_predict(SEED_BLOCK1, TARGET_SERIAL, K_BLOCK1)
block2_pool26 = xoshiro_predict(SEED_BLOCK2, TARGET_SERIAL, K_BLOCK2)
print(f"Block1 (33): {block1_pool33}")
print(f"Block2 (26): {block2_pool26}")

# ── Fetch all real draws through #2127 ───────────────────────────────────────
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

train_serials = all_serials      # ALL real draws are "before" #2128
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

print(f"\nComputing 16 methods' base pools for draw #{TARGET_SERIAL} (trained on all {len(train_main6)} real draws)...")
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

# ── Normalize each method's base pool to K=21 via the SAME cross-method-
# consensus trim/pad algorithm as backtest.html's topKNums() JS function ────
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

method_picks_21 = [top_k_nums(pool, base_pools, K_METHODS) for pool in base_pools]
print(f"\nNormalized to K={K_METHODS} via cross-method-consensus (topKNums-equivalent):")
for name, pool in zip(METHOD_NAMES, method_picks_21):
    assert len(pool) == K_METHODS, f"{name}: got {len(pool)} numbers, expected {K_METHODS}"
    print(f"  {name:24s}: {pool}")

# ── Combinatorial elimination (33-bit bitmasks over pool33 positions) ───────
print(f"\n=== Elimination ===")
pos_of = {n: i for i, n in enumerate(block1_pool33)}  # number -> bit position (0-32)

def restricted_mask(target_set):
    """Bitmask over pool33 positions: which pool33 numbers are in target_set."""
    mask = 0
    for n in target_set:
        if n in pos_of:
            mask |= (1 << pos_of[n])
    return mask

set26 = set(block2_pool26)
mask26 = restricted_mask(set26)
overlap26 = bin(mask26).count('1')
print(f"Block2 (26-set) overlap with Block1's 33-pool: {overlap26} numbers")

method_masks = []
for name, pool in zip(METHOD_NAMES, method_picks_21):
    mset = set(pool)
    mmask = restricted_mask(mset)
    overlap = bin(mmask).count('1')
    method_masks.append(mmask)
    print(f"  {name:24s} overlap with 33-pool: {overlap} numbers")

universe_count = 1
from math import comb
universe_count = comb(33, 6)
print(f"\nUniverse: C(33,6) = {universe_count:,}")

t0 = time.time()
FULL33 = (1 << 33) - 1
remaining = []
removed_by_block2 = 0
removed_by_methods = 0
positions = list(range(33))

for combo_positions in itertools.combinations(positions, 6):
    combo_mask = 0
    for p in combo_positions:
        combo_mask |= (1 << p)
    # Removed by Block2?
    if (combo_mask & ~mask26) & FULL33 == 0:
        removed_by_block2 += 1
        continue
    # Removed by any of the 16 methods?
    removed = False
    for mmask in method_masks:
        if (combo_mask & ~mmask) & FULL33 == 0:
            removed = True
            break
    if removed:
        removed_by_methods += 1
        continue
    remaining.append(tuple(sorted(block1_pool33[p] for p in combo_positions)))

elapsed = time.time() - t0
after_block2 = universe_count - removed_by_block2
final_remaining = len(remaining)
print(f"Enumerated {universe_count:,} combos in {elapsed:.1f}s")
print(f"  Removed by Block2 (26-set) containment: {removed_by_block2:,}")
print(f"  After step 1: {after_block2:,}")
print(f"  Removed by ANY of the 16 methods' K=21 containment: {removed_by_methods:,}")
print(f"  Final remaining: {final_remaining:,}")
print(f"\nElimination sequence: {universe_count:,} -> {after_block2:,} -> {final_remaining:,} remaining")

# ── Save outputs ──────────────────────────────────────────────────────────
meta = {
    'targetSerial': TARGET_SERIAL,
    'block1': {'seed': SEED_BLOCK1, 'k': K_BLOCK1, 'pool': block1_pool33},
    'block2': {'seed': SEED_BLOCK2, 'k': K_BLOCK2, 'pool': block2_pool26},
    'methodNames': METHOD_NAMES,
    'methodBasePools': base_pools,
    'methodPicks21': method_picks_21,
    'universeCount': universe_count,
    'removedByBlock2': removed_by_block2,
    'afterBlock2': after_block2,
    'removedByMethods': removed_by_methods,
    'finalRemaining': final_remaining,
    'block2Overlap': overlap26,
    'methodOverlaps': [bin(m).count('1') for m in method_masks],
}
with open(META_OUT, 'w', encoding='utf-8') as f:
    json.dump(meta, f, indent=2)
print(f"\nSaved {META_OUT}")

with open(COMBOS_OUT, 'w', encoding='utf-8') as f:
    json.dump(remaining, f, separators=(',', ':'))
print(f"Saved {COMBOS_OUT} ({len(remaining):,} combos, {os.path.getsize(COMBOS_OUT)//1024:,} KB)")
