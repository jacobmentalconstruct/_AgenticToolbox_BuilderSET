from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from src.core.reference_library.attachments import AttachmentStore
from src.core.reference_library.providers import ProviderRegistry, ProviderRequest
from src.core.reference_library.storage_primitives import Blake3HashMS, TemporalChainMS
from src.core.reference_library.utils import (
    canonical_json,
    child_logical_path,
    decode_text,
    detect_media_type,
    ensure_directory,
    looks_like_text,
    new_id,
    normalize_text,
    slugify,
    summarize_text,
    trim_excerpt,
    utc_now,
)


class ReferenceLibraryStore:
    schema_version = "1.0"
    package_name = "MindshardReferenceLibrary"
    package_version = "1.0.0"

    def __init__(
        self,
        app_dir: str | Path | None = None,
        root_dir: str | Path | None = None,
        chunk_max_chars: int = 1200,
        chunk_overlap_chars: int = 120,
    ) -> None:
        self.app_dir = Path(app_dir or Path(__file__).resolve().parents[1]).resolve()
        default_root = os.environ.get(
            "MINDSHARD_REFERENCE_LIBRARY_ROOT",
            str(Path.home() / ".mindshard_reference_library"),
        )
        self.root_dir = Path(root_dir or default_root).expanduser().resolve()
        self.library_manifest_path = self.root_dir / "library_manifest.json"
        self.providers_manifest_path = self.root_dir / "providers_manifest.json"
        self.db_path = self.root_dir / "library_index.sqlite3"
        self.operations_log_path = self.root_dir / "operations.jsonl"
        self.content_dir = self.root_dir / "content"
        self.records_dir = self.root_dir / "records"
        self.exports_dir = self.root_dir / "exports"
        self.nodes_dir = self.records_dir / "nodes"
        self.revisions_dir = self.records_dir / "revisions"
        self.temporal_db_path = self.records_dir / "temporal_chain.sqlite3"
        self.chunk_max_chars = max(200, int(chunk_max_chars))
        self.chunk_overlap_chars = max(0, int(chunk_overlap_chars))
        self.hasher = Blake3HashMS()
        self.temporal = TemporalChainMS()
        self.providers = ProviderRegistry(manifest_path=self.providers_manifest_path)
        self._bootstrap()

    def _bootstrap(self) -> None:
        for path in (
            self.root_dir,
            self.content_dir,
            self.records_dir,
            self.exports_dir,
            self.nodes_dir,
            self.revisions_dir,
            self.content_dir / "text",
            self.content_dir / "blobs",
        ):
            ensure_directory(path)
        self.providers.validate()
        conn = self._connect()
        try:
            self._init_schema(conn)
            conn.commit()
        finally:
            conn.close()
        self._write_library_manifest()
        self._write_providers_manifest()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS nodes (
                node_id TEXT PRIMARY KEY,
                parent_node_id TEXT,
                node_kind TEXT NOT NULL,
                title TEXT NOT NULL,
                logical_path TEXT NOT NULL,
                source_path TEXT,
                media_type TEXT,
                extension TEXT,
                archived INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                latest_revision_id TEXT,
                latest_revision_hash TEXT,
                metadata_json TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS revisions (
                revision_id TEXT PRIMARY KEY,
                node_id TEXT NOT NULL,
                revision_number INTEGER NOT NULL,
                content_hash TEXT NOT NULL,
                raw_hash TEXT NOT NULL,
                payload_kind TEXT NOT NULL,
                payload_relpath TEXT NOT NULL,
                logical_path TEXT NOT NULL,
                source_title TEXT NOT NULL,
                media_type TEXT,
                extension TEXT,
                imported_at TEXT NOT NULL,
                provider_id TEXT,
                provider_kind TEXT,
                provider_version TEXT,
                strategy_used TEXT,
                merkle_root TEXT,
                section_count INTEGER NOT NULL DEFAULT 0,
                metadata_json TEXT NOT NULL,
                UNIQUE(node_id, revision_number)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sections (
                section_id TEXT PRIMARY KEY,
                revision_id TEXT NOT NULL,
                node_id TEXT NOT NULL,
                parent_section_id TEXT,
                ordinal INTEGER NOT NULL,
                depth INTEGER NOT NULL,
                section_kind TEXT NOT NULL,
                anchor_path TEXT NOT NULL,
                title TEXT,
                summary TEXT,
                exact_text TEXT NOT NULL,
                char_start INTEGER NOT NULL,
                char_end INTEGER NOT NULL,
                source_span_json TEXT NOT NULL,
                section_hash TEXT NOT NULL,
                metadata_json TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS operations (
                operation_id TEXT PRIMARY KEY,
                operation_kind TEXT NOT NULL,
                node_id TEXT,
                revision_id TEXT,
                created_at TEXT NOT NULL,
                details_json TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_nodes_parent ON nodes(parent_node_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_nodes_archived ON nodes(archived)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_revisions_node ON revisions(node_id, revision_number DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sections_revision ON sections(revision_id, ordinal)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sections_node ON sections(node_id)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        try:
            conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS section_fts
                USING fts5(
                    section_id UNINDEXED,
                    node_id UNINDEXED,
                    revision_id UNINDEXED,
                    title,
                    summary,
                    exact_text
                )
                """
            )
            conn.execute(
                "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
                ("fts_enabled", "1"),
            )
        except sqlite3.OperationalError:
            conn.execute(
                "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
                ("fts_enabled", "0"),
            )

    def _fts_enabled(self, conn: sqlite3.Connection) -> bool:
        row = conn.execute("SELECT value FROM meta WHERE key = 'fts_enabled'").fetchone()
        return bool(row and row["value"] == "1")

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        ensure_directory(path.parent)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def _manifest_created_at(self) -> str:
        if self.library_manifest_path.exists():
            existing = json.loads(self.library_manifest_path.read_text(encoding="utf-8"))
            return existing.get("created_at", utc_now())
        return utc_now()

    def _write_library_manifest(self) -> None:
        payload = {
            "schema_version": self.schema_version,
            "package_name": self.package_name,
            "package_version": self.package_version,
            "library_root": str(self.root_dir),
            "created_at": self._manifest_created_at(),
            "updated_at": utc_now(),
            "paths": {
                "library_manifest": str(self.library_manifest_path),
                "providers_manifest": str(self.providers_manifest_path),
                "library_index": str(self.db_path),
                "operations_log": str(self.operations_log_path),
                "content": str(self.content_dir),
                "records": str(self.records_dir),
                "exports": str(self.exports_dir),
            },
        }
        self._write_json(self.library_manifest_path, payload)

    def _write_providers_manifest(self) -> None:
        payload = {
            "schema_version": self.schema_version,
            "updated_at": utc_now(),
            "providers": self.providers.manifests(),
        }
        self._write_json(self.providers_manifest_path, payload)

    def _row_to_node(self, row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        return {
            "node_id": row["node_id"],
            "parent_node_id": row["parent_node_id"],
            "node_kind": row["node_kind"],
            "title": row["title"],
            "logical_path": row["logical_path"],
            "source_path": row["source_path"],
            "media_type": row["media_type"],
            "extension": row["extension"],
            "archived": bool(row["archived"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "latest_revision_id": row["latest_revision_id"],
            "latest_revision_hash": row["latest_revision_hash"],
            "metadata": json.loads(row["metadata_json"] or "{}"),
        }

    def _row_to_revision(self, row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        return {
            "revision_id": row["revision_id"],
            "node_id": row["node_id"],
            "revision_number": row["revision_number"],
            "content_hash": row["content_hash"],
            "raw_hash": row["raw_hash"],
            "payload_kind": row["payload_kind"],
            "payload_relpath": row["payload_relpath"],
            "logical_path": row["logical_path"],
            "source_title": row["source_title"],
            "media_type": row["media_type"],
            "extension": row["extension"],
            "imported_at": row["imported_at"],
            "provider_id": row["provider_id"],
            "provider_kind": row["provider_kind"],
            "provider_version": row["provider_version"],
            "strategy_used": row["strategy_used"],
            "merkle_root": row["merkle_root"],
            "section_count": row["section_count"],
            "metadata": json.loads(row["metadata_json"] or "{}"),
        }

    def _row_to_section(self, row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        return {
            "section_id": row["section_id"],
            "revision_id": row["revision_id"],
            "node_id": row["node_id"],
            "parent_section_id": row["parent_section_id"],
            "ordinal": row["ordinal"],
            "depth": row["depth"],
            "section_kind": row["section_kind"],
            "anchor_path": row["anchor_path"],
            "title": row["title"],
            "summary": row["summary"],
            "exact_text": row["exact_text"],
            "char_start": row["char_start"],
            "char_end": row["char_end"],
            "source_span": json.loads(row["source_span_json"] or "{}"),
            "section_hash": row["section_hash"],
            "metadata": json.loads(row["metadata_json"] or "{}"),
        }

    def _store_payload(self, payload: bytes, bucket: str, suffix: str) -> tuple[str, str]:
        content_hash = self.hasher.hash_bytes(payload)
        extension = suffix if suffix.startswith(".") else f".{suffix}" if suffix else ""
        target = self.content_dir / bucket / content_hash[:2] / f"{content_hash}{extension}"
        ensure_directory(target.parent)
        if not target.exists():
            target.write_bytes(payload)
        return content_hash, str(target.relative_to(self.root_dir))

    def _log_operation(
        self,
        operation_kind: str,
        node_id: str | None = None,
        revision_id: str | None = None,
        details: dict[str, Any] | None = None,
        operation_id: str | None = None,
    ) -> str:
        op_id = operation_id or new_id("op")
        record = {
            "operation_id": op_id,
            "operation_kind": operation_kind,
            "node_id": node_id,
            "revision_id": revision_id,
            "created_at": utc_now(),
            "details": details or {},
        }
        conn = self._connect()
        inserted = False
        try:
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO operations (
                    operation_id, operation_kind, node_id, revision_id, created_at, details_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    record["operation_id"],
                    record["operation_kind"],
                    record["node_id"],
                    record["revision_id"],
                    record["created_at"],
                    canonical_json(record["details"]),
                ),
            )
            conn.commit()
            inserted = cursor.rowcount > 0
        finally:
            conn.close()

        if inserted:
            with self.operations_log_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, sort_keys=True) + "\n")
        return op_id

    def _create_node(
        self,
        conn: sqlite3.Connection,
        node_kind: str,
        title: str,
        logical_path: str,
        source_path: str,
        parent_node_id: str | None,
        media_type: str,
        extension: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        node_id = new_id("node")
        now = utc_now()
        conn.execute(
            """
            INSERT INTO nodes (
                node_id, parent_node_id, node_kind, title, logical_path, source_path,
                media_type, extension, archived, created_at, updated_at,
                latest_revision_id, latest_revision_hash, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, NULL, NULL, ?)
            """,
            (
                node_id,
                parent_node_id,
                node_kind,
                title,
                logical_path,
                source_path,
                media_type,
                extension,
                now,
                now,
                canonical_json(metadata),
            ),
        )
        row = conn.execute("SELECT * FROM nodes WHERE node_id = ?", (node_id,)).fetchone()
        node = self._row_to_node(row)
        assert node is not None
        self._write_json(self.nodes_dir / f"{node_id}.json", node)
        return node

    def _next_revision_number(self, conn: sqlite3.Connection, node_id: str) -> int:
        row = conn.execute(
            "SELECT COALESCE(MAX(revision_number), 0) AS max_number FROM revisions WHERE node_id = ?",
            (node_id,),
        ).fetchone()
        return int(row["max_number"]) + 1

    def _persist_revision(
        self,
        conn: sqlite3.Connection,
        node: dict[str, Any],
        revision_payload: dict[str, Any],
        sections: list[dict[str, Any]],
    ) -> dict[str, Any]:
        conn.execute(
            """
            INSERT INTO revisions (
                revision_id, node_id, revision_number, content_hash, raw_hash, payload_kind,
                payload_relpath, logical_path, source_title, media_type, extension, imported_at,
                provider_id, provider_kind, provider_version, strategy_used, merkle_root,
                section_count, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                revision_payload["revision_id"],
                revision_payload["node_id"],
                revision_payload["revision_number"],
                revision_payload["content_hash"],
                revision_payload["raw_hash"],
                revision_payload["payload_kind"],
                revision_payload["payload_relpath"],
                revision_payload["logical_path"],
                revision_payload["source_title"],
                revision_payload["media_type"],
                revision_payload["extension"],
                revision_payload["imported_at"],
                revision_payload["provider_id"],
                revision_payload["provider_kind"],
                revision_payload["provider_version"],
                revision_payload["strategy_used"],
                revision_payload["merkle_root"],
                revision_payload["section_count"],
                canonical_json(revision_payload["metadata"]),
            ),
        )
        for section in sections:
            conn.execute(
                """
                INSERT INTO sections (
                    section_id, revision_id, node_id, parent_section_id, ordinal, depth,
                    section_kind, anchor_path, title, summary, exact_text, char_start,
                    char_end, source_span_json, section_hash, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    section["section_id"],
                    revision_payload["revision_id"],
                    node["node_id"],
                    section["parent_section_id"],
                    section["ordinal"],
                    section["depth"],
                    section["section_kind"],
                    section["anchor_path"],
                    section["title"],
                    section["summary"],
                    section["exact_text"],
                    section["char_start"],
                    section["char_end"],
                    canonical_json(section["source_span"]),
                    section["section_hash"],
                    canonical_json(section["metadata"]),
                ),
            )
            if self._fts_enabled(conn):
                conn.execute(
                    """
                    INSERT INTO section_fts (
                        section_id, node_id, revision_id, title, summary, exact_text
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        section["section_id"],
                        node["node_id"],
                        revision_payload["revision_id"],
                        section["title"],
                        section["summary"],
                        section["exact_text"],
                    ),
                )
        conn.execute(
            """
            UPDATE nodes
            SET latest_revision_id = ?, latest_revision_hash = ?, updated_at = ?, media_type = ?, extension = ?
            WHERE node_id = ?
            """,
            (
                revision_payload["revision_id"],
                revision_payload["content_hash"],
                utc_now(),
                revision_payload["media_type"],
                revision_payload["extension"],
                node["node_id"],
            ),
        )
        row = conn.execute(
            "SELECT * FROM revisions WHERE revision_id = ?", (revision_payload["revision_id"],)
        ).fetchone()
        revision = self._row_to_revision(row)
        assert revision is not None
        revision["sections"] = sections
        self._write_json(self.revisions_dir / f"{revision['revision_id']}.json", revision)
        fresh_node = self._row_to_node(
            conn.execute("SELECT * FROM nodes WHERE node_id = ?", (node["node_id"],)).fetchone()
        )
        assert fresh_node is not None
        self._write_json(self.nodes_dir / f"{fresh_node['node_id']}.json", fresh_node)
        return revision

    def list_roots(self, include_archived: bool = False) -> dict[str, Any]:
        conn = self._connect()
        try:
            sql = "SELECT * FROM nodes WHERE parent_node_id IS NULL"
            if not include_archived:
                sql += " AND archived = 0"
            sql += " ORDER BY title COLLATE NOCASE"
            rows = conn.execute(sql).fetchall()
            return {"roots": [self._row_to_node(row) for row in rows]}
        finally:
            conn.close()

    def list_children(self, node_id: str, include_archived: bool = False) -> dict[str, Any]:
        conn = self._connect()
        try:
            node = self._row_to_node(conn.execute("SELECT * FROM nodes WHERE node_id = ?", (node_id,)).fetchone())
            if node is None:
                raise KeyError(node_id)
            sql = "SELECT * FROM nodes WHERE parent_node_id = ?"
            params: list[Any] = [node_id]
            if not include_archived:
                sql += " AND archived = 0"
            sql += " ORDER BY title COLLATE NOCASE"
            rows = conn.execute(sql, params).fetchall()
            return {"node": node, "children": [self._row_to_node(row) for row in rows]}
        finally:
            conn.close()

    def import_path(
        self,
        source_path: str,
        title: str | None = None,
        parent_node_id: str | None = None,
        project_path: str | None = None,
        attach: bool = False,
        attachment_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        source = Path(source_path).expanduser().resolve()
        if not source.exists():
            raise FileNotFoundError(source)
        conn = self._connect()
        try:
            if parent_node_id:
                parent_row = conn.execute(
                    "SELECT * FROM nodes WHERE node_id = ?", (parent_node_id,)
                ).fetchone()
                if parent_row is None:
                    raise KeyError(parent_node_id)
                parent_logical = str(parent_row["logical_path"])
            else:
                parent_logical = ""

            if source.is_dir():
                imported = self._import_directory(
                    conn,
                    source=source,
                    parent_node_id=parent_node_id,
                    logical_path=child_logical_path(parent_logical, title or source.name),
                    title=title or source.name,
                )
            else:
                imported = self._import_file(
                    conn,
                    source=source,
                    parent_node_id=parent_node_id,
                    logical_path=child_logical_path(parent_logical, title or source.name),
                    title=title or source.name,
                )
            conn.commit()
        finally:
            conn.close()

        if attach and project_path:
            self.attach_node(imported["node_id"], project_path, attachment_context)
        detail = self.get_detail(imported["node_id"])
        self._log_operation(
            "library_import",
            node_id=imported["node_id"],
            revision_id=detail["revision"]["revision_id"] if detail["revision"] else None,
            details={
                "source_path": str(source),
                "attached": bool(attach and project_path),
                "project_path": project_path or "",
            },
        )
        return detail

    def _import_directory(
        self,
        conn: sqlite3.Connection,
        source: Path,
        parent_node_id: str | None,
        logical_path: str,
        title: str,
    ) -> dict[str, Any]:
        node = self._create_node(
            conn=conn,
            node_kind="group",
            title=title,
            logical_path=logical_path,
            source_path=str(source),
            parent_node_id=parent_node_id,
            media_type="inode/directory",
            extension="",
            metadata={"import_kind": "directory"},
        )
        for child in sorted(source.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower())):
            child_logical = child_logical_path(node["logical_path"], child.name)
            if child.is_dir():
                self._import_directory(
                    conn=conn,
                    source=child,
                    parent_node_id=node["node_id"],
                    logical_path=child_logical,
                    title=child.name,
                )
            else:
                self._import_file(
                    conn=conn,
                    source=child,
                    parent_node_id=node["node_id"],
                    logical_path=child_logical,
                    title=child.name,
                )
        return node

    def _import_file(
        self,
        conn: sqlite3.Connection,
        source: Path,
        parent_node_id: str | None,
        logical_path: str,
        title: str,
        existing_node_id: str | None = None,
    ) -> dict[str, Any]:
        raw_blob = source.read_bytes()
        raw_hash = self.hasher.hash_bytes(raw_blob)
        media_type = detect_media_type(source)
        extension = source.suffix.lower()
        readable = looks_like_text(raw_blob, media_type=media_type, extension=extension)
        imported_at = utc_now()
        sections: list[dict[str, Any]] = []
        provider_result = None

        if existing_node_id:
            row = conn.execute("SELECT * FROM nodes WHERE node_id = ?", (existing_node_id,)).fetchone()
            node = self._row_to_node(row)
            if node is None:
                raise KeyError(existing_node_id)
        else:
            node_kind = "document" if readable else "blob"
            node = self._create_node(
                conn=conn,
                node_kind=node_kind,
                title=title,
                logical_path=logical_path,
                source_path=str(source),
                parent_node_id=parent_node_id,
                media_type=media_type,
                extension=extension,
                metadata={"import_kind": "file", "byte_size": len(raw_blob)},
            )

        if readable:
            normalized_text = normalize_text(decode_text(raw_blob))
            content_hash, payload_relpath = self._store_payload(
                normalized_text.encode("utf-8"), "text", ".txt"
            )
            request = ProviderRequest(
                request_id=new_id("request"),
                strategy_hint="tree_splitter",
                logical_path=logical_path,
                media_type=media_type,
                extension=extension,
                content_hash=content_hash,
                text_path=str(self.root_dir / payload_relpath),
                blob_path=None,
                max_chars=self.chunk_max_chars,
                overlap_chars=self.chunk_overlap_chars,
                metadata={"source_path": str(source)},
            )
            provider = self.providers.select(request, readable_text=True)
            if provider is None:
                raise RuntimeError(f"No provider available for readable text: {source}")
            provider_result = provider.parse(request, normalized_text)
            for section in provider_result.sections:
                section_hash = self.hasher.hash_content(section.exact_text)
                sections.append(
                    {
                        "section_id": section.section_id,
                        "parent_section_id": section.parent_section_id,
                        "ordinal": section.ordinal,
                        "depth": section.depth,
                        "section_kind": section.section_kind,
                        "anchor_path": section.anchor_path,
                        "title": section.title,
                        "summary": section.summary,
                        "exact_text": section.exact_text,
                        "char_start": section.char_start,
                        "char_end": section.char_end,
                        "source_span": section.source_span,
                        "section_hash": section_hash,
                        "metadata": section.metadata,
                    }
                )
            leaf_hashes = [item["section_hash"] for item in sections] or [content_hash]
            payload_kind = "text"
        else:
            content_hash, payload_relpath = self._store_payload(raw_blob, "blobs", extension or ".bin")
            leaf_hashes = [content_hash]
            payload_kind = "blob"

        revision_id = new_id("revision")
        revision_number = self._next_revision_number(conn, node["node_id"])
        merkle_root = self.temporal.commit(
            db_path=str(self.temporal_db_path),
            leaves=leaf_hashes,
            label=revision_id,
        )["root"]

        revision_payload = {
            "revision_id": revision_id,
            "node_id": node["node_id"],
            "revision_number": revision_number,
            "content_hash": content_hash,
            "raw_hash": raw_hash,
            "payload_kind": payload_kind,
            "payload_relpath": payload_relpath,
            "logical_path": logical_path,
            "source_title": title,
            "media_type": media_type,
            "extension": extension,
            "imported_at": imported_at,
            "provider_id": provider_result.provider_id if provider_result else "",
            "provider_kind": provider_result.provider_kind if provider_result else "",
            "provider_version": provider_result.provider_version if provider_result else "",
            "strategy_used": provider_result.strategy_used if provider_result else "blob_import",
            "merkle_root": merkle_root,
            "section_count": len(sections),
            "metadata": {
                "source_path": str(source),
                "byte_size": len(raw_blob),
                "summary": summarize_text(sections[0]["exact_text"]) if sections else "",
            },
        }
        self._persist_revision(conn, node=node, revision_payload=revision_payload, sections=sections)
        return node

    def refresh_document(self, node_id: str) -> dict[str, Any]:
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM nodes WHERE node_id = ?", (node_id,)).fetchone()
            node = self._row_to_node(row)
            if node is None:
                raise KeyError(node_id)
            if node["node_kind"] == "group":
                raise ValueError("Groups do not have refreshable document revisions.")
            source_path = node.get("source_path")
            if not source_path:
                raise ValueError("Node has no source_path to refresh from.")
            source = Path(source_path)
            if not source.exists():
                raise FileNotFoundError(source)
            self._import_file(
                conn=conn,
                source=source,
                parent_node_id=node["parent_node_id"],
                logical_path=node["logical_path"],
                title=node["title"],
                existing_node_id=node["node_id"],
            )
            conn.commit()
        finally:
            conn.close()
        detail = self.get_detail(node_id)
        self._log_operation(
            "library_refresh",
            node_id=node_id,
            revision_id=detail["revision"]["revision_id"] if detail["revision"] else None,
            details={"source_path": source_path},
        )
        return detail

    def create_group(self, title: str, parent_node_id: str | None = None) -> dict[str, Any]:
        conn = self._connect()
        try:
            parent_logical = ""
            if parent_node_id:
                parent = self._row_to_node(
                    conn.execute("SELECT * FROM nodes WHERE node_id = ?", (parent_node_id,)).fetchone()
                )
                if parent is None:
                    raise KeyError(parent_node_id)
                if parent["node_kind"] != "group":
                    raise ValueError("New parent must be a group node.")
                parent_logical = str(parent["logical_path"])
            node = self._create_node(
                conn=conn,
                node_kind="group",
                title=title,
                logical_path=child_logical_path(parent_logical, title),
                source_path="",
                parent_node_id=parent_node_id,
                media_type="inode/directory",
                extension="",
                metadata={"import_kind": "manual_group"},
            )
            conn.commit()
        finally:
            conn.close()
        self._log_operation("library_create_group", node_id=node["node_id"], details={"title": title})
        return self.get_detail(node["node_id"])

    def _collect_subtree_ids(self, conn: sqlite3.Connection, root_ids: list[str]) -> set[str]:
        if not root_ids:
            return set()
        placeholders = ",".join("?" for _ in root_ids)
        sql = f"""
            WITH RECURSIVE subtree(node_id) AS (
                SELECT node_id FROM nodes WHERE node_id IN ({placeholders})
                UNION ALL
                SELECT child.node_id
                FROM nodes child
                JOIN subtree parent ON child.parent_node_id = parent.node_id
            )
            SELECT node_id FROM subtree
        """
        rows = conn.execute(sql, root_ids).fetchall()
        return {str(row["node_id"]) for row in rows}

    def archive_node(self, node_id: str) -> dict[str, Any]:
        conn = self._connect()
        try:
            ids = self._collect_subtree_ids(conn, [node_id])
            if not ids:
                raise KeyError(node_id)
            now = utc_now()
            placeholders = ",".join("?" for _ in ids)
            params = [now, *ids]
            conn.execute(
                f"UPDATE nodes SET archived = 1, updated_at = ? WHERE node_id IN ({placeholders})",
                params,
            )
            for archived_id in ids:
                row = conn.execute("SELECT * FROM nodes WHERE node_id = ?", (archived_id,)).fetchone()
                node = self._row_to_node(row)
                if node is not None:
                    self._write_json(self.nodes_dir / f"{archived_id}.json", node)
            conn.commit()
        finally:
            conn.close()
        self._log_operation("library_archive", node_id=node_id, details={"subtree_count": len(ids)})
        return self.get_detail(node_id)

    def _repath_subtree(
        self,
        conn: sqlite3.Connection,
        node_id: str,
        parent_node_id: str | None,
        title_override: str | None = None,
    ) -> None:
        row = conn.execute("SELECT * FROM nodes WHERE node_id = ?", (node_id,)).fetchone()
        node = self._row_to_node(row)
        if node is None:
            raise KeyError(node_id)
        if parent_node_id:
            parent = self._row_to_node(
                conn.execute("SELECT * FROM nodes WHERE node_id = ?", (parent_node_id,)).fetchone()
            )
            if parent is None:
                raise KeyError(parent_node_id)
            parent_logical = parent["logical_path"]
        else:
            parent_logical = ""
        title = title_override or node["title"]
        new_logical_path = child_logical_path(parent_logical, title)
        conn.execute(
            """
            UPDATE nodes
            SET parent_node_id = ?, title = ?, logical_path = ?, updated_at = ?
            WHERE node_id = ?
            """,
            (parent_node_id, title, new_logical_path, utc_now(), node_id),
        )
        fresh = self._row_to_node(conn.execute("SELECT * FROM nodes WHERE node_id = ?", (node_id,)).fetchone())
        if fresh is not None:
            self._write_json(self.nodes_dir / f"{node_id}.json", fresh)
        child_rows = conn.execute(
            "SELECT node_id FROM nodes WHERE parent_node_id = ? ORDER BY title COLLATE NOCASE",
            (node_id,),
        ).fetchall()
        for child_row in child_rows:
            self._repath_subtree(conn, str(child_row["node_id"]), node_id)

    def rename_node(self, node_id: str, new_title: str) -> dict[str, Any]:
        conn = self._connect()
        try:
            row = conn.execute("SELECT parent_node_id FROM nodes WHERE node_id = ?", (node_id,)).fetchone()
            if row is None:
                raise KeyError(node_id)
            self._repath_subtree(conn, node_id=node_id, parent_node_id=row["parent_node_id"], title_override=new_title)
            conn.commit()
        finally:
            conn.close()
        self._log_operation("library_rename", node_id=node_id, details={"new_title": new_title})
        return self.get_detail(node_id)

    def move_node(self, node_id: str, new_parent_id: str | None) -> dict[str, Any]:
        conn = self._connect()
        try:
            if new_parent_id:
                parent = self._row_to_node(
                    conn.execute("SELECT * FROM nodes WHERE node_id = ?", (new_parent_id,)).fetchone()
                )
                if parent is None:
                    raise KeyError(new_parent_id)
                if parent["node_kind"] != "group":
                    raise ValueError("New parent must be a group node.")
                descendants = self._collect_subtree_ids(conn, [node_id])
                if new_parent_id in descendants:
                    raise ValueError("Cannot move a node underneath its own subtree.")
            self._repath_subtree(conn, node_id=node_id, parent_node_id=new_parent_id)
            conn.commit()
        finally:
            conn.close()
        self._log_operation("library_move", node_id=node_id, details={"new_parent_id": new_parent_id})
        return self.get_detail(node_id)

    def attach_node(
        self,
        node_id: str,
        project_path: str,
        attachment_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        store = AttachmentStore(project_path)
        payload = store.attach(node_id=node_id, attachment_context=attachment_context)
        self._log_operation(
            "library_attach",
            node_id=node_id,
            details={"project_path": str(Path(project_path).expanduser().resolve())},
        )
        return payload

    def detach_node(self, node_id: str, project_path: str) -> dict[str, Any]:
        store = AttachmentStore(project_path)
        payload = store.detach(node_id=node_id)
        self._log_operation(
            "library_detach",
            node_id=node_id,
            details={"project_path": str(Path(project_path).expanduser().resolve())},
        )
        return payload

    def list_revisions(self, node_id: str) -> dict[str, Any]:
        conn = self._connect()
        try:
            node = self._row_to_node(conn.execute("SELECT * FROM nodes WHERE node_id = ?", (node_id,)).fetchone())
            if node is None:
                raise KeyError(node_id)
            rows = conn.execute(
                "SELECT * FROM revisions WHERE node_id = ? ORDER BY revision_number DESC",
                (node_id,),
            ).fetchall()
            revisions = [self._row_to_revision(row) for row in rows]
            return {"node": node, "revisions": revisions}
        finally:
            conn.close()

    def get_detail(self, node_id: str, revision_id: str | None = None) -> dict[str, Any]:
        conn = self._connect()
        try:
            node = self._row_to_node(conn.execute("SELECT * FROM nodes WHERE node_id = ?", (node_id,)).fetchone())
            if node is None:
                raise KeyError(node_id)
            children = [
                self._row_to_node(row)
                for row in conn.execute(
                    "SELECT * FROM nodes WHERE parent_node_id = ? ORDER BY title COLLATE NOCASE",
                    (node_id,),
                ).fetchall()
            ]
            selected_revision_id = revision_id or node.get("latest_revision_id")
            revision = None
            sections: list[dict[str, Any]] = []
            if selected_revision_id:
                revision = self._row_to_revision(
                    conn.execute(
                        "SELECT * FROM revisions WHERE revision_id = ?", (selected_revision_id,)
                    ).fetchone()
                )
                if revision is not None:
                    section_rows = conn.execute(
                        "SELECT * FROM sections WHERE revision_id = ? ORDER BY ordinal",
                        (selected_revision_id,),
                    ).fetchall()
                    sections = [self._row_to_section(row) for row in section_rows]
            return {
                "node": node,
                "revision": revision,
                "sections": sections,
                "children": children,
                "latest_revision_selected": selected_revision_id == node.get("latest_revision_id"),
            }
        finally:
            conn.close()

    def search(
        self,
        query: str,
        scope: str = "attached",
        project_path: str | None = None,
        attached_root_ids: list[str] | None = None,
        limit: int = 10,
        include_archived: bool = False,
    ) -> dict[str, Any]:
        if not query.strip():
            return {"query": query, "scope": scope, "results": []}
        conn = self._connect()
        try:
            allowed_ids: set[str] | None
            if scope == "global":
                allowed_ids = None
            else:
                roots = list(attached_root_ids or [])
                if project_path:
                    roots = list({*roots, *AttachmentStore(project_path).list_root_ids()})
                if not roots:
                    return {"query": query, "scope": scope, "results": []}
                allowed_ids = self._collect_subtree_ids(conn, roots)
                if not allowed_ids:
                    return {"query": query, "scope": scope, "results": []}

            results: list[dict[str, Any]] = []
            if self._fts_enabled(conn):
                conditions = ["s.revision_id = n.latest_revision_id", "f.section_fts MATCH ?"]
                params: list[Any] = [query]
                if not include_archived:
                    conditions.append("n.archived = 0")
                if allowed_ids is not None:
                    placeholders = ",".join("?" for _ in allowed_ids)
                    conditions.append(f"s.node_id IN ({placeholders})")
                    params.extend(sorted(allowed_ids))
                sql = f"""
                    SELECT s.section_id, s.node_id, s.revision_id, s.anchor_path, s.title AS section_title,
                           s.summary, substr(s.exact_text, 1, 240) AS preview,
                           n.title AS node_title, n.logical_path
                    FROM section_fts f
                    JOIN sections s ON s.section_id = f.section_id
                    JOIN nodes n ON n.node_id = s.node_id
                    WHERE {" AND ".join(conditions)}
                    LIMIT ?
                """
                params.append(max(1, limit))
                rows = conn.execute(sql, params).fetchall()
            else:
                like_query = f"%{query}%"
                conditions = [
                    "(s.title LIKE ? OR s.summary LIKE ? OR s.exact_text LIKE ?)",
                    "s.revision_id = n.latest_revision_id",
                ]
                params = [like_query, like_query, like_query]
                if not include_archived:
                    conditions.append("n.archived = 0")
                if allowed_ids is not None:
                    placeholders = ",".join("?" for _ in allowed_ids)
                    conditions.append(f"s.node_id IN ({placeholders})")
                    params.extend(sorted(allowed_ids))
                sql = f"""
                    SELECT s.section_id, s.node_id, s.revision_id, s.anchor_path, s.title AS section_title,
                           s.summary, substr(s.exact_text, 1, 240) AS preview,
                           n.title AS node_title, n.logical_path
                    FROM sections s
                    JOIN nodes n ON n.node_id = s.node_id
                    WHERE {" AND ".join(conditions)}
                    LIMIT ?
                """
                params.append(max(1, limit))
                rows = conn.execute(sql, params).fetchall()
            for row in rows:
                results.append(
                    {
                        "section_id": row["section_id"],
                        "node_id": row["node_id"],
                        "revision_id": row["revision_id"],
                        "anchor_path": row["anchor_path"],
                        "title": row["section_title"] or row["node_title"],
                        "summary": row["summary"],
                        "preview": row["preview"],
                        "node_title": row["node_title"],
                        "logical_path": row["logical_path"],
                    }
                )
            return {"query": query, "scope": scope, "results": results}
        finally:
            conn.close()

    def _load_revision_text(self, revision: dict[str, Any]) -> str:
        payload_path = self.root_dir / revision["payload_relpath"]
        if revision["payload_kind"] != "text":
            return ""
        return payload_path.read_text(encoding="utf-8")

    def read_excerpt(
        self,
        node_id: str,
        revision_id: str,
        section_id: str | None = None,
        anchor_path: str | None = None,
        char_start: int | None = None,
        char_end: int | None = None,
        project_path: str | None = None,
        session_store=None,
        session_id: str | None = None,
        evidence_store=None,
        attachment_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        conn = self._connect()
        try:
            node = self._row_to_node(conn.execute("SELECT * FROM nodes WHERE node_id = ?", (node_id,)).fetchone())
            revision = self._row_to_revision(
                conn.execute(
                    "SELECT * FROM revisions WHERE revision_id = ? AND node_id = ?",
                    (revision_id, node_id),
                ).fetchone()
            )
            if node is None or revision is None:
                raise KeyError(f"{node_id}:{revision_id}")

            section = None
            if section_id:
                section = self._row_to_section(
                    conn.execute(
                        "SELECT * FROM sections WHERE section_id = ? AND revision_id = ?",
                        (section_id, revision_id),
                    ).fetchone()
                )
            elif anchor_path:
                section = self._row_to_section(
                    conn.execute(
                        """
                        SELECT * FROM sections
                        WHERE revision_id = ? AND anchor_path = ?
                        ORDER BY ordinal
                        LIMIT 1
                        """,
                        (revision_id, anchor_path),
                    ).fetchone()
                )
            if section is not None:
                excerpt_text = section["exact_text"]
                resolved_start = section["char_start"]
                resolved_end = section["char_end"]
                resolved_anchor_path = section["anchor_path"]
            else:
                text = self._load_revision_text(revision)
                excerpt_text, resolved_start, resolved_end = trim_excerpt(
                    text,
                    char_start=char_start,
                    char_end=char_end,
                )
                resolved_anchor_path = anchor_path or f"chars/{resolved_start}-{resolved_end}"

            effective_attachment_context = dict(attachment_context or {})
            if project_path and not effective_attachment_context:
                try:
                    effective_attachment_context = AttachmentStore(project_path).get_attachment_context(node_id)
                except Exception:
                    effective_attachment_context = {}

            operation_seed = {
                "session_id": session_id or "",
                "node_id": node_id,
                "revision_id": revision_id,
                "section_id": section["section_id"] if section else "",
                "anchor_path": resolved_anchor_path,
                "char_start": resolved_start,
                "char_end": resolved_end,
            }
            operation_id = f"op_{self.hasher.hash_content(canonical_json(operation_seed))[:24]}"
            excerpt_hash = self.hasher.hash_content(excerpt_text)
            summary_text = (
                str(section.get("summary") or "").strip()
                if section is not None
                else summarize_text(excerpt_text)
            ) or summarize_text(excerpt_text)
            provenance = {
                "library_root": str(self.root_dir),
                "node_id": node["node_id"],
                "revision_id": revision["revision_id"],
                "section_id": section["section_id"] if section else None,
                "logical_path": revision["logical_path"],
                "anchor_path": resolved_anchor_path,
                "source_title": revision["source_title"],
                "provider_id": revision.get("provider_id"),
                "provider_kind": revision.get("provider_kind"),
                "strategy_used": revision.get("strategy_used"),
                "content_hash": revision["content_hash"],
                "imported_at": revision["imported_at"],
                "attachment_context": effective_attachment_context,
                "operation_id": operation_id,
            }
        finally:
            conn.close()

        usage_written = False
        cache_written = False
        if session_store is not None and session_id:
            usage_written = bool(
                session_store.record_library_usage(
                    operation_id=operation_id,
                    session_id=session_id,
                    node_id=node_id,
                    revision_id=revision_id,
                    section_id=section["section_id"] if section else None,
                    project_path=project_path,
                    attachment_context=effective_attachment_context,
                )
            )
            cache_written = bool(
                session_store.cache_library_excerpt(
                    operation_id=operation_id,
                    session_id=session_id,
                    node_id=node_id,
                    revision_id=revision_id,
                    section_id=section["section_id"] if section else None,
                    excerpt_hash=excerpt_hash,
                    excerpt_text=excerpt_text,
                    provenance=provenance,
                )
            )

        evidence_result = {"inserted": False, "evidence_id": ""}
        if evidence_store is not None:
            existing_evidence_id = ""
            if hasattr(evidence_store, "find_by_operation_id"):
                existing_evidence_id = str(evidence_store.find_by_operation_id(operation_id) or "")
            source_anchor_id = section["section_id"] if section is not None else revision["revision_id"]
            source_anchor_locator = f"{revision['logical_path']}@{revision_id}#{resolved_anchor_path}"
            evidence_id = evidence_store.ingest_source_record(
                exact_text=excerpt_text,
                item_kind="reference_excerpt",
                role="source",
                source_anchor_kind="reference_library_section",
                source_anchor_id=source_anchor_id,
                source_anchor_locator=source_anchor_locator,
                structural_path=revision["logical_path"],
                summary_text=summary_text,
                provenance=provenance,
                operation_id=operation_id,
                session_id=session_id or "",
            )
            evidence_result = {"inserted": not bool(existing_evidence_id), "evidence_id": evidence_id}
        self._log_operation(
            "library_read_excerpt",
            node_id=node_id,
            revision_id=revision_id,
            details={"section_id": provenance.get("section_id"), "operation_id": operation_id},
            operation_id=operation_id,
        )
        return {
            "operation_id": operation_id,
            "node_id": node_id,
            "revision_id": revision_id,
            "section_id": provenance.get("section_id"),
            "anchor_path": resolved_anchor_path,
            "excerpt_text": excerpt_text,
            "summary_text": summary_text,
            "char_start": resolved_start,
            "char_end": resolved_end,
            "excerpt_hash": excerpt_hash,
            "provenance": provenance,
            "usage_recorded": usage_written,
            "cache_recorded": cache_written,
            "evidence_mirrored": evidence_result["inserted"],
            "evidence_record": evidence_result,
        }

    def export_node(self, node_id: str, destination_dir: str | None = None) -> dict[str, Any]:
        detail = self.get_detail(node_id)
        export_root = Path(destination_dir).expanduser().resolve() if destination_dir else self.exports_dir
        ensure_directory(export_root)
        export_name = f"{slugify(detail['node']['title'])}-{node_id}.json"
        export_path = export_root / export_name
        subtree = self._export_subtree(node_id)
        export_payload = {
            "exported_at": utc_now(),
            "library_root": str(self.root_dir),
            "node_detail": detail,
            "subtree": subtree,
        }
        export_path.write_text(json.dumps(export_payload, indent=2, sort_keys=True), encoding="utf-8")
        self._log_operation(
            "library_export",
            node_id=node_id,
            details={"destination": str(export_path)},
        )
        return {"export_path": str(export_path), "node_id": node_id}

    def _export_subtree(self, node_id: str) -> dict[str, Any]:
        conn = self._connect()
        try:
            subtree_ids = self._collect_subtree_ids(conn, [node_id])
            nodes = []
            revisions = []
            sections = []
            for subtree_id in sorted(subtree_ids):
                node = self._row_to_node(
                    conn.execute("SELECT * FROM nodes WHERE node_id = ?", (subtree_id,)).fetchone()
                )
                if node is not None:
                    nodes.append(node)
                revision_rows = conn.execute(
                    "SELECT * FROM revisions WHERE node_id = ? ORDER BY revision_number",
                    (subtree_id,),
                ).fetchall()
                for revision_row in revision_rows:
                    revision = self._row_to_revision(revision_row)
                    if revision is not None:
                        revisions.append(revision)
                        section_rows = conn.execute(
                            "SELECT * FROM sections WHERE revision_id = ? ORDER BY ordinal",
                            (revision["revision_id"],),
                        ).fetchall()
                        sections.extend(self._row_to_section(row) for row in section_rows)
            return {"nodes": nodes, "revisions": revisions, "sections": sections}
        finally:
            conn.close()

    def health(self) -> dict[str, Any]:
        conn = self._connect()
        try:
            node_count = conn.execute("SELECT COUNT(*) AS c FROM nodes").fetchone()["c"]
            revision_count = conn.execute("SELECT COUNT(*) AS c FROM revisions").fetchone()["c"]
            section_count = conn.execute("SELECT COUNT(*) AS c FROM sections").fetchone()["c"]
            operation_count = conn.execute("SELECT COUNT(*) AS c FROM operations").fetchone()["c"]
            return {
                "status": "online",
                "library_root": str(self.root_dir),
                "db_path": str(self.db_path),
                "counts": {
                    "nodes": node_count,
                    "revisions": revision_count,
                    "sections": section_count,
                    "operations": operation_count,
                },
                "providers": [
                    {"manifest": manifest, "health": self.providers.get(manifest["provider_id"]).health()}
                    for manifest in self.providers.manifests()
                ],
            }
        finally:
            conn.close()

    def package_manifest(self) -> dict[str, Any]:
        app_manifest = {}
        tool_manifest = {}
        app_manifest_path = self.app_dir / "app_manifest.json"
        tool_manifest_path = self.app_dir / "tool_manifest.json"
        if app_manifest_path.exists():
            app_manifest = json.loads(app_manifest_path.read_text(encoding="utf-8"))
        if tool_manifest_path.exists():
            tool_manifest = json.loads(tool_manifest_path.read_text(encoding="utf-8"))
        return {
            "package_name": self.package_name,
            "package_version": self.package_version,
            "vendor_mode": "static",
            "app_manifest": app_manifest,
            "tool_manifest": tool_manifest,
            "library": self.health(),
        }
