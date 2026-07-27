"""
Replace flat site-nav with grouped dropdown nav across all static HTML files.
Groups:
  Data    -> Latest, History, Numbers
  Predict -> Predictions, Backtest, Combo Evo, Overdue, Miss Analysis
  Analyze -> Special, Consecutive, Position, Pos-1 Predict
"""
import os, re

PUBLIC = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto\public"

NAV_CSS = """
/* ====== SHARED FIXED NAV (dropdown) ====== */
.site-nav{position:fixed;top:0;left:0;right:0;height:52px;background:#0a0f1e;
  border-bottom:1px solid #1e293b;display:flex;align-items:center;padding:0 20px;
  gap:0;z-index:9999;box-shadow:0 2px 16px rgba(0,0,0,.6)}
.site-nav .nav-logo{font-size:1rem;font-weight:800;color:#f1f5f9;text-decoration:none;
  white-space:nowrap;margin-right:24px;flex-shrink:0;letter-spacing:-.01em}
.site-nav .nav-logo span{color:#38bdf8}
.nav-groups{display:flex;gap:4px;align-items:center}
.nav-group{position:relative}
.nav-group-btn{display:flex;align-items:center;gap:5px;padding:7px 14px;border-radius:7px;
  cursor:pointer;font-size:.82rem;font-weight:600;color:#94a3b8;
  border:1px solid transparent;transition:.15s;white-space:nowrap;user-select:none}
.nav-group-btn:hover,.nav-group:hover .nav-group-btn{color:#f1f5f9;background:#1e293b;border-color:#334155}
.nav-group-btn .arrow{font-size:.6rem;opacity:.6;transition:transform .2s}
.nav-group:hover .nav-group-btn .arrow{transform:rotate(180deg)}
.nav-dropdown{display:none;position:absolute;top:100%;left:0;
  background:transparent;padding-top:6px;z-index:10000;min-width:170px}
.nav-dropdown-inner{background:#0d1526;border:1px solid #1e293b;border-radius:10px;
  padding:6px;box-shadow:0 12px 32px rgba(0,0,0,.7)}
.nav-group:hover .nav-dropdown{display:block}
.nav-dropdown a{display:flex;align-items:center;gap:8px;padding:8px 12px;
  border-radius:6px;color:#94a3b8;text-decoration:none;font-size:.82rem;
  white-space:nowrap;transition:.12s}
.nav-dropdown a:hover{color:#f1f5f9;background:#1e293b}
.nav-dropdown a.active{color:#38bdf8;background:#0c2340}
.nav-dd-label{font-size:.68rem;font-weight:700;color:#475569;padding:6px 12px 2px;
  text-transform:uppercase;letter-spacing:.06em}
.nav-divider{height:1px;background:#1e293b;margin:4px 0}

/* ========================================= */
"""

NAV_HTML = """
<nav class="site-nav">
  <a class="nav-logo" href="/">🎱 The<span>One</span>Lotto</a>
  <div class="nav-groups">

    <!-- Data -->
    <div class="nav-group">
      <div class="nav-group-btn">Data <span class="arrow">▼</span></div>
      <div class="nav-dropdown"><div class="nav-dropdown-inner">
        <div class="nav-dd-label">Results</div>
        <a href="/">🏠 Latest Draw</a>
        <a href="/history">📋 History</a>
        <a href="/numbers">🔢 Numbers</a>
      </div></div>
    </div>

    <!-- Predict -->
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
        <a href="/custom_avg.html">➕ 2-Draw Avg</a>
        <a href="/custom_avg3.html">➕ 3-Draw Avg</a>
        <a href="/avg_hub.html">⬡ All N-Draw Avg (2–43)</a>
      </div></div>
    </div>

    <!-- Analyze -->
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
"""

NAV_ACTIVE_JS = """
<script>
(function(){
  var path = window.location.pathname + window.location.hash;
  document.querySelectorAll('.nav-dropdown a').forEach(function(a){
    var href = a.getAttribute('href');
    if(!href) return;
    var hPath = href.split('#')[0];
    var hHash = href.includes('#') ? href : '';
    if(href === path) { a.classList.add('active'); return; }
    if(hPath && hPath !== '/' && path.startsWith(hPath) && !href.includes('#')) {
      a.classList.add('active');
    }
  });
})();
</script>
"""

HTML_FILES = [
    "backtest.html",
    "combo_evo.html",
    "consecutive.html",

    "modular_cycle.html",
    "overdue.html",
    "position.html",
    "special.html",
    "state_machine.html",
    "pos_predict.html",
    "next_relation.html",
    "lstm_predict.html",
    "custom_avg.html",
    "custom_avg3.html",
    "avg_hub.html",
] + [f"custom_avg{n}.html" for n in range(4, 44)]

for fname in HTML_FILES:
    fpath = os.path.join(PUBLIC, fname)
    if not os.path.exists(fpath):
        print(f"  SKIP: {fname}")
        continue

    with open(fpath, encoding="utf-8") as f:
        html = f.read()

    orig_size = len(html)

    # 1. Replace old nav CSS with new nav CSS
    html = re.sub(
        r'/\* ====== SHARED FIXED NAV ======.*?/\* ======+.*?\*/',
        '',
        html, flags=re.DOTALL
    )
    # Also remove old dropdown CSS if already patched
    html = re.sub(
        r'/\* ====== SHARED FIXED NAV \(dropdown\) ======.*?/\* =========+.*?\*/',
        '',
        html, flags=re.DOTALL
    )
    html = html.replace("<style>", "<style>" + NAV_CSS, 1)

    # 2. Replace old site-nav HTML
    old_nav_match = re.search(r'<nav class="site-nav">.*?</nav>', html, re.DOTALL)
    if old_nav_match:
        html = html[:old_nav_match.start()] + NAV_HTML + html[old_nav_match.end():]
        print(f"  Replaced nav in {fname}")
    else:
        print(f"  WARNING: no site-nav found in {fname}")

    # 3. Remove old active-link JS and replace
    html = re.sub(r'<script>\s*\(function\(\)\{[^<]*site-nav.*?\}\)\(\);\s*</script>', '', html, flags=re.DOTALL)
    html = html.replace("</body>", NAV_ACTIVE_JS + "\n</body>", 1)

    with open(fpath, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"  {fname}: {orig_size:,} → {len(html):,} bytes")

print("\nAll done.")
