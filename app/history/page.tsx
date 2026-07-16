import { getAllDraws } from "@/lib/db";
import { HistoryTable } from "@/components/HistoryTable";

export const revalidate = 3600;

export default async function HistoryPage() {
  const draws = await getAllDraws();

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">All Draws</h1>
        <p className="text-gray-500 dark:text-gray-400 text-sm mt-1">
          {draws.length.toLocaleString()} draws · Loto 6 Japan
        </p>
      </div>
      <HistoryTable draws={draws} />
    </div>
  );
}
