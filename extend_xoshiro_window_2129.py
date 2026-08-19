"""
extend_xoshiro_window_2129.py
--------------------------------
Incremental window extension for the K=33/K=35/K=38 xoshiro seed-hit
tables: brings each table's draw window up to #1000-2129 WITHOUT a full
rescan. For every seed already in a table, computes picks only for the
draw(s) missing from that table's current window and adds the resulting
hit6b/hit6/hit5 deltas onto the existing stored counts.

  K=33 (seed_hit_xoshiro_k33): old window #1001-2127 -> needs #1000, #2128, #2129
  K=35 (seed_hit_xoshiro_k35): old window #1000-2127 -> needs #2128, #2129
  K=38 (seed_hit_xoshiro_k38): old window #1000-2127 -> needs #2128, #2129

Self-checks the inlined fast path against a from-scratch modular
reference for each new draw serial (including negative seeds for K=35)
before touching any table.

Run: python extend_xoshiro_window_2129.py
"""
import json, re, time, os, sqlite3
import multiprocessing as mp
from collections import Counter

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
DB_PATH = BASE + r"\loto6_local.db"
ENV_LOCAL = BASE + r"\.env.local"

LOTO6_MAX = 43
N_WORKERS = 7
CHUNK_SIZE = 2000
MASK64 = 0xFFFFFFFFFFFFFFFF

CONFIGS = [
    {"k": 33, "table": "seed_hit_xoshiro_k33", "old_window": (1001, 2127), "new_draws": [1000, 2128, 2129], "new_window": (1000, 2129)},
    {"k": 35, "table": "seed_hit_xoshiro_k35", "old_window": (1000, 2127), "new_draws": [2128, 2129], "new_window": (1000, 2129)},
    {"k": 38, "table": "seed_hit_xoshiro_k38", "old_window": (1000, 2127), "new_draws": [2128, 2129], "new_window": (1000, 2129)},
]

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

def xoshiro_predict_modular(seed, draw_serial, k, pool_max=LOTO6_MAX):
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

def init_worker(data_bytes, k_picks):
    global _DATA, _K
    rows = json.loads(data_bytes)
    _DATA = [(r['s'], frozenset(r['a']), r['b']) for r in rows]
    _K = k_picks

def process_chunk(seed_chunk):
    arr_template = list(range(1, LOTO6_MAX + 1))
    out = []
    for seed in seed_chunk:
        d6b = d6 = d5 = 0
        for serial, actual_set, bonus in _DATA:
            picks = xoshiro_predict_inline(seed, serial, _K, LOTO6_MAX, arr_template)
            picks_set = frozenset(picks)
            h = len(actual_set & picks_set)
            if h == 6:
                d6 += 1
                if bonus in picks_set:
                    d6b += 1
            elif h == 5:
                d5 += 1
        out.append((seed, d6b, d6, d5))
    return out

def load_draws(serials):
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
        "FROM loto6_results WHERE draw_serial = ANY(%s) ORDER BY draw_serial",
        (serials,),
    )
    rows = cur.fetchall()
    conn.close()
    if len(rows) != len(serials):
        raise SystemExit(f"Expected {len(serials)} draws {serials}, got {len(rows)}: {[r[0] for r in rows]}")
    return [{'s': r[0], 'a': list(r[1:7]), 'b': r[7]} for r in rows]

def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    all_results = []

    for cfg in CONFIGS:
        k = cfg["k"]
        table = cfg["table"]
        new_draws_serials = cfg["new_draws"]
        old_lo, old_hi = cfg["old_window"]
        new_lo, new_hi = cfg["new_window"]

        print(f"\n{'='*70}\nK={k} ({table}): extending window #{old_lo}-{old_hi} -> #{new_lo}-{new_hi}")
        print(f"  New draws to fold in: {new_draws_serials}")

        DATA = load_draws(new_draws_serials)
        print(f"  Loaded {len(DATA)} new draw record(s): " + ", ".join(f"#{d['s']}" for d in DATA))

        # Capture OLD leaders before touching the table, for the changed-leader comparison.
        cur.execute(f"""SELECT seed, hit6b_count, hit6_count, hit5_count FROM {table}
                        ORDER BY hit6b_count DESC, hit6_count DESC, hit5_count DESC, seed ASC LIMIT 1""")
        old_best = cur.fetchone()
        cur.execute(f"""SELECT seed, hit6b_count, hit6_count, hit5_count FROM {table}
                        ORDER BY hit6b_count ASC, hit6_count ASC, hit5_count ASC, seed ASC LIMIT 1""")
        old_worst = cur.fetchone()
        print(f"  OLD best  (#{old_lo}-{old_hi}): seed={old_best[0]:,} hit6b={old_best[1]} hit6={old_best[2]} hit5={old_best[3]}")
        print(f"  OLD worst (#{old_lo}-{old_hi}): seed={old_worst[0]:,} hit6b={old_worst[1]} hit6={old_worst[2]} hit5={old_worst[3]}")

        # Self-check: inlined fast path vs modular reference, for each new draw,
        # for a spread of seeds including negatives if K=35.
        test_seeds = [0, 1, -1, 12345, -12345, 1000000]
        if k == 35:
            test_seeds += [-1623160, 1623160, -500000]
        arr_t = list(range(1, LOTO6_MAX + 1))
        for d in DATA:
            for ts in test_seeds:
                inline_r = sorted(xoshiro_predict_inline(ts, d['s'], k, LOTO6_MAX, arr_t))
                modular_r = xoshiro_predict_modular(ts, d['s'], k)
                assert inline_r == modular_r, f"MISMATCH K={k} seed={ts} draw={d['s']}: {inline_r} vs {modular_r}"
                assert len(inline_r) == k
        print(f"  Self-check OK: inlined fast path matches modular reference for all new draws x {len(test_seeds)} test seeds.")

        data_bytes = json.dumps(DATA)

        cur.execute(f"SELECT seed FROM {table} ORDER BY seed")
        seeds = [r[0] for r in cur.fetchall()]
        n_seeds = len(seeds)
        print(f"  {n_seeds:,} seeds currently in {table}. Computing deltas for {len(DATA)} new draw(s)...")

        chunks = [seeds[i:i + CHUNK_SIZE] for i in range(0, n_seeds, CHUNK_SIZE)]
        total_chunks = len(chunks)

        t0 = time.time()
        deltas = []
        done = 0
        with mp.Pool(N_WORKERS, initializer=init_worker, initargs=(data_bytes, k)) as pool:
            for i, chunk_result in enumerate(pool.imap_unordered(process_chunk, chunks), 1):
                deltas.extend(chunk_result)
                done += len(chunk_result)
                if i % 50 == 0 or i == total_chunks:
                    elapsed = time.time() - t0
                    rate = done / elapsed if elapsed > 0 else 0
                    print(f"    [{i}/{total_chunks} chunks, {done:,}/{n_seeds:,} seeds] elapsed={elapsed:.1f}s rate={rate:.0f} seeds/s", flush=True)
        elapsed_total = time.time() - t0
        print(f"  Delta computation done in {elapsed_total:.1f}s")

        cur.executemany(
            f"UPDATE {table} SET hit6b_count = hit6b_count + ?, hit6_count = hit6_count + ?, hit5_count = hit5_count + ? WHERE seed = ?",
            [(d6b, d6, d5, seed) for (seed, d6b, d6, d5) in deltas]
        )
        conn.commit()
        print(f"  Merged deltas into {table} ({len(deltas):,} rows updated).")

        # Report new best/worst + flag if leader changed
        cur.execute(f"""SELECT seed, hit6b_count, hit6_count, hit5_count FROM {table}
                        ORDER BY hit6b_count DESC, hit6_count DESC, hit5_count DESC, seed ASC LIMIT 1""")
        new_best = cur.fetchone()
        cur.execute(f"""SELECT seed, hit6b_count, hit6_count, hit5_count FROM {table}
                        ORDER BY hit6b_count ASC, hit6_count ASC, hit5_count ASC, seed ASC LIMIT 1""")
        new_worst = cur.fetchone()
        print(f"  NEW best  (#{new_lo}-{new_hi}): seed={new_best[0]:,} hit6b={new_best[1]} hit6={new_best[2]} hit5={new_best[3]}")
        print(f"  NEW worst (#{new_lo}-{new_hi}): seed={new_worst[0]:,} hit6b={new_worst[1]} hit6={new_worst[2]} hit5={new_worst[3]}")

        best_changed = old_best[0] != new_best[0]
        worst_changed = old_worst[0] != new_worst[0]
        print(f"  Leader changed? best={'YES' if best_changed else 'no'}  worst={'YES' if worst_changed else 'no'}")

        all_results.append({
            "k": k, "table": table,
            "old_window": [old_lo, old_hi], "new_window": [new_lo, new_hi],
            "old_best": old_best, "new_best": new_best, "best_changed": best_changed,
            "old_worst": old_worst, "new_worst": new_worst, "worst_changed": worst_changed,
        })

    conn.close()
    print(f"\n{'='*70}\nAll three tables extended to #1000-2129.")
    with open(BASE + r"\extend_xoshiro_window_2129_summary.json", "w") as f:
        json.dump(all_results, f, indent=2)
    print("Summary written to extend_xoshiro_window_2129_summary.json")

if __name__ == '__main__':
    main()
