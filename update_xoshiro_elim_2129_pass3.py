"""
update_xoshiro_elim_2129_pass3.py
-------------------------------------
Adds Pass 3 to the #2129 elimination pipeline: xoshiro256** K=33 pick
for the SAME seed as Base (#692,809, but K=33 instead of K=38), draw
#2129. Removes any of the currently-remaining 1,891,927 combos that
are fully contained within this new 33-number pool.

Note: since Pass 3 uses the same seed/draw as Base, and partial
Fisher-Yates always nests a smaller-K pick inside a larger-K pick from
the same seed, Pass 3's 33-pool is a GUARANTEED subset of Base's
38-pool (verified: all 33 numbers present in Base's 38). This isn't
independent randomness -- it's literally Base's own "inner core" that
survives even when only 33 (not 38) numbers are kept.

Filters the EXISTING remaining-combos list (from Pass 2) rather than
re-running the full C(38,6) enumeration from scratch -- much cheaper
(1.89M subset checks vs re-deriving the whole pipeline).

Run: python update_xoshiro_elim_2129_pass3.py
"""
import json, time

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
META_PATH = BASE + r"\xoshiro_elim_2129_meta.json"
COMBOS_PATH = BASE + r"\public\xoshiro_elim_2129_combos.json"

MASK64 = 0xFFFFFFFFFFFFFFFF
def splitmix64_next(z):
    z = (z + 0x9E3779B97F4A7C15) & MASK64
    zz = z
    zz = ((zz ^ (zz >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
    zz = ((zz ^ (zz >> 27)) * 0x94D049BB133111EB) & MASK64
    zz = zz ^ (zz >> 31)
    return z, zz
def seed_state(seed):
    z = seed & MASK64
    state = []
    for _ in range(4):
        z, out = splitmix64_next(z)
        state.append(out)
    return state
def rotl(x, k):
    x &= MASK64
    return ((x << k) | (x >> (64 - k))) & MASK64
def xoshiro_next(s):
    result = (rotl((s[1] * 5) & MASK64, 7) * 9) & MASK64
    t = (s[1] << 17) & MASK64
    s[2] ^= s[0]; s[3] ^= s[1]; s[1] ^= s[2]; s[0] ^= s[3]
    s[2] ^= t
    s[3] = rotl(s[3], 45)
    return result
def xoshiro_predict(seed, draw_serial, k, pool_max=43):
    combined = (seed * 10_000_000 + draw_serial) & MASK64
    s = seed_state(combined)
    arr = list(range(1, pool_max + 1))
    n = len(arr)
    for i in range(n - 1, n - 1 - k, -1):
        r = xoshiro_next(s)
        j = r % (i + 1)
        arr[i], arr[j] = arr[j], arr[i]
    return sorted(arr[n - k:])

with open(META_PATH, encoding='utf-8') as f:
    meta = json.load(f)

TARGET_SERIAL = meta['targetSerial']
SEED_PASS3 = meta['base']['seed']  # same seed as Base
K_PASS3 = 33

# Self-check against known-good chat-computed value
_KNOWN_PASS3 = [2,3,4,5,6,7,8,9,11,12,13,14,15,16,18,20,21,22,24,25,27,28,30,31,32,33,34,35,36,38,40,42,43]
pass3_pool = xoshiro_predict(SEED_PASS3, TARGET_SERIAL, K_PASS3)
assert pass3_pool == _KNOWN_PASS3, f"Pass3 self-check FAILED: {pass3_pool}"
print(f"Self-check: Pass3 (seed={SEED_PASS3}, K={K_PASS3}, draw={TARGET_SERIAL}) matches known-good value. OK.")
print(f"Pass3 pool: {pass3_pool}")

base_pool = meta['base']['pool']
is_subset = set(pass3_pool).issubset(set(base_pool))
print(f"Pass3 subset of Base's pool: {is_subset} (guaranteed by partial Fisher-Yates same-seed nesting)")
extra_in_base = sorted(set(base_pool) - set(pass3_pool))
print(f"Numbers only in Base (not Pass3): {extra_in_base}")

with open(COMBOS_PATH, encoding='utf-8') as f:
    remaining_before = json.load(f)
before_count = len(remaining_before)
print(f"\nRemaining before Pass 3: {before_count:,}")

pass3_set = set(pass3_pool)
t0 = time.time()
removed_by_pass3 = 0
remaining_after = []
for combo in remaining_before:
    if set(combo).issubset(pass3_set):
        removed_by_pass3 += 1
    else:
        remaining_after.append(combo)
elapsed = time.time() - t0

after_count = len(remaining_after)
print(f"Filtered {before_count:,} combos in {elapsed:.1f}s")
print(f"Removed by Pass 3 ({K_PASS3}-set) containment: {removed_by_pass3:,}")
print(f"Final remaining: {after_count:,}")
print(f"\nElimination sequence: {meta['universeCount']:,} -> {meta['afterPass1']:,} -> {before_count:,} -> {after_count:,} remaining")

# ── Update meta ───────────────────────────────────────────────────────────
meta['pass3'] = {'seed': SEED_PASS3, 'k': K_PASS3, 'pool': pass3_pool, 'isSubsetOfBase': is_subset}
meta['beforePass3'] = before_count
meta['removedByPass3'] = removed_by_pass3
meta['finalRemaining'] = after_count

with open(META_PATH, 'w', encoding='utf-8') as f:
    json.dump(meta, f, indent=2)
print(f"\nUpdated {META_PATH}")

with open(COMBOS_PATH, 'w', encoding='utf-8') as f:
    json.dump(remaining_after, f, separators=(',', ':'))
import os
print(f"Updated {COMBOS_PATH} ({after_count:,} combos, {os.path.getsize(COMBOS_PATH)//1024:,} KB)")
