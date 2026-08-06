"""Unit tests for frontend.utils.formatting — pure, dependency-free helpers."""

from datetime import UTC, datetime

import pytest

from frontend.utils.formatting import (
    format_bytes,
    format_number,
    format_percent,
    format_timestamp,
    truncate_text,
)


@pytest.mark.parametrize(
    ("value", "decimals", "expected"),
    [
        (1234567.891, 2, "1,234,567.89"),
        (0, 2, "0.00"),
        (42, 0, "42"),
        (None, 2, "—"),
    ],
)
def test_format_number(value: float | None, decimals: int, expected: str) -> None:
    assert format_number(value, decimals) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (12.345, "12.3%"),
        (0, "0.0%"),
        (100, "100.0%"),
        (None, "—"),
    ],
)
def test_format_percent(value: float | None, expected: str) -> None:
    assert format_percent(value) == expected


@pytest.mark.parametrize(
    ("size_bytes", "expected"),
    [
        (None, "—"),
        (0, "0 B"),
        (512, "512 B"),
        (2048, "2.0 KB"),
        (5 * 1024 * 1024, "5.0 MB"),
        (3 * 1024 * 1024 * 1024, "3.0 GB"),
    ],
)
def test_format_bytes(size_bytes: int | None, expected: str) -> None:
    assert format_bytes(size_bytes) == expected


def test_format_timestamp_from_iso_string() -> None:
    assert format_timestamp("2026-08-01T02:33:37") == "2026-08-01 02:33:37"


def test_format_timestamp_from_datetime() -> None:
    assert format_timestamp(datetime(2026, 8, 1, 2, 33, 37, tzinfo=UTC)) == "2026-08-01 02:33:37"


def test_format_timestamp_none_returns_placeholder() -> None:
    assert format_timestamp(None) == "—"


def test_format_timestamp_invalid_string_returned_unchanged() -> None:
    assert format_timestamp("not-a-timestamp") == "not-a-timestamp"


def test_truncate_text_shorter_than_max_is_unchanged() -> None:
    assert truncate_text("hello", 10) == "hello"


def test_truncate_text_longer_than_max_is_truncated_with_ellipsis() -> None:
    result = truncate_text("hello world", 8)
    assert result == "hello w…"
    assert len(result) == 8


def test_truncate_text_none_returns_placeholder() -> None:
    assert truncate_text(None) == "—"
