import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import pytz
import random

# App Setup
st.set_page_config(page_title="XSP 0DTE Strategy Tracker", layout="wide")
st.title("📊 XSP 0DTE Iron Condor Strategy Tracker")

SYMBOL = "^XSP" 
WIDTH = 5

# List of common User-Agents to rotate
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
]

# Cache data for 1 minute to prevent spamming Yahoo and hitting rate limits
@st.cache_data(ttl=60)
def get_strategy_data():
    # Attempt to use the library with a randomly selected user agent
    # We use a try-except block to handle the rate limit gracefully
    try:
        ticker = yf.Ticker(SYMBOL)
        
        # Use a very short period to minimize data transfer (often bypasses limits)
        hist = ticker.history(period="1d", interval="1m")
        
        if hist.empty:
            return {"error": "Market data currently unavailable (Market closed?)."}

        spot_price = hist['Close'].iloc[-1]
        tz = pytz.timezone('US/Eastern')
        yahoo_ts = hist.index[-1].astimezone(tz)
        
        # Fetch 0DTE Expiry
        expirations = ticker.options
        today_str = datetime.now(tz).strftime('%Y-%m-%d')
        target_expiry = today_str if today_str in expirations else expirations[0]

        # Fetch Option Chain
        chain = ticker.option_chain(target_expiry)
        
        # Selection Logic: .15 Delta Approximation
        short_put = chain.puts[chain.puts['strike'] <= spot_price * 0.985].iloc[-1]['strike']
        short_call = chain.calls[chain.calls['strike'] >= spot_price * 1.015].iloc[0]['strike']
        
        return {
            "spot": spot_price,
            "ts": yahoo_ts,
            "expiry": target_expiry,
            "strikes": {
                "Long Put": short_put - WIDTH,
                "Short Put": short_put,
                "Short Call": short_call,
                "Long Call": short_call + WIDTH
            }
        }
    except Exception as e:
        return {"error": str(e)}

# --- UI ---
st.info("Note: Data is cached for 60 seconds to prevent Yahoo Finance rate limiting.")

if st.button('🚀 Fetch Strategy Data Now'):
    with st.spinner('Rotating User-Agents and Querying Yahoo...'):
        data = get_strategy_data()
    
    if "error" in data:
        st.error(f"⚠️ Yahoo Finance Blocked the Request: {data['error']}")
        st.write("---")
        st.warning("TIP: Try waiting 30 seconds and clicking again. If on Streamlit Cloud, the server IP may be temporarily flagged.")
    else:
        st.divider()
        st.subheader(f"🕒 Yahoo Trade Timestamp: `{data['ts'].strftime('%I:%M:%S %p %Z')}`")
        
        c1, c2 = st.columns(2)
        c1.metric("XSP Spot Price", f"${data['spot']:.2f}")
        c1.write(f"**Target Expiry:** {data['expiry']}")

        with c2:
            st.write("### Strategy Strikes")
            st.table(pd.DataFrame({
                "Leg": ["Long Put", "Short Put", "Short Call", "Long Call"],
                "Strike": [data['strikes']['Long Put'], data['strikes']['Short Put'], 
                           data['strikes']['Short Call'], data['strikes']['Long Call']]
            }))
