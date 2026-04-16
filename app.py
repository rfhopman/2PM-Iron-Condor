import streamlit as st
import pandas as pd
import numpy as np
from scipy.stats import norm
from datetime import datetime, timedelta
import pytz
import yfinance as yf

# App Setup
st.set_page_config(page_title="XSP 0DTE Delta-Pro", layout="centered")
st.title("📊 XSP 0DTE Iron Condor (Delta-Based)")

SYMBOL = "^XSP"
WIDTH = 5.00
TARGET_DELTA = 0.15

def calculate_delta(S, K, T, r, sigma, option_type='call'):
    """Calculates Black-Scholes Delta for an option."""
    if T <= 0: return 0
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    if option_type == 'call':
        return norm.cdf(d1)
    else:
        return norm.cdf(d1) - 1

@st.cache_data(ttl=30)
def get_delta_data():
    try:
        ticker = yf.Ticker(SYMBOL)
        # 1. Get Spot Price & Timestamp
        hist = ticker.history(period="1d", interval="1m")
        if hist.empty: return {"error": "Market data unavailable."}
        
        S = float(hist['Close'].iloc[-1])
        tz = pytz.timezone('US/Eastern')
        yahoo_ts = hist.index[-1].astimezone(tz)

        # 2. Setup Time to Expiry (T)
        # 0DTE at 2:00 PM = ~2 hours left (2/24 / 365 in years)
        now_est = datetime.now(tz)
        close_est = now_est.replace(hour=16, minute=0, second=0, microsecond=0)
        time_diff = close_est - now_est
        hours_to_go = max(time_diff.total_seconds() / 3600, 0.5) # Minimum 30 mins
        T = (hours_to_go / 24) / 365 
        
        # 3. Get Risk-Free Rate (using 13-week T-Bill ^IRX as proxy)
        r = yf.Ticker("^IRX").fast_info.last_price / 100 
        
        # 4. Fetch Option Chain
        today_str = now_est.strftime('%Y-%m-%d')
        expirations = ticker.options
        target_expiry = today_str if today_str in expirations else expirations[0]
        chain = ticker.option_chain(target_expiry)

        # 5. Calculation Strategy (Pick strikes matching target delta)
        def find_best_strike(df, target, opt_type):
            # We estimate sigma (Implied Vol) from the middle of the chain
            # or use the provided 'impliedVolatility' from Yahoo
            df['delta'] = df.apply(lambda row: calculate_delta(
                S, row['strike'], T, r, row['impliedVolatility'], opt_type
            ), axis=1)
            # Find row where delta is closest to target
            idx = (df['delta'] - target).abs().idxmin()
            return df.loc[idx, 'strike']

        short_put = find_best_strike(chain.puts, -TARGET_DELTA, 'put')
        short_call = find_best_strike(chain.calls, TARGET_DELTA, 'call')

        return {
            "spot": S, "ts": yahoo_ts, "expiry": target_expiry,
            "strikes": {
                "Long Put": short_put - WIDTH,
                "Short Put": short_put,
                "Short Call": short_call,
                "Long Call": short_call + WIDTH
            }
        }
    except Exception as e:
        return {"error": str(e)}

# --- UI DISPLAY ---
if st.button('🚀 Calculate Strikes by 0.15 Delta'):
    with st.spinner('Running Black-Scholes Model...'):
        data = get_delta_data()
    
    if "error" in data:
        st.error(f"Logic Error: {data['error']}")
    else:
        st.metric("XSP Spot Price", f"${data['spot']:.2f}")
        st.caption(f"Yahoo Timestamp: {data['ts'].strftime('%I:%M:%S %p %Z')}")
        
        st.divider()
        st.write(f"### 🎯 Selected Strikes (Target: {TARGET_DELTA} Delta)")
        
        df = pd.DataFrame({
            "Leg": ["Long Put (Buy)", "Short Put (Sell)", "Short Call (Sell)", "Long Call (Buy)"],
            "Strike": [f"{v:.2f}" for v in data['strikes'].values()]
        })
        st.table(df)
        st.info("Note: Delta calculation uses real-time Implied Volatility and Time-to-Close (4:00 PM EST).")
