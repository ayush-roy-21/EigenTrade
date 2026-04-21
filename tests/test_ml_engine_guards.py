from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd
import pytest

# Allow imports from top-level src directory during pytest runs.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ml_engine import MLEngine


def test_train_raises_clear_error_for_insufficient_rows() -> None:
    engine = MLEngine()
    df = pd.DataFrame({"close": [100.0 + i for i in range(10)]})

    with pytest.raises(ValueError, match="Need at least 30 rows"):
        engine.train(df)


def test_train_raises_clear_error_for_missing_close_column() -> None:
    engine = MLEngine()
    df = pd.DataFrame({"price": [100.0 + i for i in range(50)]})

    with pytest.raises(ValueError, match="must include a 'close' column"):
        engine.train(df)
