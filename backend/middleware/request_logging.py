"""ASGI middleware that logs every request's method, path, status, and duration."""

import time

from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs one line per request: method, path, response status, and latency."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start_time = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start_time) * 1000

        logger.info(
            "{} {} -> {} ({:.2f}ms)",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response
