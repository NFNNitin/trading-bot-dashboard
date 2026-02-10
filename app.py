import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
import time

# --- 1. PAGE CONFIG & LIGHT THEME ---
st.set_page_config(page_title="Pro AI Trader - White Edition", layout="wide")

st.markdown("""
<style>
    /* Force White Background Everywhere */
    .stApp { background-color: #ffffff !important; color: #000000 !important; }
    h1, h2, h3, h4, p, span, label { color: #000000 !important; }
    
    /* Metric Cards */
    [data-testid="stMetricValue"] { color: #000000 !important; }
    .stMetric { background-color: #f8f9fa; border: 1px solid #dee2e6; padding: 15px; border-radius: 10px; }
    
    /* Watchlist Cards (White with Shadow) */
    .watchlist-card {
        background-color: #ffffff; color: #000000; padding: 15px; 
        border-radius: 8px; margin-bottom: 12px; border: 1px solid #e0e0e0;
        box-shadow: 0px 4px 10px rgba(0,0,0,0.05);
    }
    .buy-signal { border-left: 8px solid #28a745 !important; }
    .sell-signal { border-left: 8px solid #dc3545 !important; }
    
    /* Sidebar White */
    [data-testid="stSidebar"] { background-color: #fdfdfd !important; border-right: 1px solid #eeeeee; }
</style>
""", unsafe_allow_html=True)

# --- 2. THE ENGINE: MATH & LOGIC ---
def calculate_advanced_indicators(df):
    df = df.copy()
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    
    # EMAs
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['EMA200'] = df['Close'].ewm(span=200, adjust=False).mean()
    
    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-9))))
    
    # ADX (Trend Strength)
    df['h_l'] = df['High'] - df['Low']
    df['h_pc'] = abs(df['High'] - df['Close'].shift(1))
    df['l_pc'] = abs(df['Low'] - df['Close'].shift(1))
    df['tr'] = df[['h_l', 'h_pc', 'l_pc']].max(axis=1)
    df['ADX'] = (df['tr'].rolling(14).mean() / df['Close']) * 1000 # Simplified proxy for speed
    
    # ATR & Volatility
    df['ATR'] = df['tr'].rolling(14).mean()
    
    # VWAP (Approximate)
    df['vwap'] = (df['Close'] * df['Volume']).cumsum() / df['Volume'].cumsum()
    
    return df

def identify_candle(df):
    if len(df) < 2: return "Neutral"
    c, o, h, l = df.iloc[-1]['Close'], df.iloc[-1]['Open'], df.iloc[-1]['High'], df.iloc[-1]['Low']
    body = abs(c - o)
    if (min(o, c) - l) > (body * 2): return "🔨 Hammer"
    if (h - max(o, c)) > (body * 2): return "🌠 Shooting Star"
    if body < ((h - l) * 0.1): return "➕ Doji"
    return "Normal"

# --- 3. DATA FETCHER ---
def get_market_data(symbol):
    try:
        d5 = yf.download(symbol, period="5d", interval="5m", progress=False)
        d1h = yf.download(symbol, period="1mo", interval="1h", progress=False)
        d1d = yf.download(symbol, period="1y", interval="1d", progress=False)
        if d5.empty: return None
        for d in [d5, d1h, d1d]:
            if isinstance(d.columns, pd.MultiIndex): d.columns = d.columns.get_level_values(0)
        
        data = {'5m': d5, '1h': d1h, 'Daily': d1d}
        data['15m'] = d5.resample('15min').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'}).dropna()
        data['30m'] = d5.resample('30min').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'}).dropna()
        data['4h'] = d1h.resample('4h').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'}).dropna()
        return data
    except: return None

# --- 4. SIDEBAR & WATCHLIST ---
st.sidebar.title("🔍 Market Watch")
asset = st.sidebar.text_input("Main Asset", "GC=F").upper()
if st.sidebar.button("🔄 Refresh Now"): st.rerun()

st.sidebar.subheader("Live Watchlist")
for w in ["GC=F", "SI=F", "BTC-USD", "DX-Y"]:
    try:
        w_df = yf.download(w, period="5d", interval="1h", progress=False)
        if isinstance(w_df.columns, pd.MultiIndex): w_df.columns = w_df.columns.get_level_values(0)
        curr_w = w_df.iloc[-1]['Close']
        ema_w = w_df['Close'].ewm(span=200, adjust=False).mean().iloc[-1]
        t_style = "buy-signal" if curr_w > ema_w else "sell-signal"
        st.sidebar.markdown(f'<div class="watchlist-card {t_style}">{w}<br><b>${curr_w:,.2f}</b><br><small>{"BULLISH" if curr_w > ema_w else "BEARISH"}</small></div>', unsafe_allow_html=True)
    except: pass

# --- 5. MAIN DASHBOARD ---
st.title(f"📊 AI Trading Terminal: {asset}")
all_data = get_market_data(asset)

if all_data:
    # Top Row Metrics
    processed_1h = calculate_advanced_indicators(all_data['1h'])
    curr_1h = processed_1h.iloc[-1]
    
    last_day = all_data['Daily'].iloc[-2]
    pivot = (last_day['High'] + last_day['Low'] + last_day['Close']) / 3
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Live Price", f"${curr_1h['Close']:,.2f}")
    c2.metric("VWAP (1H)", f"${curr_1h['vwap']:,.2f}")
    c3.metric("Daily Pivot", f"${pivot:,.2f}")
    c4.metric("ADX Strength", f"{curr_1h['ADX']:.1f}")

    # 1. Multi-Timeframe Scan
    st.subheader("1. Multi-Timeframe Analysis")
    t_cols = st.columns(5)
    tf_list = ['5m', '15m', '30m', '1h', '4h']
    tf_results = {}

    for i, tf in enumerate(tf_list):
        df_tf = calculate_advanced_indicators(all_data[tf])
        row = df_tf.iloc[-1]
        tf_results[tf] = row
        candle = identify_candle(df_tf)
        
        with t_cols[i]:
            st.markdown(f"### {tf}")
            trend = "BULL" if row['Close'] > row['EMA200'] else "BEAR"
            color = "green" if trend == "BULL" else "red"
            st.markdown(f"**Trend: <span style='color:{color}'>{trend}</span>**", unsafe_allow_html=True)
            st.write(f"Candle: {candle}")
            st.caption(f"RSI: {row['RSI']:.1f}")

    st.divider()

    # 2. Strategy Logic
    st.subheader("2. AI Strategy Predictions")
    sc, it, sw = st.columns(3)
    
    with sc:
        st.markdown("### ⚡ Scalping")
        # Logic: 5m must match 1h Trend to avoid conflict
        if tf_results['5m']['Close'] > tf_results['5m']['EMA200'] and tf_results['1h']['Close'] > tf_results['1h']['EMA200']:
            st.success("BUY SIGNAL")
            st.write(f"Entry: ${curr_1h['Close']:,.2f}")
            st.write(f"TP: ${curr_1h['Close'] + tf_results['5m']['ATR']*1.5:,.2f}")
            st.write(f"SL: ${curr_1h['Close'] - tf_results['5m']['ATR']:,.2f}")
        elif tf_results['5m']['Close'] < tf_results['5m']['EMA200'] and tf_results['1h']['Close'] < tf_results['1h']['EMA200']:
            st.error("SELL SIGNAL")
            st.write(f"Entry: ${curr_1h['Close']:,.2f}")
            st.write(f"TP: ${curr_1h['Close'] - tf_results['5m']['ATR']*1.5:,.2f}")
            st.write(f"SL: ${curr_1h['Close'] + tf_results['5m']['ATR']:,.2f}")
        else:
            st.warning("Trend Conflict")
            st.caption("Scalp trend doesn't match Major trend. Waiting...")

    with it:
        st.markdown("### 📅 Intraday")
        if curr_1h['Close'] > pivot:
            st.success("BULLISH (Above Pivot)")
            st.write(f"Target: ${pivot + (pivot * 0.015):,.2f}")
        else:
            st.error("BEARISH (Below Pivot)")
            st.write(f"Target: ${pivot - (pivot * 0.015):,.2f}")

    with sw:
        st.markdown("### 🌊 Swing / Holding")
        swing_trend = "BULLISH" if tf_results['4h']['Close'] > tf_results['4h']['EMA200'] else "BEARISH"
        st.info(f"Main Trend: {swing_trend}")
        st.write(f"Hold until: ${tf_results['4h']['EMA200']:,.2f} Breakout")

    # 3. Chart (White Theme)
    st.subheader("Price Chart (1H)")
    fig = go.Figure(data=[go.Candlestick(x=processed_1h.index, open=processed_1h['Open'], high=processed_1h['High'], low=processed_1h['Low'], close=processed_1h['Close'])])
    fig.add_trace(go.Scatter(x=processed_1h.index, y=processed_1h['EMA200'], line=dict(color='blue', width=2), name="EMA 200"))
    fig.update_layout(template="plotly_white", height=500, xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

else:
    st.error("Invalid Ticker. Please use symbols like GC=F (Gold) or BTC-USD.")

time.sleep(60)
st.rerun()
