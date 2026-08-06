"""Tests for EnvironmentReport/DependencyReport builders and DiagnosticsService,
built from real (not mocked) collaborators — a real PluginRegistry/
ToolRegistry/MemoryService, exactly the same objects DI would hand a
real request.
"""

from pathlib import Path

from backend.memory.exporters.json_exporter import JSONMemoryExporter
from backend.memory.exporters.markdown_exporter import MarkdownMemoryExporter
from backend.memory.retrieval.retrieval_engine import RetrievalEngine
from backend.memory.services.memory_service import MemoryService
from backend.memory.store.memory_store import MemoryStore
from backend.memory.summarization.memory_summarizer import MemorySummarizer
from backend.observability.services.observability_service import ObservabilityService
from backend.observability.stores.trace_store import TraceStore
from backend.operations.configuration.configuration_validator import (
    ConfigurationValidator,
)
from backend.operations.diagnostics.dependency_report import build_dependency_report
from backend.operations.diagnostics.environment_report import build_environment_report
from backend.operations.feature_flags.feature_flag_service import FeatureFlagService
from backend.operations.health.diagnostics import DiagnosticsService
from backend.plugins.discovery.loader import PluginLoader
from backend.plugins.discovery.validator import PluginValidator
from backend.plugins.registry.plugin_registry import PluginRegistry
from backend.tools.registry.tool_registry import ToolRegistry
from config.settings import Settings


def _memory_service() -> MemoryService:
    observability_service = ObservabilityService(TraceStore())
    return MemoryService(
        store=MemoryStore(),
        retrieval_engine=RetrievalEngine(),
        summarizer=MemorySummarizer(),
        json_exporter=JSONMemoryExporter(),
        markdown_exporter=MarkdownMemoryExporter(),
        observability_service=observability_service,
    )


def _plugin_registry(tmp_path: Path) -> PluginRegistry:
    tool_registry = ToolRegistry()
    return PluginRegistry(PluginLoader(tmp_path / "extensions"), PluginValidator("0.1.0"), tool_registry)


def test_build_environment_report_reflects_settings_and_validation(tmp_path: Path) -> None:
    settings = Settings(plugin_extensions_dir=str(tmp_path))
    validation = ConfigurationValidator().validate(settings)
    report = build_environment_report(settings, validation)
    assert report.profile == settings.active_profile
    assert report.validation.is_valid == validation.is_valid
    assert any(d.label == "plugin_extensions" for d in report.directories)


def test_build_dependency_report_lists_registered_tools(tmp_path: Path) -> None:
    plugin_registry = _plugin_registry(tmp_path)
    tool_registry = ToolRegistry()
    report = build_dependency_report(plugin_registry, tool_registry, graph_metadata=None)
    assert report.loaded_plugins == []
    assert report.registered_tools == []
    assert report.registered_agents == []


def test_diagnostics_service_composes_a_full_report(tmp_path: Path) -> None:
    settings = Settings(plugin_extensions_dir=str(tmp_path))
    plugin_registry = _plugin_registry(tmp_path)
    tool_registry = ToolRegistry()
    memory_service = _memory_service()
    feature_flag_service = FeatureFlagService(settings)
    validator = ConfigurationValidator()

    service = DiagnosticsService(
        settings=settings, plugin_registry=plugin_registry, tool_registry=tool_registry,
        memory_service=memory_service, feature_flag_service=feature_flag_service, configuration_validator=validator,
    )
    report = service.build()

    assert report.application == "InsightPilot"
    assert report.profile == settings.active_profile
    assert len(report.feature_flags) == 6
    assert report.memory_statistics.total_items == 0
    assert report.dependency_report.registered_tools == []
