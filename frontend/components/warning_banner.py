"""Warning/error banner component — the one place every page renders a message or error.

Consolidating this here means every page reports a caught
:class:`APIClientError` identically, instead of each page re-deriving its
own ad hoc error text — and, since Phase 41, identically *friendly*: a raw
backend ``error_type``/status code is never the first thing a user reads
(see :mod:`frontend.components.error_messages`).
"""

from collections.abc import Callable
from typing import Literal

import streamlit as st

from frontend.api.exceptions import APIClientError
from frontend.components.error_messages import describe_error

Severity = Literal["info", "warning", "error", "success"]

_RENDERERS = {"info": st.info, "warning": st.warning, "error": st.error, "success": st.success}


def render_banner(message: str, severity: Severity = "warning") -> None:
    """Render ``message`` using the ``st.*`` call matching ``severity``."""
    _RENDERERS[severity](message)


def render_api_error(error: APIClientError, *, on_retry: Callable[[], None] | None = None) -> None:
    """Render a caught ``APIClientError`` as a friendly title/message/suggestion, with the
    raw technical detail available in a collapsed expander rather than shown as the main
    message. Pass ``on_retry`` to also render a "Retry" button that calls it and reruns
    the page — most call sites omit it today (rerunning the page already re-fetches for
    most read paths); it's here for pages where a specific retry action makes sense.
    """
    friendly = describe_error(error)
    st.error(f"**{friendly.title}**\n\n{friendly.message}\n\n{friendly.suggestion}")

    if on_retry is not None and st.button("Retry", key=f"retry_{id(error)}"):
        on_retry()
        st.rerun()

    if friendly.technical_detail:
        with st.expander("Technical details"):
            st.code(friendly.technical_detail)
