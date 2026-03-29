"""AgenticToolboxBuilder entry point and app state registry.

This is the single entry point for all orchestrator domains:
  - ui:   Tkinter librarian / pipeline runner (user's console)
  - mcp:  MCP server (Claude's console)
  - core: Headless engine (batch / automation)

Cross-orchestrator communication flows through AppStateRegistry
as structured state packets — orchestrators never import each other.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class AppStateRegistry:
    """Singleton state registry for cross-orchestrator communication.

    Orchestrators publish and subscribe to keyed state packets here.
    They never call each other directly.
    """

    _instance: AppStateRegistry | None = None

    def __new__(cls) -> AppStateRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._state: dict = {}
            cls._instance._listeners: dict[str, list] = {}
        return cls._instance

    def put(self, key: str, value: object) -> None:
        self._state[key] = value
        for cb in self._listeners.get(key, []):
            cb(key, value)

    def get(self, key: str, default: object = None) -> object:
        return self._state.get(key, default)

    def subscribe(self, key: str, callback) -> None:
        self._listeners.setdefault(key, []).append(callback)


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="appfoundry",
        description="AgenticToolboxBuilder — one surface, two consoles",
    )
    parser.add_argument(
        "mode",
        choices=["ui", "mcp", "core", "catalog"],
        help="Launch mode: ui | mcp | core | catalog",
    )
    args = parser.parse_args()

    registry = AppStateRegistry()
    registry.put("project_root", str(PROJECT_ROOT))

    if args.mode == "catalog":
        from library.app_factory import CatalogBuilder

        report = CatalogBuilder().build()
        print(report)
        return 0

    if args.mode == "ui":
        from src.ui.main_gui import launch

        return launch(registry)

    if args.mode == "mcp":
        from src.mcp.main_mcp_ui import launch

        return launch(registry)

    if args.mode == "core":
        from src.core.main_engine import launch

        return launch(registry)

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
