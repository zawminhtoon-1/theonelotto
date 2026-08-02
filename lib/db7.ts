import { neon } from "@neondatabase/serverless";

const sql = neon(process.env.DATABASE_URL!);

export interface Loto7Draw {
  draw_serial: number;
  draw_date: string | null;
  num1: number;
  num2: number;
  num3: number;
  num4: number;
  num5: number;
  num6: number;
  num7: number;
  bonus1: number;
  bonus2: number;
}

export async function getLatestLoto7Draw(): Promise<Loto7Draw> {
  const rows = await sql`
    SELECT draw_serial, draw_date::text, num1, num2, num3, num4, num5, num6, num7, bonus1, bonus2
    FROM loto7_results
    ORDER BY draw_serial DESC
    LIMIT 1
  `;
  return rows[0] as Loto7Draw;
}

export async function getRecentLoto7Draws(limit = 20): Promise<Loto7Draw[]> {
  const rows = await sql`
    SELECT draw_serial, draw_date::text, num1, num2, num3, num4, num5, num6, num7, bonus1, bonus2
    FROM loto7_results
    ORDER BY draw_serial DESC
    LIMIT ${limit}
  `;
  return rows as Loto7Draw[];
}

export async function getAllLoto7Draws(): Promise<Loto7Draw[]> {
  const rows = await sql`
    SELECT draw_serial, draw_date::text, num1, num2, num3, num4, num5, num6, num7, bonus1, bonus2
    FROM loto7_results
    ORDER BY draw_serial DESC
  `;
  return rows as Loto7Draw[];
}

export async function getLoto7Count(): Promise<number> {
  const rows = await sql`SELECT COUNT(*)::int AS c FROM loto7_results`;
  return (rows[0] as { c: number }).c;
}
