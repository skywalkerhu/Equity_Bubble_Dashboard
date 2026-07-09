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
    return df.resample('MS').first()

def get_market_data(start_date):
    """Fetches equity and bond data from yfinance."""
    sectors = ['XLK', 'XLF', 'XLV', 'XLY', 'XLP', 'XLE', 'XLI', 'XLU', 'XLB', 'IYR', 'IYZ']
    tickers = ['^GSPC', 'VEA', 'VWO', 'TLT', 'IEF'] + sectors
    
    raw_data = yf.download(tickers, start=start_date, interval="1mo")
    df = raw_data['Close'].dropna(how='all')
    
    if '^GSPC' in df.columns:
        df.rename(columns={'^GSPC': 'SPY'}, inplace=True)
        
    return df

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
    """Fetches current P/E metadata to calculate Implied Earnings Yield."""
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
    fetch_global_valuations()
    
    market_df = get_market_data(start_date)
    market_df.index = pd.to_datetime(market_df.index).tz_localize(None)
    
    fred_series = ['MEHOINUSA672N', 'CSUSHPINSA']
    macro_data = pd.DataFrame()
    for series in fred_series:
        macro_data[series] = get_fred_data(series, start_date)[series]
    macro_data = macro_data.ffill()
    macro_data.index = pd.to_datetime(macro_data.index).tz_localize(None)
    
    master_df = pd.DataFrame(index=market_df.index)
    master_df['SPY'] = market_df['SPY']
    
    sectors = ['XLK', 'XLF', 'XLV', 'XLY', 'XLP', 'XLE', 'XLI', 'XLU', 'XLB', 'IYR', 'IYZ']
    for sector in sectors:
        if sector in market_df.columns:
            # 1. Relative Value Z-Score
            master_df[f'{sector}_Ratio'] = market_df[sector] / market_df['SPY']
            master_df[f'{sector}_ZScore'] = calculate_hp_zscore(master_df[f'{sector}_Ratio'])
            
            # 2. Absolute Momentum Z-Score
            master_df[f'{sector}_Abs_ZScore'] = calculate_hp_zscore(market_df[sector])
            
    master_df['SPY_ZScore'] = calculate_hp_zscore(master_df['SPY'])
    
    os.makedirs('data', exist_ok=True)
    master_df.to_csv('data/market_data.csv')

if __name__ == "__main__":
    process_data()