"""
migrate_to_shared_nav.py
--------------------------------
One-time migration: replaces each generator script's baked nav CSS block,
<nav class="site-nav">...</nav> HTML block, and active-link-marking IIFE
with a single include of the new shared /site-nav.js module (see that file
for the single source of truth for nav content going forward).

For each target script, does three surgical, repeat-until-none-left
replacements (some scripts emit more than one page per run -- e.g. hub +
per-N pages -- and bake a full nav copy into each):
  1. Removes every nav-specific CSS block (from ".site-nav{{position:fixed"
     through the ".nav-divider{{...}}" rule, inclusive).
  2. Replaces every "<nav class=\"site-nav\">...</nav>" block with
     "<script src=\"/site-nav.js\"></script>".
  3. Removes every "<script>(function(){{ ... .nav-dropdown a ... }})();</script>"
     active-link-marking IIFE (site-nav.js now does this itself). Not every
     page had one to begin with -- that's fine, zero-found is not a failure.

Reports a per-file count of how many of each block were removed, so a
script whose markup doesn't match the expected pattern at all (0 CSS
blocks found) is visibly flagged rather than silently left untouched.

Run: python migrate_to_shared_nav.py file1.py file2.py ...
"""
import sys

CSS_START = ".site-nav{{position:fixed"
CSS_END_MARKER = ".nav-divider{{height:1px;background:#1e293b;margin:4px 0}}"

NAV_HTML_START = "<nav class=\"site-nav\">"
NAV_HTML_END = "</nav>"

IIFE_MARKER = "document.querySelectorAll('.nav-dropdown a').forEach(function(a){{"

def remove_all_css_blocks(text):
    count = 0
    while True:
        start_idx = text.find(CSS_START)
        if start_idx == -1:
            break
        end_marker_idx = text.find(CSS_END_MARKER, start_idx)
        if end_marker_idx == -1:
            break
        end_idx = end_marker_idx + len(CSS_END_MARKER)
        if text[end_idx:end_idx+1] == "\n":
            end_idx += 1
        text = text[:start_idx] + text[end_idx:]
        count += 1
    return text, count

def replace_all_nav_html(text):
    count = 0
    while True:
        start_idx = text.find(NAV_HTML_START)
        if start_idx == -1:
            break
        end_idx = text.find(NAV_HTML_END, start_idx)
        if end_idx == -1:
            break
        end_idx += len(NAV_HTML_END)
        if text[end_idx:end_idx+2] == "\n\n":
            end_idx += 1
        text = text[:start_idx] + '<script src="/site-nav.js"></script>' + text[end_idx:]
        count += 1
    return text, count

def remove_all_iifes(text):
    count = 0
    while True:
        marker_idx = text.find(IIFE_MARKER)
        if marker_idx == -1:
            break
        script_open_idx = text.rfind("<script>", 0, marker_idx)
        script_close_idx = text.find("</script>", marker_idx)
        if script_open_idx == -1 or script_close_idx == -1:
            break
        script_close_idx += len("</script>")
        if text[script_close_idx:script_close_idx+1] == "\n":
            script_close_idx += 1
        text = text[:script_open_idx] + text[script_close_idx:]
        count += 1
    return text, count

def migrate_file(path):
    with open(path, encoding='utf-8') as f:
        text = f.read()
    orig = text

    text, css_count = remove_all_css_blocks(text)
    text, nav_count = replace_all_nav_html(text)
    text, iife_count = remove_all_iifes(text)

    changed = text != orig
    if changed:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(text)

    return {"file": path, "css_count": css_count, "nav_count": nav_count,
            "iife_count": iife_count, "changed": changed}

if __name__ == '__main__':
    files = sys.argv[1:]
    if not files:
        print("Usage: python migrate_to_shared_nav.py file1.py file2.py ...")
        sys.exit(1)
    any_untouched = False
    for path in files:
        r = migrate_file(path)
        # A file is "OK" if at least one nav CSS+HTML block was found and
        # replaced, and the two counts agree (every nav block had matching
        # CSS). IIFE count can legitimately be 0 (some pages never had one)
        # or should match nav_count (one IIFE per page that had one).
        ok = r["css_count"] > 0 and r["css_count"] == r["nav_count"]
        if not ok:
            any_untouched = True
        status = "OK" if ok else "NO MATCH -- inspect manually"
        print(f"[{status}] {path}: css_blocks={r['css_count']} nav_blocks={r['nav_count']} iife_blocks_removed={r['iife_count']}")
    if any_untouched:
        print("\nAt least one file did not match the expected pattern (0 blocks found, or CSS/nav count mismatch) -- inspect manually before regenerating.")
        sys.exit(1)
    print("\nAll files migrated cleanly.")
