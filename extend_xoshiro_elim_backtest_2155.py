"""
extend_xoshiro_elim_backtest_2155.py
-------------------------------------
Extends xoshiro_elim_backtest100_meta.json (originally #2035-2134, 100 draws)
with draws #2135..2155 WITHOUT recomputing or touching the existing 100
results. Reuses run_for_draw() from precompute_xoshiro_elim_backtest100.py
unchanged, so methodology (strict walk-forward, no leakage) is identical.

Before extending, re-runs two already-stored draws and asserts the output
matches the stored result exactly (reproducibility check).

Run: python extend_xoshiro_elim_backtest_2155.py [--check-only]
"""
import json, sys, time, sqlite3
from collections import Counter
import psycopg2

import precompute_xoshiro_elim_backtest100 as P  # import runs P's xoshiro self-check

NEW_LO, NEW_HI = 2135, 2155
CHECK_SERIALS = [2035, 2134]  # one in-base (pass2 elim), one never_in_base
OUTCOME_ORDER = ['never_in_base', 'eliminated_pass1', 'eliminated_pass2', 'eliminated_pass3',
                 'eliminated_pass4', 'eliminated_pass5', 'survived']

with open(P.META_OUT, encoding='utf-8') as f:
    meta = json.load(f)
stored = {r['serial']: r for r in meta['results']}
assert meta['drawRange'][0] == 2035, meta['drawRange']

conn = sqlite3.connect(P.DB_PATH)
worst = conn.execute(f"SELECT seed, hit0_count FROM {P.RANDOM_TABLE} ORDER BY hit0_count DESC, seed ASC "
                     f"LIMIT {P.N_WORST_SEEDS}").fetchall()
conn.close()
print(f"Loaded {len(worst)} worst-coverage seeds.")

conn = psycopg2.connect(P.os.environ['DATABASE_URL'])
cur = conn.cursor()
cur.execute("SELECT draw_serial, draw_date, num1,num2,num3,num4,num5,num6 FROM loto6_results "
            "WHERE draw_serial = ANY(%s) OR draw_serial BETWEEN %s AND %s ORDER BY draw_serial",
            (CHECK_SERIALS, NEW_LO, NEW_HI))
rows = {r[0]: r for r in cur.fetchall()}
conn.close()

def run(serial):
    s, d, *nums = rows[serial]
    return P.run_for_draw(s, d.isoformat(), nums, worst)

# 1. Reproducibility check against stored results
for s in CHECK_SERIALS:
    t = time.time()
    r = run(s)
    ok = r == stored[s]
    print(f"check #{s}: {'MATCH' if ok else 'MISMATCH'} ({time.time()-t:.1f}s) outcome={r['outcome']}")
    if not ok:
        print("  stored:", stored[s]); print("  now:   ", r)
        sys.exit("Reproducibility check failed -- aborting without writing.")
if '--check-only' in sys.argv:
    sys.exit(0)

# 2. Extend
missing = [s for s in range(NEW_LO, NEW_HI + 1) if s not in stored]
assert all(s in rows for s in missing), "DB is missing some target draws"
new_results, t0 = [], time.time()
for i, s in enumerate(missing, 1):
    r = run(s)
    new_results.append(r)
    print(f"[{i}/{len(missing)}] #{s}: {r['outcome']} kBase={r['kBase']} overlap={r['baseOverlap']} "
          f"({time.time()-t0:.0f}s)", flush=True)
ext_elapsed = time.time() - t0

# 3. Merge (existing results kept verbatim) and write
results = meta['results'] + new_results
results.sort(key=lambda r: r['serial'])
serials = [r['serial'] for r in results]
assert serials == list(range(serials[0], serials[-1] + 1)), "gap/duplicate in merged serials"
outcomes = Counter(r['outcome'] for r in results)
meta.update({
    'nDraws': len(results),
    'drawRange': [serials[0], serials[-1]],
    'outcomeSummary': {k: outcomes[k] for k in OUTCOME_ORDER if outcomes.get(k)},
    'results': results,
    'elapsedSeconds': meta['elapsedSeconds'] + ext_elapsed,
    'extensions': meta.get('extensions', []) + [
        {'drawRange': [missing[0], missing[-1]], 'nDraws': len(missing), 'elapsedSeconds': ext_elapsed}],
})
with open(P.META_OUT, 'w', encoding='utf-8') as f:
    json.dump(meta, f, indent=2)
print(f"\nSaved {P.META_OUT}: {meta['nDraws']} draws #{serials[0]}-{serials[-1]}")
print("Outcome summary:", meta['outcomeSummary'])
