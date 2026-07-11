import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import json

st.set_page_config(page_title="Macro Superbubble Explorer", layout="wide")

# --- Load Data ---
@st.cache_data(ttl=3600)
def load_market_data():
    if not os.path.exists('data/market_data.csv'): return pd.DataFrame()
    return pd.read_csv('data/market_data.csv', index_col=0, parse_dates=True)

@st.cache_data(ttl=3600)
def load_quarterly_data():
    if not os.path.exists('data/quarterly_data.csv'): return pd.DataFrame()
    return pd.read_csv('data/quarterly_data.csv', index_col=0, parse_dates=True)

@st.cache_data(ttl=3600)
def load_baa_spread_data():
    if not os.path.exists('data/baa_spread.csv'): return pd.DataFrame()
    return pd.read_csv('data/baa_spread.csv', index_col=0, parse_dates=True)

df_monthly = load_market_data()
df_quarterly = load_quarterly_data()
df_baa = load_baa_spread_data()

# --- Sidebar ---
st.sidebar.title("Dashboard Navigation")
page = st.sidebar.radio("Select View:", ["Market & Sector Dynamics", "Quarterly U.S. Equity Issuance & Shadow Banking Financing Data"])

# ==========================================
# PAGE 1: MARKET & SECTOR DYNAMICS
# ==========================================
if page == "Market & Sector Dynamics":
    st.title("Market & Sector Dynamics")
    
    if not df_monthly.empty:
        # Macro Monitor
        st.header("Macro Asset Monitor")
        val_path = 'data/valuations.json'
        if os.path.exists(val_path):
            with open(val_path, 'r') as f:
                vals = json.load(f)
                cols = st.columns(4)
                for i, (ticker, data) in enumerate(vals.items()):
                    with cols[i % 4]: st.metric(label=f"{data['name']} ({ticker})", value=f"{data['yield']:.2f}%" if data['yield'] else "N/A")
        
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("SPY 10-Yr Cyclical Z-Score")
            fig_spy = go.Figure()
            fig_spy.add_trace(go.Scatter(x=df_monthly.index, y=df_monthly['SPY_ZScore'], mode='lines', name='Z-Score'))
            fig_spy.update_xaxes(rangeslider_visible=True)
            st.plotly_chart(fig_spy, use_container_width=True)
        with col2:
            st.subheader("Baa Corporate Bond Spread Z-Score")
            if not df_baa.empty and 'BAAFF' in df_baa.columns:
                baa = df_baa['BAAFF'].dropna()
                z = (baa - baa.rolling(2520).mean()) / baa.rolling(2520).std()
                fig_baa = go.Figure()
                fig_baa.add_trace(go.Scatter(x=z.index, y=z, mode='lines', line=dict(color='darkred')))
                fig_baa.add_hrect(y0=-5, y1=-2, fillcolor="red", opacity=0.1)
                st.plotly_chart(fig_baa, use_container_width=True)

# ==========================================
# PAGE 2: QUARTERLY DATA
# ==========================================
elif page == "Quarterly U.S. Equity Issuance & Shadow Banking Financing Data":
    st.title("Quarterly U.S. Equity Issuance & Shadow Banking Financing Data")
    
    if not df_quarterly.empty:
        # Section 1: Equity Issuance (If columns exist)
        if 'Gross_Equity_Issuance' in df_quarterly.columns:
            st.subheader("1. Gross Corporate Equity Issuance")
            fig = go.Figure(go.Bar(x=df_quarterly.index, y=df_quarterly['Gross_Equity_Issuance'], marker_color='green'))
            st.plotly_chart(fig, use_container_width=True)
        
        if 'Equity_Repurchases' in df_quarterly.columns:
            st.subheader("2. Gross Retirements by Category")
            fig = go.Figure()
            fig.add_trace(go.Bar(x=df_quarterly.index, y=df_quarterly['Equity_Repurchases'], name='Repurchases'))
            fig.add_trace(go.Bar(x=df_quarterly.index, y=df_quarterly['Equity_Retirements_MA'], name='M&A'))
            fig.update_layout(barmode='stack')
            st.plotly_chart(fig, use_container_width=True)
            
        if 'Net_Equity_Issuance' in df_quarterly.columns:
            st.subheader("3. Net Equity Issuance")
            fig = go.Figure(go.Scatter(x=df_quarterly.index, y=df_quarterly['Net_Equity_Issuance'], line=dict(color='purple', width=3)))
            st.plotly_chart(fig, use_container_width=True)
        
        # Section 2: Shadow Banking
        if 'Shadow_Bank_Credit' in df_quarterly.columns:
            st.subheader("Shadow Banking / Private Credit Share (%)")
            fig = go.Figure(go.Scatter(x=df_quarterly.index, y=df_quarterly['Shadow_Bank_Credit'], line=dict(color='teal')))
            st.plotly_chart(fig, use_container_width=True)