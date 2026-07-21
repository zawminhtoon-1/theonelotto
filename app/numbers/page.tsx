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
};

function computeStats(draws: Draw[], latestSerial: number): NumberStat[] {
  // draws arrive DESC from getAllDraws — reverse to chronological
  const asc = [...draws].reverse();
  const total = asc.length;
  const BUCKET_SIZE = 250;
  const numBuckets = Math.ceil(total / BUCKET_SIZE);

  return Array.from({ length: 43 }, (_, i) => {
    const n = i + 1;
    let mainHits = 0;
    let bonusHits = 0;
    let lastMainSerial: number | null = null;
    let lastMainDate: string | null = null;
    const positions: [number, number, number, number, number, number] = [0, 0, 0, 0, 0, 0];
    const appearances: number[] = [];
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
        appearances.push(d.draw_serial);
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
    const gapSerials: number[] = []; // serial of the draw that started each gap
    if (appearances.length > 1) {
      for (let j = 1; j < appearances.length; j++) {
        gaps.push(appearances[j] - appearances[j - 1]);
        gapSerials.push(appearances[j - 1]);
      }
      avgGap = gaps.reduce((a, b) => a + b, 0) / gaps.length;
      maxGap = Math.max(...gaps);
      minGap = Math.min(...gaps);
    }

    return { n, mainHits, bonusHits, lastMainSerial, lastMainDate, coldStreak, avgGap, maxGap, minGap, gaps, gapSerials, history, positions, buckets, bucketSize: BUCKET_SIZE };
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
