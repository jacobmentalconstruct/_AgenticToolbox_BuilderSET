from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from src.core.reference_library.adapters.reference_language_tier_ms import ReferenceLanguageTierMS
from src.core.reference_library.adapters.reference_tree_sitter_query_registry_ms import ReferenceTreeSitterQueryRegistryMS
from src.core.reference_library.adapters.reference_tree_sitter_strategy_ms import ReferenceTreeSitterStrategyMS
from src.core.reference_library.provider_contracts import ProviderRequest, ProviderResult, ProviderSection, TREE_SPLITTER
from src.core.reference_library.utils import slugify, summarize_text


class ReferenceTreeSitterProvider:
    """Tree-sitter-backed provider adapter for code, structured docs, and markup."""

    def __init__(self) -> None:
        self.start_time = time.time()
        self.language_tier = ReferenceLanguageTierMS()
        self.query_registry = ReferenceTreeSitterQueryRegistryMS()
        self.strategy = ReferenceTreeSitterStrategyMS()

    def get_health(self) -> dict[str, Any]:
        try:
            from tree_sitter_language_pack import get_parser
        except Exception as exc:
            return {"status": "offline", "reason": str(exc), "provider": "tree_sitter_language_pack"}

        healthy = 0
        for language in ("python", "javascript", "typescript", "json", "yaml", "toml", "html", "css", "xml", "bash", "markdown"):
            try:
                get_parser(language)
                healthy += 1
            except Exception:
                continue
        return {
            "status": "online" if healthy else "offline",
            "uptime": time.time() - self.start_time,
            "runtime": "tree_sitter_language_pack",
            "language_count": healthy,
        }

    def parse(self, request: ProviderRequest, text: str) -> ProviderResult:
        from tree_sitter import Query, QueryCursor
        from tree_sitter_language_pack import get_language, get_parser

        language = self._language_for_request(request)
        if not language:
            raise RuntimeError(f"No tree-sitter language mapping is available for {request.logical_path}")

        parser = get_parser(language)
        tree = parser.parse(text.encode("utf-8"))
        root = tree.root_node
        byte_to_char = self._byte_to_char_map(text)
        warnings: list[str] = []
        if bool(getattr(root, "has_error", False)):
            warnings.append("tree_sitter_parse_contains_error_nodes")

        sections = self._query_sections(
            language=language,
            root=root,
            text=text,
            request=request,
            byte_to_char=byte_to_char,
            query_cls=Query,
            query_cursor_cls=QueryCursor,
            language_obj=get_language(language),
        )
        if language == "markdown":
            sections = self._markdown_sections(root, text, request, byte_to_char) or sections
        if not sections:
            sections = self._structural_sections(language, root, text, request, byte_to_char)
        if not sections:
            sections = [self._whole_document_section(request, text)]

        return ProviderResult(
            provider_id="",
            provider_kind="microservice_provider",
            provider_version="1.0.0",
            strategy_used=TREE_SPLITTER,
            status="ok",
            warnings=warnings,
            sections=sections,
        )

    def _language_for_request(self, request: ProviderRequest) -> str:
        extension = request.extension.lower()
        if extension in {".md", ".markdown"}:
            return "markdown"
        language = self.query_registry.language_for_file(request.logical_path)
        if language:
            return language
        return self.language_tier.language_for_file(request.logical_path)

    def _byte_to_char_map(self, text: str) -> list[int]:
        encoded = text.encode("utf-8")
        mapping = [0] * (len(encoded) + 1)
        byte_cursor = 0
        for char_index, character in enumerate(text):
            encoded_char = character.encode("utf-8")
            for _ in encoded_char:
                mapping[byte_cursor] = char_index
                byte_cursor += 1
            mapping[byte_cursor] = char_index + 1
        while byte_cursor < len(encoded):
            mapping[byte_cursor] = len(text)
            byte_cursor += 1
        mapping[len(encoded)] = len(text)
        return mapping

    def _range_for_node(self, node, text: str, byte_to_char: list[int]) -> tuple[int, int, str]:
        char_start = byte_to_char[node.start_byte]
        char_end = byte_to_char[node.end_byte]
        return char_start, char_end, text[char_start:char_end]

    def _node_text(self, node, text: str, byte_to_char: list[int]) -> str:
        return self._range_for_node(node, text, byte_to_char)[2]

    def _clean_heading(self, raw: str) -> str:
        title = raw.strip().replace("\r", "")
        while title.startswith("#"):
            title = title[1:].lstrip()
        return title or "section"

    def _make_section(
        self,
        *,
        request: ProviderRequest,
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

    def _query_sections(
        self,
        *,
        language: str,
        root,
        text: str,
        request: ProviderRequest,
        byte_to_char: list[int],
        query_cls,
        query_cursor_cls,
        language_obj,
    ) -> list[ProviderSection]:
        queries = self.query_registry.get_query_set(language)
        rows: list[tuple[int, str, str, int, int, str]] = []
        seen_ranges: set[tuple[int, int, str]] = set()

        for capture_kind, query_text in (
            ("import", queries.get("import_query", "")),
            ("class", queries.get("class_query", "")),
            ("function", queries.get("function_query", "")),
        ):
            if not query_text:
                continue
            query = query_cls(language_obj, query_text)
            cursor = query_cursor_cls(query)
            for _, capture_map in cursor.matches(root):
                primary_nodes = capture_map.get(capture_kind) or capture_map.get("method") or capture_map.get("struct") or capture_map.get("type")
                if not primary_nodes:
                    continue
                node = primary_nodes[0]
                char_start, char_end, exact_text = self._range_for_node(node, text, byte_to_char)
                if not exact_text.strip():
                    continue
                name_nodes = capture_map.get("name", [])
                title = self._node_text(name_nodes[0], text, byte_to_char).strip() if name_nodes else node.type
                key = (char_start, char_end, capture_kind)
                if key in seen_ranges:
                    continue
                seen_ranges.add(key)
                rows.append((char_start, capture_kind, title, char_start, char_end, exact_text))

        rows.sort(key=lambda item: (item[0], item[1], item[2]))
        sections: list[ProviderSection] = []
        for ordinal, (_, capture_kind, title, char_start, char_end, exact_text) in enumerate(rows, start=1):
            anchor_title = slugify(title or capture_kind)
            sections.append(
                self._make_section(
                    request=request,
                    ordinal=ordinal,
                    parent_section_id=None,
                    depth=1,
                    section_kind=f"{capture_kind}_definition" if capture_kind != "import" else "import_block",
                    anchor_path=f"{language}/{capture_kind}/{anchor_title}",
                    title=title or capture_kind,
                    exact_text=exact_text,
                    char_start=char_start,
                    char_end=char_end,
                    source_span={"kind": "tree_query", "language": language, "capture": capture_kind},
                    metadata={"language": language, "query_capture": capture_kind},
                )
            )
        return sections

    def _markdown_sections(self, root, text: str, request: ProviderRequest, byte_to_char: list[int]) -> list[ProviderSection]:
        collected: list[tuple[tuple[str, ...], Any, Any | None]] = []

        def walk(node, path: list[str], parent_section_node) -> None:
            for child in node.children:
                if child.type != "section":
                    continue
                heading_node = next((grand for grand in child.children if grand.type in {"atx_heading", "setext_heading"}), None)
                if heading_node is None:
                    walk(child, path, parent_section_node)
                    continue
                title = self._clean_heading(self._node_text(heading_node, text, byte_to_char))
                next_path = path + [title]
                collected.append((tuple(next_path), child, parent_section_node))
                walk(child, next_path, child)

        walk(root, [], None)
        sections: list[ProviderSection] = []
        section_ids_by_node: dict[int, str] = {}
        for ordinal, (path, node, parent_node) in enumerate(collected, start=1):
            char_start, char_end, exact_text = self._range_for_node(node, text, byte_to_char)
            parent_section_id = section_ids_by_node.get(id(parent_node)) if parent_node is not None else None
            section = self._make_section(
                request=request,
                ordinal=ordinal,
                parent_section_id=parent_section_id,
                depth=len(path),
                section_kind="markdown_section",
                anchor_path="markdown/" + "/".join(slugify(part) for part in path),
                title=path[-1],
                exact_text=exact_text,
                char_start=char_start,
                char_end=char_end,
                source_span={"kind": "tree_markdown_section", "language": "markdown"},
                metadata={"language": "markdown", "heading_path": list(path)},
            )
            section_ids_by_node[id(node)] = section.section_id
            sections.append(section)
        return sections

    def _structural_sections(self, language: str, root, text: str, request: ProviderRequest, byte_to_char: list[int]) -> list[ProviderSection]:
        classification = self.strategy.classify_file(request.logical_path)
        tier = dict(classification.get("tier", {}) or {})
        max_depth = tier.get("max_depth", 3)
        max_depth = 3 if max_depth is None else max(1, int(max_depth))
        sections: list[ProviderSection] = []
        trivial_types = {"comment", "ERROR"}

        def walk(node, *, depth: int, parent_section_id: str | None, path: list[str]) -> None:
            if depth > max_depth:
                return
            index = 0
            for child in node.named_children:
                if child.type in trivial_types:
                    continue
                char_start, char_end, exact_text = self._range_for_node(child, text, byte_to_char)
                if not exact_text.strip():
                    continue
                index += 1
                title = exact_text.strip().splitlines()[0][:120] or child.type
                next_path = path + [child.type, str(index)]
                section = self._make_section(
                    request=request,
                    ordinal=len(sections) + 1,
                    parent_section_id=parent_section_id,
                    depth=depth,
                    section_kind=child.type,
                    anchor_path=f"{language}/" + "/".join(next_path),
                    title=title,
                    exact_text=exact_text,
                    char_start=char_start,
                    char_end=char_end,
                    source_span={"kind": "tree_structural", "language": language, "node_type": child.type},
                    metadata={"language": language, "node_type": child.type},
                )
                sections.append(section)
                walk(child, depth=depth + 1, parent_section_id=section.section_id, path=next_path)

        walk(root, depth=1, parent_section_id=None, path=[])
        return sections

    def _whole_document_section(self, request: ProviderRequest, text: str) -> ProviderSection:
        title = Path(request.logical_path).name or "document"
        return ProviderSection(
            section_id=f"{request.request_id}:section:1",
            parent_section_id=None,
            ordinal=1,
            depth=1,
            section_kind="document",
            anchor_path=f"document/{slugify(title)}",
            title=title,
            summary=summarize_text(text),
            exact_text=text,
            char_start=0,
            char_end=len(text),
            source_span={"kind": "whole_document"},
            metadata={"logical_path": request.logical_path},
        )
