"""Versioned internal runner contracts. These are not public API wire models."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from backend.engine.patcher import digest, safe_path

HASH = re.compile(r"[0-9a-f]{64}\Z")
CATEGORIES = frozenset({"security", "functional", "adversarial"})


@dataclass(frozen=True)
class ExecutionLimits:
    cpus: float = 1.0
    memory_mb: int = 256
    pids: int = 64
    timeout_seconds: float = 30.0
    total_attempt_seconds: float = 120.0
    output_bytes: int = 1024 * 1024
    scratch_mb: int = 32

    def __post_init__(self) -> None:
        bounds = {
            "cpus": (0.1, 4),
            "memory_mb": (64, 2048),
            "pids": (16, 256),
            "timeout_seconds": (1, 120),
            "total_attempt_seconds": (2, 600),
            "output_bytes": (4096, 4 * 1024 * 1024),
            "scratch_mb": (1, 128),
        }
        for field, (low, high) in bounds.items():
            value = getattr(self, field)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not low <= value <= high
            ):
                raise ValueError(f"Invalid execution limit: {field}")
            if (
                field not in {"cpus", "timeout_seconds", "total_attempt_seconds"}
                and type(value) is not int
            ):
                raise ValueError(f"Integer execution limit required: {field}")


@dataclass(frozen=True)
class TestCheck:
    test_id: str
    category: str

    def __post_init__(self) -> None:
        parts = self.test_id.split("::")
        safe_path(parts[0])
        if (
            len(parts) < 2
            or not parts[0].endswith(".py")
            or len(self.test_id) > 512
            or any(ord(c) < 32 for c in self.test_id)
            or self.category not in CATEGORIES
        ):
            raise ValueError("Invalid frozen test identity or category")


@dataclass(frozen=True)
class FrozenTestManifest:
    target: str
    suite_version: str
    checks: tuple[TestCheck, ...]
    trusted_files: tuple[tuple[str, str], ...]
    baseline_expected_failures: tuple[str, ...]
    policy_sha256: str

    def __post_init__(self) -> None:
        if self.target != "LedgerLite" or not self.suite_version:
            raise ValueError("Only the approved LedgerLite target is supported")
        if not all(
            isinstance(value, tuple)
            for value in (self.checks, self.trusted_files, self.baseline_expected_failures)
        ):
            raise ValueError("Manifest must be immutable")
        ids = [check.test_id for check in self.checks]
        files = dict(self.trusted_files)
        if (
            not self.checks
            or len(ids) != len(set(ids))
            or len(ids) > 256
            or {check.category for check in self.checks} != CATEGORIES
            or len(files) != len(self.trusted_files)
            or not files
            or not self.baseline_expected_failures
            or len(set(self.baseline_expected_failures)) != len(self.baseline_expected_failures)
            or not set(self.baseline_expected_failures) <= set(ids)
            or not HASH.fullmatch(self.policy_sha256)
        ):
            raise ValueError("Incomplete, duplicate, or invalid manifest")
        for record in self.trusted_files:
            if not isinstance(record, tuple):
                raise ValueError("Mutable file hash record")
            name, sha = record
            safe_path(name)
            if not name.endswith(".py") or not HASH.fullmatch(sha):
                raise ValueError("Invalid trusted test file or hash")
        if any(check.test_id.split("::")[0] not in files for check in self.checks):
            raise ValueError("Every test module must be hash-pinned")

    @property
    def sha256(self) -> str:
        return digest(asdict(self))

    @property
    def required_test_ids(self) -> tuple[str, ...]:
        return tuple(check.test_id for check in self.checks)


@dataclass(frozen=True)
class ProcessEvidence:
    status: str  # completed, timeout, output_limit, runner_error, stopped_by_runner
    exit_code: int | None
    stdout: str
    stderr: str
    duration_seconds: float
    # Base64 retains exact bytes even when output is not UTF-8.
    stdout_base64: str = ""
    stderr_base64: str = ""
    truncated: bool = False


@dataclass(frozen=True)
class TestEvidence:
    test_id: str
    category: str
    outcome: str
    phases: tuple[dict, ...]


@dataclass(frozen=True)
class ExecutionEvidence:
    status: str  # completed, timeout, output_limit, infrastructure_error, runner_error
    phase: str
    source_sha256: str
    manifest_sha256: str
    runner_sha256: str
    image_id: str
    execution_id: str
    tests: tuple[TestEvidence, ...] = ()
    probe: dict | None = None
    process: ProcessEvidence | None = None
    target_process: ProcessEvidence | None = None
    diagnostics: tuple[ProcessEvidence, ...] = ()
    reason: str = ""
    source: str = "execution"

    def to_dict(self) -> dict:
        return asdict(self)
