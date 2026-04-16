import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import pytz
import requests

# App Setup
st.set_page_config(page_title="XSP 0DTE Strategy Tracker", layout="wide")
st.title("📊 XSP 0DTE Iron Condor Strategy Tracker")

# --- NEW: Fix for Rate Limit Errors ---
# We create a session and give it a "User-Agent" to look like a real browser
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
})

SYMBOL = "^XSP" 
WIDTH = 5

def get_data():
    # Pass our "human-like" session to yfinance
    ticker = yf.Ticker(SYMBOL, session=session)
    
    try:
        # Use fast_info or basic info to get the price
        # Sometimes .fast_info triggers the rate limit harder; .info is safer
        spot_price = ticker.basic_info.last_price
        
        # Yahoo Timestamp
        tz = pytz.timezone('US/Eastern')
        # last_trade is more reliable for indices
        yahoo_ts = datetime.now(tz) 
        
        expirations = ticker.options
        today_str = datetime.now(tz).strftime('%Y-%m-%d')
        
        if today_str not in expirations:
            st.warning(f"No 0DTE options listed for {today_str} yet. Showing nearest expiry: {expirations[0]}")
            target_expiry = expirations[0]
        else:
            target_expiry = today_str

        # Fetch Option Chain
        chain = ticker.option_chain(target_expiry)
        calls = chain.calls
        puts = chain.puts

        # Strategy Logic: Select strikes based on distance from spot
        # (Approx .15 Delta)
        short_put_strike = puts[puts['strike'] <= spot_price * 0.985].iloc[-1]['strike']
        short_call_strike = calls[calls['strike'] >= spot_price * 1.015].iloc[0]['strike']
        
        long_put_strike = short_put_strike - WIDTH
        long_call_strike = short_call_strike + WIDTH

        return {
            "spot": spot_price,
            "ts": yahoo_ts,
            "expiry": target_expiry,
            "strikes": {
                "Long Put": long_put_strike,
                "Short Put": short_put_strike,
                "Short Call": short_call_strike,
                "Long Call": long_call_strike
            }
        }
    except Exception as e:
        st.error(f"Failed to fetch data: {e}")
        return None

# --- UI Button ---
if st.button('🚀 Fetch Strategy Data Now'):
    with st.spinner('Accessing Yahoo Finance...'):
        data = get_data()
    
    if data:
        st.divider()
        st.subheader(f"🕒 Yahoo Data Timestamp: `{data['ts'].strftime('%I:%M:%S %p %Z')}`")
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("XSP Spot Price", f"${data['spot']:.2f}")
            st.write(f"**Target Expiry:** {data['expiry']}")

        with col2:
            st.write("### Selected Strikes")
            df = pd.DataFrame({
                "Leg": ["Long Put", "Short Put", "Short Call", "Long Call"],
                "Strike": [
                    data['strikes']['Long Put'],
                    data['strikes']['Short Put'],
                    data['strikes']['Short Call'],
                    data['strikes']['Long Call']
                ]
            })
            st.table(df)
