from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

# Allow imports from top-level src directory during pytest runs.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from indicators import calculate_all_indicators
from strategy import BacktestStrategy
from loaddata import normalize_ohlcv_frame
from eigent_explainer import EigentTradeExplainer


def test_calculate_all_indicators_adds_expected_columns() -> None:
    prices = pd.Series([100 + i for i in range(80)], dtype=float)
    frame = pd.DataFrame(
        {
            "close": prices,
            "high": prices + 1,
            "low": prices - 1,
        }
    )

    out = calculate_all_indicators(frame)

    expected = {"sma_20", "ema_12", "rsi_14", "macd", "bb_upper", "atr"}
    assert expected.issubset(set(out.columns))


def test_strategy_backtest_runs_end_to_end() -> None:
    rows = 80
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=rows, freq="D"),
            "close": [100.0 + (i * 0.5) for i in range(rows)],
            "entry_signal": [False] * 10 + [True] + [False] * 50 + [True] + [False] * 18,
            "exit_signal": [False] * 30 + [True] + [False] * 49,
        }
    )

    engine = BacktestStrategy(initial_capital=100000, position_size_pct=0.5)
    results = engine.backtest(frame, entry_signal_col="entry_signal", exit_signal_col="exit_signal")

    assert "total_return_pct" in results
    assert "equity_curve" in results
    assert isinstance(results["equity_curve"], list)


def test_normalize_ohlcv_frame_normalizes_columns() -> None:
    raw = pd.DataFrame(
        {
            "ticker": ["banknifty", "banknifty"],
            "timestamp": ["2024-01-01 09:15:00", "2024-01-02 09:15:00"],
            "open_price": [100, 101],
            "high_price": [102, 103],
            "low_price": [99, 100],
            "close_price": [101, 102],
            "qty": [1000, 1200],
        }
    )

    out = normalize_ohlcv_frame(raw)

    assert list(out.columns) == ["symbol", "time", "open", "high", "low", "close", "volume"]
    assert out.iloc[0]["symbol"] == "BANKNIFTY"


def test_eigent_explainer_is_ready_property_no_attribute_error() -> None:
    # Build object without running network/client initialization and ensure property is safe.
    explainer = EigentTradeExplainer.__new__(EigentTradeExplainer)
    explainer._ready = True
    explainer._client = None

    assert explainer.is_ready is False
