"""Shared test construction helpers used across multiple test modules.

Every graph/orchestration test needs a real ``PlannerAgentNode`` wired
into ``build_default_graph()`` now that the placeholder ``PlannerNode``
is gone — this factory is the one place that wiring lives, instead of
duplicating it across eight test files. ``make_orchestration_service()``
goes one step further: the full real default graph (all five agents,
all five approval interrupt points), optionally with a real LangGraph
checkpointer — the one piece Human-in-the-Loop tests need that plain
graph/agent tests don't.
"""

from langgraph.checkpoint.memory import InMemorySaver

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
from backend.agents.planner.execution.planner_agent import PlannerAgent
from backend.agents.planner.services.execution_result_store import (
    PlannerAgentResultStore,
)
from backend.agents.planner.services.planner_agent_service import PlannerAgentService
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
from backend.orchestration.graph.config import GraphConfig
from backend.orchestration.graph.default_graph import (
    approval_node_names,
    build_default_graph,
)
from backend.orchestration.nodes.planner_agent_node import PlannerAgentNode
from backend.reporting.builders.report_builder import ReportBuilder
from backend.reporting.report_store import ReportStore
from backend.reporting.validation.validator import ReportValidator
from backend.services.ai_service import AIService
from backend.services.analysis_service import AnalysisService
from backend.services.browser_service import BrowserService
from backend.services.cleaning_service import CleaningService
from backend.services.ingestion_service import IngestionService
from backend.services.orchestration_service import OrchestrationService
from backend.services.planner_service import PlannerService
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
from backend.visualization.charts.registry import default_generators
from backend.visualization.layouts.engine import LayoutEngine
from backend.visualization.recommendations.engine import ChartRecommendationEngine
from config.settings import Settings


def make_planner_agent_node(builder: GraphBuilder) -> PlannerAgentNode:
    """Build a real PlannerAgentNode backed by MockProvider — no external AI.

    ``builder`` must be the exact ``GraphBuilder`` instance later passed
    to ``build_default_graph()``: ``PlannerAgent`` reads its registered
    nodes lazily via ``builder.export()`` at plan-generation time (see
    ``backend.agents.planner.execution.planner_agent``), so handing it
    over before the other nodes are added is safe, not a stale snapshot.
    """
    settings = Settings(ai_default_provider="mock", ai_default_model="mock-model")
    ai_service = AIService(ProviderFactory(settings), settings)
    planner_service = PlannerService(ai_service, PromptManager())
    planner_agent_service = PlannerAgentService(PlannerAgent(planner_service, builder), PlannerAgentResultStore())
    return PlannerAgentNode(planner_agent_service)


def make_orchestration_service(with_checkpointer: bool = True) -> OrchestrationService:
    """Build a real OrchestrationService wired with the full default graph — all five
    real agents (via real tools, via real MockProvider-backed services) plus all five
    approval interrupt points, and (by default) a real in-memory LangGraph checkpointer
    so pause/resume actually works, exactly like the production DI wiring.
    """
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
    sql_data_source_service = SQLDataSourceService(ConnectorRegistry(), ingestion_service)
    browser_service = BrowserService(MockBrowserProvider())

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

    browser_agent = BrowserAgent(SearchWebTool(browser_service))
    browser_agent_service = BrowserAgentService(browser_agent, BrowserAgentResultStore())

    report_agent = ReportAgent(GenerateReportTool(report_service))
    report_agent_service = ReportAgentService(report_agent, ReportAgentResultStore())

    settings = Settings(ai_default_provider="mock", ai_default_model="mock-model")
    ai_service = AIService(ProviderFactory(settings), settings)
    executive_summary_agent = ExecutiveSummaryAgent(GenerateExecutiveSummaryTool(ai_service, PromptManager()))
    executive_summary_service = ExecutiveSummaryService(executive_summary_agent, ExecutiveSummaryResultStore())

    bus = EventBus()
    config = GraphConfig(interrupt_before=approval_node_names())
    graph_builder = GraphBuilder(config=config, event_bus=bus)
    builder = build_default_graph(
        graph_builder,
        make_planner_agent_node(graph_builder),
        file_agent_service,
        sql_agent_service,
        browser_agent_service,
        report_agent_service,
        executive_summary_service,
    )
    checkpointer = InMemorySaver() if with_checkpointer else None
    return OrchestrationService(builder, ExecutionEngine(bus), checkpointer=checkpointer)
