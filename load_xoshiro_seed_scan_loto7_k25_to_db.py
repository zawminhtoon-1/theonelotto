"""
load_xoshiro_seed_scan_loto7_k25_to_db.py
---------------------------------------------
One-off loader: reads xoshiro_seed_scan_loto7_k25_10k.json (produced by
xoshiro_seed_scan_loto7_k25_10k.py -- the 10,001-seed x 500-draw x K=25
xoshiro256** Loto7 backtest scan over draws #1-500) and loads it into a
new loto7_local.db as seed_hit_xoshiro_k25, mirroring the Loto6
seed_hit_xoshiro_k33 table's schema pattern (separate DB file per game,
same naming convention within it).

Run: python load_xoshiro_seed_scan_loto7_k25_to_db.py
"""
import json, sqlite3

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
JSON_IN = BASE + r"\xoshiro_seed_scan_loto7_k25_10k.json"
DB_PATH = BASE + r"\loto7_local.db"
TABLE = "seed_hit_xoshiro_k25"

with open(JSON_IN, encoding='utf-8') as f:
    data = json.load(f)

results = data['results']  # [seed, hit7b, hit7, hit6, hit5, hit4]
print(f"Loaded {len(results)} seed rows from {JSON_IN}")
print(f"kPicks={data['kPicks']} poolMax={data['poolMax']} nDraws={data['nDraws']} drawRange={data['drawRange']}")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute(f"DROP TABLE IF EXISTS {TABLE}")
cur.execute(f"""
    CREATE TABLE {TABLE} (
        seed        INTEGER PRIMARY KEY,
        hit7b_count INTEGER NOT NULL,
        hit7_count  INTEGER NOT NULL,
        hit6_count  INTEGER NOT NULL,
        hit5_count  INTEGER NOT NULL,
        hit4_count  INTEGER NOT NULL,
        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")

cur.executemany(
    f"INSERT INTO {TABLE} (seed, hit7b_count, hit7_count, hit6_count, hit5_count, hit4_count) VALUES (?, ?, ?, ?, ?, ?)",
    results
)
conn.commit()

cur.execute(f"SELECT COUNT(*) FROM {TABLE}")
count = cur.fetchone()[0]
cur.execute(f"""SELECT seed, hit7b_count, hit7_count, hit6_count, hit5_count, hit4_count FROM {TABLE}
                ORDER BY hit7b_count DESC, hit7_count DESC, hit6_count DESC, hit5_count DESC, hit4_count DESC, seed ASC LIMIT 3""")
top3 = cur.fetchall()

conn.close()

print(f"\nWrote {count:,} rows into {TABLE} in {DB_PATH}")
print(f"Top 3 (hit7b>hit7>hit6>hit5>hit4):")
for row in top3:
    print(f"  seed={row[0]} hit7b={row[1]} hit7={row[2]} hit6={row[3]} hit5={row[4]} hit4={row[5]}")
