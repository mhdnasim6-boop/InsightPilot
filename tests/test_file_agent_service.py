"""Tests for FileAgentService: execute_step stores results; get_result/list_results fetch them."""

import asyncio
from pathlib import Path

import pytest

from backend.agents.file.exceptions.errors import AgentExecutionNotFoundError
from backend.agents.file.execution.file_agent import FileAgent
from backend.agents.file.services.execution_result_store import (
    AgentExecutionResultStore,
)
from backend.agents.file.services.file_agent_service import FileAgentService
from backend.analysis.aggregations.engine import AggregationEngine
from backend.analysis.anomalies.engine import AnomalyEngine
from backend.analysis.correlations.engine import CorrelationEngine
from backend.analysis.insights.engine import InsightEngine
from backend.analysis.kpis.engine import KPIEngine
from backend.analysis.statistics.engine import DescriptiveStatisticsEngine
from backend.analysis.trends.engine import TrendEngine
from backend.cleaning.profiling.profiler import DatasetProfilingService
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
from backend.services.visualization_service import VisualizationService
from backend.tools.execution.analyze_dataset_tool import AnalyzeDatasetTool
from backend.tools.execution.clean_dataset_tool import CleanDatasetTool
from backend.tools.execution.generate_report_tool import GenerateReportTool
from backend.tools.execution.generate_visualization_tool import (
    GenerateVisualizationTool,
)
from backend.tools.execution.ingest_dataset_tool import IngestDatasetTool
from backend.visualization.charts.registry import default_generators
from backend.visualization.layouts.engine import LayoutEngine
from backend.visualization.recommendations.engine import ChartRecommendationEngine

_CSV_CONTENT = "a,b\n1,2\n3,4\n"


def _make_service() -> FileAgentService:
    dataframe_store = DataFrameStore()
    extractor = MetadataExtractor()
    dataset_store = BusinessDatasetStore()
    ingestion_service = IngestionService(LoaderRegistry(), DatasetValidator(), extractor, dataframe_store)
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
    agent = FileAgent(
        IngestDatasetTool(ingestion_service),
        CleanDatasetTool(cleaning_service),
        AnalyzeDatasetTool(analysis_service),
        GenerateVisualizationTool(visualization_service),
        GenerateReportTool(report_service),
        dataset_store,
    )
    return FileAgentService(agent, AgentExecutionResultStore())


def _step(dataset_reference: str, step_id: str) -> ExecutionStep:
    return ExecutionStep(
        step_id=step_id, name="Run", node_name="file_agent", inputs={"dataset_reference": dataset_reference}
    )


def test_execute_step_stores_and_returns_the_same_result(tmp_path: Path) -> None:
    async def scenario() -> None:
        csv_file = tmp_path / "d.csv"
        csv_file.write_text(_CSV_CONTENT)
        service = _make_service()

        result = await service.execute_step(_step(str(csv_file), "s1"), session_id="sess-1")

        assert result.status == ExecutionStatus.COMPLETED
        assert service.get_result("s1") == result

    asyncio.run(scenario())


def test_get_result_raises_for_an_unknown_step_id() -> None:
    service = _make_service()
    with pytest.raises(AgentExecutionNotFoundError):
        service.get_result("never-ran")


def test_list_results_returns_most_recent_first(tmp_path: Path) -> None:
    async def scenario() -> None:
        csv_file = tmp_path / "d.csv"
        csv_file.write_text(_CSV_CONTENT)
        service = _make_service()

        first = await service.execute_step(_step(str(csv_file), "s1"), session_id="sess-1")
        second = await service.execute_step(_step(str(csv_file), "s2"), session_id="sess-1")

        listed = service.list_results()
        assert listed[0].step_id == second.step_id
        assert listed[1].step_id == first.step_id

    asyncio.run(scenario())


def test_execute_step_overwrites_a_result_for_a_repeated_step_id(tmp_path: Path) -> None:
    async def scenario() -> None:
        csv_file = tmp_path / "d.csv"
        csv_file.write_text(_CSV_CONTENT)
        service = _make_service()

        await service.execute_step(_step(str(csv_file), "s1"), session_id="sess-1")
        await service.execute_step(_step(str(csv_file), "s1"), session_id="sess-2")

        assert service.get_result("s1").metadata["session_id"] == "sess-2"
        assert len(service.list_results()) == 1

    asyncio.run(scenario())
