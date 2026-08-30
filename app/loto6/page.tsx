import { getLatestDraw, getRecentDraws } from "@/lib/db";
import { BallRow } from "@/components/BallRow";

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

const QUICK_LINKS = [
  { href: "/predictions", icon: "🎯", label: "Predictions", desc: "16-method consensus picks for the next draw" },
  { href: "/backtest.html", icon: "📊", label: "Backtest", desc: "1000-draw walk-forward evaluation, all 16 methods" },
  { href: "/xoshiro_elim_2132.html", icon: "✂️", label: "Latest Elimination", desc: "Draw #2132 xoshiro combinatorial elimination" },
  { href: "/xoshiro_seed_scan_k38.html", icon: "🔷", label: "Xoshiro Seed Scan K=38", desc: "1,000,001 seeds, best-performing scan" },
  { href: "/modular_cycle.html", icon: "🔁", label: "Modular Cycle", desc: "mod-43 cycle strategy page" },
  { href: "/combo_evo.html", icon: "🧬", label: "Combo Evo", desc: "Combination evolution / anti-pick analysis" },
  { href: "/numbers", icon: "🔢", label: "Number Frequency", desc: "All-time number frequency breakdown" },
  { href: "/history", icon: "📋", label: "Full History", desc: "Every Loto 6 draw on record" },
];

export default async function Loto6HomePage() {
  const [latest, recent] = await Promise.all([
    getLatestDraw(),
    getRecentDraws(10),
  ]);

  return (
    <div className="space-y-10">
      {/* Latest draw hero */}
      <section className="bg-white dark:bg-gray-900 rounded-2xl shadow-sm border border-gray-100 dark:border-gray-800 p-6 sm:p-8">
        <div className="flex items-start justify-between mb-6">
          <div>
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-1">
              Loto 6 &middot; Latest Draw
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
        <BallRow draw={latest} size="lg" />
        <p className="mt-4 text-xs text-gray-400">
          Bonus ball shown in grey · Numbers 1–10 red · 11–19 orange · 20–29 green · 30–38 blue · 39–43 purple
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
            <p className="text-xl font-bold text-gray-900 dark:text-white">{latest.draw_serial.toLocaleString()}</p>
          </div>
          <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-sm border border-gray-100 dark:border-gray-800 p-4">
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-1">Pool</p>
            <p className="text-xl font-bold text-gray-900 dark:text-white">6 from 43</p>
          </div>
          <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-sm border border-gray-100 dark:border-gray-800 p-4">
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-1">Bonus</p>
            <p className="text-xl font-bold text-gray-900 dark:text-white">1 number</p>
          </div>
          <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-sm border border-gray-100 dark:border-gray-800 p-4">
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-1">Drawn</p>
            <p className="text-xl font-bold text-gray-900 dark:text-white">Mon &amp; Thu</p>
          </div>
        </div>
      </section>

      {/* Quick links */}
      <section>
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          Explore
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
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
          More prediction strategies, xoshiro research, and elimination pages in the Predict / Xoshiro Research nav menus above.
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
                    <BallRow draw={draw} size="sm" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mt-4 text-center">
          <a
            href="/history"
            className="inline-flex items-center gap-1.5 text-sm text-blue-600 dark:text-blue-400 hover:underline"
          >
            View all {latest.draw_serial}+ draws →
          </a>
        </div>
      </section>
    </div>
  );
}
