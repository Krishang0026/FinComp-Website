export type Candle = { date: string; open: number; high: number; low: number; close: number; volume: number };
export type Position = { quantity: number; avgEntry: number };
export type Portfolio = { cash: number; positions: Record<string, Position> };
export type Game = { gameId: string; status: "waiting" | "running" | "paused" | "finished"; startAt?: number; tickSeconds: number; maxIndex: number; pausedAt?: number; pausedSeconds: number };
export const STARTING_CASH = 100_000;
