"""Synthetic unit/integration inputs; not A1's LedgerLite fixture or real execution evidence."""

import hashlib
from dataclasses import replace

from backend.engine.patcher import SourceSnapshot, apply_patch
from sandbox.ledgerlite import SOURCE_FILES
from sandbox.models import (
    ExecutionEvidence,
    FrozenTestManifest,
    ProcessEvidence,
    TestCheck,
    TestEvidence,
)

IMAGE = "sha256:" + "1" * 64
APP = """from fastapi import FastAPI, Header, HTTPException
app = FastAPI()
@app.get('/health')
def health():
    return {'status': 'ok'}
@app.get('/invoices/{invoice_id}')
def invoice(invoice_id: str, x_synthetic_identity: str | None = Header(default=None)):
    if x_synthetic_identity not in ('alice', 'bob'):
        raise HTTPException(status_code=401, detail='Synthetic identity required')
    if invoice_id != 'inv-2047':
        raise HTTPException(status_code=404, detail='Invoice not found')
    # CHECK_OWNER
    return {'id':'inv-2047', 'owner_id':'bob', 'amount_cents':48750,
            'currency':'USD', 'status':'paid', 'source':'fixture'}
"""
GOOD_APP = APP.replace(
    "    # CHECK_OWNER",
    "    if x_synthetic_identity != 'bob':\n"
    "        raise HTTPException(status_code=403, detail='Invoice access denied')",
)
TESTS = b"""def test_denied(client):
    response = client.get('/invoices/inv-2047', headers={'X-Synthetic-Identity':'alice'})
    assert response.status_code == 403
    assert response.json() == {'detail': 'Invoice access denied'}
def test_owner(client):
    response = client.get('/invoices/inv-2047', headers={'X-Synthetic-Identity':'bob'})
    assert response.status_code == 200
def test_bad_identity(client):
    response = client.get('/invoices/inv-2047', headers={'X-Synthetic-Identity':'mallory'})
    assert response.status_code == 401
"""
IDS = tuple(
    "verifier_tests/test_checks.py::" + name
    for name in ("test_denied", "test_owner", "test_bad_identity")
)


def inputs(tmp_path):
    original = SourceSnapshot(
        tuple(
            sorted(
                (name, APP.encode() if name.endswith("/app.py") else b"") for name in SOURCE_FILES
            )
        )
    )
    suite = tmp_path / "trusted"
    (suite / "verifier_tests").mkdir(parents=True)
    (suite / "verifier_tests/test_checks.py").write_bytes(TESTS)
    manifest = FrozenTestManifest(
        "LedgerLite",
        "unit-v1",
        tuple(
            TestCheck(test_id, category)
            for test_id, category in zip(
                IDS, ("security", "functional", "adversarial"), strict=True
            )
        ),
        (("verifier_tests/test_checks.py", hashlib.sha256(TESTS).hexdigest()),),
        (IDS[0],),
        "2" * 64,
    )
    return original, suite, manifest


def phases(outcome="passed"):
    return tuple(
        {
            "phase": phase,
            "outcome": outcome if phase == "call" else "passed",
            "duration_seconds": 0.01,
            "stdout": "",
            "stderr": "",
            "wasxfail": None,
        }
        for phase in ("setup", "call", "teardown")
    )


def evidence(snapshot, manifest, phase, *, failed=()):
    """Simulated reducer input; never used to claim container execution."""
    probe = {
        "request": {"path": "/invoices/inv-2047", "synthetic_identity": "alice"},
        "unauthorized_access_reproduced": phase == "baseline",
        "status_code": 200 if phase == "baseline" else 403,
        "body": (
            {
                "id": "inv-2047",
                "owner_id": "bob",
                "amount_cents": 48750,
                "currency": "USD",
                "status": "paid",
                "source": "fixture",
            }
            if phase == "baseline"
            else {"detail": "Invoice access denied"}
        ),
    }
    return ExecutionEvidence(
        "completed",
        phase,
        snapshot.sha256,
        manifest.sha256,
        "3" * 64,
        IMAGE,
        phase,
        tests=tuple(
            TestEvidence(
                check.test_id,
                check.category,
                "failed" if check.test_id in failed else "passed",
                phases("failed" if check.test_id in failed else "passed"),
            )
            for check in manifest.checks
        ),
        probe=probe,
        process=ProcessEvidence("completed", int(bool(failed)), "", "", 0.01),
    )


def good_evidence(tmp_path):
    original, suite, manifest = inputs(tmp_path)
    patch = apply_patch(original, {"demo_target/ledgerlite/app.py": GOOD_APP})
    baseline = evidence(original, manifest, "baseline", failed=manifest.baseline_expected_failures)
    patched = evidence(patch.patched, manifest, "patched")
    return patch, suite, manifest, baseline, patched


def payload(result, manifest):
    return {
        "schema_version": 1,
        "execution_id": result.execution_id,
        "source_sha256": result.source_sha256,
        "manifest_sha256": result.manifest_sha256,
        "pytest_exit_code": result.process.exit_code,
        "collected": list(manifest.required_test_ids),
        "results": {t.test_id: list(t.phases) for t in result.tests},
        "probe": result.probe,
        "pytest_stdout": "actual captured stdout",
        "pytest_stderr": "actual captured stderr",
    }


def incomplete_test(test, outcome):
    return replace(test, outcome=outcome, phases=phases(outcome))
