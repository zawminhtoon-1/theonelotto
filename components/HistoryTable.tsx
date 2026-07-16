"use client";

import { useState, useMemo } from "react";
import { Draw } from "@/lib/db";
import { BallRow } from "@/components/BallRow";

function formatDate(d: string | null): string {
  if (!d) return "—";
  return new Date(d).toLocaleDateString("en-GB", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function HistoryTable({ draws }: { draws: Draw[] }) {
  const [filters, setFilters] = useState<(string)[]>(["", "", "", "", "", ""]);

  const parsedFilters = filters.map(f => f.trim() === "" ? null : parseInt(f));

  const filtered = useMemo(() => {
    const active = parsedFilters.some(f => f !== null);
    if (!active) return draws;
    return draws.filter(draw => {
      const nums = [draw.num1, draw.num2, draw.num3, draw.num4, draw.num5, draw.num6]
        .sort((a, b) => a - b);
      return parsedFilters.every((f, i) => f === null || nums[i] === f);
    });
  }, [draws, filters]);

  const hasFilter = parsedFilters.some(f => f !== null);

  return (
    <div>
      {/* Position filters */}
      <div className="flex flex-wrap gap-2 items-center mb-4">
        <span className="text-xs text-gray-400">Filter by position:</span>
        {[1, 2, 3, 4, 5, 6].map(pos => (
          <input
            key={pos}
            type="number"
            min={1}
            max={43}
            placeholder={`Pos ${pos}`}
            value={filters[pos - 1]}
            onChange={e => {
              const next = [...filters];
              next[pos - 1] = e.target.value;
              setFilters(next);
            }}
            className="w-16 px-2 py-1 text-xs rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-200 focus:outline-none focus:ring-1 focus:ring-blue-400"
          />
        ))}
        {hasFilter && (
          <button
            onClick={() => setFilters(["", "", "", "", "", ""])}
            className="px-2 py-1 text-xs rounded-lg border border-gray-200 dark:border-gray-700 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition-colors"
          >
            Clear
          </button>
        )}
        {hasFilter && (
          <span className="text-xs text-gray-400">
            {filtered.length} / {draws.length} draws
          </span>
        )}
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
            {filtered.map(draw => (
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
            {filtered.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-xs text-gray-400">
                  No draws match these filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
