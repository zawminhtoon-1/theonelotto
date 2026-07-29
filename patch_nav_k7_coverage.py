"""
Add the new "K=7 Seed Coverage" nav link to every static HTML page's
Random Seed nav-dropdown section (mirrors the pattern used when
random_seed_backtest.html was originally added site-wide).
"""
import os, re

PUBLIC = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto\public"

NEW_LINK = '<a href="/k7_seed_coverage.html">\U0001f4c8 K=7 Seed Coverage</a>'

# Matches an existing Random Seed nav <a> line (with or without class="active",
# and with either the (1-2000) or (1-3000) label variants seen across pages)
PATTERN = re.compile(
    r'(<a href="/random_seed_backtest\.html"[^>]*>[^<]*Random Seed[^<]*</a>)'
)

patched = 0
skipped_no_match = []
skipped_already = []

for fname in sorted(os.listdir(PUBLIC)):
    if not fname.endswith(".html"):
        continue
    if fname == "k7_seed_coverage.html":
        continue
    fpath = os.path.join(PUBLIC, fname)
    with open(fpath, encoding="utf-8") as f:
        html = f.read()

    if "k7_seed_coverage.html" in html:
        skipped_already.append(fname)
        continue

    m = PATTERN.search(html)
    if not m:
        skipped_no_match.append(fname)
        continue

    new_html = html[:m.end()] + "\n        " + NEW_LINK + html[m.end():]
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(new_html)
    patched += 1

print(f"Patched: {patched}")
print(f"Already had link: {len(skipped_already)}")
print(f"No Random Seed nav found (skipped): {len(skipped_no_match)}")
if skipped_no_match:
    for n in skipped_no_match:
        print("  -", n)
