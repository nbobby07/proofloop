"""Cross-platform backend launcher; loads explicit backend-only local configuration."""

import os
from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parents[1]
SETTINGS = {
    "PROOFLOOP_BACKEND_HOST",
    "PROOFLOOP_BACKEND_PORT",
    "PROOFLOOP_CORS_ORIGINS",
    "PROOFLOOP_EXECUTION_ENABLED",
    "PROOFLOOP_VERIFIER_IMAGE",
    "PROOFLOOP_MANIFEST_SHA256",
    "PROOFLOOP_DOCKER_HOST",
    "PROOFLOOP_RUNS_DIR",
    "SEMGREP_EXECUTABLE",
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    "SSL_CERT_FILE",
    "PROOFLOOP_TELEMETRY_ENABLED",
    "CLICKHOUSE_HOST",
    "CLICKHOUSE_PORT",
    "CLICKHOUSE_USER",
    "CLICKHOUSE_PASSWORD",
    "CLICKHOUSE_SECURE",
    "CLICKHOUSE_DATABASE",
}


def load_environment() -> None:
    path = ROOT / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition("=")
            if separator and key.strip() in SETTINGS:
                os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def main() -> None:
    load_environment()
    uvicorn.run(
        "backend.api.main:app",
        host=os.getenv("PROOFLOOP_BACKEND_HOST", "127.0.0.1"),
        port=int(os.getenv("PROOFLOOP_BACKEND_PORT", "8000")),
        reload=True,
        reload_dirs=[str(ROOT / "backend")],
    )


if __name__ == "__main__":
    main()
