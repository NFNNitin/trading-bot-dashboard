import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
import time

# --- 1. PAGE CONFIG & THEME ---
st.set_page_config(page_title="AI Master Terminal", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #ffffff !important; color: #000000 !important; }
    h1, h2, h3, h4, p, span, label { color: #000000 !important; }
    .stMetric { background-color: #f8f9fa; border: 1px solid #dee2e6; padding: 15px; border-radius: 10px; }
    .signal-card { padding: 20px; border-radius: 12px; border: 1px solid #eee; margin-bottom: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
    .buy-zone { border-left: 10px solid #28a745; background-color: #f4fff7; }
    .sell-zone { border-left: 10px solid #dc3545; background-color: #fff5f5; }
    .neutral-zone { border-left: 10px solid #6c757d; background-color: #fdfdfd; }
    .volume-surge { background-color: #fff3cd; color: #856404; padding: 10px; border-radius: 5px; font-weight: bold; text-align: center; margin-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

# --- 2. TECHNICAL ENGINE ---
def calculate_all_indicators(df):
    df = df.copy()
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    
    # EMAs
    for p in [9, 21, 50, 200]: df[f'EMA{p}'] = df['Close'].ewm(span=p, adjust=False).mean()
    
    # RSI & MACD
    delta = df['Close'].diff(); gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-9))))
    exp1 = df['Close'].ewm(span=12, adjust=False).mean(); exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2; df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    
    # ATR & VWAP
    df['tr'] = df[['High', 'Low', 'Close']].apply(lambda x: max(x[0]-x[1], abs(x[0]-x[2]), abs(x[1]-x[2])), axis=1)
    df['ATR'] = df['tr'].rolling(14).mean()
    df['VWAP'] = (df['Close'] * df['Volume']).cumsum() / df['Volume'].cumsum()
    df['Vol_Avg'] = df['Volume'].rolling(20).mean()
    return df.dropna()

def identify_candle(df):
    c, o, h, l = df.iloc[-1]['Close'], df.iloc[-1]['Open'], df.iloc[-1]['High'], df.iloc[-1]['Low']
    body = abs(c - o)
    if (min(o, c) - l) > (body * 2): return "🔨 Hammer", "Bullish Reversal"
    if (h - max(o, c)) > (body * 2): return "🌠 Shooting Star", "Bearish Rejection"
    if body < ((h - l) * 0.1): return "➕ Doji", "Indecision"
    return "Neutral", "Ranging"

# --- 3. SIGNAL GENERATOR ---
def get_confluence_signal(df, mode="Scalp"):
    curr = df.iloc[-1]
    score = 0
    if curr['Close'] > curr['EMA200']: score += 1
    if curr['EMA9'] > curr['EMA21']: score += 1
    if curr['MACD'] > curr['Signal']: score += 1
    if 40 < curr['RSI'] < 70: score += 1
    
    atr_mult = 1.5 if mode == "Scalp" else 2.5
    price = curr['Close']
    
    if score >= 3:
        return {"sig": "BUY", "entry": price, "tp": price + (curr['ATR']*atr_mult), "sl": price - (curr['ATR']*1.5), "zone": "buy-zone"}
    elif score <= 1:
        return {"sig": "SELL", "entry": price, "tp": price - (curr['ATR']*atr_mult), "sl": price + (curr['ATR']*1.5), "zone": "sell-zone"}
    return {"sig": "NEUTRAL", "entry": price, "tp": 0, "sl": 0, "zone": "neutral-zone"}

# --- 4. DATA LOADER ---
@st.cache_data(ttl=60)
def load_market_data(symbol):
    d5m = yf.download(symbol, period="5d", interval="5m", progress=False)
    d1h = yf.download(symbol, period="1mo", interval="1h", progress=False)
    if d5m.empty or d1h.empty: return None
    
    data = {'5m': calculate_all_indicators(d5m)}
    data['15m'] = calculate_all_indicators(d5m.resample('15min').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'}).dropna())
    data['30m'] = calculate_all_indicators(d5m.resample('30min').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'}).dropna())
    data['1h'] = calculate_all_indicators(d1h)
    data['4h'] = calculate_all_indicators(d1h.resample('4h').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'}).dropna())
    return data

# --- 5. UI LAYOUT ---
with st.sidebar:
    st.header("Settings")
    asset = st.text_input("Symbol", "GC=F").upper()
    if st.button("🔄 MANUAL REFRESH"): st.rerun()

try:
    all_tf = load_market_data(asset)
    if all_tf:
        curr_p = all_tf['5m'].iloc[-1]['Close']
        st.title(f"🚀 AI Terminal: {asset}")
        
        # Volume Alert
        if all_tf['5m'].iloc[-1]['Volume'] > all_tf['5m'].iloc[-1]['Vol_Avg'] * 2:
            st.markdown('<div class="volume-surge">⚠️ VOLUME SURGE DETECTED! Big money entering.</div>', unsafe_allow_html=True)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Live Price", f"${curr_p:,.2f}")
        c2.metric("1h RSI", f"{all_tf['1h'].iloc[-1]['RSI']:.1f}")
        c3.metric("VWAP", f"${all_tf['5m'].iloc[-1]['VWAP']:,.2f}")
        c4.metric("Volatility (ATR)", f"{all_tf['5m'].iloc[-1]['ATR']:.2f}")

        # 1. Multi-Timeframe Analysis
        st.subheader("1. Multi-Timeframe Candles")
        t_cols = st.columns(5)
        tf_keys = ['5m', '15m', '30m', '1h', '4h']
        insights = []
        
        for i, tf in enumerate(tf_keys):
            candle, desc = identify_candle(all_tf[tf])
            insights.append(f"**{tf}**: {desc}")
            with t_cols[i]:
                st.markdown(f"### {tf}")
                st.write(f"Pattern: **{candle}**")
                st.caption(desc)

        st.info("💡 **Market Insight:** " + " | ".join(insights))
        st.divider()

        # 2. Strategy Signals
        st.subheader("2. Pro Strategy Entries")
        s1, s2, s3 = st.columns(3)
        
        with s1:
            sig = get_confluence_signal(all_tf['5m'], "Scalp")
            st.markdown(f'<div class="signal-card {sig["zone"]}"><h3>⚡ Scalping (5m)</h3><b>Signal: {sig["sig"]}</b><br>Entry: ${sig["entry"]:,.2f}<br>TP: ${sig["tp"]:,.2f}<br>SL: ${sig["sl"]:,.2f}</div>', unsafe_allow_html=True)
            
        with s2:
            sig = get_confluence_signal(all_tf['1h'], "Intraday")
            st.markdown(f'<div class="signal-card {sig["zone"]}"><h3>📅 Intraday (1h)</h3><b>Signal: {sig["sig"]}</b><br>Entry: ${sig["entry"]:,.2f}<br>TP: ${sig["tp"]:,.2f}<br>SL: ${sig["sl"]:,.2f}</div>', unsafe_allow_html=True)

        with s3:
            sig = get_confluence_signal(all_tf['4h'], "Swing")
            st.markdown(f'<div class="signal-card {sig["zone"]}"><h3>🌊 Swing (4h)</h3><b>Signal: {sig["sig"]}</b><br>Entry: ${sig["entry"]:,.2f}<br>TP: ${sig["tp"]:,.2f}<br>SL: ${sig["sl"]:,.2f}</div>', unsafe_allow_html=True)

        # 3. Chart
        st.plotly_chart(go.Figure(data=[go.Candlestick(x=all_tf['1h'].index, open=all_tf['1h']['Open'], high=all_tf['1h']['High'], low=all_tf['1h']['Low'], close=all_tf['1h']['Close'])]).update_layout(template="plotly_white", xaxis_rangeslider_visible=False, height=500), use_container_width=True)

except Exception as e:
    st.info(f"Connecting to market feed...")

time.sleep(60)
st.rerun()
