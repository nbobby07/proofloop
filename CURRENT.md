# ProofLoop current state

Updated October 9, 2026. Submission deadline: 4:30 PM America/Los_Angeles.

## Integrated baseline

All earlier PRs (#1, #3, #4, #5, #6, #7) are merged. Main at `ada492b` contains the
real LedgerLite engine, guided Find → Fix → Prove workspace, Presentation Mode,
and concise evidence-bound ElevenLabs narration. Worktrees and fallback releases
are preserved. No submission is claimed here.

## Current ClickHouse follow-up

Branch `feat/clickhouse-live`, based on main, enables the owned telemetry adapter
and an additive read-only SQL analytics route. API/schema/contract/UI wiring is part
of the user's request to use ClickHouse; no security engine or verdict logic changes.
The change requires review and passing CI before merge.

ClickHouse Cloud in NB's Organization is now verified live. Initial ingestion: 252
canonical events, six real runs, four verified and two rejected. A fresh browser
challenge passed 44/44 and advanced cloud counts to 258 events and 24 verification
rounds, with ten explicit failures and zero pending events. The website displays
real SQL metrics and clearly labels local fallback on cloud unavailability.

The new ProofLoop service is fixed at one 8 GiB replica, auto-idles after 15 minutes,
and allows the workstation IP only. Backend credentials are ignored and mode 0600;
the runtime user has SELECT/INSERT only on the events table. The account displayed
300 trial credits; no additional prepaid credits, payment method or upgrade was added.
The former unverified ClickHouse host was not used.

## Runtime and evidence

The local preview at http://127.0.0.1:5192 proxies to backend port 8002 in the product
worktree. The release backend on 8001 remains a fallback. Existing real manifests
were copied intact for the preview, and new real runs/challenges append there.
See `backend/telemetry/README.md` and `frontend/design/clickhouse/` for receipts.
Earlier release evidence remains in `docs/RELEASE-INTEGRATION.md` and sponsor notes.

Semgrep, OpenAI and ElevenLabs have real execution evidence. ClickHouse now does too.
AkashML, Senso and Guild remain unverified live. Challenge runs the frozen deterministic
suite; it does not generate novel attacks. LedgerLite is a synthetic authorized target.
Analytics cannot establish a verdict or universal security.

## Validation

355 Python tests passed, 8 opt-in skipped; 29 frontend tests passed. Ruff, frontend
lint, production build and canonical contract drift checks passed. Desktop 1280px
and phone 390px analytics had no page overflow. Actual cloud and API query receipts
are saved separately from tests that use doubles.

## Submission limits

Public repository is available. Full eligibility, shareable demo-video link, team
information and submission status are not established by this change. The organizer's
open-web action requirement is not demonstrated by a local Docker workflow alone.
ClickHouse usage is real but the dataset is small; no high-volume performance or
adaptive challenge-selection claim is made.
