/*
 * compute_modcycle_k28_x_k38_intersection.js
 * --------------------------------------------
 * Precomputes the Modular Cycle (K=28) x xoshiro K=38 seed #692,809
 * intersection backtest over the last 100 draws, for
 * gen_modcycle_k28_x_k38_intersection.py to render into a static page.
 *
 * Modular Cycle's per-draw picks live only in public/backtest.html's
 * embedded DATA array (r.p[10][0]) plus its topKNums() padding/trimming
 * logic -- there's no independent formula to reimplement in Python the way
 * xoshiro has, so this reads backtest.html directly, extracts DATA, and
 * reuses topKNums verbatim (copied byte-for-byte from that file) to stay
 * bit-exact with what the live page shows.
 *
 * The xoshiro side is the same verified xoshiro256** (SplitMix64-seeded)
 * implementation used everywhere else on the site, self-checked below
 * against a known Python-computed pick before trusting it at scale.
 *
 * Run: node compute_modcycle_k28_x_k38_intersection.js
 * Output: modcycle_k28_x_k38_intersection_data.json
 */
const fs = require('fs');

const BASE = 'C:\\Users\\Zaw Min Htoon\\source\\repos\\theonelotto';
const BACKTEST_HTML = BASE + '\\public\\backtest.html';
const OUT_JSON = BASE + '\\modcycle_k28_x_k38_intersection_data.json';

const K_MC = 28;
const K_XO = 38;
const XO_SEED = 692809;
const MC_METHOD_NAME = 'Modular Cycle (k=28)';
const N_BACKTEST_DRAWS = 100;

// ── Extract DATA and METHODS from backtest.html (verbatim JS, not re-derived) ──
const html = fs.readFileSync(BACKTEST_HTML, 'utf-8');

const dataMatch = html.match(/const DATA\s*=\s*(\[[\s\S]*?\]);\r?\n/);
if (!dataMatch) throw new Error('Could not find const DATA=[...]; in backtest.html');
const DATA = JSON.parse(dataMatch[1]);

const methodsMatch = html.match(/const METHODS\s*=\s*(\[[\s\S]*?\]);/);
if (!methodsMatch) throw new Error('Could not find const METHODS=[...]; in backtest.html');
const METHODS = JSON.parse(methodsMatch[1]);
const mi = METHODS.indexOf(MC_METHOD_NAME);
if (mi === -1) throw new Error(`Method "${MC_METHOD_NAME}" not found in METHODS: ${METHODS}`);

console.log(`Loaded DATA: ${DATA.length} draws (#${DATA[0].s}-${DATA[DATA.length-1].s})`);
console.log(`Modular Cycle method index: ${mi}`);

// ── topKNums, copied verbatim from backtest.html ─────────────────────────
function topKNums(combo, r, k) {
  const freq = {};
  r.p.forEach(pred => pred[0].forEach(n => { freq[n] = (freq[n]||0)+1; }));
  if (combo.length === k) return combo;
  if (combo.length > k) {
    return [...combo].sort((a,b)=>(freq[b]||0)-(freq[a]||0)).slice(0,k).sort((a,b)=>a-b);
  }
  const inCombo = new Set(combo);
  let extra = Object.keys(freq)
    .map(Number)
    .filter(n => !inCombo.has(n))
    .sort((a,b) => (freq[b]||0)-(freq[a]||0));
  if (combo.length + extra.length < k) {
    const have = new Set([...combo, ...extra]);
    for (let n = 1; n <= 43; n++) {
      if (!have.has(n)) extra.push(n);
    }
  }
  extra = extra.slice(0, k - combo.length);
  return [...combo, ...extra].sort((a,b)=>a-b);
}

// ── Xoshiro256**/SplitMix64, same verified implementation used site-wide ──
const MASK64 = (1n << 64n) - 1n;
function rotl(x, k) {
  x &= MASK64;
  return ((x << BigInt(k)) | (x >> BigInt(64 - k))) & MASK64;
}
function splitmix64Next(z) {
  z = (z + 0x9E3779B97F4A7C15n) & MASK64;
  let zz = z;
  zz = ((zz ^ (zz >> 30n)) * 0xBF58476D1CE4E5B9n) & MASK64;
  zz = ((zz ^ (zz >> 27n)) * 0x94D049BB133111EBn) & MASK64;
  zz = zz ^ (zz >> 31n);
  return [z, zz];
}
function seedState(seed) {
  let z = BigInt(seed) & MASK64;
  const state = [];
  for (let i = 0; i < 4; i++) {
    const [nz, out] = splitmix64Next(z);
    z = nz;
    state.push(out);
  }
  return state;
}
function xoshiroNext(s) {
  const result = (rotl((s[1] * 5n) & MASK64, 7) * 9n) & MASK64;
  const t = (s[1] << 17n) & MASK64;
  s[2] ^= s[0]; s[3] ^= s[1]; s[1] ^= s[2]; s[0] ^= s[3];
  s[2] ^= t;
  s[3] = rotl(s[3], 45);
  return result;
}
function xoshiroPredict(seed, drawSerial, k) {
  const combined = (BigInt(seed) * 10000000n + BigInt(drawSerial)) & MASK64;
  const s = seedState(combined);
  const arr = Array.from({length: 43}, (_, i) => i + 1);
  const n = arr.length;
  for (let i = n - 1; i >= n - k; i--) {
    const r = xoshiroNext(s);
    const j = Number(r % BigInt(i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr.slice(n - k);
}

// Self-check against the known Python-computed reference for seed 692809,
// draw #2129 (bit-exact match confirmed independently before this script
// was written).
const KNOWN_REF = [2,3,4,5,6,7,8,9,11,12,13,14,15,16,17,18,19,20,21,22,24,25,27,28,29,30,31,32,33,34,35,36,38,39,40,41,42,43];
const testPick = xoshiroPredict(692809, 2129, 38).sort((a,b)=>a-b);
if (JSON.stringify(testPick) !== JSON.stringify(KNOWN_REF)) {
  throw new Error('Xoshiro self-check FAILED -- does not match known reference pick.');
}
console.log('Xoshiro self-check OK (seed 692809, draw #2129 matches known reference).');

// ── Hypergeometric helpers ───────────────────────────────────────────────
function comb(n, r) {
  if (r < 0 || r > n) return 0;
  let res = 1;
  for (let i = 0; i < r; i++) res = res * (n - i) / (i + 1);
  return res;
}
function hyperPmf(k, pop, success, draws) {
  if (k > success || k > draws || (draws - k) > (pop - success)) return 0;
  return comb(success, k) * comb(pop - success, draws - k) / comb(pop, draws);
}
function hyperAtLeast(threshold, pop, success, draws) {
  let s = 0;
  for (let k = 0; k < threshold; k++) s += hyperPmf(k, pop, success, draws);
  return 1 - s;
}

// ── Backtest ──────────────────────────────────────────────────────────────
const last100 = DATA.slice(-N_BACKTEST_DRAWS);
if (last100.length !== N_BACKTEST_DRAWS) throw new Error(`Expected ${N_BACKTEST_DRAWS} draws, got ${last100.length}`);

const rows = [];
const poolSizes = [];
let hits3plus = 0, hits6 = 0;
let expected3plusSum = 0, expected6Sum = 0;

last100.forEach(r => {
  const actual = [...r.a].sort((a,b)=>a-b);
  const actualSet = new Set(actual);
  const mcCombo = new Set(topKNums(r.p[mi][0], r, K_MC));
  const xoCombo = new Set(xoshiroPredict(XO_SEED, r.s, K_XO));
  const inter = [...mcCombo].filter(n => xoCombo.has(n)).sort((a,b)=>a-b);
  const poolSize = inter.length;
  poolSizes.push(poolSize);
  const matchCount = inter.filter(n => actualSet.has(n)).length;
  const hit3plus = matchCount >= 3;
  const hit6 = matchCount === 6;
  if (hit3plus) hits3plus++;
  if (hit6) hits6++;
  expected3plusSum += hyperAtLeast(3, 43, poolSize, 6);
  expected6Sum += hyperAtLeast(6, 43, poolSize, 6);
  rows.push({ s: r.s, d: r.d, actual, bonus: r.b, inter, poolSize, matchCount, hit3plus, hit6 });
});

const n = last100.length;
const avgPool = poolSizes.reduce((a,b)=>a+b,0) / n;
const minPool = Math.min(...poolSizes);
const maxPool = Math.max(...poolSizes);
const medianPool = [...poolSizes].sort((a,b)=>a-b)[Math.floor(n/2)];

const observed3plusRate = hits3plus / n;
const expected3plusRate = expected3plusSum / n;
const ratio3plus = expected3plusRate > 0 ? observed3plusRate / expected3plusRate : NaN;

const observed6Rate = hits6 / n;
const expected6Rate = expected6Sum / n;
const ratio6 = expected6Rate > 0 ? observed6Rate / expected6Rate : NaN;

// Rough Poisson tails for both thresholds
function poissonPmf(k, lam) {
  let fact = 1;
  for (let i = 2; i <= k; i++) fact *= i;
  return Math.exp(-lam) * Math.pow(lam, k) / fact;
}
function poissonAtLeast(hitsObs, lam) {
  let s = 0;
  for (let k = 0; k < hitsObs; k++) s += poissonPmf(k, lam);
  return 1 - s;
}
const lam3 = expected3plusRate * n;
const lam6 = expected6Rate * n;
const p3 = poissonAtLeast(hits3plus, lam3);
const p6 = poissonAtLeast(hits6, lam6);

console.log(`\nPool size: min=${minPool} max=${maxPool} avg=${avgPool.toFixed(2)} median=${medianPool}`);
console.log(`3+/6: ${hits3plus}/${n} (${(observed3plusRate*100).toFixed(1)}%) vs expected ${(expected3plusRate*100).toFixed(2)}% -- ratio ${ratio3plus.toFixed(2)}x, Poisson P(>=${hits3plus}|lambda=${lam3.toFixed(2)})=${(p3*100).toFixed(2)}%`);
console.log(`6/6:   ${hits6}/${n} (${(observed6Rate*100).toFixed(2)}%) vs expected ${(expected6Rate*100).toFixed(4)}% -- ratio ${ratio6.toFixed(2)}x, Poisson P(>=${hits6}|lambda=${lam6.toFixed(4)})=${(p6*100).toFixed(2)}%`);

// ── Next-upcoming-draw reference pool (not part of the backtest) ────────
const maxSerial = DATA[DATA.length - 1].s;
const nextDraw = maxSerial + 1;
// Modular Cycle's next-draw pick isn't in DATA (DATA only has historical
// draws with known predictions attached) -- so the reference pool for the
// upcoming draw uses only the xoshiro side here; Modular Cycle needs its
// own live prediction to pair with it, which this static precompute
// doesn't have access to. Documented as a known limitation on the page.

const out = {
  meta: {
    K_MC, K_XO, XO_SEED, MC_METHOD_NAME, N_BACKTEST_DRAWS,
    drawLo: last100[0].s, drawHi: last100[last100.length-1].s,
    maxSerial,
  },
  summary: {
    n, avgPool, minPool, maxPool, medianPool,
    hits3plus, observed3plusRate, expected3plusRate, ratio3plus, lam3, p3,
    hits6, observed6Rate, expected6Rate, ratio6, lam6, p6,
  },
  rows,
};

fs.writeFileSync(OUT_JSON, JSON.stringify(out));
console.log(`\nWrote ${OUT_JSON}`);
