from __future__ import annotations


def run_headless(runtime) -> dict:
    return {
        "app": "MindshardReferenceLibrary",
        "mode": "headless",
        "services": runtime.list_services(),
    }


def launch_ui(runtime) -> None:
    raise RuntimeError(
        "MindshardReferenceLibrary ships as a headless packaged tool in v1. Use app.py --no-ui or mcp_server.py."
    )
