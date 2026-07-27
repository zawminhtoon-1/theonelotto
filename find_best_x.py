import psycopg2, numpy as np

DB_URL = "postgresql://neondb_owner:npg_QbHpRZW8of3C@ep-hidden-wind-a1q0el7s-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"
POS_IDX  = 2
BT_DRAWS = 1000
CMP_WIN  = 200
K        = 1
X_MAX    = 500   # expanded search

conn = psycopg2.connect(DB_URL)
cur  = conn.cursor()
cur.execute("SELECT num1,num2,num3,num4,num5,num6 FROM loto6_results ORDER BY draw_serial")
draws = [sorted([r[0],r[1],r[2],r[3],r[4],r[5]]) for r in cur.fetchall()]
conn.close()
vals = np.array([d[POS_IDX] for d in draws], dtype=np.int32)
T = len(vals); test_start = T - BT_DRAWS
RAND = K/43

def make_fn_table(x):
    v = np.arange(1, 44, dtype=np.int32)
    def clip(arr): return np.where((arr>=1)&(arr<=43), arr, 0).astype(np.int32)
    fns = [
        clip(x - v), clip(v + x), clip(v - x),
        clip(2*v - x), clip(2*x - v),
        clip((v + x)//2), clip(v + (x-v)//2), clip(v + (x-v)//3),
    ]
    for n in range(1, 16):
        r = round(x/n)
        if r: fns.append(clip(v+r)); fns.append(clip(v-r))
    for n in range(2, 12):
        r = x % n
        if r: fns.append(clip(v+r)); fns.append(clip(v-r))
    arr = np.stack(fns, axis=0)
    # remove rows that are all zeros (always out of range)
    valid = arr.sum(axis=1) > 0
    return arr[valid]

results = []

for x in range(1, X_MAX+1):
    fn_table = make_fn_table(x)
    if fn_table.shape[0] == 0: continue
    hits = 0; total = 0
    for i in range(test_start, T):
        s = max(0, i - CMP_WIN)
        vp_arr = vals[s:i-1]; vc_arr = vals[s+1:i]
        if len(vp_arr) < 5: continue
        preds_train = fn_table[:, vp_arr - 1]
        f_hits = np.sum(preds_train == vc_arr[np.newaxis, :], axis=1)
        v_last = vals[i-1]
        cands = fn_table[:, v_last - 1]
        pred_scores = np.zeros(44, dtype=np.int64)
        mask = cands > 0
        np.add.at(pred_scores, cands[mask], f_hits[mask])
        pred = np.argmax(pred_scores[1:]) + 1
        if pred == vals[i]: hits += 1
        total += 1
    results.append((x, hits/total if total else 0, (hits/total)/RAND if total else 0, hits, fn_table.shape[0]))

results.sort(key=lambda r: -r[2])
print(f"\nTop 30 x values (x=1..{X_MAX}, Pos3, K=1, window={CMP_WIN}, {BT_DRAWS} draws):")
print(f"{'x':>5}  {'HitRate%':>9}  {'Lift':>7}  {'Hits':>5}  {'nFormulas':>9}")
for x,hr,lift,h,nf in results[:30]:
    print(f"{x:>5}  {hr*100:>8.2f}%  {lift:>7.3f}x  {h:>5}  {nf:>9}")
print(f"\nFreq K=1 baseline: ~2.32x | Random: {RAND*100:.2f}%")
print(f"Best x={results[0][0]}  lift={results[0][2]:.3f}x")
