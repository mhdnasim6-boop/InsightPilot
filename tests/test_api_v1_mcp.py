"""Tests for the /api/v1/mcp/* endpoints, against the real app.

The MCP registry is a process-wide singleton shared by every request
(same as BusinessDatasetStore/ReportStore), so each test uses its own
unique server_id to stay independent of what earlier tests registered.
"""

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def _payload(server_id: str, **overrides: object) -> dict:
    payload = {
        "server_id": server_id,
        "name": "Local Filesystem",
        "transport": "stdio",
        "capabilities": ["filesystem"],
    }
    payload.update(overrides)
    return payload


def test_register_server_returns_the_registered_definition() -> None:
    response = client.post("/api/v1/mcp/servers", json=_payload("api-fs-1"))

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["server_id"] == "api-fs-1"
    assert data["status"] == "disconnected"
    assert data["capabilities"] == ["filesystem"]


def test_register_server_defaults_version_when_omitted() -> None:
    response = client.post("/api/v1/mcp/servers", json=_payload("api-fs-2"))
    assert response.json()["data"]["version"] == "1.0.0"


def test_register_duplicate_server_id_returns_409() -> None:
    client.post("/api/v1/mcp/servers", json=_payload("api-dup-1"))

    response = client.post("/api/v1/mcp/servers", json=_payload("api-dup-1"))

    assert response.status_code == 409
    assert response.json()["errors"]["type"] == "MCPServerAlreadyRegisteredError"


def test_register_server_with_invalid_transport_returns_422() -> None:
    response = client.post("/api/v1/mcp/servers", json=_payload("api-bad-1", transport="ftp"))
    assert response.status_code == 422


def test_list_servers_includes_a_newly_registered_server() -> None:
    client.post("/api/v1/mcp/servers", json=_payload("api-list-1"))

    response = client.get("/api/v1/mcp/servers")

    assert response.status_code == 200
    ids = {s["server_id"] for s in response.json()["data"]}
    assert "api-list-1" in ids


def test_get_server_fetches_a_registered_server() -> None:
    client.post("/api/v1/mcp/servers", json=_payload("api-get-1"))

    response = client.get("/api/v1/mcp/servers/api-get-1")

    assert response.status_code == 200
    assert response.json()["data"]["server_id"] == "api-get-1"


def test_get_unknown_server_returns_404() -> None:
    response = client.get("/api/v1/mcp/servers/does-not-exist")
    assert response.status_code == 404
    assert response.json()["errors"]["type"] == "MCPServerNotFoundError"


def test_remove_server_returns_the_removed_definition_and_then_404s() -> None:
    client.post("/api/v1/mcp/servers", json=_payload("api-remove-1"))

    delete_response = client.delete("/api/v1/mcp/servers/api-remove-1")
    assert delete_response.status_code == 200
    assert delete_response.json()["data"]["server_id"] == "api-remove-1"

    get_response = client.get("/api/v1/mcp/servers/api-remove-1")
    assert get_response.status_code == 404


def test_remove_unknown_server_returns_404() -> None:
    response = client.delete("/api/v1/mcp/servers/does-not-exist")
    assert response.status_code == 404


def test_remove_then_reregister_the_same_id_succeeds() -> None:
    client.post("/api/v1/mcp/servers", json=_payload("api-cycle-1"))
    client.delete("/api/v1/mcp/servers/api-cycle-1")

    response = client.post("/api/v1/mcp/servers", json=_payload("api-cycle-1"))

    assert response.status_code == 200


def test_health_reflects_registered_servers() -> None:
    client.post("/api/v1/mcp/servers", json=_payload("api-health-1"))

    response = client.get("/api/v1/mcp/health")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total_servers"] >= 1
    assert set(data["by_status"]) == {"disconnected", "starting", "connected", "stopping", "failed"}
    assert data["by_status"]["disconnected"] >= 1


def test_capabilities_returns_all_six_recognized_values() -> None:
    response = client.get("/api/v1/mcp/capabilities")

    assert response.status_code == 200
    assert set(response.json()["data"]) == {"filesystem", "python", "browser", "sql", "git", "custom"}
