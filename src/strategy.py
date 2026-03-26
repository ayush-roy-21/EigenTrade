"""
Backtesting engine with strategy implementation
"""
import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Tuple
from datetime import datetime
from ml_engine import MLEngine


@dataclass
class Trade:
    """Single trade record"""
    entry_date: str
    entry_price: float
    exit_date: str
    exit_price: float
    quantity: int
    side: str = "BUY"  # BUY or SELL
    reason: str = ""
    pnl: float = 0.0
    pnl_pct: float = 0.0
    
    def __post_init__(self):
        if self.entry_price > 0 and self.exit_price > 0:
            self.pnl = (self.exit_price - self.entry_price) * self.quantity
            self.pnl_pct = ((self.exit_price - self.entry_price) / self.entry_price) * 100


class BacktestStrategy:
    """Strategy backtesting engine"""
    
    def __init__(self, 
                 initial_capital: float = 100000,
                 position_size_pct: float = 0.95,
                 transaction_cost: float = 0.001,
                 model = None):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.position_size_pct = position_size_pct
        self.transaction_cost = transaction_cost
        
        self.trades: List[Trade] = []
        self.equity_curve: List[float] = [initial_capital]
        self.positions: Dict[str, Dict] = {}  # symbol -> {quantity, entry_price, entry_date}
        self.model = model
    
    def enter_position(self, symbol: str, date: str, price: float, 
                      quantity: int, reason: str = "") -> bool:
        """Enter a long position"""
        cost = price * quantity * (1 + self.transaction_cost)
        
        if cost <= self.current_capital and symbol not in self.positions:
            self.positions[symbol] = {
                'entry_date': date,
                'entry_price': price,
                'quantity': quantity,
                'reason': reason
            }
            self.current_capital -= cost
            return True
        return False
    
    def exit_position(self, symbol: str, date: str, price: float, reason: str = "") -> bool:
        """Exit a long position"""
        if symbol not in self.positions:
            return False
        
        pos = self.positions[symbol]
        proceeds = price * pos['quantity'] * (1 - self.transaction_cost)
        
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
        self.current_capital += proceeds
        del self.positions[symbol]
        
        return True
    
    def get_equity(self) -> float:
        """Current equity (cash + position value)"""
        positions_value = sum(
            pos['quantity'] * pos['entry_price'] 
            for pos in self.positions.values()
        )
        return self.current_capital + positions_value
    
    def backtest(self, df: pd.DataFrame, 
                 entry_signal_col: str,
                 exit_signal_col: str,
                 price_col: str = 'close',
                 symbol: str = 'STOCK') -> Dict:
        """
        Run backtest on dataframe with entry/exit signals
        
        Args:
            df: DataFrame with OHLCV data
            entry_signal_col: Column name with entry signals (True/False)
            exit_signal_col: Column name with exit signals (True/False)
            price_col: Price column to use (default 'close')
            symbol: Symbol name for trades
        
        Returns:
            Results dictionary with performance metrics
        """
        df = df.reset_index(drop=True)
        position_open = False
        
        if self.model:
            # Pre-calculate features for the whole dataframe for speed
            df_with_features = self.model.prepare_features(df)
            
            # Predict Proba for all rows
            X = df_with_features[self.model.features]
            probs = self.model.model.predict_proba(X)[:, 1] # Class 1 probability
            
            # Generate Signals based on Confidence > 60%
            df['entry_signal'] = probs > 0.6
            df['exit_signal'] = probs < 0.4 # Exit if confidence drops
            
            # Store confidence for the explainer later
            df['ai_confidence'] = probs
        
        for idx, row in df.iterrows():
            date_str = str(row.get('date', idx))
            price = row[price_col]
            
            # Exit logic
            if position_open and row[exit_signal_col]:
                self.exit_position(symbol, date_str, price, 
                                  reason=f"Exit signal at {price:.2f}")
                position_open = False
                self.equity_curve.append(self.get_equity())
            
            # Entry logic
            elif not position_open and row[entry_signal_col]:
                # Size position for 95% of capital
                quantity = int((self.current_capital * self.position_size_pct) / price)
                if quantity > 0:
                    self.enter_position(symbol, date_str, price, quantity,
                                       reason=f"Entry signal at {price:.2f}")
                    position_open = True
                    self.equity_curve.append(self.get_equity())
            
            # Mark-to-market
            if position_open:
                self.equity_curve.append(self.get_equity())
        
        # Close any open positions at end
        if position_open:
            last_price = df.iloc[-1][price_col]
            last_date = str(df.iloc[-1].get('date', len(df) - 1))
            self.exit_position(symbol, last_date, last_price, reason="End of backtest")
        
        return self._calculate_results(df)
    
    def _calculate_results(self, df: pd.DataFrame) -> Dict:
        """Calculate and return backtest results"""
        equity_series = pd.Series(self.equity_curve)
        returns = equity_series.pct_change().dropna()
        
        total_return = ((self.equity_curve[-1] / self.initial_capital) - 1) * 100
        
        results = {
            'initial_capital': self.initial_capital,
            'final_capital': self.equity_curve[-1],
            'total_return_pct': total_return,
            'num_trades': len(self.trades),
            'winning_trades': len([t for t in self.trades if t.pnl > 0]),
            'losing_trades': len([t for t in self.trades if t.pnl < 0]),
            'trades': self.trades,
            'equity_curve': self.equity_curve
        }
        
        if len(returns) > 0:
            results['volatility_pct'] = returns.std() * np.sqrt(252) * 100
            results['sharpe_ratio'] = (returns.mean() * 252) / (returns.std() * np.sqrt(252)) if returns.std() > 0 else 0
        
        if len(self.trades) > 0:
            total_pnl = sum(t.pnl for t in self.trades)
            results['total_pnl'] = total_pnl
            results['avg_win'] = np.mean([t.pnl for t in self.trades if t.pnl > 0]) if results['winning_trades'] > 0 else 0
            results['avg_loss'] = np.mean([t.pnl for t in self.trades if t.pnl < 0]) if results['losing_trades'] > 0 else 0
            results['win_rate_pct'] = (results['winning_trades'] / len(self.trades)) * 100
        
        return results


def create_simple_strategy(df: pd.DataFrame, 
                           rsi_lower: float = 30,
                           rsi_upper: float = 70,
                           ma_period: int = 20) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Create entry/exit signals using RSI + MA crossover
    
    Entry: RSI < 30 AND price > MA20 (oversold but trending up)
    Exit: RSI > 70 (overbought)
    
    Returns: (df with signals, entry_signals, exit_signals)
    """
    df = df.copy()
    
    # Calculate indicators
    df['sma'] = df['close'].rolling(window=ma_period).mean()
    df['rsi'] = calculate_rsi(df['close'], 14)
    
    # Generate signals
    df['entry_signal'] = (df['rsi'] < rsi_lower) & (df['close'] > df['sma'])
    df['exit_signal'] = df['rsi'] > rsi_upper
    
    return df


def calculate_rsi(data: pd.Series, period: int = 14) -> pd.Series:
    """Calculate RSI"""
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))
