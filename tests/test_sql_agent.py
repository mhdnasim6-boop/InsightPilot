"""Agent tests: SQLAgent orchestrating the real pipeline for one ExecutionStep.

Mirrors test_file_agent.py exactly. SQLAgent never builds a connection,
runs a query, cleans a DataFrame, computes a statistic, or renders a
chart — every assertion here checks that it correctly sequenced calls
into the real (not mocked) SQLDataSourceService/Cleaning/Analysis/
Visualization/Report services, never that it computed anything itself.
Uses a real, temporary SQLite database; PostgreSQL/MySQL are exercised
only via a deliberately unreachable host (no external server needed),
mirroring test_sql_connectors.py's own established pattern.
"""

import asyncio
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from backend.agents.file.exceptions.errors import InvalidAgentInputError
from backend.agents.sql.execution.sql_agent import SQLAgent
from backend.analysis.aggregations.engine import AggregationEngine
from backend.analysis.anomalies.engine import AnomalyEngine
from backend.analysis.correlations.engine import CorrelationEngine
from backend.analysis.insights.engine import InsightEngine
from backend.analysis.kpis.engine import KPIEngine
from backend.analysis.statistics.engine import DescriptiveStatisticsEngine
from backend.analysis.trends.engine import TrendEngine
from backend.cleaning.profiling.profiler import DatasetProfilingService
from backend.datasource.sql.registry.connector_registry import ConnectorRegistry
from backend.ingestion.metadata.extractor import MetadataExtractor
from backend.ingestion.registry.dataframe_store import DataFrameStore
from backend.ingestion.registry.dataset_store import BusinessDatasetStore
from backend.ingestion.registry.loader_registry import LoaderRegistry
from backend.ingestion.validators.validator import DatasetValidator
from backend.orchestration.state.state import ExecutionStatus
from backend.planning.models.step import ExecutionStep
from backend.reporting.builders.report_builder import ReportBuilder
from backend.reporting.report_store import ReportStore
from backend.reporting.validation.validator import ReportValidator
from backend.services.analysis_service import AnalysisService
from backend.services.cleaning_service import CleaningService
from backend.services.ingestion_service import IngestionService
from backend.services.report_service import ReportService
from backend.services.sql_data_source_service import SQLDataSourceService
from backend.services.visualization_service import VisualizationService
from backend.tools.execution.analyze_dataset_tool import AnalyzeDatasetTool
from backend.tools.execution.clean_dataset_tool import CleanDatasetTool
from backend.tools.execution.generate_report_tool import GenerateReportTool
from backend.tools.execution.generate_visualization_tool import (
    GenerateVisualizationTool,
)
from backend.tools.execution.query_database_tool import QueryDatabaseTool
from backend.visualization.charts.registry import default_generators
from backend.visualization.layouts.engine import LayoutEngine
from backend.visualization.recommendations.engine import ChartRecommendationEngine

_UNREACHABLE_HOST = "127.0.0.1"
_UNREACHABLE_PORT = 1  # nothing listens here; connection is refused near-instantly


def _make_agent() -> tuple[SQLAgent, BusinessDatasetStore]:
    dataframe_store = DataFrameStore()
    extractor = MetadataExtractor()
    dataset_store = BusinessDatasetStore()
    ingestion_service = IngestionService(LoaderRegistry(), DatasetValidator(), extractor, dataframe_store)
    sql_data_source_service = SQLDataSourceService(ConnectorRegistry(), ingestion_service)
    cleaning_service = CleaningService(
        ingestion_service, DatasetProfilingService(extractor), extractor, dataframe_store
    )
    aggregation_engine = AggregationEngine()
    analysis_service = AnalysisService(
        ingestion_service,
        DescriptiveStatisticsEngine(),
        KPIEngine(),
        TrendEngine(),
        CorrelationEngine(),
        AnomalyEngine(),
        InsightEngine(aggregation_engine),
    )
    visualization_service = VisualizationService(
        ingestion_service, ChartRecommendationEngine(default_generators(aggregation_engine)), LayoutEngine()
    )
    report_service = ReportService(ReportBuilder(), ReportValidator(), ReportStore())
    agent = SQLAgent(
        QueryDatabaseTool(sql_data_source_service),
        CleanDatasetTool(cleaning_service),
        AnalyzeDatasetTool(analysis_service),
        GenerateVisualizationTool(visualization_service),
        GenerateReportTool(report_service),
        dataset_store,
    )
    return agent, dataset_store


def _make_database(path: Path) -> None:
    engine = create_engine(f"sqlite:///{path}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE sales (id INTEGER PRIMARY KEY, region TEXT, revenue REAL)"))
        connection.execute(
            text(
                "INSERT INTO sales VALUES (1, 'East', 1000), (2, 'West', 200), "
                "(3, 'East', 1100), (4, 'West', 9000)"
            )
        )
    engine.dispose()


def _sqlite_connection(path: Path) -> dict:
    return {"database_type": "sqlite", "database": str(path)}


def _step(
    connection: dict,
    table_name: str | None = None,
    query: str | None = None,
    generate_report: bool = False,
    dataset_name: str | None = None,
    step_id: str = "s1",
) -> ExecutionStep:
    inputs: dict[str, object] = {"connection": connection, "generate_report": generate_report}
    if table_name is not None:
        inputs["table_name"] = table_name
    if query is not None:
        inputs["query"] = query
    if dataset_name is not None:
        inputs["dataset_name"] = dataset_name
    return ExecutionStep(step_id=step_id, name="SQL Agent Run", node_name="sql_agent", inputs=inputs)


def test_execute_via_table_name_runs_the_full_pipeline_and_registers_datasets(tmp_path: Path) -> None:
    async def scenario() -> None:
        db_path = tmp_path / "test.db"
        _make_database(db_path)
        agent, dataset_store = _make_agent()

        result = await agent.execute(
            _step(_sqlite_connection(db_path), table_name="sales", generate_report=True), session_id="sess-1"
        )

        assert result.status == ExecutionStatus.COMPLETED
        assert result.warnings == []
        assert result.dataset is not None and result.dataset.row_count == 4
        assert result.cleaning is not None
        assert result.analysis is not None and len(result.analysis.kpis) > 0
        assert result.visualization is not None
        assert result.report is not None and result.report.sections
        assert result.execution_time >= 0.0
        assert result.metadata["session_id"] == "sess-1"
        assert result.metadata["database_type"] == "sqlite"
        assert result.metadata["table_name"] == "sales"
        assert result.metadata["query"] is None
        assert "password" not in result.metadata  # never leak a credential into a stored result

        assert dataset_store.get(result.dataset.dataset_id) is not None
        assert dataset_store.get(result.cleaning.dataset.dataset_id) is not None

    asyncio.run(scenario())


def test_execute_via_query_runs_the_full_pipeline(tmp_path: Path) -> None:
    async def scenario() -> None:
        db_path = tmp_path / "test.db"
        _make_database(db_path)
        agent, _ = _make_agent()

        query = "SELECT region, SUM(revenue) AS total FROM sales GROUP BY region"
        result = await agent.execute(
            _step(_sqlite_connection(db_path), query=query, dataset_name="region_totals"), session_id="sess-1"
        )

        assert result.status == ExecutionStatus.COMPLETED
        assert result.dataset is not None and result.dataset.row_count == 2
        assert result.dataset.dataset_name == "region_totals"
        assert result.metadata["query"] == query
        assert result.metadata["table_name"] is None

    asyncio.run(scenario())


def test_execute_without_generate_report_leaves_report_none(tmp_path: Path) -> None:
    async def scenario() -> None:
        db_path = tmp_path / "test.db"
        _make_database(db_path)
        agent, _ = _make_agent()

        result = await agent.execute(_step(_sqlite_connection(db_path), table_name="sales"), session_id="sess-1")

        assert result.status == ExecutionStatus.COMPLETED
        assert result.report is None

    asyncio.run(scenario())


def test_execute_raises_for_missing_session_id(tmp_path: Path) -> None:
    async def scenario() -> None:
        db_path = tmp_path / "test.db"
        agent, _ = _make_agent()

        with pytest.raises(InvalidAgentInputError):
            await agent.execute(_step(_sqlite_connection(db_path), table_name="sales"), session_id=None)

    asyncio.run(scenario())


def test_execute_raises_for_missing_connection() -> None:
    async def scenario() -> None:
        agent, _ = _make_agent()
        step = ExecutionStep(step_id="s1", name="Bad", node_name="sql_agent", inputs={"table_name": "sales"})

        with pytest.raises(InvalidAgentInputError):
            await agent.execute(step, session_id="sess-1")

    asyncio.run(scenario())


def test_execute_raises_for_an_invalid_connection() -> None:
    async def scenario() -> None:
        agent, _ = _make_agent()
        step = ExecutionStep(
            step_id="s1",
            name="Bad",
            node_name="sql_agent",
            inputs={"connection": {"database_type": "not-a-real-dialect"}, "table_name": "sales"},
        )

        with pytest.raises(InvalidAgentInputError):
            await agent.execute(step, session_id="sess-1")

    asyncio.run(scenario())


def test_execute_raises_when_neither_table_name_nor_query_given(tmp_path: Path) -> None:
    async def scenario() -> None:
        db_path = tmp_path / "test.db"
        agent, _ = _make_agent()
        step = ExecutionStep(
            step_id="s1", name="Bad", node_name="sql_agent", inputs={"connection": _sqlite_connection(db_path)}
        )

        with pytest.raises(InvalidAgentInputError):
            await agent.execute(step, session_id="sess-1")

    asyncio.run(scenario())


def test_execute_raises_when_both_table_name_and_query_given(tmp_path: Path) -> None:
    async def scenario() -> None:
        db_path = tmp_path / "test.db"
        agent, _ = _make_agent()

        with pytest.raises(InvalidAgentInputError):
            await agent.execute(
                _step(_sqlite_connection(db_path), table_name="sales", query="SELECT 1"), session_id="sess-1"
            )

    asyncio.run(scenario())


def test_execute_on_an_unreachable_sqlite_path_returns_a_failed_result_not_a_raise() -> None:
    async def scenario() -> None:
        agent, dataset_store = _make_agent()

        result = await agent.execute(
            _step({"database_type": "sqlite", "database": "/no/such/dir/nope.db"}, table_name="sales"),
            session_id="sess-1",
        )

        assert result.status == ExecutionStatus.FAILED
        assert result.warnings
        assert result.dataset is None
        assert dataset_store.list() == []

    asyncio.run(scenario())


def test_execute_on_an_unreachable_postgres_host_returns_a_failed_result() -> None:
    """No real PostgreSQL server needed — connecting to a deliberately
    unreachable port fails fast and exercises the real psycopg2/SQLAlchemy
    error path, the same technique test_sql_connectors.py already uses."""

    async def scenario() -> None:
        agent, _ = _make_agent()
        connection = {
            "database_type": "postgresql",
            "host": _UNREACHABLE_HOST,
            "port": _UNREACHABLE_PORT,
            "database": "db",
            "username": "user",
            "password": "pass",
            "timeout": 2,
        }

        result = await agent.execute(_step(connection, table_name="sales"), session_id="sess-1")

        assert result.status == ExecutionStatus.FAILED
        assert result.warnings
        assert result.metadata["database_type"] == "postgresql"
        assert "pass" not in str(result.metadata)  # the password must never end up in a stored result

    asyncio.run(scenario())


def test_execute_on_cleaning_failure_still_returns_the_dataset_that_succeeded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def scenario() -> None:
        db_path = tmp_path / "test.db"
        _make_database(db_path)
        agent, dataset_store = _make_agent()

        class _BoomTool:
            async def execute(self, tool_input: object) -> None:
                raise RuntimeError("simulated cleaning failure")

        monkeypatch.setattr(agent, "_clean_dataset_tool", _BoomTool())

        result = await agent.execute(_step(_sqlite_connection(db_path), table_name="sales"), session_id="sess-1")

        assert result.status == ExecutionStatus.FAILED
        assert "simulated cleaning failure" in result.warnings[0]
        assert result.dataset is not None  # the SQL import had already succeeded
        assert result.cleaning is None
        assert dataset_store.get(result.dataset.dataset_id) is not None

    asyncio.run(scenario())
