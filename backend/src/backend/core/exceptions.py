"""Domain exceptions. Every module raises these, never raw HTTPException,
so the mapping from "what went wrong" to an HTTP response lives in one place.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


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


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
