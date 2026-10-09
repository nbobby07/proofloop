"""Bounded lifecycle. Engine adapters, never model output, supply trusted verdicts.

ExecutionEngine is the integration seam for A1's frozen suites, A2's independent
runner, and A3's existing provider DTOs. Implementations must enforce their own
resource/IO timeouts, admit challenges, and keep opaque execution handles alive
for rechallenge. Async operations must not block the event loop.
"""

import asyncio
import hashlib
from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

from pydantic import Field

from backend.api.schemas import (
    BaselineResult,
    ChallengeRequest,
    ContractModel,
    CreateRunRequest,
    EventSeverity,
    EventType,
    EvidenceReference,
    Finding,
    PatchProposal,
    RunResponse,
    RunStatus,
    SecurityEvent,
    Source,
    VerificationSummary,
)
from backend.storage.runs import TERMINAL, Attempt, RunRecord, RunStore, VerificationRecord

S = RunStatus
TRANSITIONS = {
    S.PENDING: {S.DISCOVERING},
    S.DISCOVERING: {S.REPRODUCING},
    S.REPRODUCING: {S.GENERATING_PATCH},
    S.GENERATING_PATCH: {S.APPLYING_PATCH},
    S.APPLYING_PATCH: {S.VERIFYING, S.RETRYING, S.REJECTED},
    S.VERIFYING: {S.CHALLENGING, S.RETRYING, S.REJECTED},
    S.CHALLENGING: {S.VERIFIED, S.RETRYING, S.REJECTED},
    S.RETRYING: {S.GENERATING_PATCH},
    S.VERIFIED: {S.CHALLENGING},
    S.REJECTED: {S.CHALLENGING},
    S.INCONCLUSIVE: {S.CHALLENGING},
    S.ERROR: set(),
}
for _state in set(S) - TERMINAL:
    TRANSITIONS[_state] |= {S.ERROR, S.INCONCLUSIVE}


class DiscoveryReceipt(ContractModel):
    finding: Finding | None = None
    evidence: list[EvidenceReference] = Field(default_factory=list)


class BaselineReceipt(ContractModel):
    result: BaselineResult
    evidence: list[EvidenceReference] = Field(default_factory=list)


class StageResult(ContractModel):
    """Internal trusted execution receipt; deliberately not a public wire contract."""

    verdict: RunStatus
    summary: VerificationSummary
    evidence: list[EvidenceReference] = Field(default_factory=list)
    # A2 attests completeness by comparing actual outcomes with frozen required IDs,
    # checking baseline and target/patch/policy/suite hashes, not by counting passes.
    complete: bool = False
    patch_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ExecutionEngine(Protocol):
    async def discover(self, run_id: str, target: str) -> DiscoveryReceipt: ...
    async def reproduce(self, run_id: str, finding: Finding) -> BaselineReceipt: ...
    async def generate_patch(
        self, run_id: str, finding: Finding, attempt: int, feedback: list[str]
    ) -> PatchProposal: ...
    async def apply_patch(self, run_id: str, patch: PatchProposal) -> None: ...
    async def verify(self, run_id: str) -> StageResult: ...
    async def challenge(self, run_id: str, request: ChallengeRequest) -> StageResult: ...


class EngineUnavailable(RuntimeError):
    """Real dependencies have not been configured; never substitute demo results."""


class ExecutionFailure(RuntimeError):
    """Trusted adapter failures use fixed codes, never raw upstream exception text."""

    def __init__(
        self,
        code: str,
        status: RunStatus = S.ERROR,
        evidence: list[EvidenceReference] | None = None,
    ):
        super().__init__(code)
        self.code = code
        self.status = status
        self.evidence = evidence or []


class InvalidTransition(ValueError):
    pass


class RunConflict(ValueError):
    pass


class Orchestrator:
    def __init__(
        self,
        store: RunStore,
        engine: ExecutionEngine | None = None,
        stage_timeout: float = 120,
        max_active: int = 4,
    ):
        if stage_timeout <= 0 or max_active < 1:
            raise ValueError("Positive stage timeout and execution capacity required")
        self.store = store
        self.engine = engine
        self.stage_timeout = stage_timeout
        self.max_active = max_active
        self.tasks: dict[str, asyncio.Task] = {}

    def emit(
        self,
        record: RunRecord,
        kind: EventType,
        message: str,
        severity: EventSeverity = EventSeverity.INFO,
    ) -> None:
        record.run.events.append(
            SecurityEvent(
                event_id=f"event_{len(record.run.events) + 1:08d}",
                run_id=record.run.run_id,
                timestamp=datetime.now(UTC),
                stage=record.run.status,
                event_type=kind,
                severity=severity,
                message=message,
                source=Source.EXECUTION,
            )
        )
        self.store.save(record)

    def transition(self, record: RunRecord, status: RunStatus) -> None:
        if status not in TRANSITIONS[record.run.status]:
            raise InvalidTransition(f"{record.run.status} -> {status}")
        self.emit(record, EventType.STAGE_COMPLETED, f"Stage {record.run.status} finished.")
        record.run.status = status
        self.emit(record, EventType.STAGE_STARTED, f"Stage {status} started.")

    def _capacity(self) -> None:
        if sum(not task.done() for task in self.tasks.values()) >= self.max_active:
            raise RunConflict("Execution capacity reached; retry later.")

    def create(self, request: CreateRunRequest) -> RunResponse:
        self._capacity()
        record = RunRecord(
            request=request,
            run=RunResponse(
                run_id=f"run_{uuid4().hex}",
                status=S.PENDING,
                target=request.target,
                source=Source.EXECUTION,
            ),
        )
        self.emit(record, EventType.STAGE_STARTED, "Run scheduled.")
        response = record.run.model_copy(deep=True)
        self._schedule(record, False, ChallengeRequest())
        return response

    def rechallenge(self, run_id: str, request: ChallengeRequest) -> None:
        record = self.store.get(run_id)
        if record.run.source != Source.EXECUTION or record.run.status not in {
            S.VERIFIED,
            S.REJECTED,
            S.INCONCLUSIVE,
        }:
            raise RunConflict("Run state does not permit a challenge.")
        if not record.run.patch or not record.attempts or not record.run.baseline:
            raise RunConflict("No applied patch is available to challenge.")
        if not record.attempts[-1].applied:
            raise RunConflict("No applied patch is available to challenge.")
        if not record.run.baseline.reproduced:
            raise RunConflict("A reproduced baseline is required.")
        self._capacity()
        record.run.verification = None
        record.failure_code = record.failure_message = None
        record.challenge_generation += 1
        self.transition(record, S.CHALLENGING)
        self._schedule(record, True, request)

    def _schedule(self, record: RunRecord, rechallenge: bool, request: ChallengeRequest) -> None:
        run_id = record.run.run_id
        task = asyncio.create_task(self._execute(record, rechallenge, request))
        self.tasks[run_id] = task

        def remove(finished):
            if self.tasks.get(run_id) is finished:
                self.tasks.pop(run_id, None)

        task.add_done_callback(remove)

    async def _call(self, operation, *args):
        async with asyncio.timeout(self.stage_timeout):
            return await operation(*args)

    def _finish(self, record: RunRecord, status: RunStatus, code: str | None = None) -> None:
        if record.attempts:
            attempt = record.attempts[-1]
            attempt.verdict = status
            if attempt.verifications and attempt.verifications[-1].verdict is None:
                attempt.verifications[-1].verdict = status
        record.failure_code = code
        record.failure_message = code.replace("_", " ") if code else None
        self.transition(record, status)
        self.emit(
            record,
            EventType.RUN_FAILED if status == S.ERROR else EventType.RUN_COMPLETED,
            f"Run finished: {status}." + (f" Reason: {code}." if code else ""),
            EventSeverity.ERROR if status == S.ERROR else EventSeverity.INFO,
        )

    def _receipt(self, record: RunRecord, result: StageResult, final: bool) -> RunStatus:
        expected = hashlib.sha256(record.run.patch.diff.encode()).hexdigest()
        if result.patch_sha256 != expected:
            record.attempts[-1].verdict = S.INCONCLUSIVE
            self.emit(
                record,
                EventType.TEST_COMPLETED,
                "Evidence does not match the current patch.",
                EventSeverity.WARNING,
            )
            return S.INCONCLUSIVE
        record.run.verification = result.summary
        record.evidence.extend(result.evidence)
        attempt = record.attempts[-1]
        attempt.verification = result.summary
        attempt.evidence.extend(result.evidence)
        verdict = result.verdict
        if verdict not in {S.VERIFIED, S.REJECTED, S.INCONCLUSIVE, S.ERROR}:
            verdict = S.INCONCLUSIVE
        suites = ("security", "functional", "adversarial") if final else ("security", "functional")
        if verdict == S.VERIFIED and (
            not result.complete
            or not result.evidence
            or not record.run.baseline.reproduced
            or any(
                getattr(result.summary, f"{s}_total") == 0
                or getattr(result.summary, f"{s}_passed") != getattr(result.summary, f"{s}_total")
                for s in suites
            )
        ):
            verdict = S.INCONCLUSIVE
        if verdict == S.REJECTED and not result.complete:
            verdict = S.INCONCLUSIVE
        attempt.verdict = verdict
        receipt = attempt.verifications[-1]
        receipt.verdict = verdict
        receipt.summary = result.summary
        receipt.evidence = result.evidence
        self.emit(record, EventType.TEST_COMPLETED, f"Independent verification returned {verdict}.")
        return verdict

    def _begin_verification(self, record: RunRecord, final: bool) -> None:
        record.attempts[-1].verifications.append(
            VerificationRecord(
                phase="challenge" if final else "verification",
                challenge_generation=record.challenge_generation,
            )
        )
        self.store.save(record)

    async def _execute(
        self, record: RunRecord, rechallenge: bool, challenge_request: ChallengeRequest
    ) -> None:
        try:
            engine = self.engine
            if engine is None:
                raise EngineUnavailable()
            run_id = record.run.run_id
            if rechallenge:
                self._begin_verification(record, True)
                result = await self._call(engine.challenge, run_id, challenge_request)
                verdict = self._receipt(record, result, True)
                self._finish(record, verdict)
                return
            self.transition(record, S.DISCOVERING)
            discovery = await self._call(engine.discover, run_id, record.run.target)
            record.evidence.extend(discovery.evidence)
            finding = discovery.finding
            if finding is None:
                self._finish(record, S.INCONCLUSIVE, "no_reproducible_finding")
                return
            record.run.finding = finding
            self.emit(record, EventType.FINDING_DISCOVERED, "Scanner finding selected.")
            self.transition(record, S.REPRODUCING)
            baseline = await self._call(engine.reproduce, run_id, finding)
            record.run.baseline = baseline.result
            record.evidence.extend(baseline.evidence)
            if not record.run.baseline.reproduced:
                self._finish(record, S.INCONCLUSIVE, "baseline_not_reproduced")
                return
            self.emit(record, EventType.BASELINE_REPRODUCED, "Independent baseline reproduced.")
            feedback: list[str] = []
            for number in range(1, record.request.max_attempts + 1):
                self.transition(record, S.GENERATING_PATCH)
                record.run.verification = None
                patch = await self._call(engine.generate_patch, run_id, finding, number, feedback)
                if patch.attempt != number:
                    raise ValueError("Provider attempt does not match requested attempt")
                record.run.patch = patch
                record.attempts.append(Attempt(patch=patch))
                self.emit(record, EventType.PATCH_PROPOSED, f"Patch attempt {number} proposed.")
                self.transition(record, S.APPLYING_PATCH)
                await self._call(engine.apply_patch, run_id, patch)
                record.attempts[-1].applied = True
                self.emit(record, EventType.PATCH_APPLIED, "Patch applied in isolated workspace.")
                self.transition(record, S.VERIFYING)
                self._begin_verification(record, False)
                verdict = self._receipt(record, await self._call(engine.verify, run_id), False)
                if verdict == S.VERIFIED:
                    self.transition(record, S.CHALLENGING)
                    self._begin_verification(record, True)
                    verdict = self._receipt(
                        record, await self._call(engine.challenge, run_id, challenge_request), True
                    )
                if verdict != S.REJECTED or number == record.request.max_attempts:
                    self._finish(record, verdict)
                    return
                feedback.append("Independent required tests rejected the previous patch.")
                self.transition(record, S.RETRYING)
                self.emit(
                    record, EventType.RETRY_SCHEDULED, "Retry scheduled within attempt budget."
                )
        except asyncio.CancelledError:
            self._finish(record, S.ERROR, "execution_interrupted")
            raise
        except TimeoutError:
            self._finish(record, S.INCONCLUSIVE, "stage_timeout")
        except ExecutionFailure as exc:
            record.evidence.extend(exc.evidence)
            self._finish(record, exc.status, exc.code)
        except EngineUnavailable:
            self._finish(record, S.ERROR, "engine_not_configured")
        except Exception:
            # Never persist arbitrary exception text: providers may include credentials/PII.
            self._finish(record, S.ERROR, "execution_failed")
        finally:
            release = getattr(self.engine, "release", None)
            if release is not None:
                release(record.run.run_id)

    def recover(self) -> None:
        """Interrupted work cannot resume against unpinned in-memory engine contexts."""
        for record in self.store.all():
            if record.run.status not in TERMINAL:
                self._finish(record, S.ERROR, "execution_interrupted")

    async def close(self) -> None:
        run_ids = list(self.tasks)
        tasks = list(self.tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        for run_id in run_ids:
            record = self.store.get(run_id)
            if record.run.status not in TERMINAL:
                self._finish(record, S.ERROR, "execution_interrupted")
