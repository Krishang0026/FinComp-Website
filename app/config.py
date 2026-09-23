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
    except Exception:
        raw = ""
    return {item.strip().upper() for item in raw.split(",") if item.strip()}


def is_admin(student_id: str) -> bool:
    return student_id.upper() in admin_ids()


def firebase_is_configured() -> bool:
    """A missing or placeholder secrets file intentionally activates the no-setup local demo."""
    try:
        sec = st.secrets
        account = dict(sec.get("firebase_service_account", {}))
        web = dict(sec.get("firebase_web", {}))
        if not account or not web:
            return False

        api_key = str(web.get("api_key", "")).strip()
        if not api_key or api_key in {"Firebase Web API key", "...", "your-api-key"}:
            return False

        project_id = str(account.get("project_id", "")).strip()
        if not project_id or project_id in {"your-project-id", "...", ""}:
            return False

        private_key = str(account.get("private_key", "")).strip()
        if not private_key or "BEGIN PRIVATE KEY" not in private_key or "..." in private_key:
            return False

        client_email = str(account.get("client_email", "")).strip()
        if not client_email or "@" not in client_email or "..." in client_email:
            return False

        return True
    except Exception:
        return False

