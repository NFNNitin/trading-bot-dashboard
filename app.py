import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
import time

# --- 1. PAGE CONFIG & LIGHT THEME ---
st.set_page_config(page_title="Pro AI Trader - Ultimate White", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #ffffff !important; color: #000000 !important; }
    h1, h2, h3, h4, p, span, label { color: #000000 !important; }
    [data-testid="stMetricValue"] { color: #000000 !important; }
    .stMetric { background-color: #f8f9fa; border: 1px solid #dee2e6; padding: 15px; border-radius: 10px; }
    .volume-alert { 
        background-color: #fff3cd; border: 2px solid #ffeeba; color: #856404; 
        padding: 15px; border-radius: 10px; font-weight: bold; margin-bottom: 20px; text-align: center;
        animation: blinker 1.5s linear infinite;
    }
    @keyframes blinker { 50% { opacity: 0.5; } }
    .news-card { border-bottom: 1px solid #eee; padding: 10px 0; }
    .news-title { font-size: 14px; font-weight: bold; color: #007bff !important; text-decoration: none; }
</style>
""", unsafe_allow_html=True)

# Initialize Session State
if 'trade_log' not in st.session_state: st.session_state.trade_log = []

# --- 2. ENGINE ---
def identify_candle_with_text(df):
    if len(df) < 2: return "Neutral", "Waiting..."
    c, o, h, l = df.iloc[-1]['Close'], df.iloc[-1]['Open'], df.iloc[-1]['High'], df.iloc[-1]['Low']
    body = abs(c - o)
    if (min(o, c) - l) > (body * 2): return "🔨 Hammer", "Bullish reversal attempt."
    if (h - max(o, c)) > (body * 2): return "🌠 Shooting Star", "Bearish rejection detected."
    if body < ((h - l) * 0.1): return "➕ Doji", "Market indecision."
    return "Normal", "Standard Trend Action."

def calculate_indicators(df):
    df = df.copy()
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    df['EMA200'] = df['Close'].ewm(span=200, adjust=False).mean()
    df['ATR'] = (df['High'] - df['Low']).rolling(14).mean()
    df['Vol_Avg'] = df['Volume'].rolling(20).mean()
    return df

# --- 3. SIDEBAR & NEWS ---
st.sidebar.title("🔍 Market Watch")
asset = st.sidebar.text_input("Main Asset", "GC=F").upper()

with st.sidebar:
    st.divider()
    st.subheader("📰 Latest News")
    try:
        ticker = yf.Ticker(asset)
        for news in ticker.news[:5]:
            st.markdown(f"""<div class='news-card'>
                <a class='news-title' href='{news['link']}' target='_blank'>{news['title']}</a><br>
                <small style='color:#666'>{news['publisher']}</small>
            </div>""", unsafe_allow_html=True)
    except: st.write("No recent news found.")

# --- 4. DATA & DASHBOARD ---
try:
    d5 = yf.download(asset, period="5d", interval="5m", progress=False)
    d1h = yf.download(asset, period="1mo", interval="1h", progress=False)
    for d in [d5, d1h]:
        if isinstance(d.columns, pd.MultiIndex): d.columns = d.columns.get_level_values(0)
    
    df_5m = calculate_indicators(d5)
    df_1h = calculate_indicators(d1h)
    curr = df_5m.iloc[-1]

    if curr['Volume'] > (curr['Vol_Avg'] * 2):
        st.markdown(f'<div class="volume-alert">⚠️ VOLUME SURGE: {curr["Volume"]/curr["Vol_Avg"]:.1f}x spike! Institutional activity detected.</div>', unsafe_allow_html=True)

    st.title(f"📊 AI Trading Terminal: {asset}")
    st.metric("Live Price", f"${curr['Close']:,.2f}")

    # Analysis Grid
    st.subheader("1. Multi-Timeframe Analysis")
    c1, c2 = st.columns(2)
    
    with c1:
        candle, msg = identify_candle_with_text(df_5m)
        st.markdown("### ⚡ 5m Scalp")
        sig = "LONG" if curr['Close'] > curr['EMA200'] else "SHORT"
        st.write(f"Trend: **{sig}** | Candle: **{candle}**")
        st.info(f"Insight: {msg}")
        log_entry = f"{datetime.now().strftime('%H:%M')} - 5m {sig} on {asset}"
        if not st.session_state.trade_log or st.session_state.trade_log[0] != log_entry:
            st.session_state.trade_log.insert(0, log_entry)

    with c2:
        st.markdown("### 📅 1h Intraday")
        curr_1h = df_1h.iloc[-1]
        sig_1h = "BULLISH" if curr_1h['Close'] > curr_1h['EMA200'] else "BEARISH"
        st.write(f"Main Trend: **{sig_1h}**")
        st.write(f"Target: ${curr_1h['Close'] + (curr_1h['ATR']*2) if sig_1h=='BULLISH' else curr_1h['Close'] - (curr_1h['ATR']*2):,.2f}")

    # Chart
    st.plotly_chart(go.Figure(data=[go.Candlestick(x=d1h.index, open=d1h['Open'], high=d1h['High'], low=d1h['Low'], close=d1h['Close'])]).update_layout(template="plotly_white", xaxis_rangeslider_visible=False), use_container_width=True)

    # Trade Log
    st.subheader("📜 Live Trade Log")
    st.table(pd.DataFrame(st.session_state.trade_log[:10], columns=["Recent Signals"]))

except Exception as e:
    st.error(f"Please check the ticker symbol or wait for market data to load.")

time.sleep(60)
st.rerun()
