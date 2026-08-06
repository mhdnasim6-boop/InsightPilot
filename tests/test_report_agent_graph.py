"""Graph tests: ReportAgent wired into the real default graph (Planner -> FileAgent ->
SQLAgent -> BrowserAgent -> ReportAgent -> ExecutiveSummaryAgent -> End),
executed end to end through the real ExecutionEngine/OrchestrationService.
Mirrors test_browser_agent_graph.py. The key integration proof:
ReportAgentNode needs no direct wiring to FileAgent/SQLAgent — it reads
whichever of their results already landed in ``state.artifacts``.
"""

import asyncio
from pathlib import Path

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

_CSV_CONTENT = (
    "date,region,revenue,cost\n"
    "2024-01-01,East,1000,600\n"
    "2024-02-01,East,1100,650\n"
    "2024-01-01,West,200,120\n"
    "2024-02-01,West,210,130\n"
)


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


def test_default_graph_runs_report_agent_end_to_end_from_file_agents_own_output(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        csv_file = tmp_path / "sales.csv"
        csv_file.write_text(_CSV_CONTENT)
        service = _make_orchestration_service()

        state = _new_state(
            session_id="sess-1",
            variables={
                "dataset_reference": str(csv_file),
                "search_request": "Acme Corp",
                "report_config": {
                    "template_type": "business_report",
                    "title": "Sales Report",
                },
            },
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

        file_agent_result = result_state.artifacts["file_agent_result"]
        assert file_agent_result["status"] == "completed"

        browser_agent_result = result_state.artifacts["browser_agent_result"]
        assert browser_agent_result["status"] == "completed"

        # The key data-flow proof: ReportAgentNode needed no direct wiring
        # to FileAgent/BrowserAgent - it read both of their already-written
        # state.artifacts entries on its own.
        report_agent_result = result_state.artifacts["report_agent_result"]
        assert report_agent_result["status"] == "completed"
        assert report_agent_result["report_document"]["title"] == "Sales Report"
        assert report_agent_result["metadata"]["external_context"]["queries"] == [
            "Acme Corp"
        ]

        # ExecutiveSummaryAgentNode also ran — the second such data-flow
        # proof — picking up ReportAgent's own report_document on its own.
        executive_summary_result = result_state.artifacts["executive_summary_result"]
        assert executive_summary_result["status"] == "completed"
        assert executive_summary_result["executive_summary"]
        assert (
            executive_summary_result["metadata"]["report_id"]
            == report_agent_result["report_id"]
        )

    asyncio.run(scenario())


def test_default_graph_completes_with_report_agent_failed_when_nothing_upstream_succeeded() -> (
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
        assert result_state.errors

    asyncio.run(scenario())


def test_compiled_graph_metadata_reflects_report_agent() -> None:
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


def test_report_agent_result_is_independent_of_the_other_stores(tmp_path: Path) -> None:
    """Proves ReportAgentResultStore is genuinely its own store: a step_id
    that File/SQL/BrowserAgent also wrote under does not collide with
    ReportAgent's own result for the same step_id."""

    async def scenario() -> None:
        csv_file = tmp_path / "sales.csv"
        csv_file.write_text(_CSV_CONTENT)
        service = _make_orchestration_service()
        state = _new_state(
            session_id="sess-1",
            metadata={"step_id": "shared-step-1"},
            variables={"dataset_reference": str(csv_file)},
        )

        result_state = await service.execute(state)

        assert result_state.artifacts["file_agent_result"]["step_id"] == "shared-step-1"
        report_agent_result = result_state.artifacts["report_agent_result"]
        assert report_agent_result["step_id"] == "shared-step-1"
        assert report_agent_result["status"] == "completed"

    asyncio.run(scenario())
