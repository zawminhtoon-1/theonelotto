"""
append_backtest.py
------------------
Append missing draws to backtest.html DATA array.
Implements all 16 prediction methods walk-forward.
Also regenerates combo_evo_data.json and combo_evo_rounds.json.

Run: python append_backtest.py
"""
import json, re, sys, math, itertools, time, os
import numpy as np
import psycopg2
from collections import Counter, defaultdict

sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

BASE      = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
HTML_PATH = BASE + r"\public\backtest.html"
DATA_PATH = BASE + r"\public\combo_evo_data.json"
ROUNDS_PATH = BASE + r"\public\combo_evo_rounds.json"
DB_URL    = os.environ["DATABASE_URL"]
LOTO6_MAX = 43
K_DEFAULT = 15   # picks per method (except ModularCycle=28)

# ── 1. Fetch all draws from DB ─────────────────────────────────────────────────
print("Fetching draws from DB...")
conn = psycopg2.connect(DB_URL)
cur  = conn.cursor()
cur.execute(
    "SELECT draw_serial, draw_date, num1,num2,num3,num4,num5,num6,bonus "
    "FROM loto6_results ORDER BY draw_serial"
)
db_rows = cur.fetchall()
conn.close()
print(f"Fetched {len(db_rows)} draws from DB")

# Build structures
all_serials  = [r[0]                                          for r in db_rows]
all_dates    = [str(r[1])                                     for r in db_rows]
all_main6    = [sorted([r[2],r[3],r[4],r[5],r[6],r[7]])      for r in db_rows]
all_bonus    = [r[8]                                          for r in db_rows]
all_allnums  = [sorted([r[2],r[3],r[4],r[5],r[6],r[7],r[8]]) for r in db_rows]
serial_to_idx = {s: i for i, s in enumerate(all_serials)}

# ── 2. Load existing backtest.html DATA ──────────────────────────────────────
print("Loading backtest.html...")
with open(HTML_PATH, encoding='utf-8') as f:
    html = f.read()

m = re.search(r'const DATA\s*=\s*(\[)', html)
bs = m.start(1)
depth = 0; pos = bs
while pos < len(html):
    if html[pos] == '[': depth += 1
    elif html[pos] == ']':
        depth -= 1
        if depth == 0: be = pos + 1; break
    pos += 1
DATA = json.loads(html[bs:be])
existing_serials = {d['s'] for d in DATA}
print(f"Loaded DATA: {len(DATA)} entries, serials {DATA[0]['s']}–{DATA[-1]['s']}")

# Find missing draws (only those newer than the current last entry)
last_serial_in_data = max(existing_serials)
missing = [s for s in all_serials if s > last_serial_in_data]
print(f"Last serial in DATA: {last_serial_in_data}")
print(f"Missing draws to append: {missing}")
if not missing:
    print("Nothing to append. Exiting.")
    sys.exit(0)

# ── Helpers ───────────────────────────────────────────────────────────────────
def pad_to_k(base_picks, all_before_main6, k=K_DEFAULT):
    """Pad base_picks to k using frequency from all prior draws."""
    freq = Counter(n for nums in all_before_main6 for n in nums)
    seen = set(base_picks)
    result = list(base_picks)
    for n in sorted(range(1, LOTO6_MAX+1), key=lambda x: -freq.get(x,0)):
        if len(result) >= k: break
        if n not in seen:
            seen.add(n); result.append(n)
    return sorted(result[:k])

def make_unique(nums, all_before_main6, k=K_DEFAULT):
    """Dedup + clamp, then pad to k."""
    seen = set()
    result = []
    for n in nums:
        n = max(1, min(LOTO6_MAX, int(round(n))))
        if n not in seen:
            seen.add(n); result.append(n)
    return pad_to_k(result, all_before_main6, k)

def compute_hits(picks, actual6, bonus):
    hits  = len(set(picks) & set(actual6))
    bbonus = bonus in picks
    return hits, bbonus

# ── LSTM helpers ───────────────────────────────────────────────────────────────
def sigmoid(x): return 1.0 / (1.0 + np.exp(-x))
def lstm_forward(W, b, Wy, by, seq_draws):
    """
    seq_draws: list of sets of drawn numbers (most recent last)
    Returns: 43-dim probability array
    H = 16, Input = 43
    """
    H = len(by)  # 43? No, Wy is (43 x H), by is 43. H = Wy.shape[1]
    Wy_np = np.array(Wy)  # (43 x H)
    W_np  = np.array(W)   # (4H x (I+H))
    b_np  = np.array(b)   # (4H,)
    by_np = np.array(by)  # (43,)
    Hsize = Wy_np.shape[1]
    Isize = W_np.shape[1] - Hsize  # = 43

    h = np.zeros(Hsize); c = np.zeros(Hsize)
    for draw_nums in seq_draws:
        x = np.zeros(Isize)
        for n in draw_nums:
            if 1 <= n <= Isize: x[n-1] = 1.0
        concat = np.concatenate([x, h])
        gates  = W_np @ concat + b_np
        ig = sigmoid(gates[:Hsize])
        fg = sigmoid(gates[Hsize:2*Hsize])
        gg = np.tanh(gates[2*Hsize:3*Hsize])
        og = sigmoid(gates[3*Hsize:])
        c  = fg * c + ig * gg
        h  = og * np.tanh(c)
    logits = Wy_np @ h + by_np
    # softmax
    ex = np.exp(logits - logits.max())
    probs = ex / ex.sum()
    return probs

# Load LSTM weights once
with open(BASE + r"\lstm_weights.json") as f:
    _lw = json.load(f)
_LSTM_W  = _lw['W']
_LSTM_b  = _lw['b']
_LSTM_Wy = _lw['Wy']
_LSTM_by = _lw['by']

def lstm_predict(idx_before, all_allnums_list, k=K_DEFAULT):
    """Use LSTM weights, SEQ=10 draws before idx_before."""
    seq_size = 10
    start = max(0, idx_before - seq_size)
    seq = [set(all_allnums_list[i]) for i in range(start, idx_before)]
    if len(seq) == 0:
        return list(range(1, k+1))
    probs = lstm_forward(_LSTM_W, _LSTM_b, _LSTM_Wy, _LSTM_by, seq)
    top_idx = np.argsort(-probs)[:k]
    return sorted(int(i)+1 for i in top_idx)

# Load existing lstm_backtest.json by serial for quick lookup
with open(BASE + r"\lstm_backtest.json") as f:
    _lbt = json.load(f)
lstm_json_by_serial = {r['serial']: r for r in _lbt['results']}

# ── 16 prediction methods ──────────────────────────────────────────────────────
def method0_poly_full(idx, train_main6, train_serials, target_serial):
    """Poly deg-2 full history per position."""
    x = np.array(train_serials, dtype=float)
    base = []
    for p in range(6):
        y = np.array([draws[p] for draws in train_main6], dtype=float)
        coeffs = np.polyfit(x, y, 2)
        raw = np.polyval(coeffs, float(target_serial))
        base.append(max(1, min(LOTO6_MAX, int(round(raw)))))
    return make_unique(base, train_main6)

def method1_ma43(idx, train_main6):
    """Moving average last 43 draws."""
    window = train_main6[-43:] if len(train_main6) >= 1 else train_main6
    base = []
    for p in range(6):
        vals = [d[p] for d in window]
        base.append(max(1, min(LOTO6_MAX, round(sum(vals)/len(vals)))))
    return make_unique(base, train_main6)

def method2_exp_weighted(idx, train_main6):
    """Exponential-weighted average (lambda=0.95)."""
    lam = 0.95
    n   = len(train_main6)
    wts = [lam**(n-1-i) for i in range(n)]
    ws  = sum(wts)
    base = []
    for p in range(6):
        vals = [train_main6[i][p] for i in range(n)]
        v = sum(wts[i]*vals[i] for i in range(n)) / ws
        base.append(max(1, min(LOTO6_MAX, int(round(v)))))
    return make_unique(base, train_main6)

def method3_freq_all(idx, train_main6, k=K_DEFAULT):
    """Most frequent numbers in all history."""
    freq = Counter(n for draws in train_main6 for n in draws)
    return sorted(n for n, _ in freq.most_common(k))

def method4_markov(idx, train_main6, k=K_DEFAULT):
    """Markov chain: transition matrix."""
    # Build co-occurrence (which numbers appear together)
    pair_freq = defaultdict(int)
    for draws in train_main6:
        for a in draws:
            for b in draws:
                if a != b:
                    pair_freq[(a, b)] += 1
    # From last draw's numbers, score each candidate
    last = set(train_main6[-1]) if train_main6 else set()
    scores = Counter()
    for src in last:
        for dst in range(1, LOTO6_MAX+1):
            if dst not in last:
                scores[dst] += pair_freq.get((src, dst), 0)
    # Fill remaining from last draw itself
    result = [n for n, _ in scores.most_common(k - len(last))]
    result = list(last) + result
    return pad_to_k(sorted(result[:k]), train_main6, k)

def method5_arima(idx, train_main6, target_serial, k=K_DEFAULT):
    """ARIMA(2,1,0) per position."""
    from statsmodels.tsa.arima.model import ARIMA
    import warnings; warnings.filterwarnings('ignore')
    base = []
    for p in range(6):
        y = [d[p] for d in train_main6]
        try:
            if len(y) < 10:
                base.append(round(sum(y)/len(y)))
                continue
            model = ARIMA(y, order=(2,1,0))
            fit   = model.fit()
            fc    = fit.forecast(steps=1)
            v     = max(1, min(LOTO6_MAX, int(round(float(fc[0])))))
        except Exception:
            v = max(1, min(LOTO6_MAX, round(sum(y[-10:])/10)))
        base.append(v)
    return make_unique(base, train_main6, k)

def method6_random_forest(idx, train_main6, train_serials, target_serial, k=K_DEFAULT):
    """Random Forest per position."""
    from sklearn.ensemble import RandomForestRegressor
    base = []
    xs = np.array(train_serials, dtype=float).reshape(-1, 1)
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

def method7_rl_linear_q(idx, train_main6, k=K_DEFAULT):
    """RL (Linear Q-learning) approximation: recency-weighted frequency."""
    n = len(train_main6)
    if n == 0:
        return list(range(1, k+1))
    # Linear decay: most recent draw has weight n, oldest has weight 1
    weights = list(range(1, n+1))
    freq = defaultdict(float)
    for w, draws in zip(weights, train_main6):
        for num in draws:
            freq[num] += w
    top = sorted(range(1, LOTO6_MAX+1), key=lambda x: -freq.get(x, 0))
    return sorted(top[:k])

def method8_hmm(idx, train_main6, k=K_DEFAULT):
    """HMM approximation: group draws by sum quintile (state), predict from current state."""
    sums = [sum(d) for d in train_main6]
    if not sums:
        return list(range(1, k+1))
    # Quantile-based state (5 states)
    q = np.percentile(sums, [20, 40, 60, 80])
    def get_state(s):
        for i, qv in enumerate(q):
            if s <= qv: return i
        return 4
    states = [get_state(s) for s in sums]
    # Build transition counts
    trans = defaultdict(lambda: defaultdict(int))
    for i in range(len(states)-1):
        trans[states[i]][states[i+1]] += 1
    # Current state = last draw's state
    cur_state = states[-1]
    # Most likely next state
    if trans[cur_state]:
        next_state = max(trans[cur_state], key=lambda s: trans[cur_state][s])
    else:
        next_state = cur_state
    # Frequency of numbers in draws with that state
    freq = Counter()
    for i, s in enumerate(states):
        if s == next_state:
            for n in train_main6[i]:
                freq[n] += 1
    if not freq:
        freq = Counter(n for d in train_main6 for n in d)
    return sorted(n for n, _ in freq.most_common(k))

def method9_knn(idx, train_main6, k_nn=10, k=K_DEFAULT):
    """kNN: find k_nn most similar past draws, pick by freq."""
    if len(train_main6) < k_nn + 1:
        return method3_freq_all(idx, train_main6, k)
    last = set(train_main6[-1])
    # Distance = number of different balls
    dists = []
    for i, d in enumerate(train_main6[:-1]):
        dist = len(last ^ set(d))  # symmetric difference
        dists.append((dist, i))
    dists.sort()
    neighbors = [train_main6[i] for _, i in dists[:k_nn]]
    freq = Counter(n for d in neighbors for n in d)
    return sorted(n for n, _ in freq.most_common(k))

def method10_modular_cycle(idx, train_serials, train_main6, target_serial, k=28):
    """Modular Cycle: pool draws where serial%43 == target%43."""
    target_mod = target_serial % LOTO6_MAX
    freq = Counter()
    for s, d in zip(train_serials, train_main6):
        if s % LOTO6_MAX == target_mod:
            for n in d:
                freq[n] += 1
    if not freq:
        freq = Counter(n for d in train_main6 for n in d)
    top = sorted(range(1, LOTO6_MAX+1), key=lambda x: -freq.get(x, 0))[:k]
    return sorted(top)

def method11_apriori(idx, train_main6, k=K_DEFAULT):
    """Apriori association rules: frequent itemsets."""
    # Find frequent pairs
    pair_freq = Counter()
    for draws in train_main6:
        for pair in itertools.combinations(draws, 2):
            pair_freq[pair] += 1
    # From last draw, score candidates by rule confidence
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

def method12_monte_carlo(idx, train_main6, k=K_DEFAULT, n_sim=1000):
    """Monte Carlo: sample draws weighted by recency, pick top freq."""
    n = len(train_main6)
    if n == 0:
        return list(range(1, k+1))
    rng = np.random.default_rng(seed=idx)
    weights = np.arange(1, n+1, dtype=float)
    weights /= weights.sum()
    freq = Counter()
    for _ in range(n_sim):
        draw_idx = rng.choice(n, p=weights)
        for num in train_main6[draw_idx]:
            freq[num] += 1
    return sorted(n for n, _ in freq.most_common(k))

def method13_naive_bayes(idx, train_main6, k=K_DEFAULT):
    """Naive Bayes: P(n in next draw | n in last draw)."""
    if len(train_main6) < 2:
        return method3_freq_all(idx, train_main6, k)
    last = set(train_main6[-1])
    # P(n in draw_t | m in draw_t-1) for each m in last
    # count co-occurrence in consecutive draws
    co = defaultdict(int)
    prior = defaultdict(int)
    for i in range(len(train_main6)-1):
        cur_set = set(train_main6[i])
        nxt_set = set(train_main6[i+1])
        for m in cur_set:
            prior[m] += 1
            for n in nxt_set:
                co[(m, n)] += 1
    scores = Counter()
    for n in range(1, LOTO6_MAX+1):
        for m in last:
            if prior[m] > 0:
                scores[n] += co[(m, n)] / prior[m]
    return sorted(n for n, _ in scores.most_common(k))

def method14_weighted_ma43(idx, train_main6, k=K_DEFAULT):
    """Weighted MA-43: linear recency weights on last 43 draws per position."""
    window = train_main6[-43:] if len(train_main6) >= 1 else train_main6
    n = len(window)
    wts = list(range(1, n+1))  # 1,2,...,n (most recent = n)
    ws  = sum(wts)
    base = []
    for p in range(6):
        vals = [window[i][p] for i in range(n)]
        v = sum(wts[i]*vals[i] for i in range(n)) / ws
        base.append(max(1, min(LOTO6_MAX, int(round(v)))))
    return make_unique(base, train_main6, k)

def method15_lstm(idx, target_serial, train_allnums, train_main6, k=K_DEFAULT):
    """LSTM: use lstm_backtest.json if available, else run forward pass."""
    if target_serial in lstm_json_by_serial:
        raw_pred = sorted(lstm_json_by_serial[target_serial]['pred'])
        return pad_to_k(raw_pred, train_main6, k)
    # Fallback: run LSTM forward pass
    return lstm_predict(idx, train_allnums, k)

# ── 3. Generate predictions for missing draws ─────────────────────────────────
print(f"\nGenerating predictions for {len(missing)} draws...")
t0 = time.time()

new_entries = []
for target_serial in missing:
    idx = serial_to_idx[target_serial]
    target_date  = all_dates[idx]
    target_actual6 = all_main6[idx]
    target_bonus   = all_bonus[idx]

    # Walk-forward: use only draws BEFORE this one
    train_serials = all_serials[:idx]
    train_dates   = all_dates[:idx]
    train_main6_t = all_main6[:idx]
    train_allnums_t = all_allnums[:idx]

    if len(train_serials) < 2:
        print(f"  Skip s={target_serial}: not enough history")
        continue

    print(f"\n  Draw {target_serial} ({target_date}): actual={target_actual6} bonus={target_bonus}")

    preds_list = []

    # Method 0: Poly deg-2 full
    picks0 = method0_poly_full(idx, train_main6_t, train_serials, target_serial)
    h0, b0 = compute_hits(picks0, target_actual6, target_bonus)
    preds_list.append([picks0, h0, b0])
    print(f"    M0 Poly:      {picks0[:6]}... hits={h0}")

    # Method 1: MA-43
    picks1 = method1_ma43(idx, train_main6_t)
    h1, b1 = compute_hits(picks1, target_actual6, target_bonus)
    preds_list.append([picks1, h1, b1])
    print(f"    M1 MA-43:     {picks1[:6]}... hits={h1}")

    # Method 2: Exp-weighted
    picks2 = method2_exp_weighted(idx, train_main6_t)
    h2, b2 = compute_hits(picks2, target_actual6, target_bonus)
    preds_list.append([picks2, h2, b2])
    print(f"    M2 ExpW:      {picks2[:6]}... hits={h2}")

    # Method 3: Most freq all
    picks3 = method3_freq_all(idx, train_main6_t)
    h3, b3 = compute_hits(picks3, target_actual6, target_bonus)
    preds_list.append([picks3, h3, b3])
    print(f"    M3 FreqAll:   {picks3[:6]}... hits={h3}")

    # Method 4: Markov
    picks4 = method4_markov(idx, train_main6_t)
    h4, b4 = compute_hits(picks4, target_actual6, target_bonus)
    preds_list.append([picks4, h4, b4])
    print(f"    M4 Markov:    {picks4[:6]}... hits={h4}")

    # Method 5: ARIMA
    picks5 = method5_arima(idx, train_main6_t, target_serial)
    h5, b5 = compute_hits(picks5, target_actual6, target_bonus)
    preds_list.append([picks5, h5, b5])
    print(f"    M5 ARIMA:     {picks5[:6]}... hits={h5}")

    # Method 6: Random Forest
    picks6 = method6_random_forest(idx, train_main6_t, train_serials, target_serial)
    h6, b6 = compute_hits(picks6, target_actual6, target_bonus)
    preds_list.append([picks6, h6, b6])
    print(f"    M6 RF:        {picks6[:6]}... hits={h6}")

    # Method 7: RL Linear Q
    picks7 = method7_rl_linear_q(idx, train_main6_t)
    h7, b7 = compute_hits(picks7, target_actual6, target_bonus)
    preds_list.append([picks7, h7, b7])
    print(f"    M7 RL-Q:      {picks7[:6]}... hits={h7}")

    # Method 8: HMM
    picks8 = method8_hmm(idx, train_main6_t)
    h8, b8 = compute_hits(picks8, target_actual6, target_bonus)
    preds_list.append([picks8, h8, b8])
    print(f"    M8 HMM:       {picks8[:6]}... hits={h8}")

    # Method 9: kNN
    picks9 = method9_knn(idx, train_main6_t)
    h9, b9 = compute_hits(picks9, target_actual6, target_bonus)
    preds_list.append([picks9, h9, b9])
    print(f"    M9 kNN:       {picks9[:6]}... hits={h9}")

    # Method 10: Modular Cycle (28 picks)
    picks10 = method10_modular_cycle(idx, train_serials, train_main6_t, target_serial, 28)
    h10, b10 = compute_hits(picks10, target_actual6, target_bonus)
    preds_list.append([picks10, h10, b10])
    print(f"    M10 ModCyc:   {picks10[:6]}... hits={h10}")

    # Method 11: Apriori
    picks11 = method11_apriori(idx, train_main6_t)
    h11, b11 = compute_hits(picks11, target_actual6, target_bonus)
    preds_list.append([picks11, h11, b11])
    print(f"    M11 Apriori:  {picks11[:6]}... hits={h11}")

    # Method 12: Monte Carlo
    picks12 = method12_monte_carlo(idx, train_main6_t)
    h12, b12 = compute_hits(picks12, target_actual6, target_bonus)
    preds_list.append([picks12, h12, b12])
    print(f"    M12 MonteCar: {picks12[:6]}... hits={h12}")

    # Method 13: Naive Bayes
    picks13 = method13_naive_bayes(idx, train_main6_t)
    h13, b13 = compute_hits(picks13, target_actual6, target_bonus)
    preds_list.append([picks13, h13, b13])
    print(f"    M13 NaiveBay: {picks13[:6]}... hits={h13}")

    # Method 14: Weighted MA-43
    picks14 = method14_weighted_ma43(idx, train_main6_t)
    h14, b14 = compute_hits(picks14, target_actual6, target_bonus)
    preds_list.append([picks14, h14, b14])
    print(f"    M14 WMA-43:   {picks14[:6]}... hits={h14}")

    # Method 15: LSTM
    picks15 = method15_lstm(idx, target_serial, train_allnums_t, train_main6_t)
    h15, b15 = compute_hits(picks15, target_actual6, target_bonus)
    preds_list.append([picks15, h15, int(b15)])  # LSTM uses int for bonus
    print(f"    M15 LSTM:     {picks15[:6]}... hits={h15}")

    entry = {
        "s": target_serial,
        "d": target_date,
        "a": target_actual6,
        "b": target_bonus,
        "p": preds_list,
    }
    new_entries.append(entry)

print(f"\nGenerated {len(new_entries)} entries in {round(time.time()-t0, 1)}s")

# ── 4. Append to DATA and rewrite backtest.html ────────────────────────────────
DATA.extend(new_entries)
DATA.sort(key=lambda d: d['s'])

data_str = json.dumps(DATA, separators=(',', ':'))
# Replace everything from bracket start to bracket end
new_html = html[:bs] + data_str + html[be:]

with open(HTML_PATH, 'w', encoding='utf-8') as f:
    f.write(new_html)
print(f"\nWrote backtest.html ({len(new_html)//1024} KB), DATA now has {len(DATA)} entries")
print(f"Serials: {DATA[0]['s']}–{DATA[-1]['s']}")

# ── 5. Regenerate combo_evo_data.json and combo_evo_rounds.json ───────────────
print("\nRegenerating combo_evo files...")
m2 = re.search(r'const METHODS\s*=\s*(\[.*?\])', new_html, re.DOTALL)
METHODS = json.loads(m2.group(1))
N = len(METHODS); T = len(DATA)
print(f"  {T} draws, {N} methods")

picks_mat  = np.zeros((T, N, 43), dtype=np.uint8)
actual_mat = np.zeros((T, 43),    dtype=np.uint8)
serials2   = []
dates2     = []
actuals2   = []

for t, row in enumerate(DATA):
    serials2.append(row['s'])
    dates2.append(row.get('d', str(row['s']))[:10])
    actual_balls = sorted(row['a'])
    actuals2.append(actual_balls)
    for n in actual_balls: actual_mat[t, n-1] = 1
    for mi, pred in enumerate(row['p']):
        if mi < N:
            for n in pred[0]: picks_mat[t, mi, n-1] = 1

all_freq = picks_mat.sum(axis=1).astype(np.float32)

def topk_mask(method_idx, K):
    score = np.where(picks_mat[:, method_idx, :], all_freq, -np.inf)
    order = np.argsort(-score, axis=1)[:, :K]
    mask  = np.zeros((T, 43), dtype=np.uint8)
    rows_ = np.repeat(np.arange(T), K)
    mask[rows_, order.ravel()] = 1
    return mask

ALL_KS = [6, 8, 10, 15, 20]
print(f"  Precomputing top-K masks for K={ALL_KS}...")
t0 = time.time()
topk_cache = {}
for K in ALL_KS:
    for mi in range(N):
        topk_cache[(mi, K)] = topk_mask(mi, K)
print(f"  done in {round(time.time()-t0,1)}s")

all_combos = list(itertools.combinations(range(N), 2))
print(f"  Running {len(all_combos)} combos × {len(ALL_KS)} K values...")
t0 = time.time()

combo_results = {}
for m0, m1 in all_combos:
    key = f"{m0},{m1}"
    combo_results[key] = {}
    for K in ALL_KS:
        union_mask = np.clip(topk_cache[(m0, K)] + topk_cache[(m1, K)], 0, 1)
        union_size = union_mask.sum(axis=1)
        hits = (union_mask * actual_mat).sum(axis=1)
        arr  = np.array(hits)
        dist = np.bincount(arr.clip(0, 6), minlength=7).tolist()
        combo_results[key][str(K)] = {
            'hits':      hits.tolist(),
            'dist':      dist,
            'avg':       round(float(arr.mean()), 4),
            'fp':        int((arr >= 4).sum()),
            'z0':        dist[0],
            'z6':        dist[6],
            'union_avg': round(float(union_size.mean()), 2),
        }
print(f"  done in {round(time.time()-t0,1)}s")

out = {
    'T': T, 'N': N, 'methods': METHODS,
    'combos': combo_results,
    'dates': dates2,
    'formula': 'union_topk',
}
with open(DATA_PATH, 'w') as f:
    json.dump(out, f, separators=(',', ':'))
print(f"  Saved combo_evo_data.json ({len(json.dumps(out))//1024} KB)")

rounds_picks = []
for t, row in enumerate(DATA):
    method_picks = []
    for mi in range(N):
        balls = sorted([n+1 for n in range(43) if picks_mat[t, mi, n]])
        method_picks.append(balls)
    rounds_picks.append(method_picks)

rounds_out = {
    'dates': dates2, 'serials': serials2,
    'actuals': actuals2, 'picks': rounds_picks,
}
with open(ROUNDS_PATH, 'w') as f:
    json.dump(rounds_out, f, separators=(',', ':'))
print(f"  Saved combo_evo_rounds.json ({len(json.dumps(rounds_out))//1024} KB)")

print("\nALL DONE")
