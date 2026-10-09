# Security engine integration checklist

Integration checkout: `proofloop-integration`, branch `feat/security-engine`.
Do not edit worker branches or merge unfinished changes. Preserve the frozen API.

## Reviewed worker commits

| Order | Worker | Completed commit | Ownership review |
| --- | --- | --- | --- |
| 1 | LedgerLite | 550a29b | demo_target and verifier_tests only |
| 2 | Verifier | 82cc654 | sandbox and engine patcher/verifier only |
| 3 | Orchestrator | 53cb868 | API, storage, orchestrator, backend tests only |
| 4 | Providers | d0a8b2f | providers and engine scanner/defender/attacker only |

## Gates after each merge

- Inspect diff, ownership, Git status, and evidence semantics before commit.
- Run backend tests plus integrated sandbox/provider suites.
- Run Ruff lint and format checks on every integrated Python path.
- Check generated API contracts for drift.
- Keep test doubles confined to tests; default execution must fail explicitly if unconfigured.
- Require complete immutable actual test outcomes for execution verdicts.
- Record failures and runtime checks that remain unexecuted.

## Remaining acceptance

- Wire provider, snapshot, runner, verifier and orchestration interfaces.
- Execute the full authorized loop using isolated Docker; verify rejection, retries and rechallenge.
- Preserve health, progress polling, reports, fixture labels and redacted errors.
- Send Developer B the frozen endpoint semantics and any proposed contract changes before editing them.
- Push the integration branch and create the final PR only when ready.
- Leave main protected; final merge requires green CI and required review.

Docker isolation and credentialed model calls were not validated by workers.

## Integration validation log

- Initial merges: LedgerLite 20 backend tests plus baseline/reference evidence passed;
  verifier 120 passed / 3 skipped; orchestrator 131 passed / 3 skipped;
  providers 255 passed / 7 skipped. Ruff lint/format and API drift passed at every gate.
- Test discovery now includes provider and sandbox suites; CI lints all integrated Python.
- Provider BOLA rule follow-up 4bcd1f6: 256 passed / 8 skipped; opt-in real Semgrep
  suite 18 passed, including vulnerable LedgerLite detection and secure-reference clean scan.
- Docker started locally and pinned image built from python:3.11-slim digest
  e88e9763f943ec1834f992a4b51e0f24500486803e8bc534e5767af9ea65f6ce.
  Runner image ID: sha256:1ec21f71172fe05dc9b15e50ec8773d782b06022fcad06f7bb115731aa52c756.
- All three real Docker integration tests passed (19.23s), covering acceptance/rejection,
  network/readonly/secret restrictions, hanging target and cleanup.
- Actual v1 LedgerLite HTTP suite returned inconclusive: 34 passed / 10 failed because
  HTTP strips trailing header whitespace. No passing verdict was accepted. A1 owns a
  reviewed v2 test-selector correction preserving 44 tests and seven expected BOLA failures.
- Frontend contracts, unchanged generated types, lint and build passed.
- Developer B coordination record: https://github.com/nbobby07/proofloop/issues/2.
- Main protection verified: backend and frontend CI plus one approving review required.

OpenAI configuration is local and ignored; model gpt-5.4-mini selected for the bounded demo.
No credentialed calls or end-to-end model success have been recorded yet.
