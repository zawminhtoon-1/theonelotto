"""
xoshiro_seed_scan_k38_full.py
------------------------------
Full expansion of the xoshiro256** K=38 seed scan from the current
0-1,000,000 range to -10,000,000 to 10,000,000 (20,000,001 seeds),
against draws #1-2100 (widened from the existing scan's #1000-2131
window, per explicit request), to find and report the best 10 and
worst 10 seeds. Updates xoshiro_seed_scan_k38.html in place once done.

Same construction as every other xoshiro256** scan on this site
(SplitMix64-expanded state, combined seed = seed*10,000,000 +
draw_serial, partial Fisher-Yates over range(1,44)). Self-checked
against the site's established known-good reference vector (seed
692809, draw 2129, K=38) plus an inline-vs-modular cross-check on
each stage's own boundary seeds before trusting the stage.

SCORING (v2, replaces the original hit6b-first ranking): per-draw
score based on how many of the 6 winning numbers land in the seed's
K=38 pick, summed across all draws in the scan window --
  0 hits -> -5   1 hit -> -4   2 hits -> -3   3 hits -> -2   4+ hits -> +1
Best seed = highest total score, worst = lowest. This needs the full
per-draw hit-count histogram (0 through 6) per seed, not just the
hit6b/hit6/hit5/hit4 aggregates the v1 version of this script tracked
-- v1's 0/1/2/3-hit draws were discarded entirely (never bucketed),
so v1's stage checkpoints (stage1-3.json, produced before this
rewrite) can't be rescored after the fact and were deleted; this
version starts the full 20-stage run over from stage 1. (Restarting
was unavoidable for a different reason too: this driver runs all 20
stages in one continuous process, and editing this file on disk
can't change an already-running process's code -- Python doesn't
hot-reload -- so getting the new scoring applied at all, even just
for not-yet-started stages, requires restarting the driver.)

Benchmarked on this machine before starting: 7.22 seeds/s
single-process at K=38 x 2100 draws -> ~50.5 seeds/s aggregate with
7 workers -> ~110 hours (~4.6 days) for the full 20,000,001 seeds
(v1 benchmark; the extra hit0-3 bucketing added here is a few more
cheap branches on a value already computed per draw, not expected to
meaningfully change this).

Staged in 20 chunks of ~1,000,000 seeds each (same round-million
boundary convention as the PCG64 K=30/K=38 scans' 10-stage split),
each stage ~5.5 hours. Runs ALL stages sequentially in one process so
nothing needs to be manually re-launched between stages. Idempotent /
resumable: skips any stage whose xoshiro_seed_scan_k38_stage{N}.json
already exists, so a crash or restart just picks up where it left off
by re-running this same script.

After all 20 stages, combines every stage's results to report the
global best-10 / worst-10 (by score) across the full -10,000,000 to
10,000,000 range and writes xoshiro_seed_scan_k38_full_summary.json.

Run: python xoshiro_seed_scan_k38_full.py
"""
import json, re, time, os
import multiprocessing as mp

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
ENV_LOCAL = BASE + r"\.env.local"

K_PICKS = 38
DRAW_START, DRAW_END = 1, 2100
N_DRAWS = DRAW_END - DRAW_START + 1  # 2100
LOTO6_MAX = 43
N_WORKERS = 7
CHUNK_SIZE = 200

MASK64 = 0xFFFFFFFFFFFFFFFF

# Same round-million-boundary convention as the PCG64 K=38 10-stage scan,
# just doubled in range: stage 1 is double-inclusive (1,000,001 seeds),
# stages 2-20 each cover the next round 1,000,000.
STAGE_BOUNDS = [(-10_000_000, -9_000_000)]
lo = -8_999_999
while lo <= 10_000_000:
    hi = lo + 999_999
    STAGE_BOUNDS.append((lo, hi))
    lo = hi + 1
assert len(STAGE_BOUNDS) == 20, f"expected 20 stages, got {len(STAGE_BOUNDS)}"
assert STAGE_BOUNDS[0][0] == -10_000_000 and STAGE_BOUNDS[-1][1] == 10_000_000
assert sum(hi - lo + 1 for lo, hi in STAGE_BOUNDS) == 20_000_001


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
    picks = []
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
        picks.append(arr[i])
    return picks


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
    def xnext(s):
        result = (rotl((s[1] * 5) & MASK64, 7) * 9) & MASK64
        t = (s[1] << 17) & MASK64
        s[2] ^= s[0]; s[3] ^= s[1]; s[1] ^= s[2]; s[0] ^= s[3]
        s[2] ^= t
        s[3] = rotl(s[3], 45)
        return result
    arr = list(range(1, pool_max + 1))
    n = len(arr)
    order = []
    for i in range(n - 1, n - 1 - k, -1):
        r = xnext(state)
        j = r % (i + 1)
        arr[i], arr[j] = arr[j], arr[i]
        order.append(arr[i])
    return sorted(order)


def init_worker(data_bytes):
    global _DATA
    rows = json.loads(data_bytes)
    _DATA = [(r['s'], frozenset(r['a']), r['b']) for r in rows]


# Per-draw score by hit count, per the new scoring definition.
SCORE_BY_HITS = {0: -5, 1: -4, 2: -3, 3: -2, 4: 1, 5: 1, 6: 1}


def process_chunk(seed_chunk):
    arr_template = list(range(1, LOTO6_MAX + 1))
    out = []
    for seed in seed_chunk:
        hit6b = hit6 = hit5 = hit4 = hit3 = hit2 = hit1 = hit0 = 0
        score = 0
        for serial, actual_set, bonus in _DATA:
            picks = xoshiro_predict_inline(seed, serial, K_PICKS, LOTO6_MAX, arr_template)
            picks_set = frozenset(picks)
            h = len(actual_set & picks_set)
            score += SCORE_BY_HITS[h]
            if h == 6:
                hit6 += 1
                if bonus in picks_set:
                    hit6b += 1
            elif h == 5:
                hit5 += 1
            elif h == 4:
                hit4 += 1
            elif h == 3:
                hit3 += 1
            elif h == 2:
                hit2 += 1
            elif h == 1:
                hit1 += 1
            else:
                hit0 += 1
        out.append((seed, score, hit6b, hit6, hit5, hit4, hit3, hit2, hit1, hit0))
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


def run_stage(stage_num, seed_lo, seed_hi, data_bytes, arr_t):
    out_json = BASE + rf"\xoshiro_seed_scan_k38_stage{stage_num}.json"
    if os.path.exists(out_json):
        print(f"[Stage {stage_num}] Already done ({out_json} exists) -- skipping.")
        return

    # Known-good reference: seed 692,809 / draw 2129 / K=38, used throughout
    # this site's other xoshiro pages -- confirms neither implementation has
    # drifted from ground truth.
    KNOWN_2129 = [2,3,4,5,6,7,8,9,11,12,13,14,15,16,17,18,19,20,21,22,24,25,27,28,29,30,31,32,33,34,35,36,38,39,40,41,42,43]
    inline_692809 = sorted(xoshiro_predict_inline(692809, 2129, K_PICKS, LOTO6_MAX, arr_t))
    modular_692809 = xoshiro_predict_modular(692809, 2129)
    assert inline_692809 == KNOWN_2129, f"INLINE MISMATCH vs known-good: {inline_692809}"
    assert modular_692809 == KNOWN_2129, f"MODULAR MISMATCH vs known-good: {modular_692809}"

    # Cross-check inline vs modular on this stage's own boundary seeds.
    boundary_cases = [(seed_lo, DRAW_START), (seed_hi, DRAW_END), (seed_lo, DRAW_END), (seed_hi, DRAW_START)]
    for test_seed, test_draw in boundary_cases:
        inline_result = sorted(xoshiro_predict_inline(test_seed, test_draw, K_PICKS, LOTO6_MAX, arr_t))
        modular_result = xoshiro_predict_modular(test_seed, test_draw)
        assert inline_result == modular_result, f"MISMATCH seed={test_seed} draw={test_draw}: {inline_result} vs {modular_result}"
        assert len(inline_result) == K_PICKS
    print(f"[Stage {stage_num}] Self-check OK (known-good ref + boundary-seed inline/modular cross-check).")

    seeds = list(range(seed_lo, seed_hi + 1))
    num_seeds = len(seeds)
    chunks = [seeds[i:i + CHUNK_SIZE] for i in range(0, len(seeds), CHUNK_SIZE)]
    total_chunks = len(chunks)
    print(f"[Stage {stage_num}] Scanning seeds {seed_lo:,} to {seed_hi:,} ({num_seeds:,} seeds) x {N_DRAWS} draws x K={K_PICKS} (xoshiro256**), "
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
    print(f"[Stage {stage_num}] DONE scanning in {elapsed_total:.1f}s ({elapsed_total/3600:.2f} hr)")

    # r = (seed, score, hit6b, hit6, hit5, hit4, hit3, hit2, hit1, hit0)
    all_results.sort(key=lambda r: r[0])
    ranked_best = sorted(all_results, key=lambda r: (-r[1], r[0]))
    ranked_worst = sorted(all_results, key=lambda r: (r[1], r[0]))
    best, worst = ranked_best[0], ranked_worst[0]

    def _rec(r):
        return {'seed': r[0], 'score': r[1], 'hit6b': r[2], 'hit6': r[3], 'hit5': r[4],
                'hit4': r[5], 'hit3': r[6], 'hit2': r[7], 'hit1': r[8], 'hit0': r[9]}

    print(f"[Stage {stage_num}] Best  seed in this range: #{best[0]}  score={best[1]}  hit6b={best[2]}  hit6={best[3]}  hit5={best[4]}  hit4={best[5]}")
    print(f"[Stage {stage_num}] Worst seed in this range: #{worst[0]}  score={worst[1]}  hit6b={worst[2]}  hit6={worst[3]}  hit5={worst[4]}  hit4={worst[5]}")

    out = {
        'stage': stage_num, 'seedRange': [seed_lo, seed_hi], 'numSeeds': num_seeds,
        'kPicks': K_PICKS, 'nDraws': N_DRAWS, 'drawRange': [DRAW_START, DRAW_END], 'algorithm': 'xoshiro256**',
        'scoring': 'v2: -5/-4/-3/-2/+1 for 0/1/2/3/4+ hits per draw, summed',
        'best': _rec(best),
        'worst': _rec(worst),
        'top10': [_rec(r) for r in ranked_best[:10]],
        'bottom10': [_rec(r) for r in ranked_worst[:10]],
        'elapsedSeconds': elapsed_total,
        'results': all_results,
    }
    with open(out_json, 'w') as f:
        json.dump(out, f, separators=(',', ':'))
    print(f"[Stage {stage_num}] Saved {out_json}\n")


def combine_and_summarize():
    all_top10 = []
    all_bottom10 = []
    total_seeds = 0
    for stage_num, (lo, hi) in enumerate(STAGE_BOUNDS, 1):
        path = BASE + rf"\xoshiro_seed_scan_k38_stage{stage_num}.json"
        with open(path) as f:
            d = json.load(f)
        total_seeds += d['numSeeds']
        all_top10.extend(d['top10'])
        all_bottom10.extend(d['bottom10'])

    ranked_best = sorted(all_top10, key=lambda r: (-r['score'], r['seed']))[:10]
    ranked_worst = sorted(all_bottom10, key=lambda r: (r['score'], r['seed']))[:10]

    summary = {
        'seedRange': [-10_000_000, 10_000_000],
        'numSeeds': total_seeds,
        'kPicks': K_PICKS, 'nDraws': N_DRAWS, 'drawRange': [DRAW_START, DRAW_END], 'algorithm': 'xoshiro256**',
        'scoring': 'v2: -5/-4/-3/-2/+1 for 0/1/2/3/4+ hits per draw, summed',
        'best10': ranked_best,
        'worst10': ranked_worst,
        'numStages': len(STAGE_BOUNDS),
    }
    with open(BASE + r"\xoshiro_seed_scan_k38_full_summary.json", 'w') as f:
        json.dump(summary, f, indent=2)

    print("\n" + "=" * 70)
    print(f"FULL SCAN COMPLETE: {total_seeds:,} seeds x {N_DRAWS} draws")
    print("=" * 70)
    print("\nBest 10 seeds (by score, highest first):")
    for r in ranked_best:
        print(f"  seed={r['seed']:11d}  score={r['score']:6d}  hit6b={r['hit6b']:4d}  hit6={r['hit6']:4d}  hit5={r['hit5']:4d}  hit4={r['hit4']:4d}")
    print("\nWorst 10 seeds (by score, lowest first):")
    for r in ranked_worst:
        print(f"  seed={r['seed']:11d}  score={r['score']:6d}  hit6b={r['hit6b']:4d}  hit6={r['hit6']:4d}  hit5={r['hit5']:4d}  hit4={r['hit4']:4d}")
    print(f"\nSaved {BASE}\\xoshiro_seed_scan_k38_full_summary.json")


def main():
    DATA = load_data_from_db()
    print(f"Loaded {len(DATA)} rows from loto6_results for draws {DRAW_START}-{DRAW_END} (expected {N_DRAWS}).")
    serials = [r['s'] for r in DATA]
    if len(DATA) != N_DRAWS:
        raise SystemExit(f"Row count mismatch: got {len(DATA)}, expected {N_DRAWS}")
    if serials != list(range(DRAW_START, DRAW_END + 1)):
        raise SystemExit("Gap check FAILED -- draws #1-2100 are not fully consecutive in the DB.")
    print(f"Verified: {len(DATA)} consecutive draws, no gaps, #{DRAW_START}-{DRAW_END} exactly.\n")
    data_bytes = json.dumps(DATA)
    arr_t = list(range(1, LOTO6_MAX + 1))

    overall_t0 = time.time()
    for stage_num, (seed_lo, seed_hi) in enumerate(STAGE_BOUNDS, 1):
        run_stage(stage_num, seed_lo, seed_hi, data_bytes, arr_t)

    print(f"\nAll 20 stages done in {(time.time()-overall_t0)/3600:.2f}hr (this run; earlier stages may have been skipped as already-done).")
    combine_and_summarize()


if __name__ == '__main__':
    main()
