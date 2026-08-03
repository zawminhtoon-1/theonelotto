"""
miniloto_combo_search.py
--------------------------
Searches all 3/4/5-method combinations of MiniLoto's 16 backtested methods
(union of each method's K=5 picks per historical draw) for one with a
genuine edge over random baseline -- same approach as loto7_combo_search.py.

Reads: miniloto_backtest_data.json (written by gen_miniloto_backtest.py)
Run: python miniloto_combo_search.py
"""
import json, itertools

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
DATA_PATH = BASE + r"\miniloto_backtest_data.json"

with open(DATA_PATH, encoding='utf-8') as f:
    obj = json.load(f)

METHODS = obj["methods"]
DATA = obj["data"]
N = len(METHODS)
T = len(DATA)
print(f"Loaded {T} draws x {N} methods")

picks_by_method = [[] for _ in range(N)]
actual_by_draw = []
for row in DATA:
    actual_by_draw.append(set(row["a"]))
    for mi, pred in enumerate(row["p"]):
        picks_by_method[mi].append(set(pred[0]))

def eval_combo(method_idxs):
    total_hits = 0
    plus3 = 0
    union_sizes = 0
    for t in range(T):
        union = set()
        for mi in method_idxs:
            union |= picks_by_method[mi][t]
        hits = len(union & actual_by_draw[t])
        total_hits += hits
        if hits >= 3:
            plus3 += 1
        union_sizes += len(union)
    avg_hits = total_hits / T
    return avg_hits, plus3, union_sizes / T

print("\nSearching all 3/4/5-method combinations...")
results = []
for size in (3, 4, 5):
    for combo in itertools.combinations(range(N), size):
        avg_hits, plus3, avg_union = eval_combo(combo)
        random_avg_for_union = avg_union * 5 / 31
        lift = avg_hits / random_avg_for_union if random_avg_for_union > 0 else 0
        results.append((lift, avg_hits, plus3, avg_union, combo))

results.sort(key=lambda x: -x[0])
print(f"\nSearched {len(results)} combinations (sizes 3,4,5)")
print("\nTop 10 by lift-over-random (normalized for union size):")
for lift, avg_hits, plus3, avg_union, combo in results[:10]:
    names = " + ".join(METHODS[i] for i in combo)
    print(f"  lift={lift:.3f}  avg_hits={avg_hits:.3f}  3+hits={plus3}/{T} ({plus3/T*100:.1f}%)  "
          f"avg_union_size={avg_union:.1f}  [{names}]")

print("\nBottom 5 (worst, for reference):")
for lift, avg_hits, plus3, avg_union, combo in results[-5:]:
    names = " + ".join(METHODS[i] for i in combo)
    print(f"  lift={lift:.3f}  avg_hits={avg_hits:.3f}  3+hits={plus3}/{T} ({plus3/T*100:.1f}%)  "
          f"avg_union_size={avg_union:.1f}  [{names}]")

top_lift = results[0][0]
print(f"\n=== VERDICT ===")
print(f"Best combo lift over random: {top_lift:.3f}x")
if top_lift > 1.10:
    print("=> Meaningful edge found (>10% lift). Worth surfacing as a Best Combo panel.")
else:
    print("=> No meaningful edge (within ~10% of random baseline). This is noise-level,")
    print("   consistent with individual methods already hovering near random.")
    print("   Recommendation: do NOT add a Best Combo panel -- would be misleading.")
