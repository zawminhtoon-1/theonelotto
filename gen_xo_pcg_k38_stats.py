"""
gen_xo_pcg_k38_stats.py
--------------------------------
Generates the "Two-Way K=38 Intersection -- xoshiro x PCG64" stats
page: the current #2134 pool (xoshiro seed #692,809's K=38 pick
intersected with PCG64 seed #-4,675,555's K=38 pick, both recomputed
live in the browser and checked against server-embedded references),
a walk-forward backtest across three windows -- #2084-2133 (50
draws), #2033-2133 (101 draws), #1884-2133 (250 draws) -- with
significance testing for each, honest framing (this construction
shows the most consistent above-chance pattern found on this site so
far, including in the fully out-of-sample 50-draw window -- still not
proof, but worth flagging plainly rather than either overselling or
flattening it to "just another null result"), plus the PCG64
in-sample-overlap caveat per window, and a paginated/filterable
per-draw breakdown table covering all 250 rows.

No Modular Cycle component -- both xoshiro and PCG64 are pure
functions of (seed, draw_serial), so no historical-draws embed is
needed for live verification (simpler/smaller than
triple_k38_stats.html).

Reads xo_pcg_k38_stats_meta.json (produced by
precompute_xo_pcg_k38_stats.py).

Output: public/xo_pcg_k38_stats.html
Run: python gen_xo_pcg_k38_stats.py
"""
import json

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
META_PATH = BASE + r"\xo_pcg_k38_stats_meta.json"
HTML_OUT = BASE + r"\public\xo_pcg_k38_stats.html"

with open(META_PATH, encoding='utf-8') as f:
    meta = json.load(f)

TARGET_SERIAL = meta['targetSerial']
TRAINED_THROUGH = meta['trainedThroughSerial']
K = meta['k']
SEED_XO = meta['seedXo']
SEED_PCG = meta['seedPcg']
xo_pool = meta['xoPool']; xo_pool_ordered = meta['xoPoolOrdered']
pcg_pool = meta['pcgPool']; pcg_pool_ordered = meta['pcgPoolOrdered']
current_pool = meta['currentPool']
per_draw = meta['perDraw']
B50_LO, B50_HI = meta['backtest50Lo'], meta['backtest50Hi']
B101_LO, B101_HI = meta['backtest101Lo'], meta['backtest101Hi']
B250_LO, B250_HI = meta['backtest250Lo'], meta['backtest250Hi']
SCAN_WINDOW_HI = meta['scanWindowHi']
s50 = meta['summary50']
s101 = meta['summary101']
s250 = meta['summary250']
inSample50 = meta['inSample50']
inSample101 = meta['inSample101']
inSample250 = meta['inSample250']

def tier_rows_html(summary):
    labels = [('hit6b', 'hit6b'), ('hit6', 'hit6 / containment'), ('hit5', 'hit5'), ('hit4', 'hit4')]
    out = ""
    for key, label in labels:
        t = summary['tiers'][key]
        sig = t['p'] < 0.05
        sig_html = '<span class="sig-badge sig-yes">p&lt;0.05</span>' if sig else '<span class="sig-badge sig-no">not significant</span>'
        out += f"""<tr>
      <td class="mname">{label}</td>
      <td class="tr">{t['observed']}</td>
      <td class="tr">{t['expected']:.2f}</td>
      <td class="tr">{t['ratio']:.3f}&times;</td>
      <td class="tr">{t['chi2']:.4f}</td>
      <td class="tc">1</td>
      <td class="tr">{t['p']:.4f}</td>
      <td class="tc">{sig_html}</td>
    </tr>"""
    return out

tier50_html = tier_rows_html(s50)
tier101_html = tier_rows_html(s101)
tier250_html = tier_rows_html(s250)

js_per_draw = json.dumps(per_draw, separators=(',', ':'))

page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Two-Way K=38 Intersection — xoshiro × PCG64 — Loto 6</title>
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
.honest.notable{{background:#1c1608;border:1px solid #92400e}}
.honest strong{{color:#fecaca}}
.honest.notable strong{{color:#fde68a}}
.honest p+p{{margin-top:10px}}

.section{{background:#0d1526;border:1px solid #1e293b;border-radius:12px;padding:20px;margin-bottom:20px}}
.section h2{{font-size:1rem;font-weight:700;color:#f1f5f9;margin-bottom:4px;display:flex;align-items:center;gap:8px;flex-wrap:wrap}}
.section h3{{font-size:.86rem;font-weight:700;color:#cbd5e1;margin:14px 0 6px}}
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
.nb.b4{{background:#052e16;color:#86efac;border-color:#22c55e55}}

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

.footer{{margin-top:28px;font-size:.78rem;color:#475569;padding-bottom:20px;line-height:1.6}}
</style>
</head>
<body>

<script src="/site-nav.js"></script>
<div class="wrap">
  <h1>📊 Two-Way K=38 Intersection — xoshiro × PCG64</h1>
  <p class="subtitle">Current #{TARGET_SERIAL} pool + walk-forward backtest across three windows: #{B50_LO}–{B50_HI} ({s50['n']} draws), #{B101_LO}–{B101_HI} ({s101['n']} draws), #{B250_LO}–{B250_HI} ({s250['n']} draws)</p>

  <div class="note">
    <p><strong style="color:#e2e8f0">Pool</strong> is the intersection of two independently-constructed K={K} pools, both
    for the same target draw: <strong>xoshiro256** seed #{SEED_XO:,}</strong> (this site's best-known K=38 xoshiro seed)
    and <strong>PCG64 (O'Neill XSL-RR 128/64) seed #{SEED_PCG:,}</strong> &mdash; the top-ranked seed from
    <a href="/pcg64_seed_scan_k38.html" style="color:#a78bfa">the PCG64 K=38 seed scan</a>'s Stage 1. No Modular Cycle
    component here (compare against <a href="/triple_k38_stats.html" style="color:#a78bfa">the three-way xoshiro × Modular
    Cycle × PCG64 intersection</a>). Both components are pure functions of (seed, draw serial) &mdash; no training data
    needed &mdash; and are recomputed <strong>live in your browser</strong> below, checked against server-embedded
    references.</p>
    <p>The backtest applies this exact construction to three windows &mdash; #{B50_LO}&ndash;{B50_HI} ({s50['n']} draws),
    #{B101_LO}&ndash;{B101_HI} ({s101['n']} draws), and #{B250_LO}&ndash;{B250_HI} ({s250['n']} draws) &mdash; re-deriving
    the pool fresh for every target (no leakage), and tallies hit6b (6 main + bonus), hit6 (6 main, any bonus, equivalent
    to full containment), hit5, and hit4 against the hypergeometric chance expectation &mdash; computed per draw using
    that draw's actual pool size ({s250['minPoolSize']}&ndash;{s250['maxPoolSize']} across these windows, not a fixed
    average), then summed for the significance test.</p>
  </div>

  <div class="honest notable">
    <p><strong>📌 This is the most consistent above-chance result found on this site so far</strong> &mdash; worth stating
    plainly rather than flattening it to "just another null," while still not treating it as proven. hit6b and hit6 both
    run <em>above</em> chance in <strong>all three</strong> backtest windows (hit6b: {s50['tiers']['hit6b']['ratio']:.2f}&times;
    / {s101['tiers']['hit6b']['ratio']:.2f}&times; / {s250['tiers']['hit6b']['ratio']:.2f}&times; for 50/101/250 draws;
    hit6: {s50['tiers']['hit6']['ratio']:.2f}&times; / {s101['tiers']['hit6']['ratio']:.2f}&times; /
    {s250['tiers']['hit6']['ratio']:.2f}&times;) &mdash; no sign flips between windows, unlike most of the constructions
    tested on this site, which typically show a result that reverses or collapses once split into sub-windows. Three of
    the six (window, tier) combinations for hit6b/hit6 individually clear p&lt;0.05: hit6b in the 50-draw window
    (p={s50['tiers']['hit6b']['p']:.4f}) and the 101-draw window (p={s101['tiers']['hit6b']['p']:.4f}), and hit6 in the
    101-draw window (p={s101['tiers']['hit6']['p']:.4f}) and the 250-draw window (p={s250['tiers']['hit6']['p']:.4f}).</p>
    <p><strong>Why this doesn't settle it, despite the consistency:</strong> (1) the 50-draw window is the only one that's
    fully out-of-sample (see the in-sample caveat below) &mdash; the 101- and 250-draw windows both include a real chunk
    of draws the PCG64 seed was originally selected against, so their significance is contaminated by that selection
    bias to some degree. (2) This is one construction among dozens tested across this site's whole investigation, with no
    formal multiple-comparisons correction applied across all of them &mdash; finding one out of many that looks this
    good is exactly what you'd expect from chance alone at this scale of searching. (3) The pool itself is large
    ({s250['avgPoolSize']:.0f} of 43 numbers, {s250['avgPoolSize']/43*100:.0f}% coverage) &mdash; even a real edge this
    size has limited practical use for elimination. Read this as the most interesting lead this session has produced, not
    as a validated method &mdash; worth watching on future draws, not worth acting on yet.</p>
  </div>

  <div class="note">
    <p><strong>In-sample seed selection caveat:</strong> the PCG64 seed #{SEED_PCG:,} was found by scanning against the
    fixed #1&ndash;{SCAN_WINDOW_HI} draw window. This matters more for wider backtest windows, since they reach further
    back into that same range:</p>
    <ul style="margin:6px 0 0 20px;line-height:1.7">
      <li>50-draw window (#{B50_LO}&ndash;{B50_HI}): <strong style="color:#86efac">{inSample50} of {s50['n']} draws
      in-sample</strong> &mdash; fully clean, out-of-sample throughout. This is the window whose significant hit6b result
      carries the most weight.</li>
      <li>101-draw window (#{B101_LO}&ndash;{B101_HI}): {inSample101} of {s101['n']} draws in-sample (#{B101_LO}&ndash;{SCAN_WINDOW_HI}).</li>
      <li>250-draw window (#{B250_LO}&ndash;{B250_HI}): <strong style="color:#fca5a5">{inSample250} of {s250['n']} draws
      in-sample</strong> (#{B250_LO}&ndash;{SCAN_WINDOW_HI}) &mdash; a majority of this window overlaps the seed's own
      selection window, so its results deserve the most skepticism of the three.</li>
    </ul>
    <p style="margin-top:8px">The xoshiro seed #{SEED_XO:,} has an analogous history from its own earlier K=38 scan.</p>
  </div>

  <div class="section">
    <h2>Current pool — draw #{TARGET_SERIAL} <span id="badgeCurrent" class="verify-badge pending">verifying…</span></h2>
    <p class="desc">Walk-forward, trained on all real draws through #{TRAINED_THROUGH} (the latest real/confirmed draw).</p>

    <h3>Xoshiro K={K} seed #{SEED_XO:,} pick <span id="badgeXo" class="verify-badge pending">verifying…</span></h3>
    <div class="order-label">Ascending order</div>
    <div class="balls" id="xoBalls"></div>
    <div class="order-label">Generation order <span class="order-hint">(partial Fisher-Yates shuffle order)</span> <span id="badgeXoOrdered" class="verify-badge pending">verifying…</span></div>
    <div class="balls" id="xoBallsOrdered"></div>

    <h3>PCG64 K={K} seed #{SEED_PCG:,} pick <span id="badgePcg" class="verify-badge pending">verifying…</span></h3>
    <div class="order-label">Ascending order</div>
    <div class="balls" id="pcgBalls"></div>
    <div class="order-label">Generation order <span class="order-hint">(O'Neill XSL-RR partial Fisher-Yates order)</span> <span id="badgePcgOrdered" class="verify-badge pending">verifying…</span></div>
    <div class="balls" id="pcgBallsOrdered"></div>

    <h3>Intersection ({len(current_pool)} numbers)</h3>
    <div class="balls" id="intersectBalls"></div>
  </div>

  <div class="section">
    <h2>Backtest results — clean OOS window, #{B50_LO}–{B50_HI} ({s50['n']} draws)</h2>
    <p class="desc">Fully out-of-sample &mdash; none of these draws overlap the PCG64 seed's #1&ndash;{SCAN_WINDOW_HI} selection window.</p>
    <div class="stats-row">
      <div class="stat-card">
        <div class="lbl">Average pool size</div>
        <div class="val">{s50['avgPoolSize']:.2f}</div>
        <div class="sub">range {s50['minPoolSize']}–{s50['maxPoolSize']}</div>
      </div>
      <div class="stat-card">
        <div class="lbl">Containment (hit6)</div>
        <div class="val">{s50['containment']:,} / {s50['n']:,}</div>
        <div class="sub">{s50['containmentPct']:.2f}%</div>
      </div>
      <div class="stat-card">
        <div class="lbl">In-sample overlap</div>
        <div class="val">{inSample50} / {s50['n']}</div>
        <div class="sub">fully clean OOS</div>
      </div>
    </div>
    <div class="tbl-wrap">
      <table class="stats-table">
        <thead><tr>
          <th>Tier</th><th>Observed</th><th>Expected</th><th>Lift</th><th>χ²</th><th class="tc">df</th><th>p-value</th><th class="tc">Significant?</th>
        </tr></thead>
        <tbody>{tier50_html}</tbody>
      </table>
    </div>
  </div>

  <div class="section">
    <h2>Backtest results — #{B101_LO}–{B101_HI} ({s101['n']} draws)</h2>
    <p class="desc">{inSample101} of {s101['n']} draws overlap the PCG64 seed's selection window.</p>
    <div class="stats-row">
      <div class="stat-card">
        <div class="lbl">Average pool size</div>
        <div class="val">{s101['avgPoolSize']:.2f}</div>
        <div class="sub">range {s101['minPoolSize']}–{s101['maxPoolSize']}</div>
      </div>
      <div class="stat-card">
        <div class="lbl">Containment (hit6)</div>
        <div class="val">{s101['containment']:,} / {s101['n']:,}</div>
        <div class="sub">{s101['containmentPct']:.2f}%</div>
      </div>
      <div class="stat-card">
        <div class="lbl">In-sample overlap</div>
        <div class="val">{inSample101} / {s101['n']}</div>
        <div class="sub">#{B101_LO}–{SCAN_WINDOW_HI}</div>
      </div>
    </div>
    <div class="tbl-wrap">
      <table class="stats-table">
        <thead><tr>
          <th>Tier</th><th>Observed</th><th>Expected</th><th>Lift</th><th>χ²</th><th class="tc">df</th><th>p-value</th><th class="tc">Significant?</th>
        </tr></thead>
        <tbody>{tier101_html}</tbody>
      </table>
    </div>
  </div>

  <div class="section">
    <h2>Backtest results — wider window, #{B250_LO}–{B250_HI} ({s250['n']} draws)</h2>
    <p class="desc"><strong style="color:#fca5a5">{inSample250} of {s250['n']} draws overlap the PCG64 seed's selection
    window</strong> &mdash; a majority, so read this window's results with the most caution.</p>
    <div class="stats-row">
      <div class="stat-card">
        <div class="lbl">Average pool size</div>
        <div class="val">{s250['avgPoolSize']:.2f}</div>
        <div class="sub">range {s250['minPoolSize']}–{s250['maxPoolSize']}</div>
      </div>
      <div class="stat-card">
        <div class="lbl">Containment (hit6)</div>
        <div class="val">{s250['containment']:,} / {s250['n']:,}</div>
        <div class="sub">{s250['containmentPct']:.2f}%</div>
      </div>
      <div class="stat-card">
        <div class="lbl">In-sample overlap</div>
        <div class="val">{inSample250} / {s250['n']}</div>
        <div class="sub">#{B250_LO}–{SCAN_WINDOW_HI}</div>
      </div>
    </div>
    <div class="tbl-wrap">
      <table class="stats-table">
        <thead><tr>
          <th>Tier</th><th>Observed</th><th>Expected</th><th>Lift</th><th>χ²</th><th class="tc">df</th><th>p-value</th><th class="tc">Significant?</th>
        </tr></thead>
        <tbody>{tier250_html}</tbody>
      </table>
    </div>
  </div>

  <div class="section">
    <h2>Per-draw breakdown — #{B250_LO}–{B250_HI} ({s250['n']} draws)</h2>
    <p class="desc">Every backtested draw across the full 250-draw window: the intersection pool (walk-forward, click
    "pool" to expand), the actual winning numbers (green = caught by the pool, purple = bonus caught too, amber = bonus
    missed, gray = missed entirely), and the resulting hit tier. Newest draws first by default.</p>
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
      <input id="pdSearch" type="number" placeholder="e.g. 2130" oninput="pdApplyFilter()">
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
    Xoshiro256** (SplitMix64-seeded): picks = partial Fisher-Yates(range(1,44), {K}) with combined seed = seed×10⁷ + draw_serial.
    PCG64 (O'Neill XSL-RR 128/64): combined seed expanded into raw 128-bit {{state,inc}} via SplitMix64 run 4x, verified
    bit-exact against <code>numpy.random.Generator(PCG64())</code>. Both recomputed live above and checked against
    server-embedded references.<br>
    Chi-square goodness-of-fit (df=1) computed via the exact relation to the standard normal CDF: p = 1 &minus; erf(&radic;(χ²/2)).<br>
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

// ── PCG64 (O'Neill XSL-RR 128/64), bit-exact BigInt port (same as
// pcg64_seed_scan_k38.html — verified against numpy.random.Generator(PCG64())). ──
const MASK128 = (1n << 128n) - 1n;
const PCG_MULT_128 = 0x2360ed051fc65da44385df649fccf645n;
function expandSeedToPcgState(combined) {{
  let z = combined & MASK64;
  const outs = [];
  for (let i = 0; i < 4; i++) {{
    const [nz, o] = splitmix64Next(z);
    z = nz;
    outs.push(o);
  }}
  const state = ((outs[0] << 64n) | outs[1]) & MASK128;
  const inc = (((outs[2] << 64n) | outs[3]) | 1n) & MASK128;
  return [state, inc];
}}
function rotr64(v, rot) {{
  rot &= 63n;
  const shift = (64n - rot) % 64n;
  return ((v >> rot) | (v << shift)) & MASK64;
}}
function pcg64Next(state, inc) {{
  state = (state * PCG_MULT_128 + inc) & MASK128;
  const xored = (state >> 64n) ^ (state & MASK64);
  const rot = (state >> 122n) & 0x3fn;
  const out = rotr64(xored, rot);
  return [state, out];
}}
function pcg64PredictRaw(seed, drawSerial, k) {{
  const combined = (BigInt(seed) * 10000000n + BigInt(drawSerial)) & MASK64;
  let [state, inc] = expandSeedToPcgState(combined);
  const arr = Array.from({{length: 43}}, (_, i) => i + 1);
  const n = arr.length;
  const order = [];
  for (let i = n - 1; i >= n - k; i--) {{
    const [ns, r] = pcg64Next(state, inc);
    state = ns;
    const j = Number(r % BigInt(i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
    order.push(arr[i]);
  }}
  return order;
}}
function pcg64Predict(seed, drawSerial, k) {{
  return pcg64PredictRaw(seed, drawSerial, k).slice().sort((a, b) => a - b);
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

// PCG64 side
const livePcg = pcg64Predict({SEED_PCG}, {TARGET_SERIAL}, {K});
const livePcgOrdered = pcg64PredictRaw({SEED_PCG}, {TARGET_SERIAL}, {K});
const KNOWN_PCG = {json.dumps(pcg_pool)};
const KNOWN_PCG_ORDERED = {json.dumps(pcg_pool_ordered)};
renderBalls('pcgBalls', livePcg, 'b4');
renderBalls('pcgBallsOrdered', livePcgOrdered, 'b4');
renderBadge('badgePcg', arraysEqual(livePcg, KNOWN_PCG));
renderBadge('badgePcgOrdered', arraysEqual(livePcgOrdered, KNOWN_PCG_ORDERED));
if (!arraysEqual(livePcg, KNOWN_PCG)) console.error('PCG64 mismatch', livePcg, KNOWN_PCG);
if (!arraysEqual(livePcgOrdered, KNOWN_PCG_ORDERED)) console.error('PCG64 (generation order) mismatch', livePcgOrdered, KNOWN_PCG_ORDERED);

// Intersection
const liveIntersect = liveXo.filter(n => livePcg.includes(n)).sort((a, b) => a - b);
const KNOWN_INTERSECT = {json.dumps(current_pool)};
renderBalls('intersectBalls', liveIntersect, 'b2');
renderBadge('badgeCurrent', arraysEqual(liveIntersect, KNOWN_INTERSECT));
if (!arraysEqual(liveIntersect, KNOWN_INTERSECT)) console.error('Intersection mismatch', liveIntersect, KNOWN_INTERSECT);

// ── Per-draw breakdown table: paginated + filterable, newest-first ─────────
const PER_DRAW = {js_per_draw};
const PD_PAGE_SIZE = 25;
let pdFiltered = PER_DRAW;
let pdCurPage = 0;
const pdExpanded = new Set();

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
