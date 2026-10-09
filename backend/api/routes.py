"""Contract-compatible execution routes; dependencies are injected by the app lifespan."""

import base64
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, Request
from fastapi.responses import FileResponse

from backend.api.schemas import (
    AnalyticsResponse,
    BriefingRequest,
    BriefingResponse,
    ChallengeRequest,
    ChallengeResponse,
    CreateRunRequest,
    ErrorResponse,
    EventsResponse,
    ExecutionDetails,
    FailurePattern,
    HealthResponse,
    ReportResponse,
    RunResponse,
    RunStatus,
    Source,
    TelemetryAnalyticsResponse,
)
from backend.reports.narrator import NarrationUnavailable
from backend.telemetry.client import TelemetryUnavailable

router = APIRouter(prefix="/api")
RunId = Annotated[str, Path(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")]
PLANNED_ERRORS = {
    501: {"model": ErrorResponse, "description": "PLANNED: engine/integration not implemented"},
    404: {"model": ErrorResponse, "description": "Run not found"},
    409: {"model": ErrorResponse, "description": "Run state conflict"},
    422: {"model": ErrorResponse, "description": "Request validation failed"},
}


def service(request: Request):
    return request.app.state.orchestrator


def record_for(request: Request, run_id: str):
    try:
        return service(request).store.get(run_id)
    except KeyError as exc:
        raise HTTPException(404, {"code": "not_found", "message": "Run not found."}) from exc


def conflict(message: str):
    raise HTTPException(409, {"code": "conflict", "message": message})


@router.get("/health", response_model=HealthResponse, tags=["health"])
def health() -> HealthResponse:
    return HealthResponse()


@router.post("/runs", response_model=RunResponse, status_code=202, responses=PLANNED_ERRORS)
async def create_run(request: CreateRunRequest, http_request: Request) -> RunResponse:
    from backend.engine.orchestrator import RunConflict

    try:
        return service(http_request).create(request)
    except RunConflict as exc:
        conflict(str(exc))


@router.get("/runs/{run_id}", response_model=RunResponse, responses=PLANNED_ERRORS)
def get_run(run_id: RunId, http_request: Request) -> RunResponse:
    return record_for(http_request, run_id).run


@router.get("/runs/{run_id}/events", response_model=EventsResponse, responses=PLANNED_ERRORS)
def get_events(
    run_id: RunId,
    http_request: Request,
    cursor: Annotated[str | None, Query(max_length=256)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> EventsResponse:
    run = record_for(http_request, run_id).run
    offset = 0
    if cursor:
        try:
            decoded = base64.b64decode(cursor, altchars=b"-_", validate=True).decode()
            owner, position = decoded.split(":")
            offset = int(position)
            if owner != run_id or offset < 0 or offset > len(run.events):
                raise ValueError()
        except (ValueError, UnicodeError) as exc:
            raise HTTPException(
                422, {"code": "invalid_request", "message": "Invalid event cursor."}
            ) from exc
    events = run.events[offset : offset + limit]
    end = offset + len(events)
    # Retain the tail cursor so clients can poll newly appended events.
    next_cursor = (
        base64.urlsafe_b64encode(f"{run_id}:{end}".encode()).decode() if events else cursor
    )
    return EventsResponse(run_id=run_id, source=run.source, events=events, next_cursor=next_cursor)


@router.get("/runs/{run_id}/report", response_model=ReportResponse, responses=PLANNED_ERRORS)
def get_report(run_id: RunId, http_request: Request) -> ReportResponse:
    from backend.storage.runs import TERMINAL

    record = record_for(http_request, run_id)
    run = record.run
    if run.status not in TERMINAL:
        conflict("Run has not completed.")
    return ReportResponse(
        run_id=run_id,
        source=run.source,
        status=run.status,
        summary=f"Run {run.status}."
        + (f" Failure code: {record.failure_code}." if record.failure_code else ""),
        verification=run.verification,
        evidence=record.evidence,
        limitations=["Results cover only the frozen executed suites; not universal security."],
    )


@router.post(
    "/runs/{run_id}/challenge",
    response_model=ChallengeResponse,
    status_code=202,
    responses=PLANNED_ERRORS,
)
async def challenge(
    run_id: RunId, request: ChallengeRequest, http_request: Request
) -> ChallengeResponse:
    from backend.engine.orchestrator import RunConflict

    record_for(http_request, run_id)
    try:
        service(http_request).rechallenge(run_id, request)
    except RunConflict as exc:
        conflict(str(exc))
    return ChallengeResponse(run_id=run_id)


@router.get("/analytics", response_model=AnalyticsResponse, responses=PLANNED_ERRORS)
def analytics(
    http_request: Request,
    run_id: Annotated[str | None, Query(pattern=r"^[A-Za-z0-9_-]+$", max_length=128)] = None,
) -> AnalyticsResponse:
    records = [record_for(http_request, run_id)] if run_id else service(http_request).store.all()
    records = [r for r in records if r.run.source == Source.EXECUTION]
    # Keep every verification/challenge execution, including incomplete and timed-out rounds.
    attempts = [a for r in records for a in r.attempts]
    outcomes = [v.verdict for a in attempts for v in a.verifications]
    outcomes.extend(a.verdict for a in attempts if not a.verifications)
    patterns = (
        [
            FailurePattern(
                challenge_family="required_suites",
                executions=len(outcomes),
                failures=sum(verdict != RunStatus.VERIFIED for verdict in outcomes),
            )
        ]
        if attempts
        else []
    )
    return AnalyticsResponse(
        source=Source.EXECUTION,
        run_count=len(records),
        verified_count=sum(r.run.status == RunStatus.VERIFIED for r in records),
        rejected_count=sum(r.run.status == RunStatus.REJECTED for r in records),
        failure_patterns=patterns,
    )


# Additive optional feature routes; the existing seven API v1 responses are unchanged.


@router.get("/runs/{run_id}/execution", response_model=ExecutionDetails)
def execution_details(run_id: RunId, http_request: Request):
    record = record_for(http_request, run_id)
    engine = getattr(http_request.app.state.orchestrator.engine, "workspace", None)
    entries = engine.entries(run_id) if hasattr(engine, "entries") else []
    budget = engine.budget.summary() if hasattr(engine, "budget") else {}
    return ExecutionDetails(
        run_id=run_id,
        target=record.run.target,
        execution_mode=record.request.execution_mode,
        entries=entries,
        budget=budget,
    )


@router.get("/telemetry/analytics", response_model=TelemetryAnalyticsResponse)
def cloud_analytics(http_request: Request) -> TelemetryAnalyticsResponse:
    delivery = getattr(http_request.app.state, "telemetry", None)
    if delivery is None:
        raise HTTPException(503, {"code": "not_implemented", "message": "ClickHouse is disabled."})
    try:
        return delivery.analytics()
    except (TelemetryUnavailable, ValueError):
        raise HTTPException(
            503,
            {"code": "internal_error", "message": "ClickHouse analytics are unavailable."},
        ) from None


def briefing_operation(request: Request, run_id: str, expected_digest: str | None = None):
    record_for(request, run_id)
    try:
        service = request.app.state.briefings
        return (
            service.generate(run_id, expected_digest) if expected_digest else service.status(run_id)
        )
    except ValueError:
        conflict("A completed current execution report and available capacity are required.")


@router.get("/runs/{run_id}/briefing", response_model=BriefingResponse, responses=PLANNED_ERRORS)
def get_briefing(run_id: RunId, http_request: Request) -> BriefingResponse:
    return briefing_operation(http_request, run_id)


@router.post(
    "/runs/{run_id}/briefing",
    response_model=BriefingResponse,
    status_code=202,
    responses=PLANNED_ERRORS,
)
async def create_briefing(
    run_id: RunId, request: BriefingRequest, http_request: Request
) -> BriefingResponse:
    return briefing_operation(http_request, run_id, expected_digest=request.report_sha256)


@router.get("/audio/{artifact_id}", response_class=FileResponse, responses=PLANNED_ERRORS)
def get_audio(artifact_id: RunId, http_request: Request):
    try:
        path, _ = http_request.app.state.briefings.media(artifact_id)
        return FileResponse(path, media_type="audio/mpeg", headers={"Cache-Control": "no-store"})
    except ValueError:
        conflict("Audio does not match the current completed report.")
    except (KeyError, OSError, NarrationUnavailable):
        raise HTTPException(404, {"code": "not_found", "message": "Audio unavailable."}) from None
