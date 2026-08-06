"""Unit tests for frontend.api.client.APIClient.

Each test injects a synchronous ``httpx.MockTransport`` so these run
without a live backend process — they verify the client's own request
construction and envelope handling, not the backend's behavior (that is
covered separately by ``tests/test_api_v1_*.py`` against the real app).
"""

import httpx
import pytest

from frontend.api.client import APIClient
from frontend.api.exceptions import APIError, BackendUnavailableError


def _client(
    handler: httpx.MockTransport | None = None,
    transport: httpx.BaseTransport | None = None,
) -> APIClient:
    return APIClient(
        "http://testserver", transport=transport if transport is not None else handler
    )


def _success_handler(data: object, message: str = "Success") -> httpx.MockTransport:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"success": True, "message": message, "data": data}
        )

    return httpx.MockTransport(handle)


def _error_handler(
    status_code: int, error_type: str, message: str = "Failed", detail: object = None
) -> httpx.MockTransport:
    def handle(request: httpx.Request) -> httpx.Response:
        body = {
            "success": False,
            "message": message,
            "errors": {
                "type": error_type,
                "status_code": status_code,
                "path": str(request.url.path),
                "detail": detail,
            },
        }
        return httpx.Response(status_code, json=body)

    return httpx.MockTransport(handle)


def _raising_handler(exc: Exception) -> httpx.MockTransport:
    def handle(request: httpx.Request) -> httpx.Response:
        raise exc

    return httpx.MockTransport(handle)


def test_health_check_returns_data() -> None:
    client = _client(
        _success_handler(
            {"status": "healthy", "application": "InsightPilot", "version": "0.1.0"}
        )
    )
    result = client.health_check()
    assert result == {
        "status": "healthy",
        "application": "InsightPilot",
        "version": "0.1.0",
    }


def test_create_session_returns_data() -> None:
    client = _client(_success_handler({"session_id": "abc123", "uploaded_files": []}))
    result = client.create_session()
    assert result["session_id"] == "abc123"


def test_get_session_uses_path_parameter() -> None:
    captured: dict[str, str] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["path"] = str(request.url.path)
        return httpx.Response(
            200, json={"success": True, "message": "ok", "data": {"session_id": "s1"}}
        )

    client = _client(httpx.MockTransport(handle))
    client.get_session("s1")
    assert captured["path"] == "/api/v1/sessions/s1"


def test_upload_dataset_sends_multipart_and_session_id() -> None:
    captured: dict[str, object] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["content_type"] = request.headers.get("content-type", "")
        captured["body"] = request.read()
        return httpx.Response(
            200, json={"success": True, "message": "ok", "data": {"dataset_id": "d1"}}
        )

    client = _client(httpx.MockTransport(handle))
    result = client.upload_dataset("s1", "sales.csv", b"a,b\n1,2\n", "text/csv")

    assert result["dataset_id"] == "d1"
    assert str(captured["content_type"]).startswith("multipart/form-data")
    assert b"sales.csv" in captured["body"]  # type: ignore[operator]
    assert b"s1" in captured["body"]  # type: ignore[operator]


def test_list_datasets_returns_list() -> None:
    client = _client(_success_handler([{"dataset_id": "d1"}, {"dataset_id": "d2"}]))
    result = client.list_datasets()
    assert [d["dataset_id"] for d in result] == ["d1", "d2"]


def test_clean_dataset_returns_outcome() -> None:
    client = _client(
        _success_handler({"dataset": {"dataset_id": "d1"}, "result": {}, "profile": {}})
    )
    result = client.clean_dataset("d1")
    assert result["dataset"]["dataset_id"] == "d1"


def test_analyze_posts_cleaning_outcome_as_json_body() -> None:
    captured: dict[str, object] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.read()
        return httpx.Response(
            200, json={"success": True, "message": "ok", "data": {"analysis_id": "a1"}}
        )

    outcome = {"dataset": {"dataset_id": "d1"}, "result": {}, "profile": {}}
    client = _client(httpx.MockTransport(handle))
    result = client.analyze(outcome)

    assert result["analysis_id"] == "a1"
    assert b'"dataset_id":"d1"' in captured["body"]  # type: ignore[operator]


def test_generate_visualizations_returns_data() -> None:
    client = _client(
        _success_handler(
            {"visualization_result": {"charts": []}, "rendered_charts": {}}
        )
    )
    result = client.generate_visualizations({"analysis_id": "a1"}, theme="dark")
    assert result["visualization_result"]["charts"] == []


def test_create_plan_returns_data() -> None:
    client = _client(
        _success_handler(
            {
                "step_id": "s1",
                "status": "completed",
                "planner_output": {"goal": "Clean the dataset.", "execution_plan": {"steps": []}},
                "warnings": [],
            }
        )
    )
    result = client.create_plan("Clean my data")
    assert result["status"] == "completed"
    assert result["planner_output"]["goal"] == "Clean the dataset."


def test_create_plan_sends_user_request_inside_step_inputs() -> None:
    captured: dict[str, object] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.read()
        return httpx.Response(
            200,
            json={
                "success": True,
                "message": "ok",
                "data": {"step_id": "s1", "status": "completed", "planner_output": None, "warnings": []},
            },
        )

    client = _client(httpx.MockTransport(handle))
    client.create_plan("Clean my data", session_id="sess-1")

    assert b'"user_request":"Clean my data"' in captured["body"]  # type: ignore[operator]
    assert b'"session_id":"sess-1"' in captured["body"]  # type: ignore[operator]
    assert b'"node_name":"planner"' in captured["body"]  # type: ignore[operator]


def test_preview_plan_returns_data() -> None:
    client = _client(_success_handler({"mermaid": "flowchart TD", "json_export": "{}", "timeline": {"entries": []}}))
    result = client.preview_plan({"plan_id": "p1", "steps": []})
    assert result["mermaid"] == "flowchart TD"


def test_validate_plan_returns_data() -> None:
    client = _client(
        _success_handler({"plan": {"plan_id": "p1"}, "validation": {"is_valid": True, "issues": []}})
    )
    result = client.validate_plan({"plan_id": "p1", "steps": []})
    assert result["validation"]["is_valid"] is True


def test_explain_plan_returns_data() -> None:
    client = _client(_success_handler({"goal": "Clean the dataset.", "confidence": 0.9, "steps": []}))
    result = client.explain_plan({"plan_id": "p1", "steps": []})
    assert result["goal"] == "Clean the dataset."


def test_execute_plan_returns_data() -> None:
    client = _client(_success_handler({"plan_id": "p1", "status": "completed"}))
    result = client.execute_plan({"plan_id": "p1", "steps": []})
    assert result["status"] == "completed"


def test_get_system_status_returns_data() -> None:
    client = _client(_success_handler({"application_version": "0.1.0"}))
    result = client.get_system_status()
    assert result["application_version"] == "0.1.0"


def test_ask_chat_posts_question_and_context_as_json_body() -> None:
    captured: dict[str, object] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.read()
        return httpx.Response(
            200,
            json={
                "success": True,
                "message": "ok",
                "data": {"answer": "You have 100 rows.", "intent": "kpi"},
            },
        )

    client = _client(httpx.MockTransport(handle))
    result = client.ask_chat("What are the KPIs?", {"session_id": "s1"})

    assert result["answer"] == "You have 100 rows."
    assert b"What are the KPIs?" in captured["body"]  # type: ignore[operator]
    assert b'"session_id":"s1"' in captured["body"]  # type: ignore[operator]


def test_connect_sql_returns_data() -> None:
    client = _client(
        _success_handler(
            {
                "is_valid": True,
                "database_type": "sqlite",
                "message": "Connection successful.",
            }
        )
    )
    result = client.connect_sql({"database_type": "sqlite", "database": "/tmp/data.db"})
    assert result["is_valid"] is True


def test_list_sql_tables_returns_list() -> None:
    client = _client(_success_handler(["customers", "orders"]))
    result = client.list_sql_tables(
        {"database_type": "sqlite", "database": "/tmp/data.db"}
    )
    assert result == ["customers", "orders"]


def test_preview_sql_table_sends_table_name_and_limit() -> None:
    captured: dict[str, object] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.read()
        return httpx.Response(
            200,
            json={"success": True, "message": "ok", "data": {"preview": {"rows": []}}},
        )

    client = _client(httpx.MockTransport(handle))
    client.preview_sql_table(
        {"database_type": "sqlite", "database": "d"}, "customers", limit=5
    )

    assert b'"table_name":"customers"' in captured["body"]  # type: ignore[operator]
    assert b'"limit":5' in captured["body"]  # type: ignore[operator]


def test_preview_sql_query_sends_query_and_limit() -> None:
    captured: dict[str, object] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.read()
        return httpx.Response(
            200,
            json={"success": True, "message": "ok", "data": {"preview": {"rows": []}}},
        )

    client = _client(httpx.MockTransport(handle))
    client.preview_sql_query(
        {"database_type": "sqlite", "database": "d"}, "SELECT 1", limit=5
    )

    assert b'"query":"SELECT 1"' in captured["body"]  # type: ignore[operator]


def test_import_sql_table_returns_business_dataset() -> None:
    client = _client(
        _success_handler({"dataset_id": "d1", "dataset_name": "customers"})
    )
    result = client.import_sql_table(
        {"database_type": "sqlite", "database": "d"}, "customers"
    )
    assert result["dataset_name"] == "customers"


def test_import_sql_query_returns_business_dataset() -> None:
    client = _client(
        _success_handler({"dataset_id": "d1", "dataset_name": "region_counts"})
    )
    result = client.import_sql_query(
        {"database_type": "sqlite", "database": "d"}, "SELECT 1", "region_counts"
    )
    assert result["dataset_name"] == "region_counts"


def test_generate_report_posts_all_inputs_as_json_body() -> None:
    captured: dict[str, object] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.read()
        return httpx.Response(
            200, json={"success": True, "message": "ok", "data": {"report_id": "r1"}}
        )

    client = _client(httpx.MockTransport(handle))
    result = client.generate_report(
        {"dataset_id": "d1"}, analysis_result={"analysis_id": "a1"}, theme="dark"
    )

    assert result["report_id"] == "r1"
    assert b'"dataset":{"dataset_id":"d1"}' in captured["body"]  # type: ignore[operator]
    assert b'"theme":"dark"' in captured["body"]  # type: ignore[operator]


def test_list_reports_returns_list() -> None:
    client = _client(_success_handler([{"report_id": "r1"}, {"report_id": "r2"}]))
    result = client.list_reports()
    assert [r["report_id"] for r in result] == ["r1", "r2"]


def test_get_report_uses_path_parameter() -> None:
    captured: dict[str, str] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["path"] = str(request.url.path)
        return httpx.Response(
            200, json={"success": True, "message": "ok", "data": {"report_id": "r1"}}
        )

    client = _client(httpx.MockTransport(handle))
    client.get_report("r1")
    assert captured["path"] == "/api/v1/reports/r1"


def test_export_report_sends_format_as_query_parameter() -> None:
    captured: dict[str, bytes] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["query"] = request.url.query
        return httpx.Response(
            200, json={"success": True, "message": "ok", "data": "# Report"}
        )

    client = _client(httpx.MockTransport(handle))
    result = client.export_report("r1", "markdown")

    assert result == "# Report"
    assert captured["query"] == b"format=markdown"


def test_list_report_templates_returns_list() -> None:
    client = _client(_success_handler(["business_report", "executive_summary"]))
    assert client.list_report_templates() == ["business_report", "executive_summary"]


def test_list_report_themes_returns_list() -> None:
    client = _client(_success_handler(["corporate", "dark"]))
    assert client.list_report_themes() == ["corporate", "dark"]


def test_register_mcp_server_posts_all_fields_as_json_body() -> None:
    captured: dict[str, object] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.read()
        return httpx.Response(
            200, json={"success": True, "message": "ok", "data": {"server_id": "fs-1"}}
        )

    client = _client(httpx.MockTransport(handle))
    result = client.register_mcp_server(
        "fs-1", "Local Filesystem", "stdio", capabilities=["filesystem"]
    )

    assert result["server_id"] == "fs-1"
    assert b'"server_id":"fs-1"' in captured["body"]  # type: ignore[operator]
    assert b'"transport":"stdio"' in captured["body"]  # type: ignore[operator]
    assert b'"capabilities":["filesystem"]' in captured["body"]  # type: ignore[operator]


def test_list_mcp_servers_returns_list() -> None:
    client = _client(_success_handler([{"server_id": "fs-1"}, {"server_id": "sql-1"}]))
    result = client.list_mcp_servers()
    assert [s["server_id"] for s in result] == ["fs-1", "sql-1"]


def test_get_mcp_server_uses_path_parameter() -> None:
    captured: dict[str, str] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["path"] = str(request.url.path)
        return httpx.Response(
            200, json={"success": True, "message": "ok", "data": {"server_id": "fs-1"}}
        )

    client = _client(httpx.MockTransport(handle))
    client.get_mcp_server("fs-1")
    assert captured["path"] == "/api/v1/mcp/servers/fs-1"


def test_remove_mcp_server_sends_delete_request() -> None:
    captured: dict[str, str] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["path"] = str(request.url.path)
        return httpx.Response(
            200, json={"success": True, "message": "ok", "data": {"server_id": "fs-1"}}
        )

    client = _client(httpx.MockTransport(handle))
    result = client.remove_mcp_server("fs-1")

    assert result["server_id"] == "fs-1"
    assert captured["method"] == "DELETE"
    assert captured["path"] == "/api/v1/mcp/servers/fs-1"


def test_get_mcp_health_returns_data() -> None:
    client = _client(
        _success_handler({"total_servers": 2, "by_status": {"connected": 1}})
    )
    result = client.get_mcp_health()
    assert result["total_servers"] == 2


def test_list_mcp_capabilities_returns_list() -> None:
    client = _client(_success_handler(["filesystem", "sql"]))
    assert client.list_mcp_capabilities() == ["filesystem", "sql"]


def test_execute_file_agent_builds_a_minimal_step_and_posts_it() -> None:
    captured: dict[str, object] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.read()
        return httpx.Response(
            200, json={"success": True, "message": "ok", "data": {"step_id": "s1"}}
        )

    client = _client(httpx.MockTransport(handle))
    result = client.execute_file_agent(
        "/data/sales.csv", "sess-1", generate_report=True, step_id="s1"
    )

    assert result["step_id"] == "s1"
    assert b'"step_id":"s1"' in captured["body"]  # type: ignore[operator]
    assert b'"dataset_reference":"/data/sales.csv"' in captured["body"]  # type: ignore[operator]
    assert b'"generate_report":true' in captured["body"]  # type: ignore[operator]
    assert b'"session_id":"sess-1"' in captured["body"]  # type: ignore[operator]


def test_execute_file_agent_generates_a_step_id_when_none_given() -> None:
    captured: dict[str, object] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.read()
        return httpx.Response(200, json={"success": True, "message": "ok", "data": {}})

    client = _client(httpx.MockTransport(handle))
    client.execute_file_agent("/data/sales.csv", "sess-1")

    assert b'"step_id":""' not in captured["body"]  # type: ignore[operator]
    assert b'"step_id":"' in captured["body"]  # type: ignore[operator]


def test_list_file_agent_executions_returns_list() -> None:
    client = _client(_success_handler([{"step_id": "s1"}, {"step_id": "s2"}]))
    result = client.list_file_agent_executions()
    assert [e["step_id"] for e in result] == ["s1", "s2"]


def test_get_file_agent_execution_uses_path_parameter() -> None:
    captured: dict[str, str] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["path"] = str(request.url.path)
        return httpx.Response(
            200, json={"success": True, "message": "ok", "data": {"step_id": "s1"}}
        )

    client = _client(httpx.MockTransport(handle))
    client.get_file_agent_execution("s1")
    assert captured["path"] == "/api/v1/agents/file/executions/s1"


def test_execute_sql_agent_builds_a_minimal_step_with_table_name() -> None:
    captured: dict[str, object] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.read()
        return httpx.Response(
            200, json={"success": True, "message": "ok", "data": {"step_id": "s1"}}
        )

    client = _client(httpx.MockTransport(handle))
    connection = {"database_type": "sqlite", "database": "/tmp/data.db"}
    result = client.execute_sql_agent(
        connection, "sess-1", table_name="sales", step_id="s1"
    )

    assert result["step_id"] == "s1"
    assert b'"table_name":"sales"' in captured["body"]  # type: ignore[operator]
    assert b'"query"' not in captured["body"]  # type: ignore[operator]
    assert b'"session_id":"sess-1"' in captured["body"]  # type: ignore[operator]


def test_execute_sql_agent_builds_a_minimal_step_with_query() -> None:
    captured: dict[str, object] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.read()
        return httpx.Response(
            200, json={"success": True, "message": "ok", "data": {"step_id": "s1"}}
        )

    client = _client(httpx.MockTransport(handle))
    connection = {"database_type": "sqlite", "database": "/tmp/data.db"}
    client.execute_sql_agent(connection, "sess-1", query="SELECT 1", dataset_name="q1")

    assert b'"query":"SELECT 1"' in captured["body"]  # type: ignore[operator]
    assert b'"dataset_name":"q1"' in captured["body"]  # type: ignore[operator]
    assert b'"table_name"' not in captured["body"]  # type: ignore[operator]


def test_get_sql_agent_execution_uses_path_parameter() -> None:
    captured: dict[str, str] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["path"] = str(request.url.path)
        return httpx.Response(
            200, json={"success": True, "message": "ok", "data": {"step_id": "s1"}}
        )

    client = _client(httpx.MockTransport(handle))
    client.get_sql_agent_execution("s1")
    assert captured["path"] == "/api/v1/agents/sql/executions/s1"


def test_execute_browser_agent_builds_a_minimal_step_with_every_field() -> None:
    captured: dict[str, object] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.read()
        return httpx.Response(
            200, json={"success": True, "message": "ok", "data": {"step_id": "s1"}}
        )

    client = _client(httpx.MockTransport(handle))
    result = client.execute_browser_agent(
        "sess-1",
        search_request="Acme Corp",
        companies=["Acme Corp"],
        industries=["Widgets"],
        step_id="s1",
    )

    assert result["step_id"] == "s1"
    assert b'"search_request":"Acme Corp"' in captured["body"]  # type: ignore[operator]
    assert b'"companies":["Acme Corp"]' in captured["body"]  # type: ignore[operator]
    assert b'"industries":["Widgets"]' in captured["body"]  # type: ignore[operator]
    assert b'"products"' not in captured["body"]  # type: ignore[operator]
    assert b'"session_id":"sess-1"' in captured["body"]  # type: ignore[operator]


def test_execute_browser_agent_with_no_topics_sends_empty_inputs() -> None:
    captured: dict[str, object] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.read()
        return httpx.Response(
            200, json={"success": True, "message": "ok", "data": {"step_id": "s1"}}
        )

    client = _client(httpx.MockTransport(handle))
    client.execute_browser_agent("sess-1", step_id="s1")

    assert b'"inputs":{}' in captured["body"]  # type: ignore[operator]


def test_get_browser_agent_execution_uses_path_parameter() -> None:
    captured: dict[str, str] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["path"] = str(request.url.path)
        return httpx.Response(
            200, json={"success": True, "message": "ok", "data": {"step_id": "s1"}}
        )

    client = _client(httpx.MockTransport(handle))
    client.get_browser_agent_execution("s1")
    assert captured["path"] == "/api/v1/agents/browser/executions/s1"


def test_execute_report_agent_builds_a_minimal_step_with_dataset_and_config() -> None:
    captured: dict[str, object] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.read()
        return httpx.Response(
            200, json={"success": True, "message": "ok", "data": {"step_id": "s1"}}
        )

    client = _client(httpx.MockTransport(handle))
    result = client.execute_report_agent(
        "sess-1",
        dataset={"dataset_id": "d1"},
        analysis_result={"analysis_id": "a1"},
        report_config={"template_type": "business_report", "title": "My Report"},
        step_id="s1",
    )

    assert result["step_id"] == "s1"
    assert b'"dataset":{"dataset_id":"d1"}' in captured["body"]  # type: ignore[operator]
    assert b'"analysis_result":{"analysis_id":"a1"}' in captured["body"]  # type: ignore[operator]
    assert b'"template_type":"business_report"' in captured["body"]  # type: ignore[operator]
    assert b'"cleaning_outcome"' not in captured["body"]  # type: ignore[operator]
    assert b'"session_id":"sess-1"' in captured["body"]  # type: ignore[operator]


def test_execute_report_agent_with_only_dataset_omits_every_optional_field() -> None:
    captured: dict[str, object] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.read()
        return httpx.Response(
            200, json={"success": True, "message": "ok", "data": {"step_id": "s1"}}
        )

    client = _client(httpx.MockTransport(handle))
    client.execute_report_agent("sess-1", dataset={"dataset_id": "d1"}, step_id="s1")

    assert b'"inputs":{"dataset":{"dataset_id":"d1"}}' in captured["body"]  # type: ignore[operator]
    assert b'"node_name":"report_agent"' in captured["body"]  # type: ignore[operator]


def test_get_report_agent_execution_uses_path_parameter() -> None:
    captured: dict[str, str] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["path"] = str(request.url.path)
        return httpx.Response(
            200, json={"success": True, "message": "ok", "data": {"step_id": "s1"}}
        )

    client = _client(httpx.MockTransport(handle))
    client.get_report_agent_execution("s1")
    assert captured["path"] == "/api/v1/agents/report/executions/s1"


def test_execute_executive_summary_agent_builds_a_minimal_step_with_report_document() -> (
    None
):
    captured: dict[str, object] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.read()
        return httpx.Response(
            200, json={"success": True, "message": "ok", "data": {"step_id": "s1"}}
        )

    client = _client(httpx.MockTransport(handle))
    result = client.execute_executive_summary_agent(
        "sess-1",
        report_document={"report_id": "r1", "title": "Sales Report"},
        step_id="s1",
    )

    assert result["step_id"] == "s1"
    assert (
        b'"report_document":{"report_id":"r1","title":"Sales Report"}'
        in captured["body"]
    )  # type: ignore[operator]
    assert b'"browser_agent_result"' not in captured["body"]  # type: ignore[operator]
    assert b'"session_id":"sess-1"' in captured["body"]  # type: ignore[operator]


def test_execute_executive_summary_agent_includes_optional_context_when_given() -> None:
    captured: dict[str, object] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.read()
        return httpx.Response(
            200, json={"success": True, "message": "ok", "data": {"step_id": "s1"}}
        )

    client = _client(httpx.MockTransport(handle))
    client.execute_executive_summary_agent(
        "sess-1",
        report_document={"report_id": "r1"},
        browser_agent_result={"step_id": "b1"},
        dataset_metadata={"row_count": 4},
        step_id="s1",
    )

    assert b'"browser_agent_result":{"step_id":"b1"}' in captured["body"]  # type: ignore[operator]
    assert b'"dataset_metadata":{"row_count":4}' in captured["body"]  # type: ignore[operator]


def test_get_executive_summary_execution_uses_path_parameter() -> None:
    captured: dict[str, str] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["path"] = str(request.url.path)
        return httpx.Response(
            200, json={"success": True, "message": "ok", "data": {"step_id": "s1"}}
        )

    client = _client(httpx.MockTransport(handle))
    client.get_executive_summary_execution("s1")
    assert captured["path"] == "/api/v1/agents/executive-summary/executions/s1"


def test_not_found_raises_api_error_with_structured_fields() -> None:
    client = _client(
        _error_handler(
            404, "NotFoundError", message="Dataset 'x' was not found.", detail=None
        )
    )
    with pytest.raises(APIError) as exc_info:
        client.get_dataset("x")

    error = exc_info.value
    assert error.status_code == 404
    assert error.error_type == "NotFoundError"
    assert error.message == "Dataset 'x' was not found."


def test_validation_error_carries_detail() -> None:
    issues = {
        "is_valid": False,
        "issues": [
            {"severity": "error", "code": "EMPTY_FILE", "message": "File is empty."}
        ],
    }
    client = _client(_error_handler(422, "DatasetValidationError", detail=issues))
    with pytest.raises(APIError) as exc_info:
        client.upload_dataset("s1", "empty.csv", b"", "text/csv")

    assert exc_info.value.detail == issues


def test_connection_failure_raises_backend_unavailable_error() -> None:
    client = _client(_raising_handler(httpx.ConnectError("connection refused")))
    with pytest.raises(BackendUnavailableError):
        client.health_check()


def test_timeout_raises_backend_unavailable_error() -> None:
    client = _client(_raising_handler(httpx.TimeoutException("timed out")))
    with pytest.raises(BackendUnavailableError):
        client.health_check()


# -- Approvals (Human-in-the-Loop) -------------------------------------------


def test_list_pending_approvals_returns_data() -> None:
    client = _client(_success_handler([{"approval_id": "a1", "status": "pending"}]))
    result = client.list_pending_approvals()
    assert result[0]["approval_id"] == "a1"


def test_list_approvals_for_plan_returns_data() -> None:
    client = _client(_success_handler([{"approval_id": "a1", "plan_id": "p1"}]))
    result = client.list_approvals_for_plan("p1")
    assert result[0]["plan_id"] == "p1"


def test_get_plan_history_returns_data() -> None:
    client = _client(_success_handler([{"event_type": "waiting"}, {"event_type": "approved"}]))
    result = client.get_plan_history("p1")
    assert [e["event_type"] for e in result] == ["waiting", "approved"]


def test_approve_approval_sends_approver_in_body() -> None:
    captured: dict[str, object] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.read()
        return httpx.Response(
            200, json={"success": True, "message": "ok", "data": {"approval_id": "a1", "status": "approved"}}
        )

    client = _client(httpx.MockTransport(handle))
    result = client.approve_approval("a1", approver="alice")

    assert result["status"] == "approved"
    assert b'"approver":"alice"' in captured["body"]  # type: ignore[operator]


def test_reject_approval_sends_reason_in_body() -> None:
    captured: dict[str, object] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.read()
        return httpx.Response(
            200, json={"success": True, "message": "ok", "data": {"approval_id": "a1", "status": "rejected"}}
        )

    client = _client(httpx.MockTransport(handle))
    result = client.reject_approval("a1", approver="alice", reason="Too risky.")

    assert result["status"] == "rejected"
    assert b'"reason":"Too risky."' in captured["body"]  # type: ignore[operator]


def test_resume_plan_execution_returns_data() -> None:
    client = _client(_success_handler({"plan_id": "p1", "status": "completed"}))
    result = client.resume_plan_execution("p1")
    assert result["status"] == "completed"


def test_reject_plan_execution_returns_data() -> None:
    client = _client(_success_handler({"plan_id": "p1", "status": "failed"}))
    result = client.reject_plan_execution("p1", reason="Not today.")
    assert result["status"] == "failed"


def test_cancel_plan_execution_returns_data() -> None:
    client = _client(_success_handler({"plan_id": "p1", "status": "cancelled"}))
    result = client.cancel_plan_execution("p1")
    assert result["status"] == "cancelled"


def test_get_approval_policy_returns_data() -> None:
    client = _client(_success_handler({"policy_type": "never"}))
    result = client.get_approval_policy()
    assert result["policy_type"] == "never"


def test_set_approval_policy_sends_policy_type_in_body() -> None:
    captured: dict[str, object] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.read()
        return httpx.Response(200, json={"success": True, "message": "ok", "data": {"policy_type": "always"}})

    client = _client(httpx.MockTransport(handle))
    result = client.set_approval_policy("always")

    assert result["policy_type"] == "always"
    assert b'"policy_type":"always"' in captured["body"]  # type: ignore[operator]


def test_list_traces_returns_list() -> None:
    client = _client(_success_handler([{"trace_id": "t1"}, {"trace_id": "t2"}]))
    result = client.list_traces()
    assert [t["trace_id"] for t in result] == ["t1", "t2"]


def test_get_trace_uses_path_parameter() -> None:
    captured: dict[str, str] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["path"] = str(request.url.path)
        return httpx.Response(200, json={"success": True, "message": "ok", "data": {"trace_id": "t1"}})

    client = _client(httpx.MockTransport(handle))
    result = client.get_trace("t1")

    assert result["trace_id"] == "t1"
    assert captured["path"] == "/api/v1/observability/traces/t1"


def test_get_trace_for_plan_uses_path_parameter() -> None:
    captured: dict[str, str] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["path"] = str(request.url.path)
        return httpx.Response(200, json={"success": True, "message": "ok", "data": {"trace_id": "t1"}})

    client = _client(httpx.MockTransport(handle))
    client.get_trace_for_plan("plan-1")

    assert captured["path"] == "/api/v1/observability/traces/plan/plan-1"


def test_get_trace_timeline_returns_list() -> None:
    client = _client(_success_handler([{"kind": "agent", "name": "sql_agent"}]))
    result = client.get_trace_timeline("t1")
    assert result[0]["kind"] == "agent"


def test_export_trace_sends_format_as_query_parameter() -> None:
    captured: dict[str, bytes] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["query"] = request.url.query
        return httpx.Response(200, json={"success": True, "message": "ok", "data": "kind,name\n"})

    client = _client(httpx.MockTransport(handle))
    result = client.export_trace("t1", "csv")

    assert result == "kind,name\n"
    assert captured["query"] == b"format=csv"


def test_get_agent_metrics_returns_list() -> None:
    client = _client(_success_handler([{"agent_name": "sql_agent", "call_count": 3}]))
    result = client.get_agent_metrics()
    assert result[0]["agent_name"] == "sql_agent"


def test_get_tool_metrics_returns_list() -> None:
    client = _client(_success_handler([{"tool_name": "query_database", "call_count": 2}]))
    result = client.get_tool_metrics()
    assert result[0]["tool_name"] == "query_database"


def test_get_ai_metrics_returns_data() -> None:
    client = _client(_success_handler({"call_count": 5, "total_tokens": 100}))
    result = client.get_ai_metrics()
    assert result["call_count"] == 5


def test_get_metrics_summary_returns_data() -> None:
    client = _client(_success_handler({"trace_count": 4}))
    result = client.get_metrics_summary()
    assert result["trace_count"] == 4


def test_start_execution_sends_plan_and_session_id_in_body() -> None:
    captured: dict[str, object] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.read()
        return httpx.Response(200, json={"success": True, "message": "ok", "data": {"execution_id": "e1"}})

    client = _client(httpx.MockTransport(handle))
    result = client.start_execution({"plan_id": "p1"}, session_id="s1")

    assert result["execution_id"] == "e1"
    assert b'"plan_id":"p1"' in captured["body"]  # type: ignore[operator]
    assert b'"session_id":"s1"' in captured["body"]  # type: ignore[operator]


def test_resume_execution_uses_path_parameter() -> None:
    captured: dict[str, str] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["path"] = str(request.url.path)
        return httpx.Response(200, json={"success": True, "message": "ok", "data": {"status": "completed"}})

    client = _client(httpx.MockTransport(handle))
    result = client.resume_execution("e1")

    assert result["status"] == "completed"
    assert captured["path"] == "/api/v1/execution/e1/resume"


def test_cancel_execution_uses_path_parameter() -> None:
    captured: dict[str, str] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["path"] = str(request.url.path)
        return httpx.Response(200, json={"success": True, "message": "ok", "data": {"status": "cancelled"}})

    client = _client(httpx.MockTransport(handle))
    result = client.cancel_execution("e1")

    assert result["status"] == "cancelled"
    assert captured["path"] == "/api/v1/execution/e1/cancel"


def test_get_execution_returns_data() -> None:
    client = _client(_success_handler({"execution_id": "e1", "status": "running"}))
    result = client.get_execution("e1")
    assert result["status"] == "running"


def test_get_execution_progress_returns_data() -> None:
    client = _client(_success_handler({"progress_percent": 50.0}))
    result = client.get_execution_progress("e1")
    assert result["progress_percent"] == 50.0


def test_get_execution_graph_returns_mermaid_string() -> None:
    client = _client(_success_handler("graph TD;\n  a-->b;"))
    result = client.get_execution_graph("e1")
    assert result == "graph TD;\n  a-->b;"


def test_create_memory_sends_expected_body() -> None:
    captured: dict[str, object] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.read()
        return httpx.Response(200, json={"success": True, "message": "ok", "data": {"memory_id": "m1"}})

    client = _client(httpx.MockTransport(handle))
    result = client.create_memory("Title", "Summary", "dataset", tags=["sales"])

    assert result["memory_id"] == "m1"
    assert b'"title":"Title"' in captured["body"]  # type: ignore[operator]
    assert b'"memory_type":"dataset"' in captured["body"]  # type: ignore[operator]


def test_list_memories_returns_list() -> None:
    client = _client(_success_handler([{"memory_id": "m1"}, {"memory_id": "m2"}]))
    result = client.list_memories()
    assert [m["memory_id"] for m in result] == ["m1", "m2"]


def test_get_memory_uses_path_parameter() -> None:
    captured: dict[str, str] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["path"] = str(request.url.path)
        return httpx.Response(200, json={"success": True, "message": "ok", "data": {"memory_id": "m1"}})

    client = _client(httpx.MockTransport(handle))
    client.get_memory("m1")

    assert captured["path"] == "/api/v1/memory/m1"


def test_delete_memory_uses_path_parameter() -> None:
    captured: dict[str, str] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["path"] = str(request.url.path)
        captured["method"] = request.method
        return httpx.Response(200, json={"success": True, "message": "ok", "data": True})

    client = _client(httpx.MockTransport(handle))
    result = client.delete_memory("m1")

    assert result is True
    assert captured["path"] == "/api/v1/memory/m1"
    assert captured["method"] == "DELETE"


def test_search_memories_sends_query_body() -> None:
    captured: dict[str, object] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.read()
        return httpx.Response(200, json={"success": True, "message": "ok", "data": {"items": [], "total_matched": 0}})

    client = _client(httpx.MockTransport(handle))
    result = client.search_memories(keyword="sales", top_k=5)

    assert result["total_matched"] == 0
    assert b'"keyword":"sales"' in captured["body"]  # type: ignore[operator]
    assert b'"top_k":5' in captured["body"]  # type: ignore[operator]


def test_summarize_memories_returns_string() -> None:
    client = _client(_success_handler("2 memories summarized."))
    result = client.summarize_memories()
    assert result == "2 memories summarized."


def test_get_memory_statistics_returns_data() -> None:
    client = _client(_success_handler({"total_items": 3}))
    result = client.get_memory_statistics()
    assert result["total_items"] == 3


def test_export_memories_sends_format_in_path() -> None:
    captured: dict[str, str] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["path"] = str(request.url.path)
        return httpx.Response(200, json={"success": True, "message": "ok", "data": "# Memory Export"})

    client = _client(httpx.MockTransport(handle))
    result = client.export_memories("markdown")

    assert result == "# Memory Export"
    assert captured["path"] == "/api/v1/memory/export/markdown"


def test_clear_memories_returns_true() -> None:
    client = _client(_success_handler(True))
    assert client.clear_memories() is True


def test_list_agent_capabilities_returns_list() -> None:
    client = _client(_success_handler([{"name": "file_agent"}, {"name": "sql_agent"}]))
    result = client.list_agent_capabilities()
    assert [c["name"] for c in result] == ["file_agent", "sql_agent"]


def test_start_collaboration_sends_expected_body() -> None:
    captured: dict[str, object] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.read()
        return httpx.Response(200, json={"success": True, "message": "ok", "data": {"collaboration_id": "c1"}})

    client = _client(httpx.MockTransport(handle))
    result = client.start_collaboration("Analyze sales", "file_agent", "Ingest", session_id="s1")

    assert result["collaboration_id"] == "c1"
    assert b'"goal":"Analyze sales"' in captured["body"]  # type: ignore[operator]
    assert b'"assigned_agent":"file_agent"' in captured["body"]  # type: ignore[operator]


def test_delegate_subtask_sends_expected_body() -> None:
    captured: dict[str, object] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.read()
        return httpx.Response(200, json={"success": True, "message": "ok", "data": {"subtask_id": "st1"}})

    client = _client(httpx.MockTransport(handle))
    result = client.delegate_subtask("c1", "report_agent", "Build report", dependencies=["st0"])

    assert result["subtask_id"] == "st1"
    assert b'"assigned_agent":"report_agent"' in captured["body"]  # type: ignore[operator]
    assert b'"dependencies":["st0"]' in captured["body"]  # type: ignore[operator]


def test_run_collaboration_uses_path_parameter() -> None:
    captured: dict[str, str] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["path"] = str(request.url.path)
        return httpx.Response(200, json={"success": True, "message": "ok", "data": {"status": "completed"}})

    client = _client(httpx.MockTransport(handle))
    result = client.run_collaboration("c1")

    assert result["status"] == "completed"
    assert captured["path"] == "/api/v1/collaboration/c1/run"


def test_resume_collaboration_uses_path_parameter() -> None:
    captured: dict[str, str] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["path"] = str(request.url.path)
        return httpx.Response(200, json={"success": True, "message": "ok", "data": {"status": "completed"}})

    client = _client(httpx.MockTransport(handle))
    client.resume_collaboration("c1")

    assert captured["path"] == "/api/v1/collaboration/c1/resume"


def test_cancel_collaboration_uses_path_parameter() -> None:
    captured: dict[str, str] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["path"] = str(request.url.path)
        return httpx.Response(200, json={"success": True, "message": "ok", "data": {"status": "cancelled"}})

    client = _client(httpx.MockTransport(handle))
    result = client.cancel_collaboration("c1")

    assert result["status"] == "cancelled"
    assert captured["path"] == "/api/v1/collaboration/c1/cancel"


def test_get_collaboration_returns_data() -> None:
    client = _client(_success_handler({"collaboration_id": "c1", "status": "running"}))
    result = client.get_collaboration("c1")
    assert result["status"] == "running"


def test_get_collaboration_history_returns_data() -> None:
    client = _client(_success_handler({"messages": [], "delegations": []}))
    result = client.get_collaboration_history("c1")
    assert result["messages"] == []


def test_get_collaboration_statistics_returns_data() -> None:
    client = _client(_success_handler({"total_sessions": 2}))
    result = client.get_collaboration_statistics()
    assert result["total_sessions"] == 2


def test_generate_reflection_sends_expected_body() -> None:
    captured: dict[str, object] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.read()
        return httpx.Response(200, json={"success": True, "message": "ok", "data": {"reflection_id": "r1"}})

    client = _client(httpx.MockTransport(handle))
    result = client.generate_reflection({"plan_id": "p1"}, collaboration_id="c1")

    assert result["reflection_id"] == "r1"
    assert b'"plan_id":"p1"' in captured["body"]  # type: ignore[operator]
    assert b'"collaboration_id":"c1"' in captured["body"]  # type: ignore[operator]


def test_get_reflection_uses_path_parameter() -> None:
    captured: dict[str, str] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["path"] = str(request.url.path)
        return httpx.Response(200, json={"success": True, "message": "ok", "data": {"reflection_id": "r1"}})

    client = _client(httpx.MockTransport(handle))
    client.get_reflection("r1")

    assert captured["path"] == "/api/v1/reflection/r1"


def test_list_reflections_returns_list() -> None:
    client = _client(_success_handler([{"reflection_id": "r1"}, {"reflection_id": "r2"}]))
    result = client.list_reflections()
    assert [r["reflection_id"] for r in result] == ["r1", "r2"]


def test_get_reflection_statistics_returns_data() -> None:
    client = _client(_success_handler({"total_reflections": 3}))
    result = client.get_reflection_statistics()
    assert result["total_reflections"] == 3


def test_export_reflection_sends_format_and_id_in_path() -> None:
    captured: dict[str, str] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["path"] = str(request.url.path)
        return httpx.Response(200, json={"success": True, "message": "ok", "data": "# Execution Review"})

    client = _client(httpx.MockTransport(handle))
    result = client.export_reflection("r1", "markdown")

    assert result == "# Execution Review"
    assert captured["path"] == "/api/v1/reflection/export/markdown/r1"


def test_optimize_plan_sends_expected_body() -> None:
    captured: dict[str, object] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.read()
        return httpx.Response(200, json={"success": True, "message": "ok", "data": {"optimization_id": "o1"}})

    client = _client(httpx.MockTransport(handle))
    result = client.optimize_plan({"plan_id": "p1"}, session_id="s1")

    assert result["optimization_id"] == "o1"
    assert b'"plan_id":"p1"' in captured["body"]  # type: ignore[operator]
    assert b'"session_id":"s1"' in captured["body"]  # type: ignore[operator]


def test_explain_plan_optimization_sends_expected_body() -> None:
    captured: dict[str, object] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.read()
        return httpx.Response(200, json={"success": True, "message": "ok", "data": {"optimization_id": ""}})

    client = _client(httpx.MockTransport(handle))
    result = client.explain_plan_optimization({"plan_id": "p1"})

    assert result["optimization_id"] == ""
    assert b'"plan_id":"p1"' in captured["body"]  # type: ignore[operator]


def test_get_adaptive_statistics_returns_data() -> None:
    client = _client(_success_handler({"total_optimizations": 4}))
    result = client.get_adaptive_statistics()
    assert result["total_optimizations"] == 4


def test_get_adaptive_history_returns_list() -> None:
    client = _client(_success_handler([{"optimization_id": "o1"}, {"optimization_id": "o2"}]))
    result = client.get_adaptive_history()
    assert [o["optimization_id"] for o in result] == ["o1", "o2"]


def test_export_optimization_sends_format_and_id_in_path() -> None:
    captured: dict[str, str] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["path"] = str(request.url.path)
        return httpx.Response(200, json={"success": True, "message": "ok", "data": "# Plan Optimization"})

    client = _client(httpx.MockTransport(handle))
    result = client.export_optimization("o1", "markdown")

    assert result == "# Plan Optimization"
    assert captured["path"] == "/api/v1/adaptive/export/markdown/o1"


def test_list_plugins_returns_list() -> None:
    client = _client(_success_handler([{"manifest": {"metadata": {"id": "p1"}}}]))
    result = client.list_plugins()
    assert result[0]["manifest"]["metadata"]["id"] == "p1"


def test_get_plugin_uses_path_parameter() -> None:
    captured: dict[str, str] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["path"] = str(request.url.path)
        return httpx.Response(200, json={"success": True, "message": "ok", "data": {"state": "registered"}})

    client = _client(httpx.MockTransport(handle))
    result = client.get_plugin("csv_statistics_plugin")

    assert result["state"] == "registered"
    assert captured["path"] == "/api/v1/plugins/csv_statistics_plugin"


def test_reload_plugins_sends_plugin_id_in_body() -> None:
    captured: dict[str, object] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.read()
        return httpx.Response(200, json={"success": True, "message": "ok", "data": []})

    client = _client(httpx.MockTransport(handle))
    client.reload_plugins("csv_statistics_plugin")

    assert b'"plugin_id":"csv_statistics_plugin"' in captured["body"]  # type: ignore[operator]


def test_load_plugins_sends_null_plugin_id_when_omitted() -> None:
    captured: dict[str, object] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.read()
        return httpx.Response(200, json={"success": True, "message": "ok", "data": []})

    client = _client(httpx.MockTransport(handle))
    client.load_plugins()

    assert b'"plugin_id":null' in captured["body"]  # type: ignore[operator]


def test_unload_plugin_sends_plugin_id_in_body() -> None:
    captured: dict[str, object] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.read()
        return httpx.Response(200, json={"success": True, "message": "ok", "data": {"state": "unloaded"}})

    client = _client(httpx.MockTransport(handle))
    result = client.unload_plugin("csv_statistics_plugin")

    assert result["state"] == "unloaded"
    assert b'"plugin_id":"csv_statistics_plugin"' in captured["body"]  # type: ignore[operator]


def test_get_operations_health_returns_liveness() -> None:
    client = _client(_success_handler({"alive": True, "application": "InsightPilot", "version": "0.1.0"}))
    result = client.get_operations_health()
    assert result["alive"] is True


def test_get_operations_readiness_returns_readiness() -> None:
    client = _client(_success_handler({"ready": True, "profile": "development", "stages": []}))
    result = client.get_operations_readiness()
    assert result["ready"] is True
    assert result["profile"] == "development"


def test_get_operations_diagnostics_returns_report() -> None:
    client = _client(_success_handler({"application": "InsightPilot", "profile": "development"}))
    result = client.get_operations_diagnostics()
    assert result["application"] == "InsightPilot"


def test_get_operations_configuration_returns_environment_report() -> None:
    client = _client(_success_handler({"profile": "production", "environment": "production"}))
    result = client.get_operations_configuration()
    assert result["profile"] == "production"


def test_get_feature_flags_returns_list() -> None:
    client = _client(_success_handler([{"name": "memory_enabled", "enabled": True}]))
    result = client.get_feature_flags()
    assert result[0]["name"] == "memory_enabled"


def test_login_sends_username_and_password() -> None:
    captured: dict[str, object] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.read()
        return httpx.Response(200, json={"success": True, "message": "ok", "data": {"access_token": "a", "refresh_token": "r"}})

    client = _client(httpx.MockTransport(handle))
    result = client.login("alice", "hunter22")

    assert result["access_token"] == "a"
    assert b'"username":"alice"' in captured["body"]  # type: ignore[operator]
    assert b'"password":"hunter22"' in captured["body"]  # type: ignore[operator]


def test_logout_sends_refresh_token_and_returns_bool() -> None:
    client = _client(_success_handler(True))
    assert client.logout("some-refresh-token") is True


def test_refresh_token_returns_new_pair() -> None:
    client = _client(_success_handler({"access_token": "new-a", "refresh_token": "new-r"}))
    result = client.refresh_token("old-refresh-token")
    assert result["access_token"] == "new-a"


def test_get_current_user_returns_profile() -> None:
    client = _client(_success_handler({"username": "alice"}))
    result = client.get_current_user()
    assert result["username"] == "alice"


def test_list_security_users_returns_list() -> None:
    client = _client(_success_handler([{"username": "alice"}, {"username": "bob"}]))
    result = client.list_security_users()
    assert [u["username"] for u in result] == ["alice", "bob"]


def test_create_security_user_sends_expected_body() -> None:
    captured: dict[str, object] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.read()
        return httpx.Response(200, json={"success": True, "message": "ok", "data": {"username": "alice"}})

    client = _client(httpx.MockTransport(handle))
    client.create_security_user("alice", "alice@example.com", "hunter22", "viewer", "Alice A")

    assert b'"role":"viewer"' in captured["body"]  # type: ignore[operator]
    assert b'"full_name":"Alice A"' in captured["body"]  # type: ignore[operator]


def test_update_security_user_sends_only_given_fields() -> None:
    captured: dict[str, object] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["path"] = str(request.url.path)
        captured["body"] = request.read()
        return httpx.Response(200, json={"success": True, "message": "ok", "data": {"role": "analyst"}})

    client = _client(httpx.MockTransport(handle))
    client.update_security_user("u1", role="analyst")

    assert captured["path"] == "/api/v1/users/u1"
    assert b'"role":"analyst"' in captured["body"]  # type: ignore[operator]


def test_delete_security_user_uses_path_parameter() -> None:
    captured: dict[str, str] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["path"] = str(request.url.path)
        return httpx.Response(200, json={"success": True, "message": "ok", "data": {"username": "alice"}})

    client = _client(httpx.MockTransport(handle))
    result = client.delete_security_user("u1")

    assert result["username"] == "alice"
    assert captured["path"] == "/api/v1/users/u1"


def test_get_audit_log_sends_limit_as_query_param() -> None:
    captured: dict[str, str] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["query"] = str(request.url.params)
        return httpx.Response(200, json={"success": True, "message": "ok", "data": []})

    client = _client(httpx.MockTransport(handle))
    client.get_audit_log(limit=25)

    assert "limit=25" in captured["query"]


def test_get_roles_returns_dict() -> None:
    client = _client(_success_handler({"admin": ["manage_users"]}))
    result = client.get_roles()
    assert result["admin"] == ["manage_users"]


def test_get_permissions_returns_list() -> None:
    client = _client(_success_handler(["view_data", "manage_users"]))
    result = client.get_permissions()
    assert "view_data" in result


def test_client_with_access_token_sends_authorization_header() -> None:
    captured: dict[str, str] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers.get("authorization", "")
        return httpx.Response(200, json={"success": True, "message": "ok", "data": {"username": "alice"}})

    client = APIClient("http://testserver", transport=httpx.MockTransport(handle), access_token="my-token")
    client.get_current_user()

    assert captured["authorization"] == "Bearer my-token"


def test_client_without_access_token_sends_no_authorization_header() -> None:
    captured: dict[str, str] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers.get("authorization", "")
        return httpx.Response(200, json={"success": True, "message": "ok", "data": {"status": "healthy"}})

    client = _client(httpx.MockTransport(handle))
    client.health_check()

    assert captured["authorization"] == ""


def test_create_workflow_sends_expected_body() -> None:
    captured: dict[str, object] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.read()
        return httpx.Response(200, json={"success": True, "message": "ok", "data": {"workflow_id": "w1"}})

    client = _client(httpx.MockTransport(handle))
    result = client.create_workflow(name="My Workflow", steps=[{"step_id": "s1"}])

    assert result["workflow_id"] == "w1"
    assert b'"name":"My Workflow"' in captured["body"]  # type: ignore[operator]
    assert b'"steps":[{"step_id":"s1"}]' in captured["body"]  # type: ignore[operator]


def test_list_workflows_returns_list() -> None:
    client = _client(_success_handler([{"workflow_id": "w1"}, {"workflow_id": "w2"}]))
    result = client.list_workflows()
    assert [w["workflow_id"] for w in result] == ["w1", "w2"]


def test_get_workflow_uses_path_parameter() -> None:
    captured: dict[str, str] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["path"] = str(request.url.path)
        return httpx.Response(200, json={"success": True, "message": "ok", "data": {"workflow_id": "w1"}})

    client = _client(httpx.MockTransport(handle))
    client.get_workflow("w1")

    assert captured["path"] == "/api/v1/workflows/w1"


def test_execute_workflow_sends_session_id() -> None:
    captured: dict[str, object] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.read()
        return httpx.Response(200, json={"success": True, "message": "ok", "data": {"status": "completed"}})

    client = _client(httpx.MockTransport(handle))
    result = client.execute_workflow("w1", session_id="s1")

    assert result["status"] == "completed"
    assert b'"session_id":"s1"' in captured["body"]  # type: ignore[operator]


def test_pause_resume_cancel_workflow_use_expected_paths() -> None:
    captured: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        captured.append(str(request.url.path))
        return httpx.Response(200, json={"success": True, "message": "ok", "data": {"status": "paused"}})

    client = _client(httpx.MockTransport(handle))
    client.pause_workflow("w1")
    client.resume_workflow("w1")
    client.cancel_workflow("w1")

    assert captured == [
        "/api/v1/workflows/w1/pause", "/api/v1/workflows/w1/resume", "/api/v1/workflows/w1/cancel",
    ]


def test_clone_workflow_sends_new_name() -> None:
    captured: dict[str, object] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.read()
        return httpx.Response(200, json={"success": True, "message": "ok", "data": {"workflow_id": "w2"}})

    client = _client(httpx.MockTransport(handle))
    result = client.clone_workflow("w1", new_name="Cloned")

    assert result["workflow_id"] == "w2"
    assert b'"new_name":"Cloned"' in captured["body"]  # type: ignore[operator]


def test_get_workflow_statistics_returns_data() -> None:
    client = _client(_success_handler({"total_executions": 3}))
    result = client.get_workflow_statistics("w1")
    assert result["total_executions"] == 3


def test_get_workflow_graph_returns_mermaid_string() -> None:
    client = _client(_success_handler("graph TD;\n    a-->b;"))
    result = client.get_workflow_graph("w1")
    assert result == "graph TD;\n    a-->b;"


# -- Realtime (Live Event Streaming) --------------------------------------------------


def test_list_realtime_event_types_returns_list() -> None:
    client = _client(_success_handler(["workflow_started", "tool_started"]))
    result = client.list_realtime_event_types()
    assert result == ["workflow_started", "tool_started"]


def test_list_realtime_subscriptions_returns_list() -> None:
    client = _client(_success_handler(["conn-1", "conn-2"]))
    result = client.list_realtime_subscriptions()
    assert result == ["conn-1", "conn-2"]


def test_replay_realtime_events_sends_only_the_given_filters() -> None:
    captured = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json={"success": True, "message": "ok", "data": []})

    client = _client(httpx.MockTransport(handle))
    client.replay_realtime_events(count=10, workflow_id="w1")

    assert captured["params"] == {"count": "10", "workflow_id": "w1"}


def test_replay_realtime_events_returns_the_envelopes() -> None:
    envelopes = [{"sequence": 1, "event": {"event_type": "workflow_started"}}]
    client = _client(_success_handler(envelopes))
    result = client.replay_realtime_events(count=5)
    assert result == envelopes


def test_websocket_url_converts_http_scheme_to_ws() -> None:
    client = APIClient("http://testserver")
    assert client._websocket_url() == "ws://testserver/ws/events"


def test_websocket_url_converts_https_scheme_to_wss() -> None:
    client = APIClient("https://testserver")
    assert client._websocket_url() == "wss://testserver/ws/events"


def test_stream_realtime_events_returns_empty_list_when_unreachable() -> None:
    client = APIClient("http://not-a-real-host.invalid:1")
    assert client.stream_realtime_events(listen_seconds=0.1) == []


# -- Distributed Execution & Horizontal Scaling ----------------------------------------


def test_list_workers_returns_list() -> None:
    client = _client(_success_handler([{"worker_id": "w1"}, {"worker_id": "w2"}]))
    result = client.list_workers()
    assert [w["worker_id"] for w in result] == ["w1", "w2"]


def test_register_worker_sends_expected_body() -> None:
    captured: dict[str, object] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.read()
        return httpx.Response(200, json={"success": True, "message": "ok", "data": {"worker_id": "w1"}})

    client = _client(httpx.MockTransport(handle))
    result = client.register_worker("w1", "host-1", ["browser_agent"], maximum_parallel_tasks=2)

    assert result["worker_id"] == "w1"
    assert b'"worker_id":"w1"' in captured["body"]  # type: ignore[operator]
    assert b'"maximum_parallel_tasks":2' in captured["body"]  # type: ignore[operator]


def test_send_worker_heartbeat_returns_data() -> None:
    client = _client(_success_handler({"worker_id": "w1", "status": "online"}))
    result = client.send_worker_heartbeat("w1")
    assert result["status"] == "online"


def test_drain_and_shutdown_worker_use_expected_paths() -> None:
    captured: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        captured.append(str(request.url.path))
        return httpx.Response(200, json={"success": True, "message": "ok", "data": {"worker_id": "w1"}})

    client = _client(httpx.MockTransport(handle))
    client.drain_worker("w1")
    client.shutdown_worker("w1")

    assert captured == ["/api/v1/distributed/workers/drain", "/api/v1/distributed/workers/shutdown"]


def test_get_cluster_statistics_returns_data() -> None:
    client = _client(_success_handler({"total_workers": 2}))
    result = client.get_cluster_statistics()
    assert result["total_workers"] == 2


def test_get_queue_snapshot_returns_data() -> None:
    client = _client(_success_handler({"active": [], "retry": []}))
    result = client.get_queue_snapshot()
    assert result == {"active": [], "retry": []}


# -- Federated Multi-Cluster Orchestration ---------------------------------------------


def test_list_clusters_returns_list() -> None:
    client = _client(_success_handler([{"cluster_id": "local"}, {"cluster_id": "c1"}]))
    result = client.list_clusters()
    assert [c["cluster_id"] for c in result] == ["local", "c1"]


def test_register_cluster_sends_expected_body() -> None:
    captured: dict[str, object] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.read()
        return httpx.Response(200, json={"success": True, "message": "ok", "data": {"cluster_id": "c1"}})

    client = _client(httpx.MockTransport(handle))
    result = client.register_cluster("c1", "Cluster One", "https://c1.example.com", {"supported_agents": ["browser_agent"]})

    assert result["cluster_id"] == "c1"
    assert b'"cluster_id":"c1"' in captured["body"]  # type: ignore[operator]
    assert b'"name":"Cluster One"' in captured["body"]  # type: ignore[operator]


def test_remove_cluster_uses_expected_path() -> None:
    captured: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        captured.append(str(request.url.path))
        return httpx.Response(200, json={"success": True, "message": "ok", "data": True})

    client = _client(httpx.MockTransport(handle))
    client.remove_cluster("c1")

    assert captured == ["/api/v1/federation/clusters/remove"]


def test_get_federation_health_returns_list() -> None:
    client = _client(_success_handler([{"cluster_id": "local", "status": "online"}]))
    result = client.get_federation_health()
    assert result[0]["status"] == "online"


def test_get_federation_statistics_returns_data() -> None:
    client = _client(_success_handler({"total_clusters": 1}))
    result = client.get_federation_statistics()
    assert result["total_clusters"] == 1


def test_get_routing_decisions_returns_list() -> None:
    client = _client(_success_handler([{"decision_id": "d1"}]))
    result = client.get_routing_decisions()
    assert result[0]["decision_id"] == "d1"


# -- Autonomous Optimization & Self-Healing ---------------------------------------------


def test_run_autonomous_analysis_returns_data() -> None:
    client = _client(_success_handler({"report_id": "r1"}))
    result = client.run_autonomous_analysis()
    assert result["report_id"] == "r1"


def test_list_optimization_reports_returns_list() -> None:
    client = _client(_success_handler([{"report_id": "r1"}, {"report_id": "r2"}]))
    result = client.list_optimization_reports()
    assert [r["report_id"] for r in result] == ["r1", "r2"]


def test_get_optimization_report_uses_expected_path() -> None:
    captured: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        captured.append(str(request.url.path))
        return httpx.Response(200, json={"success": True, "message": "ok", "data": {"report_id": "r1"}})

    client = _client(httpx.MockTransport(handle))
    client.get_optimization_report("r1")

    assert captured == ["/api/v1/autonomous/reports/r1"]


def test_get_autonomous_statistics_returns_data() -> None:
    client = _client(_success_handler({"total_reports": 3}))
    result = client.get_autonomous_statistics()
    assert result["total_reports"] == 3


def test_list_healing_recommendations_returns_list() -> None:
    client = _client(_success_handler([{"recommendation_id": "rec1"}]))
    result = client.list_healing_recommendations()
    assert result[0]["recommendation_id"] == "rec1"
