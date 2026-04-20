"""Production-style ingestion orchestration for EigenTrades."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import time
from typing import Any, Protocol

import pandas as pd
import requests

from loaddata import load_csv_directory, normalize_ohlcv_frame
from oracle import OracleClient, create_client_from_env

logger = logging.getLogger("ingestion")


@dataclass(frozen=True)
class PipelineConfig:
	source: str
	csv_dir: Path
	api_url: str
	api_token: str
	checkpoint_file: Path
	poll_seconds: int
	batch_size: int

	@classmethod
	def from_env(cls) -> "PipelineConfig":
		source = os.getenv("INGESTION_SOURCE", "csv").strip().lower()
		return cls(
			source=source,
			csv_dir=Path(os.getenv("INGESTION_CSV_DIR", "data")),
			api_url=os.getenv("INGESTION_API_URL", "").strip(),
			api_token=os.getenv("INGESTION_API_TOKEN", "").strip(),
			checkpoint_file=Path(os.getenv("INGESTION_CHECKPOINT", "results/ingestion_state.json")),
			poll_seconds=int(os.getenv("INGESTION_POLL_SECONDS", "15")),
			batch_size=int(os.getenv("INGESTION_BATCH_SIZE", "1000")),
		)


class SourceAdapter(Protocol):
	def fetch(self, since: datetime | None = None) -> pd.DataFrame:
		...


class CsvSource:
	def __init__(self, csv_dir: Path):
		self.csv_dir = csv_dir

	def fetch(self, since: datetime | None = None) -> pd.DataFrame:
		frame = load_csv_directory(self.csv_dir)
		if frame.empty:
			return frame

		if since is not None:
			frame = frame[frame["time"] > pd.Timestamp(since)]

		return frame


class HttpApiSource:
	def __init__(self, api_url: str, api_token: str = ""):
		self.api_url = api_url
		self.api_token = api_token

	def fetch(self, since: datetime | None = None) -> pd.DataFrame:
		headers: dict[str, str] = {}
		if self.api_token:
			headers["Authorization"] = f"Bearer {self.api_token}"

		params: dict[str, Any] = {}
		if since is not None:
			params["since"] = since.astimezone(timezone.utc).isoformat()

		response = requests.get(self.api_url, headers=headers, params=params, timeout=25)
		response.raise_for_status()

		payload = response.json()
		rows = payload.get("data", payload) if isinstance(payload, dict) else payload
		if not isinstance(rows, list):
			raise ValueError("HTTP source must return list payload or dict containing data list")

		return normalize_ohlcv_frame(pd.DataFrame(rows))


class CheckpointStore:
	def __init__(self, path: Path):
		self.path = path

	def read(self) -> datetime | None:
		if not self.path.exists():
			return None

		data = json.loads(self.path.read_text(encoding="utf-8"))
		value = data.get("last_event_time")
		if not value:
			return None

		parsed = datetime.fromisoformat(value)
		if parsed.tzinfo is None:
			return parsed.replace(tzinfo=timezone.utc)
		return parsed.astimezone(timezone.utc)

	def write(self, dt: datetime) -> None:
		self.path.parent.mkdir(parents=True, exist_ok=True)
		self.path.write_text(
			json.dumps({"last_event_time": dt.astimezone(timezone.utc).isoformat()}, indent=2),
			encoding="utf-8",
		)


class OracleTradeLoader:
	MERGE_SQL = """
		MERGE INTO historical_trade_data t
		USING (
			SELECT
				:symbol AS symbol,
				:event_time AS event_time,
				:open_price AS open_price,
				:high_price AS high_price,
				:low_price AS low_price,
				:close_price AS close_price,
				:volume AS volume
			FROM dual
		) src
		ON (t.symbol = src.symbol AND t.time = src.event_time)
		WHEN MATCHED THEN
			UPDATE SET
				t.open_price = src.open_price,
				t.high_price = src.high_price,
				t.low_price = src.low_price,
				t.close_price = src.close_price,
				t.volume = src.volume
		WHEN NOT MATCHED THEN
			INSERT (symbol, time, open_price, high_price, low_price, close_price, volume)
			VALUES (src.symbol, src.event_time, src.open_price, src.high_price, src.low_price, src.close_price, src.volume)
	"""

	def __init__(self, client: OracleClient):
		self.client = client

	def load(self, frame: pd.DataFrame, batch_size: int = 1000) -> int:
		if frame.empty:
			return 0

		rows: list[dict[str, Any]] = []
		for rec in frame.to_dict(orient="records"):
			event_time = pd.Timestamp(rec["time"]).to_pydatetime()
			rows.append(
				{
					"symbol": str(rec["symbol"]),
					"event_time": event_time,
					"open_price": float(rec["open"]),
					"high_price": float(rec["high"]),
					"low_price": float(rec["low"]),
					"close_price": float(rec["close"]),
					"volume": float(rec["volume"]),
				}
			)

		return self.client.execute_many(self.MERGE_SQL, rows, batch_size=batch_size)


def _event_id(row: dict[str, Any]) -> str:
	raw = "|".join(
		[
			str(row.get("symbol", "")),
			str(pd.Timestamp(row.get("time")).isoformat()),
			str(row.get("open", "")),
			str(row.get("high", "")),
			str(row.get("low", "")),
			str(row.get("close", "")),
			str(row.get("volume", "")),
		]
	)
	return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def dedupe_frame(frame: pd.DataFrame) -> pd.DataFrame:
	if frame.empty:
		return frame

	records = frame.to_dict(orient="records")
	deduped: dict[str, dict[str, Any]] = {}
	for rec in records:
		deduped[_event_id(rec)] = rec
	out = pd.DataFrame(deduped.values())
	return out.sort_values(["symbol", "time"]).reset_index(drop=True)


class IngestionPipeline:
	def __init__(
		self,
		source: SourceAdapter,
		loader: OracleTradeLoader,
		checkpoint: CheckpointStore,
		batch_size: int = 1000,
	):
		self.source = source
		self.loader = loader
		self.checkpoint = checkpoint
		self.batch_size = batch_size

	def run_once(self) -> dict[str, Any]:
		started = time.time()
		since = self.checkpoint.read()

		incoming = self.source.fetch(since=since)
		incoming = dedupe_frame(incoming)

		loaded = self.loader.load(incoming, batch_size=self.batch_size)
		if not incoming.empty:
			max_ts = pd.Timestamp(incoming["time"].max()).to_pydatetime()
			self.checkpoint.write(max_ts)

		duration_ms = round((time.time() - started) * 1000, 2)
		result = {
			"since": since.isoformat() if since else None,
			"rows_normalized": int(len(incoming)),
			"rows_loaded": int(loaded),
			"duration_ms": duration_ms,
		}
		logger.info("Ingestion completed: %s", result)
		return result

	def run_forever(self, interval_seconds: int) -> None:
		while True:
			try:
				self.run_once()
			except Exception:
				logger.exception("Ingestion cycle failed")
			time.sleep(interval_seconds)


def build_pipeline_from_env() -> tuple[IngestionPipeline, int]:
	cfg = PipelineConfig.from_env()
	if cfg.source == "csv":
		source: SourceAdapter = CsvSource(cfg.csv_dir)
	elif cfg.source == "http":
		if not cfg.api_url:
			raise ValueError("INGESTION_API_URL is required when INGESTION_SOURCE=http")
		source = HttpApiSource(cfg.api_url, cfg.api_token)
	else:
		raise ValueError("INGESTION_SOURCE must be one of: csv, http")

	loader = OracleTradeLoader(create_client_from_env())
	checkpoint = CheckpointStore(cfg.checkpoint_file)
	pipeline = IngestionPipeline(
		source=source,
		loader=loader,
		checkpoint=checkpoint,
		batch_size=cfg.batch_size,
	)
	return pipeline, cfg.poll_seconds


if __name__ == "__main__":
	logging.basicConfig(level=logging.INFO)
	pipeline, interval = build_pipeline_from_env()
	result = pipeline.run_once()
	print(json.dumps(result, indent=2))
