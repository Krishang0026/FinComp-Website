import { NextResponse } from "next/server";
import { getGame, playerFor, portfolioFor, publish, trade } from "@/lib/game";
import { sessionId } from "@/lib/session";
import { firestore } from "@/lib/firebase";
export const runtime = "nodejs";
export async function POST(request: Request) {
  try { const uid = await sessionId(); if (!uid) return NextResponse.json({ error: "Join the game first." }, { status: 401 }); const { symbol, side, quantity } = await request.json(); const game = await getGame(); const snap = await firestore().collection("players").doc(uid).get(); if (!snap.exists) throw new Error("Join the game first."); const player = await playerFor(uid, snap.data()?.username); const result = await trade(uid, game, symbol, side, Number(quantity)); await publish(uid, player.username, game, result.portfolio); return NextResponse.json({ message: `${String(side).toUpperCase()} ${quantity} ${symbol} at ₹${result.price.toLocaleString("en-IN")}` }); }
  catch (error) { return NextResponse.json({ error: error instanceof Error ? error.message : "Order rejected." }, { status: 400 }); }
}
