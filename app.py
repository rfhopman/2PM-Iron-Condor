import streamlit as st
import pandas as pd
import numpy as np
from scipy.stats import norm
from datetime import datetime
import pytz
import yfinance as yf

# App Setup
st.set_page_config(page_title="XSP 0DTE Delta-Pro", layout="centered")
st.title("📊 XSP 0DTE Iron Condor")

SYMBOL = "^XSP"
WIDTH = 5.00
TARGET_DELTA = 0.15

def calculate_delta(S, K, T, r, sigma, option_type='call'):
    """Calculates Black-Scholes Delta."""
    if T <= 0 or sigma <= 0: return 0
    # Black-Scholes Formula
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
        if hist.empty: return {"error": "Market data currently unavailable."}
        
        S = float(hist['Close'].iloc[-1])
        tz = pytz.timezone('US/Eastern')
        yahoo_ts = hist.index[-1].astimezone(tz)

        # 2. Time to Expiry (T) in years
        # Calculated from now until 4:00 PM EST
        now_est = datetime.now(tz)
        close_est = now_est.replace(hour=16, minute=0, second=0, microsecond=0)
        time_diff = close_est - now_est
        seconds_to_go = max(time_diff.total_seconds(), 1) # Avoid division by zero
        T = (seconds_to_go / (3600 * 24)) / 365 
        
        # 3. Interest Rate (Default to 5% if ^IRX fails)
        try:
            r = yf.Ticker("^IRX").fast_info.last_price / 100 
        except:
            r = 0.05
        
        # 4. Fetch Option Chain
        today_str = now_est.strftime('%Y-%m-%d')
        expirations = ticker.options
        target_expiry = today_str if today_str in expirations else expirations[0]
        chain = ticker.option_chain(target_expiry)

        # 5. Delta Filtering Logic
        def find_strike(df, target, opt_type):
            # Calculate delta for each strike using its own Implied Volatility
            df = df.copy()
            df['calc_delta'] = df.apply(lambda row: calculate_delta(
                S, row['strike'], T, r, row['impliedVolatility'], opt_type
            ), axis=1)
            # Find the strike where calculated delta is closest to target
            idx = (df['calc_delta'] - target).abs().idxmin()
            return float(df.loc[idx, 'strike'])

        short_put = find_strike(chain.puts, -TARGET_DELTA, 'put')
        short_call = find_strike(chain.calls, TARGET_DELTA, 'call')

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
if st.button('🚀 Calculate 0.15 Delta Strikes'):
    with st.spinner('Running Black-Scholes Model...'):
        data = get_delta_data()
    
    if "error" in data:
        st.error(f"Data Error: {data['error']}")
    else:
        st.metric("XSP Spot Price", f"${data['spot']:.2f}")
        st.write(f"**Yahoo Timestamp:** {data['ts'].strftime('%I:%M:%S %p %Z')}")
        
        st.divider()
        st.write(f"### 🎯 Strategy Strikes (Target: {TARGET_DELTA} Delta)")
        
        strike_df = pd.DataFrame({
            "Leg": ["Long Put (Buy)", "Short Put (Sell)", "Short Call (Sell)", "Long Call (Buy)"],
            "Strike": [f"{v:.2f}" for v in data['strikes'].values()]
        })
        st.table(strike_df)
        st.caption(f"Calculated for {data['expiry']} expiration using live IV and time-decay.")
