"""Production-safe ingestion orchestration for EigenTrades."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import time
import uuid
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
	dead_letter_dir: Path
	poll_seconds: int
	batch_size: int
	max_retries: int
	retry_backoff_seconds: int
	audit_to_db: bool
	enable_db_optimization: bool
	require_db_optimization: bool

	@classmethod
	def from_env(cls) -> "PipelineConfig":
		source = os.getenv("INGESTION_SOURCE", "csv").strip().lower()
		return cls(
			source=source,
			csv_dir=Path(os.getenv("INGESTION_CSV_DIR", "data")),
			api_url=os.getenv("INGESTION_API_URL", "").strip(),
			api_token=os.getenv("INGESTION_API_TOKEN", "").strip(),
			checkpoint_file=Path(os.getenv("INGESTION_CHECKPOINT", "results/ingestion_state.json")),
			dead_letter_dir=Path(os.getenv("INGESTION_DEAD_LETTER_DIR", "results/dead_letter")),
			poll_seconds=int(os.getenv("INGESTION_POLL_SECONDS", "15")),
			batch_size=int(os.getenv("INGESTION_BATCH_SIZE", "1000")),
			max_retries=int(os.getenv("INGESTION_MAX_RETRIES", "3")),
			retry_backoff_seconds=int(os.getenv("INGESTION_RETRY_BACKOFF_SECONDS", "2")),
			audit_to_db=os.getenv("INGESTION_AUDIT_TO_DB", "true").strip().lower() == "true",
			enable_db_optimization=os.getenv("INGESTION_ENABLE_DB_OPTIMIZATION", "true").strip().lower() == "true",
			require_db_optimization=os.getenv("INGESTION_REQUIRE_DB_OPTIMIZATION", "false").strip().lower() == "true",
		)


class OracleOptimizationManager:
	"""Ensures optimization SQL objects are present and refreshed at runtime."""

	MVIEW_CHECK_SQL = """
		SELECT mview_name
		FROM user_mviews
		WHERE mview_name = 'MARKET_SIGNALS'
	"""

	REFRESH_SQL = """
		BEGIN
			DBMS_MVIEW.REFRESH('MARKET_SIGNALS', 'F');
		END;
	"""

	def __init__(self, client: OracleClient, strict: bool = False):
		self.client = client
		self.strict = strict
		self._has_market_signals: bool | None = None

	def verify(self) -> bool:
		if self._has_market_signals is not None:
			return self._has_market_signals

		rows = self.client.fetch_all(self.MVIEW_CHECK_SQL)
		has_mview = len(rows) > 0
		self._has_market_signals = has_mview

		if has_mview:
			logger.info("DB optimization active: materialized view MARKET_SIGNALS detected")
			return True

		message = (
			"DB optimization inactive: MARKET_SIGNALS not found. "
			"Apply sql/optimization_strategy.sql in Oracle to enable optimized feature retrieval."
		)
		if self.strict:
			raise RuntimeError(message)
		logger.warning(message)
		return False

	def refresh(self) -> None:
		if not self.verify():
			return

		try:
			self.client.execute(self.REFRESH_SQL)
			logger.info("Refreshed MARKET_SIGNALS materialized view")
		except Exception as exc:
			if "ORA-12003" in str(exc) or "ORA-12018" in str(exc):
				logger.warning("Could not fast-refresh MARKET_SIGNALS; check materialized view logs and refresh mode")
				return
			raise


@dataclass
class IngestionRunStats:
	run_id: str
	source: str
	status: str
	rows_fetched: int = 0
	rows_normalized: int = 0
	rows_loaded: int = 0
	retries_used: int = 0
	start_time: datetime | None = None
	end_time: datetime | None = None
	duration_ms: float = 0.0
	checkpoint_from: datetime | None = None
	checkpoint_to: datetime | None = None
	error_message: str | None = None
	dead_letter_path: str | None = None


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
			raise ValueError("HTTP source must return list payload or dict with data list")

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


class DeadLetterSink:
	def __init__(self, root: Path):
		self.root = root

	def write(self, run_id: str, error_message: str, payload: list[dict[str, Any]] | None = None) -> str:
		self.root.mkdir(parents=True, exist_ok=True)
		path = self.root / f"ingestion_{run_id}.json"
		content = {
			"run_id": run_id,
			"error": error_message,
			"created_at": datetime.now(timezone.utc).isoformat(),
			"payload": payload or [],
		}
		path.write_text(json.dumps(content, indent=2, default=str), encoding="utf-8")
		return str(path)


class IngestionAuditWriter:
	INSERT_SQL = """
		INSERT INTO ingestion_run_audit (
			run_id,
			source,
			status,
			rows_fetched,
			rows_normalized,
			rows_loaded,
			retries_used,
			start_time,
			end_time,
			duration_ms,
			checkpoint_from,
			checkpoint_to,
			error_message,
			dead_letter_path
		) VALUES (
			:run_id,
			:source,
			:status,
			:rows_fetched,
			:rows_normalized,
			:rows_loaded,
			:retries_used,
			:start_time,
			:end_time,
			:duration_ms,
			:checkpoint_from,
			:checkpoint_to,
			:error_message,
			:dead_letter_path
		)
	"""

	def __init__(self, client: OracleClient | None):
		self.client = client

	def write(self, stats: IngestionRunStats) -> None:
		if self.client is None:
			return

		params = {
			"run_id": stats.run_id,
			"source": stats.source,
			"status": stats.status,
			"rows_fetched": stats.rows_fetched,
			"rows_normalized": stats.rows_normalized,
			"rows_loaded": stats.rows_loaded,
			"retries_used": stats.retries_used,
			"start_time": stats.start_time,
			"end_time": stats.end_time,
			"duration_ms": stats.duration_ms,
			"checkpoint_from": stats.checkpoint_from,
			"checkpoint_to": stats.checkpoint_to,
			"error_message": stats.error_message,
			"dead_letter_path": stats.dead_letter_path,
		}

		try:
			self.client.execute(self.INSERT_SQL, params)
		except Exception as exc:
			if "ORA-00942" in str(exc):
				logger.warning("ingestion_run_audit table not found; skipping DB audit write")
				return
			logger.exception("Failed to write ingestion audit")


class OracleTradeLoader:
	STAGE_INSERT_SQL = """
		INSERT INTO ingestion_stage_data (
			run_id,
			source,
			event_id,
			symbol,
			event_time,
			open_price,
			high_price,
			low_price,
			close_price,
			volume
		) VALUES (
			:run_id,
			:source,
			:event_id,
			:symbol,
			:event_time,
			:open_price,
			:high_price,
			:low_price,
			:close_price,
			:volume
		)
	"""

	STAGE_MERGE_SQL = """
		MERGE INTO historical_trade_data t
		USING (
			SELECT symbol, event_time, open_price, high_price, low_price, close_price, volume
			FROM ingestion_stage_data
			WHERE run_id = :run_id
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

	DIRECT_MERGE_SQL = """
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

	def load(self, run_id: str, source_name: str, frame: pd.DataFrame, batch_size: int = 1000) -> int:
		if frame.empty:
			return 0

		rows = self._to_rows(run_id, source_name, frame)

		try:
			self.client.execute_many(self.STAGE_INSERT_SQL, rows, batch_size=batch_size)
			self.client.execute(self.STAGE_MERGE_SQL, {"run_id": run_id})
			return len(rows)
		except Exception as exc:
			if "ORA-00942" not in str(exc):
				raise
			logger.warning("ingestion_stage_data table not found; falling back to direct merge")
			direct_rows = [
				{
					"symbol": row["symbol"],
					"event_time": row["event_time"],
					"open_price": row["open_price"],
					"high_price": row["high_price"],
					"low_price": row["low_price"],
					"close_price": row["close_price"],
					"volume": row["volume"],
				}
				for row in rows
			]
			return self.client.execute_many(self.DIRECT_MERGE_SQL, direct_rows, batch_size=batch_size)

	@staticmethod
	def _to_rows(run_id: str, source_name: str, frame: pd.DataFrame) -> list[dict[str, Any]]:
		rows: list[dict[str, Any]] = []
		for rec in frame.to_dict(orient="records"):
			rows.append(
				{
					"run_id": run_id,
					"source": source_name,
					"event_id": _event_id(rec),
					"symbol": str(rec["symbol"]),
					"event_time": pd.Timestamp(rec["time"]).to_pydatetime(),
					"open_price": float(rec["open"]),
					"high_price": float(rec["high"]),
					"low_price": float(rec["low"]),
					"close_price": float(rec["close"]),
					"volume": float(rec["volume"]),
				}
			)
		return rows


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
	deduped: dict[str, dict[str, Any]] = {}
	for rec in frame.to_dict(orient="records"):
		deduped[_event_id(rec)] = rec
	out = pd.DataFrame(deduped.values())
	return out.sort_values(["symbol", "time"]).reset_index(drop=True)


class IngestionPipeline:
	def __init__(
		self,
		config: PipelineConfig,
		source: SourceAdapter,
		loader: OracleTradeLoader,
		checkpoint: CheckpointStore,
		dead_letter: DeadLetterSink,
		audit: IngestionAuditWriter,
		optimization: OracleOptimizationManager | None = None,
	):
		self.config = config
		self.source = source
		self.loader = loader
		self.checkpoint = checkpoint
		self.dead_letter = dead_letter
		self.audit = audit
		self.optimization = optimization

	def run_once(self) -> dict[str, Any]:
		stats = IngestionRunStats(
			run_id=str(uuid.uuid4()),
			source=self.config.source,
			status="FAILED",
			start_time=datetime.now(timezone.utc),
			checkpoint_from=self.checkpoint.read(),
		)

		incoming = pd.DataFrame()
		started = time.time()
		try:
			if self.optimization is not None:
				self.optimization.verify()

			incoming = self._fetch_with_retries(stats)
			stats.rows_fetched = int(len(incoming))

			normalized = dedupe_frame(incoming)
			stats.rows_normalized = int(len(normalized))

			loaded = self.loader.load(
				run_id=stats.run_id,
				source_name=self.config.source,
				frame=normalized,
				batch_size=self.config.batch_size,
			)
			stats.rows_loaded = int(loaded)

			if self.optimization is not None and loaded > 0:
				self.optimization.refresh()

			if not normalized.empty:
				max_ts = pd.Timestamp(normalized["time"].max()).to_pydatetime()
				self.checkpoint.write(max_ts)
				stats.checkpoint_to = max_ts

			stats.status = "SUCCESS"
		except Exception as exc:
			stats.error_message = str(exc)
			payload = incoming.to_dict(orient="records") if not incoming.empty else []
			stats.dead_letter_path = self.dead_letter.write(stats.run_id, str(exc), payload[:200])
			raise
		finally:
			stats.end_time = datetime.now(timezone.utc)
			stats.duration_ms = round((time.time() - started) * 1000, 2)
			self.audit.write(stats)

		result = {
			"run_id": stats.run_id,
			"status": stats.status,
			"retries_used": stats.retries_used,
			"rows_fetched": stats.rows_fetched,
			"rows_normalized": stats.rows_normalized,
			"rows_loaded": stats.rows_loaded,
			"duration_ms": stats.duration_ms,
			"checkpoint_from": stats.checkpoint_from.isoformat() if stats.checkpoint_from else None,
			"checkpoint_to": stats.checkpoint_to.isoformat() if stats.checkpoint_to else None,
		}
		logger.info("Ingestion completed: %s", result)
		return result

	def run_forever(self) -> None:
		while True:
			try:
				self.run_once()
			except Exception:
				logger.exception("Ingestion cycle failed")
			time.sleep(self.config.poll_seconds)

	def _fetch_with_retries(self, stats: IngestionRunStats) -> pd.DataFrame:
		attempts = self.config.max_retries + 1
		last_error: Exception | None = None

		for attempt in range(attempts):
			try:
				return self.source.fetch(since=stats.checkpoint_from)
			except Exception as exc:
				last_error = exc
				if attempt >= self.config.max_retries:
					break
				stats.retries_used += 1
				sleep_seconds = self.config.retry_backoff_seconds * (attempt + 1)
				logger.warning(
					"Fetch attempt %s failed (%s). Retrying in %ss",
					attempt + 1,
					exc,
					sleep_seconds,
				)
				time.sleep(sleep_seconds)

		assert last_error is not None
		raise last_error


def build_pipeline_from_env() -> IngestionPipeline:
	cfg = PipelineConfig.from_env()
	if cfg.source == "csv":
		source: SourceAdapter = CsvSource(cfg.csv_dir)
	elif cfg.source == "http":
		if not cfg.api_url:
			raise ValueError("INGESTION_API_URL is required when INGESTION_SOURCE=http")
		source = HttpApiSource(cfg.api_url, cfg.api_token)
	else:
		raise ValueError("INGESTION_SOURCE must be one of: csv, http")

	client = create_client_from_env()
	loader = OracleTradeLoader(client)
	checkpoint = CheckpointStore(cfg.checkpoint_file)
	dead_letter = DeadLetterSink(cfg.dead_letter_dir)
	audit = IngestionAuditWriter(client if cfg.audit_to_db else None)
	optimization = (
		OracleOptimizationManager(client, strict=cfg.require_db_optimization)
		if cfg.enable_db_optimization
		else None
	)

	return IngestionPipeline(
		config=cfg,
		source=source,
		loader=loader,
		checkpoint=checkpoint,
		dead_letter=dead_letter,
		audit=audit,
		optimization=optimization,
	)


if __name__ == "__main__":
	logging.basicConfig(level=logging.INFO)
	pipeline = build_pipeline_from_env()
	result = pipeline.run_once()
	print(json.dumps(result, indent=2))
