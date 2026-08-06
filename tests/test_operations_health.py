"""Tests for LivenessService and ReadinessService."""

from backend.operations.health.liveness import LivenessService
from backend.operations.health.readiness import ReadinessService
from backend.operations.startup.startup_manager import StartupManager, StartupStage
from backend.services.health_service import HealthService
from config.settings import Settings


def test_liveness_is_always_alive() -> None:
    service = LivenessService(HealthService(Settings()))
    status = service.check()
    assert status.alive is True
    assert status.application == "InsightPilot"


def test_readiness_is_not_ready_before_any_startup_run() -> None:
    manager = StartupManager([StartupStage("a", lambda: None)])
    service = ReadinessService(manager)
    status = service.check()
    assert status.ready is False


def test_readiness_is_ready_after_a_successful_startup_run() -> None:
    manager = StartupManager([StartupStage("a", lambda: None)])
    manager.run(profile="development")
    status = ReadinessService(manager).check()
    assert status.ready is True
    assert status.profile == "development"
    assert len(status.stages) == 1


def test_readiness_is_not_ready_after_a_failed_startup_stage() -> None:
    def _fail() -> None:
        raise RuntimeError("nope")

    manager = StartupManager([StartupStage("a", lambda: None), StartupStage("b", _fail)])
    manager.run(profile="production")
    status = ReadinessService(manager).check()
    assert status.ready is False
    assert status.profile == "production"
