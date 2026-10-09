"""Load the authorized disposable target; expected values stay in trusted tests."""

import importlib.util
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def client():
    root = Path(__file__).resolve().parents[1]
    path = Path(os.environ.get("LEDGERLITE_APP_FILE", root / "demo_target/ledgerlite/app.py"))
    spec = importlib.util.spec_from_file_location("ledgerlite_candidate", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load authorized LedgerLite target")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with TestClient(module.create_app()) as test_client:
        yield test_client
