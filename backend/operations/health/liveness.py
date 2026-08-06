"""LivenessService: "is this process able to respond at all."

Deliberately reuses the existing ``HealthService`` rather than
reimplementing it — "Reuse existing health endpoints where possible," and
liveness in every standard sense (Kubernetes included) is exactly this
question: was a response produced. It carries no dependency-readiness
information — that's ``ReadinessService``'s job.
"""

from pydantic import BaseModel

from backend.services.health_service import HealthService


class LivenessStatus(BaseModel):
    """Shape of the liveness probe response."""

    alive: bool
    application: str
    version: str


class LivenessService:
    """Wraps HealthService to answer the liveness question."""

    def __init__(self, health_service: HealthService) -> None:
        self._health_service = health_service

    def check(self) -> LivenessStatus:
        """Always ``alive=True`` if this call returns at all — the process is, by definition, alive."""
        health = self._health_service.get_health()
        return LivenessStatus(alive=True, application=health.application, version=health.version)
