"""Agent tests: ReportAgent orchestrating the real ReportService for one ExecutionStep.

ReportAgent never computes a KPI, builds a chart, analyzes data, reads a
file, queries SQL, or searches the web — every assertion here checks
that it correctly sequenced one call into the real (not mocked)
ReportService, never that it computed anything itself. Every pipeline
input (BusinessDataset/CleaningOutcome/AnalysisResult/
VisualizationResult) is real, produced by the real Ingestion/Cleaning/
Analysis/Visualization services against a real CSV — mirroring
test_file_agent.py's own approach — then round-tripped through
``model_dump(mode="json")`` into ``step.inputs``, exactly as the
REST/graph channel carries them.
"""

import asyncio
from pathlib import Path

import pytest

from backend.agents.browser.execution.browser_agent import BrowserAgent
from backend.agents.file.exceptions.errors import InvalidAgentInputError
from backend.agents.report.execution.report_agent import ReportAgent
from backend.analysis.aggregations.engine import AggregationEngine
from backend.analysis.anomalies.engine import AnomalyEngine
from backend.analysis.correlations.engine import CorrelationEngine
from backend.analysis.insights.engine import InsightEngine
from backend.analysis.kpis.engine import KPIEngine
from backend.analysis.models.result import AnalysisResult
from backend.analysis.statistics.engine import DescriptiveStatisticsEngine
from backend.analysis.trends.engine import TrendEngine
from backend.browser.providers.mock import MockBrowserProvider
from backend.cleaning.models.outcome import CleaningOutcome
from backend.cleaning.profiling.profiler import DatasetProfilingService
from backend.ingestion.metadata.extractor import MetadataExtractor
from backend.ingestion.models.dataset import BusinessDataset
from backend.ingestion.registry.dataframe_store import DataFrameStore
from backend.ingestion.registry.loader_registry import LoaderRegistry
from backend.ingestion.validators.validator import DatasetValidator
from backend.orchestration.state.state import ExecutionStatus
from backend.planning.models.step import ExecutionStep
from backend.reporting.builders.report_builder import ReportBuilder
from backend.reporting.report_store import ReportStore
from backend.reporting.validation.validator import ReportValidator
from backend.services.analysis_service import AnalysisService
from backend.services.browser_service import BrowserService
from backend.services.cleaning_service import CleaningService
from backend.services.ingestion_service import IngestionService
from backend.services.report_service import ReportService
from backend.services.visualization_service import VisualizationService
from backend.tools.execution.generate_report_tool import GenerateReportTool
from backend.tools.execution.search_web_tool import SearchWebTool
from backend.visualization.charts.registry import default_generators
from backend.visualization.layouts.engine import LayoutEngine
from backend.visualization.models.result import VisualizationResult
from backend.visualization.recommendations.engine import ChartRecommendationEngine

_CSV_CONTENT = (
    "date,region,revenue,cost\n"
    "2024-01-01,East,1000,600\n"
    "2024-02-01,East,1100,650\n"
    "2024-03-01,East,1180,680\n"
    "2024-01-01,West,200,120\n"
    "2024-02-01,West,210,130\n"
    "2024-03-01,West,9000,5000\n"
)


def _build_pipeline_outputs(
    csv_path: Path,
) -> tuple[BusinessDataset, CleaningOutcome, AnalysisResult, VisualizationResult]:
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

    dataset = ingestion_service.ingest(str(csv_path))
    cleaning_outcome = cleaning_service.clean(dataset)
    analysis_result = analysis_service.analyze(cleaning_outcome)
    visualization_result = visualization_service.generate(
        analysis_result, dataset=cleaning_outcome.dataset
    )
    return (
        cleaning_outcome.dataset,
        cleaning_outcome,
        analysis_result,
        visualization_result,
    )


def _make_agent() -> ReportAgent:
    return ReportAgent(GenerateReportTool(ReportService(ReportBuilder(), ReportValidator(), ReportStore())))


def _step(
    dataset: BusinessDataset,
    cleaning_outcome: CleaningOutcome | None = None,
    analysis_result: AnalysisResult | None = None,
    visualization_result: VisualizationResult | None = None,
    browser_result: object | None = None,
    report_config: dict[str, object] | None = None,
    step_id: str = "s1",
) -> ExecutionStep:
    inputs: dict[str, object] = {"dataset": dataset.model_dump(mode="json")}
    if cleaning_outcome is not None:
        inputs["cleaning_outcome"] = cleaning_outcome.model_dump(mode="json")
    if analysis_result is not None:
        inputs["analysis_result"] = analysis_result.model_dump(mode="json")
    if visualization_result is not None:
        inputs["visualization_result"] = visualization_result.model_dump(mode="json")
    if browser_result is not None:
        inputs["browser_agent_result"] = browser_result  # already a JSON-shaped dict
    if report_config is not None:
        inputs["report_config"] = report_config
    return ExecutionStep(
        step_id=step_id,
        name="Report Agent Run",
        node_name="report_agent",
        inputs=inputs,
    )


def test_execute_with_full_pipeline_outputs_builds_a_complete_report(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        csv_file = tmp_path / "sales.csv"
        csv_file.write_text(_CSV_CONTENT)
        dataset, cleaning_outcome, analysis_result, visualization_result = (
            _build_pipeline_outputs(csv_file)
        )
        agent = _make_agent()

        result = await agent.execute(
            _step(dataset, cleaning_outcome, analysis_result, visualization_result),
            session_id="sess-1",
        )

        assert result.status == ExecutionStatus.COMPLETED
        assert result.warnings == []
        assert result.report_id is not None
        assert result.report_document is not None
        assert result.report_document.report_id == result.report_id
        assert result.report_document.sections  # a full pipeline produces real sections
        assert result.execution_time >= 0.0
        assert result.metadata["session_id"] == "sess-1"
        assert result.metadata["dataset_id"] == dataset.dataset_id
        assert result.metadata["template_type"] == "business_report"
        assert result.metadata["external_context"] is None

    asyncio.run(scenario())


def test_execute_with_dataset_and_cleaning_only_builds_a_minimal_data_quality_report(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        csv_file = tmp_path / "sales.csv"
        csv_file.write_text(_CSV_CONTENT)
        dataset, cleaning_outcome, _, _ = _build_pipeline_outputs(csv_file)
        agent = _make_agent()

        # data_quality_report only requires Overview/DatasetSummary/CleaningSummary -
        # buildable from dataset+cleaning alone, no AnalysisResult/VisualizationResult needed.
        result = await agent.execute(
            _step(
                dataset,
                cleaning_outcome,
                report_config={"template_type": "data_quality_report"},
            ),
            session_id="sess-1",
        )

        assert result.status == ExecutionStatus.COMPLETED
        assert result.report_document is not None
        # No KPI/Charts section without an AnalysisResult/VisualizationResult -
        # ReportBuilder's own graceful degradation, never fabricated by ReportAgent.
        section_ids = {
            section.section_id for section in result.report_document.sections
        }
        assert section_ids == {"overview", "dataset_summary", "cleaning_summary"}

    asyncio.run(scenario())


def test_execute_on_a_business_report_missing_analysis_fails_validation_gracefully(
    tmp_path: Path,
) -> None:
    """business_report requires a KPIs section, which needs a real AnalysisResult to build -
    a real (not simulated) ReportService validation failure, degrading to FAILED, not a raise."""

    async def scenario() -> None:
        csv_file = tmp_path / "sales.csv"
        csv_file.write_text(_CSV_CONTENT)
        dataset, _, _, _ = _build_pipeline_outputs(csv_file)
        agent = _make_agent()

        result = await agent.execute(_step(dataset), session_id="sess-1")

        assert result.status == ExecutionStatus.FAILED
        assert result.warnings
        assert result.report_id is None
        assert result.report_document is None

    asyncio.run(scenario())


def test_execute_with_browser_result_summarizes_external_context_without_changing_the_report(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        csv_file = tmp_path / "sales.csv"
        csv_file.write_text(_CSV_CONTENT)
        dataset, cleaning_outcome, analysis_result, visualization_result = (
            _build_pipeline_outputs(csv_file)
        )
        agent = _make_agent()

        browser_agent = BrowserAgent(SearchWebTool(BrowserService(MockBrowserProvider())))
        browser_step = ExecutionStep(
            step_id="b1",
            name="Browser Run",
            node_name="browser_agent",
            inputs={"search_request": "Acme Corp"},
        )
        browser_result = await browser_agent.execute(browser_step, session_id="sess-1")

        with_context = await agent.execute(
            _step(
                dataset,
                cleaning_outcome,
                analysis_result,
                visualization_result,
                browser_result=browser_result.model_dump(mode="json"),
                step_id="with-context",
            ),
            session_id="sess-1",
        )
        without_context = await agent.execute(
            _step(
                dataset,
                cleaning_outcome,
                analysis_result,
                visualization_result,
                step_id="without-context",
            ),
            session_id="sess-1",
        )

        assert with_context.status == ExecutionStatus.COMPLETED
        external_context = with_context.metadata["external_context"]
        assert external_context is not None
        assert external_context["queries"] == ["Acme Corp"]
        assert external_context["source_count"] == 3
        assert external_context["summaries"][0]["query"] == "Acme Corp"

        # The report itself never depends on whether BrowserAgent ran -
        # same sections/titles either way, only ReportAgentResult.metadata differs.
        assert [s.section_id for s in with_context.report_document.sections] == [
            s.section_id for s in without_context.report_document.sections
        ]
        assert without_context.metadata["external_context"] is None

    asyncio.run(scenario())


def test_execute_raises_for_missing_session_id(tmp_path: Path) -> None:
    async def scenario() -> None:
        csv_file = tmp_path / "sales.csv"
        csv_file.write_text(_CSV_CONTENT)
        dataset, _, _, _ = _build_pipeline_outputs(csv_file)
        agent = _make_agent()

        with pytest.raises(InvalidAgentInputError):
            await agent.execute(_step(dataset), session_id=None)

    asyncio.run(scenario())


def test_execute_raises_for_missing_dataset() -> None:
    async def scenario() -> None:
        agent = _make_agent()
        step = ExecutionStep(
            step_id="s1", name="Bad", node_name="report_agent", inputs={}
        )

        with pytest.raises(InvalidAgentInputError):
            await agent.execute(step, session_id="sess-1")

    asyncio.run(scenario())


def test_execute_raises_for_an_invalid_dataset() -> None:
    async def scenario() -> None:
        agent = _make_agent()
        step = ExecutionStep(
            step_id="s1",
            name="Bad",
            node_name="report_agent",
            inputs={"dataset": {"not": "a real dataset"}},
        )

        with pytest.raises(InvalidAgentInputError):
            await agent.execute(step, session_id="sess-1")

    asyncio.run(scenario())


def test_execute_raises_for_a_report_config_that_is_not_an_object(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        csv_file = tmp_path / "sales.csv"
        csv_file.write_text(_CSV_CONTENT)
        dataset, _, _, _ = _build_pipeline_outputs(csv_file)
        agent = _make_agent()
        step = ExecutionStep(
            step_id="s1",
            name="Bad",
            node_name="report_agent",
            inputs={
                "dataset": dataset.model_dump(mode="json"),
                "report_config": "not-an-object",
            },
        )

        with pytest.raises(InvalidAgentInputError):
            await agent.execute(step, session_id="sess-1")

    asyncio.run(scenario())


def test_execute_raises_for_an_unknown_template_type(tmp_path: Path) -> None:
    async def scenario() -> None:
        csv_file = tmp_path / "sales.csv"
        csv_file.write_text(_CSV_CONTENT)
        dataset, _, _, _ = _build_pipeline_outputs(csv_file)
        agent = _make_agent()

        with pytest.raises(InvalidAgentInputError):
            await agent.execute(
                _step(dataset, report_config={"template_type": "not-a-real-template"}),
                session_id="sess-1",
            )

    asyncio.run(scenario())


def test_execute_applies_report_config_title_theme_and_template_type(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        csv_file = tmp_path / "sales.csv"
        csv_file.write_text(_CSV_CONTENT)
        dataset, cleaning_outcome, analysis_result, visualization_result = (
            _build_pipeline_outputs(csv_file)
        )
        agent = _make_agent()

        # technical_report requires Overview/DatasetSummary/Analysis - give it
        # every pipeline output so the real ReportValidator passes.
        result = await agent.execute(
            _step(
                dataset,
                cleaning_outcome,
                analysis_result,
                visualization_result,
                report_config={
                    "template_type": "technical_report",
                    "theme": "dark",
                    "title": "Custom Title",
                    "subtitle": "Custom Subtitle",
                    "author": "InsightPilot",
                },
            ),
            session_id="sess-1",
        )

        assert result.status == ExecutionStatus.COMPLETED
        assert result.report_document.title == "Custom Title"
        assert result.report_document.subtitle == "Custom Subtitle"
        assert result.report_document.author == "InsightPilot"
        assert result.report_document.theme == "dark"
        assert result.metadata["template_type"] == "technical_report"

    asyncio.run(scenario())


def test_execute_on_a_report_building_failure_returns_a_failed_result_not_a_raise(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def scenario() -> None:
        csv_file = tmp_path / "sales.csv"
        csv_file.write_text(_CSV_CONTENT)
        dataset, _, _, _ = _build_pipeline_outputs(csv_file)
        agent = _make_agent()

        class _BoomTool:
            async def execute(self, tool_input: object) -> None:
                raise RuntimeError("simulated report-building failure")

        monkeypatch.setattr(agent, "_generate_report_tool", _BoomTool())

        result = await agent.execute(_step(dataset), session_id="sess-1")

        assert result.status == ExecutionStatus.FAILED
        assert "simulated report-building failure" in result.warnings[0]
        assert result.report_id is None
        assert result.report_document is None

    asyncio.run(scenario())
