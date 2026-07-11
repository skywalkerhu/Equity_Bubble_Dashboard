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
page = st.sidebar.radio("Select View:", ["Market & Sector Dynamics", "Quarterly U.S. Equity Issuance & Shadow Banking Financing Data"])

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

@st.cache_data(ttl=3600)
def load_baa_spread_data():
    if not os.path.exists('data/baa_spread.csv'):
        return pd.DataFrame()
    return pd.read_csv('data/baa_spread.csv', index_col=0, parse_dates=True)

df_monthly = load_market_data()
df_quarterly = load_quarterly_data()
df_baa = load_baa_spread_data()

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
        st.header("3. U.S. Equity Issuance & Investment Grade Yield Spread Over Treasury")
        
        st.subheader("Total Market Speculative Turnover (SPY + Nasdaq)")
        if 'Total_Volume_ZScore' in df_monthly.columns:
            fig_vol = make_subplots(specs=[[{"secondary_y": True}]])
            fig_vol.add_trace(go.Bar(x=df_monthly.index, y=df_monthly['Total_Volume_ZScore'], name="Volume Z-Score", marker_color='rgba(135, 206, 250, 0.6)'), secondary_y=False)
            fig_vol.add_trace(go.Scatter(x=df_monthly.index, y=df_monthly['SPY'], name="S&P 500 Price", mode='lines', line=dict(color='black')), secondary_y=True)
            fig_vol.add_hline(y=2, line_dash="dash", line_color="red", secondary_y=False)
            fig_vol.update_layout(height=400, margin=dict(l=0, r=0, t=30, b=0))
            st.plotly_chart(fig_vol, use_container_width=True)
            
        st.markdown("---")
        
        st.subheader("Moody's Baa Corporate Bond Spread (10-Yr Z-Score)")
        fig_baa = go.Figure()
        if not df_baa.empty and 'BAAFF' in df_baa.columns:
            baa_series = df_baa['BAAFF'].dropna()
            
            # Dynamically calculate a 10-year (approx 2520 trading days) rolling Z-Score for the Daily Baa Spread
            rolling_mean = baa_series.rolling(window=2520, min_periods=252).mean()
            rolling_std = baa_series.rolling(window=2520, min_periods=252).std()
            baa_zscore = (baa_series - rolling_mean) / rolling_std
            
            fig_baa.add_trace(go.Scatter(x=baa_zscore.index, y=baa_zscore, mode='lines', name='Baa Spread Z-Score', line=dict(color='darkred')))
            fig_baa.add_hline(y=0, line_dash="dash", line_color="gray", annotation_text="Historical Mean (0)")
            fig_baa.add_hline(y=2, line_dash="dash", line_color="red", annotation_text="+2σ (Credit Stress)")
            fig_baa.add_hline(y=-2, line_dash="dash", line_color="green", annotation_text="-2σ (Tight Credit)")
            
            # Highlight negative z-scores as tight spreads / exuberance
            fig_baa.add_hrect(y0=-5.0, y1=-2.0, fillcolor="red", opacity=0.1, line_width=0, annotation_text="Peak Exuberance Zone")
            st.plotly_chart(fig_baa, use_container_width=True)
    else:
        st.error("Market data file not found. Please run the data engine.")


# ==========================================
# PAGE 2: QUARTERLY MACRO RISK & LIQUIDITY
# ==========================================
elif page == "Quarterly U.S. Equity Issuance & Shadow Banking Financing Data":
    st.title("Quarterly U.S. Equity Issuance & Shadow Banking Financing Data")
    st.markdown("Analyzing market regime risk via structural issuance supply and shadow credit market conditions on a quarterly basis.")
    
    if not df_quarterly.empty:
        df_q = df_quarterly.dropna(subset=['Net_Equity_Issuance', 'Shadow_Bank_Credit'], how='all')
        
        # Create a specific dataframe for the issuance charts to drop pre-1996 NaNs cleanly
        issuance_cols = ['Net_Equity_Issuance', 'Gross_Equity_Issuance', 'Equity_Repurchases', 'Equity_Retirements_MA']
        available_issuance_cols = [col for col in issuance_cols if col in df_q.columns]
        df_issuance = df_q.dropna(subset=available_issuance_cols, how='all')
        
        st.subheader("1. Gross Corporate Equity Issuance")
        st.markdown("*Nominal total of new equity issued to the public markets.*")
        fig_gross = go.Figure()
        if 'Gross_Equity_Issuance' in df_issuance.columns:
            fig_gross.add_trace(go.Bar(x=df_issuance.index, y=df_issuance['Gross_Equity_Issuance'], name='Gross Issuance', marker_color='rgba(46, 139, 87, 0.8)'))
        fig_gross.update_layout(height=350, margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig_gross, use_container_width=True)
        
        st.subheader("2. Gross Retirements by Category")
        st.markdown("*Breakdown of equity removed from the market via Share Repurchases vs. M&A.*")
        fig_retire = go.Figure()
        if 'Equity_Repurchases' in df_issuance.columns and 'Equity_Retirements_MA' in df_issuance.columns:
            fig_retire.add_trace(go.Bar(x=df_issuance.index, y=df_issuance['Equity_Repurchases'], name='Share Repurchases', marker_color='rgba(220, 20, 60, 0.8)'))
            fig_retire.add_trace(go.Bar(x=df_issuance.index, y=df_issuance['Equity_Retirements_MA'], name='M&A Retirements', marker_color='rgba(255, 140, 0, 0.8)'))
        fig_retire.update_layout(barmode='stack', height=350, margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig_retire, use_container_width=True)
        
        st.subheader("3. Net Equity Issuance")
        st.markdown("*Gross Issuance minus Total Retirements. Positive values indicate net equity dilution.*")
        fig_net = go.Figure()
        if 'Net_Equity_Issuance' in df_issuance.columns:
            fig_net.add_trace(go.Scatter(x=df_issuance.index, y=df_issuance['Net_Equity_Issuance'], mode='lines+markers', name='Net Issuance (Nominal)', line=dict(color='purple', width=3)))
        fig_net.add_hline(y=0, line_dash="solid", line_color="gray")
        fig_net.update_layout(height=350, margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig_net, use_container_width=True)
        
        st.subheader("Shadow Banking / Private Credit Share (%)")
        st.markdown("*Non-Bank Credit as a Percentage of Total Non-Financial Credit (BIS Data, Quarterly).*")
        fig_shadow = go.Figure()
        df_shadow = df_q.dropna(subset=['Shadow_Bank_Credit'])
        fig_shadow.add_trace(go.Scatter(x=df_shadow.index, y=df_shadow['Shadow_Bank_Credit'], mode='lines+markers', name='Shadow Credit %', line=dict(color='teal')))
        st.plotly_chart(fig_shadow, use_container_width=True)
        
    else:
        st.error("Quarterly macroeconomic data not found. Please run the data engine.")