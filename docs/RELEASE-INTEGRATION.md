# Release integration — October 9, 2026

Release worktree: `/Users/noel/Desktop/cyberhack/proofloop-release`.
Branch: `feat/release-integration`. Developer B's branch was not modified.
All six pre-existing local worktrees were clean before integration and were preserved.

## Pinned inputs

| Input | Exact commit |
| --- | --- |
| Original main | `25459d5e9a85fa08cb3dd42bc7c9df288ae64537` |
| Backend: feat/security-engine | `bb5eddf1c413a96557c5c2c25c30bbe9c4ea3f98` |
| Dashboard: feat/product-dashboard | `942607b6026fe7dc1de6f6c10c68ce8211036c05` |
| Normal history-preserving merge | `fe33dd7b54585c4cd5cbe71b6212a9a6b4faf4ad` |

Release integration code commit: `3ecb7dde789a0641013f04db41edbfd04c0bb668`.

Only pushed commits were integrated. Backend worker branches were already contained
in security-engine and were not separately merged again. Later UI pushes require a
new explicit integration; the release never follows a moving dashboard ref.

## Implemented and verified

The React arena consumes all seven frozen v1 endpoints, polls ordered events,
displays actual patches/counts and reports, and supports fresh rechallenge.
Canonical Pydantic, OpenAPI and generated TypeScript remain unchanged.
Backend composition includes Semgrep discovery, bounded OpenAI proposals, exact
patch admission, independent Docker verification, retries and atomic local evidence.

Integration fixes: optional persist-first telemetry worker and explicit schema CLI;
canonical event sequence/patch/round metadata; honest local analytics labels;
rechallenge controls reflecting available v1 admission data; unique evidence-row
keys for repeated content-addressed references; active-stage timeline indicator;
macOS exited-process cleanup race without weakening process limits.

## Actual browser execution

Run `run_2cd6645e223d4febb9e3c3b8d75293d4` was started with the React Start verification
button in Live backend mode using GPT-6 Luna, actual Semgrep and hardened Docker.

- Original unauthorized access returned HTTP 200; baseline had 37 passes and seven
  expected BOLA failures out of 44 frozen checks.
- First real model patch was rejected: security 0/6, functional 16/22, adversarial 15/16.
- Second real model patch passed 6/6 security, 22/22 functional and 16/16 adversarial.
- The automatic independent challenge reran fresh baseline/patched containers and passed.
- The evidence report opened in React with actual artifact IDs and hashes.
- Challenge Again cleared the displayed verdict/counts, displayed Challenging, and
  then showed fresh 44/44 results. Seven distinct execution IDs are preserved overall.
- Final report has 19 hash-validated references; local analytics retain the rejected
  round (one unsuccessful round among four recorded verification/challenge rounds).
- Screenshots show the pending and final states in `evidence/browser/`. Sanitized
  API/evidence receipt: `evidence/release-browser-acceptance.json`.

The final production build reopened the saved run, displayed all 19 report references,
and showed one unsuccessful round among four without console errors.

The initial browser report exposed duplicate React keys for identical scanner
artifacts. That was fixed and the report reopened. No test outcomes were fabricated.
Model output is nondeterministic; this observed success does not guarantee future runs.

## Validation

- Default backend/provider/sandbox suite: 324 passed, eight opt-in skipped.
- Additional opt-in Docker and Semgrep suites: 21 passed, including real isolation,
  network/readonly/secret restrictions, rejection, timeout and cleanup checks.
- Ruff lint and formatting: backend, scripts, demo_target, verifier_tests, sandbox, guild.
- Python contract drift; frontend npm ci/contracts/lint/production build; generated
  TypeScript unchanged; Git whitespace checks.
- History secret check: 218 reachable blobs checked for configured credential values
  and common private-key/token forms, no matches. This is a bounded check, not a
  guarantee that every possible secret format can be detected.

## Sponsor status

| Integration | Actual release evidence |
| --- | --- |
| OpenAI | Two real GPT-6 Luna patch proposals, independent rejection then acceptance |
| Semgrep | Actual discovery and rescans in the browser run; opt-in scanner tests pass |
| Docker verifier | Seven real suite executions in the run, plus isolation tests |
| ClickHouse | Adapter plus durable local-event delivery implemented and tested with doubles; credentials absent, live connection/ingestion unverified |
| AkashML | Adapter preserved; no live call, core challenge uses the frozen deterministic suite |
| Senso | Adapter preserved; no live call, core uses reviewed local policy |
| Guild | Advisory adapter preserved; hosted deployment/API wiring unverified and deferred |
| ElevenLabs | Optional evidence-bound narration adapter preserved; credentials/audio route and live generation unverified |

The demo does not depend on ClickHouse. SQL failure patterns can be queried with
`python -m scripts.telemetry query` after explicit schema setup. The React analytics
route remains backed by local evidence, and never claims database connectivity.
Telemetry currently exports aggregate verification-round outcomes, not per-test
metrics or inferred timing. See `../backend/telemetry/README.md` for precise limits.

## Run the release locally

See the root README installation steps. Before the release merges, select
`feat/release-integration`. The backend reads ignored root `.env`. Execution requires
an actual backend-only OpenAI key, model, Semgrep executable, reviewed local image,
and trusted manifest pin; absent inputs produce a visible error, never fixtures.
The Docker build and configuration instructions are in `backend/api/INTEGRATION.md`
and `sandbox/README.md`.

On the integration machine the existing runtime is reused without modifying it:

```sh
cd /Users/noel/Desktop/cyberhack/proofloop-release
../proofloop/.venv/bin/python -m scripts.dev_backend
# Separate terminal:
cd /Users/noel/Desktop/cyberhack/proofloop-release/frontend
npm run dev -- --host 127.0.0.1 --port 5174
```

Release frontend: http://127.0.0.1:5174; backend: http://127.0.0.1:8001.
Separate ports preserve the existing developers' servers. The ignored release
configuration sets matching VITE_API_BASE_URL and CORS. Default fresh-clone ports
remain 5173/8000. Keep one backend process per run store and bind only to loopback.

## Delivery and remaining boundaries

The owner explicitly authorized public visibility; the repository was made public
and an unauthenticated HTTP request returned 200. Main requires backend/frontend
CI and one approving review. No protection bypass, forced push or branch cleanup.
PRs #1 and #3 remain open until the final release PR actually merges. After a normal
merge, the contained backend worker/security-engine branches can be considered for
manual deletion after submission, only if their tips still remain ancestors of main.
Keep Developer B's active dashboard branch and all worktrees.

Submission/video/contact collection is deferred at the user's request. No submission
was attempted. Optional sponsors do not block the core demo. This is a finite,
authorized synthetic LedgerLite suite, not a universal security guarantee or a
publicly authenticated hosted product.
