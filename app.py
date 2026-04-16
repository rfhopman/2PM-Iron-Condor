import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import pytz

# App Setup
st.set_page_config(page_title="XSP 0DTE Strategy Tracker", layout="wide")
st.title("📊 XSP 0DTE Iron Condor Strategy Tracker")

SYMBOL = "^XSP" 
WIDTH = 5

def get_data():
    # Per the error message, we let yfinance handle its own session
    ticker = yf.Ticker(SYMBOL)
    
    try:
        # Use history to get the most recent price point safely
        # This is often more resilient than .info or .basic_info
        hist = ticker.history(period="1d", interval="1m")
        if hist.empty:
            st.error("Could not fetch price history. Market might be closed.")
            return None
            
        spot_price = hist['Close'].iloc[-1]
        
        # Get Yahoo's internal timestamp from the data itself
        tz = pytz.timezone('US/Eastern')
        yahoo_ts = hist.index[-1].astimezone(tz)
        
        # 0DTE logic
        expirations = ticker.options
        today_str = datetime.now(tz).strftime('%Y-%m-%d')
        
        if today_str not in expirations:
            # Fallback for weekends/evenings
            target_expiry = expirations[0]
            st.warning(f"0DTE not available. Showing next expiry: {target_expiry}")
        else:
            target_expiry = today_str

        # Fetch Option Chain
        chain = ticker.option_chain(target_expiry)
        
        # Delta selection logic (~1.5% OTM)
        short_put_strike = chain.puts[chain.puts['strike'] <= spot_price * 0.985].iloc[-1]['strike']
        short_call_strike = chain.calls[chain.calls['strike'] >= spot_price * 1.015].iloc[0]['strike']
        
        return {
            "spot": spot_price,
            "ts": yahoo_ts,
            "expiry": target_expiry,
            "strikes": {
                "Long Put": short_put_strike - WIDTH,
                "Short Put": short_put_strike,
                "Short Call": short_call_strike,
                "Long Call": short_call_strike + WIDTH
            }
        }
    except Exception as e:
        st.error(f"Data retrieval error: {e}")
        return None

# --- UI ---
if st.button('🚀 Fetch Strategy Data Now'):
    with st.spinner('Querying Yahoo Finance (Using curl_cffi)...'):
        data = get_data()
    
    if data:
        st.divider()
        st.subheader(f"🕒 Yahoo Trade Timestamp: `{data['ts'].strftime('%I:%M:%S %p %Z')}`")
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("XSP Spot Price", f"${data['spot']:.2f}")
            st.write(f"**Calculated for:** {data['expiry']}")

        with col2:
            st.write("### Strategy Strikes")
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
