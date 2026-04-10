from __future__ import annotations

import ast
import time
from typing import Any


class ReferencePythonAstChunkerMS:
    """Port of the reference Python AST chunker microservice."""

    def __init__(self) -> None:
        self.start_time = time.time()

    def _node_range(self, node: ast.AST) -> dict[str, int]:
        return {
            "start": max(0, int(getattr(node, "lineno", 1)) - 1),
            "end": max(0, int(getattr(node, "end_lineno", getattr(node, "lineno", 1))) - 1),
        }

    def collect_import_block(self, source_text: str) -> dict[str, int]:
        tree = ast.parse(source_text)
        lines: list[int] = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                node_range = self._node_range(node)
                lines.extend(range(node_range["start"], node_range["end"] + 1))
        if not lines:
            return {}
        return {"start": min(lines), "end": max(lines)}

    def chunk_python_ast(self, source_text: str, file_name: str = "module.py") -> list[dict[str, Any]]:
        try:
            tree = ast.parse(source_text)
        except SyntaxError:
            return self.fallback_line_windows(source_text)

        chunks: list[dict[str, Any]] = []
        import_block = self.collect_import_block(source_text)
        if import_block:
            chunks.append({"chunk_type": "import_block", "name": "imports", **import_block})

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                chunks.append({"chunk_type": "function_def", "name": node.name, **self._node_range(node)})
            elif isinstance(node, ast.ClassDef):
                chunks.append({"chunk_type": "class_def", "name": node.name, **self._node_range(node)})
                for child in ast.iter_child_nodes(node):
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        chunks.append(
                            {
                                "chunk_type": "method_def",
                                "name": f"{node.name}.{child.name}",
                                **self._node_range(child),
                            }
                        )

        doc = ast.get_docstring(tree)
        if doc:
            for node in ast.iter_child_nodes(tree):
                if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
                    chunks.insert(
                        0,
                        {
                            "chunk_type": "module_summary",
                            "name": f"{file_name} (module)",
                            **self._node_range(node),
                        },
                    )
                    break

        return chunks or self.fallback_line_windows(source_text)

    def fallback_line_windows(self, source_text: str, window_lines: int = 120) -> list[dict[str, int]]:
        lines = source_text.splitlines()
        chunks: list[dict[str, int]] = []
        start = 0
        while start < len(lines):
            end = min(start + max(1, int(window_lines)) - 1, len(lines) - 1)
            chunks.append({"chunk_type": "line_window", "start": start, "end": end})
            start = end + 1
        return chunks

    def get_health(self) -> dict[str, Any]:
        return {"status": "online", "uptime": time.time() - self.start_time}
