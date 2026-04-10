"""Auto-generated MCP server for KnowledgeCartridgeBuilder.

Reads SERVICE_SPECS from backend.py and exposes every endpoint as an MCP tool.
Symmetry principle: same functions the UI calls, now available to agents.

Usage:
    python mcp_server.py          # stdio transport (for Claude Code / .mcp.json)
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# --- Bootstrap: match app.py's path setup ---
APP_DIR = Path(__file__).resolve().parent
_settings = json.loads((APP_DIR / "settings.json").read_text(encoding="utf-8"))
for _p in [_settings.get("canonical_import_root", "")] + list(_settings.get("compat_paths", [])):
    if not _p:
        continue
    _resolved = str(APP_DIR / _p) if not os.path.isabs(_p) else _p
    if _resolved not in sys.path:
        sys.path.insert(0, _resolved)

from fastmcp import FastMCP
from backend import BackendRuntime, SERVICE_SPECS

mcp = FastMCP("KnowledgeCartridgeBuilder")
_runtime = BackendRuntime()


def _fmt(obj: object) -> str:
    """JSON-serialize any result for MCP transport."""
    return json.dumps(obj, indent=2, default=str)


# ---------------------------------------------------------------------------
# Meta tools
# ---------------------------------------------------------------------------

@mcp.tool
def list_services() -> str:
    """List all services available in this app and their endpoints."""
    summary = []
    for spec in SERVICE_SPECS:
        summary.append({
            "class_name": spec["class_name"],
            "service_name": spec["service_name"],
            "description": spec["description"],
            "endpoints": [
                {"method": ep["method_name"], "description": ep["description"]}
                for ep in spec.get("endpoints", [])
            ],
        })
    return _fmt(summary)


@mcp.tool
def app_health() -> str:
    """Return health report for all instantiated services."""
    return _fmt(_runtime.health())


# ---------------------------------------------------------------------------
# ScoutMS - Discovery
# ---------------------------------------------------------------------------

@mcp.tool
def scan_directory(root_path: str, web_depth: int = 0) -> str:
    """Recursively scan a directory or crawl a URL. Returns a file/folder tree."""
    result = _runtime.call("ScoutMS", "scan_directory", root_path=root_path, web_depth=web_depth)
    return _fmt(result)


@mcp.tool
def flatten_tree(tree_node: str) -> str:
    """Flatten a hierarchical tree node into a simple path list. tree_node = JSON object."""
    node = json.loads(tree_node) if isinstance(tree_node, str) else tree_node
    result = _runtime.call("ScoutMS", "flatten_tree", tree_node=node)
    return _fmt(result)


# ---------------------------------------------------------------------------
# ChunkingRouterMS + Specialist Chunkers
# ---------------------------------------------------------------------------

@mcp.tool
def chunk_file(text: str, filename: str, max_size: int = 1000, overlap: int = 100) -> str:
    """Route text to the right chunker by filename extension. Returns structured chunks."""
    result = _runtime.call("ChunkingRouterMS", "chunk_file", text=text, filename=filename, max_size=max_size, overlap=overlap)
    return _fmt(result)


@mcp.tool
def chunk_python(content: str) -> str:
    """AST-based Python chunking. Returns functions, classes, and their line ranges."""
    result = _runtime.call("PythonChunkerMS", "chunk", content=content)
    return _fmt(result)


@mcp.tool
def chunk_by_chars(text: str, chunk_size: int = 1000, chunk_overlap: int = 100) -> str:
    """Sliding window text chunking by character count."""
    result = _runtime.call("TextChunkerMS", "chunk_by_chars", text=text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    return _fmt(result)


@mcp.tool
def chunk_by_lines(text: str, max_lines: int = 50, max_chars: int = 2000) -> str:
    """Line-preserving chunker, best for code."""
    result = _runtime.call("TextChunkerMS", "chunk_by_lines", text=text, max_lines=max_lines, max_chars=max_chars)
    return _fmt(result)


@mcp.tool
def chunk_by_paragraphs(text: str, target_chars: int = 1000, overlap_paragraphs: int = 1) -> str:
    """Prose-aware paragraph chunking with overlap."""
    result = _runtime.call("TextChunkerMS", "chunk_by_paragraphs", text=text, target_chars=target_chars, overlap_paragraphs=overlap_paragraphs)
    return _fmt(result)


@mcp.tool
def chunk_code_file(file_path: str, max_chars: int = 4000) -> str:
    """Splits a code file into semantic blocks using indentation and regex heuristics."""
    result = _runtime.call("CodeChunkerMS", "chunk_file", file_path=file_path, max_chars=max_chars)
    return _fmt(result)


# ---------------------------------------------------------------------------
# CodeGrapherMS - Code Analysis
# ---------------------------------------------------------------------------

@mcp.tool
def scan_code_graph(root_path: str) -> str:
    """Parse Python code in a directory to extract symbols (nodes) and call relationships (edges)."""
    result = _runtime.call("CodeGrapherMS", "scan_directory", root_path=root_path)
    return _fmt(result)


# ---------------------------------------------------------------------------
# NeuralServiceMS - Ollama AI Interface
# ---------------------------------------------------------------------------

@mcp.tool
def neural_check_connection() -> str:
    """Ping Ollama to verify connectivity."""
    result = _runtime.call("NeuralServiceMS", "check_connection")
    return _fmt(result)


@mcp.tool
def neural_get_models() -> str:
    """List available Ollama models."""
    result = _runtime.call("NeuralServiceMS", "get_available_models")
    return _fmt(result)


@mcp.tool
def neural_embed(text: str) -> str:
    """Generate a vector embedding for the provided text via Ollama."""
    result = _runtime.call("NeuralServiceMS", "get_embedding", text=text)
    return _fmt(result)


@mcp.tool
def neural_infer(prompt: str, tier: str = "fast", format_json: bool = False) -> str:
    """Request text generation from a local LLM. tier = 'fast' | 'smart'."""
    result = _runtime.call("NeuralServiceMS", "request_inference", prompt=prompt, tier=tier, format_json=format_json)
    return _fmt(result)


@mcp.tool
def neural_update_models(fast_model: str = "", smart_model: str = "", embed_model: str = "") -> str:
    """Update the active Ollama model configurations."""
    result = _runtime.call("NeuralServiceMS", "update_models", fast_model=fast_model, smart_model=smart_model, embed_model=embed_model)
    return _fmt(result)


# ---------------------------------------------------------------------------
# IngestEngineMS - RAG Pipeline
# ---------------------------------------------------------------------------

@mcp.tool
def ingest_files(file_paths: str, model_name: str = "nomic-embed-text") -> str:
    """Run the full ingest pipeline: read, chunk, embed, weave graph. file_paths = JSON array.
    Note: This is a generator endpoint; returns final status after completion."""
    paths = json.loads(file_paths) if isinstance(file_paths, str) else file_paths
    last_status = None
    for status in _runtime.call("IngestEngineMS", "process_files", file_paths=paths, model_name=model_name):
        last_status = status
    return _fmt(last_status.__dict__ if hasattr(last_status, "__dict__") else last_status)


# ---------------------------------------------------------------------------
# RefineryServiceMS - "The Night Shift"
# ---------------------------------------------------------------------------

@mcp.tool
def refine_pending(batch_size: int = 50) -> str:
    """Process pending RAW files into semantic chunks and graph edges."""
    result = _runtime.call("RefineryServiceMS", "process_pending", batch_size=batch_size)
    return _fmt(result)


# ---------------------------------------------------------------------------
# CartridgeServiceMS - "The Source of Truth"
# ---------------------------------------------------------------------------

@mcp.tool
def cartridge_status() -> str:
    """Get cartridge status flags: ingest/refine completion and health."""
    result = _runtime.call("CartridgeServiceMS", "get_status_flags")
    return _fmt(result)


@mcp.tool
def cartridge_directory_tree(root: str = "/") -> str:
    """Get the VFS directory tree from the cartridge."""
    result = _runtime.call("CartridgeServiceMS", "get_directory_tree", root=root)
    return _fmt(result)


@mcp.tool
def cartridge_search(query_vector: str, limit: int = 10) -> str:
    """Semantic vector search on cartridge chunks. query_vector = JSON array of floats."""
    vec = json.loads(query_vector) if isinstance(query_vector, str) else query_vector
    result = _runtime.call("CartridgeServiceMS", "search_embeddings", query_vector=vec, limit=limit)
    return _fmt(result)


# ---------------------------------------------------------------------------
# SearchEngineMS - "The Oracle"
# ---------------------------------------------------------------------------

@mcp.tool
def search(db_path: str, query: str, limit: int = 10) -> str:
    """Hybrid search (vector similarity + keyword matching) on a SQLite database."""
    result = _runtime.call("SearchEngineMS", "search", db_path=db_path, query=query, limit=limit)
    return _fmt(result)


# ---------------------------------------------------------------------------
# VectorFactoryMS
# ---------------------------------------------------------------------------

@mcp.tool
def create_vector_store(backend: str = "faiss", config: str = "{}") -> str:
    """Create a VectorStore instance (FAISS or Chroma). config = JSON object."""
    cfg = json.loads(config) if isinstance(config, str) else config
    result = _runtime.call("VectorFactoryMS", "create", backend=backend, config=cfg)
    return _fmt(result)


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    mcp.run()
