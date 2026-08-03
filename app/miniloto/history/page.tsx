import { getAllMiniLotoDraws } from "@/lib/dbML";
import { MiniLotoHistoryTable } from "@/components/MiniLotoHistoryTable";

export const revalidate = 300;

export default async function MiniLotoHistoryPage() {
  const draws = await getAllMiniLotoDraws();

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">MiniLoto — All Draws</h1>
        <p className="text-gray-500 dark:text-gray-400 text-sm mt-1">
          {draws.length.toLocaleString()} draws · MiniLoto Japan
        </p>
      </div>
      <MiniLotoHistoryTable draws={draws} />
    </div>
  );
}
