"""Tests for the MCP connection lifecycle state machine."""

import pytest

from backend.mcp.lifecycle.status import MCPConnectionStatus, can_transition

_S = MCPConnectionStatus


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (_S.DISCONNECTED, _S.STARTING),
        (_S.STARTING, _S.CONNECTED),
        (_S.STARTING, _S.FAILED),
        (_S.CONNECTED, _S.STOPPING),
        (_S.CONNECTED, _S.FAILED),
        (_S.STOPPING, _S.DISCONNECTED),
        (_S.STOPPING, _S.FAILED),
        (_S.FAILED, _S.STARTING),
        (_S.FAILED, _S.DISCONNECTED),
    ],
)
def test_valid_transitions_are_allowed(current: MCPConnectionStatus, target: MCPConnectionStatus) -> None:
    assert can_transition(current, target) is True


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (_S.DISCONNECTED, _S.CONNECTED),  # must pass through STARTING
        (_S.DISCONNECTED, _S.STOPPING),
        (_S.DISCONNECTED, _S.FAILED),
        (_S.CONNECTED, _S.STARTING),  # already connected
        (_S.CONNECTED, _S.DISCONNECTED),  # must pass through STOPPING
        (_S.STOPPING, _S.CONNECTED),
        (_S.STOPPING, _S.STARTING),
        (_S.STARTING, _S.DISCONNECTED),
        (_S.STARTING, _S.STOPPING),
        (_S.FAILED, _S.CONNECTED),
        (_S.FAILED, _S.STOPPING),
    ],
)
def test_invalid_transitions_are_rejected(current: MCPConnectionStatus, target: MCPConnectionStatus) -> None:
    assert can_transition(current, target) is False


@pytest.mark.parametrize("status", list(MCPConnectionStatus))
def test_no_status_can_transition_to_itself(status: MCPConnectionStatus) -> None:
    assert can_transition(status, status) is False
