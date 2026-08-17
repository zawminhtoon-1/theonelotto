"""
gen_xoshiro_elim_2129.py
----------------------------
Generates the "Xoshiro K=38/K=33 + 16-Method Elimination" page for draw
#2129 (next upcoming Loto6 draw, #2128 having since become a real,
confirmed draw). Reads xoshiro_elim_2129_meta.json (small: pool picks,
method picks, counts) produced by precompute_xoshiro_elim_2129.py. The
large remaining-combo list lives separately at
public/xoshiro_elim_2129_combos.json (already written by the precompute
script) and is fetched client-side, not inlined -- 1,891,927 combos
would bloat this HTML page itself to an unusable size.

Base (xoshiro K=38) and Pass 1 (xoshiro K=33) are recomputed LIVE in the
browser via the same bit-exact BigInt xoshiro256** port used on every
other xoshiro page -- verifiable, not just displayed. Pass 2 (the 16
statistical/ML methods, K=26) is precomputed server-side, same as every
other draw on this site (ARIMA/RandomForest/HMM/LSTM etc. aren't things
a browser should redundantly recompute) -- embedded as static data.

Output: public/xoshiro_elim_2129.html
Run: python gen_xoshiro_elim_2129.py
"""
import json

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
META_PATH = BASE + r"\xoshiro_elim_2129_meta.json"
HTML_OUT = BASE + r"\public\xoshiro_elim_2129.html"

with open(META_PATH, encoding='utf-8') as f:
    meta = json.load(f)

TARGET_SERIAL = meta['targetSerial']
base = meta['base']
pass1 = meta['pass1']
method_names = meta['methodNames']
method_picks = meta['methodPicks']
method_k = meta['methodK']
universe_count = meta['universeCount']
removed_by_pass1 = meta['removedByPass1']
after_pass1 = meta['afterPass1']
removed_by_methods = meta['removedByMethods']
final_remaining = meta['finalRemaining']
final_pct = final_remaining / universe_count * 100

methods_rows_html = ""
for name, pool in zip(method_names, method_picks):
    balls = "".join(f'<span class="nb">{n}</span>' for n in pool)
    methods_rows_html += f"""<tr><td class="mname">{name}</td><td><div class="balls">{balls}</div></td></tr>"""

page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Xoshiro K=38/K=33 + 16-Method Elimination — Draw #{TARGET_SERIAL}</title>
<style>
.site-nav{{position:fixed;top:0;left:0;right:0;height:52px;background:#0a0f1e;
  border-bottom:1px solid #1e293b;display:flex;align-items:center;padding:0 20px;
  gap:0;z-index:9999;box-shadow:0 2px 16px rgba(0,0,0,.6)}}
.site-nav .nav-logo{{font-size:1rem;font-weight:800;color:#f1f5f9;text-decoration:none;
  white-space:nowrap;margin-right:24px;flex-shrink:0;letter-spacing:-.01em}}
.site-nav .nav-logo span{{color:#38bdf8}}
.nav-groups{{display:flex;gap:4px;align-items:center}}
.nav-group{{position:relative}}
.nav-group-btn{{display:flex;align-items:center;gap:5px;padding:7px 14px;border-radius:7px;
  cursor:pointer;font-size:.82rem;font-weight:600;color:#94a3b8;
  border:1px solid transparent;transition:.15s;white-space:nowrap;user-select:none}}
.nav-group-btn:hover,.nav-group:hover .nav-group-btn{{color:#f1f5f9;background:#1e293b;border-color:#334155}}
.nav-group-btn .arrow{{font-size:.6rem;opacity:.6;transition:transform .2s}}
.nav-group:hover .nav-group-btn .arrow{{transform:rotate(180deg)}}
.nav-dropdown{{display:none;position:absolute;top:100%;left:0;
  background:transparent;padding-top:6px;z-index:10000;min-width:170px}}
.nav-dropdown-inner{{background:#0d1526;border:1px solid #1e293b;border-radius:10px;
  padding:6px;box-shadow:0 12px 32px rgba(0,0,0,.7);max-height:70vh;overflow-y:auto}}
.nav-group:hover .nav-dropdown{{display:block}}
.nav-dropdown a{{display:flex;align-items:center;gap:8px;padding:8px 12px;
  border-radius:6px;color:#94a3b8;text-decoration:none;font-size:.82rem;
  white-space:nowrap;transition:.12s}}
.nav-dropdown a:hover{{color:#f1f5f9;background:#1e293b}}
.nav-dropdown a.active{{color:#38bdf8;background:#0c2340}}
.nav-dd-label{{font-size:.68rem;font-weight:700;color:#475569;padding:6px 12px 2px;
  text-transform:uppercase;letter-spacing:.06em}}
.nav-divider{{height:1px;background:#1e293b;margin:4px 0}}

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
.section .desc{{font-size:.8rem;color:#64748b;margin-bottom:14px}}
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
.num-btn.active{{opacity:1;box-shadow:0 0 0 2px #0a0f1e,0 0 0 4px #38bdf8;transform:scale(1.08)}}
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

<nav class="site-nav">
  <a class="nav-logo" href="/">🎱 The<span>One</span>Lotto</a>
  <div class="nav-groups">
    <div class="nav-group">
      <div class="nav-group-btn">Data <span class="arrow">▼</span></div>
      <div class="nav-dropdown"><div class="nav-dropdown-inner">
        <div class="nav-dd-label">Results</div>
        <a href="/">🏠 Latest Draw</a>
        <a href="/history">📋 History</a>
        <a href="/numbers">🔢 Numbers</a>
      </div></div>
    </div>
    <div class="nav-group">
      <div class="nav-group-btn">Predict <span class="arrow">▼</span></div>
      <div class="nav-dropdown"><div class="nav-dropdown-inner">
        <div class="nav-dd-label">Prediction Tools</div>
        <a href="/predictions">🎯 Predictions</a>
        <a href="/backtest.html">📊 Backtest</a>
        <a href="/combo_evo.html">🧬 Combo Evo</a>
        <div class="nav-divider"></div>
        <div class="nav-dd-label">Strategy</div>
        <a href="/overdue.html">⏳ Overdue</a>
        <a href="/state_machine.html">🔄 State Machine</a>
        <a href="/modular_cycle.html">🔁 Modular Cycle</a>
        <a href="/next_relation.html">🔗 Next Relation</a>
        <a href="/lstm_predict.html">🧠 LSTM Neural Net</a>
        <div class="nav-divider"></div>
        <div class="nav-dd-label">N-Draw Avg</div>
        <a href="/avg_hub.html">⬡ All N-Draw Avg (2–43)</a>
        <div class="nav-divider"></div>
        <div class="nav-dd-label">N-Draw Avg Shift</div>
        <a href="/avg_shift_hub.html">⇄ All N-Shift Avg (2–43)</a>
        <div class="nav-divider"></div>
        <div class="nav-dd-label">Random Seed</div>
        <a href="/random_seed_backtest.html">🎲 Random Seed (1–3000)</a>
        <a href="/k7_seed_coverage.html">📈 K=7 Seed Coverage</a>
        <a href="/k7_seed_hit_1000.html">🗺️ K=7 Seed-Hit (1000 draws)</a>
      </div></div>
    </div>
    <div class="nav-group">
      <div class="nav-group-btn">Xoshiro Research <span class="arrow">▼</span></div>
      <div class="nav-dropdown"><div class="nav-dropdown-inner">
        <div class="nav-dd-label">Xoshiro256** Seed Scans</div>
        <a href="/xoshiro_seed_backtest.html">🌀 K=21, seeds 0–1,000</a>
        <a href="/xoshiro_seed_scan_100k.html">🔬 K=21, seeds 1–100,000</a>
        <a href="/xoshiro_seed_scan_k33.html">🎯 K=33, seeds 0–1,000,000</a>
        <a href="/xoshiro_seed_scan_k38.html">🔷 K=38, seeds 0–1,000,000</a>
        <a href="/xoshiro_seed_scan_k7.html">🔎 K=7, seeds 0–10,000</a>
        <div class="nav-divider"></div>
        <div class="nav-dd-label">Predictions</div>
        <a href="/xoshiro_elim_2128.html">✂️ Draw #2128 Elimination</a>
        <a href="/xoshiro_elim_2129.html" class="active">✂️ Draw #{TARGET_SERIAL} Elimination</a>
      </div></div>
    </div>
    <div class="nav-group">
      <div class="nav-group-btn">Analyze <span class="arrow">▼</span></div>
      <div class="nav-dropdown"><div class="nav-dropdown-inner">
        <div class="nav-dd-label">Pattern Analysis</div>
        <a href="/special.html">⭐ Special</a>
        <a href="/consecutive.html">🔗 Consecutive</a>
        <div class="nav-divider"></div>
        <div class="nav-dd-label">Position</div>
        <a href="/position.html">📍 Position Freq</a>
        <a href="/pos_predict.html">📊 Pos 1–6 Predict</a>
      </div></div>
    </div>
  </div>
</nav>

<div class="wrap">
  <h1>✂️ Xoshiro K=38/K=33 + 16-Method Elimination — Draw #{TARGET_SERIAL}</h1>
  <p class="subtitle">Combinatorial set-difference: xoshiro256** K=38 pick, minus combos covered by xoshiro K=33's pick and by any of the 16 prediction methods' K={method_k} picks</p>

  <div class="note">
    <p><strong style="color:#e2e8f0">Base</strong> (below) is seed <strong>#{base['seed']:,}</strong>'s xoshiro256** K={base['k']} pick &mdash;
    the current overall best seed found in the 0&ndash;1,000,000 K=38 scan (highest hit6b/hit6/hit5 ranking). This defines the working universe:
    all C(38,6) = {universe_count:,} six-number combinations drawable from its 38-number pool.</p>
    <p><strong style="color:#e2e8f0">Pass 1</strong> is seed <strong>#{pass1['seed']:,}</strong>'s xoshiro256** K={pass1['k']} pick &mdash;
    the current overall best seed found in the 0&ndash;1,000,000 K=33 scan. Any of Base's combos fully contained within this
    {pass1['k']}-number set gets removed.</p>
    <p><strong style="color:#e2e8f0">Pass 2</strong> is each of the 16 prediction methods' K={method_k} pick for draw #{TARGET_SERIAL}, computed
    walk-forward (trained on all {TARGET_SERIAL-1:,} real draws through #{TARGET_SERIAL-1}) then normalized to exactly {method_k} numbers via the same
    cross-method-consensus trim/pad algorithm as <a href="/backtest.html" style="color:#a78bfa">backtest.html</a>'s <code>topKNums()</code>.
    Any of Base's remaining combos fully contained within ANY single one of these 16 sets also gets removed.</p>
    <p>Base &amp; Pass 1 (xoshiro) are recomputed <strong>live in your browser</strong> below &mdash; check the verification badges.
    Pass 2's 16 statistical/ML methods (ARIMA, Random Forest, HMM, LSTM, etc.) are precomputed server-side, same as every other
    draw on this site, and embedded as static data.</p>
  </div>

  <div class="section">
    <h2>Base — xoshiro256** K={base['k']}, seed #{base['seed']:,} <span id="badge1" class="verify-badge pending">verifying…</span></h2>
    <p class="desc">Current overall best K=38 seed (0–1,000,000 scan, ranked by hit6b→hit6→hit5). This 38-number pool is the elimination universe.</p>
    <div class="balls" id="block1Balls"></div>
  </div>

  <div class="section">
    <h2>Pass 1 — xoshiro256** K={pass1['k']}, seed #{pass1['seed']:,} <span id="badge2" class="verify-badge pending">verifying…</span></h2>
    <p class="desc">Current overall best K=33 seed (0–1,000,000 scan, ranked by hit6b→hit6→hit5). Combos it fully covers get removed from Base's universe.</p>
    <div class="balls" id="block2Balls"></div>
  </div>

  <div class="section">
    <h2>Pass 2 — 16 prediction methods, K={method_k} pick for draw #{TARGET_SERIAL}</h2>
    <p class="desc">Precomputed server-side (walk-forward, trained on all real draws through #{TARGET_SERIAL-1}), normalized to K={method_k} via cross-method consensus.</p>
    <details>
      <summary>Show all 16 methods' picks</summary>
      <table class="methods-table">
        <tbody>{methods_rows_html}</tbody>
      </table>
    </details>
  </div>

  <div class="section">
    <h2>Elimination summary</h2>
    <div class="stats-row">
      <div class="stat-card">
        <div class="lbl">Universe (Base)</div>
        <div class="val">{universe_count:,}</div>
        <div class="sub">C(38,6)</div>
      </div>
      <div class="stat-card">
        <div class="lbl">Removed by Pass 1</div>
        <div class="val">{removed_by_pass1:,}</div>
        <div class="sub">contained in the {pass1['k']}-set</div>
      </div>
      <div class="stat-card">
        <div class="lbl">After Pass 1</div>
        <div class="val">{after_pass1:,}</div>
        <div class="sub">remaining after Pass 1</div>
      </div>
      <div class="stat-card">
        <div class="lbl">Removed by 16 methods</div>
        <div class="val">{removed_by_methods:,}</div>
        <div class="sub">contained in ANY method's K={method_k}</div>
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
      <span class="n">{after_pass1:,}</span>
      <span class="arrow">&rarr;</span>
      <span class="n final">{final_remaining:,}</span> remaining
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
function xoshiroPredict(seed, drawSerial, k) {{
  const combined = (BigInt(seed) * 10000000n + BigInt(drawSerial)) & MASK64;
  const s = seedState(combined);
  const arr = Array.from({{length: 43}}, (_, i) => i + 1);
  const n = arr.length;
  for (let i = n - 1; i >= n - k; i--) {{
    const r = xoshiroNext(s);
    const j = Number(r % BigInt(i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }}
  return arr.slice(n - k).sort((a, b) => a - b);
}}

// ── Base & Pass1: compute live + verify against server-embedded reference ────
const KNOWN_BLOCK1 = {json.dumps(base['pool'])};
const KNOWN_BLOCK2 = {json.dumps(pass1['pool'])};

const liveBlock1 = xoshiroPredict({base['seed']}, {TARGET_SERIAL}, {base['k']});
const liveBlock2 = xoshiroPredict({pass1['seed']}, {TARGET_SERIAL}, {pass1['k']});

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

renderBalls('block1Balls', liveBlock1, 'b1');
renderBalls('block2Balls', liveBlock2, 'b2');
renderBadge('badge1', arraysEqual(liveBlock1, KNOWN_BLOCK1));
renderBadge('badge2', arraysEqual(liveBlock2, KNOWN_BLOCK2));
if (!arraysEqual(liveBlock1, KNOWN_BLOCK1)) console.error('Base mismatch', liveBlock1, KNOWN_BLOCK1);
if (!arraysEqual(liveBlock2, KNOWN_BLOCK2)) console.error('Pass1 mismatch', liveBlock2, KNOWN_BLOCK2);

// ── Remaining combos: fetch, paginate, filter, download ─────────────────────
const POOL33 = liveBlock1;
let REMAINING = [];
let filtered = [];
const PAGE_SIZE = 100;
let curPage = 0;
const selectedNums = new Set();

fetch('/xoshiro_elim_{TARGET_SERIAL}_combos.json')
  .then(r => r.json())
  .then(data => {{
    REMAINING = data;
    filtered = REMAINING;
    document.getElementById('loadingMsg').style.display = 'none';
    document.getElementById('comboUI').style.display = 'block';
    buildFilterGrid();
    render();
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
  grid.innerHTML = POOL33.map(n =>
    '<button class="num-btn" data-n="' + n + '" style="background:' + getBallColor(n) + '" onclick="toggleNum(' + n + ')">' + n + '</button>'
  ).join('');
}}
function toggleNum(n) {{
  if (selectedNums.has(n)) selectedNums.delete(n); else selectedNums.add(n);
  document.querySelector('.num-btn[data-n="' + n + '"]').classList.toggle('active', selectedNums.has(n));
  applyFilter();
}}
function clearFilter() {{
  selectedNums.clear();
  document.querySelectorAll('.num-btn.active').forEach(b => b.classList.remove('active'));
  applyFilter();
}}
function applyFilter() {{
  filtered = selectedNums.size === 0 ? REMAINING : REMAINING.filter(c => {{
    for (const n of selectedNums) if (!c.includes(n)) return false;
    return true;
  }});
  document.getElementById('filterInfo').textContent = selectedNums.size === 0 ? '' :
    (filtered.length.toLocaleString() + ' / ' + REMAINING.length.toLocaleString() + ' combos contain ' + [...selectedNums].sort((a,b)=>a-b).join(', '));
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
<script>
(function(){{
  var path = window.location.pathname;
  document.querySelectorAll('.nav-dropdown a').forEach(function(a){{
    var href = a.getAttribute('href');
    if(!href) return;
    if(href === path || (href !== '/' && path.startsWith(href.split('#')[0])))
      a.classList.add('active');
  }});
}})();
</script>
</body>
</html>"""

with open(HTML_OUT, 'w', encoding='utf-8') as f:
    f.write(page)
print(f"Wrote {HTML_OUT} ({len(page)//1024} KB)")
