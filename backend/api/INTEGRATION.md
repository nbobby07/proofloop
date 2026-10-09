# Orchestrator integration handoff

The canonical Pydantic wire models and generated contracts are unchanged. All six execution
routes are implemented, alongside the existing health route. HTTP 202 schedules bounded work;
poll the run or append-only events endpoint. Reports return 409 until a terminal state.

## Composition and engine interface

`create_app(orchestrator=Orchestrator(RunStore(Path("runs")), engine))` installs a trusted
`ExecutionEngine` implementation from `backend.engine.orchestrator`. The default app deliberately
has no configured engine: requests create a real run that terminates with `engine_not_configured`,
never fixture findings or fake test evidence. Configure the composition only after the real
worker implementations are integrated. No API key or Docker call occurs merely by importing the app.

The async engine methods are:

- `discover(run_id, target) -> Finding | None`: pin the approved source/suite/policy context;
  run a complete real scan. Return no finding only for a completed scan without a selected finding;
  an incomplete scan must raise an explicit failure, never silently appear clean.
- `reproduce(run_id, finding) -> BaselineReceipt`: independently reproduce against the immutable
  baseline. Return the canonical `BaselineResult` as `result` plus opaque `evidence` references,
  including evidence of unsuccessful reproduction. Keep artifacts in the engine's evidence store.
- `generate_patch(run_id, finding, attempt, feedback) -> PatchProposal`: call the defender with
  the pinned source and deterministic feedback. The proposal's attempt must match the request.
- `apply_patch(run_id, patch) -> None`: trusted diff admission, frozen original, disposable workspace.
  Returning successfully means the patch was applied; proposals alone do not qualify.
- `verify(run_id) -> StageResult`: run complete required security and functional checks.
- `challenge(run_id, ChallengeRequest) -> StageResult`: admit at most `max_challenges` proposals
  against trusted templates/policy IDs, execute independently, and return the independent final
  verdict across all required security/functional/adversarial evidence. Unknown policy IDs and
  unsupported challenges must fail closed. Rechallenge reruns required checks on the exact patch;
  historical passing evidence cannot stand in for new execution.

`StageResult` is an internal receipt, not a replacement for the provider or API contracts. It holds
an independently determined verdict, canonical `VerificationSummary`, evidence references,
`complete`, and `patch_sha256` (SHA-256 of the proposal's UTF-8 diff bytes). `complete` MUST come
from the independent verifier checking frozen required test identities, outcomes, baseline,
source/patch/policy/suite/runner bindings, and artifact integrity. Never derive it from model output
or counters. The orchestrator additionally rejects stale patch hashes, empty evidence, incomplete
receipts, zero required suite totals, and partial pass counts. It never upgrades another verdict.

Engine methods must be cancellation-cooperative and must not perform blocking IO on the event loop.
Wrap bounded synchronous provider/runner operations off-loop; their own timeouts and process
cleanup remain required because cancellation cannot stop a Python thread. Default outer stage
budget is 120 seconds and maximum concurrent runs is four. Configure budgets to encompass the
runner's own cleanup deadline. No engine context or raw exception is serialized publicly.

## Existing worker contracts to reuse

A1: curated LedgerLite source, patch allowlist, frozen required test manifest, baseline expectations,
and trusted HTTP test assertions. Never run the developer checkout or let the patch alter tests.

A2: immutable snapshot, isolated patch application, independent runner and deterministic verifier.
A2 now exposes `SourceSnapshot.capture(root, allowed_files)`,
`apply_unified_diff(original, diff, allowed_files=...) -> PreparedPatch`,
`DockerRunner.run(snapshot, trusted_suite, manifest, limits, phase=..., deadline=...)`,
`baseline_reproduced(evidence, manifest)`, and
`evaluate_patch(prepared_patch, manifest, baseline, patched) -> VerificationResult`.
`Verifier.verify_patch(original, replacements_or_diff, trusted_suite, manifest, limits)`
is the combined baseline/patch convenience entry point. The integration adapter must use these
trusted entry points instead of duplicating patch parsing or verdict reduction. Map its verdict into
`StageResult` and retain/reconstruct the pinned execution context for rechallenge.

A3: reuse existing `SemgrepScanner.scan_repository(Path) -> ScanResult`,
`OpenAIDefender.generate_patch(SourceSnapshot, Finding, list[str]) -> PatchProposal`,
`AkashAttacker.generate_challenges(target, SecurityPolicy, list[ChallengeResult])`, and
`SensoPolicyStore.retrieve_security_policy` / `retrieve_policy_sources` DTOs. These synchronous
providers never supply execution verdicts. Instantiate attempt-scoped defenders as required by
the concrete implementation. A complete scan, authoritative policies, and trusted challenge
admission are composition responsibilities; the engine must not invent missing results.

## Persistence and operation

`PROOFLOOP_RUNS_DIR` defaults to ignored `runs/`. Run manifests are atomic JSON replacements with
private permissions and fsync before replace. They retain ordered canonical events, every proposed
patch, application status, every verification/challenge round, evidence references, and safe failure
codes. Only one API process may own a store; multi-process/multi-host scheduling is unsupported.
An app restart marks unfinished manifests `error/execution_interrupted` rather than resuming stale
engine context. Completed runs remain readable. Rechallenge after restart needs the adapter to
reconstruct and validate its immutable context; otherwise it must fail explicitly.

Event cursors are opaque run-scoped sequence positions; retain the tail cursor to poll new events.
Analytics exclude fixtures and include failed/incomplete rounds in denominators. `required_suites`
is an aggregate family; template-specific breakdown requires coordinated engine metadata.
Public errors omit provider exception text, credentials, host paths, and traceback. Evidence
references are opaque IDs; no new download endpoint is introduced.

## Verification and current blockers

Unit-test engines are explicitly marked test doubles and live only in backend/tests. They are
never installed by production composition and do not constitute real security execution evidence.
The lifecycle/API can be validated without keys or attacks. Real execution remains blocked until
A1/A2/A3 are integrated, an engine adapter is supplied, Docker is available, and provider
configuration is present. No claim of a real verified patch is made by this branch.
