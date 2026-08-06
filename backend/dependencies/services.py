"""Service providers.

Services are cheap, stateless orchestrators over repositories, so a fresh
instance per request is fine — all actual state lives in the injected
repositories, which are themselves singletons.
"""

from fastapi import Depends

from backend.dependencies.repositories import (
    get_file_repository,
    get_session_repository,
)
from backend.repositories.file_repository import FileRepository
from backend.repositories.session_repository import SessionRepository
from backend.services.file_service import FileService
from backend.services.health_service import HealthService
from backend.services.session_service import SessionService
from config.settings import Settings, get_settings


def get_health_service(settings: Settings = Depends(get_settings)) -> HealthService:
    """Provide a HealthService bound to the current settings."""
    return HealthService(settings)


def get_session_service(
    session_repository: SessionRepository = Depends(get_session_repository),
) -> SessionService:
    """Provide a SessionService bound to the session repository."""
    return SessionService(session_repository)


def get_file_service(
    file_repository: FileRepository = Depends(get_file_repository),
    session_service: SessionService = Depends(get_session_service),
) -> FileService:
    """Provide a FileService bound to the file repository and session service."""
    return FileService(file_repository, session_service)
