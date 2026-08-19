"""
gen_next_relation.py
Strategy: Next-Draw Relation
For each number n in draw t-1, build a conditional distribution:
  what numbers tend to appear in draw t when n appeared in draw t-1?
Score all 43 candidates by summing those distributions across the
latest draw's numbers. Pick top 28.
Backtest: last 1000 draws, match against 7 numbers (6 main + bonus).
"""
import psycopg2, json, os, statistics

DB_URL = os.environ["DATABASE_URL"]

N_PICKS = 7
BT_DRAWS = 1000

conn = psycopg2.connect(DB_URL)
cur = conn.cursor()
cur.execute("""
    SELECT draw_serial, draw_date, num1, num2, num3, num4, num5, num6, bonus
    FROM loto6_results ORDER BY draw_serial
""")
rows = cur.fetchall()
conn.close()

draws = []
for r in rows:
    nums = sorted([r[2], r[3], r[4], r[5], r[6], r[7]])
    draws.append({
        "s": r[0],
        "d": str(r[1])[:10] if r[1] else "",
        "n": nums,
        "b": r[8],
        "all": set(nums + [r[8]])
    })

N = len(draws)
test_start = max(0, N - BT_DRAWS)

# next_freq[n][f] = times f appeared in draw t when n appeared in draw t-1
next_freq   = [[0]*43 for _ in range(43)]
appearances = [0]*43  # how many times each number had a following draw

def get_scores(src_nums):
    scores = [0.0]*43
    for n in src_nums:
        ni = n - 1
        if appearances[ni] > 0:
            for fi in range(43):
                scores[fi] += next_freq[ni][fi] / appearances[ni]
    return scores

def top_picks(scores, n_picks):
    ranked = sorted(range(43), key=lambda i: -scores[i])
    return [i+1 for i in ranked[:n_picks]]

# Walk-forward backtest
# At draw i: model knows pairs (0,1)...(i-2,i-1). Predict draw i using draw i-1 as input.
# Then update model with pair (i-1, i).
bt_results = []
match_counts = []
print(f"Walk-forward backtest: last {BT_DRAWS} draws, N_PICKS={N_PICKS}")

for i in range(1, N):
    if i >= test_start:
        src = draws[i-1]["n"]
        scores = get_scores(src)
        pred = top_picks(scores, N_PICKS)
        hits = set(pred) & draws[i]["all"]
        mc = len(hits)
        match_counts.append(mc)
        bt_results.append({
            "s": draws[i]["s"], "d": draws[i]["d"],
            "actual": sorted(draws[i]["all"]),
            "hitNums": sorted(hits),
            "matches": mc,
            "pred": pred
        })

    # Update model
    prev_n = draws[i-1]["n"]
    curr_n = draws[i]["n"]
    for n in prev_n:
        appearances[n-1] += 1
        for f in curr_n:
            next_freq[n-1][f-1] += 1

# Next draw prediction (using latest draw as input, full history)
next_serial = draws[-1]["s"] + 1
src_latest = draws[-1]["n"]
next_scores = get_scores(src_latest)
next_pred = top_picks(next_scores, N_PICKS)
# Top score for relative display
max_score = max(next_scores) if max(next_scores) > 0 else 1.0
score_pct = {str(n): round(next_scores[n-1] / max_score * 100) for n in next_pred}

rand_baseline = N_PICKS * 7 / 43
avg = statistics.mean(match_counts)
c0  = sum(1 for m in match_counts if m == 0)
c3  = sum(1 for m in match_counts if m >= 3)
c4  = sum(1 for m in match_counts if m >= 4)
c5  = sum(1 for m in match_counts if m >= 5)
c6  = sum(1 for m in match_counts if m >= 6)
c7  = sum(1 for m in match_counts if m >= 7)

print(f"Avg: {avg:.4f}  rand: {rand_baseline:.4f}  lift: {(avg/rand_baseline-1)*100:+.1f}%")
print(f"6+ hits: {c6}/{BT_DRAWS}  5+: {c5}  4+: {c4}  7+: {c7}")

# Score tiers for coloring balls
def score_tier(n):
    s = next_scores[n-1]
    if s >= max_score * 0.7: return 2
    if s >= max_score * 0.4: return 1
    return 0

PAGE_DATA = {
    "nPicks": N_PICKS,
    "latestSerial": draws[-1]["s"],
    "latestDate": draws[-1]["d"],
    "srcNums": src_latest,
    "nextSerial": next_serial,
    "prediction": next_pred,
    "scorePct": score_pct,
    "freqTier": {str(n): score_tier(n) for n in next_pred},
    "btDraws": BT_DRAWS,
    "avgMatches": round(avg, 2),
    "randBaseline": round(rand_baseline, 2),
    "liftPct": round((avg / rand_baseline - 1) * 100, 1),
    "cnt0": c0,
    "cnt3plus": c3, "cnt4plus": c4, "cnt5plus": c5, "cnt6plus": c6, "cnt7plus": c7,
    "btResults": [
        {"s": r["s"], "d": r["d"], "actual": r["actual"],
         "hitNums": r["hitNums"], "matches": r["matches"], "pred": r["pred"]}
        for r in reversed(bt_results[-100:])
    ]
}

data_json = json.dumps(PAGE_DATA, ensure_ascii=False)
TIER_COLORS = ["#38bdf8", "#a78bfa", "#fbbf24"]
TIER_LABELS = ["Lower score", "Mid score", "High score"]

HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Next-Draw Relation Predict — Loto 6</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:system-ui,sans-serif;background:#0f172a;color:#e2e8f0;min-height:100vh;padding-top:60px}}
main{{max-width:1100px;margin:0 auto;padding:24px 20px}}
h1{{font-size:1.4rem;font-weight:800;color:#f1f5f9;margin-bottom:4px}}
.subtitle{{font-size:.85rem;color:#64748b;margin-bottom:20px}}
.sec{{margin-bottom:28px}}
.sec-title{{font-size:.78rem;font-weight:700;color:#94a3b8;text-transform:uppercase;
  letter-spacing:.06em;margin-bottom:12px}}
.method-card{{background:#1e293b;border-radius:12px;padding:16px 20px;margin-bottom:20px;
  border-left:4px solid #38bdf8}}
.method-card .mc-title{{font-size:.78rem;font-weight:700;color:#38bdf8;
  text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px}}
.method-card .mc-body{{font-size:.85rem;color:#94a3b8;line-height:1.6}}
.src-balls{{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}}
.src-ball{{width:34px;height:34px;border-radius:50%;display:flex;align-items:center;
  justify-content:center;font-size:.82rem;font-weight:700;background:#334155;color:#f1f5f9;
  border:2px solid #38bdf8}}
.stats-strip{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin-bottom:24px}}
.stat-card{{background:#1e293b;border-radius:10px;padding:14px 16px;text-align:center}}
.stat-card .sv{{font-size:1.6rem;font-weight:800}}
.stat-card .sl{{font-size:.72rem;color:#64748b;margin-top:2px}}
.stat-card .sd{{font-size:.78rem;margin-top:4px;color:#64748b}}
.legend{{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:12px}}
.legend-item{{display:flex;align-items:center;gap:6px;font-size:.78rem;color:#94a3b8}}
.legend-dot{{width:12px;height:12px;border-radius:50%}}
.ball-grid{{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:16px}}
.ball{{width:44px;height:44px;border-radius:50%;display:flex;align-items:center;
  justify-content:center;font-size:.9rem;font-weight:800;color:#fff;
  border:2px solid rgba(255,255,255,.15);cursor:default;transition:.12s}}
.ball:hover{{transform:scale(1.08)}}
.bt-table{{width:100%;border-collapse:collapse;font-size:.78rem}}
.bt-table th{{background:#0f172a;color:#64748b;padding:7px 10px;text-align:left;
  border-bottom:2px solid #1e293b;font-weight:600}}
.bt-table td{{padding:6px 10px;border-bottom:1px solid #1a2744}}
.bt-table tr:hover td{{background:#1a2234}}
.match-badge{{display:inline-flex;align-items:center;justify-content:center;
  width:24px;height:24px;border-radius:6px;font-weight:700;font-size:.8rem}}
.m-low{{background:#1e3a5f;color:#60a5fa}}
.m-mid{{background:#1a4731;color:#4ade80}}
.m-high{{background:#4a1d96;color:#c4b5fd}}
.m-max{{background:#78350f;color:#fbbf24}}
.hit-ball{{width:28px;height:28px;border-radius:50%;display:inline-flex;align-items:center;
  justify-content:center;font-size:.72rem;font-weight:800;margin:1px}}
.pred-mini{{width:26px;height:26px;border-radius:50%;display:inline-flex;align-items:center;
  justify-content:center;font-size:.68rem;font-weight:700;margin:1px;flex-shrink:0}}
.pm-hit{{background:#dc2626;color:#fff;box-shadow:0 0 0 2px #f87171}}
.pm-selected{{background:#e2e8f0;color:#0f172a}}
.pred-row td{{background:#0c1420;border-bottom:2px solid #1e293b}}
</style>
</head>
<body>
<script src="/site-nav.js"></script>
<main>
  <h1>&#128279; Next-Draw Relation Predict</h1>
  <p class="subtitle">Follower frequency model &middot; {N_PICKS} picks &middot; {BT_DRAWS}-draw backtest</p>

  <div class="method-card">
    <div class="mc-title">Method</div>
    <div class="mc-body">
      For each number that appeared in the previous draw, we track what numbers historically
      followed it in the next draw. We sum those conditional probabilities across all
      <span id="srcCount"></span> numbers in the latest draw to score every candidate,
      then pick the top {N_PICKS} highest-scoring numbers.
    </div>
    <div class="src-balls" id="srcBalls"></div>
  </div>

  <div class="sec">
    <div class="sec-title">Backtest Performance &mdash; last {BT_DRAWS} draws</div>
    <div class="stats-strip" id="statsStrip"></div>
  </div>

  <div class="sec">
    <div class="sec-title">Predicted {N_PICKS} Numbers for Draw #<span id="nextS"></span></div>
    <div class="legend" id="legend"></div>
    <div class="ball-grid" id="balls"></div>
  </div>

  <div class="sec">
    <div class="sec-title">Backtest &mdash; Last 100 Draws (newest first)</div>
    <table class="bt-table">
      <thead><tr>
        <th>Draw</th><th>Date</th><th>Actual Numbers</th><th>Hits</th><th></th>
      </tr></thead>
      <tbody id="btBody"></tbody>
    </table>
  </div>
</main>
<script>
const D = {data_json};
const TIER_COLORS = {json.dumps(TIER_COLORS)};
const TIER_LABELS = {json.dumps(TIER_LABELS)};

document.getElementById('nextS').textContent = D.nextSerial;
document.getElementById('srcCount').textContent = D.srcNums.length;

D.srcNums.forEach(n => {{
  document.getElementById('srcBalls').innerHTML +=
    `<div class="src-ball">${{n}}</div>`;
}});

const statsData = [
  {{label:'6+ hit draws', val:D.cnt6plus, sub:`5+: ${{D.cnt5plus}}  4+: ${{D.cnt4plus}}`, color:'#fbbf24'}},
  {{label:'0 hit draws',  val:D.cnt0, sub:`out of ${{D.btDraws}}`, color:'#fb923c'}},
  {{label:'Avg matches',  val:D.avgMatches.toFixed(2),
    sub:`Random: ${{D.randBaseline.toFixed(2)}}`,
    color: D.avgMatches >= D.randBaseline ? '#4ade80' : '#fb923c'}},
  {{label:'Lift vs random', val:(D.liftPct>=0?'+':'')+D.liftPct+'%', sub:'vs baseline',
    color: D.liftPct>=0?'#4ade80':'#fb923c'}},
];
const strip = document.getElementById('statsStrip');
statsData.forEach(s => {{
  strip.innerHTML += `<div class="stat-card">
    <div class="sv" style="color:${{s.color}}">${{s.val}}</div>
    <div class="sl">${{s.label}}</div><div class="sd">${{s.sub}}</div></div>`;
}});

const leg = document.getElementById('legend');
TIER_LABELS.forEach((lbl,i) => {{
  leg.innerHTML += `<div class="legend-item">
    <div class="legend-dot" style="background:${{TIER_COLORS[i]}}"></div>${{lbl}}</div>`;
}});

D.prediction.forEach(n => {{
  const tier = D.freqTier[String(n)] || 0;
  document.getElementById('balls').innerHTML +=
    `<div class="ball" style="background:${{TIER_COLORS[tier]}}"
      title="Score: ${{D.scorePct[String(n)]}}%">${{n}}</div>`;
}});

const tbody = document.getElementById('btBody');
D.btResults.forEach(r => {{
  const m = r.matches;
  const cls = m>=7?'m-max':m>=6?'m-high':m>=5?'m-mid':'m-low';
  const hitSet = new Set(r.hitNums);
  const actual = r.actual.map(n => {{
    const isHit = hitSet.has(n);
    return `<span class="hit-ball" style="background:${{isHit?'#4ade80':'#1e293b'}};color:${{isHit?'#000':'#94a3b8'}}">${{n}}</span>`;
  }}).join('');
  const predBalls = (r.pred||[]).map(n => {{
    const isHit = hitSet.has(n);
    const tier = D.freqTier[String(n)] || 0;
    const cls2 = isHit ? 'pm-hit' : 'pm-selected';
    return `<span class="pred-mini ${{cls2}}">${{n}}</span>`;
  }}).join('');
  tbody.innerHTML += `
    <tr>
      <td style="color:#64748b">#${{r.s}}</td>
      <td style="color:#475569">${{r.d}}</td>
      <td>${{actual}}</td>
      <td>${{r.hitNums.join(', ')||'-'}}</td>
      <td><span class="match-badge ${{cls}}">${{m}}</span></td>
    </tr>
    <tr class="pred-row">
      <td colspan="5" style="padding:4px 10px 10px">
        <div style="font-size:.65rem;color:#475569;margin-bottom:3px">Predicted 28:</div>
        <div style="display:flex;flex-wrap:wrap;gap:3px">${{predBalls}}</div>
      </td>
    </tr>`;
}});
</script>
</body>
</html>"""

out = os.path.join(os.path.dirname(__file__), "public", "next_relation.html")
with open(out, "w", encoding="utf-8") as f:
    f.write(HTML)
print(f"Written: {out} ({len(HTML):,} bytes)")
