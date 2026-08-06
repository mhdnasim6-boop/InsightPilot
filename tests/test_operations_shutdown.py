"""Tests for ShutdownManager: reverse-order execution and per-stage failure isolation."""

from backend.operations.startup.shutdown_manager import ShutdownManager, ShutdownStage
from backend.operations.startup.startup_manager import StageStatus


def test_run_executes_stages_in_the_given_order() -> None:
    # Reverse-ordering is the caller's responsibility (see
    # backend.dependencies.operations.get_shutdown_manager) — ShutdownManager
    # itself just runs whatever order it's handed.
    order: list[str] = []
    stages = [ShutdownStage(name, lambda name=name: order.append(name)) for name in ["execution", "memory", "plugins"]]
    ShutdownManager(stages).run()
    assert order == ["execution", "memory", "plugins"]


def test_run_marks_every_stage_completed_when_nothing_raises() -> None:
    stages = [ShutdownStage("a", lambda: None), ShutdownStage("b", lambda: None)]
    report = ShutdownManager(stages).run()
    assert report.completed is True
    assert all(stage.status == StageStatus.COMPLETED for stage in report.stages)


def test_a_failing_stage_does_not_stop_the_rest() -> None:
    order: list[str] = []

    def _fail() -> None:
        raise RuntimeError("shutdown failed")

    stages = [
        ShutdownStage("a", lambda: order.append("a")),
        ShutdownStage("b", _fail),
        ShutdownStage("c", lambda: order.append("c")),
    ]
    report = ShutdownManager(stages).run()

    assert order == ["a", "c"]
    assert report.completed is False
    by_name = {stage.name: stage for stage in report.stages}
    assert by_name["b"].status == StageStatus.FAILED
    assert "shutdown failed" in (by_name["b"].error or "")
    assert by_name["c"].status == StageStatus.COMPLETED


def test_run_with_no_stages_is_trivially_completed() -> None:
    report = ShutdownManager([]).run()
    assert report.completed is True
    assert report.stages == []
