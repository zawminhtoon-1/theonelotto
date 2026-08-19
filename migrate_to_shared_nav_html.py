"""
migrate_to_shared_nav_html.py
--------------------------------
Same migration as migrate_to_shared_nav.py, but for pages that are
maintained by "append/patch" scripts operating directly on already-built
HTML (e.g. append_backtest.py only ever touches backtest.html's embedded
DATA/METHODS JS arrays, never its nav) rather than a from-scratch Python
f-string template. For these there is no generator to edit -- the nav
migration has to happen on the static HTML file itself, once, and it will
stick because nothing else in the pipeline touches that part of the file.

Same three replacements as the .py-script version, but without f-string
brace escaping ({{ -> {, }} -> }).

Also handles a discovered duplication bug on some of these pages: some had
the active-link-marking IIFE accidentally re-appended on every past patch
run instead of being idempotent, leaving dozens of identical copies in a
single file. The repeat-until-none-left removal loop cleans all of them up
in one pass, not just the first.

Run: python migrate_to_shared_nav_html.py file1.html file2.html ...
"""
import sys

CSS_START = ".site-nav{position:fixed"
CSS_END_MARKER = ".nav-divider{height:1px;background:#1e293b;margin:4px 0}"

NAV_HTML_START = "<nav class=\"site-nav\">"
NAV_HTML_END = "</nav>"

IIFE_MARKER = "document.querySelectorAll('.nav-dropdown a').forEach(function(a){"

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

def collapse_blank_run(text, max_blank=1):
    """Collapse runs of 3+ blank lines down to max_blank blank lines. Purely
    cosmetic cleanup for the whitespace left behind when many duplicated
    blocks get removed back-to-back (harmless to rendering either way, but
    ugly and worth tidying while the file is already being touched)."""
    lines = text.split('\n')
    out = []
    blank_run = 0
    for line in lines:
        if line.strip() == '':
            blank_run += 1
            if blank_run <= max_blank:
                out.append(line)
        else:
            blank_run = 0
            out.append(line)
    return '\n'.join(out)

def migrate_file(path):
    with open(path, encoding='utf-8') as f:
        text = f.read()
    orig = text

    text, css_count = remove_all_css_blocks(text)
    text, nav_count = replace_all_nav_html(text)
    text, iife_count = remove_all_iifes(text)
    if iife_count > 1:
        # Only bother collapsing blank runs when we actually removed
        # duplicate blocks -- normal single-IIFE files don't need it.
        text = collapse_blank_run(text)

    changed = text != orig
    if changed:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(text)

    return {"file": path, "css_count": css_count, "nav_count": nav_count,
            "iife_count": iife_count, "changed": changed}

if __name__ == '__main__':
    files = sys.argv[1:]
    if not files:
        print("Usage: python migrate_to_shared_nav_html.py file1.html file2.html ...")
        sys.exit(1)
    any_bad = False
    for path in files:
        r = migrate_file(path)
        ok = r["css_count"] > 0 and r["css_count"] == r["nav_count"]
        if not ok:
            any_bad = True
        status = "OK" if ok else "NO MATCH -- inspect manually"
        print(f"[{status}] {path}: css_blocks={r['css_count']} nav_blocks={r['nav_count']} iife_blocks_removed={r['iife_count']}")
    if any_bad:
        print("\nAt least one file did not match the expected pattern -- inspect manually.")
        sys.exit(1)
    print("\nAll files migrated cleanly.")
