"""
add_hotcold_xoshiro_elim_2134.py
-----------------------------------
Adds a "hotCold" block to the existing xoshiro_elim_2134_meta.json
(does NOT touch any other key, does NOT re-run the heavy combo
elimination -- that stays exactly as precompute_xoshiro_elim_2134.py
left it). Computes hot/cold number status from full history through
#2133, walk-forward, no leakage from #2134:

  - hot: top N numbers by total appearance count (all-time frequency)
  - cold: bottom N numbers by total appearance count
  - coldAppear: numbers in the below-median ("cold half") frequency
    group that appeared within the last RECENT_WINDOW draws -- a
    "cold number breaking its drought" signal
  - hotOverdue: numbers in the above-median ("hot half") frequency
    group whose current gap since last appearance exceeds their own
    historical average gap (totalDraws / freq) -- i.e. currently
    running longer than their own typical interval

Cross-referenced against Base (the #2134 elimination pool) via
inBase. Every number's freq/lastSeenSerial/gap is included (not just
the four highlighted lists) so the page can render a full 1-43 table
and so the browser can independently recompute everything from the
SAME embedded historical combo list already used for Pass 3 (no new
data need be embedded -- draw_serial for HISTORICAL_COMBOS[i] is
i+1, since the DB has no gaps -- verified below before relying on it).

Run: python add_hotcold_xoshiro_elim_2134.py
"""
import json, os, re

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
ENV_LOCAL = BASE + r"\.env.local"
META_PATH = BASE + r"\xoshiro_elim_2134_meta.json"

LOTO6_MAX = 43
TARGET_SERIAL = 2134
TRAINED_THROUGH = 2133
HOT_N = 10
COLD_N = 10
RECENT_WINDOW = 5   # "just appeared" = within the last 5 draws (#2129-2133)

with open(META_PATH, encoding='utf-8') as f:
    meta = json.load(f)

assert meta['targetSerial'] == TARGET_SERIAL
assert meta['trainedThroughSerial'] == TRAINED_THROUGH
base_pool = set(meta['base']['pool'])

# ── Reuse historicalCombos already in meta.json (same list embedded
# client-side for Pass 3) instead of re-querying the DB -- but first
# independently verify against the DB that draw_serial for entry i is
# exactly i+1 (no gaps), since the JS side will rely on that to avoid
# embedding a second, redundant serial array. ────────────────────────
import psycopg2
if 'DATABASE_URL' not in os.environ:
    with open(ENV_LOCAL, encoding='utf-8') as f:
        env_text = f.read()
    m = re.search(r'DATABASE_URL=(.+)', env_text)
    os.environ['DATABASE_URL'] = m.group(1).strip()
conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()
cur.execute("SELECT draw_serial, num1,num2,num3,num4,num5,num6 FROM loto6_results ORDER BY draw_serial")
db_rows = cur.fetchall()
conn.close()

db_serials = [r[0] for r in db_rows]
db_main6 = [sorted(r[1:7]) for r in db_rows]
assert db_serials == list(range(1, TRAINED_THROUGH + 1)), \
    f"Gap or offset detected in loto6_results -- draw_serial sequence is not exactly 1..{TRAINED_THROUGH}"
assert db_main6 == meta['historicalCombos'], \
    "DB main6 numbers don't match meta.json's historicalCombos -- meta.json is stale, rerun precompute first"
print(f"Verified: {len(db_serials)} draws, serials exactly 1..{TRAINED_THROUGH}, matches meta.json historicalCombos.")

historical_combos = meta['historicalCombos']  # index i == draw_serial (i+1)
total_draws = len(historical_combos)

# ── Per-number frequency + last-seen serial + gap ────────────────────────
freq = {n: 0 for n in range(1, LOTO6_MAX + 1)}
last_seen = {n: 0 for n in range(1, LOTO6_MAX + 1)}  # 0 = never seen (shouldn't happen with 2133 draws)
for idx, combo in enumerate(historical_combos):
    serial = idx + 1
    for n in combo:
        freq[n] += 1
        last_seen[n] = serial  # overwritten each time, so ends up as the LAST (most recent) appearance

per_number = []
for n in range(1, LOTO6_MAX + 1):
    f = freq[n]
    ls = last_seen[n]
    gap = TRAINED_THROUGH - ls  # draws since last appearance; 0 = appeared in #2133 itself
    avg_gap = round(total_draws / f, 2) if f > 0 else None
    overdue_ratio = round(gap / avg_gap, 3) if avg_gap else None
    per_number.append({
        'num': n, 'freq': f, 'lastSeenSerial': ls, 'gap': gap,
        'avgGap': avg_gap, 'overdueRatio': overdue_ratio, 'inBase': n in base_pool,
    })

# ── Hot / cold: rank by frequency, tie-break by number ascending ────────
by_freq_desc = sorted(per_number, key=lambda r: (-r['freq'], r['num']))
by_freq_asc = sorted(per_number, key=lambda r: (r['freq'], r['num']))
hot = by_freq_desc[:HOT_N]
cold = by_freq_asc[:COLD_N]

median_rank = LOTO6_MAX // 2  # 21 -- top 21 = "hot half", bottom 22 = "cold half"
hot_half_nums = set(r['num'] for r in by_freq_desc[:median_rank])
cold_half_nums = set(r['num'] for r in by_freq_desc[median_rank:])

# ── Cold appear: cold-half numbers that appeared within the last RECENT_WINDOW draws ──
cold_appear = sorted(
    [r for r in per_number if r['num'] in cold_half_nums and r['gap'] <= RECENT_WINDOW - 1],
    key=lambda r: (r['gap'], r['freq'], r['num'])
)

# ── Hot overdue: hot-half numbers currently past their own average gap ──
hot_overdue = sorted(
    [r for r in per_number if r['num'] in hot_half_nums and r['overdueRatio'] is not None and r['overdueRatio'] > 1],
    key=lambda r: (-r['overdueRatio'], r['num'])
)

meta['hotCold'] = {
    'trainedThroughSerial': TRAINED_THROUGH,
    'totalDraws': total_draws,
    'hotN': HOT_N,
    'coldN': COLD_N,
    'recentWindow': RECENT_WINDOW,
    'medianRank': median_rank,
    'perNumber': per_number,
    'hot': hot,
    'cold': cold,
    'coldAppear': cold_appear,
    'hotOverdue': hot_overdue,
}

with open(META_PATH, 'w', encoding='utf-8') as f:
    json.dump(meta, f, indent=2)  # match precompute_xoshiro_elim_2134.py's formatting convention

print(f"\nHot (top {HOT_N}):  " + ', '.join(f"{r['num']}({r['freq']})" for r in hot))
print(f"Cold (bottom {COLD_N}): " + ', '.join(f"{r['num']}({r['freq']})" for r in cold))
print(f"Cold appear ({len(cold_appear)}): " + ', '.join(f"{r['num']}(f={r['freq']},gap={r['gap']})" for r in cold_appear))
print(f"Hot overdue ({len(hot_overdue)}): " + ', '.join(f"{r['num']}(f={r['freq']},gap={r['gap']},avg={r['avgGap']},ratio={r['overdueRatio']})" for r in hot_overdue))
print(f"\nUpdated {META_PATH}")
