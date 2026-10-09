# ProofLoop collaboration contract

Read `CURRENT.md`, `contracts/api-contract.md`, and `docs/DEVELOPMENT.md` at the start of every session. Confirm the repository root and current branch before editing.

## Ownership and branches

- Developer A: `feat/security-engine`; owns `backend/engine/`, `backend/providers/`, `backend/api/`, `backend/storage/`, `backend/tests/`, `demo_target/`, `verifier_tests/`, `sandbox/`.
- Developer B: `feat/product-dashboard`; owns `frontend/`, `backend/telemetry/`, `backend/reports/`, `guild/`.
- Shared and coordinated: `contracts/`, `docs/`, `scripts/`, `AGENTS.md`, `CURRENT.md`, `README.md`, root configuration, `.github/`.

Work only on your assigned feature branch. `main` is the shared integration branch. Setup engineering is the sole exception: the initial scaffold is committed to `main` before feature work begins. Do not edit another developer's files without agreement. Never overwrite or reset another developer's unfinished work. Never run both sessions against the same checkout; each computer uses its own clone.

## Evidence and trust

Never fabricate findings, executed tests, patches, sponsor calls, or security verdicts. Fixture data must retain `source: fixture` and a visible fixture label. Only executed independent tests and deterministic rules can establish a verdict. Passing the executed suite does not prove universal security.

Read `docs/SECURITY.md` before implementing execution. AI output is untrusted. Do not expose unrestricted shell execution. Patches cannot modify trusted tests, policies, the verifier, or original snapshots. Do not scan unauthorized targets. Keep provider credentials on the backend; never commit secrets or log authentication headers.

## Contracts and integration

Pydantic in `backend/api/schemas.py` is the wire-type source of truth. Coordinate contract changes before editing; regenerate JSON schemas, OpenAPI, and TypeScript using `docs/DEVELOPMENT.md`. Developer B may consume A's provider DTOs but must coordinate changes to them. Report cross-owner imports, required routes, configuration changes, and sponsor dependencies explicitly.

Validate changes before committing: backend tests, Ruff, generated-contract checks, frontend lint, and frontend build as applicable. API keys and real attack execution are prohibited in CI. At task boundaries update `CURRENT.md` and relevant docs with verified milestones, blockers, and next steps; coordinate shared documentation edits. Mark unfinished features PLANNED. Open focused pull requests and merge only completed work after review and passing checks.
