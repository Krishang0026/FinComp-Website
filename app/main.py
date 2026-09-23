from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from auth import cookies, restore_session, sign_in, sign_out, sign_up
from config import ASSETS, firebase_is_configured, is_admin
from firebase_store import (
    ensure_profile,
    execute_market_order,
    game_snapshot,
    get_or_create_portfolio,
    publish_leaderboard,
    start_game,
    pause_game,
    resume_game,
    top_twenty,
    db,
)
from market_data import load_market_data, portfolio_value, public_candles


# ------------------------------------------------------------
# Page configuration
# ------------------------------------------------------------

st.set_page_config(
    page_title="Ecofin Trading Competition",
    page_icon="📈",
    layout="wide",
)


# ------------------------------------------------------------
# Paths
# ------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]
LOGO_PATH = ROOT / "assets" / "ecofin_logo.png"


# ------------------------------------------------------------
# Styling
# ------------------------------------------------------------

st.markdown(
    """
    <style>

    /* Main application background */
    .stApp {
        background-color: #0e1117;
    }

    /* Remove some unnecessary top spacing */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }

    /* Dashboard cards */
    .dashboard-card {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 14px;
        padding: 18px 20px;
        min-height: 118px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.18);
    }

    .dashboard-card-label {
        color: #8b949e;
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.8px;
        text-transform: uppercase;
        margin-bottom: 9px;
    }

    .dashboard-card-value {
        color: #f0f6fc;
        font-size: 1.55rem;
        font-weight: 750;
        line-height: 1.2;
    }

    .dashboard-card-subtitle {
        color: #8b949e;
        font-size: 0.75rem;
        margin-top: 7px;
    }

    /* Ecofin header */
    .ecofin-title {
        color: #f0f6fc;
        font-size: 2rem;
        font-weight: 800;
        line-height: 1.05;
        margin: 0;
    }

    .ecofin-subtitle {
        color: #8b949e;
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 2px;
        margin-top: 6px;
    }

    /* Section headings */
    .section-title {
        color: #f0f6fc;
        font-size: 1.2rem;
        font-weight: 700;
        margin-top: 1rem;
        margin-bottom: 0.5rem;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ------------------------------------------------------------
# Utility functions
# ------------------------------------------------------------

def money(value: float) -> str:
    return f"${value:,.2f}"


def render_brand() -> None:
    """
    Display the Ecofin competition title.
    """
    st.markdown(
        '<div class="ecofin-title">ECOFIN</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="ecofin-subtitle">TRADING COMPETITION</div>',
        unsafe_allow_html=True,
    )
    st.divider()


def chart(
    asset: str,
    candles: pd.DataFrame,
    period: str = "All",
) -> go.Figure:

    candles = candles.copy()

    if candles.empty:

        return go.Figure()

    candles["Date"] = pd.to_datetime(
        candles["Date"]
    )

    latest_date = candles["Date"].max()

    period_offsets = {
        "1 Month": pd.DateOffset(months=1),
        "3 Months": pd.DateOffset(months=3),
        "6 Months": pd.DateOffset(months=6),
        "1 Year": pd.DateOffset(years=1),
    }

    if period in period_offsets:

        cutoff = (
            latest_date
            - period_offsets[period]
        )

        candles = candles[
            candles["Date"] >= cutoff
        ]

    figure = go.Figure(
        go.Candlestick(
            x=candles["Date"],
            open=candles["Open"],
            high=candles["High"],
            low=candles["Low"],
            close=candles["Close"],
            name=asset,
        )
    )

    figure.update_layout(
        template="plotly_dark",
        height=510,
        margin=dict(
            l=10,
            r=10,
            t=35,
            b=10,
        ),
        title=(
            f"{asset} · {period}"
        ),
        xaxis_rangeslider_visible=False,
        paper_bgcolor="#0e1117",
        plot_bgcolor="#0e1117",
        hovermode="x unified",
    )

    return figure

    return figure


def portfolio_table(
    portfolio: dict,
    market: dict,
    index: int,
) -> pd.DataFrame:

    rows = []

    for asset, position in portfolio.get("positions", {}).items():
        qty = int(position["quantity"])
        entry = float(position["avg_entry"])

        last = float(
            market[asset].iloc[index]["Close"]
        )

        value = qty * last

        rows.append(
            {
                "Asset": asset,
                "Qty": qty,
                "Avg Entry": money(entry),
                "Last": money(last),
                "Value": money(value),
                "Unrealized P&L": money(
                    value - qty * entry
                ),
            }
        )

    return pd.DataFrame(rows)


# ------------------------------------------------------------
# Login
# ------------------------------------------------------------

def render_login(manager) -> None:

    render_brand()

    st.title("Sign in to the Trading Competition")

    st.caption(
        "Sign in with your Student ID. "
        "Every account begins with $100,000 virtual cash."
    )

    signin, signup = st.tabs(
        ["Sign in", "Create account"]
    )

    with signin:

        with st.form("login"):

            student_id = st.text_input(
                "Student ID"
            ).upper().strip()

            password = st.text_input(
                "Password",
                type="password",
            )

            submitted = st.form_submit_button(
                "Sign in",
                type="primary",
            )

        if submitted:

            try:
                sign_in(
                    manager,
                    student_id,
                    password,
                )

                st.rerun()

            except ValueError as error:
                st.error(str(error))

    with signup:

        with st.form("signup"):

            student_id = st.text_input(
                "Student ID",
                key="new_id",
            ).upper().strip()

            nickname = st.text_input(
                "Nickname",
                max_chars=30,
            ).strip()

            password = st.text_input(
                "Password (8+ characters)",
                type="password",
                key="new_password",
            )

            submitted = st.form_submit_button(
                "Create account",
                type="primary",
            )

        if submitted:

            if not nickname:

                st.error(
                    "A nickname is required."
                )

            else:

                try:

                    uid = sign_up(
                        manager,
                        student_id,
                        password,
                    )

                    ensure_profile(
                        uid,
                        student_id,
                        nickname,
                    )

                    st.rerun()

                except (
                    ValueError,
                    PermissionError,
                ) as error:

                    st.error(str(error))


# ------------------------------------------------------------
# Public leaderboard
# ------------------------------------------------------------

@st.fragment(run_every=10)
def leaderboard_fragment() -> None:

    game = game_snapshot()

    render_brand()

    st.title("🏆 LIVE LEADERBOARD")

    if not game.get("game_id"):

        st.info(
            "Waiting for the professor to start the competition."
        )

        return

    st.caption(
        f"Game {game['game_id']} · "
        f"Candle {game['index'] + 1}/"
        f"{game['max_index'] + 1}"
    )

    rows = top_twenty(
        game["game_id"]
    )

    if not rows:

        st.info(
            "Waiting for the first portfolio update."
        )

        return

    table = pd.DataFrame(rows)

    table.insert(
        0,
        "Rank",
        range(1, len(table) + 1),
    )

    table["Portfolio Value"] = (
        table["total_value"].map(money)
    )

    st.dataframe(
        table[
            [
                "Rank",
                "nickname",
                "student_id",
                "Portfolio Value",
            ]
        ],
        hide_index=True,
        use_container_width=True,
        column_config={
            "nickname": "Trader",
            "student_id": "Student ID",
        },
    )


# ------------------------------------------------------------
# Student dashboard
# ------------------------------------------------------------

@st.fragment(run_every=10)
def dashboard_fragment(
    uid: str,
    profile: dict,
    market: dict,
) -> None:

    game = game_snapshot()

    if not game.get("game_id"):

        st.info(
            "The game has not started yet. "
            "Your dashboard will activate automatically."
        )

        return

    index = int(game["index"])

    portfolio = get_or_create_portfolio(
        game["game_id"],
        uid,
    )

    total = portfolio_value(
        portfolio,
        market,
        index,
    )

    if game.get("status") == "running":

        total = publish_leaderboard(
            uid,
            profile,
            portfolio,
            game,
            market,
        )

    status = game.get(
        "status",
        "waiting",
    )

    # --------------------------------------------------------
    # Game information
    # --------------------------------------------------------

    st.caption(
        f"Game: {game['game_id']} · "
        f"Candle {index + 1}/"
        f"{game['max_index'] + 1}"
    )

    # --------------------------------------------------------
    # Market status banner
    # --------------------------------------------------------

    if status == "paused":

        st.warning(
            "🟡 MARKET PAUSED\n\n"
            "The professor has temporarily paused the market. "
            "Prices and trading are frozen."
        )

    elif status == "running":

        st.success(
            "🟢 MARKET LIVE"
        )

    # --------------------------------------------------------
    # Dashboard summary cards
    # --------------------------------------------------------

    cash_value = float(
        portfolio["cash"]
    )

    portfolio_value_total = float(
        total
    )

    open_positions = len(
        portfolio.get(
            "positions",
            {},
        )
    )

    if status == "paused":
        market_status = "PAUSED"
        status_color = "#f0ad4e"

    elif status == "running":
        market_status = "LIVE"
        status_color = "#3fb950"

    elif status == "finished":
        market_status = "FINISHED"
        status_color = "#8b949e"

    else:
        market_status = status.upper()
        status_color = "#8b949e"

    card1, card2, card3, card4 = st.columns(4)

    # --------------------------------------------------------
    # Cash card
    # --------------------------------------------------------

    with card1:

        st.markdown(
            f"""
            <div class="dashboard-card">
                <div class="dashboard-card-label">
                    Cash
                </div>

                <div class="dashboard-card-value">
                    {money(cash_value)}
                </div>

                <div class="dashboard-card-subtitle">
                    Available balance
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # --------------------------------------------------------
    # Portfolio value card
    # --------------------------------------------------------

    with card2:

        st.markdown(
            f"""
            <div class="dashboard-card">
                <div class="dashboard-card-label">
                    Portfolio Value
                </div>

                <div class="dashboard-card-value">
                    {money(portfolio_value_total)}
                </div>

                <div class="dashboard-card-subtitle">
                    Total current value
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # --------------------------------------------------------
    # Open positions card
    # --------------------------------------------------------

    with card3:

        st.markdown(
            f"""
            <div class="dashboard-card">
                <div class="dashboard-card-label">
                    Open Positions
                </div>

                <div class="dashboard-card-value">
                    {open_positions}
                </div>

                <div class="dashboard-card-subtitle">
                    Currently held assets
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # --------------------------------------------------------
    # Market status card
    # --------------------------------------------------------

    with card4:

        st.markdown(
            f"""
            <div class="dashboard-card">
                <div class="dashboard-card-label">
                    Market Status
                </div>

                <div class="dashboard-card-value"
                     style="color: {status_color};">
                    {market_status}
                </div>

                <div class="dashboard-card-subtitle">
                    Competition state
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.write("")

    # --------------------------------------------------------
    # Asset selection
    # --------------------------------------------------------

    selected = st.selectbox(
    "SELECT ASSET",
    ASSETS,
    key="asset_picker",
    )

    period = st.radio(
        "CHART PERIOD",
        [
            "1 Month",
            "3 Months",
            "6 Months",
            "1 Year",
            "All",
        ],
        horizontal=True,
        key="chart_period",
    )

    left, right = st.columns(
        [3, 1]
    )

    # --------------------------------------------------------
    # Chart
    # --------------------------------------------------------

    with left:
        revealed_candles = public_candles(
            market[selected],
            index,
        )
        st.plotly_chart(
            chart(
                selected,
                revealed_candles,
                period,
            ),
            use_container_width=True,
            config={"displaylogo": False},
        )
    

    # --------------------------------------------------------
    # Trading panel
    # --------------------------------------------------------

    with right:

        st.subheader(
            "Market Order"
        )

        st.caption(
            "Trades execute at the current revealed "
            "candle close. No limit orders or short selling."
        )

        mode = st.radio(
            "Order size",
            [
                "Quantity",
                "% of available",
            ],
            key="order_mode",
        )

        if mode == "Quantity":

            quantity = int(
                st.number_input(
                    "Quantity",
                    min_value=1,
                    step=1,
                    key="qty",
                )
            )

            percent = None

        else:

            percent = float(
                st.number_input(
                    "Percentage",
                    min_value=1.0,
                    max_value=100.0,
                    step=1.0,
                    key="pct",
                )
            )

            price = float(
                market[selected]
                .iloc[index]["Close"]
            )

            st.caption(
                "Buy uses cash; sell uses your current position."
            )

            quantity = 1

        # ----------------------------------------------------
        # Buy / sell buttons
        # Disabled while market is paused
        # ----------------------------------------------------

        buy, sell = st.columns(2)

        trading_disabled = (
            game.get("status") != "running"
        )

        buy_clicked = buy.button(
            "MARKET BUY",
            type="primary",
            use_container_width=True,
            disabled=trading_disabled,
        )

        sell_clicked = sell.button(
            "MARKET SELL",
            use_container_width=True,
            disabled=trading_disabled,
        )

        if buy_clicked or sell_clicked:

            try:

                side = (
                    "buy"
                    if buy_clicked
                    else "sell"
                )

                if percent is not None:

                    price = float(
                        market[selected]
                        .iloc[index]["Close"]
                    )

                    if side == "buy":

                        base = (
                            float(portfolio["cash"])
                            / price
                        )

                    else:

                        base = int(
                            portfolio
                            .get("positions", {})
                            .get(selected, {})
                            .get("quantity", 0)
                        )

                    quantity = math.floor(
                        base * percent / 100
                    )

                confirmation = execute_market_order(
                    uid,
                    game,
                    selected,
                    quantity,
                    side,
                    market,
                )

                st.success(
                    confirmation
                )

                st.rerun(
                    scope="fragment"
                )

            except ValueError as error:

                st.error(
                    str(error)
                )

    # --------------------------------------------------------
    # Positions
    # --------------------------------------------------------

    st.subheader(
        "Positions"
    )

    positions = portfolio_table(
        portfolio,
        market,
        index,
    )

    if positions.empty:

        st.caption(
            "No open positions."
        )

    else:

        st.dataframe(
            positions,
            hide_index=True,
            use_container_width=True,
        )


# ------------------------------------------------------------
# Professor controls
# ------------------------------------------------------------

def render_admin(profile: dict) -> None:

    with st.expander(
        "Professor controls",
        expanded=True,
    ):

        game = game_snapshot()

        status = game.get(
            "status",
            "waiting",
        )

        game_id = game.get(
            "game_id"
        )

        st.markdown(
            "### Professor controls"
        )

        # ----------------------------------------------------
        # Current market status
        # ----------------------------------------------------

        if status == "running":

            st.success(
                f"🟢 MARKET LIVE  ·  "
                f"{game_id or 'No active game'}"
            )

        elif status == "paused":

            st.warning(
                f"🟡 MARKET PAUSED  ·  "
                f"{game_id or 'No active game'}"
            )

        elif status == "finished":

            st.info(
                f"Competition finished  ·  "
                f"{game_id or 'No active game'}"
            )

        else:

            st.info(
                "Waiting for a competition to start."
            )

        st.caption(
            f"Candle {game.get('index', 0) + 1} / "
            f"{game.get('max_index', 251) + 1}"
        )

        st.divider()

        # ----------------------------------------------------
        # New game
        # ----------------------------------------------------

        new_game_id = st.text_input(
            "New game ID",
            value=datetime.now().strftime(
                "class-%Y%m%d-%H%M"
            ),
        )

        # ----------------------------------------------------
        # Start game
        # ----------------------------------------------------

        if status not in {
            "running",
            "paused",
        }:

            if st.button(
                "START GAME",
                type="primary",
                use_container_width=True,
            ):

                if not new_game_id.strip():

                    st.error(
                        "Game ID is required."
                    )

                else:

                    try:

                        start_game(
                            new_game_id.strip()
                        )

                        st.success(
                            "Game started. "
                            "All clients are synchronized."
                        )

                        st.rerun()

                    except Exception as error:

                        st.error(
                            str(error)
                        )

        # ----------------------------------------------------
        # Pause game
        # ----------------------------------------------------

        elif status == "running":

            if st.button(
                "⏸ PAUSE MARKET",
                use_container_width=True,
            ):

                try:

                    pause_game()

                    st.success(
                        "Market paused. "
                        "All participants are now frozen."
                    )

                    st.rerun()

                except ValueError as error:

                    st.error(
                        str(error)
                    )

        # ----------------------------------------------------
        # Resume game
        # ----------------------------------------------------

        elif status == "paused":

            if st.button(
                "▶ RESUME MARKET",
                type="primary",
                use_container_width=True,
            ):

                try:

                    resume_game()

                    st.success(
                        "Market resumed."
                    )

                    st.rerun()

                except ValueError as error:

                    st.error(
                        str(error)
                    )


# ------------------------------------------------------------
# Main application
# ------------------------------------------------------------

def main() -> None:

    # --------------------------------------------------------
    # Demo mode when Firebase is not configured
    # --------------------------------------------------------

    # --------------------------------------------------------
    # Local mode
    # --------------------------------------------------------
    # Firebase is disabled for local development.

    # --------------------------------------------------------
    # Public leaderboard stage view
    # --------------------------------------------------------

    if st.query_params.get(
        "view"
    ) == "leaderboard":

        st.markdown(
            """
            <style>
            [data-testid="stHeader"] {
                display: none;
            }

            .stApp {
                background: #06080d;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

        leaderboard_fragment()

        return

    # --------------------------------------------------------
    # Authentication
    # --------------------------------------------------------

    manager = cookies()

    uid = restore_session(
        manager
    )

    if not uid:

        render_login(
            manager
        )

        return

    # --------------------------------------------------------
    # Load user profile
    # --------------------------------------------------------

    try:

        profile = (
            db()
            .collection("users")
            .document(uid)
            .get()
            .to_dict()
        )

        if not profile:

            raise PermissionError(
                "Account profile is missing; "
                "contact the professor."
            )

    except Exception as error:

        st.error(
            f"Unable to load your account: {error}"
        )

        return

    # --------------------------------------------------------
    # Sidebar
    # --------------------------------------------------------

    st.sidebar.write(
        f"Signed in as **{profile['nickname']}** "
        f"({profile['student_id']})"
    )

    if st.sidebar.button(
        "Sign out"
    ):

        sign_out(
            manager
        )

        st.rerun()

    st.sidebar.link_button(
        "Open stage leaderboard",
        "?view=leaderboard",
    )

    # --------------------------------------------------------
    # Professor controls
    # --------------------------------------------------------

    if is_admin(
        profile["student_id"]
    ):

        render_admin(
            profile
        )

    # --------------------------------------------------------
    # Student dashboard
    # --------------------------------------------------------

    market = load_market_data()

    render_brand()

    st.markdown(
        '<div class="section-title">Trading Dashboard</div>',
        unsafe_allow_html=True,
    )

    dashboard_fragment(
        uid,
        profile,
        market,
    )


# ------------------------------------------------------------
# Application entry point
# ------------------------------------------------------------

if __name__ == "__main__":
    main()
