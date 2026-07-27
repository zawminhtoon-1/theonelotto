"""
find_best_k_combo.py
Search for the best combination of 4 K values (from K=1..43)
that maximizes >=6 hit rate in a 28-number multi-K prediction.
"6 hit" = at least 6 of the 7 actual numbers (6 main + bonus) are in the 28 predicted.
Backtest: last 1000 draws.
"""
import psycopg2, os, numpy as np
from itertools import combinations

DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://neondb_owner:npg_QbHpRZW8of3C@ep-hidden-wind-a1q0el7s-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"
)

conn = psycopg2.connect(DB_URL)
cur = conn.cursor()
cur.execute("""
    SELECT num1, num2, num3, num4, num5, num6, bonus
    FROM loto6_results ORDER BY draw_serial
""")
rows = cur.fetchall()
conn.close()

N = len(rows)
BT = 1000
N_PICKS = 28
test_start = N - BT

# Build numpy arrays: nums[i] = 7 numbers (6 main sorted + bonus) for draw i
all_nums = np.array([[r[0],r[1],r[2],r[3],r[4],r[5],r[6]] for r in rows], dtype=np.int32)
# actual[i] = set of 7 numbers
actual = [set(rows[i]) for i in range(N)]

# Random baseline: P(>=6 of 7 actual in 28 random out of 43)
# For 6 main numbers: P(all 6 in 28) = C(28,6)/C(43,6) = 0.0618
# For >=6 of 7 (including bonus): calculated separately
from math import comb
rand_6plus = (
    comb(28,6)*comb(15,1) +  # exactly 6 of 7 in pool
    comb(28,7)               # all 7 in pool
) / comb(43,7)
print(f"Random baseline >=6 of 7 hits: {rand_6plus*100:.2f}%")
print(f"N draws = {N}, testing on last {BT}")

def score_combo(k_vals):
    """Compute avg matches and >=6 hit rate for a combination of K values."""
    hits6 = 0
    for i in range(test_start, N):
        pool = set()
        for k in k_vals:
            back = i - k
            if back >= 0:
                for n in rows[back]:
                    pool.add(n)
        # Keep top 28 by: all unique numbers, if >28 need to rank
        # Simple approach: if <=28 use all, if >28 use first 28 encountered by K order
        if len(pool) > N_PICKS:
            # Rebuild in order
            ordered = []
            seen = set()
            for k in k_vals:
                back = i - k
                if back >= 0:
                    for n in rows[back]:
                        if n not in seen:
                            ordered.append(n)
                            seen.add(n)
                            if len(ordered) == N_PICKS:
                                break
                if len(ordered) == N_PICKS:
                    break
            pool = set(ordered)

        matches = len(pool & actual[i])
        if matches >= 6:
            hits6 += 1
    return hits6 / BT * 100

# Step 1: Score each individual K for >=6 hit rate
print("\nStep 1: Individual K scores (>=6 hit rate)...")
indiv_scores = []
for k in range(1, 44):
    hits6 = 0
    for i in range(test_start, N):
        back = i - k
        if back >= 0:
            pool = set(rows[back])  # 7 numbers
            matches = len(pool & actual[i])
            if matches >= 6:
                hits6 += 1
    rate = hits6 / BT * 100
    indiv_scores.append((rate, k))

indiv_scores.sort(reverse=True)
print("Top 15 individual K by >=6 hit rate:")
for rate, k in indiv_scores[:15]:
    print(f"  K={k:2d}: {rate:.2f}%")

# Step 2: Test combinations of top 12 individual K values
top_ks = [k for rate, k in indiv_scores[:12]]
print(f"\nStep 2: Testing C({len(top_ks)},4) = {comb(len(top_ks),4)} combos from top {len(top_ks)} K values...")

best_rate = 0
best_combo = None
total = comb(len(top_ks), 4)
count = 0
for combo in combinations(top_ks, 4):
    rate = score_combo(combo)
    count += 1
    if count % 50 == 0:
        print(f"  {count}/{total}... best so far: {best_rate:.2f}% at K={best_combo}")
    if rate > best_rate:
        best_rate = rate
        best_combo = combo

print(f"\nBest combo: K={best_combo}")
print(f">=6 hit rate: {best_rate:.2f}%")
print(f"Random baseline: {rand_6plus*100:.2f}%")
print(f"Lift: {(best_rate/(rand_6plus*100)-1)*100:+.2f}%")
