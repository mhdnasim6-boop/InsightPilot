"""SQLAgent: orchestrates the existing pipeline for one SQL-sourced ExecutionStep, via tools.

QueryDatabaseTool -> CleanDatasetTool -> AnalyzeDatasetTool ->
GenerateVisualizationTool -> optionally GenerateReportTool (Tool Layer,
Phase 22) — never a service directly, but each tool itself still wraps
exactly one already-existing, already-tested service. This class adds
no query execution, no connection handling, and no statistics/chart
logic of its own, exactly as before. ``QueryDatabaseTool`` already calls
``IngestionService.ingest_dataframe()`` internally (via
``SQLDataSourceService``), so SQLAgent never ingests a second time — doing
so would re-ingest the same DataFrame under a second dataset id. A
downstream tool failing partway through is captured as a FAILED
``AgentExecutionResult`` carrying whatever succeeded first — never an
uncaught exception. Only malformed *input* (see ``validate_agent_input``)
raises immediately.
"""

import time

from loguru import logger

from backend.agents.file.models.result import AgentExecutionResult
from backend.agents.sql.validation.input_validator import validate_agent_input
from backend.ingestion.registry.dataset_store import BusinessDatasetStore
from backend.orchestration.state.state import ExecutionStatus
from backend.planning.models.step import ExecutionStep
from backend.tools.execution.analyze_dataset_tool import AnalyzeDatasetTool
from backend.tools.execution.clean_dataset_tool import CleanDatasetTool
from backend.tools.execution.generate_report_tool import GenerateReportTool
from backend.tools.execution.generate_visualization_tool import (
    GenerateVisualizationTool,
)
from backend.tools.execution.query_database_tool import QueryDatabaseTool
from backend.tools.models.inputs import (
    AnalyzeDatasetInput,
    CleanDatasetInput,
    GenerateReportInput,
    GenerateVisualizationInput,
    QueryDatabaseInput,
)


class SQLAgent:
    """Orchestrates QueryDatabaseTool -> CleanDatasetTool -> AnalyzeDatasetTool ->
    GenerateVisualizationTool -> (optional) GenerateReportTool."""

    def __init__(
        self,
        query_database_tool: QueryDatabaseTool,
        clean_dataset_tool: CleanDatasetTool,
        analyze_dataset_tool: AnalyzeDatasetTool,
        generate_visualization_tool: GenerateVisualizationTool,
        generate_report_tool: GenerateReportTool,
        dataset_store: BusinessDatasetStore,
    ) -> None:
        self._query_database_tool = query_database_tool
        self._clean_dataset_tool = clean_dataset_tool
        self._analyze_dataset_tool = analyze_dataset_tool
        self._generate_visualization_tool = generate_visualization_tool
        self._generate_report_tool = generate_report_tool
        self._dataset_store = dataset_store

    async def execute(self, step: ExecutionStep, session_id: str | None) -> AgentExecutionResult:
        """Run the pipeline described by ``step`` for ``session_id``.

        Raises ``InvalidAgentInputError`` if ``step``/``session_id`` are
        malformed. Any failure from the pipeline itself (SQL import
        onward) is captured in the returned result's ``status``/
        ``warnings`` — this method never raises for that.
        """
        connection, table_name, query = validate_agent_input(step, session_id)
        generate_report = bool(step.inputs.get("generate_report", False))
        dataset_name = step.inputs.get("dataset_name")

        start = time.perf_counter()
        warnings: list[str] = []
        dataset = cleaning = analysis = visualization = report = None
        status = ExecutionStatus.COMPLETED

        try:
            dataset = await self._query_database_tool.execute(
                QueryDatabaseInput(
                    connection=connection, table_name=table_name, query=query, dataset_name=dataset_name
                )
            )
            self._dataset_store.put(dataset)

            cleaning = await self._clean_dataset_tool.execute(CleanDatasetInput(dataset=dataset))
            self._dataset_store.put(cleaning.dataset)

            analysis = await self._analyze_dataset_tool.execute(AnalyzeDatasetInput(cleaning_outcome=cleaning))

            visualization = await self._generate_visualization_tool.execute(
                GenerateVisualizationInput(analysis_result=analysis, dataset=cleaning.dataset)
            )

            if generate_report:
                report = await self._generate_report_tool.execute(
                    GenerateReportInput(
                        dataset=cleaning.dataset,
                        cleaning_outcome=cleaning,
                        analysis_result=analysis,
                        visualization_result=visualization,
                    )
                )
        except Exception as exc:  # noqa: BLE001 - any pipeline stage's failure degrades to a FAILED result, not a crash
            logger.exception("SQLAgent step '{}' failed", step.step_id)
            warnings.append(str(exc))
            status = ExecutionStatus.FAILED

        execution_time = time.perf_counter() - start
        return AgentExecutionResult(
            step_id=step.step_id,
            status=status,
            dataset=dataset,
            cleaning=cleaning,
            analysis=analysis,
            visualization=visualization,
            report=report,
            warnings=warnings,
            execution_time=execution_time,
            metadata={
                "session_id": session_id,
                "database_type": connection.database_type.value,
                "host": connection.host,
                "database": connection.database,
                "table_name": table_name,
                "query": query,
            },
        )
