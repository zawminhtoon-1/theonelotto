"""
xoshiro_seed_scan_k30_stage.py
-----------------------------------
Parameterized stage runner for the K=30 companion to the K=20 scan:
same seed range -3,000,000 to 3,000,000 (6,000,001 seeds total), same
6 stages of 1,000,001 seeds each, same draw window #1-2050 (2050
draws -- matched exactly to the K=20 scan's fixed window, not a
trailing window to the current latest draw, for direct apples-to-
apples comparability between the two scans). Only difference: K=30
picks instead of K=20. Same xoshiro256** algorithm/formula as every
other K-value scan on this site. hit6b/hit6/hit5/hit4 metrics, same
convention as K=20 (K=30 is still a fairly tight pool relative to 43,
so hit4 remains meaningful).

Estimated runtime (reported before this scan started): ~22.0 hours
best case to ~37.3 hours worst case for all 6 stages combined,
extrapolated from the K=20 scan's actual observed throughput
(93.15 seeds/s average across all 6 stages, 67-114 seeds/s range)
scaled by the K=30/K=20 = 1.5x increase in Fisher-Yates work per
xoshiro_predict call (K=30 picks vs K=20, same 43-number pool).

Self-checks (including negative-seed cases) against known-good
reference vectors computed independently via this session's own
already-validated xoshiro256** implementation (the raw/generation-
order style used in precompute_xoshiro_elim_2133.py -- a THIRD,
separately-structured implementation from the inline/modular pair
below), before scaling. Same 5 (seed, draw) test pairs as the K=20
scan's KNOWN_GOOD, recomputed at K=30.

Usage: python xoshiro_seed_scan_k30_stage.py <stage_num> <seed_lo> <seed_hi>
Example: python xoshiro_seed_scan_k30_stage.py 1 -3000000 -2000000
"""
import json, re, time, sys, math, os
import multiprocessing as mp
from collections import Counter

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
ENV_LOCAL = BASE + r"\.env.local"

K_PICKS = 30
DRAW_START, DRAW_END = 1, 2050
N_DRAWS = DRAW_END - DRAW_START + 1  # 2050
LOTO6_MAX = 43
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
        hit6b = hit6 = hit5 = hit4 = 0
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
            elif h == 4:
                hit4 += 1
        out.append((seed, hit6b, hit6, hit5, hit4))
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
    return [{'s': r[0], 'a': list(r[1:7]), 'b': r[7]} for r in rows]

def main():
    stage_num = int(sys.argv[1])
    SEED_LO = int(sys.argv[2])
    SEED_HI = int(sys.argv[3])
    OUT_JSON = BASE + rf"\xoshiro_seed_scan_k30_stage{stage_num}.json"

    DATA = load_data_from_db()
    print(f"[Stage {stage_num}] Loaded {len(DATA)} rows from loto6_results for draws {DRAW_START}-{DRAW_END} (expected {N_DRAWS}).")
    serials = [r['s'] for r in DATA]
    if len(DATA) != N_DRAWS:
        raise SystemExit(f"Row count mismatch: got {len(DATA)}, expected {N_DRAWS}")
    if serials[0] != DRAW_START or serials[-1] != DRAW_END:
        raise SystemExit(f"Endpoint mismatch: got {serials[0]}-{serials[-1]}, expected {DRAW_START}-{DRAW_END}")
    if serials != list(range(DRAW_START, DRAW_END + 1)):
        missing = sorted(set(range(DRAW_START, DRAW_END + 1)) - set(serials))
        raise SystemExit(f"Gap check FAILED. Missing: {missing[:10]}...")
    print(f"[Stage {stage_num}] Verified: {len(DATA)} consecutive draws, no gaps, #{DRAW_START}-{DRAW_END} exactly.")

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

    # Fixed known-good reference vectors, computed independently via this
    # session's own already-validated xoshiro256** implementation (a THIRD,
    # separately-written implementation, not copy-pasted from either
    # inline/modular pair above) before ever trusting this stage's fast path.
    # Same 5 (seed, draw) test pairs as the K=20 scan, recomputed at K=30.
    KNOWN_GOOD = {
        (-3000000, 1):       [1, 3, 4, 6, 8, 9, 10, 12, 14, 15, 17, 18, 19, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 33, 35, 36, 37, 39, 41, 43],
        (-2000000, 2050):    [2, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 18, 19, 20, 22, 23, 24, 25, 26, 31, 32, 34, 36, 37, 38, 39, 41, 42, 43],
        (0, 1):              [1, 2, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 20, 21, 22, 24, 26, 28, 29, 31, 32, 33, 34, 35, 40, 42, 43],
        (-1, 2050):          [1, 2, 3, 4, 6, 7, 8, 9, 10, 12, 13, 15, 16, 17, 18, 20, 23, 25, 26, 27, 28, 29, 30, 31, 34, 37, 38, 39, 40, 42],
        (-3000000, 2050):    [1, 2, 4, 9, 11, 12, 14, 15, 16, 17, 18, 19, 20, 21, 22, 24, 25, 27, 28, 29, 30, 31, 32, 33, 36, 37, 40, 41, 42, 43],
    }
    for (test_seed, test_draw), expected in KNOWN_GOOD.items():
        inline_result = sorted(xoshiro_predict_inline(test_seed, test_draw, K_PICKS, LOTO6_MAX, arr_t))
        modular_result = xoshiro_predict_modular(test_seed, test_draw)
        assert inline_result == expected, f"INLINE MISMATCH vs known-good seed={test_seed} draw={test_draw}: {inline_result} vs {expected}"
        assert modular_result == expected, f"MODULAR MISMATCH vs known-good seed={test_seed} draw={test_draw}: {modular_result} vs {expected}"
        assert len(inline_result) == K_PICKS, f"WRONG PICK COUNT seed={test_seed}: {len(inline_result)} != {K_PICKS}"

    # Also self-check this stage's own boundary seeds against each other (inline vs modular)
    boundary_cases = [(SEED_LO, DRAW_START), (SEED_HI, DRAW_END), (SEED_LO, DRAW_END), (SEED_HI, DRAW_START)]
    for test_seed, test_draw in boundary_cases:
        inline_result = sorted(xoshiro_predict_inline(test_seed, test_draw, K_PICKS, LOTO6_MAX, arr_t))
        modular_result = xoshiro_predict_modular(test_seed, test_draw)
        assert inline_result == modular_result, f"MISMATCH seed={test_seed} draw={test_draw}: {inline_result} vs {modular_result}"
        assert len(inline_result) == K_PICKS, f"WRONG PICK COUNT seed={test_seed}: {len(inline_result)} != {K_PICKS}"
    print(f"[Stage {stage_num}] Self-check OK: inlined fast-path (K={K_PICKS}) matches both the verified modular implementation "
          f"AND {len(KNOWN_GOOD)} independently-computed known-good reference vectors (incl. negative seeds).")

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
            if i % 25 == 0 or i == total_chunks:
                elapsed = time.time() - t0
                rate = done_seeds / elapsed
                eta = (num_seeds - done_seeds) / rate if rate > 0 else 0
                print(f"[Stage {stage_num}] [{i:,}/{total_chunks:,} chunks, {done_seeds:,}/{num_seeds:,} seeds] "
                      f"elapsed={elapsed:.0f}s ({elapsed/60:.1f}min) rate={rate:.1f} seeds/s eta={eta:.0f}s ({eta/3600:.2f}hr)", flush=True)

    elapsed_total = time.time() - t0
    print(f"\n[Stage {stage_num}] DONE scanning in {elapsed_total:.1f}s ({elapsed_total/3600:.2f} hr)")

    all_results.sort(key=lambda r: r[0])
    ranked_best = sorted(all_results, key=lambda r: (-r[1], -r[2], -r[3], -r[4], r[0]))
    best = ranked_best[0]
    ranked_worst = sorted(all_results, key=lambda r: (r[1], r[2], r[3], r[4], r[0]))
    worst = ranked_worst[0]

    print(f"\n[Stage {stage_num}] Best  seed in this range: #{best[0]}  hit6b={best[1]}  hit6={best[2]}  hit5={best[3]}  hit4={best[4]}")
    print(f"[Stage {stage_num}] Worst seed in this range: #{worst[0]}  hit6b={worst[1]}  hit6={worst[2]}  hit5={worst[3]}  hit4={worst[4]}")
    print(f"\n[Stage {stage_num}] Top 5 seeds (hit6b desc, hit6 desc, hit5 desc, hit4 desc):")
    for r in ranked_best[:5]:
        print(f"  seed={r[0]:9d}  hit6b={r[1]:3d}  hit6={r[2]:3d}  hit5={r[3]:3d}  hit4={r[4]:3d}")

    out = {
        'stage': stage_num, 'seedRange': [SEED_LO, SEED_HI], 'numSeeds': num_seeds,
        'kPicks': K_PICKS, 'nDraws': N_DRAWS, 'drawRange': [DRAW_START, DRAW_END],
        'best': {'seed': best[0], 'hit6b': best[1], 'hit6': best[2], 'hit5': best[3], 'hit4': best[4]},
        'worst': {'seed': worst[0], 'hit6b': worst[1], 'hit6': worst[2], 'hit5': worst[3], 'hit4': worst[4]},
        'top10': [{'seed': r[0], 'hit6b': r[1], 'hit6': r[2], 'hit5': r[3], 'hit4': r[4]} for r in ranked_best[:10]],
        'elapsedSeconds': elapsed_total,
        'results': all_results,
    }
    with open(OUT_JSON, 'w') as f:
        json.dump(out, f, separators=(',', ':'))
    print(f"\n[Stage {stage_num}] Saved {OUT_JSON}")

if __name__ == '__main__':
    main()
