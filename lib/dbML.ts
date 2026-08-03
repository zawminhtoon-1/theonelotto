import { neon } from "@neondatabase/serverless";

const sql = neon(process.env.DATABASE_URL!);

export interface MiniLotoDraw {
  draw_serial: number;
  draw_date: string | null;
  num1: number;
  num2: number;
  num3: number;
  num4: number;
  num5: number;
  bonus: number;
}

export async function getLatestMiniLotoDraw(): Promise<MiniLotoDraw> {
  const rows = await sql`
    SELECT draw_serial, draw_date::text, num1, num2, num3, num4, num5, bonus
    FROM miniloto_results
    ORDER BY draw_serial DESC
    LIMIT 1
  `;
  return rows[0] as MiniLotoDraw;
}

export async function getRecentMiniLotoDraws(limit = 20): Promise<MiniLotoDraw[]> {
  const rows = await sql`
    SELECT draw_serial, draw_date::text, num1, num2, num3, num4, num5, bonus
    FROM miniloto_results
    ORDER BY draw_serial DESC
    LIMIT ${limit}
  `;
  return rows as MiniLotoDraw[];
}

export async function getAllMiniLotoDraws(): Promise<MiniLotoDraw[]> {
  const rows = await sql`
    SELECT draw_serial, draw_date::text, num1, num2, num3, num4, num5, bonus
    FROM miniloto_results
    ORDER BY draw_serial DESC
  `;
  return rows as MiniLotoDraw[];
}

export async function getMiniLotoCount(): Promise<number> {
  const rows = await sql`SELECT COUNT(*)::int AS c FROM miniloto_results`;
  return (rows[0] as { c: number }).c;
}
