import { cert, getApps, initializeApp } from "firebase-admin/app";
import { getFirestore } from "firebase-admin/firestore";

export function isFirebaseConfigured(): boolean {
  const raw = process.env.FIREBASE_SERVICE_ACCOUNT_JSON;
  if (!raw) return false;
  try {
    const parsed = JSON.parse(raw);
    return Boolean(parsed && parsed.project_id && parsed.private_key && !parsed.private_key.includes("..."));
  } catch {
    return false;
  }
}

export function firestore() {
  if (!getApps().length) {
    const raw = process.env.FIREBASE_SERVICE_ACCOUNT_JSON;
    if (!raw) throw new Error("Missing FIREBASE_SERVICE_ACCOUNT_JSON. Add it in Vercel Project Settings → Environment Variables.");
    const account = JSON.parse(raw);
    if (account.private_key && typeof account.private_key === "string") {
      account.private_key = account.private_key.replace(/\\n/g, "\n");
    }
    initializeApp({ credential: cert(account) });
  }
  return getFirestore();
}
