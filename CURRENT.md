# ProofLoop current state

Updated October 9, 2026. Main baseline: PRs #1, #3, #4, #5, #6, #7 and #8 merged.
The existing Classic application, saved evidence, ClickHouse service and briefing remain available.

## Akash and Workspace implementation in progress

The new LedgerLite Workspace target is separately versioned. Its correctness-focused
OpenAI generation prompt, original source and receipt are preserved before audit.
It contains two organizations, sessions, role permissions, invoice line items,
search, batch exports and membership revocation, plus a usable browser interface.
A separate trusted HTTP oracle and restricted runner leave Classic's frozen files unchanged.

Local execution of the expanded trusted suite passed 62/62 checks. Two earlier live
AkashML challenge proposals also executed successfully against the earlier 60-check
suite. These are real calls and executions; they do not establish a vulnerability.

Both Akash accounts are configured using distinct backend-only credentials. The
first successful Akash compute preflight ran three checks against each of two
containers and confirmed deployment closure (1791588263955). Two earlier cloud
attempts failed; their leases are also closed. Full browser-to-cloud acceptance is
still in progress. No complete cloud integration or prize-ready bug is claimed yet.

The feature is being prepared in reviewed stages on feat/akash-workspace. Changes
span engine/providers, API/contracts, UI, and telemetry as authorized by this task.
The initial validation budget remains $20 total. Reservations are conservative
estimates, not measured charges. No account auto-recharge or card charging was enabled.

## Runtime

ProofLoop preview: http://127.0.0.1:5192, backend 8002. LedgerLite Workspace demo:
http://127.0.0.1:8010, with a separate persistent SQLite Docker volume. Verification
uses fresh disposable storage, not that demo database. Release backend 8001 remains
untouched. Source, evidence, and existing worktrees are preserved.

## Validation so far

382 Python tests passed with eight opt-in skips; 32 frontend tests passed. Production
frontend build passed. Final checks and live acceptance are pending completion.
The original security fixture remains clearly synthetic and intentionally vulnerable.
No new vulnerability has been confirmed in the correctness-focused Workspace target.
