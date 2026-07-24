"""
Compute all C(16,2)=120 two-method combos for K=15 and K=20.
Output: combo_evo_data.json with per-draw hits for each combo.
"""
import json, itertools, re, numpy as np, time, sys
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

HTML_PATH = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto\public\backtest.html"
OUT_PATH  = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto\public\combo_evo_data.json"

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

# Also grab METHODS array
m2 = re.search(r'const METHODS\s*=\s*(\[.*?\])', html, re.DOTALL)
METHODS = json.loads(m2.group(1))

N = 16; T = len(DATA)
print(f'{T} draws, {N} methods, {len(METHODS)} method names')
print('Methods:', METHODS)

# ── Precompute matrices ───────────────────────────────────────────────────────
picks_mat  = np.zeros((T, N, 43), dtype=np.uint8)
actual_mat = np.zeros((T, 43),    dtype=np.uint8)
for t, row in enumerate(DATA):
    for n in row['a']: actual_mat[t, n-1] = 1
    for mi, pred in enumerate(row['p']):
        for n in pred[0]: picks_mat[t, mi, n-1] = 1

def hits_series(m0, m1, K):
    """Return array of per-draw hits for 2-method combo at given K."""
    # Aggregate votes: sum of two method pick vectors
    votes = picks_mat[:, m0, :].astype(np.int16) + picks_mat[:, m1, :].astype(np.int16)  # (T, 43)
    # For K=20 padding: add 0.1 * all-method avg as tie-breaker
    if K > 15:
        all_votes = picks_mat.sum(axis=1) * 0.1  # (T, 43)
        combined = votes.astype(np.float32) + all_votes
    else:
        combined = votes.astype(np.float32)
    # Top-K mask
    order = np.argsort(-combined, axis=1)[:, :K]
    top_mask = np.zeros((T, 43), dtype=np.uint8)
    for t in range(T): top_mask[t, order[t]] = 1
    hits = (top_mask * actual_mat).sum(axis=1)  # (T,)
    return hits.tolist()

# ── Run all C(16,2)=120 combos for K=15 and K=20 ──────────────────────────────
all_combos = list(itertools.combinations(range(N), 2))
print(f'\nRunning {len(all_combos)} combos x 2 K values...')

results = {}  # "m0,m1" -> { K15: {hits, dist, avg, fp}, K20: {...} }

t0 = time.time()
for m0, m1 in all_combos:
    key = f"{m0},{m1}"
    results[key] = {}
    for K in (15, 20):
        hs = hits_series(m0, m1, K)
        arr = np.array(hs)
        dist = np.bincount(arr.clip(0, 6), minlength=7).tolist()
        avg  = float(arr.mean())
        fp   = int(arr[arr >= 4].shape[0])
        results[key][str(K)] = {
            "hits": hs,   # per-draw hit series (1001 values)
            "dist": dist, # [0,1,2,3,4,5,6] counts
            "avg":  round(avg, 4),
            "fp":   fp,   # draws with 4+ hits
        }

print(f'Done in {time.time()-t0:.1f}s')

# ── Summary: best/worst ───────────────────────────────────────────────────────
for K in (15, 20):
    ks = str(K)
    by_avg = sorted(all_combos, key=lambda p: results[f"{p[0]},{p[1]}"][ks]["avg"], reverse=True)
    by_fp  = sorted(all_combos, key=lambda p: results[f"{p[0]},{p[1]}"][ks]["fp"],  reverse=True)

    print(f'\n=== K={K} ===')
    print(f'Best avg  : {by_avg[0]}  = {METHODS[by_avg[0][0]]} + {METHODS[by_avg[0][1]]}')
    r = results[f"{by_avg[0][0]},{by_avg[0][1]}"][ks]
    print(f'  avg={r["avg"]}, 4+={r["fp"]}, dist={r["dist"]}')

    print(f'Worst avg : {by_avg[-1]}  = {METHODS[by_avg[-1][0]]} + {METHODS[by_avg[-1][1]]}')
    r = results[f"{by_avg[-1][0]},{by_avg[-1][1]}"][ks]
    print(f'  avg={r["avg"]}, 4+={r["fp"]}, dist={r["dist"]}')

    print(f'Best 4+   : {by_fp[0]}  = {METHODS[by_fp[0][0]]} + {METHODS[by_fp[0][1]]}')
    r = results[f"{by_fp[0][0]},{by_fp[0][1]}"][ks]
    print(f'  avg={r["avg"]}, 4+={r["fp"]}, dist={r["dist"]}')

    print(f'Worst 4+  : {by_fp[-1]}  = {METHODS[by_fp[-1][0]]} + {METHODS[by_fp[-1][1]]}')
    r = results[f"{by_fp[-1][0]},{by_fp[-1][1]}"][ks]
    print(f'  avg={r["avg"]}, 4+={r["fp"]}, dist={r["dist"]}')

# ── Save output JSON ──────────────────────────────────────────────────────────
out = {
    "T": T,
    "N": N,
    "methods": METHODS,
    "combos": results,
    "dates": [row.get("d", str(row["s"]))[:10] for row in DATA],
}
with open(OUT_PATH, 'w') as f:
    json.dump(out, f, separators=(',', ':'))
print(f'\nSaved combo_evo_data.json ({len(json.dumps(out))//1024}KB)')
