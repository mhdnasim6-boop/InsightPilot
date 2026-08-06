"""Loading indicator component — a thin, reusable wrapper over ``st.spinner``.

Kept as its own component (rather than inlining ``st.spinner`` on every
page) so every long-running backend call shows the same loading affordance
and the wording can change in one place.
"""

from collections.abc import Iterator
from contextlib import contextmanager

import streamlit as st


@contextmanager
def loading(label: str = "Working...") -> Iterator[None]:
    """Context manager that shows a spinner labeled ``label`` for its duration."""
    with st.spinner(label):
        yield
