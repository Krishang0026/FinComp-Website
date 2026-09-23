# MarketArena

Vercel-ready, multi-user trading competition. Students join a closed-room game with a username only, receive exactly **₹100,000 cash and zero holdings**, and can trade long or short at each revealed candle's close.

## Architecture

- **Next.js + Vercel** is the web and API runtime. `npm run dev` starts it locally; `npm run build` is the production check Vercel runs.
- **Firebase Firestore (Admin SDK)** is the shared source of truth for games, players, portfolios, and the leaderboard.
- **Server-only CSV market data** is read by API routes. The browser only receives candles through the global revealed index; future rows never enter the API response.
- Every order uses a **Firestore transaction**, so concurrent orders cannot overwrite balances or positions.
- Selling more than an owned position opens a short. An optional `MAX_GROSS_EXPOSURE` guardrail caps long-plus-short market exposure.

## Local development

```powershell
npm install
Copy-Item .env.example .env.local
# Fill in FIREBASE_SERVICE_ACCOUNT_JSON and ADMIN_KEY in .env.local
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). The initial screen asks only for a unique game username. The browser receives a secure, HTTP-only room-session cookie; there are no passwords.

## Prepare the data

The application reads `data/market_data.csv` on the server. It must use this exact header:

```csv
Symbol,Date,Open,High,Low,Close,Volume
HDFCBANK,2025-10-07,842.84,851.38,834.54,843.08,70859506
```

- Use one chronological series per `Symbol`.
- All symbols must have enough rows for the desired game.
- Replace the currently committed preview CSV with your final competition CSV before deploying.
- Keep it in `data/`, **not** `public/`, so it cannot be downloaded by players.

## Firebase setup

1. Create a Firebase project and a Firestore database in Production mode.
2. In Firebase Console → Project settings → Service accounts, generate a new private key.
3. Minify its JSON into one line and set it as `FIREBASE_SERVICE_ACCOUNT_JSON`.
4. Deploy the supplied rules and index:

   ```powershell
   firebase deploy --only firestore:rules,firestore:indexes
   ```

The rules deny direct browser access. Only Vercel API routes use the Firebase Admin SDK, so players cannot read raw portfolio/game documents or unrevealed market data.

## Start a competition

Set `ADMIN_KEY`, then call the start API from PowerShell:

```powershell
$key = "your-admin-key"
Invoke-RestMethod -Method Post -Uri "http://localhost:3000/api/admin/start" `
  -Headers @{ "x-admin-key" = $key; "Content-Type" = "application/json" } `
  -Body '{"gameId":"fincomp-2026","tickSeconds":10}'
```

Starting a new `gameId` gives every participating username a fresh portfolio of ₹100,000 cash and no holdings. The global candle index is calculated from the server timestamp. At 10 seconds per row, a 252-row dataset runs for 42 minutes.

## Deploy to Vercel

1. Commit and push this repository to GitHub, including `data/market_data.csv`.
2. In Vercel, choose **Add New → Project → Import** and select the repository. Vercel detects Next.js automatically.
3. Add these Environment Variables for **Production**, **Preview**, and **Development**:

   - `FIREBASE_SERVICE_ACCOUNT_JSON`
   - `ADMIN_KEY`
   - `MAX_GROSS_EXPOSURE` (optional; defaults to `300000`)
4. Click **Deploy**.
5. Run the start request above using your deployed domain (replace `localhost:3000`).

Do not place the Firebase service-account JSON in the Git repository, client-side code, or `NEXT_PUBLIC_*` variables.

## Firestore shape

```
games/current                         global synchronized clock
players/{room-session-uuid}           unique username registry
portfolios/{gameId}_{session-uuid}    cash + signed positions
leaderboard/{gameId}_{session-uuid}   current marked-to-market total
```

## Short-selling behavior

- `BUY` increases signed quantity; `SELL` decreases it.
- A quantity below zero is a short position.
- Covering a short retains its entry price until it crosses through zero; crossing reverses the position at the current market price.
- Cash credits when opening a short and debits when covering one.
- The gross-exposure cap limits `sum(abs(quantity × last price))`, regardless of direction.
