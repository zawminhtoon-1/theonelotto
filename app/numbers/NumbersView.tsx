"use client";
import { useState } from "react";
import type { NumberStat, DrawEntry } from "./page";

function ballColor(n: number): string {
  if (n <= 10) return "#e74c3c";
  if (n <= 19) return "#e67e22";
  if (n <= 29) return "#27ae60";
  if (n <= 38) return "#2980b9";
  return "#8e44ad";
}

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="bg-gray-50 dark:bg-gray-800 rounded-xl p-3 flex flex-col gap-1">
      <span className="text-xs text-gray-400">{label}</span>
      <span className="text-lg font-bold text-gray-900 dark:text-white">{value}</span>
      {sub && <span className="text-xs text-gray-400">{sub}</span>}
    </div>
  );
}

export default function NumbersView({
  stats,
  totalDraws,
  latestSerial,
}: {
  stats: NumberStat[];
  totalDraws: number;
  latestSerial: number;
}) {
  const [selected, setSelected] = useState(1);
  const s = stats[selected - 1];

  const maxBucket = Math.max(...s.buckets, 1);
  const maxPos = Math.max(...s.positions, 1);
  const expectedPerBucket = (s.mainHits / s.buckets.length) || 0;

  const posLabels = ["1st", "2nd", "3rd", "4th", "5th", "6th"];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Number Profiles</h1>
        <p className="text-gray-500 dark:text-gray-400 text-sm mt-1">
          {totalDraws.toLocaleString()} draws analysed · draw #{latestSerial} latest · click a ball to profile it
        </p>
      </div>

      {/* Ball grid 1–43 */}
      <div className="flex flex-wrap gap-2">
        {stats.map((st) => {
          const freq = st.mainHits / totalDraws;
          const isHot = freq > 6 / 43 * 1.1;
          const isCold = st.coldStreak > 30;
          return (
            <button
              key={st.n}
              onClick={() => setSelected(st.n)}
              title={`#${st.n} · ${st.mainHits} hits · cold ${st.coldStreak}`}
              className={`w-9 h-9 rounded-full text-white text-sm font-bold transition-all
                ${selected === st.n ? "ring-4 ring-offset-2 ring-offset-white dark:ring-offset-gray-950 scale-125 z-10" : "opacity-80 hover:opacity-100 hover:scale-110"}
                ${isCold && selected !== st.n ? "opacity-40" : ""}
              `}
              style={{ background: ballColor(st.n) }}
            >
              {st.n}
            </button>
          );
        })}
      </div>

      {/* Profile panel */}
      <div className="bg-white dark:bg-gray-900 rounded-2xl border border-gray-100 dark:border-gray-800 shadow-sm p-6 space-y-6">

        {/* Title row */}
        <div className="flex items-center gap-4">
          <div
            className="w-14 h-14 rounded-full flex items-center justify-center text-white text-xl font-bold shadow-md flex-shrink-0"
            style={{ background: ballColor(s.n) }}
          >
            {s.n}
          </div>
          <div>
            <h2 className="text-xl font-bold text-gray-900 dark:text-white">Number {s.n}</h2>
            <p className="text-sm text-gray-400">
              {s.coldStreak === 0
                ? "🔥 Appeared in latest draw"
                : s.coldStreak <= 10
                ? `🟡 Last seen ${s.coldStreak} draw${s.coldStreak > 1 ? "s" : ""} ago`
                : `🧊 Cold — ${s.coldStreak} draws since last hit`}
            </p>
          </div>
        </div>

        {/* Stat cards */}
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          <StatCard
            label="Main ball hits"
            value={s.mainHits}
            sub={`${((s.mainHits / totalDraws) * 100).toFixed(1)}% of draws`}
          />
          <StatCard
            label="Bonus ball hits"
            value={s.bonusHits}
            sub={`${((s.bonusHits / totalDraws) * 100).toFixed(1)}% of draws`}
          />
          <StatCard
            label="Expected frequency"
            value={`${((6 / 43) * 100).toFixed(1)}%`}
            sub={`${((s.mainHits / totalDraws / (6 / 43))).toFixed(2)}× actual lift`}
          />
          <StatCard
            label="Last seen"
            value={s.lastMainSerial !== null ? `Draw #${s.lastMainSerial}` : "Never"}
            sub={s.lastMainDate ?? undefined}
          />
          <StatCard
            label="Cold streak"
            value={`${s.coldStreak} draws`}
            sub={s.avgGap > 0 ? `avg gap ${s.avgGap.toFixed(1)}` : "—"}
          />
          <StatCard
            label="Longest gap"
            value={s.maxGap > 0 ? `${s.maxGap} draws` : "—"}
            sub={s.mainHits > 0 ? `${s.mainHits} total appearances` : "no appearances"}
          />
        </div>

        {/* Position breakdown */}
        <div>
          <h3 className="text-sm font-semibold text-gray-500 dark:text-gray-400 mb-3 uppercase tracking-wide">
            Position within draw (1st = lowest, 6th = highest)
          </h3>
          <div className="flex gap-2 items-end h-20">
            {s.positions.map((count, pi) => {
              const pct = maxPos > 0 ? count / maxPos : 0;
              return (
                <div key={pi} className="flex-1 flex flex-col items-center gap-1">
                  <span className="text-xs text-gray-400">{count}</span>
                  <div
                    className="w-full rounded-t-sm transition-all"
                    style={{
                      height: `${Math.max(4, pct * 60)}px`,
                      background: ballColor(s.n),
                      opacity: 0.5 + pct * 0.5,
                    }}
                  />
                  <span className="text-xs text-gray-400">{posLabels[pi]}</span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Recurrence probability */}
        <div>
          <h3 className="text-sm font-semibold text-gray-500 dark:text-gray-400 mb-3 uppercase tracking-wide">
            Recurrence — how often does it reappear within N draws?
          </h3>
          <div className="flex gap-2 flex-wrap">
            {s.recurrence.map(r => (
              <div key={r.window} className="bg-gray-50 dark:bg-gray-800 rounded-xl px-4 py-3 text-center min-w-[70px]">
                <div className="text-lg font-bold" style={{ color: r.pct > 6/43 ? ballColor(s.n) : "#94a3b8" }}>
                  {(r.pct * 100).toFixed(1)}%
                </div>
                <div className="text-xs text-gray-400 mt-0.5">within {r.window}</div>
                <div className="text-[10px] text-gray-500">{r.count}/{r.total}</div>
              </div>
            ))}
          </div>
          <p className="text-xs text-gray-400 mt-2">
            Expected random baseline: {((1 - Math.pow(37/43, 6)) * 100).toFixed(1)}% per draw &nbsp;·&nbsp; coloured = above baseline
          </p>
        </div>

        {/* Co-appearance with previous draw */}
        <div>
          <h3 className="text-sm font-semibold text-gray-500 dark:text-gray-400 mb-3 uppercase tracking-wide">
            Previous draw carry-over — when #{s.n} appears, how many numbers from the prior draw also appear?
          </h3>
          <div className="flex gap-1 items-end h-20">
            {s.prevOverlap.dist.map((count, k) => {
              const maxD = Math.max(...s.prevOverlap.dist, 1);
              const pct = count / maxD;
              return (
                <div key={k} className="flex-1 flex flex-col items-center gap-1">
                  <span className="text-xs text-gray-400">{count}</span>
                  <div
                    className="w-full rounded-t-sm"
                    style={{ height: `${Math.max(3, pct * 60)}px`, background: k === 0 ? "#475569" : ballColor(s.n), opacity: 0.5 + pct * 0.5 }}
                  />
                  <span className="text-xs text-gray-400">{k}</span>
                </div>
              );
            })}
          </div>
          <div className="flex gap-4 mt-2 text-xs text-gray-400 flex-wrap">
            <span>Avg carry-over: <strong className="text-gray-200">{s.prevOverlap.avgOverlap.toFixed(2)}</strong> numbers</span>
            <span>At least 1: <strong className="text-gray-200">{(s.prevOverlap.atLeastOne * 100).toFixed(1)}%</strong></span>
            <span className="text-gray-500">· random baseline avg ≈ 0.84</span>
          </div>
        </div>

        {/* Gap history */}
        {s.gaps.length > 0 && (
          <div>
            <h3 className="text-sm font-semibold text-gray-500 dark:text-gray-400 mb-3 uppercase tracking-wide">
              Draws between appearances (newest → oldest)
            </h3>
            <div className="flex gap-0.5 items-end h-20 overflow-x-auto pb-1">
              {[...s.gaps].reverse().map((gap, gi) => {
                const revIdx = s.gaps.length - 1 - gi;
                const maxG = Math.max(...s.gaps, 1);
                const pct = gap / maxG;
                const isLong = gap > s.avgGap * 1.5;
                const isShort = gap <= 3;
                const barColor = isLong ? "#ef4444" : isShort ? "#22c55e" : ballColor(s.n);
                return (
                  <div
                    key={gi}
                    className="flex-shrink-0 flex flex-col items-center gap-0.5"
                    style={{ width: `${Math.max(6, Math.min(16, 600 / s.gaps.length))}px` }}
                    title={`After draw #${s.gapSerials[revIdx]}: ${gap} draws until next appearance`}
                  >
                    <div
                      className="w-full rounded-t-sm"
                      style={{ height: `${Math.max(3, pct * 60)}px`, background: barColor, opacity: 0.8 }}
                    />
                  </div>
                );
              })}
            </div>
            <div className="flex gap-4 mt-2 text-xs text-gray-400 flex-wrap">
              <span>Min gap: <strong className="text-green-500">{s.minGap}</strong></span>
              <span>Avg gap: <strong className="text-gray-300">{s.avgGap.toFixed(1)}</strong></span>
              <span>Max gap: <strong className="text-red-400">{s.maxGap}</strong></span>
              <span>Current streak: <strong className={s.coldStreak > s.avgGap * 1.5 ? "text-red-400" : "text-gray-300"}>{s.coldStreak}</strong></span>
              <span className="ml-auto">🟢 ≤3 draws &nbsp; 🔴 &gt;1.5× avg</span>
            </div>
          </div>
        )}

        {/* Era trend */}
        <div>
          <h3 className="text-sm font-semibold text-gray-500 dark:text-gray-400 mb-3 uppercase tracking-wide">
            Hits per {s.bucketSize}-draw era (oldest → newest)
          </h3>
          <div className="flex gap-1 items-end h-16">
            {s.buckets.map((count, bi) => {
              const pct = maxBucket > 0 ? count / maxBucket : 0;
              const aboveAvg = count > expectedPerBucket;
              return (
                <div key={bi} className="flex-1 flex flex-col items-center gap-0.5" title={`Era ${bi + 1}: ${count} hits`}>
                  <div
                    className="w-full rounded-t-sm transition-all"
                    style={{
                      height: `${Math.max(3, pct * 52)}px`,
                      background: aboveAvg ? ballColor(s.n) : "#94a3b8",
                      opacity: 0.6 + pct * 0.4,
                    }}
                  />
                  <span className="text-[9px] text-gray-400">{bi + 1}</span>
                </div>
              );
            })}
          </div>
          <p className="text-xs text-gray-400 mt-1">
            Coloured bars = above average · grey = below average · avg {expectedPerBucket.toFixed(1)} per era
          </p>
        </div>

        {/* Draw history list */}
        <div>
          <h3 className="text-sm font-semibold text-gray-500 dark:text-gray-400 mb-3 uppercase tracking-wide">
            Draw history ({s.history.length} appearances)
          </h3>
          <div className="overflow-y-auto max-h-[600px] rounded-xl border border-gray-100 dark:border-gray-800">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-gray-50 dark:bg-gray-800">
                <tr className="text-left text-xs text-gray-400">
                  <th className="px-3 py-2 font-medium">Draw</th>
                  <th className="px-3 py-2 font-medium">Date</th>
                  <th className="px-3 py-2 font-medium">Numbers drawn</th>
                  <th className="px-3 py-2 font-medium">Bonus</th>
                </tr>
              </thead>
              <tbody>
                {s.history.map((entry: DrawEntry, i: number) => (
                  <tr
                    key={entry.serial}
                    className={`border-t border-gray-50 dark:border-gray-800 ${
                      i % 2 === 0 ? "bg-white dark:bg-gray-900" : "bg-gray-50/50 dark:bg-gray-800/30"
                    }`}
                  >
                    <td className="px-3 py-2 font-mono text-gray-500 dark:text-gray-400">
                      #{entry.serial}
                    </td>
                    <td className="px-3 py-2 text-gray-400 whitespace-nowrap">
                      {entry.date ?? "—"}
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex gap-1 flex-wrap">
                        {entry.nums.map((n2) => (
                          <span
                            key={n2}
                            className={`inline-flex items-center justify-center w-7 h-7 rounded-full text-xs font-bold text-white`}
                            style={{
                              background: n2 === s.n ? ballColor(n2) : "#64748b",
                              opacity: n2 === s.n ? 1 : 0.5,
                              transform: n2 === s.n ? "scale(1.15)" : "scale(1)",
                            }}
                          >
                            {n2}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="px-3 py-2">
                      <span
                        className={`inline-flex items-center justify-center w-7 h-7 rounded-full text-xs font-bold text-white`}
                        style={{
                          background: entry.bonus === s.n ? "#f59e0b" : "#374151",
                          opacity: entry.bonus === s.n ? 1 : 0.4,
                        }}
                      >
                        {entry.bonus}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
