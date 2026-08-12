"""
xoshiro_seed_scan_k7_10k.py
-------------------------------
Scratch/reference scan (not a page generator, not saved to DB): for
seeds 0-10,000, compute K=7 xoshiro256** picks against draws #1000-2127
(1128 draws -- corrected from an initial #1001-2127/1127-draw run per
user correction), same algorithm already verified against reference
test vectors in gen_xoshiro_seed_backtest.py.

Same three per-seed metrics as the K=26/K=33 scans: hit6b (6-hit+bonus),
hit6, hit5. Also tracks the FULL per-draw hit-count distribution
(0 through 6 hits), aggregated across all seed x draw evaluations --
useful here since K=7 is much smaller than 21/26/33, so most draws will
land at 0 or 1 hits rather than the higher-hit-heavy shape seen at
larger K.

Finds both the best seed (highest hit6b, tiebreak hit6, tiebreak hit5)
and the worst seed (lowest hit6b, tiebreak hit6, tiebreak hit5).

Draw records pulled from the production Neon Postgres DB (same as the
K=26/K=33 scans), verified for exactly 1128 consecutive rows before
scanning.

Run: python xoshiro_seed_scan_k7_10k.py
"""
import json, re, time, sys, math, os
import multiprocessing as mp
from collections import Counter

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
ENV_LOCAL = BASE + r"\.env.local"
OUT_JSON = BASE + r"\xoshiro_seed_scan_k7_10k_w1000.json"

K_PICKS = 7
DRAW_START, DRAW_END = 1000, 2127
N_DRAWS = DRAW_END - DRAW_START + 1  # 1127
LOTO6_MAX = 43
NUM_SEEDS = 10_001   # seeds 0..10000 inclusive
N_WORKERS = 7
CHUNK_SIZE = 200

MASK64 = 0xFFFFFFFFFFFFFFFF

def xoshiro_predict_inline(seed, draw_serial, k, pool_max, arr_template):
    combined = (seed * 10_000_000 + draw_serial) & MASK64
    z = combined & MASK64
    s = [0, 0, 0, 0]
    for i in range(4):
        z = (z + 0x9E3779B97F4A7C15) & MASK64
        zz = z
        zz = ((zz ^ (zz >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
        zz = ((zz ^ (zz >> 27)) * 0x94D049BB133111EB) & MASK64
        zz = zz ^ (zz >> 31)
        s[i] = zz
    s0, s1, s2, s3 = s
    arr = arr_template[:]
    n = pool_max
    for i in range(n - 1, n - 1 - k, -1):
        result = (((((s1 * 5) & MASK64) << 7) | (((s1 * 5) & MASK64) >> 57)) & MASK64)
        result = (result * 9) & MASK64
        t = (s1 << 17) & MASK64
        s2 ^= s0
        s3 ^= s1
        s1 ^= s2
        s0 ^= s3
        s2 ^= t
        s3 = ((s3 << 45) | (s3 >> 19)) & MASK64
        j = result % (i + 1)
        arr[i], arr[j] = arr[j], arr[i]
    return arr[n - k:]

def init_worker(data_bytes):
    global _DATA
    rows = json.loads(data_bytes)
    _DATA = [(r['s'], frozenset(r['a']), r['b']) for r in rows]

def process_chunk(seed_chunk):
    arr_template = list(range(1, LOTO6_MAX + 1))
    out = []
    for seed in seed_chunk:
        hit6b = 0
        hit6 = 0
        hit5 = 0
        dist7 = [0, 0, 0, 0, 0, 0, 0]  # counts of draws with 0..6 hits
        for serial, actual_set, bonus in _DATA:
            picks = xoshiro_predict_inline(seed, serial, K_PICKS, LOTO6_MAX, arr_template)
            picks_set = frozenset(picks)
            h = len(actual_set & picks_set)
            dist7[h] += 1
            if h == 6:
                hit6 += 1
                if bonus in picks_set:
                    hit6b += 1
            elif h == 5:
                hit5 += 1
        out.append((seed, hit6b, hit6, hit5, dist7))
    return out

def load_data_from_db():
    if 'DATABASE_URL' not in os.environ:
        with open(ENV_LOCAL, encoding='utf-8') as f:
            env_text = f.read()
        m = re.search(r'DATABASE_URL=(.+)', env_text)
        os.environ['DATABASE_URL'] = m.group(1).strip()

    import psycopg2
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    cur = conn.cursor()
    cur.execute(
        "SELECT draw_serial, num1,num2,num3,num4,num5,num6, bonus "
        "FROM loto6_results WHERE draw_serial BETWEEN %s AND %s ORDER BY draw_serial",
        (DRAW_START, DRAW_END),
    )
    rows = cur.fetchall()
    conn.close()
    data = [{'s': r[0], 'a': list(r[1:7]), 'b': r[7]} for r in rows]
    return data

def main():
    DATA = load_data_from_db()
    print(f"Loaded {len(DATA)} rows from loto6_results for draws {DRAW_START}-{DRAW_END} (expected {N_DRAWS}).")

    serials = [r['s'] for r in DATA]
    if len(DATA) != N_DRAWS:
        raise SystemExit(f"Row count mismatch: got {len(DATA)}, expected {N_DRAWS}")
    if serials[0] != DRAW_START or serials[-1] != DRAW_END:
        raise SystemExit(f"Endpoint mismatch: got {serials[0]}-{serials[-1]}, expected {DRAW_START}-{DRAW_END}")
    if serials != list(range(DRAW_START, DRAW_END + 1)):
        missing = sorted(set(range(DRAW_START, DRAW_END + 1)) - set(serials))
        raise SystemExit(f"Gap check FAILED. Missing: {missing[:10]}...")
    print(f"Verified: {len(DATA)} consecutive draws, no gaps, #{DRAW_START}-{DRAW_END} exactly.")

    data_bytes = json.dumps(DATA)

    # ── Self-check: inlined function must match the already-verified modular one
    def xoshiro_predict_modular(seed, draw_serial, k=K_PICKS, pool_max=LOTO6_MAX):
        combined = (seed * 10_000_000 + draw_serial) & MASK64
        z = combined & MASK64
        state = []
        for _ in range(4):
            z = (z + 0x9E3779B97F4A7C15) & MASK64
            zz = z
            zz = ((zz ^ (zz >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
            zz = ((zz ^ (zz >> 27)) * 0x94D049BB133111EB) & MASK64
            zz = zz ^ (zz >> 31)
            state.append(zz)
        def rotl(x, kk):
            x &= MASK64
            return ((x << kk) | (x >> (64 - kk))) & MASK64
        s = state
        arr = list(range(1, pool_max + 1))
        n = len(arr)
        for i in range(n - 1, n - 1 - k, -1):
            result = (rotl((s[1] * 5) & MASK64, 7) * 9) & MASK64
            t = (s[1] << 17) & MASK64
            s[2] ^= s[0]; s[3] ^= s[1]; s[1] ^= s[2]; s[0] ^= s[3]
            s[2] ^= t
            s[3] = rotl(s[3], 45)
            j = result % (i + 1)
            arr[i], arr[j] = arr[j], arr[i]
        return sorted(arr[n - k:])

    arr_t = list(range(1, LOTO6_MAX + 1))
    for test_seed, test_draw in [(0, 1000), (168, 2127), (9999, 1500), (5555, 2000), (10000, 2127)]:
        inline_result = sorted(xoshiro_predict_inline(test_seed, test_draw, K_PICKS, LOTO6_MAX, arr_t))
        modular_result = xoshiro_predict_modular(test_seed, test_draw)
        assert inline_result == modular_result, f"MISMATCH seed={test_seed} draw={test_draw}: {inline_result} vs {modular_result}"
        assert len(inline_result) == K_PICKS, f"WRONG PICK COUNT seed={test_seed}: {len(inline_result)} != {K_PICKS}"
    print(f"Self-check: inlined fast-path (K={K_PICKS}) matches the verified modular implementation exactly. OK.")

    # ── Parallel scan ────────────────────────────────────────────────────────
    seeds = list(range(0, NUM_SEEDS))
    chunks = [seeds[i:i + CHUNK_SIZE] for i in range(0, len(seeds), CHUNK_SIZE)]
    total_chunks = len(chunks)
    print(f"\nScanning {NUM_SEEDS:,} seeds (0-{NUM_SEEDS-1}) x {N_DRAWS} draws x K={K_PICKS}, "
          f"{total_chunks:,} chunks of {CHUNK_SIZE}, {N_WORKERS} workers...")

    all_results = []
    t0 = time.time()
    done_seeds = 0
    with mp.Pool(N_WORKERS, initializer=init_worker, initargs=(data_bytes,)) as pool:
        for i, chunk_result in enumerate(pool.imap_unordered(process_chunk, chunks), 1):
            all_results.extend(chunk_result)
            done_seeds += len(chunk_result)
            if i % 5 == 0 or i == total_chunks:
                elapsed = time.time() - t0
                rate = done_seeds / elapsed
                eta = (NUM_SEEDS - done_seeds) / rate if rate > 0 else 0
                print(f"[{i:,}/{total_chunks:,} chunks, {done_seeds:,}/{NUM_SEEDS:,} seeds] "
                      f"elapsed={elapsed:.0f}s rate={rate:.0f} seeds/s eta={eta:.0f}s", flush=True)

    elapsed_total = time.time() - t0
    print(f"\nDONE scanning in {elapsed_total:.1f}s ({elapsed_total/60:.1f} min)")

    all_results.sort(key=lambda r: r[0])

    ranked_best = sorted(all_results, key=lambda r: (-r[1], -r[2], -r[3], r[0]))
    best = ranked_best[0]
    ranked_worst = sorted(all_results, key=lambda r: (r[1], r[2], r[3], r[0]))
    worst = ranked_worst[0]

    hit6b_vals = [r[1] for r in all_results]
    hit6_vals = [r[2] for r in all_results]
    hit5_vals = [r[3] for r in all_results]
    hit6b_dist = Counter(hit6b_vals)
    hit6_dist = Counter(hit6_vals)
    hit5_dist = Counter(hit5_vals)

    # ── Global hit-count distribution (0-6), aggregated across ALL seed x draw evaluations
    global_dist7 = [0, 0, 0, 0, 0, 0, 0]
    for r in all_results:
        d7 = r[4]
        for h in range(7):
            global_dist7[h] += d7[h]
    total_evals = NUM_SEEDS * N_DRAWS

    # ── Analytical hypergeometric baselines, for context ────────────────────
    def hyper_pmf(x, pool, success, draws):
        return (math.comb(success, x) * math.comb(pool - success, draws - x)) / math.comb(pool, draws)
    def prob_all_in(subset_size_needed, pool_max, pick_k):
        return math.comb(pool_max - subset_size_needed, pick_k - subset_size_needed) / math.comb(pool_max, pick_k)

    p_hit6b = prob_all_in(7, LOTO6_MAX, K_PICKS)
    p_hit6 = hyper_pmf(6, LOTO6_MAX, 6, K_PICKS)
    p_hit5 = hyper_pmf(5, LOTO6_MAX, 6, K_PICKS)
    exp_hit6b = p_hit6b * N_DRAWS
    exp_hit6 = p_hit6 * N_DRAWS
    exp_hit5 = p_hit5 * N_DRAWS
    analytical_dist7 = [hyper_pmf(h, LOTO6_MAX, 6, K_PICKS) * total_evals for h in range(7)]

    import statistics as st
    print(f"\n=== Results across {NUM_SEEDS:,} seeds (K={K_PICKS}, {N_DRAWS} draws #{DRAW_START}-{DRAW_END}) ===")
    print(f"BEST  seed: #{best[0]}  hit6b={best[1]}  hit6={best[2]}  hit5={best[3]}")
    print(f"WORST seed: #{worst[0]}  hit6b={worst[1]}  hit6={worst[2]}  hit5={worst[3]}")
    print(f"\nAnalytical per-seed expectation (pure chance): hit6b~={exp_hit6b:.4f}  hit6~={exp_hit6:.4f}  hit5~={exp_hit5:.4f}  (out of {N_DRAWS} draws)")
    print(f"\nSummary stats (per-seed, across {NUM_SEEDS:,} seeds):")
    for name, vals in [('hit6b', hit6b_vals), ('hit6', hit6_vals), ('hit5', hit5_vals)]:
        print(f"  {name}: min={min(vals)} max={max(vals)} mean={st.mean(vals):.4f} median={st.median(vals)} stdev={st.pstdev(vals):.4f}")

    print(f"\nhit6b (6-hit + bonus) distribution (# of seeds with N such draws):")
    for n in sorted(hit6b_dist):
        print(f"  {n}: {hit6b_dist[n]:,} seeds")

    print(f"\nhit6 (6-hit, any bonus) distribution:")
    for n in sorted(hit6_dist):
        print(f"  {n}: {hit6_dist[n]:,} seeds")

    print(f"\nhit5 (exactly 5-hit) distribution:")
    for n in sorted(hit5_dist):
        print(f"  {n}: {hit5_dist[n]:,} seeds")

    print(f"\n=== FULL hit-count distribution (0-6 hits per draw), aggregated across all {total_evals:,} seed x draw evaluations ===")
    for h in range(7):
        pct = global_dist7[h] / total_evals * 100
        exp_pct = analytical_dist7[h] / total_evals * 100
        print(f"  {h} hits: {global_dist7[h]:,} ({pct:.4f}%)  [analytical expectation: {analytical_dist7[h]:,.0f} = {exp_pct:.4f}%]")

    print(f"\nTop 10 BEST seeds (hit6b desc, hit6 desc, hit5 desc):")
    for r in ranked_best[:10]:
        print(f"  seed={r[0]:6d}  hit6b={r[1]}  hit6={r[2]}  hit5={r[3]}")

    print(f"\nBottom 10 WORST seeds (hit6b asc, hit6 asc, hit5 asc):")
    for r in ranked_worst[:10]:
        print(f"  seed={r[0]:6d}  hit6b={r[1]}  hit6={r[2]}  hit5={r[3]}")

    out = {
        'numSeeds': NUM_SEEDS, 'kPicks': K_PICKS, 'nDraws': N_DRAWS,
        'drawRange': [DRAW_START, DRAW_END],
        'analyticalExpectation': {'hit6b': exp_hit6b, 'hit6': exp_hit6, 'hit5': exp_hit5},
        'best': {'seed': best[0], 'hit6b': best[1], 'hit6': best[2], 'hit5': best[3]},
        'worst': {'seed': worst[0], 'hit6b': worst[1], 'hit6': worst[2], 'hit5': worst[3]},
        'hit6bDistribution': dict(hit6b_dist),
        'hit6Distribution': dict(hit6_dist),
        'hit5Distribution': dict(hit5_dist),
        'globalHitCountDistribution': global_dist7,
        'globalHitCountAnalytical': analytical_dist7,
        'totalEvaluations': total_evals,
        'top10Best': [{'seed': r[0], 'hit6b': r[1], 'hit6': r[2], 'hit5': r[3]} for r in ranked_best[:10]],
        'top10Worst': [{'seed': r[0], 'hit6b': r[1], 'hit6': r[2], 'hit5': r[3]} for r in ranked_worst[:10]],
        # Keep the full per-seed 0-6 hit distribution (not just hit6b/hit6/hit5) --
        # at K=7 that's the only place real per-seed variation shows up.
        'results': [(r[0], r[1], r[2], r[3], r[4]) for r in all_results],
    }
    with open(OUT_JSON, 'w') as f:
        json.dump(out, f, separators=(',', ':'))
    print(f"\nSaved {OUT_JSON}")

if __name__ == '__main__':
    main()
