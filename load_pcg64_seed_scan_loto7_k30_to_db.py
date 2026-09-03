"""
load_pcg64_seed_scan_loto7_k30_to_db.py
-----------------------------------------
Combines whichever stages of the Loto7 PCG64 K=30 scan currently
exist on disk (pcg64_seed_scan_loto7_k30_stage1.json through
stage10.json -- run INCREMENTALLY after each stage completes) into
loto7_local.db as seed_hit_pcg64_k30, mirroring the Loto6 PCG64 K=38
loader's pattern exactly (and the Loto7 xoshiro K=30 loader's schema
convention -- hit7b/hit7/hit6/hit5/hit4, not hit6b/hit6/hit5/hit4).
Designed to be re-run after EVERY stage completes, so the live page
can be rebuilt and pushed incrementally while later stages are still
running in the background. Drops and recreates the table fresh each
run (safe -- always rebuilt from the source stage JSON files, never
accumulated in-place).

Full target range once all 10 stages land: seeds -5,000,000 to
5,000,000 (10,000,001 seeds). Reports current coverage/percentage
either way -- does NOT raise if incomplete, only if what IS loaded
has gaps or duplicate seeds (a real bug), which a full/complete range
never should.

Run: python load_pcg64_seed_scan_loto7_k30_to_db.py
"""
import json, sqlite3, glob, re, time

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
DB_PATH = BASE + r"\loto7_local.db"
TABLE = "seed_hit_pcg64_k30"
FULL_SEED_LO, FULL_SEED_HI = -5_000_000, 5_000_000
FULL_EXPECTED = FULL_SEED_HI - FULL_SEED_LO + 1

stage_files = sorted(
    glob.glob(BASE + r"\pcg64_seed_scan_loto7_k30_stage*.json"),
    key=lambda p: int(re.search(r"stage(\d+)\.json$", p).group(1))
)
if not stage_files:
    raise SystemExit("No pcg64_seed_scan_loto7_k30_stage*.json files found -- run a stage first.")

all_results = []
stage_nums_loaded = []
for path in stage_files:
    with open(path, encoding='utf-8') as f:
        stage = json.load(f)
    print(f"Stage {stage['stage']}: {len(stage['results'])} rows (seeds {stage['seedRange']})", flush=True)
    all_results.extend(stage['results'])
    stage_nums_loaded.append(stage['stage'])

print(f"\nCombined: {len(all_results):,} rows from stages {stage_nums_loaded}", flush=True)

# ── De-duplicate + gap check on what IS loaded (must always be clean, complete
# or not). Uses a dict keyed by seed (O(n), not the old O(n^2) list.count()
# scan) -- an exact-duplicate seed with IDENTICAL result values (e.g. a
# harmless off-by-one stage-boundary overlap, seed scanned twice) is
# silently collapsed to one row; a duplicate seed with DIFFERING values
# (a real data bug) still raises. ────────────────────────────────────────────
t_dedup0 = time.time()
by_seed = {}
conflicting = []
for r in all_results:
    seed = r[0]
    if seed in by_seed and by_seed[seed] != r:
        conflicting.append((seed, by_seed[seed], r))
    by_seed[seed] = r
if conflicting:
    raise SystemExit(f"CONFLICTING duplicate seeds (same seed, different results) across stages: {conflicting[:5]}...")
n_exact_dupes = len(all_results) - len(by_seed)
if n_exact_dupes:
    print(f"Collapsed {n_exact_dupes} harmless exact-duplicate seed(s) (stage-boundary overlap) in "
          f"{time.time()-t_dedup0:.2f}s.", flush=True)
all_results = list(by_seed.values())
print(f"De-dup check done in {time.time()-t_dedup0:.2f}s -- {len(all_results):,} unique seeds.", flush=True)

seeds_loaded = sorted(r[0] for r in all_results)
expected_contiguous = list(range(seeds_loaded[0], seeds_loaded[-1] + 1))
if seeds_loaded != expected_contiguous:
    missing = sorted(set(expected_contiguous) - set(seeds_loaded))
    raise SystemExit(f"GAP in loaded seed range {seeds_loaded[0]:,}-{seeds_loaded[-1]:,}: missing {len(missing)} seeds, "
                      f"e.g. {missing[:10]}. Stages must be loaded in order with no skips.")
print(f"Verified: {len(seeds_loaded):,} seeds, contiguous, no gaps or duplicates "
      f"({seeds_loaded[0]:,} to {seeds_loaded[-1]:,}).", flush=True)

t_db0 = time.time()
print("Connecting to DB...", flush=True)
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Bulk-load performance pragmas (this is a scratch/rebuild-from-source table,
# durability doesn't matter -- always regenerated from the stage JSON files).
cur.execute("PRAGMA synchronous=OFF")
cur.execute("PRAGMA journal_mode=MEMORY")
cur.execute("PRAGMA temp_store=MEMORY")
print(f"Connected + pragmas set in {time.time()-t_db0:.1f}s", flush=True)

t0 = time.time()
cur.execute(f"DROP TABLE IF EXISTS {TABLE}")
cur.execute(f"""
    CREATE TABLE {TABLE} (
        seed        INTEGER PRIMARY KEY,
        hit7b_count INTEGER NOT NULL,
        hit7_count  INTEGER NOT NULL,
        hit6_count  INTEGER NOT NULL,
        hit5_count  INTEGER NOT NULL,
        hit4_count  INTEGER NOT NULL
    )
""")
print(f"Table dropped+recreated in {time.time()-t0:.1f}s", flush=True)

t0 = time.time()
cur.execute("BEGIN")
CHUNK = 100_000
for i in range(0, len(all_results), CHUNK):
    chunk = all_results[i:i+CHUNK]
    cur.executemany(
        f"INSERT INTO {TABLE} (seed, hit7b_count, hit7_count, hit6_count, hit5_count, hit4_count) VALUES (?, ?, ?, ?, ?, ?)",
        chunk
    )
    print(f"  Inserted {min(i+CHUNK, len(all_results)):,} / {len(all_results):,} rows "
          f"({time.time()-t0:.1f}s elapsed)", flush=True)
conn.commit()
print(f"Insert + commit done in {time.time()-t0:.1f}s total", flush=True)

cur.execute(f"SELECT COUNT(*) FROM {TABLE}")
count = cur.fetchone()[0]
cur.execute(f"SELECT MIN(seed), MAX(seed) FROM {TABLE}")
lo, hi = cur.fetchone()
cur.execute(f"""SELECT seed, hit7b_count, hit7_count, hit6_count, hit5_count, hit4_count FROM {TABLE}
                ORDER BY hit7b_count DESC, hit7_count DESC, hit6_count DESC, hit5_count DESC, hit4_count DESC, seed ASC LIMIT 1""")
best = cur.fetchone()
cur.execute(f"""SELECT seed, hit7b_count, hit7_count, hit6_count, hit5_count, hit4_count FROM {TABLE}
                ORDER BY hit7b_count ASC, hit7_count ASC, hit6_count ASC, hit5_count ASC, hit4_count ASC, seed ASC LIMIT 1""")
worst = cur.fetchone()

conn.close()

print(f"\nWrote {count:,} rows into {TABLE} in {DB_PATH}")
print(f"Seed range covered so far: {lo:,} to {hi:,}")
print(f"Best  so far (hit7b>hit7>hit6>hit5>hit4): seed={best[0]:,} hit7b={best[1]} hit7={best[2]} hit6={best[3]} hit5={best[4]} hit4={best[5]}")
print(f"Worst so far (hit7b<hit7<hit6<hit5<hit4): seed={worst[0]:,} hit7b={worst[1]} hit7={worst[2]} hit6={worst[3]} hit5={worst[4]} hit4={worst[5]}")

pct = count / FULL_EXPECTED * 100
if count == FULL_EXPECTED and lo == FULL_SEED_LO and hi == FULL_SEED_HI:
    print(f"\nScan COMPLETE: all {count:,} seeds loaded, full range {FULL_SEED_LO:,} to {FULL_SEED_HI:,} covered.")
else:
    print(f"\nScan IN PROGRESS: {count:,} / {FULL_EXPECTED:,} seeds loaded ({pct:.1f}% of full "
          f"{FULL_SEED_LO:,} to {FULL_SEED_HI:,} range). {len(stage_nums_loaded)}/10 stages done.")
