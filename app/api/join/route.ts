import { NextResponse } from "next/server";
import { newSession, sessionId } from "@/lib/session";
import { playerFor } from "@/lib/game";
export const runtime = "nodejs";
export async function POST(request: Request) {
  try {
    const { username } = await request.json(); const name = typeof username === "string" ? username.trim() : "";
    if (!/^[\p{L}\p{N} _-]{3,24}$/u.test(name)) return NextResponse.json({ error: "Use 3–24 letters, numbers, spaces, _ or -." }, { status: 400 });
    const uid = (await sessionId()) ?? await newSession(); const player = await playerFor(uid, name); return NextResponse.json({ username: player.username });
  } catch (error) { return NextResponse.json({ error: error instanceof Error ? error.message : "Unable to join the game." }, { status: 400 }); }
}
