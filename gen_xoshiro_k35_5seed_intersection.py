"""
gen_xoshiro_k35_5seed_intersection.py
--------------------------------------
Static report page for the 5-seed K=35 xoshiro256** intersection backtest:
seeds 1,264,797 / -1,429,890 / 820,544 / -290,286 / 1,582,907 (the top 5
seeds from seed_hit_xoshiro_k35, ranked by hit6b desc, tiebreak hit6 desc,
tiebreak hit5 desc -- this is the first intersection-backtest page on the
site where the seed list includes negative seeds), against the last 100
actual draws (#2030-2129). Mirrors gen_xoshiro_k38_5seed_intersection.py
exactly, just K=35 and the seed list.

For each draw, all 5 seeds' K=35 picks are recomputed using THAT draw's own
draw_serial (xoshiro formula = seed*10_000_000 + draw_serial, so each draw
gets its own version of each seed's pool), intersected, and the actual
6-number winner is checked against that intersection pool.

Hit definition: PARTIAL match, threshold=3 -- a draw counts as a hit if AT
LEAST 3 of its 6 winning numbers fall inside that draw's intersection pool.
The per-draw match count (0-6) is shown as its own column.

Proportionality baseline: since pool size varies per draw, the "expected
under pure chance" rate is computed per-draw via the hypergeometric
distribution -- P(X>=3) where X = count of a random 6-number draw's
numbers landing in a population-43, success-states-m pool, m = that draw's
actual intersection pool size -- then averaged across the 100 draws.

Explicit look-ahead-bias caveat included in the page itself: the K=35 scan
window is #1000-2129 (after the incremental extension), which fully
contains the #2030-2129 backtest range -- these 5 seeds were selected
because they scored best across a window that includes every draw being
"backtested" here, so this is NOT a held-out/out-of-sample test.

Output: public/xoshiro_k35_5seed_intersection.html
Run: python gen_xoshiro_k35_5seed_intersection.py
"""
import re, os, math, statistics
from math import comb

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
ENV_LOCAL = BASE + r"\.env.local"
HTML_OUT = BASE + r"\public\xoshiro_k35_5seed_intersection.html"

LOTO6_MAX = 43
K_PICKS = 35
TABLE = "seed_hit_xoshiro_k35"
MASK64 = 0xFFFFFFFFFFFFFFFF
FULL_UNIVERSE = comb(43, 6)
SEEDS = [1264797, -1429890, 820544, -290286, 1582907]
N_BACKTEST_DRAWS = 100
HIT_THRESHOLD = 3  # of 6 winning numbers must land in the intersection pool

def xoshiro_predict(seed, draw_serial, k=K_PICKS, pool_max=LOTO6_MAX):
    combined = (seed * 10_000_000 + draw_serial) & MASK64
    z = combined & MASK64
    s = [0, 0, 0, 0]
    for i in range(4):
        z = (z + 0x9E3779B97F4A7C15) & MASK64
        zz = z
        zz = ((zz ^ (zz >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
        zz = ((zz ^ (zz >> 27)) * 0x94D049BB133111EB) & MASK64
        zz = zz ^ (zz >> 31)
        s[i] = zz
    def rotl(x, kk):
        x &= MASK64
        return ((x << kk) | (x >> (64 - kk))) & MASK64
    arr = list(range(1, pool_max + 1))
    n = len(arr)
    for i in range(n - 1, n - 1 - k, -1):
        result = (rotl((s[1] * 5) & MASK64, 7) * 9) & MASK64
        t = (s[1] << 17) & MASK64
        s[2] ^= s[0]; s[3] ^= s[1]; s[1] ^= s[2]; s[0] ^= s[3]
        s[2] ^= t
        s[3] = rotl(s[3], 45)
        j = result % (i + 1)
        arr[i], arr[j] = arr[j], arr[i]
    return set(arr[n - k:])

def hyper_pmf(k, pop, success, draws):
    """P(exactly k successes) drawing `draws` from `pop` with `success` marked."""
    if k > success or k > draws or (draws - k) > (pop - success):
        return 0.0
    return comb(success, k) * comb(pop - success, draws - k) / comb(pop, draws)

def hyper_p_at_least(threshold, pop, success, draws):
    """P(X >= threshold), X ~ Hypergeometric(pop, success, draws)."""
    return 1 - sum(hyper_pmf(k, pop, success, draws) for k in range(threshold))

# ── Confirm the 5 seeds are actually the current top-5 (self-check) ─────────
import sqlite3
DB_PATH = BASE + r"\loto6_local.db"
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
cur.execute(f"""SELECT seed, hit6b_count, hit6_count, hit5_count FROM {TABLE}
                ORDER BY hit6b_count DESC, hit6_count DESC, hit5_count DESC, seed ASC LIMIT 5""")
top5_rows = cur.fetchall()
conn.close()
top5_seeds = [r[0] for r in top5_rows]
if top5_seeds != SEEDS:
    raise SystemExit(f"Top-5 seeds in DB {top5_seeds} do not match hardcoded SEEDS {SEEDS} -- rankings changed, update SEEDS.")
seed_stats = {r[0]: {'hit6b': r[1], 'hit6': r[2], 'hit5': r[3]} for r in top5_rows}
print(f"Confirmed top-5 K=35 seeds match: {SEEDS}")

# ── Load draws from production DB ────────────────────────────────────────────
if 'DATABASE_URL' not in os.environ:
    with open(ENV_LOCAL, encoding='utf-8') as f:
        env_text = f.read()
    m = re.search(r'DATABASE_URL=(.+)', env_text)
    os.environ['DATABASE_URL'] = m.group(1).strip()
import psycopg2
pg = psycopg2.connect(os.environ['DATABASE_URL'])
pgcur = pg.cursor()
pgcur.execute("SELECT MAX(draw_serial) FROM loto6_results")
max_serial = pgcur.fetchone()[0]
draw_lo, draw_hi = max_serial - N_BACKTEST_DRAWS + 1, max_serial
pgcur.execute(
    "SELECT draw_serial, draw_date, num1,num2,num3,num4,num5,num6, bonus "
    "FROM loto6_results WHERE draw_serial BETWEEN %s AND %s ORDER BY draw_serial",
    (draw_lo, draw_hi),
)
pg_rows = pgcur.fetchall()
pg.close()
if len(pg_rows) != N_BACKTEST_DRAWS:
    raise SystemExit(f"Expected {N_BACKTEST_DRAWS} draws, got {len(pg_rows)}")
print(f"Loaded {len(pg_rows)} draws (#{draw_lo}-{draw_hi}) for the backtest.")

# ── Also compute the next-upcoming-draw intersection (fixed reference, not
# part of the backtest loop) for the page header. ───────────────────────────
next_draw = max_serial + 1
next_picks = {s: xoshiro_predict(s, next_draw) for s in SEEDS}
next_intersection = sorted(set.intersection(*next_picks.values()))
next_combo_count = comb(len(next_intersection), 6) if len(next_intersection) >= 6 else 0

# ── Backtest ──────────────────────────────────────────────────────────────
rows_out = []
pool_sizes = []
match_counts = []
per_draw_expected_p = []
hits = 0
for r in pg_rows:
    serial, date, n1, n2, n3, n4, n5, n6, bonus = r
    actual = sorted([n1, n2, n3, n4, n5, n6])
    actual_set = set(actual)
    picks_per_seed = [xoshiro_predict(s, serial) for s in SEEDS]
    inter = sorted(set.intersection(*picks_per_seed))
    inter_set = set(inter)
    match_count = len(actual_set & inter_set)
    is_hit = match_count >= HIT_THRESHOLD
    if is_hit:
        hits += 1
    pool_sizes.append(len(inter))
    match_counts.append(match_count)
    per_draw_expected_p.append(hyper_p_at_least(HIT_THRESHOLD, LOTO6_MAX, len(inter), 6))
    rows_out.append({
        's': serial, 'd': date.isoformat(), 'actual': actual, 'bonus': bonus,
        'hit': is_hit, 'poolSize': len(inter), 'inter': inter, 'matchCount': match_count,
    })

avg_pool_shared = statistics.mean(pool_sizes)
median_pool_shared = statistics.median(pool_sizes)
min_pool_shared = min(pool_sizes)
max_pool_shared = max(pool_sizes)
avg_match_count = statistics.mean(match_counts)

observed_rate = hits / N_BACKTEST_DRAWS
expected_rate = statistics.mean(per_draw_expected_p)  # per-draw hypergeometric P(X>=3), averaged
ratio = observed_rate / expected_rate if expected_rate > 0 else float('nan')

# rough Poisson tail P(X >= hits | lambda = expected count), using the
# hypergeometric-derived expected rate as the Poisson rate parameter.
lam = expected_rate * N_BACKTEST_DRAWS
def poisson_pmf(k, lam):
    return math.exp(-lam) * lam**k / math.factorial(k)
p_le = sum(poisson_pmf(k, lam) for k in range(hits))
p_ge_hits = 1 - p_le

print(f"\nHits (>= {HIT_THRESHOLD} of 6 in pool): {hits}/{N_BACKTEST_DRAWS} ({observed_rate*100:.1f}%)")
print(f"Avg pool size: {avg_pool_shared:.2f} shared numbers, avg match count: {avg_match_count:.2f}")
print(f"Expected rate (hypergeometric P(X>={HIT_THRESHOLD}), per-draw pool size, averaged): {expected_rate*100:.2f}%")
print(f"Observed/expected ratio: {ratio:.2f}x  (Poisson P(X>={hits}|lambda={lam:.2f}) = {p_ge_hits*100:.2f}%)")

# ── Render ────────────────────────────────────────────────────────────────
def num_badges(nums, matched=None, bonus=None):
    matched = matched or set()
    html = ""
    for n in nums:
        cls = "nb"
        if n in matched:
            cls += " nm"
        if bonus is not None and n == bonus:
            cls += " nb-bh"
        html += f'<span class="{cls}">{n}</span>'
    return html

def match_badge(n):
    color = "#4ade80" if n >= HIT_THRESHOLD else ("#94a3b8" if n > 0 else "#475569")
    return f'<span style="font-weight:700;color:{color}">{n}</span>/6'

def render_table_rows(rows):
    html = ""
    for row in reversed(rows):  # newest first
        matched = set(row['actual']) & set(row['inter'])
        hit_badge = '<span class="hit-yes">✔ HIT</span>' if row['hit'] else '<span class="hit-no">—</span>'
        row_cls = 'hit-row' if row['hit'] else ''
        actual_html = num_badges(row['actual'], matched=matched) + f'<span class="nb nb-b">{row["bonus"]}</span>'
        inter_html = num_badges(row['inter'], matched=matched)
        html += f"""<tr class="{row_cls}">
  <td class="tc">{row['d']}</td>
  <td class="tc">{row['s']}</td>
  <td class="tc">{hit_badge}</td>
  <td class="tc">{match_badge(row['matchCount'])}</td>
  <td class="nowrap">{actual_html}</td>
  <td class="tc">{row['poolSize']}</td>
  <td class="inter-cell">{inter_html}</td>
</tr>"""
    return html

table_rows_html = render_table_rows(rows_out)
seed_rows_html = "".join(
    f'<tr><td class="tc">{rank}</td><td class="tc">{s:,}</td>'
    f'<td class="tr">{seed_stats[s]["hit6b"]}</td><td class="tr">{seed_stats[s]["hit6"]}</td>'
    f'<td class="tr">{seed_stats[s]["hit5"]}</td></tr>'
    for rank, s in enumerate(SEEDS, 1)
)
next_inter_html = num_badges(next_intersection)
seeds_display = ", ".join(f"{s:,}" for s in SEEDS)

page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>K=35 5-Seed Intersection Backtest — Loto 6</title>
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
.note p+p{{margin-top:8px}}

.stats-row{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:24px}}
.stat-card{{background:#0d1526;border:1px solid #1e293b;border-radius:10px;padding:14px 18px;flex:1;min-width:170px}}
.stat-card .lbl{{font-size:.72rem;color:#64748b;text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px}}
.stat-card .val{{font-size:1.4rem;font-weight:700;color:#f1f5f9}}
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
tbody td{{padding:8px 12px;text-align:right;color:#cbd5e1;vertical-align:middle}}
tbody td.tc{{text-align:center}}
tbody td.tr{{text-align:right}}
tbody td.nowrap{{white-space:nowrap}}
tbody td.inter-cell{{max-width:520px;white-space:normal}}

.hit-yes{{color:#4ade80;font-weight:700;font-size:.76rem}}
.hit-no{{color:#475569;font-size:.76rem}}

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
  <h1>✂️ K=35 5-Seed Intersection Backtest</h1>
  <p class="subtitle">Top 5 K=35 seeds by hit6b &middot; intersection pool per draw &middot; last {N_BACKTEST_DRAWS} draws (#{draw_lo}&ndash;{draw_hi}) &middot; hit = {HIT_THRESHOLD}+ of 6 numbers in pool</p>

  <div class="note info">
    <p><strong>Hit definition: {HIT_THRESHOLD}+ of 6 (partial match).</strong> A draw counts as a hit if at least
    {HIT_THRESHOLD} of its 6 winning numbers land inside that draw's intersection pool -- not all 6. Every row below
    shows the exact match count out of 6, and matched numbers are highlighted green in both the actual-numbers and
    intersection-numbers columns. Mirrors the K=38 version of this page, same threshold and baseline.</p>
    <p>The K=35 top-5 by hit6b currently includes {sum(1 for s in SEEDS if s < 0)} negative seed(s) ({seeds_display})
    -- the K=35 scan is the only one on this site that covers negative seeds, and the xoshiro formula
    (seed&times;10,000,000 + draw_serial, masked to 64 bits) handles them correctly via Python's/JavaScript's
    two's-complement bitwise semantics, verified elsewhere on the site.</p>
  </div>

  <div class="note warn">
    <p><strong>Not an out-of-sample test.</strong> The K=35 scan window is #1000&ndash;2129 (after the incremental
    extension that folded in #2128/#2129), which fully contains the #{draw_lo}&ndash;{draw_hi} range backtested below.
    These 5 seeds were selected <em>because</em> they scored best across a window that includes every draw being
    tested here &mdash; a subset of the data a ranking was built from will trivially show elevated performance on
    that same subset. This is look-ahead bias, not evidence the xoshiro formula predicts anything. A genuine test
    would rank seeds using only draws before some cutoff and check hits only on draws after it, which no scan on
    this site currently does.</p>
    <p>A rough Poisson check still puts P(&ge;{hits} hits by pure chance | &lambda;={lam:.2f}) at only
    {p_ge_hits*100:.2f}% &mdash; worth knowing, but read alongside the caveat above, not instead of it.</p>
  </div>

  <div class="stats-row">
    <div class="stat-card">
      <div class="lbl">Hits ({HIT_THRESHOLD}+ of 6)</div>
      <div class="val">{hits} / {N_BACKTEST_DRAWS}</div>
      <div class="sub">{observed_rate*100:.1f}% observed hit rate</div>
    </div>
    <div class="stat-card">
      <div class="lbl">Avg match count</div>
      <div class="val">{avg_match_count:.2f} / 6</div>
      <div class="sub">avg winning numbers landing in pool</div>
    </div>
    <div class="stat-card">
      <div class="lbl">Avg intersection pool</div>
      <div class="val">{avg_pool_shared:.1f} numbers</div>
      <div class="sub">range {min_pool_shared}&ndash;{max_pool_shared}, median {median_pool_shared:.0f}</div>
    </div>
    <div class="stat-card">
      <div class="lbl">Observed vs expected</div>
      <div class="val">{ratio:.2f}&times;</div>
      <div class="sub">{observed_rate*100:.2f}% observed vs {expected_rate*100:.2f}% expected (hypergeometric)</div>
    </div>
  </div>

  <div class="section">
    <h2>The 5 seeds</h2>
    <p class="desc">Top 5 by hit6b from <code>seed_hit_xoshiro_k35</code> (full #1000&ndash;2129 window), tiebreak hit6, tiebreak hit5.</p>
    <div class="tbl-wrap">
      <table>
        <thead><tr><th class="tc">#</th><th class="tc">Seed</th><th>hit6b</th><th>hit6</th><th>hit5</th></tr></thead>
        <tbody>{seed_rows_html}</tbody>
      </table>
    </div>
  </div>

  <div class="section">
    <h2>Next upcoming draw (#{next_draw}) &mdash; reference only, not part of the backtest</h2>
    <p class="desc">{len(next_intersection)}-number intersection pool &middot; C({len(next_intersection)},6) = {next_combo_count:,} combos
    ({next_combo_count/FULL_UNIVERSE*100:.2f}% of universe, for reference against the old all-6 definition).</p>
    <div class="inter-cell">{next_inter_html}</div>
  </div>

  <div class="section">
    <h2>Per-draw detail &mdash; last {N_BACKTEST_DRAWS} draws</h2>
    <p class="desc">Newest first. Each row recomputes all 5 seeds' K=35 picks using that draw's own draw_serial,
    intersects them, and counts how many of the 6 winning numbers fall inside. Hit = {HIT_THRESHOLD}+ of 6.
    Hit rows highlighted; matched numbers shown in green in both number columns.</p>
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
    Xoshiro256** (seeded via SplitMix64): picks = partial Fisher-Yates(range(1,44), 35) with combined seed =
    seed&times;10&#8311; + draw_serial. Each (seed, draw) pair independent and deterministic.<br>
    Intersection pool = numbers appearing in ALL 5 seeds' 35-number picks for that specific draw. Hit = at least
    {HIT_THRESHOLD} of the actual 6-number winner's numbers are members of that draw's intersection pool.<br>
    Expected-under-chance baseline computed per-draw via the hypergeometric distribution
    (P(X&ge;{HIT_THRESHOLD}), population=43, success-states=that draw's pool size, draws=6), then averaged across
    the {N_BACKTEST_DRAWS} draws -- not a fixed percentage, since pool size varies draw to draw.<br>
    Data read live from <code>seed_hit_xoshiro_k35</code> in <code>loto6_local.db</code> and directly from the
    production database for per-draw winning numbers.<br>
    Formula-based only &middot; Not financial advice &middot; Loto 6 is random.
  </p>
</div>

</body>
</html>"""

with open(HTML_OUT, 'w', encoding='utf-8') as f:
    f.write(page)
print(f"\nWrote {HTML_OUT} ({len(page)//1024} KB)")
