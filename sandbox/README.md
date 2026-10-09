# ProofLoop independent verifier

Internal Python interface (no wire-contract changes). `sandbox/` must be present on
PYTHONPATH alongside `backend/`; the scaffold wheel currently packages only `backend`.
Run from the repository root. No host execution of candidate source is supported.

```python
from pathlib import Path
from backend.engine.patcher import SourceSnapshot
from backend.engine.verifier import Verifier
from sandbox.ledgerlite import SOURCE_FILES, manifest_from_ledgerlite
from sandbox.models import ExecutionLimits
from sandbox.runner import DockerRunner

# trusted_manifest_document is A1's verifier_tests/manifest.json, loaded by the
# orchestrator from trusted storage. policy_sha256 pins the reviewed policy bundle.
manifest = manifest_from_ledgerlite(trusted_manifest_document, policy_sha256=policy_sha256)
# curated_source contains ONLY SOURCE_FILES in repo-relative layout, no .git,
# README, reference patch, tests, secrets, caches, links, or unapproved files.
original = SourceSnapshot.capture(Path(curated_source), SOURCE_FILES)
runner = DockerRunner(image_id="sha256:" + approved_local_image_id)
result = Verifier(runner).verify_patch(
    original,
    {"demo_target/ledgerlite/app.py": proposed_complete_app_source},
    Path(trusted_suite_root),  # contains verifier_tests/ paths from frozen manifest
    manifest,
    ExecutionLimits(),
)
report = result.to_dict()  # verdict, hashes, diff, complete baseline/patched evidence
```

`DockerRunner.run(workspace: SourceSnapshot, trusted_suite: Path,
manifest: FrozenTestManifest, limits: ExecutionLimits, *, phase="baseline"|"patched",
deadline=<optional time.monotonic deadline>) -> ExecutionEvidence` is the low-level
runner interface. It never decides a passing verdict. `Verifier.verify_patch` creates
both executions itself; never feed provider-supplied evidence to `evaluate_patch`.

`SourceSnapshot.capture` freezes bytes in a frozen dataclass. `apply_patch` admits
full-file replacements and produces a unified diff plus immutable original/patched
snapshots. Only the verifier's LedgerLite app allowlist is patchable; supporting
source stays frozen. Disk copies are freshly materialized read-only per execution,
checked after execution, and deleted. Snapshots remain in memory for evidence and
retry use. Persist their bytes and hashes in trusted storage if durable retention is
required. The defender must never have direct write access to that storage.

## Fixture integration

A1's `verifier_tests/test_ledgerlite.py` assertions run unchanged. Its in-process
`conftest.py`, local `run.py`, `probe.py`, and result plugin are hash-checked but are
**not executed** by the independent runner. `--noconftest` and disabled plugin
autoload prevent accidental in-process candidate imports. Our pinned trusted
adapter provides the `client.get` HTTP interface over loopback. Unknown future
checks require explicit category admission in `manifest_from_ledgerlite`.

The approved target is `demo_target.ledgerlite.app:app` on loopback port 8000.
The exact four source paths are exported in `SOURCE_FILES`; only app.py may change.
The image needs Python at `/usr/local/bin/python`, `/usr/bin/env`, FastAPI,
Uvicorn, and pytest. The tests' HTTP client uses the standard library.
The fixture baseline must fail exactly the frozen cross-account and access-sequence
checks and return Bob's exact synthetic invoice to Alice. The patched execution
must pass every security, functional, and adversarial check and deny that probe.

## Container isolation and evidence

Two fresh containers share only a network namespace: target uses `--network none`;
tests join `container:<target>` for loopback HTTP. They have separate PID, mount,
IPC and scratch namespaces, and different non-root UIDs. Target source never enters
the trusted test container. Target output cannot write the tester's result pipe.
There are no host ports, host environment forwarding, credential directories,
repository mounts, or Docker socket mounts. Only exact curated files are mounted
read-only. Container Python runs with `-I -B` via `env -i`; no package installs occur.

Both containers have read-only roots, all capabilities dropped, no-new-privileges,
default seccomp, CPU quota, memory and equal memory+swap limits, PID limits, file
size/descriptor limits, disabled core dumps, bounded noexec/nosuid/nodev tmpfs,
and 1 MB shared memory. Docker logs are disabled; attached pipes are drained with
bounded exact-byte capture. Timeout/output-limit kills and removes both containers,
including descendants. Cleanup failures override any successful verdict.
Default limits apply **per container**: 1 CPU, 256 MB RAM, 64 PIDs, 32 MB tmpfs;
30 seconds per execution, 120 seconds across the patch attempt, 1 MB per captured
process. Control calls are capped at 10 seconds; cleanup can add up to 20 seconds
beyond the attempt deadline so that resource reclamation is still attempted.

The image must be a locally installed, reviewed immutable `sha256:` image ID.
The runner rejects missing images, implicit image volumes, remote Docker endpoints,
and daemons missing required resource/seccomp support. It never pulls images or
silently executes on the host. Use a local Unix socket; configure Docker Desktop's
socket explicitly when it differs from `/var/run/docker.sock`.

Evidence includes every test identity, setup/call/teardown outcome, captured test
stdout/stderr, failure text, exit codes, process status, actual target logs,
control-command diagnostics, and source/manifest/policy/runner/image identities.
The test process stdout is the raw JSON envelope; decoded pytest stdout/stderr and
per-test output are inside that envelope. Base64 fields retain non-UTF-8 process
bytes. Output beyond the cap is explicitly truncated and never accepted as passing.
Skipped/xfail, missing/duplicate tests, timeout, setup/teardown errors, stale hashes,
unavailable Docker, malformed results, and runner failures cannot pass.

## Verification and limitations

Run `python -m pytest sandbox/tests backend/tests` and `python -m ruff check
backend/engine/patcher.py backend/engine/verifier.py sandbox`. Docker integration
is opt-in via `PROOFLOOP_TEST_IMAGE=sha256:<local image ID>`; absent this variable,
tests explicitly skip rather than claiming isolation was exercised.

Docker is a shared-kernel boundary, not a VM security proof. This supports only the
reviewed LedgerLite HTTP fixture; arbitrary repositories, generated tests, arbitrary
commands, dependency changes, multi-service targets, and general test clients are
unsupported. A malicious app can recognize test requests: passing the frozen suite
is not universal security. Trusted tests, the Docker daemon/image, local filesystem
owner, and orchestrator remain trusted. Read-only modes cannot protect against a
privileged host owner; immutable in-memory bytes and before/after hashes protect
the supported workflow. Approved source/test files and the reviewed image must not
contain credentials; this is an explicit integration precondition, not a secret
scanner. Raw evidence is local and may contain sensitive responses; redact before
telemetry, public reports, or provider feedback. Do not mount a Docker socket or
credentials into either container when integrating this runner.

### Unified diff integration

`Verifier.verify_patch` accepts either full-file replacement mappings **or a unified
diff string** as its second argument. For canonical provider `PatchProposal.diff`,
pass that exact string. `apply_unified_diff(original, diff, *, allowed_files)` is
also exported by `backend.engine.patcher`; it returns `PreparedPatch`. It applies
exact hunks without fuzz, shell commands, or Git invocation. The original admitted
diff bytes are preserved, so `patch_sha256` is SHA-256 of `PatchProposal.diff` UTF-8.
File creation/deletion, renaming, mode changes and binary patches are unsupported.

For orchestrator stages, `runner.run(..., phase="baseline")` plus
`baseline_reproduced(evidence, manifest)` provides reproduction evidence. Store it
with the original source hash. After `apply_unified_diff`, run `patch.patched` with
`phase="patched"`, then `evaluate_patch(patch, manifest, baseline, patched)`.
The reducer checks identities, completeness, phases, and exit codes itself. An
additional challenge must use a newly frozen reviewed manifest and fresh baseline
and patched executions; do not carry a previous passing verdict into the new suite.
Keep provider DTO conversion in the orchestrator adapter. No cross-owner modules
or API schema files were changed by this implementation.

Build the reviewed image outside verification with `sandbox/Dockerfile`, supplying
a digest-pinned `PYTHON_BASE`. Only pinned dependencies from
`sandbox/requirements.lock` are installed, and only at build time. Obtain the local
image ID with `docker image inspect --format '{{.Id}}' proofloop-runner:local`, then
pass that `sha256:...` value directly to `DockerRunner` and `PROOFLOOP_TEST_IMAGE`.
The full example above concatenates `sha256:` only if you have the bare digest.
