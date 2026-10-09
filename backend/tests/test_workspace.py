"""Admission/receipt regression tests use explicit doubles, never live AI or target execution."""

import json
import threading

import pytest
from pydantic import ValidationError

from backend.api.schemas import CreateRunRequest
from backend.providers.akash_compute import Budget, Compute, sdl


def test_budget_survives_restart_and_blocks_overlap(tmp_path):
    path = tmp_path / "budget.sqlite3"
    Budget(path).reserve("one", "akash_compute", 2)
    again = Budget(path)
    with pytest.raises(ValueError):
        again.reserve("two", "akash_compute", 2)
    again.update("one", "closed")
    for i in range(9):
        again.reserve(str(i), "akash_compute", 2)
        again.update(str(i), "closed")
    assert Budget(path).summary()["remaining_usd"] == 0
    with pytest.raises(ValueError):
        again.reserve("over", "akashml", 0.1)


def test_sdl_keeps_candidates_private_and_pins_images():
    images = {n: "ttl.sh/test@sha256:" + "a" * 64 for n in ("baseline", "patched", "tester")}
    manifest = json.loads(sdl(images))
    for name in ("baseline", "patched"):
        assert manifest["services"][name]["expose"][0]["to"] == [{"service": "tester"}]
        assert "env" not in manifest["services"][name]
    assert manifest["services"]["tester"]["expose"][0]["to"] == [{"global": True}]
    with pytest.raises(ValueError):
        sdl({**images, "baseline": "python:latest"})


def test_recovery_closes_only_journal_owned_ids(tmp_path):
    budget = Budget(tmp_path / "budget.sqlite3")
    budget.reserve("one", "akash_compute", 2)
    budget.update("one", "running", "12345")
    compute = Compute(budget, key="fixture-key")
    closed = []
    compute.close = lambda dseq: closed.append(dseq)
    compute.reconcile()
    assert closed == ["12345"] and budget.pending() == []


def test_classic_request_defaults_and_cloud_admission():
    assert CreateRunRequest(target="LedgerLite").execution_mode == "local"
    with pytest.raises(ValidationError):
        CreateRunRequest(target="LedgerLite", execution_mode="local_akash")
    assert CreateRunRequest(target="LedgerLite Workspace", execution_mode="local_akash")


@pytest.mark.parametrize("failure", ["logs", "forged", "cleanup", "cancelled"])
def test_remote_failures_always_close_and_never_return_verified(tmp_path, failure):
    budget = Budget(tmp_path / "budget.sqlite3")
    compute = Compute(budget, key="fixture-key")
    images = {n: "ttl.sh/test@sha256:" + "a" * 64 for n in ("baseline", "patched", "tester")}
    cancelled = threading.Event()
    closed = []

    def api(method, path, data=None):
        if path == "/v1/deployments" and method == "POST":
            if failure == "cancelled":
                cancelled.set()
            return {"dseq": "12345"}
        if path.startswith("/v1/bids?"):
            return [
                {
                    "bid": {
                        "state": "open",
                        "price": {"denom": "uact", "amount": "8"},
                        "id": {"dseq": "12345", "gseq": 1, "oseq": 1, "provider": "fixture"},
                    }
                }
            ]
        if path == "/v1/leases":
            return {}
        return {"leases": [{"status": {"services": {n: {"available": 1} for n in images}}}]}

    def close(dseq):
        closed.append(dseq)
        if failure == "cleanup":
            raise RuntimeError("Cleanup unconfirmed")
        return {}

    def logs(_):
        if failure == "logs":
            raise TimeoutError("Provider timeout")
        return "PROOFLOOP_RECEIPT={}"  # Untrusted, missing job identity and inventory.

    compute.api, compute.close, compute.logs = api, close, logs
    with pytest.raises((RuntimeError, TimeoutError, ValueError)):
        compute.run(images, {"job_id": "fixture", "nonce": "fixture"}, cancelled=cancelled)
    assert closed == ["12345"]
    assert bool(budget.pending()) == (failure == "cleanup")
