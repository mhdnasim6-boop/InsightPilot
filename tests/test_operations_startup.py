"""Tests for StartupManager: ordering, timing, and per-stage failure isolation.

Uses plain fake stages (no FastAPI, no real services) — StartupManager
itself only cares that ``action`` is a zero-argument callable.
"""

from backend.operations.startup.startup_manager import (
    StageStatus,
    StartupManager,
    StartupStage,
)


def test_run_executes_every_stage_in_order() -> None:
    order: list[str] = []
    stages = [StartupStage(name, lambda name=name: order.append(name)) for name in ["a", "b", "c"]]
    StartupManager(stages).run(profile="development")
    assert order == ["a", "b", "c"]


def test_run_marks_every_stage_completed_when_nothing_raises() -> None:
    stages = [StartupStage("a", lambda: None), StartupStage("b", lambda: None)]
    report = StartupManager(stages).run(profile="development")
    assert report.completed is True
    assert all(stage.status == StageStatus.COMPLETED for stage in report.stages)


def test_a_failing_stage_does_not_stop_the_rest() -> None:
    order: list[str] = []

    def _fail() -> None:
        raise RuntimeError("boom")

    stages = [
        StartupStage("a", lambda: order.append("a")),
        StartupStage("b", _fail),
        StartupStage("c", lambda: order.append("c")),
    ]
    report = StartupManager(stages).run(profile="development")

    assert order == ["a", "c"]
    assert report.completed is False
    by_name = {stage.name: stage for stage in report.stages}
    assert by_name["a"].status == StageStatus.COMPLETED
    assert by_name["b"].status == StageStatus.FAILED
    assert "boom" in (by_name["b"].error or "")
    assert by_name["c"].status == StageStatus.COMPLETED


def test_report_carries_the_given_profile() -> None:
    report = StartupManager([StartupStage("a", lambda: None)]).run(profile="staging")
    assert report.profile == "staging"


def test_last_report_is_none_before_run() -> None:
    manager = StartupManager([StartupStage("a", lambda: None)])
    assert manager.last_report is None


def test_last_report_reflects_the_most_recent_run() -> None:
    manager = StartupManager([StartupStage("a", lambda: None)])
    first = manager.run(profile="development")
    assert manager.last_report == first
    second = manager.run(profile="production")
    assert manager.last_report == second
    assert manager.last_report.profile == "production"


def test_run_with_no_stages_is_trivially_completed() -> None:
    report = StartupManager([]).run(profile="development")
    assert report.completed is True
    assert report.stages == []
