"""
New formula:
  For a 2-method combo at K:
  - rank each method's 15 stored picks by all-16-method consensus for that round
  - take top-K from each method
  - union = up to 2K unique numbers
  - hits = how many actual drawn balls fall in the union

Also writes combo_evo_rounds.json (dates, actuals, picks) for per-round detail view.
"""
import json, itertools, re, numpy as np, time, sys
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

HTML_PATH   = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto\public\backtest.html"
DATA_OUT    = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto\public\combo_evo_data.json"
ROUNDS_OUT  = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto\public\combo_evo_rounds.json"

# ── Load DATA from backtest.html ──────────────────────────────────────────────
with open(HTML_PATH, encoding='utf-8') as f:
    html = f.read()

m = re.search(r'const DATA\s*=\s*(\[)', html)
bracket_start = m.start(1)
depth=0; pos=bracket_start
while pos < len(html):
    if html[pos]=='[': depth+=1
    elif html[pos]==']':
        depth-=1
        if depth==0: bracket_end=pos+1; break
    pos+=1
DATA = json.loads(html[bracket_start:bracket_end])

m2 = re.search(r'const METHODS\s*=\s*(\[.*?\])', html, re.DOTALL)
METHODS = json.loads(m2.group(1))
N = 16; T = len(DATA)
print(str(T) + ' draws, ' + str(N) + ' methods')

# ── Precompute matrices ───────────────────────────────────────────────────────
picks_mat  = np.zeros((T, N, 43), dtype=np.uint8)
actual_mat = np.zeros((T, 43),    dtype=np.uint8)
serials    = []
dates      = []
actuals    = []

for t, row in enumerate(DATA):
    serials.append(row['s'])
    dates.append(row.get('d', str(row['s']))[:10])
    actual_balls = sorted(row['a'])
    actuals.append(actual_balls)
    for n in actual_balls: actual_mat[t, n-1] = 1
    for mi, pred in enumerate(row['p']):
        for n in pred[0]: picks_mat[t, mi, n-1] = 1

# All-method frequency per round: how many of 16 methods predict each number
all_freq = picks_mat.sum(axis=1).astype(np.float32)  # (T, 43)

# ── Helper: top-K mask for one method's picks, ranked by all-method freq ─────
def topk_mask(method_idx, K):
    """For each round, take top-K of this method's picks by all-method consensus."""
    m_picks = picks_mat[:, method_idx, :].astype(np.float32)  # (T, 43)
    # score: all_freq for picked numbers, -inf for non-picked
    score = np.where(picks_mat[:, method_idx, :], all_freq, -np.inf)  # (T, 43)
    # argsort descending, take first K
    order = np.argsort(-score, axis=1)[:, :K]  # (T, K)
    mask = np.zeros((T, 43), dtype=np.uint8)
    rows = np.repeat(np.arange(T), K)
    mask[rows, order.ravel()] = 1
    return mask

# ── Precompute topk masks for each (method, K) ───────────────────────────────
print('Precomputing top-K masks...')
t0 = time.time()
topk_cache = {}
for K in (15, 20):
    for mi in range(N):
        topk_cache[(mi, K)] = topk_mask(mi, K)
print('  done in ' + str(round(time.time()-t0, 1)) + 's')

# ── Evaluate all 120 combos ───────────────────────────────────────────────────
all_combos = list(itertools.combinations(range(N), 2))
print('Running ' + str(len(all_combos)) + ' combos x 2 K values...')
t0 = time.time()

results = {}
for m0, m1 in all_combos:
    key = str(m0) + ',' + str(m1)
    results[key] = {}
    for K in (15, 20):
        # Union of top-K from each method
        union_mask = np.clip(topk_cache[(m0, K)] + topk_cache[(m1, K)], 0, 1)  # (T, 43)
        union_size = union_mask.sum(axis=1)  # (T,) — how many unique numbers
        hits = (union_mask * actual_mat).sum(axis=1)  # (T,)

        arr = np.array(hits)
        dist = np.bincount(arr.clip(0, 6), minlength=7).tolist()
        avg  = float(arr.mean())
        fp   = int((arr >= 4).sum())

        results[key][str(K)] = {
            'hits': hits.tolist(),
            'dist': dist,
            'avg':  round(avg, 4),
            'fp':   fp,
            'z0':   dist[0],
            'z6':   dist[6],
            'union_avg': round(float(union_size.mean()), 2),  # avg union size
        }

print('Done in ' + str(round(time.time()-t0, 1)) + 's')

# ── Print summary ─────────────────────────────────────────────────────────────
for K in (15, 20):
    ks = str(K)
    rows_k = [(k, results[k][ks]) for k in results]
    best_avg  = max(rows_k, key=lambda x: x[1]['avg'])
    worst_avg = min(rows_k, key=lambda x: x[1]['avg'])
    best_z6   = max(rows_k, key=lambda x: x[1]['z6'])
    worst_z0  = max(rows_k, key=lambda x: x[1]['z0'])
    best_z0   = min(rows_k, key=lambda x: x[1]['z0'])

    def fmt(key_r):
        k, r = key_r
        m0, m1 = map(int, k.split(','))
        return METHODS[m0].replace(' (k=10)','').replace(' (k=28)','') + ' + ' + METHODS[m1].replace(' (k=10)','').replace(' (k=28)','') + ' -> avg=' + str(r['avg']) + ' 6hit=' + str(r['z6']) + ' 0hit=' + str(r['z0']) + ' unionAvg=' + str(r['union_avg'])

    print('K=' + str(K) + ':')
    print('  Best avg  : ' + fmt(best_avg))
    print('  Worst avg : ' + fmt(worst_avg))
    print('  Best 6-hit: ' + fmt(best_z6))
    print('  Most 0-hit: ' + fmt(worst_z0))
    print('  Fewest 0  : ' + fmt(best_z0))
    print()

# ── Save combo_evo_data.json ──────────────────────────────────────────────────
out = {
    'T': T,
    'N': N,
    'methods': METHODS,
    'combos': results,
    'dates': dates,
    'formula': 'union_topk',  # tag for client to know formula version
}
with open(DATA_OUT, 'w') as f:
    json.dump(out, f, separators=(',', ':'))
print('Saved combo_evo_data.json (' + str(len(json.dumps(out))//1024) + 'KB)')

# ── Save combo_evo_rounds.json (for per-round detail view) ───────────────────
# picks: for each round, each method's 15 stored picks (as list of numbers)
rounds_picks = []
for t, row in enumerate(DATA):
    method_picks = []
    for mi in range(N):
        balls = sorted([n for n in range(1, 44) if picks_mat[t, mi, n-1]])
        method_picks.append(balls)
    rounds_picks.append(method_picks)

rounds_out = {
    'dates': dates,
    'serials': serials,
    'actuals': actuals,
    'picks': rounds_picks,   # [T][N][15] — each method's 15 stored picks per round
}
with open(ROUNDS_OUT, 'w') as f:
    json.dump(rounds_out, f, separators=(',', ':'))
print('Saved combo_evo_rounds.json (' + str(len(json.dumps(rounds_out))//1024) + 'KB)')
