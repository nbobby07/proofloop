# Sponsor activation and PR follow-up — October 9, 2026

Work started from the verified release `f5d067ae6dc91bd7096b7a34370faeb4a64dc8ff`
on dedicated branch `feat/sponsor-activation`. Developer B's branch and the original
release baseline were preserved. Submission work is explicitly out of scope per
Noel's latest instruction; no submission, contact collection or video upload occurred.

## ElevenLabs: live and browser-verified

The authenticated account showed Creator with available credits. Noel approved a
new key limited to Text to Speech, 3,000 credits and one-day expiry. It was created,
stored only in ignored backend `.env` (mode 0600), and never printed or committed.
No purchase, plan change or billing-setting change was made.

Three additive routes connect the existing narrator adapter to the dashboard:

- GET `/api/runs/{run_id}/briefing`: current evidence-bound status.
- POST the same route with `report_sha256`: bounded, idempotent generation.
- GET `/api/audio/{artifact_id}`: allowlisted MP3 with content-hash and current-report checks.

The existing seven v1 response models are unchanged. Pydantic remains canonical;
OpenAPI and TypeScript are regenerated together. Only a completed source=execution
report can be narrated. Browser-supplied text, paths and fixture reports are rejected.
Narration runs outside the async request loop, cannot modify the verifier, and is
optional. Cached MP3 metadata binds the transcript and audio hash to the report hash.
Rechallenge removes current report/audio controls and makes old audio return 409.
A stale generation request also returns 409 before consuming provider credits.

Set backend-only `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`, optionally
`ELEVENLABS_MODEL_ID`, and `PROOFLOOP_NARRATION_ENABLED=1` in ignored root `.env`;
restart the backend launcher. The demonstrated voice was `JBFqnCBsd6RMkjVDRZzb`
and model `eleven_multilingual_v2`. The temporary key expires October 10 around
12:58 PM Pacific; continued use requires an operator-managed credential.

Live run `run_49e1340683774282ba8de7d51e940142` reproduced HTTP 200 unauthorized access,
rejected patch 1 (0/6 security, 16/22 functional, 15/16 adversarial), then accepted
patch 2 on all 44 checks and a fresh deterministic challenge. Browser Challenge Again
cleared counts and returned another fresh 44/44 result. All 19 report references
passed SHA-256 validation.

Two real narration requests produced playable MP3s: the initial report (41.285079s)
and the new report after rechallenge (41.1922s), durations read from the browser's
loaded audio element. Play, pause, replay, transcript display, and durable audio after
refresh were exercised. Old audio returned HTTP 409 after the new report replaced it.
The browser restored Live mode and fetched the selected persisted run after reload;
no execution results are cached in browser storage.

Receipt: `evidence/sponsors/live-narration-acceptance.json`. Screenshots are alongside
it. Raw MP3s remain private in ignored `runs/briefings/`. No measured dollar claim.

## ClickHouse: ownership claim unverified

The host `kvjim2jp8d.us-east-2.aws.clickhouse.cloud` and service-creation claim came
from Developer B's handoff/telemetry README committed by GitHub user `boaaaat` in
`942607b`. Git authorship does not prove cloud ownership or creation.

At Noel's explicit request, the foundation, coordinator and provider chats were asked.
All three said they neither created nor independently verified that service. The
coordinator had merely repeated the handoff. The dashboard author's chat was not
available in this account's chat list. No account/organization owner was established.

The current Chrome login showed “NB's Organization” and a service-creation screen,
not the claimed running database. No new service, password reset, schema, SQL query
or ingestion was performed. The reported host must not be treated as configured or
owned without confirmation from its owner. The existing optional persist-first
adapter remains implemented and tested with doubles. ClickHouse-driven adaptive
selection and live SQL dashboard results remain blocked by actual authorized access.

## Other sponsors and review

Guild opens at sign-in/free-trial with Terms acceptance; no hosted agent was deployed.
AkashML and Senso credentials are absent from the authorized backend environment;
no new credentials, paid requests or authoritative remote policies were invented.
Their adapters and deterministic core fallback remain unchanged.

A human review was requested from `boaaaat` on PR #4. Its original backend/frontend
CI passed, but no approving review was present at the follow-up checks. Main protection
remains intact. PRs #1/#3 stay open until the full release actually merges.

## Validation and limitations

328 default Python tests passed, eight opt-in tests skipped; Ruff lint/format and
contract drift checks passed; frontend contracts/lint/production build passed.
The new suite tests duplicate-job prevention, durable reads, stale report rejection,
corrupted audio, optional configuration and arbitrary-text rejection. It uses explicit
fake audio for unit tests; the live MP3/browser receipts are separate evidence.

The in-app browser intermittently failed a cross-origin POST after its preflight,
before a POST reached FastAPI. No backend result was fabricated or inferred. The
same final production UI completed the flow in Chrome with no console errors.
The local API remains loopback-only and single-worker. No publicly exposed API or
hosted deployment is claimed. Passing remains scoped to the frozen LedgerLite suite.
