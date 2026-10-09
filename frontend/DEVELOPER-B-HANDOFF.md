# Developer B implementation handoff

Branch: `feat/product-dashboard`. Developer A's `origin/feat/security-engine`
through `bb5eddf` was merged cleanly at the user's request. New implementation
edits are confined to B-owned paths. Shared Pydantic, OpenAPI and generated
TypeScript contracts are unchanged.
Coordinate the following changes with A; this file is a proposal, not a frozen API.

## Implemented frontend

- Responsive security arena, red/blue team panels, evidence-aware pipeline states.
- Explicit fixture/live selector. Fixture input is the checked example-run.json.
- Central client for every frozen route; response validation, timeouts and safe errors.
- Run creation, opening a run ID, cursor polling, event deduplication and severity filter.
- Accepted rechallenge clears current verification/report while waiting for new evidence.
- Verification counts, interactive unified diff and saved report JSON download.
- Canonical API-response analytics page and session-local execution-only history.
- Integration readiness page; reusable hosted-review display and audio player.
- Reduced-motion support, focus states, responsive grids and bounded scroll containers.

No automatic fixture fallback. No invented individual results, patched HTTP status,
Semgrep details, elapsed execution times, agent identities or integration success.
Pipeline completion markers require stage_completed events; final status is backend-owned.

## Frozen route integration

The merged API implements /api/runs, /events, /report, /challenge and /analytics.
Frontend consumes their canonical DTOs. Analytics currently reads A's local run
storage; ClickHouse backing is still pending and is not claimed by the UI.
Create request: LedgerLite, max_attempts=3. Challenge: max_challenges=2, policy_ids=[].
404/409/422/501/network errors remain visible. No mutating request is auto-retried.

Event cursor is opaque and points AFTER delivered data. Keep the last non-null
cursor when a response has no next_cursor. Drain changing cursors until an empty
page, with at most five pages per polling tick; backlog continues next tick.
The stream owns delivery order, not timestamps or snapshot events. Poll every
1.8 seconds during execution; cancel on selection/source change. Report 409 retries;
other report failures preserve run state and expose an explicit report error.

Rechallenge must atomically invalidate the old verdict before returning 202.
The client additionally suppresses a stale terminal snapshot until new completion
evidence or nonterminal progress appears. API v1 lacks immutable result revisions:
please add one through the coordinated canonical generation workflow before
claiming report/audio/audit identity across externally initiated rechallenges.

## ClickHouse hooks

Imports (existing cross-owner DTO consumption only):

```python
from backend.telemetry.client import ClickHouseClient, ClickHouseConfig
from backend.providers.contracts import AnalyticsFilters
```

`ClickHouseClient` implements the protocol already in telemetry/clickhouse.py.
Explicit connect/configuration and initialize_schema at startup/migration time;
never connect on import. Install the optional telemetry/requirements.txt dependency
and coordinate root lock/config updates. Use a dedicated runtime account and TLS.

Proposed hookup: A persists events first, calls insert_security_events in a
worker/threadpool, and replays persisted batches after TelemetryUnavailable.
Coordinate routing the existing analytics endpoint to
query_security_analytics(AnalyticsFilters(run_id=...)); failure-pattern queries
are context-restricted, historical and intended for A's orchestrator.

Required proposed metadata is documented in backend/telemetry/README.md. The most
important fields are unique monotonic sequence, target, test_execution_id, suite,
challenge_family, outcome, executed, attempt, duration_ms, suite_hash and policy_hash.
Record missing/skipped/timeouts as terminal check outcomes. Without these fields,
specific metrics remain incomplete; absent checks cannot be inferred from events.

Pattern denominator is all recorded outcomes, including incomplete/unknown results.
Numerator is explicit executed fail outcomes. This interpretation of the existing
FailurePattern.executions field needs A's agreement. Do not relabel it successful
or fully executed checks. Unsupported/conflicting metadata is not upgraded to proof.

Extended SQL metrics are INTERNAL until an approved AnalyticsResponse extension:
actual security-check starts, incomplete checks, patch attempts, baseline outcomes,
verification duration, minute outcome buckets and coverage/query timing. Recurrence
trends need stable per-test and source-revision identities and remain PLANNED.

Current counts never override verifier results. Store the returned recommendation,
sample counts, compatibility context and selection rationale in A's evidence before
the attacker chooses an allowlisted challenge. No attacker DTO changes were made.

## Proposed optional endpoints — A owns implementation

For both optional features, A loads a saved completed execution report, verifies its
identity/revision, redacts it, schedules bounded blocking work, and persists results.
The browser must never submit arbitrary text for provider execution.

| Proposed route | Request | Response and behavior |
|---|---|---|
| POST /api/runs/{id}/briefing | Empty object | 202, opaque job ID, queued status; idempotent per report/voice/model/script digest |
| GET /api/runs/{id}/briefing | No body | queued/generating/ready/error; ready has AudioArtifact, transcript, report SHA-256 and approved audio URL |
| GET /api/audio/{artifact_id} | No body | Allowlisted audio/mpeg only; no host paths |
| POST /api/runs/{id}/audit | Empty object | 202, opaque job ID, queued status; one job per approved evidence packet |
| GET /api/runs/{id}/audit | No body | queued/running/completed/error; validated review, report/packet hashes, agent version, session ID and real Guild review URL |

404 unknown run/artifact; 409 unfinished/stale report; 422 invalid input; 503 provider
not configured/unavailable; safe error bodies without provider response text/keys.
503 and feature-specific job DTOs require canonical ErrorResponse/model coordination.
Concurrent duplicate jobs need A's per-evidence lock. Handle uncertain POST outcomes
by reconciliation rather than blind retry. A owns artifact serving/access control.

Imports:

```python
from backend.reports.narrator import ElevenLabsClient, NarrationConfig
from guild.client import GuildClient, GuildConfig
```

Each adapter requires approved_for_export=True only after deliberate redaction/export
approval. ElevenLabs uses the official speech endpoint with deterministic script
and atomic evidence-bound MP3 cache. Guild starts a genuine hosted chat session and
polls runtime completion; local validation rejects unknown citations and wrong hashes.
Neither changes deterministic verdicts. No paid calls or hosted execution have run.

Once routes are approved, add canonical DTOs and central frontend client methods,
then pass ready results to IncidentBriefingPlayer and GuildAuditPanel. Until then
the dashboard intentionally displays these connections as PLANNED/unverified.

## Configuration and access

Existing variables: CLICKHOUSE_HOST/PORT/USER/PASSWORD/SECURE,
ELEVENLABS_API_KEY/VOICE_ID, GUILD_API_KEY and VITE_API_BASE_URL.
Proposed optional server variables: CLICKHOUSE_DATABASE, ELEVENLABS_MODEL_ID,
GUILD_WORKSPACE_ID and GUILD_AGENT_ID. Coordinate .env.example/root configuration
with A. The adapters read process environment; A owns dotenv loading.

ClickHouse signed-in trial service was started through Chrome. Its password cannot
be retrieved; user chose to finish the reset later. No database changes/SQL requests
ran. The current ElevenLabs browser account shows Free with API access, not Creator;
no API key exists. A form is prepared for a TTS-only, 2000-credit, one-day key, but
no credential was created. Guild opens at sign-in/sign-up; no terms were accepted.

No secret values were read, printed or committed. Never put secrets into VITE_*.

## Delivery status

The user's later instruction explicitly authorized tests and branch integration.
Frontend production build (including TypeScript), ESLint, Ruff and exported schema
checks passed. Automated checks: 319 backend tests passed in Linux (8 opt-in
skipped), 18 B adapter tests passed, and 14 frontend tests passed. See VALIDATION.md
for commands and the Windows environment limitation.

Desktop and 390px phone layouts were reviewed in Chrome. A real local API run
was scheduled, polled to its engine_not_configured error, and its report/analytics
loaded. This confirms error-path integration, not successful vulnerability execution.
Live ClickHouse ingestion, narration and hosted Guild execution remain unverified.

Shared CURRENT.md/docs updates are pending coordination. Recommended milestones:
frontend implemented; telemetry/reporting adapters unit-checked, live UNVERIFIED;
route integration, hosted deployment, real sponsor receipts and recurrence PLANNED.
