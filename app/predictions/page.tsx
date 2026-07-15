import { getAllDraws } from "@/lib/db";

export const revalidate = 3600;

function fitPredict(serials: number[], values: number[], target: number): number {
  const slice = serials.length > 200 ? serials.length - 200 : 0;
  const x = serials.slice(slice);
  const y = values.slice(slice);
  const n = x.length;
  const xm = x.reduce((a, b) => a + b, 0) / n;
  const xn = x.map((v) => v - xm);
  const xp = target - xm;
  // Least-squares degree-2 via normal equations (3x3 Cramer)
  const s = [0,1,2,3,4].map((k) => xn.reduce((a, v) => a + Math.pow(v, k), 0));
  const t = [0,1,2].map((k) => xn.reduce((a, v, i) => a + Math.pow(v, k) * y[i], 0));
  const A = [[s[4],s[3],s[2]],[s[3],s[2],s[1]],[s[2],s[1],s[0]]];
  const b = [t[2],t[1],t[0]];
  function det(m: number[][]): number {
    return m[0][0]*(m[1][1]*m[2][2]-m[1][2]*m[2][1])
          -m[0][1]*(m[1][0]*m[2][2]-m[1][2]*m[2][0])
          +m[0][2]*(m[1][0]*m[2][1]-m[1][1]*m[2][0]);
  }
  const d = det(A);
  if (Math.abs(d) < 1e-12) return Math.round(y[n-1]);
  const c = b.map((_, i) => det(A.map((row, r) => row.map((v, c) => c === i ? b[r] : v))) / d);
  return Math.max(1, Math.min(43, Math.round(c[0]*xp*xp + c[1]*xp + c[2])));
}

function makeUnique(nums: number[]): number[] {
  const seen = new Set<number>();
  const result: number[] = [];
  for (const n of nums) {
    const clamped = Math.max(1, Math.min(43, n));
    if (!seen.has(clamped)) { seen.add(clamped); result.push(clamped); }
  }
  const extras = Array.from({length:43},(_,i)=>i+1).filter(n=>!seen.has(n));
  while (result.length < 6) result.push(extras.shift()!);
  return result.slice(0,6).sort((a,b)=>a-b);
}

function ballColor(n: number): string {
  if (n <= 10) return "#e74c3c";
  if (n <= 19) return "#e67e22";
  if (n <= 29) return "#27ae60";
  if (n <= 38) return "#2980b9";
  return "#8e44ad";
}

export default async function PredictionsPage() {
  const draws = await getAllDraws();
  draws.reverse(); // oldest first for fitting
  const serials = draws.map(d => d.draw_serial);
  const nums = draws.map(d => [d.num1,d.num2,d.num3,d.num4,d.num5,d.num6]);
  const nextSerial = (serials[serials.length-1] ?? 2119) + 1;
  const histSet = new Set(nums.map(d=>[...d].sort((a,b)=>a-b).join(",")));

  function isHist(n: number[]) { return histSet.has([...n].sort((a,b)=>a-b).join(",")); }

  const last20 = nums.slice(-20);
  const freq: Record<number,number> = {};
  nums.slice(-100).forEach(d=>d.forEach(n=>{freq[n]=(freq[n]??0)+1;}));

  const lam=0.95, wts=nums.map((_,i)=>Math.pow(lam,nums.length-1-i)), ws=wts.reduce((a,b)=>a+b,0);

  const combos = [
    { label:"1", color:"#2a78d6", method:"Poly deg-2 · full history",
      raw: makeUnique([0,1,2,3,4,5].map(p=>fitPredict(serials,nums.map(d=>d[p]),nextSerial))) },
    { label:"2", color:"#1baf7a", method:"Moving average · last 20",
      raw: makeUnique([0,1,2,3,4,5].map(p=>Math.round(last20.reduce((s,d)=>s+d[p],0)/20))) },
    { label:"3", color:"#4a3aa7", method:"Exp-weighted recency",
      raw: makeUnique([0,1,2,3,4,5].map(p=>Math.round(nums.reduce((s,d,i)=>s+wts[i]*d[p],0)/ws))) },
    { label:"4", color:"#eda100", method:"Most frequent · last 100",
      raw: makeUnique(Object.entries(freq).sort((a,b)=>+b[1]-+a[1]).slice(0,6).map(([n])=>+n)) },
    { label:"5", color:"#e34948", method:"Poly deg-2 · last 200",
      raw: makeUnique([0,1,2,3,4,5].map(p=>fitPredict(serials.slice(-200),nums.slice(-200).map(d=>d[p]),nextSerial))) },
  ];

  const used=new Set<string>();
  const verified = combos.map(c=>{
    let numbers=c.raw, method=c.method;
    const key=(n:number[])=>[...n].sort((a,b)=>a-b).join(",");
    if (isHist(numbers)||used.has(key(numbers))) {
      for (let d=1;d<=42;d++) {
        const cand=makeUnique([numbers[0]+d,...numbers.slice(1)]);
        if (!isHist(cand)&&!used.has(key(cand))){numbers=cand;method=c.method+" (adj)";break;}
      }
    }
    used.add(key(numbers));
    return {...c,numbers,method};
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Predictions</h1>
        <p className="text-gray-500 dark:text-gray-400 text-sm mt-1">
          Draw #{nextSerial} &middot; {draws.length.toLocaleString()} draws analyzed &middot; verified against full history
        </p>
      </div>
      <div className="space-y-3">
        {verified.map(c=>(
          <div key={c.label} className="bg-white dark:bg-gray-900 rounded-2xl border border-gray-100 dark:border-gray-800 p-5 shadow-sm">
            <div className="flex items-start gap-4">
              <div className="w-8 h-8 rounded-full flex items-center justify-center text-white font-bold text-sm flex-shrink-0"
                style={{background:c.color}}>{c.label}</div>
              <div>
                <p className="text-xs text-gray-400 mb-2">{c.method}</p>
                <div className="flex gap-2 flex-wrap">
                  {c.numbers.map(n=>(
                    <div key={n} className="w-10 h-10 rounded-full flex items-center justify-center font-bold text-white text-sm shadow-sm"
                      style={{background:ballColor(n)}}>{n}</div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
      <p className="text-xs text-gray-400 text-center">Formula-based only &middot; Not financial advice &middot; Loto 6 is random</p>
    </div>
  );
}
