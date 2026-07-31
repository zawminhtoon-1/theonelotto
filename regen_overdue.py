"""
Regenerate overdue.html with:
  - Updated current overdue stats (latest draw)
  - 1000-draw backtest instead of 300
"""
import psycopg2, json, re, sys, os
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

DB_URL    = os.environ["DATABASE_URL"]
HTML_PATH = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto\public\overdue.html"
TOP_K     = 8
BT_DRAWS  = 1000

print("Fetching draws...")
conn = psycopg2.connect(DB_URL)
cur = conn.cursor()
cur.execute("""
    SELECT draw_serial, draw_date, num1, num2, num3, num4, num5, num6, bonus
    FROM loto6_results ORDER BY draw_serial
""")
rows = cur.fetchall()
conn.close()

draws = [{"s": r[0], "d": str(r[1])[:10] if r[1] else "", "n": sorted([r[2],r[3],r[4],r[5],r[6],r[7]]), "b": r[8]} for r in rows]
T = len(draws)
print("Total draws:", T, "  Latest serial:", draws[-1]["s"])

# ── Current overdue (after all T draws) ──────────────────────────────────────
# Cold streak for number n = draws since last main-ball appearance
last_seen = {}
for d in draws:
    for n in d["n"]:
        last_seen[n] = d["s"]

latest_serial = draws[-1]["s"]
streaks = {}  # n -> cold streak
for n in range(1, 44):
    if n in last_seen:
        streaks[n] = latest_serial - last_seen[n]
    else:
        streaks[n] = T  # never appeared

# CUR_SORTED: 1..43 sorted by streak desc
cur_sorted = sorted(range(1, 44), key=lambda n: -streaks[n])
cur_streaks_arr = [streaks[n] for n in range(1, 44)]  # indexed [n-1]

print("Current top-10 overdue:", [(n, streaks[n]) for n in cur_sorted[:10]])

# ── Walk-forward backtest for last BT_DRAWS draws ────────────────────────────
# Test draws: last BT_DRAWS entries in draws list
test_draws = draws[T - BT_DRAWS:]   # index T-1000 ... T-1 (ascending)
train_start = 0
train_end_idx = T - BT_DRAWS        # exclusive end of training block

print("Backtesting", len(test_draws), "draws:", test_draws[0]["s"], "->", test_draws[-1]["s"])

BT = []   # will be built ascending, then reversed to DESC at end
HIT_COUNTS = []
SERIALS = []
HIT_DIST = [0] * (TOP_K + 1)

# Maintain running last_seen_wf for walk-forward
last_seen_wf = {}
for d in draws[:train_end_idx]:
    for n in d["n"]:
        last_seen_wf[n] = d["s"]

for i, d in enumerate(test_draws):
    # Compute cold streaks using history before this draw
    # (last_seen_wf reflects all draws BEFORE d)
    cur_serial = d["s"]

    wf_streaks = {}
    for n in range(1, 44):
        if n in last_seen_wf:
            wf_streaks[n] = cur_serial - last_seen_wf[n] - 1  # draws BETWEEN last hit and now
        else:
            wf_streaks[n] = cur_serial  # never seen in training

    # Top-K most overdue
    pred = sorted(range(1, 44), key=lambda n: -wf_streaks[n])[:TOP_K]
    pred_set = set(pred)
    actual_set = set(d["n"])

    hits = sorted(pred_set & actual_set)
    hc = len(hits)

    HIT_DIST[hc] += 1
    HIT_COUNTS.append(hc)
    SERIALS.append(cur_serial)

    BT.append({
        "s": cur_serial,
        "d": d["d"],
        "n": d["n"],
        "pr": sorted(pred),
        "st": [wf_streaks[n] for n in sorted(pred)],
        "h": hits,
        "hc": hc,
    })

    # Update last_seen_wf with this draw
    for n in d["n"]:
        last_seen_wf[n] = cur_serial

BT_DESC = list(reversed(BT))  # newest first for display
avg_hits = sum(HIT_COUNTS) / len(HIT_COUNTS)
rand_avg = round(TOP_K * 6 / 43, 4)

SERIALS_DESC = list(reversed(SERIALS))
HIT_COUNTS_DESC = list(reversed(HIT_COUNTS))

print("Avg hits:", round(avg_hits, 4), "  Rand baseline:", rand_avg)
print("HIT_DIST:", HIT_DIST)

# ── Patch overdue.html ───────────────────────────────────────────────────────
with open(HTML_PATH, encoding='utf-8') as f:
    lines = f.readlines()

def replace_line_starting(lines, prefix, new_content):
    for i, line in enumerate(lines):
        if line.lstrip().startswith(prefix):
            lines[i] = new_content + "\n"
            return True
    return False

# Update badge
for i, line in enumerate(lines):
    if 'draws &middot; last' in line or 'draws · last' in line or 'backtested</span>' in line:
        lines[i] = re.sub(
            r'\d+ draws.*?backtested</span>',
            str(T) + ' draws &middot; last ' + str(BT_DRAWS) + ' backtested</span>',
            line
        )
        break

# Update "Draws tested" stat
for i, line in enumerate(lines):
    if 'Draws tested:' in line:
        lines[i] = re.sub(r'<span>\d+</span>', '<span>' + str(BT_DRAWS) + '</span>', line)
        break

# Update "distribution across N draws"
for i, line in enumerate(lines):
    if 'distribution across' in line and 'draws:' in line:
        lines[i] = re.sub(r'distribution across \d+ draws:', 'distribution across ' + str(BT_DRAWS) + ' draws:', line)
        break

# Update "last N draws, oldest"
for i, line in enumerate(lines):
    if 'last' in line and 'draws, oldest' in line:
        lines[i] = re.sub(r'last \d+ draws, oldest', 'last ' + str(BT_DRAWS) + ' draws, oldest', line)
        break

# Update inline JS data lines
js_replacements = {
    'const BT ':          'const BT          = ' + json.dumps(BT_DESC, separators=(',',':')) + ';',
    'const CUR_SORTED ':  'const CUR_SORTED  = ' + json.dumps(cur_sorted, separators=(',',':')) + ';  // 1-43, sorted by cold streak desc',
    'const CUR_STREAKS ': 'const CUR_STREAKS = ' + json.dumps(cur_streaks_arr, separators=(',',':')) + '; // [streak for n=1..43]',
    'const HIT_COUNTS ':  'const HIT_COUNTS  = ' + json.dumps(HIT_COUNTS_DESC, separators=(',',':')) + ';',
    'const SERIALS ':     'const SERIALS     = ' + json.dumps(SERIALS_DESC, separators=(',',':')) + ';',
    'const HIT_DIST ':    'const HIT_DIST    = ' + json.dumps(HIT_DIST, separators=(',',':')) + ';',
    'const AVG_HITS ':    'const AVG_HITS    = ' + str(round(avg_hits, 4)) + ';',
    'const RAND_AVG ':    'const RAND_AVG    = ' + str(rand_avg) + ';',
    'const TOP6_SET ':    'const TOP6_SET    = new Set(CUR_SORTED.slice(0,' + str(TOP_K) + '));',
}

for i, line in enumerate(lines):
    stripped = line.lstrip()
    for prefix, new_val in js_replacements.items():
        if stripped.startswith(prefix):
            lines[i] = new_val + "\n"
            break

# Fix text label references to old TOP_K
for i, line in enumerate(lines):
    if 'top-18' in line or 'top-6' in line.lower():
        lines[i] = line.replace('top-18', 'top-' + str(TOP_K)).replace('Top-18', 'Top-' + str(TOP_K))
        # "top-6 prediction" label refers to the highlighted set — update to match TOP_K
        lines[i] = lines[i].replace('top-6 prediction', 'top-' + str(TOP_K) + ' prediction').replace('Top-6 prediction', 'Top-' + str(TOP_K) + ' prediction')

with open(HTML_PATH, 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("Saved overdue.html")
