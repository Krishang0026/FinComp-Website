import fs from "node:fs";
import path from "node:path";
import type { Candle } from "./types";

type Markets = Record<string, Candle[]>;
let cached: Markets | undefined;

function parseCsv(text: string): Markets {
  const lines = text.trim().split(/\r?\n/); const rows: Markets = {};
  for (const line of lines.slice(1)) {
    const [symbol, date, open, high, low, close, volume] = line.split(",");
    if (symbol && date) (rows[symbol] ??= []).push({ date, open: +open, high: +high, low: +low, close: +close, volume: +volume });
  }
  for (const candles of Object.values(rows)) candles.sort((a, b) => a.date.localeCompare(b.date));
  return rows;
}
export function markets(): Markets { if (!cached) cached = parseCsv(fs.readFileSync(path.join(process.cwd(), "data", "market_data.csv"), "utf8")); return cached; }
export function symbols() { return Object.keys(markets()).sort(); }
export function closeAt(symbol: string, index: number) { const value = markets()[symbol]?.[index]; if (!value) throw new Error("Unknown symbol or unavailable price."); return value.close; }
