# Production Submission Checklist (Today)

This checklist is optimized for a same-day submission of EigenTrades.

## 1. Code and Runtime

- [ ] Pull latest code and verify no uncommitted accidental files.
- [ ] Confirm app boots:
  - Command: python -m streamlit run UI/app.py
- [ ] Confirm ingestion runs once:
  - Command: python src/ingestion_pipeline.py
- [ ] Verify environment variables are set for your demo environment:
  - ORACLE_USER
  - ORACLE_PASSWORD
  - ORACLE_DSN
  - INGESTION_SOURCE
  - INGESTION_CSV_DIR or INGESTION_API_URL

## 2. Data and Database

- [ ] Apply schema objects:
  - Run sql/schema.sql in Oracle
- [ ] Confirm required ingestion tables exist:
  - historical_trade_data
  - ingestion_stage_data
  - ingestion_run_audit
- [ ] Validate at least one successful ingestion audit row exists.

## 3. Tests and Quality Gates

- [ ] Run smoke tests locally:
  - Command: pytest -q
- [ ] Ensure GitHub Actions CI passes on your submission branch.

## 4. Submission Artifacts

- [ ] Include architecture and feature documentation:
  - docs/README.md
  - docs/PROJECT_SUMMARY.md
  - docs/INGESTION_PIPELINE.md
- [ ] Include sample results/screenshots from Streamlit dashboards.
- [ ] Include one short runbook section in your submission note:
  - Setup
  - Start commands
  - Expected outputs

## 5. Risk Notes (Be Transparent)

- [ ] Mention this is a supervised/demo-grade production submission.
- [ ] Mention that operational hardening backlog remains (alerting, autoscaling, secrets manager integration).

## 6. Final Demo Script (5-7 minutes)

- [ ] Show ingestion run output (rows fetched/loaded).
- [ ] Show Strategy Studio backtest with parameter tweak.
- [ ] Show Risk Dashboard metrics and drawdown chart.
- [ ] Show one AI explanation for a trade.

## Fast Validation Commands

- pip install -r requirements.txt
- pip install pytest
- pytest -q
- python src/ingestion_pipeline.py
- python -m streamlit run UI/app.py
