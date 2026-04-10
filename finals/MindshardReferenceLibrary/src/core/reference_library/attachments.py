from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.core.reference_library.utils import ensure_directory, utc_now


class AttachmentStore:
    """Project-local attachment truth for the global reference library."""

    schema_version = "1.0"

    def __init__(self, project_path: str | Path) -> None:
        self.project_path = Path(project_path).expanduser().resolve()
        self.state_path = (
            self.project_path
            / ".mindshard"
            / "state"
            / "reference_library_attachments.json"
        )

    def _base_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "project_path": str(self.project_path),
            "updated_at": utc_now(),
            "attachments": {},
        }

    def load(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return self._base_payload()
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        except Exception:
            payload = self._base_payload()
        payload.setdefault("schema_version", self.schema_version)
        payload.setdefault("project_path", str(self.project_path))
        payload.setdefault("updated_at", utc_now())
        payload.setdefault("attachments", {})
        return payload

    def save(self, payload: dict[str, Any]) -> dict[str, Any]:
        ensure_directory(self.state_path.parent)
        payload["schema_version"] = self.schema_version
        payload["project_path"] = str(self.project_path)
        payload["updated_at"] = utc_now()
        self.state_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return payload

    def attach(
        self,
        node_id: str,
        attachment_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = self.load()
        payload["attachments"][node_id] = {
            "attached_at": utc_now(),
            "attachment_context": dict(attachment_context or {}),
        }
        return self.save(payload)

    def detach(self, node_id: str) -> dict[str, Any]:
        payload = self.load()
        payload["attachments"].pop(node_id, None)
        return self.save(payload)

    def list_root_ids(self) -> list[str]:
        return sorted(self.load().get("attachments", {}).keys())

    def get_attachment_context(self, node_id: str) -> dict[str, Any]:
        attachments = self.load().get("attachments", {})
        context = attachments.get(node_id, {}).get("attachment_context", {})
        return dict(context or {})

    def is_attached(self, node_id: str) -> bool:
        return node_id in self.load().get("attachments", {})
