from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import firebase_admin
from firebase_admin import credentials, firestore
import streamlit as st

from config import GAME_DOC, STARTING_CASH, TICK_SECONDS
from market_data import close_at, portfolio_value


@st.cache_resource(show_spinner=False)
def db():
    if not firebase_admin._apps:
        cert = credentials.Certificate(dict(st.secrets["firebase_service_account"]))
        firebase_admin.initialize_app(cert)
    return firestore.client()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: Any) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def game_snapshot() -> dict[str, Any]:
    snap = db().collection("games").document(GAME_DOC).get()
    if not snap.exists:
        return {"status": "waiting", "game_id": None, "index": 0, "max_index": 251}
    game = snap.to_dict()
    game["index"] = game_index(game)
    return game


def game_index(game: dict[str, Any]) -> int:
    status = game.get("status")

    if status == "finished":
        return int(game.get("max_index", 251))

    if status in {"waiting", "scheduled"}:
        return 0

    start_at = _as_utc(game["start_at"])
    now = utc_now()

    # Total time the market has already spent paused.
    total_paused = float(game.get("total_paused_seconds", 0.0))

    # If currently paused, do NOT count the time since paused_at.
    if status == "paused":
        paused_at = game.get("paused_at")

        if paused_at:
            paused_at = _as_utc(paused_at)
            effective_now = paused_at
        else:
            effective_now = now
    else:
        effective_now = now

    elapsed = max(
        0.0,
        (effective_now - start_at).total_seconds() - total_paused
    )

    return min(
        int(elapsed // int(game["tick_seconds"])),
        int(game.get("max_index", 251))
    )

def start_game(game_id: str) -> None:
    """Atomically starts/restarts a game. Only the admin route calls this."""
    ref = db().collection("games").document(GAME_DOC)
    transaction = db().transaction()

    @firestore.transactional
    def apply(transaction):
        transaction.set(ref, {
            "game_id": game_id,
            "status": "running",
            "start_at": utc_now(),
            "tick_seconds": TICK_SECONDS,
            "max_index": 251,

            # Pause support
            "paused_at": None,
            "total_paused_seconds": 0.0,

            "updated_at": firestore.SERVER_TIMESTAMP,
        })

    apply(transaction)

def pause_game() -> None:
    """Pause the currently running game."""
    ref = db().collection("games").document(GAME_DOC)
    transaction = db().transaction()

    @firestore.transactional
    def apply(transaction):
        snap = transaction.get(ref)

        if not snap.exists:
            raise ValueError("No active game.")

        game = snap.to_dict()

        if game.get("status") != "running":
            raise ValueError("The game is not currently running.")

        transaction.update(ref, {
            "status": "paused",
            "paused_at": utc_now(),
            "updated_at": firestore.SERVER_TIMESTAMP,
        })

    apply(transaction)


def resume_game() -> None:
    """Resume a paused game without advancing the market during the pause."""
    ref = db().collection("games").document(GAME_DOC)
    transaction = db().transaction()

    @firestore.transactional
    def apply(transaction):
        snap = transaction.get(ref)

        if not snap.exists:
            raise ValueError("No active game.")

        game = snap.to_dict()

        if game.get("status") != "paused":
            raise ValueError("The game is not currently paused.")

        paused_at = game.get("paused_at")

        if not paused_at:
            raise ValueError("Paused game is missing paused_at.")

        paused_at = _as_utc(paused_at)
        pause_duration = max(
            0.0,
            (utc_now() - paused_at).total_seconds()
        )

        total_paused = float(
            game.get("total_paused_seconds", 0.0)
        )

        transaction.update(ref, {
            "status": "running",
            "paused_at": None,
            "total_paused_seconds": total_paused + pause_duration,
            "updated_at": firestore.SERVER_TIMESTAMP,
        })

    apply(transaction)


def ensure_profile(uid: str, student_id: str, nickname: str) -> dict[str, Any]:
    ref = db().collection("users").document(uid)
    snap = ref.get()
    if not snap.exists:
        ref.create({"student_id": student_id.upper(), "nickname": nickname, "created_at": firestore.SERVER_TIMESTAMP})
        return {"student_id": student_id.upper(), "nickname": nickname}
    profile = snap.to_dict()
    if profile["student_id"] != student_id.upper():
        raise PermissionError("Student ID does not match this Firebase account.")
    return profile


def portfolio_ref(game_id: str, uid: str):
    return db().collection("portfolios").document(f"{game_id}_{uid}")


def get_or_create_portfolio(game_id: str, uid: str) -> dict[str, Any]:
    ref = portfolio_ref(game_id, uid)
    snap = ref.get()
    if not snap.exists:
        initial = {"game_id": game_id, "uid": uid, "cash": STARTING_CASH, "positions": {}, "updated_at": firestore.SERVER_TIMESTAMP}
        try:
            ref.create(initial)
        except Exception:
            pass  # A second tab may have created it first.
        snap = ref.get()
    return snap.to_dict()


def execute_market_order(uid: str, game: dict[str, Any], asset: str, quantity: int, side: str, market: dict) -> str:
    if side not in {"buy", "sell"} or quantity <= 0:
        raise ValueError("Quantity must be a positive whole number.")
    if game.get("status") != "running" or not game.get("game_id"):
        raise ValueError("The game is not running.")
    game_ref = db().collection("games").document(GAME_DOC)
    ref = portfolio_ref(game["game_id"], uid)
    transaction = db().transaction()

    @firestore.transactional
    def apply(transaction):
        fresh_game = transaction.get(game_ref).to_dict()
        if not fresh_game or fresh_game.get("status") != "running" or fresh_game["game_id"] != game["game_id"]:
            raise ValueError("Game state changed; refresh and try again.")
        index = game_index(fresh_game)
        price = close_at(market, asset, index)
        portfolio_snap = transaction.get(ref)
        portfolio = portfolio_snap.to_dict() if portfolio_snap.exists else {
            "game_id": fresh_game["game_id"], "uid": uid, "cash": STARTING_CASH, "positions": {}
        }
        positions = dict(portfolio.get("positions", {}))
        existing = dict(positions.get(asset, {"quantity": 0, "avg_entry": 0.0}))
        current_qty = int(existing["quantity"])
        cash = float(portfolio["cash"])
        if side == "buy":
            cost = quantity * price
            if cost > cash + 0.0001:
                raise ValueError("Insufficient cash.")
            new_qty = current_qty + quantity
            existing = {"quantity": new_qty, "avg_entry": round(((current_qty * float(existing["avg_entry"])) + cost) / new_qty, 6)}
            cash -= cost
        else:
            if quantity > current_qty:
                raise ValueError("You cannot sell more than your current position.")
            new_qty = current_qty - quantity
            cash += quantity * price
            existing = {"quantity": new_qty, "avg_entry": float(existing["avg_entry"])}
        if existing["quantity"]:
            positions[asset] = existing
        else:
            positions.pop(asset, None)
        transaction.set(ref, {"game_id": fresh_game["game_id"], "uid": uid, "cash": round(cash, 2), "positions": positions,
                              "last_trade": {"side": side, "asset": asset, "quantity": quantity, "price": price, "index": index},
                              "updated_at": firestore.SERVER_TIMESTAMP}, merge=True)
        return price
    price = apply(transaction)
    return f"{side.upper()} {quantity} {asset} @ ${price:,.2f}"


def publish_leaderboard(uid: str, profile: dict[str, Any], portfolio: dict[str, Any], game: dict[str, Any], market: dict) -> float:
    """One upsert per user/index; repeated fragment reruns are no-ops."""
    index = int(game["index"])
    game_id = game["game_id"]
    ref = db().collection("leaderboard").document(f"{game_id}_{uid}")
    snap = ref.get()
    if snap.exists and snap.to_dict().get("price_index") == index:
        return float(snap.to_dict()["total_value"])
    total = portfolio_value(portfolio, market, index)
    ref.set({"game_id": game_id, "uid": uid, "student_id": profile["student_id"], "nickname": profile["nickname"],
             "total_value": total, "price_index": index, "updated_at": firestore.SERVER_TIMESTAMP}, merge=True)
    return total


def top_twenty(game_id: str) -> list[dict[str, Any]]:
    query = db().collection("leaderboard").where("game_id", "==", game_id).order_by("total_value", direction=firestore.Query.DESCENDING).limit(20)
    return [doc.to_dict() for doc in query.stream()]
