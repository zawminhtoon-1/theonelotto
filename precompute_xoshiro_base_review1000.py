"""
precompute_xoshiro_base_review1000.py
-----------------------------------------
Narrower cousin of precompute_xoshiro_elim_backtest100.py: instead of
running the full 5-pass elimination funnel retroactively against the
last 1000 real draws, this stops at the Base-pool-construction stage
(Base = Modular Cycle K=33 (walk-forward) intersect xoshiro K=38 seed
#692,809 -- same Base used on the #2130-style elimination pages) and
adds generation-order detail: for each of the target draw's 6 actual
numbers, WHERE (if at all) that number fell in each of the two inputs'
own raw pick sequence, before either gets sorted.

"Generation order" for xoshiro K=38 is the order the partial
Fisher-Yates shuffle finalizes each position (i=n-1 first, down to
i=n-1-38), same convention as xoshiro_seed_scan_k38.html and
precompute_xoshiro_elim_2132.py.

"Generation order" for Modular Cycle K=33 is: the mod-43 cycle's own
frequency ranking at native K=28 (highest match-count first, ties
broken by ascending number), FOLLOWED BY the padding numbers
top_k_nums adds to reach K=33 (highest cross-method-consensus
frequency first) -- i.e. the order the K=33 pick was actually built
in, before its own final sort(). Exact same two helper functions as
precompute_xoshiro_elim_2132.py (modular_cycle_ranked,
top_k_nums_extend_ordered).

Every walk-forward-trained component (Modular Cycle, all 16 methods
feeding the cross-method-consensus frequency table used to pad Base to
K=33) is trained ONLY on draws strictly BEFORE the target draw -- no
draw ever sees its own future.

Does NOT run the elimination passes at all (that's
xoshiro_elim_backtest100.html's job) -- just Base construction, so
this runs much faster (~1-2s/draw instead of ~18s/draw, since it skips
enumerating C(28,6)-ish combo universes entirely).

Output: xoshiro_base_review1000_meta.json
Run: python precompute_xoshiro_base_review1000.py
"""
import json, os, re, time, warnings
import numpy as np
import psycopg2
from collections import Counter, defaultdict
from math import comb

warnings.filterwarnings('ignore')

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
ENV_LOCAL = BASE + r"\.env.local"
META_OUT = BASE + r"\xoshiro_base_review1000_meta.json"

LOTO6_MAX = 43
K_XO = 38
K_MC = 33
K_MC_NATIVE = 28
SEED_XO = 692809
N_DRAWS_REVIEW = 1000

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
    each position (i=n-1 first, down to i=n-k last), NOT sorted."""
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

# ── Self-check against the verified #2129 rebuild's known-good output ───────
_KNOWN_XO_2129 = [2,3,4,5,6,7,8,9,11,12,13,14,15,16,17,18,19,20,21,22,24,25,27,28,29,30,31,32,33,34,35,36,38,39,40,41,42,43]
_check = xoshiro_predict(SEED_XO, 2129, K_XO)
assert _check == _KNOWN_XO_2129, f"Self-check FAILED: {_check}"
print(f"Self-check OK: xoshiro seed {SEED_XO} K={K_XO} draw #2129 matches known-good value.")

if 'DATABASE_URL' not in os.environ:
    with open(ENV_LOCAL, encoding='utf-8') as f:
        env_text = f.read()
    m = re.search(r'DATABASE_URL=(.+)', env_text)
    os.environ['DATABASE_URL'] = m.group(1).strip()

# ── 16-method scaffolding (verbatim from precompute_xoshiro_elim_backtest100.py) ──
def pad_to_k(base_picks, all_before_main6, k=15):
    freq = Counter(n for nums in all_before_main6 for n in nums)
    seen = set(base_picks)
    result = list(base_picks)
    for n in sorted(range(1, LOTO6_MAX+1), key=lambda x: -freq.get(x,0)):
        if len(result) >= k: break
        if n not in seen:
            seen.add(n); result.append(n)
    return sorted(result[:k])

def make_unique(nums, all_before_main6, k=15):
    seen = set()
    result = []
    for n in nums:
        n = max(1, min(LOTO6_MAX, int(round(n))))
        if n not in seen:
            seen.add(n); result.append(n)
    return pad_to_k(result, all_before_main6, k)

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

def lstm_predict(all_allnums_list, k=15):
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
def method3_freq_all(train_main6, k=15):
    freq = Counter(n for draws in train_main6 for n in draws)
    return sorted(n for n, _ in freq.most_common(k))
def method4_markov(train_main6, k=15):
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
def method5_arima(train_main6, target_serial, k=15):
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
def method6_random_forest(train_main6, train_serials, target_serial, k=15):
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
def method7_rl_linear_q(train_main6, k=15):
    n = len(train_main6)
    if n == 0: return list(range(1, k+1))
    weights = list(range(1, n+1)); freq = defaultdict(float)
    for w, draws in zip(weights, train_main6):
        for num in draws:
            freq[num] += w
    top = sorted(range(1, LOTO6_MAX+1), key=lambda x: -freq.get(x, 0))
    return sorted(top[:k])
def method8_hmm(train_main6, k=15):
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
def method9_knn(train_main6, k_nn=10, k=15):
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
def modular_cycle_ranked(train_serials, train_main6, target_serial, k=K_MC_NATIVE):
    """Generation order -- the mod-43 cycle's own frequency ranking (highest
    count first, ties broken by ascending number), NOT sorted ascending."""
    target_mod = target_serial % LOTO6_MAX
    freq = Counter()
    for s, d in zip(train_serials, train_main6):
        if s % LOTO6_MAX == target_mod:
            for n in d: freq[n] += 1
    if not freq: freq = Counter(n for d in train_main6 for n in d)
    return sorted(range(1, LOTO6_MAX+1), key=lambda x: -freq.get(x, 0))[:k]
def method10_modular_cycle(train_serials, train_main6, target_serial, k=K_MC_NATIVE):
    return sorted(modular_cycle_ranked(train_serials, train_main6, target_serial, k))
def method11_apriori(train_main6, k=15):
    import itertools
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
def method12_monte_carlo(train_main6, k=15, n_sim=1000, seed_idx=0):
    n = len(train_main6)
    if n == 0: return list(range(1, k+1))
    rng = np.random.default_rng(seed=seed_idx)
    weights = np.arange(1, n+1, dtype=float); weights /= weights.sum()
    freq = Counter()
    for _ in range(n_sim):
        draw_idx = rng.choice(n, p=weights)
        for num in train_main6[draw_idx]: freq[num] += 1
    return sorted(n for n, _ in freq.most_common(k))
def method13_naive_bayes(train_main6, k=15):
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
def method14_weighted_ma43(train_main6, k=15):
    window = train_main6[-43:] if len(train_main6) >= 1 else train_main6
    n = len(window); wts = list(range(1, n+1)); ws = sum(wts)
    base = []
    for p in range(6):
        vals = [window[i][p] for i in range(n)]
        v = sum(wts[i]*vals[i] for i in range(n)) / ws
        base.append(max(1, min(LOTO6_MAX, int(round(v)))))
    return make_unique(base, train_main6, k)
def method15_lstm(target_serial, train_allnums, train_main6, k=15):
    if target_serial in lstm_json_by_serial:
        raw_pred = sorted(lstm_json_by_serial[target_serial]['pred'])
        return pad_to_k(raw_pred, train_main6, k)
    return lstm_predict(train_allnums, k)

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
    preserves generation order instead of the final sort()."""
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

def compute_base(target_serial):
    """Shared Base-construction step (Modular Cycle K=33 ∩ xoshiro K=38 seed
    #692,809), walk-forward trained on draws strictly before target_serial.
    Used both for real historical draws (run_for_draw) and for the current
    upcoming/not-yet-drawn draw (compute_upcoming) -- for the latter,
    target_serial is simply latest_real_serial + 1, so "strictly before"
    naturally becomes "all real draws to date"."""
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    cur = conn.cursor()
    cur.execute("SELECT draw_serial, num1,num2,num3,num4,num5,num6, bonus FROM loto6_results "
                "WHERE draw_serial < %s ORDER BY draw_serial", (target_serial,))
    train_rows = cur.fetchall()
    conn.close()

    train_serials = [r[0] for r in train_rows]
    train_main6   = [sorted([r[1],r[2],r[3],r[4],r[5],r[6]]) for r in train_rows]
    train_allnums = [sorted([r[1],r[2],r[3],r[4],r[5],r[6],r[7]]) for r in train_rows]

    xo_pool_ordered = xoshiro_predict_raw(SEED_XO, target_serial, K_XO)
    xo_pool = sorted(xo_pool_ordered)

    base_pools = [
        method0_poly_full(train_main6, train_serials, target_serial),
        method1_ma43(train_main6),
        method2_exp_weighted(train_main6),
        method3_freq_all(train_main6),
        method4_markov(train_main6),
        method5_arima(train_main6, target_serial),
        method6_random_forest(train_main6, train_serials, target_serial),
        method7_rl_linear_q(train_main6),
        method8_hmm(train_main6),
        method9_knn(train_main6),
        method10_modular_cycle(train_serials, train_main6, target_serial),
        method11_apriori(train_main6),
        method12_monte_carlo(train_main6, seed_idx=len(train_main6)),
        method13_naive_bayes(train_main6),
        method14_weighted_ma43(train_main6),
        method15_lstm(target_serial, train_allnums, train_main6),
    ]

    mc_native_ordered = modular_cycle_ranked(train_serials, train_main6, target_serial, k=K_MC_NATIVE)
    mc_pool_ordered = top_k_nums_extend_ordered(mc_native_ordered, base_pools, K_MC)
    mc_pool = sorted(mc_pool_ordered)
    assert mc_pool == top_k_nums(base_pools[10], base_pools, K_MC), \
        f"#{target_serial}: mc_pool_ordered mismatch with top_k_nums reference"

    base_pool = sorted(set(mc_pool) & set(xo_pool))

    return {
        'kBase': len(base_pool),
        'basePool': base_pool,
        'mcPoolOrdered': mc_pool_ordered,
        'xoPoolOrdered': xo_pool_ordered,
    }

def run_for_draw(target_serial, draw_date, actual_main6):
    b = compute_base(target_serial)
    mc_pool_ordered = b['mcPoolOrdered']
    xo_pool_ordered = b['xoPoolOrdered']
    base_pool = b['basePool']
    K_BASE = b['kBase']

    actual_t = tuple(sorted(actual_main6))
    actual_set = set(actual_t)
    base_overlap = len(actual_set & set(base_pool))
    in_base = base_overlap == 6

    mc_index = {n: i + 1 for i, n in enumerate(mc_pool_ordered)}   # 1-indexed
    xo_index = {n: i + 1 for i, n in enumerate(xo_pool_ordered)}   # 1-indexed

    per_number = [
        {'n': n, 'mcIdx': mc_index.get(n), 'xoIdx': xo_index.get(n)}
        for n in actual_t
    ]

    return {
        'serial': target_serial,
        'date': draw_date,
        'actual': list(actual_t),
        'kBase': K_BASE,
        'universe': comb(K_BASE, 6),
        'baseOverlap': base_overlap,
        'inBase': in_base,
        'perNumber': per_number,
        'mcPoolOrdered': mc_pool_ordered,
        'xoPoolOrdered': xo_pool_ordered,
    }

def compute_upcoming(target_serial):
    """The current upcoming/not-yet-drawn draw -- Base pool only, no actual
    result to compare against yet."""
    b = compute_base(target_serial)
    return {
        'serial': target_serial,
        'kBase': b['kBase'],
        'basePool': b['basePool'],
        'mcPoolOrdered': b['mcPoolOrdered'],
        'xoPoolOrdered': b['xoPoolOrdered'],
    }

def main():
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    cur = conn.cursor()
    cur.execute("SELECT draw_serial, draw_date, num1,num2,num3,num4,num5,num6 FROM loto6_results "
                "ORDER BY draw_serial DESC LIMIT %s", (N_DRAWS_REVIEW,))
    rows = cur.fetchall()
    conn.close()
    rows.sort(key=lambda r: r[0])
    print(f"Reviewing Base construction for draws #{rows[0][0]}-{rows[-1][0]} ({len(rows)} draws)")

    results = []
    t0 = time.time()
    for i, (serial, date, n1,n2,n3,n4,n5,n6) in enumerate(rows, 1):
        r = run_for_draw(serial, date.isoformat(), [n1,n2,n3,n4,n5,n6])
        results.append(r)
        elapsed = time.time() - t0
        rate = i / elapsed
        eta = (len(rows) - i) / rate if rate > 0 else 0
        print(f"[{i}/{len(rows)}] draw #{serial} ({date}): baseOverlap={r['baseOverlap']}/6 kBase={r['kBase']} "
              f"(elapsed={elapsed:.0f}s rate={rate:.2f} draws/s eta={eta:.0f}s)", flush=True)

    elapsed_total = time.time() - t0
    print(f"\nDONE in {elapsed_total:.1f}s ({elapsed_total/60:.1f} min)")

    all6 = sum(1 for r in results if r['baseOverlap'] == 6)
    zero = sum(1 for r in results if r['baseOverlap'] == 0)
    partial = len(results) - all6 - zero
    overlap_hist = Counter(r['baseOverlap'] for r in results)
    print(f"\nCoverage summary ({len(results)} draws):")
    print(f"  All 6 in Base:  {all6}")
    print(f"  Partial (1-5):  {partial}")
    print(f"  Zero in Base:   {zero}")

    upcoming_serial = rows[-1][0] + 1
    print(f"\nComputing Base for upcoming draw #{upcoming_serial} (not yet drawn)...")
    upcoming = compute_upcoming(upcoming_serial)
    print(f"  Base (K={upcoming['kBase']}): {upcoming['basePool']}")

    meta = {
        'nDraws': len(results),
        'drawRange': [rows[0][0], rows[-1][0]],
        'kXo': K_XO,
        'kMc': K_MC,
        'kMcNative': K_MC_NATIVE,
        'seedXo': SEED_XO,
        'all6Count': all6,
        'partialCount': partial,
        'zeroCount': zero,
        'overlapHistogram': {str(k): v for k, v in sorted(overlap_hist.items())},
        'results': results,
        'elapsedSeconds': elapsed_total,
        'upcoming': upcoming,
    }
    with open(META_OUT, 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2)
    print(f"\nSaved {META_OUT}")

if __name__ == '__main__':
    main()
