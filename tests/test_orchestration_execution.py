"""Tests for ExecutionEngine: run, stream, cancel, resume, inspect."""

import asyncio

import pytest
from langgraph.graph import END

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
from backend.orchestration.nodes.base import OrchestrationNode
from backend.orchestration.state.state import ExecutionStatus, InsightPilotState
from backend.reporting.builders.report_builder import ReportBuilder
from backend.reporting.report_store import ReportStore
from backend.reporting.validation.validator import ReportValidator
from backend.services.ai_service import AIService
from backend.services.analysis_service import AnalysisService
from backend.services.browser_service import BrowserService
from backend.services.cleaning_service import CleaningService
from backend.services.ingestion_service import IngestionService
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
    ExecutionEngine mechanics, not FileAgent's own pipeline behavior."""
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
    ExecutionEngine mechanics, not SQLAgent's own pipeline behavior."""
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
    ExecutionEngine mechanics, not BrowserAgent's own pipeline behavior."""
    agent = BrowserAgent(SearchWebTool(BrowserService(MockBrowserProvider())))
    return BrowserAgentService(agent, BrowserAgentResultStore())


def _make_report_agent_service() -> ReportAgentService:
    """A real (not mocked), cheap-to-construct ReportAgentService — these tests exercise
    ExecutionEngine mechanics, not ReportAgent's own pipeline behavior."""
    report_service = ReportService(ReportBuilder(), ReportValidator(), ReportStore())
    agent = ReportAgent(GenerateReportTool(report_service))
    return ReportAgentService(agent, ReportAgentResultStore())


def _make_executive_summary_service() -> ExecutiveSummaryService:
    """A real (not mocked) ExecutiveSummaryService backed by the real MockProvider —
    these tests exercise ExecutionEngine mechanics, not the AI response content."""
    settings = Settings(ai_default_provider="mock", ai_default_model="mock-model")
    ai_service = AIService(ProviderFactory(settings), settings)
    agent = ExecutiveSummaryAgent(GenerateExecutiveSummaryTool(ai_service, PromptManager()))
    return ExecutiveSummaryService(agent, ExecutiveSummaryResultStore())


def _new_state() -> InsightPilotState:
    now = utc_now()
    return InsightPilotState(execution_id=generate_id(), created_at=now, updated_at=now)


def test_run_executes_nodes_in_order() -> None:
    async def scenario() -> None:
        bus = EventBus()
        engine = ExecutionEngine(bus)
        graph_builder = GraphBuilder(event_bus=bus)
        graph = build_default_graph(
            graph_builder,
            make_planner_agent_node(graph_builder),
            _make_file_agent_service(),
            _make_sql_agent_service(),
            _make_browser_agent_service(),
            _make_report_agent_service(),
            _make_executive_summary_service(),
        ).compile()

        state = _new_state()
        result = await engine.run(graph, state)

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


def test_run_emits_events_in_expected_order() -> None:
    async def scenario() -> None:
        bus = EventBus()
        event_names: list[str] = []
        bus.subscribe(lambda event: event_names.append(type(event).__name__))
        engine = ExecutionEngine(bus)
        graph_builder = GraphBuilder(event_bus=bus)
        graph = build_default_graph(
            graph_builder,
            make_planner_agent_node(graph_builder),
            _make_file_agent_service(),
            _make_sql_agent_service(),
            _make_browser_agent_service(),
            _make_report_agent_service(),
            _make_executive_summary_service(),
        ).compile()

        await engine.run(graph, _new_state())

        assert event_names[0] == "ExecutionStarted"
        assert event_names[-1] == "ExecutionCompleted"
        assert event_names.count("NodeStarted") == 12
        assert event_names.count("NodeCompleted") == 12

    asyncio.run(scenario())


def test_stream_yields_incremental_state_updates() -> None:
    async def scenario() -> None:
        bus = EventBus()
        engine = ExecutionEngine(bus)
        graph_builder = GraphBuilder(event_bus=bus)
        graph = build_default_graph(
            graph_builder,
            make_planner_agent_node(graph_builder),
            _make_file_agent_service(),
            _make_sql_agent_service(),
            _make_browser_agent_service(),
            _make_report_agent_service(),
            _make_executive_summary_service(),
        ).compile()

        traces = [
            state.execution_trace async for state in engine.stream(graph, _new_state())
        ]

        assert traces[0] == []
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


def test_inspect_returns_last_known_state_after_run() -> None:
    async def scenario() -> None:
        bus = EventBus()
        engine = ExecutionEngine(bus)
        graph_builder = GraphBuilder(event_bus=bus)
        graph = build_default_graph(
            graph_builder,
            make_planner_agent_node(graph_builder),
            _make_file_agent_service(),
            _make_sql_agent_service(),
            _make_browser_agent_service(),
            _make_report_agent_service(),
            _make_executive_summary_service(),
        ).compile()

        state = _new_state()
        await engine.run(graph, state)

        inspected = engine.inspect(state.execution_id)
        assert inspected is not None
        assert inspected.status == ExecutionStatus.COMPLETED

    asyncio.run(scenario())


def test_inspect_unknown_execution_returns_none() -> None:
    engine = ExecutionEngine(EventBus())
    assert engine.inspect("never-ran") is None


def test_resume_raises_checkpoint_not_configured() -> None:
    async def scenario() -> None:
        engine = ExecutionEngine(EventBus())
        with pytest.raises(CheckpointNotConfiguredError):
            await engine.resume("anything")

    asyncio.run(scenario())


def test_cancel_stops_an_in_flight_execution() -> None:
    async def scenario() -> None:
        class SlowNode(OrchestrationNode):
            name = "slow"

            async def execute(self, state: InsightPilotState) -> InsightPilotState:
                await asyncio.sleep(10)
                return state

        bus = EventBus()
        engine = ExecutionEngine(bus)
        builder = GraphBuilder(event_bus=bus)
        builder.add_node(SlowNode())
        builder.set_entry_point("slow")
        builder.add_edge("slow", END)
        graph = builder.compile()

        state = _new_state()
        run_task = asyncio.create_task(engine.run(graph, state))
        await asyncio.sleep(0.05)  # let the run actually start

        assert engine.cancel(state.execution_id) is True

        with pytest.raises(asyncio.CancelledError):
            await run_task

        inspected = engine.inspect(state.execution_id)
        assert inspected is not None
        assert inspected.status == ExecutionStatus.CANCELLED

    asyncio.run(scenario())


def test_cancel_unknown_execution_returns_false() -> None:
    engine = ExecutionEngine(EventBus())
    assert engine.cancel("never-started") is False
