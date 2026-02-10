import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
import time

st.set_page_config(page_title="Pro AI Trader Ultimate", layout="wide")

# --- CUSTOM CSS ---
st.markdown("""
<style>
    .stMetric {background-color: #0e1117; border: 1px solid #303030; padding: 10px; border-radius: 5px;}
    .watchlist-card {background-color: #1c1c1c; padding: 10px; border-radius: 5px; margin-bottom: 5px; border-left: 5px solid #555;}
    .buy-signal {border-left: 5px solid #00ff00 !important;}
    .sell-signal {border-left: 5px solid #ff0000 !important;}
</style>
""", unsafe_allow_html=True)

# --- 1. DATA ENGINE ---
def get_data(symbol):
    try:
        df_5m = yf.download(symbol, period="5d", interval="5m", progress=False)
        df_1h = yf.download(symbol, period="1mo", interval="1h", progress=False)
        df_daily = yf.download(symbol, period="1y", interval="1d", progress=False) # Added for Pivot Points
        
        if df_5m.empty or df_1h.empty: return None

        if isinstance(df_5m.columns, pd.MultiIndex): df_5m.columns = df_5m.columns.get_level_values(0)
        if isinstance(df_1h.columns, pd.MultiIndex): df_1h.columns = df_1h.columns.get_level_values(0)
        if isinstance(df_daily.columns, pd.MultiIndex): df_daily.columns = df_daily.columns.get_level_values(0)

        data = {}
        data['5m'] = df_5m
        data['15m'] = df_5m.resample('15min').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}).dropna()
        data['30m'] = df_5m.resample('30min').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}).dropna()
        data['1h'] = df_1h
        data['4h'] = df_1h.resample('4h').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}).dropna()
        data['Daily'] = df_daily # For Swing logic
        
        return data
    except:
        return None

# --- 2. INDICATORS & PIVOTS ---
def add_indicators(df):
    if len(df) < 50: return df
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['EMA200'] = df['Close'].ewm(span=200, adjust=False).mean()
    
    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-9)
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # ATR
    df['ATR'] = (df['High'] - df['Low']).rolling(14).mean()
    return df

def get_pivots(df_daily):
    # Standard Pivot Points Calculation
    last_day = df_daily.iloc[-2] # Use yesterday's data
    P = (last_day['High'] + last_day['Low'] + last_day['Close']) / 3
    R1 = (2 * P) - last_day['Low']
    S1 = (2 * P) - last_day['High']
    return P, R1, S1

# --- 3. PATTERN RECOGNITION ---
def get_candle_pattern(df):
    if len(df) < 3: return "Normal"
    row = df.iloc[-1]
    prev = df.iloc[-2]
    body = abs(row['Open'] - row['Close'])
    
    if (row['Close'] > prev['Open']) and (row['Open'] < prev['Close']) and (row['Close'] > prev['High']):
        return "🟢 Engulfing"
    elif (min(row['Open'], row['Close']) - row['Low']) > (2 * body):
        return "🔨 Hammer"
    return "Normal"

# --- 4. SIGNAL GENERATOR ---
def generate_signal(df, timeframe):
    curr = df.iloc[-1]
    trend = "BULL" if curr['Close'] > curr['EMA200'] else "BEAR"
    
    # Relaxed Logic: We don't need "Strong Buy" for everything
    signal = "NEUTRAL"
    if trend == "BULL" and curr['RSI'] < 60: signal = "BUY" # Buying dips
    if trend == "BEAR" and curr['RSI'] > 40: signal = "SELL" # Selling rallies
    if trend == "BULL" and curr['RSI'] < 30: signal = "STRONG BUY"
    if trend == "BEAR" and curr['RSI'] > 70: signal = "STRONG SELL"

    return {"Signal": signal, "RSI": round(curr['RSI'], 1), "Price": curr['Close'], "ATR": curr['ATR']}

# --- SIDEBAR & WATCHLIST ---
st.sidebar.header("⚙️ Settings")
symbol_input = st.sidebar.text_input("Main Asset", "GC=F").upper()

if st.sidebar.button("🔄 Refresh Now"):
    st.rerun()

st.sidebar.divider()
st.sidebar.subheader("👀 Live Watchlist")
watchlist = ["GC=F", "SI=F", "BTC-USD", "CL=F", "DX-Y"]

for w_sym in watchlist:
    try:
        w_df = yf.download(w_sym, period="2d", interval="1h", progress=False)
        if isinstance(w_df.columns, pd.MultiIndex): w_df.columns = w_df.columns.get_level_values(0)
        
        if not w_df.empty:
            w_curr = w_df.iloc[-1]
            w_ema = w_df['Close'].ewm(span=200, adjust=False).mean().iloc[-1]
            w_trend = "🟢" if w_curr['Close'] > w_ema else "🔴"
            
            # CSS Logic for Side Border
            css_class = "buy-signal" if w_curr['Close'] > w_ema else "sell-signal"
            
            st.sidebar.markdown(f"""
            <div class="watchlist-card {css_class}">
                <b>{w_sym}</b>: {w_trend} (${w_curr['Close']:,.2f})
            </div>
            """, unsafe_allow_html=True)
    except:
        pass

# --- MAIN DASHBOARD ---
st.title(f"📊 Pro Trading Desk: {symbol_input}")
data = get_data(symbol_input)

if data:
    current_price = data['5m'].iloc[-1]['Close']
    pivot, r1, s1 = get_pivots(data['Daily'])
    
    # Header Metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Live Price", f"${current_price:,.2f}")
    c2.metric("Pivot Point", f"${pivot:,.2f}")
    c3.metric("Resistance (R1)", f"${r1:,.2f}")
    c4.metric("Support (S1)", f"${s1:,.2f}")

    # --- 1. MULTI-TIMEFRAME GRID ---
    st.subheader("1. Multi-Timeframe Scan")
    cols = st.columns(5)
    tf_signals = {}
    
    timeframes = ['5m', '15m', '30m', '1h', '4h']
    for i, tf in enumerate(timeframes):
        df = add_indicators(data[tf])
        sig = generate_signal(df, tf)
        pattern = get_candle_pattern(df)
        tf_signals[tf] = sig
        
        color = "green" if "BUY" in sig['Signal'] else "red" if "SELL" in sig['Signal'] else "gray"
        
        cols[i].markdown(f"**{tf}**")
        cols[i].markdown(f"<span style='color:{color}; font-weight:bold'>{sig['Signal']}</span>", unsafe_allow_html=True)
        cols[i].caption(f"Pattern: {pattern}")
        cols[i].caption(f"RSI: {sig['RSI']}")

    st.divider()

    # --- 2. STRATEGY GENERATOR ---
    st.subheader("2. AI Strategy Setups")
    strat_c1, strat_c2, strat_c3 = st.columns(3)
    
    # --- SCALPING (5m/15m) ---
    with strat_c1:
        st.markdown("### ⚡ Scalp (Quick)")
        s_sig = tf_signals['5m']
        if "BUY" in s_sig['Signal']:
            st.success("LONG SIGNAL")
            st.write(f"Entry: ${current_price:,.2f}")
            st.write(f"TP: ${current_price + (s_sig['ATR']*1.5):,.2f}")
            st.write(f"SL: ${current_price - (s_sig['ATR']*1.0):,.2f}")
        elif "SELL" in s_sig['Signal']:
            st.error("SHORT SIGNAL")
            st.write(f"Entry: ${current_price:,.2f}")
            st.write(f"TP: ${current_price - (s_sig['ATR']*1.5):,.2f}")
            st.write(f"SL: ${current_price + (s_sig['ATR']*1.0):,.2f}")
        else:
            st.info("Wait for Momentum")

    # --- INTRADAY (1H + Pivot) ---
    with strat_c2:
        st.markdown("### 📅 Intraday (Levels)")
        i_sig = tf_signals['1h']
        dist_to_s1 = abs(current_price - s1)
        dist_to_r1 = abs(current_price - r1)
        
        # Intraday logic checks distance to Pivots
        if "BUY" in i_sig['Signal'] and current_price > pivot:
            st.success("LONG (Trend + Pivot)")
            st.write(f"Target: ${r1:,.2f}")
            st.write(f"Stop: ${pivot:,.2f}")
        elif "SELL" in i_sig['Signal'] and current_price < pivot:
            st.error("SHORT (Trend + Pivot)")
            st.write(f"Target: ${s1:,.2f}")
            st.write(f"Stop: ${pivot:,.2f}")
        else:
            st.warning("Price in Range (Wait)")
            st.caption(f"Needs breakout of ${pivot:,.2f}")

    # --- SWING (4H + Trend) ---
    with strat_c3:
        st.markdown("### 🌊 Swing (Multi-Day)")
        w_sig = tf_signals['4h']
        if "BUY" in w_sig['Signal']:
            st.success("POSITION LONG")
            st.write(f"Ride Trend to: ${r1 + (r1-pivot):,.2f}")
            st.write(f"Trail SL: ${current_price - (w_sig['ATR']*3):,.2f}")
        elif "SELL" in w_sig['Signal']:
            st.error("POSITION SHORT")
            st.write(f"Ride Trend to: ${s1 - (pivot-s1):,.2f}")
            st.write(f"Trail SL: ${current_price + (w_sig['ATR']*3):,.2f}")
        else:
            st.info("No Swing Setup")

    # --- CHART ---
    st.subheader("Chart Analysis")
    fig = go.Figure(data=[go.Candlestick(x=data['1h'].index, open=data['1h']['Open'], high=data['1h']['High'], low=data['1h']['Low'], close=data['1h']['Close'])])
    fig.add_trace(go.Scatter(x=data['1h'].index, y=data['1h']['EMA200'], line=dict(color='blue', width=2), name="EMA 200"))
    fig.update_layout(height=500, xaxis_rangeslider_visible=False, template="plotly_dark")
    st.plotly_chart(fig, use_container_width=True)

else:
    st.error("Symbol not found. Try GC=F, BTC-USD, SI=F")

# Auto-refresh
time.sleep(60)
st.rerun()
