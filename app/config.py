from __future__ import annotations

from pathlib import Path
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
ASSETS = (
    "HDFCBANK",
    "ICICIBANK",
    "SBIN",
    "PAYTM",
    "BAJFINANCE",
    "TCS",
    "INFY",
    "WIPRO",
    "M&M",
    "MARUTI",
    "RELIANCE",
    "NTPC",
    "TATAPOWER",
    "HAL",
    "BEL",
    "IRCTC",
    "RVNL",
    "LT",
    "TATASTEEL",
    "JSWSTEEL",
    "HUL",
    "ITC",
    "TRENT",
    "SUNPHARMA",
    "CIPLA",
)
GAME_DOC = "current"
STARTING_CASH = 100_000.0
TICK_SECONDS = 10


def admin_ids() -> set[str]:
    try:
        raw = st.secrets.get("app", {}).get("admin_student_ids", "")
    except st.errors.StreamlitSecretNotFoundError:
        raw = ""
    return {item.strip().upper() for item in raw.split(",") if item.strip()}


def is_admin(student_id: str) -> bool:
    return student_id.upper() in admin_ids()


def firebase_is_configured() -> bool:
    """A missing secrets file intentionally activates the no-setup local demo."""
    try:
        return bool(st.secrets.get("firebase_service_account", {}) and st.secrets.get("firebase_web", {}).get("api_key"))
    except st.errors.StreamlitSecretNotFoundError:
        return False
