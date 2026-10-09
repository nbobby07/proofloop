# ClickHouse adapter — implemented, live execution UNVERIFIED

`ClickHouseClient` implements the existing `ClickHouseTelemetry` protocol without
modifying API routes or provider DTOs. Install `backend/telemetry/requirements.txt`
in the backend environment; coordinate shared dependency locking with A.

Configuration: existing `CLICKHOUSE_HOST`, `CLICKHOUSE_PORT`, `CLICKHOUSE_USER`,
`CLICKHOUSE_PASSWORD`, `CLICKHOUSE_SECURE`; optional `CLICKHOUSE_DATABASE=default`.
Developer B's handoff reports `kvjim2jp8d.us-east-2.aws.clickhouse.cloud`, port 8443.
Its creator, account, and ownership are unverified; do not treat it as an authorized
configured service until its owner confirms access.
Read credentials from the ignored environment only. No dotenv loader is installed
here: A owns backend configuration/loading. Never put secrets in VITE variables.

Integration: construct `ClickHouseConfig.from_env()`, call `ClickHouseClient.connect`,
and explicitly call `initialize_schema()` once using a migration-capable account.
Use a restricted runtime account afterward. A persists canonical events before
calling `insert_security_events`, in a worker/threadpool (the adapter is synchronous).
Bound batches to 1000, flush before adaptive queries, replay persisted events on
failure. No durable queue is claimed in this module. Never synthesize success after
`TelemetryUnavailable`; A should return a safe service-unavailable response.

## Proposed metadata convention — requires producer agreement

All metadata is optional for ingestion. Unavailable dimensions remain unavailable.

| Field | Meaning |
|---|---|
| sequence | Unique monotonic integer within a run, across retries/challenges |
| target | Allowlisted target identifier |
| test_execution_id | Stable unique ID for one scheduled check; retries get new IDs |
| suite | security / functional / adversarial / baseline |
| challenge_family | Stable allowlisted attack family |
| outcome | pass / fail / timeout / error / skipped / missing |
| executed | True only when execution actually began |
| attempt | Patch attempt number |
| duration_ms | Backend-measured duration |
| patch_hash, suite_hash, policy_hash | Lowercase SHA-256 of exact execution inputs |
| finding_key | Stable recurrence identity |
| reproduced | Boolean on baseline outcome records |

Emit exactly one terminal outcome record for every required scheduled check,
including missing/skipped/timeouts. The v1 `executions` pattern denominator means
recorded outcome records, including incomplete results; it is NOT a count of
successful executions. Failure numerator includes only explicit `fail` outcomes.
Unknown outcomes remain in denominators. Extended internal metrics separate actual
starts and incomplete checks. Missing records cannot be inferred.

Pass/fail metadata without executed=true is normalized to unknown. Average patch
attempts covers all observed runs, including zero-attempt and in-progress runs;
it is not a terminal-run-only success metric. Verification timing requires exactly
one start/completion pair per run/attempt; repeated/absent pairs stay incomplete.
Coordinate schema.sql package-data inclusion before distributing a non-editable wheel.

Events without complete unique sequence metadata contribute to run_count but
cannot establish verified/rejected current-state counts. Timestamp ties cannot
silently establish order. Metadata conflicts for the same test execution are
excluded from family metrics; producer correction needs a coordinated convention.

Production insertion rejects fixture batches atomically. Messages and arbitrary
metadata are never exported; only documented scalar dimensions are retained.
The producer must redact/approve these dimensions before external transmission.
Queries use FINAL for event-id deduplication, with bound run/context parameters.
High-volume benchmarking/materialized views are PLANNED, not claimed.

`query_failure_patterns(run_id)` uses 30 days of compatible target/suite/policy
history, requires three recorded outcomes per family, and returns at most ten
families ranked by observed failure rate. Missing context returns an empty list.
A controls admission, challenge budget, policy and verdict. Record query results
and selection rationale in A's evidence store.

## Release wiring and validation

The release integrates `TelemetryDelivery` with the FastAPI lifespan. Enable with
`PROOFLOOP_TELEMETRY_ENABLED=1`; it is disabled by default. Every batch is read from
an atomically persisted local manifest, delivered in a single background worker,
and limited to 1000 events. Failed/ambiguous inserts retain the cursor for replay.
Restart replays retained manifests; `FINAL` deduplicates by run and event ID.
Local manifests must be retained as the durable outbox. There is no separate queue.
SQL and connection operations run outside the async request loop. Database outages
never block security execution or the local `/api/analytics` endpoint.

The producer now records canonical `sequence`, approved `target`, patch `attempt`
and exact proposal `patch_hash`. Each completed independent verification round
adds a unique `test_execution_id`, `suite=required_suites`, matching challenge
family, and an honest outcome/completeness flag. These are aggregate round metrics,
NOT individual-check counts. Missing individual-check, timing, suite/policy context
and baseline dimensions stay unavailable. Context-based adaptive recommendations
remain unused. Infrastructure failures without a receipt do not invent test records.
Local analytics include all recorded attempt/round failures and incomplete outcomes;
ClickHouse patterns count only explicit fail outcomes in the failure numerator.

Setup from the repository root with the backend environment active:

```sh
python -m pip install -r backend/telemetry/requirements.txt
# Set CLICKHOUSE_HOST/USER/PASSWORD and TLS settings in the ignored .env.
python -m scripts.telemetry initialize
# Then enable PROOFLOOP_TELEMETRY_ENABLED=1 and restart the backend.
python -m scripts.telemetry replay
python -m scripts.telemetry query
python -m scripts.telemetry query --run-id YOUR_RUN_ID
```

Initialization is an explicit administrative step and is never called by requests.
The query CLI reads actual SQL results or exits with a safe unavailable error.
Release tests use explicitly synthetic driver doubles for persistence-before-delivery,
ambiguous insert replay, stable IDs, batching, fixture exclusion, secret projection,
worker-thread execution and graceful outages. No live database credentials were
available during release validation; no live connection or ingestion is claimed.

Adapter unit tests pass, covering evidence admission, safe SQL boundaries and
provider-error handling. No live SQL requests or ingestion checks have been
executed. See frontend/VALIDATION.md for results and remaining access requirements.
