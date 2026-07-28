"""
gen_avg_multi.py
Generates N-draw average prediction pages for N = 4..43.
Also generates avg_hub.html — a comparison table for all N = 2..43.
"""
import psycopg2, json, os, statistics

DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://neondb_owner:npg_QbHpRZW8of3C@ep-hidden-wind-a1q0el7s-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"
)

BT_DRAWS = 1000

conn = psycopg2.connect(DB_URL)
cur  = conn.cursor()
cur.execute("""
    SELECT draw_serial, draw_date, num1, num2, num3, num4, num5, num6, bonus
    FROM loto6_results ORDER BY draw_serial
""")
rows = cur.fetchall()
conn.close()

draws = []
for r in rows:
    nums = sorted([r[2], r[3], r[4], r[5], r[6], r[7]])
    draws.append({
        "s": r[0],
        "d": str(r[1])[:10] if r[1] else "",
        "n": nums,
        "b": r[8],
        "all": sorted(nums + [r[8]])
    })

N_total  = len(draws)
BASE_DIR = os.path.dirname(__file__)
PUBLIC   = os.path.join(BASE_DIR, "public")


def avg_predict_n(draw_list):
    """
    Average N draws positionally. draw_list[0]=oldest, draw_list[-1]=newest.
    Always rounds to nearest integer (no .5 expansion).
    Collisions resolved by trying adjacent values, so result is always 7 picks.
    """
    n        = len(draw_list)
    all_vals = [d["all"] for d in draw_list]
    used     = set()
    preds    = []
    raw_info = []

    for pos in range(7):
        vals = [all_vals[i][pos] for i in range(n)]
        raw  = sum(vals) / n
        v    = max(1, min(43, round(raw)))

        if v not in used:
            used.add(v)
            preds.append(v)
            raw_info.append({"raw": round(raw), "nums": [v], "vals": vals})
        else:
            # Collision: try floor/ceil then expand outward
            floor_v = max(1, min(43, int(raw)))
            ceil_v  = max(1, min(43, int(raw) + 1))
            alt = None
            for c in [floor_v, ceil_v, floor_v - 1, ceil_v + 1,
                      floor_v - 2, ceil_v + 2, floor_v - 3, ceil_v + 3]:
                c = max(1, min(43, c))
                if c not in used:
                    alt = c
                    break
            if alt is not None:
                used.add(alt)
                preds.append(alt)
                raw_info.append({"raw": round(raw), "nums": [alt], "vals": vals})

    return sorted(preds), raw_info


hub_rows     = []
next_serial  = draws[-1]["s"] + 1

for N in range(2, 44):
    print(f"N={N}...", end=" ", flush=True)
    test_start = max(N, N_total - BT_DRAWS)

    match_counts = []
    pick_counts  = []
    bt_results   = []

    for i in range(test_start, N_total):
        pred, _ = avg_predict_n(draws[i - N:i])
        hits    = set(pred) & set(draws[i]["all"])
        mc      = len(hits)
        match_counts.append(mc)
        pick_counts.append(len(pred))
        bt_results.append({
            "s": draws[i]["s"], "d": draws[i]["d"],
            "actual": draws[i]["all"],
            "hitNums": sorted(hits), "matches": mc,
            "pred": pred,
        })

    avg_picks = statistics.mean(pick_counts)
    avg       = statistics.mean(match_counts)
    rand      = avg_picks * 7 / 43
    lift      = round((avg / rand - 1) * 100, 1) if rand > 0 else 0
    c0  = sum(1 for m in match_counts if m == 0)
    c3  = sum(1 for m in match_counts if m >= 3)
    c4  = sum(1 for m in match_counts if m >= 4)
    c5  = sum(1 for m in match_counts if m >= 5)
    c6  = sum(1 for m in match_counts if m >= 6)
    c7  = sum(1 for m in match_counts if m >= 7)

    next_pred, raw_info = avg_predict_n(draws[-N:])
    src_serials         = [draws[-N + i]["s"] for i in range(N)]

    hub_rows.append({
        "n": N, "pred": next_pred, "nPicks": len(next_pred),
        "cnt6plus": c6, "cnt5plus": c5, "cnt4plus": c4, "cnt0": c0,
        "avgMatches": round(avg, 2), "randBaseline": round(rand, 2),
        "liftPct": lift, "btDraws": len(match_counts),
    })
    print(f"6+:{c6} avg:{avg:.3f} lift:{lift:+.1f}% pred:{next_pred}")

    # N=2 and N=3 have dedicated hand-crafted pages; skip HTML generation
    if N < 4:
        continue

    # ── per-page PAGE_DATA ──────────────────────────────────────────────
    PAGE_DATA = {
        "N": N,
        "nPicks": len(next_pred),
        "avgPicks": round(avg_picks, 1),
        "latestSerial": draws[-1]["s"],
        "latestDate":   draws[-1]["d"],
        "nextSerial":   next_serial,
        "prediction":   next_pred,
        "srcSerials":   src_serials,
        "rawInfo":      raw_info,
        "btDraws": len(match_counts),
        "avgMatches":   round(avg, 2),
        "randBaseline": round(rand, 2),
        "liftPct": lift,
        "cnt0": c0,
        "cnt3plus": c3, "cnt4plus": c4, "cnt5plus": c5,
        "cnt6plus": c6, "cnt7plus": c7,
        "btResults": [
            {"s": r["s"], "d": r["d"], "actual": r["actual"],
             "hitNums": r["hitNums"], "matches": r["matches"], "pred": r["pred"]}
            for r in reversed(bt_results[-100:])
        ]
    }
    data_json    = json.dumps(PAGE_DATA, ensure_ascii=False)
    expand_note  = ""

    HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{N}-Draw Average Predict -- Loto 6</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:system-ui,sans-serif;background:#0f172a;color:#e2e8f0;min-height:100vh;padding-top:60px}}
.site-nav{{position:fixed;top:0;left:0;right:0;height:52px;background:#0a0f1e;
  border-bottom:1px solid #1e293b;display:flex;align-items:center;padding:0 20px;
  gap:0;z-index:9999;box-shadow:0 2px 16px rgba(0,0,0,.6)}}
.site-nav .nav-logo{{font-size:1rem;font-weight:800;color:#f1f5f9;text-decoration:none;
  white-space:nowrap;margin-right:24px;flex-shrink:0}}
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
  background:transparent;padding-top:6px;z-index:10000;min-width:175px}}
.nav-dropdown-inner{{background:#0d1526;border:1px solid #1e293b;border-radius:10px;
  padding:6px;box-shadow:0 12px 32px rgba(0,0,0,.7);max-height:70vh;overflow-y:auto}}
.nav-group:hover .nav-dropdown{{display:block}}
.nav-dropdown a{{display:flex;align-items:center;gap:8px;padding:8px 12px;
  border-radius:6px;color:#94a3b8;text-decoration:none;font-size:.82rem;
  white-space:nowrap;transition:.12s}}
.nav-dropdown a:hover,.nav-dropdown a.active{{color:#f1f5f9;background:#1e293b}}
.nav-dd-label{{font-size:.68rem;font-weight:700;color:#475569;padding:6px 12px 2px;
  text-transform:uppercase;letter-spacing:.06em}}
.nav-divider{{height:1px;background:#1e293b;margin:4px 0}}
main{{max-width:1100px;margin:0 auto;padding:24px 20px}}
h1{{font-size:1.4rem;font-weight:800;color:#f1f5f9;margin-bottom:4px}}
.subtitle{{font-size:.85rem;color:#64748b;margin-bottom:20px}}
.sec{{margin-bottom:28px}}
.sec-title{{font-size:.78rem;font-weight:700;color:#94a3b8;text-transform:uppercase;
  letter-spacing:.06em;margin-bottom:12px}}
.method-card{{background:#1e293b;border-radius:12px;padding:16px 20px;margin-bottom:20px;
  border-left:4px solid #a78bfa}}
.method-card .mc-title{{font-size:.78rem;font-weight:700;color:#a78bfa;
  text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px}}
.method-card .mc-body{{font-size:.85rem;color:#94a3b8;line-height:1.6;margin-bottom:12px}}
.avg-table{{width:100%;border-collapse:collapse;font-size:.8rem;margin-top:10px}}
.avg-table th{{color:#475569;font-size:.68rem;text-transform:uppercase;
  letter-spacing:.06em;padding:4px 8px;text-align:left;border-bottom:1px solid #334155}}
.avg-table th.tc{{text-align:center}}
.avg-table td{{padding:5px 8px;border-bottom:1px solid #1e293b;vertical-align:middle}}
.avg-table td.pos-col{{text-align:center;font-weight:700;color:#475569;width:32px}}
.avg-table td.vals-col{{font-size:.72rem;color:#64748b;word-break:break-word;max-width:400px}}
.avg-table td.avg-col,.avg-table td.pred-col{{text-align:center;width:70px}}
.avg-num{{display:inline-flex;align-items:center;justify-content:center;
  width:30px;height:30px;border-radius:50%;font-weight:700;font-size:.78rem}}
.an-avg{{background:#334155;color:#f1f5f9}}
.an-pred{{background:#a78bfa;color:#0f172a}}
.stats-strip{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin-bottom:24px}}
.stat-card{{background:#1e293b;border-radius:10px;padding:14px 16px;text-align:center}}
.stat-card .sv{{font-size:1.6rem;font-weight:800}}
.stat-card .sl{{font-size:.72rem;color:#64748b;margin-top:2px}}
.stat-card .sd{{font-size:.78rem;margin-top:4px;color:#64748b}}
.ball-grid{{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:16px}}
.ball{{width:52px;height:52px;border-radius:50%;display:flex;align-items:center;
  justify-content:center;font-size:1.1rem;font-weight:800;color:#f1f5f9;
  background:#7c3aed;border:3px solid #a78bfa;cursor:default;transition:.12s}}
.ball:hover{{transform:scale(1.08)}}
.bt-table{{width:100%;border-collapse:collapse;font-size:.78rem}}
.bt-table th{{background:#0f172a;color:#64748b;padding:7px 10px;text-align:left;
  border-bottom:2px solid #1e293b;font-weight:600}}
.bt-table td{{padding:6px 10px;border-bottom:1px solid #1a2744}}
.bt-table tr:hover td{{background:#1a2234}}
.match-badge{{display:inline-flex;align-items:center;justify-content:center;
  width:24px;height:24px;border-radius:6px;font-weight:700;font-size:.8rem}}
.m-low{{background:#1e3a5f;color:#60a5fa}}
.m-mid{{background:#1a4731;color:#4ade80}}
.m-high{{background:#4a1d96;color:#c4b5fd}}
.m-max{{background:#78350f;color:#fbbf24}}
.hit-ball{{width:28px;height:28px;border-radius:50%;display:inline-flex;align-items:center;
  justify-content:center;font-size:.72rem;font-weight:800;margin:1px}}
.pred-mini{{width:26px;height:26px;border-radius:50%;display:inline-flex;align-items:center;
  justify-content:center;font-size:.68rem;font-weight:700;margin:1px;flex-shrink:0}}
.pm-hit{{background:#dc2626;color:#fff;box-shadow:0 0 0 2px #f87171}}
.pm-selected{{background:#e2e8f0;color:#0f172a}}
.pred-row td{{background:#0c1420;border-bottom:2px solid #1e293b}}
</style>
</head>
<body>
<nav class="site-nav">
  <a class="nav-logo" href="/">&#127500; The<span>One</span>Lotto</a>
  <div class="nav-groups">
    <div class="nav-group">
      <div class="nav-group-btn">Data <span class="arrow">&#9660;</span></div>
      <div class="nav-dropdown"><div class="nav-dropdown-inner">
        <div class="nav-dd-label">Results</div>
        <a href="/">&#127968; Latest Draw</a>
        <a href="/history">&#128203; History</a>
        <a href="/numbers">&#128290; Numbers</a>
      </div></div>
    </div>
    <div class="nav-group">
      <div class="nav-group-btn">Predict <span class="arrow">&#9660;</span></div>
      <div class="nav-dropdown"><div class="nav-dropdown-inner">
        <div class="nav-dd-label">Prediction Tools</div>
        <a href="/predictions">&#127919; Predictions</a>
        <a href="/backtest.html">&#128202; Backtest</a>
        <a href="/combo_evo.html">&#129516; Combo Evo</a>
        <div class="nav-divider"></div>
        <div class="nav-dd-label">Strategy</div>
        <a href="/overdue.html">&#9203; Overdue</a>
        <a href="/state_machine.html">&#128260; State Machine</a>
        <a href="/modular_cycle.html">&#128260; Modular Cycle</a>
        <a href="/next_relation.html">&#128279; Next Relation</a>
        <a href="/lstm_predict.html">&#129504; LSTM Neural Net</a>
        <div class="nav-divider"></div>
        <div class="nav-dd-label">N-Draw Avg</div>
        <a href="/avg_hub.html">&#11835; All N-Draw Avg (2&#8211;43)</a>
      </div></div>
    </div>
    <div class="nav-group">
      <div class="nav-group-btn">Analyze <span class="arrow">&#9660;</span></div>
      <div class="nav-dropdown"><div class="nav-dropdown-inner">
        <div class="nav-dd-label">Pattern Analysis</div>
        <a href="/special.html">&#11088; Special</a>
        <a href="/consecutive.html">&#128279; Consecutive</a>
        <div class="nav-divider"></div>
        <div class="nav-dd-label">Position</div>
        <a href="/position.html">&#128205; Position Freq</a>
        <a href="/pos_predict.html">&#128202; Pos 1&#8211;6 Predict</a>
      </div></div>
    </div>
  </div>
</nav>
<main>
  <h1>&#10133; {N}-Draw Average Predict</h1>
  <p class="subtitle">
    Average of last {N} draws by position &rarr; <span id="nPicksSub"></span> picks &middot;
    <span id="btCount"></span>-draw backtest &nbsp;|&nbsp;
    <a href="/avg_hub.html" style="color:#a78bfa">&#11835; Compare all N</a>
  </p>

  <div class="method-card">
    <div class="mc-title">Method &mdash; {N}-Draw Average</div>
    <div class="mc-body">
      Sort all 7 numbers (6 main + bonus) from each of the last {N} draws.
      Average each position across all {N} draws, round to nearest integer.{expand_note}
      Clamp to 1&ndash;43 and resolve duplicates.
    </div>
    <div style="overflow-x:auto">
      <table class="avg-table" id="avgTable"></table>
    </div>
  </div>

  <div class="sec">
    <div class="sec-title">Backtest Performance &mdash; last <span id="btCount2"></span> draws</div>
    <div class="stats-strip" id="statsStrip"></div>
  </div>

  <div class="sec">
    <div class="sec-title">Predicted <span id="nPicksTitle"></span> Numbers for Draw #<span id="nextS"></span></div>
    <div class="ball-grid" id="balls"></div>
  </div>

  <div class="sec">
    <div class="sec-title">Backtest &mdash; Last 100 Draws (newest first)</div>
    <table class="bt-table">
      <thead><tr>
        <th>Draw</th><th>Date</th><th>Actual Numbers</th><th>Hits</th><th></th>
      </tr></thead>
      <tbody id="btBody"></tbody>
    </table>
  </div>
</main>
<script>
const D = {data_json};

document.getElementById('nextS').textContent     = D.nextSerial;
document.getElementById('nPicksSub').textContent = D.nPicks;
document.getElementById('nPicksTitle').textContent = D.nPicks;
document.getElementById('btCount').textContent   = D.btDraws;
document.getElementById('btCount2').textContent  = D.btDraws;

// Method table
var tbl = document.getElementById('avgTable');
var sA  = D.srcSerials[0];
var sB  = D.srcSerials[D.srcSerials.length - 1];
tbl.innerHTML =
  '<tr><th class="tc">Pos</th>' +
  '<th>Source values &mdash; draws #' + sA + ' &ndash; #' + sB + '</th>' +
  '<th class="tc">Avg</th><th class="tc">&rarr; Predict</th></tr>';
D.rawInfo.forEach(function(row, pos) {{
  var predBalls = row.nums.map(function(n) {{
    return '<span class="avg-num an-pred">' + n + '</span>';
  }}).join(' ');
  tbl.innerHTML +=
    '<tr>' +
    '<td class="pos-col">' + (pos + 1) + '</td>' +
    '<td class="vals-col">' + row.vals.join(', ') + '</td>' +
    '<td class="avg-col"><span class="avg-num an-avg">' + row.raw + '</span></td>' +
    '<td class="pred-col">' + predBalls + '</td>' +
    '</tr>';
}});

// Stats strip
[
  {{label:'6+ hit draws', val:D.cnt6plus, sub:'5+: '+D.cnt5plus+'  4+: '+D.cnt4plus, color:'#fbbf24'}},
  {{label:'0 hit draws',  val:D.cnt0,     sub:'out of '+D.btDraws,                   color:'#fb923c'}},
  {{label:'Avg matches',  val:D.avgMatches.toFixed(2),
    sub:'Random: '+D.randBaseline.toFixed(2),
    color: D.avgMatches >= D.randBaseline ? '#4ade80' : '#fb923c'}},
  {{label:'Lift vs random',
    val:(D.liftPct >= 0 ? '+' : '') + D.liftPct + '%',
    sub:'vs baseline',
    color: D.liftPct >= 0 ? '#4ade80' : '#fb923c'}},
].forEach(function(s) {{
  document.getElementById('statsStrip').innerHTML +=
    '<div class="stat-card"><div class="sv" style="color:' + s.color + '">' + s.val + '</div>' +
    '<div class="sl">' + s.label + '</div><div class="sd">' + s.sub + '</div></div>';
}});

// Prediction balls
D.prediction.forEach(function(n) {{
  document.getElementById('balls').innerHTML += '<div class="ball">' + n + '</div>';
}});

// Backtest table
var tbody = document.getElementById('btBody');
D.btResults.forEach(function(r) {{
  var m   = r.matches;
  var cls = m >= 7 ? 'm-max' : m >= 6 ? 'm-high' : m >= 5 ? 'm-mid' : 'm-low';
  var hitSet = new Set(r.hitNums);
  var actual = r.actual.map(function(n) {{
    var h = hitSet.has(n);
    return '<span class="hit-ball" style="background:' +
      (h ? '#4ade80' : '#1e293b') + ';color:' + (h ? '#000' : '#94a3b8') + '">' + n + '</span>';
  }}).join('');
  var predBalls = (r.pred || []).map(function(n) {{
    var h = hitSet.has(n);
    return '<span class="pred-mini ' + (h ? 'pm-hit' : 'pm-selected') + '">' + n + '</span>';
  }}).join('');
  tbody.innerHTML +=
    '<tr>' +
    '<td style="color:#64748b">#' + r.s + '</td>' +
    '<td style="color:#475569">' + r.d + '</td>' +
    '<td>' + actual + '</td>' +
    '<td>' + (r.hitNums.join(', ') || '&#8212;') + '</td>' +
    '<td><span class="match-badge ' + cls + '">' + m + '</span></td>' +
    '</tr>' +
    '<tr class="pred-row"><td colspan="5" style="padding:4px 10px 10px">' +
    '<div style="font-size:.65rem;color:#475569;margin-bottom:3px">Predicted:</div>' +
    '<div style="display:flex;flex-wrap:wrap;gap:3px">' + predBalls + '</div>' +
    '</td></tr>';
}});
</script>
</body>
</html>"""

    out_path = os.path.join(PUBLIC, f"custom_avg{N}.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(HTML)
    print(f"  → {out_path} ({len(HTML):,} bytes)")

# ── Generate avg_hub.html ─────────────────────────────────────────────────────
print("\nGenerating avg_hub.html...")
hub_json = json.dumps({
    "rows": hub_rows,
    "nextSerial": next_serial,
    "latestDate": draws[-1]["d"],
}, ensure_ascii=False)

HUB_HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>N-Draw Average Comparison -- Loto 6</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:system-ui,sans-serif;background:#0f172a;color:#e2e8f0;min-height:100vh;padding-top:60px}}
.site-nav{{position:fixed;top:0;left:0;right:0;height:52px;background:#0a0f1e;
  border-bottom:1px solid #1e293b;display:flex;align-items:center;padding:0 20px;
  gap:0;z-index:9999;box-shadow:0 2px 16px rgba(0,0,0,.6)}}
.site-nav .nav-logo{{font-size:1rem;font-weight:800;color:#f1f5f9;text-decoration:none;
  white-space:nowrap;margin-right:24px;flex-shrink:0}}
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
  background:transparent;padding-top:6px;z-index:10000;min-width:175px}}
.nav-dropdown-inner{{background:#0d1526;border:1px solid #1e293b;border-radius:10px;
  padding:6px;box-shadow:0 12px 32px rgba(0,0,0,.7);max-height:70vh;overflow-y:auto}}
.nav-group:hover .nav-dropdown{{display:block}}
.nav-dropdown a{{display:flex;align-items:center;gap:8px;padding:8px 12px;
  border-radius:6px;color:#94a3b8;text-decoration:none;font-size:.82rem;
  white-space:nowrap;transition:.12s}}
.nav-dropdown a:hover,.nav-dropdown a.active{{color:#f1f5f9;background:#1e293b}}
.nav-dd-label{{font-size:.68rem;font-weight:700;color:#475569;padding:6px 12px 2px;
  text-transform:uppercase;letter-spacing:.06em}}
.nav-divider{{height:1px;background:#1e293b;margin:4px 0}}
main{{max-width:1200px;margin:0 auto;padding:24px 20px}}
h1{{font-size:1.4rem;font-weight:800;color:#f1f5f9;margin-bottom:4px}}
.subtitle{{font-size:.85rem;color:#64748b;margin-bottom:20px}}
.sort-hint{{font-size:.75rem;color:#475569;margin-bottom:12px}}
.hub-table{{width:100%;border-collapse:collapse;font-size:.8rem}}
.hub-table th{{background:#0c1420;color:#64748b;padding:8px 12px;text-align:right;
  border-bottom:2px solid #1e293b;font-weight:600;cursor:pointer;user-select:none;
  white-space:nowrap}}
.hub-table th:first-child,.hub-table th:nth-child(2){{text-align:left}}
.hub-table th:hover{{color:#f1f5f9;background:#1e293b}}
.hub-table th.sorted{{color:#a78bfa}}
.hub-table td{{padding:7px 12px;border-bottom:1px solid #1a2744;text-align:right}}
.hub-table td:first-child,.hub-table td:nth-child(2){{text-align:left}}
.hub-table tr:hover td{{background:#1a2234}}
.n-link{{font-weight:700;color:#a78bfa;text-decoration:none;font-size:.9rem}}
.n-link:hover{{text-decoration:underline}}
.pred-pill{{display:inline-block;background:#1e293b;border-radius:6px;
  padding:2px 6px;font-size:.7rem;color:#94a3b8;margin:1px 0}}
.lift-pos{{color:#4ade80}}
.lift-neg{{color:#fb923c}}
.lift-zero{{color:#64748b}}
.badge-6{{background:#78350f;color:#fbbf24;border-radius:5px;padding:2px 7px;font-weight:700}}
.badge-5{{background:#4a1d96;color:#c4b5fd;border-radius:5px;padding:2px 7px;font-weight:700}}
.sort-arrow{{margin-left:4px;opacity:.5;font-size:.65rem}}
</style>
</head>
<body>
<nav class="site-nav">
  <a class="nav-logo" href="/">&#127500; The<span>One</span>Lotto</a>
  <div class="nav-groups">
    <div class="nav-group">
      <div class="nav-group-btn">Data <span class="arrow">&#9660;</span></div>
      <div class="nav-dropdown"><div class="nav-dropdown-inner">
        <div class="nav-dd-label">Results</div>
        <a href="/">&#127968; Latest Draw</a>
        <a href="/history">&#128203; History</a>
        <a href="/numbers">&#128290; Numbers</a>
      </div></div>
    </div>
    <div class="nav-group">
      <div class="nav-group-btn">Predict <span class="arrow">&#9660;</span></div>
      <div class="nav-dropdown"><div class="nav-dropdown-inner">
        <div class="nav-dd-label">Prediction Tools</div>
        <a href="/predictions">&#127919; Predictions</a>
        <a href="/backtest.html">&#128202; Backtest</a>
        <a href="/combo_evo.html">&#129516; Combo Evo</a>
        <div class="nav-divider"></div>
        <div class="nav-dd-label">Strategy</div>
        <a href="/overdue.html">&#9203; Overdue</a>
        <a href="/state_machine.html">&#128260; State Machine</a>
        <a href="/modular_cycle.html">&#128260; Modular Cycle</a>
        <a href="/next_relation.html">&#128279; Next Relation</a>
        <a href="/lstm_predict.html">&#129504; LSTM Neural Net</a>
        <div class="nav-divider"></div>
        <div class="nav-dd-label">N-Draw Avg</div>
        <a href="/avg_hub.html" class="active">&#11835; All N-Draw Avg (2&#8211;43)</a>
      </div></div>
    </div>
    <div class="nav-group">
      <div class="nav-group-btn">Analyze <span class="arrow">&#9660;</span></div>
      <div class="nav-dropdown"><div class="nav-dropdown-inner">
        <div class="nav-dd-label">Pattern Analysis</div>
        <a href="/special.html">&#11088; Special</a>
        <a href="/consecutive.html">&#128279; Consecutive</a>
        <div class="nav-divider"></div>
        <div class="nav-dd-label">Position</div>
        <a href="/position.html">&#128205; Position Freq</a>
        <a href="/pos_predict.html">&#128202; Pos 1&#8211;6 Predict</a>
      </div></div>
    </div>
  </div>
</nav>
<main>
  <h1>&#11835; N-Draw Average Comparison</h1>
  <p class="subtitle">Comparing all N-draw average strategies (N = 2 to 43) for Draw #<span id="nextS"></span></p>
  <div class="sort-hint">Click any column header to sort &uarr;&darr;</div>

  <div style="overflow-x:auto">
    <table class="hub-table" id="hubTable">
      <thead>
        <tr>
          <th data-col="n">N <span class="sort-arrow">&#8597;</span></th>
          <th data-col="pred">Prediction</th>
          <th data-col="nPicks">Picks <span class="sort-arrow">&#8597;</span></th>
          <th data-col="cnt6plus">6+ hits <span class="sort-arrow">&#8597;</span></th>
          <th data-col="cnt5plus">5+ hits <span class="sort-arrow">&#8597;</span></th>
          <th data-col="cnt4plus">4+ hits <span class="sort-arrow">&#8597;</span></th>
          <th data-col="cnt0">0-hit <span class="sort-arrow">&#8597;</span></th>
          <th data-col="avgMatches">Avg matches <span class="sort-arrow">&#8597;</span></th>
          <th data-col="liftPct">Lift% <span class="sort-arrow">&#8597;</span></th>
        </tr>
      </thead>
      <tbody id="hubBody"></tbody>
    </table>
  </div>
</main>
<script>
var H = {hub_json};
var rows  = H.rows;
var sortCol = 'n', sortAsc = true;
document.getElementById('nextS').textContent = H.nextSerial;

function pageUrl(n) {{
  if (n === 2 || n === 3) return null;  // no detail page for N=2/N=3 (removed)
  return '/custom_avg' + n + '.html';
}}

function render() {{
  var sorted = rows.slice().sort(function(a, b) {{
    var av = a[sortCol], bv = b[sortCol];
    return sortAsc ? (av < bv ? -1 : av > bv ? 1 : 0)
                   : (av > bv ? -1 : av < bv ? 1 : 0);
  }});
  var tb = document.getElementById('hubBody');
  tb.innerHTML = '';
  sorted.forEach(function(r) {{
    var liftCls = r.liftPct > 0 ? 'lift-pos' : r.liftPct < 0 ? 'lift-neg' : 'lift-zero';
    var predStr = r.pred.join(', ');
    var url = pageUrl(r.n);
    var nCell = url ? ('<a class="n-link" href="' + url + '">' + r.n + '-Draw</a>')
                     : ('<span class="n-link" style="cursor:default;text-decoration:none">' + r.n + '-Draw</span>');
    tb.innerHTML +=
      '<tr>' +
      '<td>' + nCell + '</td>' +
      '<td><span class="pred-pill">' + predStr + '</span></td>' +
      '<td>' + r.nPicks + '</td>' +
      '<td><span class="badge-6">' + r.cnt6plus + '</span></td>' +
      '<td><span class="badge-5">' + r.cnt5plus + '</span></td>' +
      '<td>' + r.cnt4plus + '</td>' +
      '<td>' + r.cnt0 + '</td>' +
      '<td>' + r.avgMatches.toFixed(2) + '</td>' +
      '<td class="' + liftCls + '">' + (r.liftPct >= 0 ? '+' : '') + r.liftPct + '%</td>' +
      '</tr>';
  }});
  document.querySelectorAll('.hub-table th').forEach(function(th) {{
    th.classList.remove('sorted');
    if (th.dataset.col === sortCol) th.classList.add('sorted');
  }});
}}

document.querySelectorAll('.hub-table th[data-col]').forEach(function(th) {{
  th.addEventListener('click', function() {{
    var col = th.dataset.col;
    if (sortCol === col) sortAsc = !sortAsc;
    else {{ sortCol = col; sortAsc = col === 'n'; }}
    render();
  }});
}});

render();
</script>
</body>
</html>"""

hub_path = os.path.join(PUBLIC, "avg_hub.html")
with open(hub_path, "w", encoding="utf-8") as f:
    f.write(HUB_HTML)
print(f"Written: {hub_path} ({len(HUB_HTML):,} bytes)")
print("\nAll done.")
