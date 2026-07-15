import { getAllDraws } from "@/lib/db";
import { BallRow } from "@/components/BallRow";

export const revalidate = 3600;

function formatDate(d: string | null): string {
  if (!d) return "—";
  return new Date(d).toLocaleDateString("en-GB", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

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

      <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-sm border border-gray-100 dark:border-gray-800 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-white dark:bg-gray-900 z-10">
            <tr className="border-b border-gray-100 dark:border-gray-800">
              <th className="text-left px-4 py-3 text-xs font-medium text-gray-400 uppercase tracking-wider w-20">
                Draw
              </th>
              <th className="text-left px-4 py-3 text-xs font-medium text-gray-400 uppercase tracking-wider w-32">
                Date
              </th>
              <th className="text-left px-4 py-3 text-xs font-medium text-gray-400 uppercase tracking-wider">
                Numbers
              </th>
              <th className="text-right px-4 py-3 text-xs font-medium text-gray-400 uppercase tracking-wider w-16">
                Bonus
              </th>
            </tr>
          </thead>
          <tbody>
            {draws.map((draw) => (
              <tr
                key={draw.draw_serial}
                className="border-b border-gray-50 dark:border-gray-800/50 last:border-0 hover:bg-gray-50 dark:hover:bg-gray-800/30 transition-colors"
              >
                <td className="px-4 py-2.5 font-mono text-gray-500 dark:text-gray-400 text-xs">
                  #{draw.draw_serial}
                </td>
                <td className="px-4 py-2.5 text-gray-500 dark:text-gray-400 text-xs">
                  {formatDate(draw.draw_date)}
                </td>
                <td className="px-4 py-2.5">
                  <BallRow draw={draw} size="sm" showBonus={false} />
                </td>
                <td className="px-4 py-2.5 text-right">
                  <span className="inline-flex w-7 h-7 items-center justify-center rounded-full bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 text-xs font-bold">
                    {draw.bonus}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
