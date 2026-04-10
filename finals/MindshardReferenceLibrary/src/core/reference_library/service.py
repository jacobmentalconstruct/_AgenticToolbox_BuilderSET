from __future__ import annotations

from pathlib import Path
from typing import Any

from src.core.reference_library.attachments import AttachmentStore
from src.core.reference_library.store import ReferenceLibraryStore


class ReferenceLibraryService:
    """Native facade over the immutable global reference library store."""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config
        self.store = ReferenceLibraryStore(
            app_dir=Path(__file__).resolve().parents[3],
            root_dir=self._root_dir_from_config(config),
            chunk_max_chars=self._chunk_max_chars(),
            chunk_overlap_chars=self._chunk_overlap_chars(),
        )

    def _root_dir_from_config(self, config: Any | None) -> str | None:
        if config is None:
            return None
        if isinstance(config, dict):
            return str(config.get("reference_library_root") or config.get("root_dir") or "").strip() or None
        return str(getattr(config, "reference_library_root", "") or "").strip() or None

    def _chunk_max_chars(self) -> int:
        if isinstance(self.config, dict):
            return int(self.config.get("reference_library_chunk_max_chars", 1200))
        return int(getattr(self.config, "reference_library_chunk_max_chars", 1200))

    def _chunk_overlap_chars(self) -> int:
        if isinstance(self.config, dict):
            return int(self.config.get("reference_library_chunk_overlap_chars", 120))
        return int(getattr(self.config, "reference_library_chunk_overlap_chars", 120))

    def _project_attachment(self, node_id: str, project_path: str | None) -> dict[str, Any]:
        if not project_path:
            return {"attached": False, "project_path": "", "attachment_context": {}}
        store = AttachmentStore(project_path)
        return {
            "attached": store.is_attached(node_id),
            "project_path": str(Path(project_path).expanduser().resolve()),
            "attachment_context": store.get_attachment_context(node_id),
        }

    def _normalized_scope(self, scope: str | None) -> str:
        value = str(scope or "attached").strip().lower()
        return value if value in {"attached", "global"} else "attached"

    def _scope_allowed_ids(self, scope: str | None, project_path: str | None) -> set[str] | None:
        normalized_scope = self._normalized_scope(scope)
        if normalized_scope == "global":
            return None
        if not project_path:
            return set()
        roots = AttachmentStore(project_path).list_root_ids()
        if not roots:
            return set()
        conn = self.store._connect()
        try:
            return self.store._collect_subtree_ids(conn, roots)
        finally:
            conn.close()

    def _assert_scope_access(self, node_id: str, scope: str | None, project_path: str | None) -> set[str] | None:
        allowed_ids = self._scope_allowed_ids(scope, project_path)
        if allowed_ids is not None and node_id not in allowed_ids:
            raise PermissionError(f"Node {node_id} is not attached to the active workspace.")
        return allowed_ids

    def _node_card(self, node: dict[str, Any], *, project_path: str | None = None) -> dict[str, Any]:
        detail = self.store.get_detail(node["node_id"])
        child_count = len(detail.get("children", []))
        sections = detail.get("sections", [])
        short_summary = ""
        if sections:
            short_summary = str(sections[0].get("summary") or "").strip()
        if not short_summary:
            metadata = dict(node.get("metadata", {}) or {})
            short_summary = str(metadata.get("short_summary") or metadata.get("import_kind") or "").strip()
        if not short_summary:
            short_summary = f"{node['node_kind']} at {node['logical_path']}"
        return {
            "node_id": node["node_id"],
            "node_kind": node["node_kind"],
            "title": node["title"],
            "short_summary": short_summary,
            "child_count": child_count,
            "latest_revision_id": node.get("latest_revision_id"),
            "archived": bool(node.get("archived")),
            "attachment": self._project_attachment(node["node_id"], project_path),
        }

    def health(self) -> dict[str, Any]:
        return self.store.health()

    def import_path(
        self,
        source_path: str,
        *,
        title: str | None = None,
        parent_node_id: str | None = None,
        project_path: str | None = None,
        attach: bool = False,
        attachment_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.store.import_path(
            source_path=source_path,
            title=title,
            parent_node_id=parent_node_id,
            project_path=project_path,
            attach=attach,
            attachment_context=attachment_context,
        )

    def create_group(self, title: str, *, parent_node_id: str | None = None) -> dict[str, Any]:
        return self.store.create_group(title=title, parent_node_id=parent_node_id)

    def refresh_document(self, node_id: str) -> dict[str, Any]:
        return self.store.refresh_document(node_id)

    def archive_node(self, node_id: str) -> dict[str, Any]:
        return self.store.archive_node(node_id)

    def rename_node(self, node_id: str, new_title: str) -> dict[str, Any]:
        return self.store.rename_node(node_id, new_title)

    def move_node(self, node_id: str, new_parent_id: str | None = None) -> dict[str, Any]:
        return self.store.move_node(node_id, new_parent_id)

    def attach_node(
        self,
        node_id: str,
        project_path: str,
        attachment_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.store.attach_node(node_id, project_path, attachment_context)

    def detach_node(self, node_id: str, project_path: str) -> dict[str, Any]:
        return self.store.detach_node(node_id, project_path)

    def export_node(self, node_id: str, destination_dir: str | None = None) -> dict[str, Any]:
        return self.store.export_node(node_id=node_id, destination_dir=destination_dir)

    def list_roots(
        self,
        *,
        scope: str = "attached",
        include_archived: bool = False,
        project_path: str | None = None,
    ) -> dict[str, Any]:
        normalized_scope = self._normalized_scope(scope)
        allowed_ids = self._scope_allowed_ids(normalized_scope, project_path)
        payload = self.store.list_roots(include_archived=include_archived)
        roots = list(payload.get("roots", []))
        if allowed_ids is not None:
            roots = [node for node in roots if node["node_id"] in allowed_ids]
        children = [self._node_card(node, project_path=project_path) for node in roots]
        return {
            "parent": {
                "node_id": "",
                "node_kind": "group",
                "title": "Reference Library",
                "short_summary": (
                    "Attached reference roots for the active workspace."
                    if normalized_scope == "attached"
                    else "Global immutable reference roots."
                ),
                "child_count": len(children),
                "latest_revision_id": None,
                "archived": False,
            },
            "children": children,
        }

    def list_children(
        self,
        node_id: str,
        *,
        scope: str = "attached",
        include_archived: bool = False,
        project_path: str | None = None,
    ) -> dict[str, Any]:
        allowed_ids = self._assert_scope_access(node_id, scope, project_path)
        payload = self.store.list_children(node_id=node_id, include_archived=include_archived)
        parent = self._node_card(payload["node"], project_path=project_path)
        raw_children = list(payload.get("children", []))
        if allowed_ids is not None:
            raw_children = [node for node in raw_children if node["node_id"] in allowed_ids]
        children = [self._node_card(node, project_path=project_path) for node in raw_children]
        return {"parent": parent, "children": children}

    def search(
        self,
        query: str,
        *,
        scope: str = "attached",
        project_path: str | None = None,
        attached_root_ids: list[str] | None = None,
        limit: int = 10,
        include_archived: bool = False,
    ) -> dict[str, Any]:
        normalized_scope = self._normalized_scope(scope)
        payload = self.store.search(
            query=query,
            scope=normalized_scope,
            project_path=project_path,
            attached_root_ids=attached_root_ids,
            limit=limit,
            include_archived=include_archived,
        )
        results: list[dict[str, Any]] = []
        raw_results = payload.get("results", [])
        total = max(len(raw_results), 1)
        for index, row in enumerate(raw_results):
            results.append(
                {
                    "node_id": row["node_id"],
                    "revision_id": row["revision_id"],
                    "section_id": row["section_id"],
                    "title": row["title"],
                    "summary": row.get("summary") or row.get("preview") or "",
                    "anchor_path": row["anchor_path"],
                    "logical_path": row["logical_path"],
                    "rank_score": round((total - index) / total, 4),
                    "scope": payload.get("scope", normalized_scope),
                }
            )
        return {"query": query, "scope": payload.get("scope", normalized_scope), "results": results}

    def get_detail(
        self,
        node_id: str,
        *,
        revision_id: str | None = None,
        scope: str = "attached",
        project_path: str | None = None,
    ) -> dict[str, Any]:
        self._assert_scope_access(node_id, scope, project_path)
        detail = self.store.get_detail(node_id=node_id, revision_id=revision_id)
        revision_bundle = self.store.list_revisions(node_id=node_id)
        revisions = list(revision_bundle.get("revisions", []))
        latest_revision = None
        latest_revision_id = detail["node"].get("latest_revision_id")
        for revision in revisions:
            if revision.get("revision_id") == latest_revision_id:
                latest_revision = revision
                break
        return {
            "node": detail["node"],
            "selected_revision": detail.get("revision"),
            "latest_revision": latest_revision,
            "attachment": self._project_attachment(node_id, project_path),
            "revision_count": len(revisions),
            "children": [self._node_card(node, project_path=project_path) for node in detail.get("children", [])],
            "latest_revision_selected": bool(detail.get("latest_revision_selected")),
        }

    def list_revisions(
        self,
        node_id: str,
        *,
        scope: str = "attached",
        project_path: str | None = None,
    ) -> dict[str, Any]:
        self._assert_scope_access(node_id, scope, project_path)
        bundle = self.store.list_revisions(node_id=node_id)
        return {
            "node": bundle["node"],
            "attachment": self._project_attachment(node_id, project_path),
            "revisions": bundle.get("revisions", []),
            "revision_count": len(bundle.get("revisions", [])),
        }

    def read_excerpt(
        self,
        node_id: str,
        revision_id: str,
        *,
        section_id: str | None = None,
        anchor_path: str | None = None,
        char_start: int | None = None,
        char_end: int | None = None,
        scope: str = "attached",
        project_path: str | None = None,
        session_store=None,
        session_id: str | None = None,
        evidence_store=None,
        attachment_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._assert_scope_access(node_id, scope, project_path)
        payload = self.store.read_excerpt(
            node_id=node_id,
            revision_id=revision_id,
            section_id=section_id,
            anchor_path=anchor_path,
            char_start=char_start,
            char_end=char_end,
            project_path=project_path,
            session_store=session_store,
            session_id=session_id,
            evidence_store=evidence_store,
            attachment_context=attachment_context,
        )
        return {
            "operation_id": payload["operation_id"],
            "node_id": payload["node_id"],
            "revision_id": payload["revision_id"],
            "section_id": payload["section_id"],
            "anchor_path": payload["anchor_path"],
            "excerpt_text": payload["excerpt_text"],
            "summary_text": payload["summary_text"],
            "provenance": payload["provenance"],
            "usage_recorded": payload["usage_recorded"],
            "cache_recorded": payload["cache_recorded"],
            "evidence_mirrored": payload["evidence_mirrored"],
        }
