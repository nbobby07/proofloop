# Security boundaries

This scaffold has no scanning or code-execution engine. The following are required design boundaries for future implementation, all **PLANNED** until tested.

## Authorization and trust

Only scan and attack targets owned by the team or explicitly authorized for testing. The initial target selector is a server-side `LedgerLite` id, never an arbitrary external URL, file path, shell command, or repository supplied to a model. No remote API exposure until access control and target authorization exist.

AI-generated source, diffs, attack specifications, model messages, retrieved documents, and target output are untrusted. Agents may propose; trusted code validates, executes, and decides. Do not offer AI unrestricted shell tools. Keep original snapshots, test manifests, policy revisions, and verifier code immutable and hash-pinned for each attempt.

## Workspace and patch controls

- Create disposable run/attempt workspaces under ignored `sandbox/workspaces/`; never execute against the developer checkout.
- Apply patches only to an explicit file allowlist. Reject absolute paths, traversal, symlink escapes, special files, unexpected new files, and oversized edits.
- Patches cannot modify verification tests, policies, the runner, dependencies without review, or immutable originals.
- Model-generated challenge code/specifications require trusted admission checks. Prefer bounded parameters selecting allowlisted independent templates.

## Docker runner requirements

- Non-root user, read-only root filesystem, bounded ephemeral scratch space; drop all capabilities and enable no-new-privileges.
- Explicit CPU, memory, PID, disk/output, execution-time, and total-attempt limits; terminate and clean up child processes on timeout.
- No host home, `.env`, GitHub credentials, SSH agent, cloud credentials, or Docker socket mounted into the container. Pass no inherited host environment or provider keys.
- Verification has no external network. Prefer app and tests in one isolated runner/container using loopback, with Docker network disabled; no host ports. If a multi-container design becomes necessary, document and test an internal-only network before use.
- Original and trusted tests mounted read-only, writable disposable target copy only where needed. Pin image/dependency versions. No package downloads during verification.
- Docker is an isolation layer that must be configured and tested, not an assurance by itself. An unavailable runner or violated boundary produces an explicit failure and stops execution.

No Docker image is provided yet: choose its target/runtime and resource limits after the immutable test plan is agreed. Never turn the absence of runner setup into fake test results.

## Verdicts and evidence

A real `verified` result requires baseline reproduction and fully executed required security, functional, and adversarial tests bound to the exact patch and policy/suite manifests. Failure is recorded; skipped tests, timeout, stale/missing evidence, runner/provider errors, and incomplete scans never count as passing. Freeze required test ids before execution and record every outcome, exit code, duration, and relevant hash.

LLM confidence, static-scan silence, hosted review, narration, and telemetry cannot establish a security verdict. Passing covers the executed suite only. Retry loops are bounded and preserve failed attempts. Rechallenge clears the previous passing status until required work completes.

## Data and credentials

Provider keys exist only on the backend and are never copied into verification. Never expose them via `VITE_*`, logs, auth headers, raw exceptions, commits, telemetry, or reports. Redact secrets and sensitive test-target values before persistence or external review. Generated runs/reports/workspaces are ignored by Git; ignored data still needs careful access control.

Development fixtures have `source: fixture`, visibly label all counts/events as illustrative, and are excluded from real analytics. Use event ids to deduplicate telemetry. Senso development memory cannot redefine application security requirements. Only designated authoritative policy sources may drive required tests.

## Before real execution

Demonstrate allowlist enforcement, frozen-test immutability, secret exclusion, network denial, resource/time limits, explicit incomplete outcomes, and cleanup with controlled tests. Keep host secrets inaccessible even when generated target code is malicious. Document residual limits in every evidence report.
