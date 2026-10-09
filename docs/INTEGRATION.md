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

OpenAI configuration is local and ignored. The requested final defender model is gpt-6-luna.
Actual acceptance is recorded below; optional provider calls remain unverified.

- LedgerLite v2 aaab5d6 reviewed and merged: only the transport-stable selector changes
  behavioral assertions. 256 default tests pass; Ruff and API drift pass. Local
  baseline/reference reruns meet expectations.
- Actual v2 frozen suite in isolated Docker: baseline 44 checks (37 pass, seven expected
  BOLA failures); separate secure reference 44/44 passes; independent reducer verified.
  This is reference validation, not a model-generated patch demonstration.
  Raw evidence: ignored runs/integration/reference-verification-v2.json.
  Evidence digest: 56369125f183ad9eaf37654d51f172a048f3b4ba8f56498ee9f895994f5bfbd3.
- User changed defender model to gpt-6-luna. Backend config updated locally; no secrets
  committed. Initial live run limited to three attempts, no HTTP retries.
- Reviewed Developer B completed commits fcb6617/942607b and posted frozen-v1 agreement
  in issue 2. Optional sponsor routes/report revisions deferred; B-owned files preserved.

## Model-backed acceptance

- Composition 485bd41 and diagnostic fix f14c1da reviewed and merged; all owned paths respected.
- Provider reasoning d2debf5 and replacement adapter b43e5c2 reviewed and merged.
  The model supplies bounded source replacements; trusted code derives exact diffs and the
  existing patcher/verifier admission is unchanged. Public API contracts did not change.
- Final default suite: 319 passed / 8 opt-in skipped; Ruff lint/format and API drift passed.
- Python CA bundle failure was diagnosed before provider execution; SSL_CERT_FILE uses the
  system trust bundle and authenticated model access preflight succeeded. TLS stays verified.
- Invalid model diffs failed admission with defender_invalid_patch and no applied patch.
  Their completed error manifests/evidence remain in local ignored storage.
- Actual GPT-6 Luna API run: run_c42befd59bb640d9bff0f71a7d306546. Run creation returned 202
  in 0.0024s. Discovery was an actual complete four-file Semgrep scan; baseline executed in Docker.
- Attempt one was rejected: security 6/6, functional 16/22, adversarial 15/16. It blocked
  administrator access; neither model output nor security-only success was accepted as verified.
- Attempt two: all 44 checks passed (security 6/6, functional 22/22, adversarial 16/16).
  A fresh baseline/patched deterministic challenge also passed, yielding a verified scoped verdict.
- Run/report/events/analytics were read through real API handlers, without mock transports.
  Initial verified report has 14 evidence references and preserves the rejected attempt.
- Model inference occurred only on authorized synthetic source. No AkashML/Senso calls, remote
  attacks, sponsor telemetry, narration or Guild review occurred. Actual provider billing was
  not queried; no measured dollar claim is made.

- API rechallenge returned 202/challenging, executed a fresh baseline and patched suite, then
  verified again. Five new references; final report 19 hash-validated references. Seven distinct
  actual container execution IDs across baseline, both patch attempts, challenge and rechallenge.
- Sanitized actual API acceptance receipt is committed in docs/evidence/live-api-acceptance.json;
  it includes both actual verdicts, events, summary counts, artifact hashes and execution identities.
- Production source inventory checked for the local credential: no tracked file contains it.
  Developer B frontend/telemetry/reports/Guild paths have no integration-branch modifications.
