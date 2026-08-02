"""
gen_loto7_predictions.py
--------------------------
Computes each of the 16 methods' top-15 candidate pool for the NEXT (not yet
drawn) Loto7 draw, using ALL historical draws as training data. This is a
separate, one-shot computation from gen_loto7_backtest.py's walk-forward
evaluation (which is fixed at K=7 for strict historical scoring) -- here we
want a larger ranked pool per method so the Predictions page's pick-count
toggle (7/9/11) can show genuinely different subsets, same mechanic as
Loto6's PredictionsView.tsx (trim each method's pool to top-K by cross-model
consensus).

Output: public/loto7_predictions_data.json
Run: python gen_loto7_predictions.py
"""
import os, json, itertools, warnings
import numpy as np
import psycopg2
from collections import Counter, defaultdict

warnings.filterwarnings('ignore')

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
OUT_PATH = BASE + r"\public\loto7_predictions_data.json"
DB_URL = os.environ["DATABASE_URL"]

LOTO7_MAX = 37
POOL_K = 15  # candidate pool size per method (matches Loto6's K_DEFAULT convention)

METHODS = [
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
conn = psycopg2.connect(DB_URL)
cur = conn.cursor()
cur.execute("""
    SELECT draw_serial, draw_date, num1,num2,num3,num4,num5,num6,num7, bonus1, bonus2
    FROM loto7_results ORDER BY draw_serial
""")
db_rows = cur.fetchall()
conn.close()
print(f"Fetched {len(db_rows)} draws")

all_serials = [r[0] for r in db_rows]
all_main7   = [sorted([r[2],r[3],r[4],r[5],r[6],r[7],r[8]]) for r in db_rows]

train_serials = all_serials
train_main7 = all_main7
target_serial = all_serials[-1] + 1  # next, un-drawn serial

# ── Helpers ───────────────────────────────────────────────────────────────────
def pad_to_k(base_picks, all_before_main7, k=POOL_K):
    freq = Counter(n for nums in all_before_main7 for n in nums)
    seen = set(base_picks)
    result = list(base_picks)
    for n in sorted(range(1, LOTO7_MAX + 1), key=lambda x: -freq.get(x, 0)):
        if len(result) >= k:
            break
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

# ── 16 methods, pool size = POOL_K ───────────────────────────────────────────
def method_poly():
    x = np.array(train_serials, dtype=float)
    base = []
    for p in range(7):
        y = np.array([d[p] for d in train_main7], dtype=float)
        coeffs = np.polyfit(x, y, 2)
        raw = np.polyval(coeffs, float(target_serial))
        base.append(max(1, min(LOTO7_MAX, int(round(raw)))))
    return make_unique(base, train_main7)

def method_ma(window_size=37):
    window = train_main7[-window_size:]
    base = []
    for p in range(7):
        vals = [d[p] for d in window]
        base.append(max(1, min(LOTO7_MAX, round(sum(vals) / len(vals)))))
    return make_unique(base, train_main7)

def method_exp_weighted():
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

def method_freq_all(k=POOL_K):
    freq = Counter(n for draws in train_main7 for n in draws)
    return sorted(n for n, _ in freq.most_common(k))

def method_markov(k=POOL_K):
    pair_freq = defaultdict(int)
    for draws in train_main7:
        for a in draws:
            for b in draws:
                if a != b:
                    pair_freq[(a, b)] += 1
    last = set(train_main7[-1])
    scores = Counter()
    for src in last:
        for dst in range(1, LOTO7_MAX + 1):
            if dst not in last:
                scores[dst] += pair_freq.get((src, dst), 0)
    result = [n for n, _ in scores.most_common(k - len(last))]
    result = list(last) + result
    return pad_to_k(sorted(result[:k]), train_main7, k)

def method_arima(k=POOL_K):
    from statsmodels.tsa.arima.model import ARIMA
    base = []
    for p in range(7):
        y = [d[p] for d in train_main7]
        try:
            model = ARIMA(y, order=(2,1,0))
            fit = model.fit()
            fc = fit.forecast(steps=1)
            v = max(1, min(LOTO7_MAX, int(round(float(fc[0])))))
        except Exception:
            v = max(1, min(LOTO7_MAX, round(sum(y[-10:])/10)))
        base.append(v)
    return make_unique(base, train_main7, k)

def method_random_forest(k=POOL_K):
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

def method_rl_linear_q(k=POOL_K):
    n = len(train_main7)
    weights = list(range(1, n+1))
    freq = defaultdict(float)
    for w, draws in zip(weights, train_main7):
        for num in draws:
            freq[num] += w
    top = sorted(range(1, LOTO7_MAX+1), key=lambda x: -freq.get(x, 0))
    return sorted(top[:k])

def method_hmm(k=POOL_K):
    sums = [sum(d) for d in train_main7]
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
    return sorted(n for n, _ in freq.most_common(k))

def method_knn(k_nn=10, k=POOL_K):
    last = set(train_main7[-1])
    dists = []
    for i, d in enumerate(train_main7[:-1]):
        dist = len(last ^ set(d))
        dists.append((dist, i))
    dists.sort()
    neighbors = [train_main7[i] for _, i in dists[:k_nn]]
    freq = Counter(n for d in neighbors for n in d)
    return sorted(n for n, _ in freq.most_common(k))

def method_modular_cycle(k=POOL_K):
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

def method_apriori(k=POOL_K):
    pair_freq = Counter()
    for draws in train_main7:
        for pair in itertools.combinations(draws, 2):
            pair_freq[pair] += 1
    last = set(train_main7[-1])
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

def method_monte_carlo(k=POOL_K, n_sim=2000):
    n = len(train_main7)
    rng = np.random.default_rng(seed=n)
    weights = np.arange(1, n+1, dtype=float)
    weights /= weights.sum()
    freq = Counter()
    for _ in range(n_sim):
        draw_idx = rng.choice(n, p=weights)
        for num in train_main7[draw_idx]:
            freq[num] += 1
    return sorted(n for n, _ in freq.most_common(k))

def method_naive_bayes(k=POOL_K):
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
    return sorted(n for n, _ in scores.most_common(k))

def method_weighted_ma37(k=POOL_K):
    window = train_main7[-37:]
    n = len(window)
    wts = list(range(1, n+1))
    ws = sum(wts)
    base = []
    for p in range(7):
        vals = [window[i][p] for i in range(n)]
        v = sum(wts[i]*vals[i] for i in range(n)) / ws
        base.append(max(1, min(LOTO7_MAX, int(round(v)))))
    return make_unique(base, train_main7, k)

# ── LSTM: quick online warm-up across full history, then predict pool ───────
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

def method_lstm():
    vecs = [to_vec37(nums) for nums in train_main7]
    m = LSTM()
    print("  LSTM: online training across full history...")
    for i in range(SEQ, len(vecs)):
        m.train_step(vecs[i-SEQ:i], vecs[i])
    return m.predict_pool(vecs[-SEQ:])

# ── Compute all 16 predictions ────────────────────────────────────────────────
print(f"Computing predictions for draw #{target_serial} (pool size {POOL_K})...")
labeled_fns = [
    method_poly, method_ma, method_exp_weighted, method_freq_all, method_markov,
    method_arima, method_random_forest, method_rl_linear_q, method_hmm,
    method_knn, method_modular_cycle, method_apriori, method_monte_carlo,
    method_naive_bayes, method_weighted_ma37, method_lstm,
]

combos = []
for mi, fn in enumerate(labeled_fns):
    print(f"  [{mi+1}/16] {METHODS[mi]}...")
    numbers = fn()
    combos.append({
        "label": str(mi + 1),
        "color": COLORS[mi],
        "method": METHODS[mi],
        "numbers": numbers,
    })

out = {
    "nextSerial": target_serial,
    "drawCount": len(all_serials),
    "combos": combos,
}
with open(OUT_PATH, 'w', encoding='utf-8') as f:
    json.dump(out, f, separators=(',',':'))
print(f"\nSaved {OUT_PATH}")
for c in combos:
    print(f"  {c['label']:>2} {c['method']:22s} {c['numbers']}")
