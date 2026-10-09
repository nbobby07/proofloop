# Frozen LedgerLite verification and verifier handoff

These tests assert correct behavior. **The original is expected to fail**, without
xfail, skips, weakened assertions, or importing target policy/data as the oracle.
The independent expected data live in `test_ledgerlite.py`. The default root pytest
configuration only discovers backend tests; explicitly invoke this suite.

## Execution

Use Python 3.11+ and the repository's existing `requirements.lock`. Install the root
project's dev dependencies as described in `docs/DEVELOPMENT.md` before execution.
From the repository root:

```sh
# Raw baseline regression test command: exit 1, 37 pass / 7 fail.
python -m pytest verifier_tests/test_ledgerlite.py

# Evidence harness: exit 0 only when the exact expected baseline is reproduced.
python -m verifier_tests.run --variant baseline --output verifier_tests/evidence/baseline.json

# Separate reference: exit 0 only on complete suite success and no reproduced BOLA.
python -m verifier_tests.run --variant reference --output verifier_tests/evidence/reference.json

# Four authored bad patches, each in its own temporary target copy.
python -m verifier_tests.validate_mutants --output verifier_tests/evidence/mutations.json

# Candidate uses an authorized disposable directory with the same demo_target layout.
python -m verifier_tests.run --variant candidate --target-root /absolute/disposable-copy --output /absolute/evidence.json
```

The committed evidence files record actual local execution, not illustrative counts.
`http_transport.json` additionally records all 44 unchanged test functions executed
against loopback uvicorn HTTP for both original and reference: 37/7 and 44/0. It
uses a temporary HTTP-client fixture in place of TestClient (trusted test source
unchanged), and separately records trailing-space normalization versus embedded
space rejection. This is local HTTP validation, not a hardened container claim.
They include every setup/call/teardown outcome, test IDs, pytest exit code, durations,
failure descriptions, probe request/response, manifest SHA-256, input SHA-256s,
runtime versions, stdout/stderr, and explicit completeness. Results remain synthetic
and do not establish a platform `verified` verdict. Re-running may change timing and
traceback paths; test order, fixtures, required IDs, and expectations are deterministic.

`run --variant baseline` returning 0 means **reproduction succeeded**, not that
security tests passed. Its nested `pytest_exit_code` remains 1 and `suite_passed`
remains false. Reference/candidate return 0 only when all 44 checks pass and the
probe does not reproduce unauthorized access. Infrastructure failures/timeouts,
skips, collection drift, missing phases, and changed frozen inputs fail closed.
The CLI writes `complete: false` on execution errors. Each pytest subprocess has a
60-second timeout; the independent probe has a 15-second timeout.

## Frozen suite

`manifest.json` pins all 44 required IDs, trusted Python source hashes, original
fixture hashes, and the single patch path. Do not regenerate it inside verification
or accept a model-provided manifest. Any legitimate test revision requires trusted
review and a suite version change.

- Six owner cases assert HTTP 200 and exact invoice content, preventing blanket
  blocking and inappropriate invoice allowlists.
- Six cross-account cases cover both directions across all six IDs and assert 403
  plus an error body with no invoice. The original fails all six.
- Six Administrator cases assert complete content across both owners.
- Nine missing-invoice cases cover all accounts and three absent IDs (including
  neighboring IDs), asserting 404.
- Fifteen invalid-identity cases cover absent/empty/unknown/wrong-case/embedded-space
  selectors against Alice, Bob, and missing invoices, asserting 401.
- Health and interleaved denied/owner/Administrator access preserve functionality
  and exact content after denials. The vulnerable original fails the sequence case.

`ledgerlite-v2` is a reviewed transport-compatibility revision: the three
invalid-identity cases formerly using `alice ` now use `alice bob`. HTTP servers
may normalize leading/trailing optional header whitespace, while TestClient
preserves it. Rejecting whitespace already stripped by transport is not an
application guarantee. Embedded whitespace survives transport and remains invalid.
All 44 checks and every owner/role/status assertion are preserved; the expected
baseline still has exactly seven BOLA failures.

The mutation validation actually executes four flawed patches: a two-invoice
allowlist, blanket blocking, missing Administrator bypass, and reversed ownership.
All must fail complete suites in the expected test family. These cases detect
these concrete mistakes; a finite public suite cannot exclude every hardcoded or
malicious implementation.

## Exact integration requirements

1. Server-side approved target ID is `LedgerLite`. No arbitrary external target
   URL or client-provided execution command. Target source is `demo_target/ledgerlite/`.
   Required Python modules: `fastapi`, `starlette`, `pydantic`, `pytest`, `httpx2`
   and their locked transitive dependencies. No new root dependencies are needed.
2. Freeze the Git revision and SHA-256 of `verifier_tests/manifest.json` **outside
   the candidate's control**, plus every trusted file and original hash it lists.
   Preserve the original source read-only. The only allowed candidate patch file
   is `demo_target/ledgerlite/app.py`. Data, package initializers, reference source,
   dependencies, runner, tests, policies, and manifests cannot be patched.
3. Make a disposable copy containing `demo_target/__init__.py` and the complete
   `demo_target/ledgerlite/` package. Preserve import names; `app.py` must export
   a no-argument `create_app()` factory. Candidate imports must resolve its own
   `demo_target` copy. The runner places that root before the trusted root in
   `PYTHONPATH` and uses it as the subprocess working directory.
4. Trusted harness/test files stay in the trusted repository root, separate from
   the copy. Candidate command above executes the absolute trusted suite using
   pytest importlib mode and disables auto-loaded pytest plugins. For a lower-level
   runner set `LEDGERLITE_APP_FILE` to the candidate `app.py`, run the frozen suite,
   and use the trusted `record_results` plugin with `LEDGERLITE_RESULTS_FILE` set
   to a writable evidence destination. Do not filter test IDs with `-k`.
5. Run generated candidates only inside the verifier owner's hardened, offline
   container with read-only trusted/original mounts, no credentials, no Docker
   socket, non-root, dropped capabilities, resource/output limits and enforced
   timeout/cleanup. This local subprocess harness supplies **no sandbox** and
   does not safely execute adversarial code. No Docker or verifier engine is
   implemented here. Packages must be preinstalled; no runtime downloads.
6. Consume `complete`, every frozen test outcome, hashes, nested pytest exit code,
   and probe response; counts alone are insufficient. Bind successful candidate
   evidence to the exact patch hash and reproduced baseline. Only the independent
   verifier may combine this with isolation/policy/scanner/challenge evidence to
   establish an execution verdict. A reference pass is a test-oracle demonstration.

## Layout and limits

```text
verifier_tests/
  conftest.py                  # authorized target factory loader
  test_ledgerlite.py            # immutable behavioral oracle and 44 cases
  record_results.py            # phase-level pytest recorder
  probe.py                     # Alice -> Bob reproduction
  run.py                       # completeness checks and JSON evidence CLI
  validate_mutants.py          # four known bad patch experiments
  manifest.json                # frozen IDs/hashes and patch allowlist
  evidence/{baseline,reference,mutations,http_transport}.json
```

Synthetic identity selection is forgeable by design; this suite tests object
ownership given a selected identity, not real authentication. Persistence, writes,
concurrency, timing side channels, invoice listing, unknown routes, real payment
flows, external integrations, scanning, and container isolation are out of scope.
The defined authenticated missing-invoice 404 behavior may disclose existence;
changing that policy needs a reviewed test revision. The harness is useful for
controlled fixtures, not a malicious-target trust boundary. Its timeout bounds
subprocess waiting; production child-process cleanup and output caps belong to the
isolated verifier. Shared CURRENT/docs were not modified because this work owns
only `demo_target/` and `verifier_tests/`.
