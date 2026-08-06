"""Agent tests: ExecutiveSummaryAgent turning a real ReportDocument into a grounded
executive summary via exactly one AIService.generate() call.

Uses the real (not mocked) MockProvider throughout — its deterministic
echo legitimately contains the worked-example JSON embedded in the
prompt template (see backend.agents.executive_summary.prompts.templates),
so these tests exercise the full prompt -> AIService -> parse pipeline
against a real, unmodified provider, mirroring test_planner_service.py's
own established approach. ExecutiveSummaryAgent never calls
AnalysisService, VisualizationService, ReportBuilder, CleaningService, a
SQL service, or BrowserService — every assertion here checks that it
correctly sequenced one AI call, never that it computed anything itself.
"""

import asyncio
from pathlib import Path

import pytest

from backend.agents.browser.execution.browser_agent import BrowserAgent
from backend.agents.executive_summary.execution.executive_summary_agent import (
    ExecutiveSummaryAgent,
)
from backend.agents.file.exceptions.errors import InvalidAgentInputError
from backend.ai.models.requests import AIRequest
from backend.ai.models.responses import AIResponse, TokenUsage
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
from backend.ingestion.metadata.extractor import MetadataExtractor
from backend.ingestion.registry.dataframe_store import DataFrameStore
from backend.ingestion.registry.loader_registry import LoaderRegistry
from backend.ingestion.validators.validator import DatasetValidator
from backend.orchestration.state.state import ExecutionStatus
from backend.planning.models.step import ExecutionStep
from backend.reporting.builders.report_builder import ReportBuilder
from backend.reporting.models.report_document import ReportDocument
from backend.reporting.report_store import ReportStore
from backend.reporting.validation.validator import ReportValidator
from backend.services.ai_service import AIService
from backend.services.analysis_service import AnalysisService
from backend.services.browser_service import BrowserService
from backend.services.cleaning_service import CleaningService
from backend.services.ingestion_service import IngestionService
from backend.services.report_service import ReportService
from backend.services.visualization_service import VisualizationService
from backend.tools.execution.generate_executive_summary_tool import (
    GenerateExecutiveSummaryTool,
)
from backend.tools.execution.search_web_tool import SearchWebTool
from backend.visualization.charts.registry import default_generators
from backend.visualization.layouts.engine import LayoutEngine
from backend.visualization.recommendations.engine import ChartRecommendationEngine
from config.settings import Settings

_CSV_CONTENT = (
    "date,region,revenue,cost\n"
    "2024-01-01,East,1000,600\n"
    "2024-02-01,East,1100,650\n"
    "2024-01-01,West,200,120\n"
    "2024-02-01,West,210,130\n"
)


class _NonJsonAIService:
    """A minimal AIService stand-in whose response never contains JSON.

    Only used for the one test that needs a malformed AI response - not
    achievable through the real MockProvider, since the prompt template
    itself always embeds valid worked-example JSON.
    """

    def __init__(self) -> None:
        self.call_count = 0

    async def generate(
        self, request: AIRequest, provider_name: str | None = None
    ) -> AIResponse:
        self.call_count += 1
        return AIResponse(
            content="Sorry, I cannot help with that.",
            model="mock-model",
            provider="mock",
            usage=TokenUsage(),
        )


def _make_real_ai_service() -> AIService:
    settings = Settings(ai_default_provider="mock", ai_default_model="mock-model")
    return AIService(ProviderFactory(settings), settings)


def _make_agent(ai_service: AIService | None = None) -> ExecutiveSummaryAgent:
    return ExecutiveSummaryAgent(
        GenerateExecutiveSummaryTool(ai_service or _make_real_ai_service(), PromptManager())
    )


def _build_report_document(csv_path: Path) -> ReportDocument:
    """Build a real ReportDocument via the real pipeline - ReportService.build_report()
    is synchronous, so this needs no event loop of its own and is safe to call
    from inside an already-running one (unlike going through async ReportAgent.execute())."""
    dataframe_store = DataFrameStore()
    extractor = MetadataExtractor()
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

    dataset = ingestion_service.ingest(str(csv_path))
    cleaning_outcome = cleaning_service.clean(dataset)
    analysis_result = analysis_service.analyze(cleaning_outcome)
    visualization_result = visualization_service.generate(
        analysis_result, dataset=cleaning_outcome.dataset
    )
    return report_service.build_report(
        cleaning_outcome.dataset,
        cleaning_outcome=cleaning_outcome,
        analysis_result=analysis_result,
        visualization_result=visualization_result,
    )


def _step(
    report_document: ReportDocument,
    browser_result: dict | None = None,
    dataset_metadata: dict | None = None,
    analysis_metadata: dict | None = None,
    step_id: str = "s1",
) -> ExecutionStep:
    inputs: dict[str, object] = {
        "report_document": report_document.model_dump(mode="json")
    }
    if browser_result is not None:
        inputs["browser_agent_result"] = browser_result
    if dataset_metadata is not None:
        inputs["dataset_metadata"] = dataset_metadata
    if analysis_metadata is not None:
        inputs["analysis_metadata"] = analysis_metadata
    return ExecutionStep(
        step_id=step_id,
        name="Executive Summary Run",
        node_name="executive_summary_agent",
        inputs=inputs,
    )


def test_execute_with_a_report_document_produces_a_grounded_summary(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        csv_file = tmp_path / "sales.csv"
        csv_file.write_text(_CSV_CONTENT)
        document = _build_report_document(csv_file)
        agent = _make_agent()

        result = await agent.execute(_step(document), session_id="sess-1")

        assert result.status == ExecutionStatus.COMPLETED
        assert result.warnings == []
        assert result.executive_summary
        assert result.key_findings
        assert result.risks
        assert result.recommendations
        assert result.follow_up_actions
        assert 0.0 <= result.confidence <= 1.0
        assert result.execution_time >= 0.0
        assert result.metadata["session_id"] == "sess-1"
        assert result.metadata["report_id"] == document.report_id
        assert result.metadata["external_context_included"] is False

    asyncio.run(scenario())


def test_execute_calls_ai_service_generate_exactly_once(tmp_path: Path) -> None:
    async def scenario() -> None:
        csv_file = tmp_path / "sales.csv"
        csv_file.write_text(_CSV_CONTENT)
        document = _build_report_document(csv_file)
        ai_service = _make_real_ai_service()
        call_count = 0
        original_generate = ai_service.generate

        async def counting_generate(
            request: AIRequest, provider_name: str | None = None
        ) -> AIResponse:
            nonlocal call_count
            call_count += 1
            return await original_generate(request, provider_name)

        ai_service.generate = counting_generate  # type: ignore[method-assign]
        agent = _make_agent(ai_service)

        result = await agent.execute(_step(document), session_id="sess-1")

        assert result.status == ExecutionStatus.COMPLETED
        assert call_count == 1

    asyncio.run(scenario())


def test_execute_with_browser_result_marks_external_context_included(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        csv_file = tmp_path / "sales.csv"
        csv_file.write_text(_CSV_CONTENT)
        document = _build_report_document(csv_file)
        agent = _make_agent()

        browser_agent = BrowserAgent(SearchWebTool(BrowserService(MockBrowserProvider())))
        browser_step = ExecutionStep(
            step_id="b1",
            name="Browser Run",
            node_name="browser_agent",
            inputs={"search_request": "Acme Corp"},
        )
        browser_result = await browser_agent.execute(browser_step, session_id="sess-1")

        result = await agent.execute(
            _step(document, browser_result=browser_result.model_dump(mode="json")),
            session_id="sess-1",
        )

        assert result.status == ExecutionStatus.COMPLETED
        assert result.metadata["external_context_included"] is True

    asyncio.run(scenario())


def test_execute_carries_dataset_and_analysis_metadata_through_untouched(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        csv_file = tmp_path / "sales.csv"
        csv_file.write_text(_CSV_CONTENT)
        document = _build_report_document(csv_file)
        agent = _make_agent()

        result = await agent.execute(
            _step(
                document,
                dataset_metadata={"dataset_name": "sales", "row_count": 4},
                analysis_metadata={"kpi_count": 3},
            ),
            session_id="sess-1",
        )

        assert result.status == ExecutionStatus.COMPLETED
        assert result.metadata["dataset_metadata"] == {
            "dataset_name": "sales",
            "row_count": 4,
        }
        assert result.metadata["analysis_metadata"] == {"kpi_count": 3}

    asyncio.run(scenario())


def test_execute_raises_for_missing_session_id(tmp_path: Path) -> None:
    async def scenario() -> None:
        csv_file = tmp_path / "sales.csv"
        csv_file.write_text(_CSV_CONTENT)
        document = _build_report_document(csv_file)
        agent = _make_agent()

        with pytest.raises(InvalidAgentInputError):
            await agent.execute(_step(document), session_id=None)

    asyncio.run(scenario())


def test_execute_raises_for_missing_report_document() -> None:
    async def scenario() -> None:
        agent = _make_agent()
        step = ExecutionStep(
            step_id="s1", name="Bad", node_name="executive_summary_agent", inputs={}
        )

        with pytest.raises(InvalidAgentInputError):
            await agent.execute(step, session_id="sess-1")

    asyncio.run(scenario())


def test_execute_raises_for_an_invalid_report_document() -> None:
    async def scenario() -> None:
        agent = _make_agent()
        step = ExecutionStep(
            step_id="s1",
            name="Bad",
            node_name="executive_summary_agent",
            inputs={"report_document": {"not": "a real report"}},
        )

        with pytest.raises(InvalidAgentInputError):
            await agent.execute(step, session_id="sess-1")

    asyncio.run(scenario())


def test_execute_raises_for_an_invalid_browser_agent_result(tmp_path: Path) -> None:
    async def scenario() -> None:
        csv_file = tmp_path / "sales.csv"
        csv_file.write_text(_CSV_CONTENT)
        document = _build_report_document(csv_file)
        agent = _make_agent()
        step = ExecutionStep(
            step_id="s1",
            name="Bad",
            node_name="executive_summary_agent",
            inputs={
                "report_document": document.model_dump(mode="json"),
                "browser_agent_result": {"not": "a real browser result"},
            },
        )

        with pytest.raises(InvalidAgentInputError):
            await agent.execute(step, session_id="sess-1")

    asyncio.run(scenario())


def test_execute_raises_when_dataset_metadata_is_not_an_object(tmp_path: Path) -> None:
    async def scenario() -> None:
        csv_file = tmp_path / "sales.csv"
        csv_file.write_text(_CSV_CONTENT)
        document = _build_report_document(csv_file)
        agent = _make_agent()
        step = ExecutionStep(
            step_id="s1",
            name="Bad",
            node_name="executive_summary_agent",
            inputs={
                "report_document": document.model_dump(mode="json"),
                "dataset_metadata": "not-an-object",
            },
        )

        with pytest.raises(InvalidAgentInputError):
            await agent.execute(step, session_id="sess-1")

    asyncio.run(scenario())


def test_execute_on_a_malformed_ai_response_returns_a_failed_result_not_a_raise(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        csv_file = tmp_path / "sales.csv"
        csv_file.write_text(_CSV_CONTENT)
        document = _build_report_document(csv_file)
        agent = _make_agent(_NonJsonAIService())  # type: ignore[arg-type]

        result = await agent.execute(_step(document), session_id="sess-1")

        assert result.status == ExecutionStatus.FAILED
        assert result.warnings
        assert result.executive_summary == ""
        assert result.confidence == 0.0

    asyncio.run(scenario())
