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

# ── Enumerate the full universe (no passes -- Base only) ────────────────────
print(f"\nEnumerating all C({K_BASE},7) combinations (no elimination passes)...")
t0 = time.time()
combos = [sorted(c) for c in itertools.combinations(base_pool, 7)]
elapsed = time.time() - t0
if len(combos) != universe_count:
    raise SystemExit(f"Combo count mismatch: got {len(combos)}, expected {universe_count}")
print(f"Generated {len(combos):,} combos in {elapsed:.1f}s.")

# ── Save outputs ──────────────────────────────────────────────────────────
meta = {
    'targetSerial': TARGET_SERIAL,
    'trainedThroughSerial': db_rows[-1][0],
    'seed': SEED,
    'k': K_PICKS,
    'base': {'k': K_BASE, 'pool': base_pool, 'poolOrdered': base_pool_ordered},
    'universeCount': universe_count,
    'historicalDrawCount': len(all_main7),
}
with open(META_OUT, 'w', encoding='utf-8') as f:
    json.dump(meta, f, indent=2)
print(f"\nSaved {META_OUT}")

with open(COMBOS_OUT, 'w', encoding='utf-8') as f:
    json.dump(combos, f, separators=(',', ':'))
print(f"Saved {COMBOS_OUT} ({len(combos):,} combos, {os.path.getsize(COMBOS_OUT)//1024/1024:.1f} MB)")

with open(HISTORICAL_OUT, 'w', encoding='utf-8') as f:
    json.dump(all_main7, f, separators=(',', ':'))
print(f"Saved {HISTORICAL_OUT} ({len(all_main7):,} combos, {os.path.getsize(HISTORICAL_OUT)//1024:,} KB)")
