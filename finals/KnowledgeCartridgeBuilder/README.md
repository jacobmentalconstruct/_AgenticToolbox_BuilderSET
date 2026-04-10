# KnowledgeCartridgeBuilder

Ingest-chunk-embed-refine-search pipeline. Scans a codebase, chunks by file type (AST for Python, recursive for prose), embeds via Ollama, builds a knowledge graph, and queries with hybrid vector+keyword search. Static-vendored. Runs standalone.

## Packaging

This is a **static-vendored** standalone app. All microservice source code lives in `vendor/library/`. It does not depend on any parent project or external import root. You can unzip it anywhere and run it.

## What is here

```
app.py              Entry point. python app.py --health
backend.py          BackendRuntime — service registry, call() dispatch
mcp_server.py       FastMCP stdio server, 27 tools
settings.json       Relative paths to vendor/. No machine-specific paths.
app_manifest.json   Service list metadata
vendor/library/     All vendored microservice source
```

## Services (11)

| Service | What it does |
|---------|-------------|
| **ScoutMS** | Recursive directory scan. `scan_directory(root)`, `flatten_tree(tree)` |
| **ChunkingRouterMS** | Routes text to the right chunker by file extension |
| **PythonChunkerMS** | AST-based Python chunking. Returns functions, classes, line ranges |
| **TextChunkerMS** | Three strategies: `chunk_by_chars`, `chunk_by_lines`, `chunk_by_paragraphs` |
| **CodeChunkerMS** | Indentation + regex heuristic chunker for non-Python code |
| **CodeGrapherMS** | Python symbol + call graph via AST. `scan_directory` -> `{nodes, edges}` |
| **NeuralServiceMS** | Ollama interface: `check_connection`, `get_embedding`, `request_inference` |
| **IngestEngineMS** | Full RAG pipeline: read -> chunk -> embed -> weave graph |
| **RefineryServiceMS** | Batch processor for RAW files into semantic chunks + graph edges |
| **CartridgeServiceMS** | SQLite hub (UNCF v1.0). Requires `db_path` at construction |
| **SearchEngineMS** | Hybrid vector + keyword (BM25) search on SQLite |
| **VectorFactoryMS** | FAISS/Chroma index factory |

## External dependencies

- **Python 3.10+** (required)
- **fastmcp** (only if using `mcp_server.py`)
- **requests** (for ScoutMS web crawl + Ollama HTTP calls)
- Optional: `bs4` (web crawl), `sqlite_vec` (vector search), `numpy`, `faiss`, `chromadb`

## What works without optional deps

ScoutMS (local scan), PythonChunkerMS, TextChunkerMS, CodeChunkerMS, ChunkingRouterMS, CodeGrapherMS all work with zero optional deps. NeuralServiceMS/IngestEngineMS/RefineryServiceMS need Ollama running on localhost:11434. SearchEngineMS keyword search works; vector search needs `sqlite_vec`. CartridgeServiceMS vector search needs `sqlite_vec`.

## How to use

```python
from backend import BackendRuntime
rt = BackendRuntime()

# Scan and chunk
tree = rt.call("Scout", "scan_directory", root_path="/path/to/code")
files = rt.call("Scout", "flatten_tree", tree_node=tree)

# AST-chunk Python
chunks = rt.call("PythonChunker", "chunk", content="def hello():\n    print('hi')\n")

# Route by extension
chunks = rt.call("ChunkingRouterMS", "chunk_file", filename="main.py", text=source)

# Code graph
graph = rt.call("CodeGrapher", "scan_directory", root_path="/path/to/code")
# -> {"nodes": [...], "edges": [...]}
```

## MCP tools (27)

`list_services`, `app_health`, `scan_directory`, `flatten_tree`, `chunk_file`, `chunk_python`, `chunk_by_chars`, `chunk_by_lines`, `chunk_by_paragraphs`, `chunk_code_file`, `scan_code_graph`, `neural_check_connection`, `neural_get_models`, `neural_embed`, `neural_infer`, `neural_update_models`, `ingest_files`, `refine_pending`, `cartridge_status`, `cartridge_directory_tree`, `cartridge_search`, `search`, `create_vector_store`

## Safe to use for

- Chunking any codebase or text corpus
- Building Python symbol/call graphs via AST
- Ollama-powered embedding and inference (if Ollama running)
- Hybrid search over ingested content
- Builder-side corpus exploration and cross-validation

## Not safe to assume

- This is an exploration/reference tool, not a production RAG system
- IngestEngine/Refinery require Ollama on localhost:11434
- CartridgeServiceMS requires `db_path` passed at service construction time (via `_config={"db_path": "..."}`)
- Vector search features require `sqlite_vec` C extension
