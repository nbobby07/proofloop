"""Canonical v1 contracts. Regenerate JSON and TypeScript after coordinated edits."""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, JsonValue, model_validator

Identifier = Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RunStatus(StrEnum):
    PENDING = "pending"
    DISCOVERING = "discovering"
    REPRODUCING = "reproducing"
    GENERATING_PATCH = "generating_patch"
    APPLYING_PATCH = "applying_patch"
    VERIFYING = "verifying"
    CHALLENGING = "challenging"
    RETRYING = "retrying"
    VERIFIED = "verified"
    REJECTED = "rejected"
    INCONCLUSIVE = "inconclusive"
    ERROR = "error"


class Source(StrEnum):
    FIXTURE = "fixture"
    EXECUTION = "execution"


class FindingSeverity(StrEnum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EventSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class EventType(StrEnum):
    STAGE_STARTED = "stage_started"
    STAGE_COMPLETED = "stage_completed"
    FINDING_DISCOVERED = "finding_discovered"
    BASELINE_REPRODUCED = "baseline_reproduced"
    PATCH_PROPOSED = "patch_proposed"
    PATCH_APPLIED = "patch_applied"
    TEST_COMPLETED = "test_completed"
    CHALLENGE_PROPOSED = "challenge_proposed"
    RETRY_SCHEDULED = "retry_scheduled"
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"


class SecurityEvent(ContractModel):
    event_id: Identifier
    run_id: Identifier
    timestamp: AwareDatetime
    stage: RunStatus
    event_type: EventType
    severity: EventSeverity
    message: str = Field(min_length=1, max_length=2000)
    source: Source
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class HealthResponse(ContractModel):
    status: Literal["ok"] = "ok"
    service: Literal["proofloop"] = "proofloop"


class Finding(ContractModel):
    id: Identifier
    title: str = Field(min_length=1, max_length=300)
    severity: FindingSeverity


class BaselineResult(ContractModel):
    reproduced: bool
    observed_status: int | None = Field(default=None, ge=100, le=599)


class PatchProposal(ContractModel):
    attempt: int = Field(ge=1, le=10)
    diff: str = Field(min_length=1, max_length=200_000)


class VerificationSummary(ContractModel):
    security_passed: int = Field(ge=0)
    security_total: int = Field(ge=0)
    functional_passed: int = Field(ge=0)
    functional_total: int = Field(ge=0)
    adversarial_passed: int = Field(ge=0)
    adversarial_total: int = Field(ge=0)

    @model_validator(mode="after")
    def counts_are_consistent(self) -> "VerificationSummary":
        for suite in ("security", "functional", "adversarial"):
            if getattr(self, f"{suite}_passed") > getattr(self, f"{suite}_total"):
                raise ValueError(f"{suite}_passed cannot exceed {suite}_total")
        return self


class RunResponse(ContractModel):
    run_id: Identifier
    status: RunStatus
    target: str = Field(min_length=1, max_length=128)
    source: Source
    finding: Finding | None = None
    baseline: BaselineResult | None = None
    patch: PatchProposal | None = None
    verification: VerificationSummary | None = None
    events: list[SecurityEvent] = Field(default_factory=list)

    @model_validator(mode="after")
    def events_match_run(self) -> "RunResponse":
        if any(event.run_id != self.run_id or event.source != self.source for event in self.events):
            raise ValueError("events must match their enclosing run id and source")
        return self


class CreateRunRequest(ContractModel):
    # An allowlisted server-side target id; never an arbitrary host URL or shell command.
    target: Literal["LedgerLite"]
    max_attempts: int = Field(default=3, ge=1, le=10)


class ChallengeRequest(ContractModel):
    max_challenges: int = Field(default=2, ge=1, le=10)
    policy_ids: list[Identifier] = Field(default_factory=list, max_length=20)


class ChallengeResponse(ContractModel):
    run_id: Identifier
    status: Literal["challenging"] = "challenging"
    source: Literal["execution"] = "execution"


class EventsResponse(ContractModel):
    run_id: Identifier
    source: Source
    events: list[SecurityEvent]
    next_cursor: str | None = None


class EvidenceReference(ContractModel):
    artifact_id: Identifier
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    description: str = Field(min_length=1, max_length=500)


class ReportResponse(ContractModel):
    run_id: Identifier
    source: Source
    status: RunStatus
    summary: str = Field(min_length=1, max_length=5000)
    verification: VerificationSummary | None = None
    evidence: list[EvidenceReference] = Field(default_factory=list)
    limitations: list[str]


class FailurePattern(ContractModel):
    challenge_family: str
    failures: int = Field(ge=0)
    executions: int = Field(ge=0)


class AnalyticsResponse(ContractModel):
    source: Source
    run_count: int = Field(ge=0)
    verified_count: int = Field(ge=0)
    rejected_count: int = Field(ge=0)
    failure_patterns: list[FailurePattern]


class TelemetryAnalyticsResponse(ContractModel):
    """SQL results only; local fallback never masquerades as cloud telemetry."""

    source: Literal["execution"] = "execution"
    storage: Literal["clickhouse"] = "clickhouse"
    analytics: AnalyticsResponse
    event_count: int = Field(ge=0)
    pending_events: int = Field(ge=0)
    incomplete_rounds: int = Field(ge=0)
    mean_patch_attempts: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    mean_verification_duration_ms: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    latest_event_at: AwareDatetime | None = None
    query_ms: float = Field(ge=0, allow_inf_nan=False)


class ErrorDetail(ContractModel):
    code: Literal["not_implemented", "not_found", "invalid_request", "conflict", "internal_error"]
    message: str


class ErrorResponse(ContractModel):
    error: ErrorDetail


class BriefingRequest(ContractModel):
    """Only the expected evidence identity, never arbitrary narration text."""

    report_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class BriefingResponse(ContractModel):
    run_id: Identifier
    source: Literal["execution"] = "execution"
    status: Literal["unavailable", "not_generated", "generating", "ready", "error"]
    report_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    artifact_id: Identifier | None = None
    audio_path: str | None = None
    transcript: str | None = None
