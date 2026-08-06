"""Time helpers.

All timestamps in the application are timezone-aware UTC — use
:func:`utc_now` instead of ``datetime.now()`` or ``datetime.utcnow()``
(the latter is deprecated and produces naive datetimes).
"""

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return the current time as a timezone-aware UTC datetime."""
    return datetime.now(UTC)
