"""Pure, dependency-free formatting helpers for rendering backend data.

Every function here only formats a value it is given — none of them
compute, aggregate, or interpret data. That decision already happened in
a backend engine (e.g. ``calculate_null_percentage`` already multiplies by
100 before the value ever reaches the frontend); these helpers only decide
how many decimals and which suffix a number is displayed with.
"""

from datetime import datetime

_PLACEHOLDER = "—"


def format_number(value: float | None, decimals: int = 2) -> str:
    """Format a number with thousands separators, or a placeholder for ``None``."""
    if value is None:
        return _PLACEHOLDER
    return f"{value:,.{decimals}f}"


def format_percent(value: float | None, decimals: int = 1) -> str:
    """Format a number already expressed on a 0-100 scale as a percentage string."""
    if value is None:
        return _PLACEHOLDER
    return f"{value:,.{decimals}f}%"


def format_bytes(size_bytes: int | None) -> str:
    """Format a byte count as a human-readable size (KB, MB, GB, ...)."""
    if size_bytes is None:
        return _PLACEHOLDER
    size = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024:
            return f"{size:,.1f} {unit}" if unit != "B" else f"{int(size)} {unit}"
        size /= 1024
    return f"{size:,.1f} PB"


def format_timestamp(value: str | datetime | None) -> str:
    """Format an ISO-8601 timestamp (or ``datetime``) as ``YYYY-MM-DD HH:MM:SS``."""
    if value is None:
        return _PLACEHOLDER
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    try:
        return datetime.fromisoformat(value).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return value


def truncate_text(text: str | None, max_length: int = 80) -> str:
    """Truncate ``text`` to ``max_length`` characters, appending an ellipsis if cut."""
    if text is None:
        return _PLACEHOLDER
    if len(text) <= max_length:
        return text
    return text[: max_length - 1].rstrip() + "…"
