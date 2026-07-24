import json, itertools, re, numpy as np, time

with open(r'C:\Users\Zaw Min Htoon\source\repos\theonelotto\public\backtest.html', encoding='utf-8') as f:
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
N = 16; T = len(DATA)
print(f'{T} draws, {N} methods')

# Precompute: for each draw x method, a boolean vector of which numbers are predicted
# picks_mat[t,mi,n-1] = 1 if method mi predicts number n in draw t
picks_mat = np.zeros((T, N, 43), dtype=np.uint8)
actual_mat = np.zeros((T, 43), dtype=np.uint8)
for t, row in enumerate(DATA):
    for n in row['a']: actual_mat[t, n-1] = 1
    for mi, pred in enumerate(row['p']):
        for n in pred[0]: picks_mat[t, mi, n-1] = 1

# For K=15: each method stores exactly 15 picks, use them all
# hits[t, mi] = how many of method mi's 15 picks hit the actual 6
hits_15 = np.einsum('tmn,tn->tm', picks_mat, actual_mat)  # (T, N)

# For K=20: we need cross-method consensus for each combo
# We'll handle this during combo evaluation

def eval_combo_k15(methods):
    """Top-15 is just union by vote - take top 15 by vote count"""
    # sum picks across selected methods
    votes = picks_mat[:, methods, :].sum(axis=1)  # (T, 43)
    # for each draw, find top-15 indices by vote
    # argsort descending, take first 15
    top15_mask = np.zeros((T, 43), dtype=np.uint8)
    order = np.argsort(-votes, axis=1)[:, :15]
    for t in range(T): top15_mask[t, order[t]] = 1
    hits = (top15_mask * actual_mat).sum(axis=1)  # (T,)
    dist = np.bincount(hits.clip(0,6), minlength=7)
    return dist

def eval_combo_k20(methods):
    """Pad to 20 using all-method consensus for remaining slots"""
    # votes from selected methods
    votes = picks_mat[:, methods, :].sum(axis=1)  # (T, 43)
    # where votes=0, use 0.1 * all-method avg as tie-breaker
    all_votes = picks_mat.sum(axis=1) * 0.1  # (T, 43)
    combined = votes + all_votes  # (T, 43)
    top20_mask = np.zeros((T, 43), dtype=np.uint8)
    order = np.argsort(-combined, axis=1)[:, :20]
    for t in range(T): top20_mask[t, order[t]] = 1
    hits = (top20_mask * actual_mat).sum(axis=1)
    dist = np.bincount(hits.clip(0,6), minlength=7)
    return dist

for K, eval_fn in [(15, eval_combo_k15), (20, eval_combo_k20)]:
    t0 = time.time()
    print(f'\n=== K={K} ===')
    best_avg = -1; best_cfg = None
    best_4plus = -1; best_4plus_cfg = None
    for r in range(2, 6):
        for combo in itertools.combinations(range(N), r):
            methods = list(combo)
            h = eval_fn(methods)
            avg = np.dot(h, np.arange(7)) / T
            fp = int(h[4:].sum())
            if avg > best_avg:
                best_avg = avg; best_cfg = (combo, float(avg), fp, h.tolist())
            if fp > best_4plus:
                best_4plus = fp; best_4plus_cfg = (combo, float(avg), fp, h.tolist())
    print(f'Best avg  : methods={list(best_cfg[0])} avg={best_cfg[1]:.4f} 4+={best_cfg[2]} dist={best_cfg[3]}')
    print(f'Best 4+   : methods={list(best_4plus_cfg[0])} avg={best_4plus_cfg[1]:.4f} 4+={best_4plus_cfg[2]} dist={best_4plus_cfg[3]}')
    print(f'  ({time.time()-t0:.1f}s)')
