# Ingestion Pipeline Operations

This runbook covers the production-safe ingestion flow.

## What Is Added

- Retry and backoff for source fetch failures
- Dead-letter output for failed runs
- Run-level audit writes to Oracle
- Stage-table loading before merge into historical_trade_data
- Fallback to direct merge if stage/audit tables are not present

## Required Environment Variables

- ORACLE_USER
- ORACLE_PASSWORD
- ORACLE_DSN
- INGESTION_SOURCE (csv or http)
- INGESTION_CSV_DIR (default: data)
- INGESTION_API_URL (required when source=http)
- INGESTION_API_TOKEN (optional)
- INGESTION_CHECKPOINT (default: results/ingestion_state.json)
- INGESTION_DEAD_LETTER_DIR (default: results/dead_letter)
- INGESTION_POLL_SECONDS (default: 15)
- INGESTION_BATCH_SIZE (default: 1000)
- INGESTION_MAX_RETRIES (default: 3)
- INGESTION_RETRY_BACKOFF_SECONDS (default: 2)
- INGESTION_AUDIT_TO_DB (default: true)

## SQL Apply Order

1. Apply schema objects in sql/schema.sql
2. Confirm these tables exist:
   - ingestion_stage_data
   - ingestion_run_audit

## Run Once

python src/ingestion_pipeline.py

## Continuous Run

Use a service wrapper or scheduler and call run_forever from ingestion_pipeline.py.

## Failure Handling

- Failed runs are written to INGESTION_DEAD_LETTER_DIR
- Audit row captures status, counts, retries, and error message

## Notes

- Stage-table dedupe uses unique constraint on (source, event_id)
- Pipeline remains backward-compatible with direct merge if stage tables are missing
