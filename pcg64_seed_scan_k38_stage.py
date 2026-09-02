"""
pcg64_seed_scan_k38_stage.py
-----------------------------------
Parameterized stage runner for the PCG64 K=38 seed scan -- the PCG64
companion to the xoshiro256** K20/K30/K38 scans, testing whether
swapping the underlying PRNG FAMILY (not just K) changes anything.
Seed range -5,000,000 to 5,000,000 (10,000,001 seeds total, wider
than the xoshiro scans' -3M to 3M per explicit request), split into
10 stages along the same round-million boundary convention used for
K20/K30 (stage 1 spans -5,000,000 to -4,000,000 inclusive on both
ends = 1,000,001 seeds; stages 2-10 each cover the next 1,000,000).
Same draw window #1-2050 (2050 draws) as every prior scan, for direct
comparability.

PCG64 construction (O'Neill's PCG XSL-RR 128/64, NumPy's default
PCG64 -- verified bit-exact against numpy.random.Generator(PCG64())
via direct low-level state injection, bypassing SeedSequence):
  1. combined = (seed * 10,000,000 + draw_serial) & MASK64 -- IDENTICAL
     formula/convention to every xoshiro scan on this site.
  2. combined is expanded into PCG64's raw 128-bit {state, inc} via
     SplitMix64 run four times (same expansion primitive xoshiro uses
     for its 256-bit state, just producing 128+128 bits instead of
     4x64) -- this is OUR OWN seeding convention (bypassing NumPy's
     SeedSequence, which would be a much heavier lift to port bit-
     exact into browser JS), chosen to keep this scan methodologically
     parallel to the xoshiro scans.
  3. Core step (O'Neill's standard construction, advance-then-output):
     state = (state * 0x2360ed051fc65da44385df649fccf645 + inc) mod 2^128
     output = rotr64((state>>64) ^ (state & MASK64), state>>122)
  4. K=38 picks via the same partial Fisher-Yates over range(1,44),
     generation-order convention (push swapped value immediately, loop
     i = n-1 down to n-k) as every other scan.

Self-checks against known-good reference vectors computed
independently via a separately-validated pure-Python PCG64
implementation that was itself verified bit-exact against NumPy's
actual PCG64 bit generator (10/10 raw outputs matched, via direct
state injection) before this script was written.

Benchmarked (single-threaded, this session, same machine) at ~1.65x
FASTER per call than the xoshiro256** implementation used for K20/K30
-- PCG64's core (one 128-bit multiply-add, one xor-shift, one rotate)
is cheaper in pure Python than xoshiro256**'s multi-step rotate/xor
chain, despite operating on wider integers. Estimated ~100-110
seeds/s at K=38 with 7 workers (vs K=30's actual observed 80 seeds/s)
-- roughly ~2.5-2.8 hr/stage, ~25-28 hr for all 10 stages.

Usage: python pcg64_seed_scan_k38_stage.py <stage_num> <seed_lo> <seed_hi>
Example: python pcg64_seed_scan_k38_stage.py 1 -5000000 -4000000
"""
import json, re, time, sys, math, os
import multiprocessing as mp
from collections import Counter

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
ENV_LOCAL = BASE + r"\.env.local"

K_PICKS = 38
DRAW_START, DRAW_END = 1, 2050
N_DRAWS = DRAW_END - DRAW_START + 1  # 2050
LOTO6_MAX = 43
N_WORKERS = 7
CHUNK_SIZE = 200

MASK64 = 0xFFFFFFFFFFFFFFFF
MASK128 = (1 << 128) - 1
PCG_MULT_128 = 0x2360ed051fc65da44385df649fccf645

def pcg64_predict_inline(seed, draw_serial, k, pool_max, arr_template):
    combined = (seed * 10_000_000 + draw_serial) & MASK64
    z = combined & MASK64
    outs = []
    for _ in range(4):
        z = (z + 0x9E3779B97F4A7C15) & MASK64
        zz = z
        zz = ((zz ^ (zz >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
        zz = ((zz ^ (zz >> 27)) * 0x94D049BB133111EB) & MASK64
        zz = zz ^ (zz >> 31)
        outs.append(zz)
    state = ((outs[0] << 64) | outs[1]) & MASK128
    inc = (((outs[2] << 64) | outs[3]) | 1) & MASK128
    arr = arr_template[:]
    n = pool_max
    for i in range(n - 1, n - 1 - k, -1):
        state = (state * PCG_MULT_128 + inc) & MASK128
        xored = (state >> 64) ^ (state & MASK64)
        rot = (state >> 122) & 0x3f
        result = ((xored >> rot) | (xored << ((-rot) & 63))) & MASK64
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
            picks = pcg64_predict_inline(seed, serial, K_PICKS, LOTO6_MAX, arr_template)
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
    OUT_JSON = BASE + rf"\pcg64_seed_scan_k38_stage{stage_num}.json"

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

    def pcg64_predict_modular(seed, draw_serial, k=K_PICKS, pool_max=LOTO6_MAX):
        combined = (seed * 10_000_000 + draw_serial) & MASK64
        z = combined & MASK64
        outs = []
        for _ in range(4):
            z = (z + 0x9E3779B97F4A7C15) & MASK64
            zz = z
            zz = ((zz ^ (zz >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
            zz = ((zz ^ (zz >> 27)) * 0x94D049BB133111EB) & MASK64
            zz = zz ^ (zz >> 31)
            outs.append(zz)
        state = ((outs[0] << 64) | outs[1]) & MASK128
        inc = (((outs[2] << 64) | outs[3]) | 1) & MASK128
        def rotr64(v, rot):
            rot &= 63
            return ((v >> rot) | (v << ((-rot) & 63))) & MASK64
        arr = list(range(1, pool_max + 1))
        n = len(arr)
        for i in range(n - 1, n - 1 - k, -1):
            state = (state * PCG_MULT_128 + inc) & MASK128
            xored = (state >> 64) ^ (state & MASK64)
            rot = (state >> 122) & 0x3f
            result = rotr64(xored, rot)
            j = result % (i + 1)
            arr[i], arr[j] = arr[j], arr[i]
        return sorted(arr[n - k:])

    arr_t = list(range(1, LOTO6_MAX + 1))

    # Fixed known-good reference vectors, computed independently via a
    # separately-validated pure-Python PCG64 implementation that was itself
    # verified bit-exact against numpy.random.Generator(PCG64()) (direct
    # low-level state injection, bypassing SeedSequence) before this script
    # was ever written. Uses the GLOBAL scan's extreme/special seeds
    # (-5,000,000 / 5,000,000 / 0 / -1), not this particular stage's own
    # bounds, so the same fixed set is reused unchanged across all 10 stages.
    KNOWN_GOOD = {
        (-5000000, 1):    [1, 2, 3, 4, 5, 6, 7, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 20, 21, 22, 23, 25, 26, 27, 28, 30, 31, 32, 33, 34, 35, 36, 37, 39, 40, 41, 42, 43],
        (5000000, 2050):  [1, 2, 3, 5, 6, 8, 9, 10, 11, 12, 13, 14, 15, 17, 18, 19, 20, 21, 23, 24, 25, 26, 27, 28, 29, 30, 31, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43],
        (0, 1):           [1, 2, 4, 5, 6, 7, 8, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 23, 24, 25, 26, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43],
        (-1, 2050):       [1, 2, 4, 5, 6, 7, 8, 9, 10, 11, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 28, 29, 30, 31, 32, 33, 34, 35, 37, 38, 39, 40, 41, 42],
        (-5000000, 2050): [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 16, 17, 19, 20, 21, 23, 24, 25, 26, 27, 28, 29, 30, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43],
        (4000000, 1):     [1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 12, 13, 15, 16, 17, 18, 19, 20, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 35, 36, 37, 38, 39, 40, 41, 42, 43],
    }
    for (test_seed, test_draw), expected in KNOWN_GOOD.items():
        inline_result = sorted(pcg64_predict_inline(test_seed, test_draw, K_PICKS, LOTO6_MAX, arr_t))
        modular_result = pcg64_predict_modular(test_seed, test_draw)
        assert inline_result == expected, f"INLINE MISMATCH vs known-good seed={test_seed} draw={test_draw}: {inline_result} vs {expected}"
        assert modular_result == expected, f"MODULAR MISMATCH vs known-good seed={test_seed} draw={test_draw}: {modular_result} vs {expected}"
        assert len(inline_result) == K_PICKS, f"WRONG PICK COUNT seed={test_seed}: {len(inline_result)} != {K_PICKS}"

    # Also self-check this stage's own boundary seeds against each other (inline vs modular)
    boundary_cases = [(SEED_LO, DRAW_START), (SEED_HI, DRAW_END), (SEED_LO, DRAW_END), (SEED_HI, DRAW_START)]
    for test_seed, test_draw in boundary_cases:
        inline_result = sorted(pcg64_predict_inline(test_seed, test_draw, K_PICKS, LOTO6_MAX, arr_t))
        modular_result = pcg64_predict_modular(test_seed, test_draw)
        assert inline_result == modular_result, f"MISMATCH seed={test_seed} draw={test_draw}: {inline_result} vs {modular_result}"
        assert len(inline_result) == K_PICKS, f"WRONG PICK COUNT seed={test_seed}: {len(inline_result)} != {K_PICKS}"
    print(f"[Stage {stage_num}] Self-check OK: inlined fast-path (K={K_PICKS}, PCG64) matches both the verified modular "
          f"implementation AND {len(KNOWN_GOOD)} independently-computed known-good reference vectors (incl. negative seeds).")

    seeds = list(range(SEED_LO, SEED_HI + 1))
    num_seeds = len(seeds)
    chunks = [seeds[i:i + CHUNK_SIZE] for i in range(0, len(seeds), CHUNK_SIZE)]
    total_chunks = len(chunks)
    print(f"\n[Stage {stage_num}] Scanning seeds {SEED_LO:,} to {SEED_HI:,} ({num_seeds:,} seeds) x {N_DRAWS} draws x K={K_PICKS} (PCG64), "
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
        'kPicks': K_PICKS, 'nDraws': N_DRAWS, 'drawRange': [DRAW_START, DRAW_END], 'algorithm': 'PCG64',
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
