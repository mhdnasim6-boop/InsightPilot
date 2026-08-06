"""EnvironmentReport: a structural snapshot of the resolved environment —
profile, key settings, directory checks, and the full configuration
validation result. Also what ``GET /operations/configuration`` returns
directly, so that endpoint and the "diagnostics" REST endpoint never
maintain two separate descriptions of the same thing.
"""

from pathlib import Path

from pydantic import BaseModel

from backend.core.constants import DATA_DIR, UPLOADS_DIR
from backend.operations.configuration.configuration_validator import (
    ConfigurationValidationResult,
)
from config.settings import Settings
from shared.logging import LOGS_DIR


class DirectoryCheck(BaseModel):
    """Whether one directory this application cares about currently exists."""

    label: str
    path: str
    exists: bool
    is_directory: bool | None = None


class EnvironmentReport(BaseModel):
    """A snapshot of the resolved environment, safe to expose over REST (no secrets)."""

    profile: str
    environment: str
    application_version: str
    log_level: str
    ai_default_provider: str
    plugin_extensions_dir: str
    directories: list[DirectoryCheck]
    validation: ConfigurationValidationResult


def build_environment_report(settings: Settings, validation_result: ConfigurationValidationResult) -> EnvironmentReport:
    """Build a full environment report from a resolved Settings and its validation result."""
    directories = [
        _check_directory("data", DATA_DIR),
        _check_directory("uploads", UPLOADS_DIR),
        _check_directory("logs", LOGS_DIR),
        _check_directory("plugin_extensions", Path(settings.plugin_extensions_dir)),
    ]
    return EnvironmentReport(
        profile=settings.active_profile,
        environment=settings.environment,
        application_version=settings.app_version,
        log_level=settings.log_level,
        ai_default_provider=settings.ai_default_provider,
        plugin_extensions_dir=settings.plugin_extensions_dir,
        directories=directories,
        validation=validation_result,
    )


def _check_directory(label: str, path: Path) -> DirectoryCheck:
    exists = path.exists()
    return DirectoryCheck(label=label, path=str(path), exists=exists, is_directory=path.is_dir() if exists else None)
