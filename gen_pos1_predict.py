"""
Generate Position-1 prediction feature and inject into position.html.
Strategy: for each test draw, look at last N position-1 numbers,
pick the 2 most frequent as predictions. Backtest 1000 draws.
"""
import psycopg2, json, re, collections

DB_URL = "postgresql://neondb_owner:npg_QbHpRZW8of3C@ep-hidden-wind-a1q0el7s-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"
HTML_PATH = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto\public\position.html"

print("Fetching draws...")
conn = psycopg2.connect(DB_URL)
cur = conn.cursor()
cur.execute("SELECT draw_serial, draw_date, num1, num2, num3, num4, num5, num6 FROM loto6_results ORDER BY draw_serial")
rows = cur.fetchall()
conn.close()

draws = [{"s": r[0], "d": str(r[1])[:10] if r[1] else "", "n": sorted([r[2],r[3],r[4],r[5],r[6],r[7]])} for r in rows]
T = len(draws)
print(f"Total draws: {T}, latest serial: {draws[-1]['s']}")

# Position 1 = draws[i]["n"][0] (smallest number)
BT_DRAWS = 1000
WINDOWS = [50, 100, 200, 500, 0]  # 0 = all history
PICK_K = 2  # how many candidates to pick

def predict_pos1(history_draws, k=2):
    """Pick k most frequent position-1 numbers from history."""
    freq = collections.Counter(d["n"][0] for d in history_draws)
    return [n for n, _ in freq.most_common(k)]

# Walk-forward backtest
test_start = T - BT_DRAWS
BT = {}
HDIST = {}  # {window: [miss_count, hit_count]}
for w in WINDOWS:
    BT[w] = []
    HDIST[w] = [0, 0]  # [miss, hit]

print(f"Running backtest over {BT_DRAWS} draws...")
for i in range(test_start, T):
    d = draws[i]
    actual_p1 = d["n"][0]
    for w in WINDOWS:
        if w == 0:
            train = draws[:i]
        else:
            start = max(0, i - w)
            train = draws[start:i]
        if len(train) < 5:
            continue
        pred = predict_pos1(train, PICK_K)
        hit = actual_p1 in pred
        HDIST[w][1 if hit else 0] += 1
        BT[w].append({
            "s": d["s"],
            "d": d["d"],
            "p1": actual_p1,
            "pr": pred,
            "hit": hit,
        })

print("\nBacktest results:")
for w in WINDOWS:
    label = f"last {w}" if w else "all-time"
    total = sum(HDIST[w])
    hit_rate = HDIST[w][1] / total if total else 0
    rand = PICK_K / 43
    lift = hit_rate / rand if rand else 0
    pred_now = predict_pos1(draws if w == 0 else draws[max(0, T-w):], PICK_K)
    print(f"  {label}: hit_rate={hit_rate:.3f} ({HDIST[w][1]}/{total})  rand={rand:.3f}  lift={lift:.3f}x  pred={pred_now}")

# Current predictions
CURRENT = {}
for w in WINDOWS:
    train = draws if w == 0 else draws[max(0, T-w):]
    CURRENT[str(w)] = predict_pos1(train, PICK_K)

# Recent position-1 history (last 30 draws for sparkline)
P1_HISTORY = [{"s": d["s"], "v": d["n"][0]} for d in draws[-30:]]

# All-time frequency of each number at position 1
P1_FREQ_ALL = [0] * 43
for d in draws:
    P1_FREQ_ALL[d["n"][0] - 1] += 1

out = {
    "windows": WINDOWS,
    "bt": {str(w): list(reversed(BT[w]))[:200] for w in WINDOWS},
    "hdist": {str(w): HDIST[w] for w in WINDOWS},
    "current": CURRENT,
    "pickK": PICK_K,
    "p1History": P1_HISTORY,
    "p1FreqAll": P1_FREQ_ALL,
    "totalDraws": T,
    "btDraws": BT_DRAWS,
    "latestSerial": draws[-1]["s"],
    "latestDate": draws[-1]["d"],
}

json_str = json.dumps(out, separators=(",",":"))
print(f"\nJSON size: {len(json_str):,} bytes")

# ── Patch position.html ───────────────────────────────────────────────────────
with open(HTML_PATH, encoding="utf-8") as f:
    html = f.read()

# Check if already patched
if 'id="tab-pos1pred"' in html:
    print("Already patched — removing old inject first")
    # Remove old pos1pred panel
    html = re.sub(r'<!-- TAB: POS1 PREDICT -->.*?<!-- END TAB: POS1 PREDICT -->', '', html, flags=re.DOTALL)
    html = re.sub(r'// POS1PRED_START.*?// POS1PRED_END', '', html, flags=re.DOTALL)
    html = re.sub(r'\s*<div class="tab" onclick="showTab\(\'pos1pred\'.*?</div>', '', html)

# 1. Update badge
html = re.sub(r'<span class="badge">\d+ draws</span>',
              f'<span class="badge">{T} draws</span>', html)

# 2. Add tab button before </nav>
NEW_TAB_BTN = '  <div class="tab" onclick="showTab(\'pos1pred\',this)">Pos-1 Predict</div>\n</nav>'
html = html.replace('</nav>', NEW_TAB_BTN, 1)

# 3. CSS
POS1_CSS = """
/* ---- Pos-1 Predict tab ---- */
.p1-section{margin-bottom:24px}
.p1-title{font-size:.82rem;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:.05em;margin-bottom:10px}
.p1-wbtns{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:16px}
.p1-wbtn{padding:5px 14px;border-radius:6px;cursor:pointer;font-size:.8rem;color:#94a3b8;border:1px solid #334155;background:#1e293b;transition:.15s}
.p1-wbtn:hover{color:#e2e8f0;background:#334155}
.p1-wbtn.active{color:#fff;border-color:#38bdf8;background:#0369a155}
.p1-picks{display:flex;gap:14px;align-items:center;margin-bottom:20px;flex-wrap:wrap}
.p1-pick-ball{width:56px;height:56px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:1.2rem;font-weight:800;box-shadow:0 2px 12px #0006}
.p1b-1{background:linear-gradient(135deg,#1d4ed8,#3b82f6);color:#bae6fd}
.p1b-2{background:linear-gradient(135deg,#0f766e,#14b8a6);color:#ccfbf1}
.p1-pick-label{font-size:.78rem;color:#94a3b8;margin-top:4px;text-align:center}
.p1-stat-row{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:16px}
.p1-stat{background:#1e293b;border-radius:8px;padding:10px 16px;min-width:110px}
.p1-stat .v{font-size:1.3rem;font-weight:800;color:#f1f5f9}
.p1-stat .l{font-size:.72rem;color:#64748b;margin-top:2px}
.p1-freq-grid{display:flex;flex-wrap:wrap;gap:4px;margin-bottom:20px}
.p1-freq-cell{width:40px;height:40px;border-radius:6px;display:flex;flex-direction:column;align-items:center;justify-content:center;font-size:.72rem;font-weight:700;cursor:default;border:2px solid transparent;transition:.15s}
.p1-freq-cell.pred-pick{border-color:#38bdf8;box-shadow:0 0 8px #38bdf855}
.p1-fc-num{font-size:.8rem;font-weight:800}
.p1-fc-cnt{font-size:.62rem;font-weight:400;opacity:.7}
.p1-sparkline{display:flex;gap:3px;align-items:flex-end;height:50px;padding:4px 0;margin-bottom:6px}
.p1-spark-bar{border-radius:2px 2px 0 0;flex:1;background:#334155;min-height:3px;cursor:pointer;position:relative}
.p1-spark-bar.pred-pick{background:#38bdf8}
.p1-bt-tbl{width:100%;border-collapse:collapse;font-size:.8rem}
.p1-bt-tbl th{background:#1e293b;padding:6px 8px;color:#94a3b8;font-size:.72rem;font-weight:600;text-align:left;position:sticky;top:0}
.p1-bt-tbl td{padding:5px 8px;border-bottom:1px solid #0f172a}
.p1-bt-tbl tr:hover td{background:#1e3a5f22}
.p1-bt-tbl tr.hit td:first-child{border-left:3px solid #22c55e}
.p1-bt-tbl tr.miss td:first-child{border-left:3px solid #ef444488}
.p1-bt-wrap{max-height:460px;overflow-y:auto;border-radius:8px}
"""
html = html.replace("</style>", POS1_CSS + "\n</style>")

# 4. Panel HTML
POS1_PANEL = """
<!-- TAB: POS1 PREDICT -->
<div id="tab-pos1pred" class="panel">
  <p class="section-title">
    For each draw, the 2 most frequent <strong>Position-1</strong> numbers (= smallest drawn number)
    in the selected recent window are chosen as predictions. Backtest checks if either matches the actual Pos-1.
  </p>

  <div class="p1-section">
    <div class="p1-title">Window</div>
    <div class="p1-wbtns" id="p1WBtns"></div>
  </div>

  <div class="p1-section">
    <div class="p1-title">Next Draw Prediction — Position 1</div>
    <div class="p1-picks" id="p1Picks"></div>
  </div>

  <div class="p1-section">
    <div class="p1-title">All-time Frequency at Position 1</div>
    <div class="p1-freq-grid" id="p1FreqGrid"></div>
  </div>

  <div class="p1-section">
    <div class="p1-title">Recent Position-1 Sequence (last 30 draws)</div>
    <div class="p1-sparkline" id="p1Spark"></div>
    <div style="font-size:.72rem;color:#64748b">Teal bar = current prediction pick</div>
  </div>

  <div class="p1-section">
    <div class="p1-title">Backtest — last 1000 draws</div>
    <div class="p1-stat-row" id="p1Stats"></div>
  </div>

  <div class="p1-section">
    <div class="p1-title">Recent Draws</div>
    <div class="p1-bt-wrap"><table class="p1-bt-tbl">
      <thead><tr><th>Draw</th><th>Date</th><th>Actual P1</th><th>Predictions</th><th>Result</th></tr></thead>
      <tbody id="p1BtBody"></tbody>
    </table></div>
  </div>
</div>
<!-- END TAB: POS1 PREDICT -->
"""
html = html.replace("</main>", POS1_PANEL + "\n</main>")

# 5. JS
POS1_JS = f"""
// POS1PRED_START
(function(){{
const P1D = {json_str};
let p1ActiveW = {out["windows"][1]};  // default = last 100

function renderP1() {{
  const wKey = String(p1ActiveW);
  const winLabel = p1ActiveW === 0 ? 'All-time' : 'Last ' + p1ActiveW;

  // Window buttons
  const wDiv = document.getElementById('p1WBtns');
  wDiv.innerHTML = '';
  P1D.windows.forEach(w => {{
    const b = document.createElement('div');
    b.className = 'p1-wbtn' + (w === p1ActiveW ? ' active' : '');
    b.textContent = w === 0 ? 'All-time' : 'Last ' + w;
    b.onclick = () => {{ p1ActiveW = w; renderP1(); }};
    wDiv.appendChild(b);
  }});

  // Current picks
  const picks = P1D.current[wKey] || [];
  const pickSet = new Set(picks);
  document.getElementById('p1Picks').innerHTML =
    picks.map((n,i) => `<div style="text-align:center">
      <div class="p1-pick-ball p1b-${{i+1}}">${{n}}</div>
      <div class="p1-pick-label">Pick ${{i+1}}</div>
    </div>`).join('') +
    `<div style="color:#64748b;font-size:.82rem;margin-left:8px">for draw #${{P1D.latestSerial+1}}<br>${{winLabel}} window</div>`;

  // Frequency grid (all-time, highlight picks)
  const maxF = Math.max(...P1D.p1FreqAll);
  document.getElementById('p1FreqGrid').innerHTML = P1D.p1FreqAll.map((cnt,i) => {{
    const n = i+1;
    const isPick = pickSet.has(n);
    const alpha = 0.1 + 0.75*(cnt/maxF);
    const bg = isPick ? `rgba(56,189,248,${{alpha}})` : `rgba(99,102,241,${{alpha}})`;
    return `<div class="p1-freq-cell${{isPick?' pred-pick':''}}" style="background:${{bg}}" title="No.${{n}}: ${{cnt}} times at Pos 1">
      <div class="p1-fc-num">${{n}}</div><div class="p1-fc-cnt">${{cnt}}</div>
    </div>`;
  }}).join('');

  // Sparkline of recent pos-1 sequence
  const hist = P1D.p1History;
  const maxV = Math.max(...hist.map(h=>h.v));
  document.getElementById('p1Spark').innerHTML = hist.map(h => {{
    const isPick = pickSet.has(h.v);
    const ht = Math.round(4 + (h.v / maxV) * 40);
    return `<div class="p1-spark-bar${{isPick?' pred-pick':''}}" style="height:${{ht}}px" title="Draw #${{h.s}}: Pos1=${{h.v}}"></div>`;
  }}).join('');

  // Stats
  const bt = P1D.bt[wKey] || [];
  const hdist = P1D.hdist[wKey] || [0,0];
  const total = hdist[0]+hdist[1];
  const hitRate = total ? hdist[1]/total : 0;
  const rand = P1D.pickK/43;
  const lift = rand ? (hitRate/rand) : 0;
  document.getElementById('p1Stats').innerHTML = `
    <div class="p1-stat"><div class="v">${{(hitRate*100).toFixed(1)}}%</div><div class="l">Hit rate (2 picks vs Pos 1)</div></div>
    <div class="p1-stat"><div class="v">${{(rand*100).toFixed(1)}}%</div><div class="l">Random baseline (2/43)</div></div>
    <div class="p1-stat"><div class="v">${{lift.toFixed(3)}}×</div><div class="l">Lift vs random</div></div>
    <div class="p1-stat"><div class="v">${{hdist[1]}}</div><div class="l">Hits / ${{total}} draws</div></div>
    <div class="p1-stat"><div class="v">${{hdist[0]}}</div><div class="l">Misses</div></div>`;

  // Table
  const tbody = document.getElementById('p1BtBody');
  tbody.innerHTML = '';
  bt.slice(0,150).forEach(e => {{
    const tr = document.createElement('tr');
    tr.className = e.hit ? 'hit' : 'miss';
    const predChips = e.pr.map((n,i) => {{
      const isHit = n === e.p1;
      return `<span class="pred-chip ${{isHit?'pc-hit':'pc-miss'}}">${{n}}</span>`;
    }}).join(' ');
    const p1Ball = `<span class="ball b-norm${{e.hit?' b-hit':''}}">${{e.p1}}</span>`;
    tr.innerHTML = `<td>#${{e.s}}</td><td>${{e.d}}</td><td>${{p1Ball}}</td><td>${{predChips}}</td>
      <td style="color:${{e.hit?'#22c55e':'#ef4444'}};font-weight:700">${{e.hit?'✓ HIT':'✗ MISS'}}</td>`;
    tbody.appendChild(tr);
  }});
}}

// Hook into tab switching
const _p1origShow = window.showTab;
window.showTab = function(id, el) {{
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  const panel = document.getElementById('tab-'+id);
  if(panel) panel.classList.add('active');
  if(el) el.classList.add('active');
  if(id === 'pos1pred') renderP1();
}};
}})();
// POS1PRED_END
"""
html = html.replace("</body>", POS1_JS + "\n</body>")

with open(HTML_PATH, "w", encoding="utf-8") as f:
    f.write(html)

print(f"Saved. HTML size: {len(html):,} bytes")
