"""Health is live. Planned routes fail explicitly without creating security results."""

from typing import Annotated, NoReturn

from fastapi import APIRouter, HTTPException, Path, Query

from backend.api.schemas import (
    AnalyticsResponse,
    ChallengeRequest,
    ChallengeResponse,
    CreateRunRequest,
    ErrorResponse,
    EventsResponse,
    HealthResponse,
    ReportResponse,
    RunResponse,
)

router = APIRouter(prefix="/api")
RunId = Annotated[str, Path(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")]
PLANNED_ERRORS = {
    501: {"model": ErrorResponse, "description": "PLANNED: engine/integration not implemented"},
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


def planned() -> NoReturn:
    raise HTTPException(
        status_code=501,
        detail={
            "code": "not_implemented",
            "message": "PLANNED: security execution is not enabled.",
        },
    )


@router.get("/health", response_model=HealthResponse, tags=["health"])
def health() -> HealthResponse:
    return HealthResponse()


@router.post("/runs", response_model=RunResponse, status_code=202, responses=PLANNED_ERRORS)
def create_run(request: CreateRunRequest) -> RunResponse:
    planned()


@router.get("/runs/{run_id}", response_model=RunResponse, responses=PLANNED_ERRORS)
def get_run(run_id: RunId) -> RunResponse:
    planned()


@router.get("/runs/{run_id}/events", response_model=EventsResponse, responses=PLANNED_ERRORS)
def get_events(
    run_id: RunId,
    cursor: Annotated[str | None, Query(max_length=256)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> EventsResponse:
    planned()


@router.get("/runs/{run_id}/report", response_model=ReportResponse, responses=PLANNED_ERRORS)
def get_report(run_id: RunId) -> ReportResponse:
    planned()


@router.post(
    "/runs/{run_id}/challenge",
    response_model=ChallengeResponse,
    status_code=202,
    responses=PLANNED_ERRORS,
)
def challenge(run_id: RunId, request: ChallengeRequest) -> ChallengeResponse:
    planned()


@router.get("/analytics", response_model=AnalyticsResponse, responses=PLANNED_ERRORS)
def analytics(
    run_id: Annotated[str | None, Query(pattern=r"^[A-Za-z0-9_-]+$", max_length=128)] = None,
) -> AnalyticsResponse:
    planned()
