# Equity Bubble & Sector Value Explorer

This is a data-driven macro equity markets surveillance and tactical asset allocation dashboard built using Python and Streamlit. This platform identifies structural macroeconomic extremes, cyclical asset bubbles defined as a 2-sigma event, and value capitulation points by evaluating 10-year historical data through a statistical mechanics framework.

Live Dashboard:
https://equitybubbledashboard-jadequity.streamlit.app/

## Executive Summary & Core Philosophy

The primary objective of this dashboard is to mitigate the risk of buying into late-stage asset bubbles while systematically identifying contrarian "value fishing" zones where capital flight has created extreme mispricings. The author completed this project in late June, 2026 as the author believed that we were heading into an equity bubble phase for the U.S. stock market.

The analytical core focuses on locating 2-sigma ($\sigma$) deviations from structural trends across global indices, economic ratios, and equity sectors. Data are sourced from yfinance, a public financial data API. You should expect a time lag between real-time data and data shown here on the dashbaord. However, in the author's opinion that does not matter for equity investors.

## Global Implied Earnings Yield Scoreboard ($E/P$)

Real-time tracking of global equity index valuations and US Treasury yields. By inverting the Price-to-Earnings (P/E) ratio, the dashboard provides a fast, standardized baseline of the implied earnings yield across domestic, emerging, and developed markets to contrast against the risk-free rate.

## Monthly Market & Sector Dynamics

Cyclical Z-Scores: Employs Hodrick-Prescott (HP) filters to extract the underlying cycle of the S&P 500 and apply a rolling 10-year Z-score, tracking $\ge 2\sigma$ deviations for market tops and $\le -2\sigma$ capitulations.

## Velocity & Acceleration: Measures momentum derivatives (MoM percentage change and its rate of change) of the broader market.

Sector Relative Value Explorer: Evaluates the cyclical deviation of all 11 GICS sectors relative to the S&P 500 to identify rotational value entry points.

## High-Frequency Speculative Turnover: Tracks total market trading volume (SPY + Nasdaq) as a proxy for speculative fever.

Credit Stress Indicators: Monitors the Moody's Baa Corporate Bond minus Fed Funds Rate spread. Applies a dynamic 10-year rolling Z-score to highlight periods of peak credit exuberance (negative standard deviations) or severe liquidity stress.

# Quarterly Macro Risk & Liquidity (IMF Quantity Pillars)

Corporate Equity Issuance Flow of Funds: Tracks the structural supply of equities, dynamically parsing Federal Reserve Enhanced Financial Accounts (EFA) data.

## Gross Corporate Equity Issuance

## Gross Retirements (Categorized by Share Repurchases vs. Mergers & Acquisitions)

## Net Equity Issuance

## Shadow Banking / Private Credit Share: Measures Non-Bank Credit as a percentage of Total Non-Financial Credit using Bank for International Settlements (BIS) data to proxy structural, off-balance-sheet leverage and non-traditional liquidity risk.

# Architecture & Data Pipeline

The project decouples heavy data processing from the front-end rendering to ensure lightning-fast dashboard performance.

data_engine.py (The Backend): Executed weekly via GitHub Actions. It extracts data from Yahoo Finance (yfinance), the FRED API (pandas_datareader), and local static historical flow datasets. It computes all HP filters and rolling Z-scores, handles disparate datetime index merging, and exports the aggregated data to static CSVs.

app.py (The Frontend): A Streamlit application that loads the static CSVs and renders interactive, highly responsive charts using Plotly.

GitHub Actions (update_data.yml): A fully automated CI/CD pipeline that runs the data engine every Monday at midnight to pull the latest macro data, calculates updated standard deviations, and commits the fresh CSVs back to the repository.

# Local Setup & Installation

## Clone the repository and navigate to the project directory:

git clone [https://github.com/yourusername/macro-superbubble-explorer.git](https://github.com/yourusername/macro-superbubble-explorer.git)
cd macro-superbubble-explorer


## Create and activate a virtual environment:

Mac/Linux: python -m venv venv && source venv/bin/activate

Windows: python -m venv venv then .\venv\Scripts\activate
## Install dependencies:

pip install -r requirements.txt


## Run the Data Engine:
Generate the latest market_data.csv, quarterly_data.csv, and baa_spread.csv files locally.

python data_engine.py


## Launch the Dashboard:

streamlit run app.py
