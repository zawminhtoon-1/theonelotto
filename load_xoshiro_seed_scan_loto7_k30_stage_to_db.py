"""
load_xoshiro_seed_scan_loto7_k30_stage_to_db.py
----------------------------------------------------
Loads one stage's JSON output (from xoshiro_seed_scan_loto7_k30_stage.py)
into loto7_local.db's seed_hit_xoshiro_k30 table. Creates the table on
first call (if absent); subsequent calls INSERT-append, since each
stage's seed range is disjoint (seed is the PRIMARY KEY).

Usage: python load_xoshiro_seed_scan_loto7_k30_stage_to_db.py <stage_num>
"""
import json, sqlite3, sys

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
DB_PATH = BASE + r"\loto7_local.db"
TABLE = "seed_hit_xoshiro_k30"

stage_num = sys.argv[1]
JSON_IN = BASE + rf"\xoshiro_seed_scan_loto7_k30_stage{stage_num}.json"

with open(JSON_IN, encoding='utf-8') as f:
    data = json.load(f)

results = data['results']  # [seed, hit7b, hit7, hit6, hit5, hit4]
print(f"[Stage {stage_num}] Loaded {len(results)} seed rows from {JSON_IN} "
      f"(seeds {data['seedRange'][0]:,}-{data['seedRange'][1]:,})")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute(f"""
    CREATE TABLE IF NOT EXISTS {TABLE} (
        seed        INTEGER PRIMARY KEY,
        hit7b_count INTEGER NOT NULL,
        hit7_count  INTEGER NOT NULL,
        hit6_count  INTEGER NOT NULL,
        hit5_count  INTEGER NOT NULL,
        hit4_count  INTEGER NOT NULL,
        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")

cur.execute(f"SELECT COUNT(*) FROM {TABLE}")
before_count = cur.fetchone()[0]

cur.executemany(
    f"INSERT INTO {TABLE} (seed, hit7b_count, hit7_count, hit6_count, hit5_count, hit4_count) VALUES (?, ?, ?, ?, ?, ?)",
    results
)
conn.commit()

cur.execute(f"SELECT COUNT(*) FROM {TABLE}")
after_count = cur.fetchone()[0]
cur.execute(f"SELECT MIN(seed), MAX(seed) FROM {TABLE}")
lo, hi = cur.fetchone()
cur.execute(f"""SELECT seed, hit7b_count, hit7_count, hit6_count, hit5_count, hit4_count FROM {TABLE}
                ORDER BY hit7b_count DESC, hit7_count DESC, hit6_count DESC, hit5_count DESC, hit4_count DESC, seed ASC LIMIT 3""")
top3 = cur.fetchall()

conn.close()

print(f"[Stage {stage_num}] Rows before: {before_count:,}  after: {after_count:,}  (added {after_count - before_count:,})")
print(f"[Stage {stage_num}] Seed range now covered so far: {lo:,} to {hi:,}")
print(f"[Stage {stage_num}] Overall top 3 so far (hit7b>hit7>hit6>hit5>hit4):")
for row in top3:
    print(f"    seed={row[0]:9,d}  hit7b={row[1]:2d}  hit7={row[2]:2d}  hit6={row[3]:3d}  hit5={row[4]:3d}  hit4={row[5]:3d}")
