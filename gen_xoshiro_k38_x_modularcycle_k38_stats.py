"""
gen_xoshiro_k38_x_modularcycle_k38_stats.py
--------------------------------------------------
Generates the "Xoshiro K=38 x Modular Cycle Native K=38 -- Base Pool
Statistics" page: presents the current #2133 intersected pool plus a
full walk-forward backtest of that construction over #44-2132 (the
full usable history -- see precompute script for why #44 is the
earliest valid target), with honest statistical framing (none of the
four hit tiers reach conventional significance), a per-pool-number
generation-order index profile, an aggregate hit-index distribution
(same style as xoshiro_base_review1000.py), a paginated per-draw
breakdown table, and a comparison table against the other Base
constructions tested this session.

Reads xoshiro_k38_x_modularcycle_k38_stats_meta.json (produced by
precompute_xoshiro_k38_x_modularcycle_k38_stats.py). Both the xoshiro
and Modular-Cycle sides are recomputed live in the browser (bit-exact
BigInt/JS ports) and checked against server-embedded references --
Modular Cycle's NATIVE ranking (unlike the cross-method-padded K=33
version used elsewhere) is cheap enough (pure frequency count, no ML)
to run client-side too, so both components of Base get live
verification here, not just the xoshiro side.

Output: public/xoshiro_k38_x_modularcycle_k38_stats.html
Run: python gen_xoshiro_k38_x_modularcycle_k38_stats.py
"""
import json

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
META_PATH = BASE + r"\xoshiro_k38_x_modularcycle_k38_stats_meta.json"
HTML_OUT = BASE + r"\public\xoshiro_k38_x_modularcycle_k38_stats.html"

with open(META_PATH, encoding='utf-8') as f:
    meta = json.load(f)

TARGET_SERIAL = meta['targetSerial']
TRAINED_THROUGH = meta['trainedThroughSerial']
K = meta['k']
SEED_XO = meta['seedXo']
xo_pool = meta['xoPool']
xo_pool_ordered = meta['xoPoolOrdered']
mc_pool = meta['mcPool']
mc_pool_ordered = meta['mcPoolOrdered']
current_pool = meta['currentPool']
per_draw = meta['perDraw']  # newest-first, see precompute script
pool_index_profile = meta['poolIndexProfile']
n_hits_total = meta['nHitsTotal']
xo_bucket_labels = meta['xoBucketLabels']
xo_bucket_counts = meta['xoBucketCounts']
mc_bucket_labels = meta['mcBucketLabels']
mc_bucket_counts = meta['mcBucketCounts']
xo_ranked = meta['xoRanked']
xo_expected = meta['xoExpected']
xo_chi2 = meta['xoChi2']
xo_dof = meta['xoDof']
xo_pvalue = meta['xoPvalue']
mc_ranked = meta['mcRanked']
mc_expected = meta['mcExpected']
mc_chi2 = meta['mcChi2']
mc_dof = meta['mcDof']
mc_pvalue = meta['mcPvalue']

# ── Pool index-profile table rows ────────────────────────────────────────
pool_profile_rows_html = ""
for row in pool_index_profile:
    xo_avg = f"{row['xoIdxAvg']:.1f}" if row['xoIdxAvg'] is not None else "&mdash;"
    xo_modal = row['xoIdxModal'] if row['xoIdxModal'] is not None else "&mdash;"
    mc_avg = f"{row['mcIdxAvg']:.1f}" if row['mcIdxAvg'] is not None else "&mdash;"
    mc_modal = row['mcIdxModal'] if row['mcIdxModal'] is not None else "&mdash;"
    pool_profile_rows_html += f"""<tr>
      <td class="mname">{row['n']}</td>
      <td class="tc">#{row['xoIdxToday']}</td>
      <td class="tc">{xo_avg}</td>
      <td class="tc">#{xo_modal}</td>
      <td class="tc">#{row['mcIdxToday']}</td>
      <td class="tc">{mc_avg}</td>
      <td class="tc">#{mc_modal}</td>
    </tr>"""

# ── Hit-index distribution: bucketed bars ────────────────────────────────
def dist_rows_html(labels, counts, total, color):
    out = ""
    max_count = max(counts) if counts else 1
    for lbl, cnt in zip(labels, counts):
        pct = cnt / total * 100 if total else 0
        bar_pct = cnt / max_count * 100 if max_count else 0
        out += f"""<div class="funnel-row">
        <div class="funnel-lbl">#{lbl}</div>
        <div class="funnel-bar-wrap"><div class="funnel-bar" style="width:{bar_pct:.1f}%;background:{color}"></div></div>
        <div class="funnel-val">{cnt:,} <span style="color:#64748b;font-weight:400">({pct:.1f}%)</span></div>
      </div>"""
    return out

xo_dist_html = dist_rows_html(xo_bucket_labels, xo_bucket_counts, n_hits_total, '#a78bfa')
mc_dist_html = dist_rows_html(mc_bucket_labels, mc_bucket_counts, n_hits_total, '#38bdf8')

def ranking_table_html(ranked, expected, total, limit=15):
    rows = ranked[:limit] if limit else ranked
    out = ""
    for idxv, cnt in rows:
        pct = cnt / total * 100 if total else 0
        vs_expected = (cnt - expected) / expected * 100 if expected else 0
        sign = "+" if vs_expected >= 0 else ""
        out += f"""<tr><td class="tc">#{idxv}</td><td class="tc">{cnt:,}</td><td class="tc">{pct:.2f}%</td>
      <td class="tc" style="color:{'#4ade80' if vs_expected >= 0 else '#f87171'}">{sign}{vs_expected:.1f}%</td></tr>"""
    return out

xo_top15_html = ranking_table_html(xo_ranked, xo_expected, n_hits_total)
mc_top15_html = ranking_table_html(mc_ranked, mc_expected, n_hits_total)
xo_pvalue_str = f"{xo_pvalue:.3f}" if xo_pvalue is not None else "n/a"
mc_pvalue_str = f"{mc_pvalue:.3f}" if mc_pvalue is not None else "n/a"
BACKTEST_LO = meta['backtestLo']
BACKTEST_HI = meta['backtestHi']
N_DRAWS = meta['nDraws']
avg_pool = meta['avgPoolSize']
min_pool = meta['minPoolSize']
max_pool = meta['maxPoolSize']
contained = meta['contained']
containment_pct = meta['containmentPct']
historical_draws = meta['historicalDraws']

tiers = [
    ('hit6b', meta['hit6b'], meta['hit6b_exp'], meta['hit6b_chi2'], meta['hit6b_p']),
    ('hit6 / containment', meta['hit6'], meta['hit6_exp'], meta['hit6_chi2'], meta['hit6_p']),
    ('hit5', meta['hit5'], meta['hit5_exp'], meta['hit5_chi2'], meta['hit5_p']),
    ('hit4', meta['hit4'], meta['hit4_exp'], meta['hit4_chi2'], meta['hit4_p']),
]

def balls_html(nums, cls="nb"):
    return "".join(f'<span class="{cls}">{n}</span>' for n in nums)

tier_rows_html = ""
for name, obs, exp, chi2, p in tiers:
    sig = p < 0.05
    sig_html = '<span class="sig-badge sig-yes">p&lt;0.05</span>' if sig else '<span class="sig-badge sig-no">not significant</span>'
    lift = obs / exp if exp > 0 else 0
    tier_rows_html += f"""<tr>
      <td class="mname">{name}</td>
      <td class="tr">{obs}</td>
      <td class="tr">{exp:.2f}</td>
      <td class="tr">{lift:.2f}&times;</td>
      <td class="tr">{chi2:.4f}</td>
      <td class="tc">1</td>
      <td class="tr">{p:.4f}</td>
      <td class="tc">{sig_html}</td>
    </tr>"""

# ── Comparison table vs other Base constructions tested this session ────────
# (rows other than this page's own K38xK38 backtest use the #1133-2132
# 1000-draw window computed earlier in the same chat session -- window
# noted explicitly per-row since it differs from this page's #1000-2132.)
comparison_rows = [
    ("Xoshiro K=38 alone", "#1133–2132 (1000)", "38", "1.17&times;", "1.14&times;", "n/a", "n/a"),
    ("Modular Cycle K=33 alone (padded)", "#1133–2132 (1000)", "33", "1.03&times;", "1.11&times;", "n/a", "n/a"),
    ("K=33 (padded) &cap; xoshiro K=38", "#1133–2132 (1000)", "~29", "1.53&times;", "1.45&times;", "n/a", "n/a"),
    ("K=38 (native) &cap; xoshiro K=38 &mdash; this page", f"#{BACKTEST_LO}–{BACKTEST_HI} ({N_DRAWS})", f"~{avg_pool:.0f}",
     f"{meta['hit6b']/meta['hit6b_exp']:.2f}&times;", f"{meta['hit6']/meta['hit6_exp']:.2f}&times;",
     f"p={meta['hit6b_p']:.3f}", f"p={meta['hit6_p']:.3f}"),
]
comparison_rows_html = ""
for name, window, k, lift6b, lift6, p6b, p6 in comparison_rows:
    highlight = ' style="background:#1c1608"' if 'this page' in name else ''
    comparison_rows_html += f"""<tr{highlight}>
      <td class="mname">{name}</td>
      <td class="tc">{window}</td>
      <td class="tc">{k}</td>
      <td class="tr">{lift6b}</td>
      <td class="tr">{lift6}</td>
      <td class="tc">{p6b}</td>
      <td class="tc">{p6}</td>
    </tr>"""

js_historical = json.dumps(historical_draws, separators=(',', ':'))

page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Xoshiro K=38 × Modular Cycle Native K=38 — Base Pool Statistics — Loto 6</title>
<style>

*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0a0f1e;color:#e2e8f0;font-family:system-ui,sans-serif;padding-top:60px;min-height:100vh}}
.wrap{{max-width:1100px;margin:0 auto;padding:24px 16px}}
h1{{font-size:1.4rem;font-weight:700;color:#f1f5f9;margin-bottom:4px}}
.subtitle{{font-size:.85rem;color:#64748b;margin-bottom:20px}}

.note{{background:#0d1526;border:1px solid #1e293b;border-radius:10px;padding:14px 18px;
  font-size:.8rem;color:#94a3b8;margin-bottom:20px;line-height:1.6}}
.note p+p{{margin-top:8px}}
.note code{{background:#0a0f1e;padding:1px 5px;border-radius:4px;font-size:.85em}}

.honest{{background:#450a0a;border:1px solid #7f1d1d;border-radius:10px;padding:16px 20px;
  font-size:.85rem;color:#fca5a5;margin-bottom:20px;line-height:1.65}}
.honest strong{{color:#fecaca}}

.section{{background:#0d1526;border:1px solid #1e293b;border-radius:12px;padding:20px;margin-bottom:20px}}
.section h2{{font-size:1rem;font-weight:700;color:#f1f5f9;margin-bottom:4px;display:flex;align-items:center;gap:8px;flex-wrap:wrap}}
.section .desc{{font-size:.8rem;color:#64748b;margin-bottom:14px}}
.order-label{{font-size:.7rem;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:.04em;
  margin:10px 0 5px;display:flex;align-items:center;gap:8px}}
.order-hint{{font-size:.72rem;font-weight:400;text-transform:none;letter-spacing:normal;color:#475569}}
.verify-badge{{font-size:.68rem;font-weight:700;padding:2px 8px;border-radius:10px;text-transform:uppercase;letter-spacing:.04em}}
.verify-badge.pending{{background:#1e293b;color:#94a3b8}}
.verify-badge.ok{{background:#14532d;color:#86efac}}
.verify-badge.fail{{background:#450a0a;color:#fca5a5}}

.balls{{display:flex;flex-wrap:wrap;gap:5px}}
.nb{{display:inline-flex;align-items:center;justify-content:center;width:30px;height:30px;
  border-radius:50%;font-size:.78rem;font-weight:700;background:#312e5f;color:#c4b5fd;
  border:1px solid #7c3aed55;flex-shrink:0}}
.nb.b1{{background:#0c2340;color:#7dd3fc;border-color:#38bdf855}}
.nb.b2{{background:#450a0a;color:#fca5a5;border-color:#ef444455}}
.nb.b3{{background:#1c1206;color:#fbbf24;border-color:#f59e0b55}}

.stats-row{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px}}
.stat-card{{background:#0a0f1e;border:1px solid #1e293b;border-radius:10px;padding:14px 18px;flex:1;min-width:150px}}
.stat-card .lbl{{font-size:.7rem;color:#64748b;text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px}}
.stat-card .val{{font-size:1.35rem;font-weight:700;color:#f1f5f9}}
.stat-card .sub{{font-size:.75rem;color:#94a3b8;margin-top:2px}}

.tbl-wrap{{overflow-x:auto;border-radius:10px;border:1px solid #1e293b}}
table.stats-table{{width:100%;border-collapse:collapse;font-size:.83rem}}
table.stats-table th{{background:#0a0f1e;padding:8px 12px;text-align:right;color:#94a3b8;
  font-weight:600;font-size:.7rem;text-transform:uppercase;letter-spacing:.05em;
  white-space:nowrap;border-bottom:1px solid #1e293b}}
table.stats-table th.tc{{text-align:center}}
table.stats-table th:first-child{{text-align:left}}
table.stats-table td{{padding:8px 12px;border-bottom:1px solid #0f172a;color:#cbd5e1}}
table.stats-table td.mname{{color:#e2e8f0;font-weight:600;white-space:nowrap}}
table.stats-table td.tr{{text-align:right}}
table.stats-table td.tc{{text-align:center}}
table.stats-table tr:hover td{{background:#111827}}
.sig-badge{{font-size:.68rem;font-weight:700;padding:2px 8px;border-radius:10px;text-transform:uppercase;letter-spacing:.03em}}
.sig-badge.sig-yes{{background:#14532d;color:#86efac}}
.sig-badge.sig-no{{background:#1e293b;color:#94a3b8}}

.nb-xs{{display:inline-flex;align-items:center;justify-content:center;width:20px;height:20px;
  border-radius:50%;font-size:.62rem;font-weight:700;margin:1px;flex-shrink:0;
  background:#1e293b;color:#64748b}}
.nb-xs.hit{{background:#14532d;color:#86efac}}
.nb-xs.bonus-hit{{background:#3b0764;color:#d8b4fe;border:1px solid #a855f7}}
.nb-xs.bonus-miss{{background:#451a03;color:#fde68a;border:1px solid #92400e}}

.pd-controls{{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:12px}}
.pd-controls select,.pd-controls input{{background:#0a0f1e;border:1px solid #334155;border-radius:7px;
  padding:7px 10px;color:#e2e8f0;font-size:.82rem}}
.pd-controls input{{width:110px}}
.pd-controls .pd-lbl{{font-size:.72rem;color:#64748b;text-transform:uppercase;letter-spacing:.05em}}
.pd-controls .btn{{background:#1e293b;border:1px solid #334155;border-radius:7px;padding:7px 12px;
  color:#94a3b8;font-size:.8rem;cursor:pointer}}
.pd-controls .btn:hover{{color:#f1f5f9}}
.pd-controls .btn:disabled{{opacity:.4;cursor:default}}
.pd-info{{font-size:.8rem;color:#94a3b8}}

table.pd-table{{width:100%;border-collapse:collapse;font-size:.8rem}}
table.pd-table th{{background:#0a0f1e;padding:7px 10px;text-align:left;color:#94a3b8;
  font-weight:600;font-size:.68rem;text-transform:uppercase;letter-spacing:.05em;
  white-space:nowrap;border-bottom:1px solid #1e293b}}
table.pd-table td{{padding:6px 10px;border-bottom:1px solid #0f172a;vertical-align:middle}}
table.pd-table tr:hover td{{background:#111827}}
table.pd-table td.pd-draw{{color:#e2e8f0;font-weight:600;white-space:nowrap}}
.pd-balls{{display:flex;flex-wrap:wrap;gap:2px;max-width:420px}}
.pd-tier{{font-size:.66rem;font-weight:700;padding:2px 7px;border-radius:9px;text-transform:uppercase;
  letter-spacing:.03em;white-space:nowrap}}
.pd-tier.t-hit6b{{background:#312e5f;color:#c4b5fd}}
.pd-tier.t-hit6{{background:#0c2340;color:#7dd3fc}}
.pd-tier.t-hit5{{background:#1c1206;color:#fbbf24}}
.pd-tier.t-hit4{{background:#0a1c0f;color:#4ade80}}
.pd-tier.t-hit0-3{{background:#1e293b;color:#64748b}}
.pd-pool-toggle{{background:none;border:none;color:#a78bfa;font-size:.75rem;cursor:pointer;padding:0;
  text-decoration:underline}}
.pd-pool-row td{{background:#0a0f1e;padding:8px 10px 10px 10px}}
.pd-pool-row .pd-balls{{max-width:none}}

.funnel-row{{display:flex;align-items:center;gap:10px;font-size:.82rem;margin-bottom:6px}}
.funnel-lbl{{width:60px;color:#94a3b8;flex-shrink:0}}
.funnel-bar-wrap{{flex:1;background:#0a0f1e;border-radius:6px;overflow:hidden;height:20px;border:1px solid #1e293b}}
.funnel-bar{{height:100%;border-radius:6px}}
.funnel-val{{width:110px;text-align:right;color:#f1f5f9;font-weight:600;flex-shrink:0;font-size:.78rem}}

.footer{{margin-top:28px;font-size:.78rem;color:#475569;padding-bottom:20px;line-height:1.6}}
</style>
</head>
<body>

<script src="/site-nav.js"></script>
<div class="wrap">
  <h1>📊 Xoshiro K=38 × Modular Cycle Native K=38 — Base Pool Statistics</h1>
  <p class="subtitle">Current #{TARGET_SERIAL} pool + full walk-forward backtest, #{BACKTEST_LO}–{BACKTEST_HI} ({N_DRAWS} draws)</p>

  <div class="note">
    <p><strong style="color:#e2e8f0">Base</strong> here is xoshiro256** K={K} seed #{SEED_XO:,}'s pick intersected with
    Modular Cycle's <strong>native</strong> mod-43-cycle K={K} pick &mdash; no cross-method-consensus padding, unlike the
    K=33-padded version used on <a href="/xoshiro_elim_2133.html" style="color:#a78bfa">the live elimination page</a>.
    Both components are walk-forward (Modular Cycle trained only on draws strictly before each target; xoshiro is a pure
    function of seed + draw serial, no training needed) and both are recomputed <strong>live in your browser</strong> below
    and checked against server-embedded references.</p>
    <p>The backtest applies this exact construction to all {N_DRAWS} real draws from #{BACKTEST_LO} to #{BACKTEST_HI},
    re-deriving Base fresh for every target (no leakage), and tallies hit6b (6 main + bonus), hit6 (6 main, any bonus,
    equivalent to full containment), hit5, and hit4 against the hypergeometric chance expectation for a pool of this size.</p>
  </div>

  <div class="honest">
    <strong>⚠️ Honest framing:</strong> none of the four hit tiers reach conventional statistical significance (all p &gt; 0.05
    against the chance baseline &mdash; see the table below). This construction is <strong>statistically indistinguishable
    from chance</strong> across the board. It is also meaningfully weaker than the K=33-padded intersection used on the live
    elimination page, which showed a real 1.53&times; / 1.45&times; lift on hit6b / hit6 over the same kind of backtest.
    Cross-method padding appears to matter &mdash; Modular Cycle's raw/native ranking alone doesn't carry the same edge.
  </div>

  <div class="section">
    <h2>Current pool — draw #{TARGET_SERIAL} <span id="badgeCurrent" class="verify-badge pending">verifying…</span></h2>
    <p class="desc">Walk-forward, trained on all real draws through #{TRAINED_THROUGH} (the latest real/confirmed draw).</p>

    <h3 style="font-size:.86rem;font-weight:700;color:#cbd5e1;margin:14px 0 6px">Xoshiro K={K} seed #{SEED_XO:,} pick <span id="badgeXo" class="verify-badge pending">verifying…</span></h3>
    <div class="order-label">Ascending order</div>
    <div class="balls" id="xoBalls"></div>
    <div class="order-label">Generation order <span class="order-hint">(partial Fisher-Yates shuffle order)</span> <span id="badgeXoOrdered" class="verify-badge pending">verifying…</span></div>
    <div class="balls" id="xoBallsOrdered"></div>

    <h3 style="font-size:.86rem;font-weight:700;color:#cbd5e1;margin:14px 0 6px">Modular Cycle native K={K} pick <span id="badgeMc" class="verify-badge pending">verifying…</span></h3>
    <div class="order-label">Ascending order</div>
    <div class="balls" id="mcBalls"></div>
    <div class="order-label">Generation order <span class="order-hint">(mod-43-cycle frequency rank, highest count first)</span> <span id="badgeMcOrdered" class="verify-badge pending">verifying…</span></div>
    <div class="balls" id="mcBallsOrdered"></div>

    <h3 style="font-size:.86rem;font-weight:700;color:#cbd5e1;margin:14px 0 6px">Intersected pool ({len(current_pool)} numbers)</h3>
    <div class="balls" id="baseBalls"></div>
  </div>

  <div class="section">
    <h2>Current pool — per-number index profile</h2>
    <p class="desc">For each of the {len(current_pool)} numbers in today's intersected pool: where it landed in each
    method's generation order for #{TARGET_SERIAL} specifically ("today"), plus its <b>typical</b> (average) and
    <b>most-frequent</b> (modal) index across the full #{BACKTEST_LO}–{BACKTEST_HI} backtest window, whenever it
    appeared in that method's K={K} pick.</p>
    <div class="tbl-wrap">
      <table class="stats-table">
        <thead><tr>
          <th>Number</th>
          <th class="tc">XO index (today)</th><th class="tc">XO avg index</th><th class="tc">XO modal index</th>
          <th class="tc">MC index (today)</th><th class="tc">MC avg index</th><th class="tc">MC modal index</th>
        </tr></thead>
        <tbody>{pool_profile_rows_html}</tbody>
      </table>
    </div>
  </div>

  <div class="section">
    <h2>Walk-forward backtest results — #{BACKTEST_LO}–{BACKTEST_HI} ({N_DRAWS} draws)</h2>
    <p class="desc">Base recomputed fresh for every target draw (no leakage). Chi-square goodness-of-fit, df=1, per tier
    (observed hit / no-hit vs. chance-expected hit / no-hit), equivalent to a two-sided binomial test on the same
    proportion.</p>
    <div class="stats-row">
      <div class="stat-card">
        <div class="lbl">Average pool size</div>
        <div class="val">{avg_pool:.2f}</div>
        <div class="sub">range {min_pool}–{max_pool}</div>
      </div>
      <div class="stat-card">
        <div class="lbl">Containment (hit6)</div>
        <div class="val">{contained:,} / {N_DRAWS:,}</div>
        <div class="sub">{containment_pct:.2f}%</div>
      </div>
      <div class="stat-card">
        <div class="lbl">Draws tested</div>
        <div class="val">{N_DRAWS:,}</div>
        <div class="sub">#{BACKTEST_LO}–{BACKTEST_HI}, walk-forward</div>
      </div>
    </div>
    <div class="tbl-wrap">
      <table class="stats-table">
        <thead><tr>
          <th>Tier</th><th>Observed</th><th>Expected</th><th>Lift</th><th>χ²</th><th class="tc">df</th><th>p-value</th><th class="tc">Significant?</th>
        </tr></thead>
        <tbody>{tier_rows_html}</tbody>
      </table>
    </div>
  </div>

  <div class="section">
    <h2>Hit-index distribution — where do caught winners land in each method's build order?</h2>
    <p class="desc">Across all {N_DRAWS:,} backtest draws, whenever an actual winning main number WAS caught by Base
    (present in both XO and MC that draw), where did it land in each method's own generation order for that specific
    draw? {n_hits_total:,} hit-number occurrences total. A flat/uniform distribution means hits land roughly evenly
    across the whole K={K}; a skew toward low or high indices would mean hits tend to cluster at a particular point
    in that method's own build order.</p>

    <h3 style="font-size:.86rem;font-weight:700;color:#cbd5e1;margin:14px 0 8px">Xoshiro K={K} — bucketed (width 5)</h3>
    <div style="margin-bottom:16px">{xo_dist_html}</div>
    <h3 style="font-size:.86rem;font-weight:700;color:#cbd5e1;margin:14px 0 8px">Modular Cycle K={K} — bucketed (width 5)</h3>
    <div style="margin-bottom:8px">{mc_dist_html}</div>

    <p class="desc" style="margin-top:16px">Exact-index chi-square goodness-of-fit vs. a uniform distribution across
    all {K} positions: <strong style="color:#f1f5f9">XO: &chi;&sup2;={xo_chi2:.2f}, df={xo_dof}, p={xo_pvalue_str}</strong>
    &middot; <strong style="color:#f1f5f9">MC: &chi;&sup2;={mc_chi2:.2f}, df={mc_dof}, p={mc_pvalue_str}</strong>.
    Both comfortably above 0.05 &mdash; no detectable skew in either method's hit-index pattern, consistent with the
    rest of this page's chance-baseline findings.</p>

    <details style="margin-top:12px">
      <summary style="cursor:pointer;font-size:.85rem;font-weight:600;color:#e2e8f0">Show top-15 exact-index ranking for both methods</summary>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:12px">
        <div>
          <h4 style="font-size:.8rem;color:#a78bfa;margin-bottom:6px">Xoshiro K={K}</h4>
          <table class="stats-table"><thead><tr><th class="tc">Index</th><th class="tc">Count</th><th class="tc">%</th><th class="tc">vs. expected</th></tr></thead>
          <tbody>{xo_top15_html}</tbody></table>
        </div>
        <div>
          <h4 style="font-size:.8rem;color:#38bdf8;margin-bottom:6px">Modular Cycle K={K}</h4>
          <table class="stats-table"><thead><tr><th class="tc">Index</th><th class="tc">Count</th><th class="tc">%</th><th class="tc">vs. expected</th></tr></thead>
          <tbody>{mc_top15_html}</tbody></table>
        </div>
      </div>
    </details>
  </div>

  <div class="section">
    <h2>Comparison — Base constructions tested this session</h2>
    <p class="desc">Lift = observed / chance-expected. Different rows use different backtest windows (noted per row) as
    computed earlier in this analysis session &mdash; not all four were re-run on an identical window, but each is its
    own walk-forward, no-leakage backtest.</p>
    <div class="tbl-wrap">
      <table class="stats-table">
        <thead><tr>
          <th>Construction</th><th class="tc">Window (draws)</th><th class="tc">Avg pool K</th><th>hit6b lift</th><th>hit6 lift</th><th class="tc">hit6b sig.</th><th class="tc">hit6 sig.</th>
        </tr></thead>
        <tbody>{comparison_rows_html}</tbody>
      </table>
    </div>
  </div>

  <div class="section">
    <h2>Per-draw breakdown — #{BACKTEST_LO}–{BACKTEST_HI} ({N_DRAWS} draws)</h2>
    <p class="desc">Every backtested draw: the intersected Base pool (walk-forward, click "pool" to expand), the actual
    winning numbers (green = caught by the pool, purple = bonus caught too, amber = bonus missed, gray = missed
    entirely), and the resulting hit tier. Newest draws first by default.</p>
    <div class="pd-controls">
      <span class="pd-lbl">Tier</span>
      <select id="pdTierFilter" onchange="pdApplyFilter()">
        <option value="">All tiers</option>
        <option value="hit6b">hit6b</option>
        <option value="hit6">hit6</option>
        <option value="hit5">hit5</option>
        <option value="hit4">hit4</option>
        <option value="hit0-3">hit0-3 (miss)</option>
      </select>
      <span class="pd-lbl">Draw #</span>
      <input id="pdSearch" type="number" placeholder="e.g. 2050" oninput="pdApplyFilter()">
      <button class="btn" onclick="pdClearFilter()">Clear</button>
      <span class="pd-info" id="pdFilterInfo"></span>
    </div>
    <div class="tbl-wrap">
      <div class="pd-controls" style="justify-content:space-between;padding:8px 10px;margin-bottom:0">
        <span class="pd-info" id="pdPageInfo"></span>
        <div style="display:flex;gap:6px">
          <button class="btn" id="pdFirstBtn" onclick="pdGoPage(0)">&laquo; First</button>
          <button class="btn" id="pdPrevBtn" onclick="pdGoPage(pdCurPage-1)">&lsaquo; Prev</button>
          <button class="btn" id="pdNextBtn" onclick="pdGoPage(pdCurPage+1)">Next &rsaquo;</button>
          <button class="btn" id="pdLastBtn" onclick="pdGoPage(pdTotalPages()-1)">Last &raquo;</button>
        </div>
      </div>
      <table class="pd-table">
        <thead><tr>
          <th>Draw</th><th>Actual (6 main + bonus)</th><th>Hits</th><th>Tier</th><th>Pool</th>
        </tr></thead>
        <tbody id="pdTbody"></tbody>
      </table>
    </div>
  </div>

  <p class="footer">
    Xoshiro256** (seeded via SplitMix64): picks = partial Fisher-Yates(range(1,44), {K}) with combined seed = seed×10⁷ + draw_serial.
    Modular Cycle: ranks all 43 numbers by frequency among historical draws sharing the target draw's mod-43 residue
    (walk-forward, trained only on draws strictly before the target), takes the top {K}.
    Both recomputed live above and checked against server-embedded references.<br>
    Chi-square goodness-of-fit (df=1) computed via the exact relation to the standard normal CDF (no external stats
    library needed): p = 1 &minus; erf(&radic;(χ²/2)).<br>
    Formula-based only · Not financial advice · Loto 6 is random.
  </p>
</div>

<script>
// ── xoshiro256**, bit-exact BigInt port (identical to every other xoshiro page) ──
const MASK64 = (1n << 64n) - 1n;
function rotl(x, k) {{
  x &= MASK64;
  return ((x << BigInt(k)) | (x >> BigInt(64 - k))) & MASK64;
}}
function splitmix64Next(z) {{
  z = (z + 0x9E3779B97F4A7C15n) & MASK64;
  let zz = z;
  zz = ((zz ^ (zz >> 30n)) * 0xBF58476D1CE4E5B9n) & MASK64;
  zz = ((zz ^ (zz >> 27n)) * 0x94D049BB133111EBn) & MASK64;
  zz = zz ^ (zz >> 31n);
  return [z, zz];
}}
function seedState(seed) {{
  let z = BigInt(seed) & MASK64;
  const state = [];
  for (let i = 0; i < 4; i++) {{
    const [nz, out] = splitmix64Next(z);
    z = nz;
    state.push(out);
  }}
  return state;
}}
function xoshiroNext(s) {{
  const result = (rotl((s[1] * 5n) & MASK64, 7) * 9n) & MASK64;
  const t = (s[1] << 17n) & MASK64;
  s[2] ^= s[0]; s[3] ^= s[1]; s[1] ^= s[2]; s[0] ^= s[3];
  s[2] ^= t;
  s[3] = rotl(s[3], 45);
  return result;
}}
function xoshiroPredictRaw(seed, drawSerial, k) {{
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
function xoshiroPredict(seed, drawSerial, k) {{
  return xoshiroPredictRaw(seed, drawSerial, k).slice().sort((a, b) => a - b);
}}

// ── Modular Cycle native ranking -- pure frequency count, no ML, so this
// runs live client-side too (unlike the cross-method-padded K=33 version
// used elsewhere, which needs Random Forest/ARIMA/LSTM). ────────────────────
const HISTORICAL_DRAWS = {js_historical}; // [{{s: serial, a: [6 main numbers]}}, ...]
function modularCycleRanked(trainDraws, targetSerial, k) {{
  const targetMod = ((targetSerial % 43) + 43) % 43;
  const freq = new Array(44).fill(0);
  let any = false;
  for (const d of trainDraws) {{
    if (((d.s % 43) + 43) % 43 === targetMod) {{
      any = true;
      for (const n of d.a) freq[n]++;
    }}
  }}
  if (!any) {{
    for (const d of trainDraws) for (const n of d.a) freq[n]++;
  }}
  const nums = Array.from({{length: 43}}, (_, i) => i + 1);
  nums.sort((a, b) => freq[b] - freq[a] || a - b);
  return nums.slice(0, k);
}}

function arraysEqual(a, b) {{
  return a.length === b.length && a.every((v, i) => v === b[i]);
}}
function renderBadge(id, ok) {{
  const el = document.getElementById(id);
  el.className = 'verify-badge ' + (ok ? 'ok' : 'fail');
  el.textContent = ok ? '✓ live-computed value matches' : '✗ MISMATCH — check console';
}}
function renderBalls(elId, nums, cls) {{
  document.getElementById(elId).innerHTML = nums.map(n => '<span class="nb ' + cls + '">' + n + '</span>').join('');
}}

// Xoshiro side
const liveXo = xoshiroPredict({SEED_XO}, {TARGET_SERIAL}, {K});
const liveXoOrdered = xoshiroPredictRaw({SEED_XO}, {TARGET_SERIAL}, {K});
const KNOWN_XO = {json.dumps(xo_pool)};
const KNOWN_XO_ORDERED = {json.dumps(xo_pool_ordered)};
renderBalls('xoBalls', liveXo, 'b1');
renderBalls('xoBallsOrdered', liveXoOrdered, 'b1');
renderBadge('badgeXo', arraysEqual(liveXo, KNOWN_XO));
renderBadge('badgeXoOrdered', arraysEqual(liveXoOrdered, KNOWN_XO_ORDERED));
if (!arraysEqual(liveXo, KNOWN_XO)) console.error('Xoshiro mismatch', liveXo, KNOWN_XO);
if (!arraysEqual(liveXoOrdered, KNOWN_XO_ORDERED)) console.error('Xoshiro (generation order) mismatch', liveXoOrdered, KNOWN_XO_ORDERED);

// Modular Cycle side -- trained on ALL historical draws through #{TRAINED_THROUGH}
const liveMcOrdered = modularCycleRanked(HISTORICAL_DRAWS, {TARGET_SERIAL}, {K});
const liveMc = liveMcOrdered.slice().sort((a, b) => a - b);
const KNOWN_MC = {json.dumps(mc_pool)};
const KNOWN_MC_ORDERED = {json.dumps(mc_pool_ordered)};
renderBalls('mcBalls', liveMc, 'b3');
renderBalls('mcBallsOrdered', liveMcOrdered, 'b3');
renderBadge('badgeMc', arraysEqual(liveMc, KNOWN_MC));
renderBadge('badgeMcOrdered', arraysEqual(liveMcOrdered, KNOWN_MC_ORDERED));
if (!arraysEqual(liveMc, KNOWN_MC)) console.error('Modular Cycle mismatch', liveMc, KNOWN_MC);
if (!arraysEqual(liveMcOrdered, KNOWN_MC_ORDERED)) console.error('Modular Cycle (generation order) mismatch', liveMcOrdered, KNOWN_MC_ORDERED);

// Intersection
const liveBase = liveXo.filter(n => liveMc.includes(n)).sort((a, b) => a - b);
const KNOWN_BASE = {json.dumps(current_pool)};
renderBalls('baseBalls', liveBase, 'b2');
renderBadge('badgeCurrent', arraysEqual(liveBase, KNOWN_BASE));
if (!arraysEqual(liveBase, KNOWN_BASE)) console.error('Base intersection mismatch', liveBase, KNOWN_BASE);

// ── Per-draw breakdown table: paginated + filterable, newest-first ─────────
const PER_DRAW = {json.dumps(per_draw, separators=(',', ':'))};
const PD_PAGE_SIZE = 100;
let pdFiltered = PER_DRAW;
let pdCurPage = 0;
const pdExpanded = new Set(); // serials whose pool row is currently shown

function pdTierLabel(t) {{ return t === 'hit0-3' ? 'hit0-3 (miss)' : t; }}

function pdApplyFilter() {{
  const tier = document.getElementById('pdTierFilter').value;
  const search = document.getElementById('pdSearch').value.trim();
  pdFiltered = PER_DRAW.filter(r => {{
    if (tier && r.tier !== tier) return false;
    if (search && String(r.s).indexOf(search) === -1) return false;
    return true;
  }});
  const info = document.getElementById('pdFilterInfo');
  info.textContent = (tier || search) ? (pdFiltered.length.toLocaleString() + ' / ' + PER_DRAW.length.toLocaleString() + ' draws match') : '';
  pdCurPage = 0;
  pdRender();
}}
function pdClearFilter() {{
  document.getElementById('pdTierFilter').value = '';
  document.getElementById('pdSearch').value = '';
  pdApplyFilter();
}}
function pdTotalPages() {{ return Math.max(1, Math.ceil(pdFiltered.length / PD_PAGE_SIZE)); }}
function pdGoPage(p) {{ pdCurPage = Math.max(0, Math.min(p, pdTotalPages() - 1)); pdRender(); }}
function pdTogglePool(serial) {{
  if (pdExpanded.has(serial)) pdExpanded.delete(serial); else pdExpanded.add(serial);
  pdRender();
}}
window.pdTogglePool = pdTogglePool;

function pdBallHtml(n, cls) {{ return '<span class="nb-xs ' + cls + '">' + n + '</span>'; }}

function pdRender() {{
  const start = pdCurPage * PD_PAGE_SIZE;
  const pageRows = pdFiltered.slice(start, start + PD_PAGE_SIZE);
  const parts = [];
  for (const r of pageRows) {{
    const poolSet = new Set(r.pool);
    const actualHtml = r.main.map(n => pdBallHtml(n, poolSet.has(n) ? 'hit' : '')).join('') +
      pdBallHtml(r.bonus, poolSet.has(r.bonus) ? 'bonus-hit' : 'bonus-miss');
    const tierCls = 't-' + r.tier;
    const isOpen = pdExpanded.has(r.s);
    parts.push(
      '<tr><td class="pd-draw">#' + r.s + '</td>' +
      '<td><div class="pd-balls">' + actualHtml + '</div></td>' +
      '<td>' + r.mainHits + (r.bonusHit ? '<span style="color:#a78bfa;font-size:.7rem">+B</span>' : '') + '</td>' +
      '<td><span class="pd-tier ' + tierCls + '">' + pdTierLabel(r.tier) + '</span></td>' +
      '<td><button class="pd-pool-toggle" onclick="pdTogglePool(' + r.s + ')">' + (isOpen ? 'hide' : 'show') + ' (' + r.pool.length + ')</button></td>' +
      '</tr>'
    );
    if (isOpen) {{
      const poolHtml = r.pool.map(n => pdBallHtml(n, '')).join('');
      parts.push('<tr class="pd-pool-row"><td colspan="5"><div class="pd-balls">' + poolHtml + '</div></td></tr>');
    }}
  }}
  document.getElementById('pdTbody').innerHTML = parts.join('');
  document.getElementById('pdPageInfo').textContent =
    pdFiltered.length === 0 ? 'No draws match' :
    'Showing ' + (start + 1) + '-' + Math.min(start + PD_PAGE_SIZE, pdFiltered.length) + ' of ' + pdFiltered.length.toLocaleString() + ' (page ' + (pdCurPage + 1) + ' / ' + pdTotalPages() + ')';
  document.getElementById('pdFirstBtn').disabled = pdCurPage === 0;
  document.getElementById('pdPrevBtn').disabled = pdCurPage === 0;
  document.getElementById('pdNextBtn').disabled = pdCurPage >= pdTotalPages() - 1;
  document.getElementById('pdLastBtn').disabled = pdCurPage >= pdTotalPages() - 1;
}}
pdRender();
</script>
</body>
</html>"""

with open(HTML_OUT, 'w', encoding='utf-8') as f:
    f.write(page)
print(f"Wrote {HTML_OUT} ({len(page)//1024} KB)")
