"""
precompute_xoshiro_elim_backtest100.py
-----------------------------------------
Applies the same full 5-pass elimination methodology used on
/xoshiro_elim_2130.html (Base = Modular Cycle K=33 (walk-forward)
intersect xoshiro K=38 seed #692,809; Pass1 = 16 methods K=19;
Pass2 = top 1000 worst-coverage seed_hit_random_k17 seeds, K=15;
Pass3 = xoshiro K=21 seeds 0,1,2; Pass4 = historical repeat filter;
Pass5 = Worst Combo Anti-Pick K=15) RETROACTIVELY to each of the last
100 real draws (#2030-2129).

For every draw: every walk-forward-trained component (Modular Cycle,
the 16 methods, the Worst Combo replica) is trained ONLY on draws
strictly BEFORE that draw -- never including it. Pass 4's historical
set is likewise restricted to draws strictly before the target draw
(NOT including it, unlike the #2129 rebuild's convenience inclusion --
this is a genuine blind backtest, so including the target draw would
trivially eliminate it via exact-match and defeat the point).

For each draw, records: whether the actual winning combo was even
contained in Base (a hard ceiling -- C(28,6)/C(43,6) =~ 6.2% by pure
combinatorics, before any elimination logic runs), and if so, which
pass (if any) eliminated it, plus the after-each-pass remaining count.

Does NOT store the full remaining-combo list per draw (100 draws x up
to ~150K combos each would be far too much data) -- only aggregate
counts and the hit/elimination-pass result per draw.

Timed via a 2-draw sample first (~18s/draw average, ~30min for 100
draws) before running the full batch.

Output: xoshiro_elim_backtest100_meta.json
Run: python precompute_xoshiro_elim_backtest100.py
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
META_OUT = BASE + r"\xoshiro_elim_backtest100_meta.json"

LOTO6_MAX = 43
K_XO = 38
K_MC = 33
K_METHODS = 19
K_DEFAULT = 15
K_RANDOM = 15
N_WORST_SEEDS = 1000
RANDOM_TABLE = "seed_hit_random_k17"
K_PASS3 = 21
PASS3_SEEDS = [0, 1, 2]
SEED_XO = 692809
N_DRAWS_BACKTEST = 100

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

# ── Self-check against the verified #2129 rebuild's known-good output ───────
_check = xoshiro_predict(SEED_XO, 2129, K_XO)
_KNOWN_XO_2129 = [2,3,4,5,6,7,8,9,11,12,13,14,15,16,17,18,19,20,21,22,24,25,27,28,29,30,31,32,33,34,35,36,38,39,40,41,42,43]
assert _check == _KNOWN_XO_2129, f"Self-check FAILED: {_check}"
print("Self-check OK: xoshiro seed 692809 K=38 draw #2129 matches known-good value.")

if 'DATABASE_URL' not in os.environ:
    with open(ENV_LOCAL, encoding='utf-8') as f:
        env_text = f.read()
    m = re.search(r'DATABASE_URL=(.+)', env_text)
    os.environ['DATABASE_URL'] = m.group(1).strip()

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

def random_predict(seed, draw_serial, k):
    rng = pyrandom.Random(seed * 10_000_000 + draw_serial)
    return sorted(rng.sample(range(1, LOTO6_MAX + 1), k))

# ── Worst Combo (Anti-Pick) replica of page.tsx's actual JS methods ─────────
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
    seen = set(); result = []
    for n in seed_nums:
        clamped = max(1, min(LOTO6_MAX, n))
        if clamped not in seen:
            seen.add(clamped); result.append(clamped)
    ordered = sorted(freq.keys(), key=lambda n: -freq.get(n, 0))
    for n in ordered:
        if len(result) >= 15: break
        if n not in seen:
            seen.add(n); result.append(n)
    return sorted(result[:15])

def knn_pred_page(all_draws, k=10):
    N = LOTO6_MAX
    if len(all_draws) < k + 2:
        freq = {}
        for d in all_draws:
            for n in d: freq[n] = freq.get(n, 0) + 1
        return make_unique_page([], freq)
    last_draw = all_draws[-1]; last_set = set(last_draw)
    sims = []
    for i in range(len(all_draws) - 1):
        d_set = set(all_draws[i])
        inter = len(d_set & last_set); union = len(d_set | last_set)
        sims.append((inter/union if union > 0 else 0, i))
    sims.sort(key=lambda x: -x[0])
    scores = [0.0]*N
    for sim, idx in sims[:k]:
        for n in all_draws[idx+1]: scores[n-1] += sim
    ranked = sorted(range(1, N+1), key=lambda n: -scores[n-1])
    return sorted(ranked[:15])

def apriori_pred_page(all_draws, min_sup_frac=0.05):
    N = LOTO6_MAX; T = len(all_draws)
    if T < 2: return []
    sup1 = [0.0]*N; seq1 = [0.0]*(N*N); pair_cnt = [0.0]*(N*N); seq2 = [0.0]*(N*N*N)
    for t in range(T):
        cur = all_draws[t]; nxt = all_draws[t+1] if t < T-1 else None
        for ni in cur: sup1[ni-1] += 1
        for i in range(len(cur)):
            if nxt:
                for c in nxt: seq1[(cur[i]-1)*N + (c-1)] += 1
            for j in range(i+1, len(cur)):
                a, b = cur[i]-1, cur[j]-1
                pair_cnt[a*N+b] += 1; pair_cnt[b*N+a] += 1
                if nxt:
                    for c in nxt:
                        seq2[a*N*N + b*N + (c-1)] += 1
                        seq2[b*N*N + a*N + (c-1)] += 1
    min_sup = min_sup_frac * T
    last_draw = all_draws[-1]; last_set = set(last_draw)
    score = [0.0]*N
    for ni in last_draw:
        n = ni - 1
        if sup1[n] < min_sup: continue
        for c in range(N):
            if (c+1) in last_set: continue
            score[c] += seq1[n*N+c] / max(sup1[n], 1)
    for i in range(len(last_draw)):
        for j in range(i+1, len(last_draw)):
            a, b = last_draw[i]-1, last_draw[j]-1
            p_cnt = pair_cnt[a*N+b]
            if p_cnt < min_sup: continue
            for c in range(N):
                if (c+1) in last_set: continue
                score[c] += 2.0 * seq2[a*N*N + b*N + c] / max(p_cnt, 1)
    ranked = sorted(range(1, N+1), key=lambda n: -score[n-1])
    return sorted(ranked[:15])

def restricted_mask(target_set, pos_of):
    mask = 0
    for n in target_set:
        if n in pos_of:
            mask |= (1 << pos_of[n])
    return mask

def run_for_draw(target_serial, draw_date, actual_main6, worst_seeds_cached):
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    cur = conn.cursor()
    cur.execute("SELECT draw_serial, num1,num2,num3,num4,num5,num6, bonus FROM loto6_results "
                "WHERE draw_serial < %s ORDER BY draw_serial", (target_serial,))
    train_rows = cur.fetchall()
    conn.close()

    train_serials = [r[0] for r in train_rows]
    train_main6   = [sorted([r[1],r[2],r[3],r[4],r[5],r[6]]) for r in train_rows]
    train_allnums = [sorted([r[1],r[2],r[3],r[4],r[5],r[6],r[7]]) for r in train_rows]

    xo_pool = xoshiro_predict(SEED_XO, target_serial, K_XO)

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

    modcycle_native = base_pools[10]
    mc_pool = top_k_nums(modcycle_native, base_pools, K_MC)
    base_pool = sorted(set(mc_pool) & set(xo_pool))
    K_BASE = len(base_pool)

    actual_t = tuple(sorted(actual_main6))
    actual_set = set(actual_t)
    in_base = actual_set.issubset(set(base_pool))

    result = {
        'serial': target_serial, 'date': draw_date, 'actual': list(actual_t),
        'kBase': K_BASE, 'universe': comb(K_BASE, 6), 'inBase': in_base,
        'baseOverlap': len(actual_set & set(base_pool)),
    }

    if not in_base:
        result['outcome'] = 'never_in_base'
        return result

    method_picks_19 = [top_k_nums(pool, base_pools, K_METHODS) for pool in base_pools]
    pos_of = {n: i for i, n in enumerate(base_pool)}
    FULLBASE = (1 << K_BASE) - 1
    method_masks = [restricted_mask(set(p), pos_of) for p in method_picks_19]

    def elim_pass(remaining, masks):
        out = []
        for combo in remaining:
            combo_mask = 0
            for n in combo:
                combo_mask |= (1 << pos_of[n])
            hit = False
            for mmask in masks:
                if (combo_mask & ~mmask) & FULLBASE == 0:
                    hit = True
                    break
            if not hit:
                out.append(combo)
        return out

    universe_combos = [tuple(sorted(base_pool[p] for p in cp)) for cp in itertools.combinations(range(K_BASE), 6)]
    r1 = elim_pass(universe_combos, method_masks)
    result['after1'] = len(r1)
    if actual_t not in set(r1):
        result['outcome'] = 'eliminated_pass1'
        result['finalRemaining'] = len(r1)
        return result

    random_picks = [random_predict(seed, target_serial, K_RANDOM) for seed, _ in worst_seeds_cached]
    random_masks = [restricted_mask(set(p), pos_of) for p in random_picks]
    r2 = elim_pass(r1, random_masks)
    result['after2'] = len(r2)
    if actual_t not in set(r2):
        result['outcome'] = 'eliminated_pass2'
        result['finalRemaining'] = len(r2)
        return result

    pass3_picks = [xoshiro_predict(seed, target_serial, K_PASS3) for seed in PASS3_SEEDS]
    pass3_masks = [restricted_mask(set(p), pos_of) for p in pass3_picks]
    r3 = elim_pass(r2, pass3_masks)
    result['after3'] = len(r3)
    if actual_t not in set(r3):
        result['outcome'] = 'eliminated_pass3'
        result['finalRemaining'] = len(r3)
        return result

    historical_set = set(tuple(c) for c in train_main6)  # strictly before target -- no leakage
    r4 = [c for c in r3 if c not in historical_set]
    result['after4'] = len(r4)
    if actual_t not in set(r4):
        result['outcome'] = 'eliminated_pass4'
        result['finalRemaining'] = len(r4)
        return result

    nums = train_main6
    n_draws = len(nums)
    freq_all = {}
    for d in nums:
        for n in d: freq_all[n] = freq_all.get(n, 0) + 1
    last43 = nums[-43:]
    ma43_raw = []
    for p in range(6):
        vals = [d[p] for d in last43]
        ma43_raw.append(max(1, min(LOTO6_MAX, round(sum(vals)/len(vals)))))
    ma43_pick = make_unique_page(ma43_raw, freq_all)
    lam = 0.95
    wts_pg = [lam**(n_draws-1-i) for i in range(n_draws)]; ws_pg = sum(wts_pg)
    expw_raw = []
    for p in range(6):
        v = sum(wts_pg[i]*nums[i][p] for i in range(n_draws)) / ws_pg
        expw_raw.append(max(1, min(LOTO6_MAX, round(v))))
    expw_pick = make_unique_page(expw_raw, freq_all)
    rf_raw = [rf_pred_page([d[p] for d in nums]) for p in range(6)]
    rf_pick = make_unique_page(rf_raw, freq_all)
    knn_pick = knn_pred_page(nums, k=10)
    apriori_pick = apriori_pred_page(nums, min_sup_frac=0.05)

    worst_count = {}
    for pick in (ma43_pick, expw_pick, rf_pick, knn_pick, apriori_pick):
        for n in pick: worst_count[n] = worst_count.get(n, 0) + 1
    ranked = sorted(worst_count.items(), key=lambda item: (-item[1], item[0]))
    pass5_pick = sorted(n for n, _ in ranked[:15])
    pass5_mask = restricted_mask(set(pass5_pick), pos_of)

    r5 = []
    for combo in r4:
        combo_mask = 0
        for n in combo:
            combo_mask |= (1 << pos_of[n])
        if (combo_mask & ~pass5_mask) & FULLBASE != 0:
            r5.append(combo)
    result['after5'] = len(r5)
    result['finalRemaining'] = len(r5)
    result['outcome'] = 'survived' if actual_t in set(r5) else 'eliminated_pass5'
    return result

def main():
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    cur = conn.cursor()
    cur.execute("SELECT draw_serial, draw_date, num1,num2,num3,num4,num5,num6 FROM loto6_results "
                "ORDER BY draw_serial DESC LIMIT %s", (N_DRAWS_BACKTEST,))
    rows = cur.fetchall()
    conn.close()
    rows.sort(key=lambda r: r[0])
    print(f"Backtesting draws #{rows[0][0]}-{rows[-1][0]} ({len(rows)} draws)")

    conn2 = sqlite3.connect(DB_PATH)
    cur2 = conn2.cursor()
    cur2.execute(f"SELECT seed, hit0_count FROM {RANDOM_TABLE} ORDER BY hit0_count DESC, seed ASC LIMIT {N_WORST_SEEDS}")
    worst_seeds_cached = cur2.fetchall()
    conn2.close()
    print(f"Loaded top {len(worst_seeds_cached)} worst-coverage seeds (shared across all draws).")

    results = []
    t0 = time.time()
    for i, (serial, date, n1,n2,n3,n4,n5,n6) in enumerate(rows, 1):
        r = run_for_draw(serial, date.isoformat(), [n1,n2,n3,n4,n5,n6], worst_seeds_cached)
        results.append(r)
        elapsed = time.time() - t0
        rate = i / elapsed
        eta = (len(rows) - i) / rate if rate > 0 else 0
        print(f"[{i}/{len(rows)}] draw #{serial} ({date}): {r['outcome']} "
              f"(elapsed={elapsed:.0f}s rate={rate:.2f} draws/s eta={eta:.0f}s)", flush=True)

    elapsed_total = time.time() - t0
    print(f"\nDONE in {elapsed_total:.1f}s ({elapsed_total/60:.1f} min)")

    outcomes = Counter(r['outcome'] for r in results)
    print(f"\nOutcome summary ({len(results)} draws):")
    for k in ['never_in_base', 'eliminated_pass1', 'eliminated_pass2', 'eliminated_pass3',
              'eliminated_pass4', 'eliminated_pass5', 'survived']:
        print(f"  {k}: {outcomes.get(k, 0)}")

    meta = {
        'nDraws': len(results),
        'drawRange': [rows[0][0], rows[-1][0]],
        'nWorstSeeds': N_WORST_SEEDS,
        'kRandom': K_RANDOM,
        'kPass3': K_PASS3,
        'pass3Seeds': PASS3_SEEDS,
        'outcomeSummary': dict(outcomes),
        'results': results,
        'elapsedSeconds': elapsed_total,
    }
    with open(META_OUT, 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2)
    print(f"\nSaved {META_OUT}")

if __name__ == '__main__':
    main()
