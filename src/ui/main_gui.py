"""UI orchestrator — user's console.

Wraps the existing LibrarianApp and pipeline runner UI surfaces.
Receives the shared AppStateRegistry from src/app.py.
"""

from __future__ import annotations


def launch(registry) -> int:
    from library.app_factory import CatalogBuilder, LibrarianApp, LibraryQueryService

    registry.put("ui.status", "starting")

    CatalogBuilder().build()
    query_service = LibraryQueryService()

    registry.put("ui.status", "running")
    LibrarianApp(query_service).run()

    registry.put("ui.status", "stopped")
    return 0
