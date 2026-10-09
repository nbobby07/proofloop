# ProofLoop API v1 contract

Contract frozen for initial parallel development. Pydantic in `backend/api/schemas.py` is canonical. `openapi.json`, `events.schema.json`, `run.schema.json`, and `frontend/src/types/api.generated.ts` are generated; do not edit them independently. Named TypeScript aliases in `frontend/src/types/index.ts` expose matching response types.

Base URL: `http://localhost:8000`, configurable via `VITE_API_BASE_URL`. JSON requests use `Content-Type: application/json`. No authentication exists in the local scaffold: keep it bound to loopback. Remote exposure requires authentication and authorized target access first.

## Endpoints

| Method and path | Request/query | Success model/status | Scaffold behavior |
| --- | --- | --- | --- |
| `GET /api/health` | none | `HealthResponse`, 200 | Live |
| `POST /api/runs` | `CreateRunRequest` | `RunResponse`, 202 | PLANNED, 501 |
| `GET /api/runs/{run_id}` | run id | `RunResponse`, 200 | PLANNED, 501 |
| `GET /api/runs/{run_id}/events` | `cursor?: string`, `limit: 1..200 = 100` | `EventsResponse`, 200 | PLANNED, 501 |
| `GET /api/runs/{run_id}/report` | run id | `ReportResponse`, 200 | PLANNED, 501 |
| `POST /api/runs/{run_id}/challenge` | `ChallengeRequest` | `ChallengeResponse`, 202 | PLANNED, 501 |
| `GET /api/analytics` | `run_id?: string` | `AnalyticsResponse`, 200 | PLANNED, 501 |

Health is exactly `{"status":"ok","service":"proofloop"}`.

Create: `{"target":"LedgerLite","max_attempts":3}`. `target` is an approved server-side id, not an arbitrary URL/path. Attempts are 1..10. Clients cannot set a source or verdict. The execution engine will assign `source: execution`.

Challenge: `{"max_challenges":2,"policy_ids":[]}`. Limit 1..10, at most 20 policy ids. Requests schedule bounded authorized work. Planned implementation returns 409 when run state does not permit a challenge. Rechallenging invalidates the prior verdict until all required new tests complete. A contract stub never creates a run or challenge.

Unknown run ids will return 404 once persistence exists. Invalid bodies/query values return 422. All models forbid unknown fields. IDs match `[A-Za-z0-9_-]+`, maximum 128 characters. Optional result fields are nullable until their stages finish.

## Responses and errors

`RunResponse`: `run_id`, `status`, `target`, `source`, nullable `finding`, `baseline`, `patch`, `verification`, and `events` (default empty). See `example-run.json` for a **fixture-only** full example; it has no real evidence. Passed counts must never exceed totals. Run events must match the enclosing run id and source.

`EventsResponse`: run id, source, ordered events, nullable `next_cursor`. PLANNED pagination is append-only sequence order, with opaque cursor pointing after the last delivered event; event ids are unique within each run and must be deduplicated by consumers. No SSE transport is implemented. Timestamps are timezone-aware RFC3339, emitted in UTC.

`ReportResponse`: run id, source, status, summary, optional verification counts, evidence references (`artifact_id`, lowercase SHA-256, description), limitations. Evidence references are opaque ids, never arbitrary host paths. Reports for unfinished runs return 409. Download transport requires a coordinated contract addition.

`AnalyticsResponse`: source, run_count, verified_count, rejected_count, failure_patterns. Each pattern has challenge_family, failures, executions. Real analytics exclude fixtures and preserve failures/timeouts/incomplete results in their denominators. Analytics cannot override verdicts.

`ChallengeResponse`: run_id, status `challenging`, source `execution`.

Errors share `ErrorResponse`: `{"error":{"code":"not_implemented","message":"PLANNED: security execution is not enabled."}}`. Codes: `not_implemented`, `not_found`, `invalid_request`, `conflict`, `internal_error`. Return no credentials, raw request body, sensitive headers, or traceback. Scaffold planned routes return 501 for valid requests and 422 for invalid requests.

## Lifecycle

`pending → discovering → reproducing → generating_patch → applying_patch → verifying → challenging → verified`

Failure of a patch/challenge may go to `retrying → generating_patch` within the attempt budget. Terminal states: `verified`, `rejected`, `inconclusive`, `error`. `rejected` means executed required tests failed after allowed attempts; `inconclusive` means evidence is incomplete or a required suite cannot run; `error` means infrastructure/provider failure. Timeouts/skips/missing tests cannot be counted as passing. No lifecycle engine is implemented yet.

Only the independent verifier can assign an execution verdict. `verified` requires reproduced baseline, patch-specific immutable evidence, all required security/functional/adversarial suites fully executed, and all required checks passing. Counters alone are insufficient. An LLM opinion, Semgrep absence of findings, or hosted review is not a verdict. A result covers the frozen executed suite only.

## Events

One event schema feeds timeline, telemetry, reports, and Guild review:

- `event_id`, `run_id`: stable ids.
- `timestamp`: timezone-aware RFC3339.
- `stage`: one of the 12 lifecycle states.
- `event_type`: `stage_started`, `stage_completed`, `finding_discovered`, `baseline_reproduced`, `patch_proposed`, `patch_applied`, `test_completed`, `challenge_proposed`, `retry_scheduled`, `run_completed`, `run_failed`.
- `severity`: `info`, `warning`, `error`, `critical` (event severity); finding severity separately supports `info`, `low`, `medium`, `high`, `critical`.
- `message`: redacted text, 1..2000 characters.
- `source`: `fixture` or `execution`.
- `metadata`: JSON object; redact secret/PII values before serialization and telemetry.

Fixture data must retain fixture labels at every consumer boundary. It must not feed production analytics or narrated security claims. This scaffold serves no fixture API routes; the dashboard imports the checked JSON locally.

## Coordinated changes

Agree on changes, edit Pydantic, run `python -m scripts.export_contracts`, then `npm run contracts` in frontend. Run backend tests, frontend lint/build, and drift checks. Commit canonical and generated files together. Additive changes still require coordination; breaking changes require an explicit contract revision before either developer depends on them.

## Optional incident briefing extension

The seven existing v1 response models are unchanged. New endpoints use canonical
BriefingRequest/BriefingResponse and never accept arbitrary narration text:

- GET /api/runs/{run_id}/briefing returns unavailable, not_generated, generating,
  ready or error, with the exact current report_sha256.
- POST the same path with {"report_sha256":"<expected SHA-256>"} returns 202;
  stale/incomplete reports or capacity conflicts return 409. An unconfigured optional
  provider returns status unavailable without affecting execution.
- GET /api/audio/{artifact_id} serves allowlisted audio/mpeg only while its report
  identity is current. Old audio returns 409 after rechallenge. Missing files return 404.

The frontend independently hashes the displayed report, validates the returned
identity, and clears its player when the report is invalidated. Current audio cannot
be mistaken for a new verdict. Fixture and unfinished reports are never exported.
