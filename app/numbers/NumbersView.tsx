"use client";
import { useState } from "react";
import type { NumberStat } from "./page";

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
      </div>
    </div>
  );
}
