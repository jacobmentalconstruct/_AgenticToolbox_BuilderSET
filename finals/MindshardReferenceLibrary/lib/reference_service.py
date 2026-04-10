from __future__ import annotations

from pathlib import Path
from typing import Any

from lib.reference_sessions import EvidenceShelfStore, SessionStore
from src.core.reference_library.service import ReferenceLibraryService


class MindshardReferenceLibraryService:
    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}
        self.core = ReferenceLibraryService(self.config)
        self.store = self.core.store

    def _evidence_store(self, project_path: str | None) -> EvidenceShelfStore:
        if project_path:
            db_path = (
                Path(project_path).expanduser().resolve()
                / ".mindshard"
                / "evidence"
                / "evidence.sqlite3"
            )
        else:
            db_path = self.store.records_dir / "evidence" / "evidence.sqlite3"
        return EvidenceShelfStore(db_path)

    def get_health(self) -> dict[str, Any]:
        return self.core.health()

    def library_manifest(self) -> dict[str, Any]:
        return self.store.package_manifest()

    def library_import(
        self,
        source_path: str,
        title: str | None = None,
        parent_node_id: str | None = None,
        project_path: str | None = None,
        attach: bool = False,
        attachment_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.core.import_path(
            source_path=source_path,
            title=title,
            parent_node_id=parent_node_id,
            project_path=project_path,
            attach=attach,
            attachment_context=attachment_context,
        )

    def library_refresh(self, node_id: str) -> dict[str, Any]:
        return self.core.refresh_document(node_id)

    def library_archive(self, node_id: str) -> dict[str, Any]:
        return self.core.archive_node(node_id)

    def library_rename(self, node_id: str, new_title: str) -> dict[str, Any]:
        return self.core.rename_node(node_id, new_title)

    def library_move(self, node_id: str, new_parent_id: str | None = None) -> dict[str, Any]:
        return self.core.move_node(node_id, new_parent_id)

    def library_attach(
        self,
        node_id: str,
        project_path: str,
        attachment_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.core.attach_node(node_id, project_path, attachment_context)

    def library_detach(self, node_id: str, project_path: str) -> dict[str, Any]:
        return self.core.detach_node(node_id, project_path)

    def library_list_roots(
        self,
        scope: str = "attached",
        project_path: str | None = None,
        include_archived: bool = False,
    ) -> dict[str, Any]:
        return self.core.list_roots(
            scope=scope,
            include_archived=include_archived,
            project_path=project_path,
        )

    def library_list_children(
        self,
        node_id: str,
        scope: str = "attached",
        project_path: str | None = None,
        include_archived: bool = False,
    ) -> dict[str, Any]:
        return self.core.list_children(
            node_id=node_id,
            scope=scope,
            include_archived=include_archived,
            project_path=project_path,
        )

    def library_search(
        self,
        query: str,
        scope: str = "attached",
        project_path: str | None = None,
        attached_root_ids: list[str] | None = None,
        limit: int = 10,
        include_archived: bool = False,
    ) -> dict[str, Any]:
        return self.core.search(
            query=query,
            scope=scope,
            project_path=project_path,
            attached_root_ids=attached_root_ids,
            limit=limit,
            include_archived=include_archived,
        )

    def library_get_detail(
        self,
        node_id: str,
        revision_id: str | None = None,
        scope: str = "attached",
        project_path: str | None = None,
    ) -> dict[str, Any]:
        return self.core.get_detail(
            node_id=node_id,
            revision_id=revision_id,
            scope=scope,
            project_path=project_path,
        )

    def library_list_revisions(
        self,
        node_id: str,
        scope: str = "attached",
        project_path: str | None = None,
    ) -> dict[str, Any]:
        return self.core.list_revisions(
            node_id=node_id,
            scope=scope,
            project_path=project_path,
        )

    def library_read_excerpt(
        self,
        node_id: str,
        revision_id: str,
        section_id: str | None = None,
        anchor_path: str | None = None,
        char_start: int | None = None,
        char_end: int | None = None,
        scope: str = "attached",
        project_path: str | None = None,
        session_db_path: str | None = None,
        session_id: str | None = None,
        attachment_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        session_store = SessionStore(session_db_path) if session_db_path else None
        evidence_store = self._evidence_store(project_path)
        return self.core.read_excerpt(
            node_id=node_id,
            revision_id=revision_id,
            section_id=section_id,
            anchor_path=anchor_path,
            char_start=char_start,
            char_end=char_end,
            scope=scope,
            project_path=project_path,
            session_store=session_store,
            session_id=session_id,
            evidence_store=evidence_store,
            attachment_context=attachment_context,
        )

    def library_export(self, node_id: str, destination_dir: str | None = None) -> dict[str, Any]:
        return self.core.export_node(node_id=node_id, destination_dir=destination_dir)
