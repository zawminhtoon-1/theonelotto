import { getLatestLoto7Draw, getRecentLoto7Draws, getLoto7Count } from "@/lib/db7";
import { getLatestLoto7ElimPage } from "@/lib/elimPages";
import { Loto7BallRow } from "@/components/Loto7BallRow";

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

const BASE_QUICK_LINKS = [
  { href: "/loto7/predictions", icon: "🎯", label: "Predictions", desc: "16-method consensus picks for the next draw" },
  { href: "/loto7_backtest_full.html", icon: "📊", label: "Full-History Backtest", desc: "All real draws, K=7–28 toggle, all 16 methods" },
  { href: "/loto7_backtest100_multik.html", icon: "🎯", label: "100-Draw Multi-K Backtest", desc: "Recent-window backtest with a K-size toggle" },
  { href: "/xoshiro_seed_scan_loto7_k30.html", icon: "🌀", label: "Xoshiro Seed Scan K=30", desc: "2,000,001 seeds, in-sample vs out-of-sample check" },
  { href: "/loto7/history", icon: "📋", label: "Full History", desc: "Every Loto 7 draw on record" },
];

export default async function Loto7HomePage() {
  const [latest, recent, count] = await Promise.all([
    getLatestLoto7Draw(),
    getRecentLoto7Draws(10),
    getLoto7Count(),
  ]);
  // Auto-discovered from /public — no manual edit needed when a new
  // loto7_elim_NNN.html lands.
  const latestElim = getLatestLoto7ElimPage();
  const QUICK_LINKS = latestElim
    ? [
        {
          href: latestElim.href,
          icon: "✂️",
          label: `Draw #${latestElim.drawSerial} Elimination`,
          desc: "Combinatorial elimination + retroactive result check",
        },
        ...BASE_QUICK_LINKS,
      ]
    : BASE_QUICK_LINKS;

  return (
    <div className="space-y-10">
      {/* Latest draw hero */}
      <section className="bg-white dark:bg-gray-900 rounded-2xl shadow-sm border border-gray-100 dark:border-gray-800 p-6 sm:p-8">
        <div className="flex items-start justify-between mb-6">
          <div>
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-1">
              Loto 7 &middot; Latest Draw
            </p>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
              Draw #{latest.draw_serial}
            </h1>
            <p className="text-gray-500 dark:text-gray-400 text-sm mt-0.5">
              {formatDate(latest.draw_date)}
            </p>
          </div>
          <div className="flex flex-col items-end gap-2">
            <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-400">
              Latest
            </span>
            {latestElim && (
              <a
                href={latestElim.href}
                className="inline-flex items-center gap-1 text-sm font-medium text-blue-600 dark:text-blue-400 hover:underline"
              >
                ✂️ Draw #{latestElim.drawSerial} Elimination →
              </a>
            )}
          </div>
        </div>
        <Loto7BallRow draw={latest} size="lg" />
        <p className="mt-4 text-xs text-gray-400">
          Pick 7 from 1&ndash;37, plus 2 bonus numbers (shown in grey) &middot; Drawn weekly on Fridays &middot;
          Numbers 1&ndash;8 red &middot; 9&ndash;15 orange &middot; 16&ndash;22 green &middot; 23&ndash;29 blue &middot; 30&ndash;37 purple
        </p>
      </section>

      {/* Key stats */}
      <section>
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          At a Glance
        </h2>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-sm border border-gray-100 dark:border-gray-800 p-4">
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-1">Draws on Record</p>
            <p className="text-xl font-bold text-gray-900 dark:text-white">{count.toLocaleString()}</p>
          </div>
          <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-sm border border-gray-100 dark:border-gray-800 p-4">
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-1">Pool</p>
            <p className="text-xl font-bold text-gray-900 dark:text-white">7 from 37</p>
          </div>
          <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-sm border border-gray-100 dark:border-gray-800 p-4">
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-1">Bonus</p>
            <p className="text-xl font-bold text-gray-900 dark:text-white">2 numbers</p>
          </div>
          <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-sm border border-gray-100 dark:border-gray-800 p-4">
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-1">Drawn</p>
            <p className="text-xl font-bold text-gray-900 dark:text-white">Fridays</p>
          </div>
        </div>
      </section>

      {/* Quick links */}
      <section>
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          Explore
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {QUICK_LINKS.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="bg-white dark:bg-gray-900 rounded-2xl shadow-sm border border-gray-100 dark:border-gray-800 p-4 hover:shadow-md hover:border-blue-200 dark:hover:border-blue-800 transition"
            >
              <div className="text-2xl mb-1.5">{link.icon}</div>
              <div className="font-semibold text-sm text-gray-900 dark:text-white mb-0.5">{link.label}</div>
              <div className="text-xs text-gray-500 dark:text-gray-400">{link.desc}</div>
            </a>
          ))}
        </div>
        <p className="mt-3 text-xs text-gray-400">
          Xoshiro Seed Scan K=25 / K=28 (earlier, narrower-window scans) also available via the Loto7 nav menu above.
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
                    <Loto7BallRow draw={draw} size="sm" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mt-4 text-center">
          <a
            href="/loto7/history"
            className="inline-flex items-center gap-1.5 text-sm text-blue-600 dark:text-blue-400 hover:underline"
          >
            View all {count.toLocaleString()}+ draws →
          </a>
        </div>
      </section>
    </div>
  );
}
