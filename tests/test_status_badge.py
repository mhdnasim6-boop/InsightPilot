"""Tests for frontend.components.status_badge.status_tone/status_label — the shared
status classifier every page's former ad hoc _STATUS_ICONS dict is replaced by.
"""

from frontend.components.status_badge import status_label, status_tone


def test_success_like_statuses_classify_green() -> None:
    for status in ("online", "healthy", "completed", "active", "registered"):
        assert status_tone(status) == "green"


def test_failure_like_statuses_classify_red() -> None:
    for status in ("failed", "offline", "cancelled", "critical", "rejected"):
        assert status_tone(status) == "red"


def test_in_progress_statuses_classify_blue() -> None:
    assert status_tone("running") == "blue"
    assert status_tone("in_progress") == "blue"


def test_degraded_classifies_orange() -> None:
    assert status_tone("degraded") == "orange"


def test_pending_classifies_yellow() -> None:
    assert status_tone("pending") == "yellow"


def test_unrecognized_status_classifies_gray() -> None:
    assert status_tone("some_new_unmapped_status") == "gray"


def test_classification_is_case_and_separator_insensitive() -> None:
    assert status_tone("COMPLETED") == "green"
    assert status_tone("in-progress") == "blue"
    assert status_tone(" Failed ") == "red"


def test_status_label_prefixes_an_icon() -> None:
    label = status_label("completed")
    assert label.endswith("completed")
    assert label != "completed"
