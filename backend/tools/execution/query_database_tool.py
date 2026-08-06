"""QueryDatabaseTool: wraps SQLDataSourceService.import_table()/.import_query() — nothing else.

The table-vs-query branch (and the query-mode default dataset name) is
moved verbatim from SQLAgent's own ``execute()`` — the same translation
logic, just relocated into the tool that now owns the one service call.
The exactly-one-of validation itself stays in SQLAgent's own
``validate_agent_input`` and is never duplicated here.
"""

from backend.ingestion.models.dataset import BusinessDataset
from backend.services.sql_data_source_service import SQLDataSourceService
from backend.tools.base.tool import Tool
from backend.tools.models.inputs import QueryDatabaseInput

_DEFAULT_QUERY_DATASET_NAME = "sql_import"


class QueryDatabaseTool(Tool[QueryDatabaseInput, BusinessDataset]):
    """Imports a table or a custom query's result from a SQL connection into a BusinessDataset."""

    name = "query_database"
    description = "Import a table or run a custom query against a SQL connection, wrapped into a BusinessDataset."
    input_model = QueryDatabaseInput
    output_model = BusinessDataset

    def __init__(self, sql_data_source_service: SQLDataSourceService) -> None:
        self._sql_data_source_service = sql_data_source_service

    async def execute(self, tool_input: QueryDatabaseInput) -> BusinessDataset:
        if tool_input.table_name is not None:
            return self._sql_data_source_service.import_table(
                tool_input.connection, tool_input.table_name, dataset_name=tool_input.dataset_name
            )
        assert tool_input.query is not None  # guaranteed by SQLAgent's own exactly-one-of validation
        return self._sql_data_source_service.import_query(
            tool_input.connection, tool_input.query, dataset_name=tool_input.dataset_name or _DEFAULT_QUERY_DATASET_NAME
        )
