"""One consistent status badge for the whole app.

Before Phase 41, nearly every page defined its own local ``_STATUS_ICONS``/
``_status_label`` dict and concatenated an emoji onto a raw status string
inside a table cell or ``st.markdown`` — a different emoji choice per page,
no shared color, and no themed widget. This module replaces that pattern
with one classifier (`status_tone`) that buckets *any* domain's status
vocabulary (worker/cluster/execution/plugin/workflow/... — this platform
has no single shared status enum) into one of five semantic tones, mirroring
the good/warning/serious/critical status palette from this project's own
data-visualization reference palette, rendered through Streamlit's native,
theme-aware ``st.badge`` — so a badge's color already follows
``.streamlit/config.toml`` in both light and dark mode with no extra CSS.
"""

from typing import Literal

import streamlit as st

BadgeColor = Literal["green", "blue", "yellow", "orange", "red", "gray"]

_TONE_KEYWORDS: dict[BadgeColor, frozenset[str]] = {
    "green": frozenset({
        "online", "healthy", "completed", "complete", "success", "successful", "active", "approved",
        "granted", "loaded", "registered", "connected", "ready", "good", "passed",
    }),
    "blue": frozenset({"running", "in_progress", "processing", "dispatched", "executing", "started", "live"}),
    "yellow": frozenset({"pending", "paused", "warning", "queued", "waiting", "retry", "retrying"}),
    "orange": frozenset({"degraded", "draining", "timeout", "timed_out", "serious"}),
    "red": frozenset({
        "failed", "failure", "error", "critical", "offline", "rejected", "denied", "cancelled", "canceled",
    }),
}

_TONE_ICONS: dict[BadgeColor, str] = {
    "green": "✅", "blue": "🔵", "yellow": "🟡", "orange": "🟠", "red": "🔴",
}

_DEFAULT_TONE: BadgeColor = "gray"


def status_tone(status: str) -> BadgeColor:
    """Classify any status string into one of five semantic tones — never raises,
    an unrecognized status is treated as neutral (gray)."""
    normalized = status.strip().lower().replace(" ", "_").replace("-", "_")
    for tone, keywords in _TONE_KEYWORDS.items():
        if normalized in keywords:
            return tone
    return _DEFAULT_TONE


def render_status_badge(status: str, *, label: str | None = None) -> None:
    """Render ``status`` as a themed badge — the drop-in replacement for every page's
    former ad hoc ``f"{icon} {status}"`` string."""
    tone = status_tone(status)
    display_label = label if label is not None else status.replace("_", " ").title()
    st.badge(display_label, icon=_TONE_ICONS.get(tone), color=tone if tone != "gray" else "gray")


def status_label(status: str) -> str:
    """Return the plain-text ``"icon status"`` form for contexts that can't render a
    widget (a dataframe cell, a Mermaid node label) — mirrors what every page's own
    ``_status_label()`` helper did, now backed by the same shared classifier."""
    tone = status_tone(status)
    icon = _TONE_ICONS.get(tone, "⚪")
    return f"{icon} {status}"
