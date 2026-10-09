# ProofLoop current state

Updated: October 9, 2026. Submission deadline: **4:30 PM America/Los_Angeles**.

## Objective

Establish a reproducible shared foundation for a two-person team. Next, demonstrate authorized vulnerability reproduction, isolated remediation, and independent adversarial verification. A passing suite is scoped evidence, never universal security.

## Architecture

React/TypeScript/Vite/Tailwind dashboard → FastAPI/Pydantic API → PLANNED bounded orchestration → immutable target plus disposable Docker copies → trusted verification suites → evidence/events. External integrations are PLANNED. `source: fixture` is mandatory for preview data.

## Ownership

- A (`feat/security-engine`): engine, providers, API, storage, backend tests, demo target, verifier tests, sandbox.
- B (`feat/product-dashboard`): frontend, ClickHouse telemetry, narration, Guild integration.
- Shared files: coordinate before editing contracts, docs, scripts, root configuration, and `.github/`.

## Completed milestones

- Framework scaffold, live health route, local CORS, dashboard with explicit fixture labels.
- Typed provider contracts without external calls; planned routes return 501.
- Canonical Pydantic models, generated schemas/OpenAPI/TypeScript, representative fixture.
- Ownership rules, security boundaries, installation guidance, and key-free CI workflow.
- Validation and GitHub publication details are recorded in `docs/SETUP-RESULTS.md` after setup checks.

## Active tasks

- A: implement allowlisted LedgerLite target and trusted baseline/functional tests first; then isolate execution and add deterministic verdicts.
- B: evolve the dashboard against frozen contracts; add loading/error/lifecycle displays and execution-source separation.

## Blockers

- Runtime provider credentials/models, Docker runner availability, and sponsor product access need separate configuration before real integrations.
- Team member names/emails, second developer GitHub handle, and demo-video URL have not been provided.
- Repository collaboration access and hackathon judge access must be configured manually once identities are known.

## Decisions

- No full engine, paid API requests, scanning, or attack execution in setup.
- Use a private GitHub repository initially; visibility changes require explicit authorization.
- Keep framework dependencies small. Docker is required only when implementing the runner.
- Pydantic is the wire-contract authority; generated artifacts are checked for drift.
- Semgrep runtime scanning and Guardian development review are separate integrations.
- Senso development memory is distinct from authoritative application policy; Git remains the code source of truth.

## Next steps

1. Each developer clones separately, selects their feature branch, and validates local startup.
2. Coordinate the first target, policies, event semantics, and frozen test manifest.
3. Ship a deterministic local verification loop before adding model calls or sponsor analytics.
4. Record actual sponsor evidence and prepare submission before 4:30 PM Pacific.
