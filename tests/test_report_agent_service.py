"""Tests for ReportAgentService: execute_step stores results; get_result/list_results
fetch them. Mirrors test_browser_agent_service.py.
"""

import asyncio
from pathlib import Path

import pytest

from backend.agents.file.exceptions.errors import AgentExecutionNotFoundError
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
from backend.orchestration.state.state import ExecutionStatus
from backend.planning.models.step import ExecutionStep
from backend.reporting.builders.report_builder import ReportBuilder
from backend.reporting.report_store import ReportStore
from backend.reporting.validation.validator import ReportValidator
from backend.services.cleaning_service import CleaningService
from backend.services.ingestion_service import IngestionService
from backend.services.report_service import ReportService
from backend.tools.execution.generate_report_tool import GenerateReportTool

_CSV_CONTENT = "a,b\n1,2\n3,4\n"


def _make_service() -> ReportAgentService:
    report_service = ReportService(ReportBuilder(), ReportValidator(), ReportStore())
    agent = ReportAgent(GenerateReportTool(report_service))
    return ReportAgentService(agent, ReportAgentResultStore())


def _step(csv_path: Path, step_id: str) -> ExecutionStep:
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
    return ExecutionStep(
        step_id=step_id,
        name="Run",
        node_name="report_agent",
        inputs={
            "dataset": cleaning_outcome.dataset.model_dump(mode="json"),
            "cleaning_outcome": cleaning_outcome.model_dump(mode="json"),
            "report_config": {"template_type": "data_quality_report"},
        },
    )


def test_execute_step_stores_and_returns_the_same_result(tmp_path: Path) -> None:
    csv_path = tmp_path / "t.csv"
    csv_path.write_text(_CSV_CONTENT)

    async def scenario() -> None:
        service = _make_service()

        result = await service.execute_step(_step(csv_path, "s1"), session_id="sess-1")

        assert result.status == ExecutionStatus.COMPLETED
        assert service.get_result("s1") == result

    asyncio.run(scenario())


def test_get_result_raises_for_an_unknown_step_id() -> None:
    service = _make_service()
    with pytest.raises(AgentExecutionNotFoundError):
        service.get_result("never-ran")


def test_list_results_returns_most_recent_first(tmp_path: Path) -> None:
    csv_path = tmp_path / "t.csv"
    csv_path.write_text(_CSV_CONTENT)

    async def scenario() -> None:
        service = _make_service()

        first = await service.execute_step(_step(csv_path, "s1"), session_id="sess-1")
        second = await service.execute_step(_step(csv_path, "s2"), session_id="sess-1")

        listed = service.list_results()
        assert listed[0].step_id == second.step_id
        assert listed[1].step_id == first.step_id

    asyncio.run(scenario())


def test_execute_step_overwrites_a_result_for_a_repeated_step_id(
    tmp_path: Path,
) -> None:
    csv_path = tmp_path / "t.csv"
    csv_path.write_text(_CSV_CONTENT)

    async def scenario() -> None:
        service = _make_service()

        await service.execute_step(_step(csv_path, "s1"), session_id="sess-1")
        await service.execute_step(_step(csv_path, "s1"), session_id="sess-2")

        assert service.get_result("s1").metadata["session_id"] == "sess-2"
        assert len(service.list_results()) == 1

    asyncio.run(scenario())
