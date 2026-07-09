import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os

st.set_page_config(page_title="Macro Superbubble & Value Explorer", layout="wide")
st.title("Macro Superbubble & Sector Value Explorer")

@st.cache_data(ttl=3600)
def load_data():
    if not os.path.exists('data/market_data.csv'):
        return pd.DataFrame()
    return pd.read_csv('data/market_data.csv', index_col=0, parse_dates=True)

df = load_data()

if not df.empty:
    st.header("2. Sector Relative Value & Absolute Momentum")
    sector_map = {
        'XLK': 'Technology', 'XLF': 'Financials', 'XLV': 'Health Care',
        'XLY': 'Consumer Discretionary', 'XLP': 'Consumer Staples', 'XLE': 'Energy',
        'XLI': 'Industrials', 'XLU': 'Utilities', 'XLB': 'Materials',
        'IYR': 'Real Estate', 'IYZ': 'Telecommunications'
    }
    
    selected_sector = st.selectbox("Select Sector:", list(sector_map.keys()), format_func=lambda x: f"{x} - {sector_map[x]}")
    
    df_filtered = df.loc['1999-01-01':]
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader(f"{selected_sector} vs SPY (Relative Value)")
        fig1 = go.Figure()
        fig1.add_trace(go.Scatter(x=df_filtered.index, y=df_filtered[f'{selected_sector}_ZScore'], mode='lines', name='Rel Z-Score'))
        fig1.add_hline(y=2, line_dash="dash", line_color="red")
        fig1.add_hline(y=-2, line_dash="dash", line_color="green")
        st.plotly_chart(fig1, use_container_width=True)
        
    with col2:
        st.subheader(f"{selected_sector} Absolute Price (Momentum)")
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=df_filtered.index, y=df_filtered[f'{selected_sector}_Abs_ZScore'], mode='lines', name='Abs Z-Score', line=dict(color='orange')))
        fig2.add_hline(y=2, line_dash="dash", line_color="red")
        fig2.add_hline(y=-2, line_dash="dash", line_color="green")
        st.plotly_chart(fig2, use_container_width=True)