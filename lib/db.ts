import { neon } from "@neondatabase/serverless";

// Set DATABASE_URL in .env.local:
// DATABASE_URL=postgresql://neondb_owner:<password>@ep-hidden-wind-a1q0el7s-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require
const sql = neon(process.env.DATABASE_URL!);

export interface Draw {
  draw_serial: number;
  draw_date: string | null;
  num1: number;
  num2: number;
  num3: number;
  num4: number;
  num5: number;
  num6: number;
  bonus: number;
}

export async function getLatestDraw(): Promise<Draw> {
  const rows = await sql`
    SELECT draw_serial, draw_date::text, num1, num2, num3, num4, num5, num6, bonus
    FROM loto6_results
    ORDER BY draw_serial DESC
    LIMIT 1
  `;
  return rows[0] as Draw;
}

export async function getRecentDraws(limit = 20): Promise<Draw[]> {
  const rows = await sql`
    SELECT draw_serial, draw_date::text, num1, num2, num3, num4, num5, num6, bonus
    FROM loto6_results
    ORDER BY draw_serial DESC
    LIMIT ${limit}
  `;
  return rows as Draw[];
}

export async function getAllDraws(): Promise<Draw[]> {
  const rows = await sql`
    SELECT draw_serial, draw_date::text, num1, num2, num3, num4, num5, num6, bonus
    FROM loto6_results
    ORDER BY draw_serial DESC
  `;
  return rows as Draw[];
}

export async function getDrawBySerial(serial: number): Promise<Draw | null> {
  const rows = await sql`
    SELECT draw_serial, draw_date::text, num1, num2, num3, num4, num5, num6, bonus
    FROM loto6_results
    WHERE draw_serial = ${serial}
  `;
  return (rows[0] as Draw) ?? null;
}
