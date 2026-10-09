CREATE TABLE IF NOT EXISTS {table}
(
    run_id String,
    event_id String,
    timestamp DateTime64(6, 'UTC'),
    stage LowCardinality(String),
    event_type LowCardinality(String),
    severity LowCardinality(String),
    source LowCardinality(String),
    sequence Nullable(UInt64),
    target LowCardinality(String),
    challenge_family LowCardinality(String),
    test_execution_id String,
    suite LowCardinality(String),
    outcome LowCardinality(String),
    executed UInt8,
    attempt Nullable(UInt8),
    duration_ms Nullable(Float64),
    patch_hash String,
    suite_hash String,
    policy_hash String,
    finding_key String,
    baseline_reproduced Nullable(UInt8),
    provider LowCardinality(String),
    activity LowCardinality(String),
    target_revision String,
    environment LowCardinality(String),
    model LowCardinality(String),
    cost_reservation_usd Nullable(Float64),
    measured_cost_usd Nullable(Float64),
    inserted_at DateTime64(6, 'UTC')
)
ENGINE = ReplacingMergeTree(inserted_at)
PARTITION BY toYYYYMM(timestamp)
ORDER BY (run_id, event_id)
