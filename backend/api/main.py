"""Start from repo root: python -m uvicorn backend.api.main:app --reload."""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api.routes import router


def create_app(*, orchestrator=None) -> FastAPI:
    from backend.engine.orchestrator import Orchestrator
    from backend.storage.runs import RunStore

    @asynccontextmanager
    async def lifespan(application):
        if orchestrator is None:
            from backend.api.composition import configured_engine

            store = RunStore(Path(os.getenv("PROOFLOOP_RUNS_DIR", "runs")))
            service = Orchestrator(store, configured_engine(store), stage_timeout=180)
        else:
            service = orchestrator
        application.state.orchestrator = service
        service.recover()
        from backend.telemetry.delivery import configured_delivery

        delivery = configured_delivery(service.store)
        application.state.telemetry = delivery
        if delivery:
            delivery.start()
        try:
            yield
        finally:
            await service.close()
            if delivery:
                await delivery.close()

    application = FastAPI(title="ProofLoop", version="0.1.0", lifespan=lifespan)
    origins = os.getenv("PROOFLOOP_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in origins.split(",") if origin.strip()],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @application.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException) -> JSONResponse:
        detail = (
            error.detail
            if isinstance(error.detail, dict)
            else {
                "code": "not_found" if error.status_code == 404 else "internal_error",
                "message": "The request could not be completed.",
            }
        )
        return JSONResponse(status_code=error.status_code, content={"error": detail})

    @application.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, error: RequestValidationError) -> JSONResponse:
        # Do not echo request bodies, provider keys, headers, or validation input values.
        return JSONResponse(
            status_code=422,
            content={"error": {"code": "invalid_request", "message": "Request validation failed."}},
        )

    @application.exception_handler(Exception)
    async def internal_error(request: Request, error: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "The request could not be completed.",
                }
            },
        )

    application.include_router(router)
    return application


app = create_app()
