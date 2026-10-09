"""Opt-in real isolated execution. No Docker means an explicit skip, never a fake pass."""

import os

import pytest

from backend.engine.verifier import Verifier
from sandbox.models import ExecutionLimits
from sandbox.runner import DockerRunner
from sandbox.tests.helpers import APP, GOOD_APP, inputs

IMAGE = os.environ.get("PROOFLOOP_TEST_IMAGE")
pytestmark = pytest.mark.skipif(
    not IMAGE, reason="Set PROOFLOOP_TEST_IMAGE to a reviewed local image ID"
)


def test_docker_valid_and_invalid_patch(tmp_path):
    original, suite, manifest = inputs(tmp_path)
    verifier = Verifier(DockerRunner(IMAGE, workspace_parent=tmp_path / "runs"))
    valid = verifier.verify_patch(
        original, {"demo_target/ledgerlite/app.py": GOOD_APP}, suite, manifest
    )
    assert valid.verdict == "verified", valid.to_dict()
    invalid = verifier.verify_patch(
        original, {"demo_target/ledgerlite/app.py": APP + "\n# no fix\n"}, suite, manifest
    )
    assert invalid.verdict == "rejected", invalid.to_dict()
    assert not list((tmp_path / "runs").iterdir())


def test_docker_target_cannot_mutate_trusted_files_or_reach_external_network(tmp_path):
    original, suite, manifest = inputs(tmp_path)
    # These trusted integration assertions execute INSIDE the untrusted target container.
    checks = """import os, socket
assert os.getuid() != 0
assert not os.path.exists('/suite')
assert not os.path.exists('/var/run/docker.sock')
assert 'PROOFLOOP_HOST_CANARY' not in os.environ
try:
    open('/source/demo_target/ledgerlite/app.py', 'w')
except OSError:
    pass
else:
    raise AssertionError('source is writable')
try:
    open('/cannot-write-root', 'w')
except OSError:
    pass
else:
    raise AssertionError('root is writable')
with socket.socket() as conn:
    conn.settimeout(.2)
    assert conn.connect_ex(('1.1.1.1', 443)) != 0
"""
    verifier = Verifier(DockerRunner(IMAGE, workspace_parent=tmp_path / "runs"))
    result = verifier.verify_patch(
        original, {"demo_target/ledgerlite/app.py": checks + GOOD_APP}, suite, manifest
    )
    assert result.verdict == "verified", result.to_dict()


def test_docker_hanging_target_is_inconclusive(tmp_path):
    original, suite, manifest = inputs(tmp_path)
    verifier = Verifier(DockerRunner(IMAGE, workspace_parent=tmp_path / "runs"))
    result = verifier.verify_patch(
        original,
        {"demo_target/ledgerlite/app.py": "while True: pass\n"},
        suite,
        manifest,
        ExecutionLimits(timeout_seconds=10),
    )
    assert result.verdict in {"inconclusive", "error"}
    assert not list((tmp_path / "runs").iterdir())
