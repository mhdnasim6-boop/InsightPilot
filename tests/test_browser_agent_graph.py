"""Graph tests: BrowserAgent wired into the real default graph (Planner -> FileAgent ->
SQLAgent -> BrowserAgent -> ReportAgent -> ExecutiveSummaryAgent -> End),
executed end to end through the real ExecutionEngine/OrchestrationService.
Mirrors test_sql_agent_graph.py. FileAgentNode/SQLAgentNode also run for
every case here; they gracefully report FAILED results since these
states carry neither a dataset_reference nor a SQL connection.
"""

import asyncio

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


def _make_orchestration_service() -> OrchestrationService:
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

    file_agent = FileAgent(
        IngestDatasetTool(ingestion_service),
        CleanDatasetTool(cleaning_service),
        AnalyzeDatasetTool(analysis_service),
        GenerateVisualizationTool(visualization_service),
        GenerateReportTool(report_service),
        dataset_store,
    )
    file_agent_service = FileAgentService(file_agent, AgentExecutionResultStore())

    sql_agent = SQLAgent(
        QueryDatabaseTool(sql_data_source_service),
        CleanDatasetTool(cleaning_service),
        AnalyzeDatasetTool(analysis_service),
        GenerateVisualizationTool(visualization_service),
        GenerateReportTool(report_service),
        dataset_store,
    )
    sql_agent_service = SQLAgentService(sql_agent, AgentExecutionResultStore())

    browser_agent = BrowserAgent(SearchWebTool(BrowserService(MockBrowserProvider())))
    browser_agent_service = BrowserAgentService(
        browser_agent, BrowserAgentResultStore()
    )

    report_agent = ReportAgent(GenerateReportTool(report_service))
    report_agent_service = ReportAgentService(report_agent, ReportAgentResultStore())

    settings = Settings(ai_default_provider="mock", ai_default_model="mock-model")
    ai_service = AIService(ProviderFactory(settings), settings)
    executive_summary_agent = ExecutiveSummaryAgent(GenerateExecutiveSummaryTool(ai_service, PromptManager()))
    executive_summary_service = ExecutiveSummaryService(
        executive_summary_agent, ExecutiveSummaryResultStore()
    )

    bus = EventBus()
    graph_builder = GraphBuilder(event_bus=bus)
    builder = build_default_graph(
        graph_builder,
        make_planner_agent_node(graph_builder),
        file_agent_service,
        sql_agent_service,
        browser_agent_service,
        report_agent_service,
        executive_summary_service,
    )
    return OrchestrationService(builder, ExecutionEngine(bus))


def _new_state(**overrides: object) -> InsightPilotState:
    now = utc_now()
    defaults: dict[str, object] = {
        "execution_id": generate_id(),
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    return InsightPilotState.model_validate(defaults)


def test_default_graph_runs_browser_agent_end_to_end() -> None:
    async def scenario() -> None:
        service = _make_orchestration_service()

        state = _new_state(
            session_id="sess-1", variables={"search_request": "Acme Corp"}
        )

        result_state = await service.execute(state)

        assert result_state.execution_trace == [
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
        assert result_state.status == ExecutionStatus.COMPLETED

        browser_agent_result = result_state.artifacts["browser_agent_result"]
        assert browser_agent_result["status"] == "completed"
        assert len(browser_agent_result["sources"]) == 3
        assert browser_agent_result["summaries"][0]["query"] == "Acme Corp"

        # File/SQLAgentNode also ran (every step currently triggers the whole
        # graph) and gracefully reported failures, since these variables
        # carry neither a dataset_reference nor a SQL connection.
        assert result_state.artifacts["file_agent_result"]["status"] == "failed"
        assert result_state.artifacts["sql_agent_result"]["status"] == "failed"
        assert (
            result_state.errors
        )  # the graceful File/SQLAgent failures are still surfaced

        # ReportAgentNode also ran, and — since neither File nor SQLAgent
        # produced a usable dataset — gracefully reported a FAILED result too,
        # never a crash.
        assert result_state.artifacts["report_agent_result"]["status"] == "failed"

        # ExecutiveSummaryAgentNode also ran, and — since ReportAgent produced
        # no report_document — gracefully reported a FAILED result too.
        assert result_state.artifacts["executive_summary_result"]["status"] == "failed"

    asyncio.run(scenario())


def test_default_graph_completes_with_browser_agent_skipped_when_nothing_to_search() -> (
    None
):
    async def scenario() -> None:
        service = _make_orchestration_service()
        state = _new_state(
            session_id="sess-1"
        )  # no dataset_reference, no SQL connection, no search input

        result_state = await service.execute(state)

        assert result_state.execution_trace == [
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
        assert result_state.status == ExecutionStatus.COMPLETED
        assert result_state.artifacts["file_agent_result"]["status"] == "failed"
        assert result_state.artifacts["sql_agent_result"]["status"] == "failed"
        assert result_state.artifacts["browser_agent_result"]["status"] == "skipped"
        assert result_state.artifacts["report_agent_result"]["status"] == "failed"
        assert result_state.artifacts["executive_summary_result"]["status"] == "failed"

    asyncio.run(scenario())


def test_compiled_graph_metadata_reflects_browser_agent() -> None:
    service = _make_orchestration_service()
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


def test_browser_agent_result_is_independent_of_the_file_sql_shared_store() -> None:
    """Proves BrowserAgentResultStore is genuinely a separate store: a step_id
    that FileAgent/SQLAgent also wrote under does not collide with BrowserAgent's
    own result for the same step_id."""

    async def scenario() -> None:
        service = _make_orchestration_service()
        state = _new_state(
            session_id="sess-1",
            metadata={"step_id": "shared-step-1"},
            variables={"search_request": "Acme Corp"},
        )

        result_state = await service.execute(state)

        assert result_state.artifacts["file_agent_result"]["step_id"] == "shared-step-1"
        assert result_state.artifacts["sql_agent_result"]["step_id"] == "shared-step-1"
        browser_result = result_state.artifacts["browser_agent_result"]
        assert browser_result["step_id"] == "shared-step-1"
        assert (
            browser_result["status"] == "completed"
        )  # not overwritten/clobbered by File/SQLAgent's FAILED results

    asyncio.run(scenario())
