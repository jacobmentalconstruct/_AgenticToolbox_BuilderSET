from __future__ import annotations

import json
import mimetypes
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path


PROSE_EXTENSIONS = {
    ".md",
    ".markdown",
    ".txt",
    ".rst",
    ".adoc",
    ".text",
}

READABLE_TEXT_EXTENSIONS = PROSE_EXTENSIONS | {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".env",
    ".html",
    ".css",
    ".scss",
    ".xml",
    ".csv",
    ".tsv",
    ".sql",
    ".log",
    ".sh",
    ".ps1",
    ".bat",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:24]}"


def slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return cleaned or "item"


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def detect_media_type(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(str(path))
    if guessed:
        return guessed
    suffix = path.suffix.lower()
    if suffix in {".md", ".markdown"}:
        return "text/markdown"
    if suffix in {".yml", ".yaml"}:
        return "application/yaml"
    if suffix in {".toml"}:
        return "application/toml"
    if suffix in {".csv"}:
        return "text/csv"
    if suffix in {".tsv"}:
        return "text/tab-separated-values"
    if suffix in READABLE_TEXT_EXTENSIONS:
        return "text/plain"
    return "application/octet-stream"


def looks_like_text(blob: bytes, media_type: str = "", extension: str = "") -> bool:
    if media_type.startswith("text/"):
        return True
    if extension.lower() in READABLE_TEXT_EXTENSIONS:
        return True
    if not blob:
        return True
    if b"\x00" in blob[:4096]:
        return False
    sample = blob[:4096]
    try:
        sample.decode("utf-8")
        return True
    except UnicodeDecodeError:
        try:
            sample.decode("utf-8-sig")
            return True
        except UnicodeDecodeError:
            return False


def decode_text(blob: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "utf-16", "latin-1"):
        try:
            return blob.decode(encoding)
        except UnicodeDecodeError:
            continue
    return blob.decode("utf-8", errors="replace")


def normalize_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def line_offsets(text: str) -> list[int]:
    offsets = [0]
    cursor = 0
    for line in text.splitlines(keepends=True):
        cursor += len(line)
        offsets.append(cursor)
    if len(offsets) == 1:
        offsets.append(0)
    return offsets


def char_range_from_lines(text: str, start_line: int, end_line: int) -> tuple[int, int]:
    offsets = line_offsets(text)
    safe_start = max(1, start_line)
    safe_end = max(safe_start, end_line)
    start_index = offsets[min(safe_start - 1, len(offsets) - 1)]
    end_index = offsets[min(safe_end, len(offsets) - 1)]
    return start_index, end_index


def summarize_text(text: str, limit: int = 140) -> str:
    single = " ".join(part.strip() for part in text.strip().splitlines() if part.strip())
    if len(single) <= limit:
        return single
    return single[: max(0, limit - 3)].rstrip() + "..."


def trim_excerpt(text: str, char_start: int | None = None, char_end: int | None = None, max_chars: int = 1200) -> tuple[str, int, int]:
    start = max(0, char_start or 0)
    end = len(text) if char_end is None else min(len(text), max(start, char_end))
    snippet = text[start:end]
    if len(snippet) <= max_chars:
        return snippet, start, end
    clipped = snippet[:max_chars]
    return clipped, start, start + len(clipped)


def child_logical_path(parent_logical_path: str | None, name: str) -> str:
    if not parent_logical_path:
        return name
    return f"{parent_logical_path}/{name}"
