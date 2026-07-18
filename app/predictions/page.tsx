import { getAllDraws } from "@/lib/db";
import PredictionsView from "./PredictionsView";

export const revalidate = 300;

function fitPredict(serials: number[], values: number[], target: number): number {
  const n = serials.length;
  const xm = serials.reduce((a, b) => a + b, 0) / n;
  const xn = serials.map((v) => v - xm);
  const xp = target - xm;
  const s = [0,1,2,3,4].map((k) => xn.reduce((a, v) => a + Math.pow(v, k), 0));
  const t = [0,1,2].map((k) => xn.reduce((a, v, i) => a + Math.pow(v, k) * values[i], 0));
  const A = [[s[4],s[3],s[2]],[s[3],s[2],s[1]],[s[2],s[1],s[0]]];
  const b = [t[2],t[1],t[0]];
  function det(m: number[][]): number {
    return m[0][0]*(m[1][1]*m[2][2]-m[1][2]*m[2][1])
          -m[0][1]*(m[1][0]*m[2][2]-m[1][2]*m[2][0])
          +m[0][2]*(m[1][0]*m[2][1]-m[1][1]*m[2][0]);
  }
  const d = det(A);
  if (Math.abs(d) < 1e-12) return Math.round(values[n-1]);
  const c = b.map((_, i) => det(A.map((row, r) => row.map((v, ci) => ci === i ? b[r] : v))) / d);
  return Math.max(1, Math.min(43, Math.round(c[0]*xp*xp + c[1]*xp + c[2])));
}

function makeUnique(nums: number[], freq: Record<number,number>): number[] {
  const seen = new Set<number>();
  const result: number[] = [];
  for (const n of nums) {
    const clamped = Math.max(1, Math.min(43, n));
    if (!seen.has(clamped)) { seen.add(clamped); result.push(clamped); }
  }
  // Pad to 15 with most frequent unseen numbers
  const ordered = Object.entries(freq).sort((a,b) => +b[1] - +a[1]).map(([n]) => +n);
  for (const n of ordered) {
    if (result.length >= 15) break;
    if (!seen.has(n)) { seen.add(n); result.push(n); }
  }
  return result.slice(0, 15).sort((a, b) => a - b);
}

function solveLS(X: number[][], y: number[]): number[] {
  const cols = X[0].length;
  const A: number[][] = Array.from({length: cols}, (_, i) =>
    Array.from({length: cols}, (__, j) => X.reduce((s, row) => s + row[i] * row[j], 0))
  );
  const bv: number[] = Array.from({length: cols}, (_, i) =>
    X.reduce((s, row, r) => s + row[i] * y[r], 0)
  );
  const aug = A.map((row, i) => [...row, bv[i]]);
  for (let col = 0; col < cols; col++) {
    let maxRow = col;
    for (let r = col + 1; r < cols; r++)
      if (Math.abs(aug[r][col]) > Math.abs(aug[maxRow][col])) maxRow = r;
    [aug[col], aug[maxRow]] = [aug[maxRow], aug[col]];
    if (Math.abs(aug[col][col]) < 1e-12) continue;
    for (let r = 0; r < cols; r++) {
      if (r === col) continue;
      const f = aug[r][col] / aug[col][col];
      for (let c = col; c <= cols; c++) aug[r][c] -= f * aug[col][c];
    }
  }
  return aug.map((row, i) => Math.abs(aug[i][i]) < 1e-12 ? 0 : row[cols] / aug[i][i]);
}

function arimaPred(series: number[]): number {
  const s = series.slice(-150);
  const diff: number[] = [];
  for (let i = 1; i < s.length; i++) diff.push(s[i] - s[i - 1]);
  const n = diff.length;
  if (n < 5) return Math.max(1, Math.min(43, Math.round(s.reduce((a, b) => a + b, 0) / s.length)));
  const X: number[][] = [];
  const yv: number[] = [];
  for (let i = 2; i < n; i++) { X.push([1, diff[i - 1], diff[i - 2]]); yv.push(diff[i]); }
  try {
    const coeffs = solveLS(X, yv);
    const predDiff = coeffs[0] + coeffs[1] * diff[n - 1] + coeffs[2] * diff[n - 2];
    return Math.max(1, Math.min(43, Math.round(s[s.length - 1] + predDiff)));
  } catch {
    return Math.max(1, Math.min(43, Math.round(s.slice(-20).reduce((a, b) => a + b, 0) / Math.min(20, s.length))));
  }
}

function rfPred(series: number[]): number {
  const LAGS = 8, N_BAGS = 30;
  const s = series.slice(-80);
  if (s.length < LAGS + 5) return Math.max(1, Math.min(43, Math.round(s.reduce((a, b) => a + b, 0) / s.length)));
  const X: number[][] = [];
  const yv: number[] = [];
  for (let i = LAGS; i < s.length; i++) { X.push([1, ...s.slice(i - LAGS, i)]); yv.push(s[i]); }
  const n = yv.length;
  const xNew = [1, ...s.slice(-LAGS)];
  let seed = 42;
  const rndInt = (max: number) => { seed = ((seed * 1664525 + 1013904223) & 0x7fffffff); return ((seed >>> 0) % max); };
  const preds: number[] = [];
  for (let bag = 0; bag < N_BAGS; bag++) {
    const idx = Array.from({length: n}, () => rndInt(n));
    const Xb = idx.map(i => X[i]);
    const yb = idx.map(i => yv[i]);
    try {
      const c = solveLS(Xb, yb);
      preds.push(xNew.reduce((sum, v, i) => sum + v * c[i], 0));
    } catch { preds.push(yv.reduce((a, b) => a + b, 0) / n); }
  }
  return Math.max(1, Math.min(43, Math.round(preds.reduce((a, b) => a + b, 0) / preds.length)));
}

export default async function PredictionsPage() {
  const draws = await getAllDraws();
  draws.reverse();
  const serials = draws.map(d => d.draw_serial);
  const nums = draws.map(d => [d.num1,d.num2,d.num3,d.num4,d.num5,d.num6]);
  const nextSerial = (serials[serials.length-1] ?? 2120) + 1;

  const last20 = nums.slice(-20);
  const lam=0.95, wts=nums.map((_,i)=>Math.pow(lam,nums.length-1-i)), ws=wts.reduce((a,b)=>a+b,0);

  const freqAll: Record<number,number> = {};
  nums.forEach(d=>d.forEach(n=>{ freqAll[n]=(freqAll[n]??0)+1; }));

  const T: number[][] = Array.from({length: 44}, () => new Array(44).fill(0));
  for (let k = 0; k < nums.length - 1; k++)
    for (const a of nums[k]) for (const b2 of nums[k+1]) T[a][b2]++;
  const lastDraw = nums[nums.length - 1];
  const markovScores = Array.from({length: 43}, (_, i) => ({
    n: i + 1, score: lastDraw.reduce((sum, a) => sum + T[a][i+1], 0)
  })).sort((a, b) => b.score - a.score);

  const combos = [
    { label:"1", color:"#2a78d6", method:"Poly deg-2 · full history",
      raw: makeUnique([0,1,2,3,4,5].map(p=>fitPredict(serials,nums.map(d=>d[p]),nextSerial)), freqAll) },
    { label:"2", color:"#1baf7a", method:"Moving average · last 20",
      raw: makeUnique([0,1,2,3,4,5].map(p=>Math.round(last20.reduce((s,d)=>s+d[p],0)/20)), freqAll) },
    { label:"3", color:"#4a3aa7", method:"Exp-weighted recency",
      raw: makeUnique([0,1,2,3,4,5].map(p=>Math.round(nums.reduce((s,d,i)=>s+wts[i]*d[p],0)/ws)), freqAll) },
    { label:"4", color:"#eda100", method:"Poly deg-2 · last 200",
      raw: makeUnique([0,1,2,3,4,5].map(p=>fitPredict(serials.slice(-200),nums.slice(-200).map(d=>d[p]),nextSerial)), freqAll) },
    { label:"5", color:"#e34948", method:"Most frequent · all history",
      raw: makeUnique(Object.entries(freqAll).sort((a,b)=>+b[1]-+a[1]).slice(0,15).map(([n])=>+n), freqAll) },
    { label:"6", color:"#0ea5e9", method:"Markov chain",
      raw: makeUnique(markovScores.slice(0,15).map(s=>s.n), freqAll) },
    { label:"7", color:"#f87171", method:"ARIMA(2,1,0)",
      raw: makeUnique([0,1,2,3,4,5].map(p=>arimaPred(nums.map(d=>d[p]))), freqAll) },
    { label:"8", color:"#34d399", method:"Random Forest (bagged OLS)",
      raw: makeUnique([0,1,2,3,4,5].map(p=>rfPred(nums.map(d=>d[p]))), freqAll) },
  ];

  return (
    <PredictionsView
      combos={combos.map(c => ({ label: c.label, color: c.color, method: c.method, numbers: c.raw }))}
      nextSerial={nextSerial}
      drawCount={draws.length}
    />
  );
}
