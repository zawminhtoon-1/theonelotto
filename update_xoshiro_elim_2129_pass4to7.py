"""
update_xoshiro_elim_2129_pass4to7.py
--------------------------------------
Appends the same 4 additional elimination passes already applied to the
#2130 page onto #2129's existing pipeline (Base K=38 seed #692,809 ->
Pass1 K=33 seed #118,590 -> Pass2 16 methods K=26 -> Pass3 K=33 same
seed as Base -- 1,210,881 remaining), filtering the EXISTING remaining-
combos list rather than re-running the full C(38,6) enumeration (same
incremental-update convention as update_xoshiro_elim_2129_pass3.py).

New Pass 4: top 1000 worst-coverage seeds (highest 0-hit count) from
            seed_hit_random_k17, K=15 picks for draw #2129 (ground-
            truth random.Random(seed*10_000_000+draw_serial).sample()).
New Pass 5: xoshiro256** K=21 seeds 0, 1, 2, draw #2129.
New Pass 6: historical repeat filter -- exact match to a real 6-number
            winning combo from draws #1-2129 (#2129 itself is now a
            real, confirmed draw, so it IS included in this set).
New Pass 7: Worst Combo (Anti-Pick) K=15 pick for draw #2129 (MA-43 +
            Exp-weighted + Random Forest + kNN + Apriori consensus).
            Since #2129 has already happened, /predictions no longer
            shows this pick (it now targets #2130) -- so this pass
            faithfully replicates page.tsx's actual JS methods
            (confirmed DIFFERENT from the simplified Python ports in
            append_backtest.py: page.tsx's RF is a bagged-OLS ensemble
            via Gauss-Jordan-solved normal equations with a
            deterministic LCG bootstrap seed=42, not sklearn
            RandomForestRegressor; its Apriori is 1-item+2-item
            sequential association, not simple pair co-occurrence)
            in Python, walk-forward trained on draws #1-2128 only.

Run: python update_xoshiro_elim_2129_pass4to7.py
"""
import json, time, sqlite3, random as pyrandom, os, re
import psycopg2

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
ENV_LOCAL = BASE + r"\.env.local"
DB_PATH = BASE + r"\loto6_local.db"
META_PATH = BASE + r"\xoshiro_elim_2129_meta.json"
COMBOS_PATH = BASE + r"\public\xoshiro_elim_2129_combos.json"
RANDOM_TABLE = "seed_hit_random_k17"

LOTO6_MAX = 43
TARGET_SERIAL = 2129
K_PASS4 = 15
N_WORST_SEEDS = 1000
K_PASS5 = 21
PASS5_SEEDS = [0, 1, 2]

with open(META_PATH, encoding='utf-8') as f:
    meta = json.load(f)
if meta['targetSerial'] != TARGET_SERIAL:
    raise SystemExit(f"meta targetSerial={meta['targetSerial']}, expected {TARGET_SERIAL}")

base_pool = meta['base']['pool']
K_BASE = meta['base']['k']
pos_of = {n: i for i, n in enumerate(base_pool)}
FULLBASE = (1 << K_BASE) - 1

def restricted_mask(target_set):
    mask = 0
    for n in target_set:
        if n in pos_of:
            mask |= (1 << pos_of[n])
    return mask

with open(COMBOS_PATH, encoding='utf-8') as f:
    remaining = json.load(f)
before_all = len(remaining)
print(f"Loaded {before_all:,} remaining combos (Base->Pass1->Pass2->Pass3 output).")
if before_all != meta['finalRemaining']:
    raise SystemExit(f"Mismatch: combos file has {before_all:,}, meta says {meta['finalRemaining']:,}")

# ── xoshiro256** (verified implementation, same as every other page) ────────
MASK64 = 0xFFFFFFFFFFFFFFFF
def splitmix64_next(z):
    z = (z + 0x9E3779B97F4A7C15) & MASK64
    zz = z
    zz = ((zz ^ (zz >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
    zz = ((zz ^ (zz >> 27)) * 0x94D049BB133111EB) & MASK64
    zz = zz ^ (zz >> 31)
    return z, zz
def seed_state(seed):
    z = seed & MASK64
    state = []
    for _ in range(4):
        z, out = splitmix64_next(z)
        state.append(out)
    return state
def rotl(x, k):
    x &= MASK64
    return ((x << k) | (x >> (64 - k))) & MASK64
def xoshiro_next(s):
    result = (rotl((s[1] * 5) & MASK64, 7) * 9) & MASK64
    t = (s[1] << 17) & MASK64
    s[2] ^= s[0]; s[3] ^= s[1]; s[1] ^= s[2]; s[0] ^= s[3]
    s[2] ^= t
    s[3] = rotl(s[3], 45)
    return result
def xoshiro_predict(seed, draw_serial, k, pool_max=LOTO6_MAX):
    combined = (seed * 10_000_000 + draw_serial) & MASK64
    s = seed_state(combined)
    arr = list(range(1, pool_max + 1))
    n = len(arr)
    for i in range(n - 1, n - 1 - k, -1):
        r = xoshiro_next(s)
        j = r % (i + 1)
        arr[i], arr[j] = arr[j], arr[i]
    return sorted(arr[n - k:])

# ── New Pass 4: top N_WORST_SEEDS worst-coverage seeds, K=15 picks ──────────
print(f"\n=== Pass 4 ===")
conn2 = sqlite3.connect(DB_PATH)
cur2 = conn2.cursor()
cur2.execute(f"""SELECT seed, hit0_count FROM {RANDOM_TABLE}
                 ORDER BY hit0_count DESC, seed ASC LIMIT {N_WORST_SEEDS}""")
worst_seeds = cur2.fetchall()
conn2.close()
if len(worst_seeds) != N_WORST_SEEDS:
    raise SystemExit(f"Expected {N_WORST_SEEDS} worst-coverage seeds, got {len(worst_seeds)}")
print(f"Top {N_WORST_SEEDS} worst-coverage seeds from {RANDOM_TABLE}: hit0 range {worst_seeds[0][1]} to {worst_seeds[-1][1]}")

def random_predict_pass4(seed, draw_serial, k=K_PASS4):
    rng = pyrandom.Random(seed * 10_000_000 + draw_serial)
    return sorted(rng.sample(range(1, LOTO6_MAX + 1), k))

random_picks = [random_predict_pass4(seed, TARGET_SERIAL) for seed, _ in worst_seeds]
random_masks = [restricted_mask(set(p)) for p in random_picks]
overlaps4 = [bin(m).count('1') for m in random_masks]
print(f"Overlap with {K_BASE}-pool across the {N_WORST_SEEDS} K={K_PASS4} picks: min={min(overlaps4)} max={max(overlaps4)} avg={sum(overlaps4)/len(overlaps4):.1f}")

t0 = time.time()
remaining_after4 = []
removed4 = 0
for combo in remaining:
    combo_mask = 0
    for n in combo:
        combo_mask |= (1 << pos_of[n])
    hit = False
    for mmask in random_masks:
        if (combo_mask & ~mmask) & FULLBASE == 0:
            hit = True
            break
    if hit:
        removed4 += 1
    else:
        remaining_after4.append(combo)
elapsed4 = time.time() - t0
after4 = len(remaining_after4)
print(f"Pass 4 elimination in {elapsed4:.1f}s")
print(f"  Removed by ANY of the {N_WORST_SEEDS} worst-coverage seeds' K={K_PASS4} containment: {removed4:,}")
print(f"  Before Pass 4: {before_all:,}  ->  After Pass 4: {after4:,}")

# ── New Pass 5: xoshiro256** K=21 seeds 0, 1, 2 ─────────────────────────────
print(f"\n=== Pass 5 ===")
pass5_picks = [xoshiro_predict(seed, TARGET_SERIAL, K_PASS5) for seed in PASS5_SEEDS]
pass5_masks = []
for seed, pick in zip(PASS5_SEEDS, pass5_picks):
    mmask = restricted_mask(set(pick))
    overlap = bin(mmask).count('1')
    pass5_masks.append(mmask)
    print(f"  seed={seed}: {pick}  [overlap with {K_BASE}-pool: {overlap}]")

t0 = time.time()
remaining_after5 = []
removed5 = 0
for combo in remaining_after4:
    combo_mask = 0
    for n in combo:
        combo_mask |= (1 << pos_of[n])
    hit = False
    for mmask in pass5_masks:
        if (combo_mask & ~mmask) & FULLBASE == 0:
            hit = True
            break
    if hit:
        removed5 += 1
    else:
        remaining_after5.append(combo)
elapsed5 = time.time() - t0
after5 = len(remaining_after5)
print(f"Pass 5 elimination in {elapsed5:.1f}s")
print(f"  Removed by ANY of the {len(PASS5_SEEDS)} xoshiro K={K_PASS5} seeds' containment: {removed5:,}")
print(f"  Before Pass 5: {after4:,}  ->  After Pass 5: {after5:,}")

# ── New Pass 6: historical repeat filter, draws #1-2129 (2129 itself IS a
# real, confirmed draw by now) ───────────────────────────────────────────────
print(f"\n=== Pass 6 ===")
if 'DATABASE_URL' not in os.environ:
    with open(ENV_LOCAL, encoding='utf-8') as f:
        env_text = f.read()
    m = re.search(r'DATABASE_URL=(.+)', env_text)
    os.environ['DATABASE_URL'] = m.group(1).strip()
conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()
cur.execute("SELECT draw_serial, num1,num2,num3,num4,num5,num6 FROM loto6_results "
            "WHERE draw_serial <= %s ORDER BY draw_serial", (TARGET_SERIAL,))
hist_rows = cur.fetchall()
conn.close()
if hist_rows[-1][0] != TARGET_SERIAL:
    raise SystemExit(f"Expected historical set to include draw #{TARGET_SERIAL}, latest is #{hist_rows[-1][0]}")
historical_combos = [sorted(r[1:7]) for r in hist_rows]
historical_set = set(tuple(c) for c in historical_combos)
print(f"Historical winning combos: {len(historical_set):,} (from draws #1-{TARGET_SERIAL}, includes #{TARGET_SERIAL} itself)")

remaining_after6 = []
removed_historical = []
for combo in remaining_after5:
    if tuple(combo) in historical_set:
        removed_historical.append(combo)
    else:
        remaining_after6.append(combo)
after6 = len(remaining_after6)
print(f"  Removed (exact match to a historical winning combo): {len(removed_historical):,}")
if removed_historical:
    print(f"  Matched: {removed_historical}")
print(f"  Before Pass 6: {after5:,}  ->  After Pass 6: {after6:,}")

# ── New Pass 7: Worst Combo (Anti-Pick) K=15 for draw #2129 -- page.tsx's
# actual JS methods faithfully replicated in Python (walk-forward through
# #2128 only, since #2129 is the target and must not leak into training). ──
print(f"\n=== Pass 7 ===")
cur_conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur7 = cur_conn.cursor()
cur7.execute("SELECT draw_serial, num1,num2,num3,num4,num5,num6 FROM loto6_results "
             "WHERE draw_serial < %s ORDER BY draw_serial", (TARGET_SERIAL,))
train_rows = cur7.fetchall()
cur_conn.close()
nums = [list(r[1:7]) for r in train_rows]
n_draws = len(nums)
if train_rows[-1][0] != TARGET_SERIAL - 1:
    raise SystemExit(f"Expected training data through #{TARGET_SERIAL-1}, got #{train_rows[-1][0]}")

def make_unique(seed_nums, freq):
    seen = set()
    result = []
    for n in seed_nums:
        clamped = max(1, min(LOTO6_MAX, n))
        if clamped not in seen:
            seen.add(clamped)
            result.append(clamped)
    ordered = sorted(freq.keys(), key=lambda n: -freq.get(n, 0))
    for n in ordered:
        if len(result) >= 15:
            break
        if n not in seen:
            seen.add(n)
            result.append(n)
    return sorted(result[:15])

freq_all = {}
for d in nums:
    for n in d:
        freq_all[n] = freq_all.get(n, 0) + 1

def solve_ls(X, y):
    cols = len(X[0])
    A = [[sum(row[i]*row[j] for row in X) for j in range(cols)] for i in range(cols)]
    bv = [sum(X[r][i]*y[r] for r in range(len(X))) for i in range(cols)]
    aug = [A[i] + [bv[i]] for i in range(cols)]
    for col in range(cols):
        max_row = col
        for r in range(col+1, cols):
            if abs(aug[r][col]) > abs(aug[max_row][col]):
                max_row = r
        aug[col], aug[max_row] = aug[max_row], aug[col]
        if abs(aug[col][col]) < 1e-12:
            continue
        for r in range(cols):
            if r == col:
                continue
            f = aug[r][col] / aug[col][col]
            for c in range(col, cols+1):
                aug[r][c] -= f * aug[col][c]
    return [0.0 if abs(aug[i][i]) < 1e-12 else aug[i][cols] / aug[i][i] for i in range(cols)]

def rf_pred(series):
    LAGS, N_BAGS = 8, 30
    s = series[-80:]
    if len(s) < LAGS + 5:
        return max(1, min(LOTO6_MAX, round(sum(s)/len(s))))
    X, yv = [], []
    for i in range(LAGS, len(s)):
        X.append([1] + s[i-LAGS:i])
        yv.append(s[i])
    n = len(yv)
    x_new = [1] + s[-LAGS:]
    seed = 42
    def rnd_int(maxv):
        nonlocal seed
        seed = (seed * 1664525 + 1013904223) % (2**31)
        return seed % maxv
    preds = []
    for _bag in range(N_BAGS):
        idx = [rnd_int(n) for _ in range(n)]
        Xb = [X[i] for i in idx]
        yb = [yv[i] for i in idx]
        try:
            c = solve_ls(Xb, yb)
            preds.append(sum(x_new[i]*c[i] for i in range(len(x_new))))
        except Exception:
            preds.append(sum(yv)/n)
    return max(1, min(LOTO6_MAX, round(sum(preds)/len(preds))))

def knn_pred(all_draws, k=10):
    N = LOTO6_MAX
    if len(all_draws) < k + 2:
        freq = {}
        for d in all_draws:
            for n in d:
                freq[n] = freq.get(n, 0) + 1
        return make_unique([], freq)
    last_draw = all_draws[-1]
    last_set = set(last_draw)
    sims = []
    for i in range(len(all_draws) - 1):
        d_set = set(all_draws[i])
        inter = len(d_set & last_set)
        union = len(d_set | last_set)
        sims.append((inter/union if union > 0 else 0, i))
    sims.sort(key=lambda x: -x[0])
    scores = [0.0]*N
    for sim, idx in sims[:k]:
        for n in all_draws[idx+1]:
            scores[n-1] += sim
    ranked = sorted(range(1, N+1), key=lambda n: -scores[n-1])
    return sorted(ranked[:15])

def apriori_pred(all_draws, min_sup_frac=0.05):
    N = LOTO6_MAX
    T = len(all_draws)
    if T < 2:
        return []
    sup1 = [0.0]*N
    seq1 = [0.0]*(N*N)
    pair_cnt = [0.0]*(N*N)
    seq2 = [0.0]*(N*N*N)
    for t in range(T):
        cur = all_draws[t]
        nxt = all_draws[t+1] if t < T-1 else None
        for ni in cur:
            sup1[ni-1] += 1
        for i in range(len(cur)):
            if nxt:
                for c in nxt:
                    seq1[(cur[i]-1)*N + (c-1)] += 1
            for j in range(i+1, len(cur)):
                a, b = cur[i]-1, cur[j]-1
                pair_cnt[a*N+b] += 1
                pair_cnt[b*N+a] += 1
                if nxt:
                    for c in nxt:
                        seq2[a*N*N + b*N + (c-1)] += 1
                        seq2[b*N*N + a*N + (c-1)] += 1
    min_sup = min_sup_frac * T
    last_draw = all_draws[-1]
    last_set = set(last_draw)
    score = [0.0]*N
    for ni in last_draw:
        n = ni - 1
        if sup1[n] < min_sup:
            continue
        for c in range(N):
            if (c+1) in last_set:
                continue
            score[c] += seq1[n*N+c] / max(sup1[n], 1)
    for i in range(len(last_draw)):
        for j in range(i+1, len(last_draw)):
            a, b = last_draw[i]-1, last_draw[j]-1
            p_cnt = pair_cnt[a*N+b]
            if p_cnt < min_sup:
                continue
            for c in range(N):
                if (c+1) in last_set:
                    continue
                score[c] += 2.0 * seq2[a*N*N + b*N + c] / max(p_cnt, 1)
    ranked = sorted(range(1, N+1), key=lambda n: -score[n-1])
    return sorted(ranked[:15])

last43 = nums[-43:]
ma43_raw = []
for p in range(6):
    vals = [d[p] for d in last43]
    ma43_raw.append(max(1, min(LOTO6_MAX, round(sum(vals)/len(vals)))))
ma43_pick = make_unique(ma43_raw, freq_all)

lam = 0.95
wts = [lam**(n_draws-1-i) for i in range(n_draws)]
ws = sum(wts)
expw_raw = []
for p in range(6):
    v = sum(wts[i]*nums[i][p] for i in range(n_draws)) / ws
    expw_raw.append(max(1, min(LOTO6_MAX, round(v))))
expw_pick = make_unique(expw_raw, freq_all)

rf_raw = [rf_pred([d[p] for d in nums]) for p in range(6)]
rf_pick = make_unique(rf_raw, freq_all)

knn_pick = knn_pred(nums, k=10)
apriori_pick = apriori_pred(nums, min_sup_frac=0.05)

print(f"MA43     (label 2):  {ma43_pick}")
print(f"ExpW     (label 3):  {expw_pick}")
print(f"RF       (label 7):  {rf_pick}")
print(f"kNN      (label 10): {knn_pick}")
print(f"Apriori  (label 12): {apriori_pick}")

worst_count = {}
for pick in (ma43_pick, expw_pick, rf_pick, knn_pick, apriori_pick):
    for n in pick:
        worst_count[n] = worst_count.get(n, 0) + 1
ranked = sorted(worst_count.items(), key=lambda item: (-item[1], item[0]))
pass7_pick = sorted(n for n, _ in ranked[:15])
print(f"\nWorst Combo (Anti-Pick) K=15 pick for draw #{TARGET_SERIAL}: {pass7_pick}")

pass7_mask = restricted_mask(set(pass7_pick))
pass7_overlap = bin(pass7_mask).count('1')
print(f"Overlap with {K_BASE}-pool: {pass7_overlap}")

t0 = time.time()
remaining_after7 = []
removed7 = 0
for combo in remaining_after6:
    combo_mask = 0
    for n in combo:
        combo_mask |= (1 << pos_of[n])
    if (combo_mask & ~pass7_mask) & FULLBASE == 0:
        removed7 += 1
    else:
        remaining_after7.append(combo)
elapsed7 = time.time() - t0
after7 = len(remaining_after7)
print(f"Pass 7 elimination in {elapsed7:.1f}s")
print(f"  Removed (contained within the Worst Combo K=15 pick): {removed7:,}")
print(f"  Before Pass 7: {after6:,}  ->  After Pass 7: {after7:,}")

print(f"\nFull elimination sequence: {meta['universeCount']:,} -> {meta['afterPass1']:,} -> {meta['beforePass3']:,} -> "
      f"{before_all:,} (Pass3) -> {after4:,} (Pass4) -> {after5:,} (Pass5) -> {after6:,} (Pass6) -> {after7:,} (Pass7)")

# ── Update meta ───────────────────────────────────────────────────────────
meta['randomK'] = K_PASS4
meta['randomSeeds'] = [{'seed': seed, 'hit0': hit0, 'pick': pick}
                        for (seed, hit0), pick in zip(worst_seeds, random_picks)]
meta['removedByPass4'] = removed4
meta['finalRemainingPass4'] = after4
meta['pass5K'] = K_PASS5
meta['pass5Seeds'] = [{'seed': seed, 'pick': pick} for seed, pick in zip(PASS5_SEEDS, pass5_picks)]
meta['removedByPass5'] = removed5
meta['finalRemainingPass5'] = after5
meta['historicalDrawCount'] = len(hist_rows)
meta['historicalCombos'] = historical_combos
meta['removedHistorical'] = [list(c) for c in removed_historical]
meta['finalRemainingPass6'] = after6
meta['pass7K'] = 15
meta['pass7Pick'] = pass7_pick
meta['pass7Overlap'] = pass7_overlap
meta['removedByPass7'] = removed7
meta['finalRemaining'] = after7

with open(META_PATH, 'w', encoding='utf-8') as f:
    json.dump(meta, f, indent=2)
print(f"\nUpdated {META_PATH}")

with open(COMBOS_PATH, 'w', encoding='utf-8') as f:
    json.dump(remaining_after7, f, separators=(',', ':'))
print(f"Updated {COMBOS_PATH} ({after7:,} combos, {os.path.getsize(COMBOS_PATH)//1024:,} KB)")
