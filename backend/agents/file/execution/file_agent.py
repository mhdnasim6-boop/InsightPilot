"""FileAgent: orchestrates the existing pipeline for one ExecutionStep, via tools.

Ingestion -> Cleaning -> Analysis -> Visualization -> optionally Report.
Every step is a call into a ``Tool`` (Tool Layer, Phase 22) — never a
service directly — but each tool itself still wraps exactly one
already-existing, already-tested service; this class adds no
statistics, no chart logic, no file parsing of its own, exactly as
before. A downstream tool failing partway through is captured as a
FAILED ``AgentExecutionResult`` carrying whatever succeeded first —
never an uncaught exception. Only malformed *input* (see
``validate_agent_input``) raises immediately, since that's a
caller/programming error, not a legitimate runtime pipeline failure.
"""

import time

from loguru import logger

from backend.agents.file.models.result import AgentExecutionResult
from backend.agents.file.validation.input_validator import validate_agent_input
from backend.ingestion.registry.dataset_store import BusinessDatasetStore
from backend.orchestration.state.state import ExecutionStatus
from backend.planning.models.step import ExecutionStep
from backend.tools.execution.analyze_dataset_tool import AnalyzeDatasetTool
from backend.tools.execution.clean_dataset_tool import CleanDatasetTool
from backend.tools.execution.generate_report_tool import GenerateReportTool
from backend.tools.execution.generate_visualization_tool import (
    GenerateVisualizationTool,
)
from backend.tools.execution.ingest_dataset_tool import IngestDatasetTool
from backend.tools.models.inputs import (
    AnalyzeDatasetInput,
    CleanDatasetInput,
    GenerateReportInput,
    GenerateVisualizationInput,
    IngestDatasetInput,
)


class FileAgent:
    """Orchestrates Ingestion -> Cleaning -> Analysis -> Visualization -> (optional) Report, via tools."""

    def __init__(
        self,
        ingest_dataset_tool: IngestDatasetTool,
        clean_dataset_tool: CleanDatasetTool,
        analyze_dataset_tool: AnalyzeDatasetTool,
        generate_visualization_tool: GenerateVisualizationTool,
        generate_report_tool: GenerateReportTool,
        dataset_store: BusinessDatasetStore,
    ) -> None:
        self._ingest_dataset_tool = ingest_dataset_tool
        self._clean_dataset_tool = clean_dataset_tool
        self._analyze_dataset_tool = analyze_dataset_tool
        self._generate_visualization_tool = generate_visualization_tool
        self._generate_report_tool = generate_report_tool
        self._dataset_store = dataset_store

    async def execute(self, step: ExecutionStep, session_id: str | None) -> AgentExecutionResult:
        """Run the pipeline described by ``step`` for ``session_id``.

        Raises ``InvalidAgentInputError`` if ``step``/``session_id`` are
        malformed. Any failure from the pipeline itself (ingestion
        onward) is captured in the returned result's ``status``/
        ``warnings`` — this method never raises for that.
        """
        dataset_reference = validate_agent_input(step, session_id)
        generate_report = bool(step.inputs.get("generate_report", False))

        start = time.perf_counter()
        warnings: list[str] = []
        dataset = cleaning = analysis = visualization = report = None
        status = ExecutionStatus.COMPLETED

        try:
            dataset = await self._ingest_dataset_tool.execute(IngestDatasetInput(dataset_reference=dataset_reference))
            self._dataset_store.put(dataset)

            cleaning = await self._clean_dataset_tool.execute(CleanDatasetInput(dataset=dataset))
            self._dataset_store.put(cleaning.dataset)

            analysis = await self._analyze_dataset_tool.execute(AnalyzeDatasetInput(cleaning_outcome=cleaning))

            visualization = await self._generate_visualization_tool.execute(
                GenerateVisualizationInput(analysis_result=analysis, dataset=cleaning.dataset)
            )

            if generate_report:
                report = await self._generate_report_tool.execute(
                    GenerateReportInput(
                        dataset=cleaning.dataset,
                        cleaning_outcome=cleaning,
                        analysis_result=analysis,
                        visualization_result=visualization,
                    )
                )
        except Exception as exc:  # noqa: BLE001 - any pipeline stage's failure degrades to a FAILED result, not a crash
            logger.exception("FileAgent step '{}' failed", step.step_id)
            warnings.append(str(exc))
            status = ExecutionStatus.FAILED

        execution_time = time.perf_counter() - start
        return AgentExecutionResult(
            step_id=step.step_id,
            status=status,
            dataset=dataset,
            cleaning=cleaning,
            analysis=analysis,
            visualization=visualization,
            report=report,
            warnings=warnings,
            execution_time=execution_time,
            metadata={"session_id": session_id, "dataset_reference": dataset_reference},
        )
