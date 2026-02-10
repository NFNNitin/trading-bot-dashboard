import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
import time

# --- 1. PAGE SETUP & UI ---
st.set_page_config(page_title="Ultimate AI Trader", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: white; }
    .stMetric { background-color: #1c1c1c; border: 1px solid #333; padding: 10px; border-radius: 5px; }
    .watchlist-card {
        background-color: #ffffff; color: #000000; padding: 12px; 
        border-radius: 8px; margin-bottom: 10px; border-left: 8px solid #ccc;
        font-weight: bold; box-shadow: 0px 4px 6px rgba(0,0,0,0.3);
    }
    .buy-signal { border-left: 8px solid #00c853 !important; }
    .sell-signal { border-left: 8px solid #d50000 !important; }
    .small-text { font-size: 12px; color: #444; }
</style>
""", unsafe_allow_html=True)

# --- 2. THE ENGINE: DATA & INDICATORS ---
def calculate_adx_stable(df, n=14):
    """Vectorized ADX calculation to prevent AttributeErrors."""
    df = df.copy()
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    
    # True Range
    df['h_l'] = df['High'] - df['Low']
    df['h_pc'] = abs(df['High'] - df['Close'].shift(1))
    df['l_pc'] = abs(df['Low'] - df['Close'].shift(1))
    df['tr'] = df[['h_l', 'h_pc', 'l_pc']].max(axis=1)
    
    # Directional Movement
    df['plus_dm'] = np.where((df['High'] - df['High'].shift(1)) > (df['Low'].shift(1) - df['Low']), 
                             np.maximum(df['High'] - df['High'].shift(1), 0), 0)
    df['minus_dm'] = np.where((df['Low'].shift(1) - df['Low']) > (df['High'] - df['High'].shift(1)), 
                              np.maximum(df['Low'].shift(1) - df['Low'], 0), 0)
    
    # Smooth with rolling sum
    tr_s = df['tr'].rolling(window=n).sum()
    pdm_s = df['plus_dm'].rolling(window=n).sum()
    mdm_s = df['minus_dm'].rolling(window=n).sum()
    
    df['plus_di'] = 100 * (pdm_s / tr_s)
    df['minus_di'] = 100 * (mdm_s / tr_s)
    df['dx'] = 100 * (abs(df['plus_di'] - df['minus_di']) / (df['plus_di'] + df['minus_di']))
    df['ADX'] = df['dx'].rolling(window=n).mean()
    return df

def get_candle_pattern(df):
    if len(df) < 2: return "Neutral"
    last, prev = df.iloc[-1], df.iloc[-2]
    body = abs(last['Open'] - last['Close'])
    # Hammer
    if (min(last['Open'], last['Close']) - last['Low']) > (body * 2): return "🔨 Hammer"
    # Engulfing
    if last['Close'] > prev['Open'] and last['Open'] < prev['Close']: return "🟢 Engulfing"
    if last['Close'] < prev['Open'] and last['Open'] > prev['Close']: return "🔴 Engulfing"
    return "Neutral"

def add_all_logic(df):
    if len(df) < 50: return df
    # Trend & Momentum
    df['EMA200'] = df['Close'].ewm(span=200, adjust=False).mean()
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-9))))
    df['ATR'] = (df['High'] - df['Low']).rolling(14).mean()
    
    # Stochastic
    low_14, high_14 = df['Low'].rolling(14).min(), df['High'].rolling(14).max()
    df['stoch'] = (df['Close'] - low_14) * 100 / (high_14 - low_14)
    
    return calculate_adx_stable(df)

# --- 3. THE ANALYZER ---
def get_data(symbol):
    try:
        d_5m = yf.download(symbol, period="5d", interval="5m", progress=False)
        d_1h = yf.download(symbol, period="1mo", interval="1h", progress=False)
        d_1d = yf.download(symbol, period="1y", interval="1d", progress=False)
        if d_5m.empty: return None
        # Clean columns
        for d in [d_5m, d_1h, d_1d]:
            if isinstance(d.columns, pd.MultiIndex): d.columns = d.columns.get_level_values(0)
        
        data = {'5m': d_5m, '1h': d_1h, 'Daily': d_1d}
        data['15m'] = d_5m.resample('15min').agg({'Open':'first','High':'max','Low':'min','Close':'last'}).dropna()
        data['30m'] = d_5m.resample('30min').agg({'Open':'first','High':'max','Low':'min','Close':'last'}).dropna()
        data['4h'] = d_1h.resample('4h').agg({'Open':'first','High':'max','Low':'min','Close':'last'}).dropna()
        return data
    except: return None

# --- 4. UI COMPONENTS ---
st.sidebar.header("🔍 Market Watch")
asset = st.sidebar.text_input("Main Asset", "GC=F").upper()
if st.sidebar.button("🔄 Refresh Now"): st.rerun()

st.sidebar.divider()
st.sidebar.subheader("Live Watchlist")
for w in ["GC=F", "SI=F", "BTC-USD", "EURUSD=X"]:
    try:
        w_df = yf.download(w, period="2d", interval="1h", progress=False)
        if isinstance(w_df.columns, pd.MultiIndex): w_df.columns = w_df.columns.get_level_values(0)
        price = w_df.iloc[-1]['Close']
        ema = w_df['Close'].ewm(span=200, adjust=False).mean().iloc[-1]
        trend_class = "buy-signal" if price > ema else "sell-signal"
        st.sidebar.markdown(f'<div class="watchlist-card {trend_class}">{w}<br><span class="small-text">{"BULLISH" if price > ema else "BEARISH"} | ${price:,.2f}</span></div>', unsafe_allow_html=True)
    except: pass

# --- 5. MAIN DASHBOARD ---
st.title(f"🚀 AI Trading Desk: {asset}")
all_df = get_data(asset)

if all_df:
    # Top Stats
    last_d = all_df['Daily'].iloc[-2]
    pivot = (last_d['High'] + last_d['Low'] + last_d['Close']) / 3
    curr_p = all_df['5m'].iloc[-1]['Close']
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Live Price", f"${curr_p:,.2f}")
    m2.metric("Daily Pivot", f"${pivot:,.2f}")
    m3.metric("Trend Strength (ADX)", f"{add_all_logic(all_df['1h']).iloc[-1]['ADX']:.1f}")

    # Timeframe Grid
    st.subheader("1. Multi-Timeframe Analysis")
    t_cols = st.columns(5)
    tf_list = ['5m', '15m', '30m', '1h', '4h']
    tf_data = {}

    for i, tf in enumerate(tf_list):
        processed = add_all_logic(all_df[tf])
        curr = processed.iloc[-1]
        tf_data[tf] = curr
        pattern = get_candle_pattern(processed)
        
        with t_cols[i]:
            st.markdown(f"**{tf}**")
            trend = "BULL" if curr['Close'] > curr['EMA200'] else "BEAR"
            color = "#00c853" if trend == "BULL" else "#ff1744"
            st.markdown(f"<span style='color:{color}; font-weight:bold'>{trend}</span>", unsafe_allow_html=True)
            st.caption(f"Pattern: {pattern}")
            st.caption(f"RSI: {curr['RSI']:.1f}")

    st.divider()

    # Strategy Section
    st.subheader("2. AI Prediction Strategies")
    s1, s2, s3 = st.columns(3)
    
    # LOGIC: Scalp matches 1H Trend
    with s1:
        st.markdown("### ⚡ Scalping")
        if tf_data['5m']['Close'] > tf_data['5m']['EMA200'] and tf_data['1h']['Close'] > tf_data['1h']['EMA200']:
            st.success("✅ LONG SETUP")
            st.write(f"TP: ${curr_p + tf_data['5m']['ATR']*1.5:,.2f} | SL: ${curr_p - tf_data['5m']['ATR']:,.2f}")
        elif tf_data['5m']['Close'] < tf_data['5m']['EMA200'] and tf_data['1h']['Close'] < tf_data['1h']['EMA200']:
            st.error("✅ SHORT SETUP")
            st.write(f"TP: ${curr_p - tf_data['5m']['ATR']*1.5:,.2f} | SL: ${curr_p + tf_data['5m']['ATR']:,.2f}")
        else: st.info("⏳ Trend Conflict - Wait")

    with s2:
        st.markdown("### 📅 Intraday")
        if curr_p > pivot and tf_data['1h']['RSI'] < 60:
            st.success("✅ BULLISH (Above Pivot)")
            st.write(f"Target: ${pivot + (pivot * 0.01):,.2f}")
        elif curr_p < pivot and tf_data['1h']['RSI'] > 40:
            st.error("✅ BEARISH (Below Pivot)")
            st.write(f"Target: ${pivot - (pivot * 0.01):,.2f}")
        else: st.warning("⚖️ Neutral Zone")

    with s3:
        st.markdown("### 🌊 Swing")
        if tf_data['4h']['Close'] > tf_data['4h']['EMA200']: st.success("✅ BULLISH TREND")
        else: st.error("✅ BEARISH TREND")
        st.caption(f"ADX Strength: {tf_data['4h']['ADX']:.1f}")

    # Chart
    st.plotly_chart(go.Figure(data=[go.Candlestick(x=all_df['1h'].index, open=all_df['1h']['Open'], high=all_df['1h']['High'], low=all_df['1h']['Low'], close=all_df['1h']['Close'])]).update_layout(template="plotly_dark", xaxis_rangeslider_visible=False), use_container_width=True)

else: st.error("Could not fetch data. Please check ticker.")
time.sleep(60)
st.rerun()
