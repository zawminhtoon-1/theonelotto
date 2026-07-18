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

  const displayed = selected === "all" ? combos : combos.filter((c) => c.label === selected);

  // Consensus: count across ALL methods
  const numCount: Record<number, number> = {};
  for (const c of combos) {
    for (const n of c.numbers) numCount[n] = (numCount[n] ?? 0) + 1;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Predictions</h1>
        <p className="text-gray-500 dark:text-gray-400 text-sm mt-1">
          Draw #{nextSerial} &middot; {drawCount.toLocaleString()} draws analysed &middot; 15 candidates per model
        </p>
      </div>

      {/* Model selector */}
      <div className="flex items-center gap-3 flex-wrap">
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

      {/* Consensus legend */}
      {selected === "all" && (
        <div className="flex items-center gap-2 text-xs text-gray-400">
          <span className="inline-block w-5 h-5 rounded-full border-2 border-yellow-400 bg-yellow-100 dark:bg-yellow-900/30" />
          <span>Numbers appearing in 6+ models (strong consensus)</span>
        </div>
      )}

      <div className="space-y-3">
        {displayed.map((c) => (
          <div
            key={c.label}
            className="bg-white dark:bg-gray-900 rounded-2xl border border-gray-100 dark:border-gray-800 p-5 shadow-sm"
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
                  {c.numbers.map((n) => {
                    const count = numCount[n] ?? 0;
                    const hot = selected === "all" && count >= 6;
                    return (
                      <div key={n} className="relative">
                        <div
                          className={`w-10 h-10 rounded-full flex items-center justify-center font-bold text-white text-sm shadow-sm${
                            hot ? " ring-2 ring-yellow-400 ring-offset-1 dark:ring-offset-gray-900" : ""
                          }`}
                          style={{ background: ballColor(n) }}
                          title={selected === "all" ? `In ${count}/10 models` : ""}
                        >
                          {n}
                        </div>
                        {hot && (
                          <span className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-yellow-400 text-yellow-900 text-[9px] font-bold flex items-center justify-center">
                            {count}
                          </span>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      <p className="text-xs text-gray-400 text-center">
        Formula-based only &middot; Not financial advice &middot; Loto 6 is random
      </p>
    </div>
  );
}


