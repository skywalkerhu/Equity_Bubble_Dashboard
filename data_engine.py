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
    try:
        start_dt = pd.to_datetime(start_date)
        df = web.DataReader(series_id, 'fred', start_dt)
        return df.resample(freq).first()
    except Exception as e:
        print(f"⚠️ Error fetching {series_id}: FRED API returned an error (likely 404). Skipping...")
        return pd.DataFrame(columns=[series_id])

def get_local_equity_issuance_data():
    try:
        file_path = 'data/quarterly_data.csv'
        if not os.path.exists(file_path):
            print(f"⚠️ Local file {file_path} not found. Skipping equity issuance data.")
            return pd.DataFrame(columns=['Net_Equity_Issuance', 'Gross_Equity_Issuance', 'Equity_Repurchases', 'Equity_Retirements_MA'])
            
        # Read the local CSV
        df = pd.read_csv(file_path)
        
        # Clean up column names to avoid hidden whitespace issues
        df.columns = [str(c).strip() for c in df.columns]
        date_col = df.columns[0]
        
        # Filter STRICTLY for rows where the date column is exactly YYYY:QX (e.g., "1996:Q4")
        df = df[df[date_col].astype(str).str.strip().str.match(r'^\d{4}:Q[1-4]$', na=False)]
        
        # Convert "1996:Q4" to "1996Q4" and then to a proper pandas datetime timestamp
        df.index = pd.PeriodIndex(df[date_col].astype(str).str.strip().str.replace(':', ''), freq='Q').to_timestamp()
        
        # Clean all numeric columns (strip commas, convert strings to floats)
        for col in df.columns[1:]:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce')
            
        # Map the exact columns from the CSV table
        result_df = pd.DataFrame(index=df.index)
        if 'Issuance, Net' in df.columns:
            result_df['Net_Equity_Issuance'] = df['Issuance, Net']
        if 'Issuance, Gross' in df.columns:
            result_df['Gross_Equity_Issuance'] = df['Issuance, Gross']
        if 'Retirements, Repurchases' in df.columns:
            result_df['Equity_Repurchases'] = df['Retirements, Repurchases']
        if 'Retirements, Mergers and Acquisitions' in df.columns:
            result_df['Equity_Retirements_MA'] = df['Retirements, Mergers and Acquisitions']
            
        return result_df.dropna(how='all')
            
    except Exception as e:
        print(f"⚠️ Error reading local equity issuance data: {e}")
        return pd.DataFrame(columns=['Net_Equity_Issuance', 'Gross_Equity_Issuance', 'Equity_Repurchases', 'Equity_Retirements_MA'])

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
    
    market_df.index = pd.to_datetime(market_df.index).tz_localize(None).to_period('M').to_timestamp()
    volume_df.index = pd.to_datetime(volume_df.index).tz_localize(None).to_period('M').to_timestamp()
    
    monthly_fred_series = ['MEHOINUSA672N', 'CSUSHPINSA']
    macro_monthly = pd.DataFrame()
    for series in monthly_fred_series:
        fetched = get_fred_data(series, start_date, freq='MS')
        if not fetched.empty and series in fetched.columns:
            macro_monthly[series] = fetched[series]
        else:
            macro_monthly[series] = np.nan
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
    master_df.to_csv('data/market_data.csv')
    
    # --- 2. QUARTERLY MACRO DATA ENGINE ---
    # Fetch Shadow Banking Data via FRED
    quarterly_fred_series = ['CRDQUSAPABIS', 'CRDQUSBPUBIS']
    macro_quarterly = pd.DataFrame()
    for series in quarterly_fred_series:
        fetched = get_fred_data(series, start_date, freq='QS')
        if not fetched.empty and series in fetched.columns:
            macro_quarterly[series] = fetched[series]
        else:
            macro_quarterly[series] = np.nan
    macro_quarterly.index = pd.to_datetime(macro_quarterly.index).tz_localize(None)
    
    if 'CRDQUSAPABIS' in macro_quarterly.columns and 'CRDQUSBPUBIS' in macro_quarterly.columns:
        macro_quarterly['Shadow_Bank_Credit'] = ((macro_quarterly['CRDQUSAPABIS'] - macro_quarterly['CRDQUSBPUBIS']) / macro_quarterly['CRDQUSAPABIS']) * 100
    else:
        macro_quarterly['Shadow_Bank_Credit'] = np.nan

    # --- 3. STANDALONE BAA SPREAD ENGINE (DAILY) ---
    try:
        start_dt = pd.to_datetime(start_date)
        baa_df = web.DataReader('BAAFF', 'fred', start_dt)
        baa_df.dropna(inplace=True)
        baa_df.to_csv('data/baa_spread.csv')
    except Exception as e:
        print(f"⚠️ Error fetching BAAFF: {e}")
        pd.DataFrame(columns=['BAAFF']).to_csv('data/baa_spread.csv')

if __name__ == "__main__":
    process_data()