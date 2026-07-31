"""
Patch backtest.html:
  - Recompute method 1 (index 1) from Reverse MA (44-mean) to Normal MA (mean)
  - Rename: "Reverse MA-43" -> "MA-43", "RevMA43" -> "MA-43"
Then regenerate combo_evo_data.json + combo_evo_rounds.json
using the updated predictions.
"""
import json, re, sys, psycopg2, itertools, time, os
import numpy as np
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

DB_URL    = os.environ["DATABASE_URL"]
HTML_PATH = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto\public\backtest.html"
DATA_PATH = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto\public\combo_evo_data.json"
ROUNDS_PATH = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto\public\combo_evo_rounds.json"

# ── 1. Fetch all draws from DB ────────────────────────────────────────────────
print("Connecting to DB...")
conn = psycopg2.connect(DB_URL)
cur = conn.cursor()
cur.execute("SELECT draw_serial, num1, num2, num3, num4, num5, num6 FROM loto6_results ORDER BY draw_serial")
rows = cur.fetchall()
conn.close()
print("Fetched " + str(len(rows)) + " draws from DB")

# Build list: [(serial, [sorted_balls]), ...]
all_draws = [(r[0], sorted([r[1], r[2], r[3], r[4], r[5], r[6]])) for r in rows]
serial_to_idx = {s: i for i, (s, _) in enumerate(all_draws)}
print("Serial range: " + str(all_draws[0][0]) + " - " + str(all_draws[-1][0]))

# ── 2. Load backtest DATA ─────────────────────────────────────────────────────
print("Loading backtest.html...")
with open(HTML_PATH, encoding='utf-8') as f:
    html = f.read()

m = re.search(r'const DATA\s*=\s*(\[)', html)
bs = m.start(1)
depth = 0; pos = bs
while pos < len(html):
    if html[pos] == '[': depth += 1
    elif html[pos] == ']':
        depth -= 1
        if depth == 0: be = pos + 1; break
    pos += 1
DATA = json.loads(html[bs:be])
print("Loaded DATA: " + str(len(DATA)) + " entries, serials " + str(DATA[0]['s']) + "-" + str(DATA[-1]['s']))

# ── 3. Normal MA prediction function ─────────────────────────────────────────
def normal_ma_predict(window_draws, all_before, total=15):
    """
    window_draws: list of [sorted balls] for last 43 draws
    all_before:   list of [sorted balls] for ALL draws before this prediction
    total:        pad to this many picks
    """
    # Frequency for padding
    freq = {}
    for nums in all_before:
        for n in nums:
            freq[n] = freq.get(n, 0) + 1

    # Mean per position (0..5 = sorted positions)
    base6 = []
    for p in range(6):
        vals = [d[p] for d in window_draws]
        mean_val = sum(vals) / len(vals)
        base6.append(max(1, min(43, round(mean_val))))

    # makeUnique: dedupe, then pad with freq
    seen = set()
    result = []
    for n in base6:
        if n not in seen:
            seen.add(n)
            result.append(n)

    ordered = sorted(freq.keys(), key=lambda x: -freq[x])
    for n in ordered:
        if len(result) >= total:
            break
        if n not in seen:
            seen.add(n)
            result.append(n)

    return sorted(result[:total])

# ── 4. Compute Normal MA for each of 1001 backtest draws ─────────────────────
print("Computing Normal MA predictions...")
t0 = time.time()
for i, entry in enumerate(DATA):
    s = entry['s']
    idx = serial_to_idx[s]

    # Last 43 draws BEFORE this serial
    window = [nums for _, nums in all_draws[max(0, idx-43):idx]]
    if len(window) == 0:
        continue

    # All draws BEFORE this serial (for frequency-based padding)
    all_before = [nums for _, nums in all_draws[:idx]]

    new_picks = normal_ma_predict(window, all_before, 15)

    # Preserve other fields in pred[1]: [picks, confidence, flag]
    entry['p'][1][0] = new_picks

    if i % 200 == 0:
        print("  " + str(i) + "/" + str(len(DATA)) + " s=" + str(s) + " -> " + str(new_picks[:6]) + "...")

print("Done in " + str(round(time.time()-t0, 1)) + "s")

# ── 5. Rename in HTML and replace DATA ───────────────────────────────────────
print("Patching HTML...")
data_str = json.dumps(DATA, separators=(',', ':'))
new_html = html[:bs] + data_str + html[be:]

# Rename method
new_html = new_html.replace('"Reverse MA-43"', '"MA-43"')
new_html = new_html.replace('"RevMA43"', '"MA-43"')
new_html = new_html.replace('>Reverse MA-43<', '>MA-43<')
new_html = new_html.replace('>2: Reverse MA-43<', '>2: MA-43<')

with open(HTML_PATH, 'w', encoding='utf-8') as f:
    f.write(new_html)
print("Saved backtest.html (" + str(len(new_html)//1024) + " KB)")

# ── 6. Regenerate combo_evo_data.json and combo_evo_rounds.json ──────────────
print("Regenerating combo_evo data...")

# Reload HTML to extract updated DATA
with open(HTML_PATH, encoding='utf-8') as f:
    html2 = f.read()
m2 = re.search(r'const DATA\s*=\s*(\[)', html2)
bs2 = m2.start(1)
depth2 = 0; pos2 = bs2
while pos2 < len(html2):
    if html2[pos2] == '[': depth2 += 1
    elif html2[pos2] == ']':
        depth2 -= 1
        if depth2 == 0: be2 = pos2 + 1; break
    pos2 += 1
DATA2 = json.loads(html2[bs2:be2])

m3 = re.search(r'const METHODS\s*=\s*(\[.*?\])', html2, re.DOTALL)
METHODS = json.loads(m3.group(1))
N = 16; T = len(DATA2)
print(str(T) + " draws, " + str(N) + " methods")

# Build matrices
picks_mat  = np.zeros((T, N, 43), dtype=np.uint8)
actual_mat = np.zeros((T, 43),    dtype=np.uint8)
serials2   = []
dates2     = []
actuals2   = []

for t, row in enumerate(DATA2):
    serials2.append(row['s'])
    dates2.append(row.get('d', str(row['s']))[:10])
    actual_balls = sorted(row['a'])
    actuals2.append(actual_balls)
    for n in actual_balls: actual_mat[t, n-1] = 1
    for mi, pred in enumerate(row['p']):
        for n in pred[0]: picks_mat[t, mi, n-1] = 1

all_freq = picks_mat.sum(axis=1).astype(np.float32)

def topk_mask(method_idx, K):
    score = np.where(picks_mat[:, method_idx, :], all_freq, -np.inf)
    order = np.argsort(-score, axis=1)[:, :K]
    mask  = np.zeros((T, 43), dtype=np.uint8)
    rows_  = np.repeat(np.arange(T), K)
    mask[rows_, order.ravel()] = 1
    return mask

ALL_KS = [6, 8, 10, 15, 20]
print("Precomputing top-K masks for K=" + str(ALL_KS) + "...")
t0 = time.time()
topk_cache = {}
for K in ALL_KS:
    for mi in range(N):
        topk_cache[(mi, K)] = topk_mask(mi, K)
print("  done in " + str(round(time.time()-t0, 1)) + "s")

# Evaluate all 120 combos x 5 K values
all_combos = list(itertools.combinations(range(N), 2))
print("Running " + str(len(all_combos)) + " combos x " + str(len(ALL_KS)) + " K values...")
t0 = time.time()

combo_results = {}
for m0, m1 in all_combos:
    key = str(m0) + "," + str(m1)
    combo_results[key] = {}
    for K in ALL_KS:
        union_mask = np.clip(topk_cache[(m0, K)] + topk_cache[(m1, K)], 0, 1)
        union_size = union_mask.sum(axis=1)
        hits = (union_mask * actual_mat).sum(axis=1)
        arr  = np.array(hits)
        dist = np.bincount(arr.clip(0, 6), minlength=7).tolist()
        combo_results[key][str(K)] = {
            'hits':      hits.tolist(),
            'dist':      dist,
            'avg':       round(float(arr.mean()), 4),
            'fp':        int((arr >= 4).sum()),
            'z0':        dist[0],
            'z6':        dist[6],
            'union_avg': round(float(union_size.mean()), 2),
        }

print("Done in " + str(round(time.time()-t0, 1)) + "s")

# Print summary for K=15, K=20
for K in (15, 20):
    ks = str(K)
    rows_k = [(k, combo_results[k][ks]) for k in combo_results]
    best_z6  = max(rows_k, key=lambda x: x[1]['z6'])
    worst_z0 = max(rows_k, key=lambda x: x[1]['z0'])
    best_avg = max(rows_k, key=lambda x: x[1]['avg'])
    def fmt(k_r):
        k, r = k_r
        mi0, mi1 = map(int, k.split(','))
        return METHODS[mi0] + ' + ' + METHODS[mi1] + ' avg=' + str(r['avg']) + ' 6hit=' + str(r['z6']) + ' 0hit=' + str(r['z0'])
    print('K=' + str(K) + ':')
    print('  Best 6-hit: ' + fmt(best_z6))
    print('  Best avg  : ' + fmt(best_avg))
    print('  Most 0-hit: ' + fmt(worst_z0))
    print()

# Save combo_evo_data.json
out = {
    'T': T,
    'N': N,
    'methods': METHODS,
    'combos': combo_results,
    'dates': dates2,
    'formula': 'union_topk',
}
with open(DATA_PATH, 'w') as f:
    json.dump(out, f, separators=(',', ':'))
print("Saved combo_evo_data.json (" + str(len(json.dumps(out))//1024) + " KB)")

# Save combo_evo_rounds.json
rounds_picks = []
for t, row in enumerate(DATA2):
    method_picks = []
    for mi in range(N):
        balls = sorted([n+1 for n in range(43) if picks_mat[t, mi, n]])
        method_picks.append(balls)
    rounds_picks.append(method_picks)

rounds_out = {
    'dates':   dates2,
    'serials': serials2,
    'actuals': actuals2,
    'picks':   rounds_picks,
}
with open(ROUNDS_PATH, 'w') as f:
    json.dump(rounds_out, f, separators=(',', ':'))
print("Saved combo_evo_rounds.json (" + str(len(json.dumps(rounds_out))//1024) + " KB)")
print("ALL DONE")
