"""Execution tests: ExecutiveSummaryAgentNode adapting InsightPilotState <->
ExecutiveSummaryService. Mirrors test_report_agent_node.py: like
ReportAgentNode, this node reads its own inputs out of ``state.artifacts``
(whatever ReportAgentNode already wrote), not out of ``state.variables``.
Unit-level — no GraphBuilder/ExecutionEngine involved (see
test_executive_summary_agent_graph.py for the full graph-level
integration).
"""

import asyncio
from pathlib import Path

from backend.agents.executive_summary.execution.executive_summary_agent import (
    ExecutiveSummaryAgent,
)
from backend.agents.executive_summary.services.execution_result_store import (
    ExecutiveSummaryResultStore,
)
from backend.agents.executive_summary.services.executive_summary_service import (
    ExecutiveSummaryService,
)
from backend.ai.prompts.manager import PromptManager
from backend.ai.providers.factory import ProviderFactory
from backend.cleaning.profiling.profiler import DatasetProfilingService
from backend.ingestion.metadata.extractor import MetadataExtractor
from backend.ingestion.registry.dataframe_store import DataFrameStore
from backend.ingestion.registry.loader_registry import LoaderRegistry
from backend.ingestion.validators.validator import DatasetValidator
from backend.orchestration.nodes.executive_summary_agent_node import (
    ExecutiveSummaryAgentNode,
)
from backend.orchestration.state.state import InsightPilotState
from backend.reporting.builders.report_builder import ReportBuilder
from backend.reporting.report_store import ReportStore
from backend.reporting.templates.report_template import ReportTemplateType
from backend.reporting.validation.validator import ReportValidator
from backend.services.ai_service import AIService
from backend.services.cleaning_service import CleaningService
from backend.services.ingestion_service import IngestionService
from backend.services.report_service import ReportService
from backend.tools.execution.generate_executive_summary_tool import (
    GenerateExecutiveSummaryTool,
)
from backend.utils.ids import generate_id
from backend.utils.time import utc_now
from config.settings import Settings

_CSV_CONTENT = "a,b\n1,2\n3,4\n"


def _make_node() -> ExecutiveSummaryAgentNode:
    settings = Settings(ai_default_provider="mock", ai_default_model="mock-model")
    ai_service = AIService(ProviderFactory(settings), settings)
    agent = ExecutiveSummaryAgent(GenerateExecutiveSummaryTool(ai_service, PromptManager()))
    return ExecutiveSummaryAgentNode(
        ExecutiveSummaryService(agent, ExecutiveSummaryResultStore())
    )


def _report_agent_result(csv_path: Path, status: str = "completed") -> dict:
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
    report_service = ReportService(ReportBuilder(), ReportValidator(), ReportStore())
    dataset = ingestion_service.ingest(str(csv_path))
    cleaning_outcome = cleaning_service.clean(dataset)
    document = report_service.build_report(
        cleaning_outcome.dataset,
        cleaning_outcome=cleaning_outcome,
        template_type=ReportTemplateType.DATA_QUALITY_REPORT,
    )
    return {
        "step_id": "prior-step",
        "status": status,
        "report_id": document.report_id,
        "report_document": document.model_dump(mode="json"),
        "warnings": [],
        "execution_time": 0.01,
        "metadata": {},
    }


def _new_state(**overrides: object) -> InsightPilotState:
    now = utc_now()
    defaults: dict[str, object] = {
        "execution_id": generate_id(),
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    return InsightPilotState.model_validate(defaults)


def test_execute_reads_report_document_from_a_completed_report_agent_artifact(
    tmp_path: Path,
) -> None:
    csv_path = tmp_path / "t.csv"
    csv_path.write_text(_CSV_CONTENT)

    async def scenario() -> None:
        node = _make_node()
        state = _new_state(
            session_id="sess-1",
            artifacts={"report_agent_result": _report_agent_result(csv_path)},
        )

        updated = await node.execute(state)

        result = updated.artifacts["executive_summary_result"]
        assert result["status"] == "completed"
        assert result["executive_summary"]
        assert updated.current_node == "executive_summary_agent"
        assert updated.execution_trace == ["executive_summary_agent"]
        assert updated.errors == []

    asyncio.run(scenario())


def test_execute_uses_step_id_from_state_metadata_when_present(tmp_path: Path) -> None:
    csv_path = tmp_path / "t.csv"
    csv_path.write_text(_CSV_CONTENT)

    async def scenario() -> None:
        node = _make_node()
        state = _new_state(
            session_id="sess-1",
            artifacts={"report_agent_result": _report_agent_result(csv_path)},
            metadata={"step_id": "my-step-42"},
        )

        updated = await node.execute(state)

        assert updated.artifacts["executive_summary_result"]["step_id"] == "my-step-42"

    asyncio.run(scenario())


def test_execute_reports_failed_and_never_raises_when_no_report_agent_result_is_available() -> (
    None
):
    async def scenario() -> None:
        node = _make_node()
        state = _new_state(
            session_id="sess-1"
        )  # no report_agent_result artifact at all

        updated = await node.execute(state)  # must not raise

        result = updated.artifacts["executive_summary_result"]
        assert result["status"] == "failed"
        assert updated.errors
        assert updated.current_node == "executive_summary_agent"

    asyncio.run(scenario())


def test_execute_ignores_a_failed_report_agent_artifact_with_no_report_document() -> (
    None
):
    async def scenario() -> None:
        node = _make_node()
        state = _new_state(
            session_id="sess-1",
            artifacts={
                "report_agent_result": {
                    "step_id": "x",
                    "status": "failed",
                    "report_document": None,
                }
            },
        )

        updated = await node.execute(state)  # must not raise

        result = updated.artifacts["executive_summary_result"]
        assert result["status"] == "failed"

    asyncio.run(scenario())


def test_execute_includes_completed_browser_agent_result_as_external_context(
    tmp_path: Path,
) -> None:
    csv_path = tmp_path / "t.csv"
    csv_path.write_text(_CSV_CONTENT)

    async def scenario() -> None:
        node = _make_node()
        browser_result = {
            "step_id": "b1",
            "status": "completed",
            "sources": [],
            "summaries": [
                {
                    "query": "Acme Corp",
                    "sources": [],
                    "summary": "Found nothing notable.",
                }
            ],
            "warnings": [],
            "execution_time": 0.01,
            "metadata": {"queries": ["Acme Corp"]},
        }
        state = _new_state(
            session_id="sess-1",
            artifacts={
                "report_agent_result": _report_agent_result(csv_path),
                "browser_agent_result": browser_result,
            },
        )

        updated = await node.execute(state)

        result = updated.artifacts["executive_summary_result"]
        assert result["status"] == "completed"
        assert result["metadata"]["external_context_included"] is True

    asyncio.run(scenario())


def test_execute_ignores_a_skipped_browser_agent_result(tmp_path: Path) -> None:
    csv_path = tmp_path / "t.csv"
    csv_path.write_text(_CSV_CONTENT)

    async def scenario() -> None:
        node = _make_node()
        skipped_browser_result = {
            "step_id": "b1",
            "status": "skipped",
            "sources": [],
            "summaries": [],
        }
        state = _new_state(
            session_id="sess-1",
            artifacts={
                "report_agent_result": _report_agent_result(csv_path),
                "browser_agent_result": skipped_browser_result,
            },
        )

        updated = await node.execute(state)

        result = updated.artifacts["executive_summary_result"]
        assert result["status"] == "completed"
        assert result["metadata"]["external_context_included"] is False

    asyncio.run(scenario())


def test_execute_preserves_prior_artifacts_and_execution_trace(tmp_path: Path) -> None:
    csv_path = tmp_path / "t.csv"
    csv_path.write_text(_CSV_CONTENT)

    async def scenario() -> None:
        node = _make_node()
        state = _new_state(
            session_id="sess-1",
            artifacts={
                "report_agent_result": _report_agent_result(csv_path),
                "earlier": "value",
            },
            execution_trace=[
                "planner",
                "file_agent",
                "sql_agent",
                "browser_agent",
                "report_agent",
            ],
        )

        updated = await node.execute(state)

        assert updated.artifacts["earlier"] == "value"
        assert updated.execution_trace == [
            "planner",
            "file_agent",
            "sql_agent",
            "browser_agent",
            "report_agent",
            "executive_summary_agent",
        ]

    asyncio.run(scenario())
