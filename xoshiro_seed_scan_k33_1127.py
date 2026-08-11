"""
xoshiro_seed_scan_k33_1127.py
--------------------------------
Second correction of the K=33 scan: draws #1001-2127 (1127 draws), not
#1001-2126 (1126 draws, xoshiro_seed_scan_k33_1126.py -- itself already a
correction of the original #1127-2126/1000-draw run). Draw #2127 was
backfilled into the production DB in this same session; the user asked
for it to be included in this window too.

Same K=33, same seeds 0-10,000, same xoshiro256** algorithm/formula, same
hit6b/hit6/hit5 ranking as the prior two runs. Draw records pulled from
the production Neon Postgres DB (loto6_results), same as the 1126-draw
version, since backtest.html's embedded array doesn't go back this far.

Run: python xoshiro_seed_scan_k33_1127.py
"""
import json, re, time, sys, math, os
import multiprocessing as mp
from collections import Counter

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
ENV_LOCAL = BASE + r"\.env.local"
OUT_JSON = BASE + r"\xoshiro_seed_scan_k33_1127.json"

K_PICKS = 33
DRAW_START, DRAW_END = 1001, 2127   # corrected again: was 1001-2126
N_DRAWS = DRAW_END - DRAW_START + 1  # 1127
LOTO6_MAX = 43
NUM_SEEDS = 10_001    # seeds 0..10000 inclusive
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
        for serial, actual_set, bonus in _DATA:
            picks = xoshiro_predict_inline(seed, serial, K_PICKS, LOTO6_MAX, arr_template)
            picks_set = frozenset(picks)
            h = len(actual_set & picks_set)
            if h == 6:
                hit6 += 1
                if bonus in picks_set:
                    hit6b += 1
            elif h == 5:
                hit5 += 1
        out.append((seed, hit6b, hit6, hit5))
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
        dupes = [s for s in set(serials) if serials.count(s) > 1]
        raise SystemExit(f"Gap/duplicate check FAILED. Missing: {missing[:10]}... Duplicates: {dupes[:10]}...")
    print(f"Verified: {len(DATA)} consecutive draws, no gaps, no duplicates, #{DRAW_START}-{DRAW_END} exactly.")
    print(f"Sample row 0: {DATA[0]}")
    print(f"Sample row -1: {DATA[-1]}")

    data_bytes = json.dumps(DATA)

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
    for test_seed, test_draw in [(0, 1001), (168, 2127), (9999, 1500), (5555, 2000), (10000, 1001)]:
        inline_result = sorted(xoshiro_predict_inline(test_seed, test_draw, K_PICKS, LOTO6_MAX, arr_t))
        modular_result = xoshiro_predict_modular(test_seed, test_draw)
        assert inline_result == modular_result, f"MISMATCH seed={test_seed} draw={test_draw}: {inline_result} vs {modular_result}"
        assert len(inline_result) == K_PICKS, f"WRONG PICK COUNT seed={test_seed}: {len(inline_result)} != {K_PICKS}"
    print(f"Self-check: inlined fast-path (K={K_PICKS}) matches the verified modular implementation exactly. OK.")

    seeds = list(range(0, NUM_SEEDS))
    chunks = [seeds[i:i + CHUNK_SIZE] for i in range(0, len(seeds), CHUNK_SIZE)]
    total_chunks = len(chunks)
    print(f"\nScanning {NUM_SEEDS:,} seeds (0-{NUM_SEEDS-1}) x {N_DRAWS} draws x K={K_PICKS}, "
          f"{total_chunks} chunks of {CHUNK_SIZE}, {N_WORKERS} workers...")

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
                print(f"[{i}/{total_chunks} chunks, {done_seeds:,}/{NUM_SEEDS:,} seeds] "
                      f"elapsed={elapsed:.0f}s rate={rate:.0f} seeds/s eta={eta:.0f}s", flush=True)

    elapsed_total = time.time() - t0
    print(f"\nDONE scanning in {elapsed_total:.1f}s ({elapsed_total/60:.1f} min)")

    all_results.sort(key=lambda r: r[0])
    ranked = sorted(all_results, key=lambda r: (-r[1], -r[2], -r[3], r[0]))
    best = ranked[0]

    hit6b_dist = Counter(r[1] for r in all_results)
    hit6_dist = Counter(r[2] for r in all_results)
    hit5_dist = Counter(r[3] for r in all_results)

    def hyper_pmf(x, pool, success, draws):
        return (math.comb(success, x) * math.comb(pool - success, draws - x)) / math.comb(pool, draws)
    def prob_all_in(subset_size_needed, pool_max, pick_k):
        return math.comb(pool_max - subset_size_needed, pick_k - subset_size_needed) / math.comb(pool_max, pick_k)

    p_hit6b = prob_all_in(7, LOTO6_MAX, K_PICKS)
    p_hit6_hyper = hyper_pmf(6, LOTO6_MAX, 6, K_PICKS)
    p_hit5 = hyper_pmf(5, LOTO6_MAX, 6, K_PICKS)

    exp_hit6b = p_hit6b * N_DRAWS
    exp_hit6 = p_hit6_hyper * N_DRAWS
    exp_hit5 = p_hit5 * N_DRAWS

    print(f"\n=== Results across {NUM_SEEDS:,} seeds (K={K_PICKS}, {N_DRAWS} draws #{DRAW_START}-{DRAW_END}) ===")
    print(f"Best seed: #{best[0]}  hit6b={best[1]}  hit6={best[2]}  hit5={best[3]}")
    print(f"Analytical per-seed expectation (pure chance): hit6b~={exp_hit6b:.2f}  hit6~={exp_hit6:.2f}  hit5~={exp_hit5:.2f}  (out of {N_DRAWS} draws)")

    print(f"\nhit6b (6-hit + bonus) distribution:")
    for n in sorted(hit6b_dist):
        print(f"  {n}: {hit6b_dist[n]:,} seeds")

    print(f"\nhit6 (6-hit, any bonus) distribution:")
    for n in sorted(hit6_dist):
        print(f"  {n}: {hit6_dist[n]:,} seeds")

    print(f"\nhit5 (exactly 5-hit) distribution:")
    for n in sorted(hit5_dist):
        print(f"  {n}: {hit5_dist[n]:,} seeds")

    print(f"\nTop 10 seeds by ranking (hit6b desc, hit6 desc, hit5 desc):")
    for r in ranked[:10]:
        print(f"  seed={r[0]:6d}  hit6b={r[1]:3d}  hit6={r[2]:3d}  hit5={r[3]:3d}")

    out = {
        'numSeeds': NUM_SEEDS, 'kPicks': K_PICKS, 'nDraws': N_DRAWS,
        'drawRange': [DRAW_START, DRAW_END],
        'analyticalExpectation': {'hit6b': exp_hit6b, 'hit6': exp_hit6, 'hit5': exp_hit5},
        'best': {'seed': best[0], 'hit6b': best[1], 'hit6': best[2], 'hit5': best[3]},
        'hit6bDistribution': dict(hit6b_dist),
        'hit6Distribution': dict(hit6_dist),
        'hit5Distribution': dict(hit5_dist),
        'top10': [{'seed': r[0], 'hit6b': r[1], 'hit6': r[2], 'hit5': r[3]} for r in ranked[:10]],
        'results': all_results,
    }
    with open(OUT_JSON, 'w') as f:
        json.dump(out, f, separators=(',', ':'))
    print(f"\nSaved {OUT_JSON}")

if __name__ == '__main__':
    main()
