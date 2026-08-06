"""Reusable MCP (Model Context Protocol) infrastructure.

Lets a future MCP server (filesystem, SQL, browser, git, Python, or
anything else) register itself and be discovered, without any existing
service changing. ``MCPService`` is the only entry point. No real MCP
server, transport, or communication is implemented here — this package
is the plug, not anything plugged into it.
"""
