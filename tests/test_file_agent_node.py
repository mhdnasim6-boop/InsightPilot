"""Execution tests: FileAgentNode adapting InsightPilotState <-> FileAgentService.

Unit-level — no GraphBuilder/ExecutionEngine involved (see
test_file_agent_graph.py for the full graph-level integration). Proves
the node reads dataset_reference/generate_report from state.variables
exactly how PlanExecutor already flows ExecutionStep.inputs into the
graph, and never crashes the caller regardless of what FileAgent does.
"""

import asyncio
from pathlib import Path

from backend.agents.file.execution.file_agent import FileAgent
from backend.agents.file.services.execution_result_store import (
    AgentExecutionResultStore,
)
from backend.agents.file.services.file_agent_service import FileAgentService
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
from backend.orchestration.nodes.file_agent_node import FileAgentNode
from backend.orchestration.state.state import InsightPilotState
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
from backend.utils.ids import generate_id
from backend.utils.time import utc_now
from backend.visualization.charts.registry import default_generators
from backend.visualization.layouts.engine import LayoutEngine
from backend.visualization.recommendations.engine import ChartRecommendationEngine

_CSV_CONTENT = "a,b\n1,2\n3,4\n"


def _make_node() -> FileAgentNode:
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
    return FileAgentNode(FileAgentService(agent, AgentExecutionResultStore()))


def _new_state(**overrides: object) -> InsightPilotState:
    now = utc_now()
    defaults: dict[str, object] = {"execution_id": generate_id(), "created_at": now, "updated_at": now}
    defaults.update(overrides)
    return InsightPilotState.model_validate(defaults)


def test_execute_reads_dataset_reference_from_state_variables(tmp_path: Path) -> None:
    async def scenario() -> None:
        csv_file = tmp_path / "d.csv"
        csv_file.write_text(_CSV_CONTENT)
        node = _make_node()
        state = _new_state(session_id="sess-1", variables={"dataset_reference": str(csv_file)})

        updated = await node.execute(state)

        result = updated.artifacts["file_agent_result"]
        assert result["status"] == "completed"
        assert result["dataset"]["row_count"] == 2
        assert updated.current_node == "file_agent"
        assert updated.execution_trace == ["file_agent"]
        assert updated.errors == []

    asyncio.run(scenario())


def test_execute_uses_step_id_from_state_metadata_when_present(tmp_path: Path) -> None:
    async def scenario() -> None:
        csv_file = tmp_path / "d.csv"
        csv_file.write_text(_CSV_CONTENT)
        node = _make_node()
        state = _new_state(
            session_id="sess-1",
            variables={"dataset_reference": str(csv_file)},
            metadata={"step_id": "my-step-42"},
        )

        updated = await node.execute(state)

        assert updated.artifacts["file_agent_result"]["step_id"] == "my-step-42"

    asyncio.run(scenario())


def test_execute_never_raises_when_input_is_missing() -> None:
    async def scenario() -> None:
        node = _make_node()
        state = _new_state()  # no session_id, no variables

        updated = await node.execute(state)  # must not raise

        result = updated.artifacts["file_agent_result"]
        assert result["status"] == "failed"
        assert updated.errors  # the failure is surfaced on state.errors too
        assert updated.current_node == "file_agent"
        assert updated.execution_trace == ["file_agent"]

    asyncio.run(scenario())


def test_execute_never_raises_for_a_missing_file() -> None:
    async def scenario() -> None:
        node = _make_node()
        state = _new_state(session_id="sess-1", variables={"dataset_reference": "/no/such/file.csv"})

        updated = await node.execute(state)  # must not raise

        result = updated.artifacts["file_agent_result"]
        assert result["status"] == "failed"
        assert updated.errors

    asyncio.run(scenario())


def test_execute_preserves_prior_artifacts_and_execution_trace(tmp_path: Path) -> None:
    async def scenario() -> None:
        csv_file = tmp_path / "d.csv"
        csv_file.write_text(_CSV_CONTENT)
        node = _make_node()
        state = _new_state(
            session_id="sess-1",
            variables={"dataset_reference": str(csv_file)},
            artifacts={"earlier": "value"},
            execution_trace=["planner"],
        )

        updated = await node.execute(state)

        assert updated.artifacts["earlier"] == "value"
        assert updated.execution_trace == ["planner", "file_agent"]

    asyncio.run(scenario())
