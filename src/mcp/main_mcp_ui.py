"""MCP orchestrator — Claude's console.

Exposes the same functions as the UI orchestrator but as MCP tools.
This is the symmetric counterpart to src/ui/main_gui.py.

Launch with: python src/app.py mcp
Or directly: python src/mcp/server.py
"""

from __future__ import annotations


def launch(registry) -> int:
    registry.put("mcp.status", "starting")

    from src.mcp.server import mcp as mcp_server

    registry.put("mcp.status", "running")
    mcp_server.run()

    registry.put("mcp.status", "stopped")
    return 0
