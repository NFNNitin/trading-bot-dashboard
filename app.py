import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time
import feedparser
from scipy import stats

# --- PAGE CONFIG ---
st.set_page_config(page_title="Pro AI Trader Ultimate", layout="wide")

# --- CUSTOM CSS FOR REAL-TIME FEEL ---
st.markdown("""
<style>
    .metric-card {background-color: #0e1117; border: 1px solid #303030; padding: 20px; border-radius: 10px; margin-bottom: 10px;}
    .bullish {color: #00ff00; font-weight: bold;}
    .bearish {color: #ff4b4b; font-weight: bold;}
    .neutral {color: #fca311; font-weight: bold;}
    .price-ticker {
        background: linear-gradient(90deg, #1e1e1e 0%, #2d2d2d 100%);
        padding: 15px;
        border-radius: 10px;
        margin: 10px 0;
        border-left: 4px solid #00ff00;
    }
    .news-item {
        background-color: #1a1a1a;
        padding: 12px;
        margin: 8px 0;
        border-radius: 8px;
        border-left: 3px solid #fca311;
    }
    .prediction-box {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 12px;
        color: white;
        margin: 15px 0;
    }
    .signal-strong-buy {
        background-color: #00ff00;
        color: black;
        padding: 8px 15px;
        border-radius: 5px;
        font-weight: bold;
    }
    .signal-strong-sell {
        background-color: #ff4b4b;
        color: white;
        padding: 8px 15px;
        border-radius: 5px;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# --- INITIALIZE SESSION STATE ---
if 'last_refresh' not in st.session_state:
    st.session_state.last_refresh = datetime.now()
if 'auto_refresh' not in st.session_state:
    st.session_state.auto_refresh = True

# --- LIVE PRICE FEED FOR MULTIPLE ASSETS ---
def get_live_prices():
    """Fetches real-time prices for major assets"""
    symbols = {
        'BTC-USD': 'Bitcoin',
        'GC=F': 'Gold',
        'SI=F': 'Silver',
        'DX-Y.NYB': 'Dollar Index',
        'XRP-USD': 'XRP'
    }
    
    prices = {}
    for symbol, name in symbols.items():
        try:
            ticker = yf.Ticker(symbol)
            data = ticker.history(period='1d', interval='1m')
            if not data.empty:
                current = data['Close'].iloc[-1]
                prev_close = ticker.info.get('previousClose', current)
                change = ((current - prev_close) / prev_close) * 100
                prices[name] = {
                    'price': current,
                    'change': change,
                    'symbol': symbol
                }
        except:
            prices[name] = {'price': 0, 'change': 0, 'symbol': symbol}
    
    return prices

# --- LIVE NEWS FEED ---
def get_crypto_news():
    """Fetches latest crypto/finance news from RSS feeds"""
    news_items = []
    
    # Multiple news sources
    feeds = [
        'https://cointelegraph.com/rss',
        'https://cryptonews.com/news/feed/',
    ]
    
    for feed_url in feeds:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:3]:  # Top 3 from each source
                news_items.append({
                    'title': entry.title,
                    'link': entry.link,
                    'published': entry.get('published', 'Recent')
                })
        except:
            continue
    
    return news_items[:10]  # Return top 10 news items

# --- 1. DATA ENGINE (Advanced Resampling) ---
def get_data(symbol):
    """
    Fetches granular data and resamples it to generate 5m, 15m, 30m, 1h, and 4h datasets.
    """
    try:
        # Fetch 5 days of 5m data
        df_5m = yf.download(symbol, period="5d", interval="5m", progress=False)
        
        # Fetch 1 month of 1h data
        df_1h = yf.download(symbol, period="1mo", interval="1h", progress=False)
        
        # Fetch daily data for longer-term analysis
        df_1d = yf.download(symbol, period="6mo", interval="1d", progress=False)
        
        if df_5m.empty or df_1h.empty: return None

        # Clean MultiIndex
        if isinstance(df_5m.columns, pd.MultiIndex): df_5m.columns = df_5m.columns.get_level_values(0)
        if isinstance(df_1h.columns, pd.MultiIndex): df_1h.columns = df_1h.columns.get_level_values(0)
        if isinstance(df_1d.columns, pd.MultiIndex): df_1d.columns = df_1d.columns.get_level_values(0)

        data = {}
        data['5m'] = df_5m
        data['15m'] = df_5m.resample('15min').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last', 'Volume':'sum'}).dropna()
        data['30m'] = df_5m.resample('30min').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last', 'Volume':'sum'}).dropna()
        data['1h'] = df_1h
        data['4h'] = df_1h.resample('4h').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last', 'Volume':'sum'}).dropna()
        data['1d'] = df_1d
        
        return data
    except Exception as e:
        st.error(f"Data Error: {e}")
        return None

# --- 2. ADVANCED TECHNICAL INDICATORS ---
def add_indicators(df):
    if len(df) < 50: return df
    
    # Trend Indicators
    df['EMA9'] = df['Close'].ewm(span=9, adjust=False).mean()
    df['EMA21'] = df['Close'].ewm(span=21, adjust=False).mean()
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['EMA200'] = df['Close'].ewm(span=200, adjust=False).mean()
    
    # Bollinger Bands
    df['BB_Middle'] = df['Close'].rolling(window=20).mean()
    df['BB_Std'] = df['Close'].rolling(window=20).std()
    df['BB_Upper'] = df['BB_Middle'] + (df['BB_Std'] * 2)
    df['BB_Lower'] = df['BB_Middle'] - (df['BB_Std'] * 2)
    
    # Momentum - RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-9)
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # Stochastic Oscillator
    low_14 = df['Low'].rolling(window=14).min()
    high_14 = df['High'].rolling(window=14).max()
    df['Stoch_K'] = 100 * ((df['Close'] - low_14) / (high_14 - low_14 + 1e-9))
    df['Stoch_D'] = df['Stoch_K'].rolling(window=3).mean()
    
    # MACD
    ema12 = df['Close'].ewm(span=12, adjust=False).mean()
    ema26 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema12 - ema26
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['Signal']
    
    # ADX (Trend Strength)
    plus_dm = df['High'].diff()
    minus_dm = -df['Low'].diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm < 0] = 0
    
    tr = pd.concat([df['High'] - df['Low'], 
                    abs(df['High'] - df['Close'].shift()), 
                    abs(df['Low'] - df['Close'].shift())], axis=1).max(axis=1)
    
    atr = tr.rolling(window=14).mean()
    plus_di = 100 * (plus_dm.rolling(window=14).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(window=14).mean() / atr)
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 1e-9)
    df['ADX'] = dx.rolling(window=14).mean()
    
    # ATR for Stop Loss
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    df['ATR'] = true_range.rolling(14).mean()
    
    # Volume Analysis
    df['Volume_MA'] = df['Volume'].rolling(window=20).mean()
    df['Volume_Ratio'] = df['Volume'] / (df['Volume_MA'] + 1e-9)
    
    # Price Rate of Change
    df['ROC'] = ((df['Close'] - df['Close'].shift(10)) / df['Close'].shift(10)) * 100
    
    # On-Balance Volume
    df['OBV'] = (np.sign(df['Close'].diff()) * df['Volume']).fillna(0).cumsum()
    
    return df

# --- 3. ADVANCED PATTERN RECOGNITION ---
def identify_candle(df):
    if len(df) < 3: return "Incomplete Data"
    row = df.iloc[-1]
    prev = df.iloc[-2]
    prev2 = df.iloc[-3] if len(df) > 3 else prev
    
    body = abs(row['Open'] - row['Close'])
    upper_wick = row['High'] - max(row['Open'], row['Close'])
    lower_wick = min(row['Open'], row['Close']) - row['Low']
    candle_range = row['High'] - row['Low']
    
    prev_body = abs(prev['Open'] - prev['Close'])
    
    pattern = "Normal"
    
    # Hammer / Hanging Man
    if lower_wick > (body * 2) and upper_wick < (body * 0.5):
        pattern = "🔨 Hammer (Bullish Reversal)"
    
    # Shooting Star
    elif upper_wick > (body * 2) and lower_wick < (body * 0.5):
        pattern = "🌠 Shooting Star (Bearish Reversal)"
        
    # Doji
    elif body < (candle_range * 0.1):
        pattern = "➕ Doji (Indecision)"
    
    # Bullish Engulfing
    elif (row['Close'] > row['Open'] and prev['Close'] < prev['Open'] and 
          row['Open'] <= prev['Close'] and row['Close'] > prev['Open']):
        pattern = "🟢 Bullish Engulfing (Strong Buy)"
    
    # Bearish Engulfing
    elif (row['Close'] < row['Open'] and prev['Close'] > prev['Open'] and 
          row['Open'] >= prev['Close'] and row['Close'] < prev['Open']):
        pattern = "🔴 Bearish Engulfing (Strong Sell)"
    
    # Morning Star (3-candle bullish reversal)
    elif (prev2['Close'] < prev2['Open'] and abs(prev['Open'] - prev['Close']) < prev_body * 0.3 
          and row['Close'] > row['Open'] and row['Close'] > (prev2['Open'] + prev2['Close'])/2):
        pattern = "⭐ Morning Star (Major Bullish Reversal)"
    
    # Evening Star (3-candle bearish reversal)
    elif (prev2['Close'] > prev2['Open'] and abs(prev['Open'] - prev['Close']) < prev_body * 0.3 
          and row['Close'] < row['Open'] and row['Close'] < (prev2['Open'] + prev2['Close'])/2):
        pattern = "🌙 Evening Star (Major Bearish Reversal)"
        
    return pattern

# --- 4. ADVANCED TRADING SIGNAL ENGINE ---
def generate_advanced_signal(df, timeframe_name):
    if len(df) < 200: return None
    curr = df.iloc[-1]
    prev = df.iloc[-2]
    
    signals = []
    score = 0
    max_score = 0
    
    # 1. TREND ANALYSIS (Weight: 3)
    max_score += 3
    if curr['Close'] > curr['EMA200']:
        score += 3
        signals.append("✅ Above 200 EMA (Strong Uptrend)")
    elif curr['Close'] < curr['EMA200']:
        score -= 3
        signals.append("⛔ Below 200 EMA (Strong Downtrend)")
    
    # 2. EMA ALIGNMENT (Weight: 2)
    max_score += 2
    if curr['EMA9'] > curr['EMA21'] > curr['EMA50']:
        score += 2
        signals.append("✅ Bullish EMA Stack")
    elif curr['EMA9'] < curr['EMA21'] < curr['EMA50']:
        score -= 2
        signals.append("⛔ Bearish EMA Stack")
    
    # 3. RSI MOMENTUM (Weight: 2)
    max_score += 2
    if curr['RSI'] > 70:
        score -= 2
        signals.append("⚠️ RSI Overbought (>70)")
    elif curr['RSI'] > 50:
        score += 2
        signals.append("✅ RSI Bullish (>50)")
    elif curr['RSI'] < 30:
        score += 1
        signals.append("💎 RSI Oversold (<30) - Potential Reversal")
    else:
        score -= 1
        signals.append("⛔ RSI Bearish (<50)")
    
    # 4. MACD CROSSOVER (Weight: 2)
    max_score += 2
    if curr['MACD'] > curr['Signal'] and prev['MACD'] <= prev['Signal']:
        score += 2
        signals.append("🚀 MACD Bullish Crossover (FRESH)")
    elif curr['MACD'] > curr['Signal']:
        score += 1
        signals.append("✅ MACD Above Signal")
    elif curr['MACD'] < curr['Signal'] and prev['MACD'] >= prev['Signal']:
        score -= 2
        signals.append("🔻 MACD Bearish Crossover (FRESH)")
    else:
        score -= 1
        signals.append("⛔ MACD Below Signal")
    
    # 5. STOCHASTIC (Weight: 1)
    max_score += 1
    if curr['Stoch_K'] > 80:
        signals.append("⚠️ Stochastic Overbought")
    elif curr['Stoch_K'] < 20:
        score += 1
        signals.append("💎 Stochastic Oversold")
    elif curr['Stoch_K'] > curr['Stoch_D']:
        signals.append("✅ Stochastic Bullish")
    
    # 6. BOLLINGER BANDS (Weight: 1)
    max_score += 1
    if curr['Close'] < curr['BB_Lower']:
        score += 1
        signals.append("💎 Price Below BB Lower (Oversold)")
    elif curr['Close'] > curr['BB_Upper']:
        score -= 1
        signals.append("⚠️ Price Above BB Upper (Overbought)")
    
    # 7. ADX TREND STRENGTH (Weight: 1)
    max_score += 1
    if curr['ADX'] > 25:
        signals.append(f"✅ Strong Trend (ADX: {curr['ADX']:.1f})")
        score += 1
    else:
        signals.append(f"⚠️ Weak Trend (ADX: {curr['ADX']:.1f})")
    
    # 8. VOLUME CONFIRMATION (Weight: 1)
    max_score += 1
    if curr['Volume_Ratio'] > 1.5:
        score += 1
        signals.append("✅ High Volume Confirmation")
    elif curr['Volume_Ratio'] < 0.5:
        signals.append("⚠️ Low Volume (Weak Move)")
    
    # Calculate normalized score (0-100)
    normalized_score = ((score + max_score) / (2 * max_score)) * 100
    
    # Determine signal strength
    if normalized_score >= 75:
        signal_type = "🟢 STRONG BUY"
        confidence = "Very High"
    elif normalized_score >= 60:
        signal_type = "🟢 BUY"
        confidence = "High"
    elif normalized_score >= 45:
        signal_type = "🟡 NEUTRAL/HOLD"
        confidence = "Medium"
    elif normalized_score >= 30:
        signal_type = "🔴 SELL"
        confidence = "High"
    else:
        signal_type = "🔴 STRONG SELL"
        confidence = "Very High"
    
    return {
        "Signal": signal_type,
        "Confidence": confidence,
        "Score": round(normalized_score, 1),
        "RSI": round(curr['RSI'], 1),
        "MACD": round(curr['MACD'], 4),
        "ADX": round(curr['ADX'], 1),
        "Stoch": round(curr['Stoch_K'], 1),
        "ATR": curr['ATR'],
        "Price": curr['Close'],
        "Signals": signals
    }

# --- 5. PRICE PREDICTION ENGINE ---
def predict_price_movement(df, timeframe):
    """Advanced price prediction using multiple methods"""
    if len(df) < 50:
        return None
    
    curr_price = df['Close'].iloc[-1]
    predictions = {}
    
    # Method 1: Linear Regression on recent trend
    recent_data = df['Close'].tail(20).values
    x = np.arange(len(recent_data))
    slope, intercept, r_value, p_value, std_err = stats.linregress(x, recent_data)
    
    # Predict next 1, 3, 5 periods
    predictions['Linear_1'] = slope * len(recent_data) + intercept
    predictions['Linear_3'] = slope * (len(recent_data) + 2) + intercept
    predictions['Linear_5'] = slope * (len(recent_data) + 4) + intercept
    
    # Method 2: EMA-based prediction
    ema_momentum = df['EMA9'].iloc[-1] - df['EMA21'].iloc[-1]
    predictions['EMA_Based'] = curr_price + (ema_momentum * 0.5)
    
    # Method 3: Bollinger Band reversion
    if curr_price < df['BB_Lower'].iloc[-1]:
        predictions['BB_Reversion'] = df['BB_Middle'].iloc[-1]
    elif curr_price > df['BB_Upper'].iloc[-1]:
        predictions['BB_Reversion'] = df['BB_Middle'].iloc[-1]
    else:
        predictions['BB_Reversion'] = curr_price
    
    # Method 4: ATR-based range prediction
    atr = df['ATR'].iloc[-1]
    predictions['Upper_Range'] = curr_price + (atr * 1.5)
    predictions['Lower_Range'] = curr_price - (atr * 1.5)
    
    # Ensemble prediction (average of methods)
    prediction_values = [predictions['Linear_1'], predictions['EMA_Based'], predictions['BB_Reversion']]
    ensemble = np.mean(prediction_values)
    
    movement = ((ensemble - curr_price) / curr_price) * 100
    
    return {
        'current': curr_price,
        'predicted': ensemble,
        'movement_pct': movement,
        'upper_range': predictions['Upper_Range'],
        'lower_range': predictions['Lower_Range'],
        'confidence': abs(r_value) * 100,  # R-squared as confidence
        'direction': '📈 UP' if movement > 0 else '📉 DOWN',
        'strength': 'Strong' if abs(movement) > 1 else 'Moderate' if abs(movement) > 0.3 else 'Weak'
    }

# --- 6. TRADE SETUP CALCULATOR ---
def calculate_trade(price, atr, mode="LONG", style="Scalp", risk_reward=1.5):
    """Enhanced trade calculator with risk management"""
    multiplier = 1.5 if style == "Scalp" else 2.0 if style == "Intraday" else 3.0
    sl_dist = atr * multiplier
    
    if mode == "LONG":
        sl = price - sl_dist
        tp = price + (sl_dist * risk_reward)
        breakeven = price + (sl_dist * 0.5)
    else:
        sl = price + sl_dist
        tp = price - (sl_dist * risk_reward)
        breakeven = price - (sl_dist * 0.5)
    
    risk_pct = (sl_dist / price) * 100
    reward_pct = ((tp - price) / price) * 100 if mode == "LONG" else ((price - tp) / price) * 100
    
    return {
        'entry': price,
        'sl': sl,
        'tp': tp,
        'breakeven': breakeven,
        'risk_pct': abs(risk_pct),
        'reward_pct': abs(reward_pct),
        'rr_ratio': risk_reward
    }

# ============================================
# MAIN APPLICATION
# ============================================

# --- SIDEBAR ---
st.sidebar.header("⚙️ Trading Settings")

# Manual Refresh Button
if st.sidebar.button("🔄 REFRESH NOW", use_container_width=True):
    st.session_state.last_refresh = datetime.now()
    st.rerun()

# Auto-refresh toggle
st.session_state.auto_refresh = st.sidebar.checkbox("Auto-Refresh (60s)", value=st.session_state.auto_refresh)

# Asset selection
symbol = st.sidebar.text_input("Main Asset Symbol", "BTC-USD").upper()

# Risk settings
st.sidebar.subheader("Risk Management")
risk_reward = st.sidebar.slider("Risk:Reward Ratio", 1.0, 3.0, 1.5, 0.5)
position_size = st.sidebar.number_input("Position Size ($)", min_value=100, value=1000, step=100)

st.sidebar.info(f"Last Refresh: {st.session_state.last_refresh.strftime('%H:%M:%S')}")

# --- MAIN DASHBOARD ---
st.title(f"📊 Ultimate AI Trading Dashboard")

# --- LIVE PRICE TICKER ---
st.subheader("🌐 Live Market Feed")
live_prices = get_live_prices()

ticker_cols = st.columns(5)
for idx, (name, data) in enumerate(live_prices.items()):
    with ticker_cols[idx]:
        color = "green" if data['change'] >= 0 else "red"
        st.markdown(f"""
        <div class="price-ticker" style="border-left-color: {color};">
            <div style="font-size: 12px; color: #888;">{name}</div>
            <div style="font-size: 18px; font-weight: bold;">${data['price']:,.2f}</div>
            <div style="font-size: 14px; color: {color};">
                {'▲' if data['change'] >= 0 else '▼'} {abs(data['change']):.2f}%
            </div>
        </div>
        """, unsafe_allow_html=True)

st.divider()

# --- MAIN ASSET ANALYSIS ---
st.subheader(f"📈 Main Asset: {symbol}")

data_sets = get_data(symbol)

if data_sets:
    current_price = data_sets['5m'].iloc[-1]['Close']
    price_change_24h = ((current_price - data_sets['1d'].iloc[-2]['Close']) / data_sets['1d'].iloc[-2]['Close']) * 100
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("💰 Current Price", f"${current_price:,.2f}", f"{price_change_24h:+.2f}%")
    with col2:
        high_24h = data_sets['5m']['High'].tail(288).max()  # 288 5-min periods = 24h
        st.metric("📊 24h High", f"${high_24h:,.2f}")
    with col3:
        low_24h = data_sets['5m']['Low'].tail(288).min()
        st.metric("📊 24h Low", f"${low_24h:,.2f}")
    with col4:
        volume_24h = data_sets['5m']['Volume'].tail(288).sum()
        st.metric("📊 24h Volume", f"{volume_24h:,.0f}")
    
    st.divider()
    
    # --- AI PRICE PREDICTION ---
    st.subheader("🤖 AI Price Prediction Engine")
    
    pred_cols = st.columns([2, 1])
    
    with pred_cols[0]:
        # Get predictions for different timeframes
        pred_5m = predict_price_movement(add_indicators(data_sets['5m']), '5m')
        pred_1h = predict_price_movement(add_indicators(data_sets['1h']), '1h')
        pred_4h = predict_price_movement(add_indicators(data_sets['4h']), '4h')
        
        if pred_1h:
            st.markdown(f"""
            <div class="prediction-box">
                <h3>🎯 Next Hour Prediction</h3>
                <div style="font-size: 32px; margin: 10px 0;">
                    ${pred_1h['predicted']:,.2f} {pred_1h['direction']}
                </div>
                <div style="font-size: 18px;">
                    Expected Movement: <b>{pred_1h['movement_pct']:+.2f}%</b> ({pred_1h['strength']})
                </div>
                <div style="margin-top: 10px; font-size: 14px;">
                    Confidence: {pred_1h['confidence']:.1f}% | Range: ${pred_1h['lower_range']:,.2f} - ${pred_1h['upper_range']:,.2f}
                </div>
            </div>
            """, unsafe_allow_html=True)
    
    with pred_cols[1]:
        if pred_5m and pred_4h:
            st.markdown("**⚡ Short-Term (5m)**")
            st.write(f"{pred_5m['direction']} {pred_5m['movement_pct']:+.2f}%")
            st.write(f"Strength: {pred_5m['strength']}")
            
            st.markdown("**📅 Medium-Term (4h)**")
            st.write(f"{pred_4h['direction']} {pred_4h['movement_pct']:+.2f}%")
            st.write(f"Strength: {pred_4h['strength']}")
    
    st.divider()
    
    # --- MULTI-TIMEFRAME ANALYSIS ---
    st.subheader("⏰ Multi-Timeframe Scanner")
    
    tf_cols = st.columns(5)
    timeframes = ['5m', '15m', '30m', '1h', '4h']
    
    analysis_results = {}
    
    for i, tf in enumerate(timeframes):
        df = data_sets[tf]
        df = add_indicators(df)
        candle = identify_candle(df)
        sig = generate_advanced_signal(df, tf)
        
        analysis_results[tf] = sig
        
        with tf_cols[i]:
            st.markdown(f"### {tf}")
            st.caption(candle)
            
            if sig:
                # Color-coded signal display
                if "STRONG BUY" in sig['Signal']:
                    st.markdown(f"<div class='signal-strong-buy'>{sig['Signal']}</div>", unsafe_allow_html=True)
                elif "STRONG SELL" in sig['Signal']:
                    st.markdown(f"<div class='signal-strong-sell'>{sig['Signal']}</div>", unsafe_allow_html=True)
                else:
                    st.markdown(f"**{sig['Signal']}**")
                
                st.progress(sig['Score'] / 100)
                st.caption(f"Score: {sig['Score']}/100")
                st.write(f"📊 RSI: {sig['RSI']}")
                st.write(f"💪 ADX: {sig['ADX']}")
                
                # Show top 3 signals
                with st.expander("Details"):
                    for signal in sig['Signals'][:3]:
                        st.caption(signal)
    
    st.divider()
    
    # --- AI TRADING STRATEGIES ---
    st.subheader("🎯 AI Trade Setups")
    
    strat_cols = st.columns(3)
    
    # Strategy 1: SCALPING
    with strat_cols[0]:
        st.markdown("### ⚡ Scalping (1-15min)")
        s_data = analysis_results.get('5m')
        
        if s_data:
            if "BUY" in s_data['Signal']:
                trade = calculate_trade(s_data['Price'], s_data['ATR'], "LONG", "Scalp", risk_reward)
                st.success("📈 LONG SETUP")
                st.write(f"**Entry:** ${trade['entry']:,.2f}")
                st.write(f"🎯 **TP:** ${trade['tp']:,.2f} (+{trade['reward_pct']:.2f}%)")
                st.write(f"🛑 **SL:** ${trade['sl']:,.2f} (-{trade['risk_pct']:.2f}%)")
                st.write(f"⚖️ **Breakeven:** ${trade['breakeven']:,.2f}")
                
                # Position sizing
                risk_amount = position_size * (trade['risk_pct'] / 100)
                st.info(f"Risk: ${risk_amount:.2f} | Reward: ${risk_amount * risk_reward:.2f}")
                
            elif "SELL" in s_data['Signal']:
                trade = calculate_trade(s_data['Price'], s_data['ATR'], "SHORT", "Scalp", risk_reward)
                st.error("📉 SHORT SETUP")
                st.write(f"**Entry:** ${trade['entry']:,.2f}")
                st.write(f"🎯 **TP:** ${trade['tp']:,.2f} (+{trade['reward_pct']:.2f}%)")
                st.write(f"🛑 **SL:** ${trade['sl']:,.2f} (-{trade['risk_pct']:.2f}%)")
                st.write(f"⚖️ **Breakeven:** ${trade['breakeven']:,.2f}")
                
                risk_amount = position_size * (trade['risk_pct'] / 100)
                st.info(f"Risk: ${risk_amount:.2f} | Reward: ${risk_amount * risk_reward:.2f}")
            else:
                st.info("⏸️ No Setup - Wait for Confirmation")
                st.caption(f"Score: {s_data['Score']}/100")
    
    # Strategy 2: INTRADAY
    with strat_cols[1]:
        st.markdown("### 📅 Intraday (30m-1h)")
        i_data = analysis_results.get('30m')
        h_data = analysis_results.get('1h')
        
        if i_data and h_data:
            # Require alignment between 30m and 1h
            if "BUY" in i_data['Signal'] and "BUY" in h_data['Signal']:
                trade = calculate_trade(i_data['Price'], i_data['ATR'], "LONG", "Intraday", risk_reward)
                st.success("📈 LONG SETUP (Confirmed)")
                st.write(f"**Entry:** ${trade['entry']:,.2f}")
                st.write(f"🎯 **TP:** ${trade['tp']:,.2f} (+{trade['reward_pct']:.2f}%)")
                st.write(f"🛑 **SL:** ${trade['sl']:,.2f} (-{trade['risk_pct']:.2f}%)")
                st.write(f"⚖️ **Breakeven:** ${trade['breakeven']:,.2f}")
                
                risk_amount = position_size * (trade['risk_pct'] / 100)
                st.info(f"Risk: ${risk_amount:.2f} | Reward: ${risk_amount * risk_reward:.2f}")
                
            elif "SELL" in i_data['Signal'] and "SELL" in h_data['Signal']:
                trade = calculate_trade(i_data['Price'], i_data['ATR'], "SHORT", "Intraday", risk_reward)
                st.error("📉 SHORT SETUP (Confirmed)")
                st.write(f"**Entry:** ${trade['entry']:,.2f}")
                st.write(f"🎯 **TP:** ${trade['tp']:,.2f} (+{trade['reward_pct']:.2f}%)")
                st.write(f"🛑 **SL:** ${trade['sl']:,.2f} (-{trade['risk_pct']:.2f}%)")
                st.write(f"⚖️ **Breakeven:** ${trade['breakeven']:,.2f}")
                
                risk_amount = position_size * (trade['risk_pct'] / 100)
                st.info(f"Risk: ${risk_amount:.2f} | Reward: ${risk_amount * risk_reward:.2f}")
            else:
                st.warning("⏸️ No Clear Setup")
                st.caption(f"30m: {i_data['Score']}/100 | 1h: {h_data['Score']}/100")
                st.caption("Waiting for timeframe alignment")
    
    # Strategy 3: SWING
    with strat_cols[2]:
        st.markdown("### 🌊 Swing (4h-Daily)")
        w_data = analysis_results.get('4h')
        
        if w_data:
            if "BUY" in w_data['Signal']:
                trade = calculate_trade(w_data['Price'], w_data['ATR'], "LONG", "Swing", risk_reward)
                st.success("📈 LONG SETUP")
                st.write(f"**Entry:** ${trade['entry']:,.2f}")
                st.write(f"🎯 **TP:** ${trade['tp']:,.2f} (+{trade['reward_pct']:.2f}%)")
                st.write(f"🛑 **SL:** ${trade['sl']:,.2f} (-{trade['risk_pct']:.2f}%)")
                st.write(f"⚖️ **Breakeven:** ${trade['breakeven']:,.2f}")
                
                risk_amount = position_size * (trade['risk_pct'] / 100)
                st.info(f"Risk: ${risk_amount:.2f} | Reward: ${risk_amount * risk_reward:.2f}")
                
            elif "SELL" in w_data['Signal']:
                trade = calculate_trade(w_data['Price'], w_data['ATR'], "SHORT", "Swing", risk_reward)
                st.error("📉 SHORT SETUP")
                st.write(f"**Entry:** ${trade['entry']:,.2f}")
                st.write(f"🎯 **TP:** ${trade['tp']:,.2f} (+{trade['reward_pct']:.2f}%)")
                st.write(f"🛑 **SL:** ${trade['sl']:,.2f} (-{trade['risk_pct']:.2f}%)")
                st.write(f"⚖️ **Breakeven:** ${trade['breakeven']:,.2f}")
                
                risk_amount = position_size * (trade['risk_pct'] / 100)
                st.info(f"Risk: ${risk_amount:.2f} | Reward: ${risk_amount * risk_reward:.2f}")
            else:
                st.info("⏸️ No Setup")
                st.caption(f"Score: {w_data['Score']}/100")
    
    st.divider()
    
    # --- ADVANCED CHART ---
    st.subheader("📈 Advanced Price Chart (1H)")
    
    chart_df = add_indicators(data_sets['1h'])
    
    # Create subplots
    from plotly.subplots import make_subplots
    
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.6, 0.2, 0.2],
        subplot_titles=('Price Action', 'RSI', 'MACD')
    )
    
    # Candlestick chart
    fig.add_trace(
        go.Candlestick(
            x=chart_df.index,
            open=chart_df['Open'],
            high=chart_df['High'],
            low=chart_df['Low'],
            close=chart_df['Close'],
            name="Price"
        ),
        row=1, col=1
    )
    
    # EMAs
    fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df['EMA9'], name="EMA 9", line=dict(color='yellow', width=1)), row=1, col=1)
    fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df['EMA21'], name="EMA 21", line=dict(color='orange', width=1)), row=1, col=1)
    fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df['EMA50'], name="EMA 50", line=dict(color='blue', width=2)), row=1, col=1)
    fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df['EMA200'], name="EMA 200", line=dict(color='white', width=2)), row=1, col=1)
    
    # Bollinger Bands
    fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df['BB_Upper'], name="BB Upper", line=dict(color='gray', dash='dash', width=1)), row=1, col=1)
    fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df['BB_Lower'], name="BB Lower", line=dict(color='gray', dash='dash', width=1)), row=1, col=1)
    
    # RSI
    fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df['RSI'], name="RSI", line=dict(color='purple')), row=2, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)
    
    # MACD
    fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df['MACD'], name="MACD", line=dict(color='blue')), row=3, col=1)
    fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df['Signal'], name="Signal", line=dict(color='orange')), row=3, col=1)
    fig.add_trace(go.Bar(x=chart_df.index, y=chart_df['MACD_Hist'], name="Histogram"), row=3, col=1)
    
    fig.update_layout(
        height=800,
        xaxis_rangeslider_visible=False,
        template="plotly_dark",
        showlegend=True,
        hovermode='x unified'
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    st.divider()
    
    # --- LIVE NEWS FEED ---
    st.subheader("📰 Live Crypto & Finance News")
    
    news_items = get_crypto_news()
    
    if news_items:
        news_cols = st.columns(2)
        for idx, item in enumerate(news_items[:8]):  # Show 8 items
            with news_cols[idx % 2]:
                st.markdown(f"""
                <div class="news-item">
                    <div style="font-weight: bold; margin-bottom: 5px;">{item['title']}</div>
                    <div style="font-size: 12px; color: #888;">{item['published']}</div>
                    <a href="{item['link']}" target="_blank" style="font-size: 12px; color: #fca311;">Read more →</a>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("News feed temporarily unavailable. Check back soon!")

else:
    st.warning("⚠️ Unable to fetch data. Please check the ticker symbol and try again.")

# --- AUTO-REFRESH LOGIC ---
if st.session_state.auto_refresh:
    time.sleep(60)
    st.rerun()
