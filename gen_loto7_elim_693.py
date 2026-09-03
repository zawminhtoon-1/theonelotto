"""
gen_loto7_elim_693.py
--------------------------
Generates the Loto7 draw #693 elimination page, brought up to the same
feature level as the Loto6 elimination pages (xoshiro_elim_2134.html /
xo_pcg_elim_2134.html / pcg64_top3_elim_2134.html): 7-pass pipeline
with an honest note on the Base-construction decision, hot/cold filter
dropdown, greedy "Diverse sample" Generate 5/10 buttons, and live
client-side verification badges for every pass that's pure-JS
reproducible (3, 5, 6, 7 -- historical/pattern filters). Passes 1, 2
and 4 use the 16-method ML ensemble which can't practically run in a
browser, so those stay server-computed (same as the Loto6 pages'
"Worst Combo" pass).

Reads loto7_elim_693_meta.json (small: base pool, method picks,
counts) produced by precompute_loto7_elim_693.py. The large combo list
lives separately at public/loto7_elim_693_combos.json and is fetched
client-side, not inlined.

Output: public/loto7_elim_693.html
Run: python gen_loto7_elim_693.py
"""
import json

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
META_PATH = BASE + r"\loto7_elim_693_meta.json"
HTML_OUT = BASE + r"\public\loto7_elim_693.html"

with open(META_PATH, encoding='utf-8') as f:
    meta = json.load(f)

TARGET_SERIAL = meta['targetSerial']
base = meta['base']
universe_count = meta['universeCount']
method_names = meta['methodNames']
method_k = meta['methodK']
method_picks = meta['methodPicks']
removed_by_methods = meta['removedByMethods']
final_remaining_pass1 = meta['finalRemainingPass1']
pass1_pct = final_remaining_pass1 / universe_count * 100

pass2_method_names = meta['pass2MethodNames']
pass2_k = meta['pass2K']
pass2_picks = meta['pass2Picks']
removed_by_pass2 = meta['removedByPass2']
final_remaining_pass2 = meta['finalRemainingPass2']
pass2_pct = final_remaining_pass2 / universe_count * 100

historical_draw_count = meta['historicalDrawCount']
removed_historical = meta['removedHistorical']
final_remaining_pass3 = meta['finalRemainingPass3']
pass3_pct = final_remaining_pass3 / universe_count * 100

pass4_method_names = meta['pass4MethodNames']
pass4_k = meta['pass4K']
pass4_pick = meta['pass4Pick']
pass4_overlap = meta['pass4Overlap']
removed_by_pass4 = meta['removedByPass4']
final_remaining_pass4 = meta['finalRemainingPass4']
pass4_pct = final_remaining_pass4 / universe_count * 100

pass5_threshold = meta['pass5Threshold']
pass5_hist_validation = meta['pass5HistoricalValidation']
pass5_run_distribution = meta['pass5RunDistribution']
removed_by_pass5 = meta['removedByPass5']
final_remaining_pass5 = meta['finalRemainingPass5']
pass5_pct = final_remaining_pass5 / universe_count * 100

pass6_hist_count = meta['pass6HistoricalCount']
pass6_hist_pct = meta['pass6HistoricalPct']
removed_by_pass6 = meta['removedByPass6']
final_remaining_pass6 = meta['finalRemainingPass6']
pass6_pct = final_remaining_pass6 / universe_count * 100

pass7_prev_draw_serial = meta['pass7PrevDrawSerial']
pass7_prev_draw_nums = meta['pass7PrevDrawNums']
pass7_hist_overlap_dist = meta['pass7HistoricalOverlapDistribution']
pass7_hist_pairs_count = meta['pass7HistoricalPairsCount']
pass7_overlap_distribution = meta['pass7OverlapDistribution']
removed_by_pass7 = meta['removedByPass7']
final_remaining_pass7 = meta['finalRemainingPass7']
pass7_pct = final_remaining_pass7 / universe_count * 100

final_remaining = meta['finalRemaining']
final_pct = final_remaining / universe_count * 100

methods_rows_html = ""
for name, pool in zip(method_names, method_picks):
    balls = "".join(f'<span class="nb">{n}</span>' for n in pool)
    methods_rows_html += f"""<tr><td class="mname">{name}</td><td><div class="balls">{balls}</div></td></tr>"""

pass2_rows_html = ""
for name, pool in zip(pass2_method_names, pass2_picks):
    balls = "".join(f'<span class="nb">{n}</span>' for n in pool)
    pass2_rows_html += f"""<tr><td class="mname">{name}</td><td><div class="balls">{balls}</div></td></tr>"""

historical_rows_html = ""
for combo in removed_historical:
    balls = "".join(f'<span class="nb">{n}</span>' for n in combo)
    historical_rows_html += f"""<tr><td><div class="balls">{balls}</div></td></tr>"""

pass5_hist_str = ' &middot; '.join(f'run={k}: {v} ({v/historical_draw_count*100:.2f}%)' for k, v in pass5_hist_validation.items())
pass5_run_dist_str = ' &middot; '.join(f'run={k}: {int(v):,}' for k, v in pass5_run_distribution.items())

pass7_hist_str = ' &middot; '.join(f'overlap={k}: {v}' for k, v in pass7_hist_overlap_dist.items())
pass7_overlap_dist_str = ' &middot; '.join(f'overlap={k}: {int(v):,}' for k, v in pass7_overlap_distribution.items())

page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Loto 7 — Draw #{TARGET_SERIAL} Elimination</title>
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

.honest{{background:#1c0f0f;border:1px solid #7f1d1d;border-radius:10px;padding:14px 18px;
  font-size:.8rem;color:#fca5a5;margin-bottom:20px;line-height:1.6}}
.honest strong{{color:#fecaca}}
.honest p+p{{margin-top:8px}}
.honest .stats-mini{{display:flex;gap:10px;flex-wrap:wrap;margin:10px 0}}
.honest .stats-mini div{{background:#0a0f1e;border:1px solid #450a0a;border-radius:8px;padding:8px 12px;font-size:.76rem;color:#e2e8f0}}
.honest .stats-mini div b{{color:#fca5a5}}

.section{{background:#0d1526;border:1px solid #1e293b;border-radius:12px;padding:20px;margin-bottom:20px}}
.section h2{{font-size:1rem;font-weight:700;color:#f1f5f9;margin-bottom:4px;display:flex;align-items:center;gap:8px;flex-wrap:wrap}}
.section h3{{font-size:.86rem;font-weight:700;color:#cbd5e1;margin:14px 0 6px}}
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
.nb.b2{{background:#450a0a;color:#fca5a5;border-color:#ef444455}}

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
.lookup select{{background:#0a0f1e;border:1px solid #334155;border-radius:7px;padding:7px 10px;
  color:#e2e8f0;font-size:.82rem}}
.pd-lbl{{font-size:.72rem;color:#64748b;text-transform:uppercase;letter-spacing:.05em}}
#generatedResults{{margin-bottom:14px}}
#generatedResults .gen-hdr{{font-size:.78rem;color:#94a3b8;margin-bottom:8px}}
#generatedResults .gen-row{{margin-bottom:6px}}
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
  <h1>✂️ Loto 7 — Draw #{TARGET_SERIAL} Elimination</h1>
  <p class="subtitle">Combinatorial set-difference: ARIMA's K={base['k']} Base pool, minus combos covered by any of the 16 prediction methods, minus statistically-validated pattern filters</p>

  <div class="honest">
    <p><strong>Base construction — tested, not assumed.</strong> Before building this page, we walk-forward
    backtested whether intersecting Base with the completed xoshiro K=25/28/30 Loto7 seed scans' best seeds would
    strengthen it (same rigor as the Loto6 seed-intersection pages), across all {historical_draw_count:,} real
    Loto7 draws:</p>
    <div class="stats-mini">
      <div>ARIMA K=25 alone<br>containment (actual draw fully inside pool): <b>4.35%</b> (30/690)<br>~chance level for a random 25-of-37 pool (4.67%)</div>
      <div>ARIMA ∩ 1 xoshiro seed<br>pool shrinks to ~17&ndash;20 numbers<br>containment: <b>0.29%&ndash;1.45%</b> &mdash; worse</div>
      <div>ARIMA ∩ all 3 xoshiro seeds<br>pool shrinks to ~10 numbers<br>containment: <b>0%</b> (0/690) &mdash; never once contained the real combo</div>
    </div>
    <p>Intersecting Base with any xoshiro seed makes it <strong>worse</strong>, not better — the pool shrinks enough
    that it stops reliably containing the actual winning numbers at all. Decision: Base stays
    <strong style="color:#e2e8f0">ARIMA(2,1,0) K=25 alone</strong>, not intersected with any seed scan. (Also worth
    noting: even ARIMA alone barely beats the chance level for containment — this Base isn't a strong signal on its
    own, it's a starting point the elimination passes then narrow down.)</p>
  </div>

  <div class="note">
    <p><strong style="color:#e2e8f0">Base</strong> is <strong>ARIMA(2,1,0)'s K={base['k']} pick</strong> for draw #{TARGET_SERIAL} (not yet drawn) &mdash;
    read from <a href="/loto7/predictions" style="color:#a78bfa">the live /loto7/predictions page</a>'s data (ARIMA's native
    K={base['nativeK']} pool, normalized to K={base['k']} via <code>topKNums()</code>, the same generic cross-method-consensus
    trim/pad function used throughout this site). It defines the working universe: all C({base['k']},7) = {universe_count:,}
    seven-number combinations drawable from this {base['k']}-number pool.</p>
    <p><strong style="color:#e2e8f0">Pass 1</strong> is each of the 16 prediction methods' K={method_k} pick for draw
    #{TARGET_SERIAL} (native K=15 pool normalized to K={method_k}), checked <strong>independently</strong> &mdash; NOT a union
    of raw numbers. Any Base combo fully contained within ANY single one of these 16 K={method_k} sets gets removed,
    leaving {final_remaining_pass1:,}.</p>
    <p><strong style="color:#e2e8f0">Pass 2</strong> is {len(pass2_method_names)} specific methods' K={pass2_k} pick for draw
    #{TARGET_SERIAL} &mdash; {', '.join(pass2_method_names)} &mdash; checked independently. Any Pass-1-remaining combo fully
    contained within ANY single one of these {len(pass2_method_names)} K={pass2_k} sets gets removed, leaving {final_remaining_pass2:,}.</p>
    <p><strong style="color:#e2e8f0">Pass 3</strong> is a historical repeat filter &mdash; the same "zero repeats in history"
    pattern used on the Loto6 elimination pages. Any Pass-2-remaining combo that exactly matches one of Loto7's
    {historical_draw_count:,} historical actual winning combos (draws #1&ndash;{TARGET_SERIAL-1}, main 7 numbers only,
    bonus ignored) gets removed, leaving {final_remaining_pass3:,}.</p>
    <p><strong style="color:#e2e8f0">Pass 4</strong> (NEW) is the Worst Combo (Anti-Pick) K={pass4_k} pick &mdash;
    {', '.join(pass4_method_names)} consensus, the exact Loto7 analog of the 5-method combination used on the Loto6
    pages' Worst Combo panel. Any Pass-3-remaining combo fully contained within this {pass4_k}-number pick gets removed,
    leaving {final_remaining_pass4:,}.</p>
    <p><strong style="color:#e2e8f0">Pass 5</strong> (NEW) removes any Pass-4-remaining combo containing a run of
    {pass5_threshold}+ consecutive numbers. <strong>Validated first</strong>, same rigor as the Loto6 pages: across all
    {historical_draw_count:,} real Loto7 draws, run&ge;3 occurs in 15.32% of draws &mdash; too common to be a meaningful
    pattern, so it was <strong style="color:#fca5a5">rejected</strong> (unlike Loto6, where 6.62% was judged rare enough
    to use). run&ge;{pass5_threshold} occurs in only {pass5_hist_validation.get(str(pass5_threshold), '?')}/{historical_draw_count}
    draws ({round(int(pass5_hist_validation.get(str(pass5_threshold),0))/historical_draw_count*100,2)}%) &mdash; comparably
    rare to Loto6's threshold, so this is the one actually used. Leaves {final_remaining_pass5:,}.</p>
    <p><strong style="color:#e2e8f0">Pass 6</strong> (NEW) removes any Pass-5-remaining combo that decomposes into
    exactly three consecutive pairs plus one leftover single number (e.g. 1,2,9,10,15,16,23) &mdash; the natural Loto7
    analog of Loto6's "three consecutive pairs" pattern (Loto6's exact-6-numbers-as-3-pairs pattern doesn't map onto
    Loto7's 7 numbers, so this adds the necessary 7th "single" slot). <strong>Validated first</strong>: occurs in only
    {pass6_hist_count}/{historical_draw_count} real draws ({pass6_hist_pct}%) &mdash; comparably rare to Loto6's pattern.
    Leaves {final_remaining_pass6:,}.</p>
    <p><strong style="color:#e2e8f0">Pass 7</strong> (NEW, final) removes any Pass-6-remaining combo that shares 5 or
    more numbers with the immediately previous actual draw ("1 step back") &mdash; #{pass7_prev_draw_serial}:
    {', '.join(str(n) for n in pass7_prev_draw_nums)}. <strong>Validated first</strong> via hypergeometric expectation
    (pool=37, 7-of-37 draws) against all {pass7_hist_pairs_count:,} consecutive real-draw pairs &mdash; explicitly checking
    the weak heuristic this site rejected for Loto6: overlap=3 occurred in 70/691 pairs (10.13%), essentially matching
    the 9.32% chance expectation &mdash; <strong style="color:#fca5a5">rejected</strong>, same conclusion as Loto6's
    abandoned 3-overlap idea. overlap=4 (1.59% observed vs 1.38% expected) was also rejected as too close to chance.
    overlap&ge;5 has <strong style="color:#86efac">never once occurred</strong>
    (0/{pass7_hist_pairs_count:,}, vs a near-zero 0.09% chance expectation) &mdash; well-supported, adopted. Leaves
    <strong style="color:#38bdf8">{final_remaining_pass7:,}</strong>.</p>
    <p>Passes 3, 5, 6 and 7 are recomputed <strong>live in your browser</strong> below (pure JS, pattern/historical
    checks, no PRNG involved in this page) and checked against server-embedded references &mdash; check the
    verification badges. Passes 1, 2 and 4's 16-method ML ensemble can't (practically) run in a browser, so those
    are precomputed server-side and embedded as static data.</p>
  </div>

  <div class="section">
    <h2>Base — ARIMA(2,1,0) K={base['k']}</h2>
    <p class="desc">Native K={base['nativeK']} pick normalized to K={base['k']} via cross-method-consensus trim/pad. See the
    honest-framing note above for why this is NOT intersected with a xoshiro seed.</p>
    <div class="balls">{"".join(f'<span class="nb">{n}</span>' for n in base['pool'])}</div>
  </div>

  <div class="section">
    <h2>Pass 1 — 16 prediction methods, K={method_k} pick for draw #{TARGET_SERIAL} <span class="verify-badge na">server-computed</span></h2>
    <p class="desc">Each method's native K=15 pool normalized to K={method_k}, checked independently against the Base pool.</p>
    <details>
      <summary>Show all 16 methods' K={method_k} picks</summary>
      <table class="methods-table">
        <tbody>{methods_rows_html}</tbody>
      </table>
    </details>
  </div>

  <div class="section">
    <h2>Pass 2 — {len(pass2_method_names)} methods, K={pass2_k} pick for draw #{TARGET_SERIAL} <span class="verify-badge na">server-computed</span></h2>
    <p class="desc">{', '.join(pass2_method_names)} &mdash; native K=15 pools normalized to K={pass2_k}, checked independently against what's left after Pass 1.</p>
    <table class="methods-table">
      <tbody>{pass2_rows_html}</tbody>
    </table>
  </div>

  <div class="section">
    <h2>Pass 3 — historical repeat filter <span id="badgeHistorical" class="verify-badge pending">verifying…</span></h2>
    <p class="desc">Any Pass-2-remaining combo that exactly matches one of Loto7's {historical_draw_count:,} historical actual
    winning combos (draws #1&ndash;{TARGET_SERIAL-1}, main 7 numbers only, bonus ignored) is removed. Checked live in your
    browser against the same embedded historical combo set. {len(removed_historical)} matches found.</p>
    {f"<details><summary>Show all {len(removed_historical):,} removed combos (exact match to a historical winning combo)</summary><table class='methods-table'><thead><tr><th>Removed &mdash; exact match to a historical winning combo</th></tr></thead><tbody>" + historical_rows_html + "</tbody></table></details>" if removed_historical else "<p style='color:#64748b;font-size:.85rem'>No matches found &mdash; nothing removed by this pass.</p>"}
  </div>

  <div class="section">
    <h2>Pass 4 (NEW) — Worst Combo (Anti-Pick), K={pass4_k} pick for draw #{TARGET_SERIAL} <span class="verify-badge na">server-computed</span></h2>
    <p class="desc">{', '.join(pass4_method_names)} consensus &mdash; the Loto7 analog of the 5-method combination used on the
    Loto6 pages' Worst Combo panel. Overlap with the {base['k']}-pool: {pass4_overlap} numbers.</p>
    <div class="balls">{"".join(f'<span class="nb">{n}</span>' for n in pass4_pick)}</div>
  </div>

  <div class="section">
    <h2>Pass 5 (NEW) — no {pass5_threshold}+-length consecutive-run filter <span id="badgePass5" class="verify-badge pending">verifying…</span></h2>
    <p class="desc">Removes any Pass-4-remaining combo whose sorted main numbers contain a run of {pass5_threshold} or more
    consecutive integers. Threshold chosen from historical validation, not copied from Loto6's run&ge;3 (which was too
    common at 15.32% for Loto7). Checked live in your browser (pure JS, no server reference needed).</p>
    <p class="desc" style="margin-bottom:0">Historical validation (all {historical_draw_count:,} real draws): {pass5_hist_str}.
    Max-run distribution among the {final_remaining_pass4:,} Pass-4-remaining combos: {pass5_run_dist_str}.</p>
  </div>

  <div class="section">
    <h2>Pass 6 (NEW) — three-pairs-plus-single filter <span id="badgePass6" class="verify-badge pending">verifying…</span></h2>
    <p class="desc">Removes any Pass-5-remaining combo whose sorted main numbers decompose into exactly three consecutive
    pairs plus one leftover single (pattern 2-2-2-1) &mdash; the Loto7 analog of Loto6's three-consecutive-pairs filter.
    Checked live in your browser (pure JS, no server reference needed).</p>
    <p class="desc" style="margin-bottom:0">Historical validation: {pass6_hist_count}/{historical_draw_count} real draws
    ({pass6_hist_pct}%) match this pattern. Removed {len(removed_by_pass6):,} combos matching this pattern from the
    Pass-5-remaining set &mdash; e.g. {', '.join(str(tuple(c)) for c in removed_by_pass6[:5])}{', ...' if len(removed_by_pass6) > 5 else ''}.</p>
  </div>

  <div class="section">
    <h2>Pass 7 (NEW, final) — "5+ overlap, 1 step back" filter <span id="badgePass7" class="verify-badge pending">verifying…</span>
    <span class="verify-badge" style="background:#14532d;color:#86efac">well-supported (0/{pass7_hist_pairs_count:,})</span></h2>
    <p class="desc">Removes any Pass-6-remaining combo that shares 5 or more numbers with the immediately previous
    actual draw &mdash; #{pass7_prev_draw_serial}: <span class="balls" style="display:inline-flex;vertical-align:middle">{"".join(f'<span class="nb">{n}</span>' for n in pass7_prev_draw_nums)}</span>. Historical basis: across all
    {pass7_hist_pairs_count:,} consecutive real-draw pairs, overlap&ge;5 has never once occurred (0/{pass7_hist_pairs_count:,}).
    overlap=3 and overlap=4 were tested and rejected (they match chance closely, unlike overlap&ge;5). Checked live in
    your browser (pure JS, no server reference needed).</p>
    <p class="desc" style="margin-bottom:0">Historical overlap distribution (all {pass7_hist_pairs_count:,} consecutive
    pairs): {pass7_hist_str}. Overlap distribution among the {final_remaining_pass6:,} Pass-6-remaining combos:
    {pass7_overlap_dist_str}. Removed {len(removed_by_pass7):,} combos with overlap&ge;5. Final remaining:
    <strong style="color:#38bdf8">{final_remaining_pass7:,}</strong>.</p>
  </div>

  <div class="section">
    <h2>Elimination summary</h2>
    <div class="stats-row">
      <div class="stat-card">
        <div class="lbl">Universe (Base)</div>
        <div class="val">{universe_count:,}</div>
        <div class="sub">C({base['k']},7)</div>
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
        <div class="lbl">Removed by {len(pass2_method_names)} methods (Pass 2)</div>
        <div class="val">{removed_by_pass2:,}</div>
        <div class="sub">contained in ANY method's K={pass2_k}</div>
      </div>
      <div class="stat-card">
        <div class="lbl">After Pass 2</div>
        <div class="val">{final_remaining_pass2:,}</div>
        <div class="sub">{pass2_pct:.1f}% of universe retained</div>
      </div>
      <div class="stat-card">
        <div class="lbl">Removed by historical filter (Pass 3)</div>
        <div class="val">{len(removed_historical):,}</div>
        <div class="sub">exact match to a real drawn combo</div>
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
        <div class="sub">max run of {pass5_threshold}+ consecutive numbers</div>
      </div>
      <div class="stat-card">
        <div class="lbl">After Pass 5</div>
        <div class="val">{final_remaining_pass5:,}</div>
        <div class="sub">{pass5_pct:.1f}% of universe retained</div>
      </div>
      <div class="stat-card">
        <div class="lbl">Removed by three-pairs-plus-single filter (Pass 6)</div>
        <div class="val">{len(removed_by_pass6):,}</div>
        <div class="sub">pattern 2-2-2-1</div>
      </div>
      <div class="stat-card">
        <div class="lbl">After Pass 6</div>
        <div class="val">{final_remaining_pass6:,}</div>
        <div class="sub">{pass6_pct:.1f}% of universe retained</div>
      </div>
      <div class="stat-card">
        <div class="lbl">Removed by 5+-overlap filter (Pass 7)</div>
        <div class="val">{len(removed_by_pass7):,}</div>
        <div class="sub">overlap &ge;5 &middot; 1 step back &middot; 0/{pass7_hist_pairs_count:,} historically</div>
      </div>
      <div class="stat-card final">
        <div class="lbl">Final remaining</div>
        <div class="val">{final_remaining:,}</div>
        <div class="sub">{final_pct:.1f}% of universe retained</div>
      </div>
    </div>
    <div class="elim-flow">
      <span class="n">{universe_count:,}</span>
      <span class="arrow">&rarr;</span>
      <span class="n">{final_remaining_pass1:,}</span> <span style="color:#64748b;font-size:.7rem">(P1)</span>
      <span class="arrow">&rarr;</span>
      <span class="n">{final_remaining_pass2:,}</span> <span style="color:#64748b;font-size:.7rem">(P2)</span>
      <span class="arrow">&rarr;</span>
      <span class="n">{final_remaining_pass3:,}</span> <span style="color:#64748b;font-size:.7rem">(P3)</span>
      <span class="arrow">&rarr;</span>
      <span class="n">{final_remaining_pass4:,}</span> <span style="color:#64748b;font-size:.7rem">(P4)</span>
      <span class="arrow">&rarr;</span>
      <span class="n">{final_remaining_pass5:,}</span> <span style="color:#64748b;font-size:.7rem">(P5)</span>
      <span class="arrow">&rarr;</span>
      <span class="n">{final_remaining_pass6:,}</span> <span style="color:#64748b;font-size:.7rem">(P6)</span>
      <span class="arrow">&rarr;</span>
      <span class="n final">{final_remaining:,}</span> <span style="color:#64748b;font-size:.7rem">(P7)</span>
    </div>
  </div>

  <div class="section">
    <h2>Browse remaining combinations</h2>
    <p class="desc">Fetched from a separate JSON asset (not inlined — {final_remaining:,} rows is too large for the page itself).</p>
    <div id="loadingMsg">Loading {final_remaining:,} combinations…</div>
    <div id="comboUI" style="display:none">
      <div class="lookup">
        <span class="pd-lbl">Hot/cold pattern</span>
        <select id="hcFilterSelect" onchange="applyFilter()">
          <option value="">All patterns</option>
          <option value="0">0h/7c</option>
          <option value="1">1h/6c</option>
          <option value="2">2h/5c</option>
          <option value="3">3h/4c</option>
          <option value="4">4h/3c</option>
          <option value="5">5h/2c</option>
          <option value="6">6h/1c</option>
          <option value="7">7h/0c</option>
        </select>
        <button class="btn" onclick="clearFilter()">Clear filter</button>
        <button class="btn primary" onclick="downloadCSV()">⬇ Download CSV</button>
        <span id="filterInfo" class="page-info"></span>
      </div>
      <div class="filter-legend">Click a number to cycle: <span class="swatch neutral"></span>neutral (no filter) &rarr;
        <span class="swatch include"></span>include (must contain) &rarr; <span class="swatch exclude"></span>exclude (must not
        contain) &rarr; back to neutral. Include and exclude constraints apply together. Hot/cold pattern (walk-forward
        top-18/bottom-19 split, computed live from the same embedded historical data as Pass 3) applies on top of both.</div>
      <div class="filter-grid" id="filterGrid"></div>

      <div class="lookup" style="margin-top:4px">
        <span class="pd-lbl">Diverse sample</span>
        <button class="btn primary" onclick="generateSamples(5)">🎲 Generate 5</button>
        <button class="btn primary" onclick="generateSamples(10)">🎲 Generate 10</button>
        <span class="page-info">Greedy coverage-maximizing pick from the currently filtered set (or all {final_remaining:,} if no
        filter is active) — each pick is the combo whose numbers have the least cumulative usage so far, spreading the
        sample across as many distinct pool numbers as possible rather than clustering. Not a uniform random sample.</span>
      </div>
      <div id="generatedResults"></div>

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
    Base = ARIMA(2,1,0)'s K={base['k']} pick, normalized via <code>topKNums()</code> (cross-method-consensus trim/pad,
    same function used throughout this site). Universe = all C({base['k']},7) combinations drawable from that pool.
    16 methods: Poly Regression, Moving Avg-37, Exp-Weighted Avg, Frequency, Markov Chain, ARIMA(2,1,0), Random Forest,
    RL (Linear Q), HMM, k-NN, Modular Cycle, Apriori, Monte Carlo, Naive Bayes, Weighted MA-37, LSTM — same 16 used
    throughout <a href="/loto7_backtest.html" style="color:#64748b">loto7_backtest.html</a> /
    <a href="/loto7/predictions" style="color:#64748b">predictions</a>.<br>
    Formula-based only · Not financial advice · Loto 7 is random.
  </p>
</div>

<script>
const POOL_BASE = {json.dumps(base['pool'])};

function arraysEqual(a, b) {{
  return a.length === b.length && a.every((v, i) => v === b[i]);
}}
function renderBadge(id, ok) {{
  const el = document.getElementById(id);
  el.className = 'verify-badge ' + (ok ? 'ok' : 'fail');
  el.textContent = ok ? '✓ live-computed value matches' : '✗ MISMATCH — check console';
}}

// ── Pass 3: historical repeat filter, checked live against the full
// historical combo set (fetched alongside the remaining-combos JSON below --
// too large to inline here, kept as a separate small asset). ────────────────
const REMOVED_HISTORICAL = {json.dumps(removed_historical)};

// ── Pass 5: consecutive-run filter, threshold {pass5_threshold} -- pure JS ──
const PASS5_THRESHOLD = {pass5_threshold};
function maxConsecutiveRun(combo) {{
  const s = [...combo].sort((a, b) => a - b);
  let run = 1, best = 1;
  for (let i = 1; i < s.length; i++) {{
    if (s[i] === s[i - 1] + 1) {{ run++; best = Math.max(best, run); }}
    else {{ run = 1; }}
  }}
  return best;
}}

// ── Pass 6: three-pairs-plus-single filter (pattern 2-2-2-1) -- pure JS ─────
function runLengths(combo) {{
  const s = [...combo].sort((a, b) => a - b);
  const runs = [];
  let run = [s[0]];
  for (let i = 1; i < s.length; i++) {{
    if (s[i] === s[i - 1] + 1) {{ run.push(s[i]); }}
    else {{ runs.push(run); run = [s[i]]; }}
  }}
  runs.push(run);
  return runs.map(r => r.length);
}}
function isThreePairsPlusSingle(combo) {{
  const lengths = runLengths(combo).slice().sort((a, b) => b - a);
  return lengths.length === 4 && lengths[0] === 2 && lengths[1] === 2 && lengths[2] === 2 && lengths[3] === 1;
}}

// ── Pass 7: "5+ overlap, 1 step back" filter -- pure JS ──────────────────────
const PASS7_PREV_DRAW_NUMS = {json.dumps(pass7_prev_draw_nums)};
const PASS7_PREV_DRAW_SET = new Set(PASS7_PREV_DRAW_NUMS);
function prevDrawOverlap(combo) {{
  return combo.filter(n => PASS7_PREV_DRAW_SET.has(n)).length;
}}

// ── Hot/cold pattern filter: walk-forward top-18/bottom-19 split. Needs the
// full historical winning-combo set to compute frequency -- fetched
// alongside the remaining-combos JSON below (small enough to also embed
// separately would duplicate data, so it's derived from the same server
// call that verifies Pass 3). ────────────────────────────────────────────
let HOT_SET = new Set();
function hotCount(combo) {{
  return combo.filter(n => HOT_SET.has(n)).length;
}}

// ── Remaining combos + full historical set: fetch, paginate, filter, download ──
const POOL = POOL_BASE;
let REMAINING = [];
let filtered = [];
const PAGE_SIZE = 100;
let curPage = 0;
const numState = new Map();

Promise.all([
  fetch('/loto7_elim_{TARGET_SERIAL}_combos.json').then(r => r.json()),
  fetch('/loto7_elim_{TARGET_SERIAL}_historical.json').then(r => r.json())
]).then(([combosData, historicalData]) => {{
  REMAINING = combosData;
  filtered = REMAINING;
  document.getElementById('loadingMsg').style.display = 'none';
  document.getElementById('comboUI').style.display = 'block';

  // Pass 3 verify: REMOVED_HISTORICAL should all be in historicalData, and
  // none of REMAINING should be.
  const histSet = new Set(historicalData.map(c => c.join(',')));
  const removedOk = REMOVED_HISTORICAL.every(c => histSet.has(c.join(',')));
  const noneRemainingMatch = REMAINING.every(c => !histSet.has(c.join(',')));
  renderBadge('badgeHistorical', removedOk && noneRemainingMatch);
  if (!removedOk) console.error('Pass-3 leak: a server-removed combo is not actually historical', REMOVED_HISTORICAL);
  if (!noneRemainingMatch) console.error('Pass-3 leak: a remaining combo matches history', REMAINING.filter(c => histSet.has(c.join(','))));

  // Hot/cold: walk-forward top-18/bottom-19 split from the full historical set.
  const freq = new Array(38).fill(0);
  historicalData.forEach(combo => combo.forEach(n => freq[n]++));
  const nums = Array.from({{length: 37}}, (_, i) => i + 1);
  nums.sort((a, b) => freq[b] - freq[a] || a - b);
  HOT_SET = new Set(nums.slice(0, 18));

  buildFilterGrid();
  render();

  const stillHasRun = REMAINING.filter(c => maxConsecutiveRun(c) >= PASS5_THRESHOLD);
  renderBadge('badgePass5', stillHasRun.length === 0);
  if (stillHasRun.length > 0) console.error('Pass-5 leak: remaining combos still have a run of ' + PASS5_THRESHOLD + '+', stillHasRun);

  const stillThreePairs = REMAINING.filter(c => isThreePairsPlusSingle(c));
  renderBadge('badgePass6', stillThreePairs.length === 0);
  if (stillThreePairs.length > 0) console.error('Pass-6 leak: remaining combos still match three-pairs-plus-single', stillThreePairs);

  const stillHighOverlap = REMAINING.filter(c => prevDrawOverlap(c) >= 5);
  renderBadge('badgePass7', stillHighOverlap.length === 0);
  if (stillHighOverlap.length > 0) console.error('Pass-7 leak: remaining combos still overlap draw #{pass7_prev_draw_serial} by 5+', stillHighOverlap);
}}).catch(err => {{
  document.getElementById('loadingMsg').textContent = 'Failed to load combinations: ' + err;
}});

function getBallColor(n) {{
  if (n <= 6) return '#e74c3c';
  if (n <= 11) return '#e67e22';
  if (n <= 16) return '#2ecc71';
  if (n <= 21) return '#3498db';
  if (n <= 26) return '#9b59b6';
  if (n <= 31) return '#16a085';
  return '#e91e8c';
}}
function buildFilterGrid() {{
  const grid = document.getElementById('filterGrid');
  grid.innerHTML = POOL.map(n =>
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
  document.getElementById('hcFilterSelect').value = '';
  applyFilter();
}}
function applyFilter() {{
  const includeNums = [...numState.entries()].filter(([n, s]) => s === 'include').map(([n]) => n);
  const excludeNums = [...numState.entries()].filter(([n, s]) => s === 'exclude').map(([n]) => n);
  const hcVal = document.getElementById('hcFilterSelect').value;
  filtered = (includeNums.length === 0 && excludeNums.length === 0 && hcVal === '') ? REMAINING : REMAINING.filter(c => {{
    for (const n of includeNums) if (!c.includes(n)) return false;
    for (const n of excludeNums) if (c.includes(n)) return false;
    if (hcVal !== '' && hotCount(c) !== parseInt(hcVal, 10)) return false;
    return true;
  }});
  const parts = [];
  if (includeNums.length) parts.push('contain ' + includeNums.sort((a,b)=>a-b).join(', '));
  if (excludeNums.length) parts.push('exclude ' + excludeNums.sort((a,b)=>a-b).join(', '));
  if (hcVal !== '') parts.push(hcVal + 'h/' + (7 - parseInt(hcVal, 10)) + 'c pattern');
  document.getElementById('filterInfo').textContent = parts.length === 0 ? '' :
    (filtered.length.toLocaleString() + ' / ' + REMAINING.length.toLocaleString() + ' combos ' + parts.join(' and '));
  curPage = 0;
  render();
}}

// ── Diverse sample generator: greedy coverage-maximizing pick, same
// algorithm used on the Loto6 elimination pages. ─────────────────────────
function generateSamples(n) {{
  const pool = filtered.length > 0 ? filtered : REMAINING;
  const container = document.getElementById('generatedResults');
  if (pool.length === 0) {{
    container.innerHTML = '<p style="color:#64748b;font-size:.85rem">No combos match the current filter to sample from.</p>';
    return;
  }}
  const count = Math.min(n, pool.length);

  const order = Array.from({{length: pool.length}}, (_, i) => i);
  for (let i = order.length - 1; i > 0; i--) {{
    const j = Math.floor(Math.random() * (i + 1));
    [order[i], order[j]] = [order[j], order[i]];
  }}

  const usage = new Map();
  const takenPositions = new Set();
  const picks = [];
  for (let round = 0; round < count; round++) {{
    let bestPos = -1;
    let bestScore = Infinity;
    for (let k = 0; k < order.length; k++) {{
      if (takenPositions.has(k)) continue;
      const c = pool[order[k]];
      let score = 0;
      for (let m = 0; m < c.length; m++) score += (usage.get(c[m]) || 0);
      if (score < bestScore) {{
        bestScore = score;
        bestPos = k;
        if (bestScore === 0 && round === 0) break;
      }}
    }}
    const chosen = pool[order[bestPos]];
    takenPositions.add(bestPos);
    picks.push(chosen);
    for (const num of chosen) usage.set(num, (usage.get(num) || 0) + 1);
  }}

  const distinctCovered = new Set(picks.flat()).size;
  const sourceLabel = filtered.length > 0 && filtered.length < REMAINING.length ? filtered.length.toLocaleString() + ' filtered' : REMAINING.length.toLocaleString() + ' total';
  container.innerHTML =
    '<div class="gen-hdr">Generated ' + picks.length + ' diverse combo' + (picks.length !== 1 ? 's' : '') +
    ' from ' + sourceLabel + ' — covers ' + distinctCovered + ' distinct pool numbers:</div>' +
    picks.map(c => '<div class="balls gen-row">' + c.map(n2 =>
      '<span class="nb" style="background:' + getBallColor(n2) + '33;color:#e2e8f0;border:1px solid ' + getBallColor(n2) + '">' + n2 + '</span>'
    ).join('') + '</div>').join('');
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
  let csv = 'n1,n2,n3,n4,n5,n6,n7\\n' + rows.map(c => c.join(',')).join('\\n');
  const blob = new Blob([csv], {{type: 'text/csv'}});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'loto7_draw_{TARGET_SERIAL}_remaining_combos.csv';
  a.click();
  URL.revokeObjectURL(url);
}}
</script>
</body>
</html>"""

with open(HTML_OUT, 'w', encoding='utf-8') as f:
    f.write(page)
print(f"Wrote {HTML_OUT} ({len(page)//1024} KB)")
