"""Markdown export for a list of MemoryItems: a human-readable memory report."""

from backend.memory.models.memory_item import MemoryItem


class MarkdownMemoryExporter:
    """Renders a list of MemoryItems as a single Markdown document."""

    def export(self, items: list[MemoryItem]) -> str:
        """Return ``items`` rendered as Markdown, one section per memory."""
        if not items:
            return "# Memory Export\n\nNo memories stored.\n"

        lines = ["# Memory Export", ""]
        for item in items:
            lines.append(f"## {item.title}")
            lines.append(f"**Type:** {item.memory_type.value}  ")
            lines.append(f"**Scope:** {item.scope.value}  ")
            lines.append(f"**Importance:** {item.importance:.2f}  ")
            lines.append(f"**Tags:** {', '.join(item.tags) or '—'}  ")
            lines.append(f"**Created:** {item.created_at.isoformat()}")
            lines.append("")
            lines.append(item.summary or "*(no summary)*")
            lines.append("")
        return "\n".join(lines)
