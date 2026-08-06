"""Async WebSocket helper backing ``APIClient.stream_realtime_events``.

Kept in its own module (rather than inline in ``client.py``, which is
otherwise a purely synchronous ``httpx`` wrapper) so the one async
dependency this dashboard has — a bounded ``/ws/events`` listen, since
Streamlit reruns the whole script on every interaction rather than
holding a persistent connection open across reruns — stays isolated to
exactly the one call site that needs it.
"""

import asyncio
import json
from typing import Any

import websockets


async def listen_once(
    ws_url: str,
    access_token: str | None,
    event_type: list[str] | None,
    workflow_id: str | None,
    trace_id: str | None,
    agent_name: str | None,
    listen_seconds: float,
) -> list[dict[str, Any]]:
    """Connect, subscribe with the given filters, and collect events for ``listen_seconds``."""
    url = f"{ws_url}?token={access_token}" if access_token else ws_url
    events: list[dict[str, Any]] = []
    async with websockets.connect(url, open_timeout=5) as socket:
        await socket.send(
            json.dumps(
                {
                    "action": "subscribe",
                    "event_types": event_type or [],
                    "workflow_id": workflow_id,
                    "trace_id": trace_id,
                    "agent_name": agent_name,
                }
            )
        )
        loop = asyncio.get_event_loop()
        deadline = loop.time() + listen_seconds
        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                break
            try:
                raw = await asyncio.wait_for(socket.recv(), timeout=remaining)
            except TimeoutError:
                break
            message = json.loads(raw)
            if "event" in message:
                events.append(message)
    return events
