"""ConfigurationValidator: checks a resolved Settings instance for the
seven areas this phase names — directories, plugin folder, memory
configuration, AI provider configuration, database configuration, MCP
configuration, and logging configuration — and reports problems clearly
instead of raising.

Mirrors ``backend.ingestion.validators.result``'s own
``ValidationIssue``/``*ValidationResult`` shape (each domain in this
codebase owns its own copy of that shape rather than sharing one —
``backend.planning.validator.result`` already does the same) — never
raises itself; a caller that wants a hard failure (``StartupManager``'s
own "configuration" stage) decides that on top of the returned result.
"""

from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field

from backend.ai.providers.factory import ProviderFactory
from backend.core.constants import DATA_DIR, UPLOADS_DIR
from backend.datasource.sql.exceptions.errors import DatabaseNotImplementedError
from backend.datasource.sql.models.connection_config import DatabaseType
from backend.datasource.sql.registry.connector_registry import ConnectorRegistry
from config.settings import Settings
from shared.logging import LOGS_DIR

# Every level Loguru itself recognizes — checked so a typo like
# ``LOG_LEVEL=INFOO`` is caught here, before ``setup_logging()`` calls
# ``logger.add(..., level=...)`` and raises a much less legible error.
_VALID_LOG_LEVELS = frozenset({"TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"})

# The three DatabaseType values this codebase has a real ConnectorRegistry
# entry for today (SQLSERVER/SNOWFLAKE/BIGQUERY/DUCKDB are recognized but
# unimplemented placeholders — see ConnectorRegistry's own docstring).
_CORE_DATABASE_TYPES = (DatabaseType.SQLITE, DatabaseType.POSTGRESQL, DatabaseType.MYSQL)


class IssueSeverity(str, Enum):
    """Severity of a single validation finding."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ConfigurationIssue(BaseModel):
    """A single validation finding, scoped to the configuration area it came from."""

    area: str
    severity: IssueSeverity
    code: str
    message: str


class ConfigurationValidationResult(BaseModel):
    """The full outcome of validating one resolved Settings instance."""

    is_valid: bool
    issues: list[ConfigurationIssue] = Field(default_factory=list)

    @property
    def errors(self) -> list[ConfigurationIssue]:
        """Issues severe enough that a caller may treat this as a failed validation."""
        return [issue for issue in self.issues if issue.severity == IssueSeverity.ERROR]

    @property
    def warnings(self) -> list[ConfigurationIssue]:
        """Issues worth surfacing but not blocking on."""
        return [issue for issue in self.issues if issue.severity == IssueSeverity.WARNING]


class ConfigurationValidator:
    """Validates a resolved ``Settings`` instance across every area this phase names."""

    def validate(self, settings: Settings) -> ConfigurationValidationResult:
        issues: list[ConfigurationIssue] = []
        issues.extend(self._check_directories(settings))
        issues.extend(self._check_plugin_folder(settings))
        issues.extend(self._check_memory(settings))
        issues.extend(self._check_ai_provider(settings))
        issues.extend(self._check_database(settings))
        issues.extend(self._check_mcp(settings))
        issues.extend(self._check_logging(settings))
        is_valid = not any(issue.severity == IssueSeverity.ERROR for issue in issues)
        return ConfigurationValidationResult(is_valid=is_valid, issues=issues)

    def _check_directories(self, settings: Settings) -> list[ConfigurationIssue]:
        del settings
        issues = []
        for label, path in (("data", DATA_DIR), ("uploads", UPLOADS_DIR), ("logs", LOGS_DIR)):
            issues.extend(self._check_path_is_directory("directories", label, path))
        return issues

    def _check_plugin_folder(self, settings: Settings) -> list[ConfigurationIssue]:
        if not settings.plugin_extensions_dir.strip():
            return [
                ConfigurationIssue(
                    area="plugin_folder", severity=IssueSeverity.ERROR, code="empty_plugin_dir",
                    message="plugin_extensions_dir must not be empty.",
                )
            ]
        path = Path(settings.plugin_extensions_dir)
        if not path.exists():
            return [
                ConfigurationIssue(
                    area="plugin_folder", severity=IssueSeverity.INFO, code="plugin_dir_missing",
                    message=f"Plugin folder '{path}' does not exist yet — no plugins will be discovered "
                    "(this is healthy; PluginLoader treats a missing directory as zero plugins).",
                )
            ]
        return self._check_path_is_directory("plugin_folder", "plugin_extensions_dir", path)

    def _check_memory(self, settings: Settings) -> list[ConfigurationIssue]:
        del settings
        return [
            ConfigurationIssue(
                area="memory", severity=IssueSeverity.INFO, code="memory_no_dedicated_config",
                message="Memory layer uses in-process defaults; no dedicated configuration is required.",
            )
        ]

    def _check_ai_provider(self, settings: Settings) -> list[ConfigurationIssue]:
        try:
            ProviderFactory(settings).create()
        except Exception as exc:  # noqa: BLE001 - report as a finding, never raise from a validator
            return [
                ConfigurationIssue(
                    area="ai_provider", severity=IssueSeverity.ERROR, code="ai_provider_unresolvable",
                    message=f"ai_default_provider='{settings.ai_default_provider}' could not be resolved: {exc}",
                )
            ]
        return []

    def _check_database(self, settings: Settings) -> list[ConfigurationIssue]:
        del settings
        registry = ConnectorRegistry()
        issues = []
        for database_type in _CORE_DATABASE_TYPES:
            try:
                registry.get_connector(database_type)
            except DatabaseNotImplementedError as exc:
                issues.append(
                    ConfigurationIssue(
                        area="database", severity=IssueSeverity.ERROR, code="connector_unavailable",
                        message=f"Expected connector for {database_type.value} is unavailable: {exc}",
                    )
                )
        return issues

    def _check_mcp(self, settings: Settings) -> list[ConfigurationIssue]:
        del settings
        return [
            ConfigurationIssue(
                area="mcp", severity=IssueSeverity.INFO, code="mcp_no_dedicated_config",
                message="MCP layer uses in-process defaults; no dedicated configuration is required.",
            )
        ]

    def _check_logging(self, settings: Settings) -> list[ConfigurationIssue]:
        if settings.log_level.upper() not in _VALID_LOG_LEVELS:
            return [
                ConfigurationIssue(
                    area="logging", severity=IssueSeverity.ERROR, code="invalid_log_level",
                    message=f"log_level='{settings.log_level}' is not a recognized Loguru level "
                    f"({', '.join(sorted(_VALID_LOG_LEVELS))}).",
                )
            ]
        return []

    def _check_path_is_directory(self, area: str, label: str, path: Path) -> list[ConfigurationIssue]:
        if not path.exists():
            return [
                ConfigurationIssue(
                    area=area, severity=IssueSeverity.INFO, code=f"{label}_missing",
                    message=f"'{path}' does not exist yet — created on first use.",
                )
            ]
        if not path.is_dir():
            return [
                ConfigurationIssue(
                    area=area, severity=IssueSeverity.ERROR, code=f"{label}_not_a_directory",
                    message=f"'{path}' exists but is not a directory.",
                )
            ]
        return []
