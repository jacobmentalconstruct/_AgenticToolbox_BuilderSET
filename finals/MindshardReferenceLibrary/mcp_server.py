from __future__ import annotations

import json
import os
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
SETTINGS = json.loads((APP_DIR / "settings.json").read_text(encoding="utf-8"))
for candidate in [SETTINGS.get("canonical_import_root", "")] + list(SETTINGS.get("compat_paths", [])):
    if not candidate:
        continue
    resolved = str(APP_DIR / candidate) if not os.path.isabs(candidate) else candidate
    if resolved not in sys.path:
        sys.path.insert(0, resolved)

from fastmcp import FastMCP

from backend import BackendRuntime, SERVICE_SPECS

mcp = FastMCP("MindshardReferenceLibrary")
runtime = BackendRuntime()


def _fmt(obj: object) -> str:
    return json.dumps(obj, indent=2, default=str)


def _loads(value, default):
    if value in (None, "", []):
        return default
    if isinstance(value, str):
        return json.loads(value)
    return value


@mcp.tool
def list_services() -> str:
    return _fmt(SERVICE_SPECS)


@mcp.tool
def app_health() -> str:
    return _fmt(runtime.get_service("MindshardReferenceLibrary").get_health())


@mcp.tool
def library_manifest() -> str:
    return _fmt(runtime.call("MindshardReferenceLibrary", "library_manifest"))


@mcp.tool
def library_import(
    source_path: str,
    title: str = "",
    parent_node_id: str = "",
    project_path: str = "",
    attach: bool = False,
    attachment_context: str = "{}",
) -> str:
    return _fmt(
        runtime.call(
            "MindshardReferenceLibrary",
            "library_import",
            source_path=source_path,
            title=title or None,
            parent_node_id=parent_node_id or None,
            project_path=project_path or None,
            attach=attach,
            attachment_context=_loads(attachment_context, {}),
        )
    )


@mcp.tool
def library_refresh(node_id: str) -> str:
    return _fmt(runtime.call("MindshardReferenceLibrary", "library_refresh", node_id=node_id))


@mcp.tool
def library_archive(node_id: str) -> str:
    return _fmt(runtime.call("MindshardReferenceLibrary", "library_archive", node_id=node_id))


@mcp.tool
def library_rename(node_id: str, new_title: str) -> str:
    return _fmt(
        runtime.call(
            "MindshardReferenceLibrary",
            "library_rename",
            node_id=node_id,
            new_title=new_title,
        )
    )


@mcp.tool
def library_move(node_id: str, new_parent_id: str = "") -> str:
    return _fmt(
        runtime.call(
            "MindshardReferenceLibrary",
            "library_move",
            node_id=node_id,
            new_parent_id=new_parent_id or None,
        )
    )


@mcp.tool
def library_attach(node_id: str, project_path: str, attachment_context: str = "{}") -> str:
    return _fmt(
        runtime.call(
            "MindshardReferenceLibrary",
            "library_attach",
            node_id=node_id,
            project_path=project_path,
            attachment_context=_loads(attachment_context, {}),
        )
    )


@mcp.tool
def library_detach(node_id: str, project_path: str) -> str:
    return _fmt(
        runtime.call(
            "MindshardReferenceLibrary",
            "library_detach",
            node_id=node_id,
            project_path=project_path,
        )
    )


@mcp.tool
def library_list_roots(
    scope: str = "attached",
    project_path: str = "",
    include_archived: bool = False,
) -> str:
    return _fmt(
        runtime.call(
            "MindshardReferenceLibrary",
            "library_list_roots",
            scope=scope,
            project_path=project_path or None,
            include_archived=include_archived,
        )
    )


@mcp.tool
def library_list_children(
    node_id: str,
    scope: str = "attached",
    project_path: str = "",
    include_archived: bool = False,
) -> str:
    return _fmt(
        runtime.call(
            "MindshardReferenceLibrary",
            "library_list_children",
            node_id=node_id,
            scope=scope,
            project_path=project_path or None,
            include_archived=include_archived,
        )
    )


@mcp.tool
def library_search(
    query: str,
    scope: str = "attached",
    project_path: str = "",
    attached_root_ids: str = "[]",
    limit: int = 10,
    include_archived: bool = False,
) -> str:
    return _fmt(
        runtime.call(
            "MindshardReferenceLibrary",
            "library_search",
            query=query,
            scope=scope,
            project_path=project_path or None,
            attached_root_ids=_loads(attached_root_ids, []),
            limit=limit,
            include_archived=include_archived,
        )
    )


@mcp.tool
def library_get_detail(
    node_id: str,
    revision_id: str = "",
    scope: str = "attached",
    project_path: str = "",
) -> str:
    return _fmt(
        runtime.call(
            "MindshardReferenceLibrary",
            "library_get_detail",
            node_id=node_id,
            revision_id=revision_id or None,
            scope=scope,
            project_path=project_path or None,
        )
    )


@mcp.tool
def library_list_revisions(
    node_id: str,
    scope: str = "attached",
    project_path: str = "",
) -> str:
    return _fmt(
        runtime.call(
            "MindshardReferenceLibrary",
            "library_list_revisions",
            node_id=node_id,
            scope=scope,
            project_path=project_path or None,
        )
    )


@mcp.tool
def library_read_excerpt(
    node_id: str,
    revision_id: str,
    section_id: str = "",
    anchor_path: str = "",
    char_start: int = -1,
    char_end: int = -1,
    scope: str = "attached",
    project_path: str = "",
    session_db_path: str = "",
    session_id: str = "",
    attachment_context: str = "{}",
) -> str:
    return _fmt(
        runtime.call(
            "MindshardReferenceLibrary",
            "library_read_excerpt",
            node_id=node_id,
            revision_id=revision_id,
            section_id=section_id or None,
            anchor_path=anchor_path or None,
            char_start=None if char_start < 0 else char_start,
            char_end=None if char_end < 0 else char_end,
            scope=scope,
            project_path=project_path or None,
            session_db_path=session_db_path or None,
            session_id=session_id or None,
            attachment_context=_loads(attachment_context, {}),
        )
    )


@mcp.tool
def library_export(node_id: str, destination_dir: str = "") -> str:
    return _fmt(
        runtime.call(
            "MindshardReferenceLibrary",
            "library_export",
            node_id=node_id,
            destination_dir=destination_dir or None,
        )
    )


if __name__ == "__main__":
    mcp.run()
