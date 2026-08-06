"""Maps a caught APIClientError to a friendly, actionable message.

Never shows a raw backend error_type/status code/stack trace as the
*primary* message a user reads — every caller gets a short, plain-English
title, a one-sentence explanation, and a suggested next step. The raw
technical detail is never hidden entirely (it matters for debugging and
support) — it is demoted to an explicit, opt-in "Technical details"
section instead. Mapped primarily by HTTP status code (~7 cases), not by
the dozens of distinct backend ``error_type`` values this platform can
raise — a ``*NotFoundError`` gets its entity name humanized generically
(``ClusterNotFoundError`` -> "Cluster not found") rather than requiring a
hand-maintained entry per subsystem.
"""

import json
import re
from dataclasses import dataclass
from typing import Any

from frontend.api.exceptions import APIClientError, APIError, BackendUnavailableError


@dataclass(frozen=True)
class FriendlyError:
    """A user-facing rendering of one caught error."""

    title: str
    message: str
    suggestion: str
    technical_detail: str | None = None


_StatusTemplate = tuple[str, str, str]

_STATUS_MESSAGES: dict[int, _StatusTemplate] = {
    400: (
        "Something about that request wasn't right",
        "The backend couldn't process this request as sent.",
        "Double-check the values you entered and try again.",
    ),
    401: (
        "You're signed out",
        "Your session has expired or you aren't logged in.",
        "Log in again on the Security page, then retry.",
    ),
    403: (
        "You don't have permission for this",
        "Your account doesn't have the access this action needs.",
        "Ask an administrator to grant the required permission, or switch to an account that has it.",
    ),
    404: (
        "Not found",
        "The item you're looking for doesn't exist, or it was already removed.",
        "Refresh the page and try again — it may have been deleted, or never existed.",
    ),
    409: (
        "That conflicts with the current state",
        "This action can't be completed because of the item's current state.",
        "Refresh to see the latest state, then try again.",
    ),
    422: (
        "Some fields need a second look",
        "One or more values didn't pass validation.",
        "Check the highlighted fields (see Technical details below) and try again.",
    ),
    429: (
        "Too many requests",
        "Requests are being sent faster than the backend can handle right now.",
        "Wait a moment and try again.",
    ),
    503: (
        "This service is temporarily unavailable",
        "This part of the backend isn't ready to handle requests right now.",
        "Wait a moment and try again.",
    ),
}

_DEFAULT_TEMPLATE: _StatusTemplate = (
    "Something went wrong",
    "The request didn't complete successfully.",
    "Try again, or check the Technical details below.",
)

_BACKEND_UNAVAILABLE_TITLE = "Can't reach the backend"
_BACKEND_UNAVAILABLE_MESSAGE = (
    "The InsightPilot backend isn't responding — it may be starting up, restarting, or unreachable from here."
)
_BACKEND_UNAVAILABLE_SUGGESTION = (
    "Check that the backend is running and try again. If this keeps happening, check the backend URL in Settings."
)


def _humanize_error_type(error_type: str) -> str:
    """``'ClusterNotFoundError'`` -> ``'Cluster not found'``."""
    stripped = error_type.removesuffix("Error")
    words = re.sub(r"(?<!^)(?=[A-Z])", " ", stripped).split()
    return " ".join(words).strip().capitalize() if words else error_type


def _stringify_detail(detail: Any) -> str | None:
    if detail is None:
        return None
    if isinstance(detail, str):
        return detail
    try:
        return json.dumps(detail, indent=2, default=str)
    except TypeError:
        return str(detail)


def describe_error(error: APIClientError) -> FriendlyError:
    """Return a :class:`FriendlyError` rendering of ``error`` — never the raw exception text alone."""
    if isinstance(error, BackendUnavailableError):
        return FriendlyError(
            title=_BACKEND_UNAVAILABLE_TITLE,
            message=_BACKEND_UNAVAILABLE_MESSAGE,
            suggestion=_BACKEND_UNAVAILABLE_SUGGESTION,
            technical_detail=str(error),
        )

    if isinstance(error, APIError):
        title, message, suggestion = _STATUS_MESSAGES.get(error.status_code, _DEFAULT_TEMPLATE)
        if error.status_code == 404 and error.error_type.endswith("NotFoundError"):
            message = f"{_humanize_error_type(error.error_type)}."

        technical_lines = [f"{error.error_type} ({error.status_code}): {error.message}"]
        detail_text = _stringify_detail(error.detail)
        if detail_text:
            technical_lines.append(detail_text)
        return FriendlyError(title=title, message=message, suggestion=suggestion, technical_detail="\n\n".join(technical_lines))

    title, message, suggestion = _DEFAULT_TEMPLATE
    return FriendlyError(title=title, message=message, suggestion=suggestion, technical_detail=str(error) or None)
