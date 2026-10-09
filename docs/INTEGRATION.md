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
