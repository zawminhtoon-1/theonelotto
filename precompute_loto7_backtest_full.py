"""
precompute_loto7_backtest_full.py
-----------------------------------
Full-history walk-forward backtest for Loto7, all 16 methods, over EVERY
real Loto7 draw (not just the last 100 -- see
precompute_loto7_backtest100_multik.py for that page) -- mirroring
Loto6's backtest.html architecture: each method's NATIVE K=15 candidate
pool is computed once per draw (walk-forward, no lookahead), embedded
client-side, and topKNums() (the same generic cross-method-consensus
trim/pad port used throughout this site) derives all K views live in the
browser -- no server-side recomputation needed per K. K options include
20 (this page's default/star pick), matching the multi-K page's toggle
pattern but full-history instead of last-100.

Full-history is computationally feasible for Loto7 (~690 draws total,
unlike Loto6's 2000+) -- gen_loto7_backtest.py already proves this by
walk-forwarding all 16 methods (incl. ARIMA/Random Forest/LSTM) across
the complete draw history for its own (fixed-K=7) page.

Ranking convention (same family as every hitXb-first ranking already
used across this project, e.g. Loto6's hit6b->hit6->hit5): within
each K, rank methods by highest hit7b (7-hit + either bonus number)
first, then highest hit7 (7-hit, any bonus), then hit6, then hit5,
then hit4 -- NOT average hits.

LSTM: small 60-draw bootstrap (20 epochs, same as gen_loto7_backtest.py),
then genuine online walk-forward learning from draw #1 onward (predict,
then train on the true result) -- same "if idx < SEQ: fallback" early-draw
handling as gen_loto7_backtest.py's method_lstm. The other 15 methods are
stateless, computed directly per target draw.

Output: loto7_backtest_full_data.json (consumed by
        gen_loto7_backtest_full.py to produce the actual page)
Run: python precompute_loto7_backtest_full.py
"""
import os, re, json, time, itertools, warnings
import numpy as np
import psycopg2
from collections import Counter, defaultdict

warnings.filterwarnings('ignore')

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
ENV_LOCAL = BASE + r"\.env.local"

if 'DATABASE_URL' not in os.environ:
    with open(ENV_LOCAL, encoding='utf-8') as f:
        env_text = f.read()
    m = re.search(r'DATABASE_URL=(.+)', env_text)
    os.environ['DATABASE_URL'] = m.group(1).strip()

LOTO7_MAX = 37
POOL_K = 15
K_OPTIONS = [7, 9, 13, 17, 20, 22, 25]
DEFAULT_K = 20

METHOD_NAMES = [
    "Poly deg-2", "MA-37", "Exp-weighted", "Most frequent all", "Markov chain",
    "ARIMA(2,1,0)", "Random Forest", "RL (Linear Q)", "Hidden Markov Model",
    "kNN (k=10)", "Modular Cycle (mod 37)", "Apriori Assoc Rules",
    "Monte Carlo", "Naive Bayes", "Weighted MA-37", "LSTM (seq prediction)",
]
COLORS = [
    "#38bdf8", "#818cf8", "#f472b6", "#4ade80", "#facc15", "#f87171",
    "#34d399", "#a78bfa", "#fb7185", "#f59e0b", "#10b981", "#e879f9",
    "#06b6d4", "#84cc16", "#f97316", "#e11d48",
]

print("Fetching Loto7 draws from DB...")
conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()
cur.execute("""
    SELECT draw_serial, draw_date, num1,num2,num3,num4,num5,num6,num7, bonus1, bonus2
    FROM loto7_results ORDER BY draw_serial
""")
db_rows = cur.fetchall()
conn.close()
print(f"Fetched {len(db_rows)} draws (#{db_rows[0][0]}-{db_rows[-1][0]})")

all_serials = [r[0] for r in db_rows]
all_dates   = [str(r[1]) for r in db_rows]
all_main7   = [sorted([r[2],r[3],r[4],r[5],r[6],r[7],r[8]]) for r in db_rows]
all_bonus1  = [r[9] for r in db_rows]
all_bonus2  = [r[10] for r in db_rows]
all_allnums = [sorted([r[2],r[3],r[4],r[5],r[6],r[7],r[8],r[9],r[10]]) for r in db_rows]

# ── Helpers (native pool size = POOL_K, matches gen_loto7_predictions.py) ────
def pad_to_k(base_picks, all_before_main7, k=POOL_K):
    freq = Counter(n for nums in all_before_main7 for n in nums)
    seen = set(base_picks)
    result = list(base_picks)
    for n in sorted(range(1, LOTO7_MAX + 1), key=lambda x: -freq.get(x, 0)):
        if len(result) >= k: break
        if n not in seen:
            seen.add(n); result.append(n)
    return sorted(result[:k])

def make_unique(nums, all_before_main7, k=POOL_K):
    seen = set(); result = []
    for n in nums:
        n = max(1, min(LOTO7_MAX, int(round(n))))
        if n not in seen:
            seen.add(n); result.append(n)
    return pad_to_k(result, all_before_main7, k)

# ── 16 methods (native K=15 pool, verbatim from gen_loto7_predictions.py /
# precompute_loto7_backtest100_multik.py) -- Modular Cycle uses LOTO7_MAX=37
# throughout (mod 37, NOT Loto6's mod 43 -- verified correct here). ──────────
def method_poly(train_main7, train_serials, target_serial):
    x = np.array(train_serials, dtype=float)
    base = []
    for p in range(7):
        y = np.array([d[p] for d in train_main7], dtype=float)
        coeffs = np.polyfit(x, y, 2)
        raw = np.polyval(coeffs, float(target_serial))
        base.append(max(1, min(LOTO7_MAX, int(round(raw)))))
    return make_unique(base, train_main7)

def method_ma(train_main7, window_size=37):
    window = train_main7[-window_size:] if len(train_main7) >= 1 else train_main7
    base = []
    for p in range(7):
        vals = [d[p] for d in window]
        base.append(max(1, min(LOTO7_MAX, round(sum(vals) / len(vals)))))
    return make_unique(base, train_main7)

def method_exp_weighted(train_main7):
    lam = 0.95
    n = len(train_main7)
    wts = [lam**(n-1-i) for i in range(n)]
    ws = sum(wts)
    base = []
    for p in range(7):
        vals = [train_main7[i][p] for i in range(n)]
        v = sum(wts[i]*vals[i] for i in range(n)) / ws
        base.append(max(1, min(LOTO7_MAX, int(round(v)))))
    return make_unique(base, train_main7)

def method_freq_all(train_main7, k=POOL_K):
    freq = Counter(n for draws in train_main7 for n in draws)
    # pad_to_k guards against very-early draws where fewer than k unique
    # numbers exist in history yet (e.g. idx=2 has at most 14) -- only
    # ever triggers there; a no-op once enough history has accumulated.
    return pad_to_k(sorted(n for n, _ in freq.most_common(k)), train_main7, k)

def method_markov(train_main7, k=POOL_K):
    pair_freq = defaultdict(int)
    for draws in train_main7:
        for a in draws:
            for b in draws:
                if a != b:
                    pair_freq[(a, b)] += 1
    last = set(train_main7[-1]) if train_main7 else set()
    scores = Counter()
    for src in last:
        for dst in range(1, LOTO7_MAX + 1):
            if dst not in last:
                scores[dst] += pair_freq.get((src, dst), 0)
    result = [n for n, _ in scores.most_common(k - len(last))]
    result = list(last) + result
    return pad_to_k(sorted(result[:k]), train_main7, k)

def method_arima(train_main7, k=POOL_K):
    from statsmodels.tsa.arima.model import ARIMA
    base = []
    for p in range(7):
        y = [d[p] for d in train_main7]
        try:
            if len(y) < 10:
                base.append(round(sum(y)/len(y)))
                continue
            model = ARIMA(y, order=(2,1,0))
            fit = model.fit()
            fc = fit.forecast(steps=1)
            v = max(1, min(LOTO7_MAX, int(round(float(fc[0])))))
        except Exception:
            v = max(1, min(LOTO7_MAX, round(sum(y[-10:])/10)))
        base.append(v)
    return make_unique(base, train_main7, k)

def method_random_forest(train_main7, train_serials, target_serial, k=POOL_K):
    from sklearn.ensemble import RandomForestRegressor
    base = []
    xs = np.array(train_serials, dtype=float).reshape(-1, 1)
    for p in range(7):
        y = np.array([d[p] for d in train_main7], dtype=float)
        try:
            rf = RandomForestRegressor(n_estimators=50, random_state=42, n_jobs=1)
            rf.fit(xs, y)
            pred = rf.predict([[float(target_serial)]])[0]
            v = max(1, min(LOTO7_MAX, int(round(pred))))
        except Exception:
            v = max(1, min(LOTO7_MAX, round(float(np.mean(y[-10:])))))
        base.append(v)
    return make_unique(base, train_main7, k)

def method_rl_linear_q(train_main7, k=POOL_K):
    n = len(train_main7)
    if n == 0:
        return list(range(1, k+1))
    weights = list(range(1, n+1))
    freq = defaultdict(float)
    for w, draws in zip(weights, train_main7):
        for num in draws:
            freq[num] += w
    top = sorted(range(1, LOTO7_MAX+1), key=lambda x: -freq.get(x, 0))
    return sorted(top[:k])

def method_hmm(train_main7, k=POOL_K):
    sums = [sum(d) for d in train_main7]
    if not sums:
        return list(range(1, k+1))
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
    if trans[cur_state]:
        next_state = max(trans[cur_state], key=lambda s: trans[cur_state][s])
    else:
        next_state = cur_state
    freq = Counter()
    for i, s in enumerate(states):
        if s == next_state:
            for n in train_main7[i]:
                freq[n] += 1
    if not freq:
        freq = Counter(n for d in train_main7 for n in d)
    return pad_to_k(sorted(n for n, _ in freq.most_common(k)), train_main7, k)

def method_knn(train_main7, k_nn=10, k=POOL_K):
    if len(train_main7) < k_nn + 1:
        return method_freq_all(train_main7, k)
    last = set(train_main7[-1])
    dists = []
    for i, d in enumerate(train_main7[:-1]):
        dist = len(last ^ set(d))
        dists.append((dist, i))
    dists.sort()
    neighbors = [train_main7[i] for _, i in dists[:k_nn]]
    freq = Counter(n for d in neighbors for n in d)
    return pad_to_k(sorted(n for n, _ in freq.most_common(k)), train_main7, k)

def method_modular_cycle(train_serials, train_main7, target_serial, k=POOL_K):
    target_mod = target_serial % LOTO7_MAX
    freq = Counter()
    for s, d in zip(train_serials, train_main7):
        if s % LOTO7_MAX == target_mod:
            for n in d:
                freq[n] += 1
    if not freq:
        freq = Counter(n for d in train_main7 for n in d)
    top = sorted(range(1, LOTO7_MAX+1), key=lambda x: -freq.get(x, 0))[:k]
    return sorted(top)

def method_apriori(train_main7, k=POOL_K):
    pair_freq = Counter()
    for draws in train_main7:
        for pair in itertools.combinations(draws, 2):
            pair_freq[pair] += 1
    last = set(train_main7[-1]) if train_main7 else set()
    scores = Counter()
    antecedent_counts = Counter(n for d in train_main7 for n in d)
    for src in last:
        for dst in range(1, LOTO7_MAX+1):
            if dst in last: continue
            pair = (min(src, dst), max(src, dst))
            conf = pair_freq[pair] / max(antecedent_counts[src], 1)
            scores[dst] += conf
    result = list(last)
    for n, _ in scores.most_common(k - len(last)):
        result.append(n)
    return pad_to_k(sorted(result[:k]), train_main7, k)

def method_monte_carlo(idx, train_main7, k=POOL_K, n_sim=1000):
    n = len(train_main7)
    if n == 0:
        return list(range(1, k+1))
    rng = np.random.default_rng(seed=idx)
    weights = np.arange(1, n+1, dtype=float)
    weights /= weights.sum()
    freq = Counter()
    for _ in range(n_sim):
        draw_idx = rng.choice(n, p=weights)
        for num in train_main7[draw_idx]:
            freq[num] += 1
    return pad_to_k(sorted(n for n, _ in freq.most_common(k)), train_main7, k)

def method_naive_bayes(train_main7, k=POOL_K):
    if len(train_main7) < 2:
        return method_freq_all(train_main7, k)
    last = set(train_main7[-1])
    co = defaultdict(int); prior = defaultdict(int)
    for i in range(len(train_main7) - 1):
        cur_set = set(train_main7[i]); nxt_set = set(train_main7[i + 1])
        for m in cur_set:
            prior[m] += 1
            for n in nxt_set:
                co[(m, n)] += 1
    scores = Counter()
    for n in range(1, LOTO7_MAX + 1):
        for m in last:
            if prior[m] > 0:
                scores[n] += co[(m, n)] / prior[m]
    return pad_to_k(sorted(n for n, _ in scores.most_common(k)), train_main7, k)

def method_weighted_ma37(train_main7, k=POOL_K):
    window = train_main7[-37:] if len(train_main7) >= 1 else train_main7
    n = len(window)
    wts = list(range(1, n+1))
    ws = sum(wts)
    base = []
    for p in range(7):
        vals = [window[i][p] for i in range(n)]
        v = sum(wts[i]*vals[i] for i in range(n)) / ws
        base.append(max(1, min(LOTO7_MAX, int(round(v)))))
    return make_unique(base, train_main7, k)

# ── LSTM: full sequential walk-forward online training (stateful), same
# small bootstrap + online-learning pattern as gen_loto7_backtest.py's
# method_lstm (NOT the pre-walk-then-store-last-100 pattern used by the
# 100-draw multi-K page, since here we need predictions from near the
# very start of history, not just a recent window). ─────────────────────────
SEQ, H, IN, OUT = 10, 16, 37, 37

def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -20.0, 20.0)))

class LSTM:
    def __init__(self, seed=42):
        np.random.seed(seed)
        n_xh = IN + H
        sc = np.sqrt(2.0 / (IN + H))
        self.W  = np.random.randn(4*H, n_xh) * sc
        self.b  = np.zeros(4*H); self.b[H:2*H] = 1.0
        self.Wy = np.random.randn(OUT, H) * np.sqrt(2.0 / (H + OUT))
        self.by = np.zeros(OUT)
        self.t = 0
        self.mW=np.zeros_like(self.W);  self.vW=np.zeros_like(self.W)
        self.mb=np.zeros_like(self.b);  self.vb=np.zeros_like(self.b)
        self.mWy=np.zeros_like(self.Wy); self.vWy=np.zeros_like(self.Wy)
        self.mby=np.zeros_like(self.by); self.vby=np.zeros_like(self.by)

    def forward(self, xs):
        h = np.zeros(H); c = np.zeros(H); cache = []
        for x in xs:
            xh = np.concatenate([x, h])
            z  = self.W @ xh + self.b
            ig = sigmoid(z[:H]);       fg = sigmoid(z[H:2*H])
            og = sigmoid(z[2*H:3*H]); gg = np.tanh(z[3*H:])
            cn = fg*c + ig*gg; tc = np.tanh(cn); hn = og*tc
            cache.append((x, h, c, xh, ig, fg, og, gg, cn, tc))
            h, c = hn, cn
        y = sigmoid(self.Wy @ h + self.by)
        return y, h, cache

    def train_step(self, xs, target, lr=3e-4, clip=5.0):
        y, h, cache = self.forward(xs)
        dy = y - target
        dWy = np.outer(dy, h); dby = dy.copy()
        dh = self.Wy.T @ dy; dc = np.zeros(H)
        dW = np.zeros_like(self.W); db = np.zeros_like(self.b)
        for (x,hp,cp,xh,ig,fg,og,gg,cn,tc) in reversed(cache):
            do=dh*tc; dtc=dh*og; dc_tot=dtc*(1.0-tc**2)+dc
            di=dc_tot*gg; dg=dc_tot*ig; df=dc_tot*cp; dc=dc_tot*fg
            dz=np.concatenate([di*ig*(1-ig),df*fg*(1-fg),do*og*(1-og),dg*(1-gg**2)])
            dW+=np.outer(dz,xh); db+=dz; dh=(self.W.T@dz)[IN:]
        for g in (dW,db,dWy,dby): np.clip(g,-clip,clip,out=g)
        self.t+=1; t=self.t; b1,b2,eps=0.9,0.999,1e-8
        def adam(p,g,m,v):
            m[:]=b1*m+(1-b1)*g; v[:]=b2*v+(1-b2)*g**2
            p-=lr*(m/(1-b1**t))/(np.sqrt(v/(1-b2**t))+eps)
        adam(self.W,dW,self.mW,self.vW); adam(self.b,db,self.mb,self.vb)
        adam(self.Wy,dWy,self.mWy,self.vWy); adam(self.by,dby,self.mby,self.vby)

    def predict_pool(self, xs, k=POOL_K):
        y, _, _ = self.forward(xs)
        return sorted(int(i+1) for i in np.argsort(y)[::-1][:k])

def to_vec37(nums):
    v = np.zeros(IN)
    for n in nums:
        if 1 <= n <= IN: v[n-1] = 1.0
    return v

lstm_vecs = [to_vec37(nums) for nums in all_main7]
lstm = LSTM()
WARMUP = 60  # small bootstrap; rest is genuine online walk-forward learning
print(f"\nLSTM warm-up: training on first {WARMUP} draws x 20 epochs...")
t_lstm0 = time.time()
for epoch in range(20):
    np.random.seed(epoch)
    idxs = np.random.permutation(range(SEQ, WARMUP))
    for i in idxs:
        lstm.train_step(lstm_vecs[i-SEQ:i], lstm_vecs[i])
print(f"LSTM warm-up done in {time.time()-t_lstm0:.1f}s")

def method_lstm(idx):
    """Predict draw at idx using last SEQ draws, then online-train on the
    true result -- same as gen_loto7_backtest.py's method_lstm."""
    if idx < SEQ:
        return list(range(1, POOL_K+1))
    xs = lstm_vecs[idx-SEQ:idx]
    picks = lstm.predict_pool(xs)
    lstm.train_step(xs, lstm_vecs[idx])
    return picks

# ── 16 methods, walk-forward across ALL draws (idx >= 2, matching
# gen_loto7_backtest.py's "if len(train_serials) < 2: continue"). ───────────
print(f"\nComputing 16 methods natively (K={POOL_K}) for all {len(all_serials)-2} draws (full history)...")
t0 = time.time()
DATA = []
total = len(all_serials) - 2
for i, idx in enumerate(range(2, len(all_serials)), 1):
    target_serial = all_serials[idx]
    train_serials = all_serials[:idx]
    train_main7 = all_main7[:idx]

    pools = [
        method_poly(train_main7, train_serials, target_serial),
        method_ma(train_main7),
        method_exp_weighted(train_main7),
        method_freq_all(train_main7),
        method_markov(train_main7),
        method_arima(train_main7),
        method_random_forest(train_main7, train_serials, target_serial),
        method_rl_linear_q(train_main7),
        method_hmm(train_main7),
        method_knn(train_main7),
        method_modular_cycle(train_serials, train_main7, target_serial),
        method_apriori(train_main7),
        method_monte_carlo(idx, train_main7),
        method_naive_bayes(train_main7),
        method_weighted_ma37(train_main7),
        method_lstm(idx),
    ]
    for p in pools:
        assert len(p) == POOL_K, f"pool size mismatch: {len(p)} != {POOL_K}"

    DATA.append({
        's': target_serial, 'd': all_dates[idx],
        'a': all_main7[idx], 'b1': all_bonus1[idx], 'b2': all_bonus2[idx],
        'p': pools,
    })
    if i % 20 == 0 or i == total:
        elapsed = time.time() - t0
        rate = i / elapsed
        eta = (total - i) / rate if rate > 0 else 0
        print(f"  [{i}/{total}] draw #{target_serial} elapsed={elapsed:.0f}s rate={rate:.2f} draws/s eta={eta:.0f}s", flush=True)

print(f"Done in {time.time()-t0:.1f}s")

# ── Server-side aggregate (Python reference for self-check; the page itself
# computes all K views live client-side via topKNums(), same as backtest.html).
# Tiebreak key is (-freq, n) -- ascending number on ties -- to exactly match
# JS's Object.keys(freq) behavior (integer-keyed objects always enumerate in
# ascending numeric order regardless of insertion order, unlike Python's
# Counter which preserves insertion order). Without the explicit ascending
# tiebreak here, this self-check can diverge from the live page's own
# computation whenever K is large enough that padding hits frequency ties
# (verified: at K=25 several methods differ without this fix; K=20, this
# page's default, happens to have no ties among its padding candidates so
# it was unaffected either way). ─────────────────────────────────────────────
def top_k_nums(combo, all_pools, k):
    freq = Counter()
    for pool in all_pools:
        for n in pool:
            freq[n] += 1
    if len(combo) == k:
        return sorted(combo)
    if len(combo) > k:
        return sorted(sorted(combo, key=lambda n: (-freq.get(n, 0), n))[:k])
    in_combo = set(combo)
    extra = sorted((n for n in freq if n not in in_combo), key=lambda n: (-freq.get(n, 0), n))
    if len(combo) + len(extra) < k:
        have = set(combo) | set(extra)
        for n in range(1, LOTO7_MAX + 1):
            if n not in have:
                extra.append(n)
    extra = extra[:k - len(combo)]
    return sorted(list(combo) + extra)

def compute_for_k(K):
    hit_counts = [[0]*8 for _ in range(16)]
    hit7b_counts = [0]*16
    for row in DATA:
        actual_set = set(row['a'])
        all_pools = row['p']
        for mi, pool in enumerate(all_pools):
            combo = top_k_nums(pool, all_pools, K)
            hits = len(set(combo) & actual_set)
            hit_counts[mi][min(hits, 7)] += 1
            bonus_hit = (row['b1'] in combo) or (row['b2'] in combo)
            if hits == 7 and bonus_hit:
                hit7b_counts[mi] += 1
    return hit_counts, hit7b_counts

print(f"\n=== Self-check: server-side reference computation for K={DEFAULT_K} (default/star pick) ===")
hcD, h7bD = compute_for_k(DEFAULT_K)
ranked = sorted(range(16), key=lambda mi: (-h7bD[mi], -hcD[mi][7], -hcD[mi][6], -hcD[mi][5], -hcD[mi][4]))
print(f"Rank @ K={DEFAULT_K} (hit7b -> hit7 -> hit6 -> hit5 -> hit4):")
for mi in ranked:
    print(f"  {METHOD_NAMES[mi]:24s} hit7b={h7bD[mi]} hit7={hcD[mi][7]} hit6={hcD[mi][6]} hit5={hcD[mi][5]} hit4={hcD[mi][4]}")

for K in K_OPTIONS:
    hc, h7b = compute_for_k(K)
    ranked_k = sorted(range(16), key=lambda mi: (-h7b[mi], -hc[mi][7], -hc[mi][6], -hc[mi][5], -hc[mi][4]))
    best = ranked_k[0]
    print(f"K={K}: best method = {METHOD_NAMES[best]} "
          f"(hit7b={h7b[best]} hit7={hc[best][7]} hit6={hc[best][6]} hit5={hc[best][5]} hit4={hc[best][4]})")

# ── Save JSON (DATA + method names/colors) for the HTML generator ───────────
DATA_JSON_OUT = BASE + r"\loto7_backtest_full_data.json"
with open(DATA_JSON_OUT, 'w', encoding='utf-8') as f:
    json.dump({'methods': METHOD_NAMES, 'colors': COLORS, 'kOptions': K_OPTIONS, 'defaultK': DEFAULT_K, 'data': DATA}, f, separators=(',', ':'))
print(f"\nSaved {DATA_JSON_OUT} ({os.path.getsize(DATA_JSON_OUT)//1024} KB)")
