import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import pickle
import json
import os
import plotly.graph_objects as go
import plotly.io as pio
from datetime import datetime, timedelta
import time
from scipy import stats
import requests
from collections import Counter
import re

# Try to import feedparser, use fallback if not available
try:
    import feedparser
    FEEDPARSER_AVAILABLE = True
except ImportError:
    FEEDPARSER_AVAILABLE = False
    st.warning("⚠️ feedparser not installed. News feed will be limited. Install with: pip install feedparser")

# --- PAGE CONFIG ---
st.set_page_config(page_title="Pro AI Trader Ultimate", layout="wide")

# Default toolbar visibility (can be toggled in the sidebar)
if 'show_toolbar' not in st.session_state:
    st.session_state.show_toolbar = False

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
    .key-metric {
        background-color: #000000; 
        color: #ffffff; 
        padding: 18px; 
        border-radius: 10px; 
        font-weight: 800; 
        font-size: 20px;
        border: 2px solid #ffffff;
        text-align: center;
    }
    /* Streamlit toolbar visibility controlled via settings below */
</style>
""", unsafe_allow_html=True)

# Quick visible controls to restore/hide the sidebar if it was accidentally collapsed or hidden
if 'sidebar_visible' not in st.session_state:
    st.session_state.sidebar_visible = True

col_toggle = st.columns([1,5])[0]
with col_toggle:
    if st.button('Show Sidebar'):
        st.session_state.sidebar_visible = True
    if st.button('Hide Sidebar'):
        st.session_state.sidebar_visible = False

if not st.session_state.sidebar_visible:
    st.markdown("<style>div[data-testid=\"stSidebar\"]{display:none !important;} </style>", unsafe_allow_html=True)
else:
    st.markdown("<style>div[data-testid=\"stSidebar\"]{display:block !important;} </style>", unsafe_allow_html=True)

# Toolbar visibility controlled by `show_toolbar` session state
if not st.session_state.get('show_toolbar', False):
    st.markdown("<style>[data-testid=\"stToolbar\"]{display:none !important;}</style>", unsafe_allow_html=True)
else:
    st.markdown("<style>[data-testid=\"stToolbar\"]{display:block !important;}</style>", unsafe_allow_html=True)

# If sidebar is hidden for any reason, render a fallback settings panel in main area
if not st.session_state.sidebar_visible:
    with st.expander("⚙️ Sidebar Settings (fallback)", expanded=True):
        st.write("Sidebar is hidden — these controls duplicate the sidebar settings.")
        # Appearance controls fallback
        f_compact = st.checkbox("Compact Cards", value=st.session_state.get('compact_mode', False))
        f_dark = st.checkbox("Dark Theme", value=st.session_state.get('use_dark_theme', True))
        f_font = st.selectbox("Font Size", options=['Small','Normal','Large'], index= ['Small','Normal','Large'].index(st.session_state.get('font_scale','Normal')) if st.session_state.get('font_scale') in ['Small','Normal','Large'] else 1)
        f_toolbar = st.checkbox("Show Streamlit Toolbar", value=st.session_state.get('show_toolbar', False))

        # Strict master fallback
        f_min_meta = st.slider('Min Meta Confidence', 0.5, 0.95, st.session_state.get('strict_params',{}).get('min_meta_conf',0.8), 0.05)
        f_min_rule = st.slider('Min Rule Confidence', 0.5, 0.95, st.session_state.get('strict_params',{}).get('min_rule_conf',0.8), 0.05)
        f_tp = st.slider('TP ATR Multiplier', 0.2, 3.0, st.session_state.get('strict_params',{}).get('tp_atr_mult',1.0), 0.1)
        f_sl = st.slider('SL ATR Multiplier', 0.2, 3.0, st.session_state.get('strict_params',{}).get('sl_atr_mult',1.0), 0.1)

        if st.button('Apply Settings (fallback)'):
            # mirror into session_state so main logic picks them up
            st.session_state.compact_mode = f_compact
            st.session_state.use_dark_theme = f_dark
            st.session_state.font_scale = f_font
            st.session_state.show_toolbar = f_toolbar
            st.session_state.strict_params = {'min_meta_conf': f_min_meta, 'min_rule_conf': f_min_rule, 'tp_atr_mult': f_tp, 'sl_atr_mult': f_sl}
            st.success('Applied settings')

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
if 'mobile_mode' not in st.session_state:
    st.session_state.mobile_mode = False
# Ensure desktop users see the sidebar by default
if not st.session_state.mobile_mode:
    st.session_state.sidebar_visible = True
if 'sentiment_cache' not in st.session_state:
    st.session_state.sentiment_cache = {}
if 'alert_threshold' not in st.session_state:
    st.session_state.alert_threshold = 90

# Allow restoring sidebar via URL param (?show_sidebar=1)
params = st.experimental_get_query_params()
changed = False
if params.get('show_sidebar', ['0'])[0] == '1':
    st.session_state.sidebar_visible = True
    changed = True
if params.get('show_toolbar', ['0'])[0] == '1':
    st.session_state.show_toolbar = True
    changed = True
if changed:
    st.experimental_rerun()

# --- APPEARANCE / UX SETTINGS ---
st.sidebar.subheader("Appearance & UX")
compact_mode = st.sidebar.checkbox("Compact Cards", value=False, help="Reduce padding and font sizes for a denser layout")
use_dark_theme = st.sidebar.checkbox("Dark Theme", value=True, help="Enable dark color scheme for panels")
font_scale = st.sidebar.selectbox("Font Size", options=['Small','Normal','Large'], index=1)
show_tooltips = st.sidebar.checkbox("Show Tooltips", value=True)
show_toolbar = st.sidebar.checkbox("Show Streamlit Toolbar", value=st.session_state.get('show_toolbar', False), help="Expose Streamlit toolbar for debugging or sharing")
st.session_state.show_toolbar = show_toolbar

if compact_mode:
    st.markdown("""
    <style>
    .metric-card, .prediction-box, .price-ticker {padding:8px; border-radius:8px}
    .prediction-box {padding:12px}
    .price-ticker div {font-size:12px}
    </style>
    """, unsafe_allow_html=True)

if not use_dark_theme:
    st.markdown("""
    <style>
    body, .css-1d391kg {background: #fafafa !important; color: #111 !important}
    .metric-card, .price-ticker, .prediction-box {background: #ffffff; color: #111}
    </style>
    """, unsafe_allow_html=True)

if font_scale == 'Small':
    st.markdown("""
    <style>
    body {font-size:13px}
    </style>
    """, unsafe_allow_html=True)
elif font_scale == 'Large':
    st.markdown("""
    <style>
    body {font-size:17px}
    </style>
    """, unsafe_allow_html=True)

# plotly theme
try:
    if use_dark_theme:
        pio.templates.default = 'plotly_dark'
    else:
        pio.templates.default = 'plotly'
except Exception:
    pass

# Strict Master tunables
st.sidebar.subheader('Strict Master Settings')
min_meta_conf = st.sidebar.slider('Min Meta Confidence', 0.5, 0.95, 0.8, 0.05)
min_rule_conf = st.sidebar.slider('Min Rule Confidence', 0.5, 0.95, 0.8, 0.05)
tp_atr_mult = st.sidebar.slider('TP ATR Multiplier', 0.2, 3.0, 1.0, 0.1)
sl_atr_mult = st.sidebar.slider('SL ATR Multiplier', 0.2, 3.0, 1.0, 0.1)
if 'strict_params' not in st.session_state:
    st.session_state.strict_params = {'min_meta_conf': min_meta_conf, 'min_rule_conf': min_rule_conf, 'tp_atr_mult': tp_atr_mult, 'sl_atr_mult': sl_atr_mult}

if st.sidebar.button('Apply Strict Settings'):
    st.session_state.strict_params = {'min_meta_conf': min_meta_conf, 'min_rule_conf': min_rule_conf, 'tp_atr_mult': tp_atr_mult, 'sl_atr_mult': sl_atr_mult}
    st.sidebar.success('Applied strict master settings')
if 'alert_threshold' not in st.session_state:
    st.session_state.alert_threshold = 90
if 'meta_rule_blend' not in st.session_state:
    st.session_state.meta_rule_blend = 0.6  # rule-based weight
if 'confidence_threshold' not in st.session_state:
    st.session_state.confidence_threshold = 55  # minimum score to issue BUY/SELL
if 'meta_training_samples' not in st.session_state:
    st.session_state.meta_training_samples = 80

# Sidebar controls for model tuning
with st.sidebar.expander('Model & Backtest Settings', expanded=False):
    st.session_state.meta_rule_blend = st.slider('Rule-based weight (higher = more rule-driven)', 0.0, 1.0, st.session_state.meta_rule_blend, 0.05)
    st.session_state.confidence_threshold = st.slider('Minimum confidence to issue BUY/SELL', 40, 90, st.session_state.confidence_threshold, 5)
    st.session_state.meta_training_samples = st.number_input('Meta training samples', min_value=20, max_value=500, value=st.session_state.meta_training_samples, step=10)
    if st.button('Retrain Meta-Ensemble Now'):
        st.session_state.meta_models = {}
        st.success('Meta-ensemble retrain scheduled on next render')
    if st.button('Auto-tune blend weight'):
        st.session_state.tune_blend = True
    else:
        if 'tune_blend' not in st.session_state:
            st.session_state.tune_blend = False

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
            # Prefer fast info if available, then info, then history fallback
            current = None
            try:
                current = ticker.info.get('regularMarketPrice')
            except:
                current = None

            if current is None:
                try:
                    # Try fast_info for newer yfinance versions
                    fast = getattr(ticker, 'fast_info', None)
                    if fast and isinstance(fast, dict):
                        current = fast.get('lastPrice') or fast.get('last_price')
                except:
                    current = None

            if current is None:
                try:
                    data = ticker.history(period='1d', interval='1m')
                    if not data.empty:
                        current = data['Close'].iloc[-1]
                except Exception:
                    current = None

            # Final fallback: try daily download
            if current is None:
                try:
                    hist = yf.download(symbol, period='7d', interval='1d', progress=False)
                    if not hist.empty:
                        current = hist['Close'].iloc[-1]
                except Exception:
                    current = None

            prev_close = None
            try:
                prev_close = ticker.info.get('previousClose')
            except:
                prev_close = None

            if prev_close in (None, 0):
                prev_close = current

            if current is not None:
                change = ((current - prev_close) / prev_close) * 100 if prev_close else 0
                prices[name] = {
                    'price': float(current),
                    'change': float(change),
                    'symbol': symbol
                }
        except:
            prices[name] = {'price': 0.0, 'change': 0.0, 'symbol': symbol}
    
    return prices

# --- LIVE NEWS FEED ---
def get_crypto_news():
    """Fetches latest crypto/finance news from RSS feeds"""
    if not FEEDPARSER_AVAILABLE:
        # Fallback news items
        return [
            {'title': '📰 Install feedparser for live news: pip install feedparser', 'link': '#', 'published': 'Now'},
            {'title': 'Bitcoin continues strong momentum amid institutional adoption', 'link': 'https://cointelegraph.com', 'published': 'Recent'},
            {'title': 'Gold prices surge on global economic uncertainty', 'link': 'https://www.reuters.com/markets/commodities', 'published': 'Recent'},
            {'title': 'Crypto markets show resilience in volatile trading session', 'link': 'https://cryptonews.com', 'published': 'Recent'},
            {'title': 'XRP gains traction with new partnerships announced', 'link': 'https://cointelegraph.com', 'published': 'Recent'},
        ]

    news_items = []
    feeds = [
        'https://cointelegraph.com/rss',
        'https://cryptonews.com/news/feed/',
    ]
    try:
        for feed_url in feeds:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:3]:
                news_items.append({
                    'title': entry.title,
                    'link': entry.link,
                    'published': entry.get('published', 'Recent')
                })
    except Exception:
        pass

    if not news_items:
        return [
            {'title': 'Unable to fetch live news at this time', 'link': '#', 'published': 'Now'},
        ]

    return news_items[:10]


def fetch_finnhub_events(api_key, days=1):
    """Fetches macro economic events from Finnhub for today (best-effort).
    Returns list of events with at least 'impact' and 'datetime' when available."""
    try:
        now = datetime.utcnow()
        start = (now - timedelta(days=1)).strftime('%Y-%m-%d')
        end = (now + timedelta(days=1)).strftime('%Y-%m-%d')
        url = f"https://finnhub.io/api/v1/calendar/economic?from={start}&to={end}&token={api_key}"
        r = requests.get(url, timeout=5)
        data = r.json()
        events = []
        # Finnhub may return 'economic' or similar structure; be defensive
        for key in ['economic', 'data', 'events']: 
            items = data.get(key) if isinstance(data, dict) else None
            if items:
                for ev in items:
                    events.append(ev)
                break

        # If top-level is list
        if not events and isinstance(data, list):
            events = data

        return events
    except Exception:
        return []


def check_macro_blackout(finnhub_api_key, lookahead_minutes=15):
    """Checks for high-impact macro events within ±lookahead_minutes."""
    if not finnhub_api_key:
        return False, None
    events = fetch_finnhub_events(finnhub_api_key)
    now = datetime.utcnow()
    for ev in events:
        try:
            # Try multiple common field names
            tstr = ev.get('datetime') or ev.get('time') or ev.get('start') or ev.get('date')
            impact = ev.get('impact') or ev.get('importance') or ev.get('priority')
            if not tstr:
                continue
            # parse various formats
            try:
                ev_time = datetime.fromisoformat(tstr)
            except Exception:
                try:
                    ev_time = datetime.strptime(tstr, '%Y-%m-%d %H:%M:%S')
                except:
                    continue

            delta = abs((ev_time - now).total_seconds()) / 60.0
            if delta <= lookahead_minutes and str(impact).lower() in ('high', '3', '3/3', 'major'):
                return True, ev
        except Exception:
            continue
    return False, None


def get_binance_imbalance(symbol, limit=20):
    """Fetches Binance depth for crypto symbols and returns imbalance ratio (0..1).
    Maps symbol like 'BTC-USD' or 'BTCUSD' to 'BTCUSDT' when possible."""
    try:
        # Only support common crypto tickers
        base = symbol.replace('-USD', '').replace('=F', '').replace('.', '').replace('^', '')
        pair = f"{base}USDT"
        url = f"https://api.binance.com/api/v3/depth?symbol={pair}&limit={limit}"
        r = requests.get(url, timeout=3)
        j = r.json()
        bids = j.get('bids', [])
        asks = j.get('asks', [])
        bid_vol = sum(float(b[1]) for b in bids)
        ask_vol = sum(float(a[1]) for a in asks)
        if bid_vol + ask_vol == 0:
            return None
        imbalance = bid_vol / (bid_vol + ask_vol)
        return imbalance
    except Exception:
        return None


def detect_fvg_liquidity_msb(df):
    """Detect simple Fair Value Gaps (FVG), liquidity sweeps, and MSB (market structure breaks).
    Returns flags dict with boolean indicators and brief reasons."""
    flags = {'fvg': False, 'liquidity_sweep': False, 'msb_bull': False, 'msb_bear': False, 'reasons': []}
    if df is None or len(df) < 5:
        return flags

    try:
        recent = df.tail(20).copy()
        # FVG: look for gap between two non-adjacent candles (simple heuristic)
        for i in range(2, len(recent)):
            c0 = recent.iloc[i-2]
            c1 = recent.iloc[i-1]
            c2 = recent.iloc[i]
            # Bullish FVG: low of c2 > high of c0 (gap up)
            if c2['Low'] > c0['High'] and (c1['High'] - c1['Low'])/ (c0['High'] - c0['Low'] + 1e-9) < 0.6:
                flags['fvg'] = True
                flags['reasons'].append('FVG detected (gap up)')
                break
            # Bearish FVG: high of c2 < low of c0 (gap down)
            if c2['High'] < c0['Low'] and (c1['High'] - c1['Low'])/ (c0['High'] - c0['Low'] + 1e-9) < 0.6:
                flags['fvg'] = True
                flags['reasons'].append('FVG detected (gap down)')
                break

        # Liquidity sweep: long wick below recent support then quick recovery
        lows = recent['Low']
        min_low_idx = lows.idxmin()
        min_low_pos = list(recent.index).index(min_low_idx)
        if min_low_pos >= 1 and min_low_pos < len(recent)-1:
            sweep_candle = recent.iloc[min_low_pos]
            after = recent.iloc[min_low_pos+1]
            if (sweep_candle['Low'] < recent['Low'].quantile(0.05)) and (after['Close'] > sweep_candle['Open']):
                flags['liquidity_sweep'] = True
                flags['reasons'].append('Liquidity sweep detected (wick & recovery)')

        # Simple MSB: compare last swing high/low
        highs = recent['High']
        lows = recent['Low']
        if highs.iloc[-1] > highs.iloc[-3] and lows.iloc[-1] > lows.iloc[-3]:
            flags['msb_bull'] = True
            flags['reasons'].append('MSB bullish (higher highs/lows)')
        if highs.iloc[-1] < highs.iloc[-3] and lows.iloc[-1] < lows.iloc[-3]:
            flags['msb_bear'] = True
            flags['reasons'].append('MSB bearish (lower highs/lows)')

    except Exception:
        pass

    return flags


def compute_cvd_approx(df, window=20):
    """Approximate Cumulative Volume Delta using candle direction * volume.
    Returns a normalized CVD between -1 and +1 for the window (negative = selling pressure).
    This is an approximation when tick-level trades are not available.
    """
    try:
        if df is None or len(df) < 2:
            return 0.0
        recent = df.tail(window).copy()
        # direction: +1 if close>open, -1 if close<open, 0 otherwise
        dir_signed = np.sign(recent['Close'] - recent['Open'])
        vol = recent['Volume'].fillna(0).values
        weighted = dir_signed.values * vol
        total = np.sum(np.abs(vol))
        if total == 0:
            return 0.0
        cvd = np.sum(weighted) / total
        # clamp
        return float(max(min(cvd, 1.0), -1.0))
    except Exception:
        return 0.0
    
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

# --- SENTIMENT ANALYSIS ENGINE ---
def get_sentiment_score(symbol, news_items=None):
    """
    Advanced sentiment analysis using NLP on news headlines and social signals
    Returns sentiment score from -100 (extreme bearish) to +100 (extreme bullish)
    """
    
    # Check cache (refresh every 15 minutes)
    cache_key = f"{symbol}_{datetime.now().strftime('%Y%m%d_%H%M')}"
    if cache_key in st.session_state.sentiment_cache:
        return st.session_state.sentiment_cache[cache_key]
    
    sentiment_signals = []
    
    # --- SIGNAL 1: News Headline Analysis ---
    if news_items is None:
        news_items = get_crypto_news()
    
    # Define sentiment keywords
    bullish_keywords = [
        'surge', 'rally', 'gain', 'up', 'rise', 'bullish', 'break', 'high',
        'growth', 'profit', 'strong', 'positive', 'breakthrough', 'adoption',
        'institutional', 'buy', 'accumulation', 'support', 'recovery', 'rebound'
    ]
    
    bearish_keywords = [
        'crash', 'fall', 'drop', 'down', 'decline', 'bearish', 'low', 'loss',
        'weak', 'negative', 'concern', 'risk', 'sell', 'dump', 'resistance',
        'fear', 'panic', 'liquidation', 'hack', 'ban', 'regulation'
    ]
    
    news_sentiment = 0
    news_count = 0
    
    for item in news_items[:10]:
        title = item.get('title', '').lower()
        
        # Count keyword matches
        bull_matches = sum(1 for word in bullish_keywords if word in title)
        bear_matches = sum(1 for word in bearish_keywords if word in title)
        
        if bull_matches > bear_matches:
            news_sentiment += (bull_matches - bear_matches) * 10
            news_count += 1
        elif bear_matches > bull_matches:
            news_sentiment -= (bear_matches - bull_matches) * 10
            news_count += 1
    
    if news_count > 0:
        news_sentiment = news_sentiment / news_count
        sentiment_signals.append(('news', news_sentiment, 0.3))  # 30% weight
    
    # --- SIGNAL 2: Price Action Sentiment ---
    # Analyze recent price momentum as sentiment proxy
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period='1mo', interval='1d')
        
        if not hist.empty and len(hist) >= 10:
            # 1-week performance
            week_return = ((hist['Close'].iloc[-1] - hist['Close'].iloc[-6]) / hist['Close'].iloc[-6]) * 100
            
            # 1-month performance
            month_return = ((hist['Close'].iloc[-1] - hist['Close'].iloc[0]) / hist['Close'].iloc[0]) * 100
            
            # Volume trend (increasing = bullish)
            recent_vol = hist['Volume'].tail(5).mean()
            old_vol = hist['Volume'].head(5).mean()
            vol_trend = ((recent_vol - old_vol) / old_vol) * 100 if old_vol > 0 else 0
            
            # Combine into price sentiment
            price_sentiment = (week_return * 0.4 + month_return * 0.3 + vol_trend * 0.3)
            price_sentiment = max(min(price_sentiment, 50), -50)  # Cap at ±50
            
            sentiment_signals.append(('price', price_sentiment, 0.35))  # 35% weight
    except:
        pass
    
    # --- SIGNAL 3: Volatility Sentiment ---
    # High volatility = uncertainty = bearish bias
    try:
        if not hist.empty and len(hist) >= 20:
            returns = hist['Close'].pct_change().dropna()
            volatility = returns.std() * 100
            
            # Normalize volatility to sentiment score
            # Low vol (< 2%) = bullish, High vol (> 8%) = bearish
            if volatility < 2:
                vol_sentiment = 20
            elif volatility > 8:
                vol_sentiment = -20
            else:
                vol_sentiment = 20 - ((volatility - 2) / 6) * 40
            
            sentiment_signals.append(('volatility', vol_sentiment, 0.15))  # 15% weight
    except:
        pass
    
    # --- SIGNAL 4: Market Regime Detection ---
    # Trending vs Ranging (from ADX-like calculation)
    try:
        if not hist.empty and len(hist) >= 30:
            # Calculate if market is trending
            sma_20 = hist['Close'].rolling(20).mean().iloc[-1]
            current_price = hist['Close'].iloc[-1]
            
            distance_from_ma = ((current_price - sma_20) / sma_20) * 100
            
            # Strong trend = higher sentiment confidence
            if abs(distance_from_ma) > 5:
                trend_sentiment = 15 if distance_from_ma > 0 else -15
            else:
                trend_sentiment = 0  # Ranging market = neutral
            
            sentiment_signals.append(('trend', trend_sentiment, 0.2))  # 20% weight
    except:
        pass
    
    # --- Calculate Weighted Sentiment Score ---
    if sentiment_signals:
        total_weight = sum(weight for _, _, weight in sentiment_signals)
        weighted_sentiment = sum(score * weight for _, score, weight in sentiment_signals) / total_weight
    else:
        weighted_sentiment = 0
    
    # Normalize to -100 to +100 range
    final_sentiment = max(min(weighted_sentiment, 100), -100)
    
    # Create detailed breakdown
    result = {
        'score': final_sentiment,
        'signals': sentiment_signals,
        'interpretation': get_sentiment_interpretation(final_sentiment),
        'confidence': calculate_sentiment_confidence(sentiment_signals)
    }
    
    # Cache the result
    st.session_state.sentiment_cache[cache_key] = result
    
    return result

def get_sentiment_interpretation(score):
    """Returns human-readable sentiment interpretation"""
    if score >= 60:
        return "🟢 EXTREME BULLISH"
    elif score >= 30:
        return "🟢 BULLISH"
    elif score >= 10:
        return "🟡 SLIGHTLY BULLISH"
    elif score >= -10:
        return "⚪ NEUTRAL"
    elif score >= -30:
        return "🟡 SLIGHTLY BEARISH"
    elif score >= -60:
        return "🔴 BEARISH"
    else:
        return "🔴 EXTREME BEARISH"

def calculate_sentiment_confidence(signals):
    """Calculate how confident we are in the sentiment score"""
    if not signals:
        return 0
    
    # More signals = higher confidence
    signal_count_factor = min(len(signals) / 4, 1.0) * 50
    
    # Agreement between signals = higher confidence
    scores = [score for _, score, _ in signals]
    if scores:
        # Calculate variance - low variance = high agreement
        variance = np.var(scores)
        agreement_factor = max(0, 50 - variance / 10)
    else:
        agreement_factor = 0
    
    return min(signal_count_factor + agreement_factor, 100)

# --- VOLUME PROFILE ANALYSIS ---
def calculate_volume_profile(df, num_bins=20):
    """
    Calculate volume profile - shows where most trading occurred
    Returns price levels with highest volume (Value Area)
    """
    if len(df) < 50:
        return None
    
    # Get price range
    price_min = df['Low'].min()
    price_max = df['High'].max()
    
    # Create price bins
    bins = np.linspace(price_min, price_max, num_bins)
    
    # Allocate volume to price bins
    volume_at_price = np.zeros(num_bins - 1)
    
    for idx, row in df.iterrows():
        # Find which bin this candle's volume belongs to
        # Use close price as proxy for where volume occurred
        bin_idx = np.digitize(row['Close'], bins) - 1
        if 0 <= bin_idx < len(volume_at_price):
            volume_at_price[bin_idx] += row['Volume']
    
    # Calculate Value Area (70% of volume)
    total_volume = volume_at_price.sum()
    target_volume = total_volume * 0.7
    
    # Find Point of Control (POC) - price with highest volume
    poc_idx = np.argmax(volume_at_price)
    poc_price = (bins[poc_idx] + bins[poc_idx + 1]) / 2
    
    # Find Value Area High (VAH) and Value Area Low (VAL)
    sorted_indices = np.argsort(volume_at_price)[::-1]
    cumulative_vol = 0
    value_area_indices = []
    
    for idx in sorted_indices:
        cumulative_vol += volume_at_price[idx]
        value_area_indices.append(idx)
        if cumulative_vol >= target_volume:
            break
    
    vah_price = bins[max(value_area_indices) + 1]
    val_price = bins[min(value_area_indices)]
    
    return {
        'bins': bins,
        'volume': volume_at_price,
        'poc': poc_price,
        'vah': vah_price,
        'val': val_price
    }

# --- TREND ALIGNMENT FILTER ---
def get_aligned_signal(analysis_results):
    """
    Master confluence check - only signals that pass ALL filters
    This prevents the 'lagging indicator trap'
    """
    
    sig_5m = analysis_results.get('5m')
    sig_1h = analysis_results.get('1h')
    sig_4h = analysis_results.get('4h')
    
    if not sig_5m or not sig_1h:
        return None
    
    alignment_score = 0
    max_score = 100
    filters_passed = []
    filters_failed = []
    
    # FILTER 1: Timeframe Agreement (40 points)
    if "BUY" in sig_5m['Signal'] and "BUY" in sig_1h['Signal']:
        alignment_score += 40
        filters_passed.append("✅ Timeframes aligned (5m + 1h BULLISH)")
    elif "SELL" in sig_5m['Signal'] and "SELL" in sig_1h['Signal']:
        alignment_score += 40
        filters_passed.append("✅ Timeframes aligned (5m + 1h BEARISH)")
    else:
        filters_failed.append("❌ Timeframe conflict (5m vs 1h disagree)")
    
    # FILTER 2: Momentum Strength (20 points)
    if sig_5m['RSI'] > 50 and sig_1h['RSI'] > 50:
        alignment_score += 20
        filters_passed.append("✅ Momentum aligned (Both RSI > 50)")
    elif sig_5m['RSI'] < 50 and sig_1h['RSI'] < 50:
        alignment_score += 20
        filters_passed.append("✅ Momentum aligned (Both RSI < 50)")
    else:
        filters_failed.append("❌ Momentum divergence")
    
    # FILTER 3: Trend Strength (20 points)
    if sig_5m.get('ADX', 0) > 25:
        alignment_score += 20
        filters_passed.append(f"✅ Strong trend (ADX {sig_5m['ADX']:.1f})")
    else:
        filters_failed.append(f"❌ Weak trend (ADX {sig_5m.get('ADX', 0):.1f})")
    
    # FILTER 4: Not Overbought/Oversold (20 points)
    if 30 < sig_5m['RSI'] < 70:
        alignment_score += 20
        filters_passed.append("✅ RSI in healthy range")
    else:
        filters_failed.append("⚠️ RSI extreme zone")
    
    # Determine final signal
    if alignment_score >= 80:
        signal = "🟢 STRONG CONFLUENCE"
        tradeable = True
    elif alignment_score >= 60:
        signal = "🟡 MODERATE CONFLUENCE"
        tradeable = True
    elif alignment_score >= 40:
        signal = "🟡 WEAK CONFLUENCE"
        tradeable = False
    else:
        signal = "🔴 NO CONFLUENCE"
        tradeable = False
    
    return {
        'score': alignment_score,
        'signal': signal,
        'tradeable': tradeable,
        'passed': filters_passed,
        'failed': filters_failed
    }

# --- PROFESSIONAL-GRADE ANALYSIS LAYERS ---

# --- 1. SENTIMENT ANALYSIS ENGINE ---
def get_sentiment_score(symbol, news_items=None):
    """
    Analyzes market sentiment from news and social data
    Returns: sentiment score (-100 to +100) and classification
    """
    sentiment_score = 0
    sentiment_signals = []
    
    # If we have news items, analyze them
    if news_items:
        # Simple keyword-based sentiment (in production, use NLP models)
        bullish_keywords = ['surge', 'rally', 'bullish', 'gain', 'rise', 'up', 'breakthrough', 
                           'adoption', 'partnership', 'growth', 'positive', 'strong']
        bearish_keywords = ['crash', 'drop', 'fall', 'bearish', 'decline', 'down', 'negative',
                           'warning', 'concern', 'risk', 'sell', 'weak']
        
        for item in news_items[:5]:  # Check recent 5 news items
            title = item['title'].lower()
            
            bullish_count = sum(1 for word in bullish_keywords if word in title)
            bearish_count = sum(1 for word in bearish_keywords if word in title)
            
            if bullish_count > bearish_count:
                sentiment_score += 15
                sentiment_signals.append(f"📰 Bullish news: {item['title'][:50]}...")
            elif bearish_count > bullish_count:
                sentiment_score -= 15
                sentiment_signals.append(f"📰 Bearish news: {item['title'][:50]}...")
    
    # Market context analysis based on asset type
    if 'BTC' in symbol or 'ETH' in symbol:
        # Crypto-specific sentiment factors
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            # Volume trend (high volume = high interest)
            hist = ticker.history(period='5d')
            if len(hist) > 1:
                recent_volume = hist['Volume'].tail(2).mean()
                avg_volume = hist['Volume'].mean()
                
                if recent_volume > avg_volume * 1.5:
                    sentiment_score += 10
                    sentiment_signals.append("📊 Volume surge (+10)")
                elif recent_volume < avg_volume * 0.5:
                    sentiment_score -= 10
                    sentiment_signals.append("📊 Volume declining (-10)")
        except:
            pass
    
    # Normalize to -100 to +100
    sentiment_score = max(min(sentiment_score, 100), -100)
    
    # Classify sentiment
    if sentiment_score >= 60:
        classification = "🟢 Strongly Bullish"
    elif sentiment_score >= 30:
        classification = "🟢 Bullish"
    elif sentiment_score >= -30:
        classification = "🟡 Neutral"
    elif sentiment_score >= -60:
        classification = "🔴 Bearish"
    else:
        classification = "🔴 Strongly Bearish"
    
    return {
        'score': sentiment_score,
        'classification': classification,
        'signals': sentiment_signals
    }

# --- 2. VOLUME PROFILE ANALYSIS ---
def calculate_volume_profile(df, num_bins=20):
    """
    Calculates Volume Profile to identify high-volume price levels
    These are key support/resistance zones where institutions accumulate
    """
    if len(df) < 50:
        return None
    
    # Get price range
    price_min = df['Low'].min()
    price_max = df['High'].max()
    
    # Create price bins
    bins = np.linspace(price_min, price_max, num_bins)
    
    # Calculate volume at each price level
    volume_at_price = np.zeros(num_bins - 1)
    
    for i in range(len(df)):
        candle_low = df['Low'].iloc[i]
        candle_high = df['High'].iloc[i]
        candle_volume = df['Volume'].iloc[i]
        
        # Distribute volume across bins that this candle touched
        for j in range(num_bins - 1):
            if bins[j] <= candle_high and bins[j + 1] >= candle_low:
                volume_at_price[j] += candle_volume / num_bins
    
    # Find value area (70% of volume)
    total_volume = volume_at_price.sum()
    sorted_indices = np.argsort(volume_at_price)[::-1]
    
    cumulative_volume = 0
    value_area_indices = []
    
    for idx in sorted_indices:
        cumulative_volume += volume_at_price[idx]
        value_area_indices.append(idx)
        if cumulative_volume >= total_volume * 0.7:
            break
    
    # Calculate POC (Point of Control - highest volume)
    poc_index = np.argmax(volume_at_price)
    poc_price = (bins[poc_index] + bins[poc_index + 1]) / 2
    
    # Value Area High and Low
    value_area_indices = sorted(value_area_indices)
    va_low = bins[value_area_indices[0]]
    va_high = bins[value_area_indices[-1] + 1]
    
    return {
        'bins': bins,
        'volume': volume_at_price,
        'poc': poc_price,
        'va_high': va_high,
        'va_low': va_low
    }

# --- 3. ORDER FLOW DETECTION ---
def detect_order_flow(df):
    """
    Analyzes order flow to detect institutional buying/selling
    Looks for aggressive vs passive orders
    """
    if len(df) < 10:
        return None
    
    signals = []
    strength = 0
    
    recent = df.tail(10)
    
    # Detect buying pressure vs selling pressure
    for i in range(1, len(recent)):
        prev = recent.iloc[i-1]
        curr = recent.iloc[i]
        
        # Strong buying: close near high, volume increasing
        if (curr['Close'] - curr['Low']) / (curr['High'] - curr['Low'] + 0.0001) > 0.7:
            if curr['Volume'] > prev['Volume'] * 1.2:
                strength += 2
                signals.append("🟢 Aggressive buying detected")
        
        # Strong selling: close near low, volume increasing  
        elif (curr['High'] - curr['Close']) / (curr['High'] - curr['Low'] + 0.0001) > 0.7:
            if curr['Volume'] > prev['Volume'] * 1.2:
                strength -= 2
                signals.append("🔴 Aggressive selling detected")
    
    # Absorption detection (large volume, small price movement = institutional accumulation)
    for i in range(len(recent)):
        candle = recent.iloc[i]
        body_size = abs(candle['Close'] - candle['Open'])
        candle_range = candle['High'] - candle['Low']
        
        if body_size < candle_range * 0.3:  # Small body
            avg_volume = recent['Volume'].mean()
            if candle['Volume'] > avg_volume * 2:  # High volume
                signals.append("📊 Absorption detected (institutions accumulating)")
                strength += 1
    
    classification = "Bullish" if strength > 2 else "Bearish" if strength < -2 else "Neutral"
    
    return {
        'strength': strength,
        'classification': classification,
        'signals': signals[-3:]  # Last 3 signals
    }

# --- 4. REGIME DETECTION ---
def detect_market_regime(df):
    """
    Detects if market is Trending, Ranging, or Volatile
    Different strategies work in different regimes
    """
    if len(df) < 50:
        return None
    
    # Calculate regime indicators
    adx = df['ADX'].iloc[-1]
    atr = df['ATR'].iloc[-1]
    current_price = df['Close'].iloc[-1]
    
    # Bollinger Band width (volatility measure)
    bb_width = (df['BB_Upper'].iloc[-1] - df['BB_Lower'].iloc[-1]) / df['BB_Middle'].iloc[-1]
    
    # Price position relative to moving averages
    above_ema200 = current_price > df['EMA200'].iloc[-1]
    ema_alignment = df['EMA9'].iloc[-1] > df['EMA21'].iloc[-1] > df['EMA50'].iloc[-1]
    
    # Determine regime
    if adx > 25 and ema_alignment:
        regime = "📈 Strong Trend"
        strategy = "Trend Following"
        confidence = "High"
    elif adx > 25:
        regime = "📉 Strong Trend (Bearish)"
        strategy = "Trend Following (Short)"
        confidence = "High"
    elif adx < 20 and bb_width < 0.04:
        regime = "📊 Tight Range"
        strategy = "Mean Reversion"
        confidence = "Medium"
    elif bb_width > 0.08:
        regime = "💥 High Volatility"
        strategy = "Breakout Trading"
        confidence = "Low"
    else:
        regime = "🌊 Choppy/Ranging"
        strategy = "Wait or Range Trade"
        confidence = "Low"
    
    return {
        'regime': regime,
        'strategy': strategy,
        'confidence': confidence,
        'adx': adx,
        'bb_width': bb_width * 100,
        'trending': adx > 25
    }

# --- 5. CONFLUENCE SCORING (MASTER FORMULA) ---
def calculate_confluence_score(df, sentiment_data, order_flow, regime):
    """
    The 'Master Formula' - combines all analysis layers
    Returns a weighted score showing overall signal quality
    """
    scores = {}
    weights = {}
    
    current_price = df['Close'].iloc[-1]
    
    # 1. MACRO FILTER (Sentiment) - 20% weight
    if sentiment_data:
        sentiment_contribution = sentiment_data['score'] / 100  # Normalize to 0-1
        scores['sentiment'] = sentiment_contribution
        weights['sentiment'] = 0.20
    else:
        scores['sentiment'] = 0
        weights['sentiment'] = 0.20
    
    # 2. REGIME FILTER - 25% weight
    if regime:
        if regime['confidence'] == 'High':
            regime_score = 1.0
        elif regime['confidence'] == 'Medium':
            regime_score = 0.6
        else:
            regime_score = 0.3
        
        scores['regime'] = regime_score
        weights['regime'] = 0.25
    else:
        scores['regime'] = 0.5
        weights['regime'] = 0.25
    
    # 3. TECHNICAL ALIGNMENT - 30% weight
    ema9 = df['EMA9'].iloc[-1]
    ema21 = df['EMA21'].iloc[-1]
    ema50 = df['EMA50'].iloc[-1]
    ema200 = df['EMA200'].iloc[-1]
    
    technical_score = 0
    if current_price > ema200:
        technical_score += 0.4
    if ema9 > ema21 > ema50:
        technical_score += 0.6
    
    scores['technical'] = technical_score
    weights['technical'] = 0.30
    
    # 4. ORDER FLOW - 15% weight
    if order_flow:
        flow_score = (order_flow['strength'] + 5) / 10  # Normalize -5 to +5 → 0 to 1
        flow_score = max(0, min(1, flow_score))
        scores['order_flow'] = flow_score
        weights['order_flow'] = 0.15
    else:
        scores['order_flow'] = 0.5
        weights['order_flow'] = 0.15
    
    # 5. VOLUME CONFIRMATION - 10% weight
    recent_volume = df['Volume'].tail(5).mean()
    avg_volume = df['Volume'].tail(50).mean()
    volume_ratio = recent_volume / avg_volume
    
    volume_score = min(volume_ratio / 2, 1.0)  # Cap at 1.0
    scores['volume'] = volume_score
    weights['volume'] = 0.10
    
    # --- ORDER FLOW / CVD (protective override) ---
    try:
        recent = df.tail(10)
        signed_volumes = [(row['Volume'] if row['Close'] > row['Open'] else -row['Volume']) for _, row in recent.iterrows()]
        cvd = sum(signed_volumes)
        avg_vol = df['Volume'].tail(50).mean()
    except Exception:
        cvd = 0
        avg_vol = avg_volume

    sell_spike = False
    try:
        if cvd < - (avg_vol * 2.5):
            sell_spike = True
    except:
        sell_spike = False

    # Calculate weighted confluence
    total_score = sum(scores[key] * weights[key] for key in scores.keys())

    # Apply CVD override: if aggressive selling detected, reduce confluence sharply
    if sell_spike:
        total_score = total_score * 0.4

    total_score = total_score * 100  # Convert to 0-100

    return {
        'total_score': total_score,
        'component_scores': scores,
        'weights': weights,
        'cvd': cvd,
        'sell_spike': sell_spike,
        'breakdown': {
            'Sentiment': f"{scores.get('sentiment', 0) * 100:.0f}/100",
            'Regime': f"{scores.get('regime', 0) * 100:.0f}/100",
            'Technical': f"{scores.get('technical', 0) * 100:.0f}/100",
            'Order Flow': f"{scores.get('order_flow', 0) * 100:.0f}/100",
            'Volume': f"{scores.get('volume', 0) * 100:.0f}/100"
        }
    }

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


def get_short_term_velocity(df, minutes=5):
    """Estimate short-term price velocity (dPrice/dt) in price units per minute.
    Uses available candle resolution; converts minutes to nearest number of candles.
    """
    if len(df) < 3:
        return 0.0

    # Infer candle minutes from index frequency if possible
    try:
        freq = pd.infer_freq(df.index)
    except Exception:
        freq = None

    # Default candle_minutes: try 5 if unknown
    candle_minutes = 5
    if freq and 'T' in freq:
        try:
            candle_minutes = int(re.sub('[^0-9]', '', freq))
        except:
            candle_minutes = 5

    # Number of candles to cover requested minutes (at least 2)
    n_candles = max(2, int(max(2, minutes / max(1, candle_minutes))))

    recent = df['Close'].tail(n_candles).values
    if len(recent) < 2:
        return 0.0

    x = np.arange(len(recent))
    # Linear regression slope (price change per candle)
    A = np.vstack([x, np.ones(len(x))]).T
    m, c = np.linalg.lstsq(A, recent, rcond=None)[0]
    # Convert slope per candle -> per minute
    slope_per_min = m / candle_minutes
    return float(slope_per_min)

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
    # Short-term velocity (dPrice/dt) - override EMA biases if negative
    velocity = get_short_term_velocity(df, minutes=5)
    
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

    # If short-term velocity is negative, reduce bullish bias (override long-term EMA signals)
    if velocity < 0 and normalized_score > 50:
        normalized_score = normalized_score * 0.6
        signals.append("⚠️ Short-term negative velocity detected - overriding EMA bias")

    # --- DYNAMIC LOW-VOLUME BLACKOUT ---
    try:
        avg20 = float(df['Volume'].tail(20).mean())
        if avg20 > 0 and curr['Volume'] < 0.5 * avg20:
            # Reduce confidence by ~45% and mark as caution
            normalized_score = normalized_score * 0.55
            signals.append("⚠️ Low volume detected (<50% of 20-period avg) - downgrading signal")
    except Exception:
        pass

    # --- CANDLE REVERSAL PENALTIES ---
    try:
        pattern = identify_candle(df)
        if pattern and ('Bearish' in pattern or 'Evening Star' in pattern or 'Shooting Star' in pattern or 'Bearish Engulfing' in pattern):
            # If currently bullish-biased, apply a severe negative multiplier to UP confidence
            if normalized_score > 55:
                normalized_score = normalized_score * 0.35
                signals.append(f"⚠️ Strong bearish candle pattern detected ({pattern}) - applying severe UP penalty")
        elif pattern and ('Bullish' in pattern or 'Morning Star' in pattern or 'Hammer' in pattern or 'Bullish Engulfing' in pattern):
            # If currently bearish-biased, slightly reduce sell confidence
            if normalized_score < 45:
                normalized_score = normalized_score * 0.8
                signals.append(f"✅ Bullish candle pattern detected ({pattern}) - reducing SELL bias")
    except Exception:
        pass

    # --- HARD MULTI-TIMEFRAME TREND FILTER (1H / 4H) ---
    try:
        symbol = st.session_state.get('current_symbol', None)
        if symbol and timeframe_name in ('5m', '15m'):
            # Fetch higher timeframe EMAs
            try:
                t = yf.Ticker(symbol)
                df_1h = t.history(period='7d', interval='60m')
                df_4h = t.history(period='30d', interval='240m')
                for _df in (df_1h, df_4h):
                    if _df is None or _df.empty:
                        raise Exception('empty')
                # Compute EMAs safely
                df_1h['EMA50'] = df_1h['Close'].ewm(span=50, adjust=False).mean()
                df_1h['EMA200'] = df_1h['Close'].ewm(span=200, adjust=False).mean()
                df_4h['EMA50'] = df_4h['Close'].ewm(span=50, adjust=False).mean()
                df_4h['EMA200'] = df_4h['Close'].ewm(span=200, adjust=False).mean()

                # Determine higher-timeframe trend flags
                ht1_bull = (df_1h['EMA50'].iloc[-1] > df_1h['EMA200'].iloc[-1]) and (df_1h['Close'].iloc[-1] > df_1h['EMA50'].iloc[-1])
                ht4_bull = (df_4h['EMA50'].iloc[-1] > df_4h['EMA200'].iloc[-1]) and (df_4h['Close'].iloc[-1] > df_4h['EMA50'].iloc[-1])
                ht1_bear = (df_1h['EMA50'].iloc[-1] < df_1h['EMA200'].iloc[-1]) and (df_1h['Close'].iloc[-1] < df_1h['EMA50'].iloc[-1])
                ht4_bear = (df_4h['EMA50'].iloc[-1] < df_4h['EMA200'].iloc[-1]) and (df_4h['Close'].iloc[-1] < df_4h['EMA50'].iloc[-1])

                # If short TF suggests BUY but higher TF not bullish, penalize strongly
                if normalized_score > 55 and not (ht1_bull and ht4_bull):
                    normalized_score = normalized_score * 0.6
                    signals.append('⚠️ Higher-timeframe trend not confirming BUY (hard filter applied)')
                # If short TF suggests SELL but higher TF not bearish, penalize strongly
                if normalized_score < 45 and not (ht1_bear and ht4_bear):
                    normalized_score = normalized_score * 0.6
                    signals.append('⚠️ Higher-timeframe trend not confirming SELL (hard filter applied)')
            except Exception:
                # If any fetch/compute fails, skip hard filter
                pass
    except Exception:
        pass

    # --- CUMULATIVE VOLUME DELTA (CVD) & ORDERBOOK IMBALANCE OVERRIDES ---
    try:
        # Approximate CVD from recent candles
        cvd = compute_cvd_approx(df, window=20)
        # Strong selling spike -> force Neutral/Down
        if cvd < -0.4:
            normalized_score = min(normalized_score, 30)
            signals.append(f"⚠️ Aggressive selling detected (CVD={cvd:.2f}) - forcing Neutral/Down")
        elif cvd > 0.4:
            # Aggressive buying spike -> boost bullish confidence
            normalized_score = max(normalized_score, 65)
            signals.append(f"✅ Aggressive buying detected (CVD={cvd:.2f}) - boosting BUY")

        # Use Binance orderbook imbalance for crypto-like symbols
        if symbol and isinstance(symbol, str) and ('BTC' in symbol or 'ETH' in symbol or 'XRP' in symbol):
            imb = get_binance_imbalance(symbol)
            if imb is not None:
                if imb < 0.35:
                    normalized_score = min(normalized_score, 30)
                    signals.append(f"⚠️ Orderbook imbalance bearish (imbalance={imb:.2f}) - overriding to Neutral/Down")
                elif imb > 0.65:
                    normalized_score = max(normalized_score, 65)
                    signals.append(f"✅ Orderbook imbalance bullish (imbalance={imb:.2f}) - boosting BUY")
    except Exception:
        pass
    
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
    
    # Ensure TP/SL respect direction (use ATR for adaptive stops)
    tp = None
    sl = None
    try:
        if movement_pct < 0:
            # Bearish: TP below current price, SL above
            tp = min(weighted_prediction, lower_range)
            sl = max(upper_range, curr_price + (atr * 1.0))
        else:
            # Bullish: TP above current price, SL below
            tp = max(weighted_prediction, upper_range)
            sl = min(lower_range, curr_price - (atr * 1.0))
    except Exception:
        tp = weighted_prediction
        sl = curr_price - (atr if movement_pct > 0 else -atr)

    direction_label = '📈 UP' if movement_pct > 0 else '📉 DOWN'
    strength = 'Strong' if abs(movement_pct) > 1 else 'Moderate' if abs(movement_pct) > 0.3 else 'Weak'

    return {
        'current': curr_price,
        'predicted': weighted_prediction,
        'movement_pct': movement_pct,
        'upper_range': upper_range,
        'lower_range': lower_range,
        'tp': tp,
        'sl': sl,
        'confidence': adjusted_confidence,
        'direction': direction_label,
        'strength': strength,
        'method_predictions': predictions,
        'method_weights': weights,
        'adx': adx,
        'rsi': rsi
    }


# --- META-ENSEMBLE TRAINER & PREDICTOR (STACKING) ---
def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def train_meta_ensemble(df_full, timeframe, samples=120, horizon=1, alpha=0.1):
    """Train a simple ridge stacking model using method predictions as features.
    Returns dict with weights, feature_names and intercept.
    """
    X_list = []
    y_list = []
    method_names = None

    # need at least samples + horizon + safety
    n = len(df_full)
    start = max(50, samples)  # skip early unstable region
    # We'll sample up to last-1-horizon
    for i in range(start, n - horizon):
        try:
            df_up = df_full.iloc[:i+1].copy()
            df_up = add_indicators(df_up)
            pred = predict_price_movement(df_up, timeframe)
            if pred is None:
                continue
            methods = pred.get('method_predictions', {})
            if not methods:
                continue
            curr_price = pred['current']
            # build feature vector: pct movement predicted by each method
            feats = []
            names = []
            for k, v in methods.items():
                names.append(k)
                feats.append(((v - curr_price) / curr_price))

            # Additional features
            feats.append(compute_cvd_approx(df_up, window=20))
            feats.append(df_up['RSI'].iloc[-1])
            feats.append(df_up['ADX'].iloc[-1])
            feats.append(df_up['Volume_Ratio'].iloc[-1] if 'Volume_Ratio' in df_up.columns else 1.0)

            # target: next candle up (1) or down (0)
            future_close = df_full['Close'].iloc[i + horizon]
            target = 1 if future_close > curr_price else 0

            if method_names is None:
                method_names = names
            # ensure method order matches
            if names != method_names:
                # align by method_names if possible
                aligned = []
                for mn in method_names:
                    aligned.append(feats[names.index(mn)]) if mn in names else aligned.append(0.0)
                feats = aligned + feats[len(names):]

            X_list.append(feats)
            y_list.append(target)
        except Exception:
            continue

        if len(y_list) >= samples:
            break

    if not X_list or len(y_list) < 10:
        return None

    X = np.array(X_list)
    y = np.array(y_list).reshape(-1, 1)

    # add intercept column
    X_design = np.hstack([np.ones((X.shape[0], 1)), X])

    # Ridge closed-form solution
    I = np.eye(X_design.shape[1])
    I[0, 0] = 0  # do not regularize intercept
    try:
        w = np.linalg.inv(X_design.T @ X_design + alpha * I) @ (X_design.T @ y)
        w = w.flatten()
    except np.linalg.LinAlgError:
        w = np.linalg.lstsq(X_design, y, rcond=None)[0].flatten()

    return {
        'weights': w,  # intercept first
        'method_names': method_names,
        'n_features': X_design.shape[1]
    }


def meta_predict_from_model(pred_output, model):
    """Given a predict_price_movement output and a trained model, return probability of UP."""
    try:
        methods = pred_output.get('method_predictions', {})
        curr = pred_output['current']
        feats = []
        for mn in model['method_names']:
            v = methods.get(mn, curr)
            feats.append(((v - curr) / curr))
        feats.append(compute_cvd_approx(pred_output.get('df', pd.DataFrame()), window=20) if isinstance(pred_output.get('df'), pd.DataFrame) else 0.0)
        feats.append(pred_output.get('rsi', 50))
        feats.append(pred_output.get('adx', 20))
        feats.append(pred_output.get('volume_ratio', 1.0))

        Xv = np.array([1.0] + feats)
        w = model['weights']
        score = float(Xv @ w)
        prob = sigmoid(score)
        return prob
    except Exception:
        return 0.5

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

# --- 7. MASTER SIGNAL CALCULATOR (ALL-IN-ONE) ---
def calculate_master_signal(data_sets, analysis_results, conflict_analysis):
    """
    The ULTIMATE signal calculator that considers EVERYTHING:
    - All technical indicators (RSI, MACD, ADX, Stoch, BB, EMAs)
    - Volume analysis
    - Candle patterns
    - Real-time momentum
    - Timeframe alignment
    - Conflict detection
    - Risk score
    - Sentiment scoring
    
    Returns master signals for Scalping, Intraday, and Swing with confidence scores
    """
    
    master_signals = {
        'scalping': {'signal': 'NEUTRAL', 'confidence': 0, 'score': 0, 'reasons': []},
        'intraday': {'signal': 'NEUTRAL', 'confidence': 0, 'score': 0, 'reasons': []},
        'swing': {'signal': 'NEUTRAL', 'confidence': 0, 'score': 0, 'reasons': []}
    }
    
    # Get all necessary data
    df_5m = add_indicators(data_sets['5m'])
    df_15m = add_indicators(data_sets['15m'])
    df_30m = add_indicators(data_sets['30m'])
    df_1h = add_indicators(data_sets['1h'])
    df_4h = add_indicators(data_sets['4h'])
    
    # Current values
    curr_5m = df_5m.iloc[-1]
    curr_1h = df_1h.iloc[-1]
    curr_4h = df_4h.iloc[-1]
    
    # ============================================
    # SCALPING SIGNAL (5m + 15m focus)
    # ============================================
    
    scalp_score = 0
    scalp_max_score = 0
    scalp_reasons = []
    
    # 1. Price Momentum Alignment (Weight: 25 points)
    scalp_max_score += 25
    if conflict_analysis['momentum_5m'] > 0.3:
        scalp_score += 25
        scalp_reasons.append("✅ Strong upward momentum (+0.3%+)")
    elif conflict_analysis['momentum_5m'] > 0.1:
        scalp_score += 15
        scalp_reasons.append("✅ Positive momentum")
    elif conflict_analysis['momentum_5m'] < -0.3:
        scalp_score -= 25
        scalp_reasons.append("❌ Strong downward momentum")
    elif conflict_analysis['momentum_5m'] < -0.1:
        scalp_score -= 15
        scalp_reasons.append("⚠️ Negative momentum")
    
    # 2. Technical Indicators Alignment (Weight: 20 points)
    scalp_max_score += 20
    sig_5m = analysis_results.get('5m')
    if sig_5m:
        if sig_5m['Score'] >= 75:
            scalp_score += 20
            scalp_reasons.append(f"✅ Very strong indicators (Score: {sig_5m['Score']})")
        elif sig_5m['Score'] >= 60:
            scalp_score += 12
            scalp_reasons.append(f"✅ Good indicators (Score: {sig_5m['Score']})")
        elif sig_5m['Score'] <= 40:
            scalp_score -= 20
            scalp_reasons.append(f"❌ Weak indicators (Score: {sig_5m['Score']})")
        elif sig_5m['Score'] <= 25:
            scalp_score -= 12
            scalp_reasons.append(f"⚠️ Poor indicators (Score: {sig_5m['Score']})")
    
    # 3. RSI Confirmation (Weight: 15 points)
    scalp_max_score += 15
    rsi_5m = curr_5m['RSI']
    if 40 <= rsi_5m <= 60:
        scalp_score += 15
        scalp_reasons.append(f"✅ RSI neutral zone ({rsi_5m:.1f}) - room to move")
    elif 60 < rsi_5m <= 70:
        scalp_score += 8
        scalp_reasons.append(f"✅ RSI bullish ({rsi_5m:.1f})")
    elif 30 <= rsi_5m < 40:
        scalp_score += 8
        scalp_reasons.append(f"⚠️ RSI bearish ({rsi_5m:.1f})")
    elif rsi_5m > 75:
        scalp_score -= 10
        scalp_reasons.append(f"❌ RSI severely overbought ({rsi_5m:.1f})")
    elif rsi_5m < 25:
        scalp_score -= 10
        scalp_reasons.append(f"❌ RSI severely oversold ({rsi_5m:.1f})")
    
    # 4. Volume Analysis (Weight: 15 points)
    scalp_max_score += 15
    vol_ratio = curr_5m['Volume_Ratio']
    if vol_ratio > 1.5:
        scalp_score += 15
        scalp_reasons.append(f"✅ High volume ({vol_ratio:.1f}x avg) - strong conviction")
    elif vol_ratio > 1.0:
        scalp_score += 8
        scalp_reasons.append(f"✅ Above average volume ({vol_ratio:.1f}x)")
    elif vol_ratio < 0.5:
        scalp_score -= 10
        scalp_reasons.append(f"❌ Low volume ({vol_ratio:.1f}x) - weak move")
    
    # 5. Conflict Detection (Weight: 15 points)
    scalp_max_score += 15
    risk_score = conflict_analysis['risk_score']
    if risk_score == 0:
        scalp_score += 15
        scalp_reasons.append("✅ No conflicts detected - clean setup")
    elif risk_score <= 10:
        scalp_score += 8
        scalp_reasons.append("✅ Minor warnings only")
    elif risk_score <= 20:
        scalp_score -= 5
        scalp_reasons.append("⚠️ Some conflicts present")
    else:
        scalp_score -= 15
        scalp_reasons.append(f"❌ High risk conflicts (Score: {risk_score})")
    
    # 6. Candle Pattern (Weight: 10 points)
    scalp_max_score += 10
    candle_5m = identify_candle(df_5m)
    if "Bullish" in candle_5m or "Hammer" in candle_5m or "Morning Star" in candle_5m:
        scalp_score += 10
        scalp_reasons.append(f"✅ Bullish pattern: {candle_5m}")
    elif "Bearish" in candle_5m or "Shooting Star" in candle_5m or "Evening Star" in candle_5m:
        # Severe penalty for bearish reversal patterns on active timeframe
        penalty = scalp_max_score * 0.5
        scalp_score -= 10
        scalp_score -= penalty
        scalp_reasons.append(f"❌ Bearish reversal detected - heavy penalty: {candle_5m}")
    
    # Calculate scalping signal
    scalp_normalized = ((scalp_score + scalp_max_score) / (2 * scalp_max_score)) * 100

    # Dynamic Low-Volume Safeguard: reduce confidence when volume <50% of 20-period average
    try:
        if curr_5m['Volume'] < (curr_5m['Volume_MA'] * 0.5):
            scalp_normalized = scalp_normalized * 0.6  # reduce by ~40%
            scalp_reasons.append("⚠️ Low volume safeguard applied (confidence reduced)")
    except Exception:
        pass
    
    if scalp_normalized >= 75 and risk_score < 20:
        master_signals['scalping']['signal'] = "STRONG BUY"
        master_signals['scalping']['confidence'] = "Very High"
    elif scalp_normalized >= 60 and risk_score < 25:
        master_signals['scalping']['signal'] = "BUY"
        master_signals['scalping']['confidence'] = "High"
    elif scalp_normalized <= 25 and risk_score < 20:
        master_signals['scalping']['signal'] = "STRONG SELL"
        master_signals['scalping']['confidence'] = "Very High"
    elif scalp_normalized <= 40 and risk_score < 25:
        master_signals['scalping']['signal'] = "SELL"
        master_signals['scalping']['confidence'] = "High"
    else:
        master_signals['scalping']['signal'] = "NEUTRAL"
        master_signals['scalping']['confidence'] = "Low"

    # Explicit low-volume downgrade to avoid false strong signals
    try:
        if curr_5m['Volume'] < (curr_5m['Volume_MA'] * 0.5):
            master_signals['scalping']['signal'] = "CAUTION"
            master_signals['scalping']['confidence'] = "Low"
            master_signals['scalping']['reasons'].append("⚠️ Downgraded due to low volume (safeguard)")
    except Exception:
        pass
    
    master_signals['scalping']['score'] = scalp_normalized
    master_signals['scalping']['reasons'] = scalp_reasons

    # Apply meta-ensemble correction for scalping (blend learned prediction)
    try:
        model = st.session_state.get('meta_models', {}).get('5m')
        if model:
            pred_out = predict_price_movement(df_5m.copy(), '5m')
            pred_out['df'] = df_5m
            pred_out['rsi'] = df_5m['RSI'].iloc[-1]
            pred_out['adx'] = df_5m['ADX'].iloc[-1]
            pred_out['volume_ratio'] = df_5m['Volume_Ratio'].iloc[-1] if 'Volume_Ratio' in df_5m.columns else 1.0
            prob_up = meta_predict_from_model(pred_out, model)
            meta_pct = prob_up * 100
            # Blend: 60% rule-based, 40% model
            rule_w = float(st.session_state.get('meta_rule_blend', 0.6))
            meta_w = 1.0 - rule_w
            scalp_normalized = scalp_normalized * rule_w + meta_pct * meta_w
            master_signals['scalping']['reasons'].append(f"🤖 Meta-ensemble blended (prob_up={prob_up:.2f})")
            master_signals['scalping']['score'] = scalp_normalized
    except Exception:
        pass

    # --- META-ENSEMBLE: train lightweight models if not cached ---
    try:
        if 'meta_models' not in st.session_state:
            st.session_state.meta_models = {}
            # Train small models (may take a moment)
            with st.spinner('Training lightweight meta-ensemble (this may take a few seconds)...'):
                try:
                    samples = int(st.session_state.get('meta_training_samples', 80))
                    m5 = train_meta_ensemble(data_sets['5m'], '5m', samples=samples, horizon=1, alpha=0.5)
                    m1 = train_meta_ensemble(data_sets['1h'], '1h', samples=samples, horizon=1, alpha=0.5)
                    m4 = train_meta_ensemble(data_sets['4h'], '4h', samples=samples, horizon=1, alpha=0.5)
                    st.session_state.meta_models['5m'] = m5
                    st.session_state.meta_models['1h'] = m1
                    st.session_state.meta_models['4h'] = m4
                except Exception:
                    st.session_state.meta_models = {}
    except Exception:
        pass
    
    # ============================================
    # INTRADAY SIGNAL (30m + 1h focus)
    # ============================================
    
    intra_score = 0
    intra_max_score = 0
    intra_reasons = []
    
    # 1. Timeframe Alignment (Weight: 30 points)
    intra_max_score += 30
    sig_30m = analysis_results.get('30m')
    sig_1h = analysis_results.get('1h')
    
    if sig_30m and sig_1h:
        if "BUY" in sig_30m['Signal'] and "BUY" in sig_1h['Signal']:
            intra_score += 30
            intra_reasons.append("✅ 30m and 1h both BULLISH - strong alignment")
        elif "SELL" in sig_30m['Signal'] and "SELL" in sig_1h['Signal']:
            intra_score -= 30
            intra_reasons.append("❌ 30m and 1h both BEARISH - strong alignment")
        elif "BUY" in sig_30m['Signal'] and "SELL" in sig_1h['Signal']:
            intra_score -= 10
            intra_reasons.append("⚠️ Conflicting timeframes - counter-trend risk")
        elif "SELL" in sig_30m['Signal'] and "BUY" in sig_1h['Signal']:
            intra_score -= 10
            intra_reasons.append("⚠️ Conflicting timeframes - pullback in uptrend")
    
    # 2. Price Momentum (Weight: 25 points)
    intra_max_score += 25
    if conflict_analysis['momentum_30m'] > 0.5:
        intra_score += 25
        intra_reasons.append(f"✅ Strong 30m momentum ({conflict_analysis['momentum_30m']:+.2f}%)")
    elif conflict_analysis['momentum_30m'] > 0.2:
        intra_score += 15
        intra_reasons.append(f"✅ Positive 30m momentum ({conflict_analysis['momentum_30m']:+.2f}%)")
    elif conflict_analysis['momentum_30m'] < -0.5:
        intra_score -= 25
        intra_reasons.append(f"❌ Strong 30m downtrend ({conflict_analysis['momentum_30m']:+.2f}%)")
    elif conflict_analysis['momentum_30m'] < -0.2:
        intra_score -= 15
        intra_reasons.append(f"⚠️ Negative 30m momentum ({conflict_analysis['momentum_30m']:+.2f}%)")
    
    # 3. Trend Strength (ADX) (Weight: 20 points)
    intra_max_score += 20
    adx_1h = curr_1h['ADX']
    if adx_1h > 30:
        intra_score += 20
        intra_reasons.append(f"✅ Strong trend (ADX: {adx_1h:.1f}) - high probability")
    elif adx_1h > 25:
        intra_score += 12
        intra_reasons.append(f"✅ Moderate trend (ADX: {adx_1h:.1f})")
    elif adx_1h < 20:
        intra_score -= 10
        intra_reasons.append(f"⚠️ Weak trend (ADX: {adx_1h:.1f}) - choppy market")
    
    # 4. EMA Alignment (Weight: 15 points)
    intra_max_score += 15
    ema9_1h = curr_1h['EMA9']
    ema21_1h = curr_1h['EMA21']
    ema50_1h = curr_1h['EMA50']
    curr_price = curr_1h['Close']
    
    if ema9_1h > ema21_1h > ema50_1h and curr_price > ema9_1h:
        intra_score += 15
        intra_reasons.append("✅ Perfect bullish EMA stack")
    elif ema9_1h < ema21_1h < ema50_1h and curr_price < ema9_1h:
        intra_score -= 15
        intra_reasons.append("❌ Perfect bearish EMA stack")
    elif curr_price > ema50_1h:
        intra_score += 8
        intra_reasons.append("✅ Above 50 EMA - bullish bias")
    elif curr_price < ema50_1h:
        intra_score -= 8
        intra_reasons.append("⚠️ Below 50 EMA - bearish bias")
    
    # 5. Conflict & Risk (Weight: 10 points)
    intra_max_score += 10
    if risk_score < 10:
        intra_score += 10
        intra_reasons.append("✅ Low risk environment")
    elif risk_score >= 25:
        intra_score -= 10
        intra_reasons.append(f"❌ High risk detected (Score: {risk_score})")
    
    # Calculate intraday signal
    intra_normalized = ((intra_score + intra_max_score) / (2 * intra_max_score)) * 100

    # Apply candlestick penalty on active 1h timeframe
    try:
        candle_1h = identify_candle(df_1h)
        if "Bearish" in candle_1h or "Shooting Star" in candle_1h or "Evening Star" in candle_1h:
            intra_normalized = intra_normalized * 0.6
            intra_reasons.append(f"❌ 1h Bearish reversal detected - confidence reduced: {candle_1h}")
    except Exception:
        pass
    
    if intra_normalized >= 75 and risk_score < 25:
        master_signals['intraday']['signal'] = "STRONG BUY"
        master_signals['intraday']['confidence'] = "Very High"
    elif intra_normalized >= 60 and risk_score < 30:
        master_signals['intraday']['signal'] = "BUY"
        master_signals['intraday']['confidence'] = "High"
    elif intra_normalized <= 25 and risk_score < 25:
        master_signals['intraday']['signal'] = "STRONG SELL"
        master_signals['intraday']['confidence'] = "Very High"
    elif intra_normalized <= 40 and risk_score < 30:
        master_signals['intraday']['signal'] = "SELL"
        master_signals['intraday']['confidence'] = "High"
    else:
        master_signals['intraday']['signal'] = "NEUTRAL"
        master_signals['intraday']['confidence'] = "Low"
    
    master_signals['intraday']['score'] = intra_normalized
    master_signals['intraday']['reasons'] = intra_reasons

    # Apply meta-ensemble correction for intraday (1h model)
    try:
        model1 = st.session_state.get('meta_models', {}).get('1h')
        if model1:
            pred_out1 = predict_price_movement(df_1h.copy(), '1h')
            pred_out1['df'] = df_1h
            pred_out1['rsi'] = df_1h['RSI'].iloc[-1]
            pred_out1['adx'] = df_1h['ADX'].iloc[-1]
            pred_out1['volume_ratio'] = df_1h['Volume_Ratio'].iloc[-1] if 'Volume_Ratio' in df_1h.columns else 1.0
            prob_up1 = meta_predict_from_model(pred_out1, model1)
            meta_pct1 = prob_up1 * 100
            rule_w = float(st.session_state.get('meta_rule_blend', 0.6))
            meta_w = 1.0 - rule_w
            intra_normalized = intra_normalized * rule_w + meta_pct1 * meta_w
            master_signals['intraday']['reasons'].append(f"🤖 Meta-ensemble blended (prob_up={prob_up1:.2f})")
            master_signals['intraday']['score'] = intra_normalized
    except Exception:
        pass

    # Low-volume safeguard for intraday (1h)
    try:
        if curr_1h['Volume'] < (curr_1h['Volume_MA'] * 0.5):
            master_signals['intraday']['score'] = master_signals['intraday']['score'] * 0.6
            master_signals['intraday']['signal'] = "CAUTION"
            master_signals['intraday']['confidence'] = "Low"
            master_signals['intraday']['reasons'].append("⚠️ Intraday downgraded due to low volume (safeguard)")
    except Exception:
        pass
    
    # ============================================
    # SWING SIGNAL (4h + Daily focus)
    # ============================================
    
    swing_score = 0
    swing_max_score = 0
    swing_reasons = []
    
    # 1. Major Trend (Weight: 35 points)
    swing_max_score += 35
    sig_4h = analysis_results.get('4h')
    
    if sig_4h:
        if sig_4h['Score'] >= 75:
            swing_score += 35
            swing_reasons.append(f"✅ Very strong 4h trend (Score: {sig_4h['Score']})")
        elif sig_4h['Score'] >= 65:
            swing_score += 25
            swing_reasons.append(f"✅ Strong 4h trend (Score: {sig_4h['Score']})")
        elif sig_4h['Score'] <= 35:
            swing_score -= 35
            swing_reasons.append(f"❌ Very weak 4h trend (Score: {sig_4h['Score']})")
        elif sig_4h['Score'] <= 45:
            swing_score -= 25
            swing_reasons.append(f"⚠️ Weak 4h trend (Score: {sig_4h['Score']})")
    
    # 2. Higher Timeframe Alignment (Weight: 30 points)
    swing_max_score += 30
    if sig_1h and sig_4h:
        if "BUY" in sig_1h['Signal'] and "BUY" in sig_4h['Signal']:
            swing_score += 30
            swing_reasons.append("✅ 1h and 4h aligned BULLISH")
        elif "SELL" in sig_1h['Signal'] and "SELL" in sig_4h['Signal']:
            swing_score -= 30
            swing_reasons.append("❌ 1h and 4h aligned BEARISH")
    
    # 3. 200 EMA Position (Weight: 20 points)
    swing_max_score += 20
    ema200_4h = curr_4h['EMA200']
    price_4h = curr_4h['Close']
    
    distance_from_200 = ((price_4h - ema200_4h) / ema200_4h) * 100
    
    if price_4h > ema200_4h:
        if distance_from_200 > 5:
            swing_score += 20
            swing_reasons.append(f"✅ Well above 200 EMA (+{distance_from_200:.1f}%)")
        else:
            swing_score += 12
            swing_reasons.append(f"✅ Above 200 EMA (+{distance_from_200:.1f}%)")
    else:
        if distance_from_200 < -5:
            swing_score -= 20
            swing_reasons.append(f"❌ Well below 200 EMA ({distance_from_200:.1f}%)")
        else:
            swing_score -= 12
            swing_reasons.append(f"⚠️ Below 200 EMA ({distance_from_200:.1f}%)")
    
    # 4. ADX Trend Strength (Weight: 15 points)
    swing_max_score += 15
    adx_4h = curr_4h['ADX']
    if adx_4h > 35:
        swing_score += 15
        swing_reasons.append(f"✅ Very strong trend (ADX: {adx_4h:.1f})")
    elif adx_4h > 28:
        swing_score += 10
        swing_reasons.append(f"✅ Strong trend (ADX: {adx_4h:.1f})")
    elif adx_4h < 20:
        swing_score -= 8
        swing_reasons.append(f"⚠️ No clear trend (ADX: {adx_4h:.1f})")
    
    # Calculate swing signal
    swing_normalized = ((swing_score + swing_max_score) / (2 * swing_max_score)) * 100

    # Apply candlestick penalty for 4h
    try:
        candle_4h = identify_candle(df_4h)
        if "Bearish" in candle_4h or "Shooting Star" in candle_4h or "Evening Star" in candle_4h:
            swing_normalized = swing_normalized * 0.6
            swing_reasons.append(f"❌ 4h Bearish reversal detected - confidence reduced: {candle_4h}")
    except Exception:
        pass
    
    if swing_normalized >= 75:
        master_signals['swing']['signal'] = "STRONG BUY"
        master_signals['swing']['confidence'] = "Very High"
    elif swing_normalized >= 65:
        master_signals['swing']['signal'] = "BUY"
        master_signals['swing']['confidence'] = "High"
    elif swing_normalized <= 25:
        master_signals['swing']['signal'] = "STRONG SELL"
        master_signals['swing']['confidence'] = "Very High"
    elif swing_normalized <= 35:
        master_signals['swing']['signal'] = "SELL"
        master_signals['swing']['confidence'] = "High"
    else:
        master_signals['swing']['signal'] = "NEUTRAL"
        master_signals['swing']['confidence'] = "Medium"
    
    master_signals['swing']['score'] = swing_normalized
    master_signals['swing']['reasons'] = swing_reasons

    # Apply meta-ensemble correction for swing (4h model)
    try:
        model4 = st.session_state.get('meta_models', {}).get('4h')
        if model4:
            pred_out4 = predict_price_movement(df_4h.copy(), '4h')
            pred_out4['df'] = df_4h
            pred_out4['rsi'] = df_4h['RSI'].iloc[-1]
            pred_out4['adx'] = df_4h['ADX'].iloc[-1]
            pred_out4['volume_ratio'] = df_4h['Volume_Ratio'].iloc[-1] if 'Volume_Ratio' in df_4h.columns else 1.0
            prob_up4 = meta_predict_from_model(pred_out4, model4)
            meta_pct4 = prob_up4 * 100
            rule_w = float(st.session_state.get('meta_rule_blend', 0.6))
            meta_w = 1.0 - rule_w
            swing_normalized = swing_normalized * rule_w + meta_pct4 * meta_w
            master_signals['swing']['reasons'].append(f"🤖 Meta-ensemble blended (prob_up={prob_up4:.2f})")
            master_signals['swing']['score'] = swing_normalized
    except Exception:
        pass

    # Low-volume safeguard for swing (4h)
    try:
        if curr_4h['Volume'] < (curr_4h['Volume_MA'] * 0.5):
            master_signals['swing']['score'] = master_signals['swing']['score'] * 0.6
            master_signals['swing']['signal'] = "CAUTION"
            master_signals['swing']['confidence'] = "Low"
            master_signals['swing']['reasons'].append("⚠️ Swing downgraded due to low volume (safeguard)")
    except Exception:
        pass

    # --- Timeframe Hierarchy Filter ---
    try:
        sig_1h = analysis_results.get('1h')
        if sig_1h and "SELL" in sig_1h.get('Signal', '') and sig_1h.get('Score', 0) >= 60:
            # Cap lower timeframe signals to neutral/scalp-only
            master_signals['scalping']['signal'] = "CAUTION"
            master_signals['scalping']['confidence'] = "Low"
            master_signals['scalping']['reasons'].append("⚠️ Lower TF capped due to strong 1h SELL (Timeframe Hierarchy)")
            master_signals['intraday']['signal'] = "CAUTION"
            master_signals['intraday']['confidence'] = "Low"
            master_signals['intraday']['reasons'].append("⚠️ Intraday capped due to strong 1h SELL (Timeframe Hierarchy)")
    except Exception:
        pass

    # --- RSI Overbought Exponential Penalty ---
    try:
        rsi_1h_val = float(curr_1h.get('RSI', 0))
    except Exception:
        rsi_1h_val = 0
    try:
        rsi_4h_val = float(curr_4h.get('RSI', 0))
    except Exception:
        rsi_4h_val = 0

    top_rsi = max(rsi_1h_val, rsi_4h_val)
    if top_rsi > 70:
        # exponential penalty factor
        penalty = np.exp(-(top_rsi - 70) / 4.0)
        for key in ['scalping', 'intraday', 'swing']:
            sig = master_signals.get(key)
            if sig and 'BUY' in sig['signal']:
                old_score = sig.get('score', 0)
                new_score = old_score * penalty
                master_signals[key]['score'] = new_score
                master_signals[key]['reasons'].append(f"⚠️ RSI overbought ({top_rsi:.1f}) - exponential penalty applied (x{penalty:.2f})")
                # Downgrade signal if score falls below thresholds
                if new_score < 60:
                    master_signals[key]['signal'] = 'CAUTION'
                    master_signals[key]['confidence'] = 'Low'

    # Final confidence threshold enforcement (user-configurable)
    try:
        thresh = float(st.session_state.get('confidence_threshold', 55))
        for key in ['scalping', 'intraday', 'swing']:
            sig = master_signals.get(key)
            if sig:
                sc = float(sig.get('score', 0))
                if sc < thresh:
                    sig['reasons'].append(f"⚠️ Score below confidence threshold ({sc:.1f} < {thresh}) - downgrading to CAUTION")
                    sig['signal'] = 'CAUTION'
                    sig['confidence'] = 'Low'
    except Exception:
        pass

    return master_signals

# --- 8. BACKTESTING ENGINE ---
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
        'currents': [],
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
        results['currents'].append(current_price_at_time)
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


def tune_blend_weight_for_timeframe(df, timeframe, samples=10):
    """Try several blend weights and return best blend based on direction accuracy."""
    best = {'blend': st.session_state.meta_rule_blend, 'acc': 0}
    weights = np.linspace(0.0, 1.0, 11)
    for w in weights:
        # run quick backtest using this blend
        # temporarily set blend
        original = st.session_state.meta_rule_blend
        st.session_state.meta_rule_blend = w
        try:
            df_ind = add_indicators(df.copy())
            res = run_backtest(df_ind, timeframe, periods_ahead=1)
            if res and res['total_predictions'] > 0:
                acc = res['direction_accuracy']
                if acc > best['acc']:
                    best = {'blend': w, 'acc': acc}
        except Exception:
            pass
        finally:
            st.session_state.meta_rule_blend = original
    return best


def walk_forward_cv(df, timeframe, train_window=500, test_window=50, step=50, horizon=1, samples_per_train=80):
    """Performs walk-forward cross-validation for the meta-ensemble.
    Returns a dict with per-fold and aggregated metrics.
    - df: full historical dataframe with indicators
    - train_window: number of candles used to train each fold
    - test_window: number of candles for out-of-sample test per fold
    - step: how far to move the window between folds
    - horizon: prediction horizon (in candles)
    """
    n = len(df)
    if n < train_window + test_window + 10:
        return None

    folds = []
    start_idx = 0
    while start_idx + train_window + test_window <= n:
        train_idx_start = start_idx
        train_idx_end = start_idx + train_window
        test_idx_start = train_idx_end
        test_idx_end = train_idx_end + test_window

        train_df = df.iloc[train_idx_start:train_idx_end].copy()
        test_df = df.iloc[test_idx_start:test_idx_end].copy()

        # Train model on train_df
        model = train_meta_ensemble(train_df, timeframe, samples=samples_per_train, horizon=horizon, alpha=0.5)

        # Evaluate on test_df
        y_true = []
        y_pred_prob = []
        y_pred_dir = []

        # For each point in test, build historical slice up to that point (to avoid lookahead)
        for i in range(test_idx_start, test_idx_end - horizon):
            hist = df.iloc[:i+1].copy()
            pred_out = predict_price_movement(hist, timeframe)
            if pred_out is None or model is None:
                continue
            pred_out['df'] = hist
            pred_out['rsi'] = hist['RSI'].iloc[-1] if 'RSI' in hist.columns else 50
            pred_out['adx'] = hist['ADX'].iloc[-1] if 'ADX' in hist.columns else 20
            prob_up = meta_predict_from_model(pred_out, model)

            current_price = pred_out['current']
            future_price = df['Close'].iloc[i + horizon]
            true_up = 1 if future_price > current_price else 0

            y_true.append(true_up)
            y_pred_prob.append(prob_up)
            y_pred_dir.append(1 if prob_up >= 0.5 else 0)

        # Compute metrics for this fold
        if len(y_true) == 0:
            start_idx += step
            continue

        y_true = np.array(y_true)
        y_pred_prob = np.array(y_pred_prob)
        y_pred_dir = np.array(y_pred_dir)

        accuracy = float((y_pred_dir == y_true).mean()) * 100.0
        brier = float(np.mean((y_pred_prob - y_true) ** 2))
        avg_prob = float(y_pred_prob.mean())

        folds.append({
            'train_start': df.index[train_idx_start],
            'train_end': df.index[train_idx_end-1],
            'test_start': df.index[test_idx_start],
            'test_end': df.index[test_idx_end-1],
            'n': len(y_true),
            'accuracy': accuracy,
            'brier': brier,
            'avg_prob': avg_prob
        })

        start_idx += step

    # Aggregate
    if not folds:
        return None

    accuracies = [f['accuracy'] for f in folds]
    brierrs = [f['brier'] for f in folds]
    avg_probs = [f['avg_prob'] for f in folds]

    return {
        'folds': folds,
        'mean_accuracy': float(np.mean(accuracies)),
        'std_accuracy': float(np.std(accuracies)),
        'mean_brier': float(np.mean(brierrs)),
        'mean_prob': float(np.mean(avg_probs)),
        'n_folds': len(folds)
    }


def run_wfcv_grid(df, timeframe, blend_values=None, conf_values=None, train_window=500, test_window=50, step=50, horizon=1, samples_per_train=80, feature_flags=None):
    """Grid-search over blend weights and confidence thresholds using walk-forward CV.
    feature_flags: dict to toggle features like {'use_cvd':True, 'use_orderbook':True, 'use_velocity':True}
    Returns best settings and a summary dict with all results.
    """
    if blend_values is None:
        blend_values = np.linspace(0.0, 1.0, 6)
    if conf_values is None:
        conf_values = [0.5, 0.6, 0.7, 0.8]
    if feature_flags is None:
        feature_flags = {'use_cvd': True, 'use_orderbook': True, 'use_velocity': True}

    n = len(df)
    results = []

    # window iteration
    start_idx = 0
    folds = []
    while start_idx + train_window + test_window <= n:
        train_idx_start = start_idx
        train_idx_end = start_idx + train_window
        test_idx_start = train_idx_end
        test_idx_end = train_idx_end + test_window

        train_df = df.iloc[train_idx_start:train_idx_end].copy()
        test_df = df.iloc[test_idx_start:test_idx_end].copy()

        model = train_meta_ensemble(train_df, timeframe, samples=samples_per_train, horizon=horizon, alpha=0.5)
        folds.append((train_df, test_df, model))
        start_idx += step

    # Evaluate grid
    for blend in blend_values:
        for conf in conf_values:
            accs = []
            brs = []
            covs = []
            for (train_df, test_df, model) in folds:
                y_true = []
                y_pred_prob = []
                selected_mask = []
                for i in range(len(test_df) - horizon):
                    idx = test_df.index[i]
                    # hist up to this test point (avoid lookahead)
                    hist = df.loc[:idx].copy()
                    pred_out = predict_price_movement(hist, timeframe)
                    if pred_out is None or model is None:
                        continue
                    prob_up = meta_predict_from_model(pred_out, model)

                    # apply blend as simple convex mixture with rule-based confidence if present
                    rule_conf = pred_out.get('confidence', 0.5)
                    combined = blend * prob_up + (1 - blend) * rule_conf

                    # apply feature flags by ignoring certain overrides (best-effort)
                    # (If disabled, we reduce their effect by nudging combined towards 0.5)
                    if not feature_flags.get('use_cvd', True):
                        combined = 0.8 * combined + 0.2 * 0.5
                    if not feature_flags.get('use_orderbook', True):
                        combined = 0.9 * combined + 0.1 * 0.5
                    if not feature_flags.get('use_velocity', True):
                        combined = 0.9 * combined + 0.1 * 0.5

                    current_price = pred_out.get('current', hist['Close'].iloc[-1])
                    future_price = df['Close'].loc[idx:].iloc[horizon]
                    true_up = 1 if future_price > current_price else 0

                    y_true.append(true_up)
                    y_pred_prob.append(combined)
                    selected_mask.append(1 if combined >= conf else 0)

                if len(y_true) == 0:
                    continue
                y_true = np.array(y_true)
                y_pred_prob = np.array(y_pred_prob)
                selected_mask = np.array(selected_mask)

                # metrics on selected predictions only
                if selected_mask.sum() > 0:
                    preds = (y_pred_prob[selected_mask == 1] >= 0.5).astype(int)
                    true_sel = y_true[selected_mask == 1]
                    acc = float((preds == true_sel).mean())
                else:
                    acc = np.nan

                brier = float(np.mean((y_pred_prob - y_true) ** 2))
                cov = float(selected_mask.mean())

                accs.append(acc if not np.isnan(acc) else 0.0)
                brs.append(brier)
                covs.append(cov)

            if len(accs) == 0:
                continue
            avg_acc = float(np.nanmean(accs)) * 100.0
            avg_brier = float(np.mean(brs))
            avg_cov = float(np.mean(covs)) * 100.0

            results.append({'blend': float(blend), 'conf': float(conf), 'accuracy': avg_acc, 'brier': avg_brier, 'coverage': avg_cov})

    if not results:
        return None

    dfres = pd.DataFrame(results)
    # choose best by accuracy then coverage
    dfres = dfres.sort_values(['accuracy', 'coverage'], ascending=[False, False])
    best = dfres.iloc[0].to_dict()

    return {'grid': dfres, 'best': best}


def persist_best_model(df, timeframe, best_settings, save_dir='.cache'):
    os.makedirs(save_dir, exist_ok=True)
    blend = best_settings.get('blend', 0.5)
    conf = best_settings.get('conf', 0.5)
    # retrain model on full df
    model = train_meta_ensemble(df, timeframe, samples=int(st.session_state.get('meta_training_samples', 80)), horizon=1, alpha=0.5)
    model_path = os.path.join(save_dir, f'best_meta_{timeframe}.pkl')
    with open(model_path, 'wb') as f:
        pickle.dump({'model': model, 'blend': blend, 'conf': conf, 'timeframe': timeframe}, f)
    settings_path = os.path.join(save_dir, f'best_meta_{timeframe}.json')
    with open(settings_path, 'w') as f:
        json.dump({'blend': blend, 'conf': conf, 'timeframe': timeframe}, f)
    return model_path, settings_path


def adjust_prob_for_bear_reversal(pred_out, prob, severity=0.4):
    """Apply severe negative multiplier to UP probability when bearish reversal detected."""
    try:
        df = pred_out.get('df')
        if df is None or len(df) < 3:
            return prob
        pattern = identify_candle(df)
        bearish_patterns = ['Bearish Engulfing', 'Evening Star', 'Shooting Star', 'Hanging Man']
        if pattern in bearish_patterns:
            return prob * severity
    except Exception:
        return prob
    return prob


def generate_master_strict_signal(df, timeframe, min_meta_conf=0.8, min_rule_conf=0.8, tp_atr_mult=1.0, sl_atr_mult=1.0):
    """Generate a very strict master signal: only emit when rule-based and meta-model agree
    and supporting microstructure checks (velocity, no bearish reversal) pass.
    Returns dict with keys: signal ('UP'/'DOWN'/'NONE'), entry, tp, sl, confidence
    """
    try:
        # override with session settings if available
        sp = st.session_state.get('strict_params')
        if sp:
            min_meta_conf = float(sp.get('min_meta_conf', min_meta_conf))
            min_rule_conf = float(sp.get('min_rule_conf', min_rule_conf))
            tp_atr_mult = float(sp.get('tp_atr_mult', tp_atr_mult))
            sl_atr_mult = float(sp.get('sl_atr_mult', sl_atr_mult))
        # require minimum history
        if df is None or len(df) < 30:
            return {'signal': 'NONE', 'confidence': 0.0}

        # rule-based signal
        rule = generate_advanced_signal(df, timeframe)
        rule_sig = rule.get('signal', 'NONE')
        rule_conf = float(rule.get('confidence', 0.5))

        # meta-model probability
        model = None
        meta_models = st.session_state.get('meta_models', {})
        if isinstance(meta_models, dict):
            model = meta_models.get(timeframe)
        if model is None:
            # try load persisted model
            try:
                path = f'.cache/best_meta_{timeframe}.pkl'
                if os.path.exists(path):
                    with open(path,'rb') as f:
                        obj = pickle.load(f)
                        model = obj.get('model')
            except Exception:
                model = None

        pred_out = predict_price_movement(df, timeframe)
        if pred_out is None:
            return {'signal': 'NONE', 'confidence': 0.0}

        meta_prob = 0.5
        if model is not None:
            meta_prob = float(meta_predict_from_model(pred_out, model))

        # microstructure checks
        vel = get_short_term_velocity(df, minutes=5) if 'get_short_term_velocity' in globals() else 0.0
        cvd = compute_cvd_approx(df, window=20) if 'compute_cvd_approx' in globals() else 0.0

        # bearish reversal detection
        candle = identify_candle(df) if 'identify_candle' in globals() else ''
        bearish_patterns = ['Bearish Engulfing', 'Evening Star', 'Shooting Star', 'Hanging Man']

        # decide
        signal = 'NONE'
        confidence = min(meta_prob, rule_conf)

        if rule_sig == 'UP' and meta_prob >= min_meta_conf and rule_conf >= min_rule_conf and vel > 0 and candle not in bearish_patterns and cvd > -0.2:
            signal = 'UP'
        elif rule_sig == 'DOWN' and (1 - meta_prob) >= min_meta_conf and rule_conf >= min_rule_conf and vel < 0 and candle not in ['Bullish Engulfing', 'Morning Star'] and cvd < 0.2:
            signal = 'DOWN'

        # TP/SL using ATR
        # compute ATR(14)
        df2 = df.copy()
        df2['prev_close'] = df2['Close'].shift(1)
        tr1 = (df2['High'] - df2['Low']).abs()
        tr2 = (df2['High'] - df2['prev_close']).abs()
        tr3 = (df2['Low'] - df2['prev_close']).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(14, min_periods=1).mean().iloc[-1]

        entry = float(df['Close'].iloc[-1])
        tp = None
        sl = None
        if signal == 'UP':
            tp = entry + tp_atr_mult * float(atr)
            sl = entry - sl_atr_mult * float(atr)
        elif signal == 'DOWN':
            tp = entry - tp_atr_mult * float(atr)
            sl = entry + sl_atr_mult * float(atr)

        return {'signal': signal, 'entry': entry, 'tp': tp, 'sl': sl, 'confidence': confidence, 'meta_prob': meta_prob, 'rule_conf': rule_conf}
    except Exception as e:
        return {'signal': 'NONE', 'confidence': 0.0}


def run_backtest_strict_master(df, timeframe, horizon=50, tp_atr_mult=1.0, sl_atr_mult=1.0):
    """Backtest the strict master signal: simulate TP/SL over next `horizon` bars.
    Returns metrics: total_signals, tp_hits, sl_hits, accuracy, avg_holding_bars
    """
    signals = []
    tp_hits = 0
    sl_hits = 0
    unresolved = 0
    holding_bars = []

    for i in range(30, len(df) - horizon):
        hist = df.iloc[:i+1].copy()
        res = generate_master_strict_signal(hist, timeframe, tp_atr_mult=tp_atr_mult, sl_atr_mult=sl_atr_mult)
        if res.get('signal') == 'NONE':
            continue
        entry_idx = i
        entry_price = res['entry']
        tp = res['tp']
        sl = res['sl']
        direction = res['signal']

        hit = None
        bars_used = None
        # simulate forward
        for j in range(1, horizon+1):
            row = df.iloc[i + j]
            high = row['High']
            low = row['Low']
            if direction == 'UP':
                if high >= tp and low <= sl:
                    # both hit in same bar: decide by proximity to entry
                    if abs(tp - entry_price) <= abs(entry_price - sl):
                        hit = 'TP'
                    else:
                        hit = 'SL'
                    bars_used = j
                    break
                elif high >= tp:
                    hit = 'TP'
                    bars_used = j
                    break
                elif low <= sl:
                    hit = 'SL'
                    bars_used = j
                    break
            else:
                if low <= tp and high >= sl:
                    if abs(entry_price - tp) <= abs(sl - entry_price):
                        hit = 'TP'
                    else:
                        hit = 'SL'
                    bars_used = j
                    break
                elif low <= tp:
                    hit = 'TP'
                    bars_used = j
                    break
                elif high >= sl:
                    hit = 'SL'
                    bars_used = j
                    break

        signals.append({'idx': i, 'signal': direction, 'entry': entry_price, 'tp': tp, 'sl': sl, 'hit': hit, 'bars': bars_used})
        if hit == 'TP':
            tp_hits += 1
        elif hit == 'SL':
            sl_hits += 1
        else:
            unresolved += 1
        if bars_used:
            holding_bars.append(bars_used)

    total = len(signals)
    accuracy = float(tp_hits) / total * 100.0 if total > 0 else 0.0
    avg_hold = float(np.mean(holding_bars)) if holding_bars else None
    return {'total_signals': total, 'tp_hits': tp_hits, 'sl_hits': sl_hits, 'unresolved': unresolved, 'accuracy': accuracy, 'avg_holding_bars': avg_hold, 'signals': signals}

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

    # Auto-tune blend weight if requested
    if st.session_state.get('tune_blend', False):
        with st.spinner('Auto-tuning blend weight (this may take a while)...'):
            bests = []
            for tf in timeframes:
                df = data_sets[tf].copy()
                try:
                    df_ind = add_indicators(df)
                    b = tune_blend_weight_for_timeframe(df_ind, tf, samples=8)
                    bests.append(b)
                except Exception:
                    continue
            # Choose blend that maximizes average accuracy
            if bests:
                blends = [b['blend'] for b in bests if b and 'blend' in b]
                if blends:
                    new_blend = float(np.mean(blends))
                    st.session_state.meta_rule_blend = float(np.clip(new_blend, 0.0, 1.0))
                    st.success(f"Auto-tune complete. New rule weight: {st.session_state.meta_rule_blend:.2f}")
            st.session_state.tune_blend = False
    
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
            # Historical 30-day rolling win-rate chart (direction correctness)
            try:
                preds = np.array(result['predictions'])
                actuals = np.array(result['actuals'])
                currents = np.array(result.get('currents', preds))
                # Direction correctness per test
                correct = (np.sign(preds - currents) == np.sign(actuals - currents)).astype(int)
                # 30-point rolling win rate (or smaller if not enough)
                window = min(30, len(correct))
                if window >= 3:
                    rolling = np.convolve(correct, np.ones(window)/window, mode='valid') * 100
                    # Build a simple line chart
                    import plotly.express as px
                    df_roll = pd.DataFrame({
                        'timestamp': result['timestamps'][window-1:],
                        'win_rate': rolling
                    })
                    fig = px.line(df_roll, x='timestamp', y='win_rate', title='30-Period Rolling Win-Rate (%)')
                    fig.update_yaxes(range=[0,100])
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info('Not enough points to plot 30-period rolling win-rate')
            except Exception:
                st.info('Unable to render rolling win-rate chart')
            
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
        # Walk-forward CV and Auto-tune options
        st.markdown("---")
        col_a, col_b, col_c = st.columns([1,1,1])
        with col_a:
            if st.button('Run Walk-Forward CV'):
                with st.spinner('Running walk-forward cross-validation...'):
                    df_for_cv = add_indicators(data_sets[selected_tf].copy())
                    cv_res = walk_forward_cv(df_for_cv, selected_tf, train_window=500, test_window=50, step=100, horizon=1, samples_per_train=int(st.session_state.get('meta_training_samples',80)))
                    if cv_res is None:
                        st.error('Not enough data or model training failed for walk-forward CV')
                    else:
                        st.success(f"Walk-forward CV completed: {cv_res['n_folds']} folds")
                        st.write(f"Mean accuracy: {cv_res['mean_accuracy']:.2f}% (std: {cv_res['std_accuracy']:.2f})")
                        st.write(f"Mean Brier score: {cv_res['mean_brier']:.4f}")
                        df_folds = pd.DataFrame(cv_res['folds'])
                        st.dataframe(df_folds)
                        try:
                            import plotly.express as px
                            fig2 = px.line(df_folds, x='test_start', y='accuracy', title='Walk-Forward Fold Accuracy (%)')
                            st.plotly_chart(fig2, use_container_width=True)
                        except Exception:
                            pass
        with col_b:
            if st.button('Auto-tune & Persist Best Model'):
                with st.spinner('Running grid-search WFCV and persisting best model...'):
                    df_for_cv = add_indicators(data_sets[selected_tf].copy())
                    blend_vals = np.linspace(0.0,1.0,6)
                    conf_vals = [0.5,0.6,0.7,0.8]
                    grid_res = run_wfcv_grid(df_for_cv, selected_tf, blend_values=blend_vals, conf_values=conf_vals, train_window=500, test_window=50, step=100, horizon=1, samples_per_train=int(st.session_state.get('meta_training_samples',80)))
                    if grid_res is None:
                        st.error('Grid search failed or insufficient data')
                    else:
                        best = grid_res['best']
                        st.success(f"Best settings found: blend={best['blend']:.2f}, conf={best['conf']:.2f}")
                        st.write(grid_res['grid'])
                        model_path, settings_path = persist_best_model(df_for_cv, selected_tf, best, save_dir='.cache')
                        st.write('Model saved to:', model_path)
                        st.write('Settings saved to:', settings_path)
        with col_c:
            if st.button('Feature Ablation (CVD/OB/Vel)'):
                with st.spinner('Running feature ablation WFCV...'):
                    df_for_cv = add_indicators(data_sets[selected_tf].copy())
                    combos = [
                        {'use_cvd': True, 'use_orderbook': True, 'use_velocity': True},
                        {'use_cvd': False, 'use_orderbook': True, 'use_velocity': True},
                        {'use_cvd': True, 'use_orderbook': False, 'use_velocity': True},
                        {'use_cvd': True, 'use_orderbook': True, 'use_velocity': False},
                    ]
                    ablation_rows = []
                    for flags in combos:
                        res = run_wfcv_grid(df_for_cv, selected_tf, blend_values=[0.5], conf_values=[0.6], train_window=500, test_window=50, step=100, horizon=1, samples_per_train=int(st.session_state.get('meta_training_samples',80)), feature_flags=flags)
                        if res is None:
                            continue
                        best = res['best']
                        ablation_rows.append({**flags, 'accuracy': best['accuracy'], 'coverage': best['coverage']})
                    if ablation_rows:
                        st.table(pd.DataFrame(ablation_rows))
        # Strict master backtest
        st.markdown("---")
        if st.button('Run Strict Master Backtest'):
            with st.spinner('Running strict master backtest...'):
                df_bt = add_indicators(data_sets[selected_tf].copy())
                res = run_backtest_strict_master(df_bt, selected_tf, horizon=50, tp_atr_mult=1.0, sl_atr_mult=1.0)
                if res['total_signals'] == 0:
                    st.warning('No strict signals found with current parameters')
                else:
                    st.success(f"Total signals: {res['total_signals']} — Accuracy (TP rate): {res['accuracy']:.2f}%")
                    st.write(f"TP hits: {res['tp_hits']}, SL hits: {res['sl_hits']}, Unresolved: {res['unresolved']}")
                    if res['avg_holding_bars']:
                        st.write(f"Average holding bars for resolved trades: {res['avg_holding_bars']:.1f}")
                    df_signals = pd.DataFrame(res['signals'])
                    st.dataframe(df_signals)
        
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

def render_professional_confluence(data_sets, symbol, news_items):
    """Renders the professional-grade confluence analysis"""
    
    st.subheader("🎯 Professional Confluence Analysis")
    
    st.info("""
    **Institutional-Grade Signal Scoring** - This combines:
    📰 Sentiment (News/Market Context) • 🎯 Market Regime Detection • 📊 Technical Alignment • 💼 Order Flow • 📈 Volume
    """)
    
    # Get all analysis components
    df_1h = add_indicators(data_sets['1h'])
    df_5m = add_indicators(data_sets['5m'])
    
    sentiment = get_sentiment_score(symbol, news_items)
    order_flow = detect_order_flow(df_5m)
    regime = detect_market_regime(df_1h)
    volume_profile = calculate_volume_profile(df_1h)

    # Macro blackout check (uses Finnhub API key if provided in session state)
    finnhub_key = st.session_state.get('finnhub_api_key') or None
    try:
        macro_blackout, ev = check_macro_blackout(finnhub_key, lookahead_minutes=15)
    except Exception:
        # Protect against Finnhub/API throttling causing sidebar crashes
        macro_blackout, ev = False, None

    # Depth imbalance from Binance (for crypto-like symbols)
    imbalance = get_binance_imbalance(symbol)

    # FVG / Liquidity / MSB detectors
    micro_flags = detect_fvg_liquidity_msb(df_5m)

    confluence = calculate_confluence_score(df_1h, sentiment, order_flow, regime)

    # Apply macro blackout override
    if macro_blackout:
        st.error("MACRO BLACKOUT: AI Signals Paused Due to High Volatility News Event")
        confluence['total_score'] = 0
        confluence['breakdown']['Sentiment'] = "0/100"

    # Apply order-book imbalance adjustments
    if imbalance is not None:
        try:
            if imbalance > 0.65:
                # bullish depth - boost order_flow component
                confluence['total_score'] = min(100, confluence['total_score'] + 8)
                confluence['breakdown']['Order Flow'] = f"{min(100, float(confluence['component_scores'].get('order_flow',0))*100 + 8):.0f}/100"
            elif imbalance < 0.35:
                confluence['total_score'] = max(0, confluence['total_score'] - 12)
                confluence['breakdown']['Order Flow'] = f"{max(0, float(confluence['component_scores'].get('order_flow',0))*100 - 12):.0f}/100"
        except Exception:
            pass

    # Apply microstructure detectors (penalties / boosts)
    if micro_flags.get('liquidity_sweep'):
        confluence['total_score'] = max(0, confluence['total_score'] - 20)
        confluence['breakdown']['Technical'] = f"{max(0, float(confluence['component_scores'].get('technical',0))*100 - 20):.0f}/100"
    if micro_flags.get('fvg'):
        # FVG can be a target or a warning depending on direction; slightly boost confidence
        confluence['total_score'] = min(100, confluence['total_score'] + 6)
    if micro_flags.get('msb_bear'):
        confluence['total_score'] = max(0, confluence['total_score'] - 25)
    if micro_flags.get('msb_bull'):
        confluence['total_score'] = min(100, confluence['total_score'] + 12)
    
    # Main Score Display
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        score = confluence['total_score']
        # High-contrast key metric card
        st.markdown(f"<div class='key-metric'>🎯 CONFLUENCE SCORE<br><strong style='font-size:28px'>{score:.1f}/100</strong></div>", unsafe_allow_html=True)
        # Short textual interpretation
        if score >= 80:
            st.markdown("**INSTITUTIONAL GRADE SETUP** - All systems aligned!")
        elif score >= 65:
            st.markdown("**HIGH QUALITY SETUP** - Strong agreement")
        elif score >= 50:
            st.markdown("**MODERATE SETUP** - Mixed signals")
        else:
            st.markdown("**LOW QUALITY** - Conflicting data")
    
    with col2:
        st.metric("Market Regime", regime['regime'] if regime else "Unknown")
        st.caption(f"Strategy: {regime['strategy']}" if regime else "")
    
    with col3:
        st.metric("Sentiment", sentiment['classification'])
        st.caption(f"Score: {sentiment['score']:+.0f}")
    
    st.divider()
    
    # Component Breakdown
    st.markdown("### 📊 Score Breakdown (Weighted)")
    
    breakdown_cols = st.columns(5)
    components = [
        ("📰 Sentiment", confluence['breakdown']['Sentiment'], 0.20),
        ("🎯 Regime", confluence['breakdown']['Regime'], 0.25),
        ("📈 Technical", confluence['breakdown']['Technical'], 0.30),
        ("💼 Order Flow", confluence['breakdown']['Order Flow'], 0.15),
        ("📊 Volume", confluence['breakdown']['Volume'], 0.10)
    ]
    
    for idx, (name, score_str, weight) in enumerate(components):
        with breakdown_cols[idx]:
            st.markdown(f"**{name}**")
            st.markdown(f"{score_str}")
            st.caption(f"Weight: {weight*100:.0f}%")
    
    st.divider()
    
    # Detailed Analysis Panels
    detail_cols = st.columns(2)
    
    with detail_cols[0]:
        # Sentiment Details
        st.markdown("#### 📰 Sentiment Analysis")
        if sentiment['signals']:
            for signal in sentiment['signals']:
                st.caption(signal)
        else:
            st.caption("No strong sentiment signals detected")
        
        # Order Flow Details
        st.markdown("#### 💼 Order Flow Analysis")
        if order_flow and order_flow['signals']:
            st.markdown(f"**{order_flow['classification']}** (Strength: {order_flow['strength']:+d})")
            for signal in order_flow['signals']:
                st.caption(signal)
        else:
            st.caption("Neutral order flow")
    
    with detail_cols[1]:
        # Regime Details
        st.markdown("#### 🎯 Market Regime")
        if regime:
            st.markdown(f"**{regime['regime']}**")
            st.caption(f"• ADX: {regime['adx']:.1f} {'(Strong Trend)' if regime['adx'] > 25 else '(Weak Trend)'}")
            st.caption(f"• BB Width: {regime['bb_width']:.2f}% {'(High Vol)' if regime['bb_width'] > 8 else '(Low Vol)'}")
            st.caption(f"• Best Strategy: {regime['strategy']}")
            st.caption(f"• Confidence: {regime['confidence']}")
        
        # Volume Profile
        st.markdown("#### 📊 Volume Profile")
        if volume_profile:
            current_price = df_1h['Close'].iloc[-1]
            st.caption(f"• POC (High Vol Zone): ${volume_profile['poc']:,.2f}")
            st.caption(f"• Value Area: ${volume_profile['va_low']:,.2f} - ${volume_profile['va_high']:,.2f}")
            
            if volume_profile['va_low'] <= current_price <= volume_profile['va_high']:
                st.caption("✅ Price in Value Area (Fair value zone)")
            elif current_price > volume_profile['va_high']:
                st.caption("⚠️ Price above Value Area (Premium zone)")
            else:
                st.caption("⚠️ Price below Value Area (Discount zone)")
    
    st.divider()
    
    # Alert Check
    if score >= st.session_state.alert_threshold:
        st.success(f"""
        ### 🔔 ALERT TRIGGERED!
        
        Confluence Score ({score:.1f}) exceeded alert threshold ({st.session_state.alert_threshold})
        
        **In production mode, you would receive:**
        - 📱 Mobile push notification
        - 📧 Email alert
        - 💬 SMS/Telegram message
        
        ✅ This is an institutional-grade setup!
        """)
    
    # Trading Recommendation
    st.markdown("### 💡 Confluence-Based Recommendation")
    
    if score >= 80:
        st.success("""
        **🏆 STRONG CONVICTION TRADE**
        - All systems aligned (Sentiment, Regime, Technicals, Flow, Volume)
        - This is the type of setup institutions wait for
        - Position size: 100% of normal size
        - Confidence level: Very High
        """)
    elif score >= 65:
        st.info("""
        **✅ GOOD QUALITY SETUP**
        - Most systems aligned
        - Acceptable for experienced traders
        - Position size: 75-100% of normal size
        - Confidence level: High
        """)
    elif score >= 50:
        st.warning("""
        **⚠️ MIXED SIGNALS**
        - Some conflicting data between systems
        - Only for very experienced traders with tight risk management
        - Position size: 25-50% of normal size
        - Confidence level: Medium
        """)
    else:
        st.error("""
        **❌ LOW QUALITY SETUP**
        - Major conflicts between analysis layers
        - Do NOT trade - wait for better setup
        - Position size: 0% (skip this trade)
        - Confidence level: Low
        """)

def render_single_asset_view(data_sets, symbol, risk_reward, position_size):
    """Renders the full single asset analysis view"""
    
    current_price = data_sets['5m'].iloc[-1]['Close']
    price_change_24h = ((current_price - data_sets['1d'].iloc[-2]['Close']) / data_sets['1d'].iloc[-2]['Close']) * 100
    
    # Mobile mode - simplified view
    if st.session_state.mobile_mode:
        st.subheader("📱 Quick View")
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("💰 Price", f"${current_price:,.2f}", f"{price_change_24h:+.2f}%")
        with col2:
            volume_24h = data_sets['5m']['Volume'].tail(288).sum()
            st.metric("📊 Volume", f"{volume_24h:,.0f}")
        
        st.divider()
        
        # Get news and run confluence
        news_items = get_crypto_news()
        render_professional_confluence(data_sets, symbol, news_items)
        
        st.divider()
        
        # Just show key signals
        render_timeframe_scanner(data_sets, risk_reward, position_size)
        
        return  # Skip heavy charts in mobile mode
    
    # Full Desktop View
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
    
    # Professional Confluence Analysis (NEW!)
    news_items = get_crypto_news()
    render_professional_confluence(data_sets, symbol, news_items)
    
    st.divider()
    
    # --- MASTER SIGNALS (TOP PRIORITY) ---
    st.subheader("🎯 MASTER SIGNALS - All Indicators Combined")
    st.caption("Ultimate calculated signals considering ALL factors: technical indicators, volume, momentum, risk, conflicts, candles, and sentiment")
    
    # Get analysis results first for master signal calculation
    timeframes_for_analysis = ['5m', '15m', '30m', '1h', '4h']
    analysis_results_temp = {}
    
    for tf in timeframes_for_analysis:
        df = add_indicators(data_sets[tf])
        sig = generate_advanced_signal(df, tf)
        analysis_results_temp[tf] = sig

    # Prepare short-term predictions for TP/SL display
    pred_5m = predict_price_movement(add_indicators(data_sets['5m']), '5m')
    pred_1h = predict_price_movement(add_indicators(data_sets['1h']), '1h')
    pred_4h = predict_price_movement(add_indicators(data_sets['4h']), '4h')
    
    # Get conflict analysis
    conflict_analysis_temp = detect_signal_conflicts(data_sets, analysis_results_temp)
    
    # Calculate master signals
    master_signals = calculate_master_signal(data_sets, analysis_results_temp, conflict_analysis_temp)
    
    # Display in prominent cards
    sig_col1, sig_col2, sig_col3 = st.columns(3)
    
    # Scalping Master Signal
    with sig_col1:
        scalp_sig = master_signals['scalping']
        
        # Color coding
        if "STRONG BUY" in scalp_sig['signal']:
            bg_color = "#00ff00"
            text_color = "black"
            icon = "🚀"
        elif "BUY" in scalp_sig['signal']:
            bg_color = "#90EE90"
            text_color = "black"
            icon = "📈"
        elif "STRONG SELL" in scalp_sig['signal']:
            bg_color = "#ff4b4b"
            text_color = "white"
            icon = "🔻"
        elif "SELL" in scalp_sig['signal']:
            bg_color = "#FFA07A"
            text_color = "black"
            icon = "📉"
        else:
            bg_color = "#808080"
            text_color = "white"
            icon = "⏸️"
        
        st.markdown(f"""
        <div style="background-color: {bg_color}; padding: 20px; border-radius: 15px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.3);">
            <h3 style="color: {text_color}; margin: 0;">⚡ SCALPING</h3>
            <div style="font-size: 32px; margin: 10px 0;">{icon} {scalp_sig['signal']}</div>
            <div style="color: {text_color}; font-size: 18px;">Score: {scalp_sig['score']:.1f}/100</div>
            <div style="color: {text_color}; font-size: 14px;">Confidence: {scalp_sig['confidence']}</div>
            <div style="margin-top:10px; color: {text_color}; font-weight:800;">
                {f"Entry: ${pred_5m['current']:,.2f} • TP: ${pred_5m.get('tp', pred_5m.get('upper_range')):,.2f} • SL: ${pred_5m.get('sl', pred_5m.get('lower_range')):,.2f}" if pred_5m else "Entry/TP/SL: N/A"}
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        with st.expander("📋 See Why", expanded=False):
            for reason in scalp_sig['reasons']:
                st.write(reason)
    
    # Intraday Master Signal
    with sig_col2:
        intra_sig = master_signals['intraday']
        
        if "STRONG BUY" in intra_sig['signal']:
            bg_color = "#00ff00"
            text_color = "black"
            icon = "🚀"
        elif "BUY" in intra_sig['signal']:
            bg_color = "#90EE90"
            text_color = "black"
            icon = "📈"
        elif "STRONG SELL" in intra_sig['signal']:
            bg_color = "#ff4b4b"
            text_color = "white"
            icon = "🔻"
        elif "SELL" in intra_sig['signal']:
            bg_color = "#FFA07A"
            text_color = "black"
            icon = "📉"
        else:
            bg_color = "#808080"
            text_color = "white"
            icon = "⏸️"
        
        st.markdown(f"""
        <div style="background-color: {bg_color}; padding: 20px; border-radius: 15px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.3);">
            <h3 style="color: {text_color}; margin: 0;">📅 INTRADAY</h3>
            <div style="font-size: 32px; margin: 10px 0;">{icon} {intra_sig['signal']}</div>
            <div style="color: {text_color}; font-size: 18px;">Score: {intra_sig['score']:.1f}/100</div>
            <div style="color: {text_color}; font-size: 14px;">Confidence: {intra_sig['confidence']}</div>
            <div style="margin-top:10px; color: {text_color}; font-weight:800;">
                {f"Entry: ${pred_1h['current']:,.2f} • TP: ${pred_1h.get('tp', pred_1h.get('upper_range')):,.2f} • SL: ${pred_1h.get('sl', pred_1h.get('lower_range')):,.2f}" if pred_1h else "Entry/TP/SL: N/A"}
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        with st.expander("📋 See Why", expanded=False):
            for reason in intra_sig['reasons']:
                st.write(reason)
    
    # Swing Master Signal
    with sig_col3:
        swing_sig = master_signals['swing']
        
        if "STRONG BUY" in swing_sig['signal']:
            bg_color = "#00ff00"
            text_color = "black"
            icon = "🚀"
        elif "BUY" in swing_sig['signal']:
            bg_color = "#90EE90"
            text_color = "black"
            icon = "📈"
        elif "STRONG SELL" in swing_sig['signal']:
            bg_color = "#ff4b4b"
            text_color = "white"
            icon = "🔻"
        elif "SELL" in swing_sig['signal']:
            bg_color = "#FFA07A"
            text_color = "black"
            icon = "📉"
        else:
            bg_color = "#808080"
            text_color = "white"
            icon = "⏸️"
        
        st.markdown(f"""
        <div style="background-color: {bg_color}; padding: 20px; border-radius: 15px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.3);">
            <h3 style="color: {text_color}; margin: 0;">🌊 SWING</h3>
            <div style="font-size: 32px; margin: 10px 0;">{icon} {swing_sig['signal']}</div>
            <div style="color: {text_color}; font-size: 18px;">Score: {swing_sig['score']:.1f}/100</div>
            <div style="color: {text_color}; font-size: 14px;">Confidence: {swing_sig['confidence']}</div>
            <div style="margin-top:10px; color: {text_color}; font-weight:800;">
                {f"Entry: ${pred_4h['current']:,.2f} • TP: ${pred_4h.get('tp', pred_4h.get('upper_range')):,.2f} • SL: ${pred_4h.get('sl', pred_4h.get('lower_range')):,.2f}" if pred_4h else "Entry/TP/SL: N/A"}
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        with st.expander("📋 See Why", expanded=False):
            for reason in swing_sig['reasons']:
                st.write(reason)
    
    # Quick interpretation guide
    # Live Strict Master Signal (user-selectable TF)
    strict_tf = st.selectbox("Strict Master Signal Timeframe:", ['5m','15m','30m','1h','4h'], index=3)
    strict_signal = generate_master_strict_signal(add_indicators(data_sets[strict_tf]), strict_tf)
    if strict_signal and strict_signal.get('signal') != 'NONE':
        ss = strict_signal
        color = '#00ff00' if ss['signal']=='UP' else ('#ff4b4b' if ss['signal']=='DOWN' else '#808080')
        icon = '🚀' if ss['signal']=='UP' else ('🔻' if ss['signal']=='DOWN' else '⏸️')
        st.markdown(f"""
        <div style="background-color: {color}; padding: 18px; border-radius: 12px; text-align:center;">
            <h3 style="margin:0">{icon} Strict Master ({strict_tf})</h3>
            <div style="font-size:22px; font-weight:700;">{ss['signal']} — Conf: {ss['confidence']:.2f}</div>
            <div style="margin-top:8px;">Entry: ${ss['entry']:.4f} • TP: ${ss['tp']:.4f} • SL: ${ss['sl']:.4f}</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("<div style='padding:12px; border-radius:8px; background:#f0f0f0; text-align:center;'>No strict master signal right now.</div>", unsafe_allow_html=True)

    st.info("""
    💡 **How to Read Master Signals:**
    - **STRONG BUY/SELL (75%+):** All factors aligned - highest conviction trade
    - **BUY/SELL (60-75%):** Most factors aligned - good trade opportunity
    - **NEUTRAL (<60%):** Mixed signals - wait for clarity
    
    Click "📋 See Why" to understand the exact reasoning behind each signal.
    """)
    
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
                <div style="display:flex; gap:10px; margin-top:12px;">
                    <div class="key-metric" style="flex:1">TP: ${pred_1h.get('tp', pred_1h.get('upper_range')):,.2f}</div>
                    <div class="key-metric" style="flex:1">SL: ${pred_1h.get('sl', pred_1h.get('lower_range')):,.2f}</div>
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
    """Renders compact analysis for multi-asset comparison (Master Signals + Scanner + Strategies)"""
    
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
    
    # --- MASTER SIGNALS (Compact Version) ---
    st.markdown("### 🎯 Master Signals")
    
    # Get analysis for master signals
    timeframes = ['5m', '15m', '30m', '1h', '4h']
    analysis_results_temp = {}
    
    for tf in timeframes:
        df = add_indicators(data_sets[tf])
        sig = generate_advanced_signal(df, tf)
        analysis_results_temp[tf] = sig
    
    conflict_analysis_temp = detect_signal_conflicts(data_sets, analysis_results_temp)
    master_signals = calculate_master_signal(data_sets, analysis_results_temp, conflict_analysis_temp)
    
    # Compact display
    m_col1, m_col2, m_col3 = st.columns(3)
    
    with m_col1:
        scalp_sig = master_signals['scalping']
        color = "green" if "BUY" in scalp_sig['signal'] else "red" if "SELL" in scalp_sig['signal'] else "gray"
        st.markdown(f"**⚡ Scalp:** <span style='color:{color}'>{scalp_sig['signal']}</span>", unsafe_allow_html=True)
        st.caption(f"{scalp_sig['score']:.0f}/100")
    
    with m_col2:
        intra_sig = master_signals['intraday']
        color = "green" if "BUY" in intra_sig['signal'] else "red" if "SELL" in intra_sig['signal'] else "gray"
        st.markdown(f"**📅 Intra:** <span style='color:{color}'>{intra_sig['signal']}</span>", unsafe_allow_html=True)
        st.caption(f"{intra_sig['score']:.0f}/100")
    
    with m_col3:
        swing_sig = master_signals['swing']
        color = "green" if "BUY" in swing_sig['signal'] else "red" if "SELL" in swing_sig['signal'] else "gray"
        st.markdown(f"**🌊 Swing:** <span style='color:{color}'>{swing_sig['signal']}</span>", unsafe_allow_html=True)
        st.caption(f"{swing_sig['score']:.0f}/100")
    
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
    """Renders the advanced technical chart with volume profile"""
    st.subheader("📈 Advanced Price Chart (1H) + Volume Profile")
    
    chart_df = add_indicators(data_sets['1h'])
    volume_profile = calculate_volume_profile(chart_df)
    
    from plotly.subplots import make_subplots
    
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.6, 0.2, 0.2],
        subplot_titles=('Price Action + Volume Profile', 'RSI', 'MACD')
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
    
    # Volume Profile (NEW!)
    if volume_profile:
        # Add POC line
        fig.add_hline(
            y=volume_profile['poc'],
            line_dash="solid",
            line_color="cyan",
            line_width=2,
            annotation_text="POC",
            row=1, col=1
        )
        
        # Add Value Area
        fig.add_hrect(
            y0=volume_profile['va_low'],
            y1=volume_profile['va_high'],
            fillcolor="rgba(0, 255, 255, 0.1)",
            line_width=0,
            annotation_text="Value Area",
            row=1, col=1
        )
    
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

# Mobile Mode Toggle
st.session_state.mobile_mode = st.sidebar.checkbox("📱 Mobile Mode (Simplified)", value=st.session_state.mobile_mode)

st.sidebar.divider()

# Alert Settings
st.sidebar.subheader("🔔 Alert Settings")
st.session_state.alert_threshold = st.sidebar.slider(
    "Confluence Alert Threshold", 
    50, 100, st.session_state.alert_threshold,
    help="Get notified when Sentiment + Technical confluence exceeds this %"
)

# Finnhub API Key (for macro event blackout)
# Load silently from Streamlit secrets if available. Do NOT expose keys in UI.
st.session_state['finnhub_api_key'] = st.secrets.get('finnhub_api_key', st.session_state.get('finnhub_api_key', None))

if st.sidebar.button("Test Alert 🔔", use_container_width=True):
    st.sidebar.success("✅ Alert system active! (In production, this would send notifications)")

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
                # Update the single symbol text_input widget state so it reflects the change
                try:
                    st.session_state['single_symbol_input'] = ticker
                except Exception:
                    pass
                # rely on session_state update; avoid forced rerun
            else:
                # In multi-asset mode, set to symbol_1 and update widget
                st.session_state.symbol_1 = ticker
                try:
                    st.session_state['symbol_1_input'] = ticker
                except Exception:
                    pass
                # rely on session_state update; avoid forced rerun

st.sidebar.divider()

# --- Full Asset Dropdown with Search ---
st.sidebar.subheader("🔎 All Assets (Searchable)")
assets_catalog = {
    'Bitcoin': 'BTC-USD', 'Gold': 'GC=F', 'Silver': 'SI=F', 'DXY': 'DX-Y.NYB', 'XRP': 'XRP-USD',
    'Ethereum': 'ETH-USD', 'S&P500': '^GSPC', 'Crude Oil': 'CL=F', 'Nasdaq': '^IXIC', 'TSLA': 'TSLA',
    'AAPL': 'AAPL', 'MSFT': 'MSFT', 'AMZN': 'AMZN', 'NVDA': 'NVDA'
}

search_filter = st.sidebar.text_input("Filter assets", value="")
options = [f"{name} ({ticker})" for name, ticker in assets_catalog.items()]
if search_filter:
    options = [o for o in options if search_filter.lower() in o.lower()]

selected_asset = st.sidebar.selectbox("Choose asset", options, key='asset_dropdown')
if selected_asset:
    # parse ticker
    m = re.search(r"\(([^)]+)\)", selected_asset)
    if m:
        sel_ticker = m.group(1)
        # Only apply change when selection actually changed to avoid rerun loops
        last = st.session_state.get('asset_dropdown_last')
        if last != selected_asset:
            st.session_state['asset_dropdown_last'] = selected_asset
            if view_mode == "Single Asset":
                st.session_state.current_symbol = sel_ticker
                try:
                    st.session_state['single_symbol_input'] = sel_ticker
                except Exception:
                    pass
                # rely on session_state update; avoid forced rerun
            else:
                st.session_state.symbol_1 = sel_ticker
                try:
                    st.session_state['symbol_1_input'] = sel_ticker
                except Exception:
                    pass
                st.rerun()

# Risk settings
st.sidebar.subheader("Risk Management")
risk_reward = st.sidebar.slider("Risk:Reward Ratio", 1.0, 3.0, 1.5, 0.5)
position_size = st.sidebar.number_input("Position Size ($)", min_value=100, value=1000, step=100)

st.sidebar.info(f"Last Refresh: {st.session_state.last_refresh.strftime('%H:%M:%S')}")

# --- MAIN DASHBOARD ---
st.title(f"📊 Ultimate AI Trading Dashboard")

# Persistent restore button near the title for cases where the top-left toggle is hidden
if not st.session_state.get('sidebar_visible', True):
    col_restore = st.columns([1,5])[0]
    with col_restore:
        if st.button('Show Sidebar', key='show_sidebar_top'):
            st.session_state.sidebar_visible = True
            st.experimental_rerun()
        # Provide a direct link that sets the query param to restore sidebar
        st.markdown("[Restore sidebar](?show_sidebar=1) — or [Restore and show toolbar](?show_sidebar=1&show_toolbar=1)")

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
