"""Independent deterministic acceptance of a frozen LedgerLite patch attempt."""

from __future__ import annotations

import time
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path

from backend.engine.patcher import (
    PatchRejected,
    PreparedPatch,
    SourceSnapshot,
    apply_patch,
    apply_unified_diff,
    digest,
)
from sandbox.ledgerlite import PATCH_ALLOWLIST
from sandbox.models import ExecutionEvidence, ExecutionLimits, FrozenTestManifest
from sandbox.runner import DockerRunner


@dataclass(frozen=True)
class VerificationResult:
    verdict: str  # verified, rejected, inconclusive, error
    reason: str
    original_sha256: str
    patched_sha256: str | None
    patch_sha256: str | None
    manifest_sha256: str
    policy_sha256: str
    unified_diff: str = ""
    baseline: ExecutionEvidence | None = None
    patched: ExecutionEvidence | None = None
    source: str = "execution"
    scope: str = "Frozen LedgerLite suite only; synthetic data; not universal security assurance"

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def evidence_sha256(self) -> str:
        return digest(self.to_dict())


def _complete(evidence: ExecutionEvidence, manifest: FrozenTestManifest) -> bool:
    ids = [test.test_id for test in evidence.tests]
    if (
        evidence.status != "completed"
        or evidence.manifest_sha256 != manifest.sha256
        or evidence.source != "execution"
        or evidence.process is None
        or evidence.process.status != "completed"
        or evidence.process.truncated
        or evidence.process.exit_code not in (0, 1)
        or sorted(ids) != sorted(manifest.required_test_ids)
        or any(test.outcome not in {"passed", "failed"} for test in evidence.tests)
    ):
        return False
    for test in evidence.tests:
        if (
            [p.get("phase") for p in test.phases] != ["setup", "call", "teardown"]
            or test.phases[0].get("outcome") != "passed"
            or test.phases[2].get("outcome") != "passed"
            or test.phases[1].get("outcome") != test.outcome
            or any(p.get("wasxfail") is not None for p in test.phases)
        ):
            return False
    categories = {check.test_id: check.category for check in manifest.checks}
    if any(test.category != categories[test.test_id] for test in evidence.tests):
        return False
    return evidence.process.exit_code == int(any(t.outcome == "failed" for t in evidence.tests))


def baseline_reproduced(evidence: ExecutionEvidence, manifest: FrozenTestManifest) -> bool:
    """Require the exact expected failures AND an independent exact-response HTTP probe."""
    if not _complete(evidence, manifest) or evidence.phase != "baseline":
        return False
    failures = {test.test_id for test in evidence.tests if test.outcome == "failed"}
    probe = evidence.probe or {}
    return (
        failures == set(manifest.baseline_expected_failures)
        and probe.get("unauthorized_access_reproduced") is True
        and probe.get("status_code") == 200
        and probe.get("request") == {"path": "/invoices/inv-2047", "synthetic_identity": "alice"}
        and probe.get("body")
        == {
            "id": "inv-2047",
            "owner_id": "bob",
            "amount_cents": 48750,
            "currency": "USD",
            "status": "paid",
            "source": "fixture",
        }
    )


def evaluate_patch(
    patch: PreparedPatch,
    manifest: FrozenTestManifest,
    baseline: ExecutionEvidence,
    patched: ExecutionEvidence,
) -> VerificationResult:
    """Trusted internal reducer; never accept these evidence objects from a model/client."""
    result = dict(
        original_sha256=patch.original.sha256,
        patched_sha256=patch.patched.sha256,
        patch_sha256=patch.sha256,
        manifest_sha256=manifest.sha256,
        policy_sha256=manifest.policy_sha256,
        unified_diff=patch.unified_diff,
        baseline=baseline,
        patched=patched,
    )
    for evidence, source_hash, phase in (
        (baseline, patch.original.sha256, "baseline"),
        (patched, patch.patched.sha256, "patched"),
    ):
        if (
            evidence.source_sha256 != source_hash
            or evidence.manifest_sha256 != manifest.sha256
            or evidence.phase != phase
            or not evidence.runner_sha256
            or not evidence.image_id
            or not evidence.execution_id
        ):
            return VerificationResult("inconclusive", "Evidence identity mismatch", **result)
        if evidence.status in {"infrastructure_error", "runner_error"}:
            return VerificationResult("error", evidence.reason or "Runner failed", **result)
    if (
        baseline.runner_sha256 != patched.runner_sha256
        or baseline.image_id != patched.image_id
        or baseline.execution_id == patched.execution_id
    ):
        return VerificationResult(
            "inconclusive", "Execution environment or identity mismatch", **result
        )
    if not baseline_reproduced(baseline, manifest):
        return VerificationResult(
            "inconclusive", "Baseline vulnerability not reproducibly established", **result
        )
    if not _complete(patched, manifest):
        return VerificationResult("inconclusive", "Required test evidence incomplete", **result)
    if any(test.outcome == "failed" for test in patched.tests):
        return VerificationResult("rejected", "Required patched checks failed", **result)
    probe = patched.probe or {}
    if (
        probe.get("unauthorized_access_reproduced") is not False
        or probe.get("status_code") != 403
        or probe.get("body") != {"detail": "Invoice access denied"}
    ):
        return VerificationResult("inconclusive", "Patched probe missing or inconsistent", **result)
    return VerificationResult(
        "verified", "All frozen required checks completed and passed", **result
    )


class Verifier:
    """Orchestrator entry point. Policy/test/source inputs must be server-approved."""

    def __init__(self, runner: DockerRunner):
        self.runner = runner

    def verify_patch(
        self,
        original: SourceSnapshot,
        replacements: Mapping[str, str] | str,
        trusted_suite: Path,
        manifest: FrozenTestManifest,
        limits: ExecutionLimits | None = None,
    ) -> VerificationResult:
        limits = limits or ExecutionLimits()
        deadline = time.monotonic() + limits.total_attempt_seconds
        common = dict(
            original_sha256=original.sha256,
            patched_sha256=None,
            patch_sha256=None,
            manifest_sha256=manifest.sha256,
            policy_sha256=manifest.policy_sha256,
        )
        try:
            if isinstance(replacements, str):
                patch = apply_unified_diff(original, replacements, allowed_files=PATCH_ALLOWLIST)
            else:
                if not set(replacements) <= set(PATCH_ALLOWLIST):
                    raise PatchRejected("Patch modifies protected LedgerLite support files")
                patch = apply_patch(original, replacements)
        except (PatchRejected, UnicodeError) as exc:
            return VerificationResult("rejected", str(exc), **common)
        common.update(
            patched_sha256=patch.patched.sha256,
            patch_sha256=patch.sha256,
            unified_diff=patch.unified_diff,
        )
        baseline = self.runner.run(
            original, trusted_suite, manifest, limits, phase="baseline", deadline=deadline
        )
        if not baseline_reproduced(baseline, manifest):
            verdict = (
                "error"
                if baseline.status in {"infrastructure_error", "runner_error"}
                else "inconclusive"
            )
            return VerificationResult(
                verdict,
                baseline.reason or "Baseline vulnerability not reproducibly established",
                baseline=baseline,
                **common,
            )
        if time.monotonic() >= deadline:
            return VerificationResult(
                "inconclusive", "Total attempt budget exceeded", baseline=baseline, **common
            )
        patched = self.runner.run(
            patch.patched, trusted_suite, manifest, limits, phase="patched", deadline=deadline
        )
        return evaluate_patch(patch, manifest, baseline, patched)
