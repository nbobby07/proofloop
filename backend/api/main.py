"""Start from repo root: python -m uvicorn backend.api.main:app --reload."""

import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api.routes import router


def create_app() -> FastAPI:
    application = FastAPI(title="ProofLoop", version="0.1.0")
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

    application.include_router(router)
    return application


app = create_app()
