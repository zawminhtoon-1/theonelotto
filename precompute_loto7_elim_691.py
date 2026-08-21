"""
precompute_loto7_elim_691.py
--------------------------------
First step of a Loto7 elimination page for draw #691 (next upcoming,
not yet drawn), mirroring the Loto6 elimination-page pattern (e.g.
xoshiro_elim_2130.html) but starting from just the Base pool -- no
elimination passes yet, per explicit instruction.

Base: ARIMA(2,1,0)'s K=25 prediction for draw #691. Read from
public/loto7_predictions_data.json (ARIMA's native K=15 pool, same
data the live /loto7/predictions page and
/loto7_backtest100_multik.html use), normalized to K=25 via
topKNums() -- the same generic cross-method-consensus trim/pad
function used everywhere else on this site (Python port here,
matching the JS version exactly).

Universe = all C(25,7) = 480,700 seven-number combinations drawable
from the 25-number Base pool.

Pass 1: each of the 16 prediction methods' K=22 pick for draw #691
(native K=15 pool normalized to K=22 via the same topKNums()),
checked independently -- NOT a union of raw numbers. Any Base combo
fully contained within ANY single one of these 16 K=22 sets gets
removed, same per-method containment pattern used on the Loto6
elimination pages.

Outputs:
  loto7_elim_691_meta.json           -- small: base pool, counts
  public/loto7_elim_691_combos.json  -- large: all combos (fetched
                                        client-side, not inlined)

Run: python precompute_loto7_elim_691.py
"""
import json, os, itertools, time
from collections import Counter
from math import comb

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
PREDICTIONS_PATH = BASE + r"\public\loto7_predictions_data.json"
META_OUT = BASE + r"\loto7_elim_691_meta.json"
COMBOS_OUT = BASE + r"\public\loto7_elim_691_combos.json"

LOTO7_MAX = 37
K_BASE = 25

with open(PREDICTIONS_PATH, encoding='utf-8') as f:
    payload = json.load(f)

TARGET_SERIAL = payload['nextSerial']
combos_meta = payload['combos']
all_pools = [c['numbers'] for c in combos_meta]
arima_entry = next((c for c in combos_meta if c['method'] == 'ARIMA(2,1,0)'), None)
if arima_entry is None:
    raise SystemExit("ARIMA(2,1,0) not found in loto7_predictions_data.json's combos.")
arima_native = arima_entry['numbers']
print(f"Target draw: #{TARGET_SERIAL}")
print(f"ARIMA(2,1,0) native pick (K={len(arima_native)}): {sorted(arima_native)}")

# ── topKNums, exact Python port of the JS function used throughout the site ──
def top_k_nums(combo, pools, k):
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

base_pool = top_k_nums(arima_native, all_pools, K_BASE)
if len(base_pool) != K_BASE:
    raise SystemExit(f"Base pool size mismatch: got {len(base_pool)}, expected {K_BASE}")
if not set(arima_native).issubset(set(base_pool)):
    raise SystemExit("Base pool does not contain all of ARIMA's native picks -- topKNums bug.")
print(f"\nBase (ARIMA K={K_BASE}, normalized from native K={len(arima_native)}): {base_pool}")

universe_count = comb(K_BASE, 7)
print(f"\nUniverse: C({K_BASE},7) = {universe_count:,}")

print("Enumerating all combinations...")
combos = [tuple(sorted(c)) for c in itertools.combinations(base_pool, 7)]
if len(combos) != universe_count:
    raise SystemExit(f"Combo count mismatch: got {len(combos)}, expected {universe_count}")
print(f"Generated {len(combos):,} combos.")

# ── Pass 1: 16 methods' K=22 picks, checked independently ───────────────────
print(f"\n=== Pass 1 ===")
K_METHODS = 22
METHOD_NAMES = [c['method'] for c in combos_meta]
method_native_pools = [c['numbers'] for c in combos_meta]
method_picks_22 = [top_k_nums(pool, all_pools, K_METHODS) for pool in method_native_pools]
for name, pool in zip(METHOD_NAMES, method_picks_22):
    assert len(pool) == K_METHODS, f"{name}: got {len(pool)} numbers, expected {K_METHODS}"

pos_of = {n: i for i, n in enumerate(base_pool)}
FULLBASE = (1 << K_BASE) - 1

def restricted_mask(target_set):
    mask = 0
    for n in target_set:
        if n in pos_of:
            mask |= (1 << pos_of[n])
    return mask

method_masks = []
for name, pool in zip(METHOD_NAMES, method_picks_22):
    mmask = restricted_mask(set(pool))
    overlap = bin(mmask).count('1')
    method_masks.append(mmask)
    print(f"  {name:24s} K={K_METHODS} pick: {pool}  [overlap with {K_BASE}-pool: {overlap}]")

t0 = time.time()
remaining_after1 = []
removed_by_methods = 0
for combo in combos:
    combo_mask = 0
    for n in combo:
        combo_mask |= (1 << pos_of[n])
    removed = False
    for mmask in method_masks:
        if (combo_mask & ~mmask) & FULLBASE == 0:
            removed = True
            break
    if removed:
        removed_by_methods += 1
    else:
        remaining_after1.append(list(combo))
elapsed1 = time.time() - t0
final_remaining = len(remaining_after1)
print(f"\nPass 1 elimination in {elapsed1:.1f}s")
print(f"  Removed by ANY of the 16 methods' K={K_METHODS} containment: {removed_by_methods:,}")
print(f"  Before Pass 1: {universe_count:,}  ->  After Pass 1: {final_remaining:,}")

meta = {
    'targetSerial': TARGET_SERIAL,
    'base': {'k': K_BASE, 'pool': base_pool, 'method': 'ARIMA(2,1,0)', 'nativeK': len(arima_native), 'nativePool': sorted(arima_native)},
    'universeCount': universe_count,
    'methodNames': METHOD_NAMES,
    'methodK': K_METHODS,
    'methodPicks': method_picks_22,
    'removedByMethods': removed_by_methods,
    'methodOverlaps': [bin(m).count('1') for m in method_masks],
    'finalRemaining': final_remaining,
}
with open(META_OUT, 'w', encoding='utf-8') as f:
    json.dump(meta, f, indent=2)
print(f"\nSaved {META_OUT}")

with open(COMBOS_OUT, 'w', encoding='utf-8') as f:
    json.dump(remaining_after1, f, separators=(',', ':'))
print(f"Saved {COMBOS_OUT} ({len(remaining_after1):,} combos, {os.path.getsize(COMBOS_OUT)//1024:,} KB)")
