# ClickHouse telemetry — live verified October 9, 2026

ProofLoop now delivers real persisted execution events to ClickHouse Cloud and reads
SQL-backed analytics in the website. NB's Organization owns the newly created
ProofLoop service. This replaces the earlier unverified host from the old handoff;
that old service was not used or changed.

## What runs

- `TelemetryDelivery` reads the durable local run manifests, batches at most 1000
  events, and advances a cursor only after an acknowledged insert. Restart replays
  retained manifests; `ReplacingMergeTree` with `FINAL` deduplicates run/event IDs.
- Only `source=execution` events are admitted. Free-form messages, arbitrary metadata,
  credentials and source code are not exported. Only the documented scalar dimensions
  in `ClickHouseClient.columns` are sent. Fixture batches are rejected atomically.
- A single lock serializes the synchronous driver across background delivery and API
  reads. SQL runs in workers, outside the security execution event loop.
- `GET /api/telemetry/analytics` returns actual SQL counts, event coverage, pending local
  events, incomplete rounds, mean proposals and mean verification-stage duration.
  The measured query time includes network/driver work for the complete snapshot.
- The Analytics page prefers cloud results and labels them **Live from ClickHouse**.
  If unavailable, it clears the cloud snapshot and explicitly labels local fallback.
  `/api/analytics` remains the unchanged local endpoint. Integrations tests SQL access
  independently of the backend health badge.

These are descriptive metrics. They do not select attacks, modify verifier inputs or
assign verdicts. `required_suites` outcomes describe aggregate verification rounds,
not individual assertions. Only explicit `fail` values count as failures; other
consistent recorded outcomes remain in denominators. Conflicting identities are
excluded rather than guessed. No high-volume benchmark or adaptive attack selection
is claimed for this six-run dataset.

## Setup and local runtime

Install the optional pinned adapter: `python -m pip install -r backend/telemetry/requirements.txt`.
Set backend-only `CLICKHOUSE_HOST`, `CLICKHOUSE_PORT=8443`, `CLICKHOUSE_USER`,
`CLICKHOUSE_PASSWORD`, `CLICKHOUSE_SECURE=true`, and `CLICKHOUSE_DATABASE=default`.
The ignored `.env` uses a restricted runtime user with SELECT/INSERT on
`default.proofloop_events`; credentials are never VITE variables or committed files.

Schema creation is an explicit administration step (`python -m scripts.telemetry initialize`)
using a migration-capable user. The runtime user deliberately cannot initialize schema.
An ignored mode-0600 `.env.clickhouse-admin` retains the original migration credential.
Enable `PROOFLOOP_TELEMETRY_ENABLED=1` and restart the backend launcher. Replay and
query commands remain available: `python -m scripts.telemetry replay` and
`python -m scripts.telemetry query`. A background worker normally handles delivery.

The tested local preview uses frontend port 5192, proxying to backend port 8002.
Its persisted storage is this worktree's `runs/`; the release backend on 8001 is
unchanged. The cloud service uses one fixed 8 GiB replica with 15-minute idling.
Access is restricted to the workstation's current IP; moving networks may require
an authorized IP-list update. No payment method or paid-plan upgrade was added.
The account showed 300 active trial credits and no prepaid credits at inspection.

## Actual acceptance

Initial replay acknowledged 252 real events from six existing model/Docker/Semgrep
executions: four verified and two rejected. SQL reported 10 failed rounds out of 23.
Repeated replay and backend restart left deduplicated counts unchanged. A fresh
browser Challenge on `run_b79f04fcd8114bf7b215a49e4286175e` completed 44/44 checks;
automatic delivery increased SQL totals to 258 events and 24 rounds, with zero
pending events. No sample rows or invented security executions were inserted.

Receipts and screenshots: `frontend/design/clickhouse/`. Actual API snapshot latency
was measured and recorded there; it is a small-data network-inclusive measurement,
not a throughput or scale claim. Unit tests use explicit doubles and make no cloud calls.

## Boundaries and remaining limits

Historical comparisons require matching target, suite and policy context. The
`query_failure_patterns` helper remains unused because the core producer does not
supply all those context dimensions. Missing granular dimensions stay unavailable.
The UI provides inspection guidance from aggregate failures, not model-generated
recommendations. The local manifests remain the durable evidence source. Database
outages affect cloud analytics but never turn incomplete verification into success.
