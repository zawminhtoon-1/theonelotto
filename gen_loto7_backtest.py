"""
gen_loto7_backtest.py
----------------------
Walk-forward backtest for Loto7 across all historical draws in loto7_results,
using a starter set of 5 prediction methods (Poly deg-2, MA-37, FreqAll,
Markov, Naive Bayes) adapted from Loto6's 16-method roster to Loto7's
7-from-37 + 2-bonus structure.

Each method predicts 7 numbers per draw using ONLY draws strictly before it
(no lookahead). Output: public/loto7_backtest.html.

Run: python gen_loto7_backtest.py
"""
import os, json, time
import numpy as np
import psycopg2
from collections import Counter, defaultdict

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
HTML_OUT = BASE + r"\public\loto7_backtest.html"
DB_URL = os.environ["DATABASE_URL"]

LOTO7_MAX = 37
K = 7  # fixed pick count for this first pass (natural Loto7 pick size)

METHODS = ["Poly deg-2", "MA-37", "Most frequent all", "Markov chain", "Naive Bayes"]
MSHORT  = ["Poly-2", "MA-37", "FreqAll", "Markov", "NaiveBay"]
COLORS  = ["#38bdf8", "#818cf8", "#4ade80", "#facc15", "#f87171"]

# ── 1. Fetch all draws ──────────────────────────────────────────────────────
print("Fetching Loto7 draws from DB...")
conn = psycopg2.connect(DB_URL)
cur = conn.cursor()
cur.execute("""
    SELECT draw_serial, draw_date, num1,num2,num3,num4,num5,num6,num7, bonus1, bonus2
    FROM loto7_results ORDER BY draw_serial
""")
db_rows = cur.fetchall()
conn.close()
print(f"Fetched {len(db_rows)} draws")

all_serials = [r[0] for r in db_rows]
all_dates   = [str(r[1]) for r in db_rows]
all_main7   = [sorted([r[2],r[3],r[4],r[5],r[6],r[7],r[8]]) for r in db_rows]
all_bonus1  = [r[9]  for r in db_rows]
all_bonus2  = [r[10] for r in db_rows]

# ── Helpers ───────────────────────────────────────────────────────────────────
def pad_to_k(base_picks, all_before_main7, k=K):
    freq = Counter(n for nums in all_before_main7 for n in nums)
    seen = set(base_picks)
    result = list(base_picks)
    for n in sorted(range(1, LOTO7_MAX + 1), key=lambda x: -freq.get(x, 0)):
        if len(result) >= k:
            break
        if n not in seen:
            seen.add(n); result.append(n)
    return sorted(result[:k])

def make_unique(nums, all_before_main7, k=K):
    seen = set(); result = []
    for n in nums:
        n = max(1, min(LOTO7_MAX, int(round(n))))
        if n not in seen:
            seen.add(n); result.append(n)
    return pad_to_k(result, all_before_main7, k)

def compute_hits(picks, actual7, bonus1, bonus2):
    hits = len(set(picks) & set(actual7))
    bonus_hit = (bonus1 in picks) or (bonus2 in picks)
    return hits, bonus_hit

# ── 5 prediction methods ─────────────────────────────────────────────────────
def method_poly(train_main7, train_serials, target_serial):
    x = np.array(train_serials, dtype=float)
    base = []
    for p in range(7):
        y = np.array([d[p] for d in train_main7], dtype=float)
        coeffs = np.polyfit(x, y, 2)
        raw = np.polyval(coeffs, float(target_serial))
        base.append(max(1, min(LOTO7_MAX, int(round(raw)))))
    return make_unique(base, train_main7)

def method_ma(train_main7, window_size=37):
    window = train_main7[-window_size:] if len(train_main7) >= 1 else train_main7
    base = []
    for p in range(7):
        vals = [d[p] for d in window]
        base.append(max(1, min(LOTO7_MAX, round(sum(vals) / len(vals)))))
    return make_unique(base, train_main7)

def method_freq_all(train_main7, k=K):
    freq = Counter(n for draws in train_main7 for n in draws)
    return sorted(n for n, _ in freq.most_common(k))

def method_markov(train_main7, k=K):
    pair_freq = defaultdict(int)
    for draws in train_main7:
        for a in draws:
            for b in draws:
                if a != b:
                    pair_freq[(a, b)] += 1
    last = set(train_main7[-1]) if train_main7 else set()
    scores = Counter()
    for src in last:
        for dst in range(1, LOTO7_MAX + 1):
            if dst not in last:
                scores[dst] += pair_freq.get((src, dst), 0)
    result = [n for n, _ in scores.most_common(k - len(last))]
    result = list(last) + result
    return pad_to_k(sorted(result[:k]), train_main7, k)

def method_naive_bayes(train_main7, k=K):
    if len(train_main7) < 2:
        return method_freq_all(train_main7, k)
    last = set(train_main7[-1])
    co = defaultdict(int); prior = defaultdict(int)
    for i in range(len(train_main7) - 1):
        cur_set = set(train_main7[i]); nxt_set = set(train_main7[i + 1])
        for m in cur_set:
            prior[m] += 1
            for n in nxt_set:
                co[(m, n)] += 1
    scores = Counter()
    for n in range(1, LOTO7_MAX + 1):
        for m in last:
            if prior[m] > 0:
                scores[n] += co[(m, n)] / prior[m]
    return sorted(n for n, _ in scores.most_common(k))

# ── 2. Walk-forward backtest ─────────────────────────────────────────────────
print("Running walk-forward backtest...")
t0 = time.time()

DATA = []
for idx in range(len(all_serials)):
    target_serial = all_serials[idx]
    train_serials = all_serials[:idx]
    train_main7 = all_main7[:idx]
    if len(train_serials) < 2:
        continue  # not enough history

    target_actual7 = all_main7[idx]
    target_b1, target_b2 = all_bonus1[idx], all_bonus2[idx]

    preds_list = []
    for fn in (
        lambda: method_poly(train_main7, train_serials, target_serial),
        lambda: method_ma(train_main7),
        lambda: method_freq_all(train_main7),
        lambda: method_markov(train_main7),
        lambda: method_naive_bayes(train_main7),
    ):
        picks = fn()
        hits, bonus_hit = compute_hits(picks, target_actual7, target_b1, target_b2)
        preds_list.append([picks, hits, bonus_hit])

    DATA.append({
        "s": target_serial, "d": all_dates[idx],
        "a": target_actual7, "b1": target_b1, "b2": target_b2,
        "p": preds_list,
    })

print(f"Backtested {len(DATA)} draws in {round(time.time()-t0,1)}s")

# ── 3. Aggregate stats ────────────────────────────────────────────────────────
N_METHODS = len(METHODS)
hit_counts = [[0]*8 for _ in range(N_METHODS)]   # 0..7 hits
bonus_hits = [0]*N_METHODS
match_series = [[] for _ in range(N_METHODS)]

for row in DATA:
    for mi, (picks, hits, bonus_hit) in enumerate(row["p"]):
        hit_counts[mi][min(hits,7)] += 1
        if bonus_hit:
            bonus_hits[mi] += 1
        match_series[mi].append(hits)

T = len(DATA)
avg_hits = [round(sum(match_series[mi]) / T, 4) for mi in range(N_METHODS)]
bonus_pct = [round(bonus_hits[mi] / T * 100, 1) for mi in range(N_METHODS)]
best_hits = [max(match_series[mi]) for mi in range(N_METHODS)]

# Random baseline: E[hits] = K * (7 actual winners / 37 pool)
random_avg = K * 7 / LOTO7_MAX
# P(at least one of 2 bonus balls in a random K-pick from 37)
from math import comb
random_bonus_pct = round((1 - comb(LOTO7_MAX-2, K) / comb(LOTO7_MAX, K)) * 100, 1)

print("\n=== Results ===")
for mi in range(N_METHODS):
    print(f"  {METHODS[mi]:20s} avg={avg_hits[mi]:.4f}  bonus%={bonus_pct[mi]:5.1f}  best={best_hits[mi]}  dist={hit_counts[mi]}")
print(f"  {'Random baseline':20s} avg={random_avg:.4f}  bonus%={random_bonus_pct:5.1f}")

best_method_idx = max(range(N_METHODS), key=lambda i: avg_hits[i])
print(f"\nBest method: {METHODS[best_method_idx]} (avg {avg_hits[best_method_idx]} vs random {random_avg:.4f})")

# ── 4. Generate HTML ──────────────────────────────────────────────────────────
print("\nGenerating HTML...")

html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Loto 7 — Backtest Report</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
  :root {{
    --bg: #0f172a; --surface: #1e293b; --border: #334155;
    --text: #f1f5f9; --muted: #94a3b8; --accent: #38bdf8;
    --green: #4ade80; --orange: #fb923c; --red: #f87171; --yellow: #facc15;
  }}
  * {{ box-sizing: border-box; }}
  body {{ background: var(--bg); color: var(--text); font-family: system-ui,sans-serif; padding: 24px; margin: 0; }}
  h1 {{ font-size: 1.5rem; margin: 0 0 4px; }}
  .subtitle {{ color: var(--muted); font-size: .875rem; margin-bottom: 24px; }}
  .note {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
           padding: 14px 18px; font-size: .8rem; color: var(--muted); margin-bottom: 24px; line-height: 1.6; }}
  .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px; margin-bottom: 24px; }}
  .card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
           padding: 16px; }}
  .card.best {{ border-color: var(--yellow); box-shadow: 0 0 0 1px var(--yellow); }}
  .card-name {{ font-size: .8rem; color: var(--muted); text-transform: uppercase; letter-spacing: .05em; margin-bottom: 6px; }}
  .card-avg {{ font-size: 1.6rem; font-weight: 700; color: var(--accent); }}
  .card-avg .unit {{ font-size: .8rem; color: var(--muted); font-weight: 400; margin-left: 4px; }}
  .card-sub {{ font-size: .75rem; color: var(--muted); margin-top: 8px; }}
  .chart-wrap {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
                 padding: 20px; margin-bottom: 24px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: .85rem; }}
  th {{ text-align: left; padding: 10px 8px; border-bottom: 1px solid var(--border); color: var(--muted);
        text-transform: uppercase; font-size: .7rem; letter-spacing: .05em; }}
  td {{ padding: 10px 8px; border-bottom: 1px solid var(--border); }}
  tr.best td {{ color: var(--yellow); font-weight: 600; }}
  .baseline-row td {{ color: var(--muted); font-style: italic; }}
</style>
</head>
<body>

<h1>Loto 7 — Backtest Report</h1>
<p class="subtitle">Walk-forward evaluation &middot; Draws #{DATA[0]['s']}&ndash;#{DATA[-1]['s']} &middot; {T} draws &middot; 5 methods &middot; 7 picks each</p>

<div class="note">
  Starter set of 5 methods (of Loto6's eventual 16-method roster), adapted for Loto7's
  7-from-37 + 2-bonus-number structure. Each method predicts using only draws strictly
  before the target draw (no lookahead). Fixed at K=7 picks for this first pass &mdash;
  a pick-count toggle can be added once more methods are implemented.
</div>

<div class="cards">
'''

for mi in range(N_METHODS):
    is_best = mi == best_method_idx
    html += f'''  <div class="card{' best' if is_best else ''}" data-mi="{mi}">
    <div class="card-name">{METHODS[mi]}{' ★ best' if is_best else ''}</div>
    <div class="card-avg">{avg_hits[mi]}<span class="unit">avg hits / 7</span></div>
    <div class="card-sub">Best draw: {best_hits[mi]} hits &middot; Bonus hit: {bonus_pct[mi]}%</div>
  </div>
'''

html += '''</div>

<div class="chart-wrap"><canvas id="distChart" height="110"></canvas></div>

<div class="chart-wrap">
<table>
  <thead>
    <tr><th>Method</th><th>Avg Hits</th><th>vs Random</th><th>Best Draw</th><th>Bonus Hit %</th></tr>
  </thead>
  <tbody>
'''

for mi in range(N_METHODS):
    is_best = mi == best_method_idx
    lift = round(avg_hits[mi] / random_avg, 2)
    html += f'''    <tr class="{'best' if is_best else ''}"><td>{METHODS[mi]}</td><td>{avg_hits[mi]}</td><td>{lift}&times;</td><td>{best_hits[mi]}</td><td>{bonus_pct[mi]}%</td></tr>
'''

html += f'''    <tr class="baseline-row"><td>Random baseline</td><td>{random_avg:.4f}</td><td>1.00&times;</td><td>&mdash;</td><td>{random_bonus_pct}%</td></tr>
  </tbody>
</table>
</div>

<script>
const METHODS = {json.dumps(METHODS)};
const COLORS  = {json.dumps(COLORS)};
const HIT_COUNTS = {json.dumps(hit_counts)};
const RANDOM_AVG = {random_avg};

const HP = (k) => {{
  // hypergeometric P(k matches | 7 picks, 7 actual winners, 37 total)
  const C = (n,r) => {{ if(r<0||r>n) return 0; let x=1; for(let i=0;i<r;i++) x=x*(n-i)/(i+1); return x; }};
  return C(7,k)*C(30,7-k)/C(37,7);
}};
const randomDist = [0,1,2,3,4,5,6,7].map(k => HP(k)*{T});

new Chart(document.getElementById('distChart').getContext('2d'), {{
  type: 'bar',
  data: {{
    labels: ['0','1','2','3','4','5','6','7'],
    datasets: [
      ...METHODS.map((name,mi) => ({{
        label: name, data: HIT_COUNTS[mi],
        backgroundColor: COLORS[mi]+'bb', borderColor: COLORS[mi], borderWidth: 1
      }})),
      {{ label: 'Random baseline', data: randomDist,
        type: 'line', borderColor: '#fff', borderDash: [5,3],
        borderWidth: 2, pointRadius: 0, fill: false, tension: 0 }}
    ]
  }},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ labels: {{ color:'#94a3b8' }} }} }},
    scales: {{
      x: {{ ticks:{{color:'#94a3b8'}}, grid:{{color:'#334155'}},
           title:{{display:true, text:'Matches (out of 7)', color:'#94a3b8'}} }},
      y: {{ ticks:{{color:'#94a3b8'}}, grid:{{color:'#334155'}},
           title:{{display:true, text:'Count', color:'#94a3b8'}} }}
    }}
  }}
}});
</script>

</body>
</html>
'''

with open(HTML_OUT, 'w', encoding='utf-8') as f:
    f.write(html)
print(f"Wrote {HTML_OUT} ({len(html)//1024} KB)")
