"""
precompute_pcg64_elim_693.py
--------------------------------
First step of a Loto7 PCG64-seed elimination page for draw #693 (next
upcoming, not yet drawn) -- mirrors the Loto6 elimination-page pattern
(e.g. xoshiro_elim_2130.html) but starting from just the Base pool, no
elimination passes yet, per explicit instruction. Passes will be added
in later, separately-directed builds.

Base: PCG64 (O'Neill XSL-RR 128/64) K=30 Loto7 seed #-2,826,673's pick
for draw #693 -- the overall winner of the completed Loto7 PCG64 K=30
scan (seeds -5,000,000 to 5,000,000, draws #1-650). Same construction
already verified bit-exact against numpy.random.Generator(PCG64()) for
this pool_max=37/K=30 configuration on the scan page itself.

Universe = all C(30,7) = 2,035,800 seven-number combinations drawable
from the 30-number Base pool.

Pass 1: each of the 16 prediction methods' K=20 pick for draw #693
(native K=15 pool normalized to K=20 via topKNums(), walk-forward
trained through #692, read from public/loto7_predictions_data.json --
same data loto7_elim_693.html's Pass 1 uses, just K=20 instead of
K=22). Checked independently, NOT a union. Any Base combo fully
contained within ANY single one of these 16 K=20 sets gets removed.

Pass 2: for each of the 16 methods INDIVIDUALLY, that method's K=31
pick intersected with Base (the 30-number PCG64 pool) -- 16 separate
method-specific intersected pools, not one combined 16-way
intersection. Any Pass-1-remaining combo fully contained within ANY
SINGLE one of these 16 intersected pools gets removed (same
independent-check pattern as Pass 1, just Base-intersected K=31
instead of raw K=20).

Pass 3: removes any Pass-2-remaining combo that shares 5 or more
numbers with ANY of the last 100 actual draws before #693 (draws
#593-692) -- checked against a whole 100-draw window, not a single
fixed distance, structurally the same "any of the last 100 draws"
pattern as the Loto6 elimination pages' Pass 10 (though that page uses
a 3/4/5 threshold tuned to its own multi-distance study; this pass
uses the explicitly-requested >=5 threshold for Loto7). Well-supported
basis: a multi-distance overlap validation across Loto7's full history
(distances 1,2,3,5,10,50,100 steps back) found overlap>=6 has NEVER
occurred at any tested distance (0 occurrences across 592-691 pairs
per distance); overlap=5 itself is rare (5 occurrences total across
all distances tested combined).

Pass 4 (NEW, final): removes any Pass-3-remaining combo with 4 or more
consecutive (adjacent, differ-by-1) pairs among its 7 numbers.
Well-supported basis: a consecutive-pairs analysis across all 692 real
Loto7 draws found 4-pair combos occurred 7 times (1.01%, vs 0.65%
exact chance expectation); 5- and 6-pair combos occurred ZERO times
(vs 0.027% and 0.0003% chance expectation respectively) -- essentially
never happens. This is the final pass on this page for now.

Outputs:
  pcg64_elim_693_meta.json           -- small: base pool, seed, counts
  public/pcg64_elim_693_combos.json  -- large: all combos (fetched
                                        client-side, not inlined)
  public/pcg64_elim_693_historical.json -- historical winning combos
                                        (for the hot/cold filter split,
                                        same asset pattern as
                                        loto7_elim_693_historical.json)

Run: python precompute_pcg64_elim_693.py
"""
import json, os, re, itertools, time
from math import comb
from collections import Counter
import psycopg2

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
ENV_LOCAL = BASE + r"\.env.local"
META_OUT = BASE + r"\pcg64_elim_693_meta.json"
COMBOS_OUT = BASE + r"\public\pcg64_elim_693_combos.json"
HISTORICAL_OUT = BASE + r"\public\pcg64_elim_693_historical.json"

LOTO7_MAX = 37
TARGET_SERIAL = 693
K_PICKS = 30
SEED = -2826673

# ── PCG64 (O'Neill XSL-RR 128/64), SplitMix64-expanded state -- identical
# construction to the Loto7 PCG64 K=30 seed scan, already verified bit-exact
# against numpy.random.Generator(PCG64()) for this pool_max=37/K=30 config. ──
MASK64 = 0xFFFFFFFFFFFFFFFF
MASK128 = (1 << 128) - 1
PCG_MULT_128 = 0x2360ed051fc65da44385df649fccf645

def splitmix64_next(z):
    z = (z + 0x9E3779B97F4A7C15) & MASK64
    zz = z
    zz = ((zz ^ (zz >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
    zz = ((zz ^ (zz >> 27)) * 0x94D049BB133111EB) & MASK64
    zz = zz ^ (zz >> 31)
    return z, zz

def pcg64_predict_raw(seed, draw_serial, k, pool_max=LOTO7_MAX):
    combined = (seed * 10_000_000 + draw_serial) & MASK64
    z = combined & MASK64
    outs = []
    for _ in range(4):
        z, o = splitmix64_next(z)
        outs.append(o)
    state = ((outs[0] << 64) | outs[1]) & MASK128
    inc = (((outs[2] << 64) | outs[3]) | 1) & MASK128
    def rotr64(v, rot):
        rot &= 63
        return ((v >> rot) | (v << ((-rot) & 63))) & MASK64
    arr = list(range(1, pool_max + 1))
    n = len(arr)
    order = []
    for i in range(n - 1, n - 1 - k, -1):
        state = (state * PCG_MULT_128 + inc) & MASK128
        xored = (state >> 64) ^ (state & MASK64)
        rot = (state >> 122) & 0x3f
        out = rotr64(xored, rot)
        j = out % (i + 1)
        arr[i], arr[j] = arr[j], arr[i]
        order.append(arr[i])
    return order

def pcg64_predict(seed, draw_serial, k, pool_max=LOTO7_MAX):
    return sorted(pcg64_predict_raw(seed, draw_serial, k, pool_max))

# ── Self-check against known-good reference vector before trusting Base ─────
_KNOWN_M5M_1 = [2, 3, 4, 5, 6, 8, 10, 11, 12, 15, 16, 17, 18, 19, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 37]
_check = pcg64_predict(-5000000, 1, K_PICKS)
assert _check == _KNOWN_M5M_1, f"PCG64 self-check FAILED: {_check}"
print(f"Self-check OK: PCG64 seed -5,000,000 K={K_PICKS} draw #1 matches known-good value.")

base_pool_ordered = pcg64_predict_raw(SEED, TARGET_SERIAL, K_PICKS)
base_pool = sorted(base_pool_ordered)
K_BASE = len(base_pool)
print(f"\nBase: PCG64 K={K_PICKS} seed #{SEED} pick for draw #{TARGET_SERIAL}: {base_pool}")

universe_count = comb(K_BASE, 7)
print(f"Universe: C({K_BASE},7) = {universe_count:,}")

# ── Fetch all real draws through #692 (for the hot/cold filter's historical
# frequency split -- same asset pattern as loto7_elim_693_historical.json,
# NOT used for any elimination pass here since there are none yet). ─────────
if 'DATABASE_URL' not in os.environ:
    with open(ENV_LOCAL, encoding='utf-8') as f:
        env_text = f.read()
    m = re.search(r'DATABASE_URL=(.+)', env_text)
    os.environ['DATABASE_URL'] = m.group(1).strip()

conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()
cur.execute(
    "SELECT draw_serial, num1,num2,num3,num4,num5,num6,num7 "
    "FROM loto7_results ORDER BY draw_serial"
)
db_rows = cur.fetchall()
conn.close()
print(f"\nFetched {len(db_rows)} historical draws (#{db_rows[0][0]}-{db_rows[-1][0]}).")
if db_rows[-1][0] != TARGET_SERIAL - 1:
    raise SystemExit(f"Expected latest draw #{TARGET_SERIAL-1}, found #{db_rows[-1][0]} -- draw window assumption is stale.")

all_main7 = [sorted([r[1], r[2], r[3], r[4], r[5], r[6], r[7]]) for r in db_rows]

# ── Enumerate the full universe (Base bitmask positions) ────────────────────
print(f"\nEnumerating all C({K_BASE},7) combinations...")
t0 = time.time()
pos_of = {n: i for i, n in enumerate(base_pool)}
FULLBASE = (1 << K_BASE) - 1

def restricted_mask(target_set):
    mask = 0
    for n in target_set:
        if n in pos_of:
            mask |= (1 << pos_of[n])
    return mask

universe_masks = []
for combo_positions in itertools.combinations(range(K_BASE), 7):
    mask = 0
    for p in combo_positions:
        mask |= (1 << p)
    universe_masks.append(mask)
elapsed = time.time() - t0
if len(universe_masks) != universe_count:
    raise SystemExit(f"Combo count mismatch: got {len(universe_masks)}, expected {universe_count}")
print(f"Generated {len(universe_masks):,} combo masks in {elapsed:.1f}s.")

# ── Pass 1 (NEW): 16 methods' K=20 picks, checked independently ────────────
print(f"\n=== Pass 1 (NEW) ===")
K_METHODS = 20
PREDICTIONS_PATH = BASE + r"\public\loto7_predictions_data.json"
with open(PREDICTIONS_PATH, encoding='utf-8') as f:
    payload = json.load(f)
if payload['nextSerial'] != TARGET_SERIAL:
    raise SystemExit(f"loto7_predictions_data.json is for draw #{payload['nextSerial']}, expected #{TARGET_SERIAL} -- stale.")
combos_meta = payload['combos']
all_pools = [c['numbers'] for c in combos_meta]
METHOD_NAMES = [c['method'] for c in combos_meta]

def top_k_nums(combo, pools, k):
    from collections import Counter
    freq = Counter()
    for pool in pools:
        for n in pool:
            freq[n] += 1
    if len(combo) == k:
        return sorted(combo)
    if len(combo) > k:
        return sorted(sorted(combo, key=lambda n: -freq.get(n, 0))[:k])
    in_combo = set(combo)
    extra = sorted((n for n in freq if n not in in_combo), key=lambda n: -freq.get(n, 0))
    if len(combo) + len(extra) < k:
        have = set(combo) | set(extra)
        for n in range(1, LOTO7_MAX + 1):
            if n not in have:
                extra.append(n)
    extra = extra[:k - len(combo)]
    return sorted(list(combo) + extra)

method_picks_20 = [top_k_nums(pool, all_pools, K_METHODS) for pool in all_pools]
for name, pool in zip(METHOD_NAMES, method_picks_20):
    assert len(pool) == K_METHODS, f"{name}: got {len(pool)} numbers, expected {K_METHODS}"

method_masks = []
for name, pool in zip(METHOD_NAMES, method_picks_20):
    mmask = restricted_mask(set(pool))
    overlap = bin(mmask).count('1')
    method_masks.append(mmask)
    print(f"  {name:24s} K={K_METHODS} pick: {pool}  [overlap with {K_BASE}-pool: {overlap}]")

t0 = time.time()
remaining_after1 = []
removed_by_methods = 0
for combo_mask in universe_masks:
    removed = False
    for mmask in method_masks:
        if (combo_mask & ~mmask) & FULLBASE == 0:
            removed = True
            break
    if removed:
        removed_by_methods += 1
        continue
    remaining_after1.append(tuple(sorted(base_pool[p] for p in range(K_BASE) if combo_mask & (1 << p))))
elapsed1 = time.time() - t0
final_remaining_pass1 = len(remaining_after1)
print(f"\nPass 1 elimination in {elapsed1:.1f}s")
print(f"  Removed by ANY of the 16 methods' K={K_METHODS} containment: {removed_by_methods:,}")
print(f"  Before Pass 1: {universe_count:,}  ->  After Pass 1: {final_remaining_pass1:,}")

# ── Pass 2 (NEW): for each method individually, that method's K=31 pick
# INTERSECTED with Base -- 16 separate method-specific intersected pools,
# checked independently (not a combined 16-way intersection). ─────────────
print(f"\n=== Pass 2 (NEW) ===")
K_PASS2_METHOD = 31
method_picks_31 = [top_k_nums(pool, all_pools, K_PASS2_METHOD) for pool in all_pools]
for name, pool in zip(METHOD_NAMES, method_picks_31):
    assert len(pool) == K_PASS2_METHOD, f"{name}: got {len(pool)} numbers, expected {K_PASS2_METHOD}"

base_set = set(base_pool)
pass2_intersected_pools = [sorted(base_set & set(pool)) for pool in method_picks_31]
pass2_masks = []
for name, ipool in zip(METHOD_NAMES, pass2_intersected_pools):
    mmask = restricted_mask(set(ipool))
    pass2_masks.append(mmask)
    print(f"  {name:24s} K={K_PASS2_METHOD} pick ∩ Base: {len(ipool)} numbers: {ipool}")

t0 = time.time()
remaining_after2 = []
removed_by_pass2 = 0
for combo in remaining_after1:
    combo_mask = 0
    for n in combo:
        combo_mask |= (1 << pos_of[n])
    removed = False
    for mmask in pass2_masks:
        if (combo_mask & ~mmask) & FULLBASE == 0:
            removed = True
            break
    if removed:
        removed_by_pass2 += 1
        continue
    remaining_after2.append(combo)
elapsed2 = time.time() - t0
final_remaining_pass2 = len(remaining_after2)
print(f"\nPass 2 elimination in {elapsed2:.1f}s")
print(f"  Removed by ANY of the 16 methods' (K={K_PASS2_METHOD} ∩ Base) containment: {removed_by_pass2:,}")
print(f"  Before Pass 2: {final_remaining_pass1:,}  ->  After Pass 2: {final_remaining_pass2:,}")

# ── Pass 3 (NEW): removes any combo sharing 5+ numbers with ANY of the last
# 100 actual draws before #693 (draws #593-692). ────────────────────────────
print(f"\n=== Pass 3 (NEW) ===")
PASS3_WINDOW = 100
PASS3_OVERLAP_THRESHOLD = 5
last100_serials = [r[0] for r in db_rows[-PASS3_WINDOW:]]
assert len(last100_serials) == PASS3_WINDOW, f"Expected {PASS3_WINDOW} draws, got {len(last100_serials)}"
assert last100_serials[0] == TARGET_SERIAL - PASS3_WINDOW and last100_serials[-1] == TARGET_SERIAL - 1, \
    f"Last-100 window mismatch: got #{last100_serials[0]}-{last100_serials[-1]}, expected #{TARGET_SERIAL-PASS3_WINDOW}-{TARGET_SERIAL-1}"
last100_sets = [set(r[1:8]) for r in db_rows[-PASS3_WINDOW:]]
print(f"Checking against the last {PASS3_WINDOW} actual draws: #{last100_serials[0]}-{last100_serials[-1]}")

t0 = time.time()
remaining_after3 = []
removed_by_pass3 = 0
for combo in remaining_after2:
    combo_set = set(combo)
    removed = False
    for draw_set in last100_sets:
        if len(combo_set & draw_set) >= PASS3_OVERLAP_THRESHOLD:
            removed = True
            break
    if removed:
        removed_by_pass3 += 1
        continue
    remaining_after3.append(combo)
elapsed3 = time.time() - t0
final_remaining_pass3 = len(remaining_after3)
print(f"\nPass 3 elimination in {elapsed3:.1f}s")
print(f"  Removed (overlap >= {PASS3_OVERLAP_THRESHOLD} with ANY of the last {PASS3_WINDOW} draws): {removed_by_pass3:,}")
print(f"  Before Pass 3: {final_remaining_pass2:,}  ->  After Pass 3: {final_remaining_pass3:,}")

# ── Pass 4 (NEW, final): removes any combo with 4+ consecutive (adjacent,
# differ-by-1) pairs among its 7 numbers. Validated in chat immediately
# before this build: across all 692 real Loto7 draws, 4-pair combos occurred
# 7 times (1.01%, close to the 0.65% chance expectation, ratio 1.54x -- a
# small-count bin, not a strong effect but not contradicted either); 5- and
# 6-pair combos occurred ZERO times (chance expectation 0.19 and 0.002
# respectively -- consistent with "essentially never happens"). This pass
# uses the explicitly-requested >=4 threshold, covering all three tiers. ────
print(f"\n=== Pass 4 (NEW, final) ===")
PASS4_PAIR_THRESHOLD = 4

def max_consecutive_pairs(combo):
    s = sorted(combo)
    runs = 1
    for i in range(1, len(s)):
        if s[i] != s[i-1] + 1:
            runs += 1
    return len(s) - runs  # pairs = k - number_of_runs

t0 = time.time()
remaining_after4 = []
removed_by_pass4 = 0
pair_dist = Counter()
for combo in remaining_after3:
    pairs = max_consecutive_pairs(combo)
    pair_dist[pairs] += 1
    if pairs >= PASS4_PAIR_THRESHOLD:
        removed_by_pass4 += 1
        continue
    remaining_after4.append(combo)
elapsed4 = time.time() - t0
final_remaining_pass4 = len(remaining_after4)
print(f"Pair-count distribution (of Pass-3-remaining combos): " + ", ".join(f"{k}:{v:,}" for k, v in sorted(pair_dist.items())))
print(f"Pass 4 elimination in {elapsed4:.1f}s")
print(f"  Removed (consecutive-pair count >= {PASS4_PAIR_THRESHOLD}): {removed_by_pass4:,}")
print(f"  Before Pass 4: {final_remaining_pass3:,}  ->  After Pass 4: {final_remaining_pass4:,}")

# ── Save outputs ──────────────────────────────────────────────────────────
meta = {
    'targetSerial': TARGET_SERIAL,
    'trainedThroughSerial': db_rows[-1][0],
    'seed': SEED,
    'k': K_PICKS,
    'base': {'k': K_BASE, 'pool': base_pool, 'poolOrdered': base_pool_ordered},
    'universeCount': universe_count,
    'historicalDrawCount': len(all_main7),
    'methodNames': METHOD_NAMES,
    'methodK': K_METHODS,
    'methodPicks': method_picks_20,
    'removedByMethods': removed_by_methods,
    'methodOverlaps': [bin(m).count('1') for m in method_masks],
    'finalRemainingPass1': final_remaining_pass1,
    'pass2MethodK': K_PASS2_METHOD,
    'pass2IntersectedPools': pass2_intersected_pools,
    'removedByPass2': removed_by_pass2,
    'finalRemainingPass2': final_remaining_pass2,
    'pass3Window': PASS3_WINDOW,
    'pass3OverlapThreshold': PASS3_OVERLAP_THRESHOLD,
    'pass3WindowSerials': [last100_serials[0], last100_serials[-1]],
    'pass3WindowDraws': [sorted(s) for s in last100_sets],
    'removedByPass3': removed_by_pass3,
    'finalRemainingPass3': final_remaining_pass3,
    'pass4PairThreshold': PASS4_PAIR_THRESHOLD,
    'pass4PairDistribution': {str(k): v for k, v in sorted(pair_dist.items())},
    'removedByPass4': removed_by_pass4,
    'finalRemainingPass4': final_remaining_pass4,
    'finalRemaining': final_remaining_pass4,
}
with open(META_OUT, 'w', encoding='utf-8') as f:
    json.dump(meta, f, indent=2)
print(f"\nSaved {META_OUT}")

with open(COMBOS_OUT, 'w', encoding='utf-8') as f:
    json.dump(remaining_after4, f, separators=(',', ':'))
print(f"Saved {COMBOS_OUT} ({len(remaining_after4):,} combos, {os.path.getsize(COMBOS_OUT)//1024/1024:.1f} MB)")

with open(HISTORICAL_OUT, 'w', encoding='utf-8') as f:
    json.dump(all_main7, f, separators=(',', ':'))
print(f"Saved {HISTORICAL_OUT} ({len(all_main7):,} combos, {os.path.getsize(HISTORICAL_OUT)//1024:,} KB)")
