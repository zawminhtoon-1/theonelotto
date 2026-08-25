"""
extend_random_seed_window_2131.py
--------------------------------------
Incremental window extension for the Random Seed Backtest's
seed_hit_random_k17 table (loto6_local.db): brings its draw window from
#1001-2129 (1129 draws) up to #1001-2131 (1131 draws) WITHOUT a full
rescan -- same incremental-delta pattern as extend_xoshiro_window_2129.py.

For every seed already in the table (2,473,401 rows, seeds -1,236,700
to 1,236,700), computes K=17 picks only for the 2 new draws (#2130,
#2131) via the same random.Random(seed*10_000_000+draw_serial).sample()
formula used by random_seed_scan_k17_full.py (Python's own stdlib
random.Random -- not a custom bit-manipulation port like xoshiro, so
there's no separate "inline vs modular" implementation to cross-check;
this literally calls the same trusted stdlib function), and adds the
resulting deltas onto the existing stored counts (hit6b/hit6/hit5/hit4/
hit0/total_hits/bonus_hits).

Run: python extend_random_seed_window_2131.py
"""
import json, random, re, time, os, sqlite3
import multiprocessing as mp

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
DB_PATH = BASE + r"\loto6_local.db"
ENV_LOCAL = BASE + r"\.env.local"
TABLE = "seed_hit_random_k17"

K_PICKS = 17
LOTO6_MAX = 43
OLD_WINDOW = (1001, 2129)
NEW_DRAWS = [2130, 2131]
NEW_WINDOW = (1001, 2131)
N_WORKERS = 7
CHUNK_SIZE = 2000

def random_predict(seed, draw_serial, k=K_PICKS):
    rng = random.Random(seed * 10_000_000 + draw_serial)
    return sorted(rng.sample(range(1, LOTO6_MAX + 1), k))

def init_worker(data_bytes):
    global _DATA
    rows = json.loads(data_bytes)
    _DATA = [(r['s'], frozenset(r['a']), r['b']) for r in rows]

def process_chunk(seed_chunk):
    out = []
    for seed in seed_chunk:
        total_hits = 0
        bonus_hits = 0
        hit6b = 0
        dist = [0, 0, 0, 0, 0, 0, 0]
        for serial, actual_set, bonus in _DATA:
            picks = random_predict(seed, serial)
            picks_set = frozenset(picks)
            h = len(actual_set & picks_set)
            dist[h] += 1
            total_hits += h
            bh = bonus in picks_set
            if bh:
                bonus_hits += 1
                if h == 6:
                    hit6b += 1
        # seed, d_hit6b, d_hit6, d_hit5, d_hit4, d_hit0, d_total_hits, d_bonus_hits
        out.append((seed, hit6b, dist[6], dist[5], dist[4], dist[0], total_hits, bonus_hits))
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
    print(f"Extending {TABLE} window #{OLD_WINDOW[0]}-{OLD_WINDOW[1]} -> #{NEW_WINDOW[0]}-{NEW_WINDOW[1]}")
    DATA = load_draws(NEW_DRAWS)
    print(f"Loaded {len(DATA)} new draw record(s): " + ", ".join(f"#{d['s']} main={d['a']} bonus={d['b']}" for d in DATA))

    # Sanity-check: picks are valid (17 unique numbers, 1-43) for a spread of
    # seeds incl. negatives, for each new draw. random.Random is stdlib, not
    # a custom port, so this is a validity check, not an implementation
    # cross-check.
    for d in DATA:
        for ts in [0, 1, -1, 12345, -12345, 1236700, -1236700]:
            picks = random_predict(ts, d['s'])
            assert len(picks) == K_PICKS and len(set(picks)) == K_PICKS, f"seed={ts} draw={d['s']}: bad pick {picks}"
            assert all(1 <= n <= LOTO6_MAX for n in picks), f"seed={ts} draw={d['s']}: out of range {picks}"
    print("Sanity-check OK: picks valid (17 unique, 1-43) for spread of seeds incl. negatives, both new draws.")

    data_bytes = json.dumps(DATA)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute(f"SELECT COUNT(*) FROM {TABLE}")
    n_seeds = cur.fetchone()[0]
    print(f"{n_seeds:,} seeds currently in {TABLE}.")

    cur.execute(f"""SELECT seed, hit6b_count, hit6_count, hit5_count FROM {TABLE}
                    ORDER BY hit6b_count DESC, hit6_count DESC, hit5_count DESC, seed ASC LIMIT 1""")
    old_best = cur.fetchone()
    cur.execute(f"""SELECT seed, hit0_count FROM {TABLE} ORDER BY hit0_count DESC, seed ASC LIMIT 1""")
    old_worst = cur.fetchone()
    print(f"OLD best  (#{OLD_WINDOW[0]}-{OLD_WINDOW[1]}): seed={old_best[0]:,} hit6b={old_best[1]} hit6={old_best[2]} hit5={old_best[3]}")
    print(f"OLD worst-coverage (#{OLD_WINDOW[0]}-{OLD_WINDOW[1]}): seed={old_worst[0]:,} hit0={old_worst[1]}")

    cur.execute(f"SELECT seed FROM {TABLE} ORDER BY seed")
    seeds = [r[0] for r in cur.fetchall()]
    chunks = [seeds[i:i + CHUNK_SIZE] for i in range(0, len(seeds), CHUNK_SIZE)]
    total_chunks = len(chunks)
    print(f"\nComputing deltas for {len(DATA)} new draw(s) x {n_seeds:,} seeds, {total_chunks:,} chunks, {N_WORKERS} workers...")

    t0 = time.time()
    deltas = []
    done = 0
    with mp.Pool(N_WORKERS, initializer=init_worker, initargs=(data_bytes,)) as pool:
        for i, chunk_result in enumerate(pool.imap_unordered(process_chunk, chunks), 1):
            deltas.extend(chunk_result)
            done += len(chunk_result)
            if i % 100 == 0 or i == total_chunks:
                elapsed = time.time() - t0
                rate = done / elapsed if elapsed > 0 else 0
                eta = (n_seeds - done) / rate if rate > 0 else 0
                print(f"  [{i:,}/{total_chunks:,} chunks, {done:,}/{n_seeds:,} seeds] elapsed={elapsed:.1f}s rate={rate:.0f} seeds/s eta={eta:.0f}s", flush=True)
    elapsed_total = time.time() - t0
    print(f"Delta computation done in {elapsed_total:.1f}s")

    cur.executemany(
        f"""UPDATE {TABLE} SET
            hit6b_count = hit6b_count + ?,
            hit6_count = hit6_count + ?,
            hit5_count = hit5_count + ?,
            hit4_count = hit4_count + ?,
            hit0_count = hit0_count + ?,
            total_hits = total_hits + ?,
            bonus_hits = bonus_hits + ?
            WHERE seed = ?""",
        [(d6b, d6, d5, d4, d0, dtot, dbon, seed) for (seed, d6b, d6, d5, d4, d0, dtot, dbon) in deltas]
    )
    conn.commit()
    print(f"Merged deltas into {TABLE} ({len(deltas):,} rows updated).")

    cur.execute(f"""SELECT seed, hit6b_count, hit6_count, hit5_count FROM {TABLE}
                    ORDER BY hit6b_count DESC, hit6_count DESC, hit5_count DESC, seed ASC LIMIT 1""")
    new_best = cur.fetchone()
    cur.execute(f"""SELECT seed, hit0_count FROM {TABLE} ORDER BY hit0_count DESC, seed ASC LIMIT 1""")
    new_worst = cur.fetchone()
    print(f"NEW best  (#{NEW_WINDOW[0]}-{NEW_WINDOW[1]}): seed={new_best[0]:,} hit6b={new_best[1]} hit6={new_best[2]} hit5={new_best[3]}")
    print(f"NEW worst-coverage (#{NEW_WINDOW[0]}-{NEW_WINDOW[1]}): seed={new_worst[0]:,} hit0={new_worst[1]}")
    print(f"Leader changed? best={'YES' if old_best[0]!=new_best[0] else 'no'}  worst={'YES' if old_worst[0]!=new_worst[0] else 'no'}")

    # Verify row count unchanged (only UPDATEs, no INSERT/DELETE)
    cur.execute(f"SELECT COUNT(*) FROM {TABLE}")
    final_count = cur.fetchone()[0]
    conn.close()
    if final_count != n_seeds:
        raise SystemExit(f"Row count changed unexpectedly: {n_seeds} -> {final_count}")
    print(f"\nVerified: {TABLE} still has exactly {final_count:,} rows (UPDATE-only, no seeds added/removed).")
    print(f"{TABLE} extended to #{NEW_WINDOW[0]}-{NEW_WINDOW[1]}.")

if __name__ == '__main__':
    main()
