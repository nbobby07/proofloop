"""Composition unit tests: all provider/runner doubles below are synthetic, never live results."""

import asyncio
import base64
import hashlib
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest

from backend.api import composition
from backend.api.schemas import (
    ChallengeRequest,
    CreateRunRequest,
    Finding,
    PatchProposal,
    RunStatus,
)
from backend.engine.orchestrator import ExecutionFailure, Orchestrator
from backend.engine.patcher import apply_patch
from backend.providers.contracts import ScanResult
from backend.providers.semgrep_client import ScanFinding, ScanReport
from backend.storage.evidence import EvidenceStore
from backend.storage.runs import RunStore
from sandbox.ledgerlite import SOURCE_FILES
from sandbox.tests.helpers import evidence as synthetic_evidence

ROOT = Path(__file__).resolve().parents[2]
IMAGE = "sha256:" + "1" * 64


@pytest.fixture
def engine(tmp_path):
    return composition.LedgerLiteEngine(
        repository=ROOT,
        store=RunStore(tmp_path / "runs"),
        image_id=IMAGE,
        manifest_sha256=hashlib.sha256(
            (ROOT / "verifier_tests/manifest.json").read_bytes()
        ).hexdigest(),
    )


class UnitScanner:
    """Synthetic scan transport: exercises coverage checks without a scanner subprocess."""

    def __init__(self, ruleset_hash, *, complete=True, finding=True):
        self.ruleset_hash = ruleset_hash
        self.complete = complete
        self.finding = finding

    def scan_with_details(self, workspace):
        # Scanner sees curated bytes only, never reference_secure.py, keys, or trusted tests.
        paths = {
            str(path.relative_to(workspace)) for path in workspace.rglob("*") if path.is_file()
        }
        assert paths == set(SOURCE_FILES)
        finding = Finding(id="unit_finding", title="Unit-test BOLA finding", severity="high")
        return ScanReport(
            result=ScanResult(
                findings=[finding] if self.finding else [],
                scanner_version="unit-test",
                ruleset_hash=self.ruleset_hash,
                complete=self.complete,
            ),
            locations=(
                ScanFinding(
                    finding.id,
                    "proofloop.ledgerlite.invoice-missing-ownership",
                    "demo_target/ledgerlite/app.py",
                    1,
                    1,
                ),
            )
            if self.finding
            else (),
            scanned_paths=tuple(sorted(SOURCE_FILES)),
            exit_code=0,
            diagnostics=() if self.complete else ("unit_incomplete",),
        )


class UnitRunner:
    """Synthetic evidence input to the real deterministic reducer; does not execute tests."""

    def __init__(self, engine, *, skip=False):
        self.engine = engine
        self.calls = []
        self.skip = skip

    def run(self, snapshot, suite, manifest, limits, *, phase, deadline):
        self.calls.append(phase)
        assert (suite / "verifier_tests/test_ledgerlite.py").is_file()
        result = synthetic_evidence(
            snapshot,
            manifest,
            phase,
            failed=manifest.baseline_expected_failures if phase == "baseline" else (),
        )
        result = replace(
            result,
            runner_sha256=self.engine.pins["runner_sha256"],
            image_id=IMAGE,
            execution_id=uuid4().hex,
        )
        if self.skip and phase == "patched":
            result = replace(
                result, tests=(replace(result.tests[0], outcome="skipped"), *result.tests[1:])
            )
        return result


def install_unit_dependencies(engine, monkeypatch):
    engine.scanner = UnitScanner(engine.pins["ruleset_hash"])
    runner = UnitRunner(engine)
    engine.runner = runner
    # This test-authored patch exercises the trusted parser, never supplies production fixes.
    app_name = "demo_target/ledgerlite/app.py"
    app_text = dict(engine.original.files)[app_name].decode()
    diff = apply_patch(
        engine.original, {app_name: app_text + "\n# unit-test proposal\n"}
    ).unified_diff

    class UnitDefender:
        def __init__(self, *, attempt, **kwargs):
            self.attempt = attempt

        def generate_patch(self, source, finding, feedback):
            assert set(source.files) == set(SOURCE_FILES)
            assert "reference_secure.py" not in " ".join(source.files)
            return PatchProposal(attempt=self.attempt, diff=diff)

    monkeypatch.setattr(composition, "OpenAIDefender", UnitDefender)
    return runner


def test_real_composition_with_unit_transports_persists_bound_evidence(engine, monkeypatch):
    async def scenario():
        runner = install_unit_dependencies(engine, monkeypatch)
        service = Orchestrator(engine.store, engine)
        response = service.create(CreateRunRequest(target="LedgerLite"))
        await asyncio.gather(*list(service.tasks.values()))
        record = engine.store.get(response.run_id)
        assert record.run.status == RunStatus.VERIFIED
        assert runner.calls == ["baseline", "patched", "baseline", "patched"]
        assert record.run.verification.security_total == 6
        assert (
            sum(
                getattr(record.run.verification, f"{s}_total")
                for s in ("security", "functional", "adversarial")
            )
            == 44
        )
        for reference in record.evidence:
            assert engine.artifacts.read(reference)
        # Simulate process-local context loss; rebuild only from matching pins and saved patch.
        engine.contexts.clear()
        service.rechallenge(response.run_id, ChallengeRequest(max_challenges=1))
        assert engine.store.get(response.run_id).run.verification is None
        await asyncio.gather(*list(service.tasks.values()))
        assert engine.store.get(response.run_id).run.status == RunStatus.VERIFIED
        assert runner.calls[-2:] == ["baseline", "patched"]
        assert len(runner.calls) == 6

    asyncio.run(scenario())


@pytest.mark.parametrize("mode", ["incomplete_scan", "clean_scan", "skipped", "runner_failure"])
def test_composition_failures_never_verify(engine, monkeypatch, mode):
    async def scenario():
        runner = install_unit_dependencies(engine, monkeypatch)
        if mode == "incomplete_scan":
            engine.scanner.complete = False
        if mode == "clean_scan":
            engine.scanner.finding = False
        if mode == "skipped":
            runner.skip = True
        if mode == "runner_failure":
            # Actual DockerRunner missing executable path; no target or network execution.
            engine.runner = composition.DockerRunner(
                IMAGE, docker_binary="/nonexistent/unit-docker"
            )
        service = Orchestrator(engine.store, engine)
        response = service.create(CreateRunRequest(target="LedgerLite"))
        await asyncio.gather(*list(service.tasks.values()))
        record = engine.store.get(response.run_id)
        expected = RunStatus.ERROR if mode == "runner_failure" else RunStatus.INCONCLUSIVE
        assert record.run.status == expected
        assert record.evidence
        if mode in {"incomplete_scan", "clean_scan"}:
            assert runner.calls == []

    asyncio.run(scenario())


def test_unknown_policy_and_changed_context_fail_closed(engine, monkeypatch):
    async def scenario():
        runner = install_unit_dependencies(engine, monkeypatch)
        service = Orchestrator(engine.store, engine)
        response = service.create(CreateRunRequest(target="LedgerLite"))
        await asyncio.gather(*list(service.tasks.values()))
        with pytest.raises(ExecutionFailure, match="unapproved_challenge_policy"):
            await engine.challenge(response.run_id, ChallengeRequest(policy_ids=["unapproved"]))
        assert len(runner.calls) == 4
        engine.contexts.clear()
        engine.pins["image_id"] = "sha256:" + "2" * 64
        with pytest.raises(ExecutionFailure, match="execution_context_changed"):
            await engine.challenge(response.run_id, ChallengeRequest())
        assert len(runner.calls) == 4

    asyncio.run(scenario())


def test_source_and_manifest_hash_enforcement(engine, tmp_path):
    assert {name for name, _ in engine.original.files} == set(SOURCE_FILES)
    with pytest.raises(ValueError, match="Pinned input changed"):
        composition.LedgerLiteEngine(
            repository=ROOT, store=RunStore(tmp_path), image_id=IMAGE, manifest_sha256="0" * 64
        )


def test_evidence_integrity_and_redaction(engine):
    engine.artifacts = EvidenceStore(engine.store.root / "artifacts", secrets=("unit-secret",))
    reference = engine._save(
        {"stderr": "unit-secret", "stdout_base64": base64.b64encode(b"unit-secret").decode()},
        "Unit evidence",
    )
    data = engine.artifacts.read(reference)
    assert "unit-secret" not in str(data)
    assert base64.b64decode(data["stdout_base64"]) == b"[REDACTED]"
    (engine.artifacts.root / f"{reference.artifact_id}.json").write_text("{}")
    with pytest.raises(ValueError, match="Evidence integrity"):
        engine.artifacts.read(reference)


def test_configuration_absent_or_invalid_is_fail_closed(tmp_path, monkeypatch):
    monkeypatch.delenv("PROOFLOOP_EXECUTION_ENABLED", raising=False)
    assert composition.configured_engine(RunStore(tmp_path)) is None
    monkeypatch.setenv("PROOFLOOP_EXECUTION_ENABLED", "1")
    monkeypatch.setenv("PROOFLOOP_VERIFIER_IMAGE", "unit-secret-invalid")
    assert isinstance(
        composition.configured_engine(RunStore(tmp_path)), composition.UnavailableEngine
    )
