from __future__ import annotations

import json
import re
from typing import Any

import requests
import streamlit as st
from firebase_admin import auth

# streamlit-cookies-manager 0.2.0 still declares one internal helper with
# @st.cache.  Alias only while that module is imported so it is created with
# Streamlit's current cache implementation, then immediately restore Streamlit.
_legacy_cache = st.cache
st.cache = st.cache_data
try:
    from streamlit_cookies_manager import EncryptedCookieManager
finally:
    st.cache = _legacy_cache


COOKIE_KEY = "session"


def cookies() -> EncryptedCookieManager:
    manager = EncryptedCookieManager(prefix="trading_comp_", password=st.secrets["app"]["cookie_password"])
    if not manager.ready():
        st.stop()
    return manager


def _api_url(action: str) -> str:
    return f"https://identitytoolkit.googleapis.com/v1/accounts:{action}?key={st.secrets['firebase_web']['api_key']}"


def _email(student_id: str) -> str:
    cleaned = student_id.strip().upper()
    if not re.fullmatch(r"[A-Z0-9_-]{3,40}", cleaned):
        raise ValueError("Student ID must be 3–40 letters, numbers, _ or -.")
    return f"{cleaned}@students.trading-competition.invalid"


def _identity(action: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = requests.post(_api_url(action), json=payload, timeout=10)
    if not response.ok:
        message = response.json().get("error", {}).get("message", "Authentication failed").replace("_", " ").lower()
        raise ValueError(message.capitalize())
    return response.json()


def _save_session(manager: EncryptedCookieManager, response: dict[str, Any]) -> None:
    manager[COOKIE_KEY] = json.dumps({"refresh_token": response["refreshToken"]})
    manager.save()
    st.session_state["id_token"] = response["idToken"]
    st.session_state["uid"] = response["localId"]


def restore_session(manager: EncryptedCookieManager) -> str | None:
    if st.session_state.get("uid"):
        return st.session_state["uid"]
    raw = manager.get(COOKIE_KEY)
    if not raw:
        return None
    try:
        refresh_token = json.loads(raw)["refresh_token"]
        response = requests.post(
            f"https://securetoken.googleapis.com/v1/token?key={st.secrets['firebase_web']['api_key']}",
            data={"grant_type": "refresh_token", "refresh_token": refresh_token}, timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        token = data["id_token"]
        decoded = auth.verify_id_token(token, check_revoked=True)
        st.session_state["id_token"] = token
        st.session_state["uid"] = decoded["uid"]
        return decoded["uid"]
    except Exception:
        manager[COOKIE_KEY] = ""
        manager.save()
        return None


def sign_in(manager: EncryptedCookieManager, student_id: str, password: str) -> str:
    result = _identity("signInWithPassword", {"email": _email(student_id), "password": password, "returnSecureToken": True})
    _save_session(manager, result)
    return result["localId"]


def sign_up(manager: EncryptedCookieManager, student_id: str, password: str) -> str:
    if len(password) < 8:
        raise ValueError("Use a password of at least 8 characters.")
    result = _identity("signUp", {"email": _email(student_id), "password": password, "returnSecureToken": True})
    _save_session(manager, result)
    return result["localId"]


def sign_out(manager: EncryptedCookieManager) -> None:
    manager[COOKIE_KEY] = ""
    manager.save()
    st.session_state.clear()
