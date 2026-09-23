import { cookies } from "next/headers";
import { randomUUID } from "node:crypto";

export async function sessionId() { return (await cookies()).get("market_arena_uid")?.value; }
export async function newSession() { const uid = randomUUID(); (await cookies()).set("market_arena_uid", uid, { httpOnly: true, sameSite: "lax", secure: process.env.NODE_ENV === "production", maxAge: 60 * 60 * 8, path: "/" }); return uid; }
