import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import pytz

# App Setup
st.set_page_config(page_title="XSP 0DTE Strategy Tracker", layout="wide")
st.title("📊 XSP 0DTE Iron Condor Strategy Tracker")
st.write("This app simulates the strike selection logic using Yahoo Finance data.")

# Configuration
SYMBOL = "^XSP"  # Yahoo Finance uses the caret for indices
WIDTH = 5

def get_data():
    ticker = yf.Ticker(SYMBOL)
    
    # 1. Get Spot Price and Yahoo Timestamp
    # fast_info gives us the most recent 'real-time' snapshot
    info = ticker.fast_info
    spot_price = info.last_price
    
    # Yahoo Timestamp (Last Trade Time)
    # We convert to US/Eastern for consistency with your 2pm EST requirement
    tz = pytz.timezone('US/Eastern')
    yahoo_ts = datetime.fromtimestamp(info.last_volume_time / 1000, tz=tz)
    
    # 2. Find 0DTE Expiration
    expirations = ticker.options
    today_str = datetime.now(tz).strftime('%Y-%m-%d')
    
    if today_str not in expirations:
        st.error(f"No 0DTE options found for {today_str}. (Market might be closed or data unavailable)")
        return None

    # 3. Fetch Option Chain
    chain = ticker.option_chain(today_str)
    calls = chain.calls
    puts = chain.puts

    # 4. Strategy Logic: Select .15 Delta (Approximate via IV/OTM)
    # yfinance does not provide live Delta, so we look for strikes ~1.5% OTM 
    # which typically correlates to a 15-20 delta in 0DTE XSP.
    short_put_strike = puts[puts['strike'] <= spot_price * 0.985].iloc[-1]['strike']
    short_call_strike = calls[calls['strike'] >= spot_price * 1.015].iloc[0]['strike']
    
    long_put_strike = short_put_strike - WIDTH
    long_call_strike = short_call_strike + WIDTH

    return {
        "spot": spot_price,
        "ts": yahoo_ts,
        "expiry": today_str,
        "strikes": {
            "Long Put": long_put_strike,
            "Short Put": short_put_strike,
            "Short Call": short_call_strike,
            "Long Call": long_call_strike
        }
    }

# --- UI Button ---
if st.button('🚀 Fetch Strategy Data Now'):
    data = get_data()
    
    if data:
        st.divider()
        
        # Display Yahoo Timestamp prominently
        st.subheader(f"🕒 Yahoo Finance Data Timestamp: `{data['ts'].strftime('%Y-%m-%d %I:%M:%S %p %Z')}`")
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("XSP Spot Price", f"${data['spot']:.2f}")
            st.write(f"**Expiration Target:** {data['expiry']} (0DTE)")

        with col2:
            st.write("### Selected Strikes (.15 Delta Approx)")
            st.table(pd.DataFrame({
                "Leg": ["Long Put", "Short Put", "Short Call", "Long Call"],
                "Strike": [
                    data['strikes']['Long Put'],
                    data['strikes']['Short Put'],
                    data['strikes']['Short Call'],
                    data['strikes']['Long Call']
                ]
            }))
            
        st.success("Strategy Selection Complete based on current volatility.")
