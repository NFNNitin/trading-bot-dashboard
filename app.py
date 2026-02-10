import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
import time

st.set_page_config(page_title="Pro AI Trader Ultimate", layout="wide")

# --- CUSTOM CSS (White Watchlist) ---
st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: white; }
    .stMetric { background-color: #1c1c1c; border: 1px solid #333; padding: 10px; border-radius: 5px; }
    .watchlist-card {
        background-color: #ffffff; 
        color: #000000; 
        padding: 10px; 
        border-radius: 5px; 
        margin-bottom: 8px; 
        border-left: 5px solid #ccc;
        font-weight: bold;
    }
    .buy-signal { border-left: 7px solid #00c853 !important; }
    .sell-signal { border-left: 7px solid #d50000 !important; }
</style>
""", unsafe_allow_html=True)

# --- 1. FIXED ADX ENGINE (No more AttributeErrors) ---
def calculate_adx(df, n=14):
    df = df.copy()
    # Ensure columns are flat strings, not tuples
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
        
    df['H-L'] = df['High'] - df['Low']
    df['H-PC'] = abs(df['High'] - df['Close'].shift(1))
    df['L-PC'] = abs(df['Low'] - df['Close'].shift(1))
    df['TR'] = df[['H-L', 'H-PC', 'L-PC']].max(axis=1)
    
    # Directional Movement
    df['plus_dm'] = np.where((df['High'] - df['High'].shift(1)) > (df['Low'].shift(1) - df['Low']), 
                             np.maximum(df['High'] - df['High'].shift(1), 0), 0)
    df['minus_dm'] = np.where((df['Low'].shift(1) - df['Low']) > (df['High'] - df['High'].shift(1)), 
                              np.maximum(df['Low'].shift(1) - df['Low'], 0), 0)
    
    # Smoothed TR and DM
    df['tr_smoothed'] = df['TR'].rolling(window=n).sum()
    df['plus_dm_smoothed'] = df['plus_dm'].rolling(window=n).sum()
    df['minus_dm_smoothed'] = df['minus_dm'].rolling(window=n).sum()
    
    # DI+ and DI-
    df['plus_di'] = 100 * (df['plus_dm_smoothed'] / df['tr_smoothed'])
    df['minus_di'] = 100 * (df['minus_dm_smoothed'] / df['tr_smoothed'])
    
    # DX and ADX
    df['dx'] = 100 * (abs(df['plus_di'] - df['minus_di']) / (df['plus_di'] + df['minus_di']))
    df['ADX'] = df['dx'].rolling(window=n).mean()
    
    return df

def get_data(symbol):
    try:
        df_5m = yf.download(symbol, period="5d", interval="5m", progress=False)
        df_1h = yf.download(symbol, period="1mo", interval="1h", progress=False)
        df_daily = yf.download(symbol, period="1y", interval="1d", progress=False)
        
        if df_5m.empty or df_1h.empty: return None

        # Force clean headers for EVERY dataframe
        for d in [df_5m, df_1h, df_daily]:
            if isinstance(d.columns, pd.MultiIndex):
                d.columns = d.columns.get_level_values(0)

        data = {}
        data['5m'] = df_5m
        data['15m'] = df_5m.resample('15min').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}).dropna()
        data['30m'] = df_5m.resample('30min').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}).dropna()
        data['1h'] = df_1h
        data['4h'] = df_1h.resample('4h').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}).dropna()
        data['Daily'] = df_daily
        return data
    except Exception as e:
        return None

def add_indicators(df):
    if len(df) < 50: return df
    df['EMA200'] = df['Close'].ewm(span=200, adjust=False).mean()
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-9))))
    df['ATR'] = (df['High'] - df['Low']).rolling(14).mean()
    
    # Trigger fixed ADX
    df = calculate_adx(df)
    return df

def generate_signal(df):
    curr = df.iloc[-1]
    trend = "BULL" if curr['Close'] > curr['EMA200'] else "BEAR"
    adx_val = curr['ADX'] if not np.isnan(curr['ADX']) else 0
    signal = "NEUTRAL"
    
    if adx_val > 20:
        if trend == "BULL" and curr['RSI'] < 45: signal = "BUY"
        if trend == "BEAR" and curr['RSI'] > 55: signal = "SELL"
            
    return {"Signal": signal, "Trend": trend, "RSI": curr['RSI'], "ADX": adx_val, "Price": curr['Close'], "ATR": curr['ATR']}

# --- 2. SIDEBAR & WATCHLIST ---
st.sidebar.header("🔍 Market Watch")
symbol_input = st.sidebar.text_input("Main Asset", "GC=F").upper()
if st.sidebar.button("🔄 Refresh Now"): st.rerun()

st.sidebar.divider()
st.sidebar.subheader("Live Watchlist")
watchlist = ["GC=F", "SI=F", "BTC-USD", "CL=F", "DX-Y"]

for w_sym in watchlist:
    try:
        w_df = yf.download(w_sym, period="2d", interval="1h", progress=False)
        if isinstance(w_df.columns, pd.MultiIndex): w_df.columns = w_df.columns.get_level_values(0)
        w_curr = w_df.iloc[-1]
        w_ema = w_df['Close'].ewm(span=200, adjust=False).mean().iloc[-1]
        w_trend = "BULLISH" if w_curr['Close'] > w_ema else "BEARISH"
        css_class = "buy-signal" if w_trend == "BULLISH" else "sell-signal"
        st.sidebar.markdown(f'<div class="watchlist-card {css_class}">{w_sym}<br><small>{w_trend} | ${w_curr["Close"]:,.2f}</small></div>', unsafe_allow_html=True)
    except: pass

# --- 3. MAIN DASHBOARD ---
st.title(f"🚀 AI Trader: {symbol_input}")
data = get_data(symbol_input)

if data:
    # Calculation grid
    cols = st.columns(5)
    timeframes = ['5m', '15m', '30m', '1h', '4h']
    for i, tf in enumerate(timeframes):
        df_tf = add_indicators(data[tf])
        sig = generate_signal(df_tf)
        color = "green" if sig['Signal'] == "BUY" else "red" if sig['Signal'] == "SELL" else "gray"
        with cols[i]:
            st.markdown(f"**{tf}**")
            st.markdown(f"<span style='color:{color}; font-weight:bold'>{sig['Signal']}</span>", unsafe_allow_html=True)
            st.caption(f"ADX: {sig['ADX']:.1f}")
    
    # Chart
    fig = go.Figure(data=[go.Candlestick(x=data['1h'].index, open=data['1h']['Open'], high=data['1h']['High'], low=data['1h']['Low'], close=data['1h']['Close'])])
    fig.update_layout(height=500, template="plotly_dark", xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)
else:
    st.error("Data fetch failed. Try GC=F.")

time.sleep(60)
st.rerun()
