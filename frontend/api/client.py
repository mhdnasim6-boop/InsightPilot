"""The dashboard's only channel to the backend.

``APIClient`` is a thin HTTP wrapper: every method sends one request to a
``/api/v1/...`` endpoint and returns the ``data`` payload of the unified
response envelope as a plain ``dict``/``list``. It never imports from
``backend`` — Streamlit pages only ever see JSON-derived Python primitives,
never reconstructed backend Pydantic models. That keeps the frontend and
backend deployable as fully separate services with no shared Python
package dependency, and it is what "all communication must happen through
FastAPI endpoints" means taken literally.

Each call opens and closes its own short-lived ``httpx.Client`` rather
than holding one open across the object's lifetime, because Streamlit
re-executes the whole script on every user interaction; a client held
across reruns would either leak connections or need explicit lifecycle
management this module has no hook to perform. The optional ``transport``
constructor argument exists so tests can inject a synchronous
``httpx.MockTransport`` — no live server, no real sockets. (An
``httpx.ASGITransport`` bound to the real FastAPI app would be tempting
for a truer integration test, but it only implements the async transport
interface and cannot back a synchronous ``httpx.Client`` — verified
empirically, not assumed.)
"""

import uuid
from typing import Any

import httpx

from frontend.api.exceptions import APIError, BackendUnavailableError


class APIClient:
    """Synchronous HTTP client for the InsightPilot backend API."""

    def __init__(
        self, base_url: str, timeout: float = 30.0, transport: httpx.BaseTransport | None = None,
        access_token: str | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._transport = transport
        self._access_token = access_token

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        """Send one request and return the envelope's ``data`` field.

        Raises :class:`BackendUnavailableError` if no response was ever
        received, or :class:`APIError` if the backend responded with the
        unified failure envelope. Adds ``Authorization: Bearer <token>``
        automatically whenever this client was constructed with an
        ``access_token`` — every page that needs an authenticated call
        constructs its own ``APIClient(state.backend_url, access_token=state.access_token)``
        rather than passing a header explicitly on every call.
        """
        url = f"{self._base_url}{path}"
        if self._access_token is not None:
            headers = dict(kwargs.pop("headers", None) or {})
            headers.setdefault("Authorization", f"Bearer {self._access_token}")
            kwargs["headers"] = headers
        try:
            with httpx.Client(transport=self._transport, timeout=self._timeout) as http_client:
                response = http_client.request(method, url, **kwargs)
        except httpx.HTTPError as exc:
            raise BackendUnavailableError(f"Could not reach backend at {url}: {exc}") from exc

        body = response.json()
        if response.status_code >= 400 or not body.get("success", True):
            errors = body.get("errors") or {}
            raise APIError(
                message=body.get("message", "Request failed."),
                status_code=errors.get("status_code", response.status_code),
                error_type=errors.get("type", "UnknownError"),
                detail=errors.get("detail"),
            )
        return body["data"]

    # -- Health -----------------------------------------------------------

    def health_check(self) -> dict[str, Any]:
        """``GET /api/v1/health`` — application health status."""
        return dict(self._request("GET", "/api/v1/health"))

    # -- Sessions -----------------------------------------------------------

    def create_session(self) -> dict[str, Any]:
        """``POST /api/v1/sessions`` — start a new dashboard session."""
        return dict(self._request("POST", "/api/v1/sessions"))

    def get_session(self, session_id: str) -> dict[str, Any]:
        """``GET /api/v1/sessions/{session_id}`` — fetch a session's state."""
        return dict(self._request("GET", f"/api/v1/sessions/{session_id}"))

    # -- Datasets -------------------------------------------------------------

    def upload_dataset(
        self, session_id: str, filename: str, content: bytes, content_type: str | None = None
    ) -> dict[str, Any]:
        """``POST /api/v1/datasets/upload`` — upload and ingest a CSV/Excel file."""
        return dict(
            self._request(
                "POST",
                "/api/v1/datasets/upload",
                data={"session_id": session_id},
                files={"file": (filename, content, content_type or "application/octet-stream")},
            )
        )

    def list_datasets(self) -> list[dict[str, Any]]:
        """``GET /api/v1/datasets`` — every dataset ingested so far."""
        return list(self._request("GET", "/api/v1/datasets"))

    def get_dataset(self, dataset_id: str) -> dict[str, Any]:
        """``GET /api/v1/datasets/{dataset_id}`` — fetch one dataset."""
        return dict(self._request("GET", f"/api/v1/datasets/{dataset_id}"))

    def clean_dataset(self, dataset_id: str) -> dict[str, Any]:
        """``POST /api/v1/datasets/{dataset_id}/clean`` — run the default cleaning pipeline."""
        return dict(self._request("POST", f"/api/v1/datasets/{dataset_id}/clean"))

    # -- Analysis -------------------------------------------------------------

    def analyze(self, cleaning_outcome: dict[str, Any]) -> dict[str, Any]:
        """``POST /api/v1/analysis`` — analyze a cleaned dataset's ``CleaningOutcome``."""
        return dict(self._request("POST", "/api/v1/analysis", json=cleaning_outcome))

    # -- Visualizations -------------------------------------------------------

    def generate_visualizations(
        self,
        analysis_result: dict[str, Any],
        dataset: dict[str, Any] | None = None,
        layout_type: str = "detailed_analysis",
        theme: str = "light",
    ) -> dict[str, Any]:
        """``POST /api/v1/visualizations`` — recommend charts and render them server-side."""
        payload = {
            "analysis_result": analysis_result,
            "dataset": dataset,
            "layout_type": layout_type,
            "theme": theme,
        }
        return dict(self._request("POST", "/api/v1/visualizations", json=payload))

    # -- Planner ----------------------------------------------------------------

    def create_plan(
        self,
        user_request: str,
        session_id: str | None = None,
        uploaded_datasets: list[dict[str, Any]] | None = None,
        step_id: str | None = None,
    ) -> dict[str, Any]:
        """``POST /api/v1/planner/plan`` — turn a natural-language request into a PlannerAgentResult.

        Which agents can be referenced is discovered dynamically on the
        backend from the live orchestration graph — this call never
        declares an ``available_services`` list itself.
        """
        payload = {
            "step": {
                "step_id": step_id or uuid.uuid4().hex,
                "name": "Planner Agent Run",
                "node_name": "planner",
                "inputs": {"user_request": user_request, "uploaded_datasets": uploaded_datasets or []},
            },
            "session_id": session_id,
        }
        return dict(self._request("POST", "/api/v1/planner/plan", json=payload))

    def preview_plan(self, plan: dict[str, Any]) -> dict[str, Any]:
        """``POST /api/v1/planner/preview`` — render a plan as Mermaid, JSON, and a linear timeline."""
        return dict(self._request("POST", "/api/v1/planner/preview", json={"plan": plan}))

    def validate_plan(self, plan: dict[str, Any]) -> dict[str, Any]:
        """``POST /api/v1/planner/validate`` — structurally validate a plan against the live orchestration graph."""
        return dict(self._request("POST", "/api/v1/planner/validate", json={"plan": plan}))

    def explain_plan(self, plan: dict[str, Any]) -> dict[str, Any]:
        """``POST /api/v1/planner/explain`` — explain why each step's agent was selected."""
        return dict(self._request("POST", "/api/v1/planner/explain", json={"plan": plan}))

    def execute_plan(self, plan: dict[str, Any]) -> dict[str, Any]:
        """``POST /api/v1/planner/execute`` — approve and run a plan via PlanningService.

        May return a plan with ``status: "paused"`` instead of
        ``"completed"`` — see the Approvals methods below.
        """
        return dict(self._request("POST", "/api/v1/planner/execute", json={"plan": plan}))

    # -- Approvals (Human-in-the-Loop) -------------------------------------------

    def list_pending_approvals(self) -> list[dict[str, Any]]:
        """``GET /api/v1/approvals/pending`` — every approval currently awaiting a decision."""
        return list(self._request("GET", "/api/v1/approvals/pending"))

    def list_approvals_for_plan(self, plan_id: str) -> list[dict[str, Any]]:
        """``GET /api/v1/approvals/plan/{plan_id}`` — every approval ever requested for a plan."""
        return list(self._request("GET", f"/api/v1/approvals/plan/{plan_id}"))

    def get_plan_history(self, plan_id: str) -> list[dict[str, Any]]:
        """``GET /api/v1/approvals/plan/{plan_id}/history`` — a plan's full HITL timeline."""
        return list(self._request("GET", f"/api/v1/approvals/plan/{plan_id}/history"))

    def approve_approval(self, approval_id: str, approver: str | None = None) -> dict[str, Any]:
        """``POST /api/v1/approvals/{approval_id}/approve`` — approve a pending approval."""
        return dict(
            self._request("POST", f"/api/v1/approvals/{approval_id}/approve", json={"approver": approver})
        )

    def reject_approval(self, approval_id: str, approver: str | None = None, reason: str | None = None) -> dict[str, Any]:
        """``POST /api/v1/approvals/{approval_id}/reject`` — reject a pending approval."""
        return dict(
            self._request(
                "POST", f"/api/v1/approvals/{approval_id}/reject", json={"approver": approver, "reason": reason}
            )
        )

    def resume_plan_execution(self, plan_id: str) -> dict[str, Any]:
        """``POST /api/v1/approvals/plan/{plan_id}/resume`` — resume a plan's paused execution."""
        return dict(self._request("POST", f"/api/v1/approvals/plan/{plan_id}/resume"))

    def reject_plan_execution(self, plan_id: str, reason: str | None = None) -> dict[str, Any]:
        """``POST /api/v1/approvals/plan/{plan_id}/reject`` — reject a plan's paused execution outright."""
        return dict(self._request("POST", f"/api/v1/approvals/plan/{plan_id}/reject", json={"reason": reason}))

    def cancel_plan_execution(self, plan_id: str) -> dict[str, Any]:
        """``POST /api/v1/approvals/plan/{plan_id}/cancel`` — cancel a plan's active execution outright."""
        return dict(self._request("POST", f"/api/v1/approvals/plan/{plan_id}/cancel"))

    def get_approval_policy(self) -> dict[str, Any]:
        """``GET /api/v1/approvals/policy`` — the currently active ApprovalPolicy."""
        return dict(self._request("GET", "/api/v1/approvals/policy"))

    def set_approval_policy(self, policy_type: str) -> dict[str, Any]:
        """``PUT /api/v1/approvals/policy`` — replace the active ApprovalPolicy."""
        return dict(self._request("PUT", "/api/v1/approvals/policy", json={"policy_type": policy_type}))

    # -- System -----------------------------------------------------------------

    def get_system_status(self) -> dict[str, Any]:
        """``GET /api/v1/system`` — aggregated health, AI provider, and graph status."""
        return dict(self._request("GET", "/api/v1/system"))

    # -- Chat ---------------------------------------------------------------------

    def ask_chat(self, question: str, context: dict[str, Any]) -> dict[str, Any]:
        """``POST /api/v1/chat`` — ask a question about the current dataset/analysis/plan.

        ``context`` is a plain dict shaped like the backend's
        ``ChatContext`` (session_id, selected_dataset, analysis_result,
        ...) — the frontend assembles it fresh from ``DashboardState`` on
        every call; there is no server-side conversation memory.
        """
        payload = {"question": question, "context": context}
        return dict(self._request("POST", "/api/v1/chat", json=payload))

    # -- SQL data sources -----------------------------------------------------

    def connect_sql(self, connection: dict[str, Any]) -> dict[str, Any]:
        """``POST /api/v1/datasources/sql/connect`` — validate config shape and test real connectivity."""
        return dict(self._request("POST", "/api/v1/datasources/sql/connect", json=connection))

    def list_sql_tables(self, connection: dict[str, Any]) -> list[str]:
        """``POST /api/v1/datasources/sql/tables`` — list every table visible to this connection."""
        return list(self._request("POST", "/api/v1/datasources/sql/tables", json=connection))

    def preview_sql_table(self, connection: dict[str, Any], table_name: str, limit: int = 10) -> dict[str, Any]:
        """``POST /api/v1/datasources/sql/preview`` — preview a table's rows and full structure."""
        payload = {"connection": connection, "table_name": table_name, "limit": limit}
        return dict(self._request("POST", "/api/v1/datasources/sql/preview", json=payload))

    def preview_sql_query(self, connection: dict[str, Any], query: str, limit: int = 10) -> dict[str, Any]:
        """``POST /api/v1/datasources/sql/preview`` — preview a custom query's rows."""
        payload = {"connection": connection, "query": query, "limit": limit}
        return dict(self._request("POST", "/api/v1/datasources/sql/preview", json=payload))

    def import_sql_table(
        self, connection: dict[str, Any], table_name: str, dataset_name: str | None = None
    ) -> dict[str, Any]:
        """``POST /api/v1/datasources/sql/import/table`` — import a whole table as a BusinessDataset."""
        payload = {"connection": connection, "table_name": table_name, "dataset_name": dataset_name}
        return dict(self._request("POST", "/api/v1/datasources/sql/import/table", json=payload))

    def import_sql_query(self, connection: dict[str, Any], query: str, dataset_name: str) -> dict[str, Any]:
        """``POST /api/v1/datasources/sql/import/query`` — import a custom query's result as a BusinessDataset."""
        payload = {"connection": connection, "query": query, "dataset_name": dataset_name}
        return dict(self._request("POST", "/api/v1/datasources/sql/import/query", json=payload))

    # -- Reports ----------------------------------------------------------------

    def generate_report(
        self,
        dataset: dict[str, Any],
        cleaning_outcome: dict[str, Any] | None = None,
        analysis_result: dict[str, Any] | None = None,
        visualization_result: dict[str, Any] | None = None,
        planner_output: dict[str, Any] | None = None,
        template_type: str = "business_report",
        theme: str = "corporate",
        title: str | None = None,
        subtitle: str | None = None,
        author: str | None = None,
    ) -> dict[str, Any]:
        """``POST /api/v1/reports`` — build a ReportDocument from whatever pipeline outputs are given.

        Only ``dataset`` is required; every other input that's ``None``
        simply means the sections that would have needed it are left out
        of the report — mirroring ``ReportBuilder``'s own tolerance for
        missing inputs.
        """
        payload = {
            "dataset": dataset,
            "cleaning_outcome": cleaning_outcome,
            "analysis_result": analysis_result,
            "visualization_result": visualization_result,
            "planner_output": planner_output,
            "template_type": template_type,
            "theme": theme,
            "title": title,
            "subtitle": subtitle,
            "author": author,
        }
        return dict(self._request("POST", "/api/v1/reports", json=payload))

    def list_reports(self) -> list[dict[str, Any]]:
        """``GET /api/v1/reports`` — every report generated so far, most recent first."""
        return list(self._request("GET", "/api/v1/reports"))

    def get_report(self, report_id: str) -> dict[str, Any]:
        """``GET /api/v1/reports/{report_id}`` — fetch one previously generated report."""
        return dict(self._request("GET", f"/api/v1/reports/{report_id}"))

    def export_report(self, report_id: str, export_format: str = "json") -> str:
        """``GET /api/v1/reports/{report_id}/export`` — export a report as a JSON or Markdown string."""
        return str(self._request("GET", f"/api/v1/reports/{report_id}/export", params={"format": export_format}))

    def list_report_templates(self) -> list[str]:
        """``GET /api/v1/reports/templates`` — every available report template type."""
        return list(self._request("GET", "/api/v1/reports/templates"))

    def list_report_themes(self) -> list[str]:
        """``GET /api/v1/reports/themes`` — every registered report theme name."""
        return list(self._request("GET", "/api/v1/reports/themes"))

    # -- MCP ----------------------------------------------------------------------

    def register_mcp_server(
        self,
        server_id: str,
        name: str,
        transport: str,
        description: str | None = None,
        capabilities: list[str] | None = None,
        version: str = "1.0.0",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """``POST /api/v1/mcp/servers`` — register a new MCP server (metadata only, no connection attempt)."""
        payload = {
            "server_id": server_id,
            "name": name,
            "description": description,
            "transport": transport,
            "capabilities": capabilities or [],
            "version": version,
            "metadata": metadata or {},
        }
        return dict(self._request("POST", "/api/v1/mcp/servers", json=payload))

    def list_mcp_servers(self) -> list[dict[str, Any]]:
        """``GET /api/v1/mcp/servers`` — every registered MCP server."""
        return list(self._request("GET", "/api/v1/mcp/servers"))

    def get_mcp_server(self, server_id: str) -> dict[str, Any]:
        """``GET /api/v1/mcp/servers/{server_id}`` — fetch one registered MCP server."""
        return dict(self._request("GET", f"/api/v1/mcp/servers/{server_id}"))

    def remove_mcp_server(self, server_id: str) -> dict[str, Any]:
        """``DELETE /api/v1/mcp/servers/{server_id}`` — unregister an MCP server."""
        return dict(self._request("DELETE", f"/api/v1/mcp/servers/{server_id}"))

    def get_mcp_health(self) -> dict[str, Any]:
        """``GET /api/v1/mcp/health`` — aggregate MCP server health, by lifecycle status."""
        return dict(self._request("GET", "/api/v1/mcp/health"))

    def list_mcp_capabilities(self) -> list[str]:
        """``GET /api/v1/mcp/capabilities`` — every capability kind the MCP layer recognizes."""
        return list(self._request("GET", "/api/v1/mcp/capabilities"))

    # -- File Agent -----------------------------------------------------------

    def execute_file_agent(
        self,
        dataset_reference: str,
        session_id: str,
        generate_report: bool = False,
        step_id: str | None = None,
    ) -> dict[str, Any]:
        """``POST /api/v1/agents/file/execute`` — run FileAgent for one dataset reference.

        Builds a minimal ``ExecutionStep`` itself (the backend's real
        contract), so the dashboard never needs to construct one by
        hand for this single-step, direct-invocation use.
        """
        step = {
            "step_id": step_id or uuid.uuid4().hex,
            "name": "File Agent Execution",
            "node_name": "file_agent",
            "inputs": {"dataset_reference": dataset_reference, "generate_report": generate_report},
        }
        payload = {"step": step, "session_id": session_id}
        return dict(self._request("POST", "/api/v1/agents/file/execute", json=payload))

    def list_file_agent_executions(self) -> list[dict[str, Any]]:
        """``GET /api/v1/agents/file/executions`` — every stored agent result, most recent first.

        Returns results from *every* agent (File, SQL, ...), not just
        FileAgent's own — the backend deliberately shares one result
        store across agents (see ``backend/api/v1/sql_agent.py``), so
        there is no separate SQLAgent-scoped list endpoint to call.
        """
        return list(self._request("GET", "/api/v1/agents/file/executions"))

    def get_file_agent_execution(self, step_id: str) -> dict[str, Any]:
        """``GET /api/v1/agents/file/executions/{step_id}`` — fetch one FileAgent result."""
        return dict(self._request("GET", f"/api/v1/agents/file/executions/{step_id}"))

    # -- SQL Agent --------------------------------------------------------------

    def execute_sql_agent(
        self,
        connection: dict[str, Any],
        session_id: str,
        table_name: str | None = None,
        query: str | None = None,
        dataset_name: str | None = None,
        generate_report: bool = False,
        step_id: str | None = None,
    ) -> dict[str, Any]:
        """``POST /api/v1/agents/sql/execute`` — run SQLAgent for one table or query.

        Builds a minimal ``ExecutionStep`` itself, same as
        ``execute_file_agent()``. Exactly one of ``table_name``/``query``
        must be given — the backend rejects both or neither with a 422.
        """
        inputs: dict[str, Any] = {"connection": connection, "generate_report": generate_report}
        if table_name is not None:
            inputs["table_name"] = table_name
        if query is not None:
            inputs["query"] = query
        if dataset_name is not None:
            inputs["dataset_name"] = dataset_name
        step = {
            "step_id": step_id or uuid.uuid4().hex,
            "name": "SQL Agent Execution",
            "node_name": "sql_agent",
            "inputs": inputs,
        }
        payload = {"step": step, "session_id": session_id}
        return dict(self._request("POST", "/api/v1/agents/sql/execute", json=payload))

    def get_sql_agent_execution(self, step_id: str) -> dict[str, Any]:
        """``GET /api/v1/agents/sql/executions/{step_id}`` — fetch one SQLAgent result."""
        return dict(self._request("GET", f"/api/v1/agents/sql/executions/{step_id}"))

    # -- Browser Agent ------------------------------------------------------------

    def execute_browser_agent(
        self,
        session_id: str,
        search_request: str | None = None,
        companies: list[str] | None = None,
        industries: list[str] | None = None,
        products: list[str] | None = None,
        keywords: list[str] | None = None,
        step_id: str | None = None,
    ) -> dict[str, Any]:
        """``POST /api/v1/agents/browser/execute`` — gather external context for a topic.

        Builds a minimal ``ExecutionStep`` itself, same as
        ``execute_file_agent()``/``execute_sql_agent()``. Every argument
        beyond ``session_id`` is optional — a step with none of them
        given still succeeds, coming back with ``status: "skipped"``.
        """
        inputs: dict[str, Any] = {}
        if search_request is not None:
            inputs["search_request"] = search_request
        if companies:
            inputs["companies"] = companies
        if industries:
            inputs["industries"] = industries
        if products:
            inputs["products"] = products
        if keywords:
            inputs["keywords"] = keywords
        step = {
            "step_id": step_id or uuid.uuid4().hex,
            "name": "Browser Agent Execution",
            "node_name": "browser_agent",
            "inputs": inputs,
        }
        payload = {"step": step, "session_id": session_id}
        return dict(self._request("POST", "/api/v1/agents/browser/execute", json=payload))

    def get_browser_agent_execution(self, step_id: str) -> dict[str, Any]:
        """``GET /api/v1/agents/browser/executions/{step_id}`` — fetch one BrowserAgent result."""
        return dict(self._request("GET", f"/api/v1/agents/browser/executions/{step_id}"))

    # -- Report Agent ---------------------------------------------------------------

    def execute_report_agent(
        self,
        session_id: str,
        dataset: dict[str, Any],
        cleaning_outcome: dict[str, Any] | None = None,
        analysis_result: dict[str, Any] | None = None,
        visualization_result: dict[str, Any] | None = None,
        browser_agent_result: dict[str, Any] | None = None,
        report_config: dict[str, Any] | None = None,
        step_id: str | None = None,
    ) -> dict[str, Any]:
        """``POST /api/v1/agents/report/execute`` — build a report from already-computed pipeline outputs.

        Builds a minimal ``ExecutionStep`` itself, same as
        ``execute_file_agent()``/``execute_sql_agent()``/
        ``execute_browser_agent()``. Only ``dataset`` is required; every
        other pipeline input is optional, mirroring ``ReportService``'s
        own tolerance for missing inputs.
        """
        inputs: dict[str, Any] = {"dataset": dataset}
        if cleaning_outcome is not None:
            inputs["cleaning_outcome"] = cleaning_outcome
        if analysis_result is not None:
            inputs["analysis_result"] = analysis_result
        if visualization_result is not None:
            inputs["visualization_result"] = visualization_result
        if browser_agent_result is not None:
            inputs["browser_agent_result"] = browser_agent_result
        if report_config is not None:
            inputs["report_config"] = report_config
        step = {
            "step_id": step_id or uuid.uuid4().hex,
            "name": "Report Agent Execution",
            "node_name": "report_agent",
            "inputs": inputs,
        }
        payload = {"step": step, "session_id": session_id}
        return dict(self._request("POST", "/api/v1/agents/report/execute", json=payload))

    def get_report_agent_execution(self, step_id: str) -> dict[str, Any]:
        """``GET /api/v1/agents/report/executions/{step_id}`` — fetch one ReportAgent result."""
        return dict(self._request("GET", f"/api/v1/agents/report/executions/{step_id}"))

    # -- Executive Summary Agent ---------------------------------------------------

    def execute_executive_summary_agent(
        self,
        session_id: str,
        report_document: dict[str, Any],
        browser_agent_result: dict[str, Any] | None = None,
        dataset_metadata: dict[str, Any] | None = None,
        analysis_metadata: dict[str, Any] | None = None,
        step_id: str | None = None,
    ) -> dict[str, Any]:
        """``POST /api/v1/agents/executive-summary/execute`` — write a grounded executive
        summary from an already-built report.

        Builds a minimal ``ExecutionStep`` itself, same as
        ``execute_report_agent()``. Only ``report_document`` is required;
        every other input is optional context.
        """
        inputs: dict[str, Any] = {"report_document": report_document}
        if browser_agent_result is not None:
            inputs["browser_agent_result"] = browser_agent_result
        if dataset_metadata is not None:
            inputs["dataset_metadata"] = dataset_metadata
        if analysis_metadata is not None:
            inputs["analysis_metadata"] = analysis_metadata
        step = {
            "step_id": step_id or uuid.uuid4().hex,
            "name": "Executive Summary Agent Execution",
            "node_name": "executive_summary_agent",
            "inputs": inputs,
        }
        payload = {"step": step, "session_id": session_id}
        return dict(self._request("POST", "/api/v1/agents/executive-summary/execute", json=payload))

    def get_executive_summary_execution(self, step_id: str) -> dict[str, Any]:
        """``GET /api/v1/agents/executive-summary/executions/{step_id}`` — fetch one
        ExecutiveSummaryAgent result."""
        return dict(self._request("GET", f"/api/v1/agents/executive-summary/executions/{step_id}"))

    # -- Observability --------------------------------------------------------------

    def list_traces(self) -> list[dict[str, Any]]:
        """``GET /api/v1/observability/traces`` — every execution trace, in-progress first."""
        return list(self._request("GET", "/api/v1/observability/traces"))

    def get_trace(self, trace_id: str) -> dict[str, Any]:
        """``GET /api/v1/observability/traces/{trace_id}`` — fetch one execution trace."""
        return dict(self._request("GET", f"/api/v1/observability/traces/{trace_id}"))

    def get_trace_for_plan(self, plan_id: str) -> dict[str, Any]:
        """``GET /api/v1/observability/traces/plan/{plan_id}`` — fetch a plan's execution trace."""
        return dict(self._request("GET", f"/api/v1/observability/traces/plan/{plan_id}"))

    def get_trace_timeline(self, trace_id: str) -> list[dict[str, Any]]:
        """``GET /api/v1/observability/traces/{trace_id}/timeline`` — the trace's chronological event list."""
        return list(self._request("GET", f"/api/v1/observability/traces/{trace_id}/timeline"))

    def export_trace(self, trace_id: str, export_format: str = "json") -> str:
        """``GET /api/v1/observability/traces/{trace_id}/export`` — export a trace as JSON, Markdown, or CSV."""
        return str(
            self._request(
                "GET", f"/api/v1/observability/traces/{trace_id}/export", params={"format": export_format}
            )
        )

    def get_agent_metrics(self) -> list[dict[str, Any]]:
        """``GET /api/v1/observability/metrics/agents`` — per-agent call count, failures, and latency."""
        return list(self._request("GET", "/api/v1/observability/metrics/agents"))

    def get_tool_metrics(self) -> list[dict[str, Any]]:
        """``GET /api/v1/observability/metrics/tools`` — per-tool call count, failures, and latency."""
        return list(self._request("GET", "/api/v1/observability/metrics/tools"))

    def get_ai_metrics(self) -> dict[str, Any]:
        """``GET /api/v1/observability/metrics/ai`` — AI call count, token usage, cost, and latency."""
        return dict(self._request("GET", "/api/v1/observability/metrics/ai"))

    def get_metrics_summary(self) -> dict[str, Any]:
        """``GET /api/v1/observability/metrics/summary`` — overall execution/approval metrics plus breakdowns."""
        return dict(self._request("GET", "/api/v1/observability/metrics/summary"))

    # -- Execution (dependency-aware parallel DAG engine) --------------------------

    def start_execution(self, plan: dict[str, Any], session_id: str | None = None) -> dict[str, Any]:
        """``POST /api/v1/execution/start`` — run a READY ExecutionPlan as a parallel DAG."""
        return dict(self._request("POST", "/api/v1/execution/start", json={"plan": plan, "session_id": session_id}))

    def resume_execution(self, execution_id: str) -> dict[str, Any]:
        """``POST /api/v1/execution/{execution_id}/resume`` — resume a PAUSED execution."""
        return dict(self._request("POST", f"/api/v1/execution/{execution_id}/resume"))

    def cancel_execution(self, execution_id: str) -> dict[str, Any]:
        """``POST /api/v1/execution/{execution_id}/cancel`` — cancel every running/queued/paused step."""
        return dict(self._request("POST", f"/api/v1/execution/{execution_id}/cancel"))

    def get_execution(self, execution_id: str) -> dict[str, Any]:
        """``GET /api/v1/execution/{execution_id}`` — fetch one execution's current state."""
        return dict(self._request("GET", f"/api/v1/execution/{execution_id}"))

    def get_execution_progress(self, execution_id: str) -> dict[str, Any]:
        """``GET /api/v1/execution/{execution_id}/progress`` — percent complete and per-status step lists."""
        return dict(self._request("GET", f"/api/v1/execution/{execution_id}/progress"))

    def get_execution_graph(self, execution_id: str) -> str:
        """``GET /api/v1/execution/{execution_id}/graph`` — the plan as Mermaid, steps highlighted by status."""
        return str(self._request("GET", f"/api/v1/execution/{execution_id}/graph"))

    # -- Memory (long-term knowledge layer) ------------------------------------------

    def create_memory(
        self,
        title: str,
        summary: str,
        memory_type: str,
        scope: str = "session",
        content: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        importance: float = 0.5,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """``POST /api/v1/memory`` — remember a new MemoryItem."""
        payload = {
            "title": title,
            "summary": summary,
            "memory_type": memory_type,
            "scope": scope,
            "content": content or {},
            "tags": tags or [],
            "importance": importance,
            "metadata": metadata or {},
        }
        return dict(self._request("POST", "/api/v1/memory", json=payload))

    def list_memories(self) -> list[dict[str, Any]]:
        """``GET /api/v1/memory`` — every stored memory, most recently added first."""
        return list(self._request("GET", "/api/v1/memory"))

    def get_memory(self, memory_id: str) -> dict[str, Any]:
        """``GET /api/v1/memory/{memory_id}`` — fetch one memory by id."""
        return dict(self._request("GET", f"/api/v1/memory/{memory_id}"))

    def delete_memory(self, memory_id: str) -> bool:
        """``DELETE /api/v1/memory/{memory_id}`` — forget one memory."""
        return bool(self._request("DELETE", f"/api/v1/memory/{memory_id}"))

    def search_memories(
        self,
        keyword: str | None = None,
        tags: list[str] | None = None,
        memory_type: str | None = None,
        scope: str | None = None,
        min_importance: float | None = None,
        top_k: int | None = None,
    ) -> dict[str, Any]:
        """``POST /api/v1/memory/search`` — deterministic keyword/tag/type/scope/importance search."""
        payload = {
            "keyword": keyword,
            "tags": tags or [],
            "memory_type": memory_type,
            "scope": scope,
            "min_importance": min_importance,
            "top_k": top_k,
        }
        return dict(self._request("POST", "/api/v1/memory/search", json=payload))

    def summarize_memories(self, query: dict[str, Any] | None = None, max_length: int = 800) -> str:
        """``POST /api/v1/memory/summarize`` — deterministic, extractive summary of matching memories."""
        payload = {"query": query, "max_length": max_length}
        return str(self._request("POST", "/api/v1/memory/summarize", json=payload))

    def get_memory_statistics(self) -> dict[str, Any]:
        """``GET /api/v1/memory/statistics`` — aggregate counts, recency, and average importance."""
        return dict(self._request("GET", "/api/v1/memory/statistics"))

    def export_memories(self, export_format: str = "json") -> str:
        """``GET /api/v1/memory/export/{format}`` — export every memory as JSON or Markdown."""
        return str(self._request("GET", f"/api/v1/memory/export/{export_format}"))

    def clear_memories(self) -> bool:
        """``DELETE /api/v1/memory`` — remove every stored memory."""
        return bool(self._request("DELETE", "/api/v1/memory"))

    # -- Collaboration (autonomous multi-agent collaboration) ------------------------

    def list_agent_capabilities(self) -> list[dict[str, Any]]:
        """``GET /api/v1/collaboration/capabilities`` — every registered agent's declared capability."""
        return list(self._request("GET", "/api/v1/collaboration/capabilities"))

    def start_collaboration(
        self,
        goal: str,
        assigned_agent: str,
        description: str,
        session_id: str | None = None,
        inputs: dict[str, Any] | None = None,
        reason: str = "",
    ) -> dict[str, Any]:
        """``POST /api/v1/collaboration/start`` — create a session and delegate its first SubTask."""
        payload = {
            "goal": goal,
            "session_id": session_id,
            "context": {},
            "assigned_agent": assigned_agent,
            "description": description,
            "inputs": inputs or {},
            "reason": reason,
        }
        return dict(self._request("POST", "/api/v1/collaboration/start", json=payload))

    def delegate_subtask(
        self,
        collaboration_id: str,
        assigned_agent: str,
        description: str,
        inputs: dict[str, Any] | None = None,
        dependencies: list[str] | None = None,
        reason: str = "",
    ) -> dict[str, Any]:
        """``POST /api/v1/collaboration/{id}/delegate`` — assign one more SubTask."""
        payload = {
            "assigned_agent": assigned_agent,
            "description": description,
            "inputs": inputs or {},
            "dependencies": dependencies or [],
            "reason": reason,
        }
        return dict(self._request("POST", f"/api/v1/collaboration/{collaboration_id}/delegate", json=payload))

    def run_collaboration(self, collaboration_id: str) -> dict[str, Any]:
        """``POST /api/v1/collaboration/{id}/run`` — run every ready (and dynamically spawned) subtask."""
        return dict(self._request("POST", f"/api/v1/collaboration/{collaboration_id}/run"))

    def resume_collaboration(self, collaboration_id: str) -> dict[str, Any]:
        """``POST /api/v1/collaboration/{id}/resume`` — resume a PAUSED collaboration session."""
        return dict(self._request("POST", f"/api/v1/collaboration/{collaboration_id}/resume"))

    def cancel_collaboration(self, collaboration_id: str) -> dict[str, Any]:
        """``POST /api/v1/collaboration/{id}/cancel`` — cancel a collaboration session outright."""
        return dict(self._request("POST", f"/api/v1/collaboration/{collaboration_id}/cancel"))

    def get_collaboration(self, collaboration_id: str) -> dict[str, Any]:
        """``GET /api/v1/collaboration/{id}`` — fetch a collaboration session's current task graph."""
        return dict(self._request("GET", f"/api/v1/collaboration/{collaboration_id}"))

    def get_collaboration_history(self, collaboration_id: str) -> dict[str, Any]:
        """``GET /api/v1/collaboration/{id}/history`` — messages, delegations, negotiations, artifact exchanges."""
        return dict(self._request("GET", f"/api/v1/collaboration/{collaboration_id}/history"))

    def get_collaboration_statistics(self) -> dict[str, Any]:
        """``GET /api/v1/collaboration/statistics`` — aggregate counts across every tracked session."""
        return dict(self._request("GET", "/api/v1/collaboration/statistics"))

    # -- Reflection (self-reflection & continuous learning) ---------------------------

    def generate_reflection(
        self, plan: dict[str, Any], collaboration_id: str | None = None, report_id: str | None = None
    ) -> dict[str, Any]:
        """``POST /api/v1/reflection/generate`` — reflect on a completed plan's execution."""
        payload = {"plan": plan, "collaboration_id": collaboration_id, "report_id": report_id}
        return dict(self._request("POST", "/api/v1/reflection/generate", json=payload))

    def get_reflection(self, reflection_id: str) -> dict[str, Any]:
        """``GET /api/v1/reflection/{id}`` — fetch one reflection by id."""
        return dict(self._request("GET", f"/api/v1/reflection/{reflection_id}"))

    def list_reflections(self) -> list[dict[str, Any]]:
        """``GET /api/v1/reflection/list`` — every stored reflection, most recent first."""
        return list(self._request("GET", "/api/v1/reflection/list"))

    def get_reflection_statistics(self) -> dict[str, Any]:
        """``GET /api/v1/reflection/statistics`` — aggregate counts/averages across every reflection."""
        return dict(self._request("GET", "/api/v1/reflection/statistics"))

    def export_reflection(self, reflection_id: str, export_format: str = "json") -> str:
        """``GET /api/v1/reflection/export/{format}/{id}`` — export one reflection as JSON or Markdown."""
        return str(self._request("GET", f"/api/v1/reflection/export/{export_format}/{reflection_id}"))

    # -- Adaptive Planning (deterministic plan optimization) -------------------------

    def optimize_plan(self, plan: dict[str, Any], session_id: str | None = None) -> dict[str, Any]:
        """``POST /api/v1/adaptive/optimize`` — optimize a plan against historical evidence and remember it."""
        payload = {"plan": plan, "session_id": session_id}
        return dict(self._request("POST", "/api/v1/adaptive/optimize", json=payload))

    def explain_plan_optimization(self, plan: dict[str, Any], session_id: str | None = None) -> dict[str, Any]:
        """``POST /api/v1/adaptive/explain`` — preview what optimizing a plan would suggest, no side effects."""
        payload = {"plan": plan, "session_id": session_id}
        return dict(self._request("POST", "/api/v1/adaptive/explain", json=payload))

    def get_adaptive_statistics(self) -> dict[str, Any]:
        """``GET /api/v1/adaptive/statistics`` — aggregate counts/averages across every optimization."""
        return dict(self._request("GET", "/api/v1/adaptive/statistics"))

    def get_adaptive_history(self) -> list[dict[str, Any]]:
        """``GET /api/v1/adaptive/history`` — every stored optimization, most recent first."""
        return list(self._request("GET", "/api/v1/adaptive/history"))

    def export_optimization(self, optimization_id: str, export_format: str = "json") -> str:
        """``GET /api/v1/adaptive/export/{format}/{id}`` — export one optimization as JSON or Markdown."""
        return str(self._request("GET", f"/api/v1/adaptive/export/{export_format}/{optimization_id}"))

    # -- Plugins (Plugin & Extension SDK) ----------------------------------------------

    def list_plugins(self) -> list[dict[str, Any]]:
        """``GET /api/v1/plugins`` — every known plugin record, any lifecycle state."""
        return list(self._request("GET", "/api/v1/plugins"))

    def get_plugin(self, plugin_id: str) -> dict[str, Any]:
        """``GET /api/v1/plugins/{id}`` — fetch one plugin's current record."""
        return dict(self._request("GET", f"/api/v1/plugins/{plugin_id}"))

    def reload_plugins(self, plugin_id: str | None = None) -> list[dict[str, Any]]:
        """``POST /api/v1/plugins/reload`` — unload (if active) then load again."""
        return list(self._request("POST", "/api/v1/plugins/reload", json={"plugin_id": plugin_id}))

    def load_plugins(self, plugin_id: str | None = None) -> list[dict[str, Any]]:
        """``POST /api/v1/plugins/load`` — discover and load every not-yet-active plugin."""
        return list(self._request("POST", "/api/v1/plugins/load", json={"plugin_id": plugin_id}))

    def unload_plugin(self, plugin_id: str) -> dict[str, Any]:
        """``POST /api/v1/plugins/unload`` — shut down and unregister one active plugin."""
        return dict(self._request("POST", "/api/v1/plugins/unload", json={"plugin_id": plugin_id}))

    # -- Operations (deployment/config/health) -------------------------------------------

    def get_operations_health(self) -> dict[str, Any]:
        """``GET /api/v1/operations/health`` — liveness probe."""
        return dict(self._request("GET", "/api/v1/operations/health"))

    def get_operations_readiness(self) -> dict[str, Any]:
        """``GET /api/v1/operations/readiness`` — readiness probe, reflecting StartupManager's last run."""
        return dict(self._request("GET", "/api/v1/operations/readiness"))

    def get_operations_diagnostics(self) -> dict[str, Any]:
        """``GET /api/v1/operations/diagnostics`` — full operational snapshot."""
        return dict(self._request("GET", "/api/v1/operations/diagnostics"))

    def get_operations_configuration(self) -> dict[str, Any]:
        """``GET /api/v1/operations/configuration`` — active profile, resolved settings, validation result."""
        return dict(self._request("GET", "/api/v1/operations/configuration"))

    def get_feature_flags(self) -> list[dict[str, Any]]:
        """``GET /api/v1/operations/feature-flags`` — every feature flag's current, read-only state."""
        return list(self._request("GET", "/api/v1/operations/feature-flags"))

    # -- Security (authentication, authorization, users, audit) -------------------------

    def login(self, username: str, password: str) -> dict[str, Any]:
        """``POST /api/v1/login`` — verify credentials, returns a fresh access/refresh token pair + profile."""
        return dict(self._request("POST", "/api/v1/login", json={"username": username, "password": password}))

    def logout(self, refresh_token: str) -> bool:
        """``POST /api/v1/logout`` — revoke a refresh token's session."""
        return bool(self._request("POST", "/api/v1/logout", json={"refresh_token": refresh_token}))

    def refresh_token(self, refresh_token: str) -> dict[str, Any]:
        """``POST /api/v1/refresh-token`` — exchange a refresh token for a fresh (rotated) pair."""
        return dict(self._request("POST", "/api/v1/refresh-token", json={"refresh_token": refresh_token}))

    def get_current_user(self) -> dict[str, Any]:
        """``GET /api/v1/me`` — the caller's own profile. Requires this client's own access_token."""
        return dict(self._request("GET", "/api/v1/me"))

    def list_security_users(self) -> list[dict[str, Any]]:
        """``GET /api/v1/users`` — every registered user's public profile. Requires manage_users."""
        return list(self._request("GET", "/api/v1/users"))

    def create_security_user(
        self, username: str, email: str, password: str, role: str, full_name: str = "",
    ) -> dict[str, Any]:
        """``POST /api/v1/users`` — create a new user. Requires manage_users."""
        return dict(
            self._request(
                "POST", "/api/v1/users",
                json={"username": username, "email": email, "password": password, "role": role, "full_name": full_name},
            )
        )

    def update_security_user(self, user_id: str, **fields: Any) -> dict[str, Any]:
        """``PUT /api/v1/users/{id}`` — update one or more fields of an existing user. Requires manage_users."""
        return dict(self._request("PUT", f"/api/v1/users/{user_id}", json=fields))

    def delete_security_user(self, user_id: str) -> dict[str, Any]:
        """``DELETE /api/v1/users/{id}`` — delete a user. Requires manage_users."""
        return dict(self._request("DELETE", f"/api/v1/users/{user_id}"))

    def get_audit_log(self, limit: int = 100) -> list[dict[str, Any]]:
        """``GET /api/v1/audit`` — most-recent-first audit events. Requires view_audit."""
        return list(self._request("GET", "/api/v1/audit", params={"limit": limit}))

    def get_roles(self) -> dict[str, Any]:
        """``GET /api/v1/roles`` — every built-in role mapped to its granted permissions."""
        return dict(self._request("GET", "/api/v1/roles"))

    def get_permissions(self) -> list[str]:
        """``GET /api/v1/permissions`` — every permission this deployment recognizes."""
        return list(self._request("GET", "/api/v1/permissions"))

    # -- Workflows (Autonomous Workflow Engine) ------------------------------------------

    def create_workflow(
        self, name: str | None = None, description: str = "", steps: list[dict[str, Any]] | None = None,
        objective: str | None = None, tags: list[str] | None = None, session_id: str | None = None,
    ) -> dict[str, Any]:
        """``POST /api/v1/workflows`` — create from explicit steps, or from a natural-language objective."""
        body = {
            "name": name, "description": description, "steps": steps, "objective": objective,
            "tags": tags or [], "session_id": session_id,
        }
        return dict(self._request("POST", "/api/v1/workflows", json=body))

    def list_workflows(self) -> list[dict[str, Any]]:
        """``GET /api/v1/workflows`` — every known workflow, oldest first."""
        return list(self._request("GET", "/api/v1/workflows"))

    def get_workflow(self, workflow_id: str) -> dict[str, Any]:
        """``GET /api/v1/workflows/{id}`` — fetch one workflow by id."""
        return dict(self._request("GET", f"/api/v1/workflows/{workflow_id}"))

    def execute_workflow(self, workflow_id: str, session_id: str | None = None) -> dict[str, Any]:
        """``POST /api/v1/workflows/{id}/execute`` — validate, optimize, and run a workflow."""
        return dict(self._request("POST", f"/api/v1/workflows/{workflow_id}/execute", json={"session_id": session_id}))

    def pause_workflow(self, workflow_id: str) -> dict[str, Any]:
        """``POST /api/v1/workflows/{id}/pause`` — pause a workflow's latest execution."""
        return dict(self._request("POST", f"/api/v1/workflows/{workflow_id}/pause"))

    def resume_workflow(self, workflow_id: str, session_id: str | None = None) -> dict[str, Any]:
        """``POST /api/v1/workflows/{id}/resume`` — resume a workflow's latest execution."""
        return dict(self._request("POST", f"/api/v1/workflows/{workflow_id}/resume", json={"session_id": session_id}))

    def cancel_workflow(self, workflow_id: str) -> dict[str, Any]:
        """``POST /api/v1/workflows/{id}/cancel`` — cancel a workflow's latest execution."""
        return dict(self._request("POST", f"/api/v1/workflows/{workflow_id}/cancel"))

    def clone_workflow(self, workflow_id: str, new_name: str | None = None) -> dict[str, Any]:
        """``POST /api/v1/workflows/{id}/clone`` — create a fresh, DRAFT copy of a workflow."""
        return dict(self._request("POST", f"/api/v1/workflows/{workflow_id}/clone", json={"new_name": new_name}))

    def get_workflow_statistics(self, workflow_id: str) -> dict[str, Any]:
        """``GET /api/v1/workflows/{id}/statistics`` — aggregate execution counts/durations."""
        return dict(self._request("GET", f"/api/v1/workflows/{workflow_id}/statistics"))

    def get_workflow_graph(self, workflow_id: str) -> str:
        """``GET /api/v1/workflows/{id}/graph`` — the workflow's dependency graph as Mermaid."""
        return str(self._request("GET", f"/api/v1/workflows/{workflow_id}/graph"))

    # -- Realtime (Live Event Streaming) --------------------------------------------------

    def list_realtime_event_types(self) -> list[str]:
        """``GET /api/v1/realtime/events`` — every EventType this transport layer can carry."""
        return list(self._request("GET", "/api/v1/realtime/events"))

    def list_realtime_subscriptions(self) -> list[str]:
        """``GET /api/v1/realtime/subscriptions`` — every connection_id with an active filter."""
        return list(self._request("GET", "/api/v1/realtime/subscriptions"))

    def replay_realtime_events(
        self,
        count: int | None = None,
        since: str | None = None,
        event_type: list[str] | None = None,
        workflow_id: str | None = None,
        trace_id: str | None = None,
        user_id: str | None = None,
        agent_name: str | None = None,
    ) -> list[dict[str, Any]]:
        """``GET /api/v1/realtime/replay`` — recorded event history, oldest first."""
        params: dict[str, Any] = {
            "count": count, "since": since, "event_type": event_type,
            "workflow_id": workflow_id, "trace_id": trace_id, "user_id": user_id, "agent_name": agent_name,
        }
        return list(self._request("GET", "/api/v1/realtime/replay", params={k: v for k, v in params.items() if v}))

    def stream_realtime_events(
        self,
        event_type: list[str] | None = None,
        workflow_id: str | None = None,
        trace_id: str | None = None,
        agent_name: str | None = None,
        listen_seconds: float = 2.0,
    ) -> list[dict[str, Any]]:
        """Open ``/ws/events``, subscribe with the given filters, and collect whatever
        events arrive within ``listen_seconds`` — one bounded listen per call, since
        Streamlit re-runs the whole script on every interaction rather than holding a
        persistent connection open across reruns. Returns an empty list (never raises)
        if the socket can't be reached, so a page can render its last-known state.
        """
        import asyncio

        from frontend.api.realtime_stream import listen_once

        try:
            return asyncio.run(
                listen_once(
                    ws_url=self._websocket_url(),
                    access_token=self._access_token,
                    event_type=event_type, workflow_id=workflow_id, trace_id=trace_id, agent_name=agent_name,
                    listen_seconds=listen_seconds,
                )
            )
        except Exception:  # noqa: BLE001 - a page's live feed must degrade to "nothing new" on any connection problem, never crash the rerun
            return []

    def _websocket_url(self) -> str:
        return self._base_url.replace("https://", "wss://").replace("http://", "ws://") + "/ws/events"

    # -- Distributed Execution & Horizontal Scaling ----------------------------------------

    def list_workers(self) -> list[dict[str, Any]]:
        """``GET /api/v1/distributed/workers`` — every registered worker."""
        return list(self._request("GET", "/api/v1/distributed/workers"))

    def register_worker(
        self,
        worker_id: str,
        hostname: str,
        capabilities: list[str],
        maximum_parallel_tasks: int = 1,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """``POST /api/v1/distributed/workers/register`` — register (or re-register) a worker."""
        body = {
            "worker_id": worker_id, "hostname": hostname, "capabilities": capabilities,
            "maximum_parallel_tasks": maximum_parallel_tasks, "metadata": metadata or {},
        }
        return dict(self._request("POST", "/api/v1/distributed/workers/register", json=body))

    def send_worker_heartbeat(self, worker_id: str, active_task_count: int | None = None) -> dict[str, Any]:
        """``POST /api/v1/distributed/workers/heartbeat``."""
        body: dict[str, Any] = {"worker_id": worker_id, "active_task_count": active_task_count, "metadata": {}}
        return dict(self._request("POST", "/api/v1/distributed/workers/heartbeat", json=body))

    def drain_worker(self, worker_id: str) -> dict[str, Any]:
        """``POST /api/v1/distributed/workers/drain``."""
        return dict(self._request("POST", "/api/v1/distributed/workers/drain", json={"worker_id": worker_id}))

    def shutdown_worker(self, worker_id: str) -> dict[str, Any]:
        """``POST /api/v1/distributed/workers/shutdown``."""
        return dict(self._request("POST", "/api/v1/distributed/workers/shutdown", json={"worker_id": worker_id}))

    def get_cluster_statistics(self) -> dict[str, Any]:
        """``GET /api/v1/distributed/cluster``."""
        return dict(self._request("GET", "/api/v1/distributed/cluster"))

    def get_queue_snapshot(self) -> dict[str, Any]:
        """``GET /api/v1/distributed/queue`` — active and retry-pending task assignments."""
        return dict(self._request("GET", "/api/v1/distributed/queue"))

    # -- Federated Multi-Cluster Orchestration ---------------------------------------------

    def list_clusters(self) -> list[dict[str, Any]]:
        """``GET /api/v1/federation/clusters`` — every registered cluster, including the local one."""
        return list(self._request("GET", "/api/v1/federation/clusters"))

    def register_cluster(
        self,
        cluster_id: str,
        name: str,
        endpoint: str,
        capabilities: dict[str, Any],
        version: str = "0.1.0",
        registered_workers: int = 0,
    ) -> dict[str, Any]:
        """``POST /api/v1/federation/clusters/register`` — register (or re-register) a remote cluster."""
        body = {
            "cluster_id": cluster_id, "name": name, "endpoint": endpoint, "capabilities": capabilities,
            "version": version, "registered_workers": registered_workers,
        }
        return dict(self._request("POST", "/api/v1/federation/clusters/register", json=body))

    def remove_cluster(self, cluster_id: str) -> bool:
        """``POST /api/v1/federation/clusters/remove``."""
        return bool(self._request("POST", "/api/v1/federation/clusters/remove", json={"cluster_id": cluster_id}))

    def get_federation_health(self) -> list[dict[str, Any]]:
        """``GET /api/v1/federation/health`` — every cluster's current health snapshot."""
        return list(self._request("GET", "/api/v1/federation/health"))

    def get_federation_statistics(self) -> dict[str, Any]:
        """``GET /api/v1/federation/statistics``."""
        return dict(self._request("GET", "/api/v1/federation/statistics"))

    def get_routing_decisions(self) -> list[dict[str, Any]]:
        """``GET /api/v1/federation/routing`` — every routing decision ever made."""
        return list(self._request("GET", "/api/v1/federation/routing"))

    # -- Autonomous Optimization & Self-Healing ---------------------------------------------

    def run_autonomous_analysis(self) -> dict[str, Any]:
        """``POST /api/v1/autonomous/analyze`` — run one analysis pass and store the report."""
        return dict(self._request("POST", "/api/v1/autonomous/analyze"))

    def list_optimization_reports(self) -> list[dict[str, Any]]:
        """``GET /api/v1/autonomous/reports`` — every report generated so far."""
        return list(self._request("GET", "/api/v1/autonomous/reports"))

    def get_optimization_report(self, report_id: str) -> dict[str, Any]:
        """``GET /api/v1/autonomous/reports/{report_id}``."""
        return dict(self._request("GET", f"/api/v1/autonomous/reports/{report_id}"))

    def get_autonomous_statistics(self) -> dict[str, Any]:
        """``GET /api/v1/autonomous/statistics``."""
        return dict(self._request("GET", "/api/v1/autonomous/statistics"))

    def list_healing_recommendations(self) -> list[dict[str, Any]]:
        """``GET /api/v1/autonomous/recommendations`` — every advisory recommendation ever generated."""
        return list(self._request("GET", "/api/v1/autonomous/recommendations"))
