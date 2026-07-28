import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import json

st.set_page_config(page_title="Equity Markets Bubble Explorer", layout="wide")

st.title("Equity Markets Bubble Explorer & Systemic Risk Explorer")
st.markdown(r"Tracking $\ge 2\sigma$ deviations for market tops, cyclical asset bubbles, and structural liquidity flows.")

if os.path.exists('data/meta.json'):
    with open('data/meta.json', 'r') as f:
        _ts = json.load(f)['generated_at']
    st.caption(f"Data last updated: {_ts.replace('T', ' ')[:16]} UTC")

# Moving heavy calculations into the cache prevents Out-Of-Memory (OOM) crashes on reload.
@st.cache_data(ttl=3600)
def load_market_data():
    if not os.path.exists('data/market_data.csv'):
        return pd.DataFrame()
    df = pd.read_csv('data/market_data.csv', index_col=0, parse_dates=True)
    return df.dropna(how='all')

@st.cache_data(ttl=3600)
def load_quarterly_data():
    if not os.path.exists('data/quarterly_data.csv'):
        return pd.DataFrame()
    df = pd.read_csv('data/quarterly_data.csv', index_col=0, parse_dates=True)
    # Drop completely empty rows to save RAM
    return df.dropna(how='all')

@st.cache_data(ttl=3600)
def load_baa_spread_data():
    if not os.path.exists('data/baa_spread.csv'):
        return pd.DataFrame()
    df = pd.read_csv('data/baa_spread.csv', index_col=0, parse_dates=True)
    if not df.empty and 'BAAFF' in df.columns:
        # Pre-calculate the heavy rolling Z-Score ONCE in the cache, not on the UI thread
        df['rolling_mean'] = df['BAAFF'].rolling(window=2520, min_periods=252).mean()
        df['rolling_std'] = df['BAAFF'].rolling(window=2520, min_periods=252).std()
        df['BAA_ZScore'] = (df['BAAFF'] - df['rolling_mean']) / df['rolling_std']
        # Smooth before differentiating. Raw day-over-day changes in this series are
        # dominated by noise, and the 2nd derivative amplifies that noise further.
        smoothed = df['BAAFF'].rolling(window=21, min_periods=10).mean()
        df['BAA_Velocity'] = smoothed.diff(21) * 100          # bps change per month
        df['BAA_Acceleration'] = df['BAA_Velocity'].diff(21)  # bps/month, per month
        return df[['BAAFF', 'BAA_ZScore', 'BAA_Velocity', 'BAA_Acceleration']].dropna()
    return df

df_monthly = load_market_data()
df_quarterly = load_quarterly_data()
df_baa = load_baa_spread_data()

if not df_monthly.empty:
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
        # Removed range slider to save massive amounts of JS rendering memory
        fig_spy.update_layout(height=350, margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig_spy, use_container_width=True)
        
    with col2:
        st.subheader("Market Velocity & Acceleration")
        fig_deriv = go.Figure()
        fig_deriv.add_trace(go.Scatter(x=df_monthly.index, y=df_monthly['SPY_Velocity_MoM'], mode='lines', name='Velocity (MoM %)'))
        fig_deriv.add_trace(go.Scatter(x=df_monthly.index, y=df_monthly['SPY_Acceleration'], mode='lines', name='Acceleration'))
        fig_deriv.update_layout(height=350, margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig_deriv, use_container_width=True)

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
    
    if available_cols:
        latest_data = df_monthly[available_cols].iloc[-1].dropna()
        latest_data.index = [f"{idx.split('_')[0]} - {sector_map[idx.split('_')[0]]}" for idx in latest_data.index] 
        
        fig_bar = px.bar(x=latest_data.index, y=latest_data.values, color=latest_data.values, color_continuous_scale='RdYlGn_r')
        fig_bar.add_hline(y=2, line_dash="dash", line_color="red")
        fig_bar.add_hline(y=-2, line_dash="dash", line_color="green")
        fig_bar.update_layout(height=350, margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig_bar, use_container_width=True)

        selected_sector = st.selectbox("Select Sector for Historical Deep Dive:", sectors, format_func=lambda x: f"{x} - {sector_map[x]}")
        df_filtered = df_monthly.loc['1999-01-01':]
        
        st.subheader(f"{selected_sector} ({sector_map[selected_sector]}) vs SPY: Cyclical Deviation")
        fig_sector = go.Figure()
        fig_sector.add_trace(go.Scatter(x=df_filtered.index, y=df_filtered[f'{selected_sector}_ZScore'], mode='lines'))
        fig_sector.add_hline(y=2, line_dash="dash", line_color="red")
        fig_sector.add_hline(y=-2, line_dash="dash", line_color="green")
        fig_sector.update_layout(height=350, margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig_sector, use_container_width=True)

    st.header("3. Credit Stress")
    
    st.subheader("Moody's Baa Corporate Bond Spread (10-Yr Z-Score)")
    if not df_baa.empty and 'BAA_ZScore' in df_baa.columns:
        fig_baa = go.Figure()
        fig_baa.add_trace(go.Scatter(x=df_baa.index, y=df_baa['BAA_ZScore'], mode='lines', name='Baa Spread Z-Score', line=dict(color='darkred')))
        fig_baa.add_hline(y=0, line_dash="dash", line_color="gray", annotation_text="Historical Mean (0)")
        fig_baa.add_hline(y=2, line_dash="dash", line_color="red", annotation_text="+2σ (Credit Stress)")
        fig_baa.add_hline(y=-2, line_dash="dash", line_color="green", annotation_text="-2σ (Tight Credit)")
        fig_baa.add_hrect(y0=-5.0, y1=-2.0, fillcolor="red", opacity=0.1, line_width=0, annotation_text="Peak Exuberance Zone")
        fig_baa.update_layout(height=350, margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig_baa, use_container_width=True)

        if 'BAA_Velocity' in df_baa.columns and 'BAA_Acceleration' in df_baa.columns:
            baa_col1, baa_col2 = st.columns(2)

            with baa_col1:
                st.markdown("**1st Derivative — Velocity**")
                st.markdown("*Rate of change in the spread, bps per month. Positive = widening.*")
                fig_baa_v = go.Figure()
                fig_baa_v.add_trace(go.Scatter(x=df_baa.index, y=df_baa['BAA_Velocity'], mode='lines', name='Velocity', line=dict(color='crimson', width=1)))
                fig_baa_v.add_hline(y=0, line_dash="solid", line_color="gray")
                fig_baa_v.update_layout(height=300, margin=dict(l=0, r=0, t=30, b=0), yaxis_title="bps / month")
                st.plotly_chart(fig_baa_v, use_container_width=True)

            with baa_col2:
                st.markdown("**2nd Derivative — Acceleration**")
                st.markdown("*Change in velocity. Sign flips mark inflection points in credit stress.*")
                fig_baa_a = go.Figure()
                fig_baa_a.add_trace(go.Scatter(x=df_baa.index, y=df_baa['BAA_Acceleration'], mode='lines', name='Acceleration', line=dict(color='darkorange', width=1)))
                fig_baa_a.add_hline(y=0, line_dash="solid", line_color="gray")
                fig_baa_a.update_layout(height=300, margin=dict(l=0, r=0, t=30, b=0), yaxis_title="bps / month²")
                st.plotly_chart(fig_baa_a, use_container_width=True)

else:
    st.warning("Monthly market data not found. Please run the data engine.")

st.markdown("---")
st.header("4. Quarterly U.S. Equity Issuance & Shadow Banking Financing Data")

if not df_quarterly.empty:
    # Safely subset the DataFrame depending on what columns exist to prevent crashes
    issuance_cols = ['Net_Equity_Issuance', 'Gross_Equity_Issuance', 'Equity_Repurchases', 'Equity_Retirements_MA']
    available_issuance_cols = [col for col in issuance_cols if col in df_quarterly.columns]
    
    if available_issuance_cols:
        # Snap data precisely to October 1996 to cut out historical NaNs taking up memory
        df_issuance = df_quarterly.loc['1996-10-01':].dropna(subset=available_issuance_cols, how='all')
        
        st.subheader("Gross Corporate Equity Issuance")
        st.markdown("*Nominal total of new equity issued to the public markets.*")
        if 'Gross_Equity_Issuance' in df_issuance.columns:
            fig_gross = go.Figure(go.Bar(x=df_issuance.index, y=df_issuance['Gross_Equity_Issuance'], name='Gross Issuance', marker_color='rgba(46, 139, 87, 0.8)'))
            fig_gross.update_layout(height=300, margin=dict(l=0, r=0, t=30, b=0))
            st.plotly_chart(fig_gross, use_container_width=True)
            
        st.subheader("Gross Retirements by Category")
        st.markdown("*Breakdown of equity removed from the market via Share Repurchases vs. M&A.*")
        if 'Equity_Repurchases' in df_issuance.columns and 'Equity_Retirements_MA' in df_issuance.columns:
            fig_retire = go.Figure()
            fig_retire.add_trace(go.Bar(x=df_issuance.index, y=df_issuance['Equity_Repurchases'], name='Share Repurchases', marker_color='rgba(220, 20, 60, 0.8)'))
            fig_retire.add_trace(go.Bar(x=df_issuance.index, y=df_issuance['Equity_Retirements_MA'], name='M&A Retirements', marker_color='rgba(255, 140, 0, 0.8)'))
            fig_retire.update_layout(barmode='stack', height=300, margin=dict(l=0, r=0, t=30, b=0))
            st.plotly_chart(fig_retire, use_container_width=True)
            
        st.subheader("Net Equity Issuance")
        st.markdown("*Gross Issuance minus Total Retirements. Positive values indicate net equity dilution.*")
        if 'Net_Equity_Issuance' in df_issuance.columns:
            fig_net = go.Figure(go.Scatter(x=df_issuance.index, y=df_issuance['Net_Equity_Issuance'], mode='lines+markers', name='Net Issuance', line=dict(color='purple', width=3)))
            fig_net.add_hline(y=0, line_dash="solid", line_color="gray")
            fig_net.update_layout(height=300, margin=dict(l=0, r=0, t=30, b=0))
            st.plotly_chart(fig_net, use_container_width=True)

    st.subheader("Shadow Banking / Private Credit Share (%)")
    st.markdown("*Non-Bank Credit as a Percentage of Total Non-Financial Credit (BIS Data, Quarterly).*")
    if 'Shadow_Bank_Credit' in df_quarterly.columns:
        df_shadow = df_quarterly.dropna(subset=['Shadow_Bank_Credit'])
        fig_shadow = go.Figure(go.Scatter(x=df_shadow.index, y=df_shadow['Shadow_Bank_Credit'], mode='lines+markers', name='Shadow Credit %', line=dict(color='teal')))
        fig_shadow.update_layout(height=300, margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig_shadow, use_container_width=True)
        
else:
    st.warning("Quarterly macroeconomic data not found. Please run the data engine.")