"use client";

import { Loto7Draw } from "@/lib/db7";
import { Loto7BallRow } from "@/components/Loto7BallRow";

function formatDate(d: string | null): string {
  if (!d) return "—";
  return new Date(d).toLocaleDateString("en-GB", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function Loto7HistoryTable({ draws }: { draws: Loto7Draw[] }) {
  return (
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
          </tr>
        </thead>
        <tbody>
          {draws.map(draw => (
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
                <Loto7BallRow draw={draw} size="sm" />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
