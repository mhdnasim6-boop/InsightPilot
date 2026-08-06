"""Execution tests: SQLAgentNode adapting InsightPilotState <-> SQLAgentService.

Mirrors test_file_agent_node.py. Unit-level — no GraphBuilder/
ExecutionEngine involved (see test_sql_agent_graph.py for the full
graph-level integration).
"""

import asyncio
from pathlib import Path

from sqlalchemy import create_engine, text

from backend.agents.file.services.execution_result_store import (
    AgentExecutionResultStore,
)
from backend.agents.sql.execution.sql_agent import SQLAgent
from backend.agents.sql.services.sql_agent_service import SQLAgentService
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
from backend.orchestration.nodes.sql_agent_node import SQLAgentNode
from backend.orchestration.state.state import InsightPilotState
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
from backend.utils.ids import generate_id
from backend.utils.time import utc_now
from backend.visualization.charts.registry import default_generators
from backend.visualization.layouts.engine import LayoutEngine
from backend.visualization.recommendations.engine import ChartRecommendationEngine


def _make_node() -> SQLAgentNode:
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
    return SQLAgentNode(SQLAgentService(agent, AgentExecutionResultStore()))


def _make_database(path: Path) -> None:
    engine = create_engine(f"sqlite:///{path}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE t (a INTEGER, b INTEGER)"))
        connection.execute(text("INSERT INTO t VALUES (1, 2), (3, 4)"))
    engine.dispose()


def _new_state(**overrides: object) -> InsightPilotState:
    now = utc_now()
    defaults: dict[str, object] = {"execution_id": generate_id(), "created_at": now, "updated_at": now}
    defaults.update(overrides)
    return InsightPilotState.model_validate(defaults)


def test_execute_reads_connection_and_table_name_from_state_variables(tmp_path: Path) -> None:
    async def scenario() -> None:
        db_path = tmp_path / "test.db"
        _make_database(db_path)
        node = _make_node()
        state = _new_state(
            session_id="sess-1",
            variables={"connection": {"database_type": "sqlite", "database": str(db_path)}, "table_name": "t"},
        )

        updated = await node.execute(state)

        result = updated.artifacts["sql_agent_result"]
        assert result["status"] == "completed"
        assert result["dataset"]["row_count"] == 2
        assert updated.current_node == "sql_agent"
        assert updated.execution_trace == ["sql_agent"]
        assert updated.errors == []

    asyncio.run(scenario())


def test_execute_uses_step_id_from_state_metadata_when_present(tmp_path: Path) -> None:
    async def scenario() -> None:
        db_path = tmp_path / "test.db"
        _make_database(db_path)
        node = _make_node()
        state = _new_state(
            session_id="sess-1",
            variables={"connection": {"database_type": "sqlite", "database": str(db_path)}, "table_name": "t"},
            metadata={"step_id": "my-step-42"},
        )

        updated = await node.execute(state)

        assert updated.artifacts["sql_agent_result"]["step_id"] == "my-step-42"

    asyncio.run(scenario())


def test_execute_never_raises_when_input_is_missing() -> None:
    async def scenario() -> None:
        node = _make_node()
        state = _new_state()  # no session_id, no variables

        updated = await node.execute(state)  # must not raise

        result = updated.artifacts["sql_agent_result"]
        assert result["status"] == "failed"
        assert updated.errors
        assert updated.current_node == "sql_agent"

    asyncio.run(scenario())


def test_execute_never_raises_for_an_unreachable_database() -> None:
    async def scenario() -> None:
        node = _make_node()
        state = _new_state(
            session_id="sess-1",
            variables={
                "connection": {"database_type": "sqlite", "database": "/no/such/dir/nope.db"},
                "table_name": "t",
            },
        )

        updated = await node.execute(state)  # must not raise

        result = updated.artifacts["sql_agent_result"]
        assert result["status"] == "failed"
        assert updated.errors

    asyncio.run(scenario())


def test_execute_preserves_prior_artifacts_and_execution_trace(tmp_path: Path) -> None:
    async def scenario() -> None:
        db_path = tmp_path / "test.db"
        _make_database(db_path)
        node = _make_node()
        state = _new_state(
            session_id="sess-1",
            variables={"connection": {"database_type": "sqlite", "database": str(db_path)}, "table_name": "t"},
            artifacts={"earlier": "value"},
            execution_trace=["planner", "file_agent"],
        )

        updated = await node.execute(state)

        assert updated.artifacts["earlier"] == "value"
        assert updated.execution_trace == ["planner", "file_agent", "sql_agent"]

    asyncio.run(scenario())
