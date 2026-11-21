"""The Data Analyst's tools. Calculations happen in DuckDB; the LLM only chooses the query."""
from __future__ import annotations

import json

from langchain_core.tools import tool

from ..data.sql_guard import UnsafeSQLError
from ..data.store import DatasetStore, SQLExecutionError


def make_sql_tools(store: DatasetStore, dataset_id: str):
    @tool
    def get_schema() -> str:
        """Return the table name (always `data`), the row count, and every column with its type and sample values. Call this before writing SQL."""
        return json.dumps(store.schema(dataset_id), default=str)

    @tool
    def run_sql(sql: str) -> str:
        """Run ONE read-only DuckDB SELECT query against the table `data` and return the result as JSON.
        Only SELECT is allowed. Quote column names with double quotes if needed.
        On failure the JSON contains an 'error' message; read it, fix the query and try again."""
        try:
            result = store.query(dataset_id, sql)
            return json.dumps({"ok": True, **result}, default=str)
        except UnsafeSQLError as exc:
            return json.dumps({"ok": False, "error": f"Rejected: {exc}"})
        except SQLExecutionError as exc:
            return json.dumps({"ok": False, "error": str(exc)[:400]})

    return [get_schema, run_sql]
