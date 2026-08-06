"""Markdown export for an ExecutionTrace: a human-readable execution report."""

from backend.observability.models.execution_trace import ExecutionTrace


class MarkdownTraceExporter:
    """Renders an ExecutionTrace as a single Markdown report."""

    def export(self, trace: ExecutionTrace) -> str:
        """Return ``trace`` rendered as Markdown: summary, agents, tools, AI calls, approvals, errors."""
        parts = [self._render_header(trace)]
        if trace.agent_traces:
            parts.append(self._render_agents(trace))
        if trace.tool_traces:
            parts.append(self._render_tools(trace))
        if trace.ai_calls:
            parts.append(self._render_ai_calls(trace))
        if trace.approval_traces:
            parts.append(self._render_approvals(trace))
        if trace.errors or trace.warnings:
            parts.append(self._render_errors_and_warnings(trace))
        return "\n".join(parts)

    def _render_header(self, trace: ExecutionTrace) -> str:
        lines = [
            f"# Execution Trace `{trace.trace_id}`",
            "",
            f"**Plan:** {trace.plan_id}  ",
            f"**Session:** {trace.session_id or '—'}  ",
            f"**Status:** {trace.status.value}  ",
            f"**Started:** {trace.start_time.isoformat()}  ",
            f"**Ended:** {trace.end_time.isoformat() if trace.end_time else '—'}  ",
            f"**Duration:** {f'{trace.duration_ms:.1f}ms' if trace.duration_ms is not None else '—'}",
            "",
        ]
        return "\n".join(lines)

    def _render_agents(self, trace: ExecutionTrace) -> str:
        lines = ["## Agents", "", "| Agent | Status | Duration | Tool Calls |", "|---|---|---|---|"]
        lines.extend(
            f"| {a.agent_name} | {a.status.value} | {a.duration_ms:.1f}ms | {len(a.tool_calls)} |"
            for a in trace.agent_traces
        )
        lines.append("")
        return "\n".join(lines)

    def _render_tools(self, trace: ExecutionTrace) -> str:
        lines = ["## Tools", "", "| Tool | Agent | Status | Duration |", "|---|---|---|---|"]
        lines.extend(
            f"| {t.tool_name} | {t.agent_name or '—'} | {t.status.value} | {t.duration_ms:.1f}ms |"
            for t in trace.tool_traces
        )
        lines.append("")
        return "\n".join(lines)

    def _render_ai_calls(self, trace: ExecutionTrace) -> str:
        lines = ["## AI Calls", "", "| Provider | Model | Tokens | Latency | Cost |", "|---|---|---|---|---|"]
        lines.extend(
            f"| {c.provider} | {c.model} | {c.tokens.total_tokens} | {c.latency_ms:.1f}ms | ${c.estimated_cost:.4f} |"
            for c in trace.ai_calls
        )
        lines.append("")
        return "\n".join(lines)

    def _render_approvals(self, trace: ExecutionTrace) -> str:
        lines = ["## Approvals", "", "| Step | Status | Approver | Reason |", "|---|---|---|---|"]
        lines.extend(
            f"| {a.step_id} | {a.status.value} | {a.approver or '—'} | {a.reason or '—'} |"
            for a in trace.approval_traces
        )
        lines.append("")
        return "\n".join(lines)

    def _render_errors_and_warnings(self, trace: ExecutionTrace) -> str:
        lines = ["## Errors & Warnings", ""]
        lines.extend(f"- Error: {error}" for error in trace.errors)
        lines.extend(f"- Warning: {warning}" for warning in trace.warnings)
        lines.append("")
        return "\n".join(lines)
