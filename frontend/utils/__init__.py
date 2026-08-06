"""Pure helper utilities shared across dashboard pages and components."""

from frontend.utils.chat_context import (
    build_chat_context,
    find_referenced_charts,
    find_referenced_kpis,
)
from frontend.utils.formatting import (
    format_bytes,
    format_number,
    format_percent,
    format_timestamp,
    truncate_text,
)
from frontend.utils.suggested_prompts import GENERIC_STARTERS, generate_starter_prompts

__all__ = [
    "GENERIC_STARTERS",
    "build_chat_context",
    "find_referenced_charts",
    "find_referenced_kpis",
    "format_bytes",
    "format_number",
    "format_percent",
    "format_timestamp",
    "generate_starter_prompts",
    "truncate_text",
]
