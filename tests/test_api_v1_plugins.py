"""Tests for the /api/v1/plugins/* endpoints, against the real app with the
real demo plugin (backend/extensions/csv_statistics_plugin/) auto-loaded
at startup via lifespan — mirrors every other REST test file's own
"exercise the real thing, never a hand-built fixture" pattern.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.dependencies.tools import get_tool_registry
from backend.main import app

DEMO_PLUGIN_ID = "csv_statistics_plugin"


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def test_list_plugins_includes_the_demo_plugin(client: TestClient) -> None:
    response = client.get("/api/v1/plugins")
    assert response.status_code == 200, response.text
    plugins = response.json()["data"]
    ids = [p["manifest"]["metadata"]["id"] for p in plugins]
    assert DEMO_PLUGIN_ID in ids


def test_get_plugin_returns_the_demo_plugins_record(client: TestClient) -> None:
    response = client.get(f"/api/v1/plugins/{DEMO_PLUGIN_ID}")
    assert response.status_code == 200, response.text
    record = response.json()["data"]
    assert record["state"] == "registered"
    extension_kinds = {e["kind"] for e in record["extensions"]}
    assert extension_kinds == {"tool", "analyzer"}


def test_get_plugin_returns_404_for_unknown_plugin(client: TestClient) -> None:
    response = client.get("/api/v1/plugins/does-not-exist")
    assert response.status_code == 404


def test_the_demo_plugins_tool_is_genuinely_usable_via_tool_registry(client: TestClient) -> None:
    # Proves register_tool() reached the real, shared ToolRegistry — not just PluginRegistry's own catalog.
    tool_registry = get_tool_registry()
    assert tool_registry.get("csv_row_count") is not None


def test_unload_then_reload_round_trips_the_demo_plugin(client: TestClient) -> None:
    unload_response = client.post("/api/v1/plugins/unload", json={"plugin_id": DEMO_PLUGIN_ID})
    assert unload_response.status_code == 200, unload_response.text
    assert unload_response.json()["data"]["state"] == "unloaded"

    tool_registry = get_tool_registry()
    with pytest.raises(Exception):  # noqa: B017 - ToolNotFoundError
        tool_registry.get("csv_row_count")

    reload_response = client.post("/api/v1/plugins/reload", json={"plugin_id": DEMO_PLUGIN_ID})
    assert reload_response.status_code == 200, reload_response.text
    reloaded = next(r for r in reload_response.json()["data"] if r["manifest"]["metadata"]["id"] == DEMO_PLUGIN_ID)
    assert reloaded["state"] == "registered"
    assert tool_registry.get("csv_row_count") is not None


def test_load_is_idempotent_when_the_plugin_is_already_active(client: TestClient) -> None:
    response = client.post("/api/v1/plugins/load", json={})
    assert response.status_code == 200, response.text
    records = [r for r in response.json()["data"] if r["manifest"]["metadata"]["id"] == DEMO_PLUGIN_ID]
    assert len(records) == 1
    assert records[0]["state"] == "registered"
