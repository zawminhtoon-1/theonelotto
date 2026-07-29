"""
Add the new "K=7 Seed-Hit (1000 draws)" nav link to every static HTML page's
Random Seed nav-dropdown section, right after the K=7 Seed Coverage link
added in the previous session.
"""
import os, re

PUBLIC = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto\public"

NEW_LINK = '<a href="/k7_seed_hit_1000.html">\U0001f5fa K=7 Seed-Hit (1000 draws)</a>'

PATTERN = re.compile(
    r'(<a href="/k7_seed_coverage\.html"[^>]*>[^<]*K=7 Seed Coverage[^<]*</a>)'
)

patched = 0
skipped_no_match = []
skipped_already = []

for fname in sorted(os.listdir(PUBLIC)):
    if not fname.endswith(".html"):
        continue
    if fname == "k7_seed_hit_1000.html":
        continue
    fpath = os.path.join(PUBLIC, fname)
    with open(fpath, encoding="utf-8") as f:
        html = f.read()

    if "k7_seed_hit_1000.html" in html:
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
print(f"No K=7 Seed Coverage nav found (skipped): {len(skipped_no_match)}")
if skipped_no_match:
    for n in skipped_no_match:
        print("  -", n)
