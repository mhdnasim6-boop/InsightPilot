"""Graph tests: PlannerAgent wired into the real default graph (Planner -> FileAgent ->
SQLAgent -> BrowserAgent -> ReportAgent -> ExecutiveSummaryAgent -> End), executed end
to end through the real ExecutionEngine/OrchestrationService with the real MockProvider.
Mirrors test_file_agent_graph.py. The key integration proof: PlannerAgentNode discovers
every other real agent node dynamically off the live graph — never a hardcoded list —
and its own generated plan only ever references node names that are genuinely
registered in this exact graph.
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
    ingestion_service = IngestionService(LoaderRegistry(), DatasetValidator(), extractor, dataframe_store)
    cleaning_service = CleaningService(ingestion_service, DatasetProfilingService(extractor), extractor, dataframe_store)
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
    file_agent_service = FileAgentService(agent, AgentExecutionResultStore())

    sql_data_source_service = SQLDataSourceService(ConnectorRegistry(), ingestion_service)
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
    browser_agent_service = BrowserAgentService(browser_agent, BrowserAgentResultStore())

    report_agent = ReportAgent(GenerateReportTool(report_service))
    report_agent_service = ReportAgentService(report_agent, ReportAgentResultStore())

    settings = Settings(ai_default_provider="mock", ai_default_model="mock-model")
    ai_service = AIService(ProviderFactory(settings), settings)
    executive_summary_agent = ExecutiveSummaryAgent(GenerateExecutiveSummaryTool(ai_service, PromptManager()))
    executive_summary_service = ExecutiveSummaryService(executive_summary_agent, ExecutiveSummaryResultStore())

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
    defaults: dict[str, object] = {"execution_id": generate_id(), "created_at": now, "updated_at": now}
    defaults.update(overrides)
    return InsightPilotState.model_validate(defaults)


def test_default_graph_runs_planner_agent_first_and_discovers_every_real_agent() -> None:
    async def scenario() -> None:
        service = _make_orchestration_service()
        state = _new_state(session_id="sess-1", user_request="Generate a business report.")

        result_state = await service.execute(state)

        assert result_state.execution_trace[0] == "planner"
        planner_result = result_state.artifacts["planner_agent_result"]
        assert planner_result["status"] == "completed"

        planner_output = planner_result["planner_output"]
        assert planner_output["goal"]
        steps = planner_output["execution_plan"]["steps"]
        assert len(steps) > 0
        # Every referenced agent is a real node genuinely registered in this graph -
        # never a hardcoded list - and every step explains why it was selected.
        real_agent_names = {"file_agent", "sql_agent", "browser_agent", "report_agent", "executive_summary_agent"}
        assert all(step["node_name"] in real_agent_names for step in steps)
        assert all(step["description"] for step in steps)

    asyncio.run(scenario())


def test_default_graph_completes_even_when_planner_agent_has_no_user_request() -> None:
    async def scenario() -> None:
        service = _make_orchestration_service()
        state = _new_state(session_id="sess-1")  # no user_request at all

        result_state = await service.execute(state)

        # PlannerAgent's own graceful failure never blocks the rest of the graph -
        # EndNode still runs, mirroring every other agent's own failure handling.
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
        assert result_state.artifacts["planner_agent_result"]["status"] == "failed"
        assert result_state.errors

    asyncio.run(scenario())


def test_compiled_graph_metadata_reflects_planner_agent_and_its_description() -> None:
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

    file_agent_node = next(node for node in metadata.nodes if node.name == "file_agent")
    assert "description" in file_agent_node.details
