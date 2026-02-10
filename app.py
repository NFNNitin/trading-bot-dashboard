import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
import time

# --- 1. PAGE CONFIG & THEME ---
st.set_page_config(page_title="AI Terminal + Backtester", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #ffffff !important; color: #000000 !important; }
    h1, h2, h3, h4, p, span, label { color: #000000 !important; }
    .stMetric { background-color: #f8f9fa; border: 1px solid #dee2e6; padding: 15px; border-radius: 10px; }
    .signal-card { padding: 20px; border-radius: 10px; border: 1px solid #eee; margin-bottom: 20px; }
    .score-high { border-left: 10px solid #28a745; background-color: #f4fff7; }
    .score-med { border-left: 10px solid #ffc107; background-color: #fffdf4; }
    .score-low { border-left: 10px solid #dc3545; background-color: #fff5f5; }
    .stats-box { background-color: #f1f3f5; padding: 10px; border-radius: 5px; text-align: center; }
</style>
""", unsafe_allow_html=True)

# --- 2. THE ENGINE ---
def calculate_all_indicators(df):
    df = df.copy()
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    
    # Trend
    df['EMA21'] = df['Close'].ewm(span=21, adjust=False).mean()
    df['EMA200'] = df['Close'].ewm(span=200, adjust=False).mean()
    
    # Momentum (MACD)
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['Signal_Line'] = df['MACD'].ewm(span=9, adjust=False).mean()
    
    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-9))))
    
    # ATR (for SL/TP)
    df['tr'] = df[['High', 'Low', 'Close']].apply(lambda x: max(x[0]-x[1], abs(x[0]-x[2]), abs(x[1]-x[2])), axis=1)
    df['ATR'] = df['tr'].rolling(14).mean()
    return df.dropna()

def get_signal_at_index(df, idx):
    row = df.iloc[idx]
    score = 0
    factors = []
    
    # Logic Checks
    if row['Close'] > row['EMA200']: 
        score += 1
        factors.append("Above 200 EMA")
    if row['MACD'] > row['Signal_Line']:
        score += 1
        factors.append("MACD Bullish")
    if 40 < row['RSI'] < 70:
        score += 1
        factors.append("RSI Momentum")
    
    signal = "NEUTRAL"
    if score >= 3: signal = "STRONG BUY"
    elif score <= 0: signal = "STRONG SELL" # Simplified for backtest
    
    return {"signal": signal, "score": score, "price": row['Close'], "atr": row['ATR'], "factors": factors}

# --- 3. BACKTEST FUNCTION ---
def run_backtest(df):
    results = []
    # Skip first 50 rows for indicators to stabilize
    for i in range(50, len(df) - 10):
        sig_data = get_signal_at_index(df, i)
        if sig_data['signal'] == "NEUTRAL": continue
        
        entry = sig_data['price']
        atr = sig_data['atr']
        
        # Set TP/SL
        if sig_data['signal'] == "STRONG BUY":
            tp, sl = entry + (atr * 2), entry - (atr * 1.5)
            # Scan future candles
            for j in range(i + 1, len(df)):
                if df.iloc[j]['High'] >= tp: 
                    results.append(1); break
                if df.iloc[j]['Low'] <= sl: 
                    results.append(0); break
        
        elif sig_data['signal'] == "STRONG SELL":
            tp, sl = entry - (atr * 2), entry + (atr * 1.5)
            for j in range(i + 1, len(df)):
                if df.iloc[j]['Low'] <= tp: 
                    results.append(1); break
                if df.iloc[j]['High'] >= sl: 
                    results.append(0); break
                    
    if not results: return 0, 0
    win_rate = (sum(results) / len(results)) * 100
    return win_rate, len(results)

# --- 4. SIDEBAR ---
with st.sidebar:
    st.header("Settings")
    asset = st.text_input("Symbol", "GC=F").upper()
    if st.button("🔄 MANUAL REFRESH"): st.rerun()
    
    st.divider()
    st.subheader("Action")
    run_bt = st.button("📊 RUN 30-DAY BACKTEST")

# --- 5. MAIN DASHBOARD ---
try:
    data_1h = yf.download(asset, period="1mo", interval="1h", progress=False)
    if data_1h.empty:
        st.info("Searching for asset data...")
    else:
        df = calculate_all_indicators(data_1h)
        current_sig = get_signal_at_index(df, -1)
        
        st.title(f"🚀 AI Terminal: {asset}")
        
        # Backtest Display
        if run_bt:
            win_rate, total_trades = run_backtest(df)
            st.markdown(f"""
            <div style="background-color:#e7f5ff; padding:15px; border-radius:10px; border:1px solid #a5d8ff; margin-bottom:20px;">
                <h3 style="margin:0; color:#1971c2;">Backtest Results (Last 30 Days)</h3>
                <p>Total Trades: <b>{total_trades}</b> | Win Rate: <b>{win_rate:.1f}%</b></p>
            </div>
            """, unsafe_allow_html=True)

        # Top Stats
        m1, m2, m3 = st.columns(3)
        m1.metric("Live Price", f"${current_sig['price']:,.2f}")
        m2.metric("RSI", f"{df.iloc[-1]['RSI']:.1f}")
        m3.metric("Signal Score", f"{current_sig['score']}/3")

        # Current Signal Card
        status_css = "score-high" if current_sig['score'] >= 3 else "score-low"
        st.markdown(f"""
        <div class="signal-card {status_css}">
            <h2>Current Signal: {current_sig['signal']}</h2>
            <p><b>Logic Used:</b> {', '.join(current_sig['factors'])}</p>
        </div>
        """, unsafe_allow_html=True)

        # Chart
        fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'])])
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA200'], line=dict(color='blue', width=1.5), name="EMA 200"))
        fig.update_layout(template="plotly_white", height=500, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.error(f"Waiting for market feed...")

time.sleep(60)
st.rerun()
