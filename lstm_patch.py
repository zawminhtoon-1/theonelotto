"""
1. Read lstm_weights.json -> generate TypeScript constant string
2. Read lstm_backtest.json + backtest.html -> patch DATA array
"""
import json, re, sys

BASE = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"

# ── 1. Load weights ──────────────────────────────────────────────────────
with open(BASE + r"\lstm_weights.json") as f:
    w = json.load(f)

def fmt_arr(vals, name):
    rounded = [round(v, 4) for v in vals]
    # chunk into lines of 12
    lines = []
    chunk = 12
    for i in range(0, len(rounded), chunk):
        lines.append(",".join(str(x) for x in rounded[i:i+chunk]))
    inner = ",\n  ".join(lines)
    return f"const {name} = new Float64Array([\n  {inner}\n]);"

# W: 2d list -> flatten row-major
W_flat  = [v for row in w['W']  for v in row]
Wy_flat = [v for row in w['Wy'] for v in row]
b_flat  = w['b']
by_flat = w['by']

ts_consts = "\n\n".join([
    fmt_arr(W_flat,  "LSTM_W"),
    fmt_arr(b_flat,  "LSTM_B"),
    fmt_arr(Wy_flat, "LSTM_WY"),
    fmt_arr(by_flat, "LSTM_BY"),
])

print("=== TypeScript constants ===")
print(ts_consts[:300], "...\n")
print(f"W: {len(W_flat)}, b: {len(b_flat)}, Wy: {len(Wy_flat)}, by: {len(by_flat)} values")

# Save TS snippet for reference
with open(BASE + r"\lstm_ts_consts.txt", 'w') as f:
    f.write(ts_consts)
print("Saved lstm_ts_consts.txt")

# ── 2. Patch backtest.html DATA ──────────────────────────────────────────
with open(BASE + r"\lstm_backtest.json") as f:
    bt = json.load(f)

# Index by serial
lstm_by_serial = {r['serial']: r for r in bt}

html_path = BASE + r"\public\backtest.html"
with open(html_path, encoding='utf-8') as f:
    html = f.read()

# Find DATA array (may have spaces: "const DATA    = [")
m_data = re.search(r'const DATA\s*=\s*(\[)', html)
if not m_data:
    print("ERROR: could not find DATA array"); sys.exit(1)
bracket_start = m_data.start(1)
data_var_start = m_data.start(0)

# Find matching ] by counting brackets
depth = 0; pos = bracket_start
while pos < len(html):
    if html[pos] == '[': depth += 1
    elif html[pos] == ']':
        depth -= 1
        if depth == 0: bracket_end = pos+1; break
    pos += 1
data_end = bracket_end

json_str = html[bracket_start:bracket_end]
DATA = json.loads(json_str)
data_start = data_var_start  # reuse variable name for replacement below
print(f"\nLoaded DATA: {len(DATA)} entries")
print(f"First entry p-length: {len(DATA[0]['p'])}")

# Check if LSTM already added (p should have 15 entries currently)
if len(DATA[0]['p']) >= 16:
    print("LSTM already in DATA (p already has 16 entries), skipping p-patch")
    skip_p = True
else:
    skip_p = False

if not skip_p:
    missing = 0
    for entry in DATA:
        s = entry['s']
        if s not in lstm_by_serial:
            # fallback: empty picks, 0 match
            entry['p'].append([[1,2,3,4,5,6,7,8,9,10,11,12,13,14,15], 0, 0])
            missing += 1
            continue
        r = lstm_by_serial[s]
        picks = r['picks']   # already 15 numbers
        match6  = r['match']
        bbonus  = r['bbonus']
        entry['p'].append([picks, match6, bbonus])

    if missing:
        print(f"WARNING: {missing} entries had no LSTM prediction (used fallback)")
    print(f"Appended LSTM predictions to {len(DATA)} DATA entries")

# Serialise DATA back (replace everything from "const DATA" up to and including the closing "]")
# Find the ";" that terminates the statement
semi_pos = html.index(';', data_end)
new_data_str = 'const DATA=' + json.dumps(DATA, separators=(',', ':')) + ';'
html_new = html[:data_start] + new_data_str + html[semi_pos+1:]

# ── 3. Patch METHODS, MSHORT, COLORS ─────────────────────────────────────
def patch_array(html_text, varname, new_item):
    """Find 'const VARNAME = [...]' (with possible spaces) and append new_item."""
    pat = re.compile(r'(const ' + varname + r'\s*=\s*)(\[)(.*?)(\])', re.DOTALL)
    m2 = pat.search(html_text)
    if not m2:
        print(f"  WARNING: {varname} not found"); return html_text
    arr = json.loads(m2.group(2) + m2.group(3) + m2.group(4))
    print(f"  {varname} count: {len(arr)}, last: {arr[-1]!r}")
    if len(arr) >= 16:
        print(f"  {varname} already has 16 entries, skipping")
        return html_text
    arr.append(new_item)
    replacement = m2.group(1) + json.dumps(arr, separators=(',', ':'))
    return html_text[:m2.start()] + replacement + html_text[m2.end():]

print("\nPatching METHODS/MSHORT/COLORS...")
html_new = patch_array(html_new, 'METHODS', 'LSTM (seq prediction)')
html_new = patch_array(html_new, 'MSHORT',  'LSTM')
html_new = patch_array(html_new, 'COLORS',  '#e11d48')

# ── 4. Add card (data-mi="15") ───────────────────────────────────────────
# Find last card (data-mi="14") and insert after it
card_marker = 'data-mi="14"'
if 'data-mi="15"' not in html_new:
    idx = html_new.rindex(card_marker)
    # Find end of that card's outer div
    # The cards all have format: <div class="card" data-mi="N"> ... </div>
    # Find the closing </div> for this card
    search_from = idx
    div_count = 0
    pos = search_from
    # find opening <div after card_marker
    while pos < len(html_new):
        if html_new[pos:pos+4] == '<div':
            div_count += 1
        elif html_new[pos:pos+6] == '</div>':
            div_count -= 1
            if div_count == 0:
                card_end = pos + 6
                break
        pos += 1

    new_card = '''
<div class="card" data-mi="15">
  <div class="card-header" style="background:#e11d48">
    <span class="method-num">16</span>
    <span class="method-name">LSTM (seq prediction)</span>
    <span class="badge" id="badge-15"></span>
  </div>
  <div class="card-body">
    <div class="hits-row" id="hits-15"></div>
    <canvas id="dist-15"></canvas>
  </div>
</div>'''

    html_new = html_new[:card_end] + new_card + html_new[card_end:]
    print("Added card data-mi=15")
else:
    print("Card data-mi=15 already exists")

# ── 5. Add selector option ────────────────────────────────────────────────
# Find method selector
sel_marker = '<option value="14">'
if '<option value="15">' not in html_new:
    idx = html_new.rindex(sel_marker)
    # Find end of this option
    opt_end = html_new.index('</option>', idx) + 9
    new_opt = '\n<option value="15">16: LSTM (seq prediction)</option>'
    html_new = html_new[:opt_end] + new_opt + html_new[opt_end:]
    print("Added selector option for LSTM")
else:
    print("Selector option for LSTM already exists")

# ── 6. Write out ─────────────────────────────────────────────────────────
with open(html_path, 'w', encoding='utf-8') as f:
    f.write(html_new)
print(f"\nWrote patched backtest.html ({len(html_new)//1024}KB)")
