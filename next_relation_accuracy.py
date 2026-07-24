"""
Walk-forward accuracy test for next-draw relation strategy.
For each draw t (using only history before t):
  - Take the 6 numbers drawn at t
  - Each number has a learned "next follower" distribution from draws 0..t-1
  - Aggregate scores across all 6 numbers
  - Pick top K candidates
  - Score = how many of draw t+1's actual numbers are in top K
"""
import psycopg2, numpy as np, sys
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

DB_URL = "postgresql://neondb_owner:npg_QbHpRZW8of3C@ep-hidden-wind-a1q0el7s-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"

print("Fetching draws from DB...")
conn = psycopg2.connect(DB_URL)
cur = conn.cursor()
cur.execute("SELECT num1,num2,num3,num4,num5,num6 FROM loto6_results ORDER BY draw_serial")
rows = cur.fetchall()
conn.close()
all_draws = [list(r) for r in rows]
T = len(all_draws)
print("Total draws:", T)

# Walk-forward accumulation
next_freq  = np.zeros((43, 43), dtype=np.int32)   # next_freq[n][f] = times f followed n
appearances = np.zeros(43, dtype=np.int32)         # how many times n had a valid next draw

K_VALUES = [6, 10, 15, 20]
results = {k: [] for k in K_VALUES}

# We need at least draw t=1 (pair (0,1)) in history before predicting t+1
# Loop: t = draw whose numbers we use as "input"
#        next draw = t+1 (what we predict)
#        history available = pairs (0,1) ... (t-1, t)
for t in range(1, T - 1):
    # Update history with pair (t-1, t) — draw t-1 followed by draw t
    prev = all_draws[t - 1]
    curr = all_draws[t]
    for n in prev:
        appearances[n - 1] += 1
        for f in curr:
            next_freq[n - 1][f - 1] += 1

    # Predict: aggregate next-follower scores across draw t's 6 numbers
    scores = np.zeros(43, dtype=np.float64)
    for n in curr:
        if appearances[n - 1] > 0:
            scores += next_freq[n - 1].astype(np.float64) / appearances[n - 1]

    actual_next = set(all_draws[t + 1])

    for K in K_VALUES:
        top_k = set(np.argsort(-scores)[:K] + 1)  # +1 to convert 0-index to 1-43
        hits = len(top_k & actual_next)
        results[K].append(hits)

print()
print("Walk-forward next-draw relation accuracy (" + str(T - 2) + " test draws):")
print()
for K in K_VALUES:
    arr = np.array(results[K])
    avg = arr.mean()
    baseline = K * 6 / 43
    lift = avg / baseline
    dist = np.bincount(arr, minlength=7)
    pct_3plus = (arr >= 3).sum() / len(arr) * 100
    pct_4plus = (arr >= 4).sum() / len(arr) * 100
    print("K=" + str(K) + ":")
    print("  Avg hits : " + str(round(avg, 3)) + " (baseline " + str(round(baseline, 3)) + ", lift " + str(round(lift, 3)) + "x)")
    print("  Dist 0-6 : " + str(dist.tolist()))
    print("  3+ hits  : " + str(round(pct_3plus, 1)) + "%")
    print("  4+ hits  : " + str(round(pct_4plus, 1)) + "%")
    print()

# Compare to pure random baseline
print("Random baseline (K picks from 43, 6 correct):")
for K in K_VALUES:
    print("  K=" + str(K) + " expected avg hits: " + str(round(K * 6 / 43, 3)))
