"""
xoshiro_seed_scan_loto7_k25_10k.py
-------------------------------------
First xoshiro256** seed scan for Loto7 (7 from 1-37, plus 2 bonus
numbers): seeds 0-10,000 (starting range -- same iterative pattern as
the Loto6 xoshiro scans, likely extended later), K=25 picks per seed
per draw, backtested against the FIRST 500 Loto7 draws (#1-500) --
NOT the most recent, per explicit instruction.

Reuses the exact xoshiro256**/SplitMix64 algorithm and combined-seed
formula (seed*10,000,000 + draw_serial) already verified for Loto6
(see xoshiro_seed_scan_k33_10k.py / gen_xoshiro_seed_backtest.py),
just reparameterized: pool_max=37 (not 43), K=25 (not 33).

Loto7 has 2 bonus numbers (bonus1, bonus2), confirmed from
loto7_results' schema (lib/db7.ts) and the existing 16-method Loto7
backtest convention (precompute_loto7_backtest100_multik.py): hit7b =
draws where the picks contain all 7 main winning numbers AND at least
one of the two bonus numbers ("either bonus", not "both").

Tracks 5 metrics per seed, matching the established Loto7 ranking
convention (hit7b -> hit7 -> hit6 -> hit5 -> hit4, one tier deeper
than Loto6's hit6b -> hit6 -> hit5 since Loto7 has 7 main numbers):
  - hit7b: 7-hit AND (bonus1 in picks OR bonus2 in picks)
  - hit7:  all 7 main numbers hit (regardless of bonus)
  - hit6:  exactly 6 of 7 main numbers hit
  - hit5:  exactly 5 of 7 main numbers hit
  - hit4:  exactly 4 of 7 main numbers hit

Parallelized across worker processes (mirrors xoshiro_seed_scan_k33_10k.py).

Run: python xoshiro_seed_scan_loto7_k25_10k.py
"""
import json, os, re, time, math
import multiprocessing as mp
from collections import Counter

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
ENV_LOCAL = BASE + r"\.env.local"
OUT_JSON = BASE + r"\xoshiro_seed_scan_loto7_k25_10k.json"

K_PICKS = 25
DRAW_START, DRAW_END = 1, 500
N_DRAWS = DRAW_END - DRAW_START + 1  # 500
LOTO7_MAX = 37
NUM_SEEDS = 10_001    # seeds 0..10000 inclusive
N_WORKERS = 7
CHUNK_SIZE = 200

MASK64 = 0xFFFFFFFFFFFFFFFF

# ── Core algorithm (bit-identical to the Loto6 scans, pool_max=37) ──────────
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
        hits_dist = [0, 0, 0, 0, 0, 0, 0, 0]  # index = exact hit count 0..7
        for serial, actual_set, b1, b2 in _DATA:
            picks = xoshiro_predict_inline(seed, serial, K_PICKS, LOTO7_MAX, arr_template)
            picks_set = frozenset(picks)
            h = len(actual_set & picks_set)
            hits_dist[h] += 1
            if h == 7 and (b1 in picks_set or b2 in picks_set):
                hit7b += 1
        out.append((seed, hit7b, hits_dist[7], hits_dist[6], hits_dist[5], hits_dist[4]))
    return out

def main():
    # ── Fetch first 500 Loto7 draws from Postgres ────────────────────────────
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
    db_rows = cur.fetchall()
    conn.close()
    print(f"Fetched {len(db_rows)} Loto7 draws (#{db_rows[0][0]}-{db_rows[-1][0]}).")
    if len(db_rows) != N_DRAWS or db_rows[0][0] != DRAW_START or db_rows[-1][0] != DRAW_END:
        raise SystemExit(f"Draw window mismatch: got {len(db_rows)} rows, expected {N_DRAWS} rows #{DRAW_START}-{DRAW_END}")
    serials = [r[0] for r in db_rows]
    if serials != list(range(DRAW_START, DRAW_END + 1)):
        raise SystemExit("Gap detected in draw_serial sequence #1-500 -- window assumption is stale.")

    DATA = [{'s': r[0], 'a': list(r[1:8]), 'b1': r[8], 'b2': r[9]} for r in db_rows]
    data_bytes = json.dumps(DATA)
    print(f"Confirmed: {len(DATA)} consecutive draws, #{DATA[0]['s']}-{DATA[-1]['s']}, no gaps. "
          f"Sample row: {DATA[0]}")

    # ── Self-check: inlined fast-path vs a from-scratch modular reference ───
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
    for test_seed, test_draw in [(0, 1), (168, 250), (9999, 500), (5555, 100), (10000, 500)]:
        inline_result = sorted(xoshiro_predict_inline(test_seed, test_draw, K_PICKS, LOTO7_MAX, arr_t))
        modular_result = xoshiro_predict_modular(test_seed, test_draw)
        assert inline_result == modular_result, f"MISMATCH seed={test_seed} draw={test_draw}: {inline_result} vs {modular_result}"
        assert len(inline_result) == K_PICKS, f"WRONG PICK COUNT seed={test_seed}: {len(inline_result)} != {K_PICKS}"
        assert len(set(inline_result)) == K_PICKS, f"DUPLICATE NUMBERS seed={test_seed}: {inline_result}"
        assert all(1 <= n <= LOTO7_MAX for n in inline_result), f"OUT OF RANGE seed={test_seed}: {inline_result}"
    print(f"Self-check: inlined fast-path (K={K_PICKS}, pool_max={LOTO7_MAX}) matches the modular reference exactly. OK.")

    # ── Timing sample: 50 seeds, to project full-scan ETA ────────────────────
    sample_chunk = list(range(50))
    global _DATA
    init_worker(data_bytes)
    t0 = time.time()
    process_chunk(sample_chunk)
    sample_elapsed = time.time() - t0
    per_seed = sample_elapsed / 50
    projected_serial = per_seed * NUM_SEEDS
    projected_parallel = projected_serial / N_WORKERS
    print(f"\nTiming sample: 50 seeds x {N_DRAWS} draws in {sample_elapsed:.2f}s ({per_seed*1000:.2f}ms/seed)")
    print(f"Projected: {NUM_SEEDS:,} seeds serial ~= {projected_serial:.0f}s ({projected_serial/60:.1f} min), "
          f"~{N_WORKERS} workers ~= {projected_parallel:.0f}s ({projected_parallel/60:.1f} min)")

    # ── Parallel scan ────────────────────────────────────────────────────────
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

    # ── Rank: highest hit7b, tiebreak hit7, hit6, hit5, hit4 ─────────────────
    all_results.sort(key=lambda r: r[0])
    ranked = sorted(all_results, key=lambda r: (-r[1], -r[2], -r[3], -r[4], -r[5], r[0]))
    best = ranked[0]

    hit7b_vals = [r[1] for r in all_results]
    hit7_vals  = [r[2] for r in all_results]
    hit6_vals  = [r[3] for r in all_results]
    hit5_vals  = [r[4] for r in all_results]
    hit4_vals  = [r[5] for r in all_results]

    hit7b_dist = Counter(hit7b_vals)
    hit7_dist  = Counter(hit7_vals)
    hit6_dist  = Counter(hit6_vals)
    hit5_dist  = Counter(hit5_vals)
    hit4_dist  = Counter(hit4_vals)

    # ── Analytical hypergeometric baselines (pure-chance expectation) ───────
    def hyper_pmf(x, pool, success, draws):
        return (math.comb(success, x) * math.comb(pool - success, draws - x)) / math.comb(pool, draws)
    def prob_all_in(subset_size_needed, pool_max, pick_k):
        return math.comb(pool_max - subset_size_needed, pick_k - subset_size_needed) / math.comb(pool_max, pick_k)

    # hit7b: needs all 7 main + at least 1 of 2 bonus. Exact combinatorial
    # decomposition: P(7 main in AND >=1 bonus in) = P(7 main in) x (1 - P(neither bonus in | 7 main in)).
    p_hit7_only = hyper_pmf(7, LOTO7_MAX, 7, K_PICKS)
    # Direct combinatorial: choose K_PICKS positions from pool such that all 7 main included;
    # remaining K-7 picks drawn from the other pool_max-7 numbers, 2 of which are bonus.
    remaining_pool = LOTO7_MAX - 7
    remaining_picks = K_PICKS - 7
    # P(neither bonus in remaining picks | 7 main in) = C(remaining_pool-2, remaining_picks) / C(remaining_pool, remaining_picks)
    p_neither_bonus = math.comb(remaining_pool - 2, remaining_picks) / math.comb(remaining_pool, remaining_picks)
    p_hit7b = p_hit7_only * (1 - p_neither_bonus)
    p_hit6 = hyper_pmf(6, LOTO7_MAX, 7, K_PICKS)
    p_hit5 = hyper_pmf(5, LOTO7_MAX, 7, K_PICKS)
    p_hit4 = hyper_pmf(4, LOTO7_MAX, 7, K_PICKS)

    exp_hit7b = p_hit7b * N_DRAWS
    exp_hit7 = p_hit7_only * N_DRAWS
    exp_hit6 = p_hit6 * N_DRAWS
    exp_hit5 = p_hit5 * N_DRAWS
    exp_hit4 = p_hit4 * N_DRAWS

    print(f"\n=== Results across {NUM_SEEDS:,} seeds (K={K_PICKS}, pool={LOTO7_MAX}, draws #{DRAW_START}-{DRAW_END}) ===")
    print(f"Best seed: #{best[0]}  hit7b={best[1]}  hit7={best[2]}  hit6={best[3]}  hit5={best[4]}  hit4={best[5]}")
    print(f"Analytical per-seed expectation (pure chance): hit7b~={exp_hit7b:.3f} hit7~={exp_hit7:.2f} "
          f"hit6~={exp_hit6:.2f} hit5~={exp_hit5:.2f} hit4~={exp_hit4:.2f} (out of {N_DRAWS} draws)")

    print(f"\nTop 10 seeds by ranking (hit7b desc, hit7 desc, hit6 desc, hit5 desc, hit4 desc):")
    for r in ranked[:10]:
        print(f"  seed={r[0]:6d}  hit7b={r[1]:2d}  hit7={r[2]:2d}  hit6={r[3]:3d}  hit5={r[4]:3d}  hit4={r[5]:3d}")

    # ── Save ──────────────────────────────────────────────────────────────────
    out = {
        'numSeeds': NUM_SEEDS, 'kPicks': K_PICKS, 'poolMax': LOTO7_MAX, 'nDraws': N_DRAWS,
        'drawRange': [DRAW_START, DRAW_END],
        'analyticalExpectation': {'hit7b': exp_hit7b, 'hit7': exp_hit7, 'hit6': exp_hit6, 'hit5': exp_hit5, 'hit4': exp_hit4},
        'best': {'seed': best[0], 'hit7b': best[1], 'hit7': best[2], 'hit6': best[3], 'hit5': best[4], 'hit4': best[5]},
        'hit7bDistribution': dict(hit7b_dist),
        'hit7Distribution': dict(hit7_dist),
        'hit6Distribution': dict(hit6_dist),
        'hit5Distribution': dict(hit5_dist),
        'hit4Distribution': dict(hit4_dist),
        'top10': [{'seed': r[0], 'hit7b': r[1], 'hit7': r[2], 'hit6': r[3], 'hit5': r[4], 'hit4': r[5]} for r in ranked[:10]],
        'results': all_results,  # [seed, hit7b, hit7, hit6, hit5, hit4]
    }
    with open(OUT_JSON, 'w') as f:
        json.dump(out, f, separators=(',', ':'))
    print(f"\nSaved {OUT_JSON}")

if __name__ == '__main__':
    main()
