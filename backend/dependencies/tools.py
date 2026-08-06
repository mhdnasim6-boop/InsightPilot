"""Tool Layer providers: one provider per tool, each wrapping exactly one
existing service, every tool also registered into a shared ToolRegistry.

Mirrors the rest of this package's caching convention: the registry
itself is a process-wide singleton (like ``EventBus``/``PlanEventBus``),
while individual tools are cheap, stateless wrappers constructed fresh
per request (like every agent itself) — only re-registered (idempotent,
by name) into the shared registry on each resolution.

Every tool returned here is wrapped in ``TracingTool`` before being
registered/returned — the one DI seam every agent's tool dependency
already passes through, so every tool call in the system is traced with
no change to any agent constructor or concrete tool implementation.
``TracingTool`` satisfies the same ``Tool`` contract its wrapped tool
does, so the concrete return-type annotations below stay accurate for
callers even though the object returned is a wrapper — the same
``# type: ignore[return-value]`` shape already used for this exact
pattern by ``_SpyTool`` in ``tests/test_agents_use_tools.py``.
"""

from functools import lru_cache
from typing import Any

from fastapi import Depends

from backend.ai.prompts.manager import PromptManager
from backend.dependencies.ai import get_ai_service, get_prompt_manager
from backend.dependencies.analysis import get_analysis_service
from backend.dependencies.browser import get_browser_service
from backend.dependencies.cleaning import get_cleaning_service
from backend.dependencies.ingestion import get_ingestion_service
from backend.dependencies.observability import get_observability_service
from backend.dependencies.realtime import get_realtime_service
from backend.dependencies.reporting import get_report_service
from backend.dependencies.sql_datasource import get_sql_data_source_service
from backend.dependencies.visualization import get_visualization_service
from backend.observability.services.observability_service import ObservabilityService
from backend.observability.services.tracing_tool import TracingTool
from backend.realtime.publishers.observability_publisher import RealtimePublishingTool
from backend.realtime.services.realtime_service import RealtimeService
from backend.services.ai_service import AIService
from backend.services.analysis_service import AnalysisService
from backend.services.browser_service import BrowserService
from backend.services.cleaning_service import CleaningService
from backend.services.ingestion_service import IngestionService
from backend.services.report_service import ReportService
from backend.services.sql_data_source_service import SQLDataSourceService
from backend.services.visualization_service import VisualizationService
from backend.tools.execution.analyze_dataset_tool import AnalyzeDatasetTool
from backend.tools.execution.clean_dataset_tool import CleanDatasetTool
from backend.tools.execution.generate_executive_summary_tool import (
    GenerateExecutiveSummaryTool,
)
from backend.tools.execution.generate_report_tool import GenerateReportTool
from backend.tools.execution.generate_visualization_tool import (
    GenerateVisualizationTool,
)
from backend.tools.execution.ingest_dataset_tool import IngestDatasetTool
from backend.tools.execution.query_database_tool import QueryDatabaseTool
from backend.tools.execution.search_web_tool import SearchWebTool
from backend.tools.registry.tool_registry import ToolRegistry


@lru_cache
def get_tool_registry() -> ToolRegistry:
    """Return the process-wide ToolRegistry singleton — every tool below registers into this."""
    return ToolRegistry()


def get_ingest_dataset_tool(
    ingestion_service: IngestionService = Depends(get_ingestion_service),
    registry: ToolRegistry = Depends(get_tool_registry),
    observability_service: ObservabilityService = Depends(get_observability_service),
    realtime_service: RealtimeService = Depends(get_realtime_service),
) -> IngestDatasetTool:
    """Provide IngestDatasetTool (traced), registered into the shared ToolRegistry."""
    tool: Any = RealtimePublishingTool(TracingTool(IngestDatasetTool(ingestion_service), observability_service), realtime_service)
    registry.register(tool)
    return tool


def get_clean_dataset_tool(
    cleaning_service: CleaningService = Depends(get_cleaning_service),
    registry: ToolRegistry = Depends(get_tool_registry),
    observability_service: ObservabilityService = Depends(get_observability_service),
    realtime_service: RealtimeService = Depends(get_realtime_service),
) -> CleanDatasetTool:
    """Provide CleanDatasetTool (traced), registered into the shared ToolRegistry."""
    tool: Any = RealtimePublishingTool(TracingTool(CleanDatasetTool(cleaning_service), observability_service), realtime_service)
    registry.register(tool)
    return tool


def get_analyze_dataset_tool(
    analysis_service: AnalysisService = Depends(get_analysis_service),
    registry: ToolRegistry = Depends(get_tool_registry),
    observability_service: ObservabilityService = Depends(get_observability_service),
    realtime_service: RealtimeService = Depends(get_realtime_service),
) -> AnalyzeDatasetTool:
    """Provide AnalyzeDatasetTool (traced), registered into the shared ToolRegistry."""
    tool: Any = RealtimePublishingTool(TracingTool(AnalyzeDatasetTool(analysis_service), observability_service), realtime_service)
    registry.register(tool)
    return tool


def get_generate_visualization_tool(
    visualization_service: VisualizationService = Depends(get_visualization_service),
    registry: ToolRegistry = Depends(get_tool_registry),
    observability_service: ObservabilityService = Depends(get_observability_service),
    realtime_service: RealtimeService = Depends(get_realtime_service),
) -> GenerateVisualizationTool:
    """Provide GenerateVisualizationTool (traced), registered into the shared ToolRegistry."""
    tool: Any = RealtimePublishingTool(TracingTool(GenerateVisualizationTool(visualization_service), observability_service), realtime_service)
    registry.register(tool)
    return tool


def get_generate_report_tool(
    report_service: ReportService = Depends(get_report_service),
    registry: ToolRegistry = Depends(get_tool_registry),
    observability_service: ObservabilityService = Depends(get_observability_service),
    realtime_service: RealtimeService = Depends(get_realtime_service),
) -> GenerateReportTool:
    """Provide GenerateReportTool (traced), registered into the shared ToolRegistry.

    Shared by FileAgent, SQLAgent, and ReportAgent's own DI wiring.
    """
    tool: Any = RealtimePublishingTool(TracingTool(GenerateReportTool(report_service), observability_service), realtime_service)
    registry.register(tool)
    return tool


def get_query_database_tool(
    sql_data_source_service: SQLDataSourceService = Depends(get_sql_data_source_service),
    registry: ToolRegistry = Depends(get_tool_registry),
    observability_service: ObservabilityService = Depends(get_observability_service),
    realtime_service: RealtimeService = Depends(get_realtime_service),
) -> QueryDatabaseTool:
    """Provide QueryDatabaseTool (traced), registered into the shared ToolRegistry."""
    tool: Any = RealtimePublishingTool(TracingTool(QueryDatabaseTool(sql_data_source_service), observability_service), realtime_service)
    registry.register(tool)
    return tool


def get_search_web_tool(
    browser_service: BrowserService = Depends(get_browser_service),
    registry: ToolRegistry = Depends(get_tool_registry),
    observability_service: ObservabilityService = Depends(get_observability_service),
    realtime_service: RealtimeService = Depends(get_realtime_service),
) -> SearchWebTool:
    """Provide SearchWebTool (traced), registered into the shared ToolRegistry."""
    tool: Any = RealtimePublishingTool(TracingTool(SearchWebTool(browser_service), observability_service), realtime_service)
    registry.register(tool)
    return tool


def get_generate_executive_summary_tool(
    ai_service: AIService = Depends(get_ai_service),
    prompt_manager: PromptManager = Depends(get_prompt_manager),
    registry: ToolRegistry = Depends(get_tool_registry),
    observability_service: ObservabilityService = Depends(get_observability_service),
    realtime_service: RealtimeService = Depends(get_realtime_service),
) -> GenerateExecutiveSummaryTool:
    """Provide GenerateExecutiveSummaryTool (traced), registered into the shared ToolRegistry."""
    tool: Any = RealtimePublishingTool(TracingTool(GenerateExecutiveSummaryTool(ai_service, prompt_manager), observability_service), realtime_service)
    registry.register(tool)
    return tool
