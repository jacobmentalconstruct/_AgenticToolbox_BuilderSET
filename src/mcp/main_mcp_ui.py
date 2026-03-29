"""MCP orchestrator — Claude's console.

Exposes the same functions as the UI orchestrator but as MCP tools.
This is the symmetric counterpart to src/ui/main_gui.py.

Implementation will wrap:
  - catalog queries (list services, describe, dependencies)
  - stamp/restamp operations
  - sandbox pipeline (stamp, apply, validate, promote)
  - inspect and verify operations
"""

from __future__ import annotations


def launch(registry) -> int:
    raise NotImplementedError(
        "MCP orchestrator not yet implemented. "
        "This is the next phase after project restructuring."
    )
