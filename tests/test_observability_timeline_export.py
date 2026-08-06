"""Tests for build_timeline() and the JSON/Markdown/CSV trace exporters."""

import csv
import io
import json
from datetime import timedelta

from backend.ai.models.responses import TokenUsage
from backend.approval.models.approval import ApprovalStatus, ExecutionApproval
from backend.observability.exporters.csv_exporter import CSVTraceExporter
from backend.observability.exporters.json_exporter import JSONTraceExporter
from backend.observability.exporters.markdown_exporter import MarkdownTraceExporter
from backend.observability.exporters.trace_exporter import TraceExporter
from backend.observability.models.agent_trace import AgentTrace
from backend.observability.models.ai_trace import AICallTrace
from backend.observability.models.execution_trace import ExecutionTrace
from backend.observability.models.export_format import TraceExportFormat
from backend.observability.models.tool_trace import ToolTrace
from backend.observability.services.timeline import build_timeline
from backend.orchestration.state.state import ExecutionStatus
from backend.planning.models.enums import PlanStatus
from backend.utils.time import utc_now


def _trace() -> ExecutionTrace:
    start = utc_now()
    agent_trace = AgentTrace(
        agent_name="sql_agent",
        start_time=start,
        end_time=start + timedelta(milliseconds=500),
        duration_ms=500.0,
        status=ExecutionStatus.COMPLETED,
        input_size=10,
        output_size=20,
    )
    tool_trace = ToolTrace(
        tool_name="query_database",
        agent_name="sql_agent",
        start_time=start - timedelta(milliseconds=100),
        end_time=start,
        duration_ms=100.0,
        status=ExecutionStatus.COMPLETED,
    )
    ai_trace = AICallTrace(
        agent_name="executive_summary_agent",
        provider="mock",
        model="mock-model",
        tokens=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        start_time=start + timedelta(milliseconds=600),
        end_time=start + timedelta(milliseconds=650),
        latency_ms=50.0,
        estimated_cost=0.0,
    )
    approval = ExecutionApproval(
        approval_id="a1",
        plan_id="plan-1",
        step_id="s1",
        status=ApprovalStatus.APPROVED,
        requested_at=start + timedelta(milliseconds=700),
        approved_at=start + timedelta(milliseconds=900),
        metadata={"node_name": "sql_agent"},
    )
    return ExecutionTrace(
        trace_id="t1",
        plan_id="plan-1",
        session_id="s1",
        start_time=start,
        end_time=start + timedelta(seconds=1),
        duration_ms=1000.0,
        status=PlanStatus.COMPLETED,
        agent_traces=[agent_trace],
        tool_traces=[tool_trace],
        ai_calls=[ai_trace],
        approval_traces=[approval],
        errors=["something went wrong"],
        warnings=["heads up"],
    )


def test_build_timeline_orders_every_record_type_chronologically() -> None:
    entries = build_timeline(_trace())

    assert [e.kind for e in entries] == ["tool", "agent", "ai_call", "approval"]
    assert entries[0].name == "query_database"
    assert entries[1].name == "sql_agent"
    assert entries[2].name == "mock:mock-model"
    assert entries[3].name == "sql_agent"  # approval.metadata["node_name"]
    assert entries[3].status == "approved"


def test_json_exporter_round_trips_the_trace() -> None:
    content = JSONTraceExporter().export(_trace())
    data = json.loads(content)

    assert data["trace_id"] == "t1"
    assert data["status"] == "completed"
    assert len(data["agent_traces"]) == 1
    assert len(data["approval_traces"]) == 1


def test_markdown_exporter_includes_every_section() -> None:
    content = MarkdownTraceExporter().export(_trace())

    assert "# Execution Trace `t1`" in content
    assert "## Agents" in content
    assert "sql_agent" in content
    assert "## Tools" in content
    assert "query_database" in content
    assert "## AI Calls" in content
    assert "mock" in content
    assert "## Approvals" in content
    assert "## Errors & Warnings" in content
    assert "something went wrong" in content


def test_csv_exporter_writes_one_row_per_timeline_event() -> None:
    content = CSVTraceExporter().export(_trace())
    rows = list(csv.DictReader(io.StringIO(content)))

    assert len(rows) == 4
    assert rows[0]["kind"] == "tool"
    assert rows[0]["name"] == "query_database"


def test_trace_exporter_dispatches_to_the_right_format() -> None:
    exporter = TraceExporter()
    trace = _trace()

    assert json.loads(exporter.export(trace, TraceExportFormat.JSON))["trace_id"] == "t1"
    assert "# Execution Trace" in exporter.export(trace, TraceExportFormat.MARKDOWN)
    assert exporter.export(trace, TraceExportFormat.CSV).startswith("kind,name,start_time")
