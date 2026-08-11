"""
merge_xoshiro_seed_scan_k33_10k_100k.py
------------------------------------------
Merges xoshiro_seed_scan_k33_10k_to_100k.json (seeds 10,001-100,000) into
the existing seed_hit_xoshiro_k33 table in loto6_local.db, which already
holds seeds 0-10,000 (from xoshiro_seed_scan_k33_1127.py /
load_xoshiro_seed_scan_k33_to_db.py). Does NOT drop the table -- only
INSERTs the new seed range, since seed is the PRIMARY KEY and 10,001-
100,000 doesn't overlap the existing 0-10,000 rows.

Run: python merge_xoshiro_seed_scan_k33_10k_100k.py
"""
import json, sqlite3

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
JSON_IN = BASE + r"\xoshiro_seed_scan_k33_10k_to_100k.json"
DB_PATH = BASE + r"\loto6_local.db"
TABLE = "seed_hit_xoshiro_k33"

with open(JSON_IN, encoding='utf-8') as f:
    data = json.load(f)

results = data['results']  # [seed, hit6b, hit6, hit5]
print(f"Loaded {len(results)} seed rows from {JSON_IN} (seeds {data['seedRange'][0]:,}-{data['seedRange'][1]:,})")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute(f"SELECT COUNT(*) FROM {TABLE}")
before_count = cur.fetchone()[0]
print(f"Existing rows in {TABLE} before merge: {before_count:,}")

cur.executemany(
    f"INSERT INTO {TABLE} (seed, hit6b_count, hit6_count, hit5_count) VALUES (?, ?, ?, ?)",
    results
)
conn.commit()

cur.execute(f"SELECT COUNT(*) FROM {TABLE}")
after_count = cur.fetchone()[0]
cur.execute(f"SELECT MIN(seed), MAX(seed) FROM {TABLE}")
lo, hi = cur.fetchone()
cur.execute(f"SELECT seed, hit6b_count, hit6_count, hit5_count FROM {TABLE} "
            f"ORDER BY hit6b_count DESC, hit6_count DESC, hit5_count DESC, seed ASC LIMIT 1")
best = cur.fetchone()

conn.close()

print(f"Rows after merge: {after_count:,} (added {after_count - before_count:,})")
print(f"Seed range now covered: {lo:,}-{hi:,}")
print(f"Overall best (hit6b>hit6>hit5): seed={best[0]} hit6b={best[1]} hit6={best[2]} hit5={best[3]}")

if after_count != 100_001:
    raise SystemExit(f"WARNING: expected 100,001 total rows (0-100,000), got {after_count:,}")
print("Verified: exactly 100,001 rows, seeds 0-100,000 fully covered.")
