"""
load_pcg64_seed_scan_k38_to_db.py
--------------------------------------
Combines whichever stages of the PCG64 K=38 scan currently exist on
disk (pcg64_seed_scan_k38_stage1.json through stage10.json -- run
INCREMENTALLY after each stage completes) into loto6_local.db as
seed_hit_pcg64_k38, mirroring the xoshiro K=30 loader's pattern
exactly. Designed to be re-run after EVERY stage completes, so the
live page can be rebuilt and pushed incrementally while later stages
are still running in the background. Drops and recreates the table
fresh each run (safe -- always rebuilt from the source stage JSON
files, never accumulated in-place).

Full target range once all 10 stages land: seeds -5,000,000 to
5,000,000 (10,000,001 seeds). Reports current coverage/percentage
either way -- does NOT raise if incomplete, only if what IS loaded
has gaps or duplicate seeds (a real bug), which a full/complete range
never should.

Run: python load_pcg64_seed_scan_k38_to_db.py
"""
import json, sqlite3, glob, re

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
DB_PATH = BASE + r"\loto6_local.db"
TABLE = "seed_hit_pcg64_k38"
FULL_SEED_LO, FULL_SEED_HI = -5_000_000, 5_000_000
FULL_EXPECTED = FULL_SEED_HI - FULL_SEED_LO + 1

stage_files = sorted(
    glob.glob(BASE + r"\pcg64_seed_scan_k38_stage*.json"),
    key=lambda p: int(re.search(r"stage(\d+)\.json$", p).group(1))
)
if not stage_files:
    raise SystemExit("No pcg64_seed_scan_k38_stage*.json files found -- run a stage first.")

all_results = []
stage_nums_loaded = []
for path in stage_files:
    with open(path, encoding='utf-8') as f:
        stage = json.load(f)
    print(f"Stage {stage['stage']}: {len(stage['results'])} rows (seeds {stage['seedRange']})")
    all_results.extend(stage['results'])
    stage_nums_loaded.append(stage['stage'])

print(f"\nCombined: {len(all_results):,} rows from stages {stage_nums_loaded}")

# ── Gap/duplicate check on what IS loaded (must always be clean, complete or not) ──
seeds_loaded = sorted(r[0] for r in all_results)
if len(set(seeds_loaded)) != len(seeds_loaded):
    dupes = [s for s in set(seeds_loaded) if seeds_loaded.count(s) > 1]
    raise SystemExit(f"DUPLICATE seeds found across loaded stages: {dupes[:10]}...")
expected_contiguous = list(range(seeds_loaded[0], seeds_loaded[-1] + 1))
if seeds_loaded != expected_contiguous:
    missing = sorted(set(expected_contiguous) - set(seeds_loaded))
    raise SystemExit(f"GAP in loaded seed range {seeds_loaded[0]:,}-{seeds_loaded[-1]:,}: missing {len(missing)} seeds, "
                      f"e.g. {missing[:10]}. Stages must be loaded in order with no skips.")
print(f"Verified: {len(seeds_loaded):,} seeds, contiguous, no gaps or duplicates "
      f"({seeds_loaded[0]:,} to {seeds_loaded[-1]:,}).")

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
        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")

cur.executemany(
    f"INSERT INTO {TABLE} (seed, hit6b_count, hit6_count, hit5_count, hit4_count) VALUES (?, ?, ?, ?, ?)",
    all_results
)
conn.commit()

cur.execute(f"SELECT COUNT(*) FROM {TABLE}")
count = cur.fetchone()[0]
cur.execute(f"SELECT MIN(seed), MAX(seed) FROM {TABLE}")
lo, hi = cur.fetchone()
cur.execute(f"""SELECT seed, hit6b_count, hit6_count, hit5_count, hit4_count FROM {TABLE}
                ORDER BY hit6b_count DESC, hit6_count DESC, hit5_count DESC, hit4_count DESC, seed ASC LIMIT 1""")
best = cur.fetchone()
cur.execute(f"""SELECT seed, hit6b_count, hit6_count, hit5_count, hit4_count FROM {TABLE}
                ORDER BY hit6b_count ASC, hit6_count ASC, hit5_count ASC, hit4_count ASC, seed ASC LIMIT 1""")
worst = cur.fetchone()

conn.close()

print(f"\nWrote {count:,} rows into {TABLE} in {DB_PATH}")
print(f"Seed range covered so far: {lo:,} to {hi:,}")
print(f"Best  so far (hit6b>hit6>hit5>hit4): seed={best[0]:,} hit6b={best[1]} hit6={best[2]} hit5={best[3]} hit4={best[4]}")
print(f"Worst so far (hit6b<hit6<hit5<hit4): seed={worst[0]:,} hit6b={worst[1]} hit6={worst[2]} hit5={worst[3]} hit4={worst[4]}")

pct = count / FULL_EXPECTED * 100
if count == FULL_EXPECTED and lo == FULL_SEED_LO and hi == FULL_SEED_HI:
    print(f"\nScan COMPLETE: all {count:,} seeds loaded, full range {FULL_SEED_LO:,} to {FULL_SEED_HI:,} covered.")
else:
    print(f"\nScan IN PROGRESS: {count:,} / {FULL_EXPECTED:,} seeds loaded ({pct:.1f}% of full "
          f"{FULL_SEED_LO:,} to {FULL_SEED_HI:,} range). {len(stage_nums_loaded)}/10 stages done.")
