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
TARGET_DELTA_SCALED = 15.0 

def calculate_delta(S, K, T, r, sigma, option_type='call'):
    """Calculates Black-Scholes Delta (decimal)."""
    if T <= 0 or sigma <= 0: return 0
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    if option_type == 'call':
        return norm.cdf(d1)
    else:
        return norm.cdf(d1) - 1

@st.cache_data(ttl=5) # Reduced cache to keep T and R fresh
def get_delta_data():
    try:
        ticker = yf.Ticker(SYMBOL)
        
        # 1. Get Spot Price & Timestamp
        hist = ticker.history(period="1d", interval="1m")
        if hist.empty: return {"error": "Market data currently unavailable."}
        
        S = float(hist['Close'].iloc[-1])
        tz = pytz.timezone('US/Eastern')
        yahoo_ts = hist.index[-1].astimezone(tz)

        # 2. DYNAMIC TIME TO EXPIRY (T)
        # Calculated from the EXACT MOMENT the script runs until 4:00 PM EST
        now_est = datetime.now(tz)
        close_est = now_est.replace(hour=16, minute=0, second=0, microsecond=0)
        
        # Total seconds remaining in the trading day
        seconds_remaining = (close_est - now_est).total_seconds()
        
        # T must be in years. We floor it at 30 mins (1800s) to maintain Greek stability 
        # as Gamma spikes toward infinity at exactly 0 seconds.
        seconds_to_go = max(seconds_remaining, 1800) 
        T = (seconds_to_go / (3600 * 24)) / 365 
        
        # 3. DYNAMIC RISK-FREE RATE (r)
        # Pulling the 13-week T-Bill yield (^IRX)
        try:
            irx = yf.Ticker("^IRX")
            # Divide by 100 because ^IRX is quoted as a percentage (e.g., 5.3 = 0.053)
            r = irx.fast_info.last_price / 100
            if np.isnan(r) or r <= 0: r = 0.05
        except:
            r = 0.05 # Fallback
        
        # 4. Fetch Option Chain
        today_str = now_est.strftime('%Y-%m-%d')
        expirations = ticker.options
        target_expiry = today_str if today_str in expirations else expirations[0]
        chain = ticker.option_chain(target_expiry)

        # 5. Delta Filtering Logic
        def find_strike_info(df, target_scaled, opt_type):
            df = df.copy()
            df = df[df['impliedVolatility'] > 0.01]
            
            # Apply Black-Scholes using Dynamic T and Dynamic r
            df['calc_delta_scaled'] = df.apply(lambda row: calculate_delta(
                S, row['strike'], T, r, row['impliedVolatility'], opt_type
            ) * 100, axis=1)
            
            idx = (df['calc_delta_scaled'] - target_scaled).abs().idxmin()
            return float(df.loc[idx, 'strike']), float(df.loc[idx, 'calc_delta_scaled']), float(df.loc[idx, 'impliedVolatility'])

        short_put_strike, short_put_delta, p_iv = find_strike_info(chain.puts, -TARGET_DELTA_SCALED, 'put')
        short_call_strike, short_call_delta, c_iv = find_strike_info(chain.calls, TARGET_DELTA_SCALED, 'call')

        # Calculate Longs
        lp_strike = short_put_strike - WIDTH
        lc_strike = short_call_strike + WIDTH
        
        lp_delta = calculate_delta(S, lp_strike, T, r, p_iv, 'put') * 100
        lc_delta = calculate_delta(S, lc_strike, T, r, c_iv, 'call') * 100

        return {
            "spot": S, 
            "ts": yahoo_ts, 
            "expiry": target_expiry,
            "r_rate": r * 100, # Back to percentage for display
            "time_left_mins": seconds_to_go / 60,
            "data": [
                {"Leg": "Long Put (Buy)", "Strike": lp_strike, "Delta": lp_delta},
                {"Leg": "Short Put (Sell)", "Strike": short_put_strike, "Delta": short_put_delta},
                {"Leg": "Short Call (Sell)", "Strike": short_call_strike, "Delta": short_call_delta},
                {"Leg": "Long Call (Buy)", "Strike": lc_strike, "Delta": lc_delta}
            ]
        }
    except Exception as e:
        return {"error": str(e)}

# --- UI DISPLAY ---
if st.button('🚀 Run Strategy Analysis'):
    with st.spinner('Fetching Dynamic R-Rate and Calculating T-Expiry...'):
        result = get_delta_data()
    
    if "error" in result:
        st.error(f"Data Error: {result['error']}")
    else:
        # Displaying the dynamic inputs
        st.metric("XSP Spot Price", f"${result['spot']:.2f}")
        
        c1, c2 = st.columns(2)
        c1.write(f"**Risk-Free Rate:** {result['r_rate']:.3f}%")
        c2.write(f"**Mins to Expiry:** {result['time_left_mins']:.1f}")
        
        st.divider()
        st.write(f"### 🎯 Strategy Strikes (Target ±{TARGET_DELTA_SCALED})")
        
        df = pd.DataFrame(result['data'])
        df['Strike'] = df['Strike'].map('{:,.2f}'.format)
        df['Delta'] = df['Delta'].map('{:,.2f}'.format)
        
        st.table(df)
        st.caption(f"Trade calculated at {datetime.now().strftime('%H:%M:%S')} EST for {result['expiry']} expiry.")
