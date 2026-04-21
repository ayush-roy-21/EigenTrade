from __future__ import annotations

from pathlib import Path
import sys

# Allow imports from top-level src directory during pytest runs.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from llm_local import ExplainerModule, _classify_indicator


def test_classify_indicator_thresholds() -> None:
    assert _classify_indicator("rsi", 25) == "low"
    assert _classify_indicator("rsi", 75) == "high"
    assert _classify_indicator("rsi", 50) == "neutral"
    assert _classify_indicator("macd", -0.01) == "bearish"
    assert _classify_indicator("bb_width", 0.06) == "wide"


def test_explain_signal_local_contains_key_sections() -> None:
    module = ExplainerModule(mode="local")

    signal_data = {
        "signal": 1,
        "confidence": 0.85,
        "top_factor": "sma_diff",
        "ridge_decision": 1,
        "forest_probability": 0.78,
    }
    features = {
        "rsi": 28.0,
        "macd": 0.4,
        "sma_diff": 0.02,
        "bb_width": 0.07,
        "volatility": 0.03,
    }

    result = module.explain_signal(signal_data, features)

    assert result["mode"] == "local"
    assert "Signal: Strong Buy" in result["explanation"]
    assert "Primary driver:" in result["explanation"]
    assert "Model Consensus:" in result["explanation"]


def test_explain_trade_local_formats_profit_rationale() -> None:
    module = ExplainerModule(mode="local")

    trade_data = {
        "entry_price": 100.0,
        "exit_price": 110.0,
        "pnl": 10.0,
        "pnl_pct": 10.0,
        "reason": "Target hit",
    }
    indicators = {
        "rsi": 25.0,
        "sma_20": 98.0,
        "price": 100.0,
    }

    result = module.explain_trade(trade_data, indicators)

    assert result["mode"] == "local"
    assert "oversold territory" in result["explanation"]
    assert "a profitable trade" in result["explanation"]


def test_mistral_mode_without_api_key_falls_back_to_local(monkeypatch) -> None:
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)

    module = ExplainerModule(mode="mistral")

    assert module.mode == "local"
    assert module.mistral_client is None
