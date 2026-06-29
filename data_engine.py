# This script is executed weekly by GitHub Actions.
# It extracts data, applies the HP Filter and Z-scores, and saves a static CSV.

import os
import yfinance as yf
import pandas as pd
import numpy as np
import pandas_datareader.data as web
from statsmodels.tsa.filters.hp_filter import hpfilter
import warnings
import json

warnings.filterwarnings('ignore')

def get_fred_data(series_id, start_date):
    """Fetches macroeconomic data from FRED and resamples to monthly start."""
    df = web.DataReader(series_id, 'fred', start_date)
    # CHANGED: 'MS' (Month Start) aligns FRED dates exactly with yfinance dates (e.g., 2000-01-01)
    return df.resample('MS').first()

def get_market_data(start_date):
    """Fetches equity and bond data from yfinance."""
    sectors = ['XLK', 'XLF', 'XLV', 'XLY', 'XLP', 'XLE', 'XLI', 'XLU', 'XLB', 'XLRE', 'XLC']
    tickers = ['SPY', 'VEA', 'VWO', 'TLT', 'IEF'] + sectors
    
    raw_data = yf.download(tickers, start=start_date, interval="1mo")
    return raw_data['Close'].dropna(how='all')

def calculate_hp_zscore(series, lambda_val=14400, window=120):
    """Applies HP filter to extract the cycle, then calculates a rolling 10-year Z-score."""
    clean_series = series.dropna()
    if len(clean_series) < window:
        return pd.Series(index=series.index, dtype=float)
        
    cycle, _ = hpfilter(clean_series, lamb=lambda_val)
    
    rolling_mean = cycle.rolling(window=window).mean()
    rolling_std = cycle.rolling(window=window).std()
    z_score = (cycle - rolling_mean) / rolling_std
    
    return z_score

def fetch_global_valuations():
    """Fetches current P/E metadata to calculate Implied Earnings Yield and 3Y Treasury."""
    indices = {
        'SPY': 'S&P 500 (US)',
        'QQQ': 'Nasdaq 100 (US)',
        'MCHI': 'China (MSCI)',
        'EWH': 'Hong Kong (MSCI)',
        'EWJ': 'Japan (MSCI)',
        'EWZ': 'Brazil (MSCI)',
        'INDA': 'India (MSCI)',
        'EWY': 'South Korea (MSCI)',
        'EWT': 'Taiwan (MSCI)',
        'EWG': 'Germany (MSCI)',
        'EWU': 'UK (MSCI)'
    }
    valuations = {}
    
    # 1. Fetch 3-Year US Treasury Yield (DGS3) directly from FRED
    try:
        # Looking back 10 days ensures we capture the latest daily print regardless of weekends/holidays
        treasury_df = web.DataReader('DGS3', 'fred', pd.Timestamp.now() - pd.DateOffset(days=10))
        treasury_3y = float(treasury_df.dropna().iloc[-1, 0])
        valuations['US3Y'] = {'name': '3-Yr US Treasury', 'pe': None, 'yield': treasury_3y}
    except Exception as e:
        print(f"Failed to fetch 3Y Treasury: {e}")
        valuations['US3Y'] = {'name': '3-Yr US Treasury', 'pe': None, 'yield': None}

    # 2. Fetch Equity ETFs
    for ticker, name in indices.items():
        try:
            info = yf.Ticker(ticker).info
            pe = info.get('trailingPE')
            if pe and pe > 0:
                yield_pct = (1 / pe) * 100
                valuations[ticker] = {'name': name, 'pe': pe, 'yield': yield_pct}
            else:
                valuations[ticker] = {'name': name, 'pe': None, 'yield': None}
        except Exception:
            valuations[ticker] = {'name': name, 'pe': None, 'yield': None}
            
    os.makedirs('data', exist_ok=True)
    with open('data/valuations.json', 'w') as f:
        json.dump(valuations, f)

def process_data():
    print("Starting data extraction...")
    start_date = '2000-01-01'
    
    # Fetch global valuations snapshot
    print("Fetching global earnings yields...")
    fetch_global_valuations()
    
    # 1. Fetch Data
    market_df = get_market_data(start_date)
    # Ensure yfinance index is timezone-naive so it doesn't conflict with FRED
    market_df.index = pd.to_datetime(market_df.index).tz_localize(None)
    
    # FRED: Median Household Income (Annual, ffilled to monthly) and Case-Shiller Home Price Index
    fred_series = ['MEHOINUSA672N', 'CSUSHPINSA']
    macro_data = pd.DataFrame()
    for series in fred_series:
        macro_data[series] = get_fred_data(series, start_date)[series]
        
    macro_data = macro_data.ffill() # Forward fill annual income data to monthly
    macro_data.index = pd.to_datetime(macro_data.index).tz_localize(None)
    
    master_df = pd.DataFrame(index=market_df.index)
    
    # 2. Base Assets
    master_df['SPY'] = market_df['SPY']
    master_df['TLT'] = market_df['TLT']
    master_df['IEF'] = market_df['IEF']
    
    # 3. Macro Bubble Ratios (Indices now align perfectly)
    master_df['Housing_Income_Ratio'] = macro_data['CSUSHPINSA'] / macro_data['MEHOINUSA672N']
    master_df['Dev_EM_Ratio'] = market_df['VEA'] / market_df['VWO']
    
    # 4. Market Velocity & Acceleration (Derivatives)
    master_df['SPY_Velocity_MoM'] = market_df['SPY'].pct_change()
    master_df['SPY_Acceleration'] = master_df['SPY_Velocity_MoM'].diff()
    
    # 5. Sector Ratios & Z-Scores
    sectors = ['XLK', 'XLF', 'XLV', 'XLY', 'XLP', 'XLE', 'XLI', 'XLU', 'XLB', 'XLRE', 'XLC']
    for sector in sectors:
        if sector in market_df.columns:
            master_df[f'{sector}_Ratio'] = market_df[sector] / market_df['SPY']
            master_df[f'{sector}_ZScore'] = calculate_hp_zscore(master_df[f'{sector}_Ratio'])
            
    # Calculate SPY Macro Z-Score
    master_df['SPY_ZScore'] = calculate_hp_zscore(master_df['SPY'])

    # 6. Save Data
    os.makedirs('data', exist_ok=True)
    file_path = 'data/market_data.csv'
    master_df.to_csv(file_path)
    print(f"Data successfully processed and saved to {file_path}")

if __name__ == "__main__":
    process_data()