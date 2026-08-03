import fs from "fs";
import path from "path";
import MiniLotoPredictionsView from "./MiniLotoPredictionsView";

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

export default async function MiniLotoPredictionsPage() {
  const filePath = path.join(process.cwd(), "public", "miniloto_predictions_data.json");
  const raw = fs.readFileSync(filePath, "utf-8");
  const data = JSON.parse(raw) as PredictionsData;

  return (
    <MiniLotoPredictionsView
      combos={data.combos}
      nextSerial={data.nextSerial}
      drawCount={data.drawCount}
    />
  );
}
