from __future__ import annotations

import hashlib
import sqlite3
import time
from pathlib import Path
from typing import Any


class Blake3HashMS:
    """Compat hashing helper used by the intake seed."""

    def __init__(self) -> None:
        self.start_time = time.time()
        try:
            import blake3 as _blake3  # type: ignore
        except Exception:
            _blake3 = None
        self._blake3 = _blake3

    def _hash(self, payload: bytes) -> str:
        if self._blake3 is not None:
            return self._blake3.blake3(payload).hexdigest()
        return hashlib.sha256(payload).hexdigest()

    def hash_content(self, content: str) -> str:
        return self._hash(content.encode("utf-8"))

    def hash_bytes(self, blob: bytes) -> str:
        return self._hash(blob)

    def combine_cids(self, cids: list[str]) -> str:
        return self._hash("".join(cids).encode("utf-8"))

    def get_health(self) -> dict[str, Any]:
        return {
            "status": "online",
            "uptime": time.time() - self.start_time,
            "blake3_native": self._blake3 is not None,
        }


class TemporalChainMS:
    """Small append-only Merkle-root chain for immutable revision history."""

    def __init__(self) -> None:
        self.start_time = time.time()
        self._hasher = Blake3HashMS()

    def _open(self, db_path: str | Path) -> sqlite3.Connection:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS temporal_chain (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                root_cid TEXT NOT NULL,
                prev_cid TEXT,
                label TEXT,
                leaf_count INTEGER,
                created_at REAL NOT NULL
            )
            """
        )
        conn.commit()
        return conn

    def commit(self, db_path: str | Path, leaves: list[str], label: str = "") -> dict[str, Any]:
        root = self._hasher.combine_cids(leaves or [""])
        conn = self._open(db_path)
        try:
            previous = conn.execute(
                "SELECT root_cid FROM temporal_chain ORDER BY seq DESC LIMIT 1"
            ).fetchone()
            prev_cid = str(previous["root_cid"]) if previous else None
            cursor = conn.execute(
                """
                INSERT INTO temporal_chain (root_cid, prev_cid, label, leaf_count, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (root, prev_cid, label, len(leaves), time.time()),
            )
            conn.commit()
            return {"root": root, "seq": cursor.lastrowid}
        finally:
            conn.close()

    def get_health(self) -> dict[str, Any]:
        return {"status": "online", "uptime": time.time() - self.start_time}
