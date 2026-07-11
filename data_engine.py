# This script maintains the master quarterly_data.csv
# It refreshes FRED Shadow Banking metrics and preserves your Equity Issuance manual rows.

import os
import pandas as pd
import numpy as np
import pandas_datareader.data as web
import warnings

warnings.filterwarnings('ignore')

def get_fred_data(series_id, start_date, freq='QS'):
    """Fetches quarterly macroeconomic data from FRED."""
    try:
        start_dt = pd.to_datetime(start_date)
        df = web.DataReader(series_id, 'fred', start_dt)
        return df.resample(freq).first()
    except Exception as e:
        print(f"⚠️ Error fetching {series_id}: {e}")
        return pd.DataFrame(columns=[series_id])

def process_data():
    os.makedirs('data', exist_ok=True)
    master_path = 'data/quarterly_data.csv'
    
    # 1. Fetch Latest Shadow Banking Data
    macro_quarterly = pd.DataFrame()
    for series in ['CRDQUSAPABIS', 'CRDQUSBPUBIS']:
        fetched = get_fred_data(series, '1970-01-01', freq='QS')
        if not fetched.empty:
            macro_quarterly[series] = fetched[series]
            
    if 'CRDQUSAPABIS' in macro_quarterly.columns and 'CRDQUSBPUBIS' in macro_quarterly.columns:
        macro_quarterly['Shadow_Bank_Credit'] = ((macro_quarterly['CRDQUSAPABIS'] - macro_quarterly['CRDQUSBPUBIS']) / macro_quarterly['CRDQUSAPABIS']) * 100
    
    # 2. Merge with existing Master Data (Preserving your manually managed Issuance rows)
    if os.path.exists(master_path):
        existing_df = pd.read_csv(master_path, index_col=0, parse_dates=True)
        # Drop the old shadow columns to prevent duplicates
        cols_to_drop = [c for c in ['CRDQUSAPABIS', 'CRDQUSBPUBIS', 'Shadow_Bank_Credit'] if c in existing_df.columns]
        existing_df.drop(columns=cols_to_drop, errors='ignore', inplace=True)
        # Join new FRED data
        master_df = existing_df.join(macro_quarterly, how='outer')
    else:
        master_df = macro_quarterly

    master_df.dropna(how='all', inplace=True)
    master_df.to_csv(master_path)
    print("✅ Successfully updated quarterly_data.csv with latest Shadow Banking metrics.")

if __name__ == "__main__":
    process_data()