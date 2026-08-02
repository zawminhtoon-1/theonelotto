import fs from "fs";
import path from "path";
import Loto7PredictionsView from "./Loto7PredictionsView";

export const revalidate = 300;

interface Combo {
  label: string;
  color: string;
  method: string;
  numbers: number[];
}

interface PredictionsData {
  nextSerial: number;
  drawCount: number;
  combos: Combo[];
}

export default async function Loto7PredictionsPage() {
  const filePath = path.join(process.cwd(), "public", "loto7_predictions_data.json");
  const raw = fs.readFileSync(filePath, "utf-8");
  const data = JSON.parse(raw) as PredictionsData;

  return (
    <Loto7PredictionsView
      combos={data.combos}
      nextSerial={data.nextSerial}
      drawCount={data.drawCount}
    />
  );
}
