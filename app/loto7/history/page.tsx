import { getAllLoto7Draws } from "@/lib/db7";
import { Loto7HistoryTable } from "@/components/Loto7HistoryTable";

export const revalidate = 300;

export default async function Loto7HistoryPage() {
  const draws = await getAllLoto7Draws();

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Loto 7 — All Draws</h1>
        <p className="text-gray-500 dark:text-gray-400 text-sm mt-1">
          {draws.length.toLocaleString()} draws · Loto 7 Japan
        </p>
      </div>
      <Loto7HistoryTable draws={draws} />
    </div>
  );
}
