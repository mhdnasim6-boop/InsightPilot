"""remember_agent_execution_result(): writes DATASET/ANALYSIS/VISUALIZATION
memories from an AgentExecutionResult — shared by FileAgentService and
SQLAgentService since both produce the exact same result shape (mirrors
how SQLAgentService already reuses ``AgentExecutionResult``/
``AgentExecutionResultStore`` directly from this package rather than
redefining equivalents).

REPORT memories are deliberately *not* written here: that is
``ReportService.build_report()``'s own job — the one place every
report is actually built, regardless of which agent (or the direct
``/reports`` endpoint) triggered it. Writing them here too would be
exactly the duplicated logic this phase forbids.
"""

from backend.agents.file.models.result import AgentExecutionResult
from backend.memory.models.memory_reference import MemoryReference
from backend.memory.models.memory_scope import MemoryScope
from backend.memory.models.memory_type import MemoryType
from backend.memory.services.memory_service import MemoryService


def remember_agent_execution_result(
    memory_service: MemoryService | None,
    result: AgentExecutionResult,
    agent_name: str,
    session_id: str | None,
) -> None:
    """Remember whatever DATASET/ANALYSIS/VISUALIZATION artifacts ``result`` carries."""
    if memory_service is None:
        return
    metadata = {"session_id": session_id}

    if result.dataset is not None:
        dataset = result.dataset
        memory_service.remember(
            title=f"Dataset: {dataset.dataset_name}",
            summary=f"{dataset.row_count} rows, {dataset.column_count} columns.",
            memory_type=MemoryType.DATASET,
            scope=MemoryScope.SESSION,
            content={
                "dataset_id": dataset.dataset_id,
                "row_count": dataset.row_count,
                "column_count": dataset.column_count,
            },
            tags=[agent_name, *dataset.tags],
            references=[MemoryReference(reference_type="dataset", reference_id=dataset.dataset_id)],
            metadata=metadata,
        )

    if result.analysis is not None:
        analysis = result.analysis
        memory_service.remember(
            title=f"Analysis of dataset {analysis.dataset_id}",
            summary=f"{len(analysis.kpis)} KPI(s), {len(analysis.insights)} insight(s).",
            memory_type=MemoryType.ANALYSIS,
            scope=MemoryScope.SESSION,
            content={"analysis_id": analysis.analysis_id, "dataset_id": analysis.dataset_id},
            tags=[agent_name],
            references=[
                MemoryReference(reference_type="analysis", reference_id=analysis.analysis_id),
                MemoryReference(reference_type="dataset", reference_id=analysis.dataset_id),
            ],
            metadata=metadata,
        )

    if result.visualization is not None:
        visualization = result.visualization
        memory_service.remember(
            title=f"Visualization for analysis {visualization.analysis_id}",
            summary=f"{len(visualization.charts)} chart(s).",
            memory_type=MemoryType.VISUALIZATION,
            scope=MemoryScope.SESSION,
            content={
                "visualization_id": visualization.visualization_id,
                "analysis_id": visualization.analysis_id,
            },
            tags=[agent_name],
            references=[MemoryReference(reference_type="analysis", reference_id=visualization.analysis_id)],
            metadata=metadata,
        )
