from __future__ import annotations

import time
from pathlib import Path
from typing import Any


LANGUAGE_TIERS = {
    "deep_semantic": {
        "languages": ["python", "javascript", "typescript", "java", "go", "rust", "cpp", "c_sharp", "kotlin", "scala", "swift"],
        "max_depth": 4,
        "chunk_strategy": "hierarchical",
        "meaningful_depth": True,
    },
    "shallow_semantic": {
        "languages": ["bash", "r", "ruby", "php", "c"],
        "max_depth": 2,
        "chunk_strategy": "flat",
        "meaningful_depth": True,
    },
    "structural": {
        "languages": ["json", "yaml", "toml"],
        "max_depth": None,
        "chunk_strategy": "structural",
        "meaningful_depth": False,
    },
    "hybrid": {
        "languages": ["html", "css", "xml", "markdown"],
        "max_depth": 3,
        "chunk_strategy": "markup",
        "meaningful_depth": False,
    },
}

EXTENSION_TO_LANGUAGE = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".c": "c",
    ".cpp": "cpp",
    ".cxx": "cpp",
    ".cc": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".hxx": "cpp",
    ".cs": "c_sharp",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".scala": "scala",
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "bash",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".xml": "xml",
    ".md": "markdown",
    ".markdown": "markdown",
    ".r": "r",
    ".R": "r",
}


class ReferenceTreeSitterStrategyMS:
    """Port of the reference tree-sitter strategy microservice."""

    def __init__(self) -> None:
        self.start_time = time.time()

    def get_language_tier(self, language: str) -> dict[str, Any]:
        for tier_name, cfg in LANGUAGE_TIERS.items():
            if language in cfg["languages"]:
                output = dict(cfg)
                output["tier"] = tier_name
                return output
        return {
            "tier": "shallow_semantic",
            "languages": [],
            "max_depth": 2,
            "chunk_strategy": "flat",
            "meaningful_depth": True,
        }

    def classify_file(self, file_path: str) -> dict[str, Any]:
        language = EXTENSION_TO_LANGUAGE.get(Path(file_path).suffix.lower(), "")
        return {"language": language, "tier": self.get_language_tier(language)}

    def fallback_line_windows(self, line_count: int, max_chunk_tokens: int = 800, overlap_lines: int = 3) -> list[dict[str, int]]:
        windows: list[dict[str, int]] = []
        target_tokens = max(1, int(max_chunk_tokens))
        step_lines = max(20, target_tokens // 5)
        index = 0
        cursor = 0
        while cursor < line_count:
            end = min(cursor + step_lines, line_count)
            windows.append({"index": index, "line_start": cursor, "line_end": max(cursor, end - 1)})
            index += 1
            cursor += max(1, step_lines - max(0, int(overlap_lines)))
        return windows

    def plan_dispatch(self, file_path: str, treesitter_available: bool = True, parse_has_error: bool = False) -> dict[str, Any]:
        info = self.classify_file(file_path)
        language = info["language"]
        tier = info["tier"]
        if not treesitter_available or not language or parse_has_error:
            return {
                "mode": "fallback",
                "language": language,
                "tier": tier,
                "reason": "treesitter_unavailable_or_parse_error",
                "strategy": "line_window",
            }
        return {
            "mode": "treesitter",
            "language": language,
            "tier": tier,
            "strategy": tier["chunk_strategy"],
            "meaningful_depth": tier["meaningful_depth"],
            "max_depth": tier["max_depth"],
        }

    def get_health(self) -> dict[str, Any]:
        return {"status": "online", "uptime": time.time() - self.start_time}
