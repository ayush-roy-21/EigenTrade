# 🎯 Strategy & Backtesting Module (`src/strategy.py`)

## Overview
The Strategy module provides a complete backtesting engine with position tracking, trade history, and P&L calculation. It enables realistic simulation of trading strategies on historical data.

---

## 📋 Core Classes

### 1. **Trade Class**

#### Definition
```python
@dataclass
class Trade:
    """Single trade record"""
    entry_date: str
    entry_price: float
    exit_date: str
    exit_price: float
    quantity: int
    side: str = "BUY"
    reason: str = ""
    pnl: float = 0.0
    pnl_pct: float = 0.0
```

#### Description
Represents a single completed trade with entry, exit, and P&L details.

#### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `entry_date` | str | Date trade was entered |
| `entry_price` | float | Price at which trade was entered |
| `exit_date` | str | Date trade was exited |
| `exit_price` | float | Price at which trade was exited |
| `quantity` | int | Number of shares/contracts |
| `side` | str | "BUY" or "SELL" (currently only BUY supported) |
| `reason` | str | Why the trade was entered/exited |
| `pnl` | float | Profit/loss in dollars |
| `pnl_pct` | float | Profit/loss as percentage of entry |

#### Auto-Calculated on Init
The `__post_init__` method automatically calculates:
```python
def __post_init__(self):
    if self.entry_price > 0 and self.exit_price > 0:
        self.pnl = (self.exit_price - self.entry_price) * self.quantity
        self.pnl_pct = ((self.exit_price - self.entry_price) / self.entry_price) * 100
```

#### Formula
$$\text{P\&L} = (\text{Exit Price} - \text{Entry Price}) \times \text{Quantity}$$
$$\text{P\&L\%} = \frac{\text{Exit Price} - \text{Entry Price}}{\text{Entry Price}} \times 100$$

#### Example
```python
trade = Trade(
    entry_date="2024-01-15",
    entry_price=100.0,
    exit_date="2024-01-20",
    exit_price=105.0,
    quantity=100,
    reason="RSI < 30 AND price > SMA20"
)
# Auto-calculated:
# trade.pnl = 500.0
# trade.pnl_pct = 5.0
```

---

### 2. **BacktestStrategy Class**

Main backtesting engine for strategy simulation.

#### Constructor
```python
def __init__(self, 
             initial_capital: float = 100000,
             position_size_pct: float = 0.95,
             transaction_cost: float = 0.001):
```

#### Parameters
- `initial_capital` (float): Starting account balance
- `position_size_pct` (float): % of available capital to use per trade
- `transaction_cost` (float): Slippage/commission as decimal (e.g., 0.001 = 0.1%)

#### Attributes
```python
self.initial_capital: float          # Starting capital
self.current_capital: float          # Available cash
self.position_size_pct: float        # Position sizing %
self.transaction_cost: float         # Commission/slippage
self.trades: List[Trade]             # Completed trades
self.equity_curve: List[float]       # Running equity history
self.positions: Dict[str, Dict]      # Open positions by symbol
```

#### Example Initialization
```python
strategy = BacktestStrategy(
    initial_capital=100000,      # $100k account
    position_size_pct=0.95,      # Use 95% per trade
    transaction_cost=0.001       # 0.1% commission
)
```

---

## 🔄 Core Methods

### **Method: enter_position()**

#### Signature
```python
def enter_position(self, 
                   symbol: str, 
                   date: str, 
                   price: float, 
                   quantity: int, 
                   reason: str = "") -> bool
```

#### Description
Opens a long position (buy signal).

#### Parameters
- `symbol` (str): Asset identifier
- `date` (str): Entry date
- `price` (float): Entry price
- `quantity` (int): Number of shares to buy
- `reason` (str): Signal reason

#### Returns
- `bool`: True if entry successful, False if insufficient capital or position already open

#### Logic
```python
cost = price * quantity * (1 + self.transaction_cost)

# Check: Sufficient capital AND no existing position
if cost <= self.current_capital and symbol not in self.positions:
    self.positions[symbol] = {
        'entry_date': date,
        'entry_price': price,
        'quantity': quantity,
        'reason': reason
    }
    self.current_capital -= cost  # Deduct cost from cash
    return True
return False
```

#### Example
```python
success = strategy.enter_position(
    symbol="BANKNIFTY",
    date="2024-01-15",
    price=100.0,
    quantity=100,
    reason="RSI < 30"
)
if success:
    print("Position opened")
    print(f"Remaining cash: ${strategy.current_capital:.2f}")
```

---

### **Method: exit_position()**

#### Signature
```python
def exit_position(self, 
                  symbol: str, 
                  date: str, 
                  price: float, 
                  reason: str = "") -> bool
```

#### Description
Closes an open position (sell signal).

#### Parameters
- `symbol` (str): Asset identifier
- `date` (str): Exit date
- `price` (float): Exit price
- `reason` (str): Exit reason

#### Returns
- `bool`: True if exit successful, False if no open position

#### Logic
```python
if symbol not in self.positions:
    return False

pos = self.positions[symbol]
proceeds = price * pos['quantity'] * (1 - self.transaction_cost)

# Create trade record
trade = Trade(
    entry_date=pos['entry_date'],
    entry_price=pos['entry_price'],
    exit_date=date,
    exit_price=price,
    quantity=pos['quantity'],
    side="BUY",
    reason=reason
)

self.trades.append(trade)
self.current_capital += proceeds  # Add proceeds to cash
del self.positions[symbol]        # Close position
return True
```

#### P&L Calculation
When a trade exits, P&L is calculated as:
$$\text{Proceeds} = \text{Exit Price} \times \text{Quantity} \times (1 - \text{Commission})$$
$$\text{P\&L} = \text{Proceeds} - \text{Entry Cost}$$

#### Example
```python
success = strategy.exit_position(
    symbol="BANKNIFTY",
    date="2024-01-20",
    price=105.0,
    reason="RSI > 70"
)
if success:
    print("Position closed")
    print(f"Trade P&L: ${strategy.trades[-1].pnl:.2f}")
```

---

### **Method: get_equity()**

#### Signature
```python
def get_equity(self) -> float
```

#### Description
Calculates current total equity (cash + position mark-to-market).

#### Logic
```python
positions_value = sum(
    pos['quantity'] * pos['entry_price'] 
    for pos in self.positions.values()
)
return self.current_capital + positions_value
```

#### Note
Uses entry price for open positions (not current price) for conservative valuation.

#### Example
```python
total_equity = strategy.get_equity()
print(f"Current equity: ${total_equity:.2f}")
```

---

### **Method: backtest()**

#### Signature
```python
def backtest(self, 
             df: pd.DataFrame, 
             entry_signal_col: str,
             exit_signal_col: str,
             price_col: str = 'close',
             symbol: str = 'STOCK') -> Dict
```

#### Description
Main backtesting loop that simulates strategy execution on historical data.

#### Parameters
- `df` (pd.DataFrame): OHLCV data with signal columns
- `entry_signal_col` (str): Column name with True/False entry signals
- `exit_signal_col` (str): Column name with True/False exit signals
- `price_col` (str): Price column to use (default: 'close')
- `symbol` (str): Asset symbol (default: 'STOCK')

#### Returns
- `Dict`: Results dictionary with performance metrics

#### Backtest Loop Logic
```
For each bar in dataframe:
  1. Check exit signal
     IF position_open AND exit_signal:
        - Close position at current price
        - Record trade
        - Add equity to curve
  
  2. Check entry signal
     ELIF NOT position_open AND entry_signal:
        - Calculate quantity based on available capital
        - Open position at current price
        - Add equity to curve
  
  3. Mark-to-market
     IF position_open:
        - Update equity curve with current position value

After loop:
  Close any remaining open positions at last price
  Calculate all performance metrics
```

#### Flow Diagram
```
┌─────────────────────────────┐
│ Start Backtest              │
│ - Initialize equity curve   │
│ - position_open = False     │
└──────────────┬──────────────┘
               │
               ▼
    ┌──────────────────────┐
    │ For each bar:        │
    │ 1. Check exit signal │
    │ 2. Check entry signal│
    │ 3. Mark-to-market    │
    └──────────┬───────────┘
               │
        ┌──────┴──────┐
        │             │
        ▼             ▼
   Exit?         Entry?
        │             │
        ▼             ▼
   Close      Calculate qty
   Record     Open position
   Trade
        │             │
        └──────┬──────┘
               │
               ▼
      Mark-to-market
      Update equity
               │
               ▼
      ┌───────────────┐
      │ End of data?  │
      └───┬───────┬───┘
          │ YES   │ NO
          ▼       └────────┐
      Close open          │
      positions           │
          │               │
          ▼               ▼
      Calculate results  Continue
```

#### Example
```python
import pandas as pd
from indicators import calculate_rsi, sma
from strategy import BacktestStrategy

# Load data
df = pd.read_csv('data/BANKNIFTY_active_futures.csv')

# Generate signals
df['rsi'] = calculate_rsi(df['close'], 14)
df['sma'] = sma(df['close'], 20)
df['entry_signal'] = (df['rsi'] < 30) & (df['close'] > df['sma'])
df['exit_signal'] = df['rsi'] > 70

# Run backtest
strategy = BacktestStrategy(initial_capital=100000)
results = strategy.backtest(
    df,
    entry_signal_col='entry_signal',
    exit_signal_col='exit_signal',
    symbol='BANKNIFTY'
)

# View results
print(f"Total Return: {results['total_return_pct']:.2f}%")
print(f"Number of Trades: {results['num_trades']}")
print(f"Win Rate: {results['win_rate_pct']:.1f}%")
```

---

## 📊 Results Dictionary

The `backtest()` method returns a dictionary with:

#### Key Metrics
```python
{
    'initial_capital': 100000,           # Starting balance
    'final_capital': 123450.50,          # Ending balance
    'total_return_pct': 23.45,           # Total return %
    'num_trades': 24,                    # Number of trades
    'winning_trades': 15,                # Trades with positive P&L
    'losing_trades': 9,                  # Trades with negative P&L
    'win_rate_pct': 62.5,                # % of winning trades
    'volatility_pct': 14.3,              # Annual volatility
    'sharpe_ratio': 1.32,                # Risk-adjusted return
    'total_pnl': 23450.50,               # Total P&L in dollars
    'avg_win': 1563.33,                  # Average winning trade
    'avg_loss': -1230.56,                # Average losing trade
    'trades': [...],                     # List of Trade objects
    'equity_curve': [100000, 100150, ...] # Daily equity history
}
```

#### Calculation Details

**Total Return %:**
$$\text{Return} = \frac{\text{Final Capital} - \text{Initial Capital}}{\text{Initial Capital}} \times 100$$

**Volatility %:**
$$\text{Volatility} = \text{StdDev}(\text{Daily Returns}) \times \sqrt{252}$$

**Sharpe Ratio:**
$$\text{Sharpe} = \frac{\text{Annualized Return} - \text{Risk-Free Rate}}{\text{Volatility}}$$

**Win Rate %:**
$$\text{Win Rate} = \frac{\text{Number of Winning Trades}}{\text{Total Trades}} \times 100$$

---

## 🎲 Helper Functions

### **calculate_rsi()**
```python
def calculate_rsi(data: pd.Series, period: int = 14) -> pd.Series
```
Calculates RSI. See [Indicators.md](INDICATORS.md) for details.

### **create_simple_strategy()**
```python
def create_simple_strategy(df: pd.DataFrame, 
                           rsi_lower: float = 30,
                           rsi_upper: float = 70,
                           ma_period: int = 20) -> pd.DataFrame
```

#### Description
Creates entry/exit signals using RSI + MA strategy.

#### Strategy Logic
```
ENTRY:  RSI < 30 AND Close > SMA20
        (Oversold + trending up)

EXIT:   RSI > 70
        (Overbought)
```

#### Example
```python
df = create_simple_strategy(df, rsi_lower=30, rsi_upper=70, ma_period=20)
# Adds 'sma', 'rsi', 'entry_signal', 'exit_signal' columns
```

---

## 🔍 Strategy Considerations

### Position Sizing
By default, uses this formula:
$$\text{Quantity} = \left\lfloor \frac{\text{Available Capital} \times \text{Position Size \%}}{\text{Entry Price}} \right\rfloor$$

For $100k account with 95% position size:
- Entry price $100 → Buy 950 shares
- Entry price $50 → Buy 1900 shares

### Transaction Costs
Commission/slippage deducted on both entry and exit:
- Entry cost: `price × qty × (1 + 0.001)` (0.1% commission)
- Exit proceeds: `price × qty × (1 - 0.001)` (0.1% slippage)

### Edge Cases
- **No signals**: If no entry/exit signals, backtest returns empty trades list
- **Single trade**: Handles strategies with only one trade
- **Multiple positions**: Current implementation only opens one position at a time per symbol
- **Open positions at end**: Automatically closed at final price

---

## ⚠️ Backtesting Assumptions

1. **Perfect execution**: Orders filled at signal price (no slippage beyond fixed %)
2. **Sufficient liquidity**: Can always execute desired quantity
3. **No gaps**: Assumes price touches signal price within bar
4. **No leverage**: Uses only available capital
5. **No short selling**: Only long positions
6. **Daily data**: Works best with daily OHLC data

---

## 🎯 Advanced Patterns

### Multi-Condition Entry
```python
df['entry_signal'] = (
    (df['rsi'] < 30) &           # Oversold
    (df['close'] > df['sma_20']) & # Uptrend
    (df['macd'] > df['macd_signal']) # MACD bullish
)
```

### Time-Based Exit
```python
# Exit after N bars (not shown in current code)
df['bars_in_trade'] = df['entry_signal'].cumsum()
df['exit_signal'] = df['bars_in_trade'] > 10  # Exit after 10 bars
```

### Multiple Timeframe
```python
# Generate signals on daily, execute on hourly
daily_signal = calculate_rsi(daily_df['close'], 14) < 30
hourly_df['entry_signal'] = daily_signal & (hourly_df['rsi'] < 30)
```

---

## 📈 Example Complete Backtest

```python
import pandas as pd
from indicators import sma, rsi
from strategy import BacktestStrategy

# 1. Load data
df = pd.read_csv('data/BANKNIFTY_active_futures.csv')

# 2. Calculate indicators
df['sma_20'] = sma(df['close'], 20)
df['rsi_14'] = rsi(df['close'], 14)

# 3. Generate signals
df['entry_signal'] = (df['rsi_14'] < 30) & (df['close'] > df['sma_20'])
df['exit_signal'] = df['rsi_14'] > 70

# 4. Run backtest
strategy = BacktestStrategy(
    initial_capital=100000,
    position_size_pct=0.95,
    transaction_cost=0.001
)
results = strategy.backtest(
    df,
    entry_signal_col='entry_signal',
    exit_signal_col='exit_signal',
    price_col='close',
    symbol='BANKNIFTY'
)

# 5. Analyze results
print("=" * 50)
print("BACKTEST RESULTS")
print("=" * 50)
print(f"Total Return: {results['total_return_pct']:.2f}%")
print(f"Number of Trades: {results['num_trades']}")
print(f"Winning Trades: {results['winning_trades']}")
print(f"Losing Trades: {results['losing_trades']}")
print(f"Win Rate: {results['win_rate_pct']:.1f}%")
print(f"Sharpe Ratio: {results['sharpe_ratio']:.2f}")
print(f"Volatility: {results['volatility_pct']:.2f}%")
print("\n" + "=" * 50)
print("TRADE HISTORY")
print("=" * 50)
for trade in results['trades'][:5]:  # First 5 trades
    print(f"{trade.entry_date} → {trade.exit_date}")
    print(f"  Entry: ${trade.entry_price:.2f}")
    print(f"  Exit: ${trade.exit_price:.2f}")
    print(f"  P&L: ${trade.pnl:.2f} ({trade.pnl_pct:+.2f}%)")
```

---

**See also:**
- [Indicators Module](INDICATORS.md)
- [Risk Management](RISK_MANAGEMENT.md)
- [Full Documentation](README.md)
