import { Draw } from "@/lib/db";

const BALL_COLORS: Record<number, string> = {
  1: "bg-[#e74c3c]",   // 1-10: red
  2: "bg-[#e74c3c]",
  3: "bg-[#e74c3c]",
  4: "bg-[#e74c3c]",
  5: "bg-[#e74c3c]",
  6: "bg-[#e74c3c]",
  7: "bg-[#e74c3c]",
  8: "bg-[#e74c3c]",
  9: "bg-[#e74c3c]",
  10: "bg-[#e74c3c]",
};

function getBallColor(n: number): string {
  if (n <= 10) return "bg-[#e74c3c]";   // red
  if (n <= 19) return "bg-[#e67e22]";   // orange
  if (n <= 29) return "bg-[#2ecc71]";   // green
  if (n <= 38) return "bg-[#3498db]";   // blue
  return "bg-[#9b59b6]";                 // purple
}

interface BallRowProps {
  draw: Draw;
  showBonus?: boolean;
  size?: "sm" | "md" | "lg";
}

export function BallRow({ draw, showBonus = true, size = "md" }: BallRowProps) {
  const nums = [draw.num1, draw.num2, draw.num3, draw.num4, draw.num5, draw.num6];
  const dim =
    size === "sm" ? "w-8 h-8 text-xs" :
    size === "lg" ? "w-12 h-12 text-lg" :
    "w-10 h-10 text-sm";

  return (
    <div className="flex items-center gap-1.5">
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
            {draw.bonus}
          </div>
        </>
      )}
    </div>
  );
}
