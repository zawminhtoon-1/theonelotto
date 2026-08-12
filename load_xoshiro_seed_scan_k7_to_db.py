"""
load_xoshiro_seed_scan_k7_to_db.py
--------------------------------------
One-off loader: reads xoshiro_seed_scan_k7_10k_w1000.json (produced by
xoshiro_seed_scan_k7_10k.py -- the 10,001-seed x 1128-draw x K=7
xoshiro256** backtest scan over draws #1000-2127) and loads it into
loto6_local.db as seed_hit_xoshiro_k7.

NOT to be confused with the existing seed_hit_k7 table -- that one is
from an unrelated earlier scan using Python's random.Random (Mersenne
Twister), not xoshiro256**, and has a different schema (per-draw rows,
not per-seed). This table is per-seed, xoshiro-specific, distinctly
named seed_hit_xoshiro_k7.

Stores the FULL per-seed 0-6 hit-count distribution (hit0_count through
hit6_count), not just hit6b/hit6/hit5 -- at K=7, hit6b is 0 for every
seed and hit6 is 0 for 99.9% of them, so the 0-6 distribution is where
the real per-seed variation actually lives.

Run: python load_xoshiro_seed_scan_k7_to_db.py
"""
import json, sqlite3

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
JSON_IN = BASE + r"\xoshiro_seed_scan_k7_10k_w1000.json"
DB_PATH = BASE + r"\loto6_local.db"
TABLE = "seed_hit_xoshiro_k7"

with open(JSON_IN, encoding='utf-8') as f:
    data = json.load(f)

results = data['results']  # [seed, hit6b, hit6, hit5, [hit0..hit6]]
print(f"Loaded {len(results)} seed rows from {JSON_IN}")
print(f"kPicks={data['kPicks']} nDraws={data['nDraws']} drawRange={data['drawRange']}")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute(f"DROP TABLE IF EXISTS {TABLE}")
cur.execute(f"""
    CREATE TABLE {TABLE} (
        seed        INTEGER PRIMARY KEY,
        hit0_count  INTEGER NOT NULL,
        hit1_count  INTEGER NOT NULL,
        hit2_count  INTEGER NOT NULL,
        hit3_count  INTEGER NOT NULL,
        hit4_count  INTEGER NOT NULL,
        hit5_count  INTEGER NOT NULL,
        hit6_count  INTEGER NOT NULL,
        hit6b_count INTEGER NOT NULL,
        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")

rows = [
    (seed, dist7[0], dist7[1], dist7[2], dist7[3], dist7[4], dist7[5], dist7[6], hit6b)
    for seed, hit6b, hit6, hit5, dist7 in results
]
cur.executemany(
    f"""INSERT INTO {TABLE}
        (seed, hit0_count, hit1_count, hit2_count, hit3_count, hit4_count, hit5_count, hit6_count, hit6b_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
    rows
)
conn.commit()

cur.execute(f"SELECT COUNT(*) FROM {TABLE}")
count = cur.fetchone()[0]
cur.execute(f"SELECT seed, hit6b_count, hit6_count, hit5_count FROM {TABLE} ORDER BY hit6b_count DESC, hit6_count DESC, hit5_count DESC, seed ASC LIMIT 1")
best = cur.fetchone()
cur.execute(f"SELECT seed, hit6b_count, hit6_count, hit5_count FROM {TABLE} ORDER BY hit6b_count ASC, hit6_count ASC, hit5_count ASC, seed ASC LIMIT 1")
worst = cur.fetchone()
cur.execute(f"SELECT SUM(hit0_count), SUM(hit1_count), SUM(hit2_count), SUM(hit3_count), SUM(hit4_count), SUM(hit5_count), SUM(hit6_count) FROM {TABLE}")
sums = cur.fetchone()

conn.close()

print(f"\nWrote {count:,} rows into {TABLE} in {DB_PATH}")
print(f"Best  (hit6b>hit6>hit5): seed={best[0]} hit6b={best[1]} hit6={best[2]} hit5={best[3]}")
print(f"Worst (hit6b<hit6<hit5): seed={worst[0]} hit6b={worst[1]} hit6={worst[2]} hit5={worst[3]}")
print(f"Aggregate 0-6 hit distribution (summed across all seeds): {sums}")
