from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from llm_local import ExplainerModule
from ml_engine import MLEngine


def _load_training_frame() -> pd.DataFrame:
    data_file = ROOT / "data" / "BANKNIFTY_active_futures.csv"
    df = pd.read_csv(data_file)

    close_col = "close" if "close" in df.columns else "Close" if "Close" in df.columns else None
    if close_col is None:
        raise ValueError(f"No close column found in {data_file}")

    if close_col != "close":
        df = df.rename(columns={close_col: "close"})

    return df[["close"]].copy()


def run_phase6_benchmark() -> dict[str, float | bool | str]:
    min_accuracy = float(os.getenv("PHASE6_MIN_ENSEMBLE_ACCURACY", "0.55"))
    max_llm_latency_ms = float(os.getenv("PHASE6_MAX_LLM_LATENCY_MS", "2000"))

    model = MLEngine()
    metrics = model.train(_load_training_frame())

    prepared = model.prepare_features(_load_training_frame())
    current_features = prepared[model.features].iloc[-1].to_dict()
    signal = model.predict_signal(current_features)

    explainer = ExplainerModule(mode="local")
    explanation = explainer.explain_signal(signal, current_features)

    ensemble_accuracy = float(metrics["ensemble_accuracy"])
    llm_latency_ms = float(explanation["latency_ms"])

    passed = ensemble_accuracy >= min_accuracy and llm_latency_ms <= max_llm_latency_ms

    result: dict[str, float | bool | str] = {
        "phase": "phase_6",
        "ensemble_accuracy": round(ensemble_accuracy, 6),
        "minimum_required_accuracy": min_accuracy,
        "llm_latency_ms": round(llm_latency_ms, 2),
        "maximum_allowed_latency_ms": max_llm_latency_ms,
        "status": "pass" if passed else "fail",
        "passed": passed,
    }

    return result


def main() -> int:
    result = run_phase6_benchmark()

    out_dir = ROOT / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "phase6_benchmark.json"
    out_file.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(json.dumps(result, indent=2))

    return 0 if bool(result["passed"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
