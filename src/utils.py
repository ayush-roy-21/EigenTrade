"""
Risk management and utility functions
"""
import pandas as pd
import numpy as np


class RiskMetrics:
    """Calculate risk metrics for a portfolio"""
    
    def __init__(self, returns: pd.Series, risk_free_rate: float = 0.02):
        self.returns = returns
        self.risk_free_rate = risk_free_rate
    
    def total_return(self) -> float:
        """Total return %"""
        return ((self.returns + 1).prod() - 1) * 100
    
    def annualized_return(self) -> float:
        """Annualized return % (assuming 252 trading days)"""
        total = self.total_return() / 100
        periods = len(self.returns) / 252
        if periods > 0:
            return ((1 + total) ** (1 / periods) - 1) * 100
        return 0
    
    def volatility(self) -> float:
        """Annualized volatility %"""
        return self.returns.std() * np.sqrt(252) * 100
    
    def sharpe_ratio(self) -> float:
        """Sharpe Ratio"""
        excess_return = self.annualized_return() / 100 - self.risk_free_rate
        vol = self.volatility() / 100
        if vol > 0:
            return excess_return / vol
        return 0
    
    def max_drawdown(self) -> float:
        """Maximum drawdown %"""
        cumulative = (1 + self.returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        return drawdown.min() * 100
    
    def win_rate(self, threshold: float = 0.0) -> float:
        """Win rate % (% of positive returns)"""
        wins = (self.returns > threshold).sum()
        total = len(self.returns)
        return (wins / total * 100) if total > 0 else 0
    
    def profit_factor(self) -> float:
        """Ratio of gross profit to gross loss"""
        gains = self.returns[self.returns > 0].sum()
        losses = abs(self.returns[self.returns < 0].sum())
        return gains / losses if losses != 0 else 0
    
    def get_all_metrics(self) -> dict:
        """Return all metrics as dict"""
        return {
            'Total Return (%)': self.total_return(),
            'Annualized Return (%)': self.annualized_return(),
            'Volatility (%)': self.volatility(),
            'Sharpe Ratio': self.sharpe_ratio(),
            'Max Drawdown (%)': self.max_drawdown(),
            'Win Rate (%)': self.win_rate(),
            'Profit Factor': self.profit_factor()
        }


def position_sizing(account_size: float, risk_pct: float, entry: float, stop_loss: float) -> float:
    risk_amount = account_size * (risk_pct / 100)
    price_risk = abs(entry - stop_loss)
    
    if price_risk > 0:
        position_size = risk_amount / price_risk
        return max(0, int(position_size))
    return 0


def calculate_drawdown_series(equity_curve: pd.Series) -> pd.Series:
    """Calculate running drawdown from equity curve"""
    running_max = equity_curve.expanding().max()
    drawdown = (equity_curve - running_max) / running_max * 100
    return drawdown


def check_risk_limits(current_drawdown: float, max_drawdown_limit: float) -> bool:
    """Check if current drawdown exceeds limit"""
    return abs(current_drawdown) <= abs(max_drawdown_limit)
