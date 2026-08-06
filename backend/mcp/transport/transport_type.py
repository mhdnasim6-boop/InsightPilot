"""Transport kinds an MCP server can be reached through.

A closed vocabulary only — no networking, subprocess, or socket code
exists anywhere in this package. Actually speaking any of these
protocols is a future phase's job, once a real ``MCPClient`` implements
``connect()`` for one of them.
"""

from enum import Enum


class MCPTransportType(str, Enum):
    """Every transport kind InsightPilot's MCP layer recognizes."""

    STDIO = "stdio"
    HTTP = "http"
    WEBSOCKET = "websocket"
