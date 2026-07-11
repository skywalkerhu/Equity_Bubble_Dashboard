Macro Superbubble Explorer

An institutional-grade quantitative macroeconomic dashboard designed to track equity superbubbles, sector relative value, and systemic risk. Built with Python and Streamlit, this project leverages a fully automated CI/CD data pipeline to analyze market regimes using Hodrick-Prescott filters, rolling Z-scores, and structural liquidity flows.

📊 Dashboard Features

1. Monthly Market & Sector Dynamics

Macro Asset Monitor: Real-time tracking of global equity and treasury yields.

Cyclical Z-Scores: Employs Hodrick-Prescott (HP) filters to extract the underlying cycle of the S&P 500 and apply a rolling 10-year Z-score, tracking $\ge 2\sigma$ deviations for market tops and $\le -2\sigma$ capitulations.

Velocity & Acceleration: Measures momentum derivatives of the broader market.

Sector Relative Value Explorer: Evaluates the cyclical deviation of all 11 GICS sectors relative to the S&P 500 to identify rotational value entry points.

High-Frequency Speculative Turnover: Tracks total market trading volume (SPY + Nasdaq) as a proxy for speculative fever.

Credit Stress Indicators: Monitors the Moody's Baa Corporate Bond minus Fed Funds Rate spread. Applies a dynamic 10-year rolling Z-score to highlight periods of peak credit exuberance or severe liquidity stress.

2. Quarterly Macro Risk & Liquidity (IMF Quantity Pillars)

Corporate Equity Issuance Flow of Funds: Tracks the structural supply of equities, dynamically parsing Federal Reserve Enhanced Financial Accounts (EFA) data.

Gross Corporate Equity Issuance

Gross Retirements (Categorized by Share Repurchases vs. M&A)

Net Equity Issuance

Shadow Banking / Private Credit Share: Measures Non-Bank Credit as a percentage of Total Non-Financial Credit using Bank for International Settlements (BIS) data to proxy structural, off-balance-sheet leverage.

🏗️ Architecture & Data Pipeline

The project decouples the heavy data processing from the front-end rendering to ensure lightning-fast dashboard performance.

data_engine.py (The Backend): Executed weekly via GitHub Actions. It extracts data from Yahoo Finance (yfinance), the FRED API (pandas_datareader), and local static historical flow datasets. It computes all HP filters and rolling Z-scores, then exports the cleaned, aggregated data to static CSVs.

app.py (The Frontend): A Streamlit application that loads the static CSVs and renders interactive, highly responsive charts using Plotly.

🚀 Local Setup & Installation

1. Clone the repository and navigate to the project directory:

git clone [https://github.com/yourusername/macro-superbubble-explorer.git](https://github.com/yourusername/macro-superbubble-explorer.git)
cd macro-superbubble-explorer


2. Create and activate a virtual environment:

Mac/Linux: python -m venv venv && source venv/bin/activate

Windows: python -m venv venv then .\venv\Scripts\activate

3. Install dependencies:

pip install -r requirements.txt


4. Run the Data Engine:
Generate the latest market_data.csv, quarterly_data.csv, and baa_spread.csv files locally.

python data_engine.py


5. Launch the Dashboard:

streamlit run app.py


⚙️ Automation (GitHub Actions)

This repository utilizes GitHub Actions (.github/workflows/update_data.yml) for continuous integration:

Weekly Data Cron: Runs data_engine.py automatically every Monday at midnight to pull the latest macro data, calculates updated standard deviations, and commits the fresh CSVs back to the repository.

Streamlit Heartbeat: Pings the Streamlit Cloud server periodically to prevent the app from hibernating due to inactivity.

🛠️ Tech Stack

Language: Python 3.10+

Frontend UI: Streamlit

Data Visualization: Plotly (Express & Graph Objects)

Data Engineering: Pandas, NumPy

Quantitative Modeling: Statsmodels (HP Filters)

Data Sources: yfinance, FRED API, Federal Reserve EFA, BIS