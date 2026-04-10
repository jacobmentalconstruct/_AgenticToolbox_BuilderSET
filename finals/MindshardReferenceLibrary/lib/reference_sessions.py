from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from src.core.reference_library.attachments import AttachmentStore
from src.core.reference_library.utils import canonical_json, ensure_directory, new_id, utc_now


class SessionStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path).expanduser().resolve()
        ensure_directory(self.db_path.parent)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS library_usage (
                    operation_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    node_id TEXT NOT NULL,
                    revision_id TEXT NOT NULL,
                    section_id TEXT,
                    project_path TEXT,
                    attachment_context_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS library_excerpt_cache (
                    operation_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    node_id TEXT NOT NULL,
                    revision_id TEXT NOT NULL,
                    section_id TEXT,
                    excerpt_hash TEXT NOT NULL,
                    excerpt_text TEXT NOT NULL,
                    provenance_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

    def record_library_usage(
        self,
        operation_id: str,
        session_id: str,
        node_id: str,
        revision_id: str,
        section_id: str | None,
        project_path: str | None,
        attachment_context: dict[str, Any] | None,
    ) -> bool:
        conn = self._connect()
        try:
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO library_usage (
                    operation_id, session_id, node_id, revision_id, section_id,
                    project_path, attachment_context_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    operation_id,
                    session_id,
                    node_id,
                    revision_id,
                    section_id,
                    project_path or "",
                    canonical_json(attachment_context or {}),
                    utc_now(),
                ),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def cache_library_excerpt(
        self,
        operation_id: str,
        session_id: str,
        node_id: str,
        revision_id: str,
        section_id: str | None,
        excerpt_hash: str,
        excerpt_text: str,
        provenance: dict[str, Any],
    ) -> bool:
        conn = self._connect()
        try:
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO library_excerpt_cache (
                    operation_id, session_id, node_id, revision_id, section_id,
                    excerpt_hash, excerpt_text, provenance_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    operation_id,
                    session_id,
                    node_id,
                    revision_id,
                    section_id,
                    excerpt_hash,
                    excerpt_text,
                    canonical_json(provenance),
                    utc_now(),
                ),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def list_library_usage(self) -> list[dict[str, Any]]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT operation_id, session_id, node_id, revision_id, section_id,
                       project_path, attachment_context_json, created_at
                FROM library_usage
                ORDER BY created_at ASC
                """
            ).fetchall()
            return [
                {
                    "operation_id": row["operation_id"],
                    "session_id": row["session_id"],
                    "node_id": row["node_id"],
                    "revision_id": row["revision_id"],
                    "section_id": row["section_id"],
                    "project_path": row["project_path"],
                    "attachment_context": json.loads(row["attachment_context_json"] or "{}"),
                    "created_at": row["created_at"],
                }
                for row in rows
            ]
        finally:
            conn.close()

    def list_library_excerpt_cache(self) -> list[dict[str, Any]]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT operation_id, session_id, node_id, revision_id, section_id,
                       excerpt_hash, excerpt_text, provenance_json, created_at
                FROM library_excerpt_cache
                ORDER BY created_at ASC
                """
            ).fetchall()
            return [
                {
                    "operation_id": row["operation_id"],
                    "session_id": row["session_id"],
                    "node_id": row["node_id"],
                    "revision_id": row["revision_id"],
                    "section_id": row["section_id"],
                    "excerpt_hash": row["excerpt_hash"],
                    "excerpt_text": row["excerpt_text"],
                    "provenance": json.loads(row["provenance_json"] or "{}"),
                    "created_at": row["created_at"],
                }
                for row in rows
            ]
        finally:
            conn.close()

    def record_usage(self, **kwargs) -> bool:
        return self.record_library_usage(**kwargs)

    def cache_excerpt(self, **kwargs) -> bool:
        return self.cache_library_excerpt(**kwargs)


class EvidenceShelfStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path).expanduser().resolve()
        self.evidence_root = ensure_directory(self.db_path.parent)
        self.log_path = self.evidence_root / "reference_excerpt.jsonl"
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS evidence_records (
                    evidence_id TEXT PRIMARY KEY,
                    operation_id TEXT NOT NULL UNIQUE,
                    item_kind TEXT NOT NULL,
                    role TEXT NOT NULL,
                    source_anchor_kind TEXT NOT NULL,
                    source_anchor_id TEXT NOT NULL,
                    source_anchor_locator TEXT NOT NULL,
                    structural_path TEXT NOT NULL,
                    summary_text TEXT NOT NULL,
                    excerpt_hash TEXT NOT NULL,
                    exact_text TEXT NOT NULL,
                    provenance_json TEXT NOT NULL,
                    session_id TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

    def find_by_operation_id(self, operation_id: str) -> str:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT evidence_id FROM evidence_records WHERE operation_id = ?",
                (operation_id,),
            ).fetchone()
            return str(row["evidence_id"]) if row else ""
        finally:
            conn.close()

    def ingest_source_record(
        self,
        *,
        exact_text: str,
        item_kind: str,
        role: str,
        source_anchor_kind: str,
        source_anchor_id: str,
        source_anchor_locator: str,
        structural_path: str,
        summary_text: str,
        provenance: dict[str, Any],
        operation_id: str,
        session_id: str = "",
    ) -> str:
        existing = self.find_by_operation_id(operation_id)
        if existing:
            return existing

        excerpt_hash = str(provenance.get("excerpt_hash") or "")
        if not excerpt_hash:
            import hashlib

            excerpt_hash = hashlib.sha256(exact_text.encode("utf-8")).hexdigest()

        evidence_id = new_id("evidence")
        record = {
            "evidence_id": evidence_id,
            "operation_id": operation_id,
            "item_kind": item_kind,
            "role": role,
            "source_anchor_kind": source_anchor_kind,
            "source_anchor_id": source_anchor_id,
            "source_anchor_locator": source_anchor_locator,
            "structural_path": structural_path,
            "summary_text": summary_text,
            "excerpt_hash": excerpt_hash,
            "exact_text": exact_text,
            "provenance": provenance,
            "session_id": session_id,
            "created_at": utc_now(),
        }

        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT OR IGNORE INTO evidence_records (
                    evidence_id, operation_id, item_kind, role, source_anchor_kind,
                    source_anchor_id, source_anchor_locator, structural_path, summary_text,
                    excerpt_hash, exact_text, provenance_json, session_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["evidence_id"],
                    record["operation_id"],
                    record["item_kind"],
                    record["role"],
                    record["source_anchor_kind"],
                    record["source_anchor_id"],
                    record["source_anchor_locator"],
                    record["structural_path"],
                    record["summary_text"],
                    record["excerpt_hash"],
                    record["exact_text"],
                    canonical_json(record["provenance"]),
                    record["session_id"],
                    record["created_at"],
                ),
            )
            conn.commit()
        finally:
            conn.close()

        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
        return evidence_id

    def count(self) -> int:
        conn = self._connect()
        try:
            row = conn.execute("SELECT COUNT(*) AS c FROM evidence_records").fetchone()
            return int(row["c"]) if row else 0
        finally:
            conn.close()

    def mirror_reference_excerpt(
        self,
        operation_id: str,
        excerpt_hash: str,
        excerpt_text: str,
        provenance: dict[str, Any],
    ) -> dict[str, Any]:
        evidence_id = self.ingest_source_record(
            exact_text=excerpt_text,
            item_kind="reference_excerpt",
            role="source",
            source_anchor_kind="reference_library_section",
            source_anchor_id=str(provenance.get("section_id") or provenance.get("revision_id") or ""),
            source_anchor_locator=str(
                f"{provenance.get('logical_path', '')}@{provenance.get('revision_id', '')}#{provenance.get('anchor_path', '')}"
            ),
            structural_path=str(provenance.get("logical_path") or ""),
            summary_text=str(provenance.get("summary_text") or ""),
            provenance=dict(provenance or {}, excerpt_hash=excerpt_hash),
            operation_id=operation_id,
            session_id="",
        )
        return {
            "inserted": True,
            "db_path": str(self.db_path),
            "log_path": str(self.log_path),
            "operation_id": operation_id,
            "evidence_id": evidence_id,
        }


SessionRecorder = SessionStore
EvidenceShelf = EvidenceShelfStore

__all__ = [
    "AttachmentStore",
    "EvidenceShelf",
    "EvidenceShelfStore",
    "SessionRecorder",
    "SessionStore",
]
