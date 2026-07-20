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

function hmmPred(allDraws: number[][], K = 3, nIter = 5, maxTrain = 300): number[] {
  const draws = allDraws.slice(-maxTrain);
  const T = draws.length;
  const N = 43;

  // Binary observation matrix flat (T*N)
  const O = new Float64Array(T * N);
  for (let t = 0; t < T; t++)
    for (const n of draws[t]) O[t * N + (n - 1)] = 1;

  // Empirical frequency
  const emp = new Float64Array(N);
  for (let t = 0; t < T; t++)
    for (const n of draws[t]) emp[n - 1] += 1 / T;

  // Init: stay-biased transition A, frequency-based B
  const pi = new Float64Array(K).fill(1 / K);
  const A = new Float64Array(K * K);
  for (let k = 0; k < K; k++)
    for (let l = 0; l < K; l++)
      A[k * K + l] = k === l ? 0.9 : 0.1 / (K - 1);
  let rSeed = 42;
  const lcg = () => { rSeed = ((rSeed * 1664525 + 1013904223) & 0x7fffffff); return (rSeed >>> 0) / 0x7fffffff - 0.5; };
  const B = new Float64Array(K * N);
  for (let k = 0; k < K; k++)
    for (let n = 0; n < N; n++)
      B[k * N + n] = Math.max(0.02, Math.min(0.98, emp[n] + lcg() * 0.06));

  const alpha = new Float64Array(T * K);
  const beta  = new Float64Array(T * K);
  const gamma = new Float64Array(T * K);
  const emit  = new Float64Array(T * K);

  for (let iter = 0; iter < nIter; iter++) {
    // Emission: log P(o_t|k), then row-max stabilize and normalize
    for (let t = 0; t < T; t++) {
      let mx = -Infinity;
      for (let k = 0; k < K; k++) {
        let lg = 0;
        for (let n = 0; n < N; n++) {
          const o = O[t * N + n], b = B[k * N + n];
          lg += o * Math.log(b) + (1 - o) * Math.log(1 - b);
        }
        emit[t * K + k] = lg;
        if (lg > mx) mx = lg;
      }
      let sm = 0;
      for (let k = 0; k < K; k++) { emit[t*K+k] = Math.exp(emit[t*K+k] - mx); sm += emit[t*K+k]; }
      for (let k = 0; k < K; k++) emit[t*K+k] /= sm + 1e-300;
    }

    // Forward (scaled)
    let s0 = 0;
    for (let k = 0; k < K; k++) { alpha[k] = pi[k] * emit[k]; s0 += alpha[k]; }
    for (let k = 0; k < K; k++) alpha[k] /= s0 + 1e-300;
    for (let t = 1; t < T; t++) {
      let st = 0;
      for (let l = 0; l < K; l++) {
        let sm = 0;
        for (let k = 0; k < K; k++) sm += alpha[(t-1)*K+k] * A[k*K+l];
        alpha[t*K+l] = sm * emit[t*K+l]; st += alpha[t*K+l];
      }
      for (let l = 0; l < K; l++) alpha[t*K+l] /= st + 1e-300;
    }

    // Backward (scaled)
    for (let k = 0; k < K; k++) beta[(T-1)*K+k] = 1;
    for (let t = T - 2; t >= 0; t--) {
      let st = 0;
      for (let k = 0; k < K; k++) {
        let sm = 0;
        for (let l = 0; l < K; l++) sm += A[k*K+l] * emit[(t+1)*K+l] * beta[(t+1)*K+l];
        beta[t*K+k] = sm; st += sm;
      }
      for (let k = 0; k < K; k++) beta[t*K+k] /= st + 1e-300;
    }

    // Gamma
    for (let t = 0; t < T; t++) {
      let st = 0;
      for (let k = 0; k < K; k++) { gamma[t*K+k] = alpha[t*K+k] * beta[t*K+k]; st += gamma[t*K+k]; }
      for (let k = 0; k < K; k++) gamma[t*K+k] /= st + 1e-300;
    }

    // M-step: pi
    for (let k = 0; k < K; k++) pi[k] = gamma[k];

    // M-step: A via xi (pairwise posteriors, not stored — accumulate directly)
    const Anew = new Float64Array(K * K);
    for (let t = 0; t < T - 1; t++) {
      let tot = 0;
      for (let k = 0; k < K; k++)
        for (let l = 0; l < K; l++) {
          const v = alpha[t*K+k] * A[k*K+l] * emit[(t+1)*K+l] * beta[(t+1)*K+l];
          Anew[k*K+l] += v; tot += v;
        }
    }
    for (let k = 0; k < K; k++) {
      let rs = 0; for (let l = 0; l < K; l++) rs += Anew[k*K+l];
      for (let l = 0; l < K; l++) A[k*K+l] = rs > 1e-300 ? Anew[k*K+l] / rs : 1/K;
    }

    // M-step: B
    for (let k = 0; k < K; k++) {
      let gs = 0; for (let t = 0; t < T; t++) gs += gamma[t*K+k];
      for (let n = 0; n < N; n++) {
        let num = 0; for (let t = 0; t < T; t++) num += gamma[t*K+k] * O[t*N+n];
        B[k*N+n] = Math.max(0.02, Math.min(0.98, gs > 1e-300 ? num/gs : emp[n]));
      }
    }
  }

  // Expected emission = sum_k P(state_k | all obs) * B[k,n]
  const expE = new Float64Array(N);
  for (let k = 0; k < K; k++)
    for (let n = 0; n < N; n++) expE[n] += alpha[(T-1)*K+k] * B[k*N+n];

  return Array.from({length: N}, (_, i) => ({n: i+1, e: expE[i]}))
    .sort((a, b) => b.e - a.e).slice(0, 15).map(x => x.n).sort((a, b) => a - b);
}
function modularCyclePred(allDraws: number[][], K = 28): number[] {
  // Score each number by how overdue it is relative to its expected appearance cycle.
  // K=28 found optimal via 1000-draw backtest (lift 1.0189 over random baseline).
  const N = 43;
  const T = allDraws.length;
  const count    = new Float64Array(N);
  const lastSeen = new Float64Array(N).fill(-1);

  for (let t = 0; t < T; t++)
    for (const n of allDraws[t]) { count[n-1]++; lastSeen[n-1] = t; }

  const score = new Float64Array(N);
  for (let i = 0; i < N; i++) {
    const avgCycle  = T / Math.max(count[i], 0.5);
    const sinceLast = lastSeen[i] < 0 ? T : T - lastSeen[i];
    const phase     = (sinceLast / avgCycle) % 1.0;
    const freqW     = count[i] / Math.max(T, 1);
    score[i]        = phase * (1.0 + freqW);
  }
  return Array.from({length: N}, (_, i) => ({n: i+1, s: score[i]}))
    .sort((a, b) => b.s - a.s).slice(0, K).map(x => x.n).sort((a, b) => a - b);
}

function naiveBayesPred(allDraws: number[][]): number[] {
  // Bernoulli Naive Bayes: for each candidate number c, compute
  // log P(c in next draw | features of last draw) using sequential co-occurrence counts.
  const N = 43;
  const T = allDraws.length;
  if (T < 2) return [];

  // posCount[c*N+f]: how often f appeared in draw t when c appeared in draw t+1
  // negCount[c*N+f]: how often f appeared in draw t when c did NOT appear in draw t+1
  const posCount = new Float64Array(N * N);
  const negCount = new Float64Array(N * N);
  const priorPos = new Float64Array(N);  // how many draws had c in next
  const priorNeg = new Float64Array(N);  // how many draws did NOT have c in next

  for (let t = 0; t < T - 1; t++) {
    const cur  = allDraws[t];
    const next = new Set(allDraws[t + 1]);
    for (let c = 0; c < N; c++) {
      if (next.has(c + 1)) {
        priorPos[c]++;
        for (const f of cur) posCount[c * N + (f - 1)]++;
      } else {
        priorNeg[c]++;
        for (const f of cur) negCount[c * N + (f - 1)]++;
      }
    }
  }

  const alpha  = 1.0;  // Laplace smoothing
  const lastVec = new Float64Array(N);
  for (const f of allDraws[T - 1]) lastVec[f - 1] = 1;

  const scores = new Float64Array(N);
  for (let c = 0; c < N; c++) {
    const pp = priorPos[c], pn = priorNeg[c], tot = pp + pn;
    let logScore = Math.log((pp + alpha) / (tot + 2 * alpha));
    for (let f = 0; f < N; f++) {
      if (!lastVec[f]) continue;
      const pPos = (posCount[c * N + f] + alpha) / (pp + 2 * alpha);
      const pNeg = (negCount[c * N + f] + alpha) / (pn + 2 * alpha);
      logScore += Math.log(pPos) - Math.log(pNeg);
    }
    scores[c] = logScore;
  }

  return Array.from({ length: N }, (_, i) => ({ n: i + 1, s: scores[i] }))
    .sort((a, b) => b.s - a.s).slice(0, 15).map(x => x.n).sort((a, b) => a - b);
}

function monteCarloPred(allDraws: number[][], nSims = 5000): number[] {
  const N = 43;
  const T = allDraws.length;
  if (T === 0) return [];

  // Exponentially-weighted frequency → draw probability for each number
  const lam = 0.99;
  const weights = new Float64Array(N);
  for (let t = 0; t < T; t++) {
    const w = Math.pow(lam, T - 1 - t);
    for (const n of allDraws[t]) weights[n - 1] += w;
  }
  const wSum = weights.reduce((a, b) => a + b, 0);
  const probs = Array.from(weights, w => w / wSum);

  // Cumulative distribution for inverse-CDF sampling
  const cdf = new Float64Array(N);
  cdf[0] = probs[0];
  for (let i = 1; i < N; i++) cdf[i] = cdf[i - 1] + probs[i];

  // Seeded LCG so predictions are deterministic
  let seed = allDraws[T - 1].reduce((a, b) => a + b, 0) * 1000003 + T;
  const rng = () => {
    seed = ((seed * 1664525 + 1013904223) & 0x7fffffff);
    return (seed >>> 0) / 0x80000000;
  };

  // Run simulations: each draws 6 unique numbers from the weighted distribution
  const count = new Float64Array(N);
  for (let s = 0; s < nSims; s++) {
    const drawn = new Uint8Array(N);
    let need = 6;
    while (need > 0) {
      const r = rng();
      let lo = 0, hi = N - 1;
      while (lo < hi) { const mid = (lo + hi) >> 1; if (cdf[mid] < r) lo = mid + 1; else hi = mid; }
      if (!drawn[lo]) { drawn[lo] = 1; count[lo]++; need--; }
    }
  }

  return Array.from({ length: N }, (_, i) => ({ n: i + 1, c: count[i] }))
    .sort((a, b) => b.c - a.c).slice(0, 15).map(x => x.n).sort((a, b) => a - b);
}

function aprioriPred(allDraws: number[][], minSupFrac = 0.05): number[] {
  const N = 43;
  const T = allDraws.length;
  if (T < 2) return [];

  const sup1    = new Float64Array(N);           // how often number n appears
  const seq1    = new Float64Array(N * N);       // seq1[n][c]: n in t → c in t+1
  const pairCnt = new Float64Array(N * N);       // pairCnt[a][b]: a&b co-occur in same draw
  const seq2    = new Float64Array(N * N * N);   // seq2[a][b][c]: {a,b} in t → c in t+1

  for (let t = 0; t < T; t++) {
    const cur  = allDraws[t];
    const next = t < T - 1 ? allDraws[t + 1] : null;
    for (const ni of cur) sup1[ni - 1]++;
    for (let i = 0; i < cur.length; i++) {
      if (next) for (const c of next) seq1[(cur[i]-1)*N + (c-1)]++;
      for (let j = i + 1; j < cur.length; j++) {
        const a = cur[i]-1, b = cur[j]-1;
        pairCnt[a*N+b]++;
        pairCnt[b*N+a]++;
        if (next) for (const c of next) {
          seq2[a*N*N + b*N + (c-1)]++;
          seq2[b*N*N + a*N + (c-1)]++;
        }
      }
    }
  }

  const minSup  = minSupFrac * T;
  const lastDraw = allDraws[T - 1];
  const lastSet  = new Set(lastDraw);
  const score    = new Float64Array(N);

  // 1-item antecedents
  for (const ni of lastDraw) {
    const n = ni - 1;
    if (sup1[n] < minSup) continue;
    for (let c = 0; c < N; c++) {
      if (lastSet.has(c + 1)) continue;
      score[c] += seq1[n*N + c] / Math.max(sup1[n], 1);
    }
  }

  // 2-item antecedents (weight ×2 — more specific rules)
  for (let i = 0; i < lastDraw.length; i++) {
    for (let j = i + 1; j < lastDraw.length; j++) {
      const a = lastDraw[i]-1, b = lastDraw[j]-1;
      const pCnt = pairCnt[a*N + b];
      if (pCnt < minSup) continue;
      for (let c = 0; c < N; c++) {
        if (lastSet.has(c + 1)) continue;
        score[c] += 2.0 * seq2[a*N*N + b*N + c] / Math.max(pCnt, 1);
      }
    }
  }

  return Array.from({ length: N }, (_, i) => ({ n: i+1, s: score[i] }))
    .sort((a, b) => b.s - a.s).slice(0, 15).map(x => x.n).sort((a, b) => a - b);
}

function knnPred(allDraws: number[][], k = 10): number[] {
  const N = 43;
  if (allDraws.length < k + 2) {
    const freq: Record<number, number> = {};
    for (const d of allDraws) for (const n of d) freq[n] = (freq[n] ?? 0) + 1;
    return makeUnique([], freq);
  }
  const lastDraw = allDraws[allDraws.length - 1];
  const lastSet = new Set(lastDraw);

  // Jaccard similarity between each past draw and the last draw
  const sims: { sim: number; idx: number }[] = [];
  for (let i = 0; i < allDraws.length - 1; i++) {
    const dSet = new Set(allDraws[i]);
    let inter = 0, union = 0;
    for (const n of dSet) { if (lastSet.has(n)) inter++; union++; }
    for (const n of lastSet) { if (!dSet.has(n)) union++; }
    sims.push({ sim: union > 0 ? inter / union : 0, idx: i });
  }
  sims.sort((a, b) => b.sim - a.sim);

  // Aggregate the k draws that followed the most similar past draws
  const scores = new Float64Array(N);
  for (const { sim, idx } of sims.slice(0, k)) {
    for (const n of allDraws[idx + 1]) scores[n - 1] += sim;
  }
  return Array.from({ length: N }, (_, i) => ({ n: i + 1, s: scores[i] }))
    .sort((a, b) => b.s - a.s).slice(0, 15).map(x => x.n).sort((a, b) => a - b);
}

function rlLinearQPred(allDraws: number[][]): number[] {
  // Linear Q-learning bandit: W[i][j] = score for number i+1 when j+1 appeared last draw
  const MAX = 43;
  const ALPHA = 0.001;
  const W = new Float64Array(MAX * MAX); // flat row-major, zeros

  for (let t = 0; t < allDraws.length - 1; t++) {
    const cur = allDraws[t];
    const nextSet = new Set(allDraws[t + 1]);
    const Q = new Float64Array(MAX);
    for (let i = 0; i < MAX; i++)
      for (const j of cur) Q[i] += W[i * MAX + (j - 1)];
    for (let i = 0; i < MAX; i++) {
      const delta = ALPHA * ((nextSet.has(i + 1) ? 1 : 0) - Q[i]);
      for (const j of cur) W[i * MAX + (j - 1)] += delta;
    }
  }
  const lastDraw = allDraws[allDraws.length - 1];
  const Qf = Array.from({ length: MAX }, (_, i) => {
    let q = 0;
    for (const j of lastDraw) q += W[i * MAX + (j - 1)];
    return { n: i + 1, q };
  });
  return Qf.sort((a, b) => b.q - a.q).slice(0, 15).map(x => x.n).sort((a, b) => a - b);
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

  const last43 = nums.slice(-43);
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
    { label:"2", color:"#1baf7a", method:"Reverse MA · last 43",
      raw: makeUnique([0,1,2,3,4,5].map(p=>Math.max(1,Math.min(43,44-Math.round(last43.reduce((s,d)=>s+d[p],0)/last43.length)))), freqAll) },
    { label:"3", color:"#4a3aa7", method:"Exp-weighted recency",
      raw: makeUnique([0,1,2,3,4,5].map(p=>Math.round(nums.reduce((s,d,i)=>s+wts[i]*d[p],0)/ws)), freqAll) },
    { label:"4", color:"#e34948", method:"Most frequent · all history",
      raw: makeUnique(Object.entries(freqAll).sort((a,b)=>+b[1]-+a[1]).slice(0,15).map(([n])=>+n), freqAll) },
    { label:"5", color:"#0ea5e9", method:"Markov chain",
      raw: makeUnique(markovScores.slice(0,15).map(s=>s.n), freqAll) },
    { label:"6", color:"#f87171", method:"ARIMA(2,1,0)",
      raw: makeUnique([0,1,2,3,4,5].map(p=>arimaPred(nums.map(d=>d[p]))), freqAll) },
    { label:"7", color:"#34d399", method:"Random Forest (bagged OLS)",
      raw: makeUnique([0,1,2,3,4,5].map(p=>rfPred(nums.map(d=>d[p]))), freqAll) },
    { label:"8", color:"#a78bfa", method:"RL (Linear Q-learning)",      raw: rlLinearQPred(nums) },
    { label:"9", color:"#fb7185", method:"Hidden Markov Model (K=3)",
      raw: hmmPred(nums) },
    { label:"10", color:"#f59e0b", method:"kNN (k=10, Jaccard similarity)",
      raw: knnPred(nums) },
    { label:"11", color:"#10b981", method:"Modular Cycle (k=28, optimal by 1000-draw backtest)",
      raw: modularCyclePred(nums) },
    { label:"12", color:"#e879f9", method:"Apriori Association Rules (seq 1-item + 2-item)",
      raw: aprioriPred(nums) },
    { label:"13", color:"#06b6d4", method:"Monte Carlo (5000 sims, exp-weighted sampling)",
      raw: monteCarloPred(nums) },
    { label:"14", color:"#84cc16", method:"Naive Bayes (Bernoulli, sequential co-occurrence)",
      raw: naiveBayesPred(nums) },
  ];

  return (
    <PredictionsView
      combos={combos.map(c => ({ label: c.label, color: c.color, method: c.method, numbers: c.raw }))}
      nextSerial={nextSerial}
      drawCount={draws.length}
    />
  );
}





