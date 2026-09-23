import { NextResponse } from "next/server";
import { firestore } from "@/lib/firebase";
import { markets } from "@/lib/market";
export const runtime = "nodejs";
export async function POST(request: Request) {
  try {
    if (!process.env.ADMIN_KEY || request.headers.get("x-admin-key") !== process.env.ADMIN_KEY) return NextResponse.json({ error: "Invalid admin key." }, { status: 401 });
    const { gameId, tickSeconds = 10 } = await request.json();
    const cleanId = String(gameId ?? "").trim() || `game-${new Date().toISOString().slice(0, 10)}`;
    const maxIndex = Math.min(...Object.values(markets()).map((candles) => candles.length)) - 1;
    await firestore().collection("games").doc("current").set({ gameId: cleanId, status: "running", startAt: Date.now(), tickSeconds: Math.max(1, Number(tickSeconds)), maxIndex, pausedSeconds: 0 });
    return NextResponse.json({ ok: true, gameId: cleanId });
  } catch (error) { return NextResponse.json({ error: error instanceof Error ? error.message : "Unable to start." }, { status: 400 }); }
}
