# This script is executed weekly by GitHub Actions.
# It extracts data, applies the HP Filter and Z-scores, and saves static CSVs.

import os
import yfinance as yf
import pandas as pd
import numpy as np
import pandas_datareader.data as web
from statsmodels.tsa.filters.hp_filter import hpfilter
import warnings
import json

warnings.filterwarnings('ignore')

def get_fred_data(series_id, start_date, freq='MS'):
    """Fetches macroeconomic data from FRED and resamples to the specified frequency."""
    df = web.DataReader(series_id, 'fred', start_date)
    return df.resample(freq).first()

def get_market_data(start_date):
    """Fetches equity and bond data from yfinance, including Volume."""
    sectors = ['XLK', 'XLF', 'XLV', 'XLY', 'XLP', 'XLE', 'XLI', 'XLU', 'XLB', 'IYR', 'IYZ']
    tickers = ['^GSPC', '^IXIC', 'VEA', 'VWO', 'TLT', 'IEF'] + sectors
    
    raw_data = yf.download(tickers, start=start_date, interval="1mo")
    
    close_df = raw_data['Close'].dropna(how='all')
    volume_df = raw_data['Volume'].dropna(how='all')
    
    if '^GSPC' in close_df.columns:
        close_df.rename(columns={'^GSPC': 'SPY'}, inplace=True)
    if '^GSPC' in volume_df.columns:
        volume_df.rename(columns={'^GSPC': 'SPY'}, inplace=True)
        
    return close_df, volume_df

def calculate_hp_zscore(series, lambda_val=14400, window=120):
    """Applies HP filter to extract the cycle, then calculates a rolling 10-year Z-score."""
    clean_series = series.dropna()
    
    if len(clean_series) < 24:
        return pd.Series(index=series.index, dtype=float)
        
    cycle, _ = hpfilter(clean_series, lamb=lambda_val)
    
    rolling_mean = cycle.rolling(window=window, min_periods=24).mean()
    rolling_std = cycle.rolling(window=window, min_periods=24).std()
    z_score = (cycle - rolling_mean) / rolling_std
    
    aligned_z_score = pd.Series(z_score, index=clean_series.index).reindex(series.index)
    return aligned_z_score

def fetch_global_valuations():
    """Fetches current P/E metadata."""
    indices = {
        'SPY': 'S&P 500 (US)', 'QQQ': 'Nasdaq 100 (US)', 'MCHI': 'China (MSCI)',
        'EWH': 'Hong Kong (MSCI)', 'EWJ': 'Japan (MSCI)', 'EWZ': 'Brazil (MSCI)',
        'INDA': 'India (MSCI)', 'EWY': 'South Korea (MSCI)', 'EWT': 'Taiwan (MSCI)',
        'EWG': 'Germany (MSCI)', 'EWU': 'UK (MSCI)'
    }
    valuations = {}
    
    try:
        treasury_df = web.DataReader('DGS3', 'fred', pd.Timestamp.now() - pd.DateOffset(days=10))
        treasury_3y = float(treasury_df.dropna().iloc[-1, 0])
        valuations['US3Y'] = {'name': '3-Yr US Treasury', 'pe': None, 'yield': treasury_3y}
    except Exception:
        valuations['US3Y'] = {'name': '3-Yr US Treasury', 'pe': None, 'yield': None}

    for ticker, name in indices.items():
        try:
            info = yf.Ticker(ticker).info
            pe = info.get('trailingPE')
            valuations[ticker] = {'name': name, 'pe': pe, 'yield': (1/pe)*100 if pe and pe > 0 else None}
        except Exception:
            valuations[ticker] = {'name': name, 'pe': None, 'yield': None}
            
    os.makedirs('data', exist_ok=True)
    with open('data/valuations.json', 'w') as f:
        json.dump(valuations, f)

def process_data():
    start_date = '1970-01-01'
    os.makedirs('data', exist_ok=True)
    
    fetch_global_valuations()
    
    # --- 1. MONTHLY MARKET DATA ENGINE ---
    market_df, volume_df = get_market_data(start_date)
    market_df.index = pd.to_datetime(market_df.index).tz_localize(None)
    volume_df.index = pd.to_datetime(volume_df.index).tz_localize(None)
    
    monthly_fred_series = ['MEHOINUSA672N', 'CSUSHPINSA', 'BAMLH0A0HYM2']
    macro_monthly = pd.DataFrame()
    for series in monthly_fred_series:
        macro_monthly[series] = get_fred_data(series, start_date, freq='MS')[series]
    macro_monthly.index = pd.to_datetime(macro_monthly.index).tz_localize(None)
    
    master_df = pd.DataFrame(index=market_df.index)
    master_df['SPY'] = market_df['SPY']
    master_df['SPY_Velocity_MoM'] = market_df['SPY'].pct_change()
    master_df['SPY_Acceleration'] = master_df['SPY_Velocity_MoM'].diff()
    master_df['SPY_ZScore'] = calculate_hp_zscore(master_df['SPY'])
    
    sectors = ['XLK', 'XLF', 'XLV', 'XLY', 'XLP', 'XLE', 'XLI', 'XLU', 'XLB', 'IYR', 'IYZ']
    for sector in sectors:
        if sector in market_df.columns:
            master_df[f'{sector}_Ratio'] = market_df[sector] / market_df['SPY']
            master_df[f'{sector}_ZScore'] = calculate_hp_zscore(master_df[f'{sector}_Ratio'])
            
    if '^IXIC' in volume_df.columns and 'SPY' in volume_df.columns:
        master_df['Total_Market_Volume'] = volume_df['SPY'] + volume_df['^IXIC']
        master_df['Total_Volume_ZScore'] = calculate_hp_zscore(master_df['Total_Market_Volume'])
        
    master_df = master_df.join(macro_monthly, how='left')
    master_df['HY_Spread'] = master_df['BAMLH0A0HYM2']
    master_df.to_csv('data/market_data.csv')
    
    # --- 2. QUARTERLY MACRO DATA ENGINE ---
    quarterly_fred_series = ['NCBCEIQ027S', 'NCBCEAMVD', 'CRDQUSAPABIS', 'CRDQUSBPUBIS']
    macro_quarterly = pd.DataFrame()
    for series in quarterly_fred_series:
        macro_quarterly[series] = get_fred_data(series, start_date, freq='QS')[series]
    macro_quarterly.index = pd.to_datetime(macro_quarterly.index).tz_localize(None)
    
    macro_quarterly['Net_Equity_Issuance_Yield'] = (macro_quarterly['NCBCEIQ027S'] / macro_quarterly['NCBCEAMVD']) * 100
    macro_quarterly['Shadow_Bank_Credit'] = macro_quarterly['CRDQUSAPABIS'] - macro_quarterly['CRDQUSBPUBIS']
    
    # Save purely quarterly dataset without monthly NaNs
    macro_quarterly.dropna(how='all', inplace=True)
    macro_quarterly.to_csv('data/quarterly_data.csv')

if __name__ == "__main__":
    process_data()