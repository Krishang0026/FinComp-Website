"""Create one validated 252-row daily OHLCV CSV for every competition asset.

Run from the repository root:
    python scripts/generate_market_data.py

By default the script downloads yfinance history. `--synthetic` creates realistic,
deterministic mock data instead, which is ideal for development and demos.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
from config import ASSETS

OUT = ROOT / "data"


def synthetic(asset: str) -> pd.DataFrame:
    seed = sum(ord(char) * (i + 1) for i, char in enumerate(asset))
    rng = np.random.default_rng(seed)
    end = pd.Timestamp.today().normalize()
    dates = pd.bdate_range(end=end, periods=252)
    base_prices = {
        "HDFCBANK": 850, "ICICIBANK": 1000, "SBIN": 750, "PAYTM": 400, "BAJFINANCE": 6500,
        "TCS": 3800, "INFY": 1500, "WIPRO": 480, "M&M": 2800, "MARUTI": 11000,
        "RELIANCE": 1250, "NTPC": 350, "TATAPOWER": 400, "HAL": 4500, "BEL": 280,
        "IRCTC": 900, "RVNL": 400, "LT": 3600, "TATASTEEL": 150, "JSWSTEEL": 900,
        "HUL": 2400, "ITC": 480, "TRENT": 6000, "SUNPHARMA": 1600, "CIPLA": 1500,
    }
    base = base_prices.get(asset, 500.0)
    close = base * np.exp(np.cumsum(rng.normal(0.0002, 0.022, len(dates))))
    open_ = np.r_[base, close[:-1]] * (1 + rng.normal(0, 0.006, len(dates)))
    spread = np.abs(rng.normal(0.012, 0.005, len(dates)))
    high = np.maximum(open_, close) * (1 + spread)
    low = np.minimum(open_, close) * (1 - spread)
    volume = rng.integers(1_000_000, 150_000_000, len(dates))
    return pd.DataFrame({"Date": dates, "Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume})


def download(asset: str) -> pd.DataFrame:
    import yfinance as yf
    ticker = f"{asset}.NS" if not asset.endswith(".NS") and "-" not in asset else asset
    raw = yf.download(ticker, period="18mo", interval="1d", auto_adjust=False, progress=False)
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
    df_combined = pd.concat(combined, ignore_index=True)[["Symbol", "Date", "Open", "High", "Low", "Close", "Volume"]]
    df_combined.to_csv(OUT / "market_data.csv", index=False, float_format="%.6f")
    print(f"Wrote market_data.csv ({len(df_combined)} rows; 252 per asset)")


if __name__ == "__main__":
    main()

