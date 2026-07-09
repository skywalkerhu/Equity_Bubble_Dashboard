# This is your frontend visualizer. Run locally using 'streamlit run app.py'

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import json

# --- Page Config ---
st.set_page_config(page_title="Macro Superbubble & Value Explorer", layout="wide")
st.title("Macro Superbubble & Sector Value Explorer")
st.markdown(r"Tracking $\ge 2\sigma$ deviations for market tops and $\le -2\sigma$ capitulations for value entry points.")

# --- Load Data ---
@st.cache_data(ttl=3600)
def load_data():
    if not os.path.exists('data/market_data.csv'):
        st.error("Data file not found. Please run `python data_engine.py` first.")
        return pd.DataFrame()
    df = pd.read_csv('data/market_data.csv', index_col=0, parse_dates=True)
    return df

df = load_data()

if not df.empty:
    # --- Section 1: Macro Bubble Monitor ---
    st.header("1. Macro Asset Monitor")
    
    # Global Valuations Scoreboard
    val_path = 'data/valuations.json'
    
    st.subheader("Global Implied Earnings Yields ($E/P$)")
    st.markdown("If the Earnings Yield is lower than the 10-Yr Treasury Yield, equities offer zero risk premium.")
    
    if os.path.exists(val_path):
        with open(val_path, 'r') as f:
            vals = json.load(f)
            
        cols = st.columns(4)
        for i, (ticker, data) in enumerate(vals.items()):
            with cols[i % 4]:
                if data['yield']:
                    if ticker == 'US3Y':
                        st.metric(
                            label=f"{data['name']}", 
                            value=f"{data['yield']:.2f}%", 
                            delta="Risk-Free Rate", 
                            delta_color="off"
                        )
                    else:
                        st.metric(
                            label=f"{data['name']} ({ticker})", 
                            value=f"{data['yield']:.2f}%", 
                            delta=f"P/E: {data['pe']:.1f}", 
                            delta_color="off"
                        )
                else:
                    st.metric(label=f"{data['name']} ({ticker})", value="Data N/A")
    else:
        st.warning(f"Valuation data not found.")
        
    st.markdown("---")

    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("S&P 500 (SPY) 10-Yr Cyclical Z-Score")
        fig_spy = go.Figure()
        fig_spy.add_trace(go.Scatter(x=df.index, y=df['SPY_ZScore'], mode='lines', name='Z-Score'))
        fig_spy.add_hline(y=2, line_dash="dash", line_color="red", annotation_text="+2 Sigma (Bubble)")
        fig_spy.add_hline(y=-2, line_dash="dash", line_color="green", annotation_text="-2 Sigma (Crash)")
        st.plotly_chart(fig_spy, use_container_width=True)
        
    with col2:
        st.subheader("Market Velocity & Acceleration")
        fig_deriv = go.Figure()
        fig_deriv.add_trace(go.Scatter(x=df.index, y=df['SPY_Velocity_MoM'], mode='lines', name='Velocity (MoM %)', opacity=0.5))
        fig_deriv.add_trace(go.Scatter(x=df.index, y=df['SPY_Acceleration'], mode='lines', name='Acceleration', line=dict(color='orange')))
        st.plotly_chart(fig_deriv, use_container_width=True)

    # --- Section 2: Sector Value Explorer ---
    st.header("2. Sector Relative Value Explorer")
    
    sector_map = {
        'XLK': 'Technology',
        'XLF': 'Financials',
        'XLV': 'Health Care',
        'XLY': 'Consumer Discretionary',
        'XLP': 'Consumer Staples',
        'XLE': 'Energy',
        'XLI': 'Industrials',
        'XLU': 'Utilities',
        'XLB': 'Materials',
        'IYR': 'Real Estate',
        'IYZ': 'Telecommunications'
    }
    
    # FIX: Explicitly match the list to the keys we defined in the sector_map
    sectors = list(sector_map.keys())
    zscore_cols = [f"{s}_ZScore" for s in sectors]
    
    # Filter only columns that actually exist in the dataframe to prevent KeyError
    available_cols = [col for col in zscore_cols if col in df.columns]
    
    latest_data = df[available_cols].iloc[-1].dropna()
    
    # Clean names
    latest_data.index = [f"{idx.split('_')[0]} - {sector_map[idx.split('_')[0]]}" for idx in latest_data.index] 
    
    fig_bar = px.bar(
        x=latest_data.index, 
        y=latest_data.values, 
        labels={'x': 'Sector', 'y': 'Current 10-Yr Z-Score'},
        color=latest_data.values,
        color_continuous_scale='RdYlGn_r'
    )
    fig_bar.add_hline(y=2, line_dash="dash", line_color="red")
    fig_bar.add_hline(y=-2, line_dash="dash", line_color="green")
    st.plotly_chart(fig_bar, use_container_width=True)

    selected_sector = st.selectbox(
        "Select Sector for Historical Deep Dive:", 
        sectors, 
        format_func=lambda x: f"{x} - {sector_map[x]}"
    )
    
    st.subheader(f"{selected_sector} ({sector_map[selected_sector]}) vs SPY: Cyclical Deviation")
    fig_sector = go.Figure()
    fig_sector.add_trace(go.Scatter(x=df.index, y=df[f'{selected_sector}_ZScore'], mode='lines', name=f'{selected_sector} Z-Score'))
    fig_sector.add_hline(y=2, line_dash="dash", line_color="red")
    fig_sector.add_hline(y=-2, line_dash="dash", line_color="green")
    st.plotly_chart(fig_sector, use_container_width=True)