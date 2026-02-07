import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
import time

st.set_page_config(page_title="Universal AI Predictor", layout="wide")

# --- INDICATOR CALCULATIONS ---
def calculate_all_metrics(df):
    if len(df) < 50: return df
    # 1. EMAs for Trend
    df['EMA100'] = df['Close'].ewm(span=100, adjust=False).mean()
    df['EMA200'] = df['Close'].ewm(span=200, adjust=False).mean()
    
    # 2. RSI for Momentum
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-9)
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # 3. Bollinger Bands for Volatility
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['Std'] = df['Close'].rolling(window=20).std()
    df['Upper'] = df['MA20'] + (df['Std'] * 2)
    df['Lower'] = df['MA20'] - (df['Std'] * 2)
    return df

def get_candle_pattern(df):
    if len(df) < 2: return "Neutral"
    last = df.iloc[-1]
    prev = df.iloc[-2]
    body = abs(last['Open'] - last['Close'])
    # Hammer Detection
    lower_wick = min(last['Open'], last['Close']) - last['Low']
    if lower_wick > (body * 2) and (last['High'] - max(last['Open'], last['Close'])) < (body * 0.5):
        return "🔨 Hammer (Bullish Reversal)"
    # Engulfing Detection
    if last['Close'] > prev['Open'] and last['Open'] < prev['Close'] and prev['Close'] < prev['Open']:
        return "🟢 Bullish Engulfing"
    return "No Pattern"

# --- SIDEBAR: ADD ANY ASSET ---
st.sidebar.header("🔍 Market Scanner")
# Changed from selectbox to text_input so you can add ANY symbol
user_input = st.sidebar.text_input("Enter Asset Symbol (e.g. BTC-USD, AAPL, EURUSD=X)", "BTC-USD")
asset = user_input.strip().upper()
refresh_time = st.sidebar.slider("Refresh Interval (sec)", 30, 300, 60)

# --- MAIN DASHBOARD ---
st.title(f"🤖 AI Confluence Analysis: {asset}")

try:
    # Fetch data across multiple timeframes for the prediction
    tfs = ["5m", "30m", "1h", "4h"]
    scores = []
    
    st.subheader("Multi-Timeframe Signal Scan")
    cols = st.columns(len(tfs))
    
    for i, tf in enumerate(tfs):
        # We need 1mo of data to ensure EMA 200 is accurate
        df_tf = yf.download(asset, period="1mo", interval=tf, progress=False)
        if isinstance(df_tf.columns, pd.MultiIndex): df_tf.columns = df_tf.columns.get_level_values(0)
        
        if not df_tf.empty and len(df_tf) > 100:
            df_tf = calculate_all_metrics(df_tf)
            pattern = get_candle_pattern(df_tf)
            curr = df_tf.iloc[-1]
            
            # Prediction Scoring Logic
            score = 0
            if curr['Close'] > curr['EMA200']: score += 1 # Trend
            if curr['RSI'] < 40: score += 1 # Momentum
            if "Bullish" in pattern or "Hammer" in pattern: score += 1 # Candle
            scores.append(score)
            
            with cols[i]:
                st.metric(f"{tf} Score", f"{score}/3")
                st.write(f"**Pattern:** {pattern}")
                st.caption(f"RSI: {curr['RSI']:.1f}")
        else:
            cols[i].warning(f"No {tf} Data")

    # Final Prediction
    st.divider()
    avg_score = sum(scores) / len(scores) if scores else 0
    if avg_score >= 2:
        st.success(f"### 🚀 FINAL PREDICTION: STRONG BUY SIGNAL\nHigh Confluence across multiple timeframes.")
    elif avg_score <= 0.5:
        st.error(f"### 📉 FINAL PREDICTION: SELL/WEAK\nStrong Bearish pressure or overextension.")
    else:
        st.warning(f"### ⚖️ FINAL PREDICTION: NEUTRAL\nMixed signals. Wait for clearer patterns.")

    # Main Candlestick Chart
    st.subheader(f"Interactive Analysis Chart (30m)")
    main_df = yf.download(asset, period="1mo", interval="30m", progress=False)
    if isinstance(main_df.columns, pd.MultiIndex): main_df.columns = main_df.columns.get_level_values(0)
    main_df = calculate_all_metrics(main_df)

    fig = go.Figure(data=[go.Candlestick(x=main_df.index, open=main_df['Open'], high=main_df['High'], low=main_df['Low'], close=main_df['Close'], name="Candles")])
    fig.add_trace(go.Scatter(x=main_df.index, y=main_df['EMA100'], name="EMA 100", line=dict(color='orange', width=1)))
    fig.add_trace(go.Scatter(x=main_df.index, y=main_df['EMA200'], name="EMA 200", line=dict(color='blue', width=1.5)))
    fig.update_layout(template="plotly_dark", xaxis_rangeslider_visible=False, height=600)
    st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.error(f"Could not load asset '{asset}'. Please ensure the ticker is correct.")

# Auto-refresh logic
time.sleep(refresh_time)
st.rerun()
