# Execution composition and handoff

All six execution endpoints and health are implemented without changes to canonical Pydantic
wire models or generated contracts. HTTP 202 schedules work; poll run/events. Reports return
409 until terminal. Rechallenge synchronously invalidates current verification before scheduling.

## Real runtime configuration

`backend.api.composition.LedgerLiteEngine` wires the A1/A2/A3 implementations. `create_app()`
installs it when execution is explicitly enabled. No key, image pull, model request, scanner call,
or target execution occurs just by importing the app. Set backend-only environment variables:

| Variable | Required value |
| --- | --- |
| `PROOFLOOP_EXECUTION_ENABLED` | `1` to enable real composition; otherwise runs fail `engine_not_configured` |
| `PROOFLOOP_VERIFIER_IMAGE` | Reviewed, locally installed immutable Docker image ID `sha256:<64 lowercase hex>` |
| `PROOFLOOP_MANIFEST_SHA256` | Independently reviewed SHA-256 of `verifier_tests/manifest.json` bytes |
| `OPENAI_API_KEY` | Backend-only credential; never put in frontend configuration |
| `OPENAI_MODEL` | Explicit supported OpenAI Responses model selected by operator |
| `SEMGREP_EXECUTABLE` | Optional absolute executable path; defaults to `semgrep` on backend PATH |
| `PROOFLOOP_DOCKER_HOST` | Optional local Unix socket; defaults to `unix:///var/run/docker.sock` |
| `PROOFLOOP_RUNS_DIR` | Optional private persistence root; defaults to ignored `runs/` |

The coordinator's `scripts/dev_backend.py` launcher loads an allowlist from ignored `.env`.
Direct Uvicorn startup requires those variables already present in the process environment;
API modules do not evaluate shell text or load arbitrary dotenv keys. Use one API worker.
Missing/invalid configured inputs produce safe codes such as `defender_configuration_missing`,
`invalid_execution_pins`, `approved_inputs_unavailable`, or `approved_inputs_invalid`, never
exception text or configuration values. Defender `ProviderError` codes are explicitly allowlisted
and mapped to fixed `defender_*` failure codes (for example `defender_http_400`,
`defender_missing_model`, `defender_timeout`, or `defender_invalid_patch`). Unknown codes map to
`defender_provider_failure`. The exact safe code appears in terminal events and report summaries;
raw error strings, HTTP responses, and credentials are never persisted. These failures terminate
the run without an automatic model retry, preserving diagnostic visibility and the call budget.
TLS verification remains enabled; certificate setup belongs to the trusted runtime configuration.
A manifest pin must be reviewed out of band; deriving
approval from whichever files happen to be present defeats the trust boundary.

The reviewed HTTP-compatible A1 suite v2 is integrated. Its `suite_version` is read from the
pinned manifest; no test version is hardcoded. Reviewed manifest file hash:
`2e426b9ffb46e0f9168c0327332ef4394728ceb0215ea11af59008f4a1018765`.
The original v1 trailing-space invalid-identity case is not transport stable and correctly prevents
baseline reproduction over HTTP. No tests are skipped or weakened in composition to hide it.

## Real execution path

1. Read only A2's four curated `SOURCE_FILES`, checking every byte against the approved manifest's
   original hashes. Never read or give a provider `reference_secure.py`, provider keys, or tests.
   Freeze trusted suite bytes, local policy, scanner rules, runner code, and image identity.
2. Materialize an immutable disposable copy for `SemgrepScanner.scan_with_details`. Require
   complete diagnostics, exact source coverage, no skips, and pinned rules. Select only A3's
   `proofloop.ledgerlite.invoice-missing-ownership` finding in the mutable app path. Clean scans
   return an honest inconclusive run, never a fabricated finding.
3. Run A2 Docker baseline and `baseline_reproduced`. Infrastructure failures are errors;
   timeout/output-limit/incomplete evidence is inconclusive. Preserve evidence even on failure.
4. Call the real `OpenAIDefender` with immutable source, selected finding, attempt number, and
   independent failed-test feedback. Each call has 30-second timeout, zero HTTP retries, and the
   provider's 8192 output-token cap. The request's 1..10 patch-attempt limit remains authoritative.
5. Apply the proposed unified diff through A2's strict `apply_unified_diff`, against the frozen
   original and `PATCH_ALLOWLIST`. No shell patching or model-supplied commands.
6. Completely rescan the patched source. Run the independent frozen test suite in Docker and
   consume A2 `evaluate_patch`, preserving its verdict. Counts only summarize actual test IDs;
   they do not decide acceptance. Patch/source/policy/manifest/runner/image hashes remain bound.
7. Execute one admitted `ledgerlite_frozen_suite` challenge (within every valid `max_challenges`
   budget). Rerun both baseline and patched suites freshly, including all security, functional,
   and adversarial tests. This is the explicit deterministic challenge mode, not model-generated
   attack code. Unknown policy IDs fail closed. The sole approved policy ID is
   `ledgerlite-object-authorization-v1`; an empty list uses this local policy.
8. Retry rejected independent tests within budget, preserving each attempt. Save content-addressed
   artifacts, publish the independently derived terminal status, and release in-memory context.

AkashML and Senso are optional and are not invoked by this core composition. No hosted-policy or
sponsor inference success is claimed. The reviewed local policy is versioned in composition code
and hash-bound to every manifest. Optional future adapters must preserve these trust boundaries.

## Internal interfaces and bounds

`create_app(orchestrator=Orchestrator(store, engine))` remains available for dependency injection.
The async `ExecutionEngine` methods are `discover`, `reproduce`, `generate_patch`, `apply_patch`,
`verify`, and `challenge`; exact signatures are in `backend/engine/orchestrator.py`.

`DiscoveryReceipt` retains the canonical optional finding plus scanner/context evidence references.
`BaselineReceipt` retains canonical `BaselineResult` plus baseline references. `StageResult`
retains canonical counts, the independent verdict, completeness, references, and the SHA-256 of
exact proposal diff bytes. Only A2's reducer can establish complete verified/rejected test results.
The orchestrator additionally rejects missing evidence, stale patch identity, zero totals, incomplete
receipts, and partial pass counts. Neither static scans nor model claims can upgrade a verdict.

Synchronous scanner/provider/runner work runs off the event loop through at most four live worker
slots. Cancellation does not forcibly kill Python threads; each real adapter has its own bounded
IO/process cleanup. Docker gets 25 seconds of execution and a 45-second total operation deadline,
plus its bounded cleanup. The app allows 180 seconds per lifecycle stage and four active runs.
The model adapter has no automatic retry. Rechallenge consumes no model call in deterministic mode.

Completed context is reconstructed on demand from persisted source/policy/test/rules/runner/image
pins and the exact saved patch. Changes or corrupt context artifacts fail closed. Rechallenge always
executes fresh containers, never reuses previous test outcomes. Active interrupted runs become
`error/execution_interrupted` on API restart rather than resuming half-finished work.

## Persistence, visibility, and validation

Run manifests use private atomic JSON replacement. They retain ordered events, all proposed patches,
application status, every verification/challenge round, safe failures, and opaque evidence references.
Artifacts live under `runs/artifacts`, use content-derived IDs, and are checked against SHA-256 on read.
Configured credentials are redacted, including encoded process output, before artifact persistence;
artifact hashes describe those stored redacted bytes. No download endpoint exposes raw host paths.
Baseline/patch execution artifacts retain test IDs/phases, stdout/stderr, exit codes, durations, and
execution/source/manifest identities. The public report exposes opaque references only.

Only one API process may own a store. Event cursors are run-scoped sequence positions; retain the tail
cursor for polling. Analytics exclude fixture runs and include incomplete/failed rounds in denominators.
`required_suites` is currently aggregate, not a fabricated template-specific breakdown.

Composition tests use explicitly named unit provider/runner doubles, exercising the real snapshot,
patcher, reducer, artifact store, and orchestrator without paid calls or target execution. They do not
prove real container/model success. Real acceptance is performed separately by the integration
coordinator using reviewed runtime pins and a bounded paid run. Passing a finite public synthetic
fixture suite is not universal security or real authentication verification.


Validated on this branch: 265 combined backend/provider/sandbox tests passed, 8 opt-in cases
skipped; Ruff, formatting, and generated-contract drift checks passed. A real Semgrep discovery
smoke using the isolated Semgrep runtime found the approved LedgerLite BOLA rule with complete
four-file coverage, persisted two evidence references, and used suite `ledgerlite-v2`. This smoke
made no provider/model request and does not constitute patch verification. No paid calls were
made by this worker; end-to-end paid acceptance belongs to the coordinator.
