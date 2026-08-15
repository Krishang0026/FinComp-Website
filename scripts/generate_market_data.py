"""Create one validated 252-row daily OHLCV CSV for every competition asset.

Run from the repository root:
    python scripts/generate_market_data.py

By default the script downloads yfinance history. `--synthetic` creates realistic,
deterministic mock data instead, which is ideal for development and demos.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ASSETS = ("AAPL", "TSLA", "NVDA", "BTC-USD", "ETH-USD")
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data"


def synthetic(asset: str) -> pd.DataFrame:
    seed = sum(ord(char) for char in asset)
    rng = np.random.default_rng(seed)
    end = pd.Timestamp.today().normalize()
    dates = pd.bdate_range(end=end, periods=252)
    base = {"AAPL": 180, "TSLA": 230, "NVDA": 125, "BTC-USD": 65_000, "ETH-USD": 3_200}[asset]
    close = base * np.exp(np.cumsum(rng.normal(0.0002, 0.022, len(dates))))
    open_ = np.r_[base, close[:-1]] * (1 + rng.normal(0, 0.006, len(dates)))
    spread = np.abs(rng.normal(0.012, 0.005, len(dates)))
    high = np.maximum(open_, close) * (1 + spread)
    low = np.minimum(open_, close) * (1 - spread)
    volume = rng.integers(1_000_000, 150_000_000, len(dates))
    return pd.DataFrame({"Date": dates, "Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume})


def download(asset: str) -> pd.DataFrame:
    import yfinance as yf
    raw = yf.download(asset, period="18mo", interval="1d", auto_adjust=False, progress=False)
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    raw = raw.reset_index().rename(columns={"Datetime": "Date"})
    frame = raw[["Date", "Open", "High", "Low", "Close", "Volume"]].dropna().tail(252).copy()
    if len(frame) != 252:
        raise RuntimeError(f"Only found {len(frame)} usable rows for {asset}")
    return frame


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--synthetic", action="store_true", help="Generate deterministic mock data instead of downloading")
    args = parser.parse_args()
    OUT.mkdir(exist_ok=True)
    combined = []
    for asset in ASSETS:
        frame = synthetic(asset) if args.synthetic else download(asset)
        frame["Date"] = pd.to_datetime(frame["Date"]).dt.strftime("%Y-%m-%d")
        frame.to_csv(OUT / f"{asset}.csv", index=False, float_format="%.6f")
        combined.append(frame.assign(Symbol=asset))
        print(f"Wrote {asset}.csv ({len(frame)} rows)")
    pd.concat(combined, ignore_index=True)[["Symbol", "Date", "Open", "High", "Low", "Close", "Volume"]].to_csv(
        OUT / "market_data.csv", index=False, float_format="%.6f"
    )
    print("Wrote market_data.csv (1,260 rows; 252 per asset)")


if __name__ == "__main__":
    main()
