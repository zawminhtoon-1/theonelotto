"""
gen_xoshiro_elim_backtest100.py
-----------------------------------
Generates the "Full Elimination Backtest (Last 100 Draws)" page,
applying /xoshiro_elim_2130.html's complete 5-pass methodology (Base =
Modular Cycle K=33 (walk-forward) intersect xoshiro K=38 seed
#692,809; Pass1 = 16 methods K=19; Pass2 = top 1000 worst-coverage
seed_hit_random_k17 seeds K=15; Pass3 = xoshiro K=21 seeds 0,1,2;
Pass4 = historical repeat filter; Pass5 = Worst Combo Anti-Pick K=15)
RETROACTIVELY to each of the last 100 real draws, with strict
walk-forward training (no draw ever sees its own future, including
Pass 4's historical set, which is restricted to draws strictly before
the target -- a genuine blind backtest).

Reads xoshiro_elim_backtest100_meta.json (produced by
precompute_xoshiro_elim_backtest100.py). Small enough (100 draws'
summary stats, no full combo lists) to embed directly -- no separate
fetched asset needed.

Output: public/xoshiro_elim_backtest100.html
Run: python gen_xoshiro_elim_backtest100.py
"""
import json
from math import comb

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
META_PATH = BASE + r"\xoshiro_elim_backtest100_meta.json"
HTML_OUT = BASE + r"\public\xoshiro_elim_backtest100.html"

with open(META_PATH, encoding='utf-8') as f:
    meta = json.load(f)

n_draws = meta['nDraws']
draw_lo, draw_hi = meta['drawRange']
n_worst_seeds = meta['nWorstSeeds']
k_random = meta['kRandom']
k_pass3 = meta['kPass3']
pass3_seeds = meta['pass3Seeds']
outcomes = meta['outcomeSummary']
results = meta['results']
elapsed_seconds = meta['elapsedSeconds']

never_in_base = outcomes.get('never_in_base', 0)
elim1 = outcomes.get('eliminated_pass1', 0)
elim2 = outcomes.get('eliminated_pass2', 0)
elim3 = outcomes.get('eliminated_pass3', 0)
elim4 = outcomes.get('eliminated_pass4', 0)
elim5 = outcomes.get('eliminated_pass5', 0)
survived = outcomes.get('survived', 0)

in_base_count = n_draws - never_in_base
theoretical_base_rate = comb(28, 6) / comb(43, 6) * 100  # approx, K_BASE varies slightly per draw but hovers around 28

OUTCOME_LABELS = {
    'never_in_base': 'Never in Base',
    'eliminated_pass1': 'Eliminated — Pass 1',
    'eliminated_pass2': 'Eliminated — Pass 2',
    'eliminated_pass3': 'Eliminated — Pass 3',
    'eliminated_pass4': 'Eliminated — Pass 4',
    'eliminated_pass5': 'Eliminated — Pass 5',
    'survived': 'Survived all 5 passes (HIT)',
}
OUTCOME_COLORS = {
    'never_in_base': '#475569',
    'eliminated_pass1': '#f87171',
    'eliminated_pass2': '#fb923c',
    'eliminated_pass3': '#fbbf24',
    'eliminated_pass4': '#a3e635',
    'eliminated_pass5': '#38bdf8',
    'survived': '#22c55e',
}

def fmt_n(v):
    return f"{v:,}" if v is not None else "—"

rows_html = ""
for r in reversed(results):  # newest first
    outcome = r['outcome']
    color = OUTCOME_COLORS.get(outcome, '#94a3b8')
    label = OUTCOME_LABELS.get(outcome, outcome)
    balls = "".join(f'<span class="nb">{n}</span>' for n in r['actual'])
    base_status = f"{r['baseOverlap']}/6 in Base" + (" ✓" if r['inBase'] else "")
    rows_html += f"""<tr>
  <td class="tc">#{r['serial']}</td>
  <td class="tc">{r['date']}</td>
  <td><div class="balls">{balls}</div></td>
  <td class="tc">{base_status}</td>
  <td><span class="outcome-pill" style="background:{color}22;color:{color};border:1px solid {color}55">{label}</span></td>
  <td class="tr">{fmt_n(r.get('after1'))}</td>
  <td class="tr">{fmt_n(r.get('after2'))}</td>
  <td class="tr">{fmt_n(r.get('after3'))}</td>
  <td class="tr">{fmt_n(r.get('after4'))}</td>
  <td class="tr">{fmt_n(r.get('after5'))}</td>
</tr>"""

page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Full Elimination Backtest — Last {n_draws} Draws</title>
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

.balls{{display:flex;flex-wrap:wrap;gap:3px}}
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
.funnel-lbl{{width:190px;color:#94a3b8;flex-shrink:0}}
.funnel-bar-wrap{{flex:1;background:#0a0f1e;border-radius:6px;overflow:hidden;height:22px;border:1px solid #1e293b}}
.funnel-bar{{height:100%;border-radius:6px}}
.funnel-val{{width:50px;text-align:right;color:#f1f5f9;font-weight:600;flex-shrink:0}}

.controls{{display:flex;gap:10px;align-items:center;margin-bottom:14px;flex-wrap:wrap}}
.controls select{{background:#0d1526;border:1px solid #334155;border-radius:7px;padding:7px 12px;
  color:#e2e8f0;font-size:.83rem}}

.tbl-wrap{{overflow-x:auto;border-radius:10px;border:1px solid #1e293b}}
table.results{{width:100%;border-collapse:collapse;font-size:.8rem}}
table.results th{{background:#0a0f1e;padding:8px 10px;text-align:right;color:#94a3b8;
  font-weight:600;font-size:.68rem;text-transform:uppercase;letter-spacing:.04em;
  border-bottom:1px solid #1e293b;white-space:nowrap}}
table.results th.tc{{text-align:center}}
table.results tbody tr{{border-bottom:1px solid #1e293b}}
table.results tbody tr:hover{{background:#111827}}
table.results td{{padding:7px 10px;text-align:right;color:#cbd5e1;white-space:nowrap}}
table.results td.tc{{text-align:center}}
.outcome-pill{{font-size:.7rem;font-weight:700;padding:3px 9px;border-radius:10px;white-space:nowrap}}

.footer{{margin-top:28px;font-size:.78rem;color:#475569;padding-bottom:20px;line-height:1.6}}
</style>
</head>
<body>

<script src="/site-nav.js"></script>
<div class="wrap">
  <h1>🎯 Full Elimination Backtest — Last {n_draws} Draws (#{draw_lo}–{draw_hi})</h1>
  <p class="subtitle">The complete 5-pass methodology from /xoshiro_elim_2130.html, run retroactively against each real draw — did the actual winning combo survive?</p>

  <div class="note">
    <p>This applies <a href="/xoshiro_elim_2130.html" style="color:#a78bfa">the #2130 elimination page's full pipeline</a>
    (Base = Modular Cycle K=33 &cap; xoshiro K=38 seed #692,809 &rarr; Pass 1 = 16 methods K=19 &rarr; Pass 2 = top {n_worst_seeds:,}
    worst-coverage <code>seed_hit_random_k17</code> seeds K={k_random} &rarr; Pass 3 = xoshiro K={k_pass3} seeds
    {', '.join(str(s) for s in pass3_seeds)} &rarr; Pass 4 = historical repeat filter &rarr; Pass 5 = Worst Combo Anti-Pick K=15)
    to each of the last {n_draws} real draws, one at a time.</p>
    <p><strong style="color:#e2e8f0">Strict walk-forward, no leakage:</strong> every ML-derived component (Modular Cycle, the 16
    methods, the Worst Combo replica) is trained ONLY on draws strictly before the draw being tested. Pass 4's historical-repeat
    filter is likewise restricted to draws strictly before the target &mdash; NOT including it, unlike the #2129 page's
    convenience inclusion. This is a genuine blind backtest: including the target draw in its own historical set would trivially
    eliminate it via exact match and defeat the point.</p>
    <p><strong style="color:#e2e8f0">The "Never in Base" ceiling:</strong> Base is a fixed ~28-number pool (Modular Cycle &cap;
    xoshiro), so by pure combinatorics only about C(28,6)/C(43,6) &asymp; {theoretical_base_rate:.1f}% of possible 6-number combos
    could ever be contained in it &mdash; before any elimination pass runs. Most real draws are expected to land outside Base
    entirely; this isn't a pipeline failure, it's a structural ceiling on the whole methodology's best-case hit rate.</p>
    <p>Full run took {elapsed_seconds:.0f}s ({elapsed_seconds/60:.1f} min) for all {n_draws} draws. Per-draw remaining-combo lists
    are not stored (100 draws &times; up to ~150K combos each would be far too much data) &mdash; only aggregate counts and each
    draw's elimination outcome.</p>
  </div>

  <div class="section">
    <h2>Summary</h2>
    <div class="stats-row">
      <div class="stat-card">
        <div class="lbl">Draws tested</div>
        <div class="val">{n_draws}</div>
        <div class="sub">#{draw_lo}–{draw_hi}</div>
      </div>
      <div class="stat-card neverbase">
        <div class="lbl">Never in Base</div>
        <div class="val">{never_in_base}</div>
        <div class="sub">{never_in_base/n_draws*100:.1f}% of draws</div>
      </div>
      <div class="stat-card">
        <div class="lbl">Reached elimination passes</div>
        <div class="val">{in_base_count}</div>
        <div class="sub">{in_base_count/n_draws*100:.1f}% of draws</div>
      </div>
      <div class="stat-card">
        <div class="lbl">Eliminated (Pass 1–5)</div>
        <div class="val">{elim1+elim2+elim3+elim4+elim5}</div>
        <div class="sub">of {in_base_count} that reached Base</div>
      </div>
      <div class="stat-card hit">
        <div class="lbl">Survived all 5 (HIT)</div>
        <div class="val">{survived}</div>
        <div class="sub">{survived/n_draws*100:.1f}% of all {n_draws} draws</div>
      </div>
    </div>
  </div>

  <div class="section">
    <h2>Outcome funnel</h2>
    <p class="desc">Where each of the {n_draws} draws' actual winning combo ended up.</p>
    <div class="funnel">
      <div class="funnel-row">
        <div class="funnel-lbl">Never in Base</div>
        <div class="funnel-bar-wrap"><div class="funnel-bar" style="width:{never_in_base/n_draws*100:.1f}%;background:{OUTCOME_COLORS['never_in_base']}"></div></div>
        <div class="funnel-val">{never_in_base}</div>
      </div>
      <div class="funnel-row">
        <div class="funnel-lbl">Eliminated — Pass 1</div>
        <div class="funnel-bar-wrap"><div class="funnel-bar" style="width:{elim1/n_draws*100:.1f}%;background:{OUTCOME_COLORS['eliminated_pass1']}"></div></div>
        <div class="funnel-val">{elim1}</div>
      </div>
      <div class="funnel-row">
        <div class="funnel-lbl">Eliminated — Pass 2</div>
        <div class="funnel-bar-wrap"><div class="funnel-bar" style="width:{elim2/n_draws*100:.1f}%;background:{OUTCOME_COLORS['eliminated_pass2']}"></div></div>
        <div class="funnel-val">{elim2}</div>
      </div>
      <div class="funnel-row">
        <div class="funnel-lbl">Eliminated — Pass 3</div>
        <div class="funnel-bar-wrap"><div class="funnel-bar" style="width:{elim3/n_draws*100:.1f}%;background:{OUTCOME_COLORS['eliminated_pass3']}"></div></div>
        <div class="funnel-val">{elim3}</div>
      </div>
      <div class="funnel-row">
        <div class="funnel-lbl">Eliminated — Pass 4</div>
        <div class="funnel-bar-wrap"><div class="funnel-bar" style="width:{elim4/n_draws*100:.1f}%;background:{OUTCOME_COLORS['eliminated_pass4']}"></div></div>
        <div class="funnel-val">{elim4}</div>
      </div>
      <div class="funnel-row">
        <div class="funnel-lbl">Eliminated — Pass 5</div>
        <div class="funnel-bar-wrap"><div class="funnel-bar" style="width:{elim5/n_draws*100:.1f}%;background:{OUTCOME_COLORS['eliminated_pass5']}"></div></div>
        <div class="funnel-val">{elim5}</div>
      </div>
      <div class="funnel-row">
        <div class="funnel-lbl">Survived (HIT)</div>
        <div class="funnel-bar-wrap"><div class="funnel-bar" style="width:{survived/n_draws*100:.1f}%;background:{OUTCOME_COLORS['survived']}"></div></div>
        <div class="funnel-val">{survived}</div>
      </div>
    </div>
  </div>

  <div class="section">
    <h2>Per-draw results</h2>
    <p class="desc">Newest draw first. "After N" columns show the remaining-combo count after that pass ran for THIS draw's own Base pool — only populated up to the pass that eliminated the combo (or all 5 if it survived).</p>
    <div class="controls">
      <select id="filterSel" onchange="applyFilter()">
        <option value="all">Show: All {n_draws} draws</option>
        <option value="survived">Show: Survived (HIT) only</option>
        <option value="never_in_base">Show: Never in Base only</option>
        <option value="eliminated">Show: Eliminated (any pass) only</option>
      </select>
      <span id="filterCount" class="desc" style="margin:0"></span>
    </div>
    <div class="tbl-wrap">
      <table class="results" id="resultsTable">
        <thead><tr>
          <th class="tc">Draw</th><th class="tc">Date</th><th>Actual combo</th><th class="tc">Base coverage</th>
          <th>Outcome</th><th>After 1</th><th>After 2</th><th>After 3</th><th>After 4</th><th>After 5</th>
        </tr></thead>
        <tbody id="resultsBody">{rows_html}</tbody>
      </table>
    </div>
  </div>

  <p class="footer">
    Same verified xoshiro256** and CPython MT19937 implementations used throughout this site. Modular Cycle, the 16 statistical/ML
    methods, and the Worst Combo replica are all walk-forward trained strictly on draws before each target &mdash; no draw ever
    influences its own prediction.<br>
    Formula-based only · Not financial advice · Loto 6 is random.
  </p>
</div>

<script>
const OUTCOME_DATA = {json.dumps([r['outcome'] for r in results])};
function applyFilter() {{
  const sel = document.getElementById('filterSel').value;
  const rows = document.querySelectorAll('#resultsBody tr');
  const outcomesNewestFirst = [...OUTCOME_DATA].reverse();
  let shown = 0;
  rows.forEach((tr, i) => {{
    const o = outcomesNewestFirst[i];
    let show = true;
    if (sel === 'survived') show = o === 'survived';
    else if (sel === 'never_in_base') show = o === 'never_in_base';
    else if (sel === 'eliminated') show = o && o.startsWith('eliminated');
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
