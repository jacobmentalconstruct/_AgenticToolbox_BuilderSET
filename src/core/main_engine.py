"""Core engine orchestrator — headless processing.

Handles batch operations, automation pipelines, and background tasks
without a UI surface. Communicates with other orchestrators exclusively
through the AppStateRegistry.
"""

from __future__ import annotations


def launch(registry) -> int:
    raise NotImplementedError(
        "Core engine orchestrator not yet implemented. "
        "Build this when headless batch processing is needed."
    )
