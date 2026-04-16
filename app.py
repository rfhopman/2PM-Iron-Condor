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
        now_est = datetime.now(tz)
        close_est = now_est.replace(hour=16, minute=0, second=0, microsecond=0)
        time_diff = close_est - now_est
        seconds_to_go = max(time_diff.total_seconds(), 1)
        T = (seconds_to_go / (3600 * 24)) / 365 
        
        # 3. Interest Rate
        try:
            r = yf.Ticker("^IRX").fast_info.last_price / 100 
        except:
            r = 0.05
        
        # 4. Fetch Option Chain
        today_str = now_est.strftime('%Y-%m-%d')
        expirations = ticker.options
        target_expiry = today_str if today_str in expirations else expirations[0]
        chain = ticker.option_chain(target_expiry)

        # 5. Delta Filtering Logic (Returns Strike and the Delta found)
        def find_strike_info(df, target, opt_type):
            df = df.copy()
            # Handle cases where IV might be missing or zero
            df = df[df['impliedVolatility'] > 0]
            
            df['calc_delta'] = df.apply(lambda row: calculate_delta(
                S, row['strike'], T, r, row['impliedVolatility'], opt_type
            ), axis=1)
            
            idx = (df['calc_delta'] - target).abs().idxmin()
            return float(df.loc[idx, 'strike']), float(df.loc[idx, 'calc_delta'])

        short_put_strike, short_put_delta = find_strike_info(chain.puts, -TARGET_DELTA, 'put')
        short_call_strike, short_call_delta = find_strike_info(chain.calls, TARGET_DELTA, 'call')

        # Calculate Longs (we still calculate their deltas for the table)
        long_put_strike = short_put_strike - WIDTH
        long_call_strike = short_call_strike + WIDTH
        
        # Estimate deltas for long legs
        # Note: we use the short's IV as a proxy if the long's IV is messy
        lp_delta = calculate_delta(S, long_put_strike, T, r, 0.2, 'put') # 0.2 is a dummy IV placeholder
        lc_delta = calculate_delta(S, long_call_strike, T, r, 0.2, 'call')

        return {
            "spot": S, "ts": yahoo_ts, "expiry": target_expiry,
            "data": [
                {"Leg": "Long Put (Buy)", "Strike": long_put_strike, "Delta": lp_delta},
                {"Leg": "Short Put (Sell)", "Strike": short_put_strike, "Delta": short_put_delta},
                {"Leg": "Short Call (Sell)", "Strike": short_call_strike, "Delta": short_call_delta},
                {"Leg": "Long Call (Buy)", "Strike": long_call_strike, "Delta": lc_delta}
            ]
        }
    except Exception as e:
        return {"error": str(e)}

# --- UI DISPLAY ---
if st.button('🚀 Calculate Strikes & Show Deltas'):
    with st.spinner('Calculating Greeks...'):
        result = get_delta_data()
    
    if "error" in result:
        st.error(f"Data Error: {result['error']}")
    else:
        st.metric("XSP Spot Price", f"${result['spot']:.2f}")
        st.write(f"**Yahoo Timestamp:** {result['ts'].strftime('%I:%M:%S %p %Z')}")
        
        st.divider()
        st.write(f"### 🎯 Strategy Strikes (Target: ±{TARGET_DELTA})")
        
        # Formatting for the table
        display_df = pd.DataFrame(result['data'])
        display_df['Strike'] = display_df['Strike'].map('{:,.2f}'.format)
        display_df['Delta'] = display_df['Delta'].map('{:,.4f}'.format)
        
        st.table(display_df)
        st.caption(f"Calculated for {result['expiry']} using Black-Scholes and live Implied Volatility.")
