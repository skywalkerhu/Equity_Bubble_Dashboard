# This script is executed by GitHub Actions.
# It extracts data, applies the HP Filter and Z-scores, and saves static CSVs.
#
# Set FAST_LOCAL=1 to skip the inter-request spacing during local development.
# Faster, but much more likely to come back rate-limited (0 live P/Es):
#     FAST_LOCAL=1 python data_engine.py

import os
import io
import time
import threading
import requests
import yfinance as yf
import pandas as pd
import numpy as np
import pandas_datareader.data as web
from statsmodels.tsa.filters.hp_filter import hpfilter
import warnings
import json
from datetime import datetime, timezone

warnings.filterwarnings('ignore')

# federalreserve.gov returns 403 to the default urllib User-Agent that
# pandas sends, so the download is done through requests with a UA set.
EQUITY_ISSUANCE_URL = 'https://www.federalreserve.gov/releases/efa/equity-issuance-retirement-quarterly-historical.csv'
HTTP_HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; equity-bubble-dashboard/1.0)'}

# Skip backoff sleeps when iterating locally. Actions leaves this unset.
FAST_LOCAL = os.environ.get('FAST_LOCAL') == '1'

def log(msg):
    """Print immediately. Piped stdout is block-buffered otherwise, which
    makes a running job look hung."""
    print(msg, flush=True)

def with_timeout(fn, timeout, *args, **kwargs):
    """Runs fn(*args, **kwargs) on a daemon thread and bounds how long we
    wait for it. yfinance/pandas_datareader calls have no built-in timeout,
    so a stalled Yahoo/FRED response hangs the whole job indefinitely instead
    of failing — that's the actual "taking forever" failure mode, not steady
    -state slowness. We can't kill the thread, but as a daemon it won't block
    process exit, and raising TimeoutError lets callers fall back to cache."""
    box = {}
    def target():
        try:
            box['value'] = fn(*args, **kwargs)
        except Exception as e:
            box['error'] = e
    t = threading.Thread(target=target, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        raise TimeoutError(f"{getattr(fn, '__name__', 'call')} exceeded {timeout}s")
    if 'error' in box:
        raise box['error']
    return box['value']

def get_fred_data(series_id, start_date, freq='MS'):
    """Fetches macroeconomic data from FRED and resamples to the specified frequency."""
    try:
        start_dt = pd.to_datetime(start_date)
        df = with_timeout(web.DataReader, 20, series_id, 'fred', start_dt)
        return df.resample(freq).first()
    except Exception as e:
        log(f"   ⚠️ Error fetching {series_id}: {e}. Skipping...")
        return pd.DataFrame(columns=[series_id])

def fetch_equity_issuance_data():
    """Downloads the Federal Reserve's Enhanced Financial Accounts equity
    issuance and retirement series and writes data/quarterly_data.csv.

    On any failure the existing file is left untouched, so a bad run keeps
    last-known-good data rather than wiping the chart."""
    out_path = 'data/quarterly_data.csv'
    try:
        resp = requests.get(EQUITY_ISSUANCE_URL, headers=HTTP_HEADERS, timeout=60)
        resp.raise_for_status()
        df = pd.read_csv(io.StringIO(resp.text))

        # Clean up column names to avoid hidden whitespace issues.
        # The Fed file quotes some headers with leading spaces.
        df.columns = [str(c).strip() for c in df.columns]
        date_col = df.columns[0]

        # Filter STRICTLY for rows where the date column is exactly YYYY:QX (e.g., "1996:Q4")
        df = df[df[date_col].astype(str).str.strip().str.match(r'^\d{4}:Q[1-4]$', na=False)]
        if df.empty:
            log("⚠️ Equity issuance file parsed to zero valid rows. Keeping existing file.")
            return

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

        result_df = result_df.dropna(how='all')
        if result_df.empty:
            log("⚠️ Equity issuance file had no recognised columns. Keeping existing file.")
            return

        os.makedirs('data', exist_ok=True)
        result_df.index.name = 'Date'
        result_df.to_csv(out_path)
        log(f"✅ Equity issuance updated: {len(result_df)} quarters through {result_df.index[-1].date()}")

    except Exception as e:
        log(f"⚠️ Equity issuance fetch failed ({e}). Keeping existing file.")

def get_market_data(start_date):
    """Fetches equity data from yfinance, including Volume.
    One batched call; monthly interval, so this is cheap (~2.5s)."""
    sectors = ['XLK', 'XLF', 'XLV', 'XLY', 'XLP', 'XLE', 'XLI', 'XLU', 'XLB', 'IYR', 'IYZ']
    tickers = ['^GSPC', '^IXIC'] + sectors

    raw_data = with_timeout(yf.download, 30, tickers, start=start_date, interval="1mo")

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

# Spacing between .info calls. This is PREVENTION, not politeness: Yahoo
# rate-limits by IP and then returns 200s with trailingPE stripped out.
# Retrying inside a few seconds cannot clear a rate limit (they reset over
# minutes) and triples the request count, which makes it worse. So: one
# attempt per ticker, spaced out, and fall back to last-known-good on a miss.
PE_REQUEST_SPACING = 0.0 if FAST_LOCAL else 2.0

def fetch_trailing_pe(ticker):
    """Returns a positive trailingPE, or None if Yahoo didn't supply one.
    Single attempt by design — see PE_REQUEST_SPACING above."""
    try:
        # Do NOT pass a custom requests.Session here: yfinance 1.8.0 does its
        # own cookie/crumb auth handshake, and overriding the session makes
        # Yahoo return 401 Unauthorized on every call.
        info = with_timeout(lambda: yf.Ticker(ticker).info, 15)
        pe = info.get('trailingPE')
        return pe if (pe and pe > 0) else None
    except Exception as e:
        log(f"      {ticker}: fetch error — {type(e).__name__}: {str(e)[:80]}")
        return None

def fetch_global_valuations():
    """Fetches current P/E metadata. Merges with existing file so a rate-limited
    run doesn't wipe out last-known-good values."""
    indices = {
        'SPY': 'S&P 500 (US)', 'QQQ': 'Nasdaq 100 (US)', 'MCHI': 'China (MSCI)',
        'EWH': 'Hong Kong (MSCI)', 'EWJ': 'Japan (MSCI)', 'EWZ': 'Brazil (MSCI)',
        'INDA': 'India (MSCI)', 'EWY': 'South Korea (MSCI)', 'EWT': 'Taiwan (MSCI)',
        'EWG': 'Germany (MSCI)', 'EWU': 'UK (MSCI)', 'EWC': 'Canada (MSCI)',
        'THD': 'Thailand (MSCI)', 'EWM': 'Malaysia (MSCI)', 'EIDO': 'Indonesia (MSCI)',
        'EWD': 'Sweden (MSCI)', 'EWS': 'Singapore (MSCI)'
    }

    val_path = 'data/valuations.json'
    # Load existing data as the fallback baseline
    if os.path.exists(val_path):
        with open(val_path, 'r') as f:
            valuations = json.load(f)
    else:
        valuations = {}

    log("[1/4] Valuations: fetching 3Y Treasury from FRED...")
    try:
        treasury_df = with_timeout(web.DataReader, 20, 'DGS3', 'fred', pd.Timestamp.now() - pd.DateOffset(days=10))
        treasury_clean = treasury_df.dropna()
        treasury_3y = float(treasury_clean.iloc[-1, 0])
        valuations['US3Y'] = {'name': '3-Yr US Treasury', 'pe': None, 'yield': treasury_3y}
        log(f"      DGS3 = {treasury_3y}% as of {treasury_clean.index[-1].date()}")
    except Exception as e:
        log(f"   ⚠️ Treasury fetch failed, keeping last known value: {e}")
        valuations.setdefault('US3Y', {'name': '3-Yr US Treasury', 'pe': None, 'yield': None})

    pe_live = 0
    total = len(indices)
    for i, (ticker, name) in enumerate(indices.items(), 1):
        t0 = time.perf_counter()
        pe = fetch_trailing_pe(ticker)
        elapsed = time.perf_counter() - t0
        if pe:
            valuations[ticker] = {'name': name, 'pe': pe, 'yield': (1 / pe) * 100}
            pe_live += 1
            log(f"      ({i}/{total}) {ticker:5} P/E {pe:7.2f}  {elapsed:5.2f}s")
        else:
            valuations.setdefault(ticker, {'name': name, 'pe': None, 'yield': None})
            log(f"      ({i}/{total}) {ticker:5} no data — keeping last known value  {elapsed:5.2f}s")
        # Space out requests to stay under Yahoo's rate limit. Skip after the last.
        if i < total and PE_REQUEST_SPACING:
            time.sleep(PE_REQUEST_SPACING)

    log(f"✅ Valuations: {pe_live}/{total} P/Es live this run.")
    if pe_live == 0:
        log("   ⚠️ ZERO live P/Es — almost certainly Yahoo rate-limiting this IP.")
        log("      Wait ~15-30 min before retrying; the dashboard is showing cached values.")

    os.makedirs('data', exist_ok=True)
    with open(val_path, 'w') as f:
        json.dump(valuations, f)

    # Timestamp for the dashboard, in its own file so valuations.json is unchanged.
    with open('data/meta.json', 'w') as f:
        json.dump({'generated_at': datetime.now(timezone.utc).isoformat(timespec='seconds')}, f)

def process_data():
    start_date = '1970-01-01'
    os.makedirs('data', exist_ok=True)

    fetch_global_valuations()

    # --- 1. MONTHLY MARKET DATA ENGINE ---
    # Wrapped end-to-end: a stalled/failed fetch here must not abort the
    # equity-issuance and Baa-spread steps below, and must leave the
    # existing market_data.csv untouched (same "last known good" policy as
    # the other sources in this file).
    log("[2/4] Market data: downloading 13 tickers (monthly)...")
    try:
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
        log(f"✅ Market data written: {master_df.shape[0]} months, {master_df.shape[1]} columns")
    except Exception as e:
        log(f"⚠️ Market data fetch failed ({e}). Keeping existing file.")

    # --- 2. QUARTERLY EQUITY ISSUANCE ENGINE ---
    log("[3/4] Equity issuance: downloading Fed EFA file...")
    fetch_equity_issuance_data()

    # --- 3. STANDALONE BAA SPREAD ENGINE (DAILY) ---
    log("[4/4] Baa spread: downloading BAAFF from FRED...")
    try:
        start_dt = pd.to_datetime(start_date)
        baa_df = with_timeout(web.DataReader, 20, 'BAAFF', 'fred', start_dt)
        baa_df.dropna(inplace=True)
        baa_df.to_csv('data/baa_spread.csv')
        log(f"✅ Baa spread written: {len(baa_df)} daily obs through {baa_df.index[-1].date()}")
    except Exception as e:
        log(f"⚠️ Error fetching BAAFF: {e}")
        pd.DataFrame(columns=['BAAFF']).to_csv('data/baa_spread.csv')

    log("Done.")

if __name__ == "__main__":
    process_data()