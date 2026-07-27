"""
backtest_serial_mod43.py
Strategy: group draws by (draw_serial % 43).
For draw S, pool all past draws where serial % 43 == S % 43.
Rank pooled numbers by frequency, take top 28 as prediction.
Backtest: last 1000 draws.
Compare 6-hit count vs current multi-K method.
"""
import psycopg2, os, statistics
from collections import Counter

DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://neondb_owner:npg_QbHpRZW8of3C@ep-hidden-wind-a1q0el7s-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"
)

conn = psycopg2.connect(DB_URL)
cur = conn.cursor()
cur.execute("""
    SELECT draw_serial, num1, num2, num3, num4, num5, num6, bonus
    FROM loto6_results ORDER BY draw_serial
""")
rows = cur.fetchall()
conn.close()

N = len(rows)
BT = 1000
N_PICKS = 28
test_start = N - BT

# Build indexed lookup
serials = [r[0] for r in rows]
all_nums = [set(r[1:]) for r in rows]  # 7 numbers per draw

# Group draws by serial % 43
from collections import defaultdict
mod_groups = defaultdict(list)  # mod_val -> list of (i, serial)
for i, r in enumerate(rows):
    mod_groups[r[0] % 43].append(i)

print(f"N={N}, backtest last {BT} draws")
print(f"N_PICKS={N_PICKS}")
print()

# --- Backtest ---
match_counts = []
hit_counts = [0] * (N_PICKS + 1)

for i in range(test_start, N):
    s = serials[i]
    target_mod = s % 43

    # Get all PAST draws (before i) with same mod
    group = mod_groups[target_mod]
    past = [j for j in group if j < i]

    if not past:
        # No past draws in same group — fallback: predict nothing (0 matches)
        match_counts.append(0)
        hit_counts[0] += 1
        continue

    # Count number frequencies across all past same-mod draws
    freq = Counter()
    for j in past:
        for n in rows[j][1:]:  # 7 numbers
            freq[n] += 1

    # Take top N_PICKS by frequency
    top = [n for n, _ in freq.most_common(N_PICKS)]
    pred_set = set(top)

    # Count matches with actual draw i
    matches = len(pred_set & all_nums[i])
    match_counts.append(matches)
    hit_counts[matches] = hit_counts[matches] + 1

# Stats
avg = statistics.mean(match_counts)
rand_baseline = N_PICKS * 7 / 43
cnt_6plus = sum(1 for m in match_counts if m >= 6)
cnt_5plus = sum(1 for m in match_counts if m >= 5)
cnt_4plus = sum(1 for m in match_counts if m >= 4)
cnt_7 = sum(1 for m in match_counts if m >= 7)

print("=== Serial mod 43 method ===")
print(f"Avg matches: {avg:.4f}  (random baseline: {rand_baseline:.4f})")
print(f"Lift: {(avg/rand_baseline-1)*100:+.2f}%")
print(f"6+ hit draws: {cnt_6plus} / {BT}")
print(f"5+ hit draws: {cnt_5plus} / {BT}")
print(f"4+ hit draws: {cnt_4plus} / {BT}")
print(f"7-hit draws:  {cnt_7} / {BT}")
print()
print("=== Comparison (current multi-K method) ===")
print(f"6+ hit draws: 85 / 1000  (K=23,40,38,33)")
print(f"Avg matches: ~3.65")
print()

# Distribution
print("Match distribution:")
for k in range(10):
    bar = "=" * hit_counts[k]
    print(f"  {k} matches: {hit_counts[k]:4d}  {bar}")

# Show what the prediction would be for the NEXT draw
next_s = serials[-1] + 1
next_mod = next_s % 43
past_same = [j for j in mod_groups[next_mod]]  # all existing draws with same mod
freq_next = Counter()
for j in past_same:
    for n in rows[j][1:]:
        freq_next[n] += 1
top_next = [n for n, _ in freq_next.most_common(N_PICKS)]

print(f"\nNext draw: serial {next_s} (mod 43 = {next_mod})")
print(f"Past draws with same mod: {len(past_same)} draws")
print(f"Top {N_PICKS} predicted numbers: {sorted(top_next)}")
print(f"Their frequencies: {[(n, freq_next[n]) for n in sorted(top_next)]}")
