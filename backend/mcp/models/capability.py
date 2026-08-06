"""Capabilities an MCP server can advertise."""

from enum import Enum


class MCPCapability(str, Enum):
    """Every capability kind InsightPilot's MCP layer recognizes.

    A closed vocabulary for *describing* a server, not a list of servers
    that exist — none of these have an implementation behind them yet.
    ``CUSTOM`` covers a capability that doesn't fit the other five, so a
    server never has to misrepresent itself to register.
    """

    FILESYSTEM = "filesystem"
    PYTHON = "python"
    BROWSER = "browser"
    SQL = "sql"
    GIT = "git"
    CUSTOM = "custom"
