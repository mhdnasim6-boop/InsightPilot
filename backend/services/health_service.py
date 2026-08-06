"""Health-check business logic."""

from backend.schemas.health import HealthResponse
from config.settings import Settings


class HealthService:
    """Reports application health. Trivial today; the seam exists so the
    health endpoint follows the same router -> service pattern as every
    other endpoint, rather than being a special case.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def get_health(self) -> HealthResponse:
        return HealthResponse(
            status="healthy",
            application=self._settings.app_name,
            version=self._settings.app_version,
        )
