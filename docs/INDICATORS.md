# 📈 Technical Indicators Module (`src/indicators.py`)

## Overview
The Indicators module provides technical analysis calculations used for strategy signal generation. All indicators are implemented using pure pandas/numpy for maximum efficiency.

---

## 📊 Indicators Reference

### 1. **Simple Moving Average (SMA)**

#### Function Signature
```python
def sma(data: pd.Series, period: int) -> pd.Series
```

#### Description
Calculates the simple moving average over a specified period.

#### Parameters
- `data` (pd.Series): Price series (typically closing prices)
- `period` (int): Number of periods to average

#### Returns
- `pd.Series`: SMA values aligned with input data

#### Formula
$$\text{SMA}_t = \frac{1}{n} \sum_{i=0}^{n-1} P_{t-i}$$

Where:
- $P_t$ = price at time t
- $n$ = period (e.g., 20)

#### Implementation
```python
return data.rolling(window=period).mean()
```

#### Use Case
- **Trend identification**: Price above SMA = uptrend, below = downtrend
- **Support/resistance**: SMA acts as dynamic support/resistance level
- **Crossover signals**: When fast MA crosses slow MA

#### Example
```python
import pandas as pd
from indicators import sma

prices = pd.Series([100, 101, 102, 101, 100, 99, 98, 97, 96, 95])
sma_20 = sma(prices, 5)  # 5-period SMA
# Result: [NaN, NaN, NaN, NaN, 101.2, 100.6, 100.0, 99.0, 98.0, 97.0]
```

---

### 2. **Exponential Moving Average (EMA)**

#### Function Signature
```python
def ema(data: pd.Series, period: int) -> pd.Series
```

#### Description
Calculates exponential moving average where recent prices are weighted more heavily.

#### Parameters
- `data` (pd.Series): Price series
- `period` (int): Number of periods (smoothing factor)

#### Returns
- `pd.Series`: EMA values

#### Formula
$$\text{EMA}_t = \alpha \cdot P_t + (1 - \alpha) \cdot \text{EMA}_{t-1}$$

Where:
- $\alpha = \frac{2}{n+1}$ (smoothing factor)
- $n$ = period

#### Implementation
```python
return data.ewm(span=period, adjust=False).mean()
```

#### Why EMA vs SMA?
- **EMA responds faster** to recent price changes
- **Less lagging** than SMA for trend detection
- **Better for shorter-term signals** (MACD, fast crossovers)

#### Example
```python
ema_12 = ema(prices, 12)
ema_26 = ema(prices, 26)
# EMA responds faster to price changes than SMA
```

---

### 3. **Relative Strength Index (RSI)**

#### Function Signature
```python
def rsi(data: pd.Series, period: int = 14) -> pd.Series
```

#### Description
Momentum oscillator measuring speed and magnitude of price changes. Ranges from 0-100.

#### Parameters
- `data` (pd.Series): Price series
- `period` (int): Lookback period (default: 14)

#### Returns
- `pd.Series`: RSI values (0-100)

#### Formula
$$\text{RSI} = 100 - \frac{100}{1 + RS}$$

Where:
- $RS = \frac{\text{Avg Gain}}{\text{Avg Loss}}$ over period

#### Implementation
```python
delta = data.diff()
gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
rs = gain / loss
rsi_values = 100 - (100 / (1 + rs))
```

#### Interpretation
| RSI Value | Signal | Action |
|-----------|--------|--------|
| < 30 | Oversold | Buy signal |
| 30-70 | Neutral | Monitor |
| > 70 | Overbought | Sell signal |

#### Use in EigenTrades
```python
# Entry: RSI < 30 (oversold)
# Exit: RSI > 70 (overbought)
df['entry_signal'] = (df['rsi'] < 30) & (df['close'] > df['sma_20'])
df['exit_signal'] = df['rsi'] > 70
```

#### Example
```python
rsi_14 = rsi(prices, 14)
# If RSI drops below 30: potential buy opportunity
# If RSI rises above 70: potential sell opportunity
```

---

### 4. **MACD (Moving Average Convergence Divergence)**

#### Function Signature
```python
def macd(data: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple
```

#### Description
Trend-following momentum indicator showing relationship between two moving averages.

#### Parameters
- `data` (pd.Series): Price series
- `fast` (int): Fast EMA period (default: 12)
- `slow` (int): Slow EMA period (default: 26)
- `signal` (int): Signal line EMA period (default: 9)

#### Returns
- `tuple`: (macd_line, signal_line, histogram)

#### Formula
$$\text{MACD} = \text{EMA}_{12} - \text{EMA}_{26}$$
$$\text{Signal Line} = \text{EMA}_9(\text{MACD})$$
$$\text{Histogram} = \text{MACD} - \text{Signal Line}$$

#### Implementation
```python
ema_fast = ema(data, 12)
ema_slow = ema(data, 26)
macd_line = ema_fast - ema_slow
signal_line = ema(macd_line, 9)
histogram = macd_line - signal_line
```

#### Trading Signals
- **Bullish**: MACD crosses above signal line OR MACD becomes positive
- **Bearish**: MACD crosses below signal line OR MACD becomes negative
- **Histogram divergence**: Indicates trend strength

#### Example
```python
macd_line, signal_line, histogram = macd(prices)
# Entry: MACD > Signal Line (bullish crossover)
# Exit: MACD < Signal Line (bearish crossover)
```

---

### 5. **Bollinger Bands**

#### Function Signature
```python
def bollinger_bands(data: pd.Series, period: int = 20, std_dev: float = 2.0) -> tuple
```

#### Description
Volatility indicator showing upper and lower bands around a moving average.

#### Parameters
- `data` (pd.Series): Price series
- `period` (int): MA period (default: 20)
- `std_dev` (float): Standard deviation multiplier (default: 2.0)

#### Returns
- `tuple`: (upper_band, middle_band, lower_band)

#### Formula
$$\text{Middle} = \text{SMA}_{20}$$
$$\text{Upper} = \text{Middle} + (2.0 \times \text{StdDev}_{20})$$
$$\text{Lower} = \text{Middle} - (2.0 \times \text{StdDev}_{20})$$

#### Implementation
```python
middle = sma(data, period)
std = data.rolling(window=period).std()
upper = middle + (std * std_dev)
lower = middle - (std * std_dev)
```

#### Trading Interpretation
- **Price at lower band**: Oversold (potential buy)
- **Price at upper band**: Overbought (potential sell)
- **Band width**: Wide = high volatility, Narrow = low volatility

#### Example
```python
upper, middle, lower = bollinger_bands(prices, 20, 2.0)
# Entry: Price touches lower band + RSI < 30
# Exit: Price touches upper band + RSI > 70
```

---

### 6. **Average True Range (ATR)**

#### Function Signature
```python
def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series
```

#### Description
Volatility indicator measuring average range of price movement.

#### Parameters
- `high` (pd.Series): High prices
- `low` (pd.Series): Low prices
- `close` (pd.Series): Closing prices
- `period` (int): Lookback period (default: 14)

#### Returns
- `pd.Series`: ATR values

#### Formula
$$\text{TR} = \max(H - L, |H - C_{prev}|, |L - C_{prev}|)$$
$$\text{ATR} = \text{SMA}_{14}(\text{TR})$$

Where:
- $H$ = High, $L$ = Low, $C$ = Close

#### Implementation
```python
tr1 = high - low
tr2 = abs(high - close.shift())
tr3 = abs(low - close.shift())
tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
atr_values = tr.rolling(window=period).mean()
```

#### Use Cases
- **Stop loss placement**: ATR × 2 below entry price
- **Position sizing**: Smaller position if ATR is high (volatile)
- **Volatility filter**: Skip trades if ATR > threshold

#### Example
```python
atr_14 = atr(df['high'], df['low'], df['close'], 14)
# Stop loss = Entry price - (ATR × 2)
stop_loss = entry_price - (atr_14 * 2)
```

---

## 🔗 Combined Indicators Function

#### Function Signature
```python
def calculate_all_indicators(df: pd.DataFrame, price_col: str = 'close') -> pd.DataFrame
```

#### Description
Convenience function that calculates all indicators at once and adds them to the dataframe.

#### Parameters
- `df` (pd.DataFrame): OHLCV dataframe
- `price_col` (str): Column name for prices (default: 'close')

#### Returns
- `pd.DataFrame`: Original dataframe with new indicator columns

#### Added Columns
```
'sma_20'      # 20-period Simple Moving Average
'sma_50'      # 50-period Simple Moving Average
'ema_12'      # 12-period Exponential Moving Average
'ema_26'      # 26-period Exponential Moving Average
'rsi_14'      # 14-period Relative Strength Index
'macd'        # MACD line
'macd_signal' # MACD signal line
'macd_hist'   # MACD histogram
'bb_upper'    # Bollinger Bands upper band
'bb_middle'   # Bollinger Bands middle band
'bb_lower'    # Bollinger Bands lower band
'atr'         # Average True Range (if high/low available)
```

#### Example
```python
import pandas as pd
from indicators import calculate_all_indicators

df = pd.read_csv('data/BANKNIFTY_active_futures.csv')
df = calculate_all_indicators(df, price_col='close')

# Now df has all indicators
print(df[['close', 'sma_20', 'rsi_14', 'macd']].head())
```

---

## 📊 Performance Characteristics

| Indicator | Calculation Speed | Lag | Best Use |
|-----------|-------------------|-----|----------|
| SMA | Very Fast | High | Trend confirmation |
| EMA | Very Fast | Medium | Fast signals |
| RSI | Fast | Low | Overbought/oversold |
| MACD | Medium | Medium | Trend changes |
| Bollinger Bands | Fast | Medium | Volatility ranges |
| ATR | Medium | Low | Position sizing |

---

## 🎯 Strategy Integration

All indicators are designed to work together in the `Strategy` module:

```python
# Example from strategy.py
df['rsi'] = calculate_rsi(df['close'], 14)
df['sma'] = sma(df['close'], 20)
df['entry_signal'] = (df['rsi'] < 30) & (df['close'] > df['sma'])
df['exit_signal'] = df['rsi'] > 70

strategy = BacktestStrategy(initial_capital=100000)
results = strategy.backtest(df, 'entry_signal', 'exit_signal')
```

---

## 🔍 Common Patterns

### Oversold/Overbought Strategy
```python
df['rsi'] = rsi(df['close'], 14)
df['entry_signal'] = df['rsi'] < 30      # Oversold
df['exit_signal'] = df['rsi'] > 70       # Overbought
```

### Trend Following (MACD)
```python
macd_line, signal_line, hist = macd(df['close'])
df['entry_signal'] = macd_line > signal_line
df['exit_signal'] = macd_line < signal_line
```

### Volatility Breakout
```python
upper, middle, lower = bollinger_bands(df['close'], 20, 2.0)
df['entry_signal'] = df['close'] > upper
df['exit_signal'] = df['close'] < middle
```

### Combined (RSI + MA)
```python
df['rsi'] = rsi(df['close'], 14)
df['sma'] = sma(df['close'], 20)
# Buy: Oversold + trending up
df['entry_signal'] = (df['rsi'] < 30) & (df['close'] > df['sma'])
df['exit_signal'] = df['rsi'] > 70
```

---

## ⚠️ Important Notes

1. **NaN values**: First `period` values will be NaN (warm-up period)
2. **No look-ahead bias**: Indicators use only past data
3. **Data quality**: Requires complete OHLCV data (no missing values)
4. **Normalization**: All indicators work with raw prices (no need to normalize)

---

**See also:**
- [Strategy Module](STRATEGY.md)
- [Risk Management](RISK_MANAGEMENT.md)
- [Full Documentation](README.md)
