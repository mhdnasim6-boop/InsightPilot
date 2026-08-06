"""Execution tests: ReportAgentNode adapting InsightPilotState <-> ReportAgentService.

Mirrors test_browser_agent_node.py. Unlike File/SQL/BrowserAgentNode,
ReportAgentNode reads its own inputs out of ``state.artifacts`` (whatever
FileAgentNode/SQLAgentNode already wrote), not out of
``state.variables`` — see ``ReportAgentNode``'s own module docstring for
why. Unit-level — no GraphBuilder/ExecutionEngine involved (see
test_report_agent_graph.py for the full graph-level integration).
"""

import asyncio
from pathlib import Path

from backend.agents.report.execution.report_agent import ReportAgent
from backend.agents.report.services.execution_result_store import (
    ReportAgentResultStore,
)
from backend.agents.report.services.report_agent_service import ReportAgentService
from backend.cleaning.profiling.profiler import DatasetProfilingService
from backend.ingestion.metadata.extractor import MetadataExtractor
from backend.ingestion.registry.dataframe_store import DataFrameStore
from backend.ingestion.registry.loader_registry import LoaderRegistry
from backend.ingestion.validators.validator import DatasetValidator
from backend.orchestration.nodes.report_agent_node import ReportAgentNode
from backend.orchestration.state.state import InsightPilotState
from backend.reporting.builders.report_builder import ReportBuilder
from backend.reporting.report_store import ReportStore
from backend.reporting.validation.validator import ReportValidator
from backend.services.cleaning_service import CleaningService
from backend.services.ingestion_service import IngestionService
from backend.services.report_service import ReportService
from backend.tools.execution.generate_report_tool import GenerateReportTool
from backend.utils.ids import generate_id
from backend.utils.time import utc_now

_CSV_CONTENT = "a,b\n1,2\n3,4\n"


def _make_node() -> ReportAgentNode:
    report_service = ReportService(ReportBuilder(), ReportValidator(), ReportStore())
    agent = ReportAgent(GenerateReportTool(report_service))
    return ReportAgentNode(ReportAgentService(agent, ReportAgentResultStore()))


def _file_agent_result(csv_path: Path, status: str = "completed") -> dict:
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
    dataset = ingestion_service.ingest(str(csv_path))
    cleaning_outcome = cleaning_service.clean(dataset)
    return {
        "step_id": "prior-step",
        "status": status,
        "dataset": cleaning_outcome.dataset.model_dump(mode="json"),
        "cleaning": cleaning_outcome.model_dump(mode="json"),
        "analysis": None,
        "visualization": None,
        "report": None,
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


def test_execute_reads_dataset_from_a_completed_file_agent_artifact(
    tmp_path: Path,
) -> None:
    csv_path = tmp_path / "t.csv"
    csv_path.write_text(_CSV_CONTENT)

    async def scenario() -> None:
        node = _make_node()
        state = _new_state(
            session_id="sess-1",
            variables={"report_config": {"template_type": "data_quality_report"}},
            artifacts={"file_agent_result": _file_agent_result(csv_path)},
        )

        updated = await node.execute(state)

        result = updated.artifacts["report_agent_result"]
        assert result["status"] == "completed"
        assert result["report_document"] is not None
        assert updated.current_node == "report_agent"
        assert updated.execution_trace == ["report_agent"]
        assert updated.errors == []

    asyncio.run(scenario())


def test_execute_falls_back_to_sql_agent_artifact_when_file_agent_failed(
    tmp_path: Path,
) -> None:
    csv_path = tmp_path / "t.csv"
    csv_path.write_text(_CSV_CONTENT)

    async def scenario() -> None:
        node = _make_node()
        state = _new_state(
            session_id="sess-1",
            variables={"report_config": {"template_type": "data_quality_report"}},
            artifacts={
                "file_agent_result": {
                    "step_id": "x",
                    "status": "failed",
                    "dataset": None,
                },
                "sql_agent_result": _file_agent_result(csv_path),
            },
        )

        updated = await node.execute(state)

        result = updated.artifacts["report_agent_result"]
        assert result["status"] == "completed"

    asyncio.run(scenario())


def test_execute_uses_step_id_from_state_metadata_when_present(tmp_path: Path) -> None:
    csv_path = tmp_path / "t.csv"
    csv_path.write_text(_CSV_CONTENT)

    async def scenario() -> None:
        node = _make_node()
        state = _new_state(
            session_id="sess-1",
            variables={"report_config": {"template_type": "data_quality_report"}},
            artifacts={"file_agent_result": _file_agent_result(csv_path)},
            metadata={"step_id": "my-step-42"},
        )

        updated = await node.execute(state)

        assert updated.artifacts["report_agent_result"]["step_id"] == "my-step-42"

    asyncio.run(scenario())


def test_execute_reports_failed_and_never_raises_when_no_pipeline_result_is_available() -> (
    None
):
    async def scenario() -> None:
        node = _make_node()
        state = _new_state(session_id="sess-1")  # no file/sql agent artifacts at all

        updated = await node.execute(state)  # must not raise

        result = updated.artifacts["report_agent_result"]
        assert result["status"] == "failed"
        assert updated.errors
        assert updated.current_node == "report_agent"

    asyncio.run(scenario())


def test_execute_ignores_a_failed_pipeline_artifact_with_no_dataset() -> None:
    async def scenario() -> None:
        node = _make_node()
        state = _new_state(
            session_id="sess-1",
            artifacts={
                "file_agent_result": {
                    "step_id": "x",
                    "status": "failed",
                    "dataset": None,
                }
            },
        )

        updated = await node.execute(state)  # must not raise

        result = updated.artifacts["report_agent_result"]
        assert result["status"] == "failed"

    asyncio.run(scenario())


def test_execute_preserves_prior_artifacts_and_execution_trace(tmp_path: Path) -> None:
    csv_path = tmp_path / "t.csv"
    csv_path.write_text(_CSV_CONTENT)

    async def scenario() -> None:
        node = _make_node()
        state = _new_state(
            session_id="sess-1",
            variables={"report_config": {"template_type": "data_quality_report"}},
            artifacts={
                "file_agent_result": _file_agent_result(csv_path),
                "earlier": "value",
            },
            execution_trace=["planner", "file_agent", "sql_agent", "browser_agent"],
        )

        updated = await node.execute(state)

        assert updated.artifacts["earlier"] == "value"
        assert updated.execution_trace == [
            "planner",
            "file_agent",
            "sql_agent",
            "browser_agent",
            "report_agent",
        ]

    asyncio.run(scenario())
