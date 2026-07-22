import { getAllDraws } from "@/lib/db";
import type { Draw } from "@/lib/db";
import NumbersView from "./NumbersView";

export type DrawEntry = {
  serial: number;
  date: string | null;
  nums: [number, number, number, number, number, number];
  bonus: number;
  asBonus: boolean;
};

export type NumberStat = {
  n: number;
  mainHits: number;
  bonusHits: number;
  lastMainSerial: number | null;
  lastMainDate: string | null;
  coldStreak: number;
  avgGap: number;
  maxGap: number;
  minGap: number;
  gaps: number[];          // gap (draws) between each consecutive appearance
  gapSerials: number[];    // the draw serial where each gap started
  history: DrawEntry[];    // all draws where number appeared (DESC order)
  positions: [number, number, number, number, number, number];
  buckets: number[];       // hit count per era (each ~250 draws)
  bucketSize: number;
  // Option 1: recurrence — % of appearances where n reappears within W draws
  recurrence: { window: number; pct: number; count: number; total: number }[];
  // Option 3: co-appearance with previous draw's numbers
  prevOverlap: {
    avgOverlap: number;       // avg number of prev-draw numbers that reappear alongside n
    atLeastOne: number;       // % of times at least 1 prev-draw number reappears with n
    dist: number[];           // distribution [0..6] count
  };
  // Next-draw relation: what numbers appear in the draw immediately after n is drawn
  nextRelation: {
    freq: number[];   // [43] — how many times number (i+1) appeared in the very next draw
    total: number;    // appearances that had a valid next draw
  };
};

const RECURRENCE_WINDOWS = [1, 2, 3, 5, 10, 20];

function computeStats(draws: Draw[], latestSerial: number): NumberStat[] {
  // draws arrive DESC from getAllDraws — reverse to chronological
  const asc = [...draws].reverse();
  const total = asc.length;
  const BUCKET_SIZE = 250;
  const numBuckets = Math.ceil(total / BUCKET_SIZE);

  // Precompute per-draw number sets (chronological)
  const drawSets: Set<number>[] = asc.map(d => new Set([d.num1, d.num2, d.num3, d.num4, d.num5, d.num6]));

  return Array.from({ length: 43 }, (_, i) => {
    const n = i + 1;
    let mainHits = 0;
    let bonusHits = 0;
    let lastMainSerial: number | null = null;
    let lastMainDate: string | null = null;
    const positions: [number, number, number, number, number, number] = [0, 0, 0, 0, 0, 0];
    const appearances: number[] = [];       // draw indices (not serials) where n appeared as main
    const buckets: number[] = new Array(numBuckets).fill(0);
    const history: DrawEntry[] = [];

    asc.forEach((d, idx) => {
      const main = [d.num1, d.num2, d.num3, d.num4, d.num5, d.num6] as [number,number,number,number,number,number];
      const isMain = main.includes(n);
      const isBonus = d.bonus === n;
      if (isMain) {
        mainHits++;
        lastMainSerial = d.draw_serial;
        lastMainDate = d.draw_date;
        appearances.push(idx);   // store index, not serial
        positions[main.indexOf(n)]++;
        buckets[Math.floor(idx / BUCKET_SIZE)]++;
      }
      if (isBonus) bonusHits++;
      if (isMain || isBonus) {
        history.push({ serial: d.draw_serial, date: d.draw_date, nums: main, bonus: d.bonus, asBonus: isBonus && !isMain });
      }
    });
    history.reverse(); // newest first

    const coldStreak = lastMainSerial !== null ? latestSerial - lastMainSerial : total;

    let avgGap = 0;
    let maxGap = 0;
    let minGap = 0;
    const gaps: number[] = [];
    const gapSerials: number[] = [];
    if (appearances.length > 1) {
      for (let j = 1; j < appearances.length; j++) {
        const g = appearances[j] - appearances[j - 1];
        gaps.push(g);
        gapSerials.push(asc[appearances[j - 1]].draw_serial);
      }
      avgGap = gaps.reduce((a, b) => a + b, 0) / gaps.length;
      maxGap = Math.max(...gaps);
      minGap = Math.min(...gaps);
    }

    // ── Option 1: recurrence probability ──
    const recurrence = RECURRENCE_WINDOWS.map(w => {
      let count = 0;
      let eligible = 0;
      for (const idx of appearances) {
        if (idx + w >= total) continue; // not enough future draws
        eligible++;
        for (let fw = 1; fw <= w; fw++) {
          if (drawSets[idx + fw].has(n)) { count++; break; }
        }
      }
      return { window: w, count, total: eligible, pct: eligible > 0 ? count / eligible : 0 };
    });

    // ── Option 3: co-appearance with previous draw's numbers ──
    const prevDist: number[] = [0, 0, 0, 0, 0, 0, 0]; // overlap 0..6
    for (const idx of appearances) {
      if (idx === 0) continue;
      const prevSet = drawSets[idx - 1];
      const currSet = drawSets[idx];
      let overlap = 0;
      for (const num of prevSet) { if (currSet.has(num)) overlap++; }
      prevDist[overlap]++;
    }
    const prevTotal = prevDist.reduce((a, b) => a + b, 0);
    const avgOverlap = prevTotal > 0
      ? prevDist.reduce((s, c, k) => s + k * c, 0) / prevTotal
      : 0;
    const atLeastOne = prevTotal > 0
      ? prevDist.slice(1).reduce((a, b) => a + b, 0) / prevTotal
      : 0;

    // ── Next-draw relation: what numbers follow in the very next draw ──
    const nextFreq = new Array(43).fill(0);
    let nextTotal = 0;
    for (const idx of appearances) {
      if (idx + 1 >= total) continue; // no next draw available
      nextTotal++;
      for (const num of drawSets[idx + 1]) {
        nextFreq[num - 1]++;
      }
    }

    return {
      n, mainHits, bonusHits, lastMainSerial, lastMainDate, coldStreak,
      avgGap, maxGap, minGap, gaps, gapSerials, history, positions, buckets, bucketSize: BUCKET_SIZE,
      recurrence,
      prevOverlap: { avgOverlap, atLeastOne, dist: prevDist },
      nextRelation: { freq: nextFreq, total: nextTotal },
    };
  });
}

export default async function NumbersPage() {
  const draws = await getAllDraws();
  const latestSerial = draws[0]?.draw_serial ?? 0;
  const stats = computeStats(draws, latestSerial);

  return (
    <NumbersView
      stats={stats}
      totalDraws={draws.length}
      latestSerial={latestSerial}
    />
  );
}
