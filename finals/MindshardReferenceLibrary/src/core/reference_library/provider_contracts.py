from __future__ import annotations

from dataclasses import dataclass
from typing import Any


TREE_SPLITTER = "tree_splitter"
PEG_DOCUMENT = "peg_document"
FALLBACK_CHUNKER = "fallback_chunker"


@dataclass(slots=True)
class ProviderManifest:
    provider_id: str
    schema_version: str
    provider_kind: str
    strategy: str
    priority: int
    entrypoint: str
    supported_extensions: list[str]
    supported_media_types: list[str]
    healthcheck: str
    timeout_sec: int
    enabled: bool
    version: str


@dataclass(slots=True)
class ProviderRequest:
    request_id: str
    strategy_hint: str
    logical_path: str
    media_type: str
    extension: str
    content_hash: str
    text_path: str | None
    blob_path: str | None
    max_chars: int
    overlap_chars: int
    metadata: dict[str, Any]


@dataclass(slots=True)
class ProviderSection:
    section_id: str
    parent_section_id: str | None
    ordinal: int
    depth: int
    section_kind: str
    anchor_path: str
    title: str
    summary: str
    exact_text: str
    char_start: int
    char_end: int
    source_span: dict[str, Any]
    metadata: dict[str, Any]


@dataclass(slots=True)
class ProviderResult:
    provider_id: str
    provider_kind: str
    provider_version: str
    strategy_used: str
    status: str
    warnings: list[str]
    sections: list[ProviderSection]
