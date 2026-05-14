"""Global exception handlers — every error path produces the same envelope shape
so clients can parse uniformly regardless of which layer raised.

The envelope is `{error, status, timestamp}` for every response, with an
additional `errors` array on 422 validation responses for per-field detail.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.exceptions import AppException


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=exc.to_dict())


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException,
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=AppException(str(exc.detail), exc.status_code).to_dict(),
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError,
) -> JSONResponse:
    # input/ctx dropped from per-field errors to avoid leaking submitted data
    # (e.g. attempted passwords) back into the error response.
    return JSONResponse(
        status_code=422,
        content={
            "error": "Validation failed",
            "status": 422,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "errors": [
                {"type": e["type"], "loc": e["loc"], "msg": e["msg"]}
                for e in exc.errors()
            ],
        },
    )


async def rate_limit_exception_handler(
    request: Request, exc: RateLimitExceeded,
) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content=AppException(f"Rate limit exceeded: {exc.detail}", 429).to_dict(),
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Wire all global exception handlers onto the FastAPI app."""
    app.add_exception_handler(AppException, app_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RateLimitExceeded, rate_limit_exception_handler)  # type: ignore[arg-type]
