"""
load_xoshiro_seed_scan_k38_to_db.py
--------------------------------------
Loads both stages of the K=38 scan (Stage 1: seeds 0-100,000, Stage 2:
seeds 100,001-1,000,000) into loto6_local.db as seed_hit_xoshiro_k38,
mirroring the seed_hit_xoshiro_k33 table's schema pattern.

Run: python load_xoshiro_seed_scan_k38_to_db.py
"""
import json, sqlite3

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
JSON_STAGE1 = BASE + r"\xoshiro_seed_scan_k38_0_100k.json"
JSON_STAGE2 = BASE + r"\xoshiro_seed_scan_k38_100k_to_1m.json"
DB_PATH = BASE + r"\loto6_local.db"
TABLE = "seed_hit_xoshiro_k38"

with open(JSON_STAGE1, encoding='utf-8') as f:
    stage1 = json.load(f)
with open(JSON_STAGE2, encoding='utf-8') as f:
    stage2 = json.load(f)

results1 = stage1['results']  # [seed, hit6b, hit6, hit5]
results2 = stage2['results']
all_results = results1 + results2
print(f"Stage 1: {len(results1)} rows (seeds {stage1['seedRange']})")
print(f"Stage 2: {len(results2)} rows (seeds {stage2['seedRange']})")
print(f"Combined: {len(all_results)} rows")
print(f"kPicks={stage1['kPicks']} nDraws={stage1['nDraws']} drawRange={stage1['drawRange']}")

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
print(f"Seed range covered: {lo:,}-{hi:,}")
print(f"Best  (hit6b>hit6>hit5): seed={best[0]} hit6b={best[1]} hit6={best[2]} hit5={best[3]}")
print(f"Worst (hit6b<hit6<hit5): seed={worst[0]} hit6b={worst[1]} hit6={worst[2]} hit5={worst[3]}")

if count != 1_000_001:
    raise SystemExit(f"WARNING: expected 1,000,001 total rows (0-1,000,000), got {count:,}")
print("Verified: exactly 1,000,001 rows, seeds 0-1,000,000 fully covered.")
