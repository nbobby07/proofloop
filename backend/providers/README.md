# Provider integration handoff

All four protocol stubs now have concrete synchronous adapters using the existing canonical
DTOs. No wire contracts, dependency manifests, routes, or verifier code were changed.
The three owned engine modules re-export their corresponding adapter classes.

## Construction and coordinator responsibilities

```python
from backend.providers.openai_client import OpenAIDefender
from backend.providers.semgrep_client import SemgrepScanner
from backend.providers.akash_client import AkashAttacker, ChallengeTemplate
from backend.providers.senso_client import SensoPolicyStore, ApprovedPolicyDocument
```

- `OpenAIDefender(allowed_files={"ledgerlite/app.py"}, attempt=attempt)` reads
  `OPENAI_API_KEY` and `OPENAI_MODEL`. Model choice must support Responses structured outputs.
  `generate_patch(source, finding, feedback)` returns canonical `PatchProposal` only after
  strict DTO and exact-context unified-diff admission. Supply a canonical provider
  `SourceSnapshot(snapshot_id=<opaque id or digest>, files=<approved path-to-text mapping>)`.
  A2's immutable byte snapshot is a different internal type: convert its approved files to
  UTF-8 text while retaining the immutable original for trusted application/verification.
  Paths in both snapshots and the patch allowlist must match. Recreate the defender per attempt.
  The model cannot set a different attempt. No SDK, filesystem writes, or tools are used.
  Proposals remain untrusted until A2's `apply_unified_diff` and independent verifier accept them.
- `SemgrepScanner(approved_roots=[frozen_source_root], executable="semgrep")` uses the
  bundled, limited Python rules. Paths must be real directories without symlinks; on macOS
  resolve the trusted workspace parent before construction (e.g. `/private/tmp`, not `/tmp`).
  `scan_repository(workspace)` returns canonical `ScanResult`.
  Prefer `scan_with_details(workspace)` to preserve `ScanReport.locations` (real rule ID,
  relative path, start/end line), safe diagnostics, exit code, scanned/skipped paths,
  ruleset names and limitations in internal evidence. Canonical `Finding.id` is a stable
  identifier derived from the real rule/location, because dotted rule IDs cannot fit the
  frozen API Identifier type. Version and rule-content hash remain in `ScanResult`.
  Optional `rules=[trusted_local_yaml_files]` pins exact local bytes at construction and
  detects later changes. Configure `source_suffixes=(".py", ...)` to match your approved
  source languages when providing custom rules; every matching source file must appear in
  scanned paths. Root approval must cover only approved source/workspace parents, never `/`.
  Errors, skips, zero scanned files, missing required sources, malformed JSON, missing CLI,
  timeout and changed rules produce `complete=False`; unauthorized/unsafe source trees raise
  `ProviderError`. Do not turn either into a clean scan. Preserve known findings on partial
  scans. Freeze source outside this adapter; it is not a source immutability manager.
  Metrics/version checks are disabled; no Guardian, registry fetch, account or autofix is used.
  The bundled rule set covers direct SQL string construction and dynamic Python evaluation;
  it is deliberately limited and is not proof of complete security coverage.
- `AkashAttacker(approved_targets={"LedgerLite": [ChallengeTemplate(...)]},
  max_challenges=2)` reads `AKASH_API_KEY` and `AKASH_MODEL`. Select an account-available
  model supporting documented `response_format: json_schema`. Endpoint is fixed at
  `https://api.akashml.com/v1/chat/completions`; arbitrary `AKASH_BASE_URL` overrides are
  intentionally unsupported. Each template supplies `family`, required `policy_ids`, and
  `parameter_sets` containing finite exact scalar choices (strings <=256 chars, integers
  <=10000 in magnitude, booleans). Shell/code/path/URL parameter slots are prohibited.
  `generate_challenges(target, policy, previous_results)` validates canonical DTOs,
  authoritative policy sources, target/family/policy/parameter membership, count, and
  challenge-ID uniqueness against previous results. Returned specs must be admitted and
  executed by A1/A2's trusted matching templates; this adapter never runs them or claims success.
- `SensoPolicyStore(approved_documents=[ApprovedPolicyDocument(...)])` reads `SENSO_API_KEY`.
  Each trusted binding supplies `policy_id`, canonical UUID `content_id` and `kb_node_id`,
  integer `revision`, SHA-256 of the exact UTF-8 approved full text, and `authoritative`.
  Authority is never inferred from remote metadata, ranking, editorial status or memory.
  Scoped context retrieval uses `POST /org/search/context`, then full policy reads use
  `GET /org/kb/nodes/{node_id}/content?version=<revision>`. Search must resolve to approved
  nodes; full text, ingestion completion, revision and hash must match. Empty results,
  missing authoritative sources, inconsistent source/revision mappings, stale chunks and
  differently worded authoritative documents for the same policy fail explicitly.
  Semantic conflicts across different policy IDs still require trusted policy governance.
  `retrieve_policy_sources(policy_ids)` retrieves every approved document for the requested
  IDs. No ingestion, policy creation or organization writes occur. `SENSO_ORG_ID` is not sent;
  the official API scopes the organization through the key and its KB permissions.

All constructors accept explicit credentials instead of environment values; never serialize
client state or authentication headers. Missing keys/models raise safe `ProviderError` codes
when called. Provider bodies/raw exceptions are not logged or surfaced. Model refusals and
incomplete outputs never synthesize success. HTTP payload/response limit is 1 MB; request
socket timeout defaults to 30 seconds (Senso 20); retries default to one, configurable 0..2,
with bounded backoff. Timeout settings accept (0,60] seconds. Scanner has a version probe
budget up to 10 seconds plus scan budget (default 30), fixed per-rule timeout, process-group
cleanup, and 4 MB output cap. Its child environment excludes provider credentials.

The coordinator must call these synchronous operations off the async event loop, e.g.
`await asyncio.to_thread(defender.generate_patch, source, finding, feedback)`. Configure an
outer stage deadline covering `(retries + 1) * timeout + backoff` (or all Senso document
reads plus search). Python thread cancellation does not cancel an in-flight provider call.
Catch `ProviderError` and check `ScanResult.complete`; only the independent verifier may
assign an execution verdict. Preserve scanner/policy revisions, failed attempts and evidence.

## Dependencies, tests and current validation

No additional Python HTTP/LLM SDK dependencies are needed. Existing Pydantic is sufficient.
Install the separate runtime CLI **`semgrep==1.180.0`**, the version actually exercised locally,
preferably in a dedicated environment to avoid changing application dependency resolution.
The coordinator owns any shared manifest/lock/CI changes.

```sh
python -m pytest backend/tests backend/providers/tests -ra
python -m ruff check backend scripts
python -m ruff format --check backend scripts
python -m scripts.export_contracts --check
```

**CI integration required:** existing pytest `testpaths` includes only `backend/tests`.
The coordinator must add `backend/providers/tests` to CI's explicit pytest command or shared
configuration so adapter tests are collected. Default tests need no credentials, CLI, or network.
Mock responses are labeled test data and never installed as production providers.

Opt-in local real CLI check (no provider keys, no runtime rule downloads):

```sh
PROOFLOOP_RUN_LOCAL_SEMGREP=1 SEMGREP_EXECUTABLE=/absolute/path/to/semgrep \
  python -m pytest backend/providers/tests/test_semgrep.py -ra
```

Three paid/external checks in `tests/test_live.py` are individually disabled unless
`PROOFLOOP_LIVE_OPENAI=1`, `PROOFLOOP_LIVE_AKASH=1`, or `PROOFLOOP_LIVE_SENSO=1`.
Senso additionally requires operator-approved `SENSO_APPROVED_DOCUMENTS_JSON` (a JSON list of
binding objects above) and `SENSO_POLICY_QUERY`. No external calls were made in this worktree:
OpenAI/Akash/Senso keys and both model variables were absent in the process environment and
there were no local `.env` files in this worktree or the inspected project parent/checkouts.
Live local Semgrep detected direct SQL interpolation and `eval`, and completed a subsequent
clean `eval` scan. This demonstrates scanner execution only, not remediation verification.

## Official implementation sources

- [OpenAI Responses structured output](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses)
- [AkashML introduction and endpoint/auth](https://akashml.com/docs/getting-started/introduction)
- [AkashML chat-completion schema](https://akashml.com/docs/api-reference/openai/post-v1-chat-completions)
- [Semgrep CLI reference](https://docs.semgrep.dev/cli-reference)
- [Semgrep JSON fields](https://docs.semgrep.dev/semgrep-appsec-platform/json-and-sarif)
- [Senso core concepts and retrieval/auth](https://docs.senso.ai/docs/concepts)
- [Senso official OpenAPI specification](https://docs.senso.ai/specs/sdk-api.yaml)

These adapters are implemented and mock-tested. Only Semgrep was exercised against its real
runtime; sponsor HTTP integrations require an actual credentialed call before being described
as functional sponsor executions. Shared CURRENT/SPONSORS status updates belong to the coordinator.

Recorded validation on October 9, 2026:

```text
Default combined suite: 144 passed, 4 skipped (three provider network checks, one local CLI check).
Opt-in combined suite before the final HTTP-only tests: 141 passed, 3 skipped in 34.79s.
Real Semgrep CLI: 1.180.0.
Bundled ruleset hash: dd2fed04e3aeaf1427dfe1bde191fe1031da54d2e07999eaa59b880775fee3e8.
Real match IDs: proofloop.python.dynamic-eval; proofloop.python.sql-formatted-query.
Clean eval-removal case: complete=True, findings=[].
Partial .semgrepignore case: complete=False, required_sources_not_scanned.
Ruff check/format: passed. Generated API contract drift check: current.
```

The CLI cases used disposable generated adapter-test source, not an application security
verdict. None of these results is an OpenAI/AkashML/Senso credentialed execution claim.
