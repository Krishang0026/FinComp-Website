import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  serverExternalPackages: ["firebase-admin"],
  // The CSV is intentionally outside /public. Explicit tracing ensures Vercel
  // includes it with every server function that prices or reveals candles.
  outputFileTracingIncludes: { "/*": ["./data/market_data.csv"] },
};
export default nextConfig;
