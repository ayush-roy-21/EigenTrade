"""Data loading and normalization utilities for market OHLCV data."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd


COLUMN_ALIASES = {
	"timestamp": "time",
	"datetime": "time",
	"date": "date",
	"open_price": "open",
	"high_price": "high",
	"low_price": "low",
	"close_price": "close",
	"qty": "volume",
	"ticker": "symbol",
	"instrument": "symbol",
}


def _normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
	renamed = {c: COLUMN_ALIASES.get(c.lower(), c.lower()) for c in df.columns}
	return df.rename(columns=renamed)


def normalize_ohlcv_frame(df: pd.DataFrame, symbol: str | None = None) -> pd.DataFrame:
	"""
	Normalize an input frame to canonical columns:
	symbol, time, open, high, low, close, volume
	"""
	frame = _normalize_column_names(df.copy())

	if "time" not in frame.columns and {"date", "time"}.issubset(frame.columns):
		frame["time"] = frame["date"].astype(str) + " " + frame["time"].astype(str)

	# Support datasets that provide separate date and clock columns.
	if "time" not in frame.columns and {"date", "clock"}.issubset(frame.columns):
		frame["time"] = frame["date"].astype(str) + " " + frame["clock"].astype(str)

	if "symbol" not in frame.columns:
		if symbol is None:
			raise ValueError("Input data must include symbol or caller must provide symbol argument")
		frame["symbol"] = symbol
	elif symbol is not None:
		frame["symbol"] = symbol

	required = ["symbol", "time", "open", "high", "low", "close", "volume"]
	missing = [col for col in required if col not in frame.columns]
	if missing:
		raise ValueError(f"Missing required OHLCV fields: {missing}")

	frame = frame[required]
	frame["symbol"] = frame["symbol"].astype(str).str.upper().str.strip()
	frame["time"] = pd.to_datetime(frame["time"], utc=True, errors="coerce")

	for col in ["open", "high", "low", "close", "volume"]:
		frame[col] = pd.to_numeric(frame[col], errors="coerce")

	frame = frame.dropna(subset=required)
	frame = frame[frame["symbol"] != ""]
	frame = frame[frame["volume"] >= 0]
	frame = frame.sort_values(["symbol", "time"]).reset_index(drop=True)

	return frame


def load_csv_file(path: str | Path, symbol: str | None = None) -> pd.DataFrame:
	"""Read one CSV and return canonical OHLCV frame."""
	csv_path = Path(path)
	raw = pd.read_csv(csv_path)
	return normalize_ohlcv_frame(raw, symbol=symbol)


def load_csv_directory(directory: str | Path, pattern: str = "*.csv") -> pd.DataFrame:
	"""Read all CSV files in a directory and return a combined OHLCV frame."""
	root = Path(directory)
	files = sorted(root.glob(pattern))
	if not files:
		return pd.DataFrame(columns=["symbol", "time", "open", "high", "low", "close", "volume"])

	frames = [load_csv_file(file_path) for file_path in files]
	if not frames:
		return pd.DataFrame(columns=["symbol", "time", "open", "high", "low", "close", "volume"])

	return pd.concat(frames, ignore_index=True)
