"""Unit tests for app.exception_handlers.

Locks the API error envelope contract: every handler must return a
JSONResponse with the `{error, status, timestamp}` shape (plus an `errors`
array on 422 validation responses).

The validation handler's stripping of `input` and `ctx` from per-field errors
is a security-flavored decision — these tests fail loudly if a future change
re-exposes attempted form data (e.g. submitted passwords).
"""

import json
from unittest.mock import Mock

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.exception_handlers import (
    app_exception_handler,
    http_exception_handler,
    rate_limit_exception_handler,
    validation_exception_handler,
)
from app.exceptions import AppException, MixNotFoundException


def _body(response: JSONResponse) -> dict[str, object]:
    """Parse a JSONResponse body into a dict."""
    return json.loads(response.body)


def _dummy_request() -> Request:
    """Stub Request — handlers don't use it but the signature requires one."""
    return Mock(spec=Request)


class TestAppExceptionHandler:
    async def test_returns_envelope_for_base_app_exception(self):
        # ARRANGE
        exc = AppException("oops", 500)

        # ACT
        response = await app_exception_handler(_dummy_request(), exc)

        # ASSERT
        assert response.status_code == 500
        body = _body(response)
        assert body["error"] == "oops"
        assert body["status"] == 500
        assert "timestamp" in body

    async def test_returns_envelope_for_subclass(self):
        """AppException subclasses (e.g. MixNotFoundException) flow through
        the same handler with their specific status and message."""
        # ARRANGE
        exc = MixNotFoundException("abc-123")

        # ACT
        response = await app_exception_handler(_dummy_request(), exc)

        # ASSERT
        assert response.status_code == 404
        body = _body(response)
        assert "abc-123" in str(body["error"])
        assert body["status"] == 404


class TestHTTPExceptionHandler:
    async def test_normalizes_http_exception_to_envelope(self):
        # ARRANGE
        exc = StarletteHTTPException(status_code=404, detail="Not found")

        # ACT
        response = await http_exception_handler(_dummy_request(), exc)

        # ASSERT
        assert response.status_code == 404
        body = _body(response)
        assert body["error"] == "Not found"
        assert body["status"] == 404
        assert "timestamp" in body

    async def test_preserves_status_code(self):
        # ARRANGE
        exc = StarletteHTTPException(status_code=403, detail="Forbidden")

        # ACT
        response = await http_exception_handler(_dummy_request(), exc)

        # ASSERT
        assert response.status_code == 403
        assert _body(response)["status"] == 403


class TestValidationExceptionHandler:
    async def test_returns_envelope_with_per_field_errors(self):
        # ARRANGE
        raw: list[dict[str, object]] = [
            {
                "type": "missing",
                "loc": ("body", "email"),
                "msg": "Field required",
            },
        ]
        exc = RequestValidationError(raw)

        # ACT
        response = await validation_exception_handler(_dummy_request(), exc)

        # ASSERT
        assert response.status_code == 422
        body = _body(response)
        assert body["error"] == "Validation failed"
        assert body["status"] == 422
        assert "timestamp" in body
        assert body["errors"] == [
            {"type": "missing", "loc": ["body", "email"], "msg": "Field required"},
        ]

    async def test_strips_input_and_ctx_to_avoid_leaking_submitted_data(self):
        """Critical security test: attempted form data (e.g. passwords) must
        never echo back in error responses. Regression of this stripping must
        fail loudly."""
        # ARRANGE
        raw: list[dict[str, object]] = [
            {
                "type": "missing",
                "loc": ("body", "password"),
                "msg": "Field required",
                "input": {"password": "attempted_secret"},
                "ctx": {"some": "context"},
            },
        ]
        exc = RequestValidationError(raw)

        # ACT
        response = await validation_exception_handler(_dummy_request(), exc)

        # ASSERT - structural: input/ctx keys must not appear in errors
        body = _body(response)
        assert "input" not in body["errors"][0]  # type: ignore[index]
        assert "ctx" not in body["errors"][0]  # type: ignore[index]
        # ASSERT - defense in depth: the literal sensitive value must not
        # appear anywhere in the serialized response.
        assert "attempted_secret" not in json.dumps(body)


class TestRateLimitExceptionHandler:
    async def test_returns_429_envelope(self):
        # ARRANGE - bypass slowapi's __init__ which requires a Limit object
        exc = RateLimitExceeded.__new__(RateLimitExceeded)
        exc.detail = "10 per 1 hour"

        # ACT
        response = await rate_limit_exception_handler(_dummy_request(), exc)

        # ASSERT
        assert response.status_code == 429
        body = _body(response)
        assert body["status"] == 429
        assert "Rate limit exceeded" in str(body["error"])
        assert "10 per 1 hour" in str(body["error"])
        assert "timestamp" in body
