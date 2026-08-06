"""Shared page chrome reused by every dashboard page."""

from frontend.layouts.page_layout import (
    ensure_session,
    page_header,
    render_sidebar,
    require_dataset,
)

__all__ = ["ensure_session", "page_header", "render_sidebar", "require_dataset"]
