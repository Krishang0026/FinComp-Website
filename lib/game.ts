import { FieldValue } from "firebase-admin/firestore";
import { firestore, isFirebaseConfigured } from "./firebase";
import { closeAt, markets, symbols } from "./market";
import { STARTING_CASH, type Game, type Portfolio } from "./types";

const GAME = "current";

// Local In-Memory Fallback Store
const localStore = {
  game: {
    gameId: "practice",
    status: "running" as const,
    startAt: Date.now() - 48 * 10 * 1000,
    tickSeconds: 10,
    maxIndex: 251,
    pausedSeconds: 0,
  } as Game,
  players: new Map<string, { username: string; usernameKey: string }>(),
  portfolios: new Map<string, Portfolio>(),
  leaderboard: new Map<string, { username: string; totalValue: number }>(),
};

const defaultGame = (): Game => ({
  gameId: "practice",
  status: "running",
  startAt: Date.now() - 48 * 10 * 1000,
  tickSeconds: 10,
  maxIndex: Math.min(...Object.values(markets()).map((x) => x.length)) - 1,
  pausedSeconds: 0,
});

export function currentIndex(game: Game) {
  if (game.status === "finished") return game.maxIndex;
  if (game.status !== "running" || !game.startAt) return 0;
  return Math.min(game.maxIndex, Math.max(0, Math.floor((Date.now() - game.startAt - game.pausedSeconds * 1000) / (game.tickSeconds * 1000))));
}

export async function getGame(): Promise<Game> {
  if (!isFirebaseConfigured()) {
    const maxIdx = Math.min(...Object.values(markets()).map((x) => x.length)) - 1;
    localStore.game.maxIndex = maxIdx;
    return localStore.game;
  }
  try {
    const doc = await firestore().collection("games").doc(GAME).get();
    return doc.exists ? (doc.data() as Game) : defaultGame();
  } catch {
    return localStore.game;
  }
}

export async function playerFor(uid: string, username: string): Promise<{ username: string; usernameKey: string }> {
  if (!isFirebaseConfigured()) {
    const existing = localStore.players.get(uid);
    if (existing) return existing;
    const nameToUse = username && username.trim() ? username.trim() : `Trader_${uid.slice(0, 4)}`;
    const usernameKey = nameToUse.toLowerCase();
    for (const p of localStore.players.values()) {
      if (p.usernameKey === usernameKey) throw new Error("That game username is already taken.");
    }
    const player = { username: nameToUse, usernameKey };
    localStore.players.set(uid, player);
    return player;
  }

  const db = firestore(), ref = db.collection("players").doc(uid), existing = await ref.get();
  if (existing.exists) return existing.data() as { username: string; usernameKey: string };
  const nameToUse = username && username.trim() ? username.trim() : `Trader_${uid.slice(0, 4)}`;
  const usernameKey = nameToUse.toLowerCase();
  const duplicate = await db.collection("players").where("usernameKey", "==", usernameKey).limit(1).get();
  if (!duplicate.empty) throw new Error("That game username is already taken.");
  const player = { username: nameToUse, usernameKey, createdAt: FieldValue.serverTimestamp() };
  await ref.create(player);
  return { username: player.username, usernameKey: player.usernameKey };
}

export function portfolioValue(portfolio: Portfolio, index: number) {
  return Math.round((portfolio.cash + Object.entries(portfolio.positions).reduce((sum, [symbol, position]) => sum + position.quantity * closeAt(symbol, index), 0)) * 100) / 100;
}

export async function portfolioFor(game: Game, uid: string): Promise<Portfolio> {
  if (!isFirebaseConfigured()) {
    const key = `${game.gameId}_${uid}`;
    let p = localStore.portfolios.get(key);
    if (!p) {
      p = { cash: STARTING_CASH, positions: { HDFCBANK: { quantity: 30, avgEntry: 820.0 }, RELIANCE: { quantity: 15, avgEntry: 1250.0 } } };
      localStore.portfolios.set(key, p);
    }
    return p;
  }

  try {
    const ref = firestore().collection("portfolios").doc(`${game.gameId}_${uid}`), snap = await ref.get();
    if (snap.exists) return snap.data() as Portfolio;
    const initial: Portfolio = { cash: STARTING_CASH, positions: {} };
    try { await ref.create({ ...initial, gameId: game.gameId, uid, createdAt: FieldValue.serverTimestamp() }); } catch { /* second tab won */ }
    return (await ref.get()).data() as Portfolio;
  } catch {
    const key = `${game.gameId}_${uid}`;
    let p = localStore.portfolios.get(key);
    if (!p) {
      p = { cash: STARTING_CASH, positions: {} };
      localStore.portfolios.set(key, p);
    }
    return p;
  }
}

export async function publish(uid: string, username: string, game: Game, portfolio: Portfolio) {
  const index = currentIndex(game), totalValue = portfolioValue(portfolio, index);
  if (!isFirebaseConfigured()) {
    localStore.leaderboard.set(`${game.gameId}_${uid}`, { username, totalValue });
    return totalValue;
  }
  try {
    await firestore().collection("leaderboard").doc(`${game.gameId}_${uid}`).set({ gameId: game.gameId, uid, username, totalValue, priceIndex: index, updatedAt: FieldValue.serverTimestamp() }, { merge: true });
  } catch {
    localStore.leaderboard.set(`${game.gameId}_${uid}`, { username, totalValue });
  }
  return totalValue;
}

export async function leaderboard(gameId: string) {
  if (!isFirebaseConfigured()) {
    const mockNames = ["Aarav", "Anaya", "Kabir", "Diya", "Vihaan", "Isha", "Arjun", "Meera", "Rohan", "Zara"];
    const mockValues = [113840, 111590, 109445, 107201, 105975, 104860, 103530, 102920, 101875, 100460];
    const items: { username: string; totalValue: number }[] = mockNames.map((name, i) => ({ username: name, totalValue: mockValues[i] }));
    for (const entry of localStore.leaderboard.values()) {
      const idx = items.findIndex((x) => x.username === entry.username);
      if (idx >= 0) items[idx] = entry;
      else items.push(entry);
    }
    items.sort((a, b) => b.totalValue - a.totalValue);
    return items.slice(0, 20);
  }

  try {
    const result = await firestore().collection("leaderboard").where("gameId", "==", gameId).orderBy("totalValue", "desc").limit(20).get();
    return result.docs.map((x) => x.data() as { username: string; totalValue: number });
  } catch {
    return Array.from(localStore.leaderboard.values()).sort((a, b) => b.totalValue - a.totalValue).slice(0, 20);
  }
}

export async function trade(uid: string, game: Game, symbol: string, side: "buy" | "sell", quantity: number) {
  if (!symbols().includes(symbol) || !Number.isInteger(quantity) || quantity < 1) throw new Error("Choose a valid symbol and whole-number quantity.");
  if (game.status !== "running") throw new Error("The market is not open.");

  if (!isFirebaseConfigured()) {
    const index = currentIndex(game), price = closeAt(symbol, index);
    const portfolio = await portfolioFor(game, uid);
    const prior = portfolio.positions[symbol] ?? { quantity: 0, avgEntry: 0 };
    const delta = side === "buy" ? quantity : -quantity;
    const nextQty = prior.quantity + delta;

    portfolio.cash = Math.round((portfolio.cash - delta * price) * 100) / 100;
    if (prior.quantity === 0 || Math.sign(prior.quantity) === Math.sign(delta)) {
      portfolio.positions[symbol] = { quantity: nextQty, avgEntry: Math.abs(nextQty) ? ((Math.abs(prior.quantity) * prior.avgEntry + Math.abs(delta) * price) / Math.abs(nextQty)) : 0 };
    } else if (nextQty === 0) {
      delete portfolio.positions[symbol];
    } else if (Math.sign(nextQty) !== Math.sign(prior.quantity)) {
      portfolio.positions[symbol] = { quantity: nextQty, avgEntry: price };
    } else {
      portfolio.positions[symbol] = { quantity: nextQty, avgEntry: prior.avgEntry };
    }

    const gross = Object.entries(portfolio.positions).reduce((total, [ticker, pos]) => total + Math.abs(pos.quantity * closeAt(ticker, index)), 0);
    const cap = Number(process.env.MAX_GROSS_EXPOSURE ?? 300000);
    if (gross > cap) throw new Error(`Maximum gross exposure is ₹${cap.toLocaleString("en-IN")}.`);

    localStore.portfolios.set(`${game.gameId}_${uid}`, portfolio);
    return { price, portfolio };
  }

  const db = firestore(), gameRef = db.collection("games").doc(GAME), ref = db.collection("portfolios").doc(`${game.gameId}_${uid}`);
  return db.runTransaction(async (tx) => {
    const latest = (await tx.get(gameRef)).data() as Game | undefined;
    if (!latest || latest.status !== "running" || latest.gameId !== game.gameId) throw new Error("Game state changed. Try again.");
    const index = currentIndex(latest), price = closeAt(symbol, index), data = (await tx.get(ref)).data() as Portfolio | undefined;
    const portfolio: Portfolio = data ?? { cash: STARTING_CASH, positions: {} }, prior = portfolio.positions[symbol] ?? { quantity: 0, avgEntry: 0 }, delta = side === "buy" ? quantity : -quantity, nextQty = prior.quantity + delta;
    portfolio.cash = Math.round((portfolio.cash - delta * price) * 100) / 100;
    if (prior.quantity === 0 || Math.sign(prior.quantity) === Math.sign(delta)) portfolio.positions[symbol] = { quantity: nextQty, avgEntry: Math.abs(nextQty) ? ((Math.abs(prior.quantity) * prior.avgEntry + Math.abs(delta) * price) / Math.abs(nextQty)) : 0 };
    else if (nextQty === 0) delete portfolio.positions[symbol];
    else if (Math.sign(nextQty) !== Math.sign(prior.quantity)) portfolio.positions[symbol] = { quantity: nextQty, avgEntry: price };
    else portfolio.positions[symbol] = { quantity: nextQty, avgEntry: prior.avgEntry };
    const gross = Object.entries(portfolio.positions).reduce((total, [ticker, pos]) => total + Math.abs(pos.quantity * closeAt(ticker, index)), 0), cap = Number(process.env.MAX_GROSS_EXPOSURE ?? 300000);
    if (gross > cap) throw new Error(`Maximum gross exposure is ₹${cap.toLocaleString("en-IN")}.`);
    tx.set(ref, { ...portfolio, gameId: latest.gameId, uid, updatedAt: FieldValue.serverTimestamp(), lastTrade: { symbol, side, quantity, price, index } });
    return { price, portfolio };
  });
}
