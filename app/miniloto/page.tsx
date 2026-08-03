import { getLatestMiniLotoDraw, getRecentMiniLotoDraws, getMiniLotoCount } from "@/lib/dbML";
import { MiniLotoBallRow } from "@/components/MiniLotoBallRow";

export const revalidate = 300; // revalidate every 5 minutes

function formatDate(d: string | null): string {
  if (!d) return "—";
  return new Date(d).toLocaleDateString("en-GB", {
    weekday: "short",
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export default async function MiniLotoHomePage() {
  const [latest, recent, count] = await Promise.all([
    getLatestMiniLotoDraw(),
    getRecentMiniLotoDraws(20),
    getMiniLotoCount(),
  ]);

  return (
    <div className="space-y-10">
      {/* Latest draw hero */}
      <section className="bg-white dark:bg-gray-900 rounded-2xl shadow-sm border border-gray-100 dark:border-gray-800 p-6 sm:p-8">
        <div className="flex items-start justify-between mb-6">
          <div>
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-1">
              MiniLoto &middot; Latest Draw
            </p>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
              Draw #{latest.draw_serial}
            </h1>
            <p className="text-gray-500 dark:text-gray-400 text-sm mt-0.5">
              {formatDate(latest.draw_date)}
            </p>
          </div>
          <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-400">
            Latest
          </span>
        </div>
        <MiniLotoBallRow draw={latest} size="lg" />
        <p className="mt-4 text-xs text-gray-400">
          Pick 5 from 1&ndash;31, plus 1 bonus number (shown in grey) &middot; Drawn weekly on Tuesdays &middot;
          Numbers 1&ndash;7 red &middot; 8&ndash;13 orange &middot; 14&ndash;19 green &middot; 20&ndash;25 blue &middot; 26&ndash;31 purple
        </p>
      </section>

      {/* Recent history */}
      <section>
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          Recent Draws
        </h2>
        <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-sm border border-gray-100 dark:border-gray-800 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 dark:border-gray-800">
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-400 uppercase tracking-wider w-20">
                  Draw
                </th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-400 uppercase tracking-wider w-36">
                  Date
                </th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-400 uppercase tracking-wider">
                  Numbers
                </th>
              </tr>
            </thead>
            <tbody>
              {recent.map((draw, i) => (
                <tr
                  key={draw.draw_serial}
                  className={`border-b border-gray-50 dark:border-gray-800/50 last:border-0 ${
                    i === 0 ? "bg-blue-50/30 dark:bg-blue-900/10" : ""
                  }`}
                >
                  <td className="px-4 py-3 font-mono text-gray-500 dark:text-gray-400">
                    #{draw.draw_serial}
                  </td>
                  <td className="px-4 py-3 text-gray-500 dark:text-gray-400 text-xs">
                    {formatDate(draw.draw_date)}
                  </td>
                  <td className="px-4 py-3">
                    <MiniLotoBallRow draw={draw} size="sm" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mt-4 text-center">
          <a
            href="/miniloto/history"
            className="inline-flex items-center gap-1.5 text-sm text-blue-600 dark:text-blue-400 hover:underline"
          >
            View all {count.toLocaleString()}+ draws →
          </a>
        </div>
      </section>
    </div>
  );
}
