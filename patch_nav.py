"""
Inject a unified fixed nav bar into all static HTML pages.
Replaces each page's existing <header> block and adds body padding-top.
"""
import os, re

PUBLIC = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto\public"

NAV_CSS = """
/* ====== SHARED FIXED NAV ====== */
.site-nav{position:fixed;top:0;left:0;right:0;height:52px;background:#0a0f1e;
  border-bottom:1px solid #1e293b;display:flex;align-items:center;padding:0 16px;
  gap:0;z-index:9999;box-shadow:0 2px 12px rgba(0,0,0,.5)}
.site-nav .nav-logo{font-size:1rem;font-weight:800;color:#f1f5f9;text-decoration:none;
  white-space:nowrap;margin-right:16px;flex-shrink:0}
.site-nav .nav-links{display:flex;gap:2px;overflow-x:auto;scrollbar-width:none;-ms-overflow-style:none}
.site-nav .nav-links::-webkit-scrollbar{display:none}
.site-nav .nav-links a{color:#94a3b8;text-decoration:none;font-size:.78rem;padding:5px 10px;
  border-radius:6px;white-space:nowrap;transition:.15s}
.site-nav .nav-links a:hover,.site-nav .nav-links a.active{color:#f1f5f9;background:#1e293b}
/* ============================== */
"""

NAV_HTML = """
<nav class="site-nav">
  <a class="nav-logo" href="/">🎱 TheOneLotto</a>
  <div class="nav-links">
    <a href="/">Latest</a>
    <a href="/predictions">Predictions</a>
    <a href="/history">History</a>
    <a href="/numbers">Numbers</a>
    <a href="/backtest.html">Backtest</a>
    <a href="/combo_evo.html">Combo Evo</a>
    <a href="/special.html">Special</a>
    <a href="/consecutive.html">Consecutive</a>
    <a href="/position.html">Position</a>
    <a href="/position.html#pos1pred">Pos-1 Predict</a>
    <a href="/overdue.html">Overdue</a>
    <a href="/miss_analysis.html">Miss Analysis</a>
  </div>
</nav>
"""

NAV_ACTIVE_JS = """
<script>
(function(){
  var path = window.location.pathname + window.location.hash;
  document.querySelectorAll('.site-nav .nav-links a').forEach(function(a){
    if(a.getAttribute('href') === path ||
       (path === '/' && a.getAttribute('href') === '/') ||
       (a.getAttribute('href') !== '/' && path.startsWith(a.getAttribute('href').split('#')[0]) && !a.getAttribute('href').includes('#'))) {
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
    "miss_analysis.html",
    "overdue.html",
    "position.html",
    "special.html",
]

for fname in HTML_FILES:
    fpath = os.path.join(PUBLIC, fname)
    if not os.path.exists(fpath):
        print(f"  SKIP (not found): {fname}")
        continue

    with open(fpath, encoding="utf-8") as f:
        html = f.read()

    original_size = len(html)

    # 1. Inject CSS into <style> block (after first <style> tag)
    if "/* ====== SHARED FIXED NAV ======" not in html:
        html = html.replace("<style>", "<style>" + NAV_CSS, 1)

    # 2. Add body padding-top if not already set
    # Find body tag and add/update padding-top
    if "padding-top:52px" not in html and "padding-top: 52px" not in html:
        # Try to patch existing body style
        if re.search(r'<body\s+style="', html):
            html = re.sub(r'(<body\s+style=")', r'\1padding-top:52px;', html)
        elif re.search(r'<body\b', html):
            html = re.sub(r'(<body\b)', r'\1 style="padding-top:52px"', html, count=1)

    # Also update body{...} in CSS if it exists
    # Add padding-top to body rule or add a new one
    if "body{" in html and "padding-top:52px" not in html:
        html = html.replace("body{", "body{padding-top:52px;", 1)
    elif "body {" in html and "padding-top:52px" not in html:
        html = html.replace("body {", "body {padding-top:52px;", 1)

    # 3. Remove old <header>...</header> block and replace with new nav
    # Match <header>...</header> (possibly multiline, non-greedy)
    old_header_match = re.search(r'<header\b[^>]*>.*?</header>', html, re.DOTALL)
    if old_header_match:
        html = html[:old_header_match.start()] + NAV_HTML + html[old_header_match.end():]
        print(f"  Replaced <header> in {fname}")
    else:
        # No header found — inject after <body>
        html = re.sub(r'(<body[^>]*>)', r'\1' + NAV_HTML, html, count=1)
        print(f"  Inserted nav after <body> in {fname} (no header found)")

    # 4. Inject active-link JS before </body>
    if "site-nav .nav-links a" not in html or "classList.add('active')" not in html:
        html = html.replace("</body>", NAV_ACTIVE_JS + "\n</body>", 1)

    with open(fpath, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"  {fname}: {original_size:,} → {len(html):,} bytes")

print("\nAll done.")
