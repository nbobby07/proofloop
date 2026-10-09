# ProofLoop current state

Updated October 9, 2026. Submission deadline: 4:30 PM America/Los_Angeles.

The full application is integrated on `feat/release-integration` in `proofloop-release`.
Pinned backend: `bb5eddf1c413a96557c5c2c25c30bbe9c4ea3f98`.
Pinned dashboard: `942607b6026fe7dc1de6f6c10c68ce8211036c05`.
All worker histories and worktrees are preserved; Developer B's branch is unchanged.

## Verified

React → FastAPI → real Semgrep/OpenAI → isolated Docker → persisted report works.
Browser run `run_2cd6645e223d4febb9e3c3b8d75293d4` reproduced BOLA, rejected the first
model patch, and accepted the second after all 44 checks and a fresh challenge.
Browser Challenge Again cleared the old result and completed another fresh 44/44
suite; final report has 19 hash-validated references. All seven API v1 routes remain
contract-compatible. Failures/retries are retained. Passing is scoped to executed tests.

Default tests: 324 passed / 8 opt-in skipped. Additional real Docker/Semgrep tests:
21 passed. Ruff, contracts, frontend lint/build pass. See
[release integration](docs/RELEASE-INTEGRATION.md) and its evidence receipts.

## Optional integrations

ClickHouse delivery now reads persisted canonical events on a background worker;
explicit initialization/replay/query commands are supplied. Delivery boundaries are
tested with doubles, but credentials are absent and live ingestion is unverified.
The core and local analytics work without it. ElevenLabs is now verified live through
optional evidence-bound briefing routes. Guild, AkashML and Senso remain unverified
live. None can override the verifier.

## Delivery

The owner authorized public GitHub visibility; unauthenticated access was verified.
The final PR must pass backend/frontend CI and obtain one approving review before
merge. Main has not yet been updated. PRs #1/#3 stay open until that merge.
Do not delete branches or worktrees. Submission/video/contact work is deferred at
the user's request; no submission is attempted in this integration task.

## Sponsor follow-up

See [SPONSOR-ACTIVATION.md](docs/SPONSOR-ACTIVATION.md): ElevenLabs now generated real
MP3s from completed reports and passed browser play/pause/replay/transcript checks.
Old audio returns 409 after rechallenge. Live mode and selected run survive refresh.
A fresh model-backed run again rejected its first patch and verified its second on
44/44 checks; fresh rechallenge also passed. Tests now total 328 passed / 8 skipped.
ClickHouse service ownership is unverified: the prior claim was imported from B's
handoff, not independently observed. No ClickHouse service was created in this chat.
Human review was requested from boaaaat on PR #4. Submission remains out of scope.


Latest pinned dashboard follow-up: `f9643d3c0b2bffb23784683a2272d13da61cd262`.
It includes the redesigned workspace plus adapter/frontend tests, merged without
modifying Developer B's branch. Final combined validation: 346 Python tests passed,
8 skipped; 16 frontend tests passed. CI now includes all those suites.
