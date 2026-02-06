import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import time

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Pro Crypto Dashboard", layout="wide")

# --- SIDEBAR SETTINGS ---
st.sidebar.header("⚙️ Settings")
# Default list matches your interest in BTC, XRP, Gold
default_symbols = "BTC-USD, XRP-USD, GC=F, SI=F"
user_symbols = st.sidebar.text_input("Watchlist (comma separated)", default_symbols)
watchlist = [s.strip().upper() for s in user_symbols.split(",")]
refresh_rate = st.sidebar.slider("Auto-Refresh (Seconds)", 30, 300, 60)

# --- MAIN HEADER ---
st.title("📈 Live Market Intelligence")
st.caption(f"Last Global Sync: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# --- ANALYSIS ENGINE ---
def get_market_data(symbol):
    try:
        # 1. Download 1 month of data to ensure EMA 200 is accurate
        # We use '1mo' period and '30m' interval as requested
        df = yf.download(symbol, period="1mo", interval="30m", progress=False)
        
        # 2. Data Cleaning (Fix for yfinance Multi-Index issue)
        if df.empty: return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        # Ensure we have enough data points (need 200 for EMA200)
        if len(df) < 200: return None

        # 3. Calculate Indicators
        df['EMA100'] = df['Close'].ewm(span=100, adjust=False).mean()
        df['EMA200'] = df['Close'].ewm(span=200, adjust=False).mean()
        
        # 4. Determine Status
        curr = df.iloc[-1]
        price = curr['Close']
        ema100 = curr['EMA100']
        ema200 = curr['EMA200']
        
        # Trend Logic: Bullish if above BOTH EMAs
        if price > ema100 and price > ema200:
            trend = "🟢 BULLISH"
            signal = "Look for Longs"
        elif price < ema100 and price < ema200:
            trend = "🔴 BEARISH"
            signal = "Look for Shorts"
        else:
            trend = "🟡 CHOPPY / NEUTRAL"
            signal = "Wait"
            
        return {
            "price": price,
            "trend": trend,
            "signal": signal,
            "ema100": ema100,
            "ema200": ema200
        }
    except Exception as e:
        return None

# --- DASHBOARD LAYOUT ---
# Create a grid of columns
cols = st.columns(len(watchlist))

for i, symbol in enumerate(watchlist):
    with cols[i]:
        st.subheader(symbol)
        with st.spinner("Scanning..."):
            data = get_market_data(symbol)
        
        if data:
            # Display Metric
            st.metric(label="Price (30m)", value=f"${data['price']:,.2f}")
            
            # Display Trend & Signal
            st.markdown(f"**Trend:** {data['trend']}")
            st.info(f"**Action:** {data['signal']}")
            
            # Technical Details (Collapsible)
            with st.expander("Technical Levels"):
                st.write(f"EMA 100: ${data['ema100']:,.2f}")
                st.write(f"EMA 200: ${data['ema200']:,.2f}")
                if data['trend'] == "🟢 BULLISH":
                    st.success("Price is above Long-Term Trend")
                elif data['trend'] == "🔴 BEARISH":
                    st.error("Price is below Long-Term Trend")
        else:
            st.warning("Loading data...")

# --- AUTO-REFRESH LOOP ---
# This button allows manual refresh
if st.button("🔄 Refresh Now"):
    st.rerun()

# This keeps the app updating automatically
time.sleep(refresh_rate)
st.rerun()
