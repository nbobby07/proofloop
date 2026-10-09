# Development and collaboration

Use Python 3.11+ and Node 22.12+ (24 LTS recommended). Commands assume the repository root unless explicitly stated. Read `CURRENT.md`, `AGENTS.md`, and the API contract before implementing.

## Developer A — security engine

On A's computer:

```sh
git clone https://github.com/nbobby07/proofloop.git
cd proofloop
git switch feat/security-engine
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]" -c requirements.lock
cp .env.example .env
python -m pytest
python -m scripts.dev_backend
```

Owns `backend/engine/`, `backend/providers/`, `backend/api/`, `backend/storage/`, `backend/tests/`, `demo_target/`, `verifier_tests/`, `sandbox/`. Build authorized baseline reproduction, immutable tests, isolation, deterministic verification, then model integrations.

## Developer B — product and integrations

On B's separate computer:

```sh
git clone https://github.com/nbobby07/proofloop.git
cd proofloop
git switch feat/product-dashboard
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]" -c requirements.lock
cp .env.example .env
cd frontend
npm ci
npm run lint
npm run build
npm run dev
```

In a second terminal at repo root, activate the environment and run `python -m scripts.dev_backend`. Owns `frontend/`, `backend/telemetry/`, `backend/reports/`, `guild/`. Build product flows against the frozen API; retain visible fixture labels until actual evidence arrives.

Windows PowerShell: replace `python3 -m venv` with `py -3 -m venv`, activation with `.\.venv\Scripts\Activate.ps1`, and `cp` with `Copy-Item`. If activation is unavailable, invoke `.venv\Scripts\python.exe` directly for Python commands. No bash scripts are required.

## Shared ownership

Coordinate changes to `contracts/`, `docs/`, `scripts/`, `.github/`, root config, README, CURRENT, and AGENTS. Neither owner may modify the other's unfinished files without agreement. Do not run both sessions against one working tree. Separate directories reduce conflicts; coordination is still required for interfaces and merges.

Keep commits focused. Before starting each task:

```sh
git status --short
git branch --show-current
git fetch origin
git merge origin/main
```

Resolve merges on your own feature branch without discarding another developer's work. Never force-push shared branches. Update progress docs at task boundaries after coordinating shared edits. Open a PR only when changes are reviewable:

```sh
git add <exact-reviewed-paths>
git commit -m "Describe the concrete change"
git push origin HEAD
gh pr create --base main
```

Do not merge unfinished work. Peer review and green checks are required by team policy even if the account plan cannot enforce branch protection. The initial setup commit is on `main`; both feature branches start there.

## Contracts and checks

```sh
python -m scripts.export_contracts
python -m pytest
python -m ruff check backend scripts
python -m ruff format --check backend scripts
python -m scripts.export_contracts --check
cd frontend
npm run contracts
npm run lint
npm run build
cd ..
git diff --exit-code -- frontend/src/types/api.generated.ts
```

The last drift check is intended after generated changes are reviewed/committed; an intentional uncommitted contract update will produce a diff. CI regenerates types and fails on drift. Python schema exports are checked without writes. Do not regenerate fixture values from execution output or silently remove failing samples.

## GitHub setup recovery

If publication needs to be rerun, first inspect local remotes and `gh repo view nbobby07/proofloop`. Never replace an existing remote. For a local scaffold with no remote repository, the remaining commands are:

```sh
gh auth login
gh repo view nbobby07/proofloop
# Proceed only if inspection confirms the repository does not exist.
gh repo create nbobby07/proofloop --private --source . --remote origin --push
git push origin feat/security-engine feat/product-dashboard
gh run list --workflow ci.yml
```

An owner must invite the second developer to this private repo. Keep it private until explicitly authorized otherwise. Ensure judges receive access or coordinate visibility before submission. Basic main protection may require a paid GitHub plan for private repositories.

## Optional Senso shared memory

Senso setup is manual and optional. Each developer authenticates separately in the team's existing organization:

```sh
npm install -g @senso-ai/cli
senso login
senso whoami
senso search context "ProofLoop development ownership"
```

For unattended login, the documented completion command is `senso login --complete` after browser approval. Never put keys on command lines. `SENSO_API_KEY` is supported by the CLI.

The [official Senso CLI documentation](https://docs.senso.ai/docs/senso-cli) currently rejects `.md` file uploads; use its MCP text ingestion for Markdown, or explicitly prepare approved non-secret TXT copies before using `senso ingest upload`. This setup does not ingest anything, create an organization, or assume Senso access. Keep development memory separate from authoritative target security policies. GitHub remains the shared code source of truth.
