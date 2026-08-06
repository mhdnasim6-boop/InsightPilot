"""Integration tests for PlanningService: validate -> optimize -> execute against the real orchestration layer."""

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
from backend.orchestration.execution.engine import ExecutionEngine
from backend.orchestration.graph.builder import GraphBuilder
from backend.orchestration.graph.default_graph import build_default_graph
from backend.planning.events.bus import PlanEventBus
from backend.planning.exceptions.errors import PlanNotReadyError
from backend.planning.executor.executor import PlanExecutor
from backend.planning.models.enums import PlanStatus
from backend.planning.models.plan import ExecutionPlan
from backend.planning.models.step import ExecutionStep
from backend.planning.optimizer.default import DefaultPlanOptimizer
from backend.planning.validator.validator import PlanValidator
from backend.reporting.builders.report_builder import ReportBuilder
from backend.reporting.report_store import ReportStore
from backend.reporting.validation.validator import ReportValidator
from backend.services.ai_service import AIService
from backend.services.analysis_service import AnalysisService
from backend.services.browser_service import BrowserService
from backend.services.cleaning_service import CleaningService
from backend.services.ingestion_service import IngestionService
from backend.services.orchestration_service import OrchestrationService
from backend.services.planning_service import PlanningService
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
from backend.utils.time import utc_now
from backend.visualization.charts.registry import default_generators
from backend.visualization.layouts.engine import LayoutEngine
from backend.visualization.recommendations.engine import ChartRecommendationEngine
from config.settings import Settings
from tests.helpers import make_planner_agent_node


def _make_file_agent_service() -> FileAgentService:
    """A real (not mocked), cheap-to-construct FileAgentService — these tests exercise
    PlanningService's own lifecycle, not FileAgent's pipeline behavior."""
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
    PlanningService's own lifecycle, not SQLAgent's pipeline behavior."""
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
    PlanningService's own lifecycle, not BrowserAgent's pipeline behavior."""
    agent = BrowserAgent(SearchWebTool(BrowserService(MockBrowserProvider())))
    return BrowserAgentService(agent, BrowserAgentResultStore())


def _make_report_agent_service() -> ReportAgentService:
    """A real (not mocked), cheap-to-construct ReportAgentService — these tests exercise
    PlanningService's own lifecycle, not ReportAgent's pipeline behavior."""
    report_service = ReportService(ReportBuilder(), ReportValidator(), ReportStore())
    agent = ReportAgent(GenerateReportTool(report_service))
    return ReportAgentService(agent, ReportAgentResultStore())


def _make_executive_summary_service() -> ExecutiveSummaryService:
    """A real (not mocked) ExecutiveSummaryService backed by the real MockProvider —
    these tests exercise PlanningService's own lifecycle, not the AI response content."""
    settings = Settings(ai_default_provider="mock", ai_default_model="mock-model")
    ai_service = AIService(ProviderFactory(settings), settings)
    agent = ExecutiveSummaryAgent(GenerateExecutiveSummaryTool(ai_service, PromptManager()))
    return ExecutiveSummaryService(agent, ExecutiveSummaryResultStore())


def _make_planning_service() -> PlanningService:
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
    orchestration_service = OrchestrationService(builder, ExecutionEngine(bus))
    return PlanningService(
        PlanValidator(),
        DefaultPlanOptimizer(),
        PlanExecutor(PlanEventBus()),
        orchestration_service,
        PlanEventBus(),
    )


def _step(
    step_id: str, dependencies: list[str] | None = None, node_name: str = "planner"
) -> ExecutionStep:
    return ExecutionStep(
        step_id=step_id,
        name=step_id,
        node_name=node_name,
        dependencies=dependencies or [],
    )


def _plan(steps: list[ExecutionStep]) -> ExecutionPlan:
    now = utc_now()
    return ExecutionPlan(
        plan_id="p1",
        created_at=now,
        updated_at=now,
        steps=steps,
        user_request="do the thing",
    )


def test_register_returns_the_plan_unchanged() -> None:
    async def scenario() -> None:
        service = _make_planning_service()
        result = await service.register(_plan([_step("a")]))
        assert result.status == PlanStatus.DRAFT

    asyncio.run(scenario())


def test_validate_advances_a_sound_plan_to_validated() -> None:
    async def scenario() -> None:
        service = _make_planning_service()
        plan = _plan(
            [
                _step("a", node_name="planner"),
                _step("b", node_name="file_agent", dependencies=["a"]),
            ]
        )

        validated_plan, result = await service.validate(plan)

        assert result.is_valid is True
        assert validated_plan.status == PlanStatus.VALIDATED

    asyncio.run(scenario())


def test_validate_flags_a_step_referencing_an_unregistered_node() -> None:
    async def scenario() -> None:
        service = _make_planning_service()
        plan = _plan([_step("a", node_name="not-a-real-node")])

        validated_plan, result = await service.validate(plan)

        assert result.is_valid is False
        assert validated_plan.status == PlanStatus.DRAFT

    asyncio.run(scenario())


def test_optimize_requires_a_validated_plan() -> None:
    service = _make_planning_service()
    with pytest.raises(PlanNotReadyError):
        service.optimize(_plan([_step("a")]))


def test_optimize_advances_a_validated_plan_to_ready() -> None:
    service = _make_planning_service()
    plan = _plan([_step("a")]).model_copy(update={"status": PlanStatus.VALIDATED})

    optimized = service.optimize(plan)

    assert optimized.status == PlanStatus.READY


def test_full_lifecycle_validate_optimize_execute() -> None:
    async def scenario() -> None:
        service = _make_planning_service()
        plan = _plan(
            [
                _step("a", node_name="planner"),
                _step("b", node_name="file_agent", dependencies=["a"]),
            ]
        )

        validated_plan, result = await service.validate(plan)
        assert result.is_valid is True

        ready_plan = service.optimize(validated_plan)
        assert ready_plan.status == PlanStatus.READY

        final_plan = await service.execute(ready_plan)

        assert final_plan.status == PlanStatus.COMPLETED
        assert all(step.status.value == "completed" for step in final_plan.steps)

        inspected = service.inspect(final_plan.plan_id)
        assert inspected is not None
        assert inspected.status == PlanStatus.COMPLETED

    asyncio.run(scenario())


def test_export_mermaid_json_and_timeline() -> None:
    service = _make_planning_service()
    plan = _plan([_step("a"), _step("b", dependencies=["a"])])

    mermaid = service.export_mermaid(plan)
    raw_json = service.export_json(plan)
    timeline = service.export_timeline(plan)

    assert "a --> b" in mermaid
    assert '"plan_id": "p1"' in raw_json
    assert [entry.step_id for entry in timeline.entries] == ["a", "b"]


def test_get_metrics_returns_a_snapshot() -> None:
    service = _make_planning_service()
    plan = _plan([_step("a")]).model_copy(update={"estimated_tokens": 42})

    metrics = service.get_metrics(plan)

    assert metrics.plan_id == "p1"
    assert metrics.estimated_tokens == 42


def test_inspect_unknown_plan_returns_none() -> None:
    service = _make_planning_service()
    assert service.inspect("never-ran") is None
