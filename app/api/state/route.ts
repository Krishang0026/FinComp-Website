import { NextResponse } from "next/server";
import { isFirebaseConfigured } from "@/lib/firebase";
import { currentIndex, getGame, leaderboard, playerFor, portfolioFor, publish } from "@/lib/game";
import { markets, symbols } from "@/lib/market";
import { sessionId } from "@/lib/session";

export const runtime = "nodejs";

export async function GET(request: Request) {
  try {
    const uid = await sessionId();
    if (!uid) return NextResponse.json({ joined: false });

    const game = await getGame();

    if (isFirebaseConfigured()) {
      try {
        const existing = await (await import("@/lib/firebase")).firestore().collection("players").doc(uid).get();
        if (!existing.exists) return NextResponse.json({ joined: false });
      } catch {
        // Fallback
      }
    }

    const player = await playerFor(uid, "");
    if (!player || !player.username) return NextResponse.json({ joined: false });

    const portfolio = await portfolioFor(game, uid);
    const index = currentIndex(game);
    const totalValue = await publish(uid, player.username, game, portfolio);

    const symbol = new URL(request.url).searchParams.get("symbol") ?? symbols()[0];
    const candles = markets()[symbol]?.slice(0, index + 1) ?? [];
    const prices = Object.fromEntries(
      Object.entries(portfolio.positions).map(([ticker]) => [ticker, markets()[ticker]?.[index]?.close ?? 0])
    );

    return NextResponse.json({
      joined: true,
      username: player.username,
      game: { ...game, index },
      symbols: symbols(),
      symbol,
      candles,
      prices,
      portfolio,
      totalValue,
      leaderboard: await leaderboard(game.gameId),
    });
  } catch (error) {
    return NextResponse.json({ error: error instanceof Error ? error.message : "Unable to load game." }, { status: 500 });
  }
}
