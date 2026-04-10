from __future__ import annotations

import importlib
import inspect
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from src.core.reference_library.provider_contracts import (
    FALLBACK_CHUNKER,
    PEG_DOCUMENT,
    TREE_SPLITTER,
    ProviderManifest,
    ProviderRequest,
    ProviderResult,
    ProviderSection,
)
from src.core.reference_library.utils import (
    PROSE_EXTENSIONS,
    READABLE_TEXT_EXTENSIONS,
    char_range_from_lines,
    slugify,
    summarize_text,
)

TREE_SITTER_PROVIDER_ID = "tree_sitter_reference_provider"


def _tree_sitter_runtime_available() -> bool:
    try:
        import tree_sitter_language_pack  # noqa: F401
    except Exception:
        return False
    return True


class BaseProvider:
    def __init__(self, manifest: ProviderManifest) -> None:
        self.manifest = manifest

    def health(self) -> dict[str, Any]:
        return {"status": "online", "provider_id": self.manifest.provider_id}

    def parse(self, request: ProviderRequest, text: str) -> ProviderResult:
        raise NotImplementedError


class EntrypointProvider(BaseProvider):
    """Generic manifest-driven adapter that resolves entrypoints at runtime."""

    def __init__(self, manifest: ProviderManifest) -> None:
        super().__init__(manifest)
        self._parse_endpoint = self._resolve_entrypoint(manifest.entrypoint)
        self._health_endpoint = self._resolve_entrypoint(manifest.healthcheck) if manifest.healthcheck else None

    def _resolve_entrypoint(self, entrypoint: str):
        if ":" not in entrypoint:
            raise RuntimeError(f"Invalid provider entrypoint: {entrypoint}")
        module_name, target_path = entrypoint.split(":", 1)
        module = importlib.import_module(module_name)
        target: Any = module
        for part in target_path.split("."):
            target = getattr(target, part)
            if inspect.isclass(target):
                target = target()
        return target

    def _invoke_endpoint(self, endpoint, request: ProviderRequest, text: str):
        signature = inspect.signature(endpoint)
        candidates: dict[str, Any] = {
            "request": request,
            "text": text,
            "source_text": text,
            "content": text,
            "file_name": Path(request.logical_path).name,
            "file_path": request.logical_path,
            "source_path": request.logical_path,
            "lines": text.splitlines(),
            "line_count": len(text.splitlines()),
            "is_markdown": request.extension.lower() in {".md", ".markdown"},
            "max_tokens": max(1, request.max_chars // 4),
            "max_chunk_tokens": max(1, request.max_chars // 4),
            "overlap_lines": max(0, request.overlap_chars // 80),
            "window_lines": max(20, request.max_chars // 90),
            "treesitter_available": True,
            "parse_has_error": False,
        }
        kwargs = {
            name: candidates[name]
            for name in signature.parameters
            if name in candidates
        }
        return endpoint(**kwargs)

    def health(self) -> dict[str, Any]:
        if self._health_endpoint is None:
            return super().health()
        try:
            payload = self._health_endpoint()
        except Exception as exc:
            return {"status": "offline", "provider_id": self.manifest.provider_id, "reason": str(exc)}
        if "provider_id" not in payload:
            payload = dict(payload)
            payload["provider_id"] = self.manifest.provider_id
        return payload

    def parse(self, request: ProviderRequest, text: str) -> ProviderResult:
        raw = self._invoke_endpoint(self._parse_endpoint, request, text)
        if isinstance(raw, ProviderResult):
            return self._finalize_result(raw)
        if isinstance(raw, dict) and {"provider_id", "provider_kind", "provider_version", "strategy_used", "status", "warnings", "sections"} <= set(raw):
            result = ProviderResult(
                provider_id=str(raw["provider_id"]),
                provider_kind=str(raw["provider_kind"]),
                provider_version=str(raw["provider_version"]),
                strategy_used=str(raw["strategy_used"]),
                status=str(raw["status"]),
                warnings=list(raw.get("warnings", [])),
                sections=self._coerce_sections(raw.get("sections", []), request),
            )
            return self._finalize_result(result)
        return self._normalize_raw_result(raw, request, text)

    def _finalize_result(self, result: ProviderResult) -> ProviderResult:
        if not result.provider_id:
            result.provider_id = self.manifest.provider_id
        if not result.provider_kind:
            result.provider_kind = self.manifest.provider_kind
        if not result.provider_version:
            result.provider_version = self.manifest.version
        if not result.strategy_used:
            result.strategy_used = self.manifest.strategy
        result.sections = self._coerce_sections(result.sections, None)
        return result

    def _coerce_sections(
        self,
        raw_sections: list[Any] | tuple[Any, ...] | Any,
        request: ProviderRequest | None,
    ) -> list[ProviderSection]:
        if not isinstance(raw_sections, (list, tuple)):
            raise RuntimeError(
                f"Provider {self.manifest.provider_id} returned non-list sections payload: "
                f"{type(raw_sections).__name__}"
            )
        sections: list[ProviderSection] = []
        for ordinal, raw_section in enumerate(raw_sections, start=1):
            sections.append(self._coerce_section(raw_section, ordinal=ordinal, request=request))
        return sections

    def _coerce_section(
        self,
        raw_section: Any,
        *,
        ordinal: int,
        request: ProviderRequest | None,
    ) -> ProviderSection:
        if isinstance(raw_section, ProviderSection):
            return raw_section
        if not isinstance(raw_section, dict):
            raise RuntimeError(
                f"Provider {self.manifest.provider_id} returned unsupported section payload: "
                f"{type(raw_section).__name__}"
            )
        required = {
            "section_id",
            "parent_section_id",
            "ordinal",
            "depth",
            "section_kind",
            "anchor_path",
            "title",
            "summary",
            "exact_text",
            "char_start",
            "char_end",
            "source_span",
            "metadata",
        }
        missing = sorted(required.difference(raw_section))
        if missing:
            logical_path = request.logical_path if request is not None else self.manifest.provider_id
            raise RuntimeError(
                f"Provider {self.manifest.provider_id} returned malformed section payload for "
                f"{logical_path}: missing {', '.join(missing)}"
            )
        return ProviderSection(
            section_id=str(raw_section["section_id"]),
            parent_section_id=(
                str(raw_section["parent_section_id"])
                if raw_section["parent_section_id"] is not None
                else None
            ),
            ordinal=int(raw_section["ordinal"]),
            depth=int(raw_section["depth"]),
            section_kind=str(raw_section["section_kind"]),
            anchor_path=str(raw_section["anchor_path"]),
            title=str(raw_section["title"]),
            summary=str(raw_section["summary"]),
            exact_text=str(raw_section["exact_text"]),
            char_start=int(raw_section["char_start"]),
            char_end=int(raw_section["char_end"]),
            source_span=dict(raw_section.get("source_span") or {}),
            metadata=dict(raw_section.get("metadata") or {}),
        )

    def _normalize_raw_result(self, raw: Any, request: ProviderRequest, text: str) -> ProviderResult:
        if self.manifest.strategy == TREE_SPLITTER:
            sections = self._normalize_tree_sections(raw, request, text)
        elif self.manifest.strategy == PEG_DOCUMENT:
            sections = self._normalize_peg_sections(raw, request, text)
        elif self.manifest.strategy == FALLBACK_CHUNKER:
            sections = self._normalize_fallback_sections(raw, request, text)
        else:
            raise RuntimeError(f"Unsupported provider strategy: {self.manifest.strategy}")
        return ProviderResult(
            provider_id=self.manifest.provider_id,
            provider_kind=self.manifest.provider_kind,
            provider_version=self.manifest.version,
            strategy_used=self.manifest.strategy,
            status="ok",
            warnings=[],
            sections=sections,
        )

    def _make_section(
        self,
        request: ProviderRequest,
        *,
        ordinal: int,
        parent_section_id: str | None,
        depth: int,
        section_kind: str,
        anchor_path: str,
        title: str,
        exact_text: str,
        char_start: int,
        char_end: int,
        source_span: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> ProviderSection:
        return ProviderSection(
            section_id=f"{request.request_id}:section:{ordinal}",
            parent_section_id=parent_section_id,
            ordinal=ordinal,
            depth=max(1, depth),
            section_kind=section_kind,
            anchor_path=anchor_path,
            title=title[:160] or f"section-{ordinal}",
            summary=summarize_text(exact_text),
            exact_text=exact_text,
            char_start=char_start,
            char_end=char_end,
            source_span=source_span,
            metadata=dict(metadata or {}),
        )

    def _normalize_tree_sections(self, raw: Any, request: ProviderRequest, text: str) -> list[ProviderSection]:
        chunks = raw.get("chunks", []) if isinstance(raw, dict) and "chunks" in raw else raw
        if not isinstance(chunks, list):
            raise RuntimeError(f"Unsupported tree provider payload for {self.manifest.provider_id}: {type(raw).__name__}")
        sections: list[ProviderSection] = []
        for ordinal, chunk in enumerate(chunks, start=1):
            if not isinstance(chunk, dict):
                continue
            start_line = None
            end_line = None
            if "start" in chunk and "end" in chunk:
                start_line = int(chunk["start"]) + 1
                end_line = int(chunk["end"]) + 1
            elif "start_line" in chunk and "end_line" in chunk:
                raw_start = int(chunk["start_line"])
                raw_end = int(chunk["end_line"])
                start_line = raw_start + 1 if raw_start == 0 else raw_start
                end_line = raw_end + 1 if raw_end == 0 else raw_end
            if start_line is None or end_line is None:
                continue
            char_start, char_end = char_range_from_lines(text, start_line, end_line)
            exact_text = str(chunk.get("text") or text[char_start:char_end])
            title = str(chunk.get("name") or chunk.get("chunk_type") or f"section-{ordinal}")
            anchor = f"tree/{slugify(title)}"
            sections.append(
                self._make_section(
                    request,
                    ordinal=ordinal,
                    parent_section_id=None,
                    depth=1,
                    section_kind=str(chunk.get("chunk_type", "tree_chunk")),
                    anchor_path=anchor,
                    title=title,
                    exact_text=exact_text,
                    char_start=char_start,
                    char_end=char_end,
                    source_span={"start_line": start_line, "end_line": end_line},
                    metadata={"logical_path": request.logical_path},
                )
            )
        return sections

    def _normalize_peg_sections(self, raw: Any, request: ProviderRequest, text: str) -> list[ProviderSection]:
        sections: list[ProviderSection] = []
        if isinstance(raw, list) and raw and isinstance(raw[0], str):
            search_start = 0
            for ordinal, chunk in enumerate(raw, start=1):
                lookup_start = max(0, search_start - min(len(chunk), request.overlap_chars))
                char_start = text.find(chunk, lookup_start)
                if char_start < 0:
                    char_start = text.find(chunk)
                if char_start < 0:
                    char_start = search_start
                char_end = min(len(text), char_start + len(chunk))
                search_start = char_end
                title = chunk.splitlines()[0].strip() if chunk.strip() else f"section-{ordinal}"
                title = title.lstrip("#").strip() if title.startswith("#") else title
                sections.append(
                    self._make_section(
                        request,
                        ordinal=ordinal,
                        parent_section_id=None,
                        depth=1,
                        section_kind="prose_chunk",
                        anchor_path=f"prose/{ordinal}",
                        title=title or f"section-{ordinal}",
                        exact_text=chunk,
                        char_start=char_start,
                        char_end=char_end,
                        source_span={"kind": "paragraph_window", "index": ordinal},
                        metadata={"logical_path": request.logical_path},
                    )
                )
            return sections

        chunks = raw if isinstance(raw, list) else []
        for ordinal, chunk in enumerate(chunks, start=1):
            if not isinstance(chunk, dict):
                continue
            raw_start = int(chunk.get("line_start", chunk.get("start", 0)))
            raw_end = int(chunk.get("line_end", chunk.get("end", raw_start)))
            start_line = raw_start + 1
            end_line = raw_end + 1
            char_start, char_end = char_range_from_lines(text, start_line, end_line)
            exact_text = str(chunk.get("text") or text[char_start:char_end])
            heading_path = [str(part) for part in chunk.get("heading_path", []) if str(part).strip()]
            title = heading_path[-1] if heading_path else (exact_text.strip().splitlines()[0] if exact_text.strip() else f"section-{ordinal}")
            anchor_suffix = "/".join(slugify(part) for part in heading_path) if heading_path else str(ordinal)
            sections.append(
                self._make_section(
                    request,
                    ordinal=ordinal,
                    parent_section_id=None,
                    depth=max(1, len(heading_path) or 1),
                    section_kind="document_section",
                    anchor_path=f"prose/{anchor_suffix}",
                    title=title,
                    exact_text=exact_text,
                    char_start=char_start,
                    char_end=char_end,
                    source_span={"start_line": start_line, "end_line": end_line},
                    metadata={"logical_path": request.logical_path, "heading_path": heading_path},
                )
            )
        return sections

    def _normalize_fallback_sections(self, raw: Any, request: ProviderRequest, text: str) -> list[ProviderSection]:
        windows = raw if isinstance(raw, list) else []
        sections: list[ProviderSection] = []
        for ordinal, window in enumerate(windows, start=1):
            if not isinstance(window, dict):
                continue
            start_line = int(window.get("line_start", window.get("start", 0))) + 1
            end_line = int(window.get("line_end", window.get("end", start_line - 1))) + 1
            char_start, char_end = char_range_from_lines(text, start_line, end_line)
            exact_text = str(window.get("text") or text[char_start:char_end])
            sections.append(
                self._make_section(
                    request,
                    ordinal=ordinal,
                    parent_section_id=None,
                    depth=1,
                    section_kind="line_chunk",
                    anchor_path=f"lines/{start_line}-{end_line}",
                    title=f"Lines {start_line}-{end_line}",
                    exact_text=exact_text,
                    char_start=char_start,
                    char_end=char_end,
                    source_span={"start_line": start_line, "end_line": end_line},
                    metadata={"logical_path": request.logical_path},
                )
            )
        return sections


def default_provider_manifests() -> list[ProviderManifest]:
    tree_runtime_available = _tree_sitter_runtime_available()
    tree_extensions = sorted(
        {
            ".py",
            ".js",
            ".jsx",
            ".ts",
            ".tsx",
            ".java",
            ".go",
            ".rs",
            ".c",
            ".cpp",
            ".cxx",
            ".cc",
            ".h",
            ".hpp",
            ".hxx",
            ".cs",
            ".rb",
            ".php",
            ".swift",
            ".kt",
            ".kts",
            ".scala",
            ".sh",
            ".bash",
            ".zsh",
            ".json",
            ".yaml",
            ".yml",
            ".toml",
            ".html",
            ".htm",
            ".css",
            ".xml",
            ".md",
            ".markdown",
        }
    )
    return [
        ProviderManifest(
            provider_id="python_ast_provider",
            schema_version="1.0",
            provider_kind="python_provider",
            strategy=TREE_SPLITTER,
            priority=120,
            entrypoint="src.core.reference_library.adapters.reference_python_ast_chunker_ms:ReferencePythonAstChunkerMS.chunk_python_ast",
            supported_extensions=[".py"],
            supported_media_types=["text/x-python"],
            healthcheck="src.core.reference_library.adapters.reference_python_ast_chunker_ms:ReferencePythonAstChunkerMS.get_health",
            timeout_sec=15,
            enabled=True,
            version="1.0.0",
        ),
        ProviderManifest(
            provider_id=TREE_SITTER_PROVIDER_ID,
            schema_version="1.0",
            provider_kind="microservice_provider",
            strategy=TREE_SPLITTER,
            priority=110,
            entrypoint="src.core.reference_library.adapters.reference_tree_sitter_provider:ReferenceTreeSitterProvider.parse",
            supported_extensions=tree_extensions,
            supported_media_types=[
                "text/markdown",
                "text/html",
                "text/css",
                "application/json",
                "application/xml",
                "application/yaml",
                "application/toml",
            ],
            healthcheck="src.core.reference_library.adapters.reference_tree_sitter_provider:ReferenceTreeSitterProvider.get_health",
            timeout_sec=20,
            enabled=tree_runtime_available,
            version="1.0.0",
        ),
        ProviderManifest(
            provider_id="prose_document_provider",
            schema_version="1.0",
            provider_kind="microservice_provider",
            strategy=PEG_DOCUMENT,
            priority=70,
            entrypoint="src.core.reference_library.adapters.reference_prose_chunker_ms:ReferenceProseChunkerMS.chunk_prose",
            supported_extensions=sorted({".txt", ".rst", ".adoc", ".text"}),
            supported_media_types=["text/plain", "text/markdown", "text/x-rst"],
            healthcheck="src.core.reference_library.adapters.reference_prose_chunker_ms:ReferenceProseChunkerMS.get_health",
            timeout_sec=15,
            enabled=True,
            version="1.0.0",
        ),
        ProviderManifest(
            provider_id="readable_text_fallback_provider",
            schema_version="1.0",
            provider_kind="microservice_provider",
            strategy=FALLBACK_CHUNKER,
            priority=10,
            entrypoint="src.core.reference_library.adapters.reference_tree_sitter_strategy_ms:ReferenceTreeSitterStrategyMS.fallback_line_windows",
            supported_extensions=[],
            supported_media_types=["text/plain"],
            healthcheck="src.core.reference_library.adapters.reference_tree_sitter_strategy_ms:ReferenceTreeSitterStrategyMS.get_health",
            timeout_sec=15,
            enabled=True,
            version="1.0.0",
        ),
    ]


class ProviderRegistry:
    """Manifest-driven adapter registry for reference parsing providers."""

    def __init__(self, manifest_path: str | Path | None = None) -> None:
        self.manifest_path = Path(manifest_path).resolve() if manifest_path else None
        self.providers = self._build_providers()
        self._provider_map = {provider.manifest.provider_id: provider for provider in self.providers}

    def _load_manifest_models(self) -> list[ProviderManifest]:
        if self.manifest_path and self.manifest_path.exists():
            try:
                payload = json.loads(self.manifest_path.read_text(encoding="utf-8"))
                rows = payload.get("providers", [])
                if rows:
                    manifests = [ProviderManifest(**row) for row in rows]
                    if any(self._looks_legacy_manifest(manifest) for manifest in manifests):
                        return default_provider_manifests()
                    return self._reconcile_loaded_manifests(manifests)
            except Exception:
                pass
        return default_provider_manifests()

    def _reconcile_loaded_manifests(self, manifests: list[ProviderManifest]) -> list[ProviderManifest]:
        defaults = {manifest.provider_id: manifest for manifest in default_provider_manifests()}
        reconciled: list[ProviderManifest] = []
        seen_ids: set[str] = set()
        for manifest in manifests:
            default_manifest = defaults.get(manifest.provider_id)
            if default_manifest is not None:
                reconciled.append(default_manifest)
            else:
                reconciled.append(self._runtime_adjusted_manifest(manifest))
            seen_ids.add(manifest.provider_id)
        for provider_id, default_manifest in defaults.items():
            if provider_id not in seen_ids:
                reconciled.append(default_manifest)
        return reconciled

    def _runtime_adjusted_manifest(self, manifest: ProviderManifest) -> ProviderManifest:
        if self._is_tree_sitter_manifest(manifest):
            return ProviderManifest(
                provider_id=manifest.provider_id,
                schema_version=manifest.schema_version,
                provider_kind=manifest.provider_kind,
                strategy=manifest.strategy,
                priority=manifest.priority,
                entrypoint=manifest.entrypoint,
                supported_extensions=list(manifest.supported_extensions),
                supported_media_types=list(manifest.supported_media_types),
                healthcheck=manifest.healthcheck,
                timeout_sec=manifest.timeout_sec,
                enabled=_tree_sitter_runtime_available(),
                version=manifest.version,
            )
        return manifest

    def _is_tree_sitter_manifest(self, manifest: ProviderManifest) -> bool:
        values = [manifest.provider_id, manifest.entrypoint, manifest.healthcheck]
        return any(TREE_SITTER_PROVIDER_ID in value for value in values if value)

    def _looks_legacy_manifest(self, manifest: ProviderManifest) -> bool:
        values = [manifest.entrypoint, manifest.healthcheck]
        for value in values:
            if not value:
                continue
            if ":" not in value:
                return True
            module_name, _ = value.split(":", 1)
            if "/" in module_name or "\\" in module_name:
                return True
        return False

    def _build_providers(self) -> list[BaseProvider]:
        providers = [EntrypointProvider(manifest) for manifest in self._load_manifest_models()]
        providers.sort(key=lambda item: item.manifest.priority, reverse=True)
        return providers

    def manifests(self) -> list[dict[str, Any]]:
        return [asdict(provider.manifest) for provider in self.providers]

    def validate(self) -> None:
        for provider in self.providers:
            if not provider.manifest.enabled:
                continue
            health = provider.health()
            if str(health.get("status", "")).lower() not in {"online", "ok"}:
                raise RuntimeError(f"Provider {provider.manifest.provider_id} is unavailable: {health}")

    def _supports(self, provider: BaseProvider, extension: str, media_type: str) -> bool:
        manifest = provider.manifest
        extensions = {item.lower() for item in manifest.supported_extensions}
        media_types = {item.lower() for item in manifest.supported_media_types}
        if extension and extension.lower() in extensions:
            return True
        if media_type and media_type.lower() in media_types:
            return True
        return False

    def _enabled_by_strategy(self, strategy: str) -> list[BaseProvider]:
        return [provider for provider in self.providers if provider.manifest.enabled and provider.manifest.strategy == strategy]

    def select(self, request: ProviderRequest, readable_text: bool) -> BaseProvider | None:
        tree_candidates = [
            provider
            for provider in self._enabled_by_strategy(TREE_SPLITTER)
            if self._supports(provider, request.extension, request.media_type)
        ]
        if tree_candidates:
            return tree_candidates[0]

        is_prose = (
            request.extension.lower() in PROSE_EXTENSIONS
            or request.media_type.lower() in {"text/markdown", "text/x-rst"}
            or (not request.extension and request.media_type.lower() == "text/plain")
        )
        if is_prose:
            peg_candidates = self._enabled_by_strategy(PEG_DOCUMENT)
            if not peg_candidates and request.extension.lower() in PROSE_EXTENSIONS:
                raise RuntimeError(f"No PEG document provider is configured for {request.logical_path}")
            if peg_candidates:
                return peg_candidates[0]

        if readable_text:
            fallback_candidates = self._enabled_by_strategy(FALLBACK_CHUNKER)
            if fallback_candidates:
                return fallback_candidates[0]

        return None

    def get(self, provider_id: str) -> BaseProvider | None:
        return self._provider_map.get(provider_id)

    def supported_tree_extensions(self) -> set[str]:
        values: set[str] = set()
        for provider in self._enabled_by_strategy(TREE_SPLITTER):
            values.update(item.lower() for item in provider.manifest.supported_extensions)
        return values

    def supports_readable_text(self, extension: str, media_type: str) -> bool:
        if extension.lower() in READABLE_TEXT_EXTENSIONS:
            return True
        if media_type.lower().startswith("text/"):
            return True
        return False
