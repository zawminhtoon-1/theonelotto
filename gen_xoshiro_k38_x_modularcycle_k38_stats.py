"""
gen_xoshiro_k38_x_modularcycle_k38_stats.py
--------------------------------------------------
Generates the "Xoshiro K=38 x Modular Cycle Native K=38 -- Base Pool
Statistics" page: presents the current #2133 intersected pool plus a
full walk-forward backtest of that construction over #1000-2132 (1133
draws, no leakage), with honest statistical framing (none of the four
hit tiers reach conventional significance) and a comparison table
against the other Base constructions tested this session.

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
</script>
</body>
</html>"""

with open(HTML_OUT, 'w', encoding='utf-8') as f:
    f.write(page)
print(f"Wrote {HTML_OUT} ({len(page)//1024} KB)")
