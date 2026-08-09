"""
load_xoshiro_seed_scan_100k_to_db.py
--------------------------------------
One-off loader: reads xoshiro_seed_scan_100k.json (produced by
xoshiro_seed_scan_100k.py -- the 100,000-seed x 1000-draw x K=21
xoshiro256** backtest scan) and loads it into loto6_local.db as a new
table, seed_hit_xoshiro_k21, mirroring the seed_hit_k7 table's schema
pattern (plain per-key stat columns + created_at timestamp).

Only K=21 is loaded -- no other K values were scanned.

Run: python load_xoshiro_seed_scan_100k_to_db.py
"""
import json, sqlite3

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
JSON_IN = BASE + r"\xoshiro_seed_scan_100k.json"
DB_PATH = BASE + r"\loto6_local.db"
TABLE = "seed_hit_xoshiro_k21"

with open(JSON_IN, encoding='utf-8') as f:
    data = json.load(f)

results = data['results']  # [seed, avg, hit6, hit0]
print(f"Loaded {len(results)} seed rows from {JSON_IN}")
print(f"kPicks={data['kPicks']} nDraws={data['nDraws']} drawRange={data['drawRange']} baseline={data['baseline']:.4f}")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute(f"DROP TABLE IF EXISTS {TABLE}")
cur.execute(f"""
    CREATE TABLE {TABLE} (
        seed        INTEGER PRIMARY KEY,
        avg_hits    REAL NOT NULL,
        hit6_count  INTEGER NOT NULL,
        hit0_count  INTEGER NOT NULL,
        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")

cur.executemany(
    f"INSERT INTO {TABLE} (seed, avg_hits, hit6_count, hit0_count) VALUES (?, ?, ?, ?)",
    results
)
conn.commit()

cur.execute(f"SELECT COUNT(*) FROM {TABLE}")
count = cur.fetchone()[0]
cur.execute(f"SELECT seed, avg_hits, hit6_count, hit0_count FROM {TABLE} ORDER BY avg_hits DESC LIMIT 1")
best_avg = cur.fetchone()
cur.execute(f"SELECT seed, avg_hits, hit6_count, hit0_count FROM {TABLE} ORDER BY hit6_count DESC, avg_hits DESC LIMIT 1")
best_hit6 = cur.fetchone()

conn.close()

print(f"\nWrote {count:,} rows into {TABLE} in {DB_PATH}")
print(f"Best by avg_hits:   seed={best_avg[0]} avg={best_avg[1]:.4f} hit6={best_avg[2]} hit0={best_avg[3]}")
print(f"Best by hit6_count: seed={best_hit6[0]} avg={best_hit6[1]:.4f} hit6={best_hit6[2]} hit0={best_hit6[3]}")
