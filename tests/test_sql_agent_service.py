"""Tests for SQLAgentService: execute_step stores results; get_result/list_results
fetch them. Mirrors test_file_agent_service.py.
"""

import asyncio
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from backend.agents.file.exceptions.errors import AgentExecutionNotFoundError
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


def _make_service() -> SQLAgentService:
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
    return SQLAgentService(agent, AgentExecutionResultStore())


def _make_database(path: Path) -> None:
    engine = create_engine(f"sqlite:///{path}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE t (a INTEGER, b INTEGER)"))
        connection.execute(text("INSERT INTO t VALUES (1, 2), (3, 4)"))
    engine.dispose()


def _step(db_path: Path, step_id: str) -> ExecutionStep:
    return ExecutionStep(
        step_id=step_id,
        name="Run",
        node_name="sql_agent",
        inputs={"connection": {"database_type": "sqlite", "database": str(db_path)}, "table_name": "t"},
    )


def test_execute_step_stores_and_returns_the_same_result(tmp_path: Path) -> None:
    async def scenario() -> None:
        db_path = tmp_path / "test.db"
        _make_database(db_path)
        service = _make_service()

        result = await service.execute_step(_step(db_path, "s1"), session_id="sess-1")

        assert result.status == ExecutionStatus.COMPLETED
        assert service.get_result("s1") == result

    asyncio.run(scenario())


def test_get_result_raises_for_an_unknown_step_id() -> None:
    service = _make_service()
    with pytest.raises(AgentExecutionNotFoundError):
        service.get_result("never-ran")


def test_list_results_returns_most_recent_first(tmp_path: Path) -> None:
    async def scenario() -> None:
        db_path = tmp_path / "test.db"
        _make_database(db_path)
        service = _make_service()

        first = await service.execute_step(_step(db_path, "s1"), session_id="sess-1")
        second = await service.execute_step(_step(db_path, "s2"), session_id="sess-1")

        listed = service.list_results()
        assert listed[0].step_id == second.step_id
        assert listed[1].step_id == first.step_id

    asyncio.run(scenario())


def test_execute_step_overwrites_a_result_for_a_repeated_step_id(tmp_path: Path) -> None:
    async def scenario() -> None:
        db_path = tmp_path / "test.db"
        _make_database(db_path)
        service = _make_service()

        await service.execute_step(_step(db_path, "s1"), session_id="sess-1")
        await service.execute_step(_step(db_path, "s1"), session_id="sess-2")

        assert service.get_result("s1").metadata["session_id"] == "sess-2"
        assert len(service.list_results()) == 1

    asyncio.run(scenario())
