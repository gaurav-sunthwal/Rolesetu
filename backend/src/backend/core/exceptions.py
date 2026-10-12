"""Domain exceptions. Every module raises these, never raw HTTPException,
so the mapping from "what went wrong" to an HTTP response lives in one place.
"""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base for all domain errors. status_code is the HTTP response to map to."""

    status_code: int = 500
    detail: str = "Internal server error"

    def __init__(self, detail: str | None = None) -> None:
        if detail:
            self.detail = detail
        super().__init__(self.detail)


class NotFoundError(AppError):
    status_code = 404
    detail = "Resource not found"


class ForbiddenError(AppError):
    status_code = 403
    detail = "Forbidden"


class UnauthorizedError(AppError):
    status_code = 401
    detail = "Unauthorized"


class ConflictError(AppError):
    status_code = 409
    detail = "Conflict"


class RateLimitedError(AppError):
    status_code = 429
    detail = "Too many requests. Please try again later."


class ValidationFailedError(AppError):
    status_code = 422
    detail = "Validation failed"


# What a field is called when telling a person it was wrong.
_FIELD_NAMES = {
    "jd_text": "The job description",
    "url": "The link",
    "role": "The job title",
    "company": "The company name",
    "skills": "The list of skills",
    "name": "A skill name",
    "headline": "The headline",
    "file": "The file",
}


def describe_validation(errors: list[dict[str, Any]]) -> str:
    """One sentence for a request the API refused, in place of the framework's
    list of error objects (which no screen can show as it is).
    """
    if not errors:
        return "That request was not understood. Please try again."
    first = errors[0]
    message = str(first.get("msg", "")).removeprefix("Value error, ")
    kind = str(first.get("type", ""))
    if kind == "value_error" and message:
        return message  # written by us, for people
    field = next(
        (str(part) for part in reversed(first.get("loc", ())) if isinstance(part, str)), ""
    )
    subject = _FIELD_NAMES.get(field, "Part of that request")
    limit = (first.get("ctx") or {}).get("max_length") or (first.get("ctx") or {}).get("min_length")
    if kind in ("string_too_long", "too_long"):
        return f"{subject} is too long (the limit is {limit})."
    if kind in ("string_too_short", "too_short"):
        return f"{subject} is too short (it needs at least {limit})."
    if kind == "missing":
        return f"{subject} is missing."
    return f"{subject} is not valid. Please check it and try again."


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(RequestValidationError)
    async def handle_bad_request(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [dict(error) for error in exc.errors()]
        logger.warning("Request refused: %s", [(e.get("loc"), e.get("type")) for e in errors])
        return JSONResponse(status_code=422, content={"detail": describe_validation(errors)})

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        """A bug. The person is told plainly and nothing internal is shown; the
        full error goes to the log, where it can be fixed.
        """
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={
                "detail": (
                    "Something went wrong on our side, not yours. Please try again in a moment."
                )
            },
        )
