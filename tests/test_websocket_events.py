"""Tests for the ``/ws/events`` WebSocket endpoint, against the real app —
mirrors every other REST test file's own "exercise the real thing" pattern,
using Starlette's ``TestClient.websocket_connect()`` for the live socket.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from backend.main import app

_ADMIN_USERNAME = "admin"
_ADMIN_PASSWORD = "ChangeMe123!"


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def _access_token(client: TestClient) -> str:
    response = client.post("/api/v1/login", json={"username": _ADMIN_USERNAME, "password": _ADMIN_PASSWORD})
    assert response.status_code == 200, response.text
    return str(response.json()["data"]["access_token"])


def test_connect_without_token_is_rejected(client: TestClient) -> None:
    # The server closes (code 4401) before ever accepting the handshake, so
    # Starlette's own test session raises WebSocketDisconnect out of __enter__ itself.
    with pytest.raises(WebSocketDisconnect) as exc_info, client.websocket_connect("/ws/events"):
        pass
    assert exc_info.value.code == 4401


def test_connect_with_valid_token_and_heartbeat(client: TestClient) -> None:
    token = _access_token(client)
    with client.websocket_connect(f"/ws/events?token={token}") as websocket:
        websocket.send_json({"action": "heartbeat"})
        message = websocket.receive_json()
        assert message["type"] == "heartbeat_ack"
        assert "timestamp" in message


def test_subscribe_and_unsubscribe_acknowledge(client: TestClient) -> None:
    token = _access_token(client)
    with client.websocket_connect(f"/ws/events?token={token}") as websocket:
        websocket.send_json({"action": "subscribe", "event_types": ["user_logged_in"]})
        subscribed_ack = websocket.receive_json()
        assert subscribed_ack["type"] == "subscribed"

        websocket.send_json({"action": "unsubscribe"})
        unsubscribed_ack = websocket.receive_json()
        assert unsubscribed_ack["type"] == "unsubscribed"


def test_unknown_action_returns_an_error_message(client: TestClient) -> None:
    token = _access_token(client)
    with client.websocket_connect(f"/ws/events?token={token}") as websocket:
        websocket.send_json({"action": "not_a_real_action"})
        message = websocket.receive_json()
        assert message["type"] == "error"


def test_subscribed_connection_receives_a_live_broadcast(client: TestClient) -> None:
    """The core "no polling" proof: a second, independent request (login) triggers a
    real publish, and the already-open, already-subscribed socket receives it pushed —
    never asked for it, never re-requested."""
    listener_token = _access_token(client)
    with client.websocket_connect(f"/ws/events?token={listener_token}") as websocket:
        websocket.send_json({"action": "subscribe", "event_types": ["user_logged_in"]})
        assert websocket.receive_json()["type"] == "subscribed"

        _access_token(client)  # a second, independent login — publishes UserLoggedIn

        message = websocket.receive_json()
        assert message["event"]["event_type"] == "user_logged_in"


def test_replay_action_sends_matching_history_to_the_requesting_connection(client: TestClient) -> None:
    token = _access_token(client)  # publishes one user_logged_in before the socket even opens
    with client.websocket_connect(f"/ws/events?token={token}") as websocket:
        websocket.send_json({"action": "subscribe", "event_types": ["user_logged_in"]})
        assert websocket.receive_json()["type"] == "subscribed"

        websocket.send_json({"action": "replay", "count": 5})

        message = websocket.receive_json()
        assert message["event"]["event_type"] == "user_logged_in"
