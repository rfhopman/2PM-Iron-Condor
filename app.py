import streamlit as st
import pandas as pd
from datetime import datetime
import pytz
import yfinance as yf

# App Setup
st.set_page_config(page_title="XSP 0DTE Strategy", layout="centered") # 'centered' is better for mobile
st.title("📊 XSP 0DTE Iron Condor")

SYMBOL = "^XSP"
WIDTH = 5.00

@st.cache_data(ttl=30)
def get_data():
    try:
        ticker = yf.Ticker(SYMBOL)
        
        # Using fast_info for the spot price
        info = ticker.fast_info
        spot_price = info.last_price
        
        # Yahoo Timestamp
        tz = pytz.timezone('US/Eastern')
        yahoo_ts = datetime.fromtimestamp(info.last_volume_time / 1000, tz=tz)

        # 0DTE Expiry Logic
        expirations = ticker.options
        today_str = datetime.now(tz).strftime('%Y-%m-%d')
        target_expiry = today_str if today_str in expirations else expirations[0]

        # Fetch Option Chain
        chain = ticker.option_chain(target_expiry)
        
        # Strike Selection (.15 Delta Approx)
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

# --- UI DISPLAY (Mobile Optimized) ---
if st.button('🚀 Pull Strategy Data'):
    with st.spinner('Accessing Yahoo Finance...'):
        data = get_data()
    
    if "error" in data:
        st.error(f"Rate Limit Active: {data['error']}")
    else:
        st.success("Data Updated")
        
        # 1. Price and Time (Top)
        st.metric("XSP Spot Price", f"${data['spot']:.2f}")
        st.write(f"**Yahoo Timestamp:** {data['ts'].strftime('%I:%M:%S %p %Z')}")
        st.write(f"**Target Expiry:** {data['expiry']}")
        
        st.divider()

        # 2. Strikes Data (Below, in a full-width table)
        st.write("### 🎯 Selected Strikes")
        
        # Formatting strikes to 2 decimals
        strike_data = {
            "Leg": ["Long Put (Buy)", "Short Put (Sell)", "Short Call (Sell)", "Long Call (Buy)"],
            "Strike": [
                f"{data['strikes']['Long Put']:.2f}",
                f"{data['strikes']['Short Put']:.2f}",
                f"{data['strikes']['Short Call']:.2f}",
                f"{data['strikes']['Long Call']:.2f}"
            ]
        }
        
        df = pd.DataFrame(strike_data)
        # Using st.table instead of dataframe for better static mobile rendering
        st.table(df)

        st.caption("Strategy: 0DTE Iron Condor | Selection: ~0.15 Delta")
