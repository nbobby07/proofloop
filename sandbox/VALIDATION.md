# Verification record — October 9, 2026

Branch: `feat/a-verifier`; worktree: `proofloop-verifier`.

- `python -m pytest sandbox/tests backend/tests`: **120 passed, 3 skipped**.
  Skips are the opt-in Docker integration tests, because no reviewed local image
  was supplied and the local Docker daemon is unavailable.
- `python -m ruff check backend scripts sandbox`: passed.
- `python -m ruff format --check backend scripts sandbox`: passed.
- `python -m scripts.export_contracts --check`: contracts current.
- `git diff --check`: passed.
- Live `DockerRunner.run` against the unavailable local Docker daemon returned
  `status: infrastructure_error`, zero test evidence records, and a cleaned
  disposable workspace. Docker's formatted `info` command returned exit code 0
  alongside a daemon error; the runner detects the missing server and preserves
  that real exit code and stderr instead of treating it as successful execution.
- Read-only admission of A1's then-current `ledgerlite-v1` manifest checked seven
  trusted file hashes and 44 required identities: 6 security, 22 functional,
  16 adversarial; 7 expected baseline failures. This checked compatibility and
  file integrity only, with a placeholder policy digest. It did not execute A1's
  target, and is not a security verdict for LedgerLite.

Unit coverage includes valid/invalid Python patches, exact-context unified diffs,
protected-file admission, immutable snapshots, special files and links, malformed
or missing evidence, explicit skipped/xfail outcomes, source/manifest/image/runner
identity mismatches, process exit codes, non-UTF-8 output, output caps, deadlines,
and container/workspace cleanup (Docker control-plane simulations).
A harmless trusted test also exercises the real pytest plugin's HTTP-client
fixture registration, collection identities, phase reporting, and stdout capture;
no candidate source is imported or executed on the host.

The three Docker integration tests are supplied for real valid/invalid patch
execution, source/root read-only enforcement, secret/socket/test-directory
exclusion, external-network denial, and a hanging target. **These container
properties have not been exercised on this machine.** CPU/memory/PID flags and
separate namespace configuration have unit checks; runtime resource enforcement
still needs Docker integration validation. No container security or LedgerLite
remediation success is claimed from mocked tests.

Before integration, provide a reviewed local digest-pinned image, a working local
Docker daemon with required cgroup/seccomp capabilities, the exact curated source
inventory, A1's frozen trusted suite, the reviewed policy digest, and bounded
execution limits. Build and runtime instructions and residual security limitations
are in `sandbox/README.md`. The root package configuration must include `sandbox`
when deploying as a wheel; running from the repository root already exposes it.
