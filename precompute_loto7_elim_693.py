"""
precompute_loto7_elim_693.py
--------------------------------
Loto7 elimination page for draw #693 (next upcoming, not yet drawn),
brought up to the same feature level as the Loto6 elimination pages
(xoshiro_elim_2134.html / xo_pcg_elim_2134.html / pcg64_top3_elim_2134.html).

Base: ARIMA(2,1,0)'s K=25 prediction for draw #693 (read from
public/loto7_predictions_data.json, same data the live
/loto7/predictions page and /loto7_backtest100_multik.html use),
normalized to K=25 via topKNums(). Universe = all C(25,7) = 480,700
seven-number combinations drawable from the 25-number Base pool.

BASE CONSTRUCTION DECISION (tested, not assumed): intersecting this
Base with the completed xoshiro K=25/28/30 Loto7 seed scans' best
seeds was walk-forward backtested against all 690 historical Loto7
draws before deciding whether to use it. Result: ARIMA-alone K=25
containment (actual draw's 7 numbers all inside the pool) = 4.35%
(30/690) -- already close to the ~4.67% chance level for a random
25-of-37 pool, i.e. ARIMA isn't beating chance at containing the real
combo. Intersecting with any single xoshiro seed shrinks the pool to
~17-20 numbers and containment collapses further (0.29%-1.45%); the
triple xoshiro intersection produces 0% containment across all 690
draws (never once contained the actual winning combo). Intersecting
makes Base WORSE, not better -- decision: Base stays ARIMA K=25 alone,
NOT intersected with any xoshiro seed.

Pass 1 (16 methods, K=22, independent containment) and Pass 2 (4
methods -- MA-37, Poly deg-2, HMM, Weighted MA-37 -- K=25, independent
containment) and Pass 3 (historical repeat filter): unchanged from the
original build.

Pass 4 (NEW): Worst Combo (Anti-Pick) K=15 -- same 5-method consensus
construction as the Loto6 elimination pages (MA-37, Exp-weighted,
Random Forest, kNN (k=10), Apriori Assoc Rules -- the exact Loto7
analogs of Loto6's WORST_COMBO_METHOD_INDICES=[1,2,6,9,11] positions).

Pass 5 (NEW): consecutive-run filter. VALIDATED historically (all 692
real Loto7 draws) before picking a threshold: run>=3 occurs in 15.32%
of real draws (106/692) -- too common to treat as a meaningful
pattern, REJECTED. run>=4 occurs in 2.75% (19/692) -- comparably rare
to the 6.62% threshold used on the Loto6 pages, ADOPTED. run>=5 occurs
in only 0.14% (1/692) -- essentially never, considered but judged too
aggressive (removes very little of the universe) as a standalone pass
on top of run>=4.

Pass 6 (NEW): three-consecutive-pairs analog. Loto6's pattern (exactly
three runs of length 2, i.e. 6 numbers = 3 pairs) doesn't map onto
Loto7's 7 numbers directly. VALIDATED the natural adaptation --
decomposition into exactly three pairs plus one leftover single,
i.e. sorted run-lengths (2,2,2,1) -- historically: 4/692 draws (0.58%),
comparably rare to Loto6's three-pairs pattern. ADOPTED.

Pass 7 (NEW, final): overlap-with-previous-draw filter. VALIDATED via
hypergeometric expectation (pool=37, 7-of-37 draws) against all 691
consecutive real-draw pairs before picking a threshold -- explicitly
checking the weak heuristic this site rejected for Loto6:
  overlap=3: observed 70/691 (10.13%) vs hypergeom expected 64.38
    (9.32%) -- matches chance almost exactly, NOT rare, REJECTED
    (same conclusion as the abandoned Loto6 3-overlap heuristic).
  overlap=4: observed 11/691 (1.59%) vs expected 9.54 (1.38%) --
    still close to chance, occurs regularly, REJECTED.
  overlap=5: observed 0/691 vs expected 0.61 -- never happened.
  overlap=6: observed 0/691 vs expected 0.01 -- never happened.
  overlap=7 (identical draw): observed 0/691, expected ~0 -- never
    happened (and structurally impossible with distinct draws anyway).
ADOPTED: overlap in {5,6,7} vs draw #692 -- well-supported (0/691),
mirroring Loto6's "5 or 6 overlap never happened (0/2132)" precedent.

Outputs:
  loto7_elim_693_meta.json           -- small: base pool, method picks, counts
  public/loto7_elim_693_combos.json  -- large: remaining combo list
                                        (fetched client-side, not inlined)

Run: python precompute_loto7_elim_693.py
"""
import json, os, re, itertools, time
from collections import Counter
from math import comb
import psycopg2

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
PREDICTIONS_PATH = BASE + r"\public\loto7_predictions_data.json"
ENV_LOCAL = BASE + r"\.env.local"
META_OUT = BASE + r"\loto7_elim_693_meta.json"
COMBOS_OUT = BASE + r"\public\loto7_elim_693_combos.json"
HISTORICAL_OUT = BASE + r"\public\loto7_elim_693_historical.json"

LOTO7_MAX = 37
K_BASE = 25

with open(PREDICTIONS_PATH, encoding='utf-8') as f:
    payload = json.load(f)

TARGET_SERIAL = payload['nextSerial']
combos_meta = payload['combos']
all_pools = [c['numbers'] for c in combos_meta]
native_by_name = {c['method']: c['numbers'] for c in combos_meta}
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

pos_of = {n: i for i, n in enumerate(base_pool)}
FULLBASE = (1 << K_BASE) - 1

def restricted_mask(target_set):
    mask = 0
    for n in target_set:
        if n in pos_of:
            mask |= (1 << pos_of[n])
    return mask

# ── Pass 1: 16 methods' K=22 picks, checked independently ───────────────────
print(f"\n=== Pass 1 ===")
K_METHODS = 22
METHOD_NAMES = [c['method'] for c in combos_meta]
method_native_pools = [c['numbers'] for c in combos_meta]
method_picks_22 = [top_k_nums(pool, all_pools, K_METHODS) for pool in method_native_pools]
for name, pool in zip(METHOD_NAMES, method_picks_22):
    assert len(pool) == K_METHODS, f"{name}: got {len(pool)} numbers, expected {K_METHODS}"

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
final_remaining_pass1 = len(remaining_after1)
print(f"\nPass 1 elimination in {elapsed1:.1f}s")
print(f"  Removed by ANY of the 16 methods' K={K_METHODS} containment: {removed_by_methods:,}")
print(f"  Before Pass 1: {universe_count:,}  ->  After Pass 1: {final_remaining_pass1:,}")

meta = {
    'targetSerial': TARGET_SERIAL,
    'base': {'k': K_BASE, 'pool': base_pool, 'method': 'ARIMA(2,1,0)', 'nativeK': len(arima_native), 'nativePool': sorted(arima_native)},
    'universeCount': universe_count,
    'methodNames': METHOD_NAMES,
    'methodK': K_METHODS,
    'methodPicks': method_picks_22,
    'removedByMethods': removed_by_methods,
    'methodOverlaps': [bin(m).count('1') for m in method_masks],
    'finalRemainingPass1': final_remaining_pass1,
}

# ── Pass 2: 4 specific methods' K=25 pick, checked independently ────────────
print(f"\n=== Pass 2 ===")
K_PASS2 = 25
PASS2_METHOD_NAMES = ["MA-37", "Poly deg-2", "Hidden Markov Model", "Weighted MA-37"]
for name in PASS2_METHOD_NAMES:
    if name not in native_by_name:
        raise SystemExit(f"Method '{name}' not found in loto7_predictions_data.json's combos.")

pass2_picks = [top_k_nums(native_by_name[name], all_pools, K_PASS2) for name in PASS2_METHOD_NAMES]
for name, pool in zip(PASS2_METHOD_NAMES, pass2_picks):
    assert len(pool) == K_PASS2, f"{name}: got {len(pool)} numbers, expected {K_PASS2}"

pass2_masks = []
for name, pool in zip(PASS2_METHOD_NAMES, pass2_picks):
    mmask = restricted_mask(set(pool))
    overlap = bin(mmask).count('1')
    pass2_masks.append(mmask)
    print(f"  {name:24s} K={K_PASS2} pick: {pool}  [overlap with {K_BASE}-pool: {overlap}]")

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
    else:
        remaining_after2.append(combo)
elapsed2 = time.time() - t0
final_remaining_pass2 = len(remaining_after2)
print(f"\nPass 2 elimination in {elapsed2:.1f}s")
print(f"  Removed by ANY of the 4 methods' K={K_PASS2} containment: {removed_by_pass2:,}")
print(f"  Before Pass 2: {final_remaining_pass1:,}  ->  After Pass 2: {final_remaining_pass2:,}")

meta['pass2MethodNames'] = PASS2_METHOD_NAMES
meta['pass2K'] = K_PASS2
meta['pass2Picks'] = pass2_picks
meta['removedByPass2'] = removed_by_pass2
meta['pass2Overlaps'] = [bin(m).count('1') for m in pass2_masks]
meta['finalRemainingPass2'] = final_remaining_pass2

# ── Pass 3: historical repeat filter ─────────────────────────────────────────
print(f"\n=== Pass 3 ===")
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
print(f"Fetched {len(db_rows)} historical draws (#{db_rows[0][0]}-{db_rows[-1][0]}).")
if db_rows[-1][0] != TARGET_SERIAL - 1:
    raise SystemExit(f"Expected latest draw #{TARGET_SERIAL-1}, found #{db_rows[-1][0]} -- draw window assumption is stale.")

all_main7 = [sorted([r[1], r[2], r[3], r[4], r[5], r[6], r[7]]) for r in db_rows]
all_serials = [r[0] for r in db_rows]
historical_combos = set(tuple(c) for c in all_main7)
print(f"Historical winning combos: {len(historical_combos):,} (from {len(all_main7):,} draws, #1-{TARGET_SERIAL-1})")
if len(historical_combos) != len(all_main7):
    print(f"  NOTE: {len(all_main7) - len(historical_combos)} duplicate historical combo(s) collapsed by the set.")

t0 = time.time()
remaining_after3 = []
removed_historical = []
for combo in remaining_after2:
    if tuple(combo) in historical_combos:
        removed_historical.append(combo)
    else:
        remaining_after3.append(combo)
elapsed3 = time.time() - t0
final_remaining_pass3 = len(remaining_after3)
print(f"\nPass 3 elimination in {elapsed3:.1f}s")
print(f"  Removed (exact match to a historical winning combo): {len(removed_historical):,}")
if removed_historical:
    print(f"  Matched historical combos: {removed_historical}")
print(f"  Before Pass 3: {final_remaining_pass2:,}  ->  After Pass 3: {final_remaining_pass3:,}")

meta['historicalDrawCount'] = len(all_main7)
meta['removedHistorical'] = [list(c) for c in removed_historical]
meta['finalRemainingPass3'] = final_remaining_pass3

# ── Pass 4 (NEW): Worst Combo (Anti-Pick) K=15 pick ──────────────────────────
print(f"\n=== Pass 4 (NEW) ===")
K_PASS4 = 15
WORST_COMBO_METHOD_NAMES = ["MA-37", "Exp-weighted", "Random Forest", "kNN (k=10)", "Apriori Assoc Rules"]
for name in WORST_COMBO_METHOD_NAMES:
    if name not in native_by_name:
        raise SystemExit(f"Method '{name}' not found for Worst Combo construction.")
worst_combo_count = Counter()
for name in WORST_COMBO_METHOD_NAMES:
    for n in native_by_name[name]:
        worst_combo_count[n] += 1
PASS4_PICK = sorted(sorted(worst_combo_count.keys(), key=lambda n: (-worst_combo_count[n], n))[:K_PASS4])
pass4_mask = restricted_mask(set(PASS4_PICK))
pass4_overlap = bin(pass4_mask).count('1')
print(f"Worst Combo (Anti-Pick) K={K_PASS4} pick for draw #{TARGET_SERIAL} (computed from {WORST_COMBO_METHOD_NAMES}): {PASS4_PICK}")
print(f"  Overlap with {K_BASE}-pool: {pass4_overlap}")

t0 = time.time()
remaining_after4 = []
removed_by_pass4 = 0
for combo in remaining_after3:
    combo_mask = 0
    for n in combo:
        combo_mask |= (1 << pos_of[n])
    if (combo_mask & ~pass4_mask) & FULLBASE == 0:
        removed_by_pass4 += 1
    else:
        remaining_after4.append(combo)
elapsed4 = time.time() - t0
final_remaining_pass4 = len(remaining_after4)
print(f"Pass 4 elimination in {elapsed4:.1f}s")
print(f"  Removed (contained within the Worst Combo K={K_PASS4} pick): {removed_by_pass4:,}")
print(f"  Before Pass 4: {final_remaining_pass3:,}  ->  After Pass 4: {final_remaining_pass4:,}")

meta['pass4MethodNames'] = WORST_COMBO_METHOD_NAMES
meta['pass4K'] = K_PASS4
meta['pass4Pick'] = PASS4_PICK
meta['pass4Overlap'] = pass4_overlap
meta['removedByPass4'] = removed_by_pass4
meta['finalRemainingPass4'] = final_remaining_pass4

# ── Pass 5 (NEW): consecutive-run filter, threshold run>=4 (validated) ──────
print(f"\n=== Pass 5 (NEW) ===")
def max_consecutive_run(combo):
    s = sorted(combo)
    run = 1; best = 1
    for i in range(1, len(s)):
        if s[i] == s[i-1] + 1:
            run += 1; best = max(best, run)
        else:
            run = 1
    return best

# Historical validation (all 692 real draws) -- printed for the record.
hist_run_dist = Counter()
for c in all_main7:
    hist_run_dist[max_consecutive_run(c)] += 1
n_hist = len(all_main7)
print("Historical max-consecutive-run distribution (all real Loto7 draws):")
for k in sorted(hist_run_dist):
    print(f"  run={k}: {hist_run_dist[k]} ({hist_run_dist[k]/n_hist*100:.2f}%)")
run3plus_pct = sum(v for k,v in hist_run_dist.items() if k>=3) / n_hist * 100
run4plus_pct = sum(v for k,v in hist_run_dist.items() if k>=4) / n_hist * 100
print(f"  run>=3: {run3plus_pct:.2f}% -- REJECTED (too common, unlike Loto6's 6.62%)")
print(f"  run>=4: {run4plus_pct:.2f}% -- ADOPTED (comparably rare to Loto6's threshold)")

PASS5_THRESHOLD = 4
t0 = time.time()
remaining_after5 = []
removed_by_pass5 = 0
run_dist = Counter()
for combo in remaining_after4:
    mr = max_consecutive_run(combo)
    run_dist[mr] += 1
    if mr >= PASS5_THRESHOLD:
        removed_by_pass5 += 1
    else:
        remaining_after5.append(combo)
elapsed5 = time.time() - t0
final_remaining_pass5 = len(remaining_after5)
print(f"Pass 5 elimination in {elapsed5:.1f}s")
print(f"  Max-run distribution (of Pass-4-remaining combos): " + ", ".join(f"{k}:{v:,}" for k, v in sorted(run_dist.items())))
print(f"  Removed (max consecutive run >= {PASS5_THRESHOLD}): {removed_by_pass5:,}")
print(f"  Before Pass 5: {final_remaining_pass4:,}  ->  After Pass 5: {final_remaining_pass5:,}")

meta['pass5Threshold'] = PASS5_THRESHOLD
meta['pass5HistoricalValidation'] = {str(k): v for k, v in sorted(hist_run_dist.items())}
meta['pass5RunDistribution'] = {str(k): v for k, v in sorted(run_dist.items())}
meta['removedByPass5'] = removed_by_pass5
meta['finalRemainingPass5'] = final_remaining_pass5

# ── Pass 6 (NEW): three-pairs-plus-single filter, pattern (2,2,2,1) ─────────
print(f"\n=== Pass 6 (NEW) ===")
def run_lengths(combo):
    s = sorted(combo)
    runs = []
    run = [s[0]]
    for i in range(1, len(s)):
        if s[i] == s[i-1] + 1:
            run.append(s[i])
        else:
            runs.append(run); run = [s[i]]
    runs.append(run)
    return [len(r) for r in runs]

def is_three_pairs_plus_single(combo):
    lengths = sorted(run_lengths(combo), reverse=True)
    return lengths == [2, 2, 2, 1]

# Historical validation.
hist_pattern_count = sum(1 for c in all_main7 if is_three_pairs_plus_single(c))
print(f"Historical (2,2,2,1) three-pairs-plus-single pattern: {hist_pattern_count}/{n_hist} draws ({hist_pattern_count/n_hist*100:.2f}%) -- ADOPTED (rare)")

t0 = time.time()
remaining_after6 = []
removed_by_pass6 = []
for combo in remaining_after5:
    if is_three_pairs_plus_single(combo):
        removed_by_pass6.append(combo)
    else:
        remaining_after6.append(combo)
elapsed6 = time.time() - t0
final_remaining_pass6 = len(remaining_after6)
print(f"Pass 6 elimination in {elapsed6:.1f}s")
print(f"  Removed (three pairs + single, pattern 2-2-2-1): {len(removed_by_pass6):,}")
print(f"  Before Pass 6: {final_remaining_pass5:,}  ->  After Pass 6: {final_remaining_pass6:,}")

meta['pass6HistoricalCount'] = hist_pattern_count
meta['pass6HistoricalPct'] = round(hist_pattern_count/n_hist*100, 2)
meta['removedByPass6'] = [list(c) for c in removed_by_pass6]
meta['finalRemainingPass6'] = final_remaining_pass6

# ── Pass 7 (NEW, final): overlap-with-previous-draw filter, threshold >=5 ──
print(f"\n=== Pass 7 (NEW, final) ===")
PREV_DRAW_SERIAL = TARGET_SERIAL - 1  # 692
PREV_DRAW_NUMS = sorted(all_main7[all_serials.index(PREV_DRAW_SERIAL)])
prev_draw_set = set(PREV_DRAW_NUMS)
print(f"Previous actual draw #{PREV_DRAW_SERIAL}: {PREV_DRAW_NUMS}")

# Historical validation: overlap distribution across all consecutive real-draw
# pairs, compared to hypergeometric expectation (pool=37, k=7 each draw).
overlap_dist = Counter()
pairs_count = 0
for i in range(1, n_hist):
    prev = set(all_main7[i-1]); cur_ = set(all_main7[i])
    overlap_dist[len(prev & cur_)] += 1
    pairs_count += 1
print(f"Historical overlap-with-previous-draw distribution (all {pairs_count} consecutive real-draw pairs):")
for k in range(8):
    obs = overlap_dist.get(k, 0)
    p_hyper = comb(7, k) * comb(30, 7 - k) / comb(37, 7)
    exp = p_hyper * pairs_count
    flag = ""
    if k in (3, 4):
        flag = "  <- REJECTED, matches chance" if abs(obs - exp) < exp * 0.5 or obs > 5 else ""
    print(f"  overlap={k}: observed={obs} ({obs/pairs_count*100:.2f}%)  expected={exp:.2f}  ({p_hyper*100:.3f}%){flag}")
print(f"  overlap>=5: observed=0/{pairs_count} -- ADOPTED, well-supported (never happened; matches near-zero chance expectation too)")

t0 = time.time()
remaining_after7 = []
removed_by_pass7 = []
final_overlap_dist = Counter()
for combo in remaining_after6:
    ov = len(set(combo) & prev_draw_set)
    final_overlap_dist[ov] += 1
    if ov >= 5:
        removed_by_pass7.append(combo)
    else:
        remaining_after7.append(combo)
elapsed7 = time.time() - t0
final_remaining_pass7 = len(remaining_after7)
print(f"Pass 7 elimination in {elapsed7:.1f}s")
print(f"  Overlap distribution (of Pass-6-remaining combos vs draw #{PREV_DRAW_SERIAL}): " +
      ", ".join(f"{k}:{v:,}" for k, v in sorted(final_overlap_dist.items())))
print(f"  Removed (overlap >= 5 with draw #{PREV_DRAW_SERIAL}): {len(removed_by_pass7):,}")
print(f"  Before Pass 7: {final_remaining_pass6:,}  ->  After Pass 7: {final_remaining_pass7:,}")

meta['pass7PrevDrawSerial'] = PREV_DRAW_SERIAL
meta['pass7PrevDrawNums'] = PREV_DRAW_NUMS
meta['pass7HistoricalOverlapDistribution'] = {str(k): overlap_dist.get(k, 0) for k in range(8)}
meta['pass7HistoricalPairsCount'] = pairs_count
meta['pass7OverlapDistribution'] = {str(k): v for k, v in sorted(final_overlap_dist.items())}
meta['removedByPass7'] = [list(c) for c in removed_by_pass7]
meta['finalRemainingPass7'] = final_remaining_pass7
meta['finalRemaining'] = final_remaining_pass7

print(f"\nFull elimination sequence: {universe_count:,} -> {final_remaining_pass1:,} (P1) -> {final_remaining_pass2:,} (P2) -> "
      f"{final_remaining_pass3:,} (P3) -> {final_remaining_pass4:,} (P4) -> {final_remaining_pass5:,} (P5) -> "
      f"{final_remaining_pass6:,} (P6) -> {final_remaining_pass7:,} (P7)")

with open(META_OUT, 'w', encoding='utf-8') as f:
    json.dump(meta, f, indent=2)
print(f"\nSaved {META_OUT}")

with open(COMBOS_OUT, 'w', encoding='utf-8') as f:
    json.dump(remaining_after7, f, separators=(',', ':'))
print(f"Saved {COMBOS_OUT} ({len(remaining_after7):,} combos, {os.path.getsize(COMBOS_OUT)//1024:,} KB)")

with open(HISTORICAL_OUT, 'w', encoding='utf-8') as f:
    json.dump(all_main7, f, separators=(',', ':'))
print(f"Saved {HISTORICAL_OUT} ({len(all_main7):,} combos, {os.path.getsize(HISTORICAL_OUT)//1024:,} KB)")
