"""
Patch backtest.html to add K=15 and K=20 pick options:
1. Add "15 picks" and "20 picks" toggle buttons
2. Fix topKNums to pad picks when K > combo.length
3. Add BC_CONFIGS entries for K=15 and K=20
"""
import re, sys
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

HTML_PATH = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto\public\backtest.html"

with open(HTML_PATH, encoding='utf-8') as f:
    html = f.read()

print(f"Loaded backtest.html ({len(html)//1024}KB)")

changes = 0

# ── 1. Add 15 picks / 20 picks buttons ───────────────────────────────────────
OLD_BUTTONS = '    <button class="ptbtn" onclick="setGlobalK(10,this)">10 picks</button>\n  </div>'
NEW_BUTTONS = (
    '    <button class="ptbtn" onclick="setGlobalK(10,this)">10 picks</button>\n'
    '    <button class="ptbtn" onclick="setGlobalK(15,this)">15 picks</button>\n'
    '    <button class="ptbtn" onclick="setGlobalK(20,this)">20 picks</button>\n'
    '  </div>'
)
if OLD_BUTTONS in html:
    html = html.replace(OLD_BUTTONS, NEW_BUTTONS, 1)
    print("+ Added 15 picks and 20 picks buttons")
    changes += 1
elif '15 picks' in html and '20 picks' in html:
    print("  Buttons already present, skipping")
else:
    print("ERROR: could not find pick toggle buttons"); sys.exit(1)

# ── 2. Fix topKNums to handle K > combo.length (pad from cross-method votes) ──
OLD_TOPK = """function topKNums(combo, r, k) {
  if (combo.length <= k) return combo;
  const freq = {};
  r.p.forEach(pred => pred[0].forEach(n => { freq[n] = (freq[n]||0)+1; }));
  return [...combo].sort((a,b)=>(freq[b]||0)-(freq[a]||0)).slice(0,k).sort((a,b)=>a-b);
}"""
NEW_TOPK = """function topKNums(combo, r, k) {
  const freq = {};
  r.p.forEach(pred => pred[0].forEach(n => { freq[n] = (freq[n]||0)+1; }));
  if (combo.length === k) return combo;
  if (combo.length > k) {
    // Trim: keep top-k by cross-method frequency
    return [...combo].sort((a,b)=>(freq[b]||0)-(freq[a]||0)).slice(0,k).sort((a,b)=>a-b);
  }
  // Pad: K > stored picks, fill extra slots from cross-method consensus
  const inCombo = new Set(combo);
  const extra = Object.keys(freq)
    .map(Number)
    .filter(n => !inCombo.has(n))
    .sort((a,b) => (freq[b]||0)-(freq[a]||0))
    .slice(0, k - combo.length);
  return [...combo, ...extra].sort((a,b)=>a-b);
}"""
if OLD_TOPK in html:
    html = html.replace(OLD_TOPK, NEW_TOPK, 1)
    print("+ Fixed topKNums to support K > 15 (padding)")
    changes += 1
elif 'fill extra slots from cross-method consensus' in html:
    print("  topKNums already patched, skipping")
else:
    print("ERROR: could not find topKNums function"); sys.exit(1)

# ── 3. Add BC_CONFIGS entries for K=15 and K=20 ──────────────────────────────
OLD_BC = """BC_CONFIGS = [
  { K: 6,  methods: [6,9,10,13], label: "RF + kNN + ModCyc + NaiveBay",
    note: "Best avg hits across 1,001 draws" },
  { K: 8,  methods: [3,4,6,9,10], label: "FreqAll + Markov + RF + kNN + ModCyc",
    note: "Most 4+ hit draws (13)" },
  { K: 10, methods: [7,8,9,10], label: "RL-Q + HMM + kNN + ModCyc",
    note: "Best avg hits + most 4+ draws (30)" },
];"""
NEW_BC = """BC_CONFIGS = [
  { K: 6,  methods: [6,9,10,13], label: "RF + kNN + ModCyc + NaiveBay",
    note: "Best avg hits across 1,001 draws" },
  { K: 8,  methods: [3,4,6,9,10], label: "FreqAll + Markov + RF + kNN + ModCyc",
    note: "Most 4+ hit draws (13)" },
  { K: 10, methods: [7,8,9,10], label: "RL-Q + HMM + kNN + ModCyc",
    note: "Best avg hits + most 4+ draws (30)" },
  { K: 15, methods: [4,5,11,13], label: "Markov + ARIMA + Apriori + NaiveBay",
    note: "Best avg hits (2.19) across 1,001 draws" },
  { K: 20, methods: [3,6,8,10], label: "FreqAll + RF + HMM + ModCyc",
    note: "Best avg hits (2.85) + most 4+ draws (304)" },
];"""
if OLD_BC in html:
    html = html.replace(OLD_BC, NEW_BC, 1)
    print("+ Added BC_CONFIGS entries for K=15 and K=20")
    changes += 1
elif 'K: 15' in html and 'K: 20' in html:
    print("  BC_CONFIGS entries already present, skipping")
else:
    print("ERROR: could not find BC_CONFIGS block"); sys.exit(1)

# ── Write out ─────────────────────────────────────────────────────────────────
if changes > 0:
    with open(HTML_PATH, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"\nWrote patched backtest.html ({len(html)//1024}KB), {changes} change(s)")
else:
    print("\nNo changes needed")
