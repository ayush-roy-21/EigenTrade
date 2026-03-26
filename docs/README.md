# 🚀 EigenTrades: AI-Powered Algorithmic Trading Platform

**An intelligent, professional-grade trading platform that combines real-time backtesting, AI-powered trade explanations, and advanced risk management.**

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Key Features](#key-features)
3. [Architecture](#architecture)
4. [Core Components](#core-components)
5. [Three Dashboards](#three-dashboards)
6. [Installation & Setup](#installation--setup)
7. [Usage Guide](#usage-guide)
8. [API Reference](#api-reference)

---

## 📌 Overview

**EigenTrades** is a full-stack algorithmic trading platform that bridges the gap between algorithmic execution and human understanding. It provides:

- **Real-time strategy backtesting** with live parameter tuning
- **AI-powered trade explanations** using Claude API to explain every trade in plain English
- **Professional risk management** dashboard with institutional-grade metrics

### Core Use Cases
✅ Backtest trading strategies on historical data  
✅ Compare multiple strategy variations instantly  
✅ Understand WHY each trade was executed (via AI)  
✅ Monitor professional risk metrics (Sharpe ratio, max drawdown, win rate)  
✅ Calculate optimal position sizes based on risk tolerance  
✅ Visualize equity curves and drawdown analysis  

---

## 🎯 Key Features

| Feature | Description |
|---------|-------------|
| **Live Strategy Studio** | Adjust RSI thresholds, MA periods, position sizing on live sliders with instant backtest results |
| **AI Trade Explainer** | Claude AI explains each trade in plain English (e.g., "Bought because RSI < 30 AND price > 20-day MA") |
| **Risk Dashboard** | Professional metrics: Sharpe ratio, max drawdown, win rate, volatility, profit factor |
| **Technical Indicators** | RSI, SMA, EMA, MACD, Bollinger Bands, ATR |
| **Backtesting Engine** | Entry/exit signals, position tracking, P&L calculation, trade history |
| **Position Sizing** | Risk-based position calculator (determines shares based on risk tolerance) |
| **Drawdown Monitoring** | Real-time visualization with risk alerts when limits exceeded |
| **Multi-Dataset Support** | Load and analyze multiple CSV files simultaneously |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│              Streamlit UI (app.py)                  │
│  - Strategy Studio (Live Parameter Tuning)          │
│  - Trade Explainer (Claude AI Integration)          │
│  - Risk Dashboard (Professional Metrics)            │
└──────────────────┬──────────────────────────────────┘
                   │
        ┌──────────┴──────────┬─────────────┐
        │                     │             │
        ▼                     ▼             ▼
┌─────────────────┐ ┌──────────────────┐ ┌──────────────┐
│  Strategy.py    │ │ Indicators.py    │ │  Utils.py    │
│                 │ │                  │ │              │
│ • Trade class   │ │ • RSI            │ │ • RiskMetrics│
│ • Backtest      │ │ • SMA/EMA        │ │ • Position   │
│   engine        │ │ • MACD           │ │   sizing     │
│ • Entry/exit    │ │ • Bollinger      │ │ • Drawdown   │
│   signals       │ │   Bands          │ │   tracking   │
│ • Results calc  │ │ • ATR            │ │              │
└─────────────────┘ └──────────────────┘ └──────────────┘
        │                     │             │
        └──────────────────────┬─────────────┘
                               │
                    ┌──────────▼──────────┐
                    │   CSV Data Files    │
                    │  (data/ folder)     │
                    └─────────────────────┘
```

---

## 🔧 Core Components

### 1. **Indicators Module** (`src/indicators.py`)
Technical analysis indicators for strategy signals.

### 2. **Strategy Module** (`src/strategy.py`)
Backtesting engine with trade tracking and P&L calculation.

### 3. **Risk Management** (`src/utils.py`)
Professional risk metrics and position sizing.

### 4. **Interactive UI** (`UI/app.py`)
Streamlit-based dashboard with 3 operational modes.

---

## 📊 Three Dashboards

### 🚀 Dashboard 1: Live Strategy Studio
**What it does:** Interactive parameter tuning with instant backtest feedback

**Features:**
- Select dataset from loaded CSV files
- Adjust 5 parameters live:
  - RSI Lower Threshold (entry signal threshold)
  - RSI Upper Threshold (exit signal threshold)
  - Moving Average Period (trend confirmation)
  - Position Size (% of capital per trade)
  - Initial Capital (account balance)
- Click "Run Backtest" to execute
- View results in real-time:
  - Total return %
  - Number of trades
  - Win rate
  - Final equity
  - Volatility
  - Sharpe ratio
  - Equity curve chart
  - Complete trade history table

**Use Case:** Optimize strategy parameters for best risk-adjusted returns

---

### 🤖 Dashboard 2: AI Trade Explainer
**What it does:** Claude AI explains each trade in plain English

**Features:**
- Select dataset
- Set RSI entry threshold
- Click "Analyze & Explain Trades"
- For each trade, see:
  - Entry date & price
  - Exit date & price
  - P&L in dollars and percentage
  - **AI-generated explanation** in natural language

**Example Explanation:**
> "The algorithm bought 10 shares at $100 because the Relative Strength Index (RSI) dropped below 30 (indicating oversold conditions) while the price remained above the 20-day moving average (indicating uptrend). It sold at $105 when RSI rose above 70 (overbought), locking in a $50 profit."

**Use Case:** Understand the logic behind algorithmic decisions, build confidence in strategy

---

### ⚠️ Dashboard 3: Risk Management Dashboard
**What it does:** Professional risk metrics and real-time monitoring

**Features:**
- Key Risk Metrics (displayed as cards):
  - **Max Drawdown %**: Largest peak-to-trough decline
  - **Sharpe Ratio**: Risk-adjusted returns (higher = better)
  - **Win Rate %**: Percentage of profitable trades
  - **Volatility (Annual) %**: Price fluctuation magnitude
  - **Total Return %**: Cumulative profit/loss
  - **Profit Factor**: Ratio of gross gains to gross losses

- Drawdown Visualization:
  - Area chart showing running drawdown over time
  - Color-coded warning when limits exceeded

- Risk Alerts (3 levels):
  - 🟢 **SAFE**: Drawdown within limits
  - 🟡 **WARNING**: Drawdown > 10%
  - 🔴 **CRITICAL**: Drawdown > 20%

- Position Sizing Calculator:
  - Input: Entry price, Stop loss price, Risk per trade (%)
  - Output: Optimal number of shares to buy
  - Example: $100K account, $100 entry, $95 stop, 2% risk = 400 shares

- Trade Statistics:
  - Total trades, wins, losses
  - Average win/loss dollar amount
  - Profit/Loss ratio

**Use Case:** Ensure trading aligns with professional risk management standards

---

## 📦 Installation & Setup

### Prerequisites
- Python 3.8+
- pip package manager

### Step 1: Install Dependencies
```bash
cd C:\EigenTrades
pip install -r requirements.txt
```

### Step 2: Prepare Data
Place CSV files in `data/` folder. Required columns:
- `date`: Trade date
- `close`: Closing price
- `high` (optional): High price for ATR calculation
- `low` (optional): Low price for ATR calculation

### Step 3: Set Up Claude API (Optional, for Trade Explainer)
```bash
set ANTHROPIC_API_KEY=your_api_key_here
```

### Step 4: Run the App
```bash
python -m streamlit run UI/app.py
```

App opens at `http://localhost:8501`

---

## 🎮 Usage Guide

### Workflow 1: Strategy Optimization
1. Go to **Strategy Studio** tab
2. Select a dataset
3. Adjust RSI and MA parameters
4. Click "Run Backtest"
5. Review metrics and equity curve
6. Repeat with different parameters to find optimal settings

### Workflow 2: Trade Understanding
1. Go to **Trade Explainer** tab
2. Select dataset
3. Set RSI threshold
4. Click "Analyze & Explain Trades"
5. Expand each trade to read AI explanation
6. Understand the logic behind each entry/exit

### Workflow 3: Risk Assessment
1. Go to **Risk Dashboard** tab
2. Review key metrics (especially Max Drawdown and Sharpe Ratio)
3. Check risk alerts
4. Use position sizing calculator to determine trade size
5. Ensure metrics align with your risk tolerance

---

## 📚 API Reference

See detailed documentation in:
- [Indicators API](INDICATORS.md)
- [Strategy API](STRATEGY.md)
- [Risk Management API](RISK_MANAGEMENT.md)
- [Streamlit UI API](UI.md)

---

## 📊 Example Results

**Sample Backtest Output:**
```
Total Return:        +23.45%
Annualized Return:   +18.92%
Volatility:          14.3%
Sharpe Ratio:        1.32
Max Drawdown:        -8.5%
Win Rate:            62.5%
Num Trades:          24
Winning Trades:      15
Losing Trades:       9
Profit Factor:       2.15
```

---

## 🔐 Data Privacy

- ✅ Data loaded from local CSV files only
- ✅ No data sent to external servers (except Claude API for Trade Explainer)
- ✅ Claude API calls only include trade metadata, not account info
- ✅ Backtest results stored locally in Streamlit session

---

## 🚀 Advanced Features

### Multi-Dataset Analysis
Load multiple CSV files and compare strategies across different assets

### Real-Time Parameter Tuning
See results update instantly as you adjust sliders (no page refresh needed)

### Institutional Risk Metrics
Professional-grade calculations:
- Sharpe ratio (excess return per unit of risk)
- Maximum drawdown (peak-to-trough decline)
- Profit factor (win/loss ratio)
- Annualized return (return over 252 trading days)

---

## 💡 Tips & Best Practices

1. **Start with defaults**: Test the strategy with default parameters first
2. **Compare metrics**: Don't chase returns; focus on Sharpe ratio and max drawdown
3. **Check trade explanations**: Use AI explainer to validate strategy logic
4. **Risk management first**: Set position size based on max drawdown limits
5. **Walk-forward testing**: Test on different time periods, not just one dataset

---

## 🤝 Support & Contribution

For issues or feature requests, contact the development team.

---

**Built with ❤️ for quantitative traders and algo developers**
