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


class ReferenceLanguageTierMS:
    """Port of the reference language/tier microservice."""

    def __init__(self) -> None:
        self.start_time = time.time()

    def language_for_file(self, file_path: str) -> str:
        return EXTENSION_TO_LANGUAGE.get(Path(file_path).suffix, "")

    def get_language_tier(self, language: str) -> dict[str, Any]:
        for tier_name, config in LANGUAGE_TIERS.items():
            if language in config["languages"]:
                payload = dict(config)
                payload["tier"] = tier_name
                return payload
        return {
            "tier": "shallow_semantic",
            "languages": [],
            "max_depth": 2,
            "chunk_strategy": "flat",
            "meaningful_depth": True,
        }

    def classify_file(self, file_path: str) -> dict[str, Any]:
        language = self.language_for_file(file_path)
        tier = self.get_language_tier(language) if language else self.get_language_tier("")
        return {
            "file_path": file_path,
            "extension": Path(file_path).suffix,
            "language": language,
            "tier": tier["tier"],
            "chunk_strategy": tier["chunk_strategy"],
            "meaningful_depth": tier["meaningful_depth"],
            "max_depth": tier["max_depth"],
        }

    def treesitter_supported(self, language: str) -> bool:
        try:
            from tree_sitter_language_pack import get_parser
        except Exception:
            return False
        try:
            get_parser(language)
        except Exception:
            return False
        return True

    def get_health(self) -> dict[str, Any]:
        return {"status": "online", "uptime": time.time() - self.start_time}
