"""
gen_xoshiro_elim_2134.py
----------------------------
Generates the "Xoshiro K=38 x Modular Cycle (native K=38) + 16-Method
Elimination" page for draw #2134 -- the true next-upcoming Loto6 draw
(#2133 is now the latest real/confirmed draw). Reads
xoshiro_elim_2134_meta.json (small: pool picks, method picks, counts)
produced by precompute_xoshiro_elim_2134.py. The large remaining-combo
list lives separately at public/xoshiro_elim_2134_combos.json (already
written by the precompute script) and is fetched client-side, not
inlined.

Adapted from gen_xoshiro_elim_2133.py with two deliberate changes, per
explicit user request:

1. Base's Modular Cycle side is now the NATIVE K=38 pick (direct
   frequency-rank top-38 for the target draw's mod-43 residue class),
   not the cross-method-consensus-padded K=33 pick used on the #2133
   page. This is the same construction as
   xoshiro_k38_x_modularcycle_k38_stats.html, which found it produced
   a striking real-world result for #2133 (full hit6b -- all 7 numbers
   including bonus caught) even though it is NOT statistically
   significant in aggregate across the #44-2132 backtest window (all
   of hit6b/hit6/hit5/hit4 p>0.05). Modular Cycle's pick stays
   server-computed/embedded only (same "na" badge convention as the
   #2133 page) -- native ranking COULD run client-side cheaply (see
   the stats page's modularCycleRanked() JS), but that would require
   embedding full historical draw data that isn't in this page's
   meta.json, and the user's ask was to follow the #2133 page's
   structure, not extend it further.

2. Passes 7-10 (the four "recent-draw overlap" heuristic filters) are
   REMOVED entirely -- per this site's own analysis, none of them
   clear a 5% significance threshold (Pass 7's binomial test: p=0.071;
   Pass 10's pooled 100,000-comparison check: observed rate matches
   chance almost exactly). In their place is a single new final Pass 7
   -- overlap 5 or 6 with the immediately previous draw (#2133) -- which
   IS well-supported: 0 occurrences among every consecutive real-draw
   pair in the site's history. This is a stronger, narrower claim than
   the removed passes' "overlap 3, 4, or 5" criterion (which included
   the not-significant 3-and-4 tiers).

Output: public/xoshiro_elim_2134.html
Run: python gen_xoshiro_elim_2134.py
"""
import json

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
META_PATH = BASE + r"\xoshiro_elim_2134_meta.json"
HTML_OUT = BASE + r"\public\xoshiro_elim_2134.html"

with open(META_PATH, encoding='utf-8') as f:
    meta = json.load(f)

TARGET_SERIAL = meta['targetSerial']
TRAINED_THROUGH = meta['trainedThroughSerial']
xo = meta['xo']
mc = meta['mc']
base = meta['base']
method_names = meta['methodNames']
method_picks = meta['methodPicks']
method_k = meta['methodK']
universe_count = meta['universeCount']
removed_by_methods = meta['removedByMethods']
final_remaining_pass1 = meta['finalRemainingPass1']
pass1_pct = final_remaining_pass1 / universe_count * 100

pass2_k = meta['pass2K']
pass2_seeds = meta['pass2Seeds']
removed_by_pass2 = meta['removedByPass2']
final_remaining_pass2 = meta['finalRemainingPass2']
pass2_pct = final_remaining_pass2 / universe_count * 100
pass2_pct_of_pass1 = final_remaining_pass2 / final_remaining_pass1 * 100

historical_draw_count = meta['historicalDrawCount']
historical_combos = meta['historicalCombos']
removed_historical = meta['removedHistorical']
final_remaining_pass3 = meta['finalRemainingPass3']
pass3_pct = final_remaining_pass3 / universe_count * 100
pass3_pct_of_pass2 = final_remaining_pass3 / final_remaining_pass2 * 100

pass4_k = meta['pass4K']
pass4_pick = meta['pass4Pick']
pass4_overlap = meta['pass4Overlap']
removed_by_pass4 = meta['removedByPass4']
final_remaining_pass4 = meta['finalRemainingPass4']
pass4_pct = final_remaining_pass4 / universe_count * 100
pass4_pct_of_pass3 = final_remaining_pass4 / final_remaining_pass3 * 100

removed_by_pass5 = meta['removedByPass5']
pass5_run_distribution = meta['pass5RunDistribution']
final_remaining_pass5 = meta['finalRemainingPass5']
pass5_pct = final_remaining_pass5 / universe_count * 100
pass5_pct_of_pass4 = final_remaining_pass5 / final_remaining_pass4 * 100

removed_by_pass6 = meta['removedByPass6']
final_remaining_pass6 = meta['finalRemainingPass6']
pass6_pct = final_remaining_pass6 / universe_count * 100
pass6_pct_of_pass5 = final_remaining_pass6 / final_remaining_pass5 * 100

pass7_prev_draw_serial = meta['pass7PrevDrawSerial']
pass7_prev_draw_nums = meta['pass7PrevDrawNums']
removed_by_pass7 = meta['removedByPass7']
pass7_overlap_distribution = meta['pass7OverlapDistribution']
final_remaining = meta['finalRemaining']
final_pct = final_remaining / universe_count * 100
pass7_pct_of_pass6 = final_remaining / final_remaining_pass6 * 100
pass7_pairs_count = historical_draw_count - 1  # consecutive real-draw pairs, #1-TRAINED_THROUGH

methods_rows_html = ""
for name, pool in zip(method_names, method_picks):
    balls = "".join(f'<span class="nb">{n}</span>' for n in pool)
    methods_rows_html += f"""<tr><td class="mname">{name}</td><td><div class="balls">{balls}</div></td></tr>"""

pass2_rows_html = ""
for p2 in pass2_seeds:
    balls = "".join(f'<span class="nb">{n}</span>' for n in p2['pick'])
    pass2_rows_html += f"""<tr><td class="mname">seed #{p2['seed']}</td><td><div class="balls">{balls}</div></td></tr>"""

historical_rows_html = ""
for combo in removed_historical:
    balls = "".join(f'<span class="nb">{n}</span>' for n in combo)
    historical_rows_html += f"""<tr><td><div class="balls">{balls}</div></td></tr>"""

page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Xoshiro K=38 x Modular Cycle (native K=38) + 16-Method Elimination — Draw #{TARGET_SERIAL}</title>
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

.section{{background:#0d1526;border:1px solid #1e293b;border-radius:12px;padding:20px;margin-bottom:20px}}
.section h2{{font-size:1rem;font-weight:700;color:#f1f5f9;margin-bottom:4px;display:flex;align-items:center;gap:8px}}
.section h3{{font-size:.86rem;font-weight:700;color:#cbd5e1;margin:14px 0 6px}}
.order-label{{font-size:.7rem;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:.04em;
  margin:10px 0 5px;display:flex;align-items:center;gap:8px}}
.order-hint{{font-size:.72rem;font-weight:400;text-transform:none;letter-spacing:normal;color:#475569}}
.section .desc{{font-size:.8rem;color:#64748b;margin-bottom:14px}}
.verify-badge{{font-size:.68rem;font-weight:700;padding:2px 8px;border-radius:10px;text-transform:uppercase;letter-spacing:.04em}}
.verify-badge.pending{{background:#1e293b;color:#94a3b8}}
.verify-badge.ok{{background:#14532d;color:#86efac}}
.verify-badge.fail{{background:#450a0a;color:#fca5a5}}
.verify-badge.na{{background:#1e293b;color:#64748b}}

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
.stat-card.final .val{{color:#38bdf8}}

.elim-flow{{font-size:1rem;color:#e2e8f0;text-align:center;padding:16px;background:#0a0f1e;
  border:1px solid #1e293b;border-radius:10px;font-weight:600;letter-spacing:.02em}}
.elim-flow .arrow{{color:#64748b;margin:0 10px}}
.elim-flow .n{{color:#f1f5f9}}
.elim-flow .final{{color:#38bdf8}}

details{{background:#0a0f1e;border:1px solid #1e293b;border-radius:10px;padding:12px 16px}}
summary{{cursor:pointer;font-size:.85rem;font-weight:600;color:#e2e8f0;user-select:none}}
summary:hover{{color:#f1f5f9}}
.methods-table{{width:100%;border-collapse:collapse;font-size:.82rem;margin-top:12px}}
.methods-table td{{padding:7px 10px;border-bottom:1px solid #1e293b;vertical-align:middle}}
.methods-table td.mname{{color:#94a3b8;white-space:nowrap;font-weight:600;width:180px}}
.methods-table .nb{{width:26px;height:26px;font-size:.7rem;background:#1e293b;color:#94a3b8;border:none}}

.lookup{{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:14px}}
.lookup .btn{{padding:6px 14px;background:#1e293b;border:1px solid #334155;border-radius:7px;
  color:#94a3b8;font-size:.8rem;cursor:pointer}}
.lookup .btn:hover{{color:#f1f5f9}}
.lookup .btn.primary{{background:#7c3aed;border-color:#7c3aed;color:#fff}}
.lookup .btn.primary:hover{{background:#6d28d9}}
.lookup .btn:disabled{{opacity:.4;cursor:default}}
.filter-grid{{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:10px}}
.num-btn{{display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;
  border-radius:50%;font-size:.72rem;font-weight:700;color:#fff;background:#312e5f;
  border:none;cursor:pointer;opacity:.65;transition:all .12s;flex-shrink:0}}
.num-btn:hover{{opacity:.9}}
.num-btn.include{{opacity:1;box-shadow:0 0 0 2px #0a0f1e,0 0 0 4px #22c55e;transform:scale(1.08)}}
.num-btn.exclude{{opacity:.55;box-shadow:0 0 0 2px #0a0f1e,0 0 0 4px #ef4444;transform:scale(1.08);
  text-decoration:line-through;text-decoration-thickness:2px}}
.filter-legend{{font-size:.72rem;color:#64748b;margin-bottom:8px}}
.filter-legend .swatch{{display:inline-flex;align-items:center;justify-content:center;width:16px;height:16px;
  border-radius:50%;font-size:0;margin:0 3px -3px 0}}
.filter-legend .swatch.neutral{{background:#312e5f;opacity:.65}}
.filter-legend .swatch.include{{background:#312e5f;box-shadow:0 0 0 1px #0a0f1e,0 0 0 2px #22c55e}}
.filter-legend .swatch.exclude{{background:#312e5f;opacity:.55;box-shadow:0 0 0 1px #0a0f1e,0 0 0 2px #ef4444}}
.page-info{{font-size:.8rem;color:#94a3b8}}
.tbl-wrap{{overflow-x:auto;border-radius:10px;border:1px solid #1e293b}}
table.combos{{width:100%;border-collapse:collapse;font-size:.83rem}}
table.combos th{{background:#0a0f1e;padding:8px 12px;text-align:left;color:#94a3b8;
  font-weight:600;font-size:.7rem;text-transform:uppercase;letter-spacing:.05em;
  border-bottom:1px solid #1e293b}}
table.combos td{{padding:6px 12px;border-bottom:1px solid #0f172a}}
table.combos tr:hover td{{background:#111827}}
#loadingMsg{{padding:30px;text-align:center;color:#64748b;font-size:.85rem}}

.footer{{margin-top:28px;font-size:.78rem;color:#475569;padding-bottom:20px;line-height:1.6}}
</style>
</head>
<body>

<script src="/site-nav.js"></script>
<div class="wrap">
  <h1>✂️ Xoshiro K=38 × Modular Cycle (native K=38) + 16-Method Elimination — Draw #{TARGET_SERIAL}</h1>
  <p class="subtitle">Combinatorial set-difference: (Modular Cycle native K=38 ∩ xoshiro K=38) pick, minus combos covered by any of the 16 prediction methods' K={method_k} picks, minus a handful of well-supported pattern filters</p>

  <div class="note">
    <p><strong style="color:#e2e8f0">Base</strong> (below) is <strong>Modular Cycle's NATIVE K={mc['k']} pick</strong> &mdash; the
    direct top-{mc['k']} numbers by mod-43-residue frequency rank, with <em>no cross-method-consensus padding</em> &mdash;
    intersected with <strong>xoshiro256** K={xo['k']} seed #{xo['seed']:,}'s pick</strong>, both for draw #{TARGET_SERIAL},
    walk-forward trained on all real draws through #{TRAINED_THROUGH} (the latest real/confirmed draw). This is a different
    construction from <a href="/xoshiro_elim_2133.html" style="color:#a78bfa">the #2133 elimination page</a>, which used
    Modular Cycle's cross-method-padded K=33 pick; see
    <a href="/xoshiro_k38_x_modularcycle_k38_stats.html" style="color:#a78bfa">the native-K38×K38 stats page</a> for the
    full walk-forward backtest of this construction. It defines the working universe: all C({base['k']},6) = {universe_count:,}
    six-number combinations drawable from this {base['k']}-number pool.</p>
    <p><strong style="color:#fbbf24">Why this construction, for this draw specifically:</strong> for #{pass7_prev_draw_serial}
    (the draw just before this one), this exact native-K38×K38 Base fully contained the real winning combo
    &mdash; all 6 main numbers <em>and</em> the bonus &mdash; while the K33-padded Base used on the #2133 elimination page
    missed it (it was short one number). That's one data point, not a validated edge: the stats page's full walk-forward
    backtest across #44&ndash;2132 finds this construction is <em>not</em> statistically significant in aggregate on any
    tier (hit6b/hit6/hit5/hit4 all p&gt;0.05 vs. the hypergeometric chance baseline). It's used here because it happens to
    be the most promising Base construction on the site right now, not because it's been proven to work.</p>
    <p><strong style="color:#e2e8f0">Pass 1</strong> is each of the 16 prediction methods' K={method_k} pick for draw #{TARGET_SERIAL}, computed
    walk-forward (trained on all {TRAINED_THROUGH:,} real draws through #{TRAINED_THROUGH}) then normalized to exactly {method_k} numbers via the same
    cross-method-consensus trim/pad algorithm as <a href="/backtest.html" style="color:#a78bfa">backtest.html</a>'s <code>topKNums()</code>.
    Any of Base's combos fully contained within ANY single one of these 16 sets gets removed, leaving {final_remaining_pass1:,}.</p>
    <p><strong style="color:#e2e8f0">Pass 2</strong> is <a href="/xoshiro_seed_backtest.html" style="color:#a78bfa">xoshiro256**</a>
    K={pass2_k} seeds {', '.join(str(p2['seed']) for p2 in pass2_seeds)} &mdash; the same K=21 algorithm used on the 0&ndash;1,000
    seed page. Each seed's K={pass2_k} pick for draw #{TARGET_SERIAL} uses the same verified xoshiro256** implementation as Base's
    xoshiro side. Any Pass-1-remaining combo fully contained within ANY single one of these {len(pass2_seeds)} picks gets removed,
    leaving {final_remaining_pass2:,}.</p>
    <p><strong style="color:#e2e8f0">Pass 3</strong> is a historical repeat filter &mdash; the same "zero repeats in
    history" pattern used throughout this site's elimination pages. Any Pass-2-remaining combo that exactly matches an actual
    6-number winning combo from any of the {historical_draw_count:,} real draws (#1&ndash;{TRAINED_THROUGH}) gets removed, leaving
    {final_remaining_pass3:,}. No K=6 Loto 6 combo has ever repeated across {historical_draw_count:,} draws, so this pass strictly
    removes exact historical matches, not near-misses.</p>
    <p><strong style="color:#e2e8f0">Pass 4</strong> is the Worst Combo (Anti-Pick) K={pass4_k} pick for draw #{TARGET_SERIAL}
    &mdash; the MA-43 + Exp-weighted + Random Forest + kNN + Apriori Association Rules consensus, same 5-method combination as
    <a href="/predictions" style="color:#a78bfa">the Predictions page's</a> Worst Combo panel. Any Pass-3-remaining combo fully
    contained within this {pass4_k}-number pick gets removed. These 5 methods can't all run client-side, so the pick is computed
    directly here (from the same 5 methods' native picks above, indices into Pass 1's 16-method table, using the same
    union-count-desc-then-ascending-number combining rule as the Predictions page's own consensus logic) and embedded as static
    data, same convention as Modular Cycle's pick.</p>
    <p><strong style="color:#e2e8f0">Pass 5</strong> removes any Pass-4-remaining combo containing a run of 3 or more
    consecutive numbers &mdash; based on the historical finding that only 6.62% of all real Loto6 draws through #{TRAINED_THROUGH}
    have such a run (a run of 5 or 6 has never happened), so this pass removes combos matching that same rare pattern. Any
    Pass-4-remaining combo with max consecutive run &ge;3 gets removed, leaving {final_remaining_pass5:,}.</p>
    <p><strong style="color:#e2e8f0">Pass 6</strong> removes any Pass-5-remaining combo that decomposes into exactly
    three consecutive pairs &mdash; each a run of exactly 2, no run of 3+, no isolated singles (e.g. 1,2,9,10,15,16) &mdash;
    a pattern matched by only a small handful of real Loto6 draws to date. Any Pass-5-remaining combo matching it gets removed,
    leaving {final_remaining_pass6:,}.</p>
    <p><strong style="color:#e2e8f0">Pass 7</strong> (final) removes any Pass-6-remaining combo that shares 5 or 6 numbers
    with the immediately previous actual draw ("1 step back") &mdash; #{pass7_prev_draw_serial}: {', '.join(str(n) for n in pass7_prev_draw_nums)}.
    Unlike the "3, 4, or 5 overlap" heuristics used on earlier elimination pages (which this page deliberately drops &mdash;
    see below), this narrower 5-or-6 criterion has a clean historical basis: across all {pass7_pairs_count:,} consecutive
    real-draw pairs on this site (#1&ndash;{TRAINED_THROUGH}), an overlap of 5 or 6 numbers between adjacent draws has
    <strong style="color:#86efac">never once occurred</strong> (0/{pass7_pairs_count:,}). Leaves
    <strong style="color:#38bdf8">{final_remaining:,}</strong>.</p>
    <p style="color:#fca5a5"><strong>Why passes 7&ndash;10 from earlier elimination pages (e.g. #2133) are dropped here:</strong>
    those pages removed any combo overlapping 3, 4, <em>or</em> 5 numbers with a recent draw, at increasing scope (1/2/3 steps
    back, then the last 100 draws at once). This site's own significance testing found that heuristic doesn't hold up &mdash;
    the 1-step-back version's binomial test came back p=0.071 (missing the conventional 5% threshold, with the 4-overlap tier
    actually running <em>above</em> chance), and a pooled ~100,000-comparison check behind the broadest version landed within
    a few hundredths of a percent of the exact chance rate at every tier. The 5-or-6-overlap case is different in kind, not
    just degree: it isn't a "somewhat rarer than chance" claim needing a significance test to distinguish from noise, it's a
    hard zero across the entire dataset &mdash; the strongest empirical basis of any filter used on this site. This page keeps
    only that one, well-supported case.</p>
    <p>The xoshiro side of Base, all {len(pass2_seeds)} Pass-2 picks, and Passes 5&ndash;7's pattern checks are recomputed
    <strong>live in your browser</strong> below (bit-exact BigInt xoshiro256** port for Base and Pass 2, plain JS for Passes
    5&ndash;7) and checked against a server-embedded reference &mdash; check the verification badges. Modular Cycle's native
    pick, Pass 1's 16 statistical/ML methods (ARIMA, Random Forest, HMM, LSTM, etc.), and Pass 4's Worst Combo pick can't
    (practically) run in a browser, so those are precomputed server-side, same as every other draw on this site, and embedded
    as static data. Pass 3's historical combo set is embedded and checked client-side too.</p>
  </div>

  <div class="section">
    <h2>Base — Modular Cycle native K={mc['k']} ∩ xoshiro K={xo['k']} seed #{xo['seed']:,} <span id="badgeBase" class="verify-badge pending">verifying…</span></h2>
    <p class="desc">Modular Cycle: walk-forward pick trained on all real draws through #{TRAINED_THROUGH}, NATIVE K={mc['k']}
    &mdash; direct top-{mc['k']} by mod-43-residue frequency rank, no cross-method padding (server-computed). Xoshiro: current
    overall best K=38 seed (0&ndash;1,000,000 scan), computed live below. Base = their intersection &mdash; this {base['k']}-number
    pool is the elimination universe.</p>
    <h3>Modular Cycle native K={mc['k']} pick <span class="verify-badge na">server-computed</span></h3>
    <div class="order-label">Ascending order</div>
    <div class="balls" id="mcBalls"></div>
    <div class="order-label">Generation order <span class="order-hint">(mod-43-cycle frequency rank, before sorting)</span></div>
    <div class="balls" id="mcBallsOrdered"></div>
    <h3>Xoshiro K={xo['k']} seed #{xo['seed']:,} pick <span id="badgeXo" class="verify-badge pending">verifying…</span></h3>
    <div class="order-label">Ascending order</div>
    <div class="balls" id="xoBalls"></div>
    <div class="order-label">Generation order <span class="order-hint">(partial Fisher-Yates shuffle order)</span> <span id="badgeXoOrdered" class="verify-badge pending">verifying…</span></div>
    <div class="balls" id="xoBallsOrdered"></div>
    <h3>Base (intersection)</h3>
    <div class="balls" id="baseBalls"></div>
  </div>

  <div class="section">
    <h2>Pass 1 — 16 prediction methods, K={method_k} pick for draw #{TARGET_SERIAL}</h2>
    <p class="desc">Precomputed server-side (walk-forward, trained on all real draws through #{TRAINED_THROUGH}), normalized to K={method_k} via cross-method consensus.</p>
    <details>
      <summary>Show all 16 methods' picks</summary>
      <table class="methods-table">
        <tbody>{methods_rows_html}</tbody>
      </table>
    </details>
  </div>

  <div class="section">
    <h2>Pass 2 — xoshiro256** K={pass2_k} seeds {', '.join(str(p2['seed']) for p2 in pass2_seeds)}, pick for draw #{TARGET_SERIAL} <span id="badgePass2" class="verify-badge pending">verifying…</span></h2>
    <p class="desc">Same xoshiro256** implementation as Base's xoshiro side, K={pass2_k} (the same K used on <a href="/xoshiro_seed_backtest.html" style="color:#a78bfa">the 0&ndash;1,000 seed page</a>). Picks recomputed live below and checked against server-embedded references.</p>
    <table class="methods-table">
      <tbody>{pass2_rows_html}</tbody>
    </table>
  </div>

  <div class="section">
    <h2>Pass 3 — historical repeat filter <span id="badgeHistorical" class="verify-badge pending">verifying…</span></h2>
    <p class="desc">Removes any Pass-2-remaining combo that exactly matches a real 6-number winning combo from the {historical_draw_count:,}
    draws #1&ndash;{TRAINED_THROUGH}. Checked live in your browser against the same embedded historical combo set. {len(removed_historical)} matches found.</p>
    {f"<details><summary>Show all {len(removed_historical):,} removed combos (exact match to a historical winning combo)</summary><table class='methods-table'><thead><tr><th>Removed &mdash; exact match to a historical winning combo</th></tr></thead><tbody>" + historical_rows_html + "</tbody></table></details>" if removed_historical else "<p style='color:#64748b;font-size:.85rem'>No matches found &mdash; nothing removed by this pass.</p>"}
  </div>

  <div class="section">
    <h2>Pass 4 — Worst Combo (Anti-Pick), K={pass4_k} pick for draw #{TARGET_SERIAL} <span class="verify-badge na">server-computed</span></h2>
    <p class="desc">Same 5-method combination as <a href="/predictions" style="color:#a78bfa">the Predictions page's</a> Worst Combo
    panel &mdash; MA-43 + Exp-weighted + Random Forest + kNN + Apriori Association Rules consensus &mdash; computed directly here
    for #{TARGET_SERIAL} to keep this script self-contained. Overlap with the {base['k']}-pool: {pass4_overlap} numbers.</p>
    <div class="balls">{"".join(f'<span class="nb">{n}</span>' for n in pass4_pick)}</div>
  </div>

  <div class="section">
    <h2>Pass 5 — no 3+/4+/5+/6-length consecutive-run filter <span id="badgePass5" class="verify-badge pending">verifying…</span></h2>
    <p class="desc">Removes any Pass-4-remaining combo whose sorted main numbers contain a run of 3 or more consecutive integers
    (e.g. 5,6,7). Historical basis: across real Loto6 draws through #{TRAINED_THROUGH}, runs of 3+ collectively occur in only
    about 6.62% of real draws, and a run of 5 or 6 has never happened. Checked live in your browser (pure JS, no server
    reference needed &mdash; this pass only looks at each combo's own sorted numbers).</p>
    <p class="desc" style="margin-bottom:0">Max-run distribution among the {final_remaining_pass4:,} Pass-4-remaining combos:
    {' &middot; '.join(f'run={k}: {int(v):,}' for k, v in pass5_run_distribution.items())}.</p>
  </div>

  <div class="section">
    <h2>Pass 6 — three consecutive pairs filter <span id="badgePass6" class="verify-badge pending">verifying…</span></h2>
    <p class="desc">Removes any Pass-5-remaining combo whose sorted main numbers decompose into exactly three consecutive pairs
    (each run exactly 2, no run of 3+, no isolated singles &mdash; e.g. 1,2,9,10,15,16). Historical basis: only a small handful
    of real Loto6 draws to date match this exact pattern. Checked live in your browser (pure JS, no server reference needed).</p>
    <p class="desc" style="margin-bottom:0">Removed {len(removed_by_pass6):,} combos matching this pattern &mdash; e.g.
    {', '.join(str(tuple(c)) for c in removed_by_pass6[:5])}{', ...' if len(removed_by_pass6) > 5 else ''}.</p>
  </div>

  <div class="section">
    <h2>Pass 7 (final) — "5-or-6 overlap, 1 step back" filter <span id="badgePass7" class="verify-badge pending">verifying…</span>
    <span class="verify-badge" style="background:#14532d;color:#86efac">well-supported (0/{pass7_pairs_count:,})</span></h2>
    <p class="desc">Removes any Pass-6-remaining combo that shares 5 or 6 numbers with the immediately previous
    actual draw &mdash; #{pass7_prev_draw_serial}: <span class="balls" style="display:inline-flex;vertical-align:middle">{"".join(f'<span class="nb">{n}</span>' for n in pass7_prev_draw_nums)}</span>. Historical basis: across all
    {pass7_pairs_count:,} consecutive real-draw pairs on this site (#1&ndash;{TRAINED_THROUGH}), a 5-or-6 overlap between adjacent
    draws has never once occurred &mdash; a hard 0/{pass7_pairs_count:,}, not a "somewhat rarer than chance" claim needing a
    significance test. This is a narrower, stronger criterion than the "3, 4, or 5 overlap" filters dropped from earlier
    elimination pages (see the note above). Checked live in your browser (pure JS, no server reference needed &mdash; this
    pass only compares each combo's own numbers against the embedded previous-draw numbers).</p>
    <p class="desc" style="margin-bottom:0">Overlap distribution among the {final_remaining_pass6:,} Pass-6-remaining combos:
    {' &middot; '.join(f'overlap={k}: {int(v):,}' for k, v in pass7_overlap_distribution.items())}. Removed
    {len(removed_by_pass7):,} combos with overlap 5 or 6 &mdash; e.g.
    {', '.join(str(tuple(c)) for c in removed_by_pass7[:5])}{', ...' if len(removed_by_pass7) > 5 else ''}. Final remaining:
    <strong style="color:#38bdf8">{final_remaining:,}</strong>.</p>
  </div>

  <div class="section">
    <h2>Elimination summary</h2>
    <div class="stats-row">
      <div class="stat-card">
        <div class="lbl">Universe (Base)</div>
        <div class="val">{universe_count:,}</div>
        <div class="sub">C({base['k']},6)</div>
      </div>
      <div class="stat-card">
        <div class="lbl">Removed by 16 methods (Pass 1)</div>
        <div class="val">{removed_by_methods:,}</div>
        <div class="sub">contained in ANY method's K={method_k}</div>
      </div>
      <div class="stat-card">
        <div class="lbl">After Pass 1</div>
        <div class="val">{final_remaining_pass1:,}</div>
        <div class="sub">{pass1_pct:.1f}% of universe retained</div>
      </div>
      <div class="stat-card">
        <div class="lbl">Removed by {len(pass2_seeds)} xoshiro K={pass2_k} seeds (Pass 2)</div>
        <div class="val">{removed_by_pass2:,}</div>
        <div class="sub">contained in ANY seed's K={pass2_k}</div>
      </div>
      <div class="stat-card">
        <div class="lbl">After Pass 2</div>
        <div class="val">{final_remaining_pass2:,}</div>
        <div class="sub">{pass2_pct:.1f}% of universe retained</div>
      </div>
      <div class="stat-card">
        <div class="lbl">Removed by historical repeat filter (Pass 3)</div>
        <div class="val">{len(removed_historical):,}</div>
        <div class="sub">exact match to a real winning combo</div>
      </div>
      <div class="stat-card">
        <div class="lbl">After Pass 3</div>
        <div class="val">{final_remaining_pass3:,}</div>
        <div class="sub">{pass3_pct:.1f}% of universe retained</div>
      </div>
      <div class="stat-card">
        <div class="lbl">Removed by Worst Combo K={pass4_k} (Pass 4)</div>
        <div class="val">{removed_by_pass4:,}</div>
        <div class="sub">contained in the anti-pick's K={pass4_k}</div>
      </div>
      <div class="stat-card">
        <div class="lbl">After Pass 4</div>
        <div class="val">{final_remaining_pass4:,}</div>
        <div class="sub">{pass4_pct:.1f}% of universe retained</div>
      </div>
      <div class="stat-card">
        <div class="lbl">Removed by consecutive-run filter (Pass 5)</div>
        <div class="val">{removed_by_pass5:,}</div>
        <div class="sub">max run of 3+ consecutive numbers</div>
      </div>
      <div class="stat-card">
        <div class="lbl">After Pass 5</div>
        <div class="val">{final_remaining_pass5:,}</div>
        <div class="sub">{pass5_pct:.1f}% of universe retained</div>
      </div>
      <div class="stat-card">
        <div class="lbl">Removed by three-pairs filter (Pass 6)</div>
        <div class="val">{len(removed_by_pass6):,}</div>
        <div class="sub">exactly three consecutive pairs</div>
      </div>
      <div class="stat-card">
        <div class="lbl">After Pass 6</div>
        <div class="val">{final_remaining_pass6:,}</div>
        <div class="sub">{pass6_pct:.1f}% of universe retained</div>
      </div>
      <div class="stat-card">
        <div class="lbl">Removed by 5-or-6-overlap filter (Pass 7)</div>
        <div class="val">{len(removed_by_pass7):,}</div>
        <div class="sub">overlap 5 or 6 · 1 step back · 0/{pass7_pairs_count:,} historically</div>
      </div>
      <div class="stat-card final">
        <div class="lbl">Final remaining</div>
        <div class="val">{final_remaining:,}</div>
        <div class="sub">{final_pct:.1f}% of universe · {pass7_pct_of_pass6:.1f}% of Pass-6 output</div>
      </div>
    </div>
    <div class="elim-flow">
      <span class="n">{universe_count:,}</span>
      <span class="arrow">&rarr;</span>
      <span class="n">{final_remaining_pass1:,}</span> <span style="color:#64748b;font-size:.7rem">(Pass 1)</span>
      <span class="arrow">&rarr;</span>
      <span class="n">{final_remaining_pass2:,}</span> <span style="color:#64748b;font-size:.7rem">(Pass 2)</span>
      <span class="arrow">&rarr;</span>
      <span class="n">{final_remaining_pass3:,}</span> <span style="color:#64748b;font-size:.7rem">(Pass 3)</span>
      <span class="arrow">&rarr;</span>
      <span class="n">{final_remaining_pass4:,}</span> <span style="color:#64748b;font-size:.7rem">(Pass 4)</span>
      <span class="arrow">&rarr;</span>
      <span class="n">{final_remaining_pass5:,}</span> <span style="color:#64748b;font-size:.7rem">(Pass 5)</span>
      <span class="arrow">&rarr;</span>
      <span class="n">{final_remaining_pass6:,}</span> <span style="color:#64748b;font-size:.7rem">(Pass 6)</span>
      <span class="arrow">&rarr;</span>
      <span class="n final">{final_remaining:,}</span> <span style="color:#64748b;font-size:.7rem">(Pass 7)</span>
    </div>
  </div>

  <div class="section">
    <h2>Browse remaining combinations</h2>
    <p class="desc">Fetched from a separate JSON asset (not inlined — {final_remaining:,} rows is too large for the page itself).</p>
    <div id="loadingMsg">Loading {final_remaining:,} combinations…</div>
    <div id="comboUI" style="display:none">
      <div class="lookup">
        <button class="btn" onclick="clearFilter()">Clear filter</button>
        <button class="btn primary" onclick="downloadCSV()">⬇ Download CSV</button>
        <span id="filterInfo" class="page-info"></span>
      </div>
      <div class="filter-legend">Click a number to cycle: <span class="swatch neutral"></span>neutral (no filter) &rarr;
        <span class="swatch include"></span>include (must contain) &rarr; <span class="swatch exclude"></span>exclude (must not
        contain) &rarr; back to neutral. Include and exclude constraints apply together.</div>
      <div class="filter-grid" id="filterGrid"></div>
      <div class="tbl-wrap">
        <div class="lookup" style="justify-content:space-between;padding:10px 12px;margin-bottom:0">
          <span id="pageInfo" class="page-info"></span>
          <div style="display:flex;gap:6px">
            <button class="btn" id="firstBtn" onclick="goPage(0)">&laquo; First</button>
            <button class="btn" id="prevBtn" onclick="goPage(curPage-1)">&lsaquo; Prev</button>
            <button class="btn" id="nextBtn" onclick="goPage(curPage+1)">Next &rsaquo;</button>
            <button class="btn" id="lastBtn" onclick="goPage(totalPages()-1)">Last &raquo;</button>
          </div>
        </div>
        <table class="combos">
          <thead><tr><th>#</th><th>Combination</th></tr></thead>
          <tbody id="comboBody"></tbody>
        </table>
      </div>
    </div>
  </div>

  <p class="footer">
    Xoshiro256** (seeded via SplitMix64): picks = partial Fisher-Yates(range(1,44), K) with combined seed = seed×10⁷ + draw_serial.
    Algorithm verified against independent reference sources — see <a href="/xoshiro_seed_backtest.html" style="color:#64748b">the 0–1000 seed page</a>.<br>
    16 methods: Poly Regression, Moving Avg-43, Exp-Weighted Avg, Frequency, Markov Chain, ARIMA(2,1,0), Random Forest, RL (Linear Q),
    HMM, k-NN, Modular Cycle, Apriori, Monte Carlo, Naive Bayes, Weighted MA-43, LSTM — same 16 used throughout
    <a href="/backtest.html" style="color:#64748b">backtest.html</a> / <a href="/predictions" style="color:#64748b">predictions</a>.<br>
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
  // Generation order -- the order the partial Fisher-Yates shuffle finalizes
  // each position (i = n-1 first, down to i = n-k last), NOT sorted. Same
  // convention as xoshiro_seed_scan_k38.html: push arr[i] right after each
  // swap, in loop order.
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

// ── Modular Cycle (native): server-computed, embedded (can't run ML/ranking in the browser here) ──
const MC_POOL = {json.dumps(mc['pool'])};
const MC_POOL_ORDERED = {json.dumps(mc['poolOrdered'])};
const KNOWN_BASE = {json.dumps(base['pool'])};

// ── Xoshiro side: compute live + verify against server-embedded reference ──
const liveXo = xoshiroPredict({xo['seed']}, {TARGET_SERIAL}, {xo['k']});
const liveXoOrdered = xoshiroPredictRaw({xo['seed']}, {TARGET_SERIAL}, {xo['k']});
const KNOWN_XO = {json.dumps(xo['pool'])};
const KNOWN_XO_ORDERED = {json.dumps(xo['poolOrdered'])};

// ── Base: client-side intersection of live xoshiro + embedded Modular Cycle ─
const liveBase = liveXo.filter(n => MC_POOL.includes(n)).sort((a, b) => a - b);

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

renderBalls('mcBalls', MC_POOL, 'b3');
renderBalls('mcBallsOrdered', MC_POOL_ORDERED, 'b3');
renderBalls('xoBalls', liveXo, 'b1');
renderBalls('xoBallsOrdered', liveXoOrdered, 'b1');
renderBalls('baseBalls', liveBase, 'b2');
renderBadge('badgeXo', arraysEqual(liveXo, KNOWN_XO));
renderBadge('badgeXoOrdered', arraysEqual(liveXoOrdered, KNOWN_XO_ORDERED));
renderBadge('badgeBase', arraysEqual(liveBase, KNOWN_BASE));
if (!arraysEqual(liveXo, KNOWN_XO)) console.error('Xoshiro mismatch', liveXo, KNOWN_XO);
if (!arraysEqual(liveXoOrdered, KNOWN_XO_ORDERED)) console.error('Xoshiro (generation order) mismatch', liveXoOrdered, KNOWN_XO_ORDERED);
if (!arraysEqual(liveBase, KNOWN_BASE)) console.error('Base mismatch', liveBase, KNOWN_BASE);

// ── Pass 2: xoshiro256** K={pass2_k} seeds, reusing the same verified
// BigInt xoshiroPredict() used for Base's xoshiro side above. ───────────────
const PASS2_SEEDS_DATA = {json.dumps(pass2_seeds)};
const livePass2Picks = PASS2_SEEDS_DATA.map(p2 => xoshiroPredict(p2.seed, {TARGET_SERIAL}, {pass2_k}));
const pass2AllMatch = PASS2_SEEDS_DATA.every((p2, i) => arraysEqual(livePass2Picks[i], p2.pick));
renderBadge('badgePass2', pass2AllMatch);
PASS2_SEEDS_DATA.forEach((p2, i) => {{
  if (!arraysEqual(livePass2Picks[i], p2.pick)) console.error('Pass-2 seed mismatch', p2.seed, livePass2Picks[i], p2.pick);
}});

// ── Pass 3: historical repeat filter, checked live against the embedded
// historical combo set. ──────────────────────────────────────────────────
const HISTORICAL_COMBOS = {json.dumps(historical_combos)};
const HISTORICAL_SET = new Set(HISTORICAL_COMBOS.map(c => c.join(',')));
const REMOVED_HISTORICAL = {json.dumps(removed_historical)};
const liveRemovedHistorical = REMOVED_HISTORICAL.every(c => HISTORICAL_SET.has(c.join(',')));
renderBadge('badgeHistorical', liveRemovedHistorical);
if (!liveRemovedHistorical) console.error('Pass-3 historical-match mismatch', REMOVED_HISTORICAL);

// ── Pass 4: Worst Combo (Anti-Pick) K={pass4_k} pick -- server-computed,
// embedded (5 methods including Random Forest/kNN/Apriori can't run
// client-side). Sanity-checked below against the fetched remaining set. ────
const PASS4_PICK = {json.dumps(pass4_pick)};

// ── Pass 5: no 3+/4+/5+/6-length consecutive-run filter -- pure JS, no
// server reference needed (only looks at each combo's own numbers). ────────
function maxConsecutiveRun(combo) {{
  const s = [...combo].sort((a, b) => a - b);
  let run = 1, best = 1;
  for (let i = 1; i < s.length; i++) {{
    if (s[i] === s[i - 1] + 1) {{ run++; best = Math.max(best, run); }}
    else {{ run = 1; }}
  }}
  return best;
}}

// ── Pass 6: three consecutive pairs filter -- pure JS, no server reference
// needed (only looks at each combo's own numbers). ──────────────────────────
function isThreeConsecutivePairs(combo) {{
  const s = [...combo].sort((a, b) => a - b);
  const runs = [];
  let run = [s[0]];
  for (let i = 1; i < s.length; i++) {{
    if (s[i] === s[i - 1] + 1) {{ run.push(s[i]); }}
    else {{ runs.push(run); run = [s[i]]; }}
  }}
  runs.push(run);
  return runs.length === 3 && runs.every(r => r.length === 2);
}}

// ── Pass 7 (final): "5-or-6 overlap, 1 step back" filter -- pure JS, no
// server reference needed (only compares each combo against the embedded
// previous-draw numbers). ───────────────────────────────────────────────
const PASS7_PREV_DRAW_NUMS = {json.dumps(pass7_prev_draw_nums)};
const PASS7_PREV_DRAW_SET = new Set(PASS7_PREV_DRAW_NUMS);
function prevDrawOverlap(combo) {{
  return combo.filter(n => PASS7_PREV_DRAW_SET.has(n)).length;
}}

// ── Remaining combos: fetch, paginate, filter, download ─────────────────────
const POOL_BASE = liveBase;
let REMAINING = [];
let filtered = [];
const PAGE_SIZE = 100;
let curPage = 0;
// 3-state per-number filter: 'include' (must contain), 'exclude' (must not
// contain), or absent (neutral, no constraint). Cycle on click: neutral ->
// include -> exclude -> neutral. Both constraint types apply simultaneously.
const numState = new Map();

fetch('/xoshiro_elim_{TARGET_SERIAL}_combos.json')
  .then(r => r.json())
  .then(data => {{
    REMAINING = data;
    filtered = REMAINING;
    document.getElementById('loadingMsg').style.display = 'none';
    document.getElementById('comboUI').style.display = 'block';
    buildFilterGrid();
    render();
    const stillHistorical = REMAINING.filter(c => HISTORICAL_SET.has(c.join(',')));
    if (stillHistorical.length > 0) console.error('Pass-3 leak: remaining combos still match history', stillHistorical);
    const pass4Set = new Set(PASS4_PICK);
    const stillInPass4 = REMAINING.filter(c => c.every(n => pass4Set.has(n)));
    if (stillInPass4.length > 0) console.error('Pass-4 leak: remaining combos still contained in Worst Combo pick', stillInPass4);
    const stillHasRun3 = REMAINING.filter(c => maxConsecutiveRun(c) >= 3);
    renderBadge('badgePass5', stillHasRun3.length === 0);
    if (stillHasRun3.length > 0) console.error('Pass-5 leak: remaining combos still have a run of 3+', stillHasRun3);
    const stillThreePairs = REMAINING.filter(c => isThreeConsecutivePairs(c));
    renderBadge('badgePass6', stillThreePairs.length === 0);
    if (stillThreePairs.length > 0) console.error('Pass-6 leak: remaining combos still match three-consecutive-pairs', stillThreePairs);
    const stillHighOverlap = REMAINING.filter(c => [5,6].includes(prevDrawOverlap(c)));
    renderBadge('badgePass7', stillHighOverlap.length === 0);
    if (stillHighOverlap.length > 0) console.error('Pass-7 leak: remaining combos still overlap draw #{pass7_prev_draw_serial} by 5-6', stillHighOverlap);
  }})
  .catch(err => {{
    document.getElementById('loadingMsg').textContent = 'Failed to load combinations: ' + err;
  }});

function getBallColor(n) {{
  if (n <= 7) return '#e74c3c';
  if (n <= 13) return '#e67e22';
  if (n <= 19) return '#2ecc71';
  if (n <= 25) return '#3498db';
  if (n <= 31) return '#9b59b6';
  if (n <= 37) return '#16a085';
  return '#e91e8c';
}}
function buildFilterGrid() {{
  const grid = document.getElementById('filterGrid');
  grid.innerHTML = POOL_BASE.map(n =>
    '<button class="num-btn" data-n="' + n + '" style="background:' + getBallColor(n) + '" onclick="toggleNum(' + n + ')">' + n + '</button>'
  ).join('');
}}
function toggleNum(n) {{
  const cur = numState.get(n);
  const next = cur === undefined ? 'include' : cur === 'include' ? 'exclude' : undefined;
  if (next === undefined) numState.delete(n); else numState.set(n, next);
  const btn = document.querySelector('.num-btn[data-n="' + n + '"]');
  btn.classList.remove('include', 'exclude');
  if (next) btn.classList.add(next);
  applyFilter();
}}
function clearFilter() {{
  numState.clear();
  document.querySelectorAll('.num-btn.include, .num-btn.exclude').forEach(b => b.classList.remove('include', 'exclude'));
  applyFilter();
}}
function applyFilter() {{
  const includeNums = [...numState.entries()].filter(([n, s]) => s === 'include').map(([n]) => n);
  const excludeNums = [...numState.entries()].filter(([n, s]) => s === 'exclude').map(([n]) => n);
  filtered = (includeNums.length === 0 && excludeNums.length === 0) ? REMAINING : REMAINING.filter(c => {{
    for (const n of includeNums) if (!c.includes(n)) return false;
    for (const n of excludeNums) if (c.includes(n)) return false;
    return true;
  }});
  const parts = [];
  if (includeNums.length) parts.push('contain ' + includeNums.sort((a,b)=>a-b).join(', '));
  if (excludeNums.length) parts.push('exclude ' + excludeNums.sort((a,b)=>a-b).join(', '));
  document.getElementById('filterInfo').textContent = parts.length === 0 ? '' :
    (filtered.length.toLocaleString() + ' / ' + REMAINING.length.toLocaleString() + ' combos ' + parts.join(' and '));
  curPage = 0;
  render();
}}
function totalPages() {{ return Math.max(1, Math.ceil(filtered.length / PAGE_SIZE)); }}
function goPage(p) {{ curPage = Math.max(0, Math.min(p, totalPages()-1)); render(); }}
function render() {{
  const start = curPage * PAGE_SIZE;
  const pageRows = filtered.slice(start, start + PAGE_SIZE);
  document.getElementById('comboBody').innerHTML = pageRows.map((c, i) => {{
    const balls = c.map(n => '<span class="nb" style="width:26px;height:26px;font-size:.72rem;background:' + getBallColor(n) + '33;color:#e2e8f0;border:1px solid ' + getBallColor(n) + '">' + n + '</span>').join('');
    return '<tr><td>' + (start+i+1) + '</td><td><div class="balls">' + balls + '</div></td></tr>';
  }}).join('');
  document.getElementById('pageInfo').textContent =
    filtered.length === 0 ? 'No combinations match' :
    'Showing ' + (start+1) + '-' + Math.min(start+PAGE_SIZE, filtered.length) + ' of ' + filtered.length.toLocaleString() + ' (page ' + (curPage+1) + ' / ' + totalPages() + ')';
  document.getElementById('firstBtn').disabled = curPage === 0;
  document.getElementById('prevBtn').disabled = curPage === 0;
  document.getElementById('nextBtn').disabled = curPage >= totalPages()-1;
  document.getElementById('lastBtn').disabled = curPage >= totalPages()-1;
}}
function downloadCSV() {{
  const rows = filtered.length > 0 ? filtered : REMAINING;
  let csv = 'n1,n2,n3,n4,n5,n6\\n' + rows.map(c => c.join(',')).join('\\n');
  const blob = new Blob([csv], {{type: 'text/csv'}});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'draw_{TARGET_SERIAL}_remaining_combos.csv';
  a.click();
  URL.revokeObjectURL(url);
}}
</script>
</body>
</html>"""

with open(HTML_OUT, 'w', encoding='utf-8') as f:
    f.write(page)
print(f"Wrote {HTML_OUT} ({len(page)//1024} KB)")
