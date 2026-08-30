"""
gen_xoshiro_base_review100.py
-----------------------------------
Generates the "Base Pool Construction Review — Last 100 Draws" page:
a narrower cousin of xoshiro_elim_backtest100.html that stops at the
Base-pool-construction stage (Base = Modular Cycle K=33 (walk-forward)
intersect xoshiro K=38 seed #692,809) instead of running the full
5-pass elimination funnel, and adds generation-order detail -- for
each of the last 100 real draws' 6 actual numbers, WHERE (if at all)
that number fell in each of the two inputs' own raw pick sequence.

Reads xoshiro_base_review100_meta.json (produced by
precompute_xoshiro_base_review100.py).

Output: public/xoshiro_base_review100.html
Run: python gen_xoshiro_base_review100.py
"""
import json
from collections import Counter
from math import comb

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
META_PATH = BASE + r"\xoshiro_base_review100_meta.json"
HTML_OUT = BASE + r"\public\xoshiro_base_review100.html"

with open(META_PATH, encoding='utf-8') as f:
    meta = json.load(f)

n_draws = meta['nDraws']
draw_lo, draw_hi = meta['drawRange']
k_xo = meta['kXo']
k_mc = meta['kMc']
k_mc_native = meta['kMcNative']
seed_xo = meta['seedXo']
all6 = meta['all6Count']
partial = meta['partialCount']
zero = meta['zeroCount']
overlap_hist = meta['overlapHistogram']
results = meta['results']
elapsed_seconds = meta['elapsedSeconds']

theoretical_base_rate = comb(29, 6) / comb(43, 6) * 100  # approx, K_BASE hovers ~28-29

# Early/late thresholds for the per-number index badges -- top third of each
# method's own K counts as "early".
MC_EARLY = -(-k_mc // 3)   # ceil(33/3) = 11
XO_EARLY = -(-k_xo // 3)   # ceil(38/3) = 13

def idx_badge(label, idx, early_cutoff):
    if idx is None:
        return f'<span class="idx-badge absent">{label} —</span>'
    cls = "early" if idx <= early_cutoff else "late"
    return f'<span class="idx-badge {cls}">{label} #{idx}</span>'

# ── Aggregate cross-method findings over all {n_draws}x6 actual-number instances ──
total_numbers = 0
in_mc = in_xo = in_both = in_neither = 0
mc_idx_sum = mc_idx_n = 0
xo_idx_sum = xo_idx_n = 0
mc_only = xo_only = 0
for r in results:
    for pn in r['perNumber']:
        total_numbers += 1
        has_mc = pn['mcIdx'] is not None
        has_xo = pn['xoIdx'] is not None
        if has_mc: in_mc += 1; mc_idx_sum += pn['mcIdx']; mc_idx_n += 1
        if has_xo: in_xo += 1; xo_idx_sum += pn['xoIdx']; xo_idx_n += 1
        if has_mc and has_xo: in_both += 1
        if not has_mc and not has_xo: in_neither += 1
        if has_mc and not has_xo: mc_only += 1
        if has_xo and not has_mc: xo_only += 1

mc_avg_idx = mc_idx_sum / mc_idx_n if mc_idx_n else 0
xo_avg_idx = xo_idx_sum / xo_idx_n if xo_idx_n else 0

rows_html = ""
for r in reversed(results):  # newest first
    balls_html = ""
    for pn in r['perNumber']:
        mc_b = idx_badge("MC", pn['mcIdx'], MC_EARLY)
        xo_b = idx_badge("XO", pn['xoIdx'], XO_EARLY)
        balls_html += f"""<div class="numchip">
        <span class="nb">{pn['n']}</span>
        <div class="idxrow">{mc_b}{xo_b}</div>
      </div>"""
    overlap = r['baseOverlap']
    if overlap == 6:
        cov_cls, cov_label = "cov-all", "6/6 — All in Base ✓"
    elif overlap == 0:
        cov_cls, cov_label = "cov-zero", "0/6 — None in Base"
    else:
        cov_cls, cov_label = "cov-partial", f"{overlap}/6 — Partial"
    rows_html += f"""<tr data-overlap="{overlap}">
  <td class="tc">#{r['serial']}</td>
  <td class="tc">{r['date']}</td>
  <td><div class="numchips">{balls_html}</div></td>
  <td class="tc"><span class="cov-pill {cov_cls}">{cov_label}</span></td>
  <td class="tc">{r['kBase']}</td>
</tr>"""

OVERLAP_COLORS = {6: '#22c55e', 5: '#4ade80', 4: '#a3e635', 3: '#fbbf24', 2: '#fb923c', 1: '#f87171', 0: '#475569'}
funnel_rows = ""
for k in [6, 5, 4, 3, 2, 1, 0]:
    v = overlap_hist.get(str(k), 0)
    pct = v / n_draws * 100
    funnel_rows += f"""<div class="funnel-row">
        <div class="funnel-lbl">{k}/6 in Base</div>
        <div class="funnel-bar-wrap"><div class="funnel-bar" style="width:{pct:.1f}%;background:{OVERLAP_COLORS[k]}"></div></div>
        <div class="funnel-val">{v}</div>
      </div>"""

page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Base Pool Construction Review — Last {n_draws} Draws</title>
<style>

*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0a0f1e;color:#e2e8f0;font-family:system-ui,sans-serif;padding-top:60px;min-height:100vh}}
.wrap{{max-width:1300px;margin:0 auto;padding:24px 16px}}
h1{{font-size:1.4rem;font-weight:700;color:#f1f5f9;margin-bottom:4px}}
.subtitle{{font-size:.85rem;color:#64748b;margin-bottom:20px}}

.note{{background:#0d1526;border:1px solid #1e293b;border-radius:10px;padding:14px 18px;
  font-size:.8rem;color:#94a3b8;margin-bottom:20px;line-height:1.6}}
.note p+p{{margin-top:8px}}
.note code{{background:#0a0f1e;padding:1px 5px;border-radius:4px;font-size:.85em}}

.section{{background:#0d1526;border:1px solid #1e293b;border-radius:12px;padding:20px;margin-bottom:20px}}
.section h2{{font-size:1rem;font-weight:700;color:#f1f5f9;margin-bottom:4px}}
.section .desc{{font-size:.8rem;color:#64748b;margin-bottom:14px}}

.nb{{display:inline-flex;align-items:center;justify-content:center;width:24px;height:24px;
  border-radius:50%;font-size:.68rem;font-weight:700;background:#312e5f;color:#c4b5fd;
  border:1px solid #7c3aed55;flex-shrink:0}}

.stats-row{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px}}
.stat-card{{background:#0a0f1e;border:1px solid #1e293b;border-radius:10px;padding:14px 18px;flex:1;min-width:140px}}
.stat-card .lbl{{font-size:.68rem;color:#64748b;text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px}}
.stat-card .val{{font-size:1.3rem;font-weight:700;color:#f1f5f9}}
.stat-card .sub{{font-size:.72rem;color:#94a3b8;margin-top:2px}}
.stat-card.hit .val{{color:#22c55e}}
.stat-card.neverbase .val{{color:#475569}}

.funnel{{display:flex;flex-direction:column;gap:6px}}
.funnel-row{{display:flex;align-items:center;gap:10px;font-size:.82rem}}
.funnel-lbl{{width:150px;color:#94a3b8;flex-shrink:0}}
.funnel-bar-wrap{{flex:1;background:#0a0f1e;border-radius:6px;overflow:hidden;height:22px;border:1px solid #1e293b}}
.funnel-bar{{height:100%;border-radius:6px}}
.funnel-val{{width:50px;text-align:right;color:#f1f5f9;font-weight:600;flex-shrink:0}}

.controls{{display:flex;gap:10px;align-items:center;margin-bottom:14px;flex-wrap:wrap}}
.controls select{{background:#0d1526;border:1px solid #334155;border-radius:7px;padding:7px 12px;
  color:#e2e8f0;font-size:.83rem}}

.tbl-wrap{{overflow-x:auto;border-radius:10px;border:1px solid #1e293b}}
table.results{{width:100%;border-collapse:collapse;font-size:.8rem}}
table.results th{{background:#0a0f1e;padding:8px 10px;text-align:left;color:#94a3b8;
  font-weight:600;font-size:.68rem;text-transform:uppercase;letter-spacing:.04em;
  border-bottom:1px solid #1e293b;white-space:nowrap}}
table.results th.tc{{text-align:center}}
table.results tbody tr{{border-bottom:1px solid #1e293b}}
table.results tbody tr:hover{{background:#111827}}
table.results td{{padding:8px 10px;color:#cbd5e1;vertical-align:middle}}
table.results td.tc{{text-align:center;white-space:nowrap}}

.cov-pill{{font-size:.7rem;font-weight:700;padding:3px 9px;border-radius:10px;white-space:nowrap}}
.cov-all{{background:#22c55e22;color:#4ade80;border:1px solid #22c55e55}}
.cov-partial{{background:#fbbf2422;color:#fbbf24;border:1px solid #fbbf2455}}
.cov-zero{{background:#47556922;color:#94a3b8;border:1px solid #47556955}}

.numchips{{display:flex;flex-wrap:wrap;gap:8px}}
.numchip{{display:flex;flex-direction:column;align-items:center;gap:3px}}
.idxrow{{display:flex;gap:3px}}
.idx-badge{{font-size:.6rem;font-weight:700;padding:2px 5px;border-radius:5px;white-space:nowrap}}
.idx-badge.early{{background:#22c55e22;color:#4ade80;border:1px solid #22c55e44}}
.idx-badge.late{{background:#fbbf2422;color:#fbbf24;border:1px solid #fbbf2444}}
.idx-badge.absent{{background:#47556922;color:#64748b;border:1px solid #47556944}}

.legend{{display:flex;gap:16px;flex-wrap:wrap;font-size:.75rem;color:#94a3b8;margin-top:10px}}
.legend span.dot{{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:5px;vertical-align:middle}}

.footer{{margin-top:28px;font-size:.78rem;color:#475569;padding-bottom:20px;line-height:1.6}}
</style>
</head>
<body>

<script src="/site-nav.js"></script>
<div class="wrap">
  <h1>🧪 Base Pool Construction Review — Last {n_draws} Draws (#{draw_lo}–{draw_hi})</h1>
  <p class="subtitle">Narrower than the full 5-pass elimination backtest — just the Base-pool-construction stage, with generation-order detail for both inputs.</p>

  <div class="note">
    <p>Base = <strong style="color:#e2e8f0">Modular Cycle K={k_mc}</strong> (walk-forward, native K={k_mc_native} padded to {k_mc}
    via cross-method-consensus <code>topKNums()</code>) &cap; <strong style="color:#e2e8f0">xoshiro K={k_xo} seed #{seed_xo:,}</strong>
    &mdash; the exact same Base construction used on the /xoshiro_elim_2130.html-style elimination pages, run retroactively against
    each of the last {n_draws} real draws. Every walk-forward-trained component (Modular Cycle's frequency ranking, all 16 methods
    feeding the cross-method-consensus table used to pad Base to K={k_mc}) is trained ONLY on draws strictly before the target draw
    &mdash; no draw ever sees its own future.</p>
    <p><strong style="color:#e2e8f0">Generation order:</strong> for each of a draw's 6 actual numbers, this page shows WHERE (if at
    all) that number fell in each input's own raw pick sequence, before either gets sorted. For xoshiro, that's the order the partial
    Fisher-Yates shuffle finalizes each position. For Modular Cycle, that's the mod-43 cycle's own frequency ranking (native K={k_mc_native}),
    followed by the cross-method-consensus padding numbers added to reach K={k_mc} &mdash; the order the pick was actually built in.
    <span style="color:#4ade80">Green</span> = in the top third of that method's own K (an early/high-confidence pick);
    <span style="color:#fbbf24">amber</span> = present but later; <span style="color:#64748b">grey "—"</span> = never generated by
    that method at all.</p>
    <p><strong style="color:#e2e8f0">This is Base construction only</strong> &mdash; it does NOT run the elimination passes
    (see <a href="/xoshiro_elim_backtest100.html" style="color:#a78bfa">the full 5-pass elimination backtest</a> for that). Base is
    a fixed ~{results[-1]['kBase']}-number pool, so by pure combinatorics only about C(29,6)/C(43,6) &asymp; {theoretical_base_rate:.1f}%
    of possible 6-number combos could ever be fully contained in it &mdash; before any elimination logic runs. Full run took
    {elapsed_seconds:.0f}s ({elapsed_seconds/60:.1f} min) for all {n_draws} draws.</p>
  </div>

  <div class="section">
    <h2>Summary</h2>
    <div class="stats-row">
      <div class="stat-card">
        <div class="lbl">Draws reviewed</div>
        <div class="val">{n_draws}</div>
        <div class="sub">#{draw_lo}–{draw_hi}</div>
      </div>
      <div class="stat-card hit">
        <div class="lbl">All 6 in Base</div>
        <div class="val">{all6}</div>
        <div class="sub">{all6/n_draws*100:.1f}% of draws</div>
      </div>
      <div class="stat-card">
        <div class="lbl">Partial (1–5 in Base)</div>
        <div class="val">{partial}</div>
        <div class="sub">{partial/n_draws*100:.1f}% of draws</div>
      </div>
      <div class="stat-card neverbase">
        <div class="lbl">Zero in Base</div>
        <div class="val">{zero}</div>
        <div class="sub">{zero/n_draws*100:.1f}% of draws</div>
      </div>
    </div>
  </div>

  <div class="section">
    <h2>Base coverage distribution</h2>
    <p class="desc">How many of a draw's 6 actual numbers landed in that draw's own walk-forward Base pool.</p>
    <div class="funnel">{funnel_rows}</div>
  </div>

  <div class="section">
    <h2>Cross-method generation-order findings</h2>
    <p class="desc">Aggregated over all {total_numbers:,} actual-number instances ({n_draws} draws &times; 6 numbers) across the review window.</p>
    <div class="stats-row">
      <div class="stat-card">
        <div class="lbl">Generated by Modular Cycle</div>
        <div class="val">{in_mc:,}</div>
        <div class="sub">{in_mc/total_numbers*100:.1f}% &middot; avg index #{mc_avg_idx:.1f} of {k_mc}</div>
      </div>
      <div class="stat-card">
        <div class="lbl">Generated by xoshiro</div>
        <div class="val">{in_xo:,}</div>
        <div class="sub">{in_xo/total_numbers*100:.1f}% &middot; avg index #{xo_avg_idx:.1f} of {k_xo}</div>
      </div>
      <div class="stat-card">
        <div class="lbl">In both (&rarr; in Base)</div>
        <div class="val">{in_both:,}</div>
        <div class="sub">{in_both/total_numbers*100:.1f}% of all instances</div>
      </div>
      <div class="stat-card">
        <div class="lbl">In neither</div>
        <div class="val">{in_neither:,}</div>
        <div class="sub">{in_neither/total_numbers*100:.1f}% of all instances</div>
      </div>
      <div class="stat-card">
        <div class="lbl">MC only (xoshiro missed it)</div>
        <div class="val">{mc_only:,}</div>
        <div class="sub">{mc_only/total_numbers*100:.1f}% of all instances</div>
      </div>
      <div class="stat-card">
        <div class="lbl">xoshiro only (MC missed it)</div>
        <div class="val">{xo_only:,}</div>
        <div class="sub">{xo_only/total_numbers*100:.1f}% of all instances</div>
      </div>
    </div>
  </div>

  <div class="section">
    <h2>Per-draw results</h2>
    <p class="desc">Newest draw first. Each actual number shows two generation-order badges: MC = position within the Modular
    Cycle K={k_mc} pick's own build order, XO = position within the xoshiro K={k_xo} pick's own Fisher-Yates finalization order.</p>
    <div class="legend">
      <span><span class="dot" style="background:#4ade80"></span>Early (top third of that method's K)</span>
      <span><span class="dot" style="background:#fbbf24"></span>Present, later in the order</span>
      <span><span class="dot" style="background:#64748b"></span>Never generated by that method</span>
    </div>
    <div class="controls" style="margin-top:14px">
      <select id="filterSel" onchange="applyFilter()">
        <option value="all">Show: All {n_draws} draws</option>
        <option value="6">Show: All 6 in Base only</option>
        <option value="partial">Show: Partial (1–5) only</option>
        <option value="0">Show: Zero in Base only</option>
      </select>
      <span id="filterCount" class="desc" style="margin:0"></span>
    </div>
    <div class="tbl-wrap">
      <table class="results" id="resultsTable">
        <thead><tr>
          <th class="tc">Draw</th><th class="tc">Date</th><th>Actual combo (generation-order index per number)</th>
          <th class="tc">Base coverage</th><th class="tc">|Base|</th>
        </tr></thead>
        <tbody id="resultsBody">{rows_html}</tbody>
      </table>
    </div>
  </div>

  <p class="footer">
    Same verified xoshiro256** implementation and mod-43 cycle logic used throughout this site. Modular Cycle and all 16
    cross-method-consensus-feeding methods are walk-forward trained strictly on draws before each target &mdash; no draw ever
    influences its own prediction.<br>
    Formula-based only · Not financial advice · Loto 6 is random.
  </p>
</div>

<script>
function applyFilter() {{
  const sel = document.getElementById('filterSel').value;
  const rows = document.querySelectorAll('#resultsBody tr');
  let shown = 0;
  rows.forEach((tr) => {{
    const overlap = tr.getAttribute('data-overlap');
    let show = true;
    if (sel === '6') show = overlap === '6';
    else if (sel === '0') show = overlap === '0';
    else if (sel === 'partial') show = overlap !== '6' && overlap !== '0';
    tr.style.display = show ? '' : 'none';
    if (show) shown++;
  }});
  document.getElementById('filterCount').textContent = 'Showing ' + shown + ' of ' + rows.length;
}}
applyFilter();
</script>
</body>
</html>"""

with open(HTML_OUT, 'w', encoding='utf-8') as f:
    f.write(page)
print(f"Wrote {HTML_OUT} ({len(page)//1024} KB)")
