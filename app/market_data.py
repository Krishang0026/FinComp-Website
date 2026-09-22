from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd
import streamlit as st

from config import ASSETS, DATA_DIR


@st.cache_data(show_spinner=False)
def load_market_data() -> dict[str, pd.DataFrame]:
    """
    Load all local CSV market files.

    Each asset must contain:
        Date, Open, High, Low, Close, Volume

    The number of rows is allowed to vary.
    The competition clock determines how many rows
    have been revealed to students.
    """

    result: dict[str, pd.DataFrame] = {}

    needed = {
        "Date",
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
    }

    combined_path = DATA_DIR / "market_data.csv"

    combined = (
        pd.read_csv(
            combined_path,
            parse_dates=["Date"],
        )
        if combined_path.exists()
        else None
    )

    if combined is not None:

        expected = needed | {"Symbol"}

        if set(combined.columns) != expected:

            raise ValueError(
                "market_data.csv must contain exactly: "
                "Symbol, Date, Open, High, Low, Close, Volume"
            )

    for asset in ASSETS:

        path = DATA_DIR / f"{asset}.csv"

        if combined is not None:

            frame = (
                combined.loc[
                    combined["Symbol"] == asset,
                    list(needed),
                ]
                .sort_values("Date")
                .reset_index(drop=True)
            )

        elif path.exists():

            frame = pd.read_csv(
                path,
                parse_dates=["Date"],
            )

        else:

            raise FileNotFoundError(
                f"Missing market file: {path}"
            )

        if set(frame.columns) != needed:

            raise ValueError(
                f"{asset} data must contain exactly "
                f"{sorted(needed)}"
            )

        if frame.empty:

            raise ValueError(
                f"{asset} data contains no rows"
            )

        if not frame["Date"].is_monotonic_increasing:

            raise ValueError(
                f"{asset} dates must be chronological"
            )

        if frame["Date"].duplicated().any():

            raise ValueError(
                f"{asset} contains duplicate dates"
            )

        numeric_columns = [
            "Open",
            "High",
            "Low",
            "Close",
            "Volume",
        ]

        if (
            frame[numeric_columns] < 0
        ).any().any():

            raise ValueError(
                f"{asset} data contains negative "
                "OHLCV values"
            )

        frame = frame.reset_index(
            drop=True
        )

        result[asset] = frame

    return result


def close_at(
    data: dict[str, pd.DataFrame],
    asset: str,
    index: int,
) -> float:

    return float(
        data[asset]
        .iloc[index]["Close"]
    )


def portfolio_value(
    portfolio: dict[str, Any],
    data: dict[str, pd.DataFrame],
    index: int,
) -> float:

    value = float(
        portfolio.get(
            "cash",
            0.0,
        )
    )

    for asset, position in (
        portfolio
        .get("positions", {})
        .items()
    ):

        value += (
            float(position["quantity"])
            * close_at(
                data,
                asset,
                index,
            )
        )

    return round(
        value,
        2,
    )


def public_candles(
    frame: pd.DataFrame,
    index: int,
) -> pd.DataFrame:

    """
    Return only candles that have been revealed
    by the competition clock.

    This is the security boundary for the chart.
    """

    if frame.empty:

        return frame.copy()

    safe_index = min(
        max(int(index), 0),
        len(frame) - 1,
    )

    return frame.iloc[
        : safe_index + 1
    ].copy()
