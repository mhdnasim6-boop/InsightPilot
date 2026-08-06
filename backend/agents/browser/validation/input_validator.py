"""Collects BrowserAgent's search queries from a step's own inputs.

Deliberately tolerant of *absence*: a step carrying none of
``search_request``/``companies``/``industries``/``products``/
``keywords`` is not malformed — most plan steps have nothing to search
for (every step currently triggers the whole graph, so BrowserAgentNode
runs even for a File- or SQL-only step; see ``default_graph.py``). That
case returns an empty list; ``BrowserAgent.execute()`` treats an empty
list as "gracefully skip", never raises, and never fails. Only a
*present but malformed* field (wrong type, or a missing session) raises
``InvalidAgentInputError``.
"""

from backend.agents.file.exceptions.errors import InvalidAgentInputError
from backend.planning.models.step import ExecutionStep

_LIST_FIELDS = ("companies", "industries", "products", "keywords")


def validate_agent_input(step: ExecutionStep, session_id: str | None) -> list[str]:
    """Return every distinct, non-empty search query this step asks BrowserAgent to run.

    Returns ``[]`` if the step carries no browser-relevant input at
    all — the caller must treat that as "nothing to search", not an
    error. Raises ``InvalidAgentInputError`` if the session is missing,
    or a present field is not the shape it claims to be.
    """
    if not session_id or not session_id.strip():
        raise InvalidAgentInputError(f"BrowserAgent step '{step.step_id}' has no session_id.")

    queries: list[str] = []

    search_request = step.inputs.get("search_request")
    if search_request is not None:
        if not isinstance(search_request, str) or not search_request.strip():
            raise InvalidAgentInputError(
                f"BrowserAgent step '{step.step_id}' has a 'search_request' that is not a non-empty string."
            )
        queries.append(search_request.strip())

    for field_name in _LIST_FIELDS:
        raw = step.inputs.get(field_name)
        if raw is None:
            continue
        if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
            raise InvalidAgentInputError(
                f"BrowserAgent step '{step.step_id}' has a '{field_name}' field that is not a list of strings."
            )
        queries.extend(item.strip() for item in raw if item.strip())

    seen: set[str] = set()
    unique_queries: list[str] = []
    for query in queries:
        if query not in seen:
            seen.add(query)
            unique_queries.append(query)
    return unique_queries
