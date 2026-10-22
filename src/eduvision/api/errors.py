import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class AppError(Exception):
    """An error that maps to an HTTP status and the standard error body."""

    def __init__(
        self, status_code: int, code: str, message: str, analysis_id: str | None = None
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.analysis_id = analysis_id


def error_response(
    status_code: int, code: str, message: str, analysis_id: str | None = None
) -> JSONResponse:
    error = {"code": code, "message": message}
    if analysis_id is not None:  # only failed analyses carry an id
        error["analysis_id"] = analysis_id
    return JSONResponse(status_code=status_code, content={"error": error})


async def _handle_app_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    return error_response(exc.status_code, exc.code, exc.message, exc.analysis_id)


async def _handle_http_exception(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    code = "not_found" if exc.status_code == 404 else "http_error"
    return error_response(exc.status_code, code, str(exc.detail))


async def _handle_validation_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    details = "; ".join(
        f"{'.'.join(str(part) for part in err['loc'])}: {err['msg']}" for err in exc.errors()
    )
    return error_response(422, "validation_error", details)


async def _handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error", exc_info=exc)
    return error_response(500, "internal_error", "An unexpected error occurred.")


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _handle_app_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_exception)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(Exception, _handle_unexpected_error)
