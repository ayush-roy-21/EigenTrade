# 🎨 Streamlit UI Module (`UI/app.py`)

## Overview
The Streamlit UI provides three interactive dashboards for strategy optimization, trade explanation, and risk management. Built with Streamlit for instant feedback and live parameter tuning.

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│              Streamlit App Entry Point                  │
│                     (main())                            │
└──────────────────┬──────────────────────────────────────┘
                   │
        ┌──────────┼──────────┐
        │          │          │
        ▼          ▼          ▼
   ┌────────┐ ┌──────────┐ ┌──────────┐
   │Strategy│ │Trade     │ │Risk      │
   │Studio  │ │Explainer │ │Dashboard │
   └────────┘ └──────────┘ └──────────┘
        │          │          │
        └──────────┼──────────┘
                   │
        ┌──────────▼──────────┐
        │ Helper Functions    │
        ├─────────────────────┤
        │ • load_data()       │
        │ • explain_trade()   │
        └─────────────────────┘
```

---

## 📊 Page Configuration

```python
st.set_page_config(
    page_title="EigenTrades",
    layout="wide",
    initial_sidebar_state="expanded"
)
```

#### Settings
| Setting | Value | Purpose |
|---------|-------|---------|
| `page_title` | "EigenTrades" | Browser tab title |
| `layout` | "wide" | Use full screen width |
| `initial_sidebar_state` | "expanded" | Show sidebar by default |

---

## 🔧 Helper Functions

### **load_data()**

#### Signature
```python
@st.cache_data
def load_data():
    """Load all CSV files from data folder"""
```

#### Description
Loads all CSV files from `data/` folder with caching for performance.

#### Implementation
```python
data_folder = Path(__file__).parent.parent / 'data'
dfs = {}

if data_folder.exists():
    csv_files = list(data_folder.glob('*.csv'))
    for path in csv_files:
        try:
            df = pd.read_csv(path)
            # Ensure date column is datetime
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'], errors='coerce')
            dfs[path.stem] = df.sort_values('date') if 'date' in df.columns else df
        except Exception as e:
            st.warning(f"Failed to load {path.name}: {e}")

return dfs
```

#### Returns
- `dict`: Filename stem → DataFrame mapping

#### Example Output
```python
{
    'BANKNIFTY_active_futures': DataFrame(3326 rows × 5 cols),
    'FINNIFTY_part1': DataFrame(5000 rows × 5 cols),
    ...
}
```

#### Caching
The `@st.cache_data` decorator:
- Loads data once on first run
- Reuses cached data on subsequent runs
- Improves app responsiveness
- Invalidates when file timestamp changes

---

### **explain_trade_with_claude()**

#### Signature
```python
def explain_trade_with_claude(trade_data: dict, indicators: dict) -> str
```

#### Description
Uses Claude API to generate natural language trade explanations.

#### Parameters
- `trade_data` (dict): Trade details (entry, exit, price, P&L)
- `indicators` (dict): Indicator values at entry

#### Returns
- `str`: AI-generated explanation or error message

#### Implementation Flow
```
1. Check if Claude API available
2. Create prompt with trade details
3. Call Claude with trade context
4. Return explanation or error message
```

#### Prompt Template
```
A trading algorithm just made this trade:

Entry Date: {entry_date}
Entry Price: ${entry_price}
Exit Date: {exit_date}
Exit Price: ${exit_price}
Profit/Loss: ${pnl} ({pnl_pct}%)
Reason: {reason}

Technical Indicators at Entry:
- RSI: {rsi}
- SMA 20: {sma_20}
- Price: {price}

Explain this trade in 1-2 sentences like you're explaining to someone 
who doesn't understand trading. Be specific about why the algorithm 
entered and exited.
```

#### API Configuration
```python
client = Anthropic()
message = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=200,
    messages=[{"role": "user", "content": prompt}]
)
```

#### Error Handling
```python
except Exception as e:
    return f"Error explaining trade: {e}"
```

#### Example Output
> "The algorithm bought 100 shares at $100 because the Relative Strength Index dropped below 30 (indicating oversold) while price remained above the 20-day moving average. It sold at $105 when RSI rose above 70."

---

## 🚀 Dashboard 1: Strategy Studio

### **Function: tab_strategy_studio()**

#### Layout
```
┌─────────────────────────────────────────────────┐
│ 🚀 Live Strategy Studio                         │
│ Adjust parameters and see backtest results...   │
├────────────────┬────────────────────────────────┤
│ LEFT COLUMN    │ RIGHT COLUMN                   │
├────────────────┼────────────────────────────────┤
│ 📊 Data Select │ ⚙️ Strategy Parameters         │
│ - Dropdown     │ - RSI Lower Slider             │
│ - File stats   │ - RSI Upper Slider             │
│                │ - MA Period Slider             │
│                │ - Position Size Slider         │
│                │ - Initial Capital Input        │
├────────────────┼────────────────────────────────┤
│                 ▶️ Run Backtest (PRIMARY BUTTON) │
├────────────────┴────────────────────────────────┤
│ 📈 Backtest Results                            │
│ - 4 metrics cards (Return, Trades, Win, Equity)│
│ - 4 metrics cards (Vol, Sharpe, Wins, Losses)  │
│ - Line chart (Equity curve)                    │
│ - Table (Trade history)                        │
└────────────────────────────────────────────────┘
```

### Workflow

#### Step 1: Data Selection
```python
datasets = load_data()
selected_dataset = st.selectbox("Select Dataset", list(datasets.keys()))
df = datasets[selected_dataset].copy()
```

- User selects from available CSV files
- Displays row count and date range
- Validates 'close' column exists

#### Step 2: Parameter Selection
```python
rsi_lower = st.slider("RSI Lower Threshold (Entry)", 10, 40, 30)
rsi_upper = st.slider("RSI Upper Threshold (Exit)", 60, 90, 70)
ma_period = st.slider("Moving Average Period", 5, 100, 20)
position_pct = st.slider("Position Size (% of capital)", 50, 100, 95)
initial_capital = st.number_input("Initial Capital ($)", 1000, 1000000, 100000)
```

| Parameter | Range | Default | Purpose |
|-----------|-------|---------|---------|
| RSI Lower | 10-40 | 30 | Entry signal threshold |
| RSI Upper | 60-90 | 70 | Exit signal threshold |
| MA Period | 5-100 | 20 | Trend confirmation |
| Position % | 50-100 | 95 | Risk management |
| Initial $ | 1k-1M | 100k | Account size |

#### Step 3: Backtest Execution
```python
if st.button("▶️ Run Backtest"):
    with st.spinner("Running backtest..."):
        # Calculate indicators
        df['rsi'] = calculate_rsi(df['close'], 14)
        df['sma'] = sma(df['close'], ma_period)
        
        # Generate signals
        df['entry_signal'] = (df['rsi'] < rsi_lower) & (df['close'] > df['sma'])
        df['exit_signal'] = df['rsi'] > rsi_upper
        
        # Run backtest
        strategy = BacktestStrategy(
            initial_capital=initial_capital,
            position_size_pct=position_pct / 100
        )
        results = strategy.backtest(df, 'entry_signal', 'exit_signal')
```

#### Step 4: Results Display

**Performance Metrics (4+4 cards):**
```python
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Return", f"{results['total_return_pct']:.2f}%")
col2.metric("Number of Trades", int(results['num_trades']))
col3.metric("Win Rate", f"{results.get('win_rate_pct', 0):.1f}%")
col4.metric("Final Equity", f"${results['final_capital']:,.0f}")
```

**Equity Curve Chart:**
```python
st.line_chart(pd.DataFrame({
    'Equity': results['equity_curve']
}))
```

**Trade History Table:**
```python
trades_df = pd.DataFrame([{
    'Entry Date': t.entry_date,
    'Entry Price': f"${t.entry_price:.2f}",
    'Exit Date': t.exit_date,
    'Exit Price': f"${t.exit_price:.2f}",
    'P&L': f"${t.pnl:.2f}",
    'P&L %': f"{t.pnl_pct:.2f}%",
    'Reason': t.reason
} for t in results['trades']])
st.dataframe(trades_df, use_container_width=True)
```

---

## 🤖 Dashboard 2: Trade Explainer

### **Function: tab_trade_explainer()**

#### Layout
```
┌─────────────────────────────────────────────────┐
│ 🤖 AI Trade Explainer                           │
│ Claude explains each trade in plain English     │
├────────────────────────────────────────────────┤
│ Select Dataset | RSI Entry Threshold            │
├────────────────────────────────────────────────┤
│    🔍 Analyze & Explain Trades (PRIMARY)        │
├────────────────────────────────────────────────┤
│ 📝 Trade Explanations                          │
│ ├─ Trade #1: 2024-01-15 → 2024-01-20 (+5.23%)  │
│ │  "The algorithm bought because RSI < 30..."  │
│ │                                              │
│ ├─ Trade #2: 2024-01-21 → 2024-01-25 (-2.10%)  │
│ │  "The algorithm exited early due to..."      │
│ │                                              │
│ └─ ...                                         │
└────────────────────────────────────────────────┘
```

### Workflow

#### Step 1: Parameter Selection
```python
selected_dataset = st.selectbox("Select Dataset", list(datasets.keys()))
rsi_lower = st.slider("RSI Entry Threshold", 10, 40, 30)
```

#### Step 2: Strategy Execution
```python
if st.button("🔍 Analyze & Explain Trades"):
    df = datasets[selected_dataset].copy()
    
    # Calculate indicators
    df['rsi'] = calculate_rsi(df['close'], 14)
    df['sma'] = sma(df['close'], 20)
    df['entry_signal'] = (df['rsi'] < rsi_lower) & (df['close'] > df['sma'])
    df['exit_signal'] = df['rsi'] > 70
    
    # Run backtest
    strategy = BacktestStrategy(initial_capital=100000)
    results = strategy.backtest(df, 'entry_signal', 'exit_signal')
```

#### Step 3: Trade Explanation Loop
```python
for i, trade in enumerate(results['trades'][:10], 1):
    with st.expander(f"Trade #{i}: {trade.entry_date} → {trade.exit_date} ({trade.pnl_pct:+.2f}%)"):
        trade_info = {
            'entry_date': trade.entry_date,
            'entry_price': trade.entry_price,
            'exit_date': trade.exit_date,
            'exit_price': trade.exit_price,
            'pnl': trade.pnl,
            'pnl_pct': trade.pnl_pct,
            'reason': trade.reason
        }
        
        explanation = explain_trade_with_claude(trade_info, {...})
        st.write(explanation)
        st.divider()
```

#### Features
- **Expandable trades**: Click to view explanation
- **Color-coded**: Green for wins, red for losses
- **Limit to 10 trades**: Avoid overwhelming the UI
- **Error handling**: Shows error if Claude API unavailable

---

## ⚠️ Dashboard 3: Risk Management

### **Function: tab_risk_dashboard()**

#### Layout
```
┌─────────────────────────────────────────────────┐
│ ⚠️ Risk Management Dashboard                    │
│ Professional risk metrics and real-time...      │
├────────────────────────────────────────────────┤
│ Dataset Selection | Initial Capital Input      │
├────────────────────────────────────────────────┤
│ 📊 Key Risk Metrics                            │
│ ├─ Max Drawdown: -8.5% | Sharpe: 1.32         │
│ └─ Win Rate: 62.5%                            │
│                                                │
│ 📉 Drawdown Over Time (Area Chart)             │
│                                                │
│ 🚨 Risk Alerts                                 │
│ ├─ 🟢 Drawdown within safe limits              │
│ └─ 🟡 WARNING: Sharpe ratio below 1.0         │
│                                                │
│ 📐 Position Sizing Calculator                  │
│ ├─ Entry: $100 | Stop: $95 | Risk: 2%         │
│ └─ → Position Size: 400 shares                │
│                                                │
│ 📊 Trade Statistics                            │
│ ├─ Num Trades: 24 | Winning: 15               │
│ └─ Avg Win: $1,563 | Avg Loss: -$1,231        │
└────────────────────────────────────────────────┘
```

### Workflow

#### Step 1: Data Setup
```python
selected_dataset = st.selectbox("Select Dataset", list(datasets.keys()))
df = datasets[selected_dataset].copy()
initial_capital = st.number_input("Initial Capital", value=100000)

# Run strategy
df['rsi'] = calculate_rsi(df['close'], 14)
df['sma'] = sma(df['close'], 20)
df['entry_signal'] = (df['rsi'] < 30) & (df['close'] > df['sma'])
df['exit_signal'] = df['rsi'] > 70

strategy = BacktestStrategy(initial_capital=initial_capital)
results = strategy.backtest(df, 'entry_signal', 'exit_signal')
```

#### Step 2: Risk Metrics Calculation
```python
equity_series = pd.Series(results['equity_curve'])
returns = equity_series.pct_change().dropna()

risk_metrics = RiskMetrics(returns)
metrics = risk_metrics.get_all_metrics()
```

#### Step 3: Display Metrics (3+3 cards)
```python
col1, col2, col3 = st.columns(3)
col1.metric("Max Drawdown", f"{metrics['Max Drawdown (%)']:.2f}%")
col2.metric("Sharpe Ratio", f"{metrics['Sharpe Ratio']:.2f}")
col3.metric("Win Rate", f"{metrics['Win Rate (%)']:.1f}%")

col1, col2, col3 = st.columns(3)
col1.metric("Volatility (Annual)", f"{metrics['Volatility (%)']:.2f}%")
col2.metric("Total Return", f"{metrics['Total Return (%)']:.2f}%")
col3.metric("Profit Factor", f"{metrics['Profit Factor']:.2f}")
```

#### Step 4: Drawdown Visualization
```python
drawdown_series = calculate_drawdown_series(equity_series)
st.area_chart(drawdown_series * 100, color="#FF6B6B")
```

Drawdown chart shows:
- Red area chart of daily drawdown %
- Peaks show worst drawdown during period
- Helps visualize equity curve stress points

#### Step 5: Risk Alerts
```python
max_dd = metrics['Max Drawdown (%)']
if max_dd < -20:
    st.error(f"⚠️ CRITICAL: Max drawdown {max_dd:.2f}% exceeds 20% threshold!")
elif max_dd < -10:
    st.warning(f"⚠️ WARNING: Max drawdown {max_dd:.2f}% exceeds 10% threshold")
else:
    st.success(f"✅ Drawdown {max_dd:.2f}% is within safe limits")
```

Three-level alert system:
- 🔴 **CRITICAL**: DD < -20%
- 🟡 **WARNING**: DD < -10%
- 🟢 **OK**: DD ≥ -10%

#### Step 6: Position Sizing Calculator
```python
entry_price = col1.number_input("Entry Price ($)", value=100.0)
stop_loss = col2.number_input("Stop Loss Price ($)", value=95.0)
risk_pct = col3.number_input("Risk per Trade (%)", value=2.0, min_value=0.1, max_value=10.0)

position_size = position_sizing(initial_capital, risk_pct, entry_price, stop_loss)
st.info(f"📍 **Position Size: {position_size:,} shares**")
```

Interactive calculator showing optimal position size based on:
- Account balance
- Risk tolerance
- Entry and stop loss prices

#### Step 7: Trade Statistics
```python
col1, col2 = st.columns(2)
with col1:
    st.metric("Num Trades", int(results['num_trades']))
    st.metric("Winning Trades", int(results['winning_trades']))
    st.metric("Avg Win", f"${results.get('avg_win', 0):,.2f}")

with col2:
    st.metric("Losing Trades", int(results['losing_trades']))
    st.metric("Avg Loss", f"${results.get('avg_loss', 0):,.2f}")
    if results.get('avg_loss', 0) != 0:
        ratio = abs(results.get('avg_win', 0) / results.get('avg_loss', 1))
        st.metric("Profit/Loss Ratio", f"{ratio:.2f}")
```

---

## 🎮 Sidebar Navigation

```python
st.sidebar.title("⚙️ EigenTrades")
st.sidebar.write("AI-Powered Algorithmic Trading Platform")
st.sidebar.divider()

mode = st.sidebar.radio(
    "Select Mode",
    ["🚀 Strategy Studio", "🤖 Trade Explainer", "⚠️ Risk Dashboard"],
    index=0
)

st.sidebar.divider()
st.sidebar.write("### 📚 About")
st.sidebar.write(
    "**EigenTrades** combines:\n"
    "- Live backtesting with parameter tuning\n"
    "- AI-powered trade explanations\n"
    "- Professional risk management"
)
```

#### Features
- Radio buttons for mode selection
- Persistent across all tabs
- Shows project description
- Icon indicators for each mode

---

## 🔄 Data Flow

```
User selects parameters
        │
        ▼
load_data() returns dict
        │
        ▼
Calculate indicators
(RSI, SMA, MACD, etc.)
        │
        ▼
Generate entry/exit signals
        │
        ▼
BacktestStrategy.backtest()
        │
        ▼
Calculate performance metrics
        │
        ▼
Display results:
├─ Metrics cards
├─ Charts
├─ Tables
└─ Alerts
```

---

## 📊 Key Components

### Metric Cards
```python
col1, col2, col3, col4 = st.columns(4)
col1.metric("Label", "Value", delta="Change")
```

- Shows KPI at a glance
- Optional delta indicator
- Color-coded (green up, red down)

### Sliders
```python
value = st.slider("Label", min_value, max_value, default_value)
```

- Instant feedback (no submit button)
- Real-time UI updates
- Keyboard + mouse support

### Line Charts
```python
st.line_chart(data)
```

- Automatic axis scaling
- Smooth interpolation
- Interactive hover

### Area Charts
```python
st.area_chart(data, color="#FF6B6B")
```

- Filled area for visibility
- Good for drawdown (red)

### Expanders
```python
with st.expander("Title"):
    st.write("Content")
```

- Collapse/expand for details
- Saves screen space
- Organized information

### DataFrames
```python
st.dataframe(df, use_container_width=True)
```

- Sortable columns
- Searchable
- Responsive width

---

## 🎨 UI/UX Best Practices Used

1. **Responsive Layout**: `st.columns()` for side-by-side elements
2. **Caching**: `@st.cache_data` for fast data loading
3. **Spinners**: `st.spinner()` for long operations
4. **Error Handling**: Try/except with user-friendly messages
5. **Color Coding**: Green (good), Red (bad), Blue (neutral)
6. **Icons**: Emojis for visual hierarchy
7. **Grouping**: `st.divider()` to separate sections
8. **Breadcrumbs**: Clear mode selection in sidebar

---

## ⚙️ Configuration Files

### `.streamlit/config.toml`
```toml
[theme]
primaryColor = "#FF6B6B"
backgroundColor = "#0E1117"
secondaryBackgroundColor = "#262730"
textColor = "#FAFAFA"
font = "sans serif"

[browser]
gatherUsageStats = false
```

---

## 🚀 Performance Optimizations

1. **Caching**: Data loaded once, reused across reruns
2. **Lazy loading**: Charts only generated on backtest click
3. **Efficient pandas**: Vectorized operations, not loops
4. **No API calls**: Claude calls only when requested
5. **Session state**: Could be added for state persistence

---

## 🔐 Error Handling

```python
try:
    df = pd.read_csv(path)
except Exception as e:
    st.warning(f"Failed to load {path.name}: {e}")
    
try:
    result = strategy.backtest(...)
except Exception as e:
    st.error(f"Backtest failed: {e}")

try:
    explanation = explain_trade_with_claude(...)
except Exception as e:
    return f"Error: {e}"
```

---

## 📱 Mobile Responsiveness

- Uses `layout="wide"` for desktop optimization
- Responsive columns adapt to screen size
- Touch-friendly sliders and buttons
- Tables scroll horizontally on mobile

---

**See also:**
- [Strategy Module](STRATEGY.md)
- [Indicators Module](INDICATORS.md)
- [Risk Management](RISK_MANAGEMENT.md)
- [Full Documentation](README.md)
