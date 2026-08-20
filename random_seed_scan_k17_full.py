"""
random_seed_scan_k17_full.py
--------------------------------
Full scan for the Random Seed Backtest page's 100x range expansion:
seeds -1,236,700 to 1,236,700 (2,473,401 seeds total), K=17 picks,
draw window #1001-2129 (1129 draws), same random.Random(seed*10_000_000
+draw_serial).sample(range(1,44), 17) formula as gen_random_seed_backtest.py.

Unlike the smaller 24,753-seed scan (which embedded every seed as an HTML
row), this scales 100x, so results are streamed straight into SQLite
(loto6_local.db, table seed_hit_random_k17) as the scan progresses rather
than held in memory / dumped as one giant JSON -- mirroring the
seed_hit_xoshiro_k33/k35/k38 tables' schema pattern used elsewhere on the
site.

Self-checked (multiprocessing worker path vs. independent single-process
recompute) for a handful of seeds -- including both new range boundaries,
0, and several previously-reported seeds from the smaller scan -- before
trusting the full parallel run.

Run: python random_seed_scan_k17_full.py
"""
import json, re, random, os, time, sqlite3
import multiprocessing as mp

BASE      = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
ENV_LOCAL = BASE + r"\.env.local"
DB_PATH   = BASE + r"\loto6_local.db"
TABLE     = "seed_hit_random_k17"

K_PICKS   = 17
DRAW_START, DRAW_END = 1001, 2129
N_DRAWS   = DRAW_END - DRAW_START + 1  # 1129
SEED_LO, SEED_HI = -1_236_700, 1_236_700
LOTO6_MAX = 43
N_WORKERS = 7
CHUNK_SIZE = 200
COMMIT_EVERY_CHUNKS = 50   # ~10,000 seeds per DB commit

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
        # seed, hit6b, hit6, hit5, hit4, hit0, total_hits, bonus_hits
        out.append((seed, hit6b, dist[6], dist[5], dist[4], dist[0], total_hits, bonus_hits))
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
    DATA = load_data_from_db()
    print(f"Loaded {len(DATA)} rows from loto6_results for draws {DRAW_START}-{DRAW_END} (expected {N_DRAWS}).")
    serials = [r['s'] for r in DATA]
    if len(DATA) != N_DRAWS:
        raise SystemExit(f"Row count mismatch: got {len(DATA)}, expected {N_DRAWS}")
    if serials != list(range(DRAW_START, DRAW_END + 1)):
        missing = sorted(set(range(DRAW_START, DRAW_END + 1)) - set(serials))
        raise SystemExit(f"Gap check FAILED. Missing: {missing[:10]}...")
    print(f"Verified: {len(DATA)} consecutive draws, no gaps, #{DRAW_START}-{DRAW_END} exactly.")

    data_bytes = json.dumps(DATA)

    # ── Self-check: multiprocessing worker path must match an independent
    # single-process recomputation, for boundary + known-interesting seeds,
    # before trusting the full parallel scan. ──────────────────────────────
    init_worker(data_bytes)
    test_seeds = [SEED_LO, SEED_HI, 0, 1, -1, -10059, 520, 2021, -12376, 12376]
    for ts in test_seeds:
        direct = process_chunk([ts])[0]
        th = bh = h6b = 0
        d = [0]*7
        for row in DATA:
            picks = set(random_predict(ts, row['s']))
            hh = len(set(row['a']) & picks)
            d[hh] += 1
            th += hh
            if row['b'] in picks:
                bh += 1
                if hh == 6:
                    h6b += 1
        expected = (ts, h6b, d[6], d[5], d[4], d[0], th, bh)
        assert direct == expected, f"Self-check MISMATCH seed={ts}: {direct} vs {expected}"
    print(f"Self-check OK: {len(test_seeds)} seeds (incl. both range boundaries + negatives) verified consistent.")

    # ── SQLite table setup ──────────────────────────────────────────────────
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(f"DROP TABLE IF EXISTS {TABLE}")
    cur.execute(f"""
        CREATE TABLE {TABLE} (
            seed        INTEGER PRIMARY KEY,
            hit6b_count INTEGER NOT NULL,
            hit6_count  INTEGER NOT NULL,
            hit5_count  INTEGER NOT NULL,
            hit4_count  INTEGER NOT NULL,
            hit0_count  INTEGER NOT NULL,
            total_hits  INTEGER NOT NULL,
            bonus_hits  INTEGER NOT NULL,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()

    # ── Parallel scan, streamed into SQLite ─────────────────────────────────
    seeds = list(range(SEED_LO, SEED_HI + 1))
    num_seeds = len(seeds)
    chunks = [seeds[i:i + CHUNK_SIZE] for i in range(0, num_seeds, CHUNK_SIZE)]
    total_chunks = len(chunks)
    print(f"\nScanning {num_seeds:,} seeds ({SEED_LO:,} to {SEED_HI:,}) x {N_DRAWS} draws x K={K_PICKS}, "
          f"{total_chunks:,} chunks of {CHUNK_SIZE}, {N_WORKERS} workers...", flush=True)

    insert_sql = f"""INSERT INTO {TABLE}
        (seed, hit6b_count, hit6_count, hit5_count, hit4_count, hit0_count, total_hits, bonus_hits)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)"""

    pending = []
    t0 = time.time()
    done_seeds = 0
    chunks_since_commit = 0
    with mp.Pool(N_WORKERS, initializer=init_worker, initargs=(data_bytes,)) as pool:
        for i, chunk_result in enumerate(pool.imap_unordered(process_chunk, chunks), 1):
            pending.extend(chunk_result)
            done_seeds += len(chunk_result)
            chunks_since_commit += 1
            if chunks_since_commit >= COMMIT_EVERY_CHUNKS or i == total_chunks:
                cur.executemany(insert_sql, pending)
                conn.commit()
                pending = []
                chunks_since_commit = 0
            if i % 100 == 0 or i == total_chunks:
                elapsed = time.time() - t0
                rate = done_seeds / elapsed
                eta = (num_seeds - done_seeds) / rate if rate > 0 else 0
                print(f"[{i:,}/{total_chunks:,} chunks, {done_seeds:,}/{num_seeds:,} seeds] "
                      f"elapsed={elapsed:.0f}s ({elapsed/60:.1f}min) rate={rate:.1f} seeds/s "
                      f"eta={eta:.0f}s ({eta/60:.1f}min)", flush=True)

    elapsed_total = time.time() - t0
    print(f"\nDONE scanning in {elapsed_total:.1f}s ({elapsed_total/60:.1f} min)", flush=True)

    cur.execute(f"SELECT COUNT(*) FROM {TABLE}")
    count = cur.fetchone()[0]
    if count != num_seeds:
        raise SystemExit(f"WARNING: expected {num_seeds:,} rows in {TABLE}, got {count:,}")
    print(f"Verified: exactly {count:,} rows written to {TABLE} in {DB_PATH}.")

    cur.execute(f"""SELECT seed, hit6b_count, hit6_count, hit5_count, hit4_count, hit0_count, total_hits, bonus_hits
                    FROM {TABLE} ORDER BY hit6b_count DESC, hit6_count DESC, hit5_count DESC, seed ASC LIMIT 5""")
    top5 = cur.fetchall()
    cur.execute(f"""SELECT seed, hit0_count, hit6b_count, hit6_count, hit5_count, total_hits
                    FROM {TABLE} ORDER BY hit0_count DESC, seed ASC LIMIT 1""")
    worst = cur.fetchone()
    cur.execute(f"SELECT AVG(hit0_count) FROM {TABLE}")
    hit0_mean = cur.fetchone()[0]

    conn.close()

    print(f"\nTop 5 seeds (hit6b desc, hit6 desc, hit5 desc):")
    for r in top5:
        print(f"  seed={r[0]:>10,}  hit6b={r[1]:3d}  hit6={r[2]:3d}  hit5={r[3]:3d}  hit4={r[4]:4d}  hit0={r[5]:4d}  total_hits={r[6]}  bonus={r[7]}")
    print(f"\nWorst-coverage seed: #{worst[0]:,}  hit0={worst[1]}  (mean hit0 across all seeds: {hit0_mean:.2f})  "
          f"hit6b={worst[2]} hit6={worst[3]} hit5={worst[4]} total_hits={worst[5]}")

if __name__ == '__main__':
    main()
