import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import json

st.set_page_config(page_title="Macro Superbubble Explorer", layout="wide")

# --------------------------------------------------------------------------
# Cache lifetime
# --------------------------------------------------------------------------
# data_engine.py only refreshes market_data.csv / quarterly_data.csv /
# baa_spread.csv once a week (the GitHub Action), and each new commit already
# triggers a redeploy on Streamlit Cloud, which clears every cache anyway.
# The original ttl=3600 was forcing a full reload + every chart rebuilt from
# scratch every hour, for every visitor, even though the data hadn't changed
# in days. Stretching this to match the real refresh cadence cuts that
# recompute rate by ~12x. Turn it back down if you start updating more often.
DATA_TTL = 60 * 60 * 12  # 12 hours


def _downcast_floats(df: pd.DataFrame) -> pd.DataFrame:
    """float64 -> float32 for numeric columns. Roughly halves a DataFrame's
    memory footprint; no visible difference at chart resolution."""
    float_cols = df.select_dtypes(include="float64").columns
    if len(float_cols):
        df[float_cols] = df[float_cols].astype("float32")
    return df


# --------------------------------------------------------------------------
# Data loading
# --------------------------------------------------------------------------
@st.cache_data(ttl=DATA_TTL)
def load_market_data():
    if not os.path.exists("data/market_data.csv"):
        return pd.DataFrame()
    return _downcast_floats(pd.read_csv("data/market_data.csv", index_col=0, parse_dates=True))


@st.cache_data(ttl=DATA_TTL)
def load_quarterly_data():
    if not os.path.exists("data/quarterly_data.csv"):
        return pd.DataFrame()
    return _downcast_floats(pd.read_csv("data/quarterly_data.csv", index_col=0, parse_dates=True))


@st.cache_data(ttl=DATA_TTL)
def load_baa_spread_data():
    if not os.path.exists("data/baa_spread.csv"):
        return pd.DataFrame()
    return _downcast_floats(pd.read_csv("data/baa_spread.csv", index_col=0, parse_dates=True))


@st.cache_data(ttl=DATA_TTL)
def load_valuations():
    val_path = "data/valuations.json"
    if not os.path.exists(val_path):
        return {}
    with open(val_path, "r") as f:
        return json.load(f)


df_monthly = load_market_data()
df_quarterly = load_quarterly_data()
df_baa = load_baa_spread_data()

st.title("Macro Superbubble Explorer")

# --------------------------------------------------------------------------
# Figure builders
# --------------------------------------------------------------------------
# Streamlit reruns the ENTIRE script top-to-bottom on every interaction, so
# in the original version, clicking the sector dropdown in section 3 was
# rebuilding all ~10 Plotly figures on this page from scratch -- including
# the ones in sections 1, 2, 4, and 5 that have nothing to do with that
# dropdown -- for that user's session. Wrapping each chart builder in
# st.cache_resource means a given chart is built once per DATA_TTL window,
# and every later call (any user, any rerun) just gets handed the same
# object back.
#
# st.cache_resource rather than st.cache_data on purpose: cache_data pickles
# a fresh copy of its return value on every cache hit (the safe default,
# since a caller might mutate what it gets back). That's wasted CPU and
# memory for a Plotly figure that's only ever read, never mutated, after
# it's built. cache_resource skips the copy and hands back the same object --
# much cheaper, and safe here specifically because nothing downstream
# modifies these figures in place.
#
# Each builder takes its DataFrame as an explicit argument rather than
# reading df_monthly/df_quarterly/df_baa from the enclosing scope, so
# Streamlit's cache key is tied to the actual data (via its built-in
# DataFrame hashing) -- a chart rebuilds exactly when its underlying data
# changes, instead of relying on separate TTLs staying in sync by hand.

SECTOR_MAP = {
    "XLK": "Technology", "XLF": "Financials", "XLV": "Health Care",
    "XLY": "Consumer Discretionary", "XLP": "Consumer Staples", "XLE": "Energy",
    "XLI": "Industrials", "XLU": "Utilities", "XLB": "Materials",
    "IYR": "Real Estate", "IYZ": "Telecommunications",
}
SECTORS = list(SECTOR_MAP.keys())


@st.cache_resource(ttl=DATA_TTL)
def build_spy_zscore_fig(df_monthly: pd.DataFrame):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_monthly.index, y=df_monthly["SPY_ZScore"], mode="lines", name="Z-Score"))
    fig.add_hline(y=2, line_dash="dash", line_color="red")
    fig.add_hline(y=-2, line_dash="dash", line_color="green")
    fig.update_xaxes(rangeslider_visible=True)
    return fig


@st.cache_resource(ttl=DATA_TTL)
def build_velocity_fig(df_monthly: pd.DataFrame):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_monthly.index, y=df_monthly["SPY_Velocity_MoM"], mode="lines", name="Velocity (MoM %)"))
    fig.add_trace(go.Scatter(x=df_monthly.index, y=df_monthly["SPY_Acceleration"], mode="lines", name="Acceleration"))
    return fig


@st.cache_resource(ttl=DATA_TTL)
def build_sector_bar_fig(df_monthly: pd.DataFrame):
    zscore_cols = [f"{s}_ZScore" for s in SECTORS]
    available_cols = [c for c in zscore_cols if c in df_monthly.columns]
    latest_data = df_monthly[available_cols].iloc[-1].dropna()
    latest_data.index = [f"{idx.split('_')[0]} - {SECTOR_MAP[idx.split('_')[0]]}" for idx in latest_data.index]
    fig = px.bar(x=latest_data.index, y=latest_data.values, color=latest_data.values, color_continuous_scale="RdYlGn_r")
    fig.add_hline(y=2, line_dash="dash", line_color="red")
    fig.add_hline(y=-2, line_dash="dash", line_color="green")
    return fig


@st.cache_resource(ttl=DATA_TTL)
def build_sector_deep_dive_fig(df_monthly: pd.DataFrame, selected_sector: str):
    df_filtered = df_monthly.loc["1999-01-01":]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_filtered.index, y=df_filtered[f"{selected_sector}_ZScore"], mode="lines"))
    fig.add_hline(y=2, line_dash="dash", line_color="red")
    fig.add_hline(y=-2, line_dash="dash", line_color="green")
    return fig


@st.cache_resource(ttl=DATA_TTL)
def build_volume_fig(df_monthly: pd.DataFrame):
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Bar(x=df_monthly.index, y=df_monthly["Total_Volume_ZScore"], name="Volume Z-Score", marker_color="rgba(135, 206, 250, 0.6)"),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(x=df_monthly.index, y=df_monthly["SPY"], name="S&P 500 Price", mode="lines", line=dict(color="black")),
        secondary_y=True,
    )
    fig.add_hline(y=2, line_dash="dash", line_color="red", secondary_y=False)
    return fig


@st.cache_resource(ttl=DATA_TTL)
def build_baa_fig(df_baa: pd.DataFrame):
    baa_series = df_baa["BAAFF"].dropna()
    rolling_mean = baa_series.rolling(window=2520, min_periods=252).mean()
    rolling_std = baa_series.rolling(window=2520, min_periods=252).std()
    baa_zscore = (baa_series - rolling_mean) / rolling_std
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=baa_zscore.index, y=baa_zscore, mode="lines", name="Baa Spread Z-Score", line=dict(color="darkred")))
    fig.add_hrect(y0=-5.0, y1=-2.0, fillcolor="red", opacity=0.1, line_width=0, annotation_text="Exuberance")
    return fig


@st.cache_resource(ttl=DATA_TTL)
def build_issuance_fig(df_issuance: pd.DataFrame):
    return go.Figure(go.Bar(x=df_issuance.index, y=df_issuance["Gross_Equity_Issuance"], marker_color="green"))


@st.cache_resource(ttl=DATA_TTL)
def build_retirements_fig(df_issuance: pd.DataFrame):
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df_issuance.index, y=df_issuance["Equity_Repurchases"], name="Repurchases"))
    fig.add_trace(go.Bar(x=df_issuance.index, y=df_issuance["Equity_Retirements_MA"], name="M&A"))
    fig.update_layout(barmode="stack")
    return fig


@st.cache_resource(ttl=DATA_TTL)
def build_net_issuance_fig(df_issuance: pd.DataFrame):
    return go.Figure(go.Scatter(x=df_issuance.index, y=df_issuance["Net_Equity_Issuance"], line=dict(color="purple")))


@st.cache_resource(ttl=DATA_TTL)
def build_shadow_banking_fig(df_q: pd.DataFrame):
    return go.Figure(go.Scatter(x=df_q.index, y=df_q["Shadow_Bank_Credit"], line=dict(color="teal")))


# --------------------------------------------------------------------------
# Section 1: Macro Asset Monitor
# --------------------------------------------------------------------------
st.header("1. Macro Asset Monitor")
vals = load_valuations()
if vals:
    cols = st.columns(4)
    for i, (ticker, data) in enumerate(vals.items()):
        with cols[i % 4]:
            st.metric(label=f"{data['name']} ({ticker})", value=f"{data['yield']:.2f}%" if data["yield"] else "N/A")

st.markdown("---")

# --------------------------------------------------------------------------
# Section 2: Market & Sector Dynamics
# --------------------------------------------------------------------------
st.header("2. Market & Sector Dynamics")
col1, col2 = st.columns(2)
with col1:
    st.subheader("S&P 500 (SPY) 10-Yr Cyclical Z-Score")
    if "SPY_ZScore" in df_monthly.columns:
        st.plotly_chart(build_spy_zscore_fig(df_monthly), use_container_width=True)
with col2:
    st.subheader("Market Velocity & Acceleration")
    if {"SPY_Velocity_MoM", "SPY_Acceleration"}.issubset(df_monthly.columns):
        st.plotly_chart(build_velocity_fig(df_monthly), use_container_width=True)

# --------------------------------------------------------------------------
# Section 3: Sector Relative Value Explorer
# --------------------------------------------------------------------------
# This section is wrapped in @st.fragment. Previously, picking a different
# sector in the dropdown below triggered a full top-to-bottom script rerun,
# which meant every chart on the page -- sections 1, 2, 4, and 5 included --
# got recomputed even though none of them depend on this dropdown. A
# fragment scopes the rerun to just the function below, so changing sectors
# now only touches this one chart.
#
# Note: caching and fragments can't be combined on the *same* function, so
# this function itself isn't cached -- it just calls the cached builder
# functions above, which is exactly what keeps it cheap.
st.header("3. Sector Relative Value Explorer")


@st.fragment
def render_sector_explorer():
    zscore_cols = [f"{s}_ZScore" for s in SECTORS]
    if not df_monthly.empty and any(c in df_monthly.columns for c in zscore_cols):
        st.plotly_chart(build_sector_bar_fig(df_monthly), use_container_width=True)

    selected_sector = st.selectbox(
        "Select Sector for Historical Deep Dive:",
        SECTORS,
        format_func=lambda x: f"{x} - {SECTOR_MAP[x]}",
    )
    if f"{selected_sector}_ZScore" in df_monthly.columns:
        st.subheader(f"{selected_sector} ({SECTOR_MAP[selected_sector]}) vs SPY: Cyclical Deviation")
        st.plotly_chart(build_sector_deep_dive_fig(df_monthly, selected_sector), use_container_width=True)


render_sector_explorer()

# --------------------------------------------------------------------------
# Section 4: High-Frequency Quantitative Risk
# --------------------------------------------------------------------------
st.header("4. High-Frequency Quantitative Risk")
st.subheader("Total Market Speculative Turnover (SPY + Nasdaq)")
if "Total_Volume_ZScore" in df_monthly.columns:
    st.plotly_chart(build_volume_fig(df_monthly), use_container_width=True)

st.subheader("Moody's Baa Corporate Bond Spread (10-Yr Z-Score)")
if not df_baa.empty and "BAAFF" in df_baa.columns:
    st.plotly_chart(build_baa_fig(df_baa), use_container_width=True)

# --------------------------------------------------------------------------
# Section 5: Quarterly U.S. Equity Issuance & Shadow Banking
# --------------------------------------------------------------------------
st.header("5. Quarterly U.S. Equity Issuance & Shadow Banking")
if not df_quarterly.empty:
    df_q = df_quarterly.dropna(subset=["Shadow_Bank_Credit"], how="all")
    df_issuance = df_q.loc["1996-10-01":]

    st.subheader("Gross Corporate Equity Issuance")
    if "Gross_Equity_Issuance" in df_issuance.columns:
        st.plotly_chart(build_issuance_fig(df_issuance), use_container_width=True)

    st.subheader("Gross Retirements by Category")
    if "Equity_Repurchases" in df_issuance.columns:
        st.plotly_chart(build_retirements_fig(df_issuance), use_container_width=True)

    st.subheader("Net Equity Issuance")
    if "Net_Equity_Issuance" in df_issuance.columns:
        st.plotly_chart(build_net_issuance_fig(df_issuance), use_container_width=True)

    st.subheader("Shadow Banking / Private Credit Share (%)")
    if "Shadow_Bank_Credit" in df_q.columns:
        st.plotly_chart(build_shadow_banking_fig(df_q), use_container_width=True)