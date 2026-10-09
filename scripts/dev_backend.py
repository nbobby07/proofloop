"""Cross-platform backend launcher; loads only non-secret development settings."""

import os
from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parents[1]
SETTINGS = {"PROOFLOOP_BACKEND_HOST", "PROOFLOOP_BACKEND_PORT", "PROOFLOOP_CORS_ORIGINS"}


def main() -> None:
    path = ROOT / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition("=")
            if separator and key.strip() in SETTINGS:
                os.environ.setdefault(key.strip(), value.strip().strip("\"'"))
    uvicorn.run(
        "backend.api.main:app",
        host=os.getenv("PROOFLOOP_BACKEND_HOST", "127.0.0.1"),
        port=int(os.getenv("PROOFLOOP_BACKEND_PORT", "8000")),
        reload=True,
        reload_dirs=[str(ROOT / "backend")],
    )


if __name__ == "__main__":
    main()
