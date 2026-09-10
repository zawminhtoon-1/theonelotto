"""
gen_xoshiro_seed_detail_neg7070245.py
--------------------------------------
Standalone single-seed detail page for xoshiro256** seed #-7,070,245
(K=38) -- the seed that showed the provisional stage-3 lead in the
now-stopped -10,000,000..10,000,000 K=38 full-range scan
(xoshiro_seed_scan_k38_full.py). That scan was explicitly stopped
before completion and its stage checkpoint JSONs were deleted, so
this page does NOT read from any scan output file. Every number shown
is independently recomputed here, fresh, straight from the production
database, using the exact same xoshiro256**/SplitMix64 algorithm and
combined-seed formula (seed*10,000,000 + draw_serial) as every other
xoshiro page on this site.

Two windows are reported and clearly labeled, since they are NOT the
same draws:
  - In-sample (#1-2100): the scan's own training window. Recomputed
    here and asserted to match the last-known provisional numbers
    (935/1054/777/250) -- confirms those numbers were accurate even
    though the checkpoint that produced them is gone.
  - Out-of-sample (#2101-2134): the 34 real draws that happened AFTER
    the scan's window and were never seen by it -- a genuine
    walk-forward check. n=34 is small; treat with appropriate caution.
  - Combined (#1-2134): both windows folded together, for reference.

Follows the site's established single-seed-detail conventions:
  - Shared /xoshiro256.js (bit-exact BigInt port) + /elim-badges.css
    verify-badge styling, same as xoshiro_elim_2135.html.
  - A live "recomputed in your browser, checked against server-embedded
    reference" verify badge per stat window.
  - An embedded per-draw DRAWS array + expandable full breakdown table,
    same shape/fields as xoshiro_seed_scan_k38.html's seed-detail modal.
  - A "🔍 compare another seed" lookup box reusing that same modal
    pattern, scoped to this page's #1-2134 window, so seed #692,809 (or
    any other seed) can be checked side-by-side without leaving the page.
  - A next-draw (#2135) walk-forward pick callout, tagged upcoming/not
    yet drawn, same treatment as xoshiro_seed_scan_k38.html.

Output: public/xoshiro_seed_detail_neg7070245.html
Run: python gen_xoshiro_seed_detail_neg7070245.py
"""
import json, re, os

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
ENV_LOCAL = BASE + r"\.env.local"
HTML_OUT = BASE + r"\public\xoshiro_seed_detail_neg7070245.html"

SEED = -7_070_245
K_PICKS = 38
LOTO6_MAX = 43
DRAW_START, DRAW_END = 1, 2134
IN_SAMPLE_END = 2100
MASK64 = 0xFFFFFFFFFFFFFFFF

# Last-known provisional figures from the deleted stage-3 checkpoint --
# used ONLY as an assertion target below (to prove the fresh recompute
# matches), never trusted directly.
CLAIMED_IN_SAMPLE = (935, 1054, 777, 250)  # hit6b, hit6, hit5, hit4

# Published comparison seed, from the live xoshiro_seed_scan_k38.html page.
COMPARE_SEED = 692809
COMPARE_STATS = {'hit6b': 525, 'hit6': 588, 'hit5': 397, 'n_draws': 1132, 'range': '#1000\u20132131'}


def xoshiro_predict(seed, draw_serial, k=K_PICKS, pool_max=LOTO6_MAX):
    combined = (seed * 10_000_000 + draw_serial) & MASK64
    z = combined & MASK64
    state = []
    for _ in range(4):
        z = (z + 0x9E3779B97F4A7C15) & MASK64
        zz = z
        zz = ((zz ^ (zz >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
        zz = ((zz ^ (zz >> 27)) * 0x94D049BB133111EB) & MASK64
        zz = zz ^ (zz >> 31)
        state.append(zz)
    def rotl(x, kk):
        x &= MASK64
        return ((x << kk) | (x >> (64 - kk))) & MASK64
    def xnext(s):
        result = (rotl((s[1] * 5) & MASK64, 7) * 9) & MASK64
        t = (s[1] << 17) & MASK64
        s[2] ^= s[0]; s[3] ^= s[1]; s[1] ^= s[2]; s[0] ^= s[3]
        s[2] ^= t
        s[3] = rotl(s[3], 45)
        return result
    arr = list(range(1, pool_max + 1))
    n = len(arr)
    order = []
    for i in range(n - 1, n - 1 - k, -1):
        r = xnext(state)
        j = r % (i + 1)
        arr[i], arr[j] = arr[j], arr[i]
        order.append(arr[i])
    return order  # generation order


# Self-check against the site's known-good reference vector before trusting anything.
KNOWN_2129 = [2,3,4,5,6,7,8,9,11,12,13,14,15,16,17,18,19,20,21,22,24,25,27,28,29,30,31,32,33,34,35,36,38,39,40,41,42,43]
_check = sorted(xoshiro_predict(692809, 2129))
assert _check == KNOWN_2129, f"SELF-CHECK FAILED vs known-good reference: {_check}"
print("[Self-check] OK vs known-good seed 692809/draw 2129 reference.")

# ── Load draws #1-2134 from the production database ─────────────────────────
if 'DATABASE_URL' not in os.environ:
    with open(ENV_LOCAL, encoding='utf-8') as f:
        env_text = f.read()
    m = re.search(r'DATABASE_URL=(.+)', env_text)
    os.environ['DATABASE_URL'] = m.group(1).strip()
import psycopg2
conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()
cur.execute(
    "SELECT draw_serial, draw_date, num1,num2,num3,num4,num5,num6, bonus "
    "FROM loto6_results WHERE draw_serial BETWEEN %s AND %s ORDER BY draw_serial",
    (DRAW_START, DRAW_END),
)
pg_rows = cur.fetchall()
conn.close()

if len(pg_rows) != DRAW_END - DRAW_START + 1:
    raise SystemExit(f"Draw window mismatch: got {len(pg_rows)} rows, expected {DRAW_END - DRAW_START + 1}")
serials = [r[0] for r in pg_rows]
if serials != list(range(DRAW_START, DRAW_END + 1)):
    raise SystemExit("Gap or out-of-order draw detected in #1-2134!")
print(f"[DB] Verified {len(pg_rows)} consecutive draws, #{DRAW_START}-{DRAW_END}, no gaps.")

DRAWS = [{'s': r[0], 'd': r[1].isoformat(), 'a': list(r[2:8]), 'b': r[8]} for r in pg_rows]

# ── Recompute hit tallies for SEED, split in-sample / out-of-sample ──────────
def tally(rows):
    hit6b = hit6 = hit5 = hit4 = 0
    for row in rows:
        picks = xoshiro_predict(SEED, row['s'])
        actual_set = frozenset(row['a'])
        picks_set = frozenset(picks)
        h = len(actual_set & picks_set)
        if h == 6:
            hit6 += 1
            if row['b'] in picks_set:
                hit6b += 1
        elif h == 5:
            hit5 += 1
        elif h == 4:
            hit4 += 1
    return hit6b, hit6, hit5, hit4

rows_in = [r for r in DRAWS if r['s'] <= IN_SAMPLE_END]
rows_oos = [r for r in DRAWS if r['s'] > IN_SAMPLE_END]
in_sample = tally(rows_in)
out_of_sample = tally(rows_oos)
combined = tuple(a + b for a, b in zip(in_sample, out_of_sample))

assert in_sample == CLAIMED_IN_SAMPLE, f"MISMATCH vs claimed provisional figures: recomputed={in_sample} claimed={CLAIMED_IN_SAMPLE}"
print(f"[Verify] In-sample (#1-{IN_SAMPLE_END}) recompute matches claimed provisional figures: {in_sample}")
print(f"[Verify] Out-of-sample (#{IN_SAMPLE_END+1}-{DRAW_END}, n={len(rows_oos)}): {out_of_sample}")
print(f"[Verify] Combined (#1-{DRAW_END}): {combined}")

def rate100(count, n):
    return round(count / n * 100, 2)

IN_N = len(rows_in)
OOS_N = len(rows_oos)
COMBINED_N = len(DRAWS)

in_rates = tuple(rate100(v, IN_N) for v in in_sample)
oos_rates = tuple(rate100(v, OOS_N) for v in out_of_sample)
combined_rates = tuple(rate100(v, COMBINED_N) for v in combined)

compare_rates = (
    rate100(COMPARE_STATS['hit6b'], COMPARE_STATS['n_draws']),
    rate100(COMPARE_STATS['hit6'], COMPARE_STATS['n_draws']),
    rate100(COMPARE_STATS['hit5'], COMPARE_STATS['n_draws']),
)

# ── Next-draw (#2135) walk-forward pick, not yet drawn ───────────────────────
NEXT_SERIAL = DRAW_END + 1
next_pick_order = xoshiro_predict(SEED, NEXT_SERIAL)
next_pick_sorted = sorted(next_pick_order)

js_draws = json.dumps(DRAWS, separators=(',', ':'))
js_next_order = json.dumps(next_pick_order)
js_next_sorted = json.dumps(next_pick_sorted)

seed_str = f"{SEED:,}"

next_balls_html = "".join(f'<div class="ball">{n}</div>' for n in next_pick_order)

page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Xoshiro Seed Detail — #{seed_str} (K=38) — Loto 6</title>
<style>

*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0a0f1e;color:#e2e8f0;font-family:system-ui,sans-serif;padding-top:60px;min-height:100vh}}
.wrap{{max-width:1200px;margin:0 auto;padding:24px 16px}}
h1{{font-size:1.4rem;font-weight:700;color:#f1f5f9;margin-bottom:4px}}
.subtitle{{font-size:.85rem;color:#64748b;margin-bottom:20px}}

.note{{background:#0d1526;border:1px solid #1e293b;border-radius:10px;padding:14px 18px;
  font-size:.8rem;color:#94a3b8;margin-bottom:20px;line-height:1.6}}
.note p+p{{margin-top:8px}}
.note code{{background:#0a0f1e;padding:1px 5px;border-radius:4px;font-size:.85em}}
.note b.warn{{color:#fbbf24}}

.section{{background:#0d1526;border:1px solid #1e293b;border-radius:12px;padding:20px;margin-bottom:20px}}
.section h2{{font-size:1rem;font-weight:700;color:#f1f5f9;margin-bottom:4px;display:flex;align-items:center;gap:8px;flex-wrap:wrap}}
.section .desc{{font-size:.8rem;color:#64748b;margin-bottom:14px}}

.stats-row{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:8px}}
.stat-card{{background:#0a0f1e;border:1px solid #1e293b;border-radius:10px;padding:14px 18px;flex:1;min-width:150px}}
.stat-card .lbl{{font-size:.7rem;color:#64748b;text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px}}
.stat-card .val{{font-size:1.35rem;font-weight:700;color:#f1f5f9}}
.stat-card .sub{{font-size:.75rem;color:#94a3b8;margin-top:2px}}
.window-lbl{{font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.05em;margin:14px 0 8px;display:flex;align-items:center;gap:8px}}
.window-lbl.in{{color:#38bdf8}}
.window-lbl.oos{{color:#fbbf24}}
.window-lbl.combined{{color:#a78bfa}}
.window-lbl .n{{font-weight:400;color:#64748b;text-transform:none;letter-spacing:normal}}
.caution{{font-size:.74rem;color:#fbbf24;margin-top:-2px;margin-bottom:12px}}

.next-pred{{background:#0d1526;border:1px solid #f59e0b55;border-radius:10px;padding:16px 18px;margin-bottom:20px}}
.next-pred .lbl{{font-size:.72rem;color:#f59e0b;text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px;font-weight:700}}
.next-pred .tag{{display:inline-block;background:#78350f;color:#fde68a;font-size:.66rem;font-weight:700;padding:2px 8px;
  border-radius:10px;text-transform:uppercase;letter-spacing:.04em;margin-left:8px}}
.next-pred .order-note{{font-size:.75rem;color:#94a3b8;margin-top:8px}}
.next-pred .balls{{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}}
.next-pred .ball{{width:32px;height:32px;border-radius:50%;background:#1e3a5f;display:flex;align-items:center;
  justify-content:center;font-weight:700;font-size:.8rem;color:#93c5fd;border:1px solid #2563eb55}}

.cmp-tbl{{width:100%;border-collapse:collapse;font-size:.83rem}}
.cmp-tbl th{{background:#0a0f1e;padding:8px 12px;text-align:right;color:#94a3b8;
  font-weight:600;font-size:.7rem;text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid #1e293b;white-space:nowrap}}
.cmp-tbl th:first-child{{text-align:left}}
.cmp-tbl td{{padding:8px 12px;border-bottom:1px solid #0f172a;text-align:right;color:#cbd5e1;white-space:nowrap}}
.cmp-tbl td:first-child{{text-align:left;color:#e2e8f0;font-weight:600}}
.cmp-tbl tr:hover td{{background:#111827}}

.lookup{{background:#0a0f1e;border:1px solid #a78bfa55;border-radius:10px;padding:14px 18px;margin-bottom:0;display:flex;gap:10px;align-items:center;flex-wrap:wrap}}
.lookup .lbl{{font-size:.72rem;color:#a78bfa;text-transform:uppercase;letter-spacing:.06em;font-weight:700;margin-right:4px}}
.lookup input{{background:#0d1526;border:1px solid #334155;border-radius:7px;padding:8px 12px;
  color:#e2e8f0;font-size:.85rem;width:160px}}
.lookup button{{background:#7c3aed;border:none;color:#fff;padding:8px 16px;border-radius:7px;
  cursor:pointer;font-size:.83rem;font-weight:600}}
.lookup button:hover{{background:#6d28d9}}
.lookup .hint{{font-size:.78rem;color:#64748b}}
.lookup .err{{font-size:.78rem;color:#f87171}}

details{{background:#0a0f1e;border:1px solid #1e293b;border-radius:10px;padding:12px 16px}}
summary{{cursor:pointer;font-size:.85rem;font-weight:600;color:#e2e8f0;user-select:none}}
summary:hover{{color:#f1f5f9}}

.view-toggle{{display:flex;gap:8px;margin-top:12px}}
.toggle-btn{{background:#1e293b;border:1px solid #334155;color:#94a3b8;padding:7px 14px;
  border-radius:7px;cursor:pointer;font-size:.8rem;font-weight:600}}
.toggle-btn:hover{{color:#f1f5f9}}
.toggle-btn.active{{background:#7c3aed;border-color:#7c3aed;color:#fff}}

.tbl-wrap{{overflow-x:auto;overflow-y:auto;max-height:600px;border-radius:10px;border:1px solid #1e293b;margin-top:12px}}
.draw-tbl{{width:100%;border-collapse:collapse;font-size:.78rem}}
.draw-tbl thead{{position:sticky;top:0;background:#0a0f1e;z-index:1}}
.draw-tbl th{{padding:9px 12px;color:#64748b;text-align:left;border-bottom:1px solid #1e293b;font-weight:600;font-size:.72rem;text-transform:uppercase;letter-spacing:.04em;white-space:nowrap}}
.draw-tbl td{{padding:6px 10px;border-bottom:1px solid #0f172a;vertical-align:middle}}
.draw-tbl tr:hover td{{background:#0f172a}}
.draw-tbl tr.oos-row td{{background:#1c1508}}
.nb{{display:inline-flex;align-items:center;justify-content:center;width:24px;height:24px;border-radius:50%;background:#1e293b;color:#64748b;font-size:.66rem;font-weight:700;margin:1px}}
.nm{{background:#14532d;color:#86efac}}
.nb-b{{background:#451a03;color:#fde68a;border:1px solid #92400e}}
.nb-bh{{background:#7c2d12;color:#fed7aa}}

#seedModal{{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.82);z-index:20000;align-items:flex-start;justify-content:center;padding:60px 16px 20px}}
.modal-box{{background:#0a0f1e;border:1px solid #1e293b;border-radius:12px;width:100%;max-width:1050px;max-height:85vh;display:flex;flex-direction:column}}
.modal-hdr{{display:flex;justify-content:space-between;align-items:center;padding:14px 18px;border-bottom:1px solid #1e293b;flex-shrink:0;gap:16px;flex-wrap:wrap}}
.modal-hdr h2{{font-size:.95rem;font-weight:700;color:#f1f5f9;margin:0}}
.modal-hdr .modal-stats{{font-size:.78rem;color:#94a3b8;display:flex;gap:14px;flex-wrap:wrap}}
.modal-hdr .modal-stats b{{color:#e2e8f0}}
.modal-close{{background:#1e293b;border:none;color:#94a3b8;padding:5px 14px;border-radius:6px;cursor:pointer;font-size:.83rem}}
.modal-close:hover{{background:#334155;color:#f1f5f9}}
.modal-body{{overflow-y:auto;flex:1}}

.footer{{margin-top:28px;font-size:.78rem;color:#475569;padding-bottom:20px;line-height:1.6}}
</style>
<link rel="stylesheet" href="/elim-badges.css">
</head>
<body>

<script src="/site-nav.js"></script>
<script src="/xoshiro256.js"></script>
<div class="wrap">
  <h1>🔎 Xoshiro Seed Detail — #{seed_str} (K=38)</h1>
  <p class="subtitle">xoshiro256** (SplitMix64-seeded) · K=38 picks · draws #{DRAW_START}\u2013{DRAW_END} available in the production database</p>

  <div class="note">
    <p>Seed <b>#{seed_str}</b> showed the provisional stage-3 lead in the -10,000,000..10,000,000 K=38 full-range
    scan (<code>xoshiro_seed_scan_k38_full.py</code>). <b class="warn">That scan was explicitly stopped before completion</b>
    and its stage checkpoint JSONs were deleted with no backup — so nothing on this page is read from that scan's output.
    Every number here was recomputed fresh, directly from the production database, using the exact same xoshiro256**/SplitMix64
    algorithm and combined-seed formula (<code>seed×10,000,000 + draw_serial</code>) as every other xoshiro page on this site.</p>
    <p>Two windows matter here and are <b>not the same draws</b>, so they're kept clearly separate: the
    <b style="color:#38bdf8">in-sample</b> window (#1\u2013{IN_SAMPLE_END}) is what the stopped scan was actually scoring seeds
    against — recomputing it here independently confirms the last-known provisional figures (935/1054/777/250) were accurate.
    The <b style="color:#fbbf24">out-of-sample</b> window (#{IN_SAMPLE_END+1}\u2013{DRAW_END}, {OOS_N} draws) is real draws that
    happened <em>after</em> the scan's window and were never seen by it at all — a genuine walk-forward check, though
    <b class="warn">n={OOS_N} is small</b> and shouldn't be read as strong evidence either way.</p>
  </div>

  <div class="section">
    <h2>Verified stats <span id="badgeIn" class="verify-badge pending">verifying…</span> <span id="badgeOos" class="verify-badge pending">verifying…</span></h2>
    <p class="desc">Recomputed live in your browser (bit-exact BigInt xoshiro256** port) and checked against the server-embedded reference — see the badges above.</p>

    <div class="window-lbl in">In-sample <span class="n">#{DRAW_START}\u2013{IN_SAMPLE_END} · n={IN_N} draws</span></div>
    <div class="stats-row">
      <div class="stat-card"><div class="lbl">hit6b</div><div class="val">{in_sample[0]}</div><div class="sub">{in_rates[0]} per 100 draws</div></div>
      <div class="stat-card"><div class="lbl">hit6</div><div class="val">{in_sample[1]}</div><div class="sub">{in_rates[1]} per 100 draws</div></div>
      <div class="stat-card"><div class="lbl">hit5</div><div class="val">{in_sample[2]}</div><div class="sub">{in_rates[2]} per 100 draws</div></div>
      <div class="stat-card"><div class="lbl">hit4</div><div class="val">{in_sample[3]}</div><div class="sub">{in_rates[3]} per 100 draws</div></div>
    </div>

    <div class="window-lbl oos">Out-of-sample <span class="n">#{IN_SAMPLE_END+1}\u2013{DRAW_END} · n={OOS_N} draws — never seen by the scan</span></div>
    <p class="caution">⚠ Small sample (n={OOS_N}) — normalized rates here are noisy, shown for reference only, not as confirmation of anything.</p>
    <div class="stats-row">
      <div class="stat-card"><div class="lbl">hit6b</div><div class="val">{out_of_sample[0]}</div><div class="sub">{oos_rates[0]} per 100 draws</div></div>
      <div class="stat-card"><div class="lbl">hit6</div><div class="val">{out_of_sample[1]}</div><div class="sub">{oos_rates[1]} per 100 draws</div></div>
      <div class="stat-card"><div class="lbl">hit5</div><div class="val">{out_of_sample[2]}</div><div class="sub">{oos_rates[2]} per 100 draws</div></div>
      <div class="stat-card"><div class="lbl">hit4</div><div class="val">{out_of_sample[3]}</div><div class="sub">{oos_rates[3]} per 100 draws</div></div>
    </div>

    <div class="window-lbl combined">Combined <span class="n">#{DRAW_START}\u2013{DRAW_END} · n={COMBINED_N} draws (both windows folded together)</span></div>
    <div class="stats-row">
      <div class="stat-card"><div class="lbl">hit6b</div><div class="val">{combined[0]}</div><div class="sub">{combined_rates[0]} per 100 draws</div></div>
      <div class="stat-card"><div class="lbl">hit6</div><div class="val">{combined[1]}</div><div class="sub">{combined_rates[1]} per 100 draws</div></div>
      <div class="stat-card"><div class="lbl">hit5</div><div class="val">{combined[2]}</div><div class="sub">{combined_rates[2]} per 100 draws</div></div>
      <div class="stat-card"><div class="lbl">hit4</div><div class="val">{combined[3]}</div><div class="sub">{combined_rates[3]} per 100 draws</div></div>
    </div>
  </div>

  <div class="next-pred">
    <div class="lbl">🎯 Seed #{seed_str} — pick for draw #{NEXT_SERIAL}<span class="tag">upcoming · not yet drawn</span></div>
    <div class="balls">
      {next_balls_html}
    </div>
    <div class="order-note">Shown in generation order (the actual partial Fisher-Yates finalization sequence), not sorted ascending — same convention as xoshiro_seed_scan_k38.html. Walk-forward: pure function of (seed, draw serial), computed through the latest actual draw (#{DRAW_END}). No hit highlighting since draw #{NEXT_SERIAL} hasn't happened yet.</div>
  </div>

  <div class="section">
    <h2>Comparison vs seed #{COMPARE_SEED:,}'s published best</h2>
    <p class="desc">Seed #{COMPARE_SEED:,} is the current top-ranked seed on the completed, published <a href="/xoshiro_seed_scan_k38.html" style="color:#a78bfa">K=38 seed scan (0\u20131,000,000)</a> page. Its window (#1000\u20132131) and this seed's in-sample window (#1\u2013{IN_SAMPLE_END}) overlap on draws #1000\u2013{IN_SAMPLE_END} but each includes draws the other doesn't — so normalized rates (per 100 draws) are the fairest comparison, not raw counts.</p>
    <div class="tbl-wrap" style="max-height:none">
      <table class="cmp-tbl">
        <thead><tr><th>Seed</th><th>Window</th><th>n draws</th><th>hit6b</th><th>hit6b /100</th><th>hit6</th><th>hit6 /100</th><th>hit5</th><th>hit5 /100</th><th>hit4</th><th>hit4 /100</th></tr></thead>
        <tbody>
          <tr><td>#{COMPARE_SEED:,} (published best)</td><td>{COMPARE_STATS['range']}</td><td>{COMPARE_STATS['n_draws']}</td><td>{COMPARE_STATS['hit6b']}</td><td>{compare_rates[0]}</td><td>{COMPARE_STATS['hit6']}</td><td>{compare_rates[1]}</td><td>{COMPARE_STATS['hit5']}</td><td>{compare_rates[2]}</td><td>N/A</td><td>N/A</td></tr>
          <tr><td>#{seed_str} (in-sample)</td><td>#{DRAW_START}\u2013{IN_SAMPLE_END}</td><td>{IN_N}</td><td>{in_sample[0]}</td><td>{in_rates[0]}</td><td>{in_sample[1]}</td><td>{in_rates[1]}</td><td>{in_sample[2]}</td><td>{in_rates[2]}</td><td>{in_sample[3]}</td><td>{in_rates[3]}</td></tr>
        </tbody>
      </table>
    </div>
    <p class="caution" style="margin-top:10px">hit4 is N/A for #{COMPARE_SEED:,} — the published K=38 scan page only ever tracked hit6b/hit6/hit5, never hit4, so there's nothing to compare there.</p>
  </div>

  <div class="section">
    <h2>Full {COMBINED_N}-draw breakdown for seed #{seed_str}</h2>
    <p class="desc">Rendered live in your browser from the embedded draw records — the amber-tinted rows are the out-of-sample #{IN_SAMPLE_END+1}\u2013{DRAW_END} draws. Toggle below to switch between chronological order and ranked-by-hit-count order.</p>
    <details id="ownBreakdownDetails">
      <summary>Show all {COMBINED_N} draws</summary>
      <div class="view-toggle">
        <button class="toggle-btn active" id="btnChrono" onclick="setOwnView('chrono')">📅 Draw order</button>
        <button class="toggle-btn" id="btnRanked" onclick="setOwnView('ranked')">🏆 Ranked by hits</button>
      </div>
      <div class="tbl-wrap">
        <table class="draw-tbl">
          <thead><tr><th style="text-align:right">#</th><th>Draw</th><th>Date</th><th>Actual (6) + bonus</th><th>Picks (38) · generation order</th><th style="text-align:center">Hits</th></tr></thead>
          <tbody id="ownBreakdownTbody"></tbody>
        </table>
      </div>
    </details>
  </div>

  <div class="section">
    <div class="lookup">
      <span class="lbl">🔍 Compare another seed</span>
      <input id="seedLookupInput" type="number" step="1" placeholder="e.g. 692809 or -7070245" onkeydown="if(event.key==='Enter')lookupSeed()">
      <button onclick="lookupSeed()">View {COMBINED_N}-draw breakdown</button>
      <span class="hint">Same #{DRAW_START}\u2013{DRAW_END} window, computed live in your browser for any seed — try {COMPARE_SEED:,}.</span>
      <span id="lookupErr" class="err" style="display:none"></span>
    </div>
  </div>

  <p class="footer">
    Xoshiro256** (seeded via SplitMix64): picks = partial Fisher-Yates(range(1,44), 38) with combined seed = seed×10⁷ + draw_serial.
    Same shared implementation (<code>/xoshiro256.js</code>) as every other xoshiro page on this site.<br>
    Draw records for #{DRAW_START}\u2013{DRAW_END} sourced directly from the production database, verified for exactly {COMBINED_N}
    consecutive rows with no gaps before computing anything.<br>
    This page exists as a transparency record for the #{seed_str} figures quoted in chat after the K=38 full-range scan was
    stopped — see <a href="/xoshiro_seed_scan_k38.html" style="color:#64748b">xoshiro_seed_scan_k38.html</a> for the completed,
    published 0\u20131,000,000 scan.<br>
    Formula-based only · Not financial advice · Loto 6 is random.
  </p>

  <div id="seedModal">
    <div class="modal-box">
      <div class="modal-hdr">
        <h2 id="modalTitle">Seed detail</h2>
        <div class="modal-stats" id="modalStats"></div>
        <button class="modal-close" onclick="document.getElementById('seedModal').style.display='none'">✕ Close</button>
      </div>
      <div class="modal-body">
        <table class="draw-tbl">
          <thead><tr>
            <th>Draw</th><th>Date</th>
            <th>Actual (6) + bonus</th>
            <th>Picks (38) · generation order</th>
            <th style="text-align:center">Hits</th>
          </tr></thead>
          <tbody id="modalTbody"></tbody>
        </table>
      </div>
    </div>
  </div>
</div>

<script>
const SEED = {SEED};
const IN_SAMPLE_END = {IN_SAMPLE_END};
const DRAWS = {js_draws};

const KNOWN_IN_SAMPLE = {list(CLAIMED_IN_SAMPLE)};
const KNOWN_OOS = {list(out_of_sample)};
const KNOWN_NEXT_ORDER = {js_next_order};
const KNOWN_NEXT_SORTED = {js_next_sorted};

function arraysEqual(a, b) {{
  return a.length === b.length && a.every((v, i) => v === b[i]);
}}
function renderBadge(id, ok, okText, failText) {{
  const el = document.getElementById(id);
  el.className = 'verify-badge ' + (ok ? 'ok' : 'fail');
  el.textContent = ok ? (okText || '✓ live-computed value matches') : (failText || '✗ MISMATCH — check console');
}}

function xoshiroPredict(seed, drawSerial, k) {{
  const combined = (BigInt(seed) * 10000000n + BigInt(drawSerial)) & MASK64;
  const s = seedState(combined);
  const arr = Array.from({{length: 43}}, (_, i) => i + 1);
  const n = arr.length;
  const order = [];
  for (let i = n - 1; i >= n - k; i--) {{
    const r = xoshiroNext(s);
    const j = Number(r % BigInt(i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
    order.push(arr[i]);
  }}
  return order;
}}

function tallyAndRenderRows(seed, rows) {{
  let hit6b = 0, hit6 = 0, hit5 = 0, hit4 = 0;
  const htmlParts = [];
  [...rows].reverse().forEach(row => {{
    const picks = xoshiroPredict(seed, row.s, 38);
    const actualSet = new Set(row.a);
    const picksSet = new Set(picks);
    const hits = picks.filter(p => actualSet.has(p)).length;
    const bh = picksSet.has(row.b);
    if (hits === 6) {{ hit6++; if (bh) hit6b++; }}
    else if (hits === 5) {{ hit5++; }}
    else if (hits === 4) {{ hit4++; }}

    const actualHtml = row.a.map(n => '<span class="nb nm">' + n + '</span>').join('') +
      '<span class="nb nb-b">' + row.b + '</span>';
    const picksHtml = picks.map(n =>
      '<span class="nb' + (actualSet.has(n) ? ' nm' : '') + (n === row.b ? ' nb-bh' : '') + '">' + n + '</span>'
    ).join('');
    const hc = hits >= 5 ? '#22c55e' : hits >= 4 ? '#4ade80' : hits >= 3 ? '#fbbf24' : hits >= 2 ? '#fb923c' : '#475569';
    const rowCls = row.s > IN_SAMPLE_END ? ' class="oos-row"' : '';
    htmlParts.push(
      '<tr' + rowCls + '><td style="color:#64748b;white-space:nowrap">' + row.s + '</td>' +
      '<td style="color:#64748b;white-space:nowrap">' + (row.d || '') + '</td>' +
      '<td style="white-space:nowrap">' + actualHtml + '</td>' +
      '<td style="white-space:nowrap">' + picksHtml + '</td>' +
      '<td style="text-align:center;font-weight:700;color:' + hc + '">' + hits + (bh ? '<span style="color:#a78bfa;font-size:.7rem">+B</span>' : '') + '</td></tr>'
    );
  }});
  return {{ tally: [hit6b, hit6, hit5, hit4], html: htmlParts.join('') }};
}}

// ── Own breakdown (seed #{seed_str}) + live badges ───────────────────────────
const rowsIn = DRAWS.filter(r => r.s <= IN_SAMPLE_END);
const rowsOos = DRAWS.filter(r => r.s > IN_SAMPLE_END);
const inResult = tallyAndRenderRows(SEED, rowsIn);
const oosResult = tallyAndRenderRows(SEED, rowsOos);

const inOk = arraysEqual(inResult.tally, KNOWN_IN_SAMPLE);
const oosOk = arraysEqual(oosResult.tally, KNOWN_OOS);
renderBadge('badgeIn', inOk, '✓ in-sample matches', '✗ in-sample MISMATCH');
renderBadge('badgeOos', oosOk, '✓ out-of-sample matches', '✗ out-of-sample MISMATCH');
if (!inOk) console.error('In-sample mismatch', inResult.tally, KNOWN_IN_SAMPLE);
if (!oosOk) console.error('Out-of-sample mismatch', oosResult.tally, KNOWN_OOS);

// ── Own breakdown table: chronological (default) vs ranked-by-hits toggle ───
function computeOwnRecords(seed, rows) {{
  return rows.map(row => {{
    const picks = xoshiroPredict(seed, row.s, 38);
    const actualSet = new Set(row.a);
    const picksSet = new Set(picks);
    const hits = picks.filter(p => actualSet.has(p)).length;
    const bh = picksSet.has(row.b);
    return {{ row, picks, actualSet, hits, bh }};
  }});
}}
function renderOwnRow(rec, idx) {{
  const {{ row, picks, actualSet, hits, bh }} = rec;
  const actualHtml = row.a.map(n => '<span class="nb nm">' + n + '</span>').join('') +
    '<span class="nb nb-b">' + row.b + '</span>';
  const picksHtml = picks.map(n =>
    '<span class="nb' + (actualSet.has(n) ? ' nm' : '') + (n === row.b ? ' nb-bh' : '') + '">' + n + '</span>'
  ).join('');
  const hc = hits >= 5 ? '#22c55e' : hits >= 4 ? '#4ade80' : hits >= 3 ? '#fbbf24' : hits >= 2 ? '#fb923c' : '#475569';
  const rowCls = row.s > IN_SAMPLE_END ? ' class="oos-row"' : '';
  return '<tr' + rowCls + '><td style="color:#64748b;text-align:right">' + idx + '</td>' +
    '<td style="color:#64748b;white-space:nowrap">' + row.s + '</td>' +
    '<td style="color:#64748b;white-space:nowrap">' + (row.d || '') + '</td>' +
    '<td style="white-space:nowrap">' + actualHtml + '</td>' +
    '<td style="white-space:nowrap">' + picksHtml + '</td>' +
    '<td style="text-align:center;font-weight:700;color:' + hc + '">' + hits + (bh ? '<span style="color:#a78bfa;font-size:.7rem">+B</span>' : '') + '</td></tr>';
}}
// Ranked-by-hits comparator: highest hit count first; among ties, a hit6b
// (6 main + bonus) row ranks above a plain hit6 row; final tiebreak is
// chronological ascending, purely for stable/readable ordering.
function ownRankComparator(a, b) {{
  if (b.hits !== a.hits) return b.hits - a.hits;
  if (b.bh !== a.bh) return (b.bh ? 1 : 0) - (a.bh ? 1 : 0);
  return a.row.s - b.row.s;
}}
const ownRecords = computeOwnRecords(SEED, DRAWS); // chronological ascending, as embedded
let ownView = 'chrono';
function renderOwnBreakdown() {{
  const recs = ownView === 'ranked'
    ? [...ownRecords].sort(ownRankComparator)
    : [...ownRecords].reverse(); // newest draw first (previous default behavior)
  document.getElementById('ownBreakdownTbody').innerHTML = recs.map((rec, i) => renderOwnRow(rec, i + 1)).join('');
}}
function setOwnView(view) {{
  ownView = view;
  document.getElementById('btnChrono').classList.toggle('active', view === 'chrono');
  document.getElementById('btnRanked').classList.toggle('active', view === 'ranked');
  renderOwnBreakdown();
}}
renderOwnBreakdown();

const liveNextOrder = xoshiroPredict(SEED, {NEXT_SERIAL}, 38);
if (!arraysEqual(liveNextOrder, KNOWN_NEXT_ORDER)) console.error('Next-draw pick mismatch', liveNextOrder, KNOWN_NEXT_ORDER);

// ── "Compare another seed" lookup, reusing the same modal pattern used on
// xoshiro_seed_scan_k38.html, scoped to this page's #{DRAW_START}\u2013{DRAW_END} window ──
function lookupSeed() {{
  const input = document.getElementById('seedLookupInput');
  const errEl = document.getElementById('lookupErr');
  const raw = input.value.trim();
  errEl.style.display = 'none';
  if (raw === '' || !/^-?\\d+$/.test(raw)) {{
    errEl.textContent = 'Enter a whole number (negative seeds allowed).';
    errEl.style.display = 'inline';
    return;
  }}
  openSeedDetail(parseInt(raw, 10));
}}

function openSeedDetail(seed) {{
  const result = tallyAndRenderRows(seed, DRAWS);
  const [hit6b, hit6, hit5, hit4] = result.tally;
  document.getElementById('modalTitle').textContent = 'Seed #' + seed.toLocaleString() + ' — ' + DRAWS.length + ' draws (K=38)';
  document.getElementById('modalStats').innerHTML =
    'hit6b: <b>' + hit6b + '</b> &nbsp;\u00b7&nbsp; hit6: <b>' + hit6 + '</b> &nbsp;\u00b7&nbsp; hit5: <b>' + hit5 + '</b> &nbsp;\u00b7&nbsp; hit4: <b>' + hit4 + '</b>';
  document.getElementById('modalTbody').innerHTML = result.html;
  document.getElementById('seedModal').style.display = 'flex';
}}

document.getElementById('seedModal').addEventListener('click', function(e) {{
  if (e.target === this) this.style.display = 'none';
}});
document.addEventListener('keydown', function(e) {{
  if (e.key === 'Escape') document.getElementById('seedModal').style.display = 'none';
}});
</script>
</body>
</html>"""

with open(HTML_OUT, 'w', encoding='utf-8') as f:
    f.write(page)
print(f"Wrote {HTML_OUT} ({len(page)//1024} KB)")
