"""
precompute_xoshiro_elim_2135.py
--------------------------------
First step of a Loto6 elimination page for draw #2135 (next upcoming,
not yet drawn) -- Base pool only, no elimination passes yet, per
explicit instruction. Passes will be added in later, separately-
directed builds (same pattern as pcg64_elim_693.html's build).

Base: xoshiro256** best K=38 seed #692,809's pick for draw #2135,
walk-forward, trained on all real draws through #2134. Single-source
construction -- deliberately simpler than xoshiro_elim_2134.html's
two-way (xoshiro ∩ Modular Cycle) Base. Seed #692,809 is the overall
winner of the completed 0-1,000,000 K=38 seed scan
(xoshiro_seed_scan_k38.html).

Universe = all C(38,6) = 2,760,681 six-number combinations drawable
from the 38-number Base pool.

Mirrors xoshiro_elim_2134.html's combo browser exactly (number
include/exclude filter grid, pagination, CSV download) -- no hot/cold
filter or diverse-sample generator, since the Loto6 xoshiro_elim_*
family doesn't have those (unlike the Loto7 pages/pcg64_top3_elim_2134
/xo_pcg_elim_2134). No historical-combos asset needed as a result.

Outputs:
  xoshiro_elim_2135_meta.json           -- small: base pool, seed, counts
  public/xoshiro_elim_2135_combos.json  -- large: all combos (fetched
                                           client-side, not inlined)

Run: python precompute_xoshiro_elim_2135.py
"""
import json, os, re, itertools, time
from math import comb
import psycopg2

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
ENV_LOCAL = BASE + r"\.env.local"
META_OUT = BASE + r"\xoshiro_elim_2135_meta.json"
COMBOS_OUT = BASE + r"\public\xoshiro_elim_2135_combos.json"

LOTO6_MAX = 43
TARGET_SERIAL = 2135
SEED_XO = 692809   # best K=38 seed (0-1,000,000 scan)
K_XO = 38

# ── xoshiro256** (verified implementation, same as every other page) ────────
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
def xoshiro_predict_raw(seed, draw_serial, k, pool_max=LOTO6_MAX):
    """Generation order -- the order the partial Fisher-Yates shuffle finalizes
    each position (i = n-1 first, down to i = n-k last), NOT sorted."""
    combined = (seed * 10_000_000 + draw_serial) & MASK64
    s = seed_state(combined)
    arr = list(range(1, pool_max + 1))
    n = len(arr)
    order = []
    for i in range(n - 1, n - 1 - k, -1):
        r = xoshiro_next(s)
        j = r % (i + 1)
        arr[i], arr[j] = arr[j], arr[i]
        order.append(arr[i])
    return order
def xoshiro_predict(seed, draw_serial, k, pool_max=LOTO6_MAX):
    return sorted(xoshiro_predict_raw(seed, draw_serial, k, pool_max))

# ── Self-check against known-good value before trusting the xoshiro side ────
_KNOWN_2129 = [2,3,4,5,6,7,8,9,11,12,13,14,15,16,17,18,19,20,21,22,24,25,27,28,29,30,31,32,33,34,35,36,38,39,40,41,42,43]
_check = xoshiro_predict(SEED_XO, 2129, K_XO)
assert _check == _KNOWN_2129, f"Self-check FAILED: {_check}"
print(f"Self-check OK: xoshiro seed {SEED_XO} K={K_XO} draw #2129 matches known-good value.")

base_pool_ordered = xoshiro_predict_raw(SEED_XO, TARGET_SERIAL, K_XO)
base_pool = sorted(base_pool_ordered)
K_BASE = len(base_pool)
print(f"\nBase: xoshiro K={K_XO} seed #{SEED_XO} pick for draw #{TARGET_SERIAL}: {base_pool}")

universe_count = comb(K_BASE, 6)
print(f"Universe: C({K_BASE},6) = {universe_count:,}")

# ── Confirm DB's latest draw is #2134 (walk-forward, no leakage) ────────────
if 'DATABASE_URL' not in os.environ:
    with open(ENV_LOCAL, encoding='utf-8') as f:
        env_text = f.read()
    m = re.search(r'DATABASE_URL=(.+)', env_text)
    os.environ['DATABASE_URL'] = m.group(1).strip()

conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()
cur.execute("SELECT MAX(draw_serial) FROM loto6_results")
latest = cur.fetchone()[0]
conn.close()
print(f"DB's latest draw: #{latest}")
if latest != TARGET_SERIAL - 1:
    raise SystemExit(f"Expected latest draw #{TARGET_SERIAL-1}, found #{latest} -- stale.")

# ── Enumerate the full universe (no passes -- Base only) ────────────────────
print(f"\nEnumerating all C({K_BASE},6) combinations (no elimination passes)...")
t0 = time.time()
combos = [sorted(c) for c in itertools.combinations(base_pool, 6)]
elapsed = time.time() - t0
if len(combos) != universe_count:
    raise SystemExit(f"Combo count mismatch: got {len(combos)}, expected {universe_count}")
print(f"Generated {len(combos):,} combos in {elapsed:.1f}s.")

# ── Save outputs ──────────────────────────────────────────────────────────
meta = {
    'targetSerial': TARGET_SERIAL,
    'trainedThroughSerial': latest,
    'seed': SEED_XO,
    'k': K_XO,
    'poolMax': LOTO6_MAX,
    'base': {'k': K_BASE, 'pool': base_pool, 'poolOrdered': base_pool_ordered},
    'universeCount': universe_count,
}
with open(META_OUT, 'w', encoding='utf-8') as f:
    json.dump(meta, f, indent=2)
print(f"\nSaved {META_OUT}")

with open(COMBOS_OUT, 'w', encoding='utf-8') as f:
    json.dump(combos, f, separators=(',', ':'))
print(f"Saved {COMBOS_OUT} ({len(combos):,} combos, {os.path.getsize(COMBOS_OUT)//1024/1024:.1f} MB)")
