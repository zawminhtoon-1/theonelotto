"use client";
import { useState } from "react";

type Combo = { label: string; color: string; method: string; numbers: number[] };

function ballColor(n: number): string {
  if (n <= 10) return "#e74c3c";
  if (n <= 19) return "#e67e22";
  if (n <= 29) return "#27ae60";
  if (n <= 38) return "#2980b9";
  return "#8e44ad";
}

export default function PredictionsView({
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
  const [showK, setShowK] = useState<6 | 8 | 10>(6);

  const filterNum = (() => {
    const v = parseInt(filterInput, 10);
    return !isNaN(v) && v >= 1 && v <= 43 ? v : null;
  })();

  const displayed = selected === "all" ? combos : combos.filter((c) => c.label === selected);

  // Consensus: count across ALL methods
  const numCount: Record<number, number> = {};
  for (const c of combos) {
    for (const n of c.numbers) numCount[n] = (numCount[n] ?? 0) + 1;
  }

  // Which models contain the filtered number?
  const modelsWithFilter = filterNum
    ? combos.filter((c) => c.numbers.includes(filterNum)).length
    : 0;

  // Best combo per K (from backtest combination analysis)
  const BEST_COMBOS: Record<number, { labels: string[]; name: string }> = {
    6:  { labels: ["7","10","11","14"], name: "RF + kNN + ModCyc + NaiveBay" },
    8:  { labels: ["4","5","7","10","11"], name: "FreqAll + Markov + RF + kNN + ModCyc" },
    10: { labels: ["8","9","10","11"], name: "RL-Q + HMM + kNN + ModCyc" },
  };
  const bestComboConfig = BEST_COMBOS[showK];
  const bestComboCombos = combos.filter(c => bestComboConfig.labels.includes(c.label));
  const bestCount: Record<number, number> = {};
  for (const c of bestComboCombos) {
    for (const n of c.numbers) bestCount[n] = (bestCount[n] ?? 0) + 1;
  }
  const bestComboNums = Object.entries(bestCount)
    .sort((a, b) => +b[1] - +a[1])
    .slice(0, showK)
    .map(([n]) => +n)
    .sort((a, b) => a - b);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Predictions</h1>
        <p className="text-gray-500 dark:text-gray-400 text-sm mt-1">
          Draw #{nextSerial} &middot; {drawCount.toLocaleString()} draws analysed &middot; 15 models
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
          {([6, 8, 10] as const).map((k) => (
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
              max={43}
              value={filterInput}
              onChange={(e) => setFilterInput(e.target.value)}
              placeholder="1–43"
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
            <span>8+ of 15 models (consensus)</span>
          </div>
        )}
        {filterNum !== null && (
          <div className="flex items-center gap-1.5">
            <span className="inline-block w-4 h-4 rounded-full border-2 border-cyan-400 bg-cyan-100 dark:bg-cyan-900/30" />
            <span>Number {filterNum} highlighted</span>
          </div>
        )}
      </div>

      {/* Best Combo panel */}
      {selected === "all" && (
        <div className="bg-gradient-to-r from-yellow-50 to-amber-50 dark:from-yellow-900/20 dark:to-amber-900/20 rounded-2xl border border-yellow-200 dark:border-yellow-700/50 p-5 shadow-sm">
          <div className="flex items-start gap-4">
            <div className="w-8 h-8 rounded-full flex items-center justify-center text-yellow-900 dark:text-yellow-200 font-bold text-sm flex-shrink-0 bg-yellow-400 dark:bg-yellow-600">
              ★
            </div>
            <div className="flex-1">
              <p className="text-xs font-semibold text-yellow-700 dark:text-yellow-400 mb-0.5">
                Best Combo for {showK} picks · {bestComboConfig.name}
              </p>
              <p className="text-[10px] text-yellow-600/70 dark:text-yellow-500/60 mb-3">
                Top combination by backtest score across 1,001 draws
              </p>
              <div className="flex gap-2 flex-wrap">
                {bestComboNums.map(n => (
                  <div
                    key={n}
                    className="w-10 h-10 rounded-full flex items-center justify-center font-bold text-white text-sm shadow-sm ring-2 ring-yellow-400/60"
                    style={{ background: ballColor(n) }}
                  >
                    {n}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="space-y-3">
        {displayed.map((c) => {
          // Always cap to showK, keeping the numbers with most cross-model support
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
                      const hot = selected === "all" && count >= 8;
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
                                ? `#${n} — in ${count}/15 models`
                                : selected === "all"
                                ? `In ${count}/15 models`
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
        Formula-based only &middot; Not financial advice &middot; Loto 6 is random
      </p>
    </div>
  );
}


