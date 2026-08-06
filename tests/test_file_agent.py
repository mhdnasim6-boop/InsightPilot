"""Agent tests: FileAgent orchestrating the real pipeline for one ExecutionStep.

FileAgent never parses a file, cleans a DataFrame, computes a statistic,
or renders a chart — every assertion here checks that it correctly
sequenced calls into the real (not mocked) Ingestion/Cleaning/Analysis/
Visualization/Report services, never that it computed anything itself.
"""

import asyncio
from pathlib import Path

import pytest

from backend.agents.file.exceptions.errors import InvalidAgentInputError
from backend.agents.file.execution.file_agent import FileAgent
from backend.analysis.aggregations.engine import AggregationEngine
from backend.analysis.anomalies.engine import AnomalyEngine
from backend.analysis.correlations.engine import CorrelationEngine
from backend.analysis.insights.engine import InsightEngine
from backend.analysis.kpis.engine import KPIEngine
from backend.analysis.statistics.engine import DescriptiveStatisticsEngine
from backend.analysis.trends.engine import TrendEngine
from backend.cleaning.profiling.profiler import DatasetProfilingService
from backend.ingestion.metadata.extractor import MetadataExtractor
from backend.ingestion.registry.dataframe_store import DataFrameStore
from backend.ingestion.registry.dataset_store import BusinessDatasetStore
from backend.ingestion.registry.loader_registry import LoaderRegistry
from backend.ingestion.validators.validator import DatasetValidator
from backend.orchestration.state.state import ExecutionStatus
from backend.planning.models.step import ExecutionStep
from backend.reporting.builders.report_builder import ReportBuilder
from backend.reporting.report_store import ReportStore
from backend.reporting.validation.validator import ReportValidator
from backend.services.analysis_service import AnalysisService
from backend.services.cleaning_service import CleaningService
from backend.services.ingestion_service import IngestionService
from backend.services.report_service import ReportService
from backend.services.visualization_service import VisualizationService
from backend.tools.execution.analyze_dataset_tool import AnalyzeDatasetTool
from backend.tools.execution.clean_dataset_tool import CleanDatasetTool
from backend.tools.execution.generate_report_tool import GenerateReportTool
from backend.tools.execution.generate_visualization_tool import (
    GenerateVisualizationTool,
)
from backend.tools.execution.ingest_dataset_tool import IngestDatasetTool
from backend.visualization.charts.registry import default_generators
from backend.visualization.layouts.engine import LayoutEngine
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


def _make_agent() -> tuple[FileAgent, BusinessDatasetStore]:
    dataframe_store = DataFrameStore()
    extractor = MetadataExtractor()
    dataset_store = BusinessDatasetStore()
    ingestion_service = IngestionService(LoaderRegistry(), DatasetValidator(), extractor, dataframe_store)
    cleaning_service = CleaningService(
        ingestion_service, DatasetProfilingService(extractor), extractor, dataframe_store
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
    return agent, dataset_store


def _step(dataset_reference: str, generate_report: bool = False, step_id: str = "s1") -> ExecutionStep:
    return ExecutionStep(
        step_id=step_id,
        name="File Agent Run",
        node_name="file_agent",
        inputs={"dataset_reference": dataset_reference, "generate_report": generate_report},
    )


def test_execute_runs_the_full_pipeline_and_registers_datasets(tmp_path: Path) -> None:
    async def scenario() -> None:
        csv_file = tmp_path / "sales.csv"
        csv_file.write_text(_CSV_CONTENT)
        agent, dataset_store = _make_agent()

        result = await agent.execute(_step(str(csv_file), generate_report=True), session_id="sess-1")

        assert result.status == ExecutionStatus.COMPLETED
        assert result.warnings == []
        assert result.dataset is not None and result.dataset.row_count == 6
        assert result.cleaning is not None and result.cleaning.result.quality_score == 100.0
        assert result.analysis is not None and len(result.analysis.kpis) > 0
        assert result.visualization is not None and len(result.visualization.charts) > 0
        assert result.report is not None and result.report.sections
        assert result.execution_time >= 0.0
        assert result.metadata["session_id"] == "sess-1"
        assert result.metadata["dataset_reference"] == str(csv_file)

        # both the freshly ingested and the cleaned dataset must be registered
        assert dataset_store.get(result.dataset.dataset_id) is not None
        assert dataset_store.get(result.cleaning.dataset.dataset_id) is not None

    asyncio.run(scenario())


def test_execute_without_generate_report_leaves_report_none(tmp_path: Path) -> None:
    async def scenario() -> None:
        csv_file = tmp_path / "sales.csv"
        csv_file.write_text(_CSV_CONTENT)
        agent, _ = _make_agent()

        result = await agent.execute(_step(str(csv_file), generate_report=False), session_id="sess-1")

        assert result.status == ExecutionStatus.COMPLETED
        assert result.report is None

    asyncio.run(scenario())


def test_execute_raises_for_missing_dataset_reference() -> None:
    async def scenario() -> None:
        agent, _ = _make_agent()
        step = ExecutionStep(step_id="s1", name="Bad", node_name="file_agent", inputs={})

        with pytest.raises(InvalidAgentInputError):
            await agent.execute(step, session_id="sess-1")

    asyncio.run(scenario())


def test_execute_raises_for_missing_session_id() -> None:
    async def scenario() -> None:
        agent, _ = _make_agent()

        with pytest.raises(InvalidAgentInputError):
            await agent.execute(_step("/some/file.csv"), session_id=None)

    asyncio.run(scenario())


def test_execute_raises_for_blank_session_id() -> None:
    async def scenario() -> None:
        agent, _ = _make_agent()

        with pytest.raises(InvalidAgentInputError):
            await agent.execute(_step("/some/file.csv"), session_id="   ")

    asyncio.run(scenario())


def test_execute_on_a_missing_file_returns_a_failed_result_not_a_raise() -> None:
    async def scenario() -> None:
        agent, dataset_store = _make_agent()

        result = await agent.execute(_step("/no/such/file.csv"), session_id="sess-1")

        assert result.status == ExecutionStatus.FAILED
        assert result.warnings
        assert result.dataset is None
        assert result.cleaning is None
        assert dataset_store.list() == []  # nothing was ever registered

    asyncio.run(scenario())


def test_execute_on_cleaning_failure_still_returns_the_dataset_that_succeeded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    async def scenario() -> None:
        csv_file = tmp_path / "sales.csv"
        csv_file.write_text(_CSV_CONTENT)
        agent, dataset_store = _make_agent()

        class _BoomTool:
            async def execute(self, tool_input: object) -> None:
                raise RuntimeError("simulated cleaning failure")

        monkeypatch.setattr(agent, "_clean_dataset_tool", _BoomTool())

        result = await agent.execute(_step(str(csv_file)), session_id="sess-1")

        assert result.status == ExecutionStatus.FAILED
        assert "simulated cleaning failure" in result.warnings[0]
        assert result.dataset is not None  # ingestion had already succeeded
        assert result.cleaning is None
        assert dataset_store.get(result.dataset.dataset_id) is not None

    asyncio.run(scenario())
