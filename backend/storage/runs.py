"""Atomic local manifests for a single API process; no database or fixture fallback."""

import os
import re
import tempfile
from pathlib import Path
from threading import RLock

from pydantic import Field

from backend.api.schemas import (
    ContractModel,
    CreateRunRequest,
    EvidenceReference,
    PatchProposal,
    RunResponse,
    RunStatus,
    VerificationSummary,
)

TERMINAL = {RunStatus.VERIFIED, RunStatus.REJECTED, RunStatus.INCONCLUSIVE, RunStatus.ERROR}


class VerificationRecord(ContractModel):
    phase: str
    challenge_generation: int
    verdict: RunStatus | None = None
    summary: VerificationSummary | None = None
    evidence: list[EvidenceReference] = Field(default_factory=list)


class Attempt(ContractModel):
    patch: PatchProposal
    verification: VerificationSummary | None = None
    verdict: RunStatus | None = None
    applied: bool = False
    verifications: list[VerificationRecord] = Field(default_factory=list)
    evidence: list[EvidenceReference] = Field(default_factory=list)


class RunRecord(ContractModel):
    request: CreateRunRequest
    run: RunResponse
    attempts: list[Attempt] = Field(default_factory=list)
    evidence: list[EvidenceReference] = Field(default_factory=list)
    failure_code: str | None = None
    failure_message: str | None = None
    # Opaque engine-owned handle; never returned to API clients.
    execution_id: str | None = None
    challenge_generation: int = 0


class RunStore:
    """Manifests are replaced atomically; readers never observe partial JSON.

    Deploy with one API worker. The orchestrator serializes each run's mutations.
    Raw provider exceptions and target output must never be stored here.
    """

    def __init__(self, root: Path):
        self.root = root
        self.lock = RLock()

    def _path(self, run_id: str) -> Path:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", run_id):
            raise KeyError(run_id)
        return self.root / f"{run_id}.json"

    def get(self, run_id: str) -> RunRecord:
        with self.lock:
            try:
                return RunRecord.model_validate_json(self._path(run_id).read_text())
            except FileNotFoundError as exc:
                raise KeyError(run_id) from exc

    def save(self, record: RunRecord) -> None:
        with self.lock:
            self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
            path = self._path(record.run.run_id)
            fd, temporary = tempfile.mkstemp(dir=self.root, prefix=".manifest-")
            try:
                with os.fdopen(fd, "w") as stream:
                    stream.write(record.model_dump_json())
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, path)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)

    def all(self) -> list[RunRecord]:
        with self.lock:
            return [self.get(path.stem) for path in sorted(self.root.glob("*.json"))]
