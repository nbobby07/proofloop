# Incident briefings — live execution verified on October 9, 2026

`ElevenLabsClient` implements the existing `ElevenLabsNarrator` protocol using the
[official REST speech endpoint](https://elevenlabs.io/docs/api-reference/text-to-speech/convert).
It needs no new SDK dependency. `NarrationConfig.from_env()` reads existing
ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID; optional ELEVENLABS_MODEL_ID selects
an account-supported model (default eleven_multilingual_v2).

A supplies a trusted artifact directory under ignored generated_reports, loads
backend environment configuration, and wires generation/media routes. Construct
with approved_for_export=True only after redaction and deliberate export approval.
Calls are blocking: schedule through A's bounded worker/threadpool, not the async
event loop. Provider errors are optional-feature failures and cannot affect verdicts.

Only terminal source=execution reports are accepted. The deterministic transcript
quotes the saved summary and verification counts, includes all supplied limitations,
and never invents reproduction/patch details missing from ReportResponse v1.
Do not send arbitrary browser text to the provider. The upstream producer is
responsible for redacting the saved report summary and limitations.

MP3s are cached by report digest, voice, model and script version. Adjacent JSON
stores transcript, report/audio hashes and run identity; serving routes use opaque
artifact IDs with artifact_paths, never browser-supplied paths. Rechallenge changes
the report digest. Display historical audio only with its historical evidence.
Concurrent duplicate generation still requires A's per-artifact job lock; cache
writes are atomic but provider charges are not transactional.

Required proposed API: POST /api/runs/{id}/briefing schedules a bounded job;
GET reports queued/generating/ready/error with AudioArtifact, transcript and report
digest; an approved media route serves audio/mpeg. These routes now exist; POST accepts the expected report_sha256, and media serving
rejects stale reports with 409.
The frontend player already accepts a resolved same-origin/approved media URL.

Real report narration, browser playback/pause/replay/transcript and stale-audio rejection
are verified in docs/SPONSOR-ACTIVATION.md. The temporary key has a one-day expiry.

The server owns bounded jobs through backend/reports/briefings.py. Opt in with
PROOFLOOP_NARRATION_ENABLED=1 and backend-only credentials; no narration is performed
on startup or by tests. Existing terminal reports remain available if narration fails.
