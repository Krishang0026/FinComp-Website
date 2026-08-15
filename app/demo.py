"""No-setup local preview of the trading experience.

This module is never used in Firebase mode. It lets the UI be reviewed before
credentials and the competition CSV are supplied.
"""
from __future__ import annotations

import math
import time

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import ASSETS, STARTING_CASH, TICK_SECONDS
from market_data import load_market_data, portfolio_value, public_candles


NAMES = ("Aarav", "Anaya", "Kabir", "Diya", "Vihaan", "Isha", "Arjun", "Meera", "Rohan", "Zara", "Aditya", "Kiara", "Ishaan", "Naina", "Reyansh", "Avni", "Dev", "Tara", "Neil", "Maya")


def money(value: float) -> str:
    return f"${value:,.2f}"


def _state() -> tuple[dict, int]:
    if "demo_started" not in st.session_state:
        st.session_state.demo_started = time.time() - 48 * TICK_SECONDS
        st.session_state.demo_portfolio = {
            "cash": 63_470.25,
            "positions": {"AAPL": {"quantity": 110, "avg_entry": 184.60}, "NVDA": {"quantity": 85, "avg_entry": 126.20}},
        }
    index = min(251, 48 + int((time.time() - st.session_state.demo_started) // TICK_SECONDS))
    return st.session_state.demo_portfolio, index


def _trade(asset: str, quantity: int, side: str, price: float) -> str:
    portfolio = st.session_state.demo_portfolio
    positions = portfolio["positions"]
    position = positions.get(asset, {"quantity": 0, "avg_entry": 0.0})
    current = int(position["quantity"])
    if quantity < 1:
        raise ValueError("Enter at least one share/unit.")
    if side == "buy":
        cost = quantity * price
        if cost > portfolio["cash"]:
            raise ValueError("Insufficient buying power.")
        position["avg_entry"] = ((current * position["avg_entry"]) + cost) / (current + quantity)
        position["quantity"] = current + quantity
        portfolio["cash"] -= cost
    else:
        if quantity > current:
            raise ValueError(f"You own {current} units of {asset}.")
        position["quantity"] = current - quantity
        portfolio["cash"] += quantity * price
    if position["quantity"]:
        positions[asset] = position
    else:
        positions.pop(asset, None)
    return f"{side.upper()} filled: {quantity} {asset} at {money(price)}"


def _chart(asset: str, frame: pd.DataFrame) -> go.Figure:
    fig = go.Figure(go.Candlestick(x=frame["Date"], open=frame["Open"], high=frame["High"], low=frame["Low"], close=frame["Close"], increasing_line_color="#18c29c", decreasing_line_color="#f05b5b", name=asset))
    fig.update_layout(height=485, margin=dict(l=4, r=4, t=42, b=4), title=dict(text=f"{asset} <span style='font-size:14px;color:#a8b0bf'> · Daily</span>", x=0.01),
                      xaxis_rangeslider_visible=False, showlegend=False, paper_bgcolor="#101722", plot_bgcolor="#101722",
                      font=dict(color="#e6ebf2"), xaxis=dict(gridcolor="#253042"), yaxis=dict(gridcolor="#253042", side="right"))
    return fig


def _positions(portfolio: dict, market: dict, index: int) -> pd.DataFrame:
    rows = []
    for asset, position in portfolio["positions"].items():
        qty, entry = int(position["quantity"]), float(position["avg_entry"])
        last = float(market[asset].iloc[index]["Close"])
        value = qty * last
        rows.append({"Symbol": asset, "Quantity": qty, "Avg. Cost": money(entry), "Last": money(last), "Market Value": money(value), "Unrealized P/L": money(value - qty * entry)})
    return pd.DataFrame(rows)


def _leaderboard(total: float) -> pd.DataFrame:
    values = [113_840, 111_590, 109_445, 107_201, 105_975, 104_860, 103_530, 102_920, 101_875, 100_460, 99_910, 98_720, 97_680, 96_830, 95_600, 94_410, 93_290, 92_115, 90_860, 89_740]
    rows = [{"Trader": name, "Student ID": f"STU{101 + i:03d}", "Portfolio Value": value} for i, (name, value) in enumerate(zip(NAMES, values))]
    rows.append({"Trader": "You (Demo)", "Student ID": "DEMO001", "Portfolio Value": total})
    frame = pd.DataFrame(rows).sort_values("Portfolio Value", ascending=False).head(20).reset_index(drop=True)
    frame.insert(0, "Rank", frame.index + 1)
    frame["Portfolio Value"] = frame["Portfolio Value"].map(money)
    return frame


def _style() -> None:
    st.markdown("""<style>
    .stApp {background:#0b1018;color:#e7edf6}.block-container {max-width:1450px;padding-top:1.4rem}
    [data-testid='stSidebar'] {background:#101722;border-right:1px solid #263245}
    .brand {font-size:1.52rem;font-weight:800;letter-spacing:-.7px}.brand span {color:#16c79a}
    .eyebrow {font-size:.72rem;color:#90a0b7;text-transform:uppercase;letter-spacing:1.15px;font-weight:700}
    .metric-card {background:#101722;border:1px solid #253247;border-radius:10px;padding:15px 18px;min-height:91px}
    .metric-card b {display:block;font-size:1.4rem;margin-top:3px}.positive {color:#18c29c}.muted {color:#93a1b5}
    .order-card {background:#101722;border:1px solid #28364b;border-radius:10px;padding:17px}
    .stButton > button {border-radius:7px;font-weight:750;letter-spacing:.2px}.buy button {background:#10a985!important;border-color:#10a985!important}.sell button {background:#d9534f!important;border-color:#d9534f!important;color:#fff!important}
    [data-testid='stDataFrame'] {border:1px solid #253247;border-radius:10px;overflow:hidden}
    </style>""", unsafe_allow_html=True)


@st.fragment(run_every=10)
def render() -> None:
    _style()
    market = load_market_data()
    portfolio, index = _state()
    total = portfolio_value(portfolio, market, index)
    st.markdown("<div class='brand'>MARKET<span>ARENA</span></div><div class='muted'>A realistic, real-time stock market simulator</div>", unsafe_allow_html=True)
    st.warning("LOCAL PREVIEW MODE — Firebase and your final CSV are not configured. Trades persist only for this browser session.", icon="⚡")
    top = st.columns([1.1, 1.1, 1.1, 2])
    top[0].markdown(f"<div class='metric-card'><div class='eyebrow'>Portfolio value</div><b>{money(total)}</b></div>", unsafe_allow_html=True)
    top[1].markdown(f"<div class='metric-card'><div class='eyebrow'>Cash / buying power</div><b>{money(portfolio['cash'])}</b></div>", unsafe_allow_html=True)
    top[2].markdown(f"<div class='metric-card'><div class='eyebrow'>Today's simulation</div><b class='positive'>LIVE <span class='muted'>· Candle {index + 1}</span></b></div>", unsafe_allow_html=True)
    top[3].markdown("<div class='metric-card'><div class='eyebrow'>Competition clock</div><b>01:00:00 <span class='muted'>· New candle every 10 sec</span></b></div>", unsafe_allow_html=True)
    st.divider()
    nav1, nav2, nav3 = st.columns([1.5, 1.5, 7])
    section = nav1.radio("", ["Trade", "Portfolio", "Leaderboard"], horizontal=True, label_visibility="collapsed")
    nav2.caption("Market open · simulated")
    if section == "Leaderboard":
        st.subheader("Live competition leaderboard")
        st.caption("Ranked by current total portfolio value. The production version reads these values from Firebase every tick.")
        st.dataframe(_leaderboard(total), hide_index=True, use_container_width=True)
        return
    if section == "Portfolio":
        st.subheader("Your portfolio")
        st.caption("Positions are marked at the latest revealed close.")
        table = _positions(portfolio, market, index)
        if table.empty:
            st.info("No positions yet. Go to Trade to place a market order.")
        else:
            st.dataframe(table, hide_index=True, use_container_width=True)
        return
    asset = st.selectbox("Symbol", ASSETS, format_func=lambda value: f"{value}  ·  {value} market", label_visibility="collapsed")
    price = float(market[asset].iloc[index]["Close"])
    change = price - float(market[asset].iloc[max(0, index - 1)]["Close"])
    left, right = st.columns([3.15, 1], gap="large")
    with left:
        st.markdown(f"<span class='eyebrow'>Last price</span> &nbsp; <span style='font-size:1.55rem;font-weight:750'>{money(price)}</span> &nbsp; <span class='{'positive' if change >= 0 else ''}'>{change:+.2f}</span>", unsafe_allow_html=True)
        st.plotly_chart(_chart(asset, public_candles(market[asset], index)), use_container_width=True, config={"displaylogo": False})
    with right:
        st.markdown("<div class='order-card'>", unsafe_allow_html=True)
        st.subheader("Place order")
        st.caption("Market order · executes at last price")
        side = st.radio("Transaction", ["Buy", "Sell"], horizontal=True, label_visibility="collapsed")
        sizing = st.radio("Order size", ["Shares / units", "% of buying power"], label_visibility="collapsed")
        entered = st.number_input("Quantity" if sizing.startswith("Shares") else "Percentage", min_value=1.0, max_value=100.0 if not sizing.startswith("Shares") else None, value=10.0, step=1.0)
        if sizing.startswith("Shares"):
            quantity = int(entered)
        else:
            available = portfolio["cash"] / price if side == "Buy" else portfolio["positions"].get(asset, {}).get("quantity", 0)
            quantity = math.floor(available * entered / 100)
        st.caption(f"Estimated {side.lower()} value: **{money(quantity * price)}**")
        css = "buy" if side == "Buy" else "sell"
        st.markdown(f"<div class='{css}'>", unsafe_allow_html=True)
        clicked = st.button(f"MARKET {side.upper()}", use_container_width=True)
        st.markdown("</div></div>", unsafe_allow_html=True)
        if clicked:
            try:
                st.success(_trade(asset, quantity, side.lower(), price))
                st.rerun(scope="fragment")
            except ValueError as error:
                st.error(str(error))
    st.subheader("Open positions")
    positions = _positions(portfolio, market, index)
    if positions.empty:
        st.caption("No open positions.")
    else:
        st.dataframe(positions, hide_index=True, use_container_width=True)
