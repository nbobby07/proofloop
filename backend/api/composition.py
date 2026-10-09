"""Real LedgerLite composition: providers propose; the isolated verifier decides.

No reference patch, host execution, mock provider, or inferred passing result is used.
The reviewed local policy and frozen adversarial suite are the core challenge mode.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import re
import stat
import tempfile
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from backend.api.schemas import BaselineResult, ChallengeRequest, RunStatus, VerificationSummary
from backend.engine.orchestrator import (
    BaselineReceipt,
    DiscoveryReceipt,
    ExecutionFailure,
    StageResult,
)
from backend.engine.patcher import (
    SourceSnapshot,
    apply_unified_diff,
    checked_root,
    digest,
    disposable_workspace,
    materialize,
    remove_readonly,
)
from backend.engine.verifier import baseline_reproduced, evaluate_patch
from backend.providers.contracts import ChallengeSpec, PolicySource, SecurityPolicy
from backend.providers.contracts import SourceSnapshot as ProviderSnapshot
from backend.providers.errors import ProviderError
from backend.providers.openai_client import OpenAIDefender
from backend.providers.policy_validation import validate_policy
from backend.providers.semgrep_client import SemgrepScanner
from backend.storage.evidence import EvidenceStore
from backend.storage.runs import RunStore
from sandbox.ledgerlite import PATCH_ALLOWLIST, SOURCE_FILES, manifest_from_ledgerlite
from sandbox.models import ExecutionLimits
from sandbox.runner import DockerRunner, freeze_suite, runner_hash

POLICY_ID = "ledgerlite-object-authorization-v1"
POLICY_TEXT = (
    "LedgerLite synthetic identities: owners may read their invoices; administrator may read "
    "all invoices; authenticated nonowners must receive 403 without invoice data. Invalid "
    "identities receive 401, missing invoices receive 404, and health remains available. "
    "All frozen security, functional, and adversarial tests must execute. Only app.py is mutable."
)
CONTEXT_DESCRIPTION = "Pinned LedgerLite execution context."

# ProviderError is internal, but still never concatenate an arbitrary upstream code.
DEFENDER_ERROR_CODES = {
    code: f"defender_{code}"
    for code in (
        "missing_credentials",
        "missing_model",
        "invalid_input",
        "invalid_configuration",
        "request_too_large",
        "response_too_large",
        "timeout",
        "network_error",
        "authentication_failed",
        "access_denied",
        "credits_required",
        "rate_limited",
        "invalid_json",
        "invalid_response",
        "incomplete_response",
        "unexpected_output",
        "refused",
        "invalid_attempt",
    )
}
DEFENDER_ERROR_CODES["unsafe_patch"] = "defender_invalid_patch"
DEFENDER_ERROR_CODES.update(
    {f"http_{status}": f"defender_http_{status}" for status in range(400, 600)}
)


def defender_failure_code(code: str) -> str:
    return DEFENDER_ERROR_CODES.get(code, "defender_provider_failure")


def local_policy() -> SecurityPolicy:
    return validate_policy(
        SecurityPolicy(
            policy_ids=[POLICY_ID],
            sources=[
                PolicySource(
                    policy_id=POLICY_ID,
                    source_id="reviewed-local-ledgerlite-v1",
                    revision="1",
                    text=POLICY_TEXT,
                    authoritative=True,
                )
            ],
        ),
        "local",
    )


def pinned_read(root: Path, name: str, expected: str) -> bytes:
    """Curated reads only: no whole-repository copy or reference-source access."""
    path = root / name
    checked_root(path.parent)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError("Unsafe pinned input")
        data = stream.read(256 * 1024 + 1)
    if len(data) > 256 * 1024 or hashlib.sha256(data).hexdigest() != expected:
        raise ValueError("Pinned input changed")
    return data


@dataclass
class Context:
    pins: dict
    baseline: object | None = None
    patch: object | None = None
    finding: object | None = None
    feedback: tuple[str, ...] = ()


class LedgerLiteEngine:
    def __init__(
        self,
        *,
        repository: Path,
        store: RunStore,
        image_id: str,
        manifest_sha256: str,
        docker_host: str = "unix:///var/run/docker.sock",
        semgrep_executable: str = "semgrep",
    ):
        self.repository = checked_root(repository)
        self.store = store
        manifest_bytes = pinned_read(repository, "verifier_tests/manifest.json", manifest_sha256)
        document = json.loads(manifest_bytes)
        self.policy = local_policy()
        self.manifest = manifest_from_ledgerlite(
            document, policy_sha256=digest(self.policy.model_dump(mode="json"))
        )
        self.original = SourceSnapshot(
            tuple(
                sorted(
                    (name, pinned_read(repository, name, document["original_file_sha256"][name]))
                    for name in SOURCE_FILES
                )
            )
        )
        self.suite = freeze_suite(repository, self.manifest)
        self.workspaces = repository / "sandbox" / "workspaces"
        self.workspaces.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.scanner = SemgrepScanner(
            approved_roots=[self.workspaces], timeout=30, executable=semgrep_executable
        )
        self.legacy_scanner = SemgrepScanner(
            approved_roots=[self.workspaces],
            timeout=30,
            executable=semgrep_executable,
            rules=[repository / "backend/providers/rules/python-security-classic-v1.yml"],
        )
        self.runner = DockerRunner(
            image_id, workspace_parent=self.workspaces, docker_host=docker_host
        )
        self.limits = ExecutionLimits(timeout_seconds=25, total_attempt_seconds=45)
        self.artifacts = EvidenceStore(
            store.root / "artifacts",
            secrets=tuple(
                os.getenv(key, "") for key in ("OPENAI_API_KEY", "AKASH_API_KEY", "SENSO_API_KEY")
            ),
        )
        self.pins = {
            "source_sha256": self.original.sha256,
            "manifest_sha256": self.manifest.sha256,
            "manifest_file_sha256": manifest_sha256,
            "policy_sha256": self.manifest.policy_sha256,
            "ruleset_hash": self.scanner.ruleset_hash,
            "runner_sha256": runner_hash(),
            "image_id": image_id,
            "challenge_mode": "frozen_deterministic_suite",
            "policy": self.policy.model_dump(mode="json"),
        }
        self.contexts: dict[str, Context] = {}
        # Cancelled asyncio calls cannot create unbounded live synchronous workers.
        self.slots = threading.BoundedSemaphore(4)

    def release(self, run_id: str) -> None:
        self.contexts.pop(run_id, None)

    async def _offload(self, operation, *args):
        def bounded():
            if not self.slots.acquire(blocking=False):
                raise ExecutionFailure("engine_capacity_reached")
            try:
                return operation(*args)
            finally:
                self.slots.release()

        return await asyncio.to_thread(bounded)

    def _save(self, payload, description):
        # Base64 process output is redacted through its decoded representation as well.
        def redact_encoded(value):
            if isinstance(value, dict):
                result = {}
                for key, item in value.items():
                    if key.endswith("_base64") and isinstance(item, str) and item:
                        raw = base64.b64decode(item)
                        for secret in self.artifacts.secrets:
                            raw = raw.replace(secret.encode(), b"[REDACTED]")
                        item = base64.b64encode(raw).decode()
                    result[key] = redact_encoded(item)
                return result
            if isinstance(value, (list, tuple)):
                return [redact_encoded(item) for item in value]
            return value

        return self.artifacts.save(redact_encoded(payload), description)

    def _context(self, run_id):
        if run_id not in self.contexts:
            record = self.store.get(run_id)
            reference = next(
                (ref for ref in record.evidence if ref.description == CONTEXT_DESCRIPTION), None
            )
            stored = self.artifacts.read(reference) if reference else None
            if stored is None or (
                {k: v for k, v in stored.items() if k != "ruleset_hash"}
                != {k: v for k, v in self.pins.items() if k != "ruleset_hash"}
                or stored.get("ruleset_hash")
                not in {self.scanner.ruleset_hash, self.legacy_scanner.ruleset_hash}
            ):
                raise ExecutionFailure("execution_context_changed")
            ctx = Context(dict(stored))
            if record.run.patch:
                ctx.patch = apply_unified_diff(
                    self.original, record.run.patch.diff, allowed_files=PATCH_ALLOWLIST
                )
            self.contexts[run_id] = ctx
        return self.contexts[run_id]

    def _scan(self, snapshot, ctx=None):
        expected = ctx.pins["ruleset_hash"] if ctx else self.pins["ruleset_hash"]
        scanner = (
            self.legacy_scanner if expected == self.legacy_scanner.ruleset_hash else self.scanner
        )
        with disposable_workspace(snapshot, self.workspaces) as workspace:
            report = scanner.scan_with_details(workspace)
        payload = asdict(report)
        payload["result"] = report.result.model_dump(mode="json")
        payload["source_sha256"] = snapshot.sha256
        reference = self._save(payload, "Complete scanner diagnostics and source coverage.")
        if (
            not report.result.complete
            or report.diagnostics
            or report.skipped_paths
            or set(report.scanned_paths) != set(SOURCE_FILES)
            or report.result.ruleset_hash != expected
        ):
            raise ExecutionFailure("scan_incomplete", RunStatus.INCONCLUSIVE, [reference])
        return report, reference

    async def discover(self, run_id, target):
        return await self._offload(self._discover, run_id, target)

    def _discover(self, run_id, target):
        if target != "LedgerLite":
            raise ExecutionFailure("unapproved_target")
        ctx = Context(dict(self.pins))
        self.contexts[run_id] = ctx
        context_ref = self._save(ctx.pins, CONTEXT_DESCRIPTION)
        try:
            report, scan_ref = self._scan(self.original)
        except ExecutionFailure as exc:
            exc.evidence.insert(0, context_ref)
            raise
        allowed_ids = {
            location.finding_id
            for location in report.locations
            if location.path in PATCH_ALLOWLIST
            and location.rule_id == "proofloop.ledgerlite.invoice-missing-ownership"
        }
        finding = next((item for item in report.result.findings if item.id in allowed_ids), None)
        ctx.finding = finding
        return DiscoveryReceipt(finding=finding, evidence=[context_ref, scan_ref])

    def _run(self, ctx, snapshot, phase):
        if runner_hash() != ctx.pins["runner_sha256"]:
            raise ExecutionFailure("trusted_runner_changed", RunStatus.INCONCLUSIVE)
        # Materialize only hash-checked immutable test bytes; target and tests stay separate.
        with tempfile.TemporaryDirectory(dir=self.workspaces, prefix="trusted-suite-") as directory:
            suite_root = Path(directory) / "suite"
            try:
                materialize(self.suite, suite_root)
                result = self.runner.run(
                    snapshot,
                    suite_root,
                    self.manifest,
                    self.limits,
                    phase=phase,
                    deadline=time.monotonic() + 45,
                )
            finally:
                remove_readonly(suite_root)
        reference = self._save(result.to_dict(), f"Independent {phase} execution evidence.")
        if result.status in {"infrastructure_error", "runner_error"}:
            raise ExecutionFailure("runner_unavailable_or_failed", evidence=[reference])
        if result.status != "completed":
            raise ExecutionFailure("runner_incomplete", RunStatus.INCONCLUSIVE, [reference])
        if (
            result.source_sha256 != snapshot.sha256
            or result.manifest_sha256 != self.manifest.sha256
            or result.runner_sha256 != ctx.pins["runner_sha256"]
            or result.image_id != ctx.pins["image_id"]
            or result.phase != phase
        ):
            raise ExecutionFailure(
                "evidence_identity_mismatch", RunStatus.INCONCLUSIVE, [reference]
            )
        return result, reference

    async def reproduce(self, run_id, finding):
        return await self._offload(self._reproduce, run_id)

    def _reproduce(self, run_id):
        ctx = self._context(run_id)
        ctx.baseline, reference = self._run(ctx, self.original, "baseline")
        reproduced = baseline_reproduced(ctx.baseline, self.manifest)
        observed = (ctx.baseline.probe or {}).get("status_code")
        return BaselineReceipt(
            result=BaselineResult(reproduced=reproduced, observed_status=observed),
            evidence=[reference],
        )

    async def generate_patch(self, run_id, finding, attempt, feedback):
        def generate():
            ctx = self._context(run_id)
            defender = OpenAIDefender(
                allowed_files=PATCH_ALLOWLIST, attempt=attempt, timeout=30, retries=0
            )
            source = ProviderSnapshot(
                snapshot_id=f"source_{self.original.sha256}",
                files={name: data.decode() for name, data in self.original.files},
            )
            return defender.generate_patch(source, finding, (feedback + list(ctx.feedback))[-20:])

        try:
            return await self._offload(generate)
        except ProviderError as exc:
            raise ExecutionFailure(defender_failure_code(exc.code)) from None

    async def apply_patch(self, run_id, patch):
        def apply():
            self._context(run_id).patch = apply_unified_diff(
                self.original, patch.diff, allowed_files=PATCH_ALLOWLIST
            )

        await self._offload(apply)

    async def verify(self, run_id):
        return await self._offload(self._evaluate, run_id, False)

    def _evaluate(self, run_id, fresh_baseline):
        ctx = self._context(run_id)
        if ctx.patch is None:
            raise ExecutionFailure("patch_not_applied")
        refs = []
        try:
            if fresh_baseline:
                ctx.baseline, baseline_ref = self._run(ctx, self.original, "baseline")
                refs.append(baseline_ref)
            if ctx.baseline is None:
                raise ExecutionFailure("baseline_missing", RunStatus.INCONCLUSIVE)
            _, scan_ref = self._scan(ctx.patch.patched, ctx)
            refs.append(scan_ref)
            patched, execution_ref = self._run(ctx, ctx.patch.patched, "patched")
            refs.append(execution_ref)
            result = evaluate_patch(ctx.patch, self.manifest, ctx.baseline, patched)
            refs.append(
                self._save(result.to_dict(), "Independent patch verdict and bound evidence.")
            )
            ctx.feedback = tuple(
                f"Independent check failed: {test.test_id}"
                for test in patched.tests
                if test.outcome == "failed"
            )[:19]
            counts = {}
            for category in ("security", "functional", "adversarial"):
                required = [
                    test.test_id for test in self.manifest.checks if test.category == category
                ]
                counts[f"{category}_total"] = len(required)
                counts[f"{category}_passed"] = len(
                    {
                        test.test_id
                        for test in patched.tests
                        if test.outcome == "passed" and test.test_id in required
                    }
                )
            return StageResult(
                verdict=RunStatus(result.verdict),
                summary=VerificationSummary(**counts),
                evidence=refs,
                complete=result.verdict in {"verified", "rejected"},
                patch_sha256=ctx.patch.sha256,
            )
        except ExecutionFailure as exc:
            exc.evidence = refs + exc.evidence
            raise

    async def challenge(self, run_id, request: ChallengeRequest):
        def execute():
            if not set(request.policy_ids) <= {POLICY_ID}:
                raise ExecutionFailure("unapproved_challenge_policy", RunStatus.INCONCLUSIVE)
            spec = ChallengeSpec(
                challenge_id=f"frozen_{run_id}",
                family="ledgerlite_frozen_suite",
                target_id="LedgerLite",
                policy_ids=[POLICY_ID],
                parameters={"suite_version": self.manifest.suite_version},
            )
            # Exactly one admitted deterministic challenge, within every valid request budget.
            spec_ref = self._save(
                spec.model_dump(mode="json"),
                "Admitted frozen deterministic challenge; no sponsor inference.",
            )
            try:
                result = self._evaluate(run_id, True)
            except ExecutionFailure as exc:
                exc.evidence.insert(0, spec_ref)
                raise
            result.evidence.insert(0, spec_ref)
            return result

        return await self._offload(execute)


class UnavailableEngine:
    """A configuration failure is a real run error, not an execution substitute."""

    def __init__(self, code):
        self.code = code

    async def discover(self, run_id, target):
        raise ExecutionFailure(self.code)


def _configured_classic_engine(store: RunStore):
    """Opt-in only. Configuration errors become safe run failures, not startup tracebacks."""
    if os.getenv("PROOFLOOP_EXECUTION_ENABLED") != "1":
        return None
    if not os.getenv("OPENAI_API_KEY") or not os.getenv("OPENAI_MODEL"):
        return UnavailableEngine("defender_configuration_missing")
    image_id = os.getenv("PROOFLOOP_VERIFIER_IMAGE", "")
    manifest_sha256 = os.getenv("PROOFLOOP_MANIFEST_SHA256", "")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id) or not re.fullmatch(
        r"[0-9a-f]{64}", manifest_sha256
    ):
        return UnavailableEngine("invalid_execution_pins")
    try:
        return LedgerLiteEngine(
            repository=Path(__file__).resolve().parents[2],
            store=store,
            image_id=image_id,
            manifest_sha256=manifest_sha256,
            docker_host=os.getenv("PROOFLOOP_DOCKER_HOST", "unix:///var/run/docker.sock"),
            semgrep_executable=os.getenv("SEMGREP_EXECUTABLE", "semgrep"),
        )
    except OSError:
        return UnavailableEngine("approved_inputs_unavailable")
    except ValueError:
        return UnavailableEngine("approved_inputs_invalid")
    except Exception:
        return UnavailableEngine("execution_configuration_failed")


def configured_engine(store: RunStore):
    classic = _configured_classic_engine(store)
    if os.getenv("PROOFLOOP_WORKSPACE_ENABLED") != "1":
        return classic
    from backend.api.workspace_engine import TargetDispatcher, WorkspaceEngine

    try:
        workspace = WorkspaceEngine(Path(__file__).resolve().parents[2], store)
    except Exception:
        workspace = UnavailableEngine("workspace_configuration_failed")
    return TargetDispatcher(classic, workspace, store)
