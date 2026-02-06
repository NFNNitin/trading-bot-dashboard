import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
import time

st.set_page_config(page_title="AI Trading Predictor", layout="wide")

# --- INDICATOR CALCULATIONS ---
def get_indicators(df):
    # EMAs
    df['EMA100'] = df['Close'].ewm(span=100, adjust=False).mean()
    df['EMA200'] = df['Close'].ewm(span=200, adjust=False).mean()
    
    # RSI (14 Period)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    return df

def find_levels(df):
    # Simple logic to find horizontal Support and Resistance from past peaks/troughs
    levels = []
    for i in range(2, len(df)-2):
        if df['Low'][i] < df['Low'][i-1] and df['Low'][i] < df['Low'][i+1] and df['Low'][i] < df['Low'][i-2] and df['Low'][i] < df['Low'][i+2]:
            levels.append(('Support', df['Low'][i]))
        if df['High'][i] > df['High'][i-1] and df['High'][i] > df['High'][i+1] and df['High'][i] > df['High'][i-2] and df['High'][i] > df['High'][i+2]:
            levels.append(('Resistance', df['High'][i]))
    return levels

# --- DASHBOARD UI ---
st.title("🤖 AI Market Confluence Predictor")
symbol = st.sidebar.selectbox("Select Asset", ["BTC-USD", "XRP-USD", "ETH-USD", "GC=F", "SI=F"])

# Fetch Data (30m for primary analysis)
df = yf.download(symbol, period="1mo", interval="30m", progress=False)
if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
df = get_indicators(df)
levels = find_levels(df)

# --- PREDICTION LOGIC ---
curr = df.iloc[-1]
score = 0
reasons = []

# 1. EMA Trend (2 Points)
if curr['Close'] > curr['EMA100'] and curr['Close'] > curr['EMA200']:
    score += 2
    reasons.append("Price is in a Bullish Trend (Above EMAs)")
elif curr['Close'] < curr['EMA100'] and curr['Close'] < curr['EMA200']:
    score -= 2
    reasons.append("Price is in a Bearish Trend (Below EMAs)")

# 2. RSI Momentum (1 Point)
if curr['RSI'] < 35:
    score += 1
    reasons.append("RSI is Oversold (Potential Bounce)")
elif curr['RSI'] > 65:
    score -= 1
    reasons.append("RSI is Overbought (Potential Pullback)")

# 3. Support/Resistance Proximity (1 Point)
last_support = [l[1] for l in levels if l[0] == 'Support'][-1] if any(l[0] == 'Support' for l in levels) else 0
if abs(curr['Close'] - last_support) / curr['Close'] < 0.01:
    score += 1
    reasons.append("Price is near a major Support level")

# Display Prediction
st.divider()
c1, c2 = st.columns([1, 2])
with c1:
    if score >= 2:
        st.success(f"### PREDICTION: BUY\nConfidence: {abs(score)}/4")
    elif score <= -2:
        st.error(f"### PREDICTION: SELL\nConfidence: {abs(score)}/4")
    else:
        st.warning(f"### PREDICTION: NEUTRAL\nConfidence: Low")
    
    for r in reasons:
        st.write(f"- {r}")

# --- CANDLESTICK CHART ---
with c2:
    fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Candles")])
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA100'], name="EMA 100", line=dict(color='orange')))
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA200'], name="EMA 200", line=dict(color='blue')))
    
    # Plot Support Levels
    for level in levels[-5:]: # Show last 5 major levels
        color = "green" if level[0] == "Support" else "red"
        fig.add_hline(y=level[1], line_dash="dash", line_color=color, annotation_text=level[0])
        
    fig.update_layout(xaxis_rangeslider_visible=False, height=500, template="plotly_dark")
    st.plotly_chart(fig, use_container_width=True)

# Update Frequency
time.sleep(60)
st.rerun()
