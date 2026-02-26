"""
╔══════════════════════════════════════════════════════════════════════════╗
║         INSTITUTIONAL AI TRADING SIGNAL PLATFORM — PRO EDITION          ║
║         Powered by CCXT (Binance) | Multi-Asset | Multi-Timeframe       ║
╚══════════════════════════════════════════════════════════════════════════╝
SIGNALS ON TOP · 15m SCALPING ENGINE · ADVANCED CONFLUENCE SCORING
Supports: Crypto Spot + Futures | Gold (XAU/USDT) | Silver (XAG/USDT)
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import time
import warnings
warnings.filterwarnings('ignore')

# ─────────────────────────────────────────────
# CCXT IMPORT (Binance API)
# ─────────────────────────────────────────────
try:
    import ccxt
    CCXT_AVAILABLE = True
except ImportError:
    CCXT_AVAILABLE = False

# ─────────────────────────────────────────────
# FEEDPARSER (optional)
# ─────────────────────────────────────────────
try:
    import feedparser
    FEEDPARSER_AVAILABLE = True
except ImportError:
    FEEDPARSER_AVAILABLE = False

# ══════════════════════════════════════════════
# PAGE CONFIG
# ══════════════════════════════════════════════
st.set_page_config(
    page_title="Institutional AI Trader",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ══════════════════════════════════════════════
# CSS STYLING
# ══════════════════════════════════════════════
st.markdown("""
<style>
  /* Dark base */
  body, .stApp { background-color: #0a0e17; color: #e0e0e0; }

  /* Ticker bar */
  .ticker-wrap {
    background: linear-gradient(90deg,#0d1117,#111827);
    border: 1px solid #1e2a3a;
    border-radius: 10px; padding: 14px 18px; margin-bottom: 6px;
  }
  .ticker-name { font-size: 11px; color: #6b7a8d; letter-spacing: 1px; }
  .ticker-price { font-size: 20px; font-weight: 700; color: #f0f0f0; }
  .ticker-up   { color: #00e676; font-weight: 600; }
  .ticker-dn   { color: #ff5252; font-weight: 600; }

  /* Signal cards */
  .sig-card {
    border-radius: 14px; padding: 22px 18px; text-align: center;
    box-shadow: 0 6px 20px rgba(0,0,0,0.5); margin-bottom: 4px;
  }
  .sig-label  { font-size: 13px; font-weight: 600; letter-spacing: 2px; opacity:.8; }
  .sig-main   { font-size: 28px; font-weight: 800; margin: 8px 0; }
  .sig-score  { font-size: 15px; opacity: .85; }
  .sig-conf   { font-size: 12px; opacity: .65; margin-top: 4px; }

  .card-strong-buy  { background: linear-gradient(135deg,#00c853,#1b5e20); }
  .card-buy         { background: linear-gradient(135deg,#43a047,#1b5e20); }
  .card-neutral     { background: linear-gradient(135deg,#37474f,#263238); }
  .card-sell        { background: linear-gradient(135deg,#e53935,#7f0000); }
  .card-strong-sell { background: linear-gradient(135deg,#b71c1c,#4a0000); }

  /* Conflict / warning boxes */
  .conflict-critical {
    background: rgba(183,28,28,.25); border-left: 4px solid #b71c1c;
    border-radius: 8px; padding: 14px; margin: 8px 0;
  }
  .conflict-high {
    background: rgba(230,81,0,.2); border-left: 4px solid #e65100;
    border-radius: 8px; padding: 14px; margin: 8px 0;
  }
  .conflict-medium {
    background: rgba(249,168,37,.15); border-left: 4px solid #f9a825;
    border-radius: 8px; padding: 14px; margin: 8px 0;
  }

  /* News item */
  .news-item {
    background: #111827; border-left: 3px solid #fca311;
    border-radius: 8px; padding: 12px; margin: 6px 0;
  }

  /* Prediction box */
  .pred-box {
    background: linear-gradient(135deg,#1a237e,#4a148c);
    border-radius: 12px; padding: 20px; color: #fff; margin: 10px 0;
  }

  /* Metric override */
  [data-testid="stMetricValue"] { color: #f0f0f0 !important; }

  /* Divider */
  hr { border-color: #1e2a3a !important; }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════
# SESSION STATE
# ══════════════════════════════════════════════
_defaults = {
    'last_refresh': datetime.now(),
    'auto_refresh': True,
    'current_symbol': 'BTC/USDT',
    'view_mode': 'Single Asset',
    'symbol_1': 'BTC/USDT',
    'symbol_2': 'XAU/USDT',
    'show_backtest': False,
    'mobile_mode': False,
    'alert_threshold': 85,
    'sentiment_cache': {},
    'exchange_type': 'spot',        # 'spot' or 'futures'
    'api_key': '',
    'api_secret': '',
}
for k, v in _defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ══════════════════════════════════════════════
# CCXT / BINANCE DATA ENGINE
# ══════════════════════════════════════════════

@st.cache_resource
def get_exchange(api_key='', api_secret='', exchange_type='spot'):
    """Returns a configured Binance exchange object (spot or futures)."""
    if not CCXT_AVAILABLE:
        return None
    try:
        if exchange_type == 'futures':
            ex = ccxt.binanceusdm({
                'apiKey': api_key or '',
                'secret': api_secret or '',
                'enableRateLimit': True,
                'options': {'defaultType': 'future'},
            })
        else:
            ex = ccxt.binance({
                'apiKey': api_key or '',
                'secret': api_secret or '',
                'enableRateLimit': True,
            })
        ex.load_markets()
        return ex
    except Exception as e:
        st.warning(f"Exchange init failed: {e}")
        return None


def _is_futures_symbol(symbol: str) -> bool:
    """Check if symbol needs futures endpoint."""
    futures_symbols = {'XAU/USDT', 'XAG/USDT', 'XAU/USDT:USDT', 'XAG/USDT:USDT'}
    return symbol in futures_symbols or ':USDT' in symbol


def fetch_ohlcv(symbol: str, timeframe: str, limit: int = 500) -> pd.DataFrame:
    """
    Fetch OHLCV from Binance via CCXT.
    Automatically routes to futures exchange for metals (XAU, XAG).
    Falls back to synthetic demo data if CCXT unavailable.
    """
    if not CCXT_AVAILABLE:
        return _synthetic_ohlcv(symbol, timeframe, limit)

    try:
        use_futures = _is_futures_symbol(symbol)
        ex = get_exchange(
            st.session_state.api_key,
            st.session_state.api_secret,
            'futures' if use_futures else 'spot'
        )
        if ex is None:
            return _synthetic_ohlcv(symbol, timeframe, limit)

        # Normalise symbol for futures (e.g. XAU/USDT → XAU/USDT:USDT)
        fetch_sym = symbol
        if use_futures and ':USDT' not in symbol:
            fetch_sym = symbol + ':USDT'

        raw = ex.fetch_ohlcv(fetch_sym, timeframe=timeframe, limit=limit)
        if not raw:
            return _synthetic_ohlcv(symbol, timeframe, limit)

        df = pd.DataFrame(raw, columns=['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        df = df.astype(float)
        return df

    except Exception as e:
        st.warning(f"⚠️ Data fetch error for {symbol} ({timeframe}): {e}. Using demo data.")
        return _synthetic_ohlcv(symbol, timeframe, limit)


def _synthetic_ohlcv(symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
    """Generates realistic synthetic OHLCV data for demo / fallback."""
    tf_minutes = {'1m': 1, '3m': 3, '5m': 5, '15m': 15, '30m': 30,
                  '1h': 60, '2h': 120, '4h': 240, '1d': 1440}
    mins = tf_minutes.get(timeframe, 60)

    # Base prices for common symbols
    bases = {
        'BTC/USDT': 65000, 'ETH/USDT': 3200, 'BNB/USDT': 580,
        'SOL/USDT': 145, 'XRP/USDT': 0.55, 'ADA/USDT': 0.45,
        'XAU/USDT': 2320, 'XAG/USDT': 27.5,
        'DOGE/USDT': 0.13, 'AVAX/USDT': 35,
    }
    base = bases.get(symbol, 100)
    np.random.seed(abs(hash(symbol)) % 9999)

    end = datetime.now()
    start = end - timedelta(minutes=mins * limit)
    idx = pd.date_range(start=start, periods=limit, freq=f'{mins}min')

    price = base
    prices = []
    for _ in range(limit):
        chg = np.random.normal(0, base * 0.002)
        price = max(price + chg, base * 0.5)
        prices.append(price)

    prices = np.array(prices)
    noise = base * 0.001
    df = pd.DataFrame({
        'Open':   prices + np.random.uniform(-noise, noise, limit),
        'High':   prices + np.abs(np.random.normal(0, noise * 2, limit)),
        'Low':    prices - np.abs(np.random.normal(0, noise * 2, limit)),
        'Close':  prices,
        'Volume': np.random.uniform(1e6, 1e8, limit),
    }, index=idx)
    return df


def get_ticker_price(symbol: str) -> dict:
    """Fetches latest ticker data for the market feed."""
    if not CCXT_AVAILABLE:
        bases = {
            'BTC/USDT': 65000, 'ETH/USDT': 3200, 'BNB/USDT': 580,
            'SOL/USDT': 145, 'XRP/USDT': 0.55, 'XAU/USDT': 2320, 'XAG/USDT': 27.5,
        }
        price = bases.get(symbol, 100)
        return {'price': price, 'change': np.random.uniform(-2, 2), 'volume': 1e9}

    try:
        use_futures = _is_futures_symbol(symbol)
        ex = get_exchange(
            st.session_state.api_key,
            st.session_state.api_secret,
            'futures' if use_futures else 'spot'
        )
        fetch_sym = symbol + ':USDT' if use_futures and ':USDT' not in symbol else symbol
        ticker = ex.fetch_ticker(fetch_sym)
        return {
            'price': ticker.get('last', 0),
            'change': ticker.get('percentage', 0) or 0,
            'volume': ticker.get('quoteVolume', 0) or 0,
        }
    except:
        return {'price': 0, 'change': 0, 'volume': 0}


def get_all_datasets(symbol: str) -> dict | None:
    """Fetches all required timeframes for a symbol."""
    try:
        datasets = {
            '1m':  fetch_ohlcv(symbol, '1m',  limit=300),
            '3m':  fetch_ohlcv(symbol, '3m',  limit=300),
            '15m': fetch_ohlcv(symbol, '15m', limit=300),
            '30m': fetch_ohlcv(symbol, '30m', limit=300),
            '1h':  fetch_ohlcv(symbol, '1h',  limit=500),
            '4h':  fetch_ohlcv(symbol, '4h',  limit=300),
            '1d':  fetch_ohlcv(symbol, '1d',  limit=200),
        }
        # Validate
        if datasets['15m'].empty or datasets['1h'].empty:
            return None
        return datasets
    except Exception as e:
        st.error(f"Dataset error: {e}")
        return None

# ══════════════════════════════════════════════
# TECHNICAL INDICATORS ENGINE
# ══════════════════════════════════════════════

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Adds a full suite of professional technical indicators."""
    df = df.copy()
    if len(df) < 50:
        return df

    c = df['Close']
    h = df['High']
    l = df['Low']
    v = df['Volume']

    # ── Trend EMAs ──────────────────────────────
    for span in [5, 8, 9, 13, 21, 34, 50, 89, 200]:
        df[f'EMA{span}'] = c.ewm(span=span, adjust=False).mean()

    # ── Bollinger Bands ─────────────────────────
    df['BB_Middle'] = c.rolling(20).mean()
    bb_std = c.rolling(20).std()
    df['BB_Upper'] = df['BB_Middle'] + 2 * bb_std
    df['BB_Lower'] = df['BB_Middle'] - 2 * bb_std
    df['BB_Width']  = (df['BB_Upper'] - df['BB_Lower']) / df['BB_Middle']
    df['BB_Pct']    = (c - df['BB_Lower']) / (df['BB_Upper'] - df['BB_Lower'] + 1e-9)

    # ── Keltner Channel ─────────────────────────
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    df['ATR']  = tr.rolling(14).mean()
    df['ATR21']= tr.rolling(21).mean()
    kc_mid = c.ewm(span=20, adjust=False).mean()
    df['KC_Upper'] = kc_mid + 1.5 * df['ATR']
    df['KC_Lower'] = kc_mid - 1.5 * df['ATR']

    # ── Squeeze (Bollinger vs Keltner) ──────────
    df['Squeeze'] = (df['BB_Upper'] < df['KC_Upper']) & (df['BB_Lower'] > df['KC_Lower'])

    # ── RSI ─────────────────────────────────────
    delta = c.diff()
    gain  = delta.where(delta > 0, 0).rolling(14).mean()
    loss  = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['RSI'] = 100 - 100 / (1 + gain / (loss + 1e-9))
    df['RSI_EMA'] = df['RSI'].ewm(span=9, adjust=False).mean()  # RSI signal line

    # ── Stochastic RSI ──────────────────────────
    rsi_min = df['RSI'].rolling(14).min()
    rsi_max = df['RSI'].rolling(14).max()
    df['StochRSI_K'] = 100 * (df['RSI'] - rsi_min) / (rsi_max - rsi_min + 1e-9)
    df['StochRSI_D'] = df['StochRSI_K'].rolling(3).mean()

    # ── Stochastic Oscillator ───────────────────
    low14  = l.rolling(14).min()
    high14 = h.rolling(14).max()
    df['Stoch_K'] = 100 * (c - low14) / (high14 - low14 + 1e-9)
    df['Stoch_D'] = df['Stoch_K'].rolling(3).mean()

    # ── MACD ────────────────────────────────────
    ema12 = c.ewm(span=12, adjust=False).mean()
    ema26 = c.ewm(span=26, adjust=False).mean()
    df['MACD']      = ema12 - ema26
    df['MACD_Sig']  = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Sig']

    # ── ADX / DI ────────────────────────────────
    plus_dm  = h.diff().clip(lower=0)
    minus_dm = (-l.diff()).clip(lower=0)
    plus_dm[plus_dm < minus_dm]   = 0
    minus_dm[minus_dm < plus_dm]  = 0
    atr14    = tr.rolling(14).mean()
    plus_di  = 100 * plus_dm.rolling(14).mean()  / (atr14 + 1e-9)
    minus_di = 100 * minus_dm.rolling(14).mean() / (atr14 + 1e-9)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di + 1e-9)
    df['ADX']      = dx.rolling(14).mean()
    df['Plus_DI']  = plus_di
    df['Minus_DI'] = minus_di

    # ── CCI (Commodity Channel Index) ───────────
    typical = (h + l + c) / 3
    df['CCI'] = (typical - typical.rolling(20).mean()) / (0.015 * typical.rolling(20).std() + 1e-9)

    # ── Williams %R ─────────────────────────────
    df['Williams_R'] = -100 * (h.rolling(14).max() - c) / (h.rolling(14).max() - l.rolling(14).min() + 1e-9)

    # ── OBV & Volume ────────────────────────────
    df['OBV']        = (np.sign(c.diff()) * v).fillna(0).cumsum()
    df['OBV_EMA']    = df['OBV'].ewm(span=20, adjust=False).mean()
    df['Volume_MA']  = v.rolling(20).mean()
    df['Volume_Ratio'] = v / (df['Volume_MA'] + 1e-9)

    # ── VWAP (Rolling daily) ────────────────────
    df['VWAP'] = (typical * v).rolling(20).sum() / (v.rolling(20).sum() + 1e-9)

    # ── Ichimoku Cloud ──────────────────────────
    tenkan  = (h.rolling(9).max()  + l.rolling(9).min())  / 2
    kijun   = (h.rolling(26).max() + l.rolling(26).min()) / 2
    df['Ichimoku_Tenkan']  = tenkan
    df['Ichimoku_Kijun']   = kijun
    df['Ichimoku_SpanA']   = ((tenkan + kijun) / 2).shift(26)
    df['Ichimoku_SpanB']   = ((h.rolling(52).max() + l.rolling(52).min()) / 2).shift(26)
    df['Ichimoku_Chikou']  = c.shift(-26)

    # ── Pivot Points (Classic) ──────────────────
    ph = h.shift(1); pl = l.shift(1); pc = c.shift(1)
    df['Pivot']  = (ph + pl + pc) / 3
    df['R1']     = 2 * df['Pivot'] - pl
    df['S1']     = 2 * df['Pivot'] - ph
    df['R2']     = df['Pivot'] + (ph - pl)
    df['S2']     = df['Pivot'] - (ph - pl)
    df['R3']     = ph + 2 * (df['Pivot'] - pl)
    df['S3']     = pl - 2 * (ph - df['Pivot'])

    # ── Supertrend ─────────────────────────────
    hl2 = (h + l) / 2
    atr_st = df['ATR'].copy()
    upper_band = hl2 + 3 * atr_st
    lower_band = hl2 - 3 * atr_st
    supertrend = pd.Series(np.nan, index=df.index)
    direction  = pd.Series(1, index=df.index)
    for i in range(1, len(df)):
        prev_close = c.iloc[i - 1]
        curr_close = c.iloc[i]
        ub = upper_band.iloc[i]
        lb = lower_band.iloc[i]
        if direction.iloc[i - 1] == 1:
            supertrend.iloc[i] = lb if curr_close > lb else ub
            direction.iloc[i]  = 1  if curr_close > lb else -1
        else:
            supertrend.iloc[i] = ub if curr_close < ub else lb
            direction.iloc[i]  = -1 if curr_close < ub else 1
    df['Supertrend']     = supertrend
    df['Supertrend_Dir'] = direction

    # ── Rate of Change ──────────────────────────
    df['ROC']  = c.pct_change(10) * 100
    df['ROC3'] = c.pct_change(3)  * 100

    # ── Money Flow Index ────────────────────────
    tp_v = typical * v
    pos_flow = tp_v.where(typical > typical.shift(1), 0).rolling(14).sum()
    neg_flow = tp_v.where(typical < typical.shift(1), 0).rolling(14).sum()
    df['MFI'] = 100 - 100 / (1 + pos_flow / (neg_flow + 1e-9))

    # ── Elder Ray ────────────────────────────────
    ema13 = c.ewm(span=13, adjust=False).mean()
    df['Bull_Power'] = h - ema13
    df['Bear_Power'] = l - ema13

    return df

# ══════════════════════════════════════════════
# PATTERN RECOGNITION ENGINE
# ══════════════════════════════════════════════

def identify_candle_patterns(df: pd.DataFrame) -> list[dict]:
    """
    Detects 20+ candlestick patterns.
    Returns list of detected patterns with bullish/bearish classification.
    """
    patterns = []
    if len(df) < 5:
        return patterns

    r0 = df.iloc[-1]
    r1 = df.iloc[-2]
    r2 = df.iloc[-3]
    r3 = df.iloc[-4] if len(df) > 4 else r2
    r4 = df.iloc[-5] if len(df) > 5 else r3

    o0, h0, l0, c0 = r0['Open'], r0['High'], r0['Low'], r0['Close']
    o1, h1, l1, c1 = r1['Open'], r1['High'], r1['Low'], r1['Close']
    o2, h2, l2, c2 = r2['Open'], r2['High'], r2['Low'], r2['Close']

    body0 = abs(c0 - o0); wick_up0 = h0 - max(o0,c0); wick_dn0 = min(o0,c0) - l0
    body1 = abs(c1 - o1); wick_up1 = h1 - max(o1,c1); wick_dn1 = min(o1,c1) - l1
    rng0  = h0 - l0 + 1e-9

    bull = c0 > o0; bear = c0 < o0
    prev_bull = c1 > o1; prev_bear = c1 < o1

    # ── 1-Candle Patterns ─────────────────────
    if wick_dn0 > body0 * 2 and wick_up0 < body0 * 0.5:
        patterns.append({'name': '🔨 Hammer', 'bias': 'bullish', 'strength': 'moderate'})

    if wick_up0 > body0 * 2 and wick_dn0 < body0 * 0.5:
        patterns.append({'name': '⭐ Shooting Star', 'bias': 'bearish', 'strength': 'moderate'})

    if wick_dn0 > body0 * 2 and bear:
        patterns.append({'name': '🪝 Hanging Man', 'bias': 'bearish', 'strength': 'moderate'})

    if wick_up0 > body0 * 2 and bull:
        patterns.append({'name': '💉 Inverted Hammer', 'bias': 'bullish', 'strength': 'moderate'})

    if body0 < rng0 * 0.08:
        patterns.append({'name': '➕ Doji', 'bias': 'neutral', 'strength': 'weak'})

    if wick_up0 > rng0 * 0.45 and wick_dn0 > rng0 * 0.45 and body0 < rng0 * 0.1:
        patterns.append({'name': '✚ Long-Legged Doji', 'bias': 'neutral', 'strength': 'moderate'})

    if body0 > rng0 * 0.8 and bull:
        patterns.append({'name': '💚 Marubozu Bullish', 'bias': 'bullish', 'strength': 'strong'})

    if body0 > rng0 * 0.8 and bear:
        patterns.append({'name': '🔴 Marubozu Bearish', 'bias': 'bearish', 'strength': 'strong'})

    # ── 2-Candle Patterns ─────────────────────
    if (bull and prev_bear and o0 <= c1 and c0 > o1 and body0 > body1):
        patterns.append({'name': '🟢 Bullish Engulfing', 'bias': 'bullish', 'strength': 'strong'})

    if (bear and prev_bull and o0 >= c1 and c0 < o1 and body0 > body1):
        patterns.append({'name': '🔴 Bearish Engulfing', 'bias': 'bearish', 'strength': 'strong'})

    if (prev_bear and bull and o0 > l1 and o0 < c1 and c0 > l1 and c0 < o1):
        patterns.append({'name': '🌸 Bullish Harami', 'bias': 'bullish', 'strength': 'moderate'})

    if (prev_bull and bear and o0 < h1 and o0 > c1 and c0 < h1 and c0 > o1):
        patterns.append({'name': '🌼 Bearish Harami', 'bias': 'bearish', 'strength': 'moderate'})

    if (prev_bear and bull and c0 > (o1 + c1) / 2):
        patterns.append({'name': '🔵 Piercing Line', 'bias': 'bullish', 'strength': 'moderate'})

    if (prev_bull and bear and c0 < (o1 + c1) / 2):
        patterns.append({'name': '☁️ Dark Cloud Cover', 'bias': 'bearish', 'strength': 'moderate'})

    if (prev_bull and abs(body0) < body1 * 0.3 and h0 < h1 and l0 > l1):
        patterns.append({'name': '⚡ Bearish Harami Cross', 'bias': 'bearish', 'strength': 'moderate'})

    # ── 3-Candle Patterns ─────────────────────
    if (c2 < o2 and abs(c1 - o1) < abs(c2 - o2) * 0.3 and
            bull and c0 > (o2 + c2) / 2):
        patterns.append({'name': '🌅 Morning Star', 'bias': 'bullish', 'strength': 'very strong'})

    if (c2 > o2 and abs(c1 - o1) < abs(c2 - o2) * 0.3 and
            bear and c0 < (o2 + c2) / 2):
        patterns.append({'name': '🌆 Evening Star', 'bias': 'bearish', 'strength': 'very strong'})

    if bull and c1 > o1 and c2 > o2:
        if c0 > c1 > c2 and o0 > o1 > o2:
            patterns.append({'name': '🚀 Three White Soldiers', 'bias': 'bullish', 'strength': 'very strong'})

    if bear and c1 < o1 and c2 < o2:
        if c0 < c1 < c2 and o0 < o1 < o2:
            patterns.append({'name': '💀 Three Black Crows', 'bias': 'bearish', 'strength': 'very strong'})

    # ── 4+ Candle Patterns ────────────────────
    # Three Inside Up
    if (c2 < o2 and bull and
            o0 > o1 and c0 > o1 and c0 > c2):
        patterns.append({'name': '🌀 Three Inside Up', 'bias': 'bullish', 'strength': 'strong'})

    if not patterns:
        patterns.append({'name': '📊 No Pattern', 'bias': 'neutral', 'strength': 'n/a'})

    return patterns

# ══════════════════════════════════════════════
# SIGNAL GENERATION ENGINE
# ══════════════════════════════════════════════

def generate_signal(df: pd.DataFrame, timeframe: str) -> dict | None:
    """Generates a comprehensive trading signal with score."""
    if len(df) < 200:
        return None
    df = add_indicators(df)
    curr = df.iloc[-1]
    prev = df.iloc[-2]
    prev2 = df.iloc[-3]

    score = 0
    max_score = 0
    signals = []

    # 1. EMA 200 Trend Filter (weight 3)
    max_score += 3
    if curr['Close'] > curr['EMA200']:
        score += 3
        signals.append("✅ Above EMA200 (Bull Market)")
    else:
        score -= 3
        signals.append("⛔ Below EMA200 (Bear Market)")

    # 2. Supertrend (weight 3)
    max_score += 3
    if 'Supertrend_Dir' in curr and not pd.isna(curr['Supertrend_Dir']):
        if curr['Supertrend_Dir'] == 1:
            score += 3
            signals.append("✅ Supertrend Bullish")
        else:
            score -= 3
            signals.append("⛔ Supertrend Bearish")

    # 3. EMA Stack (weight 2)
    max_score += 2
    if curr['EMA9'] > curr['EMA21'] > curr['EMA50']:
        score += 2
        signals.append("✅ Bullish EMA Stack (9>21>50)")
    elif curr['EMA9'] < curr['EMA21'] < curr['EMA50']:
        score -= 2
        signals.append("⛔ Bearish EMA Stack")

    # 4. Ichimoku (weight 2)
    max_score += 2
    if 'Ichimoku_SpanA' in curr and not pd.isna(curr.get('Ichimoku_SpanA', np.nan)):
        cloud_top = max(curr['Ichimoku_SpanA'], curr['Ichimoku_SpanB'])
        cloud_bot = min(curr['Ichimoku_SpanA'], curr['Ichimoku_SpanB'])
        if curr['Close'] > cloud_top:
            score += 2
            signals.append("✅ Price above Ichimoku Cloud")
        elif curr['Close'] < cloud_bot:
            score -= 2
            signals.append("⛔ Price below Ichimoku Cloud")
        if curr['Ichimoku_Tenkan'] > curr['Ichimoku_Kijun']:
            score += 1
            signals.append("✅ TK Cross Bullish")
        else:
            score -= 1
            signals.append("⛔ TK Cross Bearish")
        max_score += 1

    # 5. RSI (weight 2)
    max_score += 2
    rsi = curr['RSI']
    if rsi > 70:
        score -= 2; signals.append(f"⚠️ RSI Overbought ({rsi:.1f})")
    elif rsi > 55:
        score += 2; signals.append(f"✅ RSI Bullish ({rsi:.1f})")
    elif rsi > 45:
        score += 1; signals.append(f"🟡 RSI Neutral ({rsi:.1f})")
    elif rsi > 30:
        score -= 1; signals.append(f"⛔ RSI Bearish ({rsi:.1f})")
    else:
        score += 1; signals.append(f"💎 RSI Oversold ({rsi:.1f}) – Reversal Zone")

    # 6. Stochastic RSI (weight 2)
    max_score += 2
    sk = curr['StochRSI_K']
    sd = curr['StochRSI_D']
    if sk > 80:
        signals.append(f"⚠️ StochRSI Overbought ({sk:.0f})")
    elif sk < 20:
        score += 2; signals.append(f"💎 StochRSI Oversold ({sk:.0f})")
    elif sk > sd:
        score += 2; signals.append(f"✅ StochRSI Bullish ({sk:.0f})")
    else:
        score -= 1; signals.append(f"⛔ StochRSI Bearish ({sk:.0f})")

    # 7. MACD (weight 2)
    max_score += 2
    if curr['MACD'] > curr['MACD_Sig'] and prev['MACD'] <= prev['MACD_Sig']:
        score += 2; signals.append("🚀 MACD Bullish Crossover (FRESH)")
    elif curr['MACD'] > curr['MACD_Sig']:
        score += 1; signals.append("✅ MACD Above Signal")
    elif curr['MACD'] < curr['MACD_Sig'] and prev['MACD'] >= prev['MACD_Sig']:
        score -= 2; signals.append("🔻 MACD Bearish Crossover (FRESH)")
    else:
        score -= 1; signals.append("⛔ MACD Below Signal")

    # MACD Histogram momentum
    if curr['MACD_Hist'] > prev['MACD_Hist'] > prev2['MACD_Hist']:
        score += 1; signals.append("✅ MACD Histogram Expanding Bullish")
        max_score += 1
    elif curr['MACD_Hist'] < prev['MACD_Hist'] < prev2['MACD_Hist']:
        score -= 1; signals.append("⛔ MACD Histogram Expanding Bearish")
        max_score += 1

    # 8. ADX Trend Strength (weight 1)
    max_score += 1
    adx = curr['ADX']
    if adx > 30:
        score += 1; signals.append(f"✅ Very Strong Trend (ADX {adx:.1f})")
    elif adx > 20:
        signals.append(f"🟡 Moderate Trend (ADX {adx:.1f})")
    else:
        score -= 1; signals.append(f"⚠️ Weak Trend – Choppy (ADX {adx:.1f})")

    # DI cross
    if curr['Plus_DI'] > curr['Minus_DI'] and prev['Plus_DI'] <= prev['Minus_DI']:
        score += 1; signals.append("✅ DI+ Cross Above DI- (FRESH)"); max_score += 1
    elif curr['Minus_DI'] > curr['Plus_DI'] and prev['Minus_DI'] <= prev['Plus_DI']:
        score -= 1; signals.append("⛔ DI- Cross Above DI+ (FRESH)"); max_score += 1

    # 9. Bollinger Bands (weight 1)
    max_score += 1
    bp = curr['BB_Pct']
    if bp < 0.05:
        score += 1; signals.append("💎 Price at/below BB Lower (Oversold)")
    elif bp > 0.95:
        score -= 1; signals.append("⚠️ Price at/above BB Upper (Overbought)")
    elif 0.4 < bp < 0.6:
        signals.append("🟡 Price near BB Midline")

    # Squeeze
    if curr.get('Squeeze', False):
        signals.append("🔵 BB Squeeze Active – Breakout Imminent")

    # 10. CCI (weight 1)
    max_score += 1
    cci = curr['CCI']
    if cci > 100:
        score -= 1; signals.append(f"⚠️ CCI Overbought ({cci:.0f})")
    elif cci < -100:
        score += 1; signals.append(f"💎 CCI Oversold ({cci:.0f})")
    elif cci > 0:
        signals.append(f"✅ CCI Positive ({cci:.0f})")

    # 11. Williams %R (weight 1)
    max_score += 1
    wr = curr['Williams_R']
    if wr < -80:
        score += 1; signals.append(f"💎 Williams %R Oversold ({wr:.1f})")
    elif wr > -20:
        score -= 1; signals.append(f"⚠️ Williams %R Overbought ({wr:.1f})")

    # 12. MFI (weight 1)
    max_score += 1
    mfi = curr['MFI']
    if mfi < 20:
        score += 1; signals.append(f"💎 MFI Oversold ({mfi:.0f}) – Smart money buying")
    elif mfi > 80:
        score -= 1; signals.append(f"⚠️ MFI Overbought ({mfi:.0f})")

    # 13. Volume (weight 1)
    max_score += 1
    vr = curr['Volume_Ratio']
    if vr > 2:
        score += 1; signals.append(f"✅ Volume Surge ({vr:.1f}x avg)")
    elif vr > 1.3:
        signals.append(f"✅ Above Average Volume ({vr:.1f}x)")
    elif vr < 0.5:
        score -= 1; signals.append(f"⚠️ Low Volume ({vr:.1f}x avg)")

    # 14. OBV Divergence (weight 1)
    max_score += 1
    if 'OBV_EMA' in curr:
        if curr['OBV'] > curr['OBV_EMA']:
            score += 1; signals.append("✅ OBV above OBV-EMA (Bullish)")
        else:
            score -= 1; signals.append("⛔ OBV below OBV-EMA (Bearish)")

    # 15. Elder Ray (weight 1)
    max_score += 1
    if curr['Bull_Power'] > 0 and curr['Bear_Power'] > 0:
        score += 1; signals.append("✅ Elder Ray: Strong Bull Power")
    elif curr['Bull_Power'] < 0 and curr['Bear_Power'] < 0:
        score -= 1; signals.append("⛔ Elder Ray: Strong Bear Power")

    # 16. VWAP (weight 1)
    max_score += 1
    if curr['Close'] > curr['VWAP']:
        score += 1; signals.append("✅ Price above VWAP")
    else:
        score -= 1; signals.append("⛔ Price below VWAP")

    # Normalise → 0‒100
    normalised = ((score + max_score) / (2 * max_score)) * 100

    if normalised >= 78:
        sig_label, confidence = "🟢 STRONG BUY", "Very High"
    elif normalised >= 63:
        sig_label, confidence = "🟢 BUY", "High"
    elif normalised >= 50:
        sig_label, confidence = "🟡 HOLD/NEUTRAL", "Medium"
    elif normalised >= 37:
        sig_label, confidence = "🔴 SELL", "High"
    else:
        sig_label, confidence = "🔴 STRONG SELL", "Very High"

    return {
        'Signal': sig_label,
        'Confidence': confidence,
        'Score': round(normalised, 1),
        'RSI': round(rsi, 1),
        'MACD': round(curr['MACD'], 6),
        'ADX': round(adx, 1),
        'ATR': curr['ATR'],
        'Price': curr['Close'],
        'Signals': signals,
        'BB_Pct': round(curr['BB_Pct'] * 100, 1),
        'Volume_Ratio': round(vr, 2),
        'Supertrend_Dir': curr.get('Supertrend_Dir', 0),
    }

# ══════════════════════════════════════════════
# 15-MINUTE SCALPING ENGINE (PRIMARY)
# ══════════════════════════════════════════════

def generate_15m_scalp_signal(df_15m: pd.DataFrame, df_1h: pd.DataFrame) -> dict:
    """
    Dedicated 15m scalping engine with higher-timeframe confluence filter.
    Uses 15m as the primary entry timeframe confirmed by 1h direction.
    """
    df15 = add_indicators(df_15m.copy())
    df1h = add_indicators(df_1h.copy())

    if len(df15) < 50 or len(df1h) < 50:
        return {'signal': 'INSUFFICIENT DATA', 'score': 0, 'reasons': []}

    c15 = df15.iloc[-1];  p15 = df15.iloc[-2]
    c1h = df1h.iloc[-1]

    score = 0; reasons = []

    # ── 1h TREND FILTER (must agree, weight 30) ─
    h_bull = c1h['Close'] > c1h['EMA50'] and c1h['EMA21'] > c1h['EMA50']
    h_bear = c1h['Close'] < c1h['EMA50'] and c1h['EMA21'] < c1h['EMA50']
    if h_bull:
        score += 30; reasons.append("✅ 1H Trend Filter: BULLISH (trading with trend)")
    elif h_bear:
        score -= 30; reasons.append("❌ 1H Trend Filter: BEARISH (trading with trend)")
    else:
        reasons.append("⚠️ 1H Trend: MIXED (counter-trend risk)")

    # ── 15m Supertrend (weight 20) ──────────────
    if c15.get('Supertrend_Dir', 0) == 1:
        score += 20; reasons.append("✅ 15m Supertrend: BULLISH")
    else:
        score -= 20; reasons.append("❌ 15m Supertrend: BEARISH")

    # ── 15m EMA 8 / 21 / 34 Ribbon (weight 15) ──
    if c15['EMA8'] > c15['EMA21'] > c15['EMA34']:
        score += 15; reasons.append("✅ 15m EMA Ribbon Bullish (8>21>34)")
    elif c15['EMA8'] < c15['EMA21'] < c15['EMA34']:
        score -= 15; reasons.append("❌ 15m EMA Ribbon Bearish")

    # ── Price vs VWAP (weight 10) ────────────────
    if c15['Close'] > c15['VWAP']:
        score += 10; reasons.append("✅ 15m Price above VWAP")
    else:
        score -= 10; reasons.append("❌ 15m Price below VWAP")

    # ── Stochastic RSI cross (weight 10) ─────────
    if c15['StochRSI_K'] > c15['StochRSI_D'] and p15['StochRSI_K'] <= p15['StochRSI_D']:
        if c15['StochRSI_K'] < 80:
            score += 10; reasons.append("🚀 15m StochRSI Bullish Cross (FRESH)")
    elif c15['StochRSI_K'] < c15['StochRSI_D'] and p15['StochRSI_K'] >= p15['StochRSI_D']:
        if c15['StochRSI_K'] > 20:
            score -= 10; reasons.append("🔻 15m StochRSI Bearish Cross (FRESH)")

    # ── RSI zone filter (weight 5) ────────────────
    rsi = c15['RSI']
    if 40 < rsi < 65:
        score += 5; reasons.append(f"✅ 15m RSI in trade zone ({rsi:.0f})")
    elif rsi > 75 or rsi < 25:
        score -= 5; reasons.append(f"⚠️ 15m RSI extreme ({rsi:.0f}) – expect reversal")

    # ── Volume spike (weight 5) ──────────────────
    if c15['Volume_Ratio'] > 1.5:
        score += 5; reasons.append(f"✅ Volume spike ({c15['Volume_Ratio']:.1f}x avg)")
    elif c15['Volume_Ratio'] < 0.6:
        score -= 5; reasons.append(f"⚠️ Low volume ({c15['Volume_Ratio']:.1f}x avg) – weak move")

    # ── Bollinger Squeeze breakout (weight 5) ────
    if c15.get('Squeeze', False):
        if c15['MACD_Hist'] > 0:
            score += 5; reasons.append("🔵 BB Squeeze Breakout UP")
        else:
            score -= 5; reasons.append("🔵 BB Squeeze Breakout DOWN")

    # ── Convert to 0-100 ─────────────────────────
    norm = max(0, min(100, (score + 100) / 2))

    if norm >= 78:
        sig, conf = "STRONG BUY", "Very High"
    elif norm >= 62:
        sig, conf = "BUY", "High"
    elif norm >= 45:
        sig, conf = "NEUTRAL", "Medium"
    elif norm >= 30:
        sig, conf = "SELL", "High"
    else:
        sig, conf = "STRONG SELL", "Very High"

    patterns = identify_candle_patterns(df15)
    pattern_str = patterns[0]['name'] if patterns else "No Pattern"

    # Entry / exit levels
    atr = c15['ATR']
    price = c15['Close']
    sl_mult = 1.5; tp_mult = 2.5  # Scalp ATR multipliers
    if "BUY" in sig:
        sl = price - atr * sl_mult; tp = price + atr * tp_mult
    else:
        sl = price + atr * sl_mult; tp = price - atr * tp_mult

    return {
        'signal': sig, 'confidence': conf,
        'score': round(norm, 1), 'reasons': reasons,
        'pattern': pattern_str, 'price': price,
        'sl': sl, 'tp': tp, 'atr': atr,
        'rsi': round(rsi, 1),
        'stoch_k': round(c15['StochRSI_K'], 1),
    }

# ══════════════════════════════════════════════
# MASTER SIGNAL CALCULATOR
# ══════════════════════════════════════════════

def calc_master_signal(datasets: dict, scalp_sig: dict) -> dict:
    """Combines all timeframe signals into master signals for Scalp/Intra/Swing."""
    masters = {}

    # ── Scalp (15m primary) ─────────────────────
    masters['scalp'] = {
        'signal': scalp_sig.get('signal', 'NEUTRAL'),
        'score':  scalp_sig.get('score', 50),
        'conf':   scalp_sig.get('confidence', 'Low'),
    }

    # ── Intraday (30m + 1h) ─────────────────────
    sig30 = generate_signal(add_indicators(datasets['30m']), '30m')
    sig1h = generate_signal(add_indicators(datasets['1h']),  '1h')
    if sig30 and sig1h:
        intra_score = (sig30['Score'] * 0.4 + sig1h['Score'] * 0.6)
        if intra_score >= 78:
            i_sig = "STRONG BUY"
        elif intra_score >= 63:
            i_sig = "BUY"
        elif intra_score >= 45:
            i_sig = "NEUTRAL"
        elif intra_score >= 37:
            i_sig = "SELL"
        else:
            i_sig = "STRONG SELL"
        masters['intraday'] = {'signal': i_sig, 'score': round(intra_score, 1), 'conf': sig1h['Confidence']}
    else:
        masters['intraday'] = {'signal': 'NEUTRAL', 'score': 50, 'conf': 'Low'}

    # ── Swing (4h + Daily) ───────────────────────
    sig4h = generate_signal(add_indicators(datasets['4h']), '4h')
    sig1d = generate_signal(add_indicators(datasets['1d']), '1d')
    if sig4h and sig1d:
        swing_score = (sig4h['Score'] * 0.5 + sig1d['Score'] * 0.5)
        if swing_score >= 78:
            s_sig = "STRONG BUY"
        elif swing_score >= 63:
            s_sig = "BUY"
        elif swing_score >= 45:
            s_sig = "NEUTRAL"
        elif swing_score >= 37:
            s_sig = "SELL"
        else:
            s_sig = "STRONG SELL"
        masters['swing'] = {'signal': s_sig, 'score': round(swing_score, 1), 'conf': sig4h['Confidence']}
    else:
        masters['swing'] = {'signal': 'NEUTRAL', 'score': 50, 'conf': 'Low'}

    return masters

# ══════════════════════════════════════════════
# CONFLICT DETECTION
# ══════════════════════════════════════════════

def detect_conflicts(datasets: dict, all_sigs: dict) -> dict:
    """Detects inter-indicator and timeframe conflicts."""
    conflicts = []; warnings = []
    risk = 0

    sig15 = all_sigs.get('15m')
    sig1h = all_sigs.get('1h')
    sig4h = all_sigs.get('4h')

    # Price momentum (15m)
    df15 = datasets['15m']
    if len(df15) >= 3:
        mom15 = (df15['Close'].iloc[-1] / df15['Close'].iloc[-3] - 1) * 100
    else:
        mom15 = 0

    # Timeframe conflict
    if sig15 and sig1h:
        if "BUY" in sig15['Signal'] and "SELL" in sig1h['Signal']:
            conflicts.append({'severity': 'HIGH',
                'msg': "⚠️ 15m BUY vs 1H SELL – Counter-trend scalp only",
                'action': "Use tight stop, 50% size max"})
            risk += 20
        if "SELL" in sig15['Signal'] and "BUY" in sig1h['Signal']:
            conflicts.append({'severity': 'MEDIUM',
                'msg': "⚠️ 15m SELL vs 1H BUY – Pullback only, not reversal",
                'action': "Do not short aggressively"})
            risk += 10

    # Price vs signal conflict
    if sig15 and "BUY" in sig15['Signal'] and mom15 < -0.5:
        conflicts.append({'severity': 'HIGH',
            'msg': f"⚠️ BUY signal but price fell {mom15:.2f}% (last 15m)",
            'action': "Wait for stabilisation"})
        risk += 20

    if sig15 and "SELL" in sig15['Signal'] and mom15 > 0.5:
        conflicts.append({'severity': 'HIGH',
            'msg': f"⚠️ SELL signal but price rose +{mom15:.2f}% (last 15m)",
            'action': "Wait for rejection confirmation"})
        risk += 20

    # RSI divergence
    if sig15:
        rsi = sig15['RSI']
        if "BUY" in sig15['Signal'] and rsi > 72:
            warnings.append({'msg': f"⚠️ BUY but RSI overbought ({rsi:.0f})", 'action': "Tight SL"})
            risk += 10
        if "SELL" in sig15['Signal'] and rsi < 28:
            warnings.append({'msg': f"⚠️ SELL but RSI oversold ({rsi:.0f})", 'action': "Bounce likely"})
            risk += 10

    # ADX / Trend strength
    if sig15 and sig15['ADX'] < 18 and ("STRONG" in sig15['Signal']):
        warnings.append({'msg': f"⚠️ STRONG signal on weak trend (ADX {sig15['ADX']:.0f})",
                          'action': "Reduce size 50%"}); risk += 8

    # Assessment
    if risk >= 35:
        assessment = "🚫 HIGH RISK – Skip or micro-size"
    elif risk >= 20:
        assessment = "⚠️ MEDIUM RISK – Reduce size"
    elif risk > 0:
        assessment = "💛 LOW RISK – Trade with caution"
    else:
        assessment = "✅ CLEAN SETUP – Full size allowed"

    return {
        'conflicts': conflicts, 'warnings': warnings,
        'risk_score': risk, 'assessment': assessment,
        'momentum_15m': round(mom15, 3),
    }

# ══════════════════════════════════════════════
# VOLUME PROFILE
# ══════════════════════════════════════════════

def volume_profile(df: pd.DataFrame, bins: int = 24) -> dict | None:
    if len(df) < 30:
        return None
    price_min = df['Low'].min(); price_max = df['High'].max()
    edges = np.linspace(price_min, price_max, bins)
    vol_at_price = np.zeros(bins - 1)
    for _, row in df.iterrows():
        lo, hi, vol = row['Low'], row['High'], row['Volume']
        for j in range(bins - 1):
            if edges[j] <= hi and edges[j+1] >= lo:
                vol_at_price[j] += vol / max(1, bins - 1)
    poc_idx = np.argmax(vol_at_price)
    poc = (edges[poc_idx] + edges[poc_idx+1]) / 2
    total = vol_at_price.sum()
    sorted_idx = np.argsort(vol_at_price)[::-1]
    cumvol = 0; va_idx = []
    for i in sorted_idx:
        cumvol += vol_at_price[i]; va_idx.append(i)
        if cumvol >= total * 0.70: break
    va_idx.sort()
    return {'poc': poc, 'va_low': edges[va_idx[0]], 'va_high': edges[va_idx[-1]+1],
            'bins': edges, 'volume': vol_at_price}

# ══════════════════════════════════════════════
# ORDER FLOW DETECTION
# ══════════════════════════════════════════════

def detect_order_flow(df: pd.DataFrame) -> dict:
    if len(df) < 10:
        return {'strength': 0, 'classification': 'Neutral', 'signals': []}
    strength = 0; signals = []
    recent = df.tail(10)
    for i in range(1, len(recent)):
        curr = recent.iloc[i]; prev = recent.iloc[i-1]
        rng = curr['High'] - curr['Low'] + 1e-9
        close_pct = (curr['Close'] - curr['Low']) / rng
        if close_pct > 0.7 and curr['Volume'] > prev['Volume'] * 1.2:
            strength += 2; signals.append("🟢 Aggressive buying")
        elif close_pct < 0.3 and curr['Volume'] > prev['Volume'] * 1.2:
            strength -= 2; signals.append("🔴 Aggressive selling")
        body = abs(curr['Close'] - curr['Open'])
        if body < rng * 0.3 and curr['Volume'] > recent['Volume'].mean() * 2:
            signals.append("📊 Absorption – Institutional accumulation likely")
            strength += 1
    cls = "Bullish" if strength > 2 else "Bearish" if strength < -2 else "Neutral"
    return {'strength': strength, 'classification': cls, 'signals': signals[-3:]}

# ══════════════════════════════════════════════
# MARKET REGIME
# ══════════════════════════════════════════════

def detect_regime(df: pd.DataFrame) -> dict | None:
    df = add_indicators(df)
    if len(df) < 60:
        return None
    curr = df.iloc[-1]
    adx = curr['ADX']
    bb_w = curr['BB_Width'] * 100
    ema_align = curr['EMA9'] > curr['EMA21'] > curr['EMA50']
    above200 = curr['Close'] > curr['EMA200']

    if adx > 30 and ema_align:
        regime = "📈 Strong Uptrend"; strat = "Trend-Follow Long"; conf = "High"
    elif adx > 30 and not ema_align:
        regime = "📉 Strong Downtrend"; strat = "Trend-Follow Short"; conf = "High"
    elif adx < 18 and bb_w < 4:
        regime = "📊 Tight Consolidation"; strat = "Breakout Watch"; conf = "Medium"
    elif bb_w > 9:
        regime = "💥 High Volatility"; strat = "Reduce Size / Breakout"; conf = "Low"
    else:
        regime = "🌊 Ranging/Choppy"; strat = "Mean Reversion"; conf = "Low"

    return {'regime': regime, 'strategy': strat, 'confidence': conf,
            'adx': adx, 'bb_width': bb_w, 'above200': above200}

# ══════════════════════════════════════════════
# NEWS FEED
# ══════════════════════════════════════════════

def get_news() -> list:
    if FEEDPARSER_AVAILABLE:
        items = []
        for url in ['https://cointelegraph.com/rss', 'https://cryptonews.com/news/feed/']:
            try:
                feed = feedparser.parse(url)
                for e in feed.entries[:4]:
                    items.append({'title': e.title, 'link': e.link,
                                   'pub': e.get('published', 'Recent')})
            except: pass
        if items: return items[:10]
    return [
        {'title': 'BTC holds key support as institutions accumulate', 'link': '#', 'pub': 'Recent'},
        {'title': 'Gold (XAU) surges on geopolitical uncertainty',    'link': '#', 'pub': 'Recent'},
        {'title': 'Crypto market rebounds after short-term correction','link': '#', 'pub': 'Recent'},
        {'title': 'XRP gains on SEC settlement rumours',               'link': '#', 'pub': 'Recent'},
    ]

# ══════════════════════════════════════════════
# TRADE CALCULATOR
# ══════════════════════════════════════════════

def calc_trade(price, atr, direction='LONG', style='Scalp', rr=2.0):
    mult = {'Scalp': 1.2, 'Intraday': 1.8, 'Swing': 2.5}.get(style, 1.5)
    sl_dist = atr * mult; tp_dist = sl_dist * rr
    if direction == 'LONG':
        sl = price - sl_dist; tp = price + tp_dist; be = price + sl_dist * 0.5
    else:
        sl = price + sl_dist; tp = price - tp_dist; be = price - sl_dist * 0.5
    return {'entry': price, 'sl': sl, 'tp': tp, 'breakeven': be,
            'risk_pct': sl_dist / price * 100, 'reward_pct': tp_dist / price * 100,
            'rr': rr}

# ══════════════════════════════════════════════
# ═══════  RENDER HELPERS  ════════════════════
# ══════════════════════════════════════════════

def _sig_card_css(signal: str) -> str:
    if "STRONG BUY"  in signal: return "card-strong-buy"
    if "BUY"         in signal: return "card-buy"
    if "STRONG SELL" in signal: return "card-strong-sell"
    if "SELL"        in signal: return "card-sell"
    return "card-neutral"

def _sig_icon(signal: str) -> str:
    if "STRONG BUY"  in signal: return "🚀"
    if "BUY"         in signal: return "📈"
    if "STRONG SELL" in signal: return "💀"
    if "SELL"        in signal: return "📉"
    return "⏸"

def render_master_signal_cards(masters: dict):
    """Renders the 3 master signal cards prominently at the top."""
    col1, col2, col3 = st.columns(3)
    labels = [
        ("⚡ SCALPING (15m)", "scalp"),
        ("📅 INTRADAY (1H)",  "intraday"),
        ("🌊 SWING (4H/D)",   "swing"),
    ]
    for col, (label, key) in zip([col1, col2, col3], labels):
        ms = masters.get(key, {'signal': 'NEUTRAL', 'score': 50, 'conf': 'Low'})
        css = _sig_card_css(ms['signal'])
        icon = _sig_icon(ms['signal'])
        with col:
            st.markdown(f"""
            <div class="sig-card {css}">
                <div class="sig-label">{label}</div>
                <div class="sig-main">{icon} {ms['signal']}</div>
                <div class="sig-score">Score: {ms['score']:.1f} / 100</div>
                <div class="sig-conf">Confidence: {ms['conf']}</div>
            </div>
            """, unsafe_allow_html=True)


def render_scalp_detail(scalp: dict):
    """Detailed 15m scalp panel."""
    st.markdown("#### ⚡ 15m Scalp Deep-Dive")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Entry", f"${scalp['price']:,.4f}")
    c2.metric("Stop-Loss", f"${scalp['sl']:,.4f}")
    c3.metric("Take-Profit", f"${scalp['tp']:,.4f}")
    c4.metric("RSI / StochRSI", f"{scalp['rsi']:.0f} / {scalp['stoch_k']:.0f}")
    st.caption(f"Pattern: {scalp['pattern']}  |  ATR: {scalp['atr']:.4f}")
    with st.expander("📋 Scalp Signal Reasoning"):
        for r in scalp['reasons']:
            st.write(r)


def render_conflict_panel(conflict: dict):
    """Conflict & Risk panel."""
    st.subheader("🚨 Signal Quality & Risk Check")
    c1, c2, c3 = st.columns([2, 1, 1])
    risk = conflict['risk_score']
    if risk >= 35:
        c1.error(f"**{conflict['assessment']}**")
    elif risk >= 20:
        c1.warning(f"**{conflict['assessment']}**")
    else:
        c1.success(f"**{conflict['assessment']}**")
    c2.metric("Risk Score", risk, help="0 = clean, 35+ = skip")
    c3.metric("15m Momentum", f"{conflict['momentum_15m']:+.2f}%")

    for cf in conflict['conflicts']:
        cls = 'conflict-critical' if cf['severity'] == 'HIGH' else 'conflict-medium'
        st.markdown(f"""
        <div class="{cls}">
            <b>{cf['msg']}</b><br>
            <small>💡 {cf['action']}</small>
        </div>
        """, unsafe_allow_html=True)

    for w in conflict['warnings']:
        st.warning(f"{w['msg']} — {w['action']}")


def render_timeframe_scanner(datasets: dict, rr: float, pos_size: float):
    """Full multi-timeframe scanner + trade setups."""
    st.subheader("⏰ Multi-Timeframe Scanner")
    tfs = ['15m', '30m', '1h', '4h', '1d']
    cols = st.columns(len(tfs))
    all_sigs = {}

    for col, tf in zip(cols, tfs):
        df = add_indicators(datasets[tf])
        sig = generate_signal(df, tf)
        all_sigs[tf] = sig
        with col:
            st.markdown(f"**{tf.upper()}**")
            if sig:
                css = _sig_card_css(sig['Signal'])
                icon = _sig_icon(sig['Signal'])
                st.markdown(f"""
                <div class="sig-card {css}" style="padding:12px 8px;">
                    <div style="font-size:11px;opacity:.7;">{icon}</div>
                    <div style="font-size:13px;font-weight:700;">{sig['Signal'].replace('🟢','').replace('🔴','').replace('🟡','').strip()}</div>
                    <div style="font-size:11px;">{sig['Score']}/100</div>
                </div>
                """, unsafe_allow_html=True)
                st.caption(f"RSI {sig['RSI']} | ADX {sig['ADX']}")
                with st.expander("Details"):
                    for s in sig['Signals'][:5]: st.caption(s)

    st.divider()

    # ── Candle Patterns ──────────────────────────
    st.subheader("🕯️ Candlestick Patterns (15m + 1H)")
    pc1, pc2 = st.columns(2)
    with pc1:
        st.markdown("**15m Patterns**")
        for p in identify_candle_patterns(datasets['15m'])[:4]:
            bias_color = "🟢" if p['bias']=='bullish' else "🔴" if p['bias']=='bearish' else "⚪"
            st.caption(f"{bias_color} {p['name']} ({p['strength']})")
    with pc2:
        st.markdown("**1H Patterns**")
        for p in identify_candle_patterns(datasets['1h'])[:4]:
            bias_color = "🟢" if p['bias']=='bullish' else "🔴" if p['bias']=='bearish' else "⚪"
            st.caption(f"{bias_color} {p['name']} ({p['strength']})")

    st.divider()

    # ── AI Trade Setups ──────────────────────────
    st.subheader("🎯 AI Trade Setups")
    sc, ic, swc = st.columns(3)

    # Scalp
    s15 = all_sigs.get('15m')
    with sc:
        st.markdown("### ⚡ Scalp (15m)")
        if s15:
            direction = "LONG" if "BUY" in s15['Signal'] else "SHORT" if "SELL" in s15['Signal'] else None
            if direction:
                t = calc_trade(s15['Price'], s15['ATR'], direction, 'Scalp', rr)
                fn = st.success if direction == "LONG" else st.error
                fn(f"{'📈' if direction=='LONG' else '📉'} {direction}")
                st.write(f"Entry: **${t['entry']:,.4f}**")
                st.write(f"🎯 TP: ${t['tp']:,.4f} (+{t['reward_pct']:.2f}%)")
                st.write(f"🛑 SL: ${t['sl']:,.4f} (-{t['risk_pct']:.2f}%)")
                st.write(f"⚖️ BE: ${t['breakeven']:,.4f}")
                st.caption(f"Risk $: ${pos_size * t['risk_pct'] / 100:.2f}")
            else:
                st.info("⏸ No Setup")

    # Intraday
    s30 = all_sigs.get('30m'); s1h = all_sigs.get('1h')
    with ic:
        st.markdown("### 📅 Intraday (30m+1H)")
        if s30 and s1h:
            if "BUY" in s30['Signal'] and "BUY" in s1h['Signal']:
                t = calc_trade(s1h['Price'], s1h['ATR'], 'LONG', 'Intraday', rr)
                st.success("📈 LONG (Aligned)")
                st.write(f"Entry: **${t['entry']:,.4f}**")
                st.write(f"🎯 TP: ${t['tp']:,.4f} (+{t['reward_pct']:.2f}%)")
                st.write(f"🛑 SL: ${t['sl']:,.4f} (-{t['risk_pct']:.2f}%)")
                st.caption(f"Risk $: ${pos_size * t['risk_pct'] / 100:.2f}")
            elif "SELL" in s30['Signal'] and "SELL" in s1h['Signal']:
                t = calc_trade(s1h['Price'], s1h['ATR'], 'SHORT', 'Intraday', rr)
                st.error("📉 SHORT (Aligned)")
                st.write(f"Entry: **${t['entry']:,.4f}**")
                st.write(f"🎯 TP: ${t['tp']:,.4f} (+{t['reward_pct']:.2f}%)")
                st.write(f"🛑 SL: ${t['sl']:,.4f} (-{t['risk_pct']:.2f}%)")
                st.caption(f"Risk $: ${pos_size * t['risk_pct'] / 100:.2f}")
            else:
                st.warning("⏸ Wait – Timeframes not aligned")

    # Swing
    s4h = all_sigs.get('4h')
    with swc:
        st.markdown("### 🌊 Swing (4H)")
        if s4h:
            direction = "LONG" if "BUY" in s4h['Signal'] else "SHORT" if "SELL" in s4h['Signal'] else None
            if direction:
                t = calc_trade(s4h['Price'], s4h['ATR'], direction, 'Swing', rr)
                fn = st.success if direction == "LONG" else st.error
                fn(f"{'📈' if direction=='LONG' else '📉'} {direction}")
                st.write(f"Entry: **${t['entry']:,.4f}**")
                st.write(f"🎯 TP: ${t['tp']:,.4f} (+{t['reward_pct']:.2f}%)")
                st.write(f"🛑 SL: ${t['sl']:,.4f} (-{t['risk_pct']:.2f}%)")
                st.caption(f"Risk $: ${pos_size * t['risk_pct'] / 100:.2f}")
            else:
                st.info("⏸ No Setup")

    return all_sigs


def render_chart(datasets: dict):
    """Advanced chart: Candles + EMAs + BB + Volume Profile + RSI + MACD + Volume."""
    st.subheader("📈 Advanced Chart (1H) + Volume Profile + Full Indicator Suite")
    df = add_indicators(datasets['1h'])
    vp = volume_profile(df)

    fig = make_subplots(
        rows=4, cols=1, shared_xaxes=True,
        vertical_spacing=0.02,
        row_heights=[0.55, 0.15, 0.15, 0.15],
        subplot_titles=('Price + Indicators', 'RSI', 'MACD', 'Volume')
    )

    # Candlesticks
    fig.add_trace(go.Candlestick(
        x=df.index, open=df['Open'], high=df['High'],
        low=df['Low'], close=df['Close'], name="Price",
        increasing_line_color='#00e676', decreasing_line_color='#ff5252',
    ), row=1, col=1)

    # EMAs
    ema_cfg = [('EMA9','#ffeb3b',1),('EMA21','#ff9800',1.5),
               ('EMA50','#2196f3',2),('EMA200','#ffffff',2)]
    for name, color, width in ema_cfg:
        if name in df.columns:
            fig.add_trace(go.Scatter(x=df.index, y=df[name], name=name,
                line=dict(color=color, width=width), opacity=0.8), row=1, col=1)

    # Bollinger Bands
    fig.add_trace(go.Scatter(x=df.index, y=df['BB_Upper'], name='BB Upper',
        line=dict(color='#607d8b', width=1, dash='dot'), opacity=0.6), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['BB_Lower'], name='BB Lower',
        line=dict(color='#607d8b', width=1, dash='dot'),
        fill='tonexty', fillcolor='rgba(96,125,139,0.05)', opacity=0.6), row=1, col=1)

    # Supertrend
    if 'Supertrend' in df.columns:
        bull_st = df['Supertrend'].where(df['Supertrend_Dir'] == 1)
        bear_st = df['Supertrend'].where(df['Supertrend_Dir'] == -1)
        fig.add_trace(go.Scatter(x=df.index, y=bull_st, name='Supertrend ▲',
            line=dict(color='#00e676', width=2), mode='lines'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=bear_st, name='Supertrend ▼',
            line=dict(color='#ff5252', width=2), mode='lines'), row=1, col=1)

    # VWAP
    if 'VWAP' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['VWAP'], name='VWAP',
            line=dict(color='#e040fb', width=1.5, dash='dash'), opacity=0.9), row=1, col=1)

    # Volume Profile lines
    if vp:
        fig.add_hline(y=vp['poc'], line_color='#00bcd4', line_width=2,
            annotation_text="POC", annotation_position="right", row=1, col=1)
        fig.add_hrect(y0=vp['va_low'], y1=vp['va_high'],
            fillcolor='rgba(0,188,212,0.07)', line_width=0, row=1, col=1)

    # Pivot levels
    if 'R1' in df.columns:
        for lv, lbl, clr in [('R1','R1','#ef5350'),('S1','S1','#66bb6a'),
                              ('R2','R2','#e53935'),('S2','S2','#388e3c')]:
            fig.add_hline(y=df[lv].iloc[-1], line_color=clr, line_width=1,
                line_dash='dot', annotation_text=lbl, row=1, col=1)

    # RSI
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], name='RSI',
        line=dict(color='#ab47bc', width=1.5)), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI_EMA'], name='RSI Signal',
        line=dict(color='#ffa726', width=1, dash='dash')), row=2, col=1)
    for lvl, clr in [(70,'red'),(30,'green'),(50,'gray')]:
        fig.add_hline(y=lvl, line_dash='dash', line_color=clr, opacity=0.4, row=2, col=1)

    # MACD
    fig.add_trace(go.Scatter(x=df.index, y=df['MACD'], name='MACD',
        line=dict(color='#2196f3')), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MACD_Sig'], name='Signal',
        line=dict(color='#ff9800')), row=3, col=1)
    colors = ['#00e676' if v >= 0 else '#ff5252' for v in df['MACD_Hist']]
    fig.add_trace(go.Bar(x=df.index, y=df['MACD_Hist'], name='Histogram',
        marker_color=colors, opacity=0.7), row=3, col=1)

    # Volume
    vcol = ['#00e676' if df['Close'].iloc[i] >= df['Open'].iloc[i] else '#ff5252'
            for i in range(len(df))]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='Volume',
        marker_color=vcol, opacity=0.6), row=4, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['Volume_MA'], name='Vol MA',
        line=dict(color='white', width=1)), row=4, col=1)

    fig.update_layout(
        height=900, template='plotly_dark',
        xaxis_rangeslider_visible=False,
        showlegend=True, hovermode='x unified',
        legend=dict(orientation='h', y=1.02, x=0),
        margin=dict(l=40, r=40, t=40, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_confluence_panel(symbol: str, datasets: dict, news: list):
    """Full institutional confluence panel."""
    st.subheader("🎯 Institutional Confluence Analysis")

    df1h = add_indicators(datasets['1h'])
    df15 = add_indicators(datasets['15m'])

    regime = detect_regime(df1h)
    order_flow = detect_order_flow(df15)
    vp = volume_profile(df1h)

    # Scores
    regime_score = {'High': 80, 'Medium': 55, 'Low': 30}.get(regime['confidence'] if regime else 'Low', 50)
    of_strength = order_flow['strength']
    of_score = max(0, min(100, 50 + of_strength * 10))

    sig1h = generate_signal(df1h, '1h')
    tech_score = sig1h['Score'] if sig1h else 50

    news_score = 50  # Default neutral sentiment
    bullish_kw = ['surge','rally','bullish','gain','rise','adoption','partnership']
    bearish_kw = ['crash','drop','decline','bearish','ban','fear','liquidation']
    for item in news[:6]:
        title = item['title'].lower()
        b = sum(1 for w in bullish_kw if w in title)
        d = sum(1 for w in bearish_kw if w in title)
        news_score += (b - d) * 6
    news_score = max(0, min(100, news_score))

    confluence = (tech_score * 0.40 + regime_score * 0.25 +
                  of_score * 0.20 + news_score * 0.15)

    # Display
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        if confluence >= 78:
            st.success(f"### 🏆 CONFLUENCE: {confluence:.1f} / 100 — INSTITUTIONAL GRADE")
        elif confluence >= 63:
            st.info(f"### ✅ CONFLUENCE: {confluence:.1f} / 100 — HIGH QUALITY")
        elif confluence >= 50:
            st.warning(f"### ⚠️ CONFLUENCE: {confluence:.1f} / 100 — MODERATE")
        else:
            st.error(f"### ❌ CONFLUENCE: {confluence:.1f} / 100 — LOW QUALITY")

    with c2:
        st.metric("Market Regime", regime['regime'] if regime else "N/A")
        st.caption(regime['strategy'] if regime else '')

    with c3:
        st.metric("Order Flow", order_flow['classification'])
        st.caption(f"Strength: {of_strength:+d}")

    # Breakdown
    st.markdown("**Score Breakdown (Weighted)**")
    bc = st.columns(4)
    for col, (label, val, wt) in zip(bc, [
        ("📈 Technical (40%)", tech_score, 0.40),
        ("🎯 Regime (25%)",    regime_score, 0.25),
        ("💼 Order Flow (20%)", of_score, 0.20),
        ("📰 Sentiment (15%)", news_score, 0.15),
    ]):
        with col:
            st.markdown(f"**{label}**")
            st.progress(val / 100)
            st.caption(f"{val:.0f}/100")

    # Volume Profile detail
    if vp:
        st.divider()
        price = df1h['Close'].iloc[-1]
        vp_c1, vp_c2, vp_c3 = st.columns(3)
        vp_c1.metric("POC (Max Volume)", f"${vp['poc']:,.2f}")
        vp_c2.metric("Value Area Low",   f"${vp['va_low']:,.2f}")
        vp_c3.metric("Value Area High",  f"${vp['va_high']:,.2f}")
        if vp['va_low'] <= price <= vp['va_high']:
            st.success("✅ Price inside Value Area – Fair Value Zone")
        elif price > vp['va_high']:
            st.warning("⚠️ Price above Value Area – Premium Zone")
        else:
            st.info("💡 Price below Value Area – Discount Zone (potential buy)")

    # Alert check
    if confluence >= st.session_state.alert_threshold:
        st.balloons()
        st.success(f"🔔 **ALERT!** Confluence {confluence:.1f}% exceeded threshold "
                   f"({st.session_state.alert_threshold}%) — Institutional-grade setup detected!")


def render_news():
    st.subheader("📰 Live Market News")
    news = get_news()
    c1, c2 = st.columns(2)
    for i, item in enumerate(news[:8]):
        with (c1 if i % 2 == 0 else c2):
            st.markdown(f"""
            <div class="news-item">
                <b>{item['title']}</b><br>
                <small style="color:#888">{item['pub']}</small>
                <a href="{item['link']}" target="_blank" style="color:#fca311;font-size:12px;"> Read →</a>
            </div>
            """, unsafe_allow_html=True)


def render_live_ticker(symbols: list):
    """Top-of-page live price ticker bar."""
    cols = st.columns(len(symbols))
    for col, sym in zip(cols, symbols):
        data = get_ticker_price(sym)
        color = "#00e676" if data['change'] >= 0 else "#ff5252"
        arrow = "▲" if data['change'] >= 0 else "▼"
        col.markdown(f"""
        <div class="ticker-wrap" style="border-left:3px solid {color};">
            <div class="ticker-name">{sym}</div>
            <div class="ticker-price">${data['price']:,.4f}</div>
            <div style="color:{color};font-size:13px;">{arrow} {abs(data['change']):.2f}%</div>
        </div>
        """, unsafe_allow_html=True)

# ══════════════════════════════════════════════
# ═══════════  MAIN APP  ══════════════════════
# ══════════════════════════════════════════════

# ─── SIDEBAR ─────────────────────────────────
st.sidebar.title("⚙️ Settings")

# API Keys
with st.sidebar.expander("🔑 Binance API (Optional)"):
    st.session_state.api_key    = st.text_input("API Key",    value=st.session_state.api_key,    type="password")
    st.session_state.api_secret = st.text_input("API Secret", value=st.session_state.api_secret, type="password")
    if not st.session_state.api_key:
        st.caption("ℹ️ No key needed for public market data.")

# View mode
view_mode = st.sidebar.radio("View Mode", ["Single Asset", "Multi-Asset"], index=0)

# Quick symbols
st.sidebar.markdown("**⚡ Quick Select**")
QUICK = {
    'BTC':    'BTC/USDT',
    'ETH':    'ETH/USDT',
    'SOL':    'SOL/USDT',
    'BNB':    'BNB/USDT',
    'XRP':    'XRP/USDT',
    'DOGE':   'DOGE/USDT',
    'ADA':    'ADA/USDT',
    'AVAX':   'AVAX/USDT',
    'Gold':   'XAU/USDT',
    'Silver': 'XAG/USDT',
}
qs_cols = st.sidebar.columns(2)
for i, (name, ticker) in enumerate(QUICK.items()):
    with qs_cols[i % 2]:
        if st.button(name, key=f"qs_{ticker}", use_container_width=True):
            if view_mode == "Single Asset":
                st.session_state.current_symbol = ticker
            else:
                st.session_state.symbol_1 = ticker
            st.rerun()

st.sidebar.divider()

if view_mode == "Single Asset":
    symbol = st.sidebar.text_input("Symbol", value=st.session_state.current_symbol).upper()
    st.session_state.current_symbol = symbol
else:
    st.session_state.symbol_1 = st.sidebar.text_input("Asset 1", value=st.session_state.symbol_1).upper()
    st.session_state.symbol_2 = st.sidebar.text_input("Asset 2", value=st.session_state.symbol_2).upper()

st.sidebar.divider()

# Risk
st.sidebar.subheader("💰 Risk Management")
rr         = st.sidebar.slider("Risk : Reward", 1.0, 4.0, 2.0, 0.5)
pos_size   = st.sidebar.number_input("Position Size ($)", 100, 1_000_000, 1000, 100)

# Alerts
st.sidebar.divider()
st.sidebar.subheader("🔔 Alerts")
st.session_state.alert_threshold = st.sidebar.slider("Confluence Alert %", 50, 100, 85)

# Refresh
st.sidebar.divider()
st.session_state.auto_refresh = st.sidebar.checkbox("Auto Refresh (60s)", value=st.session_state.auto_refresh)
if st.sidebar.button("🔄 Refresh Now", use_container_width=True):
    st.rerun()
st.sidebar.caption(f"Last: {st.session_state.last_refresh.strftime('%H:%M:%S')}")

if not CCXT_AVAILABLE:
    st.sidebar.warning("⚠️ CCXT not installed.\n`pip install ccxt`\nUsing demo data.")

# ─── HEADER ─────────────────────────────────
st.markdown("# 🏛️ Institutional AI Trading Platform")
st.caption(f"Powered by CCXT (Binance) · {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")

TICKER_SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'XAU/USDT', 'XAG/USDT']
render_live_ticker(TICKER_SYMBOLS)
st.divider()

# ─── MAIN CONTENT ────────────────────────────
def full_asset_page(symbol: str):
    st.subheader(f"📊 {symbol}")

    with st.spinner(f"Loading {symbol} data from Binance..."):
        datasets = get_all_datasets(symbol)

    if not datasets:
        st.error("❌ Could not load data. Check symbol or try again."); return

    news = get_news()

    # ═══════════════════════════════════════════
    # 🔝  SIGNALS ON TOP  (highest priority)
    # ═══════════════════════════════════════════
    st.markdown("## 🎯 Live Trading Signals")

    # 15m scalp
    scalp = generate_15m_scalp_signal(datasets['15m'], datasets['1h'])
    # Master signals
    masters = calc_master_signal(datasets, scalp)

    render_master_signal_cards(masters)
    st.divider()
    render_scalp_detail(scalp)
    st.divider()

    # ═══════════════════════════════════════════
    # CONFLICT CHECK
    # ═══════════════════════════════════════════
    all_sigs_for_conflict = {}
    for tf in ['15m', '1h', '4h']:
        df = add_indicators(datasets[tf])
        all_sigs_for_conflict[tf] = generate_signal(df, tf)
    conflict = detect_conflicts(datasets, all_sigs_for_conflict)
    render_conflict_panel(conflict)
    st.divider()

    # ═══════════════════════════════════════════
    # CONFLUENCE
    # ═══════════════════════════════════════════
    render_confluence_panel(symbol, datasets, news)
    st.divider()

    # ═══════════════════════════════════════════
    # TIMEFRAME SCANNER + TRADE SETUPS
    # ═══════════════════════════════════════════
    render_timeframe_scanner(datasets, rr, pos_size)
    st.divider()

    # ═══════════════════════════════════════════
    # CHART
    # ═══════════════════════════════════════════
    render_chart(datasets)
    st.divider()

    # ═══════════════════════════════════════════
    # NEWS
    # ═══════════════════════════════════════════
    render_news()


# ─── ROUTING ─────────────────────────────────
if view_mode == "Single Asset":
    full_asset_page(st.session_state.current_symbol)

else:
    col_a, col_b = st.columns(2)
    with col_a:
        full_asset_page(st.session_state.symbol_1)
    with col_b:
        full_asset_page(st.session_state.symbol_2)

# ─── AUTO REFRESH ────────────────────────────
if st.session_state.auto_refresh:
    time.sleep(60)
    st.session_state.last_refresh = datetime.now()
    st.rerun()
