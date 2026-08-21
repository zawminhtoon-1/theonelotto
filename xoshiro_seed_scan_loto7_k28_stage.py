"""
xoshiro_seed_scan_loto7_k28_stage.py
----------------------------------------
Parameterized stage runner for the Loto7 K=28 xoshiro scan: seeds
-1,000,000 to 1,000,000 (2,000,001 seeds total), split into 4
roughly equal stages of ~500,000 seeds each -- direct reuse of the
K=25 scan's infrastructure (xoshiro_seed_scan_loto7_k25_stage.py),
just K_PICKS changed from 25 to 28. Same xoshiro256** algorithm/
formula (seed*10,000,000 + draw_serial, negative seeds handled via
Python's arbitrary-precision ints + & MASK64, i.e. two's-complement
wrap -- no special-casing needed, same pattern verified on the Loto6
K=35 scan and the Loto7 K=25 scan), same draw window #1-500, same
hit7b/hit7/hit6/hit5/hit4 metrics. Self-checks (including negative-
seed cases) before scaling, per stage.

Usage: python xoshiro_seed_scan_loto7_k28_stage.py <stage_num> <seed_lo> <seed_hi>
Example: python xoshiro_seed_scan_loto7_k28_stage.py 1 -1000000 -500001
"""
import json, re, time, sys, os
import multiprocessing as mp

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
ENV_LOCAL = BASE + r"\.env.local"

K_PICKS = 28
DRAW_START, DRAW_END = 1, 500
N_DRAWS = DRAW_END - DRAW_START + 1  # 500
LOTO7_MAX = 37
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
    _DATA = [(r['s'], frozenset(r['a']), r['b1'], r['b2']) for r in rows]

def process_chunk(seed_chunk):
    arr_template = list(range(1, LOTO7_MAX + 1))
    out = []
    for seed in seed_chunk:
        hit7b = 0
        hits_dist = [0, 0, 0, 0, 0, 0, 0, 0]
        for serial, actual_set, b1, b2 in _DATA:
            picks = xoshiro_predict_inline(seed, serial, K_PICKS, LOTO7_MAX, arr_template)
            picks_set = frozenset(picks)
            h = len(actual_set & picks_set)
            hits_dist[h] += 1
            if h == 7 and (b1 in picks_set or b2 in picks_set):
                hit7b += 1
        out.append((seed, hit7b, hits_dist[7], hits_dist[6], hits_dist[5], hits_dist[4]))
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
        "SELECT draw_serial, num1,num2,num3,num4,num5,num6,num7, bonus1, bonus2 "
        "FROM loto7_results WHERE draw_serial BETWEEN %s AND %s ORDER BY draw_serial",
        (DRAW_START, DRAW_END),
    )
    rows = cur.fetchall()
    conn.close()
    return [{'s': r[0], 'a': list(r[1:8]), 'b1': r[8], 'b2': r[9]} for r in rows]

def main():
    stage_num = int(sys.argv[1])
    SEED_LO = int(sys.argv[2])
    SEED_HI = int(sys.argv[3])
    OUT_JSON = BASE + rf"\xoshiro_seed_scan_loto7_k28_stage{stage_num}.json"

    DATA = load_data_from_db()
    print(f"[Stage {stage_num}] Loaded {len(DATA)} rows from loto7_results for draws {DRAW_START}-{DRAW_END} (expected {N_DRAWS}).")
    serials = [r['s'] for r in DATA]
    if len(DATA) != N_DRAWS:
        raise SystemExit(f"Row count mismatch: got {len(DATA)}, expected {N_DRAWS}")
    if serials != list(range(DRAW_START, DRAW_END + 1)):
        missing = sorted(set(range(DRAW_START, DRAW_END + 1)) - set(serials))
        raise SystemExit(f"Gap check FAILED. Missing: {missing[:10]}...")
    print(f"[Stage {stage_num}] Verified: {len(DATA)} consecutive draws, no gaps, #{DRAW_START}-{DRAW_END} exactly.")

    data_bytes = json.dumps(DATA)

    def xoshiro_predict_modular(seed, draw_serial, k=K_PICKS, pool_max=LOTO7_MAX):
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

    arr_t = list(range(1, LOTO7_MAX + 1))
    test_cases = [(SEED_LO, DRAW_START), (SEED_HI, DRAW_END), (-1000000, 1), (-1, 500), (0, 1), (1000000, 500), (-500000, 250)]
    for test_seed, test_draw in test_cases:
        inline_result = sorted(xoshiro_predict_inline(test_seed, test_draw, K_PICKS, LOTO7_MAX, arr_t))
        modular_result = xoshiro_predict_modular(test_seed, test_draw)
        assert inline_result == modular_result, f"MISMATCH seed={test_seed} draw={test_draw}: {inline_result} vs {modular_result}"
        assert len(inline_result) == K_PICKS, f"WRONG PICK COUNT seed={test_seed}: {len(inline_result)} != {K_PICKS}"
        assert len(set(inline_result)) == K_PICKS, f"DUPLICATE NUMBERS seed={test_seed}: {inline_result}"
        assert all(1 <= n <= LOTO7_MAX for n in inline_result), f"OUT OF RANGE seed={test_seed}: {inline_result}"
    print(f"[Stage {stage_num}] Self-check (incl. negative seeds): inlined fast-path (K={K_PICKS}, pool={LOTO7_MAX}) matches the modular reference exactly. OK.")

    seeds = list(range(SEED_LO, SEED_HI + 1))
    num_seeds = len(seeds)
    chunks = [seeds[i:i + CHUNK_SIZE] for i in range(0, len(seeds), CHUNK_SIZE)]
    total_chunks = len(chunks)
    print(f"\n[Stage {stage_num}] Scanning seeds {SEED_LO:,} to {SEED_HI:,} ({num_seeds:,} seeds) x {N_DRAWS} draws x K={K_PICKS}, "
          f"{total_chunks:,} chunks of {CHUNK_SIZE}, {N_WORKERS} workers...")

    all_results = []
    t0 = time.time()
    done_seeds = 0
    with mp.Pool(N_WORKERS, initializer=init_worker, initargs=(data_bytes,)) as pool:
        for i, chunk_result in enumerate(pool.imap_unordered(process_chunk, chunks), 1):
            all_results.extend(chunk_result)
            done_seeds += len(chunk_result)
            if i % 50 == 0 or i == total_chunks:
                elapsed = time.time() - t0
                rate = done_seeds / elapsed
                eta = (num_seeds - done_seeds) / rate if rate > 0 else 0
                print(f"[Stage {stage_num}] [{i:,}/{total_chunks:,} chunks, {done_seeds:,}/{num_seeds:,} seeds] "
                      f"elapsed={elapsed:.0f}s ({elapsed/60:.1f}min) rate={rate:.1f} seeds/s eta={eta:.0f}s ({eta/60:.1f}min)", flush=True)

    elapsed_total = time.time() - t0
    print(f"\n[Stage {stage_num}] DONE scanning in {elapsed_total:.1f}s ({elapsed_total/60:.1f} min)")

    all_results.sort(key=lambda r: r[0])
    ranked_best = sorted(all_results, key=lambda r: (-r[1], -r[2], -r[3], -r[4], -r[5], r[0]))
    best = ranked_best[0]

    print(f"\n[Stage {stage_num}] Best seed in this range: #{best[0]}  hit7b={best[1]}  hit7={best[2]}  hit6={best[3]}  hit5={best[4]}  hit4={best[5]}")
    print(f"[Stage {stage_num}] Top 5 seeds (hit7b desc, hit7 desc, hit6 desc, hit5 desc, hit4 desc):")
    for r in ranked_best[:5]:
        print(f"  seed={r[0]:9d}  hit7b={r[1]:2d}  hit7={r[2]:2d}  hit6={r[3]:3d}  hit5={r[4]:3d}  hit4={r[5]:3d}")

    out = {
        'stage': stage_num, 'seedRange': [SEED_LO, SEED_HI], 'numSeeds': num_seeds,
        'kPicks': K_PICKS, 'poolMax': LOTO7_MAX, 'nDraws': N_DRAWS, 'drawRange': [DRAW_START, DRAW_END],
        'best': {'seed': best[0], 'hit7b': best[1], 'hit7': best[2], 'hit6': best[3], 'hit5': best[4], 'hit4': best[5]},
        'top10': [{'seed': r[0], 'hit7b': r[1], 'hit7': r[2], 'hit6': r[3], 'hit5': r[4], 'hit4': r[5]} for r in ranked_best[:10]],
        'results': all_results,
    }
    with open(OUT_JSON, 'w') as f:
        json.dump(out, f, separators=(',', ':'))
    print(f"\n[Stage {stage_num}] Saved {OUT_JSON}")

if __name__ == '__main__':
    main()
