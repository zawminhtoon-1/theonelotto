"""
load_xoshiro_seed_scan_k33_to_db.py
--------------------------------------
One-off loader: reads xoshiro_seed_scan_k33_1126.json (produced by
xoshiro_seed_scan_k33_1126.py -- the 10,001-seed x 1126-draw x K=33
xoshiro256** backtest scan over draws #1001-2126) and loads it into
loto6_local.db as seed_hit_xoshiro_k33, mirroring the seed_hit_xoshiro_k21
table's schema pattern.

Run: python load_xoshiro_seed_scan_k33_to_db.py
"""
import json, sqlite3

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
JSON_IN = BASE + r"\xoshiro_seed_scan_k33_1126.json"
DB_PATH = BASE + r"\loto6_local.db"
TABLE = "seed_hit_xoshiro_k33"

with open(JSON_IN, encoding='utf-8') as f:
    data = json.load(f)

results = data['results']  # [seed, hit6b, hit6, hit5]
print(f"Loaded {len(results)} seed rows from {JSON_IN}")
print(f"kPicks={data['kPicks']} nDraws={data['nDraws']} drawRange={data['drawRange']}")

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
    results
)
conn.commit()

cur.execute(f"SELECT COUNT(*) FROM {TABLE}")
count = cur.fetchone()[0]
cur.execute(f"SELECT seed, hit6b_count, hit6_count, hit5_count FROM {TABLE} ORDER BY hit6b_count DESC, hit6_count DESC, hit5_count DESC, seed ASC LIMIT 1")
best = cur.fetchone()

conn.close()

print(f"\nWrote {count:,} rows into {TABLE} in {DB_PATH}")
print(f"Best (hit6b>hit6>hit5): seed={best[0]} hit6b={best[1]} hit6={best[2]} hit5={best[3]}")
