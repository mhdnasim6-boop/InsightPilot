"""Empty state component — the one place every page renders "there's nothing here yet."

Before Phase 41, every page reached for a bare ``st.info("No X yet.")``
in its own words. This gives every empty state the same shape: an icon,
a short heading, one explanatory line, and — where a page has an obvious
next action — a primary button that jumps straight to it, instead of the
user having to work out where to go next on their own.
"""

from collections.abc import Callable

import streamlit as st


def render_empty_state(
    title: str,
    message: str,
    *,
    icon: str = "📭",
    action_label: str | None = None,
    on_action: Callable[[], None] | None = None,
    key: str | None = None,
) -> bool:
    """Render an empty state. Returns ``True`` the run the action button was clicked.

    ``on_action`` is optional and called before returning ``True`` — pass it
    for a side effect (e.g. ``state.add_activity(...)``); a caller that
    just needs to know whether to switch pages/rerun can rely on the
    return value alone and pass no ``on_action`` at all.
    """
    with st.container(border=True):
        st.markdown(f"### {icon} {title}")
        st.caption(message)
        if action_label is not None:
            clicked = st.button(action_label, type="primary", key=key or f"empty_state_action_{title}")
            if clicked:
                if on_action is not None:
                    on_action()
                return True
    return False
