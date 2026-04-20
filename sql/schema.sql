-- ============================================================================
-- EigenTrade: Database Schema for Historical Trade Data
-- Designed for Oracle PL/SQL with partition-based optimization
-- Supports 10-20 million historical records with sub-second queries
-- ============================================================================

-- Core trade data table (partitioned by year for pruning)
CREATE TABLE historical_trade_data (
    trade_id        NUMBER GENERATED ALWAYS AS IDENTITY,
    symbol          VARCHAR2(20) NOT NULL,
    time            TIMESTAMP NOT NULL,
    open_price      NUMBER(12,4),
    high_price      NUMBER(12,4),
    low_price       NUMBER(12,4),
    close_price     NUMBER(12,4),
    volume          NUMBER(15),
    expiry_date     DATE,
    daily_return    NUMBER(10,6) GENERATED ALWAYS AS (
        (close_price - open_price) / NULLIF(open_price, 0)
    ) VIRTUAL,
    CONSTRAINT pk_trade PRIMARY KEY (trade_id, time)
)
PARTITION BY RANGE (time) (
    PARTITION p_2011 VALUES LESS THAN (TIMESTAMP '2012-01-01 00:00:00'),
    PARTITION p_2012 VALUES LESS THAN (TIMESTAMP '2013-01-01 00:00:00'),
    PARTITION p_2013 VALUES LESS THAN (TIMESTAMP '2014-01-01 00:00:00'),
    PARTITION p_2014 VALUES LESS THAN (TIMESTAMP '2015-01-01 00:00:00'),
    PARTITION p_2015 VALUES LESS THAN (TIMESTAMP '2016-01-01 00:00:00'),
    PARTITION p_2016 VALUES LESS THAN (TIMESTAMP '2017-01-01 00:00:00'),
    PARTITION p_2017 VALUES LESS THAN (TIMESTAMP '2018-01-01 00:00:00'),
    PARTITION p_2018 VALUES LESS THAN (TIMESTAMP '2019-01-01 00:00:00'),
    PARTITION p_2019 VALUES LESS THAN (TIMESTAMP '2020-01-01 00:00:00'),
    PARTITION p_2020 VALUES LESS THAN (TIMESTAMP '2021-01-01 00:00:00'),
    PARTITION p_2021 VALUES LESS THAN (TIMESTAMP '2022-01-01 00:00:00'),
    PARTITION p_2022 VALUES LESS THAN (TIMESTAMP '2023-01-01 00:00:00'),
    PARTITION p_2023 VALUES LESS THAN (TIMESTAMP '2024-01-01 00:00:00'),
    PARTITION p_2024 VALUES LESS THAN (TIMESTAMP '2025-01-01 00:00:00'),
    PARTITION p_2025 VALUES LESS THAN (TIMESTAMP '2026-01-01 00:00:00'),
    PARTITION p_future VALUES LESS THAN (MAXVALUE)
);

-- Indexes
CREATE INDEX idx_sym_time ON historical_trade_data (symbol, time) LOCAL;
CREATE INDEX idx_sym_close ON historical_trade_data (symbol, time, close_price, volume) LOCAL COMPRESS 2;

-- ML prediction log
CREATE TABLE prediction_log (
    prediction_id   NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    symbol          VARCHAR2(20) NOT NULL,
    prediction_time TIMESTAMP DEFAULT SYSTIMESTAMP,
    signal          NUMBER(1),         -- 0 = Hold, 1 = Buy
    confidence      NUMBER(5,4),
    ridge_decision  NUMBER(1),
    forest_prob     NUMBER(5,4),
    top_factor      VARCHAR2(50),
    latency_ms      NUMBER(8,2),
    features_json   CLOB               -- Snapshot of features at prediction time
);

-- Trade execution log
CREATE TABLE trade_log (
    log_id          NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    symbol          VARCHAR2(20) NOT NULL,
    entry_date      TIMESTAMP,
    entry_price     NUMBER(12,4),
    exit_date       TIMESTAMP,
    exit_price      NUMBER(12,4),
    quantity        NUMBER(10),
    pnl             NUMBER(14,4),
    pnl_pct         NUMBER(8,4),
    reason          VARCHAR2(200),
    ai_explanation  CLOB
);

-- ============================================================================
-- Ingestion staging and audit tables (production operations)
-- ============================================================================

CREATE TABLE ingestion_stage_data (
    stage_id         NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id           VARCHAR2(64) NOT NULL,
    source           VARCHAR2(30) NOT NULL,
    event_id         VARCHAR2(64) NOT NULL,
    symbol           VARCHAR2(20) NOT NULL,
    event_time       TIMESTAMP NOT NULL,
    open_price       NUMBER(12,4),
    high_price       NUMBER(12,4),
    low_price        NUMBER(12,4),
    close_price      NUMBER(12,4),
    volume           NUMBER(15),
    ingest_status    VARCHAR2(20) DEFAULT 'STAGED',
    ingested_at      TIMESTAMP DEFAULT SYSTIMESTAMP,
    CONSTRAINT uq_ingestion_event UNIQUE (source, event_id)
);

CREATE INDEX idx_ing_stage_run ON ingestion_stage_data (run_id);
CREATE INDEX idx_ing_stage_symbol_time ON ingestion_stage_data (symbol, event_time);

CREATE TABLE ingestion_run_audit (
    audit_id          NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id            VARCHAR2(64) NOT NULL,
    source            VARCHAR2(30) NOT NULL,
    status            VARCHAR2(20) NOT NULL,
    rows_fetched      NUMBER DEFAULT 0,
    rows_normalized   NUMBER DEFAULT 0,
    rows_loaded       NUMBER DEFAULT 0,
    retries_used      NUMBER DEFAULT 0,
    start_time        TIMESTAMP,
    end_time          TIMESTAMP,
    duration_ms       NUMBER(12,2),
    checkpoint_from   TIMESTAMP,
    checkpoint_to     TIMESTAMP,
    error_message     VARCHAR2(2000),
    dead_letter_path  VARCHAR2(500),
    created_at        TIMESTAMP DEFAULT SYSTIMESTAMP,
    CONSTRAINT uq_ingestion_run UNIQUE (run_id)
);

CREATE INDEX idx_ing_audit_status_time ON ingestion_run_audit (status, created_at);
