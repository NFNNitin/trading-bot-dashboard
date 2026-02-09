import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
import time

# --- PAGE CONFIG ---
st.set_page_config(page_title="Pro AI Trader Ultimate", layout="wide")

# --- CUSTOM CSS FOR REAL-TIME FEEL ---
st.markdown("""
<style>
    .metric-card {background-color: #0e1117; border: 1px solid #303030; padding: 20px; border-radius: 10px; margin-bottom: 10px;}
    .bullish {color: #00ff00; font-weight: bold;}
    .bearish {color: #ff4b4b; font-weight: bold;}
    .neutral {color: #fca311; font-weight: bold;}
</style>
""", unsafe_allow_html=True)

# --- 1. DATA ENGINE (Advanced Resampling) ---
def get_data(symbol):
    """
    Fetches granular data and resamples it to generate 5m, 15m, 30m, 1h, and 4h datasets.
    This ensures we have valid data for all timeframes without making too many API calls.
    """
    try:
        # Fetch 5 days of 5m data (covers 5m, 15m, 30m, 1h)
        df_5m = yf.download(symbol, period="5d", interval="5m", progress=False)
        
        # Fetch 1 month of 1h data (covers 4h analysis)
        df_1h = yf.download(symbol, period="1mo", interval="1h", progress=False)
        
        if df_5m.empty or df_1h.empty: return None

        # Clean MultiIndex
        if isinstance(df_5m.columns, pd.MultiIndex): df_5m.columns = df_5m.columns.get_level_values(0)
        if isinstance(df_1h.columns, pd.MultiIndex): df_1h.columns = df_1h.columns.get_level_values(0)

        data = {}
        data['5m'] = df_5m
        data['15m'] = df_5m.resample('15min').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last', 'Volume':'sum'}).dropna()
        data['30m'] = df_5m.resample('30min').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last', 'Volume':'sum'}).dropna()
        data['1h'] = df_1h
        data['4h'] = df_1h.resample('4h').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last', 'Volume':'sum'}).dropna()
        
        return data
    except Exception as e:
        st.error(f"Data Error: {e}")
        return None

# --- 2. TECHNICAL INDICATOR LIBRARY ---
def add_indicators(df):
    if len(df) < 50: return df
    
    # Trend Indicators
    df['EMA9'] = df['Close'].ewm(span=9, adjust=False).mean()
    df['EMA21'] = df['Close'].ewm(span=21, adjust=False).mean()
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['EMA200'] = df['Close'].ewm(span=200, adjust=False).mean()
    
    # Momentum
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-9)
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # MACD
    ema12 = df['Close'].ewm(span=12, adjust=False).mean()
    ema26 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema12 - ema26
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    
    # Volatility (ATR for Stop Loss)
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    df['ATR'] = true_range.rolling(14).mean()
    
    return df

# --- 3. PATTERN RECOGNITION AI ---
def identify_candle(df):
    if len(df) < 3: return "Incomplete Data"
    row = df.iloc[-1]
    prev = df.iloc[-2]
    
    body = abs(row['Open'] - row['Close'])
    upper_wick = row['High'] - max(row['Open'], row['Close'])
    lower_wick = min(row['Open'], row['Close']) - row['Low']
    candle_range = row['High'] - row['Low']
    
    pattern = "Normal"
    
    # Hammer / Hanging Man
    if lower_wick > (body * 2) and upper_wick < (body * 0.5):
        pattern = "🔨 Hammer (Reversal)"
    
    # Shooting Star / Inverted Hammer
    elif upper_wick > (body * 2) and lower_wick < (body * 0.5):
        pattern = "🌠 Shooting Star (Reversal)"
        
    # Doji
    elif body < (candle_range * 0.1):
        pattern = "➕ Doji (Indecision)"
        
    # Engulfing
    elif row['Close'] > prev['Open'] and row['Open'] < prev['Close'] and row['Close'] > prev['High']:
        pattern = "🟢 Bullish Engulfing"
    elif row['Close'] < prev['Open'] and row['Open'] > prev['Close'] and row['Close'] < prev['Low']:
        pattern = "🔴 Bearish Engulfing"
        
    return pattern

# --- 4. TRADING STRATEGY ENGINE ---
def generate_signal(df, timeframe_name):
    if len(df) < 200: return None
    curr = df.iloc[-1]
    
    # Logic Checks
    trend = "BULLISH" if curr['Close'] > curr['EMA200'] else "BEARISH"
    momentum = "UP" if curr['RSI'] > 50 else "DOWN"
    macd_cross = "BULL" if curr['MACD'] > curr['Signal'] else "BEAR"
    
    score = 0
    if trend == "BULLISH": score += 1
    if momentum == "UP": score += 1
    if macd_cross == "BULL": score += 1
    
    signal = "NEUTRAL"
    if score == 3: signal = "STRONG BUY"
    elif score == 0: signal = "STRONG SELL"
    
    return {
        "Signal": signal,
        "Trend": trend,
        "RSI": round(curr['RSI'], 1),
        "ATR": curr['ATR'],
        "Price": curr['Close']
    }

# --- MAIN GUI ---
st.sidebar.header("⚙️ Settings")
symbol = st.sidebar.text_input("Asset (e.g., BTC-USD, GOLD)", "BTC-USD").upper()
st.sidebar.info("Auto-refreshes every 60s")

st.title(f"📊 Ultimate Trading Desk: {symbol}")

# Get Data
data_sets = get_data(symbol)

if data_sets:
    current_price = data_sets['5m'].iloc[-1]['Close']
    st.metric("Live Price", f"${current_price:,.2f}")
    
    # --- SECTION 1: TIMEFRAME SCANNER ---
    st.subheader("1. Multi-Timeframe Analysis")
    cols = st.columns(5)
    timeframes = ['5m', '15m', '30m', '1h', '4h']
    
    analysis_results = {}
    
    for i, tf in enumerate(timeframes):
        df = data_sets[tf]
        df = add_indicators(df)
        candle = identify_candle(df)
        sig = generate_signal(df, tf)
        
        analysis_results[tf] = sig # Store for strategy logic
        
        with cols[i]:
            st.markdown(f"**{tf} Chart**")
            st.caption(f"Candle: {candle}")
            if sig:
                color = "green" if "BUY" in sig['Signal'] else "red" if "SELL" in sig['Signal'] else "gray"
                st.markdown(f"<span style='color:{color}'>{sig['Signal']}</span>", unsafe_allow_html=True)
                st.write(f"RSI: {sig['RSI']}")

    st.divider()

    # --- SECTION 2: AI PREDICTION STRATEGIES ---
    st.subheader("2. AI Trade Setups")
    strat_cols = st.columns(3)
    
    # Helper to calculate SL/TP
    def calculate_trade(price, atr, mode="LONG", style="Scalp"):
        multiplier = 1.5 if style == "Scalp" else 2.0 if style == "Intraday" else 3.0
        sl_dist = atr * multiplier
        
        if mode == "LONG":
            sl = price - sl_dist
            tp = price + (sl_dist * 1.5) # 1.5 Risk Reward
        else:
            sl = price + sl_dist
            tp = price - (sl_dist * 1.5)
            
        return sl, tp

    # Strategy 1: SCALPING (5m/15m Focus)
    with strat_cols[0]:
        st.markdown("### ⚡ Scalping (Short Term)")
        s_data = analysis_results['5m']
        if s_data and "BUY" in s_data['Signal']:
            sl, tp = calculate_trade(s_data['Price'], s_data['ATR'], "LONG", "Scalp")
            st.success("Scalp Call: LONG")
            st.write(f"Entry: ${s_data['Price']:,.2f}")
            st.write(f"🎯 TP: ${tp:,.2f}")
            st.write(f"🛑 SL: ${sl:,.2f}")
        elif s_data and "SELL" in s_data['Signal']:
            sl, tp = calculate_trade(s_data['Price'], s_data['ATR'], "SHORT", "Scalp")
            st.error("Scalp Call: SHORT")
            st.write(f"Entry: ${s_data['Price']:,.2f}")
            st.write(f"🎯 TP: ${tp:,.2f}")
            st.write(f"🛑 SL: ${sl:,.2f}")
        else:
            st.info("No Scalp Setup")

    # Strategy 2: INTRADAY (30m/1H Focus)
    with strat_cols[1]:
        st.markdown("### 📅 Intraday (Day Trade)")
        i_data = analysis_results['30m']
        if i_data and "BUY" in i_data['Signal'] and analysis_results['1h']['Trend'] == "BULLISH":
            sl, tp = calculate_trade(i_data['Price'], i_data['ATR'], "LONG", "Intraday")
            st.success("Day Trade: LONG")
            st.write(f"Entry: ${i_data['Price']:,.2f}")
            st.write(f"🎯 TP: ${tp:,.2f}")
            st.write(f"🛑 SL: ${sl:,.2f}")
        elif i_data and "SELL" in i_data['Signal'] and analysis_results['1h']['Trend'] == "BEARISH":
            sl, tp = calculate_trade(i_data['Price'], i_data['ATR'], "SHORT", "Intraday")
            st.error("Day Trade: SHORT")
            st.write(f"Entry: ${i_data['Price']:,.2f}")
            st.write(f"🎯 TP: ${tp:,.2f}")
            st.write(f"🛑 SL: ${sl:,.2f}")
        else:
            st.info("No Intraday Setup")

    # Strategy 3: SWING (4H Focus)
    with strat_cols[2]:
        st.markdown("### 🌊 Swing (Multi-Day)")
        w_data = analysis_results['4h']
        if w_data and "BUY" in w_data['Signal']:
            sl, tp = calculate_trade(w_data['Price'], w_data['ATR'], "LONG", "Swing")
            st.success("Swing Call: LONG")
            st.write(f"Entry: ${w_data['Price']:,.2f}")
            st.write(f"🎯 TP: ${tp:,.2f}")
            st.write(f"🛑 SL: ${sl:,.2f}")
        elif w_data and "SELL" in w_data['Signal']:
            sl, tp = calculate_trade(w_data['Price'], w_data['ATR'], "SHORT", "Swing")
            st.error("Swing Call: SHORT")
            st.write(f"Entry: ${w_data['Price']:,.2f}")
            st.write(f"🎯 TP: ${tp:,.2f}")
            st.write(f"🛑 SL: ${sl:,.2f}")
        else:
            st.info("No Swing Setup")

    st.divider()
    
    # --- SECTION 3: VISUAL CHART ---
    st.subheader("Price Action & EMA Cloud (1H)")
    chart_df = data_sets['1h']
    fig = go.Figure(data=[go.Candlestick(x=chart_df.index, open=chart_df['Open'], high=chart_df['High'], low=chart_df['Low'], close=chart_df['Close'], name="Price")])
    fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df['EMA50'], name="EMA 50 (Fast Trend)", line=dict(color='orange')))
    fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df['EMA200'], name="EMA 200 (Major Trend)", line=dict(color='blue', width=2)))
    fig.update_layout(height=600, xaxis_rangeslider_visible=False, template="plotly_dark")
    st.plotly_chart(fig, use_container_width=True)

else:
    st.warning("Waiting for data... check the ticker symbol.")

time.sleep(60)
st.rerun()
