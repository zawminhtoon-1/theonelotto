"""
gen_xoshiro_seed_backtest.py
------------------------------
Same idea as gen_random_seed_backtest.py (seed a PRNG per draw, sample K
picks, backtest against actual results, rank seeds by avg hits) but using
a from-scratch Xoshiro256** implementation instead of Python's
random.Random (Mersenne Twister). Separate page, separate ranking.

PRNG: xoshiro256** (Blackman & Vigna), seeded via SplitMix64 -- the
"standard companion" seeding scheme the xoshiro authors themselves
recommend for expanding a single 64-bit seed into the 256-bit state.

*** Both algorithms were verified against independent reference sources
    before this script was trusted to run the full backtest: ***
  - SplitMix64: matched exactly against the `rand_xoshiro` Rust crate's
    own reference test vector (seed 1477776061723855037 -> first three
    outputs 1985237415132408290, 2979275885539914483, 13511426838097143398).
  - xoshiro256** transition function: matched exactly against `randomgen`
    (an independent, actively-maintained Python PRNG library citing
    Vigna's own work) across 3 arbitrary raw states, by setting randomgen's
    internal state directly (bypassing its own seeding, which turned out to
    route scalar ints through numpy's SeedSequence rather than plain
    SplitMix64 -- a different but unrelated seeding pipeline, not a bug in
    either implementation).

Sampling: seed = seed*10_000_000 + draw_serial (identical combination
formula to gen_random_seed_backtest.py, for consistency), then a PARTIAL
Fisher-Yates shuffle over [1..43] using xoshiro256** raw outputs reduced
via modulo -- only the last K positions are shuffled into place (cheaper
than a full 43-element shuffle when K=21 < 43). Modulo bias from reducing
a 64-bit output mod a small range (<=43) is on the order of 43/2^64, far
below any measurable threshold, so no rejection sampling was needed.

Output: public/xoshiro_seed_backtest.html
Run: python gen_xoshiro_seed_backtest.py
"""
import json, re

BASE      = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
HTML_IN   = BASE + r"\public\backtest.html"
HTML_OUT  = BASE + r"\public\xoshiro_seed_backtest.html"
K_PICKS   = 21
N_DRAWS   = 1000
SEEDS     = range(0, 1001)   # 0 to 1000 inclusive, per spec
LOTO6_MAX = 43

MASK64 = 0xFFFFFFFFFFFFFFFF

# ── SplitMix64 (seeding) ──────────────────────────────────────────────────────
def splitmix64_next(z):
    z = (z + 0x9E3779B97F4A7C15) & MASK64
    zz = z
    zz = ((zz ^ (zz >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
    zz = ((zz ^ (zz >> 27)) * 0x94D049BB133111EB) & MASK64
    zz = zz ^ (zz >> 31)
    return z, zz  # return updated splitmix state AND its output

def seed_state(seed):
    z = seed & MASK64
    state = []
    for _ in range(4):
        z, out = splitmix64_next(z)
        state.append(out)
    return state

# ── xoshiro256** ───────────────────────────────────────────────────────────────
def rotl(x, k):
    x &= MASK64
    return ((x << k) | (x >> (64 - k))) & MASK64

def xoshiro_next(s):
    """s is a 4-element list, mutated in place. Returns next 64-bit output."""
    result = (rotl((s[1] * 5) & MASK64, 7) * 9) & MASK64
    t = (s[1] << 17) & MASK64
    s[2] ^= s[0]
    s[3] ^= s[1]
    s[1] ^= s[2]
    s[0] ^= s[3]
    s[2] ^= t
    s[3] = rotl(s[3], 45)
    return result

def xoshiro_predict(seed, draw_serial, k=K_PICKS, pool_max=LOTO6_MAX):
    combined_seed = (seed * 10_000_000 + draw_serial) & MASK64
    s = seed_state(combined_seed)
    arr = list(range(1, pool_max + 1))
    n = len(arr)
    # Partial Fisher-Yates: only shuffle the last k positions into place
    for i in range(n - 1, n - 1 - k, -1):
        r = xoshiro_next(s)
        j = r % (i + 1)
        arr[i], arr[j] = arr[j], arr[i]
    return sorted(arr[n - k:])

# ── Self-check before running the full backtest ────────────────────────────────
# (Independent verification against reference sources already done separately;
# this is just a sanity re-check that the module-level functions used here
# reproduce the same verified values.)
_sm_state = 1477776061723855037 & MASK64
_out1 = splitmix64_next(_sm_state)[1]
assert _out1 == 1985237415132408290, f"SplitMix64 self-check failed: {_out1}"
print("Self-check: SplitMix64 matches reference test vector. OK.")

# ── Load backtest DATA (same source as gen_random_seed_backtest.py) ───────────
with open(HTML_IN, encoding='utf-8') as f:
    html = f.read()

m = re.search(r'const DATA\s*=\s*(\[)', html)
bs = m.start(1)
depth = 0; pos = bs
while pos < len(html):
    if html[pos] == '[': depth += 1
    elif html[pos] == ']':
        depth -= 1
        if depth == 0: be = pos + 1; break
    pos += 1
ALL_DATA = json.loads(html[bs:be])

DATA = ALL_DATA[-N_DRAWS:]
print(f"Loaded {len(ALL_DATA)} total entries. Using last {len(DATA)}: draws {DATA[0]['s']}-{DATA[-1]['s']}")

# ── Evaluate each seed ─────────────────────────────────────────────────────────
BASELINE = K_PICKS * 6 / LOTO6_MAX

results = []
for seed in SEEDS:
    total_hits = 0
    bonus_hits = 0
    dist = [0] * 7
    for row in DATA:
        actual = set(row['a'])
        bonus = row['b']
        picks = xoshiro_predict(seed, row['s'])
        h = len(actual & set(picks))
        bh = bonus in picks
        total_hits += h
        bonus_hits += int(bh)
        dist[min(h, 6)] += 1
    n = len(DATA)
    avg = total_hits / n
    lift = (avg / BASELINE - 1) * 100
    results.append({
        'seed': seed, 'avg': round(avg, 4), 'lift': round(lift, 2),
        'dist': dist, 'bonus': bonus_hits,
        'hit6': dist[6], 'hit5': dist[5], 'hit4': dist[4], 'hit0': dist[0],
    })
    if seed % 100 == 0:
        print(f"  Seed {seed:4d}: avg={avg:.4f} lift={lift:+.1f}% 6hits={dist[6]} 5hits={dist[5]}")

results.sort(key=lambda r: (-r['avg'], r['seed']))
best = results[0]
worst = results[-1]
print(f"\nBest  seed {best['seed']:4d}: avg={best['avg']:.4f} lift={best['lift']:+.1f}% 6hits={best['hit6']}")
print(f"Worst seed {worst['seed']:4d}: avg={worst['avg']:.4f} lift={worst['lift']:+.1f}% 6hits={worst['hit6']}")
print(f"Baseline avg (pure random): {BASELINE:.4f}")

# ── Build HTML ─────────────────────────────────────────────────────────────────
rows_html = ""
for rank, r in enumerate(results, 1):
    is_best = r['seed'] == best['seed']
    lift_color = "#22c55e" if r['lift'] > 0 else "#ef4444"
    best_badge = ' <span style="background:#fef08a;color:#713f12;font-size:10px;padding:2px 6px;border-radius:4px;margin-left:4px;">BEST</span>' if is_best else ''
    rows_html += f"""<tr class="dr" onclick="selSeed({r['seed']})">
  <td class="tc">{rank}</td>
  <td class="tc">{r['seed']}{best_badge}</td>
  <td class="tr">{r['avg']:.4f}</td>
  <td class="tr" style="color:{lift_color}">{r['lift']:+.1f}%</td>
  <td class="tr">{r['hit6']}</td>
  <td class="tr">{r['hit5']}</td>
  <td class="tr">{r['hit4']}</td>
  <td class="tr">{r['hit0']}</td>
  <td class="tr">{r['bonus']}</td>
</tr>"""

js_data = json.dumps(results, separators=(',', ':'))
js_draws = json.dumps([{'s': r['s'], 'd': r['d'], 'a': r['a'], 'b': r['b']} for r in DATA], separators=(',', ':'))

next_serial = DATA[-1]['s'] + 1
next_picks = xoshiro_predict(best['seed'], next_serial)

page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Xoshiro Seed Backtest — Loto 6</title>
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
.wrap{{max-width:1100px;margin:0 auto;padding:24px 16px}}
h1{{font-size:1.4rem;font-weight:700;color:#f1f5f9;margin-bottom:4px}}
.subtitle{{font-size:.85rem;color:#64748b;margin-bottom:20px}}

.note{{background:#0d1526;border:1px solid #1e293b;border-radius:10px;padding:14px 18px;
  font-size:.8rem;color:#94a3b8;margin-bottom:20px;line-height:1.6}}

.stats-row{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:24px}}
.stat-card{{background:#0d1526;border:1px solid #1e293b;border-radius:10px;padding:14px 18px;flex:1;min-width:140px}}
.stat-card .lbl{{font-size:.72rem;color:#64748b;text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px}}
.stat-card .val{{font-size:1.5rem;font-weight:700;color:#f1f5f9}}
.stat-card .sub{{font-size:.78rem;color:#94a3b8;margin-top:2px}}

.controls{{display:flex;gap:10px;align-items:center;margin-bottom:14px;flex-wrap:wrap}}
.controls input{{background:#0d1526;border:1px solid #334155;border-radius:7px;padding:7px 12px;
  color:#e2e8f0;font-size:.83rem;width:200px}}
.controls select{{background:#0d1526;border:1px solid #334155;border-radius:7px;padding:7px 12px;
  color:#e2e8f0;font-size:.83rem}}

.tbl-wrap{{overflow-x:auto;border-radius:10px;border:1px solid #1e293b}}
table{{width:100%;border-collapse:collapse;font-size:.83rem}}
thead th{{background:#0d1526;padding:10px 14px;text-align:right;color:#94a3b8;
  font-weight:600;font-size:.75rem;text-transform:uppercase;letter-spacing:.05em;
  cursor:pointer;user-select:none;white-space:nowrap;border-bottom:1px solid #1e293b}}
thead th:hover{{color:#f1f5f9}}
thead th.tc{{text-align:center}}
tbody tr{{border-bottom:1px solid #1e293b;cursor:pointer;transition:.12s}}
tbody tr:hover{{background:#111827}}
tbody tr.selected{{background:#0c2340 !important;outline:1px solid #38bdf8}}
tbody td{{padding:9px 14px;text-align:right;color:#cbd5e1}}
tbody td.tc{{text-align:center}}
tbody td.tr{{text-align:right}}
.rank1 td{{color:#fbbf24}}

#seedModal{{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.82);z-index:20000;align-items:flex-start;justify-content:center;padding:60px 16px 20px}}
.modal-box{{background:#0a0f1e;border:1px solid #1e293b;border-radius:12px;width:100%;max-width:1000px;max-height:85vh;display:flex;flex-direction:column}}
.modal-hdr{{display:flex;justify-content:space-between;align-items:center;padding:14px 18px;border-bottom:1px solid #1e293b;flex-shrink:0}}
.modal-hdr h2{{font-size:.95rem;font-weight:700;color:#f1f5f9;margin:0}}
.modal-close{{background:#1e293b;border:none;color:#94a3b8;padding:5px 14px;border-radius:6px;cursor:pointer;font-size:.83rem}}
.modal-close:hover{{background:#334155;color:#f1f5f9}}
.modal-body{{overflow-y:auto;flex:1}}
.modal-table{{width:100%;border-collapse:collapse;font-size:.78rem}}
.modal-table thead{{position:sticky;top:0;background:#0a0f1e;z-index:1}}
.modal-table th{{padding:9px 12px;color:#64748b;text-align:left;border-bottom:1px solid #1e293b;font-weight:600;font-size:.72rem;text-transform:uppercase;letter-spacing:.04em;white-space:nowrap}}
.modal-table td{{padding:6px 10px;border-bottom:1px solid #0f172a;vertical-align:middle}}
.modal-table tr:hover td{{background:#0f172a}}
.nb{{display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;border-radius:50%;background:#1e293b;color:#64748b;font-size:.7rem;font-weight:700;margin:1px}}
.nm{{background:#14532d;color:#86efac}}
.nb-b{{background:#451a03;color:#fde68a;border:1px solid #92400e}}
.nb-bh{{background:#7c2d12;color:#fed7aa}}

.next-pred{{background:#0d1526;border:1px solid #a78bfa55;border-radius:10px;padding:16px 18px;margin-top:16px}}
.next-pred .lbl{{font-size:.72rem;color:#a78bfa;text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px}}
.balls{{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}}
.ball{{width:34px;height:34px;border-radius:50%;background:#312e5f;display:flex;align-items:center;
  justify-content:center;font-weight:700;font-size:.85rem;color:#c4b5fd;border:1px solid #7c3aed55}}

.footer{{margin-top:28px;font-size:.78rem;color:#475569;padding-bottom:20px}}
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
        <a href="/xoshiro_seed_backtest.html" class="active">🌀 Xoshiro Seed (0–1000)</a>
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
  <h1>🌀 Xoshiro Seed Backtest</h1>
  <p class="subtitle">Seeds {SEEDS.start}–{SEEDS.stop - 1} · {K_PICKS} picks · last {N_DRAWS} draws ({DATA[0]['s']}–{DATA[-1]['s']}) · random baseline ≈ {BASELINE:.3f} avg hits</p>

  <div class="note">
    Same idea as the <a href="/random_seed_backtest.html" style="color:#a78bfa">Random Seed Backtest</a>
    but with a completely different PRNG: <strong style="color:#e2e8f0">xoshiro256**</strong>
    (Blackman &amp; Vigna) implemented from scratch, seeded via SplitMix64, instead of Python's
    Mersenne-Twister-based <code>random.Random</code>. Both algorithms were independently verified
    against reference test vectors before running this backtest &mdash; SplitMix64 against the
    <code>rand_xoshiro</code> Rust crate's own reference vector, and the xoshiro256** transition
    function bit-exact against the <code>randomgen</code> Python library (with its internal state
    set directly, bypassing its own seeding pipeline which uses numpy's SeedSequence rather than
    plain SplitMix64). Picks: seed = seed&times;10,000,000 + draw_serial, then a partial Fisher-Yates
    shuffle over 1&ndash;43 using xoshiro256** outputs.
  </div>

  <div class="stats-row">
    <div class="stat-card">
      <div class="lbl">Best seed</div>
      <div class="val">#{best['seed']}</div>
      <div class="sub">avg {best['avg']:.4f} hits · {best['lift']:+.1f}% vs baseline</div>
    </div>
    <div class="stat-card">
      <div class="lbl">Best 6-hit draws</div>
      <div class="val">{max(r['hit6'] for r in results)}</div>
      <div class="sub">seed #{sorted(results, key=lambda r: -r['hit6'])[0]['seed']}</div>
    </div>
    <div class="stat-card">
      <div class="lbl">Baseline (pure chance)</div>
      <div class="val">{BASELINE:.3f}</div>
      <div class="sub">{K_PICKS} picks × 6 / 43</div>
    </div>
    <div class="stat-card">
      <div class="lbl">Draws evaluated</div>
      <div class="val">{N_DRAWS}</div>
      <div class="sub">serials {DATA[0]['s']}–{DATA[-1]['s']}</div>
    </div>
  </div>

  <div class="next-pred">
    <div class="lbl">🏆 Best seed #{best['seed']} — predicted picks for draw #{next_serial}</div>
    <div class="balls">
      {''.join(f'<div class="ball">{n}</div>' for n in next_picks)}
    </div>
  </div>

  <div class="controls" style="margin-top:20px">
    <input id="filterInput" placeholder="Filter by seed number..." oninput="filterTable()">
    <select id="sortSel" onchange="sortTable(this.value)">
      <option value="rank">Sort: Rank (avg hits)</option>
      <option value="seed">Sort: Seed</option>
      <option value="hit6">Sort: 6-hit draws</option>
      <option value="hit5">Sort: 5-hit draws</option>
      <option value="hit4">Sort: 4-hit draws</option>
      <option value="hit0">Sort: 0-hit draws ↑</option>
      <option value="lift">Sort: Lift %</option>
    </select>
  </div>

  <div class="tbl-wrap">
    <table id="mainTable">
      <thead>
        <tr>
          <th class="tc" onclick="sortTable('rank')">#</th>
          <th class="tc" onclick="sortTable('seed')">Seed</th>
          <th onclick="sortTable('rank')">Avg hits ▼</th>
          <th onclick="sortTable('lift')">Lift %</th>
          <th onclick="sortTable('hit6')">6-hits</th>
          <th onclick="sortTable('hit5')">5-hits</th>
          <th onclick="sortTable('hit4')">4-hits</th>
          <th onclick="sortTable('hit0')">0-hits ↑</th>
          <th onclick="sortTable('bonus')">Bonus hits</th>
        </tr>
      </thead>
      <tbody id="tbody">
{rows_html}
      </tbody>
    </table>
  </div>

  <div id="seedModal">
    <div class="modal-box">
      <div class="modal-hdr">
        <h2 id="modalTitle">Seed detail</h2>
        <button class="modal-close" onclick="document.getElementById('seedModal').style.display='none'">✕ Close</button>
      </div>
      <div class="modal-body">
        <table class="modal-table">
          <thead><tr>
            <th>Draw</th><th>Date</th>
            <th>Actual (6) + bonus</th>
            <th>Picks ({K_PICKS})</th>
            <th style="text-align:center">Hits</th>
          </tr></thead>
          <tbody id="modalTbody"></tbody>
        </table>
      </div>
    </div>
  </div>

  <p class="footer">
    Xoshiro256** (seeded via SplitMix64): picks = partial Fisher-Yates(range(1,44), {K_PICKS}) with
    combined seed = seed×10⁷ + draw_serial.<br>
    Each (seed, draw) pair is independent and deterministic. Lift = % above pure-chance baseline
    ({BASELINE:.3f} avg hits). Both PRNG stages verified against independent reference
    implementations before this backtest was run -- see the note above.
  </p>
</div>

<script>
const DATA = {js_data};
const DRAWS = {js_draws};
const BEST_SEED = {best['seed']};
let selSeedVal = null;

function filterTable() {{
  const q = document.getElementById('filterInput').value.trim();
  document.querySelectorAll('#tbody tr').forEach(tr => {{
    const seed = tr.cells[1].textContent.trim().split(' ')[0];
    tr.style.display = (!q || seed.includes(q)) ? '' : 'none';
  }});
}}

let sortKey = 'rank'; let sortAsc = false;
function sortTable(key) {{
  sortAsc = (key === sortKey) ? !sortAsc : (key === 'hit0' || key === 'seed');
  sortKey = key;
  const tbody = document.getElementById('tbody');
  const rows = [...tbody.querySelectorAll('tr')];
  const keyMap = {{rank: 2, seed: 1, lift: 3, hit6: 4, hit5: 5, hit4: 6, hit0: 7, bonus: 8}};
  const col = keyMap[key] || 2;
  rows.sort((a, b) => {{
    const av = parseFloat(a.cells[col].textContent) || 0;
    const bv = parseFloat(b.cells[col].textContent) || 0;
    return sortAsc ? av - bv : bv - av;
  }});
  rows.forEach(r => tbody.appendChild(r));
}}

// ── xoshiro256**, bit-exact port of the Python implementation, using BigInt
// for genuine 64-bit unsigned arithmetic (not an approximation like the
// Random Seed page's mulberry32 -- this matches the backtest table exactly).
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

function selSeed(seed) {{
  selSeedVal = seed;
  document.querySelectorAll('#tbody tr').forEach(tr => {{
    tr.classList.toggle('selected', tr.cells[1].textContent.trim().split(' ')[0] == seed);
  }});

  const K = {K_PICKS};
  document.getElementById('modalTitle').textContent = 'Seed #' + seed + ' — ' + DRAWS.length + ' draws (K=' + K + ')';

  const htmlParts = [];
  [...DRAWS].reverse().forEach(row => {{
    const picks = xoshiroPredict(seed, row.s, K);
    const actualSet = new Set(row.a);
    const hits = picks.filter(p => actualSet.has(p)).length;
    const bh   = picks.includes(row.b);

    const actualHtml = row.a.map(n =>
      '<span class="nb nm">' + n + '</span>'
    ).join('') + '<span class="nb nb-b">' + row.b + '</span>';

    const picksHtml = picks.map(n =>
      '<span class="nb' + (actualSet.has(n) ? ' nm' : '') + (n === row.b ? ' nb-bh' : '') + '">' + n + '</span>'
    ).join('');

    const hc = hits >= 5 ? '#22c55e' : hits >= 4 ? '#4ade80' : hits >= 3 ? '#fbbf24' : hits >= 2 ? '#fb923c' : '#475569';
    htmlParts.push(
      '<tr><td style="color:#64748b;white-space:nowrap">' + row.s + '</td>' +
      '<td style="color:#64748b;white-space:nowrap">' + (row.d||'') + '</td>' +
      '<td style="white-space:nowrap">' + actualHtml + '</td>' +
      '<td style="white-space:nowrap">' + picksHtml + '</td>' +
      '<td style="text-align:center;font-weight:700;color:' + hc + '">' + hits + (bh ? '<span style="color:#a78bfa;font-size:.7rem">+B</span>' : '') + '</td></tr>'
    );
  }});
  document.getElementById('modalTbody').innerHTML = htmlParts.join('');
  document.getElementById('seedModal').style.display = 'flex';
}}

document.getElementById('seedModal').addEventListener('click', function(e) {{
  if (e.target === this) this.style.display = 'none';
}});
document.addEventListener('keydown', function(e) {{
  if (e.key === 'Escape') document.getElementById('seedModal').style.display = 'none';
}});
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
print(f"\nWrote {HTML_OUT} ({len(page)//1024} KB)")
print(f"Best seed: #{best['seed']} avg={best['avg']:.4f} lift={best['lift']:+.1f}% 6hits={best['hit6']}")
print(f"Predicted picks for draw #{next_serial}: {next_picks}")
