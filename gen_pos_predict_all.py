"""
Generate pos_predict.html — Position 1-6 prediction, each as a tab.
For each position (smallest→largest), pick 2 most-frequent numbers as prediction.
Walk-forward backtest 1000 draws. Shows frequency grid, sparkline, backtest table.
"""
import psycopg2, json, collections

DB_URL = "postgresql://neondb_owner:npg_QbHpRZW8of3C@ep-hidden-wind-a1q0el7s-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"
OUT_PATH = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto\public\pos_predict.html"

BT_DRAWS = 1000
WINDOWS  = [50, 100, 200, 500, 0]
PICK_K   = 2

POS_META = [
    {"idx": 0, "label": "Position 1", "short": "Pos 1", "desc": "Smallest number drawn",  "color": "#6366f1"},
    {"idx": 1, "label": "Position 2", "short": "Pos 2", "desc": "2nd smallest number",    "color": "#3b82f6"},
    {"idx": 2, "label": "Position 3", "short": "Pos 3", "desc": "3rd number (mid-low)",   "color": "#14b8a6"},
    {"idx": 3, "label": "Position 4", "short": "Pos 4", "desc": "4th number (mid-high)",  "color": "#22c55e"},
    {"idx": 4, "label": "Position 5", "short": "Pos 5", "desc": "5th largest number",     "color": "#f59e0b"},
    {"idx": 5, "label": "Position 6", "short": "Pos 6", "desc": "Largest number drawn",   "color": "#ef4444"},
]

print("Fetching draws...")
conn = psycopg2.connect(DB_URL)
cur  = conn.cursor()
cur.execute("SELECT draw_serial, draw_date, num1,num2,num3,num4,num5,num6 FROM loto6_results ORDER BY draw_serial")
rows = cur.fetchall()
conn.close()

draws = [{"s": r[0], "d": str(r[1])[:10] if r[1] else "",
          "n": sorted([r[2],r[3],r[4],r[5],r[6],r[7]])} for r in rows]
T = len(draws)
test_start = T - BT_DRAWS
print(f"Total: {T} draws, testing last {BT_DRAWS}")

def compute_position(pos_idx):
    """Compute all data for one position index (0-5)."""
    label = POS_META[pos_idx]["label"]

    # Walk-forward backtest
    bt      = {w: [] for w in WINDOWS}
    hdist   = {w: [0, 0] for w in WINDOWS}

    for i in range(test_start, T):
        actual = draws[i]["n"][pos_idx]
        for w in WINDOWS:
            train = draws[:i] if w == 0 else draws[max(0, i-w):i]
            if len(train) < 5:
                continue
            freq = collections.Counter(d["n"][pos_idx] for d in train)
            pred = [n for n, _ in freq.most_common(PICK_K)]
            hit  = actual in pred
            hdist[w][1 if hit else 0] += 1
            bt[w].append({"s": draws[i]["s"], "d": draws[i]["d"],
                          "v": actual, "pr": pred, "hit": hit})

    # Current prediction per window
    current = {}
    for w in WINDOWS:
        train = draws if w == 0 else draws[max(0, T-w):]
        freq  = collections.Counter(d["n"][pos_idx] for d in train)
        current[str(w)] = [n for n, _ in freq.most_common(PICK_K)]

    # All-time frequency at this position
    freq_all = [0] * 43
    for d in draws:
        freq_all[d["n"][pos_idx] - 1] += 1

    # Recent 30-draw history
    history = [{"s": d["s"], "v": d["n"][pos_idx]} for d in draws[-30:]]

    # Stats summary per window
    stats = {}
    for w in WINDOWS:
        total   = sum(hdist[w])
        hit_rate = hdist[w][1] / total if total else 0
        rand    = PICK_K / 43
        lift    = hit_rate / rand if rand else 0
        stats[str(w)] = {"hitRate": round(hit_rate, 4), "rand": round(rand, 4),
                         "lift": round(lift, 4), "hits": hdist[w][1], "total": total}
        wl = "all-time" if w == 0 else f"last {w}"
        print(f"  {label} {wl}: hit={hit_rate:.3f}  lift={lift:.3f}x  pred={current[str(w)]}")

    return {
        "windows": WINDOWS,
        "bt":      {str(w): list(reversed(bt[w]))[:200] for w in WINDOWS},
        "hdist":   {str(w): hdist[w] for w in WINDOWS},
        "current": current,
        "stats":   stats,
        "freqAll": freq_all,
        "history": history,
        "pickK":   PICK_K,
    }

POS_DATA = []
for pm in POS_META:
    print(f"\n{pm['label']}:")
    POS_DATA.append(compute_position(pm["idx"]))

DATA = {
    "posMeta":     POS_META,
    "posData":     POS_DATA,
    "totalDraws":  T,
    "btDraws":     BT_DRAWS,
    "latestSerial": draws[-1]["s"],
    "latestDate":  draws[-1]["d"],
}
DATA_JSON = json.dumps(DATA, separators=(",", ":"))
print(f"\nJSON size: {len(DATA_JSON):,} bytes")

# ── HTML ──────────────────────────────────────────────────────────────────────
NAV_HTML = """<nav class="site-nav">
  <a class="nav-logo" href="/">🎱 The<span>One</span>Lotto</a>
  <div class="nav-groups">
    <div class="nav-group">
      <div class="nav-group-btn">Data <span class="arrow">▼</span></div>
      <div class="nav-dropdown">
        <div class="nav-dd-label">Results</div>
        <a href="/">🏠 Latest Draw</a>
        <a href="/history">📋 History</a>
        <a href="/numbers">🔢 Numbers</a>
      </div>
    </div>
    <div class="nav-group">
      <div class="nav-group-btn">Predict <span class="arrow">▼</span></div>
      <div class="nav-dropdown">
        <div class="nav-dd-label">Prediction Tools</div>
        <a href="/predictions">🎯 Predictions</a>
        <a href="/backtest.html">📊 Backtest</a>
        <a href="/combo_evo.html">🧬 Combo Evo</a>
        <div class="nav-divider"></div>
        <div class="nav-dd-label">Strategy</div>
        <a href="/overdue.html">⏳ Overdue</a>
        <a href="/miss_analysis.html">❌ Miss Analysis</a>
        <a href="/state_machine.html">🔄 State Machine</a>
      </div>
    </div>
    <div class="nav-group">
      <div class="nav-group-btn">Analyze <span class="arrow">▼</span></div>
      <div class="nav-dropdown">
        <div class="nav-dd-label">Pattern Analysis</div>
        <a href="/special.html">⭐ Special</a>
        <a href="/consecutive.html">🔗 Consecutive</a>
        <div class="nav-divider"></div>
        <div class="nav-dd-label">Position</div>
        <a href="/position.html">📍 Position Freq</a>
        <a href="/position.html#pos1pred">🎯 Pos-1 Predict</a>
        <a href="/pos_predict.html" class="active">📊 Pos 1–6 Predict</a>
      </div>
    </div>
  </div>
</nav>"""

HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Position Prediction — Loto 6</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:system-ui,sans-serif;background:#0f172a;color:#e2e8f0;min-height:100vh;padding-top:52px}}

/* ── NAV ── */
.site-nav{{position:fixed;top:0;left:0;right:0;height:52px;background:#0a0f1e;
  border-bottom:1px solid #1e293b;display:flex;align-items:center;padding:0 20px;
  gap:0;z-index:9999;box-shadow:0 2px 16px rgba(0,0,0,.6)}}
.site-nav .nav-logo{{font-size:1rem;font-weight:800;color:#f1f5f9;text-decoration:none;white-space:nowrap;margin-right:24px;flex-shrink:0}}
.site-nav .nav-logo span{{color:#38bdf8}}
.nav-groups{{display:flex;gap:4px;align-items:center}}
.nav-group{{position:relative}}
.nav-group-btn{{display:flex;align-items:center;gap:5px;padding:7px 14px;border-radius:7px;
  cursor:pointer;font-size:.82rem;font-weight:600;color:#94a3b8;
  border:1px solid transparent;transition:.15s;white-space:nowrap;user-select:none}}
.nav-group-btn:hover,.nav-group:hover .nav-group-btn{{color:#f1f5f9;background:#1e293b;border-color:#334155}}
.nav-group-btn .arrow{{font-size:.6rem;opacity:.6;transition:transform .2s}}
.nav-group:hover .nav-group-btn .arrow{{transform:rotate(180deg)}}
.nav-dropdown{{display:none;position:absolute;top:calc(100% + 6px);left:0;
  background:#0d1526;border:1px solid #1e293b;border-radius:10px;
  min-width:175px;padding:6px;box-shadow:0 12px 32px rgba(0,0,0,.7);z-index:10000}}
.nav-group:hover .nav-dropdown{{display:block}}
.nav-dropdown a{{display:flex;align-items:center;gap:8px;padding:8px 12px;
  border-radius:6px;color:#94a3b8;text-decoration:none;font-size:.82rem;white-space:nowrap;transition:.12s}}
.nav-dropdown a:hover,.nav-dropdown a.active{{color:#f1f5f9;background:#1e293b}}
.nav-dd-label{{font-size:.68rem;font-weight:700;color:#475569;padding:6px 12px 2px;text-transform:uppercase;letter-spacing:.06em}}
.nav-divider{{height:1px;background:#1e293b;margin:4px 0}}

/* ── LAYOUT ── */
main{{max-width:1100px;margin:0 auto;padding:24px 20px}}
h1{{font-size:1.4rem;font-weight:800;color:#f1f5f9;margin-bottom:4px}}
.subtitle{{font-size:.85rem;color:#64748b;margin-bottom:20px}}
.sec{{margin-bottom:28px}}
.sec-title{{font-size:.78rem;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:.06em;margin-bottom:10px}}

/* ── POS TABS (outer) ── */
.pos-tabs{{display:flex;gap:0;margin-bottom:0;border-bottom:2px solid #1e293b;overflow-x:auto;scrollbar-width:none}}
.pos-tabs::-webkit-scrollbar{{display:none}}
.pos-tab{{padding:10px 20px;cursor:pointer;font-size:.84rem;font-weight:700;color:#64748b;
  border-radius:8px 8px 0 0;border:1px solid transparent;border-bottom:none;
  transition:.15s;white-space:nowrap;margin-bottom:-2px;flex-shrink:0}}
.pos-tab:hover{{color:#94a3b8;background:#1e293b22}}
.pos-tab.active{{color:#f1f5f9;border-color:#1e293b;border-bottom:2px solid #0f172a}}
.pos-panel{{display:none;padding-top:20px}}.pos-panel.active{{display:block}}

/* ── INNER WINDOW TABS ── */
.win-tabs{{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:16px}}
.win-btn{{padding:5px 14px;border-radius:6px;cursor:pointer;font-size:.8rem;color:#94a3b8;
  border:1px solid #334155;background:#1e293b;transition:.15s}}
.win-btn:hover{{color:#e2e8f0;background:#334155}}
.win-btn.active{{color:#fff;border-color:var(--c);background:color-mix(in srgb,var(--c) 20%,transparent)}}

/* ── PREDICTION BALLS ── */
.picks-row{{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-bottom:20px}}
.pick-ball{{width:56px;height:56px;border-radius:50%;display:flex;align-items:center;justify-content:center;
  font-size:1.15rem;font-weight:800;box-shadow:0 2px 12px #0006;color:#fff}}
.pick-lbl{{font-size:.75rem;color:#94a3b8;margin-top:4px;text-align:center}}

/* ── STATS ROW ── */
.stats-row{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px}}
.stat-box{{background:#1e293b;border-radius:8px;padding:9px 16px;min-width:100px}}
.stat-box .sv{{font-size:1.25rem;font-weight:800;color:#f1f5f9}}
.stat-box .sl{{font-size:.7rem;color:#64748b;margin-top:1px}}

/* ── FREQ GRID ── */
.freq-grid{{display:flex;flex-wrap:wrap;gap:4px;margin-bottom:20px}}
.freq-cell{{width:40px;height:40px;border-radius:6px;display:flex;flex-direction:column;align-items:center;
  justify-content:center;cursor:default;border:2px solid transparent;transition:.15s}}
.freq-cell.pick{{border-color:var(--c);box-shadow:0 0 8px color-mix(in srgb,var(--c) 55%,transparent)}}
.fc-num{{font-size:.8rem;font-weight:800}}
.fc-cnt{{font-size:.62rem;opacity:.7}}

/* ── SPARKLINE ── */
.spark{{display:flex;gap:3px;align-items:flex-end;height:52px;padding:4px 0;margin-bottom:6px}}
.spark-bar{{border-radius:2px 2px 0 0;flex:1;background:#334155;min-height:3px;cursor:pointer}}
.spark-bar.pick{{background:var(--c)}}

/* ── BT TABLE ── */
.bt-wrap{{max-height:440px;overflow-y:auto;border-radius:8px}}
.bt-tbl{{width:100%;border-collapse:collapse;font-size:.8rem}}
.bt-tbl th{{background:#1e293b;padding:6px 8px;color:#94a3b8;font-size:.72rem;font-weight:600;
  text-align:left;position:sticky;top:0;z-index:2}}
.bt-tbl td{{padding:5px 8px;border-bottom:1px solid #0f172a;vertical-align:middle}}
.bt-tbl tr.hit td:first-child{{border-left:3px solid #22c55e}}
.bt-tbl tr.miss td:first-child{{border-left:3px solid #ef444488}}
.bt-tbl tr:hover td{{background:#1e3a5f22}}
.v-ball{{display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;
  border-radius:50%;font-size:.78rem;font-weight:700;background:#1e3a5f;color:#93c5fd}}
.v-ball.bh{{border:2px solid #22c55e;background:#0c2e1f;color:#4ade80}}
.pchip{{display:inline-flex;align-items:center;justify-content:center;min-width:28px;height:22px;
  border-radius:5px;font-size:.78rem;font-weight:700;padding:0 5px;margin:1px}}
.pc-hit{{background:#14532d;color:#4ade80;border:1px solid #4ade80}}
.pc-miss{{background:#1e293b;color:#64748b;border:1px solid #334155}}

/* ── COMPARISON STRIP ── */
.cmp-strip{{display:grid;grid-template-columns:repeat(6,1fr);gap:8px;margin-bottom:24px}}
.cmp-card{{background:#1e293b;border-radius:10px;padding:12px;text-align:center;border-top:3px solid;cursor:pointer;transition:.15s}}
.cmp-card:hover{{background:#263548}}
.cmp-card h3{{font-size:.82rem;font-weight:700;margin-bottom:6px}}
.cmp-card .cv{{font-size:1.1rem;font-weight:800}}
.cmp-card .cl{{font-size:.7rem;color:#64748b;margin-top:2px}}
.cmp-card .pn{{font-size:.72rem;margin-top:8px;color:#94a3b8}}
.cmp-card .balls{{display:flex;justify-content:center;gap:4px;margin-top:8px;flex-wrap:wrap}}
.sm-ball{{width:32px;height:32px;border-radius:50%;display:flex;align-items:center;justify-content:center;
  font-size:.78rem;font-weight:800;color:#fff}}

@media(max-width:640px){{
  .cmp-strip{{grid-template-columns:repeat(3,1fr)}}
  .pos-tab{{padding:8px 14px;font-size:.78rem}}
}}
</style>
</head>
<body>
{NAV_HTML}
<main>
  <h1>📊 Position Prediction</h1>
  <p class="subtitle">For each position (smallest→largest in a draw), pick the 2 most-frequent historical numbers. Backtest: 1000 draws, walk-forward.</p>

  <!-- Summary strip (click to switch tab) -->
  <div class="sec">
    <div class="sec-title">All Positions — Current Predictions (Last-100 window)</div>
    <div class="cmp-strip" id="cmpStrip"></div>
  </div>

  <!-- Position tabs -->
  <div class="pos-tabs" id="posTabs"></div>
  <div id="posPanels"></div>
</main>

<script>
const D = {DATA_JSON};

function hexRgba(h, a) {{
  const r=parseInt(h.slice(1,3),16),g=parseInt(h.slice(3,5),16),b=parseInt(h.slice(5,7),16);
  return `rgba(${{r}},${{g}},${{b}},${{a}})`;
}}

// ── Summary strip ────────────────────────────────────────────────
const strip = document.getElementById('cmpStrip');
D.posMeta.forEach((pm, pi) => {{
  const pd = D.posData[pi];
  const w = 100;  // default window
  const pred = pd.current[String(w)] || [];
  const stats = pd.stats[String(w)] || {{}};
  const card = document.createElement('div');
  card.className = 'cmp-card';
  card.style.borderColor = pm.color;
  card.style.setProperty('--c', pm.color);
  card.innerHTML = `
    <h3 style="color:${{pm.color}}">${{pm.short}}</h3>
    <div class="cv">${{(stats.hitRate*100||0).toFixed(1)}}%</div>
    <div class="cl">hit rate · ${{(stats.lift||0).toFixed(2)}}× lift</div>
    <div class="pn">Predict #${{D.latestSerial+1}}</div>
    <div class="balls">${{pred.map(n=>`<div class="sm-ball" style="background:${{hexRgba(pm.color,.8)}}">${{n}}</div>`).join('')}}</div>`;
  card.onclick = () => activatePos(pi);
  strip.appendChild(card);
}});

// ── Build tabs & panels ──────────────────────────────────────────
const tabsEl   = document.getElementById('posTabs');
const panelsEl = document.getElementById('posPanels');

function activatePos(pi) {{
  document.querySelectorAll('.pos-tab').forEach((t,i) => t.classList.toggle('active', i===pi));
  document.querySelectorAll('.pos-panel').forEach((p,i) => p.classList.toggle('active', i===pi));
  // Style active tab border
  document.querySelectorAll('.pos-tab').forEach((t,i) => {{
    t.style.borderTopColor = i===pi ? D.posMeta[i].color : 'transparent';
    t.style.color = i===pi ? D.posMeta[i].color : '';
  }});
}}

D.posMeta.forEach((pm, pi) => {{
  const pd = D.posData[pi];

  // Tab button
  const tab = document.createElement('div');
  tab.className = 'pos-tab' + (pi===0?' active':'');
  tab.textContent = pm.short;
  tab.style.setProperty('--c', pm.color);
  if(pi===0) {{ tab.style.borderTopColor=pm.color; tab.style.color=pm.color; }}
  tab.onclick = () => activatePos(pi);
  tabsEl.appendChild(tab);

  // Panel
  const panel = document.createElement('div');
  panel.className = 'pos-panel' + (pi===0?' active':'');
  panel.style.setProperty('--c', pm.color);
  panel.innerHTML = buildPanelHTML(pm, pi);
  panelsEl.appendChild(panel);

  // Render with default window
  renderPos(pi, pd.windows[1]);
}});

function buildPanelHTML(pm, pi) {{
  return `
  <div class="sec">
    <div class="sec-title" style="color:${{pm.color}}">${{pm.label}} — ${{pm.desc}}</div>
    <div class="win-tabs" id="wtabs-${{pi}}" style="--c:${{pm.color}}"></div>
  </div>
  <div class="sec">
    <div class="sec-title">Prediction for Draw #${{D.latestSerial+1}}</div>
    <div class="picks-row" id="picks-${{pi}}"></div>
  </div>
  <div class="sec">
    <div class="sec-title">All-time Frequency at ${{pm.label}}</div>
    <div class="freq-grid" id="freq-${{pi}}" style="--c:${{pm.color}}"></div>
  </div>
  <div class="sec">
    <div class="sec-title">Recent 30-Draw Sequence at ${{pm.label}}</div>
    <div class="spark" id="spark-${{pi}}" style="--c:${{pm.color}}"></div>
    <div style="font-size:.72rem;color:#64748b">Highlighted bar = current prediction</div>
  </div>
  <div class="sec">
    <div class="sec-title">Backtest Stats — Last 1000 Draws</div>
    <div class="stats-row" id="stats-${{pi}}"></div>
  </div>
  <div class="sec">
    <div class="sec-title">Recent Draw Results</div>
    <div class="bt-wrap"><table class="bt-tbl">
      <thead><tr><th>Draw</th><th>Date</th><th>Actual ${{pm.short}}</th><th>Predicted</th><th>Result</th></tr></thead>
      <tbody id="btbody-${{pi}}"></tbody>
    </table></div>
  </div>`;
}}

function renderPos(pi, activeW) {{
  const pm = D.posMeta[pi];
  const pd = D.posData[pi];
  const wKey = String(activeW);
  const pickSet = new Set(pd.current[wKey] || []);

  // Window buttons
  const wtabs = document.getElementById(`wtabs-${{pi}}`);
  wtabs.innerHTML = '';
  pd.windows.forEach(w => {{
    const b = document.createElement('div');
    b.className = 'win-btn' + (w===activeW?' active':'');
    b.style.setProperty('--c', pm.color);
    b.textContent = w===0 ? 'All-time' : 'Last '+w;
    b.onclick = () => renderPos(pi, w);
    wtabs.appendChild(b);
  }});

  // Picks
  const picks = pd.current[wKey] || [];
  document.getElementById(`picks-${{pi}}`).innerHTML =
    picks.map((n,i) => `<div style="text-align:center">
      <div class="pick-ball" style="background:${{hexRgba(pm.color,.7+i*.1)}}">${{n}}</div>
      <div class="pick-lbl">Pick ${{i+1}}</div>
    </div>`).join('') +
    `<span style="color:#64748b;font-size:.82rem;margin-left:10px">for draw #${{D.latestSerial+1}}<br>
    (${{activeW===0?'All-time':'Last '+activeW}} window)</span>`;

  // Freq grid
  const maxF = Math.max(...pd.freqAll);
  document.getElementById(`freq-${{pi}}`).innerHTML = pd.freqAll.map((cnt,i) => {{
    const n = i+1;
    const isPick = pickSet.has(n);
    const alpha = 0.08 + 0.72*(cnt/maxF);
    const bg = hexRgba(pm.color, alpha);
    return `<div class="freq-cell${{isPick?' pick':''}}" style="background:${{bg}}" title="#${{n}}: ${{cnt}} times at ${{pm.short}}">
      <div class="fc-num">${{n}}</div><div class="fc-cnt">${{cnt}}</div>
    </div>`;
  }}).join('');

  // Sparkline
  const hist = pd.history;
  const maxV = Math.max(...hist.map(h=>h.v));
  const minV = Math.min(...hist.map(h=>h.v));
  const range = maxV - minV || 1;
  document.getElementById(`spark-${{pi}}`).innerHTML = hist.map(h => {{
    const ht = Math.round(6 + ((h.v - minV) / range) * 40);
    return `<div class="spark-bar${{pickSet.has(h.v)?' pick':''}}" style="height:${{ht}}px"
      title="Draw #${{h.s}}: ${{pm.short}}=${{h.v}}"></div>`;
  }}).join('');

  // Stats
  const stats = pd.stats[wKey] || {{}};
  document.getElementById(`stats-${{pi}}`).innerHTML = `
    <div class="stat-box"><div class="sv">${{(stats.hitRate*100||0).toFixed(1)}}%</div><div class="sl">Hit rate (2 picks)</div></div>
    <div class="stat-box"><div class="sv">${{(stats.rand*100||0).toFixed(1)}}%</div><div class="sl">Random baseline</div></div>
    <div class="stat-box"><div class="sv">${{(stats.lift||0).toFixed(3)}}×</div><div class="sl">Lift vs random</div></div>
    <div class="stat-box"><div class="sv">${{stats.hits||0}}</div><div class="sl">Hits / ${{stats.total||0}} draws</div></div>`;

  // BT table
  const tbody = document.getElementById(`btbody-${{pi}}`);
  tbody.innerHTML = '';
  (pd.bt[wKey] || []).slice(0, 120).forEach(e => {{
    const tr = document.createElement('tr');
    tr.className = e.hit ? 'hit' : 'miss';
    const ball = `<span class="v-ball${{e.hit?' bh':''}}">${{e.v}}</span>`;
    const chips = (e.pr||[]).map(n =>
      `<span class="pchip ${{n===e.v?'pc-hit':'pc-miss'}}">${{n}}</span>`
    ).join(' ');
    tr.innerHTML = `<td>#${{e.s}}</td><td>${{e.d}}</td><td>${{ball}}</td><td>${{chips}}</td>
      <td style="color:${{e.hit?'#22c55e':'#ef4444'}};font-weight:700">${{e.hit?'✓':'✗'}}</td>`;
    tbody.appendChild(tr);
  }});
}}
</script>
</body>
</html>"""

with open(OUT_PATH, "w", encoding="utf-8") as f:
    f.write(HTML)
print(f"\nWritten: {OUT_PATH} ({len(HTML):,} bytes)")
