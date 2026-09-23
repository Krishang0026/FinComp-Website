import type { Metadata } from "next";
import "./styles.css";
export const metadata: Metadata = { title: "MarketArena", description: "Live trading competition" };
export default function Layout({ children }: Readonly<{ children: React.ReactNode }>) { return <html lang="en"><body>{children}</body></html>; }
