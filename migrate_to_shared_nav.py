"""
migrate_to_shared_nav.py
--------------------------------
One-time migration: replaces each generator script's baked nav CSS block,
<nav class="site-nav">...</nav> HTML block, and active-link-marking IIFE
with a single include of the new shared /site-nav.js module (see that file
for the single source of truth for nav content going forward).

For each target script, does three surgical string replacements:
  1. Removes the nav-specific CSS rules (from ".site-nav{{position:fixed"
     through the ".nav-divider{{...}}" rule, inclusive).
  2. Replaces "<body>\\n<nav class=\"site-nav\">...</nav>" with
     "<body>\\n<script src=\"/site-nav.js\"></script>".
  3. Removes the "<script>(function(){{ ... .nav-dropdown a ... }})();</script>"
     active-link-marking IIFE (site-nav.js now does this itself).

Reports a per-file summary of which of the 3 replacements succeeded, so any
file whose markup doesn't match the expected pattern is visibly flagged
rather than silently left half-migrated.

Run: python migrate_to_shared_nav.py file1.py file2.py ...
"""
import re, sys

CSS_START = ".site-nav{{position:fixed"
CSS_END_MARKER = ".nav-divider{{height:1px;background:#1e293b;margin:4px 0}}"

NAV_HTML_START = "<nav class=\"site-nav\">"
NAV_HTML_END = "</nav>"

IIFE_MARKER = "document.querySelectorAll('.nav-dropdown a').forEach(function(a){{"

def migrate_file(path):
    with open(path, encoding='utf-8') as f:
        text = f.read()
    orig = text
    report = {"file": path, "css_removed": False, "nav_html_replaced": False, "iife_removed": False}

    # 1. Remove nav CSS block.
    css_start_idx = text.find(CSS_START)
    if css_start_idx != -1:
        css_end_marker_idx = text.find(CSS_END_MARKER, css_start_idx)
        if css_end_marker_idx != -1:
            css_end_idx = css_end_marker_idx + len(CSS_END_MARKER)
            # Trim the trailing newline after the removed block so we don't leave a blank line.
            if text[css_end_idx:css_end_idx+1] == "\n":
                css_end_idx += 1
            text = text[:css_start_idx] + text[css_end_idx:]
            report["css_removed"] = True

    # 2. Replace <nav class="site-nav">...</nav> with the script include,
    #    anchored to right after <body> (matches the existing convention
    #    where the nav is the first thing in body on every page).
    nav_start_idx = text.find(NAV_HTML_START)
    if nav_start_idx != -1:
        nav_end_idx = text.find(NAV_HTML_END, nav_start_idx)
        if nav_end_idx != -1:
            nav_end_idx += len(NAV_HTML_END)
            # Also eat a trailing blank line right after </nav> if present.
            tail = text[nav_end_idx:nav_end_idx+2]
            if tail == "\n\n":
                nav_end_idx += 1
            text = text[:nav_start_idx] + '<script src="/site-nav.js"></script>' + text[nav_end_idx:]
            report["nav_html_replaced"] = True

    # 3. Remove the active-link-marking IIFE (a standalone <script>...</script>
    #    block containing the .nav-dropdown a marker).
    iife_marker_idx = text.find(IIFE_MARKER)
    if iife_marker_idx != -1:
        # Walk backward to the start of its enclosing <script> tag.
        script_open_idx = text.rfind("<script>", 0, iife_marker_idx)
        script_close_idx = text.find("</script>", iife_marker_idx)
        if script_open_idx != -1 and script_close_idx != -1:
            script_close_idx += len("</script>")
            if text[script_close_idx:script_close_idx+1] == "\n":
                script_close_idx += 1
            text = text[:script_open_idx] + text[script_close_idx:]
            report["iife_removed"] = True

    changed = text != orig
    if changed:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(text)
    report["changed"] = changed
    return report

if __name__ == '__main__':
    files = sys.argv[1:]
    if not files:
        print("Usage: python migrate_to_shared_nav.py file1.py file2.py ...")
        sys.exit(1)
    all_ok = True
    for path in files:
        r = migrate_file(path)
        ok = r["css_removed"] and r["nav_html_replaced"] and r["iife_removed"]
        all_ok = all_ok and ok
        status = "OK" if ok else "PARTIAL/FAILED"
        print(f"[{status}] {path}: css_removed={r['css_removed']} nav_html_replaced={r['nav_html_replaced']} iife_removed={r['iife_removed']}")
    if not all_ok:
        print("\nSome files did not fully match the expected pattern -- inspect those manually before regenerating.")
        sys.exit(1)
    print("\nAll files migrated cleanly.")
