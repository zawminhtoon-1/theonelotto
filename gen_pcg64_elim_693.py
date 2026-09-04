"""
gen_pcg64_elim_693.py
--------------------------
Generates the Loto7 PCG64-seed draw #693 elimination page -- mirrors
the Loto6 elimination-page pattern (e.g. xoshiro_elim_2130.html) and
Loto7's own loto7_elim_693.html: shows the Base pool, live client-side
verification badge (bit-exact BigInt PCG64 port), Pass 1 (16 methods'
K=20 picks, checked independently -- same style as loto7_elim_693.html's
Pass 1 but K=20 instead of K=22), Pass 2 (16 methods, each individually
intersected with Base at K=31, checked independently -- 16 separate
method-specific pools, not one combined intersection), Pass 3 (removes
any combo overlapping 5+ with ANY of the last 100 actual draws --
checked live client-side, pure historical data, no ML methods needed),
Pass 4 (final -- removes any combo with 4+ consecutive/adjacent-
differ-by-1 pairs among its 7 numbers, also checked live client-side),
the elimination summary, and a paginated/filterable/CSV-downloadable
combo browser over the Pass-4-remaining combos -- hot/cold pattern
filter dropdown and greedy "Diverse sample" Generate 5/10 buttons
included.

Reads pcg64_elim_693_meta.json (small: base pool, seed, counts). The
large combo list lives separately at public/pcg64_elim_693_combos.json
and the historical winning-combo set (for the hot/cold split) at
public/pcg64_elim_693_historical.json -- both fetched client-side, not
inlined.

Output: public/pcg64_elim_693.html
Run: python gen_pcg64_elim_693.py
"""
import json

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
META_PATH = BASE + r"\pcg64_elim_693_meta.json"
HTML_OUT = BASE + r"\public\pcg64_elim_693.html"

with open(META_PATH, encoding='utf-8') as f:
    meta = json.load(f)

TARGET_SERIAL = meta['targetSerial']
TRAINED_THROUGH = meta['trainedThroughSerial']
SEED = meta['seed']
K_PICKS = meta['k']
base = meta['base']
universe_count = meta['universeCount']
historical_draw_count = meta['historicalDrawCount']

method_names = meta['methodNames']
method_k = meta['methodK']
method_picks = meta['methodPicks']
removed_by_methods = meta['removedByMethods']
final_remaining_pass1 = meta['finalRemainingPass1']
pass1_pct = final_remaining_pass1 / universe_count * 100

pass2_method_k = meta['pass2MethodK']
pass2_intersected_pools = meta['pass2IntersectedPools']
removed_by_pass2 = meta['removedByPass2']
final_remaining_pass2 = meta['finalRemainingPass2']
pass2_pct = final_remaining_pass2 / universe_count * 100
pass2_pct_of_pass1 = final_remaining_pass2 / final_remaining_pass1 * 100

pass3_window = meta['pass3Window']
pass3_overlap_threshold = meta['pass3OverlapThreshold']
pass3_window_serials = meta['pass3WindowSerials']
pass3_window_draws = meta['pass3WindowDraws']
removed_by_pass3 = meta['removedByPass3']
final_remaining_pass3 = meta['finalRemainingPass3']
pass3_pct = final_remaining_pass3 / universe_count * 100
pass3_pct_of_pass2 = final_remaining_pass3 / final_remaining_pass2 * 100

pass4_pair_threshold = meta['pass4PairThreshold']
pass4_pair_distribution = meta['pass4PairDistribution']
removed_by_pass4 = meta['removedByPass4']
final_remaining_pass4 = meta['finalRemainingPass4']
pass4_pct = final_remaining_pass4 / universe_count * 100
pass4_pct_of_pass3 = final_remaining_pass4 / final_remaining_pass3 * 100

final_remaining = meta['finalRemaining']
final_pct = final_remaining / universe_count * 100

methods_rows_html = ""
for name, pool in zip(method_names, method_picks):
    balls = "".join(f'<span class="nb">{n}</span>' for n in pool)
    methods_rows_html += f"""<tr><td class="mname">{name}</td><td><div class="balls">{balls}</div></td></tr>"""

pass2_rows_html = ""
for name, ipool in zip(method_names, pass2_intersected_pools):
    balls = "".join(f'<span class="nb">{n}</span>' for n in ipool)
    pass2_rows_html += f"""<tr><td class="mname">{name}</td><td><div class="balls">{balls}</div></td></tr>"""

page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Loto 7 PCG64 Seed — Draw #{TARGET_SERIAL} Elimination</title>
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
.section h2{{font-size:1rem;font-weight:700;color:#f1f5f9;margin-bottom:4px;display:flex;align-items:center;gap:8px;flex-wrap:wrap}}
.section h3{{font-size:.86rem;font-weight:700;color:#cbd5e1;margin:14px 0 6px}}
.order-label{{font-size:.7rem;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:.04em;
  margin:10px 0 5px;display:flex;align-items:center;gap:8px}}
.order-hint{{font-size:.72rem;font-weight:400;text-transform:none;letter-spacing:normal;color:#475569}}
.section .desc{{font-size:.8rem;color:#64748b;margin-bottom:14px}}
.verify-badge{{font-size:.68rem;font-weight:700;padding:2px 8px;border-radius:10px;text-transform:uppercase;letter-spacing:.04em}}
.verify-badge.pending{{background:#1e293b;color:#94a3b8}}
.verify-badge.ok{{background:#14532d;color:#86efac}}
.verify-badge.fail{{background:#450a0a;color:#fca5a5}}

.balls{{display:flex;flex-wrap:wrap;gap:5px}}
.nb{{display:inline-flex;align-items:center;justify-content:center;width:30px;height:30px;
  border-radius:50%;font-size:.78rem;font-weight:700;background:#312e5f;color:#c4b5fd;
  border:1px solid #7c3aed55;flex-shrink:0}}
.nb.b4{{background:#052e16;color:#86efac;border-color:#22c55e55}}

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

.verify-badge.na{{background:#1e293b;color:#64748b}}

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
.pairs-check{{display:inline-flex;align-items:center;gap:4px;font-size:.8rem;color:#cbd5e1;cursor:pointer;user-select:none}}
.pairs-check input{{accent-color:#7c3aed;cursor:pointer}}
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
  <h1>✂️ Loto 7 PCG64 Seed — Draw #{TARGET_SERIAL} Elimination</h1>
  <p class="subtitle">PCG64 K={K_PICKS} seed #{SEED:,}'s pick for draw #{TARGET_SERIAL} — Pass 1 = 16 methods' K={method_k} picks — Pass 2 = 16 methods' K={pass2_method_k} picks ∩ Base — Pass 3 = overlap≥{pass3_overlap_threshold} vs last {pass3_window} draws — Pass 4 = consecutive-pairs≥{pass4_pair_threshold}</p>

  <div class="note">
    <p><strong style="color:#e2e8f0">Base</strong> is <strong>PCG64 (O'Neill XSL-RR 128/64) K={K_PICKS} seed
    #{SEED:,}'s pick</strong> for draw #{TARGET_SERIAL} (not yet drawn), walk-forward — a pure function of
    (seed, draw serial), no training data needed. This seed is the overall winner of
    <a href="/pcg64_seed_scan_loto7_k30.html" style="color:#a78bfa">the completed Loto7 PCG64 K=30 seed scan</a>
    (10,000,001 seeds, -5,000,000 to 5,000,000, draws #1-650). It defines the working universe: all
    C({base['k']},7) = {universe_count:,} seven-number combinations drawable from this {base['k']}-number pool.</p>
    <p><strong style="color:#e2e8f0">Pass 1</strong> is each of the 16 prediction methods' K={method_k} pick for draw
    #{TARGET_SERIAL} (native K=15 pool normalized to K={method_k} via <code>topKNums()</code>, walk-forward trained
    through #{TRAINED_THROUGH}), checked <strong>independently</strong> — NOT a union of raw numbers, same style as
    <a href="/loto7_elim_693.html" style="color:#a78bfa">loto7_elim_693.html</a>'s Pass 1 (just K={method_k} instead
    of K=22). Any Base combo fully contained within ANY single one of these 16 K={method_k} sets gets removed,
    leaving {final_remaining_pass1:,}.</p>
    <p><strong style="color:#e2e8f0">Pass 2</strong> is, for each of the 16 methods <strong>individually</strong>,
    that method's K={pass2_method_k} pick <strong>intersected with Base</strong> — 16 separate method-specific
    intersected pools, NOT one combined 16-way intersection. Each intersected pool is checked independently, same
    pattern as Pass 1. Any Pass-1-remaining combo fully contained within ANY SINGLE one of these 16 intersected
    pools gets removed, leaving {final_remaining_pass2:,}.</p>
    <p><strong style="color:#e2e8f0">Pass 3</strong> removes any Pass-2-remaining combo that shares
    {pass3_overlap_threshold} or more numbers with <strong>ANY</strong> of the last {pass3_window} actual draws
    before #{TARGET_SERIAL} — draws #{pass3_window_serials[0]}&ndash;{pass3_window_serials[1]}, checked against the
    whole window, not one fixed distance. <strong style="color:#e2e8f0">Validated first:</strong> a multi-distance
    overlap check across Loto7's full 692-draw history (distances 1, 2, 3, 5, 10, 50, and 100 steps back) found
    overlap&ge;6 has <strong style="color:#86efac">never once occurred</strong> at any tested distance (0/592&ndash;691
    pairs per distance); overlap=5 is rare but not impossible (5 occurrences total across all distances combined).
    This pass uses the &ge;{pass3_overlap_threshold} threshold. Leaves {final_remaining_pass3:,}.</p>
    <p><strong style="color:#e2e8f0">Pass 4</strong> (final) removes any Pass-3-remaining combo with
    {pass4_pair_threshold} or more consecutive (adjacent, differ-by-1) pairs among its 7 numbers.
    <strong style="color:#e2e8f0">Validated first:</strong> a consecutive-pairs analysis across all 692 real Loto7
    draws found 4-pair combos occurred 7 times (1.01%, vs 0.65% exact chance expectation); 5- and 6-pair combos
    occurred <strong style="color:#86efac">zero times</strong> (vs 0.027% and 0.0003% chance expectation
    respectively). This pass uses the &ge;{pass4_pair_threshold} threshold, covering all three tiers. Leaves
    <strong style="color:#38bdf8">{final_remaining_pass4:,}</strong>.</p>
    <p><strong style="color:#fbbf24">No further passes yet</strong> beyond Pass 4 — more passes will be added in
    later, separately-directed builds (see
    <a href="/pcg64_top3_elim_2134.html" style="color:#a78bfa">the Loto6 equivalent</a> for what a fully-built
    multi-pass elimination page on this site looks like).</p>
    <p>The Base pool, Pass 3, and Pass 4 are recomputed <strong>live in your browser</strong> below (bit-exact
    BigInt PCG64 port for Base, pure JS historical/pattern checks for Passes 3 and 4) and checked against the
    server-embedded reference — check the verification badges. Passes 1 and 2's 16 statistical/ML methods can't
    (practically) run in a browser, so those are precomputed server-side and embedded as static data.</p>
  </div>

  <div class="section">
    <h2>Base — PCG64 K={K_PICKS} seed #{SEED:,} <span id="badgeBase" class="verify-badge pending">verifying…</span></h2>
    <p class="desc">Pure function of (seed, draw serial) — no training data needed.</p>
    <div class="order-label">Ascending order</div>
    <div class="balls" id="baseBalls"></div>
    <div class="order-label">Generation order <span class="order-hint">(O'Neill XSL-RR partial Fisher-Yates order)</span> <span id="badgeBaseOrdered" class="verify-badge pending">verifying…</span></div>
    <div class="balls" id="baseBallsOrdered"></div>
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
    <h2>Pass 2 — 16 methods, K={pass2_method_k} pick ∩ Base for draw #{TARGET_SERIAL} <span class="verify-badge na">server-computed</span></h2>
    <p class="desc">Each method's native K=15 pool normalized to K={pass2_method_k}, then intersected with the {base['k']}-number
    Base pool — 16 separate method-specific pools (sizes vary per method), checked independently against what's left after Pass 1.</p>
    <details>
      <summary>Show all 16 methods' (K={pass2_method_k} ∩ Base) pools</summary>
      <table class="methods-table">
        <tbody>{pass2_rows_html}</tbody>
      </table>
    </details>
  </div>

  <div class="section">
    <h2>Pass 3 — overlap&ge;{pass3_overlap_threshold} vs last {pass3_window} draws <span id="badgePass3" class="verify-badge pending">verifying…</span>
    <span class="verify-badge" style="background:#14532d;color:#86efac">overlap&ge;6 well-supported (0/592&ndash;691 per distance)</span></h2>
    <p class="desc">Removes any Pass-2-remaining combo that shares {pass3_overlap_threshold}+ numbers with ANY of the
    {pass3_window} actual draws #{pass3_window_serials[0]}&ndash;{pass3_window_serials[1]}. Checked live in your
    browser (pure JS, no server reference needed).</p>
    <p class="desc" style="margin-bottom:0">Removed {removed_by_pass3:,} combos with overlap&ge;{pass3_overlap_threshold}
    against at least one of the {pass3_window} draws. Final remaining after Pass 3: {final_remaining_pass3:,}.</p>
  </div>

  <div class="section">
    <h2>Pass 4 (final) — consecutive-pairs&ge;{pass4_pair_threshold} <span id="badgePass4" class="verify-badge pending">verifying…</span>
    <span class="verify-badge" style="background:#14532d;color:#86efac">5-6 pairs well-supported (0/692 historically)</span></h2>
    <p class="desc">Removes any Pass-3-remaining combo with {pass4_pair_threshold}+ consecutive (adjacent,
    differ-by-1) pairs among its 7 numbers — e.g. a combo containing 14,15,16,17 has 3 such pairs (14-15, 15-16,
    16-17); pair-count = 7 minus the number of separate consecutive runs. Checked live in your browser (pure JS,
    no server reference needed).</p>
    <p class="desc" style="margin-bottom:0">Pair-count distribution among the {final_remaining_pass3:,}
    Pass-3-remaining combos: {' &middot; '.join(f'{k} pairs: {int(v):,}' for k, v in pass4_pair_distribution.items())}.
    Removed {removed_by_pass4:,} combos with {pass4_pair_threshold}+ pairs. Final remaining:
    <strong style="color:#38bdf8">{final_remaining_pass4:,}</strong>.</p>
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
        <div class="lbl">Removed by 16 methods ∩ Base (Pass 2)</div>
        <div class="val">{removed_by_pass2:,}</div>
        <div class="sub">contained in ANY method's (K={pass2_method_k} ∩ Base)</div>
      </div>
      <div class="stat-card">
        <div class="lbl">After Pass 2</div>
        <div class="val">{final_remaining_pass2:,}</div>
        <div class="sub">{pass2_pct:.1f}% of universe · {pass2_pct_of_pass1:.1f}% of Pass-1 output</div>
      </div>
      <div class="stat-card">
        <div class="lbl">Removed by last-{pass3_window}-draws filter (Pass 3)</div>
        <div class="val">{removed_by_pass3:,}</div>
        <div class="sub">overlap &ge;{pass3_overlap_threshold} vs ANY of the {pass3_window} draws</div>
      </div>
      <div class="stat-card">
        <div class="lbl">After Pass 3</div>
        <div class="val">{final_remaining_pass3:,}</div>
        <div class="sub">{pass3_pct:.1f}% of universe · {pass3_pct_of_pass2:.1f}% of Pass-2 output</div>
      </div>
      <div class="stat-card">
        <div class="lbl">Removed by consecutive-pairs filter (Pass 4)</div>
        <div class="val">{removed_by_pass4:,}</div>
        <div class="sub">consecutive-pairs &ge;{pass4_pair_threshold}</div>
      </div>
      <div class="stat-card final">
        <div class="lbl">Final remaining</div>
        <div class="val">{final_remaining:,}</div>
        <div class="sub">{final_pct:.1f}% of universe · {pass4_pct_of_pass3:.1f}% of Pass-3 output</div>
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
      <span class="n final">{final_remaining_pass4:,}</span> <span style="color:#64748b;font-size:.7rem">(P4)</span>
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
        <span class="pd-lbl" style="margin-left:6px">Pairs filter</span>
        <label class="pairs-check"><input type="checkbox" id="pairsCheck1" checked onchange="applyFilter()"> 1 pair</label>
        <label class="pairs-check"><input type="checkbox" id="pairsCheck2" checked onchange="applyFilter()"> 2 pairs</label>
        <label class="pairs-check"><input type="checkbox" id="pairsCheck3" checked onchange="applyFilter()"> 3 pairs</label>
        <button class="btn" onclick="clearFilter()">Clear filter</button>
        <button class="btn primary" onclick="downloadCSV()">⬇ Download CSV</button>
        <span id="filterInfo" class="page-info"></span>
      </div>
      <div class="filter-legend">Click a number to cycle: <span class="swatch neutral"></span>neutral (no filter) &rarr;
        <span class="swatch include"></span>include (must contain) &rarr; <span class="swatch exclude"></span>exclude (must not
        contain) &rarr; back to neutral. Include and exclude constraints apply together. Hot/cold pattern (walk-forward
        top-18/bottom-19 split, computed live from the embedded historical data) and the pairs filter both apply on top
        of the number filter. The pairs filter is browsing-only — it does NOT touch the underlying {final_remaining:,}-combo
        pool or the Pass 4 badge above (which already permanently removed all 4+-pair combos); unchecking a box here just
        hides that pair-count tier from the current view.</div>
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
    PCG64 (O'Neill XSL-RR 128/64, seeded via SplitMix64-expanded {{state,inc}}): picks = partial Fisher-Yates(range(1,38), {K_PICKS})
    with combined seed = seed×10⁷ + draw_serial. Core algorithm verified bit-exact against <code>numpy.random.Generator(PCG64())</code>
    for this pool_max=37/K={K_PICKS} configuration before the seed scan ran.<br>
    Base = the overall winner of the completed Loto7 PCG64 K=30 seed scan (10,000,001 seeds). Pass 1 = 16 methods'
    K={method_k} picks, same style as loto7_elim_693.html. Pass 2 = each method's K={pass2_method_k} pick intersected
    with Base individually (16 separate pools). Pass 3 = overlap&ge;{pass3_overlap_threshold} vs any of the last
    {pass3_window} actual draws. Pass 4 = consecutive-pairs&ge;{pass4_pair_threshold}. {final_remaining:,} of
    {universe_count:,} combos remain.<br>
    16 methods: Poly Regression, Moving Avg-37, Exp-Weighted Avg, Frequency, Markov Chain, ARIMA(2,1,0), Random Forest,
    RL (Linear Q), HMM, k-NN, Modular Cycle, Apriori, Monte Carlo, Naive Bayes, Weighted MA-37, LSTM — same 16 used
    throughout <a href="/loto7_backtest.html" style="color:#64748b">loto7_backtest.html</a> /
    <a href="/loto7/predictions" style="color:#64748b">predictions</a>.<br>
    Formula-based only · Not financial advice · Loto 7 is random.
  </p>
</div>

<script>
// ── PCG64 (O'Neill XSL-RR 128/64), bit-exact BigInt port ────────────────────
const MASK64 = (1n << 64n) - 1n;
const MASK128 = (1n << 128n) - 1n;
const PCG_MULT_128 = 0x2360ed051fc65da44385df649fccf645n;

function splitmix64Next(z) {{
  z = (z + 0x9E3779B97F4A7C15n) & MASK64;
  let zz = z;
  zz = ((zz ^ (zz >> 30n)) * 0xBF58476D1CE4E5B9n) & MASK64;
  zz = ((zz ^ (zz >> 27n)) * 0x94D049BB133111EBn) & MASK64;
  zz = zz ^ (zz >> 31n);
  return [z, zz];
}}
function pcg64PredictRaw(seed, drawSerial, k) {{
  const combined = (BigInt(seed) * 10000000n + BigInt(drawSerial)) & MASK64;
  let z = combined & MASK64;
  const outs = [];
  for (let i = 0; i < 4; i++) {{
    const [nz, o] = splitmix64Next(z);
    z = nz;
    outs.push(o);
  }}
  let state = ((outs[0] << 64n) | outs[1]) & MASK128;
  let inc = (((outs[2] << 64n) | outs[3]) | 1n) & MASK128;
  const arr = Array.from({{length: {37}}}, (_, i) => i + 1);
  const n = arr.length;
  const order = [];
  for (let i = n - 1; i >= n - k; i--) {{
    state = (state * PCG_MULT_128 + inc) & MASK128;
    const xored = (state >> 64n) ^ (state & MASK64);
    const rot = (state >> 122n) & 0x3fn;
    const shift = (64n - rot) % 64n;
    const out = ((xored >> rot) | (xored << shift)) & MASK64;
    const j = Number(out % BigInt(i + 1));
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

const KNOWN_BASE = {json.dumps(base['pool'])};
const KNOWN_BASE_ORDERED = {json.dumps(base['poolOrdered'])};

const liveBase = pcg64Predict({SEED}, {TARGET_SERIAL}, {K_PICKS});
const liveBaseOrdered = pcg64PredictRaw({SEED}, {TARGET_SERIAL}, {K_PICKS});
renderBalls('baseBalls', liveBase, 'b4');
renderBalls('baseBallsOrdered', liveBaseOrdered, 'b4');
renderBadge('badgeBase', arraysEqual(liveBase, KNOWN_BASE));
renderBadge('badgeBaseOrdered', arraysEqual(liveBaseOrdered, KNOWN_BASE_ORDERED));
if (!arraysEqual(liveBase, KNOWN_BASE)) console.error('Base mismatch', liveBase, KNOWN_BASE);
if (!arraysEqual(liveBaseOrdered, KNOWN_BASE_ORDERED)) console.error('Base (generation order) mismatch', liveBaseOrdered, KNOWN_BASE_ORDERED);

// ── Hot/cold pattern filter: walk-forward top-18/bottom-19 split, computed
// live from the embedded historical winning-combo set. ─────────────────────
let HOT_SET = new Set();
function hotCount(combo) {{
  return combo.filter(n => HOT_SET.has(n)).length;
}}

// ── Pass 3: overlap>={pass3_overlap_threshold} vs ANY of the last {pass3_window} actual draws -- pure JS,
// no server reference needed beyond the embedded draw window itself. ───────
const PASS3_WINDOW_DRAWS = {json.dumps(pass3_window_draws)};
const PASS3_OVERLAP_THRESHOLD = {pass3_overlap_threshold};
function maxOverlapVsWindow(combo) {{
  let best = 0;
  for (const draw of PASS3_WINDOW_DRAWS) {{
    let ov = 0;
    for (const n of combo) if (draw.includes(n)) ov++;
    if (ov > best) best = ov;
  }}
  return best;
}}

// ── Pass 4: consecutive-pairs>={pass4_pair_threshold} filter -- pure JS,
// pair-count = 7 minus the number of separate consecutive runs. ─────────────
const PASS4_PAIR_THRESHOLD = {pass4_pair_threshold};
function consecutivePairCount(combo) {{
  const s = [...combo].sort((a, b) => a - b);
  let runs = 1;
  for (let i = 1; i < s.length; i++) {{
    if (s[i] !== s[i - 1] + 1) runs++;
  }}
  return s.length - runs;
}}

// ── Remaining combos + historical set: fetch, paginate, filter, download ────
const POOL_BASE = liveBase;
let REMAINING = [];
let filtered = [];
const PAGE_SIZE = 100;
let curPage = 0;
const numState = new Map();

Promise.all([
  fetch('/pcg64_elim_{TARGET_SERIAL}_combos.json').then(r => r.json()),
  fetch('/pcg64_elim_{TARGET_SERIAL}_historical.json').then(r => r.json())
]).then(([combosData, historicalData]) => {{
  REMAINING = combosData;
  filtered = REMAINING;
  document.getElementById('loadingMsg').style.display = 'none';
  document.getElementById('comboUI').style.display = 'block';

  const freq = new Array(38).fill(0);
  historicalData.forEach(combo => combo.forEach(n => freq[n]++));
  const nums = Array.from({{length: 37}}, (_, i) => i + 1);
  nums.sort((a, b) => freq[b] - freq[a] || a - b);
  HOT_SET = new Set(nums.slice(0, 18));

  const stillHighOverlap = REMAINING.filter(c => maxOverlapVsWindow(c) >= PASS3_OVERLAP_THRESHOLD);
  renderBadge('badgePass3', stillHighOverlap.length === 0);
  if (stillHighOverlap.length > 0) console.error('Pass-3 leak: remaining combos still overlap >= ' + PASS3_OVERLAP_THRESHOLD + ' with a last-{pass3_window}-draws window entry', stillHighOverlap);

  const stillHighPairs = REMAINING.filter(c => consecutivePairCount(c) >= PASS4_PAIR_THRESHOLD);
  renderBadge('badgePass4', stillHighPairs.length === 0);
  if (stillHighPairs.length > 0) console.error('Pass-4 leak: remaining combos still have consecutive-pairs >= ' + PASS4_PAIR_THRESHOLD, stillHighPairs);

  buildFilterGrid();
  render();
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
  document.getElementById('hcFilterSelect').value = '';
  document.getElementById('pairsCheck1').checked = true;
  document.getElementById('pairsCheck2').checked = true;
  document.getElementById('pairsCheck3').checked = true;
  applyFilter();
}}
function applyFilter() {{
  const includeNums = [...numState.entries()].filter(([n, s]) => s === 'include').map(([n]) => n);
  const excludeNums = [...numState.entries()].filter(([n, s]) => s === 'exclude').map(([n]) => n);
  const hcVal = document.getElementById('hcFilterSelect').value;

  // Pairs filter: browsing-only, does NOT touch REMAINING (the stored pool)
  // or any badge -- purely restricts what's displayed/sampled here. All
  // three boxes checked (the default) means "no filtering" -- 0-pair combos
  // (which have no checkbox of their own) stay visible in that default
  // state, matching "nothing changes by default".
  const p1 = document.getElementById('pairsCheck1').checked;
  const p2 = document.getElementById('pairsCheck2').checked;
  const p3 = document.getElementById('pairsCheck3').checked;
  const pairsFilterActive = !(p1 && p2 && p3);
  const allowedPairCounts = new Set([...(p1 ? [1] : []), ...(p2 ? [2] : []), ...(p3 ? [3] : [])]);

  filtered = (includeNums.length === 0 && excludeNums.length === 0 && hcVal === '' && !pairsFilterActive) ? REMAINING : REMAINING.filter(c => {{
    for (const n of includeNums) if (!c.includes(n)) return false;
    for (const n of excludeNums) if (c.includes(n)) return false;
    if (hcVal !== '' && hotCount(c) !== parseInt(hcVal, 10)) return false;
    if (pairsFilterActive && !allowedPairCounts.has(consecutivePairCount(c))) return false;
    return true;
  }});
  const parts = [];
  if (includeNums.length) parts.push('contain ' + includeNums.sort((a,b)=>a-b).join(', '));
  if (excludeNums.length) parts.push('exclude ' + excludeNums.sort((a,b)=>a-b).join(', '));
  if (hcVal !== '') parts.push(hcVal + 'h/' + (7 - parseInt(hcVal, 10)) + 'c pattern');
  if (pairsFilterActive) parts.push('pairs in {{' + [...allowedPairCounts].sort().join(',') + '}} (0-pair combos hidden)');
  document.getElementById('filterInfo').textContent = parts.length === 0 ? '' :
    (filtered.length.toLocaleString() + ' / ' + REMAINING.length.toLocaleString() + ' combos ' + parts.join(' and '));
  curPage = 0;
  render();
}}

// ── Diverse sample generator: greedy coverage-maximizing pick, same
// algorithm used on the other elimination pages. ─────────────────────────
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
  a.download = 'loto7_draw_{TARGET_SERIAL}_pcg64_base_combos.csv';
  a.click();
  URL.revokeObjectURL(url);
}}
</script>
</body>
</html>"""

with open(HTML_OUT, 'w', encoding='utf-8') as f:
    f.write(page)
print(f"Wrote {HTML_OUT} ({len(page)//1024} KB)")
