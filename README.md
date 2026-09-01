# Trading Competition

Production-oriented Streamlit application for a synchronized, multi-user trading event. It reveals exactly one local OHLCV candle every 10 seconds and keeps all pricing, portfolio changes, and future data on the server.

## What is included

- Firebase Auth sign-up/sign-in using Student ID, nickname, and password.
- Refresh-resistant encrypted browser session: a refresh token is encrypted in a cookie and silently exchanged for a fresh Firebase ID token after reload.
- A Firestore-backed global game clock. Every worker derives the current candle index from the same UTC `start_at` timestamp—there is no per-browser timer to drift.
- Firestore transactional market orders, no short selling, no limit orders, and $100,000 starting cash.
- Plotly candlesticks that receive only the slice through the active candle.
- Tick-idempotent leaderboard publishing: each student writes at most one leaderboard document per candle index, even if Streamlit reruns multiple times.
- Public stage leaderboard at `/?view=leaderboard`, refreshing every 10 seconds.
- Professor-controlled market pause/resume. Pausing freezes the
  server-synchronized market clock, disables trading, and allows
  instructors to explain concepts before resuming.

## Local setup

1. Create a Firebase project. Enable **Authentication → Sign-in method → Email/Password**, then create a Firestore database in production mode.
2. Create a Firebase service account with Firestore access and download its JSON credentials. Do not commit it.
3. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`. Copy each service-account field into `[firebase_service_account]`, set the Firebase **Web API key** under `[firebase_web]`, choose a long random `cookie_password`, and list your professor IDs in `admin_student_ids`.
4. Create market data. For a no-network demo dataset:

   ```powershell
   python -m pip install -r requirements.txt
   python scripts/generate_market_data.py --synthetic
   ```

   Omit `--synthetic` to download the most recent 252 daily rows from Yahoo Finance. The generator produces `data/market_data.csv` (the consolidated source consumed by the app) and convenient per-asset CSVs. They are deliberately ignored by Git; use a locked, pre-event dataset in production.
5. Start the app:

   ```powershell
   # Local development via npm (recommended)
   npm run dev

   # Or run the underlying Python launcher directly:
   .\run.ps1
   ```

6. Sign up with a Student ID that is in `admin_student_ids`, open **Professor controls**, and click **START GAME**. Project `http://localhost:8501/?view=leaderboard` for the stage view.

## Firestore schema

```
games/current
  game_id
  status
  start_at
  tick_seconds
  max_index
  paused_at
  total_paused_seconds
  updated_at

users/{firebase_uid}
  student_id, nickname, created_at

portfolios/{game_id}_{firebase_uid}
  game_id, uid, cash, positions: { ASSET: { quantity, avg_entry } }, last_trade, updated_at

leaderboard/{game_id}_{firebase_uid}
  game_id, uid, student_id, nickname, total_value, price_index, updated_at
```

Deploy `firebase/firestore.rules` to block all browser Firestore access—the Streamlit server is the only data client and uses the Admin SDK. Deploy `firebase/firestore.indexes.json` before the event to support the ranked query:

```powershell
firebase deploy --only firestore:rules,firestore:indexes
```

## Operational notes

- The 252 candles take 42 minutes at 10 seconds each (not 40 minutes). For a strict 40-minute event, set `TICK_SECONDS = 9.5238` and adjust the integer-clock implementation, or use 240 rows at 10 seconds. This code honors the stated 10-second candle cadence.
- The server must be deployed with HTTPS and a correctly synchronized system clock. A single `start_at` timestamp is what synchronizes all Streamlit sessions.
- For production, run on a managed Streamlit platform with horizontal scaling as needed. The only scheduled client write is one small leaderboard upsert per student per tick: about 30 writes/sec at 300 participants. Trades use short Firestore transactions and do not write the leaderboard directly.
- Firestore Admin credentials must be held only in platform secrets. The files under `data/` must be mounted/readable only by the server; never serve them as static downloads.
- A 1-hour competition needs a Firebase Auth refresh token policy longer than one hour (the default Firebase refresh token behavior meets this); the app exchanges the saved refresh token on browser reload.
