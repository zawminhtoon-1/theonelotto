"""
xoshiro_seed_scan_100k.py
----------------------------
Scratch/reference scan (not a page generator): for seeds 1-100,000, compute
K=21 xoshiro256** picks against all 1000 historical draws (#1127-2126, same
window as xoshiro_seed_backtest.html), same algorithm already verified
against reference test vectors in gen_xoshiro_seed_backtest.py.

Parallelized across worker processes (mirrors the earlier K=7 seed-hit
scan's approach) since 100,000 seeds x 1000 draws x 21 picks is ~100x the
scale of the existing 0-1000 seed page.

For each seed, tracks: avg hits, 6-hit draw count, 0-hit draw count.
Prints periodic progress. Saves full results to xoshiro_seed_scan_100k.json
at the end for reference / potential DB loading.

Run: python xoshiro_seed_scan_100k.py
"""
import json, re, time, sys
import multiprocessing as mp

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
HTML_IN = BASE + r"\public\backtest.html"
OUT_JSON = BASE + r"\xoshiro_seed_scan_100k.json"

K_PICKS = 21
N_DRAWS = 1000
LOTO6_MAX = 43
NUM_SEEDS = 100_000   # seeds 1..100000
N_WORKERS = 7
CHUNK_SIZE = 500      # seeds per work unit, for progress granularity

MASK64 = 0xFFFFFFFFFFFFFFFF

# ── Core algorithm (same as gen_xoshiro_seed_backtest.py, inlined for speed) ──
def xoshiro_predict_inline(seed, draw_serial, k, pool_max, arr_template):
    combined = (seed * 10_000_000 + draw_serial) & MASK64
    # SplitMix64 x4 -> state
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
    arr = arr_template[:]  # fresh copy of [1..pool_max]
    n = pool_max
    for i in range(n - 1, n - 1 - k, -1):
        # inlined xoshiro256** next()
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
    _DATA = [(r['s'], frozenset(r['a'])) for r in rows]

def process_chunk(seed_chunk):
    arr_template = list(range(1, LOTO6_MAX + 1))
    out = []
    for seed in seed_chunk:
        total_hits = 0
        hit6 = 0
        hit0 = 0
        for serial, actual_set in _DATA:
            picks = xoshiro_predict_inline(seed, serial, K_PICKS, LOTO6_MAX, arr_template)
            h = len(actual_set.intersection(picks))
            total_hits += h
            if h == 6:
                hit6 += 1
            elif h == 0:
                hit0 += 1
        avg = total_hits / len(_DATA)
        out.append((seed, round(avg, 4), hit6, hit0))
    return out

def main():
    # ── Load DATA ────────────────────────────────────────────────────────────
    with open(HTML_IN, encoding='utf-8') as f:
        html = f.read()
    m = re.search(r'const DATA\s*=\s*(\[)', html)
    bs = m.start(1)
    depth = 0; pos = bs
    while pos < len(html):
        if html[pos] == '[': depth += 1
        elif html[pos] == ']':
            depth -= 1
            if depth == 0: be = pos + 1; break
        pos += 1
    ALL_DATA = json.loads(html[bs:be])
    DATA = ALL_DATA[-N_DRAWS:]
    print(f"Loaded {len(ALL_DATA)} total entries. Using last {len(DATA)}: draws {DATA[0]['s']}-{DATA[-1]['s']}")

    slim_data = [{'s': r['s'], 'a': r['a']} for r in DATA]
    data_bytes = json.dumps(slim_data)

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
    for test_seed, test_draw in [(1, 1127), (168, 2126), (99999, 1500), (55555, 2000)]:
        inline_result = sorted(xoshiro_predict_inline(test_seed, test_draw, K_PICKS, LOTO6_MAX, arr_t))
        modular_result = xoshiro_predict_modular(test_seed, test_draw)
        assert inline_result == modular_result, f"MISMATCH seed={test_seed} draw={test_draw}: {inline_result} vs {modular_result}"
    print("Self-check: inlined fast-path matches the verified modular implementation exactly. OK.")

    # ── Parallel scan ────────────────────────────────────────────────────────
    seeds = list(range(1, NUM_SEEDS + 1))
    chunks = [seeds[i:i + CHUNK_SIZE] for i in range(0, len(seeds), CHUNK_SIZE)]
    total_chunks = len(chunks)
    print(f"\nScanning {NUM_SEEDS:,} seeds x {len(DATA)} draws x K={K_PICKS}, "
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

    # ── Aggregate stats ──────────────────────────────────────────────────────
    all_results.sort(key=lambda r: r[0])  # by seed
    avgs = [r[1] for r in all_results]
    hit6s = [r[2] for r in all_results]
    hit0s = [r[3] for r in all_results]

    best_by_avg = max(all_results, key=lambda r: r[1])
    best_by_hit6 = max(all_results, key=lambda r: (r[2], r[1]))

    from collections import Counter
    hit6_dist = Counter(hit6s)
    hit0_dist = Counter(hit0s)

    print(f"\n=== Results across {NUM_SEEDS:,} seeds ===")
    print(f"Best seed by avg hits: #{best_by_avg[0]} avg={best_by_avg[1]:.4f} 6hits={best_by_avg[2]} 0hits={best_by_avg[3]}")
    print(f"Best seed by 6-hit count: #{best_by_hit6[0]} 6hits={best_by_hit6[2]} avg={best_by_hit6[1]:.4f} 0hits={best_by_hit6[3]}")
    BASELINE = K_PICKS * 6 / LOTO6_MAX
    print(f"Random baseline avg: {BASELINE:.4f}")
    print(f"Best seed lift: {(best_by_avg[1]/BASELINE - 1)*100:+.2f}%")

    print(f"\n6-hit count distribution (seeds with N six-hit draws out of {len(DATA)}):")
    for n in sorted(hit6_dist):
        print(f"  {n} six-hit draws: {hit6_dist[n]:,} seeds")

    print(f"\n0-hit count distribution (top/bottom of range):")
    for n in sorted(hit0_dist)[:5]:
        print(f"  {n} zero-hit draws: {hit0_dist[n]:,} seeds")
    print("  ...")
    for n in sorted(hit0_dist)[-5:]:
        print(f"  {n} zero-hit draws: {hit0_dist[n]:,} seeds")

    # ── Save ──────────────────────────────────────────────────────────────────
    out = {
        'numSeeds': NUM_SEEDS, 'kPicks': K_PICKS, 'nDraws': len(DATA),
        'drawRange': [DATA[0]['s'], DATA[-1]['s']],
        'baseline': BASELINE,
        'bestByAvg': {'seed': best_by_avg[0], 'avg': best_by_avg[1], 'hit6': best_by_avg[2], 'hit0': best_by_avg[3]},
        'bestByHit6': {'seed': best_by_hit6[0], 'avg': best_by_hit6[1], 'hit6': best_by_hit6[2], 'hit0': best_by_hit6[3]},
        'hit6Distribution': dict(hit6_dist),
        'hit0Distribution': dict(hit0_dist),
        'results': all_results,  # [seed, avg, hit6, hit0]
    }
    with open(OUT_JSON, 'w') as f:
        json.dump(out, f, separators=(',', ':'))
    print(f"\nSaved {OUT_JSON}")

if __name__ == '__main__':
    main()
