-- Explicit additive migration with administrator credentials; runtime stays SELECT/INSERT only.
ALTER TABLE {table}
ADD COLUMN IF NOT EXISTS provider LowCardinality(String) DEFAULT '',
ADD COLUMN IF NOT EXISTS activity LowCardinality(String) DEFAULT '',
ADD COLUMN IF NOT EXISTS target_revision String DEFAULT '',
ADD COLUMN IF NOT EXISTS environment LowCardinality(String) DEFAULT '',
ADD COLUMN IF NOT EXISTS model LowCardinality(String) DEFAULT '',
ADD COLUMN IF NOT EXISTS cost_reservation_usd Nullable(Float64) DEFAULT NULL,
ADD COLUMN IF NOT EXISTS measured_cost_usd Nullable(Float64) DEFAULT NULL
