"""FileAgent providers: result store, FileAgent, FileAgentService."""

from functools import lru_cache

from fastapi import Depends

from backend.agents.file.execution.file_agent import FileAgent
from backend.agents.file.services.execution_result_store import (
    AgentExecutionResultStore,
)
from backend.agents.file.services.file_agent_service import FileAgentService
from backend.dependencies.ingestion import get_business_dataset_store
from backend.dependencies.memory import get_memory_service
from backend.dependencies.tools import (
    get_analyze_dataset_tool,
    get_clean_dataset_tool,
    get_generate_report_tool,
    get_generate_visualization_tool,
    get_ingest_dataset_tool,
)
from backend.ingestion.registry.dataset_store import BusinessDatasetStore
from backend.memory.services.memory_service import MemoryService
from backend.tools.execution.analyze_dataset_tool import AnalyzeDatasetTool
from backend.tools.execution.clean_dataset_tool import CleanDatasetTool
from backend.tools.execution.generate_report_tool import GenerateReportTool
from backend.tools.execution.generate_visualization_tool import (
    GenerateVisualizationTool,
)
from backend.tools.execution.ingest_dataset_tool import IngestDatasetTool


@lru_cache
def get_agent_execution_result_store() -> AgentExecutionResultStore:
    """Return the process-wide AgentExecutionResultStore singleton.

    Cached for the same reason as ``get_report_store``: a result
    produced by one request (or one graph run) must still be fetchable
    ("Get execution result") in a later one.
    """
    return AgentExecutionResultStore()


def get_file_agent(
    ingest_dataset_tool: IngestDatasetTool = Depends(get_ingest_dataset_tool),
    clean_dataset_tool: CleanDatasetTool = Depends(get_clean_dataset_tool),
    analyze_dataset_tool: AnalyzeDatasetTool = Depends(get_analyze_dataset_tool),
    generate_visualization_tool: GenerateVisualizationTool = Depends(get_generate_visualization_tool),
    generate_report_tool: GenerateReportTool = Depends(get_generate_report_tool),
    dataset_store: BusinessDatasetStore = Depends(get_business_dataset_store),
) -> FileAgent:
    """Provide FileAgent — orchestrates tools, never a business-logic implementation itself."""
    return FileAgent(
        ingest_dataset_tool,
        clean_dataset_tool,
        analyze_dataset_tool,
        generate_visualization_tool,
        generate_report_tool,
        dataset_store,
    )


def get_file_agent_service(
    agent: FileAgent = Depends(get_file_agent),
    result_store: AgentExecutionResultStore = Depends(get_agent_execution_result_store),
    memory_service: MemoryService = Depends(get_memory_service),
) -> FileAgentService:
    """Provide FileAgentService — the only object that should be used to run FileAgent or fetch its results.

    Not itself cached (like ``get_report_service``): FileAgentService
    holds no state of its own — the one thing that must persist across
    callers is ``AgentExecutionResultStore``'s contents, and that store
    is already the cached singleton.
    """
    return FileAgentService(agent, result_store, memory_service)
