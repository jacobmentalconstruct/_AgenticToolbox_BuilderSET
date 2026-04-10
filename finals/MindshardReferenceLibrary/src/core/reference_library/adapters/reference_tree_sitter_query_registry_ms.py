from __future__ import annotations

import time
from pathlib import Path
from typing import Any


FUNCTION_QUERIES = {
    "python": "(function_definition name: (identifier) @name) @function",
    "javascript": "(function_declaration name: (identifier) @name) @function",
    "typescript": "(function_declaration name: (identifier) @name) @function",
    "java": "(method_declaration name: (identifier) @name) @method",
    "go": "(function_declaration name: (identifier) @name) @function",
    "rust": "(function_item name: (identifier) @name) @function",
    "c": "(function_definition declarator: (function_declarator declarator: (identifier) @name)) @function",
    "cpp": "(function_definition declarator: (function_declarator declarator: (identifier) @name)) @function",
    "c_sharp": "(method_declaration name: (identifier) @name) @method",
    "ruby": "(method name: (identifier) @name) @method",
    "php": "(function_definition name: (name) @name) @function",
    "swift": "(function_declaration name: (simple_identifier) @name) @function",
    "kotlin": "(function_declaration (simple_identifier) @name) @function",
    "scala": "(function_definition name: (identifier) @name) @function",
    "bash": "(function_definition name: (word) @name) @function",
}

CLASS_QUERIES = {
    "python": "(class_definition name: (identifier) @name) @class",
    "javascript": "(class_declaration name: (identifier) @name) @class",
    "typescript": "(class_declaration name: (type_identifier) @name) @class",
    "java": "(class_declaration name: (identifier) @name) @class",
    "go": "(type_declaration (type_spec name: (type_identifier) @name)) @type",
    "rust": "(struct_item name: (type_identifier) @name) @struct",
    "c": "(struct_specifier name: (type_identifier) @name) @struct",
    "cpp": "(class_specifier name: (type_identifier) @name) @class",
    "c_sharp": "(class_declaration name: (identifier) @name) @class",
    "ruby": "(class name: (constant) @name) @class",
    "php": "(class_declaration name: (name) @name) @class",
    "swift": "(class_declaration name: (type_identifier) @name) @class",
    "kotlin": "(class_declaration (type_identifier) @name) @class",
    "scala": "(class_definition name: (identifier) @name) @class",
}

IMPORT_QUERIES = {
    "python": "(import_statement) @import (import_from_statement) @import",
    "javascript": "(import_statement) @import",
    "typescript": "(import_statement) @import",
    "java": "(import_declaration) @import",
    "go": "(import_declaration) @import",
    "rust": "(use_declaration) @import",
    "c": "(preproc_include) @import",
    "cpp": "(preproc_include) @import",
    "c_sharp": "(using_directive) @import",
    "ruby": "(call method: (identifier) @method (#match? @method \"^(require|require_relative|load|import)$\")) @import",
    "php": "(namespace_use_declaration) @import",
    "swift": "(import_declaration) @import",
    "kotlin": "(import_header) @import",
    "scala": "(import_declaration) @import",
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


class ReferenceTreeSitterQueryRegistryMS:
    """Port of the reference tree-sitter query registry microservice."""

    def __init__(self) -> None:
        self.start_time = time.time()

    def language_for_file(self, file_path: str) -> str:
        return EXTENSION_TO_LANGUAGE.get(Path(file_path).suffix.lower(), "")

    def get_query_set(self, language: str) -> dict[str, str]:
        return {
            "function_query": FUNCTION_QUERIES.get(language, ""),
            "class_query": CLASS_QUERIES.get(language, ""),
            "import_query": IMPORT_QUERIES.get(language, ""),
        }

    def list_languages(self) -> list[str]:
        return sorted(set(FUNCTION_QUERIES) | set(CLASS_QUERIES) | set(IMPORT_QUERIES) | {"markdown", "json", "yaml", "toml", "html", "css", "xml"})

    def is_language_supported(self, extension: str) -> bool:
        return extension.lower() in EXTENSION_TO_LANGUAGE

    def get_health(self) -> dict[str, Any]:
        return {"status": "online", "uptime": time.time() - self.start_time, "language_count": len(self.list_languages())}
