import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import json

st.set_page_config(page_title="Macro Superbubble & Value Explorer", layout="wide")
st.title("Macro Superbubble & Sector Value Explorer")

@st.cache_data(ttl=3600)
def load_data():
    if not os.path.exists('data/market_data.csv'):
        return pd.DataFrame()
    return pd.read_csv('data/market_data.csv', index_col=0, parse_dates=True)

df = load_data()

if not df.empty:
    # Section 1: Macro Bubble Monitor
    st.header("1. Macro Asset Monitor")
    if os.path.exists('data/valuations.json'):
        with open('data/valuations.json', 'r') as f:
            vals = json.load(f)
            cols = st.columns(4)
            for i, (ticker, data) in enumerate(vals.items()):
                with cols[i % 4]:
                    st.metric(label=f"{data['name']} ({ticker})", value=f"{data['yield']:.2f}%" if data['yield'] else "N/A")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("S&P 500 (SPY) 10-Yr Cyclical Z-Score")
        fig_spy = go.Figure()
        fig_spy.add_trace(go.Scatter(x=df.index, y=df['SPY_ZScore'], mode='lines'))
        fig_spy.update_xaxes(rangeslider_visible=True)
        st.plotly_chart(fig_spy, use_container_width=True)
    with col2:
        st.subheader("Market Velocity & Acceleration")
        fig_deriv = go.Figure()
        fig_deriv.add_trace(go.Scatter(x=df.index, y=df['SPY_Velocity_MoM'], mode='lines', name='Velocity'))
        fig_deriv.add_trace(go.Scatter(x=df.index, y=df['SPY_Acceleration'], mode='lines', name='Acceleration'))
        st.plotly_chart(fig_deriv, use_container_width=True)

    # Section 2: Sector Value Explorer
    st.header("2. Sector Relative Value Explorer")
    sector_map = {
        'XLK': 'Technology', 'XLF': 'Financials', 'XLV': 'Health Care',
        'XLY': 'Consumer Discretionary', 'XLP': 'Consumer Staples', 'XLE': 'Energy',
        'XLI': 'Industrials', 'XLU': 'Utilities', 'XLB': 'Materials',
        'IYR': 'Real Estate', 'IYZ': 'Telecommunications'
    }
    
    sectors = list(sector_map.keys())
    zscore_cols = [f"{s}_ZScore" for s in sectors]
    available_cols = [col for col in zscore_cols if col in df.columns]
    
    latest_data = df[available_cols].iloc[-1].dropna()
    latest_data.index = [f"{idx.split('_')[0]} - {sector_map[idx.split('_')[0]]}" for idx in latest_data.index]
    
    fig_bar = px.bar(x=latest_data.index, y=latest_data.values, color=latest_data.values, color_continuous_scale='RdYlGn_r')
    fig_bar.add_hline(y=2, line_dash="dash", line_color="red")
    fig_bar.add_hline(y=-2, line_dash="dash", line_color="green")
    st.plotly_chart(fig_bar, use_container_width=True)

    # Section 3: Sector Deep Dive (Dual Charts)
    st.header("3. Sector Deep Dive")
    selected_sector = st.selectbox("Select Sector:", sectors, format_func=lambda x: f"{x} - {sector_map[x]}")
    df_filtered = df.loc['1999-01-01':]
    
    colA= st.columns(1)
    with colA:
        st.subheader("Relative Value (vs SPY)")

        fig_rel = go.Figure()
        fig_rel.add_trace(
            go.Scatter(
                x=df_filtered.index,
                y=df_filtered[f"{selected_sector}_ZScore"],
                mode="lines"
            )
        )

        fig_rel.add_hline(y=2, line_dash="dash", line_color="red")
        fig_rel.add_hline(y=-2, line_dash="dash", line_color="green")

        st.plotly_chart(fig_rel, use_container_width=True)
        
else:
    st.error("Data missing.")