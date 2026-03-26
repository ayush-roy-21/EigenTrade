# ⚠️ Risk Management Module (`src/utils.py`)

## Overview
The Risk Management module provides professional risk metrics, position sizing, and equity monitoring tools. Implements institutional-grade risk calculations used by professional traders.

---

## 📊 RiskMetrics Class

### Purpose
Calculates comprehensive risk statistics from a series of returns.

### Constructor
```python
def __init__(self, returns: pd.Series, risk_free_rate: float = 0.02):
```

#### Parameters
- `returns` (pd.Series): Daily returns as decimals (e.g., 0.05 = +5%)
- `risk_free_rate` (float): Risk-free rate for Sharpe calculation (default: 2% annual)

#### Example Initialization
```python
import pandas as pd
from utils import RiskMetrics

# Calculate returns from equity curve
equity = pd.Series([100000, 100500, 101200, 100800, ...])
returns = equity.pct_change().dropna()

# Create risk metrics calculator
risk = RiskMetrics(returns, risk_free_rate=0.02)
```

---

## 📈 Metrics Methods

### 1. **total_return()**

#### Signature
```python
def total_return(self) -> float
```

#### Description
Calculates cumulative return from inception to end of period.

#### Formula
$$\text{Total Return} = \left(\prod_{i=1}^{n} (1 + r_i)\right) - 1$$

Where $r_i$ = return on day $i$

#### Implementation
```python
return ((self.returns + 1).prod() - 1) * 100
```

#### Example
```python
total_ret = risk.total_return()
# Result: 23.45 (meaning +23.45%)
```

#### Interpretation
- Positive: Strategy gained money
- Negative: Strategy lost money
- **Note**: Does NOT account for volatility (see Sharpe ratio instead)

---

### 2. **annualized_return()**

#### Signature
```python
def annualized_return(self) -> float
```

#### Description
Converts total return to annual percentage rate (assuming 252 trading days/year).

#### Formula
$$\text{Annualized Return} = \left[(1 + \text{Total Return})^{\frac{252}{n}}\right] - 1$$

Where:
- $n$ = number of days in period
- 252 = trading days in year

#### Implementation
```python
total = self.total_return() / 100
periods = len(self.returns) / 252
if periods > 0:
    return ((1 + total) ** (1 / periods) - 1) * 100
return 0
```

#### Example
```python
# 100 days of returns
ann_ret = risk.annualized_return()
# If total return = 5% over 100 days:
# Annualized = (1.05)^(252/100) - 1 = 12.67%
```

#### Use Case
Compares strategies across different time periods fairly.

---

### 3. **volatility()**

#### Signature
```python
def volatility(self) -> float
```

#### Description
Calculates annualized volatility (standard deviation of returns).

#### Formula
$$\text{Volatility} = \text{StdDev}(\text{Returns}) \times \sqrt{252}$$

Where:
- StdDev = standard deviation of daily returns
- 252 = trading days per year

#### Implementation
```python
return self.returns.std() * np.sqrt(252) * 100
```

#### Example
```python
vol = risk.volatility()
# Result: 14.3 (meaning 14.3% annualized volatility)
```

#### Interpretation
| Volatility | Risk Level | Trading Style |
|-----------|-----------|---------------|
| < 5% | Very Low | Long-term trend |
| 5-15% | Low | Swing trading |
| 15-30% | Moderate | Day trading |
| > 30% | High | Scalping |

---

### 4. **sharpe_ratio()**

#### Signature
```python
def sharpe_ratio(self) -> float
```

#### Description
Risk-adjusted return metric. Returns earned per unit of risk taken.

#### Formula
$$\text{Sharpe Ratio} = \frac{\text{Annualized Return} - \text{Risk-Free Rate}}{\text{Volatility}}$$

#### Implementation
```python
excess_return = self.annualized_return() / 100 - self.risk_free_rate
vol = self.volatility() / 100
if vol > 0:
    return excess_return / vol
return 0
```

#### Example
```python
sharpe = risk.sharpe_ratio()
# Result: 1.45

# Interpretation:
# Returns 1.45% for every 1% of risk taken
```

#### Interpretation Guide
| Sharpe Ratio | Quality | Assessment |
|-------------|---------|------------|
| < 0.5 | Poor | Lose money on risk-adjusted basis |
| 0.5 - 1.0 | Average | Acceptable for some traders |
| 1.0 - 2.0 | Good | Strong risk-adjusted returns |
| 2.0 - 3.0 | Excellent | Professional quality |
| > 3.0 | Outstanding | Institutional quality |

**EigenTrades Target:** Sharpe > 1.0 (good risk-adjusted returns)

---

### 5. **max_drawdown()**

#### Signature
```python
def max_drawdown(self) -> float
```

#### Description
Largest peak-to-trough decline in equity. Most important risk metric.

#### Formula
$$\text{Drawdown}_t = \frac{V_t - \text{Peak}}{V_{\text{Peak}}}$$
$$\text{Max Drawdown} = \min(\text{Drawdown}_t)$$

Where:
- $V_t$ = equity at time t
- Peak = running maximum equity

#### Implementation
```python
cumulative = (1 + self.returns).cumprod()
running_max = cumulative.expanding().max()
drawdown = (cumulative - running_max) / running_max
return drawdown.min() * 100
```

#### Example
```python
max_dd = risk.max_drawdown()
# Result: -15.3 (meaning largest decline was -15.3%)

# Timeline:
# Peak equity: $100,000
# Trough: $84,700
# Drawdown: ($84,700 - $100,000) / $100,000 = -15.3%
```

#### Visualization
```
Equity Curve:
$100,000 ┌─────────╲
         │         ╲
 $90,000 │          ╲──────
         │          (MAX DD)
 $80,000 │          
         └─────────────────
         
Max Drawdown = -15.3%
```

#### Importance
- **Most traded metric** by institutional investors
- **Determines margin requirements**
- **Psychological impact**: Hardest part of trading
- **Risk management**: Set position size to keep DD < 20%

---

### 6. **win_rate()**

#### Signature
```python
def win_rate(self, threshold: float = 0.0) -> float
```

#### Description
Percentage of periods with positive returns.

#### Formula
$$\text{Win Rate} = \frac{\text{Count of Returns} > \text{Threshold}}{\text{Total Periods}} \times 100$$

#### Implementation
```python
wins = (self.returns > threshold).sum()
total = len(self.returns)
return (wins / total * 100) if total > 0 else 0
```

#### Example
```python
win_rate = risk.win_rate(threshold=0.0)
# Result: 62.5 (62.5% of days were profitable)
```

#### Interpretation
| Win Rate | Strategy Type |
|----------|---------------|
| 30-40% | High-probability trend following |
| 40-50% | Balanced strategy |
| 50-60% | Mean reversion |
| 60-70% | Very high quality |
| > 70% | Suspiciously high (check for overfitting) |

**Note:** High win rate + low Sharpe = small wins with occasional large losses

---

### 7. **profit_factor()**

#### Signature
```python
def profit_factor(self) -> float
```

#### Description
Ratio of total gains to total losses. Indicates strategy robustness.

#### Formula
$$\text{Profit Factor} = \frac{\text{Sum of Gains}}{\text{Sum of Losses}}$$

#### Implementation
```python
gains = self.returns[self.returns > 0].sum()
losses = abs(self.returns[self.returns < 0].sum())
return gains / losses if losses != 0 else 0
```

#### Example
```python
pf = risk.profit_factor()
# Result: 2.15

# Interpretation:
# For every $1 lost, make $2.15
```

#### Interpretation
| Profit Factor | Assessment |
|--------------|------------|
| < 1.0 | Losing strategy |
| 1.0 - 1.5 | Marginal |
| 1.5 - 2.0 | Good |
| 2.0 - 3.0 | Excellent |
| > 3.0 | Outstanding |

---

### 8. **get_all_metrics()**

#### Signature
```python
def get_all_metrics(self) -> dict
```

#### Description
Calculates and returns all risk metrics in one call.

#### Returns
Dictionary with all metrics:
```python
{
    'Total Return (%)': 23.45,
    'Annualized Return (%)': 18.92,
    'Volatility (%)': 14.3,
    'Sharpe Ratio': 1.32,
    'Max Drawdown (%)': -8.5,
    'Win Rate (%)': 62.5,
    'Profit Factor': 2.15
}
```

#### Example
```python
metrics = risk.get_all_metrics()
for metric_name, value in metrics.items():
    print(f"{metric_name}: {value:.2f}")
```

---

## 💰 Position Sizing Function

### **position_sizing()**

#### Signature
```python
def position_sizing(account_size: float, 
                   risk_pct: float, 
                   entry: float, 
                   stop_loss: float) -> float
```

#### Description
Calculates optimal number of shares to trade based on risk tolerance.

#### Parameters
- `account_size` (float): Total account balance
- `risk_pct` (float): % of account willing to risk (e.g., 2.0 for 2%)
- `entry` (float): Entry price
- `stop_loss` (float): Stop loss price

#### Returns
- `float`: Number of shares to buy

#### Formula
$$\text{Risk Amount} = \text{Account} \times \text{Risk \%}$$
$$\text{Price Risk} = |\text{Entry} - \text{Stop Loss}|$$
$$\text{Position Size} = \left\lfloor \frac{\text{Risk Amount}}{\text{Price Risk}} \right\rfloor$$

#### Implementation
```python
risk_amount = account_size * (risk_pct / 100)
price_risk = abs(entry - stop_loss)

if price_risk > 0:
    position_size = risk_amount / price_risk
    return max(0, int(position_size))
return 0
```

#### Example Calculation

**Scenario:**
- Account: $100,000
- Entry price: $100
- Stop loss: $95
- Risk per trade: 2%

**Calculation:**
```
Risk Amount = $100,000 × 2% = $2,000
Price Risk = |$100 - $95| = $5
Position Size = $2,000 / $5 = 400 shares

Max Loss = 400 × $5 = $2,000
Account Risk = $2,000 / $100,000 = 2% ✓
```

#### Code Example
```python
from utils import position_sizing

shares = position_sizing(
    account_size=100000,
    risk_pct=2.0,
    entry=100.0,
    stop_loss=95.0
)
print(f"Buy {shares} shares")
# Output: Buy 400 shares
```

---

## 📊 Drawdown Tracking

### **calculate_drawdown_series()**

#### Signature
```python
def calculate_drawdown_series(equity_curve: pd.Series) -> pd.Series
```

#### Description
Calculates running drawdown at each point in time.

#### Parameters
- `equity_curve` (pd.Series): Time series of account equity

#### Returns
- `pd.Series`: Drawdown % at each point

#### Formula
$$\text{Drawdown}_t = \frac{V_t - \text{Peak}}{V_{\text{Peak}}} \times 100$$

#### Implementation
```python
running_max = equity_curve.expanding().max()
drawdown = (equity_curve - running_max) / running_max * 100
return drawdown
```

#### Example
```python
equity = pd.Series([100, 105, 110, 100, 95, 105])
dd = calculate_drawdown_series(equity)
# Result: [0.0, 0.0, 0.0, -9.09, -13.64, -4.55]

# Timeline:
# Day 0: $100 (peak)
# Day 1: $105 (new peak)
# Day 2: $110 (new peak)
# Day 3: $100 (-9.09% from peak)
# Day 4: $95  (-13.64% from peak) ← MAX DRAWDOWN
# Day 5: $105 (-4.55% from peak)
```

#### Use in Streamlit
```python
# In tab_risk_dashboard()
drawdown_series = calculate_drawdown_series(equity_series)
st.area_chart(drawdown_series * 100, color="#FF6B6B")
```

---

### **check_risk_limits()**

#### Signature
```python
def check_risk_limits(current_drawdown: float, 
                     max_drawdown_limit: float) -> bool
```

#### Description
Checks if current drawdown exceeds acceptable limit.

#### Parameters
- `current_drawdown` (float): Current drawdown % (e.g., -8.5)
- `max_drawdown_limit` (float): Maximum acceptable (e.g., -20.0)

#### Returns
- `bool`: True if within limits, False if exceeded

#### Implementation
```python
return abs(current_drawdown) <= abs(max_drawdown_limit)
```

#### Example
```python
from utils import check_risk_limits

# Current: -8.5%, Limit: -20%
ok = check_risk_limits(-8.5, -20.0)
print(ok)  # True

# Current: -25%, Limit: -20%
ok = check_risk_limits(-25.0, -20.0)
print(ok)  # False - ALERT!
```

---

## 🎯 Professional Risk Management Framework

### Risk Tiering System
```
Account Risk Level:    Max Position Size:    Max Drawdown Target:
─────────────────────────────────────────────────────────────
Conservative          1-2%                   5-10%
Balanced              2-3%                   10-15%
Aggressive            3-5%                   15-20%
Very Aggressive       > 5%                   > 20%
```

### Position Sizing Examples

**Example 1: Conservative Trader**
```python
# $50k account, risk 1% per trade, $20 stop
position_sizing(50000, 1.0, 100.0, 80.0)
# = $500 risk / $20 stop = 25 shares
```

**Example 2: Balanced Trader**
```python
# $100k account, risk 2% per trade, $5 stop
position_sizing(100000, 2.0, 100.0, 95.0)
# = $2,000 risk / $5 stop = 400 shares
```

**Example 3: Aggressive Trader**
```python
# $200k account, risk 5% per trade, $2 stop
position_sizing(200000, 5.0, 100.0, 98.0)
# = $10,000 risk / $2 stop = 5,000 shares
```

---

## 📈 Complete Risk Analysis Example

```python
import pandas as pd
from utils import RiskMetrics, position_sizing, calculate_drawdown_series
from strategy import BacktestStrategy

# Run backtest (see Strategy.md for details)
strategy = BacktestStrategy(initial_capital=100000)
results = strategy.backtest(df, 'entry_signal', 'exit_signal')

# Calculate risk metrics
equity_series = pd.Series(results['equity_curve'])
returns = equity_series.pct_change().dropna()
risk = RiskMetrics(returns, risk_free_rate=0.02)

# Get all metrics
metrics = risk.get_all_metrics()
print("=" * 60)
print("RISK ANALYSIS")
print("=" * 60)
for name, value in metrics.items():
    print(f"{name:.<30} {value:>6.2f}")

# Check against risk limits
print("\n" + "=" * 60)
print("RISK ASSESSMENT")
print("=" * 60)

max_dd = metrics['Max Drawdown (%)']
if max_dd < -20:
    print("🔴 CRITICAL: Drawdown exceeds 20% limit!")
elif max_dd < -10:
    print("🟡 WARNING: Drawdown exceeds 10% limit")
else:
    print("🟢 OK: Drawdown within acceptable range")

sharpe = metrics['Sharpe Ratio']
if sharpe > 1.0:
    print(f"🟢 GOOD: Sharpe ratio {sharpe:.2f} indicates good risk-adjusted returns")
else:
    print(f"🟡 WEAK: Sharpe ratio {sharpe:.2f} below 1.0 target")

# Position sizing calculation
print("\n" + "=" * 60)
print("POSITION SIZING RECOMMENDATION")
print("=" * 60)

initial_capital = results['initial_capital']
entry_price = 100.0
stop_loss = 95.0
risk_pct = 2.0

shares = position_sizing(initial_capital, risk_pct, entry_price, stop_loss)
max_loss = shares * abs(entry_price - stop_loss)
account_risk = max_loss / initial_capital * 100

print(f"Entry Price: ${entry_price}")
print(f"Stop Loss: ${stop_loss}")
print(f"Position Size: {shares} shares")
print(f"Max Loss: ${max_loss:,.2f}")
print(f"Account Risk: {account_risk:.2f}%")

# Drawdown analysis
print("\n" + "=" * 60)
print("DRAWDOWN ANALYSIS")
print("=" * 60)

drawdown = calculate_drawdown_series(equity_series)
print(f"Current Drawdown: {drawdown.iloc[-1]:.2f}%")
print(f"Max Drawdown: {drawdown.min():.2f}%")
print(f"Avg Drawdown: {drawdown[drawdown < 0].mean():.2f}%")
```

---

## ⚠️ Risk Management Best Practices

1. **Always use stop losses**: Set max acceptable loss before trading
2. **Size positions for max drawdown**: Not just expected return
3. **Monitor Sharpe ratio**: Risk-adjusted returns more important than absolute returns
4. **Watch profit factor**: Ensure gains >> losses
5. **Track drawdown daily**: Know your worst day at any time
6. **Use position sizing**: Never risk more than 2-3% per trade

---

**See also:**
- [Strategy Module](STRATEGY.md)
- [Indicators Module](INDICATORS.md)
- [Full Documentation](README.md)
