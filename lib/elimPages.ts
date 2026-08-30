import fs from "fs";
import path from "path";

export interface ElimPageInfo {
  drawSerial: number;
  href: string;
}

/**
 * Scans /public for filenames matching `pattern` (which must have a single
 * capture group for the draw serial) and returns the entry with the highest
 * draw serial, or null if none exist. This makes "latest elimination page"
 * links self-updating: drop a new xoshiro_elim_2133.html / loto7_elim_692.html
 * into /public and it's picked up automatically, no code change needed.
 */
function findLatestMatchingFile(pattern: RegExp): ElimPageInfo | null {
  const publicDir = path.join(process.cwd(), "public");
  let files: string[];
  try {
    files = fs.readdirSync(publicDir);
  } catch {
    return null;
  }

  let best: ElimPageInfo | null = null;
  for (const file of files) {
    const match = file.match(pattern);
    if (!match) continue;
    const drawSerial = parseInt(match[1], 10);
    if (Number.isNaN(drawSerial)) continue;
    if (!best || drawSerial > best.drawSerial) {
      best = { drawSerial, href: `/${file}` };
    }
  }
  return best;
}

/** Latest Loto 6 xoshiro elimination page, e.g. /xoshiro_elim_2132.html */
export function getLatestLoto6ElimPage(): ElimPageInfo | null {
  return findLatestMatchingFile(/^xoshiro_elim_(\d+)\.html$/);
}

/** Latest Loto 7 xoshiro elimination page, e.g. /loto7_elim_691.html */
export function getLatestLoto7ElimPage(): ElimPageInfo | null {
  return findLatestMatchingFile(/^loto7_elim_(\d+)\.html$/);
}
