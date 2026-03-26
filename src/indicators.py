"""
Technical indicators for strategy backtesting
"""
import pandas as pd
import numpy as np


def sma(data: pd.Series, period: int) -> pd.Series:
    """Simple Moving Average"""
    return data.rolling(window=period).mean()


def ema(data: pd.Series, period: int) -> pd.Series:
    """Exponential Moving Average"""
    return data.ewm(span=period, adjust=False).mean()


def rsi(data: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index"""
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi_values = 100 - (100 / (1 + rs))
    return rsi_values


def macd(data: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple:
    """MACD (Moving Average Convergence Divergence)
    Returns: (macd_line, signal_line, histogram)
    """
    ema_fast = ema(data, fast)
    ema_slow = ema(data, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def bollinger_bands(data: pd.Series, period: int = 20, std_dev: float = 2.0) -> tuple:
    """Bollinger Bands
    Returns: (upper_band, middle_band, lower_band)
    """
    middle = sma(data, period)
    std = data.rolling(window=period).std()
    upper = middle + (std * std_dev)
    lower = middle - (std * std_dev)
    return upper, middle, lower


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Average True Range - volatility indicator"""
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr_values = tr.rolling(window=period).mean()
    return atr_values


def calculate_rsi(data: pd.Series, period: int = 14) -> pd.Series:
    """Calculate RSI - alias for rsi function"""
    return rsi(data, period)


def calculate_all_indicators(df: pd.DataFrame, price_col: str = 'close') -> pd.DataFrame:
    """Calculate all indicators and add to dataframe"""
    df = df.copy()
    
    # Moving Averages
    df['sma_20'] = sma(df[price_col], 20)
    df['sma_50'] = sma(df[price_col], 50)
    df['ema_12'] = ema(df[price_col], 12)
    df['ema_26'] = ema(df[price_col], 26)
    
    # RSI
    df['rsi_14'] = rsi(df[price_col], 14)
    
    # MACD
    df['macd'], df['macd_signal'], df['macd_hist'] = macd(df[price_col])
    
    # Bollinger Bands
    df['bb_upper'], df['bb_middle'], df['bb_lower'] = bollinger_bands(df[price_col], 20)
    
    # ATR (if high/low available)
    if 'high' in df.columns and 'low' in df.columns:
        df['atr'] = atr(df['high'], df['low'], df[price_col], 14)
    
    return df
