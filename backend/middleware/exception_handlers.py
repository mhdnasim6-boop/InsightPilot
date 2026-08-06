"""Global exception handling.

FastAPI's ``add_exception_handler`` mechanism (rather than a hand-rolled ASGI
middleware) is the idiomatic way to guarantee every error — InsightPilot's
own domain exceptions, expected HTTP errors, request validation errors, and
truly unhandled exceptions — is converted into the same JSON envelope
(:class:`ErrorResponse`).

``model_dump(mode="json")`` (not plain ``model_dump()``) is used throughout
so nested non-JSON-native types (e.g. ``datetime``) serialize correctly —
``JSONResponse`` does its own ``json.dumps`` and won't do that conversion
for us the way FastAPI's automatic response-model serialization does.
"""

from typing import cast

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ExceptionHandler

from backend.core.exceptions import InsightPilotError
from backend.schemas.errors import ErrorDetail, ErrorResponse


async def application_exception_handler(request: Request, exc: InsightPilotError) -> JSONResponse:
    """Handle InsightPilot's own domain exceptions (NotFoundError, ValidationError, ...)."""
    logger.warning("{} at {}: {}", exc.error_type, request.url.path, exc.message)
    body = ErrorResponse(
        message=exc.message,
        errors=ErrorDetail(
            type=exc.error_type,
            status_code=exc.status_code,
            path=request.url.path,
            detail=exc.detail,
        ),
    )
    return JSONResponse(status_code=exc.status_code, content=body.model_dump(mode="json"))


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Handle raised ``HTTPException``s with the standard error envelope."""
    logger.warning("HTTPException {} at {}: {}", exc.status_code, request.url.path, exc.detail)
    body = ErrorResponse(
        message=str(exc.detail),
        errors=ErrorDetail(type=type(exc).__name__, status_code=exc.status_code, path=request.url.path),
    )
    return JSONResponse(status_code=exc.status_code, content=body.model_dump(mode="json"))


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle request validation failures (HTTP 422)."""
    logger.warning("Validation error at {}: {}", request.url.path, exc.errors())
    body = ErrorResponse(
        message="Request validation failed.",
        errors=ErrorDetail(
            type="ValidationError",
            status_code=422,
            path=request.url.path,
            detail=jsonable_encoder(exc.errors()),
        ),
    )
    return JSONResponse(status_code=422, content=body.model_dump(mode="json"))


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for any exception not otherwise handled (HTTP 500)."""
    logger.exception("Unhandled exception at {}", request.url.path)
    body = ErrorResponse(
        message="An unexpected error occurred.",
        errors=ErrorDetail(type="InternalServerError", status_code=500, path=request.url.path),
    )
    return JSONResponse(status_code=500, content=body.model_dump(mode="json"))


def register_exception_handlers(app: FastAPI) -> None:
    """Attach the global exception handlers to the given FastAPI app.

    Starlette's ``add_exception_handler`` dispatches by the exception type
    given as its first argument, so each handler below only ever receives
    the specific exception type its own signature declares — that's safe
    at runtime, but Starlette's stub type for the second argument is the
    general ``ExceptionHandler`` (parameterized on ``Exception``), which
    mypy can't narrow automatically. The ``cast`` calls tell mypy that
    without widening the handlers' own signatures away from their precise,
    self-documenting exception types.
    """
    app.add_exception_handler(InsightPilotError, cast(ExceptionHandler, application_exception_handler))
    app.add_exception_handler(StarletteHTTPException, cast(ExceptionHandler, http_exception_handler))
    app.add_exception_handler(RequestValidationError, cast(ExceptionHandler, validation_exception_handler))
    app.add_exception_handler(Exception, unhandled_exception_handler)
