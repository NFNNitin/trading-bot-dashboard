import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time
from scipy import stats

# Try to import feedparser, use fallback if not available
try:
    import feedparser
    FEEDPARSER_AVAILABLE = True
except ImportError:
    FEEDPARSER_AVAILABLE = False
    st.warning("⚠️ feedparser not installed. News feed will be limited. Install with: pip install feedparser")

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
    .conflict-critical {
        background-color: #ff4b4b;
        padding: 15px;
        border-radius: 8px;
        border-left: 5px solid #darkred;
        margin: 10px 0;
    }
    .conflict-warning {
        background-color: #fca311;
        padding: 15px;
        border-radius: 8px;
        border-left: 5px solid #ff8800;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

# --- INITIALIZE SESSION STATE ---
if 'last_refresh' not in st.session_state:
    st.session_state.last_refresh = datetime.now()
if 'auto_refresh' not in st.session_state:
    st.session_state.auto_refresh = True
if 'current_symbol' not in st.session_state:
    st.session_state.current_symbol = 'BTC-USD'
if 'view_mode' not in st.session_state:
    st.session_state.view_mode = 'Single Asset'
if 'symbol_1' not in st.session_state:
    st.session_state.symbol_1 = 'BTC-USD'
if 'symbol_2' not in st.session_state:
    st.session_state.symbol_2 = 'GC=F'
if 'backtest_log' not in st.session_state:
    st.session_state.backtest_log = []
if 'show_backtest' not in st.session_state:
    st.session_state.show_backtest = False

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
    if not FEEDPARSER_AVAILABLE:
        # Fallback news items
        return [
            {'title': '📰 Install feedparser for live news: pip install feedparser', 
             'link': '#', 'published': 'Now'},
            {'title': 'Bitcoin continues strong momentum amid institutional adoption', 
             'link': 'https://cointelegraph.com', 'published': 'Recent'},
            {'title': 'Gold prices surge on global economic uncertainty', 
             'link': 'https://www.reuters.com/markets/commodities', 'published': 'Recent'},
            {'title': 'Crypto markets show resilience in volatile trading session', 
             'link': 'https://cryptonews.com', 'published': 'Recent'},
            {'title': 'XRP gains traction with new partnerships announced', 
             'link': 'https://cointelegraph.com', 'published': 'Recent'},
        ]
    
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
    
    # If no news fetched, return fallback
    if not news_items:
        return [
            {'title': 'Unable to fetch live news at this time', 
             'link': '#', 'published': 'Now'},
        ]
    
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

# --- 5. ADVANCED PREDICTION ENGINE WITH ML TECHNIQUES ---
def predict_price_movement(df, timeframe):
    """
    Enhanced prediction using multiple methods with machine learning principles:
    1. Weighted Linear Regression (time-decay weights)
    2. Momentum-adjusted EMA prediction
    3. Mean Reversion (Bollinger Bands + RSI)
    4. Volume-Weighted Price Analysis
    5. Support/Resistance Levels
    6. Trend Strength Adjustment (ADX)
    """
    if len(df) < 50:
        return None
    
    curr_price = df['Close'].iloc[-1]
    predictions = {}
    weights = {}
    
    # --- METHOD 1: Weighted Linear Regression (Recent data more important) ---
    recent_data = df['Close'].tail(30).values
    x = np.arange(len(recent_data))
    # Apply exponential weights (recent data weighted higher)
    time_weights = np.exp(x / len(recent_data))
    
    # Weighted regression
    weighted_mean_x = np.average(x, weights=time_weights)
    weighted_mean_y = np.average(recent_data, weights=time_weights)
    
    numerator = np.sum(time_weights * (x - weighted_mean_x) * (recent_data - weighted_mean_y))
    denominator = np.sum(time_weights * (x - weighted_mean_x) ** 2)
    
    if denominator != 0:
        slope = numerator / denominator
        intercept = weighted_mean_y - slope * weighted_mean_x
        predictions['Weighted_Linear'] = slope * len(recent_data) + intercept
        
        # Calculate R-squared for confidence
        y_pred = slope * x + intercept
        ss_res = np.sum((recent_data - y_pred) ** 2)
        ss_tot = np.sum((recent_data - np.mean(recent_data)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
        weights['Weighted_Linear'] = abs(r_squared) * 2
    else:
        predictions['Weighted_Linear'] = curr_price
        weights['Weighted_Linear'] = 0.5
    
    # --- METHOD 2: Momentum-Adjusted EMA Prediction ---
    ema9 = df['EMA9'].iloc[-1]
    ema21 = df['EMA21'].iloc[-1]
    ema50 = df['EMA50'].iloc[-1]
    
    # Calculate momentum from multiple EMAs
    short_momentum = ema9 - ema21
    medium_momentum = ema21 - ema50
    
    # Momentum strength (0-1 scale)
    momentum_strength = min(abs(short_momentum / curr_price), 0.02)  # Cap at 2%
    
    # Predict based on aligned momentum
    if short_momentum > 0 and medium_momentum > 0:
        predictions['Momentum_EMA'] = curr_price + (short_momentum * 1.5)
        weights['Momentum_EMA'] = 2.0
    elif short_momentum < 0 and medium_momentum < 0:
        predictions['Momentum_EMA'] = curr_price + (short_momentum * 1.5)
        weights['Momentum_EMA'] = 2.0
    else:
        predictions['Momentum_EMA'] = curr_price + (short_momentum * 0.5)
        weights['Momentum_EMA'] = 1.0
    
    # --- METHOD 3: Mean Reversion with RSI Confirmation ---
    bb_upper = df['BB_Upper'].iloc[-1]
    bb_middle = df['BB_Middle'].iloc[-1]
    bb_lower = df['BB_Lower'].iloc[-1]
    rsi = df['RSI'].iloc[-1]
    
    # Calculate distance from bands
    if curr_price < bb_lower and rsi < 35:
        # Oversold - expect reversion up
        predictions['Mean_Reversion'] = bb_middle
        weights['Mean_Reversion'] = 2.5  # High confidence in reversion
    elif curr_price > bb_upper and rsi > 65:
        # Overbought - expect reversion down
        predictions['Mean_Reversion'] = bb_middle
        weights['Mean_Reversion'] = 2.5
    else:
        # Not at extremes
        predictions['Mean_Reversion'] = curr_price
        weights['Mean_Reversion'] = 0.8
    
    # --- METHOD 4: Volume-Weighted Price Projection ---
    recent_volume = df['Volume'].tail(10).values
    recent_prices = df['Close'].tail(10).values
    
    if recent_volume.sum() > 0:
        vwap_recent = np.sum(recent_prices * recent_volume) / recent_volume.sum()
        volume_trend = recent_volume[-3:].mean() / recent_volume[:-3].mean()
        
        # If volume increasing, price likely to continue direction
        if volume_trend > 1.2:
            direction = 1 if curr_price > vwap_recent else -1
            predictions['Volume_Weighted'] = curr_price + (direction * abs(curr_price - vwap_recent) * 0.3)
            weights['Volume_Weighted'] = 1.5
        else:
            predictions['Volume_Weighted'] = vwap_recent
            weights['Volume_Weighted'] = 1.0
    else:
        predictions['Volume_Weighted'] = curr_price
        weights['Volume_Weighted'] = 0.5
    
    # --- METHOD 5: Support/Resistance Levels ---
    # Find recent swing highs and lows
    window = 20
    recent_highs = df['High'].tail(window)
    recent_lows = df['Low'].tail(window)
    
    resistance = recent_highs.quantile(0.95)
    support = recent_lows.quantile(0.05)
    
    # Predict based on proximity to S/R
    distance_to_resistance = (resistance - curr_price) / curr_price
    distance_to_support = (curr_price - support) / curr_price
    
    if distance_to_resistance < 0.01:  # Within 1% of resistance
        predictions['SR_Level'] = curr_price - (curr_price * 0.005)  # Slight pullback
        weights['SR_Level'] = 1.5
    elif distance_to_support < 0.01:  # Within 1% of support
        predictions['SR_Level'] = curr_price + (curr_price * 0.005)  # Slight bounce
        weights['SR_Level'] = 1.5
    else:
        predictions['SR_Level'] = curr_price
        weights['SR_Level'] = 1.0
    
    # --- METHOD 6: Trend Strength (ADX) Adjustment ---
    adx = df['ADX'].iloc[-1]
    
    # Strong trend (ADX > 25) - trend continuation more likely
    if adx > 25:
        trend_direction = 1 if ema9 > ema21 else -1
        predictions['Trend_ADX'] = curr_price + (trend_direction * curr_price * 0.01)
        weights['Trend_ADX'] = (adx / 25)  # Scale weight by ADX strength
    else:
        predictions['Trend_ADX'] = curr_price
        weights['Trend_ADX'] = 0.5
    
    # --- ENSEMBLE PREDICTION (Weighted Average) ---
    total_weight = sum(weights.values())
    weighted_prediction = sum(pred * weights[key] for key, pred in predictions.items()) / total_weight
    
    # Calculate prediction metrics
    movement_pct = ((weighted_prediction - curr_price) / curr_price) * 100
    
    # ATR-based range
    atr = df['ATR'].iloc[-1]
    upper_range = curr_price + (atr * 1.5)
    lower_range = curr_price - (atr * 1.5)
    
    # Overall confidence (normalized)
    base_confidence = (total_weight / len(predictions)) * 100
    
    # Adjust confidence based on volatility
    volatility_factor = min(atr / curr_price, 0.1) * 100
    adjusted_confidence = max(min(base_confidence - volatility_factor, 95), 30)
    
    return {
        'current': curr_price,
        'predicted': weighted_prediction,
        'movement_pct': movement_pct,
        'upper_range': upper_range,
        'lower_range': lower_range,
        'confidence': adjusted_confidence,
        'direction': '📈 UP' if movement_pct > 0 else '📉 DOWN',
        'strength': 'Strong' if abs(movement_pct) > 1 else 'Moderate' if abs(movement_pct) > 0.3 else 'Weak',
        'method_predictions': predictions,
        'method_weights': weights,
        'adx': adx,
        'rsi': rsi
    }

# --- 6. DIVERGENCE & CONFLICT DETECTION ---
def detect_signal_conflicts(data_sets, analysis_results):
    """
    Detects when indicators say one thing but price action says another.
    This is THE KEY to avoiding false signals!
    """
    conflicts = []
    warnings = []
    
    # Get recent price action
    df_5m = data_sets['5m']
    df_1h = data_sets['1h']
    
    current_price = df_5m['Close'].iloc[-1]
    price_5min_ago = df_5m['Close'].iloc[-2] if len(df_5m) > 1 else current_price
    price_30min_ago = df_5m['Close'].iloc[-7] if len(df_5m) > 7 else current_price
    price_1h_ago = df_1h['Close'].iloc[-2] if len(df_1h) > 1 else current_price
    
    # Calculate REAL-TIME price momentum
    momentum_5m = ((current_price - price_5min_ago) / price_5min_ago) * 100
    momentum_30m = ((current_price - price_30min_ago) / price_30min_ago) * 100
    momentum_1h = ((current_price - price_1h_ago) / price_1h_ago) * 100
    
    # Check for divergences
    sig_5m = analysis_results.get('5m')
    sig_30m = analysis_results.get('30m')
    sig_1h = analysis_results.get('1h')
    
    # CONFLICT 1: Signal says BUY but price is actively falling
    if sig_5m and "BUY" in sig_5m['Signal']:
        if momentum_5m < -0.3:  # Price dropped >0.3% in last 5 min
            conflicts.append({
                'type': 'PRICE_DIVERGENCE',
                'severity': 'HIGH',
                'message': f"⚠️ STRONG BUY signal BUT price dropped {momentum_5m:.2f}% in last 5min",
                'action': "WAIT for price stabilization before entering",
                'technical': "Indicators are lagging - price rejecting recent high"
            })
        
        if momentum_30m < -1.0:  # Price dropped >1% in last 30 min
            conflicts.append({
                'type': 'PRICE_DIVERGENCE',
                'severity': 'CRITICAL',
                'message': f"🚨 BUY signal BUT price falling {momentum_30m:.2f}% (30min)",
                'action': "DO NOT ENTER - Possible liquidity grab or false breakout",
                'technical': "Sharp recent decline contradicts bullish indicators"
            })
    
    # CONFLICT 2: Signal says SELL but price is actively rising
    if sig_5m and "SELL" in sig_5m['Signal']:
        if momentum_5m > 0.3:  # Price rose >0.3% in last 5 min
            conflicts.append({
                'type': 'PRICE_DIVERGENCE',
                'severity': 'HIGH',
                'message': f"⚠️ SELL signal BUT price rose {momentum_5m:.2f}% in last 5min",
                'action': "WAIT for price stabilization before shorting",
                'technical': "Indicators lagging - price momentum still bullish"
            })
    
    # CONFLICT 3: Timeframe disagreement (5m vs 1h)
    if sig_5m and sig_1h:
        if "BUY" in sig_5m['Signal'] and "SELL" in sig_1h['Signal']:
            conflicts.append({
                'type': 'TIMEFRAME_CONFLICT',
                'severity': 'MEDIUM',
                'message': "⚠️ 5m says BUY but 1h says SELL",
                'action': "High risk - only scalp if you're experienced",
                'technical': "Counter-trend trade against higher timeframe"
            })
        
        if "SELL" in sig_5m['Signal'] and "BUY" in sig_1h['Signal']:
            conflicts.append({
                'type': 'TIMEFRAME_CONFLICT',
                'severity': 'MEDIUM',
                'message': "⚠️ 5m says SELL but 1h says BUY",
                'action': "Likely a pullback in uptrend - not a reversal",
                'technical': "Short-term bearish in larger bullish trend"
            })
    
    # WARNING 1: Overbought on BUY signal
    if sig_5m and "BUY" in sig_5m['Signal'] and sig_5m['RSI'] > 70:
        warnings.append({
            'type': 'OVERBOUGHT',
            'severity': 'MEDIUM',
            'message': f"⚠️ BUY signal but RSI overbought ({sig_5m['RSI']:.1f})",
            'action': "Expect pullback soon - use tight stop-loss",
            'technical': "Momentum exhaustion likely - late entry risk"
        })
    
    # WARNING 2: Oversold on SELL signal
    if sig_5m and "SELL" in sig_5m['Signal'] and sig_5m['RSI'] < 30:
        warnings.append({
            'type': 'OVERSOLD',
            'severity': 'MEDIUM',
            'message': f"⚠️ SELL signal but RSI oversold ({sig_5m['RSI']:.1f})",
            'action': "Bounce likely - avoid shorting here",
            'technical': "Oversold conditions favor reversal over continuation"
        })
    
    # WARNING 3: Low ADX (weak trend)
    if sig_5m and sig_5m.get('ADX', 0) < 20:
        if "STRONG BUY" in sig_5m['Signal'] or "STRONG SELL" in sig_5m['Signal']:
            warnings.append({
                'type': 'WEAK_TREND',
                'severity': 'MEDIUM',
                'message': f"⚠️ STRONG signal but ADX weak ({sig_5m['ADX']:.1f})",
                'action': "Choppy market - reduce position size by 50%",
                'technical': "Low ADX = no clear trend = higher failure rate"
            })
    
    # WARNING 4: Volume divergence
    df_recent = df_5m.tail(10)
    avg_volume = df_recent['Volume'].mean()
    current_volume = df_5m['Volume'].iloc[-1]
    
    if current_volume < avg_volume * 0.5:  # Volume 50% below average
        if sig_5m and ("BUY" in sig_5m['Signal'] or "SELL" in sig_5m['Signal']):
            warnings.append({
                'type': 'LOW_VOLUME',
                'severity': 'LOW',
                'message': "⚠️ Signal on low volume (50% below average)",
                'action': "Weak conviction - wait for volume confirmation",
                'technical': "Low volume moves often reverse - lack of participation"
            })
    
    # Calculate overall risk score
    risk_score = 0
    risk_score += len([c for c in conflicts if c['severity'] == 'CRITICAL']) * 30
    risk_score += len([c for c in conflicts if c['severity'] == 'HIGH']) * 20
    risk_score += len([c for c in conflicts if c['severity'] == 'MEDIUM']) * 10
    risk_score += len([w for w in warnings if w['severity'] == 'MEDIUM']) * 5
    
    # Overall assessment
    if risk_score >= 30:
        assessment = "🚫 HIGH RISK - Do not trade"
        color = "red"
    elif risk_score >= 15:
        assessment = "⚠️ MEDIUM RISK - Reduce position size"
        color = "orange"
    elif risk_score > 0:
        assessment = "💛 LOW RISK - Tradeable with caution"
        color = "yellow"
    else:
        assessment = "✅ LOW RISK - Signal aligned"
        color = "green"
    
    return {
        'conflicts': conflicts,
        'warnings': warnings,
        'risk_score': risk_score,
        'assessment': assessment,
        'color': color,
        'momentum_5m': momentum_5m,
        'momentum_30m': momentum_30m,
        'momentum_1h': momentum_1h
    }

# --- 7. BACKTESTING ENGINE ---
def run_backtest(df, timeframe_name, periods_ahead=1):
    """
    Runs backtest on historical data to validate prediction accuracy
    
    Args:
        df: DataFrame with OHLCV data and indicators
        timeframe_name: Name of timeframe (5m, 1h, etc.)
        periods_ahead: How many periods ahead to predict (1 = next candle)
    
    Returns:
        Dictionary with backtest results and metrics
    """
    if len(df) < 100:
        return None
    
    results = {
        'predictions': [],
        'actuals': [],
        'timestamps': [],
        'correct_direction': 0,
        'total_predictions': 0,
        'mae': 0,  # Mean Absolute Error
        'mape': 0,  # Mean Absolute Percentage Error
        'direction_accuracy': 0,
        'within_range': 0
    }
    
    # Run predictions on historical data
    # Start from index 50 to ensure we have enough data for indicators
    # Stop before the last 'periods_ahead' to have actual data to compare
    backtest_window = min(len(df) - periods_ahead - 50, 200)  # Test on last 200 periods max
    
    for i in range(50, 50 + backtest_window):
        # Create subset of data up to this point
        historical_df = df.iloc[:i].copy()
        
        # Make prediction
        prediction = predict_price_movement(historical_df, timeframe_name)
        
        if prediction is None:
            continue
        
        # Get actual price 'periods_ahead' later
        actual_price = df.iloc[i + periods_ahead]['Close']
        predicted_price = prediction['predicted']
        current_price_at_time = prediction['current']
        
        # Store results
        results['predictions'].append(predicted_price)
        results['actuals'].append(actual_price)
        results['timestamps'].append(df.index[i])
        
        # Check direction accuracy
        predicted_direction = 1 if predicted_price > current_price_at_time else -1
        actual_direction = 1 if actual_price > current_price_at_time else -1
        
        if predicted_direction == actual_direction:
            results['correct_direction'] += 1
        
        # Check if actual price was within predicted range
        if prediction['lower_range'] <= actual_price <= prediction['upper_range']:
            results['within_range'] += 1
        
        results['total_predictions'] += 1
    
    if results['total_predictions'] > 0:
        # Calculate metrics
        predictions_arr = np.array(results['predictions'])
        actuals_arr = np.array(results['actuals'])
        
        # Mean Absolute Error
        results['mae'] = np.mean(np.abs(predictions_arr - actuals_arr))
        
        # Mean Absolute Percentage Error
        results['mape'] = np.mean(np.abs((actuals_arr - predictions_arr) / actuals_arr)) * 100
        
        # Direction Accuracy
        results['direction_accuracy'] = (results['correct_direction'] / results['total_predictions']) * 100
        
        # Range Accuracy (how often actual price was within predicted range)
        results['range_accuracy'] = (results['within_range'] / results['total_predictions']) * 100
        
        # Recent performance (last 20 predictions)
        recent_count = min(20, results['total_predictions'])
        recent_correct = sum(1 for i in range(-recent_count, 0) 
                           if (predictions_arr[i] > predictions_arr[i-1]) == (actuals_arr[i] > actuals_arr[i-1]))
        results['recent_accuracy'] = (recent_correct / recent_count) * 100 if recent_count > 0 else 0
    
    return results

def format_backtest_summary(backtest_results):
    """Creates a formatted summary of backtest results"""
    if not backtest_results or backtest_results['total_predictions'] == 0:
        return "❌ Not enough data for backtesting"
    
    # Determine performance grade
    dir_acc = backtest_results['direction_accuracy']
    if dir_acc >= 70:
        grade = "🏆 Excellent"
        color = "green"
    elif dir_acc >= 60:
        grade = "✅ Good"
        color = "lightgreen"
    elif dir_acc >= 50:
        grade = "⚠️ Fair"
        color = "orange"
    else:
        grade = "❌ Poor"
        color = "red"
    
    summary = f"""
    **Backtest Performance: {grade}**
    
    📊 **Direction Accuracy:** {dir_acc:.1f}%
    📈 **Recent Performance (Last 20):** {backtest_results['recent_accuracy']:.1f}%
    🎯 **Range Accuracy:** {backtest_results['range_accuracy']:.1f}%
    📉 **Avg Error:** {backtest_results['mape']:.2f}%
    🔢 **Total Predictions Tested:** {backtest_results['total_predictions']}
    """
    
    return summary, color, dir_acc
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
# RENDER FUNCTIONS
# ============================================

def render_backtest_results(data_sets, symbol):
    """Renders comprehensive backtest results with visualizations"""
    
    st.subheader("🧪 Backtest & Prediction Accuracy Report")
    
    st.info("""
    **How This Works:** We test our prediction model on historical data by:
    1. Making predictions at each historical point
    2. Comparing predictions to actual prices that occurred
    3. Calculating accuracy metrics across all timeframes
    """)
    
    # Run backtests for multiple timeframes
    timeframes = ['5m', '15m', '1h', '4h']
    backtest_data = {}
    
    with st.spinner("Running backtests on historical data..."):
        for tf in timeframes:
            df = add_indicators(data_sets[tf])
            # Adjust periods_ahead based on timeframe
            periods = 1 if tf in ['5m', '15m'] else 1
            backtest_data[tf] = run_backtest(df, tf, periods_ahead=periods)
    
    # Display summary cards
    st.markdown("### 📊 Accuracy by Timeframe")
    
    cols = st.columns(4)
    overall_accuracy = []
    
    for idx, tf in enumerate(timeframes):
        result = backtest_data[tf]
        with cols[idx]:
            if result and result['total_predictions'] > 0:
                summary, color, acc = format_backtest_summary(result)
                st.markdown(f"**{tf.upper()} Timeframe**")
                st.markdown(summary)
                overall_accuracy.append(acc)
            else:
                st.warning(f"{tf}: Not enough data")
    
    st.divider()
    
    # Overall Performance Metrics
    if overall_accuracy:
        avg_accuracy = np.mean(overall_accuracy)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("🎯 Average Accuracy", f"{avg_accuracy:.1f}%")
        
        with col2:
            best_tf = timeframes[np.argmax(overall_accuracy)]
            st.metric("🏆 Best Timeframe", best_tf.upper(), f"{max(overall_accuracy):.1f}%")
        
        with col3:
            # Calculate consistency (lower std dev = more consistent)
            consistency = 100 - min(np.std(overall_accuracy), 30)
            st.metric("📈 Consistency", f"{consistency:.1f}%")
    
    st.divider()
    
    # Detailed Analysis - Choose timeframe
    st.markdown("### 🔍 Detailed Performance Analysis")
    
    selected_tf = st.selectbox("Select Timeframe for Details:", timeframes, index=2)
    
    result = backtest_data[selected_tf]
    
    if result and result['total_predictions'] > 0:
        # Performance breakdown
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 📊 Accuracy Metrics")
            st.write(f"✅ **Direction Accuracy:** {result['direction_accuracy']:.1f}%")
            st.write(f"🎯 **Range Accuracy:** {result['range_accuracy']:.1f}%")
            st.write(f"📈 **Recent Performance:** {result['recent_accuracy']:.1f}%")
            st.write(f"📉 **Avg % Error (MAPE):** {result['mape']:.2f}%")
            st.write(f"🔢 **Total Tests:** {result['total_predictions']}")
            
            # Interpretation
            st.markdown("---")
            st.markdown("**💡 What This Means:**")
            if result['direction_accuracy'] >= 60:
                st.success("✅ Model shows good predictive power for price direction")
            elif result['direction_accuracy'] >= 50:
                st.warning("⚠️ Model shows moderate accuracy - use with caution")
            else:
                st.error("❌ Model needs improvement - consider this timeframe less reliable")
        
        with col2:
            st.markdown("#### 📈 Prediction vs Actual")
            
            # Create comparison chart
            if len(result['predictions']) > 0:
                # Use last 50 predictions for visualization
                chart_size = min(50, len(result['predictions']))
                
                fig = go.Figure()
                
                # Actual prices
                fig.add_trace(go.Scatter(
                    x=list(range(chart_size)),
                    y=result['actuals'][-chart_size:],
                    name='Actual Price',
                    line=dict(color='blue', width=2)
                ))
                
                # Predicted prices
                fig.add_trace(go.Scatter(
                    x=list(range(chart_size)),
                    y=result['predictions'][-chart_size:],
                    name='Predicted Price',
                    line=dict(color='orange', width=2, dash='dash')
                ))
                
                fig.update_layout(
                    title=f"Last {chart_size} Predictions vs Actual",
                    xaxis_title="Test Number",
                    yaxis_title="Price",
                    height=400,
                    template="plotly_dark",
                    hovermode='x unified'
                )
                
                st.plotly_chart(fig, use_container_width=True)
        
        st.divider()
        
        # Recommendations based on results
        st.markdown("### 💡 AI Model Recommendations")
        
        recommendations = []
        
        if result['direction_accuracy'] >= 65:
            recommendations.append("✅ **High Confidence:** This timeframe shows strong prediction accuracy. Suitable for trading decisions.")
        
        if result['range_accuracy'] >= 70:
            recommendations.append("✅ **Reliable Ranges:** Price ranges are accurate. Use stop-loss and take-profit levels with confidence.")
        
        if result['recent_accuracy'] > result['direction_accuracy'] + 5:
            recommendations.append("📈 **Improving Performance:** Recent predictions are more accurate. Model is adapting well to current market conditions.")
        elif result['recent_accuracy'] < result['direction_accuracy'] - 5:
            recommendations.append("⚠️ **Performance Decline:** Recent accuracy is lower. Market conditions may have changed. Exercise caution.")
        
        if result['mape'] < 1.5:
            recommendations.append("🎯 **Low Error Rate:** Prediction errors are minimal. High precision model.")
        elif result['mape'] > 5:
            recommendations.append("⚠️ **High Volatility:** Large prediction errors detected. Consider using wider stop-losses.")
        
        if result['direction_accuracy'] < 55:
            recommendations.append("❌ **Unreliable Timeframe:** Consider using longer timeframes or additional confirmation before trading.")
        
        for rec in recommendations:
            st.markdown(rec)
    
    else:
        st.warning(f"Not enough data to backtest {selected_tf} timeframe")

def render_single_asset_view(data_sets, symbol, risk_reward, position_size):
    """Renders the full single asset analysis view"""
    
    current_price = data_sets['5m'].iloc[-1]['Close']
    price_change_24h = ((current_price - data_sets['1d'].iloc[-2]['Close']) / data_sets['1d'].iloc[-2]['Close']) * 100
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("💰 Current Price", f"${current_price:,.2f}", f"{price_change_24h:+.2f}%")
    with col2:
        high_24h = data_sets['5m']['High'].tail(288).max()
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
            
            # Show prediction methods breakdown
            with st.expander("🔬 See Prediction Method Details"):
                st.markdown("**How This Prediction Was Made:**")
                st.write("Our AI uses 6 different prediction methods and combines them with intelligent weighting:")
                
                method_names = {
                    'Weighted_Linear': '📈 Time-Weighted Trend Analysis',
                    'Momentum_EMA': '🚀 Multi-EMA Momentum',
                    'Mean_Reversion': '🔄 Bollinger Band Mean Reversion',
                    'Volume_Weighted': '📊 Volume-Weighted Analysis',
                    'SR_Level': '🎯 Support/Resistance Levels',
                    'Trend_ADX': '💪 ADX Trend Strength'
                }
                
                for method_key, method_name in method_names.items():
                    if method_key in pred_1h['method_predictions']:
                        pred_val = pred_1h['method_predictions'][method_key]
                        weight = pred_1h['method_weights'][method_key]
                        st.write(f"{method_name}: ${pred_val:,.2f} (Weight: {weight:.1f})")
                
                st.divider()
                st.caption(f"📊 ADX (Trend Strength): {pred_1h['adx']:.1f}")
                st.caption(f"📈 RSI (Momentum): {pred_1h['rsi']:.1f}")
    
    with pred_cols[1]:
        if pred_5m and pred_4h:
            st.markdown("**⚡ Short-Term (5m)**")
            st.write(f"{pred_5m['direction']} {pred_5m['movement_pct']:+.2f}%")
            st.write(f"Strength: {pred_5m['strength']}")
            
            st.markdown("**📅 Medium-Term (4h)**")
            st.write(f"{pred_4h['direction']} {pred_4h['movement_pct']:+.2f}%")
            st.write(f"Strength: {pred_4h['strength']}")
    
    st.divider()
    
    # Backtest section (conditional)
    if st.session_state.show_backtest:
        render_backtest_results(data_sets, symbol)
        st.divider()
    
    # Multi-timeframe + strategies
    render_timeframe_scanner(data_sets, risk_reward, position_size)
    
    st.divider()
    
    # Advanced chart
    render_advanced_chart(data_sets)
    
    st.divider()
    
    # News feed
    render_news_feed()


def render_compact_analysis(data_sets, symbol, risk_reward, position_size):
    """Renders compact analysis for multi-asset comparison (Scanner + Strategies only)"""
    
    current_price = data_sets['5m'].iloc[-1]['Close']
    price_change_24h = ((current_price - data_sets['1d'].iloc[-2]['Close']) / data_sets['1d'].iloc[-2]['Close']) * 100
    
    # Price header
    col1, col2 = st.columns(2)
    with col1:
        st.metric("💰 Price", f"${current_price:,.2f}", f"{price_change_24h:+.2f}%")
    with col2:
        volume_24h = data_sets['5m']['Volume'].tail(288).sum()
        st.metric("📊 Volume", f"{volume_24h:,.0f}")
    
    st.divider()
    
    # Only render scanner and strategies (compact view)
    render_timeframe_scanner(data_sets, risk_reward, position_size)


def render_timeframe_scanner(data_sets, risk_reward, position_size):
    """Renders multi-timeframe scanner and AI trade setups"""
    
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
            st.markdown(f"**{tf}**")
            st.caption(candle[:30])  # Truncate long pattern names
            
            if sig:
                if "STRONG BUY" in sig['Signal']:
                    st.markdown(f"<div class='signal-strong-buy'>{sig['Signal']}</div>", unsafe_allow_html=True)
                elif "STRONG SELL" in sig['Signal']:
                    st.markdown(f"<div class='signal-strong-sell'>{sig['Signal']}</div>", unsafe_allow_html=True)
                else:
                    st.markdown(f"**{sig['Signal']}**")
                
                st.progress(sig['Score'] / 100)
                st.caption(f"Score: {sig['Score']}/100")
                st.write(f"RSI: {sig['RSI']}")
                
                with st.expander("📋"):
                    for signal in sig['Signals'][:3]:
                        st.caption(signal)
    
    st.divider()
    
    # --- DIVERGENCE & CONFLICT DETECTION ---
    st.subheader("🚨 Signal Quality Check")
    
    conflict_analysis = detect_signal_conflicts(data_sets, analysis_results)
    
    # Display overall assessment
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        if conflict_analysis['color'] == 'red':
            st.error(f"**{conflict_analysis['assessment']}**")
        elif conflict_analysis['color'] == 'orange':
            st.warning(f"**{conflict_analysis['assessment']}**")
        elif conflict_analysis['color'] == 'yellow':
            st.info(f"**{conflict_analysis['assessment']}**")
        else:
            st.success(f"**{conflict_analysis['assessment']}**")
    
    with col2:
        st.metric("Risk Score", conflict_analysis['risk_score'], 
                 "Lower is better", delta_color="inverse")
    
    with col3:
        st.metric("Live Momentum", f"{conflict_analysis['momentum_5m']:+.2f}%",
                 "Last 5 minutes")
    
    # Display conflicts (CRITICAL issues)
    if conflict_analysis['conflicts']:
        st.markdown("### 🚨 Critical Conflicts Detected")
        for conflict in conflict_analysis['conflicts']:
            severity_icon = "🚨" if conflict['severity'] == 'CRITICAL' else "⚠️"
            
            with st.expander(f"{severity_icon} {conflict['message']}", expanded=True):
                st.markdown(f"**What's happening:** {conflict['technical']}")
                st.markdown(f"**Recommended action:** {conflict['action']}")
                
                if conflict['severity'] == 'CRITICAL':
                    st.error("❌ This is a high-risk situation. Consider waiting.")
    
    # Display warnings (Important but not critical)
    if conflict_analysis['warnings']:
        st.markdown("### ⚠️ Important Warnings")
        warn_cols = st.columns(2)
        for idx, warning in enumerate(conflict_analysis['warnings']):
            with warn_cols[idx % 2]:
                st.warning(f"**{warning['message']}**")
                st.caption(f"💡 {warning['action']}")
    
    # Show real-time momentum
    with st.expander("📊 Real-Time Price Momentum Analysis"):
        mom_col1, mom_col2, mom_col3 = st.columns(3)
        
        with mom_col1:
            color = "green" if conflict_analysis['momentum_5m'] > 0 else "red"
            st.markdown(f"**5-Min:** <span style='color:{color}'>{conflict_analysis['momentum_5m']:+.2f}%</span>", 
                       unsafe_allow_html=True)
        
        with mom_col2:
            color = "green" if conflict_analysis['momentum_30m'] > 0 else "red"
            st.markdown(f"**30-Min:** <span style='color:{color}'>{conflict_analysis['momentum_30m']:+.2f}%</span>", 
                       unsafe_allow_html=True)
        
        with mom_col3:
            color = "green" if conflict_analysis['momentum_1h'] > 0 else "red"
            st.markdown(f"**1-Hour:** <span style='color:{color}'>{conflict_analysis['momentum_1h']:+.2f}%</span>", 
                       unsafe_allow_html=True)
        
        st.caption("💡 Real-time momentum helps identify if indicators are lagging behind actual price movement")
    
    st.divider()
    
    # --- AI TRADING STRATEGIES ---
    st.subheader("🎯 AI Trade Setups")
    
    strat_cols = st.columns(3)
    
    # Strategy 1: SCALPING
    with strat_cols[0]:
        st.markdown("### ⚡ Scalping")
        s_data = analysis_results.get('5m')
        
        if s_data:
            if "BUY" in s_data['Signal']:
                trade = calculate_trade(s_data['Price'], s_data['ATR'], "LONG", "Scalp", risk_reward)
                st.success("📈 LONG")
                st.write(f"**Entry:** ${trade['entry']:,.2f}")
                st.write(f"🎯 **TP:** ${trade['tp']:,.2f} (+{trade['reward_pct']:.2f}%)")
                st.write(f"🛑 **SL:** ${trade['sl']:,.2f} (-{trade['risk_pct']:.2f}%)")
                
                risk_amount = position_size * (trade['risk_pct'] / 100)
                st.caption(f"💰 Risk: ${risk_amount:.2f}")
                
            elif "SELL" in s_data['Signal']:
                trade = calculate_trade(s_data['Price'], s_data['ATR'], "SHORT", "Scalp", risk_reward)
                st.error("📉 SHORT")
                st.write(f"**Entry:** ${trade['entry']:,.2f}")
                st.write(f"🎯 **TP:** ${trade['tp']:,.2f} (+{trade['reward_pct']:.2f}%)")
                st.write(f"🛑 **SL:** ${trade['sl']:,.2f} (-{trade['risk_pct']:.2f}%)")
                
                risk_amount = position_size * (trade['risk_pct'] / 100)
                st.caption(f"💰 Risk: ${risk_amount:.2f}")
            else:
                st.info("⏸️ No Setup")
                st.caption(f"Score: {s_data['Score']}/100")
    
    # Strategy 2: INTRADAY
    with strat_cols[1]:
        st.markdown("### 📅 Intraday")
        i_data = analysis_results.get('30m')
        h_data = analysis_results.get('1h')
        
        if i_data and h_data:
            if "BUY" in i_data['Signal'] and "BUY" in h_data['Signal']:
                trade = calculate_trade(i_data['Price'], i_data['ATR'], "LONG", "Intraday", risk_reward)
                st.success("📈 LONG ✓✓")
                st.write(f"**Entry:** ${trade['entry']:,.2f}")
                st.write(f"🎯 **TP:** ${trade['tp']:,.2f} (+{trade['reward_pct']:.2f}%)")
                st.write(f"🛑 **SL:** ${trade['sl']:,.2f} (-{trade['risk_pct']:.2f}%)")
                
                risk_amount = position_size * (trade['risk_pct'] / 100)
                st.caption(f"💰 Risk: ${risk_amount:.2f}")
                
            elif "SELL" in i_data['Signal'] and "SELL" in h_data['Signal']:
                trade = calculate_trade(i_data['Price'], i_data['ATR'], "SHORT", "Intraday", risk_reward)
                st.error("📉 SHORT ✓✓")
                st.write(f"**Entry:** ${trade['entry']:,.2f}")
                st.write(f"🎯 **TP:** ${trade['tp']:,.2f} (+{trade['reward_pct']:.2f}%)")
                st.write(f"🛑 **SL:** ${trade['sl']:,.2f} (-{trade['risk_pct']:.2f}%)")
                
                risk_amount = position_size * (trade['risk_pct'] / 100)
                st.caption(f"💰 Risk: ${risk_amount:.2f}")
            else:
                st.warning("⏸️ Wait")
                st.caption(f"30m: {i_data['Score']}/100")
                st.caption(f"1h: {h_data['Score']}/100")
    
    # Strategy 3: SWING
    with strat_cols[2]:
        st.markdown("### 🌊 Swing")
        w_data = analysis_results.get('4h')
        
        if w_data:
            if "BUY" in w_data['Signal']:
                trade = calculate_trade(w_data['Price'], w_data['ATR'], "LONG", "Swing", risk_reward)
                st.success("📈 LONG")
                st.write(f"**Entry:** ${trade['entry']:,.2f}")
                st.write(f"🎯 **TP:** ${trade['tp']:,.2f} (+{trade['reward_pct']:.2f}%)")
                st.write(f"🛑 **SL:** ${trade['sl']:,.2f} (-{trade['risk_pct']:.2f}%)")
                
                risk_amount = position_size * (trade['risk_pct'] / 100)
                st.caption(f"💰 Risk: ${risk_amount:.2f}")
                
            elif "SELL" in w_data['Signal']:
                trade = calculate_trade(w_data['Price'], w_data['ATR'], "SHORT", "Swing", risk_reward)
                st.error("📉 SHORT")
                st.write(f"**Entry:** ${trade['entry']:,.2f}")
                st.write(f"🎯 **TP:** ${trade['tp']:,.2f} (+{trade['reward_pct']:.2f}%)")
                st.write(f"🛑 **SL:** ${trade['sl']:,.2f} (-{trade['risk_pct']:.2f}%)")
                
                risk_amount = position_size * (trade['risk_pct'] / 100)
                st.caption(f"💰 Risk: ${risk_amount:.2f}")
            else:
                st.info("⏸️ No Setup")
                st.caption(f"Score: {w_data['Score']}/100")


def render_advanced_chart(data_sets):
    """Renders the advanced technical chart"""
    st.subheader("📈 Advanced Price Chart (1H)")
    
    chart_df = add_indicators(data_sets['1h'])
    
    from plotly.subplots import make_subplots
    
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.6, 0.2, 0.2],
        subplot_titles=('Price Action', 'RSI', 'MACD')
    )
    
    # Candlestick
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


def render_news_feed():
    """Renders the live news feed"""
    st.subheader("📰 Live Crypto & Finance News")
    
    news_items = get_crypto_news()
    
    if news_items:
        news_cols = st.columns(2)
        for idx, item in enumerate(news_items[:8]):
            with news_cols[idx % 2]:
                st.markdown(f"""
                <div class="news-item">
                    <div style="font-weight: bold; margin-bottom: 5px;">{item['title']}</div>
                    <div style="font-size: 12px; color: #888;">{item['published']}</div>
                    <a href="{item['link']}" target="_blank" style="font-size: 12px; color: #fca311;">Read more →</a>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("News feed temporarily unavailable.")

# ============================================
# MAIN APPLICATION
# ============================================

# --- SIDEBAR ---
st.sidebar.header("⚙️ Trading Settings")

# View Mode Selection
view_mode = st.sidebar.radio(
    "📊 View Mode",
    ["Single Asset", "Multi-Asset Comparison"],
    index=0 if st.session_state.view_mode == "Single Asset" else 1
)
st.session_state.view_mode = view_mode

st.sidebar.divider()

# Asset selection based on view mode
if view_mode == "Single Asset":
    symbol = st.sidebar.text_input(
        "Asset Symbol", 
        value=st.session_state.current_symbol,
        key="single_symbol_input"
    ).upper()
    # Update session state
    if symbol:
        st.session_state.current_symbol = symbol
else:
    col1, col2 = st.sidebar.columns(2)
    with col1:
        symbol_1 = st.sidebar.text_input(
            "Asset 1", 
            value=st.session_state.symbol_1,
            key="symbol_1_input"
        ).upper()
        if symbol_1:
            st.session_state.symbol_1 = symbol_1
    with col2:
        symbol_2 = st.sidebar.text_input(
            "Asset 2", 
            value=st.session_state.symbol_2,
            key="symbol_2_input"
        ).upper()
        if symbol_2:
            st.session_state.symbol_2 = symbol_2

st.sidebar.divider()

# Manual Refresh Button
if st.sidebar.button("🔄 REFRESH NOW", use_container_width=True):
    st.session_state.last_refresh = datetime.now()
    st.rerun()

# Auto-refresh toggle
st.session_state.auto_refresh = st.sidebar.checkbox("Auto-Refresh (60s)", value=st.session_state.auto_refresh)

st.sidebar.divider()

# Backtest Section
st.sidebar.subheader("🧪 Backtest & Validation")
if st.sidebar.button("📊 Run Backtest", use_container_width=True):
    st.session_state.show_backtest = not st.session_state.show_backtest
    st.rerun()

if st.session_state.show_backtest:
    st.sidebar.success("✅ Backtest results visible below")
else:
    st.sidebar.info("Click to view prediction accuracy")

st.sidebar.divider()

# Popular Assets Quick Select
st.sidebar.subheader("⚡ Quick Select")
quick_assets = {
    'BTC': 'BTC-USD',
    'Gold': 'GC=F',
    'Silver': 'SI=F',
    'DXY': 'DX-Y.NYB',
    'XRP': 'XRP-USD',
    'ETH': 'ETH-USD',
    'S&P500': '^GSPC',
    'Oil': 'CL=F'
}

cols = st.sidebar.columns(2)
for idx, (name, ticker) in enumerate(quick_assets.items()):
    with cols[idx % 2]:
        if st.button(name, use_container_width=True, key=f"quick_{ticker}"):
            if view_mode == "Single Asset":
                st.session_state.current_symbol = ticker
                st.rerun()
            else:
                # In multi-asset mode, set to symbol_1
                st.session_state.symbol_1 = ticker
                st.rerun()

st.sidebar.divider()

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

# ========================================
# CONDITIONAL RENDERING BASED ON VIEW MODE
# ========================================

if view_mode == "Single Asset":
    # ==================== SINGLE ASSET VIEW ====================
    symbol = st.session_state.current_symbol
    st.subheader(f"📈 Analysis: {symbol}")
    
    data_sets = get_data(symbol)
    
    if data_sets:
        render_single_asset_view(data_sets, symbol, risk_reward, position_size)
    else:
        st.warning("⚠️ Unable to fetch data. Please check the ticker symbol and try again.")

else:
    # ==================== MULTI-ASSET COMPARISON VIEW ====================
    st.subheader(f"📊 Multi-Asset Comparison: {st.session_state.symbol_1} vs {st.session_state.symbol_2}")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(f"### 📈 {st.session_state.symbol_1}")
        data_1 = get_data(st.session_state.symbol_1)
        if data_1:
            render_compact_analysis(data_1, st.session_state.symbol_1, risk_reward, position_size)
        else:
            st.error(f"Unable to fetch data for {st.session_state.symbol_1}")
    
    with col2:
        st.markdown(f"### 📈 {st.session_state.symbol_2}")
        data_2 = get_data(st.session_state.symbol_2)
        if data_2:
            render_compact_analysis(data_2, st.session_state.symbol_2, risk_reward, position_size)
        else:
            st.error(f"Unable to fetch data for {st.session_state.symbol_2}")

# --- AUTO-REFRESH LOGIC ---
if st.session_state.auto_refresh:
    time.sleep(60)
    st.rerun()


# --- AUTO-REFRESH LOGIC ---
if st.session_state.auto_refresh:
    time.sleep(60)
    st.rerun()
