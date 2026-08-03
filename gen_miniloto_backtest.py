"""
gen_miniloto_backtest.py
--------------------------
Walk-forward backtest for MiniLoto across all historical draws in
miniloto_results, implementing the full 16-method roster adapted from
Loto6/Loto7's backtests to MiniLoto's 5-from-31 + 1-bonus structure.

Each method predicts 5 numbers per draw using ONLY draws strictly before it
(no lookahead). Headline metric: count of 5-hit / 4-hit / 3-hit draws (the
game only has 5 numbers total, so these are the top three meaningful bands,
same idea as Loto7's 6/5/4 but shifted down since MiniLoto's max is 5).

Output: public/miniloto_backtest.html
Run: python gen_miniloto_backtest.py
"""
import os, json, time, itertools, warnings
import numpy as np
import psycopg2
from collections import Counter, defaultdict

warnings.filterwarnings('ignore')

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
HTML_OUT = BASE + r"\public\miniloto_backtest.html"
DB_URL = os.environ["DATABASE_URL"]

ML_MAX = 31
K = 5  # fixed pick count for all methods (MiniLoto's natural pick size)

METHODS = [
    "Poly deg-2", "MA-31", "Exp-weighted", "Most frequent all", "Markov chain",
    "ARIMA(2,1,0)", "Random Forest", "RL (Linear Q)", "Hidden Markov Model",
    "kNN (k=10)", "Modular Cycle (mod 31)", "Apriori Assoc Rules",
    "Monte Carlo", "Naive Bayes", "Weighted MA-31", "LSTM (seq prediction)",
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
def pad_to_k(base_picks, all_before_main5, k=K):
    freq = Counter(n for nums in all_before_main5 for n in nums)
    seen = set(base_picks)
    result = list(base_picks)
    for n in sorted(range(1, ML_MAX + 1), key=lambda x: -freq.get(x, 0)):
        if len(result) >= k:
            break
        if n not in seen:
            seen.add(n); result.append(n)
    return sorted(result[:k])

def make_unique(nums, all_before_main5, k=K):
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

# ── 16 prediction methods (5 positions instead of Loto7's 7) ────────────────

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

def method_freq_all(train_main5, k=K):
    freq = Counter(n for draws in train_main5 for n in draws)
    return sorted(n for n, _ in freq.most_common(k))

def method_markov(train_main5, k=K):
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

def method_arima(train_main5, k=K):
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

def method_random_forest(train_main5, train_serials, target_serial, k=K):
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

def method_rl_linear_q(train_main5, k=K):
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

def method_hmm(train_main5, k=K):
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

def method_knn(train_main5, k_nn=10, k=K):
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

def method_modular_cycle(train_serials, train_main5, target_serial, k=K):
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

def method_apriori(train_main5, k=K):
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

def method_monte_carlo(idx, train_main5, k=K, n_sim=1000):
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

def method_naive_bayes(train_main5, k=K):
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

def method_weighted_ma31(train_main5, k=K):
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
SEQ, H, IN, OUT, N_PICKS = 10, 16, 31, 31, 5

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

    def predict(self, xs, k=N_PICKS):
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
        return list(range(1, N_PICKS+1))
    xs = lstm_vecs[idx-SEQ:idx]
    picks = lstm.predict(xs)
    lstm.train_step(xs, lstm_vecs[idx])
    return picks

# ── 2. Walk-forward backtest (reuse cached DATA if it matches current DB) ────
CACHE_PATH = BASE + r"\miniloto_backtest_data.json"
DATA = None
if os.path.exists(CACHE_PATH):
    with open(CACHE_PATH, encoding='utf-8') as f:
        cached = json.load(f)
    if cached.get("methods") == METHODS and len(cached.get("data", [])) == len(all_serials) - 2:
        print(f"Reusing cached backtest data from {CACHE_PATH} ({len(cached['data'])} draws, methods match)")
        DATA = cached["data"]

if DATA is None:
    print("No usable cache -- running walk-forward backtest (16 methods)...")
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

# ── 3. Aggregate stats ────────────────────────────────────────────────────────
N_METHODS = len(METHODS)
hit_counts = [[0]*6 for _ in range(N_METHODS)]  # 0..5 hits
bonus_hits = [0]*N_METHODS
match_series = [[] for _ in range(N_METHODS)]

for row in DATA:
    for mi, (picks, hits, bonus_hit) in enumerate(row["p"]):
        hit_counts[mi][min(hits,5)] += 1
        if bonus_hit:
            bonus_hits[mi] += 1
        match_series[mi].append(hits)

T = len(DATA)
avg_hits = [round(sum(match_series[mi]) / T, 4) for mi in range(N_METHODS)]
bonus_pct = [round(bonus_hits[mi] / T * 100, 1) for mi in range(N_METHODS)]
best_hits = [max(match_series[mi]) for mi in range(N_METHODS)]

# Headline metric: count of 5-hit / 4-hit / 3-hit draws per method
hit5 = [hit_counts[mi][5] for mi in range(N_METHODS)]
hit4 = [hit_counts[mi][4] for mi in range(N_METHODS)]
hit3 = [hit_counts[mi][3] for mi in range(N_METHODS)]

random_avg = K * 5 / ML_MAX
from math import comb
random_bonus_pct = round((1 - comb(ML_MAX-1, K) / comb(ML_MAX, K)) * 100, 1)

def hypergeom_p(k):
    return comb(5,k) * comb(ML_MAX-5, K-k) / comb(ML_MAX, K)

random_hit5 = round(hypergeom_p(5) * T, 3)
random_hit4 = round(hypergeom_p(4) * T, 2)
random_hit3 = round(hypergeom_p(3) * T, 2)

print("\n=== Results ===")
for mi in range(N_METHODS):
    print(f"  {METHODS[mi]:24s} 5hit={hit5[mi]:3d}  4hit={hit4[mi]:3d}  3hit={hit3[mi]:3d}  avg={avg_hits[mi]:.4f}  bonus%={bonus_pct[mi]:5.1f}")
print(f"  {'Random baseline':24s} 5hit={random_hit5:6.3f}  4hit={random_hit4:5.2f}  3hit={random_hit3:5.2f}  avg={random_avg:.4f}  bonus%={random_bonus_pct:5.1f}")

best_method_idx = max(range(N_METHODS), key=lambda i: (hit5[i], hit4[i], hit3[i]))
print(f"\nBest method: {METHODS[best_method_idx]} (5hit={hit5[best_method_idx]} 4hit={hit4[best_method_idx]} 3hit={hit3[best_method_idx]})")

# ── 4. Save DATA for downstream use (Best Combo search, predictions, etc.) ───
DATA_JSON_OUT = BASE + r"\miniloto_backtest_data.json"
with open(DATA_JSON_OUT, 'w') as f:
    json.dump({"methods": METHODS, "data": DATA}, f, separators=(',',':'))
print(f"Saved {DATA_JSON_OUT}")

# ── 5. Generate HTML ──────────────────────────────────────────────────────────
print("\nGenerating HTML...")

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
           padding: 14px 18px; font-size: .8rem; color: var(--muted); margin-bottom: 24px; line-height: 1.6; }}
  .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 12px; margin-bottom: 24px; }}
  .card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
           padding: 14px; }}
  .card.best {{ border-color: var(--yellow); box-shadow: 0 0 0 1px var(--yellow); }}
  .card-name {{ font-size: .75rem; color: var(--muted); text-transform: uppercase; letter-spacing: .05em; margin-bottom: 6px; }}
  .card-avg {{ font-size: 1.4rem; font-weight: 700; color: var(--accent); }}
  .card-avg .unit {{ font-size: .75rem; color: var(--muted); font-weight: 400; margin-left: 4px; }}
  .card-sub {{ font-size: .72rem; color: var(--muted); margin-top: 6px; }}
  .chart-wrap {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
                 padding: 20px; margin-bottom: 24px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: .85rem; }}
  th {{ text-align: left; padding: 10px 8px; border-bottom: 1px solid var(--border); color: var(--muted);
        text-transform: uppercase; font-size: .7rem; letter-spacing: .05em; }}
  td {{ padding: 10px 8px; border-bottom: 1px solid var(--border); }}
  tr.best td {{ color: var(--yellow); font-weight: 600; }}
  .baseline-row td {{ color: var(--muted); font-style: italic; }}
</style>
</head>
<body>

<h1>MiniLoto — Backtest Report</h1>
<p class="subtitle">Walk-forward evaluation &middot; Draws #{DATA[0]['s']}&ndash;#{DATA[-1]['s']} &middot; {T} draws &middot; {N_METHODS} methods &middot; 5 picks each</p>

<div class="note">
  Full 16-method roster adapted from Loto6/Loto7's backtests, for MiniLoto's 5-from-31 +
  1-bonus-number structure. Each method predicts using only draws strictly before the target
  draw (no lookahead) &mdash; LSTM additionally trains online after each prediction. Fixed at
  K=5 picks for all methods (MiniLoto's natural pick size). Headline metric: count of 5-hit /
  4-hit / 3-hit draws (out of 5 possible) per method across all {T} backtested draws &mdash;
  the top three meaningful bands for a 5-number game.
</div>

<div class="cards">
'''

for mi in range(N_METHODS):
    is_best = mi == best_method_idx
    html += f'''  <div class="card{' best' if is_best else ''}" data-mi="{mi}">
    <div class="card-name">{METHODS[mi]}{' ★' if is_best else ''}</div>
    <div class="card-avg">{hit4[mi]}<span class="unit">4-hit draws</span></div>
    <div class="card-sub">5-hit: {hit5[mi]} &middot; 3-hit: {hit3[mi]} &middot; Bonus hit: {bonus_pct[mi]}%</div>
  </div>
'''

html += '''</div>

<div class="chart-wrap"><canvas id="distChart" height="110"></canvas></div>

<div class="chart-wrap">
<table>
  <thead>
    <tr><th>Method</th><th>5 Hits</th><th>4 Hits</th><th>3 Hits</th><th>Avg Hits</th><th>vs Random</th><th>Bonus Hit %</th></tr>
  </thead>
  <tbody>
'''

order = sorted(range(N_METHODS), key=lambda i: (-hit5[i], -hit4[i], -hit3[i]))
for mi in order:
    is_best = mi == best_method_idx
    lift = round(avg_hits[mi] / random_avg, 2)
    html += f'''    <tr class="{'best' if is_best else ''}"><td>{METHODS[mi]}</td><td>{hit5[mi]}</td><td>{hit4[mi]}</td><td>{hit3[mi]}</td><td>{avg_hits[mi]}</td><td>{lift}&times;</td><td>{bonus_pct[mi]}%</td></tr>
'''

html += f'''    <tr class="baseline-row"><td>Random baseline (expected)</td><td>{random_hit5}</td><td>{random_hit4}</td><td>{random_hit3}</td><td>{random_avg:.4f}</td><td>1.00&times;</td><td>{random_bonus_pct}%</td></tr>
  </tbody>
</table>
</div>

<script>
const METHODS = {json.dumps(METHODS)};
const COLORS  = {json.dumps(COLORS)};
const HIT_COUNTS = {json.dumps(hit_counts)};

const HP = (k) => {{
  const C = (n,r) => {{ if(r<0||r>n) return 0; let x=1; for(let i=0;i<r;i++) x=x*(n-i)/(i+1); return x; }};
  return C(5,k)*C(26,5-k)/C(31,5);
}};
const randomDist = [0,1,2,3,4,5].map(k => HP(k)*{T});

new Chart(document.getElementById('distChart').getContext('2d'), {{
  type: 'bar',
  data: {{
    labels: ['0','1','2','3','4','5'],
    datasets: [
      ...METHODS.map((name,mi) => ({{
        label: name, data: HIT_COUNTS[mi],
        backgroundColor: COLORS[mi]+'bb', borderColor: COLORS[mi], borderWidth: 1
      }})),
      {{ label: 'Random baseline', data: randomDist,
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
</script>

</body>
</html>
'''

with open(HTML_OUT, 'w', encoding='utf-8') as f:
    f.write(html)
print(f"Wrote {HTML_OUT} ({len(html)//1024} KB)")
