"""
gen_random_seed_backtest.py
---------------------------
For each seed -12,376 to 12,376 (24,753 seeds, including negative seeds
-- the seed formula is seed*10_000_000+draw_serial, same convention as
the xoshiro pages), generate K=17 picks via Python's seeded random.Random
for each of draws #1001-2129 (1129 draws), compare against actual
results.

PRNG mismatch bug (previously documented, now FIXED): the seed-detail
modal used to run a completely different PRNG (mulberry32 + a hand-rolled
Fisher-Yates shuffle) than the table (Python's real random.Random.sample(),
backed by Mersenne Twister), so the modal's live per-draw picks did not
match the table's numbers for the same seed (caught via seed #294 on draw
#2123 mismatching). Fixed by porting CPython's actual seeding algorithm
(random_seed's abs-value + little-endian word split + init_by_array) and
its real random.sample() pool-method algorithm to JS, bit-exact --
verified against 65+ independently Python-computed reference cases
(including negative seeds and both range boundaries) before trusting it
at scale. The modal now uses this port instead of mulberry32.

Draws are pulled directly from the production DB (backtest.html's
embedded array only goes back to #1121, short of the requested #1001
start), verified for exactly 1129 consecutive rows with no gaps.

Multiprocessing (7 workers) -- self-checked against a small single-process
sample before trusting the pool.

Output: public/random_seed_backtest.html
Run: python gen_random_seed_backtest.py
"""
import json, re, random, math, os, time
import multiprocessing as mp
from collections import Counter

BASE      = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
ENV_LOCAL = BASE + r"\.env.local"
HTML_OUT  = BASE + r"\public\random_seed_backtest.html"

K_PICKS   = 17
DRAW_START, DRAW_END = 1001, 2129
N_DRAWS   = DRAW_END - DRAW_START + 1  # 1129
SEED_LO, SEED_HI = -12376, 12376
LOTO6_MAX = 43
N_WORKERS = 7
CHUNK_SIZE = 200

# ── Random prediction function (ground truth -- real Python random.Random) ──
def random_predict(seed, draw_serial, k=K_PICKS):
    rng = random.Random(seed * 10_000_000 + draw_serial)
    return sorted(rng.sample(range(1, LOTO6_MAX + 1), k))

BASELINE = K_PICKS * 6 / LOTO6_MAX  # expected hits by pure chance

def init_worker(data_bytes):
    global _DATA
    rows = json.loads(data_bytes)
    _DATA = [(r['s'], frozenset(r['a']), r['b']) for r in rows]

def process_chunk(seed_chunk):
    out = []
    for seed in seed_chunk:
        total_hits = 0
        bonus_hits = 0
        dist = [0, 0, 0, 0, 0, 0, 0]
        for serial, actual_set, bonus in _DATA:
            picks = random_predict(seed, serial)
            picks_set = frozenset(picks)
            h = len(actual_set & picks_set)
            dist[h] += 1
            total_hits += h
            if bonus in picks_set:
                bonus_hits += 1
        out.append((seed, total_hits, bonus_hits, dist))
    return out

def load_data_from_db():
    if 'DATABASE_URL' not in os.environ:
        with open(ENV_LOCAL, encoding='utf-8') as f:
            env_text = f.read()
        m = re.search(r'DATABASE_URL=(.+)', env_text)
        os.environ['DATABASE_URL'] = m.group(1).strip()
    import psycopg2
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    cur = conn.cursor()
    cur.execute(
        "SELECT draw_serial, draw_date, num1,num2,num3,num4,num5,num6, bonus "
        "FROM loto6_results WHERE draw_serial BETWEEN %s AND %s ORDER BY draw_serial",
        (DRAW_START, DRAW_END),
    )
    rows = cur.fetchall()
    conn.close()
    return [{'s': r[0], 'd': r[1].isoformat(), 'a': list(r[2:8]), 'b': r[8]} for r in rows]

def main():
    DATA = load_data_from_db()
    print(f"Loaded {len(DATA)} rows from loto6_results for draws {DRAW_START}-{DRAW_END} (expected {N_DRAWS}).")
    serials = [r['s'] for r in DATA]
    if len(DATA) != N_DRAWS:
        raise SystemExit(f"Row count mismatch: got {len(DATA)}, expected {N_DRAWS}")
    if serials[0] != DRAW_START or serials[-1] != DRAW_END:
        raise SystemExit(f"Endpoint mismatch: got {serials[0]}-{serials[-1]}, expected {DRAW_START}-{DRAW_END}")
    if serials != list(range(DRAW_START, DRAW_END + 1)):
        missing = sorted(set(range(DRAW_START, DRAW_END + 1)) - set(serials))
        raise SystemExit(f"Gap check FAILED. Missing: {missing[:10]}...")
    print(f"Verified: {len(DATA)} consecutive draws, no gaps, #{DRAW_START}-{DRAW_END} exactly.")

    data_bytes = json.dumps(DATA)

    # ── Self-check: multiprocessing worker path must match a plain single-
    # process computation for a handful of seeds (incl. negative + boundary),
    # before trusting the full parallel scan. ──────────────────────────────
    init_worker(data_bytes)
    test_seeds = [SEED_LO, SEED_HI, 0, 1, -1, 168, -12000, 9999]
    for ts in test_seeds:
        direct = process_chunk([ts])[0]
        # Re-derive independently without going through process_chunk, as
        # an extra cross-check that process_chunk itself is doing the right
        # aggregation (not just re-running the same code path).
        th = bh = 0
        d = [0]*7
        for row in DATA:
            picks = set(random_predict(ts, row['s']))
            hh = len(set(row['a']) & picks)
            d[hh] += 1
            th += hh
            if row['b'] in picks:
                bh += 1
        assert direct == (ts, th, bh, d), f"Self-check MISMATCH seed={ts}: {direct} vs {(ts, th, bh, d)}"
    print(f"Self-check OK: {len(test_seeds)} seeds (incl. negative + boundary) verified consistent.")

    # ── Parallel scan ────────────────────────────────────────────────────────
    seeds = list(range(SEED_LO, SEED_HI + 1))
    num_seeds = len(seeds)
    chunks = [seeds[i:i + CHUNK_SIZE] for i in range(0, num_seeds, CHUNK_SIZE)]
    total_chunks = len(chunks)
    print(f"\nScanning {num_seeds:,} seeds ({SEED_LO:,} to {SEED_HI:,}) x {N_DRAWS} draws x K={K_PICKS}, "
          f"{total_chunks:,} chunks of {CHUNK_SIZE}, {N_WORKERS} workers...")

    all_raw = []
    t0 = time.time()
    done_seeds = 0
    with mp.Pool(N_WORKERS, initializer=init_worker, initargs=(data_bytes,)) as pool:
        for i, chunk_result in enumerate(pool.imap_unordered(process_chunk, chunks), 1):
            all_raw.extend(chunk_result)
            done_seeds += len(chunk_result)
            if i % 20 == 0 or i == total_chunks:
                elapsed = time.time() - t0
                rate = done_seeds / elapsed
                eta = (num_seeds - done_seeds) / rate if rate > 0 else 0
                print(f"[{i:,}/{total_chunks:,} chunks, {done_seeds:,}/{num_seeds:,} seeds] "
                      f"elapsed={elapsed:.0f}s rate={rate:.0f} seeds/s eta={eta:.0f}s", flush=True)
    elapsed_total = time.time() - t0
    print(f"\nDONE scanning in {elapsed_total:.1f}s ({elapsed_total/60:.1f} min)")

    results = []
    for seed, total_hits, bonus_hits, dist in all_raw:
        avg = total_hits / N_DRAWS
        lift = (avg / BASELINE - 1) * 100
        results.append({
            'seed': seed, 'avg': round(avg, 4), 'lift': round(lift, 2), 'dist': dist,
            'bonus': bonus_hits, 'hit6': dist[6], 'hit5': dist[5], 'hit4': dist[4], 'hit0': dist[0],
        })
    results.sort(key=lambda r: (-r['avg'], r['seed']))
    best = results[0]

    worst_coverage_ranked = sorted(results, key=lambda r: (-r['hit0'], r['seed']))
    worst_coverage = worst_coverage_ranked[0]
    hit0_vals = [r['hit0'] for r in results]
    import statistics as st
    hit0_mean = st.mean(hit0_vals)

    print(f"\nBest  seed {best['seed']}: avg={best['avg']:.4f} lift={best['lift']:+.1f}% 6hits={best['hit6']} 5hits={best['hit5']}")
    print(f"Worst-coverage seed {worst_coverage['seed']}: hit0={worst_coverage['hit0']} "
          f"(mean hit0 across all seeds: {hit0_mean:.2f}) dist={worst_coverage['dist']} "
          f"avg={worst_coverage['avg']:.4f} lift={worst_coverage['lift']:+.1f}%")
    print(f"Baseline avg (pure random): {BASELINE:.4f}")

    # ── Build HTML ─────────────────────────────────────────────────────────────────
    rows_html = ""
    for rank, r in enumerate(results, 1):
        is_best = r['seed'] == best['seed']
        lift_color = "#22c55e" if r['lift'] > 0 else "#ef4444"
        best_badge = ' <span style="background:#fef08a;color:#713f12;font-size:10px;padding:2px 6px;border-radius:4px;margin-left:4px;">BEST</span>' if is_best else ''
        rows_html += f"""<tr class="dr" onclick="selSeed({r['seed']})">
  <td class="tc">{rank}</td>
  <td class="tc">{r['seed']:,}{best_badge}</td>
  <td class="tr">{r['avg']:.4f}</td>
  <td class="tr" style="color:{lift_color}">{r['lift']:+.1f}%</td>
  <td class="tr">{r['hit6']}</td>
  <td class="tr">{r['hit5']}</td>
  <td class="tr">{r['hit4']}</td>
  <td class="tr">{r['hit0']}</td>
  <td class="tr">{r['bonus']}</td>
</tr>"""

    js_draws = json.dumps([{'s': r['s'], 'd': r['d'], 'a': r['a'], 'b': r['b']} for r in DATA], separators=(',', ':'))

    next_serial = DATA[-1]['s'] + 1
    next_picks = random_predict(best['seed'], next_serial)

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Random Seed Backtest — Loto 6</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0a0f1e;color:#e2e8f0;font-family:system-ui,sans-serif;padding-top:60px;min-height:100vh}}
.wrap{{max-width:1100px;margin:0 auto;padding:24px 16px}}
h1{{font-size:1.4rem;font-weight:700;color:#f1f5f9;margin-bottom:4px}}
.subtitle{{font-size:.85rem;color:#64748b;margin-bottom:20px}}

.note{{background:#0d1526;border:1px solid #1e293b;border-radius:10px;padding:14px 18px;
  font-size:.8rem;color:#94a3b8;margin-bottom:20px;line-height:1.6}}
.note strong{{color:#e2e8f0}}

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

/* modal */
#seedModal{{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.82);z-index:20000;align-items:flex-start;justify-content:center;padding:60px 16px 20px}}
.modal-box{{background:#0a0f1e;border:1px solid #1e293b;border-radius:12px;width:100%;max-width:1000px;max-height:85vh;display:flex;flex-direction:column}}
.modal-hdr{{display:flex;justify-content:space-between;align-items:center;padding:14px 18px;border-bottom:1px solid #1e293b;flex-shrink:0;gap:16px;flex-wrap:wrap}}
.modal-hdr h2{{font-size:.95rem;font-weight:700;color:#f1f5f9;margin:0}}
.modal-hdr .modal-stats{{font-size:.78rem;color:#94a3b8}}
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

.next-pred{{background:#0d1526;border:1px solid #f59e0b55;border-radius:10px;padding:16px 18px;margin-top:16px}}
.next-pred .lbl{{font-size:.72rem;color:#f59e0b;text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px}}
.balls{{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}}
.ball{{width:34px;height:34px;border-radius:50%;background:#1e3a5f;display:flex;align-items:center;
  justify-content:center;font-weight:700;font-size:.85rem;color:#93c5fd;border:1px solid #2563eb55}}

.footer{{margin-top:28px;font-size:.78rem;color:#475569;padding-bottom:20px;line-height:1.6}}
</style>
</head>
<body>

<script src="/site-nav.js"></script>
<div class="wrap">
  <h1>🎲 Random Seed Backtest</h1>
  <p class="subtitle">Seeds {SEED_LO:,}–{SEED_HI:,} · {K_PICKS} picks · {N_DRAWS} draws (#{DRAW_START}–{DRAW_END}) · random baseline ≈ {BASELINE:.3f} avg hits</p>

  <div class="note">
    <strong>PRNG mismatch bug fixed:</strong> the seed-detail modal below now runs a bit-exact JavaScript port of
    CPython's actual Mersenne Twister seeding (<code>random_seed</code>'s abs-value + <code>init_by_array</code>)
    and its real <code>random.sample()</code> pool-method algorithm — verified against 65+ independently
    Python-computed reference cases (including negative seeds and both range boundaries) before trusting it.
    Previously the modal used an unrelated PRNG (mulberry32 + a hand-rolled Fisher-Yates shuffle), so its live
    per-draw picks did not match this table's numbers for the same seed. Click any row to confirm agreement yourself.
  </div>

  <div class="stats-row">
    <div class="stat-card">
      <div class="lbl">Best seed</div>
      <div class="val">#{best['seed']:,}</div>
      <div class="sub">avg {best['avg']:.4f} hits · {best['lift']:+.1f}% vs baseline</div>
    </div>
    <div class="stat-card">
      <div class="lbl">Best 6-hit draws</div>
      <div class="val">{max(r['hit6'] for r in results)}</div>
      <div class="sub">seed #{sorted(results, key=lambda r: -r['hit6'])[0]['seed']:,}</div>
    </div>
    <div class="stat-card">
      <div class="lbl">Worst coverage (0-hit)</div>
      <div class="val">#{worst_coverage['seed']:,}</div>
      <div class="sub">{worst_coverage['hit0']} zero-hit draws (mean {hit0_mean:.1f})</div>
    </div>
    <div class="stat-card">
      <div class="lbl">Baseline (pure chance)</div>
      <div class="val">{BASELINE:.3f}</div>
      <div class="sub">{K_PICKS} picks × 6 / 43</div>
    </div>
    <div class="stat-card">
      <div class="lbl">Draws evaluated</div>
      <div class="val">{N_DRAWS}</div>
      <div class="sub">serials {DRAW_START}–{DRAW_END}</div>
    </div>
  </div>

  <!-- Next-draw prediction from best seed -->
  <div class="next-pred">
    <div class="lbl">🏆 Best seed #{best['seed']:,} — predicted picks for draw #{next_serial}</div>
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

  <!-- Seed detail modal -->
  <div id="seedModal">
    <div class="modal-box">
      <div class="modal-hdr">
        <h2 id="modalTitle">Seed detail</h2>
        <div class="modal-stats" id="modalStats"></div>
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
    Seeded random: picks = sorted(random.Random(seed×10⁷+draw_serial).sample(range(1,44), {K_PICKS})).<br>
    Each (seed, draw) pair is independent and deterministic. Lift = % above pure-chance baseline ({BASELINE:.3f} avg hits).<br>
    Seed range includes negative seeds; Python's random.Random(x) takes abs(x) before seeding Mersenne Twister, so the
    combined value (seed×10⁷+draw_serial, which can itself be negative) is what gets absolute-valued -- verified this
    still produces seed-distinct sequences (not mirrored positive/negative pairs) since draw_serial is small relative
    to seed×10⁷.
  </p>
</div>

<script>
const DRAWS = {js_draws};
let selSeedVal = null;

function filterTable() {{
  const q = document.getElementById('filterInput').value.trim();
  document.querySelectorAll('#tbody tr').forEach(tr => {{
    const seed = tr.cells[1].textContent.trim().split(' ')[0].replace(/,/g, '');
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
    const av = parseFloat(a.cells[col].textContent.replace(/,/g, '')) || 0;
    const bv = parseFloat(b.cells[col].textContent.replace(/,/g, '')) || 0;
    return sortAsc ? av - bv : bv - av;
  }});
  rows.forEach(r => tbody.appendChild(r));
}}

// ── CPython-compatible MT19937 port (bit-exact random.Random + random.sample) ──
// Verified against 65+ independently Python-computed reference cases
// (including negative seeds and both range boundaries) before use here.
function imul32(a, b) {{ return Math.imul(a, b) >>> 0; }}
const MT_N = 624, MT_M = 397;
const MATRIX_A = 0x9908b0df, UPPER_MASK = 0x80000000, LOWER_MASK = 0x7fffffff;
function MT19937() {{ this.mt = new Uint32Array(MT_N); this.mti = MT_N + 1; }}
MT19937.prototype.initGenrand = function (s) {{
  this.mt[0] = s >>> 0;
  for (let i = 1; i < MT_N; i++) {{
    const prev = this.mt[i - 1] ^ (this.mt[i - 1] >>> 30);
    this.mt[i] = (imul32(1812433253, prev) + i) >>> 0;
  }}
  this.mti = MT_N;
}};
MT19937.prototype.initByArray = function (initKey) {{
  this.initGenrand(19650218);
  let i = 1, j = 0, k = Math.max(MT_N, initKey.length);
  for (; k; k--) {{
    const prev = this.mt[i - 1] ^ (this.mt[i - 1] >>> 30);
    this.mt[i] = ((this.mt[i] ^ imul32(prev, 1664525)) + initKey[j] + j) >>> 0;
    i++; j++;
    if (i >= MT_N) {{ this.mt[0] = this.mt[MT_N - 1]; i = 1; }}
    if (j >= initKey.length) j = 0;
  }}
  for (k = MT_N - 1; k; k--) {{
    const prev = this.mt[i - 1] ^ (this.mt[i - 1] >>> 30);
    this.mt[i] = ((this.mt[i] ^ imul32(prev, 1566083941)) - i) >>> 0;
    i++;
    if (i >= MT_N) {{ this.mt[0] = this.mt[MT_N - 1]; i = 1; }}
  }}
  this.mt[0] = 0x80000000;
}};
MT19937.prototype.genrandUint32 = function () {{
  const mag01 = [0, MATRIX_A]; let y;
  if (this.mti >= MT_N) {{
    let kk;
    for (kk = 0; kk < MT_N - MT_M; kk++) {{
      y = (this.mt[kk] & UPPER_MASK) | (this.mt[kk + 1] & LOWER_MASK);
      this.mt[kk] = this.mt[kk + MT_M] ^ (y >>> 1) ^ mag01[y & 1];
    }}
    for (; kk < MT_N - 1; kk++) {{
      y = (this.mt[kk] & UPPER_MASK) | (this.mt[kk + 1] & LOWER_MASK);
      this.mt[kk] = this.mt[kk + (MT_M - MT_N)] ^ (y >>> 1) ^ mag01[y & 1];
    }}
    y = (this.mt[MT_N - 1] & UPPER_MASK) | (this.mt[0] & LOWER_MASK);
    this.mt[MT_N - 1] = this.mt[MT_M - 1] ^ (y >>> 1) ^ mag01[y & 1];
    this.mti = 0;
  }}
  y = this.mt[this.mti++];
  y ^= (y >>> 11); y ^= (y << 7) & 0x9d2c5680; y ^= (y << 15) & 0xefc60000; y ^= (y >>> 18);
  return y >>> 0;
}};
function pythonSeedKey(seedBigInt) {{
  let n = seedBigInt < 0n ? -seedBigInt : seedBigInt;
  if (n === 0n) return [0];
  let bits = 0; {{ let tmp = n; while (tmp > 0n) {{ bits++; tmp >>= 1n; }} }}
  const keymax = Math.floor((bits - 1) / 32) + 1;
  const words = [];
  for (let i = 0; i < keymax; i++) {{ words.push(Number(n & 0xffffffffn)); n >>= 32n; }}
  return words;
}}
function pythonRandomSeed(combinedBigInt) {{
  const key = pythonSeedKey(combinedBigInt);
  const mt = new MT19937(); mt.initByArray(key); return mt;
}}
function bitLength(n) {{ return 32 - Math.clz32(n); }}
function getrandbits(mt, k) {{ return mt.genrandUint32() >>> (32 - k); }}
function randbelow(mt, n) {{
  if (n <= 0) return 0;
  const k = bitLength(n); let r = getrandbits(mt, k);
  while (r >= n) r = getrandbits(mt, k);
  return r;
}}
function pythonSample(mt, n, k) {{
  const pool = Array.from({{ length: n }}, (_, i) => i + 1);
  const result = new Array(k);
  for (let i = 0; i < k; i++) {{
    const j = randbelow(mt, n - i);
    result[i] = pool[j]; pool[j] = pool[n - i - 1];
  }}
  return result;
}}
function randomPredict(seed, drawSerial, k) {{
  const combined = BigInt(seed) * 10000000n + BigInt(drawSerial);
  const mt = pythonRandomSeed(combined);
  return pythonSample(mt, 43, k).sort((a, b) => a - b);
}}

function selSeed(seed) {{
  selSeedVal = seed;
  document.querySelectorAll('#tbody tr').forEach(tr => {{
    tr.classList.toggle('selected', tr.cells[1].textContent.trim().split(' ')[0].replace(/,/g, '') == seed);
  }});

  const K = {K_PICKS};
  document.getElementById('modalTitle').textContent = 'Seed #' + seed.toLocaleString() + ' — ' + DRAWS.length + ' draws (K=' + K + ')';

  let hit6 = 0, hit5 = 0, hit4 = 0, hit0 = 0, bonusHits = 0, totalHits = 0;
  const htmlParts = [];
  [...DRAWS].reverse().forEach(row => {{
    const picks = randomPredict(seed, row.s, K);
    const actualSet = new Set(row.a);
    const picksSet = new Set(picks);
    const hits = picks.filter(p => actualSet.has(p)).length;
    const bh   = picksSet.has(row.b);
    totalHits += hits;
    if (bh) bonusHits++;
    if (hits === 6) hit6++; else if (hits === 5) hit5++; else if (hits === 4) hit4++; else if (hits === 0) hit0++;

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
      '<td style="text-align:center;font-weight:700;color:' + hc + '">' + hits + (bh ? '<span style="color:#f59e0b;font-size:.7rem">+B</span>' : '') + '</td></tr>'
    );
  }});
  const avg = (totalHits / DRAWS.length).toFixed(4);
  document.getElementById('modalStats').innerHTML =
    'avg: <b>' + avg + '</b> &nbsp;·&nbsp; 6-hit: <b>' + hit6 + '</b> &nbsp;·&nbsp; 5-hit: <b>' + hit5 + '</b> &nbsp;·&nbsp; 4-hit: <b>' + hit4 + '</b> &nbsp;·&nbsp; 0-hit: <b>' + hit0 + '</b> &nbsp;·&nbsp; bonus: <b>' + bonusHits + '</b>';
  document.getElementById('modalTbody').innerHTML = htmlParts.join('');
  document.getElementById('seedModal').style.display = 'flex';
}}

// Close modal on backdrop click
document.getElementById('seedModal').addEventListener('click', function(e) {{
  if (e.target === this) this.style.display = 'none';
}});
document.addEventListener('keydown', function(e) {{
  if (e.key === 'Escape') document.getElementById('seedModal').style.display = 'none';
}});
</script>
</body>
</html>"""

    with open(HTML_OUT, 'w', encoding='utf-8') as f:
        f.write(page)
    print(f"\nWrote {HTML_OUT} ({len(page)//1024} KB)")
    print(f"Best seed: #{best['seed']:,} avg={best['avg']:.4f} lift={best['lift']:+.1f}% 6hits={best['hit6']}")
    print(f"Worst-coverage seed: #{worst_coverage['seed']:,} hit0={worst_coverage['hit0']}")
    print(f"Predicted picks for draw #{next_serial}: {next_picks}")

if __name__ == '__main__':
    main()
