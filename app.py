import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time

# --- 1. PAGE CONFIG (ULTRA WHITE) ---
st.set_page_config(page_title="AI Trading Terminal Pro", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #ffffff !important; color: #000000 !important; }
    [data-testid="stMetricValue"] { color: #000000 !important; font-weight: bold; }
    .stMetric { background-color: #f8f9fa; border: 1px solid #dee2e6; padding: 15px; border-radius: 12px; }
    .signal-card { padding: 20px; border-radius: 15px; border: 1px solid #eee; margin-bottom: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
    .buy-signal { border-left: 10px solid #28a745; background-color: #f4fff7; }
    .sell-signal { border-left: 10px solid #dc3545; background-color: #fff5f5; }
    .neutral-signal { border-left: 10px solid #6c757d; background-color: #fdfdfd; }
</style>
""", unsafe_allow_html=True)

# --- 2. ADVANCED TECHNICAL ENGINE ---
def get_indicators(df):
    df = df.copy()
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    
    # Trend
    df['EMA9'] = df['Close'].ewm(span=9, adjust=False).mean()
    df['EMA21'] = df['Close'].ewm(span=21, adjust=False).mean()
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['EMA200'] = df['Close'].ewm(span=200, adjust=False).mean()
    
    # Momentum
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-9))))
    
    # MACD
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['Signal_Line'] = df['MACD'].ewm(span=9, adjust=False).mean()
    
    # Volatility
    df['ATR'] = (df['High'] - df['Low']).rolling(14).mean()
    df['VWAP'] = (df['Close'] * df['Volume']).cumsum() / df['Volume'].cumsum()
    
    # Stochastic
    low_14 = df['Low'].rolling(14).min()
    high_14 = df['High'].rolling(14).max()
    df['K'] = (df['Close'] - low_14) * 100 / (high_14 - low_14)
    
    return df

def get_candle_logic(df):
    if len(df) < 3: return "Normal", "Standard Trend"
    c, o, h, l = df.iloc[-1]['Close'], df.iloc[-1]['Open'], df.iloc[-1]['High'], df.iloc[-1]['Low']
    prev_c, prev_o = df.iloc[-2]['Close'], df.iloc[-2]['Open']
    body = abs(c - o)
    
    if (min(o, c) - l) > (body * 2): return "🔨 Hammer", "Bullish Reversal Potential"
    if (h - max(o, c)) > (body * 2): return "🌠 Shooting Star", "Bearish Rejection"
    if c > o and prev_o > prev_c and c > prev_o and o < prev_c: return "🟢 Bullish Engulfing", "Strong Buy Signal"
    if o > c and prev_c > prev_o and o > prev_c and c < prev_o: return "🔴 Bearish Engulfing", "Strong Sell Signal"
    return "Neutral", "Ranging"

# --- 3. SIGNAL STRATEGY ---
def generate_strategy_signal(df, mode="Scalp"):
    curr = df.iloc[-1]
    atr = curr['ATR']
    price = curr['Close']
    
    # Confluence Logic
    bullish = (curr['EMA9'] > curr['EMA21']) and (curr['MACD'] > curr['Signal_Line']) and (curr['RSI'] < 70)
    bearish = (curr['EMA9'] < curr['EMA21']) and (curr['MACD'] < curr['Signal_Line']) and (curr['RSI'] > 30)
    
    if bullish:
        sig = "BUY"
        tp = price + (atr * 2.5) if mode == "Swing" else price + (atr * 1.5)
        sl = price - (atr * 1.2)
        status = "buy-signal"
    elif bearish:
        sig = "SELL"
        tp = price - (atr * 2.5) if mode == "Swing" else price - (atr * 1.5)
        sl = price + (atr * 1.2)
        status = "sell-signal"
    else:
        sig, tp, sl, status = "NEUTRAL", 0, 0, "neutral-signal"
        
    return {"sig": sig, "entry": price, "tp": tp, "sl": sl, "status": status}

# --- 4. SIDEBAR ---
with st.sidebar:
    st.title("Settings")
    asset = st.text_input("Ticker Symbol", "GC=F").upper()
    if st.button("🔄 MANUAL REFRESH"): st.rerun()
    
    st.divider()
    st.subheader("News Feed")
    try:
        ticker_news = yf.Ticker(asset).news[:4]
        for n in ticker_news:
            st.markdown(f"**[{n['publisher']}]** \n[{n['title']}]({n['link']})")
    except: st.write("No news available.")

# --- 5. MAIN DASHBOARD ---
try:
    # Fetch all timeframes
    d5m = yf.download(asset, period="2d", interval="5m", progress=False)
    d1h = yf.download(asset, period="1mo", interval="1h", progress=False)
    d4h = yf.download(asset, period="3mo", interval="1h", progress=False) # Will resample
    
    if d5m.empty: st.error("Invalid Asset Symbol.")
    else:
        # Process Data
        df5 = get_indicators(d5m)
        df15 = get_indicators(d5m.resample('15min').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'}).dropna())
        df1h = get_indicators(d1h)
        df4h = get_indicators(d1h.resample('4h').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'}).dropna())
        
        # Header Metrics
        curr_p = df5.iloc[-1]['Close']
        change = curr_p - df5.iloc[-2]['Close']
        
        st.title(f"🚀 AI Trading Terminal: {asset}")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Live Price", f"${curr_p:,.2f}", f"{change:,.2f}")
        c2.metric("VWAP (5m)", f"${df5.iloc[-1]['VWAP']:,.2f}")
        c3.metric("ATR (Volatility)", f"{df5.iloc[-1]['ATR']:.2f}")
        c4.metric("RSI (1h)", f"{df1h.iloc[-1]['RSI']:.1f}")

        # 1. Multi-Timeframe Grid
        st.subheader("1. Multi-Timeframe Analysis")
        t_cols = st.columns(4)
        timeframes = [("5m", df5), ("15m", df15), ("1h", df1h), ("4h", df4h)]
        
        for i, (name, df) in enumerate(timeframes):
            candle, note = get_candle_logic(df)
            trend = "Bullish" if df.iloc[-1]['Close'] > df.iloc[-1]['EMA200'] else "Bearish"
            with t_cols[i]:
                st.markdown(f"**{name} Window**")
                st.write(f"Trend: {trend}")
                st.write(f"Pattern: **{candle}**")
                st.caption(note)

        st.divider()

        # 2. Strategy Predictions
        st.subheader("2. AI Strategy Entry Points")
        s1, s2, s3 = st.columns(3)
        
        # Scalping (5m)
        scalp = generate_strategy_signal(df5, "Scalp")
        with s1:
            st.markdown(f'<div class="signal-card {scalp["status"]}"><h3>⚡ Scalping (5m)</h3>'
                        f'<b>Signal: {scalp["sig"]}</b><br>'
                        f'Entry: ${scalp["entry"]:,.2f}<br>'
                        f'TP: <span style="color:green">${scalp["tp"]:,.2f}</span><br>'
                        f'SL: <span style="color:red">${scalp["sl"]:,.2f}</span></div>', unsafe_allow_html=True)
        
        # Intraday (1h)
        day = generate_strategy_signal(df1h, "Day")
        with s2:
            st.markdown(f'<div class="signal-card {day["status"]}"><h3>📅 Intraday (1h)</h3>'
                        f'<b>Signal: {day["sig"]}</b><br>'
                        f'Entry: ${day["entry"]:,.2f}<br>'
                        f'TP: <span style="color:green">${day["tp"]:,.2f}</span><br>'
                        f'SL: <span style="color:red">${day["sl"]:,.2f}</span></div>', unsafe_allow_html=True)
            
        # Swing (4h)
        swing = generate_strategy_signal(df4h, "Swing")
        with s3:
            st.markdown(f'<div class="signal-card {swing["status"]}"><h3>🌊 Swing (4h)</h3>'
                        f'<b>Signal: {swing["sig"]}</b><br>'
                        f'Entry: ${swing["entry"]:,.2f}<br>'
                        f'TP: <span style="color:green">${swing["tp"]:,.2f}</span><br>'
                        f'SL: <span style="color:red">${swing["sl"]:,.2f}</span></div>', unsafe_allow_html=True)

        # 3. Professional Chart
        st.subheader("3. Technical Chart (1h View)")
        fig = go.Figure(data=[go.Candlestick(x=df1h.index, open=df1h['Open'], high=df1h['High'], low=df1h['Low'], close=df1h['Close'], name="Price")])
        fig.add_trace(go.Scatter(x=df1h.index, y=df1h['EMA50'], line=dict(color='orange', width=1), name="EMA 50"))
        fig.add_trace(go.Scatter(x=df1h.index, y=df1h['EMA200'], line=dict(color='blue', width=2), name="EMA 200"))
        fig.update_layout(template="plotly_white", height=500, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.info("Searching for asset data...")

time.sleep(60)
st.rerun()
