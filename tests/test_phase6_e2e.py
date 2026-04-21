from __future__ import annotations

import importlib
from pathlib import Path
import sys
import types

import numpy as np
import pandas as pd
import pytest

# Allow imports from top-level src directory during pytest runs.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from indicators import calculate_all_indicators
from llm_local import ExplainerModule
from ml_engine import MLEngine
from strategy import BacktestStrategy


def _synthetic_close_series(rows: int = 320) -> pd.Series:
    x = np.linspace(0, 12 * np.pi, rows)
    trend = np.linspace(100.0, 120.0, rows)
    wave = 4.0 * np.sin(x)
    noise = 0.4 * np.cos(x * 0.5)
    return pd.Series(trend + wave + noise, dtype=float)


def test_phase6_e2e_pipeline_smoke() -> None:
    close = _synthetic_close_series()
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=len(close), freq="D"),
            "close": close,
            "high": close + 1.0,
            "low": close - 1.0,
        }
    )

    with_indicators = calculate_all_indicators(frame)
    assert {"sma_20", "rsi_14", "macd", "bb_upper"}.issubset(set(with_indicators.columns))

    model = MLEngine(n_estimators=80)
    metrics = model.train(frame[["close"]])
    assert 0.0 <= metrics["ensemble_accuracy"] <= 1.0
    assert metrics["total_rows"] > 200

    prepared = model.prepare_features(frame[["close"]])
    current_features = prepared[model.features].iloc[-1].to_dict()
    signal = model.predict_signal(current_features)

    assert signal["signal"] in (0, 1)
    assert 0.0 <= signal["confidence"] <= 1.0

    explainer = ExplainerModule(mode="local")
    explanation = explainer.explain_signal(signal, current_features)
    assert explanation["mode"] == "local"
    assert explanation["latency_ms"] < 2000
    assert "Signal:" in explanation["explanation"]

    bt_frame = pd.DataFrame(
        {
            "date": frame["date"],
            "close": frame["close"],
            "entry_signal": [False] * 30 + [True] + [False] * 240 + [True] + [False] * 48,
            "exit_signal": [False] * 80 + [True] + [False] * 140 + [True] + [False] * 98,
        }
    )

    engine = BacktestStrategy(initial_capital=100000, position_size_pct=0.5)
    results = engine.backtest(bt_frame, entry_signal_col="entry_signal", exit_signal_col="exit_signal")

    assert "total_return_pct" in results
    assert isinstance(results["equity_curve"], list)
    assert results["num_trades"] >= 1


class _MockSource:
    def __init__(self, frame: pd.DataFrame):
        self._frame = frame

    def fetch(self, since=None) -> pd.DataFrame:
        return self._frame.copy()


class _MockOracleClient:
    def __init__(self):
        self.executed_sql: list[str] = []
        self.execute_many_calls: list[tuple[str, int]] = []

    def fetch_all(self, query: str, params=None):
        # Pretend optimization view is present in Oracle.
        if "FROM user_mviews" in query:
            return [("MARKET_SIGNALS",)]
        return []

    def execute(self, statement: str, params=None) -> None:
        self.executed_sql.append(statement)

    def execute_many(self, statement: str, rows, batch_size: int = 1000) -> int:
        self.execute_many_calls.append((statement, len(rows)))
        return len(rows)


class _MockOracleClientMissingMView(_MockOracleClient):
    def fetch_all(self, query: str, params=None):
        if "FROM user_mviews" in query:
            return []
        return super().fetch_all(query, params=params)


def test_phase6_e2e_ingestion_pipeline_with_optimization(tmp_path: Path, monkeypatch) -> None:
    fake_oracle = types.ModuleType("oracle")
    fake_oracle.OracleClient = object
    fake_oracle.create_client_from_env = lambda: None
    monkeypatch.setitem(sys.modules, "oracle", fake_oracle)

    ingestion = importlib.import_module("ingestion_pipeline")

    times = pd.date_range("2024-01-01", periods=3, freq="h", tz="UTC")
    incoming = pd.DataFrame(
        {
            "symbol": ["BANKNIFTY", "BANKNIFTY", "BANKNIFTY"],
            "time": [times[0], times[0], times[1]],  # one duplicate event
            "open": [100.0, 100.0, 101.0],
            "high": [101.0, 101.0, 102.0],
            "low": [99.0, 99.0, 100.0],
            "close": [100.5, 100.5, 101.5],
            "volume": [1000.0, 1000.0, 1200.0],
        }
    )

    cfg = ingestion.PipelineConfig(
        source="csv",
        csv_dir=tmp_path,
        api_url="",
        api_token="",
        checkpoint_file=tmp_path / "checkpoint.json",
        dead_letter_dir=tmp_path / "dead_letter",
        poll_seconds=15,
        batch_size=500,
        max_retries=1,
        retry_backoff_seconds=0,
        audit_to_db=True,
        enable_db_optimization=True,
        require_db_optimization=True,
    )

    client = _MockOracleClient()
    pipeline = ingestion.IngestionPipeline(
        config=cfg,
        source=_MockSource(incoming),
        loader=ingestion.OracleTradeLoader(client),
        checkpoint=ingestion.CheckpointStore(cfg.checkpoint_file),
        dead_letter=ingestion.DeadLetterSink(cfg.dead_letter_dir),
        audit=ingestion.IngestionAuditWriter(client),
        optimization=ingestion.OracleOptimizationManager(client, strict=True),
    )

    result = pipeline.run_once()

    assert result["status"] == "SUCCESS"
    assert result["rows_fetched"] == 3
    assert result["rows_normalized"] == 2
    assert result["rows_loaded"] == 2
    assert cfg.checkpoint_file.exists()

    merged_sql = "\n".join(client.executed_sql)
    assert "MERGE INTO historical_trade_data" in merged_sql
    assert "INSERT INTO ingestion_run_audit" in merged_sql
    assert "DBMS_MVIEW.REFRESH('MARKET_SIGNALS', 'F')" in merged_sql


def test_phase6_e2e_ingestion_fails_when_required_optimization_missing(tmp_path: Path, monkeypatch) -> None:
    fake_oracle = types.ModuleType("oracle")
    fake_oracle.OracleClient = object
    fake_oracle.create_client_from_env = lambda: None
    monkeypatch.setitem(sys.modules, "oracle", fake_oracle)

    ingestion = importlib.import_module("ingestion_pipeline")

    times = pd.date_range("2024-01-01", periods=2, freq="h", tz="UTC")
    incoming = pd.DataFrame(
        {
            "symbol": ["BANKNIFTY", "BANKNIFTY"],
            "time": [times[0], times[1]],
            "open": [100.0, 101.0],
            "high": [101.0, 102.0],
            "low": [99.0, 100.0],
            "close": [100.5, 101.5],
            "volume": [1000.0, 1200.0],
        }
    )

    cfg = ingestion.PipelineConfig(
        source="csv",
        csv_dir=tmp_path,
        api_url="",
        api_token="",
        checkpoint_file=tmp_path / "checkpoint.json",
        dead_letter_dir=tmp_path / "dead_letter",
        poll_seconds=15,
        batch_size=500,
        max_retries=1,
        retry_backoff_seconds=0,
        audit_to_db=True,
        enable_db_optimization=True,
        require_db_optimization=True,
    )

    client = _MockOracleClientMissingMView()
    pipeline = ingestion.IngestionPipeline(
        config=cfg,
        source=_MockSource(incoming),
        loader=ingestion.OracleTradeLoader(client),
        checkpoint=ingestion.CheckpointStore(cfg.checkpoint_file),
        dead_letter=ingestion.DeadLetterSink(cfg.dead_letter_dir),
        audit=ingestion.IngestionAuditWriter(client),
        optimization=ingestion.OracleOptimizationManager(client, strict=True),
    )

    with pytest.raises(RuntimeError, match="MARKET_SIGNALS not found"):
        pipeline.run_once()

    assert not cfg.checkpoint_file.exists()
    dead_letter_files = list(cfg.dead_letter_dir.glob("ingestion_*.json"))
    assert dead_letter_files
