# Equity Bubble & Sector Value Explorer

This is a data-driven macro equity markets surveillance and tactical asset allocation dashboard built using Python and Streamlit. This platform identifies structural macroeconomic extremes, cyclical asset bubbles defined as a 2-sigma event, and value capitulation points by evaluating 10-year historical data through a statistical mechanics framework.

Live Dashboard: 

---

## 1. Executive Summary & Core Philosophy

The primary objective of this dashboard is to mitigate the risk of buying into late-stage asset bubbles while systematically identifying contrarian "value fishing" zones where capital flight has created extreme mispricings. The author completed this project in late June, 2026 as the author believed that we were heading into an equity bubble phase for the U.S. stock market.

The analytical core focuses on locating 2-sigma ($\sigma$) deviations from structural trends across global indices, economic ratios, and equity sectors. Data are sourced from yfinance, a public financial data API. You should expect a time lag between real-time data and data shown here on the dashbaord. However, in the author's opinion that does not matter for equity investors. 

---

## 2. Global Implied Earnings Yield Scoreboard ($E/P$)

At the top of the dashboard is a real-time global valuation tracking grid. Rather than viewing price multiples in isolation, the engine extracts trailing P/E ratios of a few regional and thematic benchmarks and transforms them into an **Implied Earnings Yield**:

$$\text{Implied Earnings Yield } (E/P) = \frac{1}{\text{Trailing P/E}} \times 100$$

### Macro Implementation:
* **The Opportunity Cost Baseline:** The scoreboard explicitly includes the **3-Year US Treasury Yield** - sourced dynamically from the Federal Reserve Bank of St. Louis FRED API - as the short-to-medium-term risk-free proxy. The author wanted to avoid the "too long-term" illusion to pretend that he's an "involuntary long-term value investor".
* **The Equity Risk Premium (ERP):** By placing regional equity yields side-by-side with the risk-free rate, you can immediately assess if a country or theme offers an acceptable premium for equity risk. If a major index yield drops near or below the U.S. Treasury rate, the risk premium compression signals structural overvaluation.
* **Granular Arbitrage Geographies:** To avoid the distortion of generalized "Emerging Market" baskets, the scoreboard breaks allocations down into direct geographic proxies. Hong Kong is placed into the EM bucket since over 95% of public companies there are from Chinese mainland. 
  * **US Equity Focus:** S&P 500 (`SPY`), Nasdaq 100 (`QQQ`)
  * **Developed International:** Japan (`EWJ`), Germany (`EWG`), United Kingdom (`WWU`)
  * **Emerging Markets:** China (`MCHI`), Hong Kong (`EWH`), Brazil (`EWZ`), India (`INDA`), South Korea (`EWY`), Taiwan (`EWT`)

---

## 3. Quantitative Methodologies

### 10-Year Cyclical Z-Score: The Hodrick-Prescott Framework
To find cyclical tops and bottoms, the backend engine eliminates secular macro noise from asset time series using the **Hodrick-Prescott (HP) Filter**. This mathematical tool decomposes an economic time series $y_t$ into a smooth long-term trend component $g_t$ and a cyclical component $c_t$:

$$y_t = g_t + c_t$$

The filter minimizes the variance of the cyclical component subject to a penalty parameter $\lambda$ which is configured to $14,400$ for monthly data to insulate longer structural waves:

$$\min_{g_t} \sum_{t=1}^T c_t^2 + \lambda \sum_{t=2}^{T-1} [ (g_{t+1} - g_t) - (g_t - g_{t-1}) ]^2$$

Once the cyclical component $c_t$ is isolated, the system runs a rolling 10-year mean and standard deviation to generate a standardized **Z-Score**:

$$Z_t = \frac{c_t - \mu_{\text{10Yr}}}{\sigma_{\text{10Yr}}}$$

* **$\ge +2\sigma$ - Bubble Zone:** The asset cycle is overextended. Historically, entries at these points yield poor multi-year forward returns.
* **$\le -2\sigma$ -  Value Zone:** The cycle has experienced meaningful selling pressure, presenting high-probability windows for secular value investors.

### Market Velocity & Acceleration
To capture structural inflection points before a full price reversal materializes, the platform plots the first and second derivatives of price momentum:
* **Velocity - Month-over-Month % Change:** Captures the speed of price expansion or contraction.
* **Acceleration - Rate of Change of Velocity:** Measures the exhaustion of a trend. A decelerating velocity at a $+2\sigma$ peak often signals the absolute top of a superbubble structure.

### Housing-to-Income Ratio
A systemic long-term structural health index tracking the median housing price index relative to real personal disposable income. When this ratio scales into extreme positive Z-scores, it signals asset-price expansion driven by excessive credit or unsustainable multiple-expansion, rather than structural economic fundamentals. 
What's worse than an equity bubble is a housing bubble, or housing + equity + multi-asset bubble. We might be in multi-asset bubble territory given how far commodities/precious metals like gold and silver have extended their price runs. 

### Developed Markets vs. Emerging Markets Ratio  - `VEA` / `VWO`
This metric maps the relative pricing of Developed Markets against Emerging Markets over multi-year periods.
* **High Ratio / Uptrend:** Signals extreme capital concentration in defensive or dominant developed geographies (often peaking during late-stage Western technology cycles).
* **Low Ratio / Downtrend:** Signals deep capital flight away from developing spaces. When this ratio compresses to historical standard deviation boundaries, it signals an asymmetric macro opportunity to rotate out of expensive developed large-caps and back into highly-discounted global asset classes.

### Sector Relative Value Explorer
This explorer compares individual S&P 500 sectors against the broader index. By taking the sector price relative to the market ($P_{\text{sector}} / P_{\text{market}}$) and generating its cyclical Z-score, it highlights exact pockets within the market undergoing structural capital flight (e.g., Energy or Utilities trading at $\le -2\sigma$ during a secular technology blow-off top).

---

## 4. Local Installation & Architecture

The system splits database management and visualization into a distinct two-layer architecture to maximize analytical stability:

```text
├── data_engine.py       # Backend Data Fetcher (YFinance/FRED APIs), Processing, and Mathematical Modeling
├── app.py               # Frontend UI Framework (Streamlit Web Application & Plotly Engines)
└── data/
    ├── market_data.csv  # Standardized Historical Cycle Data
    └── valuations.json  # Live Implied Global Valuation Metadata Archive