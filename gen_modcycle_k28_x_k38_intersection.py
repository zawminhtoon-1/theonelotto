"""
gen_modcycle_k28_x_k38_intersection.py
--------------------------------------
Static report page for the Modular Cycle (K=28) x xoshiro K=38 seed
#692,809 intersection backtest over the last 100 draws. Mirrors the
K=38/K=35 5-seed intersection pages' structure, style, hit threshold
(3+ of 6), and hypergeometric proportionality baseline -- but additionally
tracks full 6/6 matches as a separate, distinctly-badged metric, since
that's the more interesting result for this particular pairing (2.44x
observed-vs-expected vs 1.05x for the 3+ threshold).

Reads modcycle_k28_x_k38_intersection_data.json, produced by
compute_modcycle_k28_x_k38_intersection.js (which extracts Modular
Cycle's real per-draw picks from public/backtest.html's embedded DATA
array plus its topKNums() logic -- there's no independent formula for
this method the way there is for xoshiro seeds, so it can't be
recomputed in pure Python the way the other intersection pages are).

Look-ahead-bias note: this pairing is a mix of two different kinds of
bias. The xoshiro seed (#692,809) was picked because it scored best on
a scan window (#1000-2129) that fully contains these same 100 backtested
draws -- same issue as the other intersection pages. Modular Cycle's
picks aren't seed-selected that way, but its predictions are trained on
data through the draw being predicted, so it isn't a clean held-out test
either. Both caveats are shown on the page.

Output: public/xoshiro_k38_x_modularcycle_k28_intersection.html
Run: node compute_modcycle_k28_x_k38_intersection.js
     python gen_modcycle_k28_x_k38_intersection.py
"""
import json
from math import comb

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
DATA_JSON = BASE + r"\modcycle_k28_x_k38_intersection_data.json"
HTML_OUT = BASE + r"\public\xoshiro_k38_x_modularcycle_k28_intersection.html"

FULL_UNIVERSE = comb(43, 6)

with open(DATA_JSON, encoding='utf-8') as f:
    payload = json.load(f)

meta = payload['meta']
summary = payload['summary']
rows_data = payload['rows']

K_MC = meta['K_MC']
K_XO = meta['K_XO']
XO_SEED = meta['XO_SEED']
N_BACKTEST_DRAWS = meta['N_BACKTEST_DRAWS']
draw_lo, draw_hi = meta['drawLo'], meta['drawHi']

n = summary['n']
avg_pool = summary['avgPool']
min_pool = summary['minPool']
max_pool = summary['maxPool']
median_pool = summary['medianPool']

hits3 = summary['hits3plus']
obs3_rate = summary['observed3plusRate']
exp3_rate = summary['expected3plusRate']
ratio3 = summary['ratio3plus']
lam3 = summary['lam3']
p3 = summary['p3']

hits6 = summary['hits6']
obs6_rate = summary['observed6Rate']
exp6_rate = summary['expected6Rate']
ratio6 = summary['ratio6']
lam6 = summary['lam6']
p6 = summary['p6']

print(f"Loaded {n} draws (#{draw_lo}-{draw_hi})")
print(f"Pool: min={min_pool} max={max_pool} avg={avg_pool:.2f} median={median_pool}")
print(f"3+/6: {hits3}/{n} ({obs3_rate*100:.1f}%) vs expected {exp3_rate*100:.2f}% -- {ratio3:.2f}x")
print(f"6/6:   {hits6}/{n} ({obs6_rate*100:.2f}%) vs expected {exp6_rate*100:.4f}% -- {ratio6:.2f}x")

# ── Render ────────────────────────────────────────────────────────────────
def num_badges(nums, matched=None, bonus=None):
    matched = matched or set()
    html = ""
    for n_ in nums:
        cls = "nb"
        if n_ in matched:
            cls += " nm"
        if bonus is not None and n_ == bonus:
            cls += " nb-bh"
        html += f'<span class="{cls}">{n_}</span>'
    return html

def match_badge(count):
    color = "#4ade80" if count >= 3 else ("#94a3b8" if count > 0 else "#475569")
    return f'<span style="font-weight:700;color:{color}">{count}</span>/6'

def hit_badge(row):
    parts = []
    if row['hit3plus']:
        parts.append('<span class="hit-yes">&#10003; HIT</span>')
    else:
        parts.append('<span class="hit-no">&mdash;</span>')
    if row['hit6']:
        parts.append('<span class="six-badge">&#9733; 6/6</span>')
    return ' '.join(parts)

def render_table_rows(rows):
    html = ""
    for row in reversed(rows):  # newest first
        matched = set(row['actual']) & set(row['inter'])
        row_cls = []
        if row['hit6']:
            row_cls.append('six-row')
        elif row['hit3plus']:
            row_cls.append('hit-row')
        actual_html = num_badges(row['actual'], matched=matched) + f'<span class="nb nb-b">{row["bonus"]}</span>'
        inter_html = num_badges(row['inter'], matched=matched)
        html += f"""<tr class="{' '.join(row_cls)}">
  <td class="tc">{row['d'][:10]}</td>
  <td class="tc">{row['s']}</td>
  <td class="tc">{hit_badge(row)}</td>
  <td class="tc">{match_badge(row['matchCount'])}</td>
  <td class="nowrap">{actual_html}</td>
  <td class="tc">{row['poolSize']}</td>
  <td class="inter-cell">{inter_html}</td>
</tr>"""
    return html

table_rows_html = render_table_rows(rows_data)

page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Modular Cycle x K=38 Intersection Backtest — Loto 6</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0a0f1e;color:#e2e8f0;font-family:system-ui,sans-serif;padding-top:60px;min-height:100vh}}
.wrap{{max-width:1300px;margin:0 auto;padding:24px 16px}}
h1{{font-size:1.4rem;font-weight:700;color:#f1f5f9;margin-bottom:4px}}
.subtitle{{font-size:.85rem;color:#64748b;margin-bottom:20px}}

.note{{background:#0d1526;border:1px solid #1e293b;border-radius:10px;padding:14px 18px;
  font-size:.8rem;color:#94a3b8;margin-bottom:20px;line-height:1.6}}
.note.warn{{border-color:#f59e0b55;background:#1c1206}}
.note.warn strong{{color:#fbbf24}}
.note.info{{border-color:#38bdf855}}
.note.info strong{{color:#7dd3fc}}
.note.gold{{border-color:#eab30855;background:#1c1706}}
.note.gold strong{{color:#facc15}}
.note p+p{{margin-top:8px}}

.stats-row{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px}}
.stat-card{{background:#0d1526;border:1px solid #1e293b;border-radius:10px;padding:14px 18px;flex:1;min-width:170px}}
.stat-card.gold{{border-color:#eab30866;background:#1a1608}}
.stat-card .lbl{{font-size:.72rem;color:#64748b;text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px}}
.stat-card .val{{font-size:1.4rem;font-weight:700;color:#f1f5f9}}
.stat-card.gold .val{{color:#facc15}}
.stat-card .sub{{font-size:.78rem;color:#94a3b8;margin-top:2px}}

.section{{background:#0d1526;border:1px solid #1e293b;border-radius:12px;padding:20px;margin-bottom:24px}}
.section h2{{font-size:1rem;font-weight:700;color:#f1f5f9;margin-bottom:4px}}
.section .desc{{font-size:.8rem;color:#64748b;margin-bottom:16px}}

.tbl-wrap{{overflow-x:auto;border-radius:10px;border:1px solid #1e293b}}
table{{width:100%;border-collapse:collapse;font-size:.8rem}}
thead th{{background:#0d1526;padding:9px 12px;text-align:right;color:#94a3b8;
  font-weight:600;font-size:.72rem;text-transform:uppercase;letter-spacing:.05em;
  white-space:nowrap;border-bottom:1px solid #1e293b}}
thead th.tc{{text-align:center}}
tbody tr{{border-bottom:1px solid #1e293b}}
tbody tr:hover{{background:#111827}}
tbody tr.hit-row{{background:#0d2416}}
tbody tr.hit-row:hover{{background:#123420}}
tbody tr.six-row{{background:#241c06}}
tbody tr.six-row:hover{{background:#332707}}
tbody td{{padding:8px 12px;text-align:right;color:#cbd5e1;vertical-align:middle}}
tbody td.tc{{text-align:center}}
tbody td.nowrap{{white-space:nowrap}}
tbody td.inter-cell{{max-width:520px;white-space:normal}}

.hit-yes{{color:#4ade80;font-weight:700;font-size:.76rem}}
.hit-no{{color:#475569;font-size:.76rem}}
.six-badge{{display:inline-block;color:#0a0f1e;background:#facc15;font-weight:800;font-size:.68rem;
  padding:2px 6px;border-radius:5px;margin-left:4px;white-space:nowrap}}

.nb{{display:inline-flex;align-items:center;justify-content:center;width:23px;height:23px;border-radius:50%;background:#1e293b;color:#64748b;font-size:.64rem;font-weight:700;margin:1px}}
.nm{{background:#14532d;color:#86efac}}
.nb-b{{background:#451a03;color:#fde68a;border:1px solid #92400e}}
.nb-bh{{background:#7c2d12;color:#fed7aa}}

.footer{{margin-top:28px;font-size:.78rem;color:#475569;padding-bottom:20px;line-height:1.6}}
</style>
</head>
<body>
<script src="/site-nav.js"></script>

<div class="wrap">
  <h1>&#9986;&#65039; Modular Cycle (K=28) &times; K=38 Seed #{XO_SEED:,} Intersection</h1>
  <p class="subtitle">Modular Cycle backtest.html method (K={K_MC}) &times; xoshiro K=38 seed #{XO_SEED:,} &middot;
  intersection pool per draw &middot; last {N_BACKTEST_DRAWS} draws (#{draw_lo}&ndash;{draw_hi})</p>

  <div class="note info">
    <p><strong>Two different pick sources, intersected.</strong> Modular Cycle is one of the 16 trained-model methods
    on <a href="/backtest.html" style="color:#7dd3fc">backtest.html</a> (its own K=28 pick, padded/trimmed via the
    same cross-method-consensus <code>topKNums()</code> logic that page uses); the other side is xoshiro256**
    seed #{XO_SEED:,} (the top-ranked K=38 seed by hit6b), computed fresh per draw from that draw's own
    draw_serial. Every row recomputes both picks and intersects them for that specific draw.</p>
    <p><strong>Hit definition: 3+ of 6 (partial match)</strong> for the main Hit column, same threshold as the
    K=38/K=35 5-seed intersection pages. A separate <span class="six-badge">&#9733; 6/6</span> badge marks full
    6-of-6 matches specifically, since that turned out to be the more interesting result here: only
    {ratio3:.2f}&times; expected at the 3+ threshold, but {ratio6:.2f}&times; expected for a full 6/6 (see stats
    below).</p>
  </div>

  <div class="note warn">
    <p><strong>Not a clean out-of-sample test, for two separate reasons.</strong> The xoshiro seed was selected
    because it scored best on a scan window (#1000&ndash;2129) that fully contains these same 100 backtested draws
    &mdash; the same look-ahead-bias issue as the other intersection pages. Separately, Modular Cycle's own
    predictions are trained on data through the draw being predicted, so its side of the pairing isn't a clean
    held-out test either, even though it isn't seed-selected the same way. Read the stats below with both of
    those in mind.</p>
    <p>Rough Poisson checks: P(&ge;{hits3} at 3+ threshold | &lambda;={lam3:.2f}) = {p3*100:.2f}%;
    P(&ge;{hits6} at full 6/6 | &lambda;={lam6:.4f}) = {p6*100:.2f}%.</p>
  </div>

  <div class="stats-row">
    <div class="stat-card">
      <div class="lbl">Intersection pool size</div>
      <div class="val">{avg_pool:.2f} avg</div>
      <div class="sub">range {min_pool}&ndash;{max_pool}, median {median_pool}</div>
    </div>
    <div class="stat-card">
      <div class="lbl">3+ of 6 hits</div>
      <div class="val">{hits3} / {n}</div>
      <div class="sub">{obs3_rate*100:.1f}% observed vs {exp3_rate*100:.2f}% expected</div>
    </div>
    <div class="stat-card">
      <div class="lbl">3+ of 6: observed vs expected</div>
      <div class="val">{ratio3:.2f}&times;</div>
      <div class="sub">hypergeometric baseline, per-draw pool size</div>
    </div>
  </div>

  <div class="stats-row">
    <div class="stat-card gold">
      <div class="lbl">&#9733; Full 6/6 hits</div>
      <div class="val">{hits6} / {n}</div>
      <div class="sub">{obs6_rate*100:.2f}% observed vs {exp6_rate*100:.4f}% expected</div>
    </div>
    <div class="stat-card gold">
      <div class="lbl">&#9733; 6/6: observed vs expected</div>
      <div class="val">{ratio6:.2f}&times;</div>
      <div class="sub">hypergeometric baseline, per-draw pool size</div>
    </div>
    <div class="stat-card gold">
      <div class="lbl">&#9733; Expected full-6 count</div>
      <div class="val">{lam6:.2f}</div>
      <div class="sub">sum of per-draw C(pool,6)/C(43,6)</div>
    </div>
  </div>

  <div class="note">
    <p>No next-upcoming-draw reference pool is shown on this page (unlike the K=38/K=35 5-seed pages): Modular
    Cycle's picks come from <code>backtest.html</code>'s precomputed prediction data, which only covers historical
    draws with known outcomes attached &mdash; there's no live client-side implementation of its training/prediction
    logic to compute a pick for a not-yet-drawn serial the way the pure-formula xoshiro seeds can.</p>
  </div>

  <div class="section">
    <h2>Per-draw detail &mdash; last {N_BACKTEST_DRAWS} draws</h2>
    <p class="desc">Newest first. Each row recomputes Modular Cycle's K={K_MC} pick and xoshiro seed #{XO_SEED:,}'s
    K={K_XO} pick using that draw's own draw_serial, intersects them, and counts how many of the 6 winning numbers
    fall inside. Hit = 3+ of 6; <span class="six-badge">&#9733; 6/6</span> marks a full match. Matched numbers
    shown in green in both number columns.</p>
    <div class="tbl-wrap">
      <table>
        <thead><tr>
          <th class="tc">Date</th><th class="tc">Draw</th><th class="tc">Hit</th><th class="tc">Match count</th>
          <th>Actual (6) + bonus</th><th class="tc">Pool size</th><th>Intersection numbers</th>
        </tr></thead>
        <tbody>{table_rows_html}</tbody>
      </table>
    </div>
  </div>

  <p class="footer">
    Modular Cycle: one of 16 backtested prediction methods on <a href="/backtest.html" style="color:#64748b">backtest.html</a>,
    K={K_MC} picks, trimmed/padded via cross-method-consensus <code>topKNums()</code>.<br>
    Xoshiro256** (seeded via SplitMix64): picks = partial Fisher-Yates(range(1,44), {K_XO}) with combined seed =
    seed&times;10&#8311; + draw_serial. Each (seed, draw) pair independent and deterministic.<br>
    Intersection pool = numbers appearing in BOTH picks for that specific draw. Hit = at least 3 of the actual
    6-number winner's numbers are members of that draw's intersection pool; the gold badge marks a full 6-of-6.<br>
    Expected-under-chance baselines computed per-draw via the hypergeometric distribution (population=43,
    success-states=that draw's pool size, draws=6), averaged across the {N_BACKTEST_DRAWS} draws.<br>
    Data: Modular Cycle picks extracted from <code>backtest.html</code>'s embedded prediction data; draw records
    and xoshiro seed ranking sourced the same way as the other xoshiro pages on this site.<br>
    Formula-based only &middot; Not financial advice &middot; Loto 6 is random.
  </p>
</div>

</body>
</html>"""

with open(HTML_OUT, 'w', encoding='utf-8') as f:
    f.write(page)
print(f"\nWrote {HTML_OUT} ({len(page)//1024} KB)")
