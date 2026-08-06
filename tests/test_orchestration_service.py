"""Tests for OrchestrationService."""

import asyncio

import pytest

from backend.agents.browser.execution.browser_agent import BrowserAgent
from backend.agents.browser.services.browser_agent_service import BrowserAgentService
from backend.agents.browser.services.execution_result_store import (
    BrowserAgentResultStore,
)
from backend.agents.executive_summary.execution.executive_summary_agent import (
    ExecutiveSummaryAgent,
)
from backend.agents.executive_summary.services.execution_result_store import (
    ExecutiveSummaryResultStore,
)
from backend.agents.executive_summary.services.executive_summary_service import (
    ExecutiveSummaryService,
)
from backend.agents.file.execution.file_agent import FileAgent
from backend.agents.file.services.execution_result_store import (
    AgentExecutionResultStore,
)
from backend.agents.file.services.file_agent_service import FileAgentService
from backend.agents.report.execution.report_agent import ReportAgent
from backend.agents.report.services.execution_result_store import (
    ReportAgentResultStore,
)
from backend.agents.report.services.report_agent_service import ReportAgentService
from backend.agents.sql.execution.sql_agent import SQLAgent
from backend.agents.sql.services.sql_agent_service import SQLAgentService
from backend.ai.prompts.manager import PromptManager
from backend.ai.providers.factory import ProviderFactory
from backend.analysis.aggregations.engine import AggregationEngine
from backend.analysis.anomalies.engine import AnomalyEngine
from backend.analysis.correlations.engine import CorrelationEngine
from backend.analysis.insights.engine import InsightEngine
from backend.analysis.kpis.engine import KPIEngine
from backend.analysis.statistics.engine import DescriptiveStatisticsEngine
from backend.analysis.trends.engine import TrendEngine
from backend.browser.providers.mock import MockBrowserProvider
from backend.cleaning.profiling.profiler import DatasetProfilingService
from backend.datasource.sql.registry.connector_registry import ConnectorRegistry
from backend.ingestion.metadata.extractor import MetadataExtractor
from backend.ingestion.registry.dataframe_store import DataFrameStore
from backend.ingestion.registry.dataset_store import BusinessDatasetStore
from backend.ingestion.registry.loader_registry import LoaderRegistry
from backend.ingestion.validators.validator import DatasetValidator
from backend.orchestration.events.bus import EventBus
from backend.orchestration.exceptions import CheckpointNotConfiguredError
from backend.orchestration.execution.engine import ExecutionEngine
from backend.orchestration.graph.builder import GraphBuilder
from backend.orchestration.graph.default_graph import build_default_graph
from backend.orchestration.state.state import ExecutionStatus, InsightPilotState
from backend.reporting.builders.report_builder import ReportBuilder
from backend.reporting.report_store import ReportStore
from backend.reporting.validation.validator import ReportValidator
from backend.services.ai_service import AIService
from backend.services.analysis_service import AnalysisService
from backend.services.browser_service import BrowserService
from backend.services.cleaning_service import CleaningService
from backend.services.ingestion_service import IngestionService
from backend.services.orchestration_service import OrchestrationService
from backend.services.report_service import ReportService
from backend.services.sql_data_source_service import SQLDataSourceService
from backend.services.visualization_service import VisualizationService
from backend.tools.execution.analyze_dataset_tool import AnalyzeDatasetTool
from backend.tools.execution.clean_dataset_tool import CleanDatasetTool
from backend.tools.execution.generate_executive_summary_tool import (
    GenerateExecutiveSummaryTool,
)
from backend.tools.execution.generate_report_tool import GenerateReportTool
from backend.tools.execution.generate_visualization_tool import (
    GenerateVisualizationTool,
)
from backend.tools.execution.ingest_dataset_tool import IngestDatasetTool
from backend.tools.execution.query_database_tool import QueryDatabaseTool
from backend.tools.execution.search_web_tool import SearchWebTool
from backend.utils.ids import generate_id
from backend.utils.time import utc_now
from backend.visualization.charts.registry import default_generators
from backend.visualization.layouts.engine import LayoutEngine
from backend.visualization.recommendations.engine import ChartRecommendationEngine
from config.settings import Settings
from tests.helpers import make_planner_agent_node


def _make_file_agent_service() -> FileAgentService:
    """A real (not mocked), cheap-to-construct FileAgentService — these tests exercise
    OrchestrationService's own behavior, not FileAgent's pipeline."""
    dataframe_store = DataFrameStore()
    extractor = MetadataExtractor()
    dataset_store = BusinessDatasetStore()
    ingestion_service = IngestionService(
        LoaderRegistry(), DatasetValidator(), extractor, dataframe_store
    )
    cleaning_service = CleaningService(
        ingestion_service,
        DatasetProfilingService(extractor),
        extractor,
        dataframe_store,
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
        ingestion_service,
        ChartRecommendationEngine(default_generators(aggregation_engine)),
        LayoutEngine(),
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


def _make_sql_agent_service() -> SQLAgentService:
    """A real (not mocked), cheap-to-construct SQLAgentService — these tests exercise
    OrchestrationService's own behavior, not SQLAgent's pipeline."""
    dataframe_store = DataFrameStore()
    extractor = MetadataExtractor()
    dataset_store = BusinessDatasetStore()
    ingestion_service = IngestionService(
        LoaderRegistry(), DatasetValidator(), extractor, dataframe_store
    )
    sql_data_source_service = SQLDataSourceService(
        ConnectorRegistry(), ingestion_service
    )
    cleaning_service = CleaningService(
        ingestion_service,
        DatasetProfilingService(extractor),
        extractor,
        dataframe_store,
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
        ingestion_service,
        ChartRecommendationEngine(default_generators(aggregation_engine)),
        LayoutEngine(),
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


def _make_browser_agent_service() -> BrowserAgentService:
    """A real (not mocked), cheap-to-construct BrowserAgentService — these tests exercise
    OrchestrationService's own behavior, not BrowserAgent's pipeline."""
    agent = BrowserAgent(SearchWebTool(BrowserService(MockBrowserProvider())))
    return BrowserAgentService(agent, BrowserAgentResultStore())


def _make_report_agent_service() -> ReportAgentService:
    """A real (not mocked), cheap-to-construct ReportAgentService — these tests exercise
    OrchestrationService's own behavior, not ReportAgent's pipeline."""
    report_service = ReportService(ReportBuilder(), ReportValidator(), ReportStore())
    agent = ReportAgent(GenerateReportTool(report_service))
    return ReportAgentService(agent, ReportAgentResultStore())


def _make_executive_summary_service() -> ExecutiveSummaryService:
    """A real (not mocked) ExecutiveSummaryService backed by the real MockProvider —
    these tests exercise OrchestrationService's own behavior, not the AI response content."""
    settings = Settings(ai_default_provider="mock", ai_default_model="mock-model")
    ai_service = AIService(ProviderFactory(settings), settings)
    agent = ExecutiveSummaryAgent(GenerateExecutiveSummaryTool(ai_service, PromptManager()))
    return ExecutiveSummaryService(agent, ExecutiveSummaryResultStore())


def _make_service() -> OrchestrationService:
    bus = EventBus()
    graph_builder = GraphBuilder(event_bus=bus)
    builder = build_default_graph(
        graph_builder,
        make_planner_agent_node(graph_builder),
        _make_file_agent_service(),
        _make_sql_agent_service(),
        _make_browser_agent_service(),
        _make_report_agent_service(),
        _make_executive_summary_service(),
    )
    return OrchestrationService(builder, ExecutionEngine(bus))


def _new_state() -> InsightPilotState:
    now = utc_now()
    return InsightPilotState(execution_id=generate_id(), created_at=now, updated_at=now)


def test_compile_graph_returns_metadata() -> None:
    service = _make_service()
    metadata = service.compile_graph()

    assert {node.name for node in metadata.nodes} == {
        "planner",
        "approval_file_agent",
        "file_agent",
        "approval_sql_agent",
        "sql_agent",
        "approval_browser_agent",
        "browser_agent",
        "approval_report_agent",
        "report_agent",
        "approval_executive_summary_agent",
        "executive_summary_agent",
        "end",
    }
    assert metadata.entry_point == "planner"


def test_execute_compiles_lazily_and_runs_the_graph() -> None:
    async def scenario() -> None:
        service = _make_service()  # compile_graph() not called explicitly
        result = await service.execute(_new_state())

        assert result.execution_trace == [
            "planner",
            "approval_file_agent",
            "file_agent",
            "approval_sql_agent",
            "sql_agent",
            "approval_browser_agent",
            "browser_agent",
            "approval_report_agent",
            "report_agent",
            "approval_executive_summary_agent",
            "executive_summary_agent",
            "end",
        ]
        assert result.status == ExecutionStatus.COMPLETED

    asyncio.run(scenario())


def test_stream_yields_state_per_node() -> None:
    async def scenario() -> None:
        service = _make_service()
        traces = [state.execution_trace async for state in service.stream(_new_state())]

        assert traces[-1] == [
            "planner",
            "approval_file_agent",
            "file_agent",
            "approval_sql_agent",
            "sql_agent",
            "approval_browser_agent",
            "browser_agent",
            "approval_report_agent",
            "report_agent",
            "approval_executive_summary_agent",
            "executive_summary_agent",
            "end",
        ]

    asyncio.run(scenario())


def test_validate_state_accepts_well_formed_data() -> None:
    service = _make_service()
    now = utc_now()
    state = service.validate_state(
        {"execution_id": "e1", "created_at": now, "updated_at": now}
    )
    assert state.execution_id == "e1"


def test_validate_state_rejects_missing_required_field() -> None:
    from pydantic import ValidationError

    service = _make_service()
    with pytest.raises(ValidationError):
        service.validate_state({"created_at": utc_now(), "updated_at": utc_now()})


def test_get_graph_metadata_and_mermaid() -> None:
    service = _make_service()
    metadata = service.get_graph_metadata()
    mermaid = service.get_mermaid()

    assert metadata.entry_point == "planner"
    assert "planner" in mermaid
    assert "file_agent" in mermaid
    assert "sql_agent" in mermaid
    assert "browser_agent" in mermaid
    assert "report_agent" in mermaid
    assert "executive_summary_agent" in mermaid


def test_get_png_does_not_raise() -> None:
    service = _make_service()
    png = service.get_png()
    assert png is None or isinstance(png, bytes)


def test_cancel_and_inspect_delegate_to_execution_engine() -> None:
    async def scenario() -> None:
        service = _make_service()
        state = _new_state()

        assert service.cancel(state.execution_id) is False  # never started

        await service.execute(state)
        inspected = service.inspect(state.execution_id)

        assert inspected is not None
        assert inspected.status == ExecutionStatus.COMPLETED

    asyncio.run(scenario())


def test_resume_raises_checkpoint_not_configured() -> None:
    async def scenario() -> None:
        service = _make_service()
        with pytest.raises(CheckpointNotConfiguredError):
            await service.resume("anything")

    asyncio.run(scenario())
