"""
gen_miniloto_backtest.py
--------------------------
Walk-forward backtest for MiniLoto across all historical draws in
miniloto_results, implementing the full 16-method roster adapted from
Loto6/Loto7's backtests to MiniLoto's 5-from-31 + 1-bonus structure.

Each method predicts using only draws strictly before it (no lookahead).
Each method's picks are stored as a POOL of 15 candidates per draw (not
just 5) so the generated page can live-recompute hit distributions for
K=5/6/7/17/19/29 by trimming/padding that pool via cross-method consensus
-- the same topKNums()/computeForK() mechanism Loto6's public/backtest.html
uses -- instead of being locked to a single fixed K baked in at generation
time. Any K above 15 takes the pad path (each method's own 15 plus more
from cross-method consensus). At very high K (e.g. 29, just 2 short of the
full 31-number pool), a given draw's cross-method consensus pool can itself
run short of K distinct numbers -- topKNums() has a last-resort fallback
that fills any remaining slots from ALL numbers 1..31 not already picked,
in ascending order, so every combo always reaches exactly K regardless.

Also embeds the full per-draw DATA array so the page can render a Draw
Detail tab (model selector + position filters + per-draw actual-vs-
predicted breakdown), mirroring Loto6's backtest.html Draw Detail tab.

Headline metric shown: count of 5-hit / 4-hit / 3-hit draws (out of 5
possible -- MiniLoto only has 5 real winning numbers, so these bands stay
fixed regardless of which K is selected; a bigger K just gives each
method more chances to have caught them).

Output: public/miniloto_backtest.html
Run: python gen_miniloto_backtest.py
"""
import os, json, time, itertools, warnings
import numpy as np
import psycopg2
from collections import Counter, defaultdict
from math import comb

warnings.filterwarnings('ignore')

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
HTML_OUT = BASE + r"\public\miniloto_backtest.html"
DB_URL = os.environ["DATABASE_URL"]

ML_MAX = 31
POOL_SIZE = 15   # candidate pool stored per method per draw (matches Loto6's K_DEFAULT convention)
DEFAULT_K = 5    # initial displayed pick count (MiniLoto's natural pick size)

METHODS = [
    "Poly deg-2", "MA-31", "Exp-weighted", "Most frequent all", "Markov chain",
    "ARIMA(2,1,0)", "Random Forest", "RL (Linear Q)", "Hidden Markov Model",
    "kNN (k=10)", "Modular Cycle (mod 31)", "Apriori Assoc Rules",
    "Monte Carlo", "Naive Bayes", "Weighted MA-31", "LSTM (seq prediction)",
]
MSHORT = [
    "Poly-2", "MA-31", "Exp-W", "FreqAll", "Markov", "ARIMA", "RF", "RL-Q",
    "HMM", "kNN", "ModCyc", "Apriori", "MonteCar", "NaiveBay", "WMA-31", "LSTM",
]
COLORS = [
    "#38bdf8", "#818cf8", "#f472b6", "#4ade80", "#facc15", "#f87171",
    "#34d399", "#a78bfa", "#fb7185", "#f59e0b", "#10b981", "#e879f9",
    "#06b6d4", "#84cc16", "#f97316", "#e11d48",
]

# ── 1. Fetch all draws ──────────────────────────────────────────────────────
print("Fetching MiniLoto draws from DB...")
conn = psycopg2.connect(DB_URL)
cur = conn.cursor()
cur.execute("""
    SELECT draw_serial, draw_date, num1,num2,num3,num4,num5, bonus
    FROM miniloto_results ORDER BY draw_serial
""")
db_rows = cur.fetchall()
conn.close()
print(f"Fetched {len(db_rows)} draws")

all_serials = [r[0] for r in db_rows]
all_dates   = [str(r[1]) for r in db_rows]
all_main5   = [sorted([r[2],r[3],r[4],r[5],r[6]]) for r in db_rows]
all_bonus   = [r[7] for r in db_rows]

# ── Helpers ───────────────────────────────────────────────────────────────────
def pad_to_k(base_picks, all_before_main5, k=POOL_SIZE):
    freq = Counter(n for nums in all_before_main5 for n in nums)
    seen = set(base_picks)
    result = list(base_picks)
    for n in sorted(range(1, ML_MAX + 1), key=lambda x: -freq.get(x, 0)):
        if len(result) >= k:
            break
        if n not in seen:
            seen.add(n); result.append(n)
    return sorted(result[:k])

def make_unique(nums, all_before_main5, k=POOL_SIZE):
    seen = set(); result = []
    for n in nums:
        n = max(1, min(ML_MAX, int(round(n))))
        if n not in seen:
            seen.add(n); result.append(n)
    return pad_to_k(result, all_before_main5, k)

def compute_hits(picks, actual5, bonus):
    hits = len(set(picks) & set(actual5))
    bonus_hit = bonus in picks
    return hits, bonus_hit

# ── 16 prediction methods (each now returns a POOL_SIZE=15 candidate pool) ──

def method_poly(train_main5, train_serials, target_serial):
    x = np.array(train_serials, dtype=float)
    base = []
    for p in range(5):
        y = np.array([d[p] for d in train_main5], dtype=float)
        coeffs = np.polyfit(x, y, 2)
        raw = np.polyval(coeffs, float(target_serial))
        base.append(max(1, min(ML_MAX, int(round(raw)))))
    return make_unique(base, train_main5)

def method_ma(train_main5, window_size=31):
    window = train_main5[-window_size:] if len(train_main5) >= 1 else train_main5
    base = []
    for p in range(5):
        vals = [d[p] for d in window]
        base.append(max(1, min(ML_MAX, round(sum(vals) / len(vals)))))
    return make_unique(base, train_main5)

def method_exp_weighted(train_main5):
    lam = 0.95
    n = len(train_main5)
    wts = [lam**(n-1-i) for i in range(n)]
    ws = sum(wts)
    base = []
    for p in range(5):
        vals = [train_main5[i][p] for i in range(n)]
        v = sum(wts[i]*vals[i] for i in range(n)) / ws
        base.append(max(1, min(ML_MAX, int(round(v)))))
    return make_unique(base, train_main5)

def method_freq_all(train_main5, k=POOL_SIZE):
    freq = Counter(n for draws in train_main5 for n in draws)
    return sorted(n for n, _ in freq.most_common(k))

def method_markov(train_main5, k=POOL_SIZE):
    pair_freq = defaultdict(int)
    for draws in train_main5:
        for a in draws:
            for b in draws:
                if a != b:
                    pair_freq[(a, b)] += 1
    last = set(train_main5[-1]) if train_main5 else set()
    scores = Counter()
    for src in last:
        for dst in range(1, ML_MAX + 1):
            if dst not in last:
                scores[dst] += pair_freq.get((src, dst), 0)
    result = [n for n, _ in scores.most_common(k - len(last))]
    result = list(last) + result
    return pad_to_k(sorted(result[:k]), train_main5, k)

def method_arima(train_main5, k=POOL_SIZE):
    from statsmodels.tsa.arima.model import ARIMA
    base = []
    for p in range(5):
        y = [d[p] for d in train_main5]
        try:
            if len(y) < 10:
                base.append(round(sum(y)/len(y)))
                continue
            model = ARIMA(y, order=(2,1,0))
            fit = model.fit()
            fc = fit.forecast(steps=1)
            v = max(1, min(ML_MAX, int(round(float(fc[0])))))
        except Exception:
            v = max(1, min(ML_MAX, round(sum(y[-10:])/10)))
        base.append(v)
    return make_unique(base, train_main5, k)

def method_random_forest(train_main5, train_serials, target_serial, k=POOL_SIZE):
    from sklearn.ensemble import RandomForestRegressor
    base = []
    xs = np.array(train_serials, dtype=float).reshape(-1, 1)
    for p in range(5):
        y = np.array([d[p] for d in train_main5], dtype=float)
        try:
            rf = RandomForestRegressor(n_estimators=50, random_state=42, n_jobs=1)
            rf.fit(xs, y)
            pred = rf.predict([[float(target_serial)]])[0]
            v = max(1, min(ML_MAX, int(round(pred))))
        except Exception:
            v = max(1, min(ML_MAX, round(float(np.mean(y[-10:])))))
        base.append(v)
    return make_unique(base, train_main5, k)

def method_rl_linear_q(train_main5, k=POOL_SIZE):
    n = len(train_main5)
    if n == 0:
        return list(range(1, k+1))
    weights = list(range(1, n+1))
    freq = defaultdict(float)
    for w, draws in zip(weights, train_main5):
        for num in draws:
            freq[num] += w
    top = sorted(range(1, ML_MAX+1), key=lambda x: -freq.get(x, 0))
    return sorted(top[:k])

def method_hmm(train_main5, k=POOL_SIZE):
    sums = [sum(d) for d in train_main5]
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
            for n in train_main5[i]:
                freq[n] += 1
    if not freq:
        freq = Counter(n for d in train_main5 for n in d)
    return sorted(n for n, _ in freq.most_common(k))

def method_knn(train_main5, k_nn=10, k=POOL_SIZE):
    if len(train_main5) < k_nn + 1:
        return method_freq_all(train_main5, k)
    last = set(train_main5[-1])
    dists = []
    for i, d in enumerate(train_main5[:-1]):
        dist = len(last ^ set(d))
        dists.append((dist, i))
    dists.sort()
    neighbors = [train_main5[i] for _, i in dists[:k_nn]]
    freq = Counter(n for d in neighbors for n in d)
    return sorted(n for n, _ in freq.most_common(k))

def method_modular_cycle(train_serials, train_main5, target_serial, k=POOL_SIZE):
    target_mod = target_serial % ML_MAX
    freq = Counter()
    for s, d in zip(train_serials, train_main5):
        if s % ML_MAX == target_mod:
            for n in d:
                freq[n] += 1
    if not freq:
        freq = Counter(n for d in train_main5 for n in d)
    top = sorted(range(1, ML_MAX+1), key=lambda x: -freq.get(x, 0))[:k]
    return sorted(top)

def method_apriori(train_main5, k=POOL_SIZE):
    pair_freq = Counter()
    for draws in train_main5:
        for pair in itertools.combinations(draws, 2):
            pair_freq[pair] += 1
    last = set(train_main5[-1]) if train_main5 else set()
    scores = Counter()
    antecedent_counts = Counter(n for d in train_main5 for n in d)
    for src in last:
        for dst in range(1, ML_MAX+1):
            if dst in last: continue
            pair = (min(src, dst), max(src, dst))
            conf = pair_freq[pair] / max(antecedent_counts[src], 1)
            scores[dst] += conf
    result = list(last)
    for n, _ in scores.most_common(k - len(last)):
        result.append(n)
    return pad_to_k(sorted(result[:k]), train_main5, k)

def method_monte_carlo(idx, train_main5, k=POOL_SIZE, n_sim=1000):
    n = len(train_main5)
    if n == 0:
        return list(range(1, k+1))
    rng = np.random.default_rng(seed=idx)
    weights = np.arange(1, n+1, dtype=float)
    weights /= weights.sum()
    freq = Counter()
    for _ in range(n_sim):
        draw_idx = rng.choice(n, p=weights)
        for num in train_main5[draw_idx]:
            freq[num] += 1
    return sorted(n for n, _ in freq.most_common(k))

def method_naive_bayes(train_main5, k=POOL_SIZE):
    if len(train_main5) < 2:
        return method_freq_all(train_main5, k)
    last = set(train_main5[-1])
    co = defaultdict(int); prior = defaultdict(int)
    for i in range(len(train_main5) - 1):
        cur_set = set(train_main5[i]); nxt_set = set(train_main5[i + 1])
        for m in cur_set:
            prior[m] += 1
            for n in nxt_set:
                co[(m, n)] += 1
    scores = Counter()
    for n in range(1, ML_MAX + 1):
        for m in last:
            if prior[m] > 0:
                scores[n] += co[(m, n)] / prior[m]
    return sorted(n for n, _ in scores.most_common(k))

def method_weighted_ma31(train_main5, k=POOL_SIZE):
    window = train_main5[-31:] if len(train_main5) >= 1 else train_main5
    n = len(window)
    wts = list(range(1, n+1))
    ws = sum(wts)
    base = []
    for p in range(5):
        vals = [window[i][p] for i in range(n)]
        v = sum(wts[i]*vals[i] for i in range(n)) / ws
        base.append(max(1, min(ML_MAX, int(round(v)))))
    return make_unique(base, train_main5, k)

# ── LSTM (trained online, walk-forward, no separate weights file) ───────────
SEQ, H, IN, OUT = 10, 16, 31, 31

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

    def predict(self, xs, k=POOL_SIZE):
        y, _, _ = self.forward(xs)
        return sorted(int(i+1) for i in np.argsort(y)[::-1][:k])

def to_vec31(nums):
    v = np.zeros(IN)
    for n in nums:
        if 1 <= n <= IN: v[n-1] = 1.0
    return v

lstm_vecs = [to_vec31(nums) for nums in all_main5]
lstm = LSTM()
WARMUP = 60
print(f"LSTM warm-up: training on first {WARMUP} draws x 20 epochs...")
t_lstm0 = time.time()
for epoch in range(20):
    np.random.seed(epoch)
    idxs = np.random.permutation(range(SEQ, WARMUP))
    for i in idxs:
        lstm.train_step(lstm_vecs[i-SEQ:i], lstm_vecs[i])
print(f"LSTM warm-up done in {time.time()-t_lstm0:.1f}s")

def method_lstm(idx):
    if idx < SEQ:
        return list(range(1, POOL_SIZE+1))
    xs = lstm_vecs[idx-SEQ:idx]
    picks = lstm.predict(xs)
    lstm.train_step(xs, lstm_vecs[idx])
    return picks

# ── Python mirror of the page's topKNums(), used only for the console summary
def top_k_nums(pool, all_pools_this_draw, k):
    if len(pool) == k:
        return pool
    freq = Counter()
    for p in all_pools_this_draw:
        for n in p:
            freq[n] += 1
    if len(pool) > k:
        return sorted(sorted(pool, key=lambda n: -freq.get(n, 0))[:k])
    in_pool = set(pool)
    extra = sorted((n for n in freq if n not in in_pool), key=lambda n: -freq[n])
    return sorted(list(pool) + extra[:k - len(pool)])

# ── 2. Walk-forward backtest (reuse cached DATA if it matches current DB) ────
CACHE_PATH = BASE + r"\miniloto_backtest_data.json"
DATA = None
if os.path.exists(CACHE_PATH):
    with open(CACHE_PATH, encoding='utf-8') as f:
        cached = json.load(f)
    if (cached.get("methods") == METHODS
            and len(cached.get("data", [])) == len(all_serials) - 2
            and cached.get("poolSize") == POOL_SIZE):
        print(f"Reusing cached backtest data from {CACHE_PATH} ({len(cached['data'])} draws, pool size matches)")
        DATA = cached["data"]

if DATA is None:
    print(f"No usable cache -- running walk-forward backtest (16 methods, pool size {POOL_SIZE})...")
    t0 = time.time()
    DATA = []
    for idx in range(len(all_serials)):
        target_serial = all_serials[idx]
        train_serials = all_serials[:idx]
        train_main5 = all_main5[:idx]
        if len(train_serials) < 2:
            continue

        target_actual5 = all_main5[idx]
        target_bonus = all_bonus[idx]

        picks_fns = [
            lambda: method_poly(train_main5, train_serials, target_serial),
            lambda: method_ma(train_main5),
            lambda: method_exp_weighted(train_main5),
            lambda: method_freq_all(train_main5),
            lambda: method_markov(train_main5),
            lambda: method_arima(train_main5),
            lambda: method_random_forest(train_main5, train_serials, target_serial),
            lambda: method_rl_linear_q(train_main5),
            lambda: method_hmm(train_main5),
            lambda: method_knn(train_main5),
            lambda: method_modular_cycle(train_serials, train_main5, target_serial),
            lambda: method_apriori(train_main5),
            lambda: method_monte_carlo(idx, train_main5),
            lambda: method_naive_bayes(train_main5),
            lambda: method_weighted_ma31(train_main5),
            lambda: method_lstm(idx),
        ]

        preds_list = []
        for fn in picks_fns:
            picks = fn()
            hits, bonus_hit = compute_hits(picks, target_actual5, target_bonus)
            preds_list.append([picks, hits, bonus_hit])

        DATA.append({
            "s": target_serial, "d": all_dates[idx],
            "a": target_actual5, "b": target_bonus,
            "p": preds_list,
        })

        if len(DATA) % 100 == 0:
            print(f"  {len(DATA)}/{len(all_serials)-2} draws, elapsed {time.time()-t0:.0f}s")

    print(f"Backtested {len(DATA)} draws in {round(time.time()-t0,1)}s")

# ── 3. Aggregate stats at DEFAULT_K (for console summary only -- the page
#      recomputes live in JS for whatever K the user selects) ────────────────
N_METHODS = len(METHODS)
T = len(DATA)

hit_counts_default = [[0]*6 for _ in range(N_METHODS)]  # 0..5 hits
bonus_hits_default = [0]*N_METHODS
match_series_default = [[] for _ in range(N_METHODS)]

for row in DATA:
    all_pools = [pred[0] for pred in row["p"]]
    actual_set = set(row["a"])
    for mi, pred in enumerate(row["p"]):
        combo = top_k_nums(pred[0], all_pools, DEFAULT_K)
        hits = len(set(combo) & actual_set)
        hit_counts_default[mi][min(hits,5)] += 1
        if row["b"] in combo:
            bonus_hits_default[mi] += 1
        match_series_default[mi].append(hits)

avg_hits = [round(sum(match_series_default[mi]) / T, 4) for mi in range(N_METHODS)]
bonus_pct = [round(bonus_hits_default[mi] / T * 100, 1) for mi in range(N_METHODS)]

hit5 = [hit_counts_default[mi][5] for mi in range(N_METHODS)]
hit4 = [hit_counts_default[mi][4] for mi in range(N_METHODS)]
hit3 = [hit_counts_default[mi][3] for mi in range(N_METHODS)]

def hypergeom_p(k, K):
    return comb(5,k) * comb(ML_MAX-5, K-k) / comb(ML_MAX, K)

random_avg = sum(k * hypergeom_p(k, DEFAULT_K) for k in range(6))
random_bonus_pct = round(DEFAULT_K / ML_MAX * 100, 1)

print(f"\n=== Results at default K={DEFAULT_K} (live-recomputable on the page for K=5/6/7) ===")
for mi in range(N_METHODS):
    print(f"  {METHODS[mi]:24s} 5hit={hit5[mi]:3d}  4hit={hit4[mi]:3d}  3hit={hit3[mi]:3d}  avg={avg_hits[mi]:.4f}  bonus%={bonus_pct[mi]:5.1f}")
print(f"  {'Random baseline':24s} avg={random_avg:.4f}  bonus%={random_bonus_pct:5.1f}")

best_method_idx = max(range(N_METHODS), key=lambda i: (hit5[i], hit4[i], hit3[i]))
print(f"\nBest method at K={DEFAULT_K}: {METHODS[best_method_idx]} (5hit={hit5[best_method_idx]} 4hit={hit4[best_method_idx]} 3hit={hit3[best_method_idx]})")

# ── 4. Save DATA (now with 15-pick pools) for downstream use ────────────────
DATA_JSON_OUT = BASE + r"\miniloto_backtest_data.json"
with open(DATA_JSON_OUT, 'w') as f:
    json.dump({"methods": METHODS, "poolSize": POOL_SIZE, "data": DATA}, f, separators=(',',':'))
print(f"Saved {DATA_JSON_OUT}")

# ── 5. Generate HTML (live-recompute engine, mirroring Loto6's backtest.html) ─
print("\nGenerating HTML...")

data_json_str = json.dumps(DATA, separators=(',',':'))

html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>MiniLoto — Backtest Report</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
  :root {{
    --bg: #0f172a; --surface: #1e293b; --border: #334155;
    --text: #f1f5f9; --muted: #94a3b8; --accent: #38bdf8;
    --green: #4ade80; --orange: #fb923c; --red: #f87171; --yellow: #facc15;
  }}
  * {{ box-sizing: border-box; }}
  body {{ background: var(--bg); color: var(--text); font-family: system-ui,sans-serif; padding: 24px; margin: 0; }}
  h1 {{ font-size: 1.5rem; margin: 0 0 4px; }}
  .subtitle {{ color: var(--muted); font-size: .875rem; margin-bottom: 24px; }}
  .note {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
           padding: 14px 18px; font-size: .8rem; color: var(--muted); margin-bottom: 20px; line-height: 1.6; }}
  .ctrl-row {{ display: flex; gap: 10px; flex-wrap: wrap; align-items: center; margin: 0 0 20px; }}
  .pick-toggle {{ display:flex; background:var(--surface); border:1px solid var(--border); border-radius:6px; overflow:hidden; }}
  .ptbtn {{ padding:6px 14px; background:transparent; border:none; color:var(--muted); font-size:.8rem; cursor:pointer; transition:background .15s,color .15s; }}
  .ptbtn.active {{ background:var(--accent); color:#fff; }}
  .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 12px; margin-bottom: 20px; }}
  .card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 14px; }}
  .card.best {{ border-color: var(--yellow); box-shadow: 0 0 0 1px var(--yellow); }}
  .card-name {{ font-size: .75rem; color: var(--muted); text-transform: uppercase; letter-spacing: .05em; margin-bottom: 6px; }}
  .card-avg {{ font-size: 1.4rem; font-weight: 700; color: var(--accent); }}
  .card-avg .unit {{ font-size: .75rem; color: var(--muted); font-weight: 400; margin-left: 4px; }}
  .card-sub {{ font-size: .72rem; color: var(--muted); margin-top: 6px; }}
  .tabs {{ display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; }}
  .tab {{ padding: 8px 18px; border-radius: 6px; border: 1px solid var(--border);
          background: var(--surface); color: var(--muted); cursor: pointer; font-size: .875rem; }}
  .tab.active {{ background: var(--accent); color: #0f172a; border-color: var(--accent); font-weight: 600; }}
  .panel {{ display: none; }}
  .panel.active {{ display: block; }}
  .chart-wrap {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 20px; margin-bottom: 20px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: .82rem; }}
  th {{ position: sticky; top: 0; background: var(--surface); text-align: left; padding: 8px 6px;
        border-bottom: 1px solid var(--border); color: var(--muted); text-transform: uppercase;
        font-size: .68rem; letter-spacing: .05em; white-space: nowrap; z-index: 1; }}
  td {{ padding: 7px 6px; border-bottom: 1px solid var(--border); vertical-align: top; white-space: nowrap; }}
  tr:hover td {{ background: rgba(255,255,255,.04); }}
  tr.best td {{ color: var(--yellow); font-weight: 600; }}
  .baseline-row td {{ color: var(--muted); font-style: italic; }}
  /* Draw detail */
  .detail-wrap {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
                  padding: 16px; max-height: 620px; overflow-y: auto; overflow-x: auto; }}
  .balls {{ display: flex; flex-wrap: wrap; gap: 3px; }}
  .ball {{ display: inline-flex; align-items: center; justify-content: center;
           width: 26px; height: 26px; border-radius: 50%; font-size: .7rem; font-weight: 700;
           background: var(--border); color: var(--text); flex-shrink: 0; }}
  .ball.match {{ background: var(--green); color: #052e16; }}
  .ball.bonus {{ background: var(--orange); color: #431407; }}
  select.model-sel {{ padding: 6px 10px; background: var(--surface); border: 1px solid var(--border);
                       border-radius: 6px; color: var(--text); font-size: .85rem; cursor: pointer; }}
  input.pos-filter {{ width: 60px; padding: 4px 6px; background: var(--surface);
                       border: 1px solid var(--border); border-radius: 6px; color: var(--text); font-size: .8rem; }}
  .btn-clear {{ padding: 4px 10px; background: var(--surface); border: 1px solid var(--border);
                border-radius: 6px; color: var(--muted); font-size: .8rem; cursor: pointer; }}
  .sticky-cols th:nth-child(1), .sticky-cols td:nth-child(1) {{
    position: sticky; left: 0; background: var(--surface); z-index: 2; min-width: 44px; }}
  .sticky-cols th:nth-child(2), .sticky-cols td:nth-child(2) {{
    position: sticky; left: 44px; background: var(--surface); z-index: 2; min-width: 84px; }}
  .sticky-cols th:nth-child(3), .sticky-cols td:nth-child(3) {{
    position: sticky; left: 128px; background: var(--surface); z-index: 2; min-width: 170px;
    border-right: 1px solid var(--border); }}
  .scroll-hint {{ font-size:.72rem; color:#64748b; display:none; margin-left:auto; }}
</style>
</head>
<body>

<h1>MiniLoto — Backtest Report</h1>
<p class="subtitle">Walk-forward evaluation &middot; Draws #{DATA[0]['s']}&ndash;#{DATA[-1]['s']} &middot; {T} draws &middot; {N_METHODS} methods</p>

<div class="note">
  Full 16-method roster adapted from Loto6/Loto7's backtests, for MiniLoto's 5-from-31 +
  1-bonus-number structure. Each method predicts using only draws strictly before the target
  draw (no lookahead) &mdash; LSTM additionally trains online after each prediction. Each method
  stores a pool of {POOL_SIZE} ranked candidates per draw, live-trimmed/padded (by cross-method
  consensus, same mechanism as Loto6's backtest page) to whichever pick count is selected below.
  Headline metric: count of 5-hit / 4-hit / 3-hit draws (out of 5 possible) &mdash; these bands
  stay fixed regardless of K, since MiniLoto always has exactly 5 real winning numbers; a bigger
  K just gives each method more chances to have caught them.
</div>

<div class="ctrl-row">
  <span style="font-size:.8rem;color:var(--muted);">Picks per draw:</span>
  <div class="pick-toggle">
    <button class="ptbtn active" onclick="setGlobalK(5,this)">5 picks</button>
    <button class="ptbtn" onclick="setGlobalK(6,this)">6 picks</button>
    <button class="ptbtn" onclick="setGlobalK(7,this)">7 picks</button>
    <button class="ptbtn" onclick="setGlobalK(17,this)">17 picks</button>
    <button class="ptbtn" onclick="setGlobalK(19,this)">19 picks</button>
    <button class="ptbtn" onclick="setGlobalK(29,this)">29 picks</button>
  </div>
</div>

<div class="cards" id="cardsWrap"></div>

<div class="tabs">
  <button class="tab active" onclick="switchTab('dist',this)">Distribution</button>
  <button class="tab" onclick="switchTab('detail',this)">Draw Detail</button>
</div>

<div id="tab-dist" class="panel active">
  <div class="chart-wrap"><canvas id="distChart" height="110"></canvas></div>
  <div class="chart-wrap">
    <table>
      <thead>
        <tr><th>Method</th><th>5 Hits</th><th>4 Hits</th><th>3 Hits</th><th>Avg Hits</th><th>vs Random</th><th>Bonus Hit %</th></tr>
      </thead>
      <tbody id="summaryBody"></tbody>
    </table>
  </div>
</div>

<div id="tab-detail" class="panel">
  <div class="ctrl-row">
    <label style="font-size:.8rem;color:var(--muted);">Model:</label>
    <select id="modelSelect" class="model-sel" onchange="buildDetail()">
      <option value="-1">All Models (compact)</option>
'''

for mi in range(N_METHODS):
    html += f'      <option value="{mi}">{mi+1}: {METHODS[mi]}</option>\n'

html += f'''    </select>
    <span id="scrollHint" class="scroll-hint">⟵ scroll right to see all 16 models ⟶</span>
  </div>
  <div class="ctrl-row" id="posFilterRow">
    <label style="font-size:.8rem;color:var(--muted);">Filter actual by position:</label>
    <input id="f1" class="pos-filter" type="number" min="1" max="31" placeholder="P1" oninput="applyFilter()">
    <input id="f2" class="pos-filter" type="number" min="1" max="31" placeholder="P2" oninput="applyFilter()">
    <input id="f3" class="pos-filter" type="number" min="1" max="31" placeholder="P3" oninput="applyFilter()">
    <input id="f4" class="pos-filter" type="number" min="1" max="31" placeholder="P4" oninput="applyFilter()">
    <input id="f5" class="pos-filter" type="number" min="1" max="31" placeholder="P5" oninput="applyFilter()">
    <button class="btn-clear" onclick="clearFilters()">Clear</button>
    <span id="filterCount" style="font-size:.75rem;color:var(--muted);"></span>
  </div>
  <div class="detail-wrap">
    <table id="detailTable">
      <thead id="detailHead"></thead>
      <tbody id="detailBody"></tbody>
    </table>
  </div>
</div>

<script>
const METHODS = ''' + json.dumps(METHODS) + ''';
const MSHORT  = ''' + json.dumps(MSHORT) + ''';
const COLORS  = ''' + json.dumps(COLORS) + ''';
const ML_MAX  = 31;
const DATA = ''' + data_json_str + f'''
const N = DATA.length;

// Combinatorics + hypergeometric P(k matches | K picks, 5 actual, 31 total)
const C = (n,k) => {{ if(k<0||k>n) return 0; let r=1; for(let i=0;i<k;i++) r=r*(n-i)/(i+1); return r; }};
const HP = (k,K) => C(5,k)*C(ML_MAX-5,K-k)/C(ML_MAX,K);

// Return top-K numbers ranked by cross-method consensus frequency
function topKNums(pool, r, k) {{
  const freq = {{}};
  r.p.forEach(pred => pred[0].forEach(n => {{ freq[n] = (freq[n]||0)+1; }}));
  if (pool.length === k) return pool;
  if (pool.length > k) {{
    return [...pool].sort((a,b)=>(freq[b]||0)-(freq[a]||0)).slice(0,k).sort((a,b)=>a-b);
  }}
  const inPool = new Set(pool);
  let extra = Object.keys(freq)
    .map(Number)
    .filter(n => !inPool.has(n))
    .sort((a,b) => (freq[b]||0)-(freq[a]||0));
  // Last-resort fallback: if cross-method consensus doesn't have enough
  // candidates to reach k (can happen at high K, e.g. K=29 near the
  // 31-number pool limit), fill remaining slots from ANY number not
  // already included, in ascending order -- deterministic, unbiased,
  // and only ever kicks in when the primary consensus pool is exhausted.
  if (pool.length + extra.length < k) {{
    const have = new Set([...pool, ...extra]);
    for (let n = 1; n <= ML_MAX; n++) {{
      if (!have.has(n)) extra.push(n);
    }}
  }}
  extra = extra.slice(0, k - pool.length);
  return [...pool, ...extra].sort((a,b)=>a-b);
}}

function computeForK(K) {{
  const hitCounts = METHODS.map(() => [0,0,0,0,0,0]);
  const bonusCounts = new Array(METHODS.length).fill(0);
  DATA.forEach(r => {{
    const actualSet = new Set(r.a);
    r.p.forEach((pred,mi) => {{
      const combo = topKNums(pred[0], r, K);
      const hits  = combo.filter(n=>actualSet.has(n)).length;
      hitCounts[mi][Math.min(hits,5)]++;
      if (combo.includes(r.b)) bonusCounts[mi]++;
    }});
  }});
  const randAvg = [0,1,2,3,4,5].reduce((s,k) => s+k*HP(k,K), 0);
  const randBonusPct = K/ML_MAX*100;
  return {{ hitCounts, bonusCounts, randAvg, randBonusPct }};
}}

let distChart = null;
let CUR_HIT_COUNTS = null;

function buildAll(K) {{
  const {{ hitCounts, bonusCounts, randAvg, randBonusPct }} = computeForK(K);
  CUR_HIT_COUNTS = hitCounts;

  const hit5 = hitCounts.map(c => c[5]);
  const hit4 = hitCounts.map(c => c[4]);
  const hit3 = hitCounts.map(c => c[3]);
  const avgHits = hitCounts.map(c => (c.reduce((s,v,i)=>s+v*i,0)/N));
  const bonusPct = bonusCounts.map(b => b/N*100);
  const bestIdx = [...METHODS.keys()].sort((a,b) =>
    hit5[b]-hit5[a] || hit4[b]-hit4[a] || hit3[b]-hit3[a])[0];

  // Distribution chart
  if (distChart) distChart.destroy();
  distChart = new Chart(document.getElementById('distChart').getContext('2d'), {{
    type: 'bar',
    data: {{
      labels: ['0','1','2','3','4','5'],
      datasets: [
        ...METHODS.map((name,mi) => ({{
          label: name, data: hitCounts[mi],
          backgroundColor: COLORS[mi]+'bb', borderColor: COLORS[mi], borderWidth: 1
        }})),
        {{ label: 'Random baseline', data: [0,1,2,3,4,5].map(k=>HP(k,K)*N),
          type: 'line', borderColor: '#fff', borderDash: [5,3],
          borderWidth: 2, pointRadius: 0, fill: false, tension: 0 }}
      ]
    }},
    options: {{
      responsive: true,
      plugins: {{ legend: {{ labels: {{ color:'#94a3b8', boxWidth: 12, font: {{size: 10}} }} }} }},
      scales: {{
        x: {{ ticks:{{color:'#94a3b8'}}, grid:{{color:'#334155'}},
             title:{{display:true, text:'Matches (out of 5)', color:'#94a3b8'}} }},
        y: {{ ticks:{{color:'#94a3b8'}}, grid:{{color:'#334155'}},
             title:{{display:true, text:'Count', color:'#94a3b8'}} }}
      }}
    }}
  }});

  // Cards
  const cardsWrap = document.getElementById('cardsWrap');
  cardsWrap.innerHTML = METHODS.map((name,mi) => {{
    const isBest = mi === bestIdx;
    return `<div class="card${{isBest?' best':''}}">
      <div class="card-name">${{name}}${{isBest?' \u2605':''}}</div>
      <div class="card-avg">${{hit4[mi]}}<span class="unit">4-hit draws</span></div>
      <div class="card-sub">5-hit: ${{hit5[mi]}} &middot; 3-hit: ${{hit3[mi]}} &middot; Bonus hit: ${{bonusPct[mi].toFixed(1)}}%</div>
    </div>`;
  }}).join('');

  // Summary table
  const order = [...METHODS.keys()].sort((a,b) =>
    hit5[b]-hit5[a] || hit4[b]-hit4[a] || hit3[b]-hit3[a]);
  const rows = order.map(mi => {{
    const isBest = mi === bestIdx;
    const lift = (avgHits[mi]/randAvg).toFixed(2);
    return `<tr class="${{isBest?'best':''}}"><td>${{METHODS[mi]}}</td><td>${{hit5[mi]}}</td><td>${{hit4[mi]}}</td><td>${{hit3[mi]}}</td><td>${{avgHits[mi].toFixed(4)}}</td><td>${{lift}}&times;</td><td>${{bonusPct[mi].toFixed(1)}}%</td></tr>`;
  }}).join('');
  const baseline = `<tr class="baseline-row"><td>Random baseline (expected)</td><td>${{(HP(5,K)*N).toFixed(3)}}</td><td>${{(HP(4,K)*N).toFixed(2)}}</td><td>${{(HP(3,K)*N).toFixed(2)}}</td><td>${{randAvg.toFixed(4)}}</td><td>1.00&times;</td><td>${{randBonusPct.toFixed(1)}}%</td></tr>`;
  document.getElementById('summaryBody').innerHTML = rows + baseline;

  // Sync detail table
  SHOW_K = K;
  builtModel = -999;
  if (document.querySelector('#tab-detail.active')) buildDetail();
}}

let SHOW_K = ''' + str(DEFAULT_K) + f'''
function setGlobalK(k, btn) {{
  document.querySelectorAll('.pick-toggle .ptbtn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  buildAll(k);
}}

// Draw Detail
const REV_DATA = [...DATA].reverse();
let builtModel = -999;

function matchColor(m) {{
  return m>=4 ? '#4ade80' : m>=3 ? '#86efac' : m>=2 ? '#facc15' : '#94a3b8';
}}

function buildDetail() {{
  const mi = parseInt(document.getElementById('modelSelect').value);
  if (mi === builtModel) {{ applyFilter(); return; }}
  builtModel = mi;

  const head = document.getElementById('detailHead');
  const body = document.getElementById('detailBody');
  body.innerHTML = '';
  const tbl  = document.getElementById('detailTable');
  const hint = document.getElementById('scrollHint');

  if (mi === -1) {{
    tbl.classList.add('sticky-cols');
    hint.style.display = 'inline';
    head.innerHTML =
      '<tr><th>#</th><th>Date</th><th>Actual</th>' +
      MSHORT.map((s,i) =>
        '<th style="color:'+COLORS[i]+';text-align:center">'+s+
        '<br><span style="font-weight:400;font-size:.7rem;color:#64748b">'+SHOW_K+'pk</span></th>'
      ).join('') + '</tr>';
    REV_DATA.forEach(r => {{
      const tr = document.createElement('tr');
      tr.dataset.actual = JSON.stringify(r.a);
      const actualSet = new Set(r.a);
      let cells =
        '<td>'+r.s+'</td>' +
        '<td>'+(r.d ? r.d.slice(0,10) : '')+'</td>' +
        '<td><div class="balls">' +
        r.a.map(n=>'<span class="ball">'+n+'</span>').join('') +
        '<span class="ball bonus">'+r.b+'\u2605</span></div></td>';
      r.p.forEach((pred,i) => {{
        const combo = topKNums(pred[0], r, SHOW_K);
        const m = combo.filter(n=>actualSet.has(n)).length;
        const bh = combo.includes(r.b);
        cells += '<td style="text-align:center;font-weight:700;color:'+matchColor(m)+'">'+m+(bh?'\u2726':'')+'</td>';
      }});
      tr.innerHTML = cells;
      body.appendChild(tr);
    }});
  }} else {{
    tbl.classList.remove('sticky-cols');
    hint.style.display = 'none';
    head.innerHTML =
      '<tr><th>#</th><th>Date</th><th>Actual (5)</th>' +
      '<th>'+METHODS[mi]+' — '+SHOW_K+' picks</th>' +
      '<th style="text-align:center">Hits</th></tr>';
    REV_DATA.forEach(r => {{
      const tr = document.createElement('tr');
      tr.dataset.actual = JSON.stringify(r.a);
      const actualSet = new Set(r.a);
      const pred    = r.p[mi];
      const combo   = topKNums(pred[0], r, SHOW_K);
      const matched = combo.filter(n=>actualSet.has(n)).length;
      const bHit    = combo.includes(r.b);
      const predSet = new Set(combo);
      let cells =
        '<td>'+r.s+'</td>' +
        '<td>'+(r.d ? r.d.slice(0,10) : '')+'</td>' +
        '<td><div class="balls">' +
        r.a.map(n=>'<span class="ball'+(predSet.has(n)?' match':'')+'">'+n+'</span>').join('') +
        '<span class="ball'+(bHit?' bonus':'')+'">'+r.b+(bHit?'\u2605':'')+'</span></div></td>' +
        '<td><div class="balls">' +
        combo.map(n=>'<span class="ball'+(actualSet.has(n)?' match':'')+'">'+n+'</span>').join('') +
        '</div></td>' +
        '<td style="text-align:center;font-weight:700;color:'+matchColor(matched)+'">'+matched+'</td>';
      tr.innerHTML = cells;
      body.appendChild(tr);
    }});
  }}
  applyFilter();
}}

function applyFilter() {{
  const filters = [1,2,3,4,5].map(i => {{
    const v = document.getElementById('f'+i).value.trim();
    return v==='' ? null : parseInt(v);
  }});
  const rows = Array.from(document.getElementById('detailBody').rows);
  let shown = 0;
  rows.forEach(tr => {{
    const actual = JSON.parse(tr.dataset.actual);
    const sorted = [...actual].sort((a,b)=>a-b);
    const ok = filters.every((f,i) => f===null||sorted[i]===f);
    tr.style.display = ok ? '' : 'none';
    if (ok) shown++;
  }});
  const active = filters.some(f=>f!==null);
  document.getElementById('filterCount').textContent = active ? shown+' / '+rows.length+' draws' : '';
}}
function clearFilters() {{
  [1,2,3,4,5].forEach(i => document.getElementById('f'+i).value='');
  applyFilter();
}}

function switchTab(name, btn) {{
  document.querySelectorAll('.panel').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  document.getElementById('tab-'+name).classList.add('active');
  btn.classList.add('active');
  if (name==='detail' && builtModel===-999) buildDetail();
}}

// Initial build
buildAll(''' + str(DEFAULT_K) + ''');
</script>

</body>
</html>
'''

with open(HTML_OUT, 'w', encoding='utf-8') as f:
    f.write(html)
print(f"Wrote {HTML_OUT} ({len(html)//1024} KB)")
