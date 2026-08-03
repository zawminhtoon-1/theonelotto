"use client";

import { useState, useMemo } from "react";
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

function getBallColor(n: number): string {
  if (n <= 8) return "#e74c3c";
  if (n <= 15) return "#e67e22";
  if (n <= 22) return "#2ecc71";
  if (n <= 29) return "#3498db";
  return "#9b59b6";
}

export function Loto7HistoryTable({ draws }: { draws: Loto7Draw[] }) {
  const [selectedNums, setSelectedNums] = useState<Set<number>>(new Set());
  const [drawFrom, setDrawFrom] = useState("");
  const [drawTo, setDrawTo] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const toggleNum = (n: number) => {
    setSelectedNums((prev) => {
      const next = new Set(prev);
      if (next.has(n)) next.delete(n);
      else next.add(n);
      return next;
    });
  };

  const filtered = useMemo(() => {
    const from = drawFrom.trim() === "" ? null : parseInt(drawFrom, 10);
    const to = drawTo.trim() === "" ? null : parseInt(drawTo, 10);
    return draws.filter((draw) => {
      if (from !== null && draw.draw_serial < from) return false;
      if (to !== null && draw.draw_serial > to) return false;
      if (dateFrom && (!draw.draw_date || draw.draw_date < dateFrom)) return false;
      if (dateTo && (!draw.draw_date || draw.draw_date > dateTo)) return false;
      if (selectedNums.size > 0) {
        const allNums = new Set([
          draw.num1, draw.num2, draw.num3, draw.num4, draw.num5, draw.num6, draw.num7,
          draw.bonus1, draw.bonus2,
        ]);
        for (const n of selectedNums) {
          if (!allNums.has(n)) return false;
        }
      }
      return true;
    });
  }, [draws, drawFrom, drawTo, dateFrom, dateTo, selectedNums]);

  const hasFilter = selectedNums.size > 0 || drawFrom !== "" || drawTo !== "" || dateFrom !== "" || dateTo !== "";

  const clearAll = () => {
    setSelectedNums(new Set());
    setDrawFrom(""); setDrawTo("");
    setDateFrom(""); setDateTo("");
  };

  return (
    <div>
      {/* Filters */}
      <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-sm border border-gray-100 dark:border-gray-800 p-4 mb-4 space-y-4">
        <div className="flex flex-wrap items-end gap-x-6 gap-y-3">
          <div>
            <label className="block text-xs text-gray-400 mb-1">Draw # from</label>
            <input
              type="number"
              min={1}
              placeholder="e.g. 1"
              value={drawFrom}
              onChange={(e) => setDrawFrom(e.target.value)}
              className="w-24 px-2 py-1.5 text-sm rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-200 focus:outline-none focus:ring-1 focus:ring-blue-400"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">to</label>
            <input
              type="number"
              min={1}
              placeholder="e.g. 688"
              value={drawTo}
              onChange={(e) => setDrawTo(e.target.value)}
              className="w-24 px-2 py-1.5 text-sm rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-200 focus:outline-none focus:ring-1 focus:ring-blue-400"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">Date from</label>
            <input
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              className="px-2 py-1.5 text-sm rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-200 focus:outline-none focus:ring-1 focus:ring-blue-400"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">Date to</label>
            <input
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              className="px-2 py-1.5 text-sm rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-200 focus:outline-none focus:ring-1 focus:ring-blue-400"
            />
          </div>
          {hasFilter && (
            <button
              onClick={clearAll}
              className="px-3 py-1.5 text-xs rounded-lg border border-gray-200 dark:border-gray-700 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition-colors"
            >
              Clear all
            </button>
          )}
        </div>

        <div>
          <label className="block text-xs text-gray-400 mb-2">
            Contains number{selectedNums.size > 0 ? ` (${selectedNums.size} selected, draw must contain all)` : ""}
          </label>
          <div className="flex flex-wrap gap-1.5">
            {Array.from({ length: 37 }, (_, i) => i + 1).map((n) => {
              const active = selectedNums.has(n);
              return (
                <button
                  key={n}
                  onClick={() => toggleNum(n)}
                  className={`w-7 h-7 rounded-full text-white text-[11px] font-bold shadow-sm transition-all flex items-center justify-center ${
                    active ? "ring-2 ring-offset-1 ring-gray-900 dark:ring-white dark:ring-offset-gray-900 scale-110" : "opacity-70 hover:opacity-100"
                  }`}
                  style={{ background: getBallColor(n) }}
                  title={`Filter draws containing ${n}`}
                >
                  {n}
                </button>
              );
            })}
          </div>
        </div>

        {hasFilter && (
          <p className="text-xs text-gray-400">
            {filtered.length.toLocaleString()} / {draws.length.toLocaleString()} draws match
          </p>
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
            </tr>
          </thead>
          <tbody>
            {filtered.map((draw) => (
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
            {filtered.length === 0 && (
              <tr>
                <td colSpan={3} className="px-4 py-8 text-center text-xs text-gray-400">
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
