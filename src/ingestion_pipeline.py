"""
Real ingestion pipeline for EigenTrades.

Pipeline stages:
1) Source poll (CSV or HTTP API)
2) Normalize to canonical OHLCV schema
3) Idempotent Oracle upsert (MERGE)
4) Checkpoint persistence for orchestration
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import time
from typing import Any, Protocol

import pandas as pd
import requests

from oracle import OracleClient, create_client_from_env

logger = logging.getLogger("ingestion")


@dataclass(frozen=True)
class CandleRecord:
    symbol: str
    time: datetime
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: float
    source: str
    event_id: str


class SourceAdapter(Protocol):
    def fetch(self, since: datetime | None = None) -> list[dict[str, Any]]:
        ...


class CsvFolderSource:
    """Poll CSV files from a folder and normalize columns to expected names."""

    def __init__(self, folder: Path):
        self.folder = folder

    def fetch(self, since: datetime | None = None) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        if not self.folder.exists():
            return rows

        for csv_file in sorted(self.folder.glob("*.csv")):
            df = pd.read_csv(csv_file)
            if df.empty:
                continue

            df = _align_columns(df)
            if "time" not in df.columns:
                continue

            df["time"] = pd.to_datetime(df["time"], utc=True, errors="coerce")
            df = df.dropna(subset=["time", "symbol", "open", "high", "low", "close", "volume"])

            if since is not None:
                since_ts = pd.Timestamp(since)
                if since_ts.tz is None:
                    since_ts = since_ts.tz_localize("UTC")
                else:
                    since_ts = since_ts.tz_convert("UTC")
                df = df[df["time"] > since_ts]

            for record in df.to_dict(orient="records"):
                record["source"] = f"csv:{csv_file.name}"
                rows.append(record)

        return rows


class HttpJsonSource:
    """Poll a JSON API that returns an array of OHLCV rows."""

    def __init__(self, url: str, timeout_seconds: int = 20, headers: dict[str, str] | None = None):
        self.url = url
        self.timeout_seconds = timeout_seconds
        self.headers = headers or {}

    def fetch(self, since: datetime | None = None) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if since is not None:
            params["since"] = since.astimezone(timezone.utc).isoformat()

        response = requests.get(
            self.url,
            params=params,
            headers=self.headers,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()

        if isinstance(payload, dict) and "data" in payload:
            items = payload["data"]
        else:
            items = payload

        if not isinstance(items, list):
            raise ValueError("HTTP source must return a list or {data: [...]} payload")

        df = pd.DataFrame(items)
        if df.empty:
            return []

        df = _align_columns(df)
        if "time" not in df.columns:
            raise ValueError("HTTP source payload missing time column")

        df["time"] = pd.to_datetime(df["time"], utc=True, errors="coerce")
        df = df.dropna(subset=["time", "symbol", "open", "high", "low", "close", "volume"])

        return [
            {
                **row,
                "source": f"http:{self.url}",
            }
            for row in df.to_dict(orient="records")
        ]


class OracleTradeLoader:
    """Idempotent load into historical_trade_data using MERGE."""

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

    def __init__(self, oracle_client: OracleClient):
        self.oracle_client = oracle_client

    def load(self, records: list[CandleRecord], batch_size: int = 1000) -> int:
        if not records:
            return 0

        rows = [
            {
                "symbol": record.symbol,
                "event_time": record.time,
                "open_price": record.open_price,
                "high_price": record.high_price,
                "low_price": record.low_price,
                "close_price": record.close_price,
                "volume": record.volume,
            }
            for record in records
        ]

        return self.oracle_client.execute_many(self.MERGE_SQL, rows, batch_size=batch_size)


class IngestionPipeline:
    def __init__(
        self,
        source: SourceAdapter,
        loader: OracleTradeLoader,
        checkpoint_file: Path,
    ):
        self.source = source
        self.loader = loader
        self.checkpoint_file = checkpoint_file

    def run_once(self) -> dict[str, Any]:
        started_at = time.time()
        since = self._read_checkpoint()
        raw_items = self.source.fetch(since)
        normalized = normalize_rows(raw_items)
        loaded = self.loader.load(normalized)

        if normalized:
            last_ts = max(r.time for r in normalized)
            self._write_checkpoint(last_ts)

        duration_ms = round((time.time() - started_at) * 1000, 2)
        result = {
            "raw_items": len(raw_items),
            "normalized": len(normalized),
            "loaded": loaded,
            "duration_ms": duration_ms,
            "since": since.isoformat() if since else None,
        }

        logger.info("Ingestion run complete: %s", result)
        return result

    def run_forever(self, interval_seconds: int = 15) -> None:
        while True:
            try:
                self.run_once()
            except Exception:
                logger.exception("Ingestion run failed")
            time.sleep(interval_seconds)

    def _read_checkpoint(self) -> datetime | None:
        if not self.checkpoint_file.exists():
            return None

        data = json.loads(self.checkpoint_file.read_text(encoding="utf-8"))
        value = data.get("last_event_time")
        if not value:
            return None
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    def _write_checkpoint(self, value: datetime) -> None:
        self.checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
        self.checkpoint_file.write_text(
            json.dumps({"last_event_time": value.astimezone(timezone.utc).isoformat()}, indent=2),
            encoding="utf-8",
        )


def normalize_rows(raw_rows: list[dict[str, Any]]) -> list[CandleRecord]:
    if not raw_rows:
        return []

    df = pd.DataFrame(raw_rows)
    if df.empty:
        return []

    df = _align_columns(df)
    required = ["symbol", "time", "open", "high", "low", "close", "volume"]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required fields for normalization: {missing}")

    df["time"] = pd.to_datetime(df["time"], utc=True, errors="coerce")
    for numeric in ["open", "high", "low", "close", "volume"]:
        df[numeric] = pd.to_numeric(df[numeric], errors="coerce")

    df = df.dropna(subset=required)
    df["symbol"] = df["symbol"].astype(str).str.upper().str.strip()
    df = df[df["symbol"] != ""]
    df = df[df["volume"] >= 0]

    records: list[CandleRecord] = []
    for item in df.to_dict(orient="records"):
        event_id = _build_event_id(item)
        event_time = item["time"]
        if isinstance(event_time, pd.Timestamp):
            event_time = event_time.to_pydatetime()

        records.append(
            CandleRecord(
                symbol=str(item["symbol"]),
                time=event_time.astimezone(timezone.utc),
                open_price=float(item["open"]),
                high_price=float(item["high"]),
                low_price=float(item["low"]),
                close_price=float(item["close"]),
                volume=float(item["volume"]),
                source=str(item.get("source", "unknown")),
                event_id=event_id,
            )
        )

    # Deduplicate by deterministic event id
    deduped: dict[str, CandleRecord] = {record.event_id: record for record in records}
    return sorted(deduped.values(), key=lambda x: x.time)


def _align_columns(df: pd.DataFrame) -> pd.DataFrame:
    mapping = {
        "timestamp": "time",
        "datetime": "time",
        "date": "time",
        "open_price": "open",
        "high_price": "high",
        "low_price": "low",
        "close_price": "close",
        "qty": "volume",
    }

    normalized_columns = {col: mapping.get(col.lower(), col.lower()) for col in df.columns}
    return df.rename(columns=normalized_columns)


def _build_event_id(item: dict[str, Any]) -> str:
    raw = "|".join(
        [
            str(item.get("symbol", "")),
            str(pd.Timestamp(item.get("time")).isoformat()),
            str(item.get("open", "")),
            str(item.get("high", "")),
            str(item.get("low", "")),
            str(item.get("close", "")),
            str(item.get("volume", "")),
        ]
    )
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def build_pipeline_from_env() -> IngestionPipeline:
    import os

    configured_kind = os.getenv("INGESTION_SOURCE", "csv").lower()

    if configured_kind == "csv":
        source: SourceAdapter = CsvFolderSource(Path("data"))
    elif configured_kind == "http":
        api_url = os.getenv("INGESTION_API_URL", "")
        if not api_url:
            raise ValueError("INGESTION_API_URL is required when INGESTION_SOURCE=http")
        source = HttpJsonSource(api_url)
    else:
        raise ValueError("INGESTION_SOURCE must be one of: csv, http")

    checkpoint = Path("results") / "ingestion_state.json"
    oracle_client = create_client_from_env()
    loader = OracleTradeLoader(oracle_client)
    return IngestionPipeline(source=source, loader=loader, checkpoint_file=checkpoint)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    pipeline = build_pipeline_from_env()
    result = pipeline.run_once()
    print(json.dumps(result, indent=2))
