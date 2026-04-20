# Real Ingestion Pipeline Guide

This project now includes a production-style ingestion orchestrator in src/ingestion_pipeline.py.

## What It Does

- Polls from a source adapter:
  - CSV folder polling (default)
  - HTTP JSON polling
- Normalizes payloads into canonical OHLCV format
- Deduplicates events with deterministic event_id
- Loads into Oracle using idempotent MERGE on (symbol, time)
- Persists checkpoint to results/ingestion_state.json

## Required Environment Variables

- ORACLE_USER
- ORACLE_PASSWORD
- ORACLE_DSN
- INGESTION_SOURCE: csv or http
- INGESTION_API_URL: required when INGESTION_SOURCE=http

## Expected Input Schema

The pipeline accepts any of these aliases and normalizes them:

- time: time, timestamp, datetime, date
- open: open, open_price
- high: high, high_price
- low: low, low_price
- close: close, close_price
- volume: volume, qty
- symbol

## Run Once

From project root:

python src/ingestion_pipeline.py

## Continuous Polling

Import and run from your process manager:

from ingestion_pipeline import build_pipeline_from_env
pipeline = build_pipeline_from_env()
pipeline.run_forever(interval_seconds=15)

## Notes

- The loader uses MERGE into historical_trade_data for idempotent upserts.
- Checkpointing is timestamp-based (last successfully normalized event time).
- You can add more source adapters by implementing SourceAdapter.fetch().
