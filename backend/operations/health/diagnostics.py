"""DiagnosticsService: the one owner of "what does a full diagnostics
snapshot look like" — composes EnvironmentReport + DependencyReport +
memory statistics + feature flags into one DiagnosticsReport.

Every piece it reports on is read from an already-existing, already-
injected collaborator (``ConfigurationValidator``, ``PluginRegistry``,
``ToolRegistry``, ``MemoryService``, ``FeatureFlagService``) — this class
adds no new business logic of its own, only composition.
"""

from datetime import datetime

from pydantic import BaseModel

from backend.memory.models.memory_statistics import MemoryStatistics
from backend.memory.services.memory_service import MemoryService
from backend.operations.configuration.configuration_validator import (
    ConfigurationValidator,
)
from backend.operations.diagnostics.dependency_report import (
    DependencyReport,
    build_dependency_report,
)
from backend.operations.diagnostics.environment_report import (
    EnvironmentReport,
    build_environment_report,
)
from backend.operations.feature_flags.feature_flag import FeatureFlag
from backend.operations.feature_flags.feature_flag_service import FeatureFlagService
from backend.orchestration.graph.metadata import GraphMetadata
from backend.plugins.registry.plugin_registry import PluginRegistry
from backend.tools.registry.tool_registry import ToolRegistry
from backend.utils.time import utc_now
from config.settings import Settings


class DiagnosticsReport(BaseModel):
    """A full, point-in-time operational snapshot."""

    application: str
    version: str
    profile: str
    environment: str
    generated_at: datetime
    environment_report: EnvironmentReport
    dependency_report: DependencyReport
    memory_statistics: MemoryStatistics
    feature_flags: list[FeatureFlag]


class DiagnosticsService:
    """Composes a full DiagnosticsReport from already-existing collaborators."""

    def __init__(
        self,
        settings: Settings,
        plugin_registry: PluginRegistry,
        tool_registry: ToolRegistry,
        memory_service: MemoryService,
        feature_flag_service: FeatureFlagService,
        configuration_validator: ConfigurationValidator,
    ) -> None:
        self._settings = settings
        self._plugin_registry = plugin_registry
        self._tool_registry = tool_registry
        self._memory_service = memory_service
        self._feature_flag_service = feature_flag_service
        self._configuration_validator = configuration_validator

    def build(self, graph_metadata: GraphMetadata | None = None) -> DiagnosticsReport:
        """Build a fresh diagnostics report. ``graph_metadata`` is optional — see
        ``build_dependency_report``'s own docstring for why."""
        validation_result = self._configuration_validator.validate(self._settings)
        environment_report = build_environment_report(self._settings, validation_result)
        dependency_report = build_dependency_report(self._plugin_registry, self._tool_registry, graph_metadata)
        return DiagnosticsReport(
            application=self._settings.app_name,
            version=self._settings.app_version,
            profile=self._settings.active_profile,
            environment=self._settings.environment,
            generated_at=utc_now(),
            environment_report=environment_report,
            dependency_report=dependency_report,
            memory_statistics=self._memory_service.statistics(),
            feature_flags=self._feature_flag_service.list_flags(),
        )
