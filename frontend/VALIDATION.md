# Developer B validation — 2026-10-09

Branch: feat/product-dashboard. Integrated origin/feat/security-engine through
bb5eddf and origin/feat/release-integration through f5d067a using normal merges.
No new A-owned implementation or frozen DTO edits.
The user's latest instruction authorized tests and integration checks.

## Automated results

| Check | Result |
|---|---|
| Linux backend: python -m pytest | 324 passed, 8 opt-in skipped |
| B adapters: pytest backend/telemetry/tests backend/reports/tests guild/tests | 18 passed |
| Frontend: npm test | 15 passed |
| Frontend: npm run lint | Passed |
| Frontend: npm run build | Passed; includes TypeScript compilation |
| Ruff check backend scripts demo_target verifier_tests sandbox guild | Passed |
| python -m scripts.export_contracts --check | Current |

357 passing tests across these suites. Provider/network behavior in B unit tests
uses explicitly named doubles; these are not receipts for actual sponsor calls.
The eight backend skips are opt-in acceptance suites, not asserted successes.

Linux backend used Python 3.12.3, Ubuntu 24.04 on WSL, a separate LF checkout
of the merged commit and requirements.lock. The first full Windows attempt had
282 passed, 14 failed, 26 errors and 8 skipped: A's sandbox expects POSIX
O_NOFOLLOW and exact LF hash-pinned source bytes. The supported Linux run passed
without weakening sandbox checks or changing A's files. B adapters also passed
under Windows Python 3.12.7. Frontend used Node 24.13.0.

## Browser integration

Chrome desktop and 390 × 844 phone layouts reviewed. The first mobile review
caught clipped navigation; four equal-width navigation items now remain visible.
Keyboard interaction and focus/Escape behavior are covered by frontend tests.

Real API at localhost:8005; frontend at localhost:5175. Created
run_1d4de1572ec54a3b9398ac03e8e7e9d1, received four ordered execution events,
loaded its terminal report and refreshed analytics (one error run). Execution
correctly returned engine_not_configured. No passing security verdict was claimed.
Fixture preview remains explicitly labeled and execution controls disabled.

Saved screenshots in design/ show the labeled fixture preview, not executed proof.

The merged lead release separately records a real model/Docker/Semgrep browser
run and successful rechallenge in docs/evidence/release-browser-acceptance.json.
That is the lead's execution receipt, not a fresh local run by Developer B.

## Pending live acceptance

- Configure A's sandbox/provider environment for a successful fresh end-to-end
  vulnerability/patch/challenge run. Local Docker daemon was unavailable.
- ClickHouse password remains user-deferred; real ingestion and SQL performance
  are unverified. The merged release supplies optional durable delivery; adaptive
  orchestrator recommendations still require compatible history and coordination.
- Guild hosted deployment and approved API routes are pending access/coordination.
- ElevenLabs key, approved briefing routes and real generated audio are pending.
- Shared CURRENT.md/docs milestone updates require team coordination; this owned
  record is the handoff source for those updates.

The dashboard's live analytics describe the current canonical API response, not
ClickHouse SQL. Sponsor features remain planned until actual execution receipts exist.
