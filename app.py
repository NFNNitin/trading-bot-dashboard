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
    /* Main Background */
    .stApp { background-color: #0e1117; color: white; }
    
    /* Metrics */
    .stMetric { background-color: #1c1c1c; border: 1px solid #333; padding: 10px; border-radius: 5px; }
    
    /* Watchlist - WHITE Background */
    .watchlist-card {
        background-color: #ffffff; 
        color: #000000; 
        padding: 10px; 
        border-radius: 5px; 
        margin-bottom: 8px; 
        border-left: 5px solid #ccc;
        font-weight: bold;
        box-shadow: 0px 2px 5px rgba(0,0,0,0.1);
    }
    .buy-signal { border-left: 7px solid #00c853 !important; }
    .sell-signal { border-left: 7px solid #d50000 !important; }
    
    /* Text Helpers */
    .small-text { font-size: 12px; color: #555; }
</style>
""", unsafe_allow_html=True)

# --- 1. ADVANCED MATH ENGINE ---
def calculate_adx(df, n=14):
    """Calculates ADX to determine Trend Strength."""
    df['H-L'] = df['High'] - df['Low']
    df['H-PC'] = abs(df['High'] - df['Close'].shift(1))
    df['L-PC'] = abs(df['Low'] - df['Close'].shift(1))
    df['TR'] = df[['H-L', 'H-PC', 'L-PC']].max(axis=1)
    df['DMplus'] = np.where((df['High'] - df['High'].shift(1)) > (df['Low'].shift(1) - df['Low']), df['High'] - df['High'].shift(1), 0)
    df['DMplus'] = np.where(df['DMplus'] < 0, 0, df['DMplus'])
    df['DMminus'] = np.where((df['Low'].shift(1) - df['Low']) > (df['High'] - df['High'].shift(1)), df['Low'].shift(1) - df['Low'], 0)
    df['DMminus'] = np.where(df['DMminus'] < 0, 0, df['DMminus'])
    TRn = []
    DMplusN = []
    DMminusN = []
    TR = df['TR'].tolist()
    DMplus = df['DMplus'].tolist()
    DMminus = df['DMminus'].tolist()
    for i in range(len(df)):
        if i < n:
            TRn.append(np.NaN)
            DMplusN.append(np.NaN)
            DMminusN.append(np.NaN)
        elif i == n:
            TRn.append(df['TR'].iloc[:n].sum())
            DMplusN.append(df['DMplus'].iloc[:n].sum())
            DMminusN.append(df['DMminus'].iloc[:n].sum())
        else:
            TRn.append(TRn[i-1] - (TRn[i-1]/n) + TR[i])
            DMplusN.append(DMplusN[i-1] - (DMplusN[i-1]/n) + DMplus[i])
            DMminusN.append(DMminusN[i-1] - (DMminusN[i-1]/n) + DMminus[i])
    df['TRn'] = TRn
    df['DMplusN'] = DMplusN
    df['DMminusN'] = DMminusN
    df['DIplus'] = 100 * (df['DMplusN'] / df['TRn'])
    df['DIminus'] = 100 * (df['DMminusN'] / df['TRn'])
    df['DX'] = 100 * abs((df['DIplus'] - df['DIminus']) / (df['DIplus'] + df['DIminus']))
    df['ADX'] = df['DX'].rolling(n).mean()
    return df

def get_data(symbol):
    try:
        # Fetch data
        df_5m = yf.download(symbol, period="5d", interval="5m", progress=False)
        df_1h = yf.download(symbol, period="1mo", interval="1h", progress=False)
        df_daily = yf.download(symbol, period="1y", interval="1d", progress=False)
        
        if df_5m.empty or df_1h.empty: return None

        # Clean Headers
        for d in [df_5m, df_1h, df_daily]:
            if isinstance(d.columns, pd.MultiIndex): d.columns = d.columns.get_level_values(0)

        data = {}
        data['5m'] = df_5m
        data['15m'] = df_5m.resample('15min').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}).dropna()
        data['30m'] = df_5m.resample('30min').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}).dropna()
        data['1h'] = df_1h
        data['4h'] = df_1h.resample('4h').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}).dropna()
        data['Daily'] = df_daily
        return data
    except:
        return None

def add_indicators(df):
    if len(df) < 50: return df
    # Trend
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['EMA200'] = df['Close'].ewm(span=200, adjust=False).mean()
    
    # Momentum (RSI)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-9)
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # Fast Momentum (Stochastic)
    low_14 = df['Low'].rolling(14).min()
    high_14 = df['High'].rolling(14).max()
    df['%K'] = (df['Close'] - low_14) * 100 / (high_14 - low_14)
    df['%D'] = df['%K'].rolling(3).mean()

    # Volatility (ATR)
    df['ATR'] = (df['High'] - df['Low']).rolling(14).mean()
    
    # Trend Strength (ADX) - Simple approximation for speed if full func fails
    df = calculate_adx(df)
    
    return df

def get_pivots(df_daily):
    last = df_daily.iloc[-2]
    P = (last['High'] + last['Low'] + last['Close']) / 3
    R1 = (2 * P) - last['Low']
    S1 = (2 * P) - last['High']
    return P, R1, S1

# --- 2. LOGIC ENGINE (With Trend Alignment) ---
def generate_signal(df, timeframe):
    curr = df.iloc[-1]
    
    # Base Trend
    trend = "BULL" if curr['Close'] > curr['EMA200'] else "BEAR"
    
    # Trend Strength (ADX)
    adx_status = "WEAK" if curr['ADX'] < 20 else "STRONG"
    
    signal = "NEUTRAL"
    
    # LOGIC: Only trade if ADX > 20 (Trend is real)
    if adx_status == "STRONG":
        if trend == "BULL":
            if curr['RSI'] < 45 or curr['%K'] < 20: signal = "BUY" # Pullback Buy
        if trend == "BEAR":
            if curr['RSI'] > 55 or curr['%K'] > 80: signal = "SELL" # Pullback Sell
            
    return {"Signal": signal, "Trend": trend, "RSI": curr['RSI'], "ADX": curr['ADX'], "Price": curr['Close'], "ATR": curr['ATR']}

# --- 3. UI DASHBOARD ---
st.sidebar.header("🔍 Market Watch")
symbol_input = st.sidebar.text_input("Main Asset", "GC=F").upper()

if st.sidebar.button("🔄 Refresh Now"):
    st.rerun()

st.sidebar.divider()
st.sidebar.subheader("Live Watchlist")
watchlist = ["GC=F", "SI=F", "BTC-USD", "CL=F", "DX-Y", "EURUSD=X"]

for w_sym in watchlist:
    try:
        w_df = yf.download(w_sym, period="2d", interval="1h", progress=False)
        if isinstance(w_df.columns, pd.MultiIndex): w_df.columns = w_df.columns.get_level_values(0)
        
        if not w_df.empty:
            w_curr = w_df.iloc[-1]
            w_ema = w_df['Close'].ewm(span=200, adjust=False).mean().iloc[-1]
            w_trend = "BULLISH" if w_curr['Close'] > w_ema else "BEARISH"
            css_class = "buy-signal" if w_curr['Close'] > w_ema else "sell-signal"
            
            st.sidebar.markdown(f"""
            <div class="watchlist-card {css_class}">
                <div style="font-size: 16px;">{w_sym}</div>
                <div class="small-text">{w_trend} | ${w_curr['Close']:,.2f}</div>
            </div>
            """, unsafe_allow_html=True)
    except:
        pass

# --- MAIN PAGE ---
st.title(f"🚀 Pro AI Trader: {symbol_input}")
data = get_data(symbol_input)

if data:
    curr_price = data['5m'].iloc[-1]['Close']
    pivot, r1, s1 = get_pivots(data['Daily'])
    
    # 1. METRICS
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Live Price", f"${curr_price:,.2f}")
    m2.metric("Daily Pivot", f"${pivot:,.2f}")
    m3.metric("Resistance (R1)", f"${r1:,.2f}")
    m4.metric("Support (S1)", f"${s1:,.2f}")

    # 2. ANALYSIS GRID
    st.subheader("1. Multi-Timeframe Scan")
    cols = st.columns(5)
    
    signals = {}
    timeframes = ['5m', '15m', '30m', '1h', '4h']
    
    for i, tf in enumerate(timeframes):
        df = add_indicators(data[tf])
        sig = generate_signal(df, tf)
        signals[tf] = sig
        
        color = "green" if sig['Signal'] == "BUY" else "red" if sig['Signal'] == "SELL" else "gray"
        
        with cols[i]:
            st.markdown(f"**{tf}**")
            st.markdown(f"<span style='color:{color}; font-weight:bold; font-size:18px'>{sig['Signal']}</span>", unsafe_allow_html=True)
            st.caption(f"Trend: {sig['Trend']}")
            st.caption(f"ADX: {sig['ADX']:.1f} ({'Strong' if sig['ADX']>20 else 'Weak'})")

    st.divider()

    # 3. CONFLUENCE STRATEGIES
    st.subheader("2. High-Probability Setups")
    s_col, i_col, sw_col = st.columns(3)
    
    # --- SCALPING (Strict Trend Filter) ---
    with s_col:
        st.markdown("### ⚡ Scalp (5m)")
        s_data = signals['5m']
        trend_1h = signals['1h']['Trend']
        
        # LOGIC: Scalp Signal MUST match 1H Trend
        if s_data['Signal'] == "BUY" and trend_1h == "BULL":
            st.success("✅ LONG SCALP")
            st.write(f"Entry: ${curr_price:,.2f}")
            st.write(f"TP: ${curr_price + (s_data['ATR']*1.5):,.2f}")
            st.write(f"SL: ${curr_price - (s_data['ATR']*1.0):,.2f}")
        elif s_data['Signal'] == "SELL" and trend_1h == "BEAR":
            st.error("✅ SHORT SCALP")
            st.write(f"Entry: ${curr_price:,.2f}")
            st.write(f"TP: ${curr_price - (s_data['ATR']*1.5):,.2f}")
            st.write(f"SL: ${curr_price + (s_data['ATR']*1.0):,.2f}")
        else:
            st.info("⏳ WAIT")
            if s_data['Signal'] != "NEUTRAL":
                st.caption(f"Ignored {s_data['Signal']} (Against 1H Trend)")

    # --- INTRADAY (Pivot Logic) ---
    with i_col:
        st.markdown("### 📅 Intraday (1H)")
        i_data = signals['1h']
        
        if i_data['Signal'] == "BUY" and curr_price > pivot:
            st.success("✅ DAY LONG")
            st.write(f"Target: ${r1:,.2f}")
            st.write(f"Stop: ${pivot:,.2f}")
        elif i_data['Signal'] == "SELL" and curr_price < pivot:
            st.error("✅ DAY SHORT")
            st.write(f"Target: ${s1:,.2f}")
            st.write(f"Stop: ${pivot:,.2f}")
        else:
            st.warning("⚖️ RANGING / WAIT")
            st.caption(f"ADX: {i_data['ADX']:.1f}")

    # --- SWING (4H Logic) ---
    with sw_col:
        st.markdown("### 🌊 Swing (4H)")
        w_data = signals['4h']
        if w_data['Signal'] == "BUY":
            st.success("✅ SWING LONG")
            st.write(f"Trail SL: ${curr_price - (w_data['ATR']*3):,.2f}")
        elif w_data['Signal'] == "SELL":
            st.error("✅ SWING SHORT")
            st.write(f"Trail SL: ${curr_price + (w_data['ATR']*3):,.2f}")
        else:
            st.info("💤 NO SETUP")

    # 4. CHART
    st.subheader("Price Action (1H)")
    fig = go.Figure(data=[go.Candlestick(x=data['1h'].index, open=data['1h']['Open'], high=data['1h']['High'], low=data['1h']['Low'], close=data['1h']['Close'])])
    fig.add_trace(go.Scatter(x=data['1h'].index, y=data['1h']['EMA50'], line=dict(color='orange'), name="EMA 50"))
    fig.add_trace(go.Scatter(x=data['1h'].index, y=data['1h']['EMA200'], line=dict(color='blue'), name="EMA 200"))
    fig.update_layout(height=500, template="plotly_dark", xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

else:
    st.error("Symbol not found. Try GC=F, BTC-USD")
