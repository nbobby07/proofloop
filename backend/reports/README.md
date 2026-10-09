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

Only terminal source=execution reports are accepted. The v2 deterministic transcript
leads with the actual verdict, gives concise recorded counts, states the security
scope and offers the next action. It never reads run IDs, hashes, paths, raw summaries
or error codes aloud. Additional report limitations trigger a spoken reminder to
review the full written report; the underlying report is not changed. No reproduction
or patch details missing from ReportResponse v1 are invented. No arbitrary browser
text is sent to the provider. The script version changes the audio cache identity,
so old verbose clips are not reused for the new briefing.

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

## Concise briefing validation — October 9, 2026

Script v2 was generated through the real ElevenLabs API using the existing voice and
model. Browser playback and pause succeeded; the audio element measured 16.532608
seconds for a 34-word transcript. No run ID, hash, path or raw summary is spoken.
The same verified report produces a new cache identity, preserving the full original
report and all stale-report protections. Receipt and screenshot are under
`frontend/design/redesign/briefing-v2-*`. Raw audio remains in ignored storage.

Validation: 352 Python tests passed, 8 opt-in skipped; 26 frontend tests passed;
Ruff, schema drift, frontend lint and production build passed. New tests cover all
four terminal statuses, no spoken technical identifiers, a bounded script, partial
counts, written limitation guidance and cache separation from v1.

The local redesign preview on port 5192 now proxies to its isolated backend on
8002, using a byte-preserving copy of existing release run storage. The release
backend on 8001 and other worktrees are untouched. The audio validation did not
rerun security checks or relabel historical execution as new.
