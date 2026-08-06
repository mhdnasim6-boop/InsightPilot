"""Correlation context for tracing: which trace/agent a tool call or AI call
currently belongs to, without threading new parameters through every
intervening method signature.

``contextvars.ContextVar`` (not a global/thread-local) because it is the
standard mechanism for cross-cutting async correlation — it survives
``await`` boundaries within one asyncio task, and ``asyncio.create_task()``
copies the current context into the new task by default, so a value set
before ``ExecutionEngine.run()`` calls ``asyncio.create_task(self._invoke(...))``
is still visible inside every node/tool/AI call the graph run makes.
This is the exact mechanism OpenTelemetry itself uses for span context.

Two seams set these: ``PlanExecutor`` sets ``current_trace_id`` for the
duration of a step; ``GraphBuilder._wrap()`` sets ``current_agent_name``
for the duration of one node's ``execute()`` call. Everything else
(``TracingTool``, ``AIService``) only ever reads them.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

current_trace_id: ContextVar[str | None] = ContextVar("current_trace_id", default=None)
current_agent_name: ContextVar[str | None] = ContextVar("current_agent_name", default=None)


@contextmanager
def trace_context(trace_id: str | None) -> Iterator[None]:
    """Set ``current_trace_id`` for the duration of the ``with`` block, then restore it."""
    token = current_trace_id.set(trace_id)
    try:
        yield
    finally:
        current_trace_id.reset(token)


@contextmanager
def agent_context(agent_name: str | None) -> Iterator[None]:
    """Set ``current_agent_name`` for the duration of the ``with`` block, then restore it."""
    token = current_agent_name.set(agent_name)
    try:
        yield
    finally:
        current_agent_name.reset(token)
