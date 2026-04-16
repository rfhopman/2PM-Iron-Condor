import streamlit as st
import pandas as pd
from datetime import datetime
import pytz
import yfinance as yf

# App Setup
st.set_page_config(page_title="XSP 0DTE Strategy", layout="centered") 
st.title("📊 XSP 0DTE Iron Condor")

SYMBOL = "^XSP"
WIDTH = 5.00

@st.cache_data(ttl=30)
def get_data():
    try:
        ticker = yf.Ticker(SYMBOL)
        
        # Pulling 1 day of 1-minute data is the most reliable way to get 
        # both the latest price and the actual trade timestamp
        hist = ticker.history(period="1d", interval="1m")
        
        if hist.empty:
            return {"error": "No price data found. Is the market open?"}
        
        # Get the very last row
        latest_row = hist.iloc[-1]
        spot_price = float(latest_row['Close'])
        
        # Get the timestamp from the index (the time of the last 1m candle)
        tz = pytz.timezone('US/Eastern')
        yahoo_ts = hist.index[-1].astimezone(tz)

        # 0DTE Expiry Logic
        expirations = ticker.options
        today_str = datetime.now(tz).strftime('%Y-%m-%d')
        target_expiry = today_str if today_str in expirations else expirations[0]

        # Fetch Option Chain
        chain = ticker.option_chain(target_expiry)
        
        # Strike Selection (.15 Delta Approx: ~1.5% OTM)
        short_put = float(chain.puts[chain.puts['strike'] <= spot_price * 0.985].iloc[-1]['strike'])
        short_call = float(chain.calls[chain.calls['strike'] >= spot_price * 1.015].iloc[0]['strike'])

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
    with st.spinner('Updating from Yahoo Finance...'):
        data = get_data()
    
    if "error" in data:
        st.error(f"Issue Found: {data['error']}")
        st.info("Yahoo might be limiting the cloud connection. Try again in 30-60 seconds.")
    else:
        st.success("Data Updated")
        
        # 1. Price and Time (Vertical stack for mobile)
        st.metric("XSP Spot Price", f"${data['spot']:.2f}")
        st.write(f"**Yahoo Timestamp:** {data['ts'].strftime('%I:%M:%S %p %Z')}")
        st.write(f"**Target Expiry:** {data['expiry']}")
        
        st.divider()

        # 2. Strikes Data (Large table below for easy reading)
        st.write("### 🎯 Selected Strikes")
        
        strike_table = pd.DataFrame({
            "Leg": ["Long Put (Buy)", "Short Put (Sell)", "Short Call (Sell)", "Long Call (Buy)"],
            "Strike": [
                f"{data['strikes']['Long Put']:.2f}",
                f"{data['strikes']['Short Put']:.2f}",
                f"{data['strikes']['Short Call']:.2f}",
                f"{data['strikes']['Long Call']:.2f}"
            ]
        })
        
        st.table(strike_table)
        st.caption("Strategy: 0DTE Iron Condor | Selection: ~0.15 Delta | Width: $5.00")
