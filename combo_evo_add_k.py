"""
Add K=6, 8, 10 to combo_evo_data.json (already has K=15, 20).
Same formula: top-K from each method (by all-method consensus rank),
union up to 2K unique numbers, score = hits vs actual draw.
"""
import json, itertools, re, numpy as np, time, sys
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

HTML_PATH  = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto\public\backtest.html"
DATA_PATH  = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto\public\combo_evo_data.json"

# ── Load backtest DATA ────────────────────────────────────────────────────────
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
RAW = json.loads(html[bracket_start:bracket_end])
N=16; T=len(RAW)
print(str(T) + ' draws, ' + str(N) + ' methods')

picks_mat  = np.zeros((T,N,43), dtype=np.uint8)
actual_mat = np.zeros((T,43),   dtype=np.uint8)
for t,row in enumerate(RAW):
    for n in row['a']: actual_mat[t,n-1]=1
    for mi,pred in enumerate(row['p']):
        for n in pred[0]: picks_mat[t,mi,n-1]=1

all_freq = picks_mat.sum(axis=1).astype(np.float32)  # (T,43)

def topk_mask(method_idx, K):
    score = np.where(picks_mat[:,method_idx,:], all_freq, -np.inf)
    order = np.argsort(-score, axis=1)[:,:K]
    mask  = np.zeros((T,43), dtype=np.uint8)
    rows  = np.repeat(np.arange(T), K)
    mask[rows, order.ravel()] = 1
    return mask

# ── Load existing data ────────────────────────────────────────────────────────
with open(DATA_PATH) as f:
    existing = json.load(f)

# ── Precompute top-K masks for K=6,8,10 ──────────────────────────────────────
NEW_KS = [6, 8, 10]
print('Precomputing masks for K=' + str(NEW_KS) + '...')
t0 = time.time()
topk_cache = {}
for K in NEW_KS:
    for mi in range(N):
        topk_cache[(mi,K)] = topk_mask(mi, K)
print('  done in ' + str(round(time.time()-t0,2)) + 's')

# ── Compute for all 120 combos ────────────────────────────────────────────────
all_combos = list(itertools.combinations(range(N), 2))
print('Running ' + str(len(all_combos)) + ' combos x 3 new K values...')
t0 = time.time()
methods = existing['methods']

for m0, m1 in all_combos:
    key = str(m0) + ',' + str(m1)
    for K in NEW_KS:
        union_mask = np.clip(topk_cache[(m0,K)] + topk_cache[(m1,K)], 0, 1)
        union_size = union_mask.sum(axis=1)
        hits = (union_mask * actual_mat).sum(axis=1)
        arr  = np.array(hits)
        dist = np.bincount(arr.clip(0,6), minlength=7).tolist()
        existing['combos'][key][str(K)] = {
            'hits':      hits.tolist(),
            'dist':      dist,
            'avg':       round(float(arr.mean()), 4),
            'fp':        int((arr>=4).sum()),
            'z0':        dist[0],
            'z6':        dist[6],
            'union_avg': round(float(union_size.mean()), 2),
        }

print('Done in ' + str(round(time.time()-t0,1)) + 's')

# ── Print summaries ───────────────────────────────────────────────────────────
for K in NEW_KS:
    ks = str(K)
    rows = [(k, existing['combos'][k][ks]) for k in existing['combos']]
    best_avg  = max(rows, key=lambda x: x[1]['avg'])
    worst_avg = min(rows, key=lambda x: x[1]['avg'])
    best_z6   = max(rows, key=lambda x: x[1]['z6'])
    worst_z0  = max(rows, key=lambda x: x[1]['z0'])
    best_z0   = min(rows, key=lambda x: x[1]['z0'])

    def fmt(k_r):
        k,r = k_r
        mi0,mi1 = map(int, k.split(','))
        return methods[mi0].split('(')[0].strip() + ' + ' + methods[mi1].split('(')[0].strip() + ' avg=' + str(r['avg']) + ' 6hit=' + str(r['z6']) + ' 0hit=' + str(r['z0']) + ' union=' + str(r['union_avg'])

    print('K=' + str(K) + ':')
    print('  Best avg  : ' + fmt(best_avg))
    print('  Worst avg : ' + fmt(worst_avg))
    print('  Best 6-hit: ' + fmt(best_z6))
    print('  Most 0-hit: ' + fmt(worst_z0))
    print()

# ── Save ──────────────────────────────────────────────────────────────────────
with open(DATA_PATH, 'w') as f:
    json.dump(existing, f, separators=(',',':'))
print('Saved combo_evo_data.json (' + str(len(json.dumps(existing))//1024) + 'KB)')
