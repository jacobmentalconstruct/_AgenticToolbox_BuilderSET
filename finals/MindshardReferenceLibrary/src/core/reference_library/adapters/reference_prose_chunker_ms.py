from __future__ import annotations

import re
import time
from typing import Any


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")


class ReferenceProseChunkerMS:
    """Port of the reference prose chunker microservice."""

    def __init__(self) -> None:
        self.start_time = time.time()

    def _estimate_tokens(self, text: str) -> int:
        return max(1, len(text.split()))

    def split_on_headings(self, lines: list[str]) -> list[dict[str, Any]]:
        sections: list[dict[str, Any]] = []
        heading_stack: list[tuple[int, str]] = []
        current_start: int | None = None
        current_path: list[str] = []

        def flush(end_idx: int) -> None:
            if current_start is not None and end_idx >= current_start:
                sections.append({"start": current_start, "end": end_idx, "heading_path": list(current_path)})

        for index, line in enumerate(lines):
            match = _HEADING_RE.match(line)
            if not match:
                continue
            level = len(match.group(1))
            title = match.group(2).strip()
            flush(index - 1)
            heading_stack[:] = [(old_level, text) for old_level, text in heading_stack if old_level < level]
            heading_stack.append((level, title))
            current_path = [text for _, text in heading_stack]
            current_start = index

        flush(len(lines) - 1)
        return sections

    def split_on_paragraphs(self, lines: list[str]) -> list[dict[str, Any]]:
        sections: list[dict[str, Any]] = []
        start: int | None = None
        for index, line in enumerate(lines):
            if line.strip():
                if start is None:
                    start = index
                continue
            if start is not None:
                sections.append({"start": start, "end": index - 1, "heading_path": []})
                start = None
        if start is not None:
            sections.append({"start": start, "end": len(lines) - 1, "heading_path": []})
        return sections

    def chunk_prose(
        self,
        text: str,
        is_markdown: bool = True,
        max_tokens: int = 800,
        overlap_lines: int = 2,
    ) -> list[dict[str, Any]]:
        lines = text.splitlines()
        sections = self.split_on_headings(lines) if is_markdown else self.split_on_paragraphs(lines)
        if not sections and lines:
            sections = [{"start": 0, "end": len(lines) - 1, "heading_path": []}]

        chunks: list[dict[str, Any]] = []
        for section in sections:
            lo = int(section["start"])
            hi = int(section["end"])
            section_lines = lines[lo : hi + 1]
            token_count = self._estimate_tokens("\n".join(section_lines))
            if token_count <= max_tokens:
                chunks.append(
                    {
                        "line_start": lo,
                        "line_end": hi,
                        "heading_path": list(section.get("heading_path", [])),
                        "text": "\n".join(section_lines),
                        "tokens": token_count,
                    }
                )
                continue

            cursor = lo
            while cursor <= hi:
                end = cursor
                tokens = 0
                while end <= hi:
                    tokens += self._estimate_tokens(lines[end])
                    if tokens > max_tokens and end > cursor:
                        break
                    end += 1
                chunk_end = min(end - 1, hi)
                chunk_lines = lines[cursor : chunk_end + 1]
                chunks.append(
                    {
                        "line_start": cursor,
                        "line_end": chunk_end,
                        "heading_path": list(section.get("heading_path", [])),
                        "text": "\n".join(chunk_lines),
                        "tokens": self._estimate_tokens("\n".join(chunk_lines)),
                    }
                )
                next_cursor = chunk_end + 1 - max(0, int(overlap_lines))
                cursor = next_cursor if next_cursor > cursor else cursor + 1

        return chunks

    def get_health(self) -> dict[str, Any]:
        return {"status": "online", "uptime": time.time() - self.start_time}
