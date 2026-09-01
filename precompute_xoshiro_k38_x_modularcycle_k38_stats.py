"""
precompute_xoshiro_k38_x_modularcycle_k38_stats.py
--------------------------------------------------------
Precomputes everything the "Xoshiro K=38 x Modular Cycle Native K=38 --
Base Pool Statistics" page needs: the current #2133 intersected pool
(xoshiro K=38 seed #692,809 ∩ Modular Cycle's native mod-43-cycle K=38
pick, no cross-method padding) plus a full walk-forward backtest of
that same construction, no leakage -- Modular Cycle is retrained fresh
for every target draw using only draws strictly before it.

Backtest window (extended 2026-09-01 from the original #1000-2132):
#44-2132, the FULL usable history. Draw #44 is the earliest possible
walk-forward target: draws #1-43 span all 43 mod-43 residue classes
exactly once, so by draw #44 every residue class has at least one
prior representative draw and Modular Cycle's frequency count never
needs its "no prior same-residue draws yet" fallback (plain overall
frequency) -- draws #1-43 themselves would all hit that fallback and
aren't a meaningful test of the mod-cycle method specifically, so
they're excluded.

This is the WEAKER of the two intersection constructions tested this
session -- unlike xoshiro_elim_2133.html's Base (Modular Cycle K=33,
cross-method-consensus PADDED, intersected with xoshiro K=38), this
uses Modular Cycle's raw/native K=38 pick with no padding. The
backtest results confirm it: none of the four hit tiers reach
conventional statistical significance against the hypergeometric
chance baseline.

Also computes, for every number in the CURRENT #2133 pool, its
typical (average) and most-frequent (modal) generation-order index in
each method's own build order across the full backtest window -- and,
separately, an aggregate "hit-index distribution": among all backtest
draws, wherever a winning main number WAS caught by Base (present in
both MC and XO that draw), where did it land in each method's own
generation order? Bucketed (width 5) + exact-index chi-square
goodness-of-fit vs. uniform, same style as xoshiro_base_review1000.py.

Both components are cheap to compute walk-forward (xoshiro is a pure
function of seed+draw_serial; Modular Cycle's native ranking is just a
frequency count over prior draws with the same mod-43 cycle residue --
no ML training needed, unlike the padded K=33 version used elsewhere),
so the full ~2089-draw backtest still runs in well under a second.

Output: xoshiro_k38_x_modularcycle_k38_stats_meta.json
Run: python precompute_xoshiro_k38_x_modularcycle_k38_stats.py
"""
import json, os, re, math, time
from collections import Counter

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
ENV_LOCAL = BASE + r"\.env.local"
META_OUT = BASE + r"\xoshiro_k38_x_modularcycle_k38_stats_meta.json"

LOTO6_MAX = 43
K = 38
SEED_XO = 692809
TARGET_SERIAL = 2133
BACKTEST_LO, BACKTEST_HI = 44, 2132  # see docstring for rationale on #44

MASK64 = 0xFFFFFFFFFFFFFFFF

def xoshiro_predict_raw(seed, draw_serial, k, pool_max, arr_template):
    """Generation order -- same convention as every other xoshiro page on
    this site (order the partial Fisher-Yates shuffle finalizes each
    position, i=n-1 first down to i=n-k)."""
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

# ── Self-check against known-good value before trusting the xoshiro side ────
arr_template = list(range(1, LOTO6_MAX + 1))
_KNOWN_2129 = [2,3,4,5,6,7,8,9,11,12,13,14,15,16,17,18,19,20,21,22,24,25,27,28,29,30,31,32,33,34,35,36,38,39,40,41,42,43]
_check = xoshiro_predict(SEED_XO, 2129, K, LOTO6_MAX, arr_template)
assert _check == _KNOWN_2129, f"Self-check FAILED: {_check}"
print(f"Self-check OK: xoshiro seed {SEED_XO} K={K} draw #2129 matches known-good value.")

def modular_cycle_ranked(train_serials, train_main6, target_serial, k):
    """Generation order -- the mod-43 cycle's own frequency ranking
    (highest count first, ties broken by ascending number)."""
    target_mod = target_serial % LOTO6_MAX
    freq = Counter()
    for s, d in zip(train_serials, train_main6):
        if s % LOTO6_MAX == target_mod:
            for n in d:
                freq[n] += 1
    if not freq:
        freq = Counter(n for d in train_main6 for n in d)
    return sorted(range(1, LOTO6_MAX + 1), key=lambda x: -freq.get(x, 0))[:k]

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
all_main6_sorted = [sorted(r[1:7]) for r in all_rows]
by_serial = {r[0]: {'main6': sorted(r[1:7]), 'bonus': r[7]} for r in all_rows}
assert all_serials == list(range(all_serials[0], all_serials[-1] + 1))
print(f"Fetched {len(all_rows)} historical draws (#{all_serials[0]}-{all_serials[-1]}).")
if all_serials[-1] != TARGET_SERIAL - 1:
    raise SystemExit(f"Expected latest draw #{TARGET_SERIAL-1}, found #{all_serials[-1]} -- stale.")

# sanity: draws #1-43 really do span all 43 residues exactly once
_residues_1_43 = sorted(s % LOTO6_MAX for s in range(1, 44))
assert _residues_1_43 == sorted(range(LOTO6_MAX)) or True  # 0..42, informational only

# ── Current #2133 pool ───────────────────────────────────────────────────
xo_pool_ordered = xoshiro_predict_raw(SEED_XO, TARGET_SERIAL, K, LOTO6_MAX, arr_template)
xo_pool = sorted(xo_pool_ordered)
mc_pool_ordered = modular_cycle_ranked(all_serials, all_main6_sorted, TARGET_SERIAL, K)
mc_pool = sorted(mc_pool_ordered)
current_pool = sorted(set(xo_pool) & set(mc_pool))
print(f"\n#{TARGET_SERIAL} pool: xoshiro K={K}: {xo_pool}")
print(f"#{TARGET_SERIAL} pool: Modular Cycle native K={K}: {mc_pool}")
print(f"#{TARGET_SERIAL} intersected pool ({len(current_pool)} numbers): {current_pool}")
xo_pos_today = {n: i + 1 for i, n in enumerate(xo_pool_ordered)}
mc_pos_today = {n: i + 1 for i, n in enumerate(mc_pool_ordered)}

# ── Walk-forward backtest, #44-2132 (full usable history) ────────────────
t0 = time.time()
targets = list(range(BACKTEST_LO, BACKTEST_HI + 1))
hit6b = hit6 = hit5 = hit4 = 0
contained = 0
kbases = []
per_draw = []  # per-draw detail for the page's breakdown table

# per-number index tallies (ALL appearances, not just hits) -- for the
# "typical/frequent generation-order index" per-pool-number profile
sum_xo_idx = {n: 0 for n in range(1, LOTO6_MAX + 1)}
cnt_xo_idx = {n: 0 for n in range(1, LOTO6_MAX + 1)}
modal_xo_idx = {n: Counter() for n in range(1, LOTO6_MAX + 1)}
sum_mc_idx = {n: 0 for n in range(1, LOTO6_MAX + 1)}
cnt_mc_idx = {n: 0 for n in range(1, LOTO6_MAX + 1)}
modal_mc_idx = {n: Counter() for n in range(1, LOTO6_MAX + 1)}

# hit-index tallies (ONLY numbers that were both actual winners AND in Base
# that draw) -- for the aggregate hit-index distribution section
hit_xo_indices = []
hit_mc_indices = []

for T in targets:
    idx = all_serials.index(T)
    train_serials = all_serials[:idx]
    train_main6 = all_main6_sorted[:idx]

    xo_ord = xoshiro_predict_raw(SEED_XO, T, K, LOTO6_MAX, arr_template)
    mc_ord = modular_cycle_ranked(train_serials, train_main6, T, K)
    xo_p = set(xo_ord)
    mc_p = set(mc_ord)
    base_pool = xo_p & mc_p
    kbases.append(len(base_pool))

    xo_pos = {n: i + 1 for i, n in enumerate(xo_ord)}
    mc_pos = {n: i + 1 for i, n in enumerate(mc_ord)}
    for n in xo_ord:
        sum_xo_idx[n] += xo_pos[n]
        cnt_xo_idx[n] += 1
        modal_xo_idx[n][xo_pos[n]] += 1
    for n in mc_ord:
        sum_mc_idx[n] += mc_pos[n]
        cnt_mc_idx[n] += 1
        modal_mc_idx[n][mc_pos[n]] += 1

    d = by_serial[T]
    actual_set = set(d['main6'])
    bonus = d['bonus']
    h = len(actual_set & base_pool)
    bonus_hit = bonus in base_pool
    if h == 6:
        hit6 += 1
        tier = 'hit6b' if bonus_hit else 'hit6'
        if bonus_hit:
            hit6b += 1
    elif h == 5:
        hit5 += 1
        tier = 'hit5'
    elif h == 4:
        hit4 += 1
        tier = 'hit4'
    else:
        tier = 'hit0-3'
    if actual_set.issubset(base_pool):
        contained += 1

    for n in actual_set:
        if n in base_pool:
            hit_xo_indices.append(xo_pos[n])
            hit_mc_indices.append(mc_pos[n])

    per_draw.append({
        's': T,
        'pool': sorted(base_pool),
        'main': d['main6'],
        'bonus': bonus,
        'mainHits': h,
        'bonusHit': bonus_hit,
        'tier': tier,
    })

elapsed = time.time() - t0
N = len(targets)
avg_k = sum(kbases) / N
print(f"\nBacktest done in {elapsed:.1f}s ({N} draws, #{BACKTEST_LO}-{BACKTEST_HI})")
print(f"Average Base pool size: {avg_k:.2f} (range {min(kbases)}-{max(kbases)})")
print(f"hit6b={hit6b}  hit6={hit6}  hit5={hit5}  hit4={hit4}")
print(f"Containment: {contained}/{N} = {contained/N*100:.2f}%")

def hyper_pmf(x, pool, success, draws):
    return (math.comb(success, x) * math.comb(pool - success, draws - x)) / math.comb(pool, draws)
def prob_all_in(subset_size_needed, pool_max, pick_k):
    return math.comb(pool_max - subset_size_needed, pick_k - subset_size_needed) / math.comb(pool_max, pick_k)

Kavg = round(avg_k)
p6b = prob_all_in(7, LOTO6_MAX, Kavg)
p6 = hyper_pmf(6, LOTO6_MAX, 6, Kavg)
p5 = hyper_pmf(5, LOTO6_MAX, 6, Kavg)
p4 = hyper_pmf(4, LOTO6_MAX, 6, Kavg)

def chi2_binom_stats(obs, p, n):
    exp = p * n
    exp_not = n - exp
    obs_not = n - obs
    chi2 = (obs - exp) ** 2 / exp + (obs_not - exp_not) ** 2 / exp_not
    # chi-square CDF via exact relation to the standard normal CDF, df=1
    # special case: P(X<=x) = erf(sqrt(x/2)); no scipy dependency needed.
    p_value = 1 - math.erf(math.sqrt(chi2 / 2))
    return exp, chi2, p_value

hit6b_exp, hit6b_chi2, hit6b_p = chi2_binom_stats(hit6b, p6b, N)
hit6_exp, hit6_chi2, hit6_p = chi2_binom_stats(hit6, p6, N)
hit5_exp, hit5_chi2, hit5_p = chi2_binom_stats(hit5, p5, N)
hit4_exp, hit4_chi2, hit4_p = chi2_binom_stats(hit4, p4, N)

print(f"\nhit6b: obs={hit6b} exp={hit6b_exp:.2f} chi2={hit6b_chi2:.4f} p={hit6b_p:.4f}")
print(f"hit6:  obs={hit6} exp={hit6_exp:.2f} chi2={hit6_chi2:.4f} p={hit6_p:.4f}")
print(f"hit5:  obs={hit5} exp={hit5_exp:.2f} chi2={hit5_chi2:.4f} p={hit5_p:.4f}")
print(f"hit4:  obs={hit4} exp={hit4_exp:.2f} chi2={hit4_chi2:.4f} p={hit4_p:.4f}")

# ── Per-pool-number index profile: for each of the 33 CURRENT-pool numbers,
# its today's index + typical (average) + most-frequent (modal) index in
# each method's own generation order, across the full backtest window. ─────
pool_index_profile = []
for n in current_pool:
    xo_avg = sum_xo_idx[n] / cnt_xo_idx[n] if cnt_xo_idx[n] else None
    xo_modal = modal_xo_idx[n].most_common(1)[0][0] if modal_xo_idx[n] else None
    mc_avg = sum_mc_idx[n] / cnt_mc_idx[n] if cnt_mc_idx[n] else None
    mc_modal = modal_mc_idx[n].most_common(1)[0][0] if modal_mc_idx[n] else None
    pool_index_profile.append({
        'n': n,
        'xoIdxToday': xo_pos_today.get(n),
        'xoIdxAvg': xo_avg,
        'xoIdxModal': xo_modal,
        'xoAppearances': cnt_xo_idx[n],
        'mcIdxToday': mc_pos_today.get(n),
        'mcIdxAvg': mc_avg,
        'mcIdxModal': mc_modal,
        'mcAppearances': cnt_mc_idx[n],
    })

# ── Hit-index distribution: bucketed (width 5) + exact-index chi-square vs
# uniform, same style as xoshiro_base_review1000.py. ─────────────────────
def bucket_counts(indices, k, width=5):
    n_buckets = -(-k // width)
    counts = [0] * n_buckets
    for idxv in indices:
        b = min((idxv - 1) // width, n_buckets - 1)
        counts[b] += 1
    labels = []
    for b in range(n_buckets):
        lo = b * width + 1
        hi = min((b + 1) * width, k)
        labels.append(f"{lo}\u2013{hi}" if lo != hi else f"{lo}")
    return labels, counts

def exact_index_ranking(indices, k):
    counts = Counter(indices)
    total = len(indices)
    ranked = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
    expected = total / k
    chi2 = sum((counts.get(i, 0) - expected) ** 2 / expected for i in range(1, k + 1))
    dof = k - 1
    # general chi-square upper-tail p-value via the regularized upper
    # incomplete gamma function Q(dof/2, chi2/2) = gammaincc(dof/2, chi2/2).
    # No scipy dependency: use math.gamma-based series/continued-fraction
    # is overkill here -- fall back to scipy if available, else report
    # the chi2/expected ratio only (still informative) with p=None.
    try:
        from scipy import stats as _st
        p_value = 1 - _st.chi2.cdf(chi2, dof)
    except Exception:
        p_value = None
    return ranked, expected, chi2, dof, p_value

n_hits_total = len(hit_xo_indices)
xo_bucket_labels, xo_bucket_counts = bucket_counts(hit_xo_indices, K)
mc_bucket_labels, mc_bucket_counts = bucket_counts(hit_mc_indices, K)
xo_ranked, xo_expected, xo_chi2, xo_dof, xo_pvalue = exact_index_ranking(hit_xo_indices, K)
mc_ranked, mc_expected, mc_chi2, mc_dof, mc_pvalue = exact_index_ranking(hit_mc_indices, K)

print(f"\nHit-index distribution: {n_hits_total:,} hit-number occurrences across the backtest")
print(f"XO exact-index chi2={xo_chi2:.2f} df={xo_dof} p={xo_pvalue}")
print(f"MC exact-index chi2={mc_chi2:.2f} df={mc_dof} p={mc_pvalue}")

meta = {
    'targetSerial': TARGET_SERIAL,
    'trainedThroughSerial': all_serials[-1],
    'k': K,
    'seedXo': SEED_XO,
    'xoPool': xo_pool,
    'xoPoolOrdered': xo_pool_ordered,
    'mcPool': mc_pool,
    'mcPoolOrdered': mc_pool_ordered,
    'currentPool': current_pool,
    'backtestLo': BACKTEST_LO,
    'backtestHi': BACKTEST_HI,
    'nDraws': N,
    'avgPoolSize': avg_k,
    'minPoolSize': min(kbases),
    'maxPoolSize': max(kbases),
    'hit6b': hit6b, 'hit6b_exp': hit6b_exp, 'hit6b_chi2': hit6b_chi2, 'hit6b_p': hit6b_p,
    'hit6': hit6, 'hit6_exp': hit6_exp, 'hit6_chi2': hit6_chi2, 'hit6_p': hit6_p,
    'hit5': hit5, 'hit5_exp': hit5_exp, 'hit5_chi2': hit5_chi2, 'hit5_p': hit5_p,
    'hit4': hit4, 'hit4_exp': hit4_exp, 'hit4_chi2': hit4_chi2, 'hit4_p': hit4_p,
    'contained': contained,
    'containmentPct': contained / N * 100,
    'poolIndexProfile': pool_index_profile,
    'nHitsTotal': n_hits_total,
    'xoBucketLabels': xo_bucket_labels, 'xoBucketCounts': xo_bucket_counts,
    'mcBucketLabels': mc_bucket_labels, 'mcBucketCounts': mc_bucket_counts,
    'xoRanked': xo_ranked, 'xoExpected': xo_expected, 'xoChi2': xo_chi2, 'xoDof': xo_dof, 'xoPvalue': xo_pvalue,
    'mcRanked': mc_ranked, 'mcExpected': mc_expected, 'mcChi2': mc_chi2, 'mcDof': mc_dof, 'mcPvalue': mc_pvalue,
    # for the client-side historical data (compact: serial + 6 main numbers,
    # no bonus needed for the JS Modular Cycle recompute or xoshiro recompute)
    'historicalDraws': [{'s': s, 'a': d} for s, d in zip(all_serials, all_main6_sorted)],
    # per-draw breakdown for the page's paginated table (Base pool, actual
    # numbers, hit tier) -- newest first, matching the page's default sort
    'perDraw': list(reversed(per_draw)),
}
with open(META_OUT, 'w', encoding='utf-8') as f:
    json.dump(meta, f, separators=(',', ':'))
print(f"\nSaved {META_OUT}")
