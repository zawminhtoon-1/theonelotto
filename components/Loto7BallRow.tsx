import { Loto7Draw } from "@/lib/db7";

function getBallColor(n: number): string {
  if (n <= 8) return "bg-[#e74c3c]";    // red
  if (n <= 15) return "bg-[#e67e22]";   // orange
  if (n <= 22) return "bg-[#2ecc71]";   // green
  if (n <= 29) return "bg-[#3498db]";   // blue
  return "bg-[#9b59b6]";                 // purple
}

interface Loto7BallRowProps {
  draw: Loto7Draw;
  showBonus?: boolean;
  size?: "sm" | "md" | "lg";
}

export function Loto7BallRow({ draw, showBonus = true, size = "md" }: Loto7BallRowProps) {
  const nums = [draw.num1, draw.num2, draw.num3, draw.num4, draw.num5, draw.num6, draw.num7];
  const dim =
    size === "sm" ? "w-8 h-8 text-xs" :
    size === "lg" ? "w-12 h-12 text-lg" :
    "w-10 h-10 text-sm";

  return (
    <div className="flex items-center gap-1.5 flex-wrap">
      {nums.map((n, i) => (
        <div
          key={i}
          className={`${dim} ${getBallColor(n)} rounded-full flex items-center justify-center font-bold text-white shadow-sm`}
        >
          {n}
        </div>
      ))}
      {showBonus && (
        <>
          <span className="text-gray-300 mx-1 text-sm">+</span>
          <div
            className={`${dim} bg-gray-400 rounded-full flex items-center justify-center font-bold text-white shadow-sm ring-2 ring-gray-300`}
          >
            {draw.bonus1}
          </div>
          <div
            className={`${dim} bg-gray-400 rounded-full flex items-center justify-center font-bold text-white shadow-sm ring-2 ring-gray-300`}
          >
            {draw.bonus2}
          </div>
        </>
      )}
    </div>
  );
}
