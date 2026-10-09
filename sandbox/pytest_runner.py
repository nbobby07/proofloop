"""Trusted container entry point: HTTP-only pytest client; never imports target code."""

import contextlib
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

BASE_URL = "http://127.0.0.1:8000"
EXPECTED_LEAK = {
    "id": "inv-2047",
    "owner_id": "bob",
    "amount_cents": 48750,
    "currency": "USD",
    "status": "paid",
    "source": "fixture",
}


class Response:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self.content = body
        self.text = body.decode("utf-8", errors="replace")

    def json(self):
        return json.loads(self.content)


class Client:
    def __init__(self):
        # Never use image/host proxy configuration.
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def get(self, path, headers=None):
        if not path.startswith("/") or path.startswith("//"):
            raise ValueError("Only LedgerLite relative HTTP paths are supported")
        request = urllib.request.Request(BASE_URL + path, headers=headers or {})
        try:
            response = self.opener.open(request, timeout=2)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            body = response.read(65537)
            if len(body) > 65536:
                raise ValueError("Target response exceeds limit")
            return Response(response.code, body)


class Recorder:
    def __init__(self):
        self.collected = []
        self.results = {}

    @pytest.fixture(scope="session")
    def client(self):
        return Client()

    def pytest_collection_finish(self, session):
        self.collected = [item.nodeid for item in session.items]

    def pytest_runtest_logreport(self, report):
        self.results.setdefault(report.nodeid, []).append(
            {
                "phase": report.when,
                "outcome": report.outcome,
                "duration_seconds": report.duration,
                "stdout": report.capstdout,
                "stderr": report.capstderr,
                "failure": str(report.longrepr) if report.failed or report.skipped else None,
                "wasxfail": getattr(report, "wasxfail", None),
            }
        )


class LimitedText(io.StringIO):
    def __init__(self, limit):
        super().__init__()
        self.limit = limit
        self.size = 0

    def write(self, value):
        self.size += len(value.encode("utf-8"))
        if self.size > self.limit:
            raise RuntimeError("Trusted test output limit exceeded")
        return super().write(value)


def main():
    config = json.loads(Path("/runner/manifest.json").read_text())
    os.chdir("/suite")
    sys.path.insert(0, "/suite")  # Only trusted files; target source is in a different container.
    client = Client()
    deadline = time.monotonic() + 8
    while True:
        try:
            response = client.get("/health")
            if response.status_code == 200:
                break
        except (OSError, ValueError):
            pass
        if time.monotonic() >= deadline:
            raise RuntimeError("LedgerLite failed to become ready")
        time.sleep(0.05)
    response = client.get("/invoices/inv-2047", {"X-Synthetic-Identity": "alice"})
    probe = {
        "request": {"path": "/invoices/inv-2047", "synthetic_identity": "alice"},
        "status_code": response.status_code,
        "body": response.json(),
        "unauthorized_access_reproduced": (
            response.status_code == 200 and response.json() == EXPECTED_LEAK
        ),
    }
    recorder = Recorder()
    stdout = LimitedText(config["output_bytes"] // 4)
    stderr = LimitedText(config["output_bytes"] // 4)
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = pytest.main(
            [
                "-c",
                "/dev/null",
                "--rootdir=/suite",
                "--noconftest",
                "--import-mode=importlib",
                "-p",
                "no:cacheprovider",
                "--capture=sys",
                "-q",
                "--",
                *config["required_test_ids"],
            ],
            plugins=[recorder],
        )
    print(
        json.dumps(
            {
                "schema_version": 1,
                "execution_id": config["execution_id"],
                "source_sha256": config["source_sha256"],
                "manifest_sha256": config["manifest_sha256"],
                "collected": recorder.collected,
                "results": recorder.results,
                "probe": probe,
                "pytest_exit_code": int(code),
                "pytest_stdout": stdout.getvalue(),
                "pytest_stderr": stderr.getvalue(),
            }
        )
    )
    return int(code)


if __name__ == "__main__":
    raise SystemExit(main())
