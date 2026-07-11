import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import json

st.set_page_config(page_title="Macro Superbubble Explorer", layout="wide")

# --- Sidebar Navigation ---
st.sidebar.title("Dashboard Navigation")
page = st.sidebar.radio("Select View:", ["Market & Sector Dynamics", "Quarterly Macro Risk & Liquidity"])

# --- Load Data ---
@st.cache_data(ttl=3600)
def load_market_data():
    if not os.path.exists('data/market_data.csv'):
        return pd.DataFrame()
    return pd.read_csv('data/market_data.csv', index_col=0, parse_dates=True)

@st.cache_data(ttl=3600)
def load_quarterly_data():
    if not os.path.exists('data/quarterly_data.csv'):
        return pd.DataFrame()
    return pd.read_csv('data/quarterly_data.csv', index_col=0, parse_dates=True)

df_monthly = load_market_data()
df_quarterly = load_quarterly_data()

# ==========================================
# PAGE 1: MONTHLY MARKET & SECTOR DYNAMICS
# ==========================================
if page == "Market & Sector Dynamics":
    st.title("Market & Sector Dynamics")
    st.markdown(r"Tracking $\ge 2\sigma$ deviations for market tops and $\le -2\sigma$ capitulations for value entry points.")
    
    if not df_monthly.empty:
        # --- Section 1: Macro Bubble Monitor ---
        st.header("1. Macro Asset Monitor")
        val_path = 'data/valuations.json'
        
        if os.path.exists(val_path):
            with open(val_path, 'r') as f:
                vals = json.load(f)
                cols = st.columns(4)
                for i, (ticker, data) in enumerate(vals.items()):
                    with cols[i % 4]:
                        st.metric(label=f"{data['name']} ({ticker})", value=f"{data['yield']:.2f}%" if data['yield'] else "N/A")
        
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("S&P 500 (SPY) 10-Yr Cyclical Z-Score")
            fig_spy = go.Figure()
            fig_spy.add_trace(go.Scatter(x=df_monthly.index, y=df_monthly['SPY_ZScore'], mode='lines', name='Z-Score'))
            fig_spy.add_hline(y=2, line_dash="dash", line_color="red")
            fig_spy.add_hline(y=-2, line_dash="dash", line_color="green")
            fig_spy.update_xaxes(rangeslider_visible=True)
            st.plotly_chart(fig_spy, use_container_width=True)
        with col2:
            st.subheader("Market Velocity & Acceleration")
            fig_deriv = go.Figure()
            fig_deriv.add_trace(go.Scatter(x=df_monthly.index, y=df_monthly['SPY_Velocity_MoM'], mode='lines', name='Velocity (MoM %)'))
            fig_deriv.add_trace(go.Scatter(x=df_monthly.index, y=df_monthly['SPY_Acceleration'], mode='lines', name='Acceleration'))
            st.plotly_chart(fig_deriv, use_container_width=True)

        # --- Section 2: Sector Value Explorer ---
        st.header("2. Sector Relative Value Explorer")
        sector_map = {
            'XLK': 'Technology', 'XLF': 'Financials', 'XLV': 'Health Care',
            'XLY': 'Consumer Discretionary', 'XLP': 'Consumer Staples', 'XLE': 'Energy',
            'XLI': 'Industrials', 'XLU': 'Utilities', 'XLB': 'Materials',
            'IYR': 'Real Estate', 'IYZ': 'Telecommunications'
        }
        
        sectors = list(sector_map.keys())
        zscore_cols = [f"{s}_ZScore" for s in sectors]
        available_cols = [col for col in zscore_cols if col in df_monthly.columns]
        
        latest_data = df_monthly[available_cols].iloc[-1].dropna()
        latest_data.index = [f"{idx.split('_')[0]} - {sector_map[idx.split('_')[0]]}" for idx in latest_data.index] 
        
        fig_bar = px.bar(x=latest_data.index, y=latest_data.values, color=latest_data.values, color_continuous_scale='RdYlGn_r')
        fig_bar.add_hline(y=2, line_dash="dash", line_color="red")
        fig_bar.add_hline(y=-2, line_dash="dash", line_color="green")
        st.plotly_chart(fig_bar, use_container_width=True)

        selected_sector = st.selectbox("Select Sector for Historical Deep Dive:", sectors, format_func=lambda x: f"{x} - {sector_map[x]}")
        
        df_filtered = df_monthly.loc['1999-01-01':]
        
        st.subheader(f"{selected_sector} ({sector_map[selected_sector]}) vs SPY: Cyclical Deviation")
        fig_sector = go.Figure()
        fig_sector.add_trace(go.Scatter(x=df_filtered.index, y=df_filtered[f'{selected_sector}_ZScore'], mode='lines'))
        fig_sector.add_hline(y=2, line_dash="dash", line_color="red")
        fig_sector.add_hline(y=-2, line_dash="dash", line_color="green")
        st.plotly_chart(fig_sector, use_container_width=True)

        # --- Section 3: High-Frequency Quantity Data ---
        st.header("3. High-Frequency Market Sentiment")
        
        col3, col4 = st.columns(2)
        with col3:
            st.subheader("Total Market Speculative Turnover (SPY + Nasdaq)")
            if 'Total_Volume_ZScore' in df_monthly.columns:
                fig_vol = make_subplots(specs=[[{"secondary_y": True}]])
                fig_vol.add_trace(go.Bar(x=df_monthly.index, y=df_monthly['Total_Volume_ZScore'], name="Volume Z-Score", marker_color='rgba(135, 206, 250, 0.6)'), secondary_y=False)
                fig_vol.add_trace(go.Scatter(x=df_monthly.index, y=df_monthly['SPY'], name="S&P 500 Price", mode='lines', line=dict(color='black')), secondary_y=True)
                fig_vol.add_hline(y=2, line_dash="dash", line_color="red", secondary_y=False)
                fig_vol.update_layout(height=400, margin=dict(l=0, r=0, t=30, b=0))
                st.plotly_chart(fig_vol, use_container_width=True)
        
        with col4:
            st.subheader("ICE BofA US High Yield Spread")
            fig_hy = go.Figure()
            if 'HY_Spread' in df_monthly.columns:
                hy_df = df_monthly['HY_Spread'].dropna()
                fig_hy.add_trace(go.Scatter(x=hy_df.index, y=hy_df, mode='lines', name='HY Spread %', line=dict(color='darkred')))
                fig_hy.add_hline(y=hy_df.mean(), line_dash="dash", line_color="blue", annotation_text="Historical Mean")
                fig_hy.add_hrect(y0=0, y1=4.0, fillcolor="red", opacity=0.1, line_width=0, annotation_text="Peak Exuberance Zone")
                st.plotly_chart(fig_hy, use_container_width=True)
    else:
        st.error("Market data file not found. Please run the data engine.")


# ==========================================
# PAGE 2: QUARTERLY MACRO RISK & LIQUIDITY
# ==========================================
elif page == "Quarterly Macro Risk & Liquidity":
    st.title("Macro Risk & Liquidity (IMF Quantity Pillars)")
    st.markdown("Analyzing market regime risk via structural issuance supply and shadow credit market conditions on a quarterly basis.")
    
    if not df_quarterly.empty:
        # Drop strict NaNs to ensure clean line drawing for quarterly data
        df_q = df_quarterly.dropna(subset=['Net_Equity_Issuance_Yield', 'Shadow_Bank_Credit'], how='all')
        
        st.subheader("Net Equity Issuance Yield")
        st.markdown("*Positive spikes indicate major public share dilution/IPOs vastly outpacing share buybacks.*")
        fig_issuance = go.Figure()
        fig_issuance.add_trace(go.Scatter(x=df_q.index, y=df_q['Net_Equity_Issuance_Yield'], mode='lines+markers', name='Issuance Yield %', line=dict(color='purple')))
        fig_issuance.add_hline(y=0, line_dash="solid", line_color="gray")
        st.plotly_chart(fig_issuance, use_container_width=True)
        
        st.subheader("Shadow Banking / Private Credit Proxy")
        st.markdown("*Total Non-Financial Credit minus Domestic Bank Credit (BIS Data, Quarterly).*")
        fig_shadow = go.Figure()
        # Filter where shadow credit actually has data to plot cleanly
        df_shadow = df_q.dropna(subset=['Shadow_Bank_Credit'])
        fig_shadow.add_trace(go.Scatter(x=df_shadow.index, y=df_shadow['Shadow_Bank_Credit'], mode='lines+markers', name='Shadow Credit', line=dict(color='teal')))
        st.plotly_chart(fig_shadow, use_container_width=True)
        
    else:
        st.error("Quarterly macroeconomic data not found. Please run the data engine.")