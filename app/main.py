from __future__ import annotations

import math
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from auth import cookies, restore_session, sign_in, sign_out, sign_up
from config import ASSETS, firebase_is_configured, is_admin
from firebase_store import (ensure_profile, execute_market_order, game_snapshot,
                            get_or_create_portfolio, publish_leaderboard,
                            start_game, pause_game, resume_game, top_twenty, db)
from market_data import load_market_data, portfolio_value, public_candles
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
LOGO_PATH = ROOT / "assets" / "ecofin_logo.jpeg"

st.set_page_config(page_title="Trading Competition", page_icon="📈", layout="wide")

def render_brand() -> None:
    if LOGO_PATH.exists():
        left, right = st.columns([0.18, 0.82])

        with left:
            st.image(str(LOGO_PATH), width=70)

        with right:
            st.markdown(
                """
                <div class="brand-title">
                    ECOFIN
                </div>
                <div class="brand-subtitle">
                    TRADING COMPETITION
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            """
            <div class="brand-title">
                ECOFIN
            </div>
            <div class="brand-subtitle">
                TRADING COMPETITION
            </div>
            """,
            unsafe_allow_html=True,
        )

def apply_styles() -> None:
    st.markdown(
        """
        <style>

        /* ---------- GLOBAL ---------- */

        .stApp {
            background:
                radial-gradient(
                    circle at top right,
                    rgba(22, 199, 154, 0.07),
                    transparent 30%
                ),
                #080d14;
            color: #e8eef7;
        }

        .block-container {
            max-width: 1450px;
            padding-top: 2rem;
            padding-bottom: 3rem;
        }

        /* ---------- BRAND ---------- */

        .brand-title {
            font-size: 2rem;
            font-weight: 850;
            letter-spacing: -1px;
            line-height: 1;
        }

        .brand-subtitle {
            color: #8e9bad;
            font-size: .78rem;
            font-weight: 700;
            letter-spacing: 2px;
            margin-top: 7px;
        }

        /* ---------- CARDS ---------- */

        .dashboard-card {
            background: linear-gradient(
                145deg,
                #111925,
                #0d141e
            );
            border: 1px solid #243246;
            border-radius: 14px;
            padding: 18px 20px;
        }

        .card-label {
            color: #8795aa;
            font-size: .72rem;
            font-weight: 750;
            letter-spacing: 1.2px;
            text-transform: uppercase;
        }

        .card-value {
            font-size: 1.55rem;
            font-weight: 800;
            margin-top: 5px;
        }

        /* ---------- MARKET STATUS ---------- */

        .market-live {
            background: rgba(22, 199, 154, .09);
            border: 1px solid rgba(22, 199, 154, .3);
            border-radius: 12px;
            padding: 13px 16px;
        }

        .market-paused {
            background: rgba(245, 185, 66, .09);
            border: 1px solid rgba(245, 185, 66, .3);
            border-radius: 12px;
            padding: 13px 16px;
        }

        /* ---------- BUTTONS ---------- */

        .stButton > button {
            border-radius: 9px;
            font-weight: 750;
            min-height: 42px;
        }

        /* ---------- SIDEBAR ---------- */

        [data-testid="stSidebar"] {
            background: #0d141e;
            border-right: 1px solid #202c3d;
        }

        /* ---------- TABLES ---------- */

        [data-testid="stDataFrame"] {
            border: 1px solid #243246;
            border-radius: 12px;
            overflow: hidden;
        }

        </style>
        """,
        unsafe_allow_html=True,
    )

def money(value: float) -> str:
    return f"${value:,.2f}"


def chart(asset: str, candles: pd.DataFrame) -> go.Figure:
    figure = go.Figure(go.Candlestick(x=candles["Date"], open=candles["Open"], high=candles["High"], low=candles["Low"], close=candles["Close"], name=asset))
    figure.update_layout(template="plotly_dark", height=510, margin=dict(l=10, r=10, t=35, b=10), title=f"{asset} — revealed market history",
                         xaxis_rangeslider_visible=False, paper_bgcolor="#0e1117", plot_bgcolor="#0e1117")
    return figure


def portfolio_table(portfolio: dict, market: dict, index: int) -> pd.DataFrame:
    rows = []
    for asset, position in portfolio.get("positions", {}).items():
        qty, entry = int(position["quantity"]), float(position["avg_entry"])
        last = float(market[asset].iloc[index]["Close"])
        value = qty * last
        rows.append({"Asset": asset, "Qty": qty, "Avg Entry": money(entry), "Last": money(last), "Value": money(value), "Unrealized P&L": money(value - qty * entry)})
    return pd.DataFrame(rows)


def render_login(manager) -> None:
    st.title("📈 Trading Competition")
    st.caption("Sign in with your Student ID. Every account begins with $100,000 virtual cash.")
    signin, signup = st.tabs(["Sign in", "Create account"])
    with signin:
        with st.form("login"):
            student_id = st.text_input("Student ID").upper().strip()
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign in", type="primary")
        if submitted:
            try:
                sign_in(manager, student_id, password)
                st.rerun()
            except ValueError as error:
                st.error(str(error))
    with signup:
        with st.form("signup"):
            student_id = st.text_input("Student ID", key="new_id").upper().strip()
            nickname = st.text_input("Nickname", max_chars=30).strip()
            password = st.text_input("Password (8+ characters)", type="password", key="new_password")
            submitted = st.form_submit_button("Create account", type="primary")
        if submitted:
            if not nickname:
                st.error("A nickname is required.")
            else:
                try:
                    uid = sign_up(manager, student_id, password)
                    ensure_profile(uid, student_id, nickname)
                    st.rerun()
                except (ValueError, PermissionError) as error:
                    st.error(str(error))


@st.fragment(run_every=10)
def leaderboard_fragment() -> None:
    game = game_snapshot()
    st.title("🏆 LIVE LEADERBOARD")
    if not game.get("game_id"):
        st.info("Waiting for the professor to start the competition.")
        return
    st.caption(f"Game {game['game_id']} · Candle {game['index'] + 1}/{game['max_index'] + 1}")
    rows = top_twenty(game["game_id"])
    if not rows:
        st.info("Waiting for the first portfolio update.")
        return
    table = pd.DataFrame(rows)
    table.insert(0, "Rank", range(1, len(table) + 1))
    table["Portfolio Value"] = table["total_value"].map(money)
    st.dataframe(table[["Rank", "nickname", "student_id", "Portfolio Value"]], hide_index=True, use_container_width=True,
                 column_config={"nickname": "Trader", "student_id": "Student ID"})


@st.fragment(run_every=10)
def dashboard_fragment(uid: str, profile: dict, market: dict) -> None:
    game = game_snapshot()
    if not game.get("game_id"):
        st.info("The game has not started yet. Your dashboard will activate automatically.")
        return
    index = int(game["index"])
    portfolio = get_or_create_portfolio(game["game_id"], uid)
    total = portfolio_value(portfolio, market, index)
    if game.get("status") == "running":
        total = publish_leaderboard(uid, profile, portfolio, game, market)
    status = game.get("status", "waiting")

    st.caption(
      f"Game: {game['game_id']} · "
      f"Candle {index + 1}/{game['max_index'] + 1}"
    )

    if status == "paused":
      st.warning(
          "🟡 MARKET PAUSED\n\n"
          "The professor has temporarily paused the market. "
          "Prices and trading are frozen."
      )
    elif status == "running":
      st.success("🟢 MARKET LIVE")
    first, second, third = st.columns(3)
    first.metric("Cash", money(float(portfolio["cash"])))
    second.metric("Portfolio Value", money(total))
    third.metric("Open Positions", len(portfolio.get("positions", {})))
    selected = st.selectbox("SELECT ASSET", ASSETS, key="asset_picker")
    left, right = st.columns([3, 1])
    with left:
        st.plotly_chart(chart(selected, public_candles(market[selected], index)), use_container_width=True, config={"displaylogo": False})
    with right:
        st.subheader("Market Order")
        st.caption("Trades execute at the current revealed candle close. No limit orders or short selling.")
        mode = st.radio("Order size", ["Quantity", "% of available"], key="order_mode")
        if mode == "Quantity":
            quantity = int(st.number_input("Quantity", min_value=1, step=1, key="qty"))
            percent = None
        else:
            percent = float(st.number_input("Percentage", min_value=1.0, max_value=100.0, step=1.0, key="pct"))
            
            price = float(market[selected].iloc[index]["Close"])
            st.caption("Buy uses cash; sell uses your current position.")
            quantity = 1  # Converted to a side-specific quantity after the button is chosen.
        buy, sell = st.columns(2)
        buy_clicked = buy.button("MARKET BUY", type="primary", use_container_width=True, disabled=game.get("status") != "running")
        sell_clicked = sell.button("MARKET SELL", use_container_width=True, disabled=game.get("status") != "running")
        if buy_clicked or sell_clicked:
            try:
                side = "buy" if buy_clicked else "sell"
                if percent is not None:
                    price = float(market[selected].iloc[index]["Close"])
                    base = float(portfolio["cash"]) / price if side == "buy" else int(portfolio.get("positions", {}).get(selected, {}).get("quantity", 0))
                    quantity = math.floor(base * percent / 100)
                confirmation = execute_market_order(uid, game, selected, quantity, side, market)
                st.success(confirmation)
                st.rerun(scope="fragment")
            except ValueError as error:
                st.error(str(error))
    st.subheader("Positions")
    positions = portfolio_table(portfolio, market, index)
    if positions.empty:
        st.caption("No open positions.")
    else:
        st.dataframe(positions, hide_index=True, use_container_width=True)


def render_admin(profile: dict) -> None:
    with st.expander("Professor controls", expanded=True):
        game = game_snapshot()

        status = game.get("status", "waiting")
        game_id = game.get("game_id")

        st.markdown("### Professor controls")

        if status == "running":
            st.success(
                f"🟢 MARKET LIVE  ·  {game_id or 'No active game'}"
            )

        elif status == "paused":
            st.warning(
                f"🟡 MARKET PAUSED  ·  {game_id or 'No active game'}"
            )

        elif status == "finished":
            st.info(
                f"Competition finished  ·  {game_id or 'No active game'}"
            )

        else:
            st.info("Waiting for a competition to start.")

        st.caption(
            f"Candle {game.get('index', 0) + 1} / "
            f"{game.get('max_index', 251) + 1}"
        )

        st.divider()

        new_game_id = st.text_input(
            "New game ID",
            value=datetime.now().strftime("class-%Y%m%d-%H%M")
        )

        if status not in {"running", "paused"}:
            if st.button("START GAME", type="primary", use_container_width=True):
                if not new_game_id.strip():
                    st.error("Game ID is required.")
                else:
                    try:
                        start_game(new_game_id.strip())
                        st.success(
                            "Game started. All clients are synchronized."
                        )
                        st.rerun()
                    except Exception as error:
                        st.error(str(error))

        elif status == "running":
            if st.button(
                "⏸ PAUSE MARKET",
                use_container_width=True
            ):
                try:
                    pause_game()
                    st.success(
                        "Market paused. All participants are now frozen."
                    )
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))

        elif status == "paused":
            if st.button(
                "▶ RESUME MARKET",
                type="primary",
                use_container_width=True
            ):
                try:
                    resume_game()
                    st.success(
                        "Market resumed."
                    )
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))

def main() -> None:
    # Credentials are optional for UI review. The production path below is
    # untouched and activates automatically as soon as Firebase is configured.
    apply_styles()
    if not firebase_is_configured():
        from demo import render
        render()
        return
    # Stage display is deliberately unauthenticated, but its data is only ranked totals.
    if st.query_params.get("view") == "leaderboard":
        st.markdown("<style>[data-testid='stHeader'] {display:none} .stApp {background:#06080d}</style>", unsafe_allow_html=True)
        leaderboard_fragment()
        return
    manager = cookies()
    uid = restore_session(manager)
    if not uid:
        render_login(manager)
        return
    try:
        # A profile is immutable after signup, binding Firebase account to Student ID.
        profile = db().collection("users").document(uid).get().to_dict()
        if not profile:
            raise PermissionError("Account profile is missing; contact the professor.")
    except Exception as error:
        st.error(f"Unable to load your account: {error}")
        return
    st.sidebar.write(f"Signed in as **{profile['nickname']}** ({profile['student_id']})")
    if st.sidebar.button("Sign out"):
        sign_out(manager)
        st.rerun()
    st.sidebar.link_button("Open stage leaderboard", "?view=leaderboard")
    if is_admin(profile["student_id"]):
        render_admin(profile)
    market = load_market_data()
    render_brand()
    dashboard_fragment(uid, profile, market)


if __name__ == "__main__":
    main()
