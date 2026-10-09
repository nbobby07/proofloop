# ProofLoop

**Autonomous adversarial security verification.**

ProofLoop is a Cyberdefense Hackathon project for October 9, 2026 in San Francisco. The planned system discovers vulnerabilities in authorized targets, reproduces them, proposes defensive patches, applies those patches to isolated copies, and challenges the results with independent tests. It exists to make remediation measurable and reproducible.

Agents may propose attacks and fixes. They never determine their own verdicts. A passing result means the patch passed the executed suite; it does not prove universal security.

## Current implementation

Working: FastAPI health endpoint, local CORS, React dashboard shell, a clearly labeled fixture preview, shared Pydantic/TypeScript contracts, provider interfaces, tests, linting, and key-free CI.

**PLANNED:** scanning, reproduction, AI inference, patch application, Docker runner, verification engine, run persistence, ClickHouse analytics, Senso retrieval, hosted Guild review, and ElevenLabs narration. Run/challenge/report/analytics endpoints are contract stubs returning `501 not_implemented`. Fixture success counts are invented interface examples and never execution evidence.

## Architecture and stack

React + TypeScript + Vite + Tailwind → FastAPI + Pydantic → PLANNED orchestrator → isolated target copies + trusted verification → evidence and telemetry. pytest and Ruff validate the backend; ESLint and TypeScript validate the frontend. Python 3.11+ and Node 22.12+ are required; Node 24 LTS is used in CI. No infrastructure or deployment pipeline is required for setup.

See [architecture](docs/ARCHITECTURE.md), [API contract](contracts/api-contract.md), and [security boundaries](docs/SECURITY.md).

## Install

Use a separate clone on each computer. Run from the repository root:

```sh
git clone https://github.com/nbobby07/proofloop.git
cd proofloop
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]" -c requirements.lock
cp .env.example .env
cd frontend
npm ci
cd ..
```

Windows PowerShell substitutes:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]" -c requirements.lock
Copy-Item .env.example .env
cd frontend
npm ci
cd ..
```

If activation is disabled, use `.venv\Scripts\python.exe` directly. Verify `python --version` is at least 3.11 and `node --version` at least 22.12. Dependency versions are frozen in `requirements.lock` and `frontend/package-lock.json`; update them intentionally together.

## Run locally

Terminal 1, repository root, activated Python environment:

```sh
python -m scripts.dev_backend
```

Terminal 2:

```sh
cd frontend
npm run dev
```

Open [dashboard](http://localhost:5173) and [API documentation](http://localhost:8000/docs). The dashboard shows actual health connectivity and separate fixture preview data. Check health with `curl http://localhost:8000/api/health`; Windows can use `Invoke-RestMethod http://localhost:8000/api/health`. Expected JSON: `{"status":"ok","service":"proofloop"}`. The API runs locally without keys or Docker.

## Validate

```sh
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

No check performs inference, scanning, or attacks. Contract regeneration and integration workflow are in [development](docs/DEVELOPMENT.md). Local and remote check outcomes are recorded in [setup results](docs/SETUP-RESULTS.md).

## Team workflow

Developer A: `git switch feat/security-engine`; owns backend engine/providers/API/storage/tests and demo target/verifier/sandbox. Developer B: `git switch feat/product-dashboard`; owns frontend, backend telemetry/reports, and Guild.

Use separate clones and pull requests into `main`. Coordinate shared contracts/docs/root configuration. Do not edit another owner's unfinished work. Read `AGENTS.md` and `CURRENT.md` every session. See [ownership and exact handoff commands](docs/DEVELOPMENT.md).

## Environment variables

`.env.example` contains only empty credential placeholders and non-secret defaults. The backend launcher loads only local host/port/CORS settings; provider loading is PLANNED. Vite reads root `.env` and exposes **only `VITE_*` values** to the browser. Never prefix secrets with `VITE_`.

| Variable | Purpose |
| --- | --- |
| `OPENAI_API_KEY` | PLANNED defender credential; standard OpenAI SDK name |
| `OPENAI_MODEL` | PLANNED configured defender model; no default inference |
| `AKASH_API_KEY` | PLANNED AkashML credential, passed explicitly to its client |
| `AKASH_BASE_URL` | PLANNED OpenAI-compatible base URL, `https://api.akashml.com/v1` |
| `AKASH_MODEL` | PLANNED account-supported attacker model id |
| `CLICKHOUSE_HOST` | PLANNED ClickHouse host name |
| `CLICKHOUSE_PORT` | PLANNED HTTP(S) client port; default secure cloud port 8443 |
| `CLICKHOUSE_USER` | PLANNED database user |
| `CLICKHOUSE_PASSWORD` | PLANNED database password |
| `CLICKHOUSE_SECURE` | PLANNED TLS switch, default `true`; adapt to chosen client |
| `SENSO_API_KEY` | PLANNED policy retrieval key; also supported by Senso CLI |
| `SENSO_ORG_ID` | PLANNED app-level organization selector; validate against authenticated org |
| `GUILD_API_KEY` | Reserved app-level placeholder; verify official Guild auth mechanism before implementation |
| `ELEVENLABS_API_KEY` | PLANNED narration credential, passed explicitly to chosen client |
| `ELEVENLABS_VOICE_ID` | PLANNED voice selection |
| `PROOFLOOP_ENV` | App environment label, reserved for future configuration |
| `PROOFLOOP_BACKEND_HOST` | Backend bind address, default `127.0.0.1` |
| `PROOFLOOP_BACKEND_PORT` | Backend port, default `8000` |
| `PROOFLOOP_CORS_ORIGINS` | Comma-separated allowed frontend origins; no wildcard |
| `PROOFLOOP_FRONTEND_HOST` | Vite development host, default `localhost` |
| `PROOFLOOP_FRONTEND_PORT` | Vite development port, default `5173` |
| `VITE_API_BASE_URL` | Public browser API base URL, default `http://localhost:8000` |

When changing ports, update the browser API URL and CORS origins together. Shell variables override file settings. No provider SDK is installed yet; app-level placeholder names do not imply automatic SDK loading. Never print keys, request authorization headers, or raw sensitive evidence.

## Sponsor roadmap

All integrations are **PLANNED**: Semgrep static scanning; AkashML adversarial generation; ClickHouse telemetry influencing next challenges; Senso grounded policy retrieval; Guild.ai hosted evidence review. Pi sponsors the overall award and needs no API. OpenAI defender and optional ElevenLabs narration are additional tools. [Sponsor contracts and official reference links](docs/SPONSORS.md) describe integration readiness requirements.

Submission deadline: **October 9, 2026, 4:30 PM Pacific**. [Sprint](docs/SPRINT.md) and [submission checklist](docs/SUBMISSION.md) track the remaining work.
