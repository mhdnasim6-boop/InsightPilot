"""RequestContextMiddleware: establishes a correlation id for every
request — read from an incoming ``X-Request-ID`` header if the caller
already has one (letting a gateway/load balancer propagate its own),
generated fresh otherwise. Mirrors ``backend.observability.context``'s
own ``ContextVar``-based correlation pattern (Phase 24) exactly: a
``ContextVar`` survives ``await`` boundaries within one asyncio task,
which is what lets any code deeper in the request — without threading a
new parameter through every intervening call — read
``current_request_id.get()`` and see the same id AuditService ultimately
records.

The outermost middleware (added last in ``backend.main.create_app()``,
which Starlette runs first — confirmed empirically, not assumed): every
other middleware and the route handler itself run inside this one's
``with`` scope, so they all see the same id.
"""

from collections.abc import Awaitable, Callable
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from backend.utils.ids import generate_id

current_request_id: ContextVar[str | None] = ContextVar("current_request_id", default=None)

_HEADER_NAME = "X-Request-ID"


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Sets a correlation id (``request.state.request_id`` + ``current_request_id``) for the
    duration of one request, and echoes it back in the response's own ``X-Request-ID`` header."""

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        request_id = request.headers.get(_HEADER_NAME) or generate_id()
        request.state.request_id = request_id
        token = current_request_id.set(request_id)
        try:
            response = await call_next(request)
        finally:
            current_request_id.reset(token)
        response.headers[_HEADER_NAME] = request_id
        return response
