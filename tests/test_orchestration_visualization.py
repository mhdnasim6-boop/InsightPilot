"""Tests for graph visualization (Mermaid text, best-effort PNG)."""

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
from backend.orchestration.graph.builder import GraphBuilder
from backend.orchestration.graph.compiled import CompiledGraph
from backend.orchestration.graph.default_graph import build_default_graph
from backend.orchestration.nodes.placeholders import PlannerNode
from backend.orchestration.visualization.mermaid import generate_mermaid, generate_png
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
from backend.visualization.charts.registry import default_generators
from backend.visualization.layouts.engine import LayoutEngine
from backend.visualization.recommendations.engine import ChartRecommendationEngine
from config.settings import Settings
from tests.helpers import make_planner_agent_node


def _make_file_agent_service() -> FileAgentService:
    """A real (not mocked), cheap-to-construct FileAgentService — these tests exercise
    Mermaid/PNG generation, not FileAgent's pipeline."""
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
    Mermaid/PNG generation, not SQLAgent's pipeline."""
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
    Mermaid/PNG generation, not BrowserAgent's pipeline."""
    agent = BrowserAgent(SearchWebTool(BrowserService(MockBrowserProvider())))
    return BrowserAgentService(agent, BrowserAgentResultStore())


def _make_report_agent_service() -> ReportAgentService:
    """A real (not mocked), cheap-to-construct ReportAgentService — these tests exercise
    Mermaid/PNG generation, not ReportAgent's pipeline."""
    report_service = ReportService(ReportBuilder(), ReportValidator(), ReportStore())
    agent = ReportAgent(GenerateReportTool(report_service))
    return ReportAgentService(agent, ReportAgentResultStore())


def _make_executive_summary_service() -> ExecutiveSummaryService:
    """A real (not mocked) ExecutiveSummaryService backed by the real MockProvider —
    these tests exercise Mermaid/PNG generation, not the AI response content."""
    settings = Settings(ai_default_provider="mock", ai_default_model="mock-model")
    ai_service = AIService(ProviderFactory(settings), settings)
    agent = ExecutiveSummaryAgent(GenerateExecutiveSummaryTool(ai_service, PromptManager()))
    return ExecutiveSummaryService(agent, ExecutiveSummaryResultStore())


def _compiled_default_graph() -> CompiledGraph:
    graph_builder = GraphBuilder()
    return build_default_graph(
        graph_builder,
        make_planner_agent_node(graph_builder),
        _make_file_agent_service(),
        _make_sql_agent_service(),
        _make_browser_agent_service(),
        _make_report_agent_service(),
        _make_executive_summary_service(),
    ).compile()


def test_generate_mermaid_contains_every_node_and_an_arrow() -> None:
    graph = _compiled_default_graph()
    mermaid = generate_mermaid(graph)

    assert "planner" in mermaid
    assert "file_agent" in mermaid
    assert "sql_agent" in mermaid
    assert "browser_agent" in mermaid
    assert "report_agent" in mermaid
    assert "executive_summary_agent" in mermaid
    assert "end" in mermaid
    assert "-->" in mermaid


def test_generate_mermaid_is_deterministic() -> None:
    graph = _compiled_default_graph()
    assert generate_mermaid(graph) == generate_mermaid(graph)


def test_generate_png_never_raises() -> None:
    graph = _compiled_default_graph()
    png = generate_png(graph)
    assert png is None or isinstance(png, bytes)


def test_single_node_graph_mermaid_reflects_entry_point() -> None:
    builder = GraphBuilder()
    planner = PlannerNode()
    builder.add_node(planner)
    builder.set_entry_point(planner.name)
    builder.add_edge(planner.name, END)

    mermaid = generate_mermaid(builder.compile())

    assert "planner" in mermaid
    assert "router" not in mermaid
