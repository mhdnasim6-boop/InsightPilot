"""Validates a SQLAgent invocation's own inputs before any service is called.

Deliberately shallow, mirroring ``backend.agents.file.validation``: this
never re-validates a connection's reachability (that's
``SQLDataSourceService``/``SQLConnector.validate()``'s job) — it only
checks that the caller gave SQLAgent enough to even attempt a run.
"""

from pydantic import ValidationError

from backend.agents.file.exceptions.errors import InvalidAgentInputError
from backend.datasource.sql.models.connection_config import SQLConnectionConfig
from backend.planning.models.step import ExecutionStep


def validate_agent_input(
    step: ExecutionStep, session_id: str | None
) -> tuple[SQLConnectionConfig, str | None, str | None]:
    """Check that ``step``/``session_id`` carry what SQLAgent needs to run.

    Returns ``(connection, table_name, query)`` — exactly one of
    ``table_name``/``query`` is non-``None``. Raises
    ``InvalidAgentInputError`` if the session is missing, ``connection``
    is missing or malformed, or ``table_name``/``query`` aren't given
    exactly-one-of.
    """
    if not session_id or not session_id.strip():
        raise InvalidAgentInputError(f"SQLAgent step '{step.step_id}' has no session_id.")

    raw_connection = step.inputs.get("connection")
    if not isinstance(raw_connection, dict):
        raise InvalidAgentInputError(
            f"SQLAgent step '{step.step_id}' is missing a 'connection' object in step.inputs."
        )
    try:
        connection = SQLConnectionConfig.model_validate(raw_connection)
    except ValidationError as exc:
        raise InvalidAgentInputError(
            f"SQLAgent step '{step.step_id}' has an invalid connection configuration: {exc}"
        ) from exc

    table_name = step.inputs.get("table_name")
    query = step.inputs.get("query")
    if bool(table_name) == bool(query):
        raise InvalidAgentInputError(
            f"SQLAgent step '{step.step_id}' must give exactly one of 'table_name' or 'query' in step.inputs."
        )

    return connection, table_name, query
