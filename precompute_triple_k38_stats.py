"""
precompute_triple_k38_stats.py
-----------------------------------
Precomputes everything the "Triple K=38 Intersection -- xoshiro x
Modular Cycle x PCG64" stats page needs: the current #2134 pool
(three component K=38 pools -- xoshiro256** seed #692,809, Modular
Cycle native, PCG64 seed #-4,675,555 -- and their triple intersection),
plus a walk-forward backtest of that same construction over the last
101 real draws (#2033-2133), no leakage.

CAVEAT (carried into the page, not just this docstring): the PCG64
seed #-4,675,555 was found via a scan against the FIXED #1-2050 draw
window (Stage 1 of the PCG64 K=38 scan). Draws #2033-2050 of this
backtest (18 of the 101) were part of that same scanned window, so
results on those draws are partially in-sample for that seed. Draws
#2051-2133 are genuinely out-of-sample. The xoshiro seed #692,809 has
an analogous history from its own earlier 0-1,000,000 K=38 scan.

Significance is computed via the exact per-draw hypergeometric chance
(NOT a single fixed avg-K approximation) since the triple-intersection
pool size varies draw to draw (28-33 in this window) -- expected count
and variance are summed across draws (each an independent
hypergeometric trial), then a normal-approximation z-test / chi-square
(df=1) is applied to the sum, same convention as the site's other
varying-pool-size backtests (e.g. the 2-2-2 hot/cold pool test).

Two windows reported: the full 101-draw window (#2033-2133) and the
last 50 draws (#2084-2133).

Output: triple_k38_stats_meta.json
Run: python precompute_triple_k38_stats.py
"""
import json, os, re, math
from collections import Counter

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
ENV_LOCAL = BASE + r"\.env.local"
META_OUT = BASE + r"\triple_k38_stats_meta.json"

LOTO6_MAX = 43
K = 38
SEED_XO = 692809
SEED_PCG = -4675555
TARGET_SERIAL = 2134
BACKTEST101_LO, BACKTEST101_HI = 2033, 2133
BACKTEST50_LO, BACKTEST50_HI = 2084, 2133

MASK64 = 0xFFFFFFFFFFFFFFFF

def xoshiro_predict_raw(seed, draw_serial, k, pool_max, arr_template):
    combined = (seed * 10_000_000 + draw_serial) & MASK64
    z = combined & MASK64
    s = [0, 0, 0, 0]
    for i in range(4):
        z = (z + 0x9E3779B97F4A7C15) & MASK64
        zz = z
        zz = ((zz ^ (zz >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
        zz = ((zz ^ (zz >> 27)) * 0x94D049BB133111EB) & MASK64
        zz = zz ^ (zz >> 31)
        s[i] = zz
    s0, s1, s2, s3 = s
    arr = arr_template[:]
    n = pool_max
    order = []
    for i in range(n - 1, n - 1 - k, -1):
        result = (((((s1 * 5) & MASK64) << 7) | (((s1 * 5) & MASK64) >> 57)) & MASK64)
        result = (result * 9) & MASK64
        t = (s1 << 17) & MASK64
        s2 ^= s0
        s3 ^= s1
        s1 ^= s2
        s0 ^= s3
        s2 ^= t
        s3 = ((s3 << 45) | (s3 >> 19)) & MASK64
        j = result % (i + 1)
        arr[i], arr[j] = arr[j], arr[i]
        order.append(arr[i])
    return order

def xoshiro_predict(seed, draw_serial, k, pool_max, arr_template):
    return sorted(xoshiro_predict_raw(seed, draw_serial, k, pool_max, arr_template))

# ── PCG64 (verified bit-exact against numpy.random.Generator(PCG64())) ──────
MASK128 = (1 << 128) - 1
PCG_MULT_128 = 0x2360ed051fc65da44385df649fccf645
def splitmix64_next(z):
    z = (z + 0x9E3779B97F4A7C15) & MASK64
    zz = z
    zz = ((zz ^ (zz >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
    zz = ((zz ^ (zz >> 27)) * 0x94D049BB133111EB) & MASK64
    zz = zz ^ (zz >> 31)
    return z, zz
def expand_seed_to_pcg_state(combined):
    z = combined & MASK64
    outs = []
    for _ in range(4):
        z, o = splitmix64_next(z)
        outs.append(o)
    state = (outs[0] << 64) | outs[1]
    inc = ((outs[2] << 64) | outs[3]) | 1
    return state & MASK128, inc & MASK128
def rotr64(v, rot):
    rot &= 63
    return ((v >> rot) | (v << ((-rot) & 63))) & MASK64
def pcg64_next(state, inc):
    state = (state * PCG_MULT_128 + inc) & MASK128
    xored = (state >> 64) ^ (state & MASK64)
    rot = (state >> 122) & 0x3f
    out = rotr64(xored, rot)
    return state, out
def pcg64_predict_raw(seed, draw_serial, k, pool_max=LOTO6_MAX):
    combined = (seed * 10_000_000 + draw_serial) & MASK64
    state, inc = expand_seed_to_pcg_state(combined)
    arr = list(range(1, pool_max + 1))
    n = len(arr)
    order = []
    for i in range(n - 1, n - 1 - k, -1):
        state, r = pcg64_next(state, inc)
        j = r % (i + 1)
        arr[i], arr[j] = arr[j], arr[i]
        order.append(arr[i])
    return order
def pcg64_predict(seed, draw_serial, k, pool_max=LOTO6_MAX):
    return sorted(pcg64_predict_raw(seed, draw_serial, k, pool_max))

def modular_cycle_ranked(train_serials, train_main6, target_serial, k):
    target_mod = target_serial % LOTO6_MAX
    freq = Counter()
    for s, d in zip(train_serials, train_main6):
        if s % LOTO6_MAX == target_mod:
            for n in d:
                freq[n] += 1
    if not freq:
        freq = Counter(n for d in train_main6 for n in d)
    return sorted(range(1, LOTO6_MAX + 1), key=lambda x: -freq.get(x, 0))[:k]

# ── Self-checks before trusting either PRNG side ─────────────────────────────
arr_template = list(range(1, LOTO6_MAX + 1))
_KNOWN_XO_2129 = [2,3,4,5,6,7,8,9,11,12,13,14,15,16,17,18,19,20,21,22,24,25,27,28,29,30,31,32,33,34,35,36,38,39,40,41,42,43]
assert xoshiro_predict(SEED_XO, 2129, K, LOTO6_MAX, arr_template) == _KNOWN_XO_2129, "xoshiro self-check FAILED"
_KNOWN_PCG_M5M_1 = [1, 2, 3, 4, 5, 6, 7, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 20, 21, 22, 23, 25, 26, 27, 28, 30, 31, 32, 33, 34, 35, 36, 37, 39, 40, 41, 42, 43]
assert pcg64_predict(-5000000, 1, K) == _KNOWN_PCG_M5M_1, "PCG64 self-check FAILED"
print("Self-checks OK: xoshiro (K=38, draw #2129) and PCG64 (seed -5,000,000, draw #1) both match known-good values.")

# ── Fetch full history ────────────────────────────────────────────────────
if 'DATABASE_URL' not in os.environ:
    with open(ENV_LOCAL, encoding='utf-8') as f:
        env_text = f.read()
    m = re.search(r'DATABASE_URL=(.+)', env_text)
    os.environ['DATABASE_URL'] = m.group(1).strip()
import psycopg2
conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()
cur.execute("SELECT draw_serial, num1,num2,num3,num4,num5,num6, bonus FROM loto6_results ORDER BY draw_serial")
all_rows = cur.fetchall()
conn.close()

all_serials = [r[0] for r in all_rows]
all_main6 = [sorted(r[1:7]) for r in all_rows]
by_serial = {r[0]: {'main6': sorted(r[1:7]), 'bonus': r[7]} for r in all_rows}
assert all_serials == list(range(1, all_serials[-1] + 1)), "gap/offset in draw_serial sequence"
print(f"Fetched {len(all_rows)} historical draws (#{all_serials[0]}-{all_serials[-1]}).")
if all_serials[-1] != TARGET_SERIAL - 1:
    raise SystemExit(f"Expected latest draw #{TARGET_SERIAL-1}, found #{all_serials[-1]} -- stale.")

# ── Current #2134 pool: three components + triple intersection ──────────────
xo_pool_ordered = xoshiro_predict_raw(SEED_XO, TARGET_SERIAL, K, LOTO6_MAX, arr_template)
xo_pool = sorted(xo_pool_ordered)
mc_pool_ordered = modular_cycle_ranked(all_serials, all_main6, TARGET_SERIAL, K)
mc_pool = sorted(mc_pool_ordered)
pcg_pool_ordered = pcg64_predict_raw(SEED_PCG, TARGET_SERIAL, K)
pcg_pool = sorted(pcg_pool_ordered)
current_pool = sorted(set(xo_pool) & set(mc_pool) & set(pcg_pool))
print(f"\n#{TARGET_SERIAL} xoshiro pool ({len(xo_pool)}): {xo_pool}")
print(f"#{TARGET_SERIAL} Modular Cycle pool ({len(mc_pool)}): {mc_pool}")
print(f"#{TARGET_SERIAL} PCG64 pool ({len(pcg_pool)}): {pcg_pool}")
print(f"#{TARGET_SERIAL} triple intersection ({len(current_pool)}): {current_pool}")

# ── Walk-forward backtest, #2033-2133 (101 draws) ────────────────────────────
def hyper_pmf(x, pool, success, draws):
    if x > success or x > draws or (draws - x) > (pool - success) or x < 0 or (draws - x) < 0:
        return 0.0
    return (math.comb(success, x) * math.comb(pool - success, draws - x)) / math.comb(pool, draws)
def prob_all_in(subset_needed, pool_max, pick_k):
    if subset_needed > pick_k:
        return 0.0
    return math.comb(pool_max - subset_needed, pick_k - subset_needed) / math.comb(pool_max, pick_k)

targets = list(range(BACKTEST101_LO, BACKTEST101_HI + 1))
per_draw = []
for T in targets:
    idx = T - 1
    train_serials = all_serials[:idx]
    train_main6 = all_main6[:idx]

    xo_p = set(xoshiro_predict(SEED_XO, T, K, LOTO6_MAX, arr_template))
    mc_p = set(modular_cycle_ranked(train_serials, train_main6, T, K))
    pcg_p = set(pcg64_predict(SEED_PCG, T, K))
    pool = xo_p & mc_p & pcg_p

    d = by_serial[T]
    actual = d['main6']
    bonus = d['bonus']
    actual_set = set(actual)
    h = len(actual_set & pool)
    bonus_hit = bonus in pool
    if h == 6:
        tier = 'hit6b' if bonus_hit else 'hit6'
    elif h == 5:
        tier = 'hit5'
    elif h == 4:
        tier = 'hit4'
    else:
        tier = 'hit0-3'

    per_draw.append({
        's': T, 'pool': sorted(pool), 'main': actual, 'bonus': bonus,
        'mainHits': h, 'bonusHit': bonus_hit, 'tier': tier,
    })

def significance_for_window(rows):
    n = len(rows)
    avg_pool = sum(len(r['pool']) for r in rows) / n
    hit6b = sum(1 for r in rows if r['mainHits'] == 6 and r['bonusHit'])
    hit6 = sum(1 for r in rows if r['mainHits'] == 6)
    hit5 = sum(1 for r in rows if r['mainHits'] == 5)
    hit4 = sum(1 for r in rows if r['mainHits'] == 4)

    def stats_for(observed_count, prob_fn):
        exp_total = sum(prob_fn(len(r['pool'])) for r in rows)
        var_total = sum(prob_fn(len(r['pool'])) * (1 - prob_fn(len(r['pool']))) for r in rows)
        z = (observed_count - exp_total) / math.sqrt(var_total) if var_total > 0 else float('nan')
        chi2 = z * z
        p = 1 - math.erf(math.sqrt(chi2 / 2)) if var_total > 0 else float('nan')
        ratio = observed_count / exp_total if exp_total > 0 else float('nan')
        return dict(observed=observed_count, expected=exp_total, ratio=ratio, z=z, chi2=chi2, p=p)

    s6b = stats_for(hit6b, lambda ps: prob_all_in(7, LOTO6_MAX, ps) if ps >= 7 else 0.0)
    s6 = stats_for(hit6, lambda ps: hyper_pmf(6, LOTO6_MAX, 6, ps))
    s5 = stats_for(hit5, lambda ps: hyper_pmf(5, LOTO6_MAX, 6, ps))
    s4 = stats_for(hit4, lambda ps: hyper_pmf(4, LOTO6_MAX, 6, ps))
    return dict(
        n=n, avgPoolSize=avg_pool,
        minPoolSize=min(len(r['pool']) for r in rows), maxPoolSize=max(len(r['pool']) for r in rows),
        hit6b=hit6b, hit6=hit6, hit5=hit5, hit4=hit4,
        containment=hit6, containmentPct=hit6 / n * 100,
        tiers={'hit6b': s6b, 'hit6': s6, 'hit5': s5, 'hit4': s4},
    )

per_draw_by_serial = {r['s']: r for r in per_draw}
window101 = [per_draw_by_serial[s] for s in range(BACKTEST101_LO, BACKTEST101_HI + 1)]
window50 = [per_draw_by_serial[s] for s in range(BACKTEST50_LO, BACKTEST50_HI + 1)]
summary101 = significance_for_window(window101)
summary50 = significance_for_window(window50)

print(f"\n=== #{BACKTEST101_LO}-{BACKTEST101_HI} ({summary101['n']} draws) ===")
print(f"Avg pool: {summary101['avgPoolSize']:.2f} (range {summary101['minPoolSize']}-{summary101['maxPoolSize']})")
for tier_name, s in summary101['tiers'].items():
    print(f"  {tier_name}: obs={s['observed']} exp={s['expected']:.2f} ratio={s['ratio']:.3f}x z={s['z']:.3f} chi2={s['chi2']:.3f} p={s['p']:.4f}")

print(f"\n=== #{BACKTEST50_LO}-{BACKTEST50_HI} ({summary50['n']} draws) ===")
print(f"Avg pool: {summary50['avgPoolSize']:.2f} (range {summary50['minPoolSize']}-{summary50['maxPoolSize']})")
for tier_name, s in summary50['tiers'].items():
    print(f"  {tier_name}: obs={s['observed']} exp={s['expected']:.2f} ratio={s['ratio']:.3f}x z={s['z']:.3f} chi2={s['chi2']:.3f} p={s['p']:.4f}")

meta = {
    'targetSerial': TARGET_SERIAL,
    'trainedThroughSerial': all_serials[-1],
    'k': K,
    'seedXo': SEED_XO,
    'seedPcg': SEED_PCG,
    'xoPool': xo_pool, 'xoPoolOrdered': xo_pool_ordered,
    'mcPool': mc_pool, 'mcPoolOrdered': mc_pool_ordered,
    'pcgPool': pcg_pool, 'pcgPoolOrdered': pcg_pool_ordered,
    'currentPool': current_pool,
    'backtest101Lo': BACKTEST101_LO, 'backtest101Hi': BACKTEST101_HI,
    'backtest50Lo': BACKTEST50_LO, 'backtest50Hi': BACKTEST50_HI,
    'summary101': summary101,
    'summary50': summary50,
    'historicalDraws': [{'s': s, 'a': d} for s, d in zip(all_serials, all_main6)],
    'perDraw': list(reversed(per_draw)),  # newest-first, matching page default
}
with open(META_OUT, 'w', encoding='utf-8') as f:
    json.dump(meta, f, separators=(',', ':'))
print(f"\nSaved {META_OUT}")
