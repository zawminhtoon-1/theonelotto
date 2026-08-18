"""
load_xoshiro_seed_scan_k35_to_db.py
--------------------------------------
Combines all 4 stages of the K=35 scan (seeds -1,623,160 to 1,623,160,
3,246,321 seeds total) into loto6_local.db as seed_hit_xoshiro_k35,
mirroring the other seed_hit_xoshiro_k* tables' schema pattern. First
scan on this site to include negative seeds.

Run: python load_xoshiro_seed_scan_k35_to_db.py
"""
import json, sqlite3

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
DB_PATH = BASE + r"\loto6_local.db"
TABLE = "seed_hit_xoshiro_k35"

all_results = []
stage_files = [BASE + rf"\xoshiro_seed_scan_k35_stage{n}.json" for n in range(1, 5)]
for path in stage_files:
    with open(path, encoding='utf-8') as f:
        stage = json.load(f)
    print(f"Stage {stage['stage']}: {len(stage['results'])} rows (seeds {stage['seedRange']})")
    all_results.extend(stage['results'])

print(f"Combined: {len(all_results)} rows")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute(f"DROP TABLE IF EXISTS {TABLE}")
cur.execute(f"""
    CREATE TABLE {TABLE} (
        seed        INTEGER PRIMARY KEY,
        hit6b_count INTEGER NOT NULL,
        hit6_count  INTEGER NOT NULL,
        hit5_count  INTEGER NOT NULL,
        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")

cur.executemany(
    f"INSERT INTO {TABLE} (seed, hit6b_count, hit6_count, hit5_count) VALUES (?, ?, ?, ?)",
    all_results
)
conn.commit()

cur.execute(f"SELECT COUNT(*) FROM {TABLE}")
count = cur.fetchone()[0]
cur.execute(f"SELECT MIN(seed), MAX(seed) FROM {TABLE}")
lo, hi = cur.fetchone()
cur.execute(f"""SELECT seed, hit6b_count, hit6_count, hit5_count FROM {TABLE}
                ORDER BY hit6b_count DESC, hit6_count DESC, hit5_count DESC, seed ASC LIMIT 1""")
best = cur.fetchone()
cur.execute(f"""SELECT seed, hit6b_count, hit6_count, hit5_count FROM {TABLE}
                ORDER BY hit6b_count ASC, hit6_count ASC, hit5_count ASC, seed ASC LIMIT 1""")
worst = cur.fetchone()

conn.close()

print(f"\nWrote {count:,} rows into {TABLE} in {DB_PATH}")
print(f"Seed range covered: {lo:,} to {hi:,}")
print(f"Best  (hit6b>hit6>hit5): seed={best[0]:,} hit6b={best[1]} hit6={best[2]} hit5={best[3]}")
print(f"Worst (hit6b<hit6<hit5): seed={worst[0]:,} hit6b={worst[1]} hit6={worst[2]} hit5={worst[3]}")

expected_count = 1_623_160 - (-1_623_160) + 1
if count != expected_count:
    raise SystemExit(f"WARNING: expected {expected_count:,} total rows, got {count:,}")
print(f"Verified: exactly {count:,} rows, seeds -1,623,160 to 1,623,160 fully covered.")
