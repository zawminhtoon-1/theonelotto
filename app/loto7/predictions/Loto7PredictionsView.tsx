"use client";
import { useState } from "react";

type Combo = { label: string; color: string; method: string; numbers: number[] };

function ballColor(n: number): string {
  if (n <= 8) return "#e74c3c";
  if (n <= 15) return "#e67e22";
  if (n <= 22) return "#2ecc71";
  if (n <= 29) return "#3498db";
  return "#9b59b6";
}

export default function Loto7PredictionsView({
  combos,
  nextSerial,
  drawCount,
}: {
  combos: Combo[];
  nextSerial: number;
  drawCount: number;
}) {
  const [selected, setSelected] = useState("all");
  const [filterInput, setFilterInput] = useState("");
  const [showK, setShowK] = useState<7 | 9 | 11>(7);

  const filterNum = (() => {
    const v = parseInt(filterInput, 10);
    return !isNaN(v) && v >= 1 && v <= 37 ? v : null;
  })();

  const displayed = selected === "all" ? combos : combos.filter((c) => c.label === selected);

  // Consensus: count across ALL methods
  const numCount: Record<number, number> = {};
  for (const c of combos) {
    for (const n of c.numbers) numCount[n] = (numCount[n] ?? 0) + 1;
  }

  const modelsWithFilter = filterNum
    ? combos.filter((c) => c.numbers.includes(filterNum)).length
    : 0;

  // No Best Combo panel: unlike Loto6 (which has a real backtest-searched
  // best 3-method combination), we haven't found a combination with a
  // genuine edge over random for Loto7 yet -- individual methods hover at
  // essentially random-baseline performance (see /loto7_backtest.html), so
  // adding a "Best Combo" panel here would be presenting noise as signal.

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Loto 7 Predictions</h1>
        <p className="text-gray-500 dark:text-gray-400 text-sm mt-1">
          Draw #{nextSerial} &middot; {drawCount.toLocaleString()} draws analysed &middot; 16 models
        </p>
      </div>

      {/* Controls row */}
      <div className="flex items-center gap-4 flex-wrap">
        {/* Model selector */}
        <div className="flex items-center gap-2">
          <label className="text-sm text-gray-500 dark:text-gray-400">Model:</label>
          <select
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
            className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg
                       px-3 py-2 text-sm text-gray-800 dark:text-gray-200 shadow-sm focus:outline-none
                       focus:ring-2 focus:ring-blue-500"
          >
            <option value="all">All Models</option>
            {combos.map((c) => (
              <option key={c.label} value={c.label}>
                Model {c.label}: {c.method}
              </option>
            ))}
          </select>
        </div>

        {/* Pick count toggle */}
        <div className="flex items-center gap-1 bg-gray-100 dark:bg-gray-800 rounded-lg p-1">
          {([7, 9, 11] as const).map((k) => (
            <button
              key={k}
              onClick={() => setShowK(k)}
              className={`px-3 py-1 rounded-md text-sm font-medium transition-colors${
                showK === k
                  ? " bg-white dark:bg-gray-700 text-gray-900 dark:text-white shadow-sm"
                  : " text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
              }`}
            >
              {k} picks
            </button>
          ))}
        </div>

        {/* Number highlight filter */}
        <div className="flex items-center gap-2">
          <label className="text-sm text-gray-500 dark:text-gray-400">Highlight:</label>
          <div className="relative">
            <input
              type="number"
              min={1}
              max={37}
              value={filterInput}
              onChange={(e) => setFilterInput(e.target.value)}
              placeholder="1–37"
              className="w-20 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg
                         px-3 py-2 text-sm text-gray-800 dark:text-gray-200 shadow-sm focus:outline-none
                         focus:ring-2 focus:ring-cyan-500 [appearance:textfield]
                         [&::-webkit-outer-spin-button]:appearance-none
                         [&::-webkit-inner-spin-button]:appearance-none"
            />
            {filterInput && (
              <button
                onClick={() => setFilterInput("")}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 text-xs"
              >
                ✕
              </button>
            )}
          </div>
          {filterNum !== null && (
            <span className="text-xs text-cyan-600 dark:text-cyan-400 font-medium">
              #{filterNum} in {modelsWithFilter}/{combos.length} models
            </span>
          )}
        </div>
      </div>

      {/* Legends */}
      <div className="flex items-center gap-4 flex-wrap text-xs text-gray-400">
        {selected === "all" && (
          <div className="flex items-center gap-1.5">
            <span className="inline-block w-4 h-4 rounded-full border-2 border-yellow-400 bg-yellow-100 dark:bg-yellow-900/30" />
            <span>9+ of 16 models (consensus)</span>
          </div>
        )}
        {filterNum !== null && (
          <div className="flex items-center gap-1.5">
            <span className="inline-block w-4 h-4 rounded-full border-2 border-cyan-400 bg-cyan-100 dark:bg-cyan-900/30" />
            <span>Number {filterNum} highlighted</span>
          </div>
        )}
      </div>

      {/* No Best Combo panel -- see comment above: no method combination has
          shown a genuine edge over random in the Loto7 backtest yet. */}
      <div className="bg-gray-50 dark:bg-gray-900/50 rounded-2xl border border-gray-100 dark:border-gray-800 p-4 text-xs text-gray-400">
        No &quot;Best Combo&quot; panel here (yet): unlike Loto6, a backtest search across
        Loto7 method combinations hasn&apos;t found any combination with a real edge over
        random guessing &mdash; see the{" "}
        <a href="/loto7_backtest.html" className="text-cyan-600 dark:text-cyan-400 hover:underline">
          backtest report
        </a>{" "}
        for the full comparison. We&apos;d rather say that honestly than show a misleading panel.
      </div>

      <div className="space-y-3">
        {displayed.map((c) => {
          const visibleNums = [...c.numbers]
            .sort((a, b) => (numCount[b] ?? 0) - (numCount[a] ?? 0))
            .slice(0, showK)
            .sort((a, b) => a - b);
          const hasFilter = filterNum !== null && visibleNums.includes(filterNum);
          return (
            <div
              key={c.label}
              className={`bg-white dark:bg-gray-900 rounded-2xl border p-5 shadow-sm transition-opacity${
                filterNum !== null && !hasFilter
                  ? " border-gray-100 dark:border-gray-800 opacity-40"
                  : filterNum !== null && hasFilter
                  ? " border-cyan-300 dark:border-cyan-700"
                  : " border-gray-100 dark:border-gray-800"
              }`}
            >
              <div className="flex items-start gap-4">
                <div
                  className="w-8 h-8 rounded-full flex items-center justify-center text-white font-bold text-sm flex-shrink-0"
                  style={{ background: c.color }}
                >
                  {c.label}
                </div>
                <div className="flex-1">
                  <p className="text-xs text-gray-400 mb-3">{c.method}</p>
                  <div className="flex gap-2 flex-wrap">
                    {visibleNums.map((n) => {
                      const count = numCount[n] ?? 0;
                      const hot = selected === "all" && count >= 9;
                      const isFilterMatch = filterNum !== null && n === filterNum;
                      const dimmed = filterNum !== null && !isFilterMatch;
                      return (
                        <div key={n} className="relative">
                          <div
                            className={`w-10 h-10 rounded-full flex items-center justify-center font-bold text-white text-sm shadow-sm transition-all${
                              isFilterMatch
                                ? " ring-2 ring-cyan-400 ring-offset-2 dark:ring-offset-gray-900 scale-110"
                                : hot
                                ? " ring-2 ring-yellow-400 ring-offset-1 dark:ring-offset-gray-900"
                                : ""
                            }${dimmed ? " opacity-25" : ""}`}
                            style={{ background: ballColor(n) }}
                            title={
                              isFilterMatch
                                ? `#${n} — in ${count}/16 models`
                                : selected === "all"
                                ? `In ${count}/16 models`
                                : ""
                            }
                          >
                            {n}
                          </div>
                          {hot && !isFilterMatch && (
                            <span className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-yellow-400 text-yellow-900 text-[9px] font-bold flex items-center justify-center">
                              {count}
                            </span>
                          )}
                          {isFilterMatch && (
                            <span className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-cyan-400 text-cyan-900 text-[9px] font-bold flex items-center justify-center">
                              ✓
                            </span>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <p className="text-xs text-gray-400 text-center">
        Formula-based only &middot; Not financial advice &middot; Loto 7 is random
      </p>
    </div>
  );
}
