"""Remove the pos1pred tab from position.html — now covered by pos_predict.html."""
import re

PATH = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto\public\position.html"

with open(PATH, encoding="utf-8") as f:
    html = f.read()

before = len(html)

# 1. Remove tab button
html = re.sub(r"\s*<div class=\"tab\" onclick=\"showTab\('pos1pred'.*?</div>", "", html)

# 2. Remove panel block
html = re.sub(r"<!-- TAB: POS1 PREDICT -->.*?<!-- END TAB: POS1 PREDICT -->", "", html, flags=re.DOTALL)

# 3. Remove JS block (inside <script> tags)
html = re.sub(r"<script>\s*\n// POS1PRED_START.*?// POS1PRED_END\s*\n</script>", "", html, flags=re.DOTALL)

# 4. Remove dangling POS1PRED markers if any
html = re.sub(r"// POS1PRED_START.*?// POS1PRED_END", "", html, flags=re.DOTALL)

with open(PATH, "w", encoding="utf-8") as f:
    f.write(html)

print(f"Done. {before:,} → {len(html):,} bytes (saved {before-len(html):,} bytes)")
