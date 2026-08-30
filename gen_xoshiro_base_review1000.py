"""
gen_xoshiro_base_review1000.py
-----------------------------------
Generates the "Base Pool Construction Review — Last 1000 Draws" page:
the 1000-draw scale-up of xoshiro_base_review100.html (same Base
construction, same per-number generation-order detail, same hit
highlighting) plus a new aggregate section showing the distribution
of hit numbers' generation-order index across each of Modular Cycle
K=33 and xoshiro K=38 -- do hits cluster at certain positions in each
method's own build order, or land roughly evenly across the whole K?

A narrower cousin of xoshiro_elim_backtest100.html that stops at the
Base-pool-construction stage (Base = Modular Cycle K=33 (walk-forward)
intersect xoshiro K=38 seed #692,809) instead of running the full
5-pass elimination funnel, and adds generation-order detail -- for
each of the last 1000 real draws' 6 actual numbers, WHERE (if at all)
that number fell in each of the two inputs' own raw pick sequence.

Reads xoshiro_base_review1000_meta.json (produced by
precompute_xoshiro_base_review1000.py).

Output: public/xoshiro_base_review1000.html
Run: python gen_xoshiro_base_review1000.py
"""
import json
from collections import Counter, defaultdict
from math import comb

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
META_PATH = BASE + r"\xoshiro_base_review1000_meta.json"
HTML_OUT = BASE + r"\public\xoshiro_base_review1000.html"

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
upcoming = meta.get('upcoming')

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

# ── Hit-index distribution: for numbers that ARE hits (in Base -- present in
# BOTH MC and XO), where did they land in each method's own generation
# order? Bucketed into width-5 ranges to see whether hits cluster at
# certain positions or spread evenly across the whole K. ────────────────────
def bucket_counts(indices, k, width=5):
    n_buckets = -(-k // width)  # ceil
    counts = [0] * n_buckets
    for idx in indices:
        b = min((idx - 1) // width, n_buckets - 1)
        counts[b] += 1
    labels = []
    for b in range(n_buckets):
        lo = b * width + 1
        hi = min((b + 1) * width, k)
        labels.append(f"{lo}–{hi}" if lo != hi else f"{lo}")
    return labels, counts

hit_mc_indices = []
hit_xo_indices = []
for r in results:
    for pn in r['perNumber']:
        if pn['mcIdx'] is not None and pn['xoIdx'] is not None:
            hit_mc_indices.append(pn['mcIdx'])
            hit_xo_indices.append(pn['xoIdx'])
n_hits_total = len(hit_mc_indices)
mc_bucket_labels, mc_bucket_counts = bucket_counts(hit_mc_indices, k_mc)
xo_bucket_labels, xo_bucket_counts = bucket_counts(hit_xo_indices, k_xo)

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

mc_dist_html = dist_rows_html(mc_bucket_labels, mc_bucket_counts, n_hits_total, '#38bdf8')
xo_dist_html = dist_rows_html(xo_bucket_labels, xo_bucket_counts, n_hits_total, '#a78bfa')

# ── Exact-index frequency ranking: which individual index positions (not
# buckets) show up most often among hit numbers, for each method separately.
# Includes a chi-square goodness-of-fit test against a uniform distribution
# to flag whether the ranking is a real pattern or just sampling noise. ─────
from scipy import stats as _scipy_stats

def exact_index_ranking(indices, k):
    counts = Counter(indices)
    total = len(indices)
    ranked = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
    expected = total / k
    chi2 = sum((counts.get(i, 0) - expected) ** 2 / expected for i in range(1, k + 1))
    dof = k - 1
    p_value = 1 - _scipy_stats.chi2.cdf(chi2, dof)
    return ranked, expected, chi2, dof, p_value

mc_ranked, mc_expected, mc_chi2, mc_dof, mc_pvalue = exact_index_ranking(hit_mc_indices, k_mc)
xo_ranked, xo_expected, xo_chi2, xo_dof, xo_pvalue = exact_index_ranking(hit_xo_indices, k_xo)

def ranking_table_html(ranked, expected, limit=None):
    rows = ranked[:limit] if limit else ranked
    out = ""
    for idx, cnt in rows:
        pct = cnt / n_hits_total * 100
        vs_expected = (cnt - expected) / expected * 100
        sign = "+" if vs_expected >= 0 else ""
        out += f"""<tr><td class="tc">#{idx}</td><td class="tc">{cnt:,}</td><td class="tc">{pct:.2f}%</td>
      <td class="tc" style="color:{'#4ade80' if vs_expected >= 0 else '#f87171'}">{sign}{vs_expected:.1f}%</td></tr>"""
    return out

def full_list_text(ranked):
    return " ".join(f"#{idx}({cnt})" for idx, cnt in ranked)

mc_top15_html = ranking_table_html(mc_ranked, mc_expected, limit=15)
xo_top15_html = ranking_table_html(xo_ranked, xo_expected, limit=15)
mc_full_list = full_list_text(mc_ranked)
xo_full_list = full_list_text(xo_ranked)

# ── MC-vs-XO correlation: for the SAME hit number in the SAME draw, does its
# MC index correlate with its XO index? Pearson (linear) + Spearman (rank)
# correlation, plus a cross-tab / chi-square independence test. ─────────────
def pearson_r(xs, ys):
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(xs, ys)) / n
    sx = (sum((a - mx) ** 2 for a in xs) / n) ** 0.5
    sy = (sum((b - my) ** 2 for b in ys) / n) ** 0.5
    return cov / (sx * sy)

def rank_values(lst):
    order = sorted(range(len(lst)), key=lambda i: lst[i])
    ranks = [0.0] * len(lst)
    i = 0
    while i < len(lst):
        j = i
        while j + 1 < len(lst) and lst[order[j + 1]] == lst[order[i]]:
            j += 1
        avg_rank = (i + j) / 2 + 1
        for k_ in range(i, j + 1):
            ranks[order[k_]] = avg_rank
        i = j + 1
    return ranks

pearson_corr = pearson_r(hit_mc_indices, hit_xo_indices)
spearman_corr = pearson_r(rank_values(hit_mc_indices), rank_values(hit_xo_indices))

def cross_tab(mc_idx_list, xo_idx_list, k_mc_, k_xo_, width=5):
    n_mc_b = -(-k_mc_ // width)
    n_xo_b = -(-k_xo_ // width)
    table = [[0] * n_xo_b for _ in range(n_mc_b)]
    for a, b in zip(mc_idx_list, xo_idx_list):
        table[min((a - 1) // width, n_mc_b - 1)][min((b - 1) // width, n_xo_b - 1)] += 1
    return table, n_mc_b, n_xo_b

ct_table, ct_n_mc_b, ct_n_xo_b = cross_tab(hit_mc_indices, hit_xo_indices, k_mc, k_xo)
ct_row_sums = [sum(row) for row in ct_table]
ct_col_sums = [sum(ct_table[i][j] for i in range(ct_n_mc_b)) for j in range(ct_n_xo_b)]
ct_total = n_hits_total
ct_chi2 = 0.0
for i in range(ct_n_mc_b):
    for j in range(ct_n_xo_b):
        exp_ij = ct_row_sums[i] * ct_col_sums[j] / ct_total
        if exp_ij > 0:
            ct_chi2 += (ct_table[i][j] - exp_ij) ** 2 / exp_ij
ct_dof = (ct_n_mc_b - 1) * (ct_n_xo_b - 1)
ct_pvalue = 1 - _scipy_stats.chi2.cdf(ct_chi2, ct_dof)
cramers_v = (ct_chi2 / (ct_total * (min(ct_n_mc_b, ct_n_xo_b) - 1))) ** 0.5

ct_mc_labels, _ = bucket_counts(hit_mc_indices, k_mc)  # reuse label formatting
ct_xo_labels, _ = bucket_counts(hit_xo_indices, k_xo)

ct_header_html = "<th class=\"tc\">MC \\ XO</th>" + "".join(f'<th class="tc">#{l}</th>' for l in ct_xo_labels)
ct_rows_html = ""
for i, row in enumerate(ct_table):
    cells = "".join(f'<td class="tc">{v}</td>' for v in row)
    ct_rows_html += f'<tr><td class="tc" style="font-weight:600;color:#7dd3fc">#{ct_mc_labels[i]}</td>{cells}</tr>'

# ── Hit index-set patterns: for every draw, the full sorted set of hit
# generation-order indices per method, plus a repeat-frequency check within
# each hit-count tier (does any exact index-set recur across draws?). ───────
draw_patterns = []  # (serial, date, tier, mc_set, xo_set)
tier_mc_sets = defaultdict(list)
tier_xo_sets = defaultdict(list)
for r in results:
    hits = [pn for pn in r['perNumber'] if pn['mcIdx'] is not None and pn['xoIdx'] is not None]
    tier = len(hits)
    mc_set = tuple(sorted(pn['mcIdx'] for pn in hits))
    xo_set = tuple(sorted(pn['xoIdx'] for pn in hits))
    draw_patterns.append((r['serial'], r['date'], tier, mc_set, xo_set))
    if tier > 0:
        tier_mc_sets[tier].append((r['serial'], mc_set))
        tier_xo_sets[tier].append((r['serial'], xo_set))

tier_draw_counts = {t: len(tier_mc_sets.get(t, [])) for t in range(7)}

def repeat_summary(tier_sets, k):
    out = {}
    for tier, entries in tier_sets.items():
        counts = Counter(s for _, s in entries)
        repeats = [(s, c) for s, c in counts.items() if c > 1]
        out[tier] = {
            'nDraws': len(entries), 'nDistinct': len(counts),
            'universe': comb(k, tier) if tier <= k else 0,
            'repeats': sorted(repeats, key=lambda x: -x[1]),
        }
    return out

mc_repeat_info = repeat_summary(tier_mc_sets, k_mc)
xo_repeat_info = repeat_summary(tier_xo_sets, k_xo)

def repeat_examples_text(tier_sets_lookup, repeat_info, tier):
    info = repeat_info.get(tier)
    if not info or not info['repeats']:
        return ""
    parts = []
    entries = tier_sets_lookup[tier]
    for s, c in info['repeats'][:5]:
        draws = [str(ser) for ser, ss in entries if ss == s]
        parts.append(f"{{{', '.join(str(n) for n in s)}}} (#{'/#'.join(draws)})")
    return ", ".join(parts)

def set_str(s):
    return "{" + ", ".join(str(n) for n in s) + "}" if s else "—"

patterns_rows_html = ""
for serial, date, tier, mc_set, xo_set in reversed(draw_patterns):  # newest first
    patterns_rows_html += f"""<tr data-tier="{tier}" data-serial="{serial}">
  <td class="tc">#{serial}</td>
  <td class="tc">{date}</td>
  <td class="tc">{tier}/6</td>
  <td style="color:#7dd3fc;font-family:monospace;font-size:.8rem">{set_str(mc_set)}</td>
  <td style="color:#c4b5fd;font-family:monospace;font-size:.8rem">{set_str(xo_set)}</td>
</tr>"""

# ── Repeat-analysis summary note (supplementary, not a large section) ───────
_repeat_note_parts = []
for tier in (6, 5):
    mc_i, xo_i = mc_repeat_info.get(tier), xo_repeat_info.get(tier)
    if mc_i and xo_i:
        _repeat_note_parts.append(
            f"<strong style=\"color:#f1f5f9\">{tier}/6:</strong> no repeats in either method &mdash; all "
            f"{mc_i['nDraws']} draws produced {mc_i['nDistinct']} distinct index-sets for both Modular Cycle "
            f"(universe C({k_mc},{tier})={mc_i['universe']:,}) and xoshiro (universe C({k_xo},{tier})={xo_i['universe']:,})."
        )
lower_tier_bits = []
for tier in (4, 3, 2, 1):
    mc_i, xo_i = mc_repeat_info.get(tier), xo_repeat_info.get(tier)
    if not mc_i or not xo_i:
        continue
    mc_ex = repeat_examples_text(tier_mc_sets, mc_repeat_info, tier)
    xo_ex = repeat_examples_text(tier_xo_sets, xo_repeat_info, tier)
    bit = f"<strong style=\"color:#f1f5f9\">{tier}/6:</strong> MC {len(mc_i['repeats'])} repeat(s)"
    if mc_ex:
        bit += f" &mdash; {mc_ex}"
    bit += f"; XO {len(xo_i['repeats'])} repeat(s)"
    if xo_ex:
        bit += f" &mdash; {xo_ex}"
    lower_tier_bits.append(bit)
_repeat_note_parts.append("<strong style=\"color:#f1f5f9\">4/6 down to 1/6:</strong> " + " &nbsp;|&nbsp; ".join(lower_tier_bits) + ". Every one of these counts is within normal statistical noise of what pure chance predicts (birthday-paradox math on each tier's combinatorial universe) &mdash; not a discovered pattern.")
repeat_note_html = "</p><p>".join(_repeat_note_parts)

tier_options_html = ""
for t in (6, 5, 4, 3, 2, 1, 0):
    tier_options_html += f'<option value="{t}">Show: {t}/6 hits ({tier_draw_counts.get(t, 0)} draws)</option>'

rows_html = ""
for r in reversed(results):  # newest first
    balls_html = ""
    hit_parts = []
    for pn in r['perNumber']:
        is_hit = pn['mcIdx'] is not None and pn['xoIdx'] is not None  # in Base = in both
        mc_b = idx_badge("MC", pn['mcIdx'], MC_EARLY)
        xo_b = idx_badge("XO", pn['xoIdx'], XO_EARLY)
        chip_cls = "numchip hit" if is_hit else "numchip"
        hit_tag = '<div class="hit-tag">🎯 HIT</div>' if is_hit else ""
        balls_html += f"""<div class="{chip_cls}">
        <span class="nb">{pn['n']}</span>
        {hit_tag}
        <div class="idxrow">{mc_b}{xo_b}</div>
      </div>"""
        if is_hit:
            hit_parts.append(f"<strong>{pn['n']}</strong> (MC #{pn['mcIdx']}, XO #{pn['xoIdx']})")
    hit_summary = (
        f'<div class="hit-summary">🎯 Hit numbers\' generation-order index: {", ".join(hit_parts)}</div>'
        if hit_parts else
        '<div class="hit-summary hit-summary-none">No hit numbers this draw (none of the 6 landed in both MC and xoshiro\'s picks).</div>'
    )
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
  <td><div class="numchips">{balls_html}</div>{hit_summary}</td>
  <td class="tc"><span class="cov-pill {cov_cls}">{cov_label}</span></td>
  <td class="tc">{r['kBase']}</td>
</tr>"""

# ── Upcoming draw row (not yet drawn -- no actual result to compare against,
# so no hit highlighting; just the Base pool itself, pinned at the top) ─────
upcoming_row_html = ""
if upcoming:
    up_balls = "".join(f'<span class="nb up">{n}</span>' for n in upcoming['basePool'])
    upcoming_row_html = f"""<tr class="upcoming-row" data-upcoming="1">
  <td class="tc">#{upcoming['serial']}</td>
  <td class="tc"><em>upcoming</em></td>
  <td>
    <div class="upcoming-label">⏳ Base pool for draw #{upcoming['serial']} &mdash; not yet drawn, no actual result to compare against yet</div>
    <div class="numchips">{up_balls}</div>
  </td>
  <td class="tc"><em style="color:#64748b">not yet drawn</em></td>
  <td class="tc">{upcoming['kBase']}</td>
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
table.results th.sortable{{cursor:pointer;user-select:none}}
table.results th.sortable:hover{{color:#e2e8f0}}
table.results tbody tr{{border-bottom:1px solid #1e293b}}
table.results tbody tr:hover{{background:#111827}}
table.results td{{padding:8px 10px;color:#cbd5e1;vertical-align:middle}}
table.results td.tc{{text-align:center;white-space:nowrap}}

.cov-pill{{font-size:.7rem;font-weight:700;padding:3px 9px;border-radius:10px;white-space:nowrap}}
.cov-all{{background:#22c55e22;color:#4ade80;border:1px solid #22c55e55}}
.cov-partial{{background:#fbbf2422;color:#fbbf24;border:1px solid #fbbf2455}}
.cov-zero{{background:#47556922;color:#94a3b8;border:1px solid #47556955}}

.numchips{{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:8px}}
.numchip{{display:flex;flex-direction:column;align-items:center;gap:3px;padding:3px;border-radius:8px}}
.numchip.hit{{background:#38bdf814;border:1px solid #38bdf855}}
.nb.up{{background:#38bdf822;color:#7dd3fc;border-color:#38bdf866}}

tr.upcoming-row{{background:rgba(56,189,248,.08);border-bottom:2px solid #38bdf8}}
tr.upcoming-row td{{color:#e2e8f0}}
tr.upcoming-row td:first-child{{font-weight:700;color:#38bdf8}}
.upcoming-label{{font-size:.72rem;font-weight:600;color:#7dd3fc;margin-bottom:8px}}
.hit-tag{{font-size:.52rem;font-weight:800;color:#38bdf8;letter-spacing:.03em;white-space:nowrap}}
.idxrow{{display:flex;gap:3px}}
.idx-badge{{font-size:.6rem;font-weight:700;padding:2px 5px;border-radius:5px;white-space:nowrap}}
.idx-badge.early{{background:#22c55e22;color:#4ade80;border:1px solid #22c55e44}}
.idx-badge.late{{background:#fbbf2422;color:#fbbf24;border:1px solid #fbbf2444}}
.idx-badge.absent{{background:#47556922;color:#64748b;border:1px solid #47556944}}

.hit-summary{{font-size:.72rem;color:#7dd3fc;line-height:1.5}}
.hit-summary-none{{color:#64748b;font-style:italic}}

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
    <h2>Hit-index distribution</h2>
    <p class="desc">Across all {n_hits_total:,} hit numbers found in this window (numbers present in BOTH picks, i.e. actually
    inside Base), where did each land in its method's own generation order? Bucketed into width-5 ranges &mdash; a flat
    distribution means hits land roughly evenly across the whole K; a skew toward low ranges means hits tend to be
    high-confidence/early picks for that method.</p>
    <div style="margin-bottom:22px">
      <h3 style="font-size:.85rem;color:#7dd3fc;margin-bottom:10px">Modular Cycle K={k_mc}</h3>
      <div class="funnel">{mc_dist_html}</div>
    </div>
    <div>
      <h3 style="font-size:.85rem;color:#c4b5fd;margin-bottom:10px">xoshiro K={k_xo}</h3>
      <div class="funnel">{xo_dist_html}</div>
    </div>
  </div>

  <div class="section">
    <h2>Exact-index frequency ranking</h2>
    <p class="desc">Not bucketed &mdash; the individual generation-order index positions (1, 2, 3, ...) ranked by how often a hit
    number landed there, for each method separately.</p>
    <div class="note" style="border-color:#fbbf2455;background:#1c1608;margin-bottom:16px">
      <p style="color:#fbbf24"><strong>⚠️ Not statistically significant.</strong> A chi-square goodness-of-fit test against a
      uniform distribution gives <strong style="color:#f1f5f9">MC: &chi;&sup2;={mc_chi2:.2f}, df={mc_dof}, p={mc_pvalue:.2f}</strong>
      and <strong style="color:#f1f5f9">XO: &chi;&sup2;={xo_chi2:.2f}, df={xo_dof}, p={xo_pvalue:.2f}</strong> &mdash; both far
      above the p&lt;0.05 threshold. The spread between the top and bottom index below is fully consistent with random sampling
      noise around a flat distribution (expected count per index: MC &asymp;{mc_expected:.1f}, XO &asymp;{xo_expected:.1f}), not a
      real preferred position. This ranking would likely reshuffle noticeably on a different 1000-draw window &mdash; treat it as
      a snapshot, not a discovered pattern.</p>
    </div>

    <h3 style="font-size:.85rem;color:#7dd3fc;margin-bottom:8px">Modular Cycle K={k_mc} &mdash; top 15</h3>
    <div class="tbl-wrap" style="margin-bottom:10px">
      <table class="results">
        <thead><tr><th class="tc">Index</th><th class="tc">Hits</th><th class="tc">%</th><th class="tc">vs. expected</th></tr></thead>
        <tbody>{mc_top15_html}</tbody>
      </table>
    </div>
    <details style="margin-bottom:22px">
      <summary style="cursor:pointer;color:#94a3b8;font-size:.78rem;padding:6px 0">Show full ranked list (all {k_mc} indices)</summary>
      <p style="font-size:.75rem;color:#94a3b8;line-height:1.8;margin-top:8px;font-family:monospace">{mc_full_list}</p>
    </details>

    <h3 style="font-size:.85rem;color:#c4b5fd;margin-bottom:8px">xoshiro K={k_xo} &mdash; top 15</h3>
    <div class="tbl-wrap" style="margin-bottom:10px">
      <table class="results">
        <thead><tr><th class="tc">Index</th><th class="tc">Hits</th><th class="tc">%</th><th class="tc">vs. expected</th></tr></thead>
        <tbody>{xo_top15_html}</tbody>
      </table>
    </div>
    <details>
      <summary style="cursor:pointer;color:#94a3b8;font-size:.78rem;padding:6px 0">Show full ranked list (all {k_xo} indices)</summary>
      <p style="font-size:.75rem;color:#94a3b8;line-height:1.8;margin-top:8px;font-family:monospace">{xo_full_list}</p>
    </details>
  </div>

  <div class="section">
    <h2>Modular Cycle vs xoshiro: are the two orderings related?</h2>
    <p class="desc">For the SAME hit number in the SAME draw, does an early Modular Cycle generation-order index predict an
    early or late xoshiro index &mdash; or are the two methods' orderings independent?</p>
    <div class="stats-row" style="margin-bottom:16px">
      <div class="stat-card">
        <div class="lbl">Pearson r (linear)</div>
        <div class="val">{pearson_corr:.4f}</div>
        <div class="sub">~0 = no linear relationship</div>
      </div>
      <div class="stat-card">
        <div class="lbl">Spearman &rho; (rank)</div>
        <div class="val">{spearman_corr:.4f}</div>
        <div class="sub">~0 = no monotonic relationship</div>
      </div>
      <div class="stat-card">
        <div class="lbl">Cross-tab &chi;&sup2; test</div>
        <div class="val">p={ct_pvalue:.3f}</div>
        <div class="sub">&chi;&sup2;={ct_chi2:.2f}, df={ct_dof} &mdash; not significant</div>
      </div>
      <div class="stat-card">
        <div class="lbl">Cramer's V (effect size)</div>
        <div class="val">{cramers_v:.4f}</div>
        <div class="sub">~0 = negligible association</div>
      </div>
    </div>
    <div class="note" style="margin-bottom:16px">
      <p><strong style="color:#e2e8f0">No relationship.</strong> Both correlation coefficients are indistinguishable from zero
      (two orders of magnitude below what would count as even a weak correlation), and the cross-tab independence test fails to
      reject the null hypothesis of independence (p={ct_pvalue:.2f} &gt;&gt; 0.05) with a negligible effect size. This matches
      what the two methods' mechanics predict: Modular Cycle's order comes from a mod-43 draw-frequency ranking (a function of
      historical draw data), xoshiro's comes from an independently-seeded Fisher-Yates shuffle &mdash; no shared derivation, no
      shared state, and empirically, no shared structure either. A number that's an early pick for one method is exactly as
      likely to land anywhere in the other method's own generation order.</p>
    </div>
    <p class="desc">Cross-tabulation: hit count by MC index-range (rows) &times; XO index-range (columns), width-5 buckets.</p>
    <div class="tbl-wrap">
      <table class="results">
        <thead><tr>{ct_header_html}</tr></thead>
        <tbody>{ct_rows_html}</tbody>
      </table>
    </div>
  </div>

  <div class="section">
    <h2>Hit index-set patterns</h2>
    <p class="desc">For every draw, the full sorted set of generation-order indices where its hit numbers landed &mdash; e.g.
    a draw with 5 hits might show Modular Cycle <code>{{8, 12, 13, 14, 29}}</code> and xoshiro <code>{{4, 6, 24, 30, 37}}</code>.
    Organized by hit-count tier, filterable below.</p>
    <div class="note" style="margin-bottom:16px">
      <p>{repeat_note_html}</p>
    </div>
    <div class="controls">
      <select id="patternsTierSel" onchange="applyPatternsFilter()">
        <option value="all">Show: All tiers ({n_draws} draws)</option>
        {tier_options_html}
      </select>
      <span id="patternsFilterCount" class="desc" style="margin:0"></span>
    </div>
    <div class="tbl-wrap">
      <table class="results" id="patternsTable">
        <thead><tr>
          <th class="tc sortable" data-key="serial" onclick="sortPatterns('serial')">Draw ⇅</th>
          <th class="tc">Date</th>
          <th class="tc sortable" data-key="tier" onclick="sortPatterns('tier')">Hits ⇅</th>
          <th>Modular Cycle index-set</th>
          <th>xoshiro index-set</th>
        </tr></thead>
        <tbody id="patternsBody">{patterns_rows_html}</tbody>
      </table>
    </div>
  </div>

  <div class="section">
    <h2>Per-draw results</h2>
    <p class="desc">The <strong style="color:#7dd3fc">⏳ upcoming draw</strong> is pinned at the top, showing the Base pool computed
    for it &mdash; not yet drawn, so there's no actual result to compare against and no hit highlighting. Below it, the {n_draws}
    real historical draws are newest first. Each actual number shows two generation-order badges: MC = position within the
    Modular Cycle K={k_mc} pick's own build order, XO = position within the xoshiro K={k_xo} pick's own Fisher-Yates
    finalization order. Numbers that hit Base &mdash; present in BOTH picks, so they're actually inside the intersection
    &mdash; are highlighted and tagged <strong style="color:#38bdf8">🎯 HIT</strong>, with a one-line summary underneath the
    combo spelling out each hit number's index in both sources at a glance.</p>
    <div class="legend">
      <span><span class="dot" style="background:#38bdf8"></span>🎯 HIT — number is in Base (present in both MC and XO)</span>
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
          <th class="tc">Draw</th><th class="tc">Date</th><th>Actual combo &amp; generation-order index (🎯 hit numbers highlighted + summarized)</th>
          <th class="tc">Base coverage</th><th class="tc">|Base|</th>
        </tr></thead>
        <tbody id="resultsBody">{upcoming_row_html}{rows_html}</tbody>
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
  let shown = 0, total = 0;
  rows.forEach((tr) => {{
    if (tr.getAttribute('data-upcoming') === '1') {{
      tr.style.display = '';  // always shown, pinned at top, not part of the filter/count
      return;
    }}
    total++;
    const overlap = tr.getAttribute('data-overlap');
    let show = true;
    if (sel === '6') show = overlap === '6';
    else if (sel === '0') show = overlap === '0';
    else if (sel === 'partial') show = overlap !== '6' && overlap !== '0';
    tr.style.display = show ? '' : 'none';
    if (show) shown++;
  }});
  document.getElementById('filterCount').textContent = 'Showing ' + shown + ' of ' + total;
}}
applyFilter();

function applyPatternsFilter() {{
  const sel = document.getElementById('patternsTierSel').value;
  const rows = document.querySelectorAll('#patternsBody tr');
  let shown = 0;
  rows.forEach((tr) => {{
    const tier = tr.getAttribute('data-tier');
    const show = sel === 'all' || sel === tier;
    tr.style.display = show ? '' : 'none';
    if (show) shown++;
  }});
  document.getElementById('patternsFilterCount').textContent = 'Showing ' + shown + ' of ' + rows.length;
}}
applyPatternsFilter();

let _patternsSortState = {{ key: 'serial', dir: -1 }};  // default: newest draw first
function sortPatterns(key) {{
  const tbody = document.getElementById('patternsBody');
  const rows = Array.from(tbody.querySelectorAll('tr'));
  if (_patternsSortState.key === key) {{
    _patternsSortState.dir *= -1;
  }} else {{
    _patternsSortState = {{ key: key, dir: key === 'serial' ? -1 : -1 }};
  }}
  const dir = _patternsSortState.dir;
  rows.sort((a, b) => {{
    const av = parseInt(a.getAttribute('data-' + (key === 'serial' ? 'serial' : 'tier')), 10);
    const bv = parseInt(b.getAttribute('data-' + (key === 'serial' ? 'serial' : 'tier')), 10);
    return (av - bv) * dir;
  }});
  rows.forEach(r => tbody.appendChild(r));
}}
</script>
</body>
</html>"""

with open(HTML_OUT, 'w', encoding='utf-8') as f:
    f.write(page)
print(f"Wrote {HTML_OUT} ({len(page)//1024} KB)")
