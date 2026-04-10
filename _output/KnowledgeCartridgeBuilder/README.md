# KnowledgeCartridgeBuilder — RAG Pipeline for the 5-Surface Model

## What this is

A headless app built from 11 microservices (+ 3 auto-resolved dependencies = 14 artifacts) that provides a complete ingest-chunk-embed-refine-search pipeline. It can scan a codebase, chunk it by file type (AST for Python, recursive for prose), embed via Ollama, build a knowledge graph, and query it with hybrid vector+keyword search.

It ships with an MCP server (`mcp_server.py`) exposing 27 tools over stdio transport.

## How it maps to the BDNeuralTranslation 5-surface model

The Emitter's pipeline is: Splitter (HyperHunks) -> Emitter (GraphAssembler + BootstrapNucleus) -> Cold Artifact (SQLite). The 5 neuronal surfaces are **grammatical, structural, statistical, semantic, verbatim**.

KnowledgeCartridgeBuilder provides a parallel/complementary pipeline that could feed or augment the Emitter at several points:

| KCB Service | What it does for the Emitter |
|-------------|------------------------------|
| **ScoutMS** | Scan a corpus directory or URL. Returns a file tree. Use `scan_directory(root)` then `flatten_tree(tree)` to get a file list for the Splitter or for direct ingest. |
| **ChunkingRouterMS** | Routes text to the right chunker by file extension. `.py` -> AST-based PythonChunkerMS. `.md`/`.txt` -> TextChunkerMS. `.js`/`.go`/etc -> CodeChunkerMS. Returns structured chunks with `name`, `type`, `start_line`, `end_line`. |
| **PythonChunkerMS** | AST-based Python chunking. Returns functions, classes, and their exact line ranges. This is a second opinion on Python code structure beside the Splitter's own CST/PEG path. |
| **TextChunkerMS** | Three strategies: `chunk_by_chars` (sliding window), `chunk_by_lines` (code-friendly), `chunk_by_paragraphs` (prose-aware). Could cross-validate the Splitter's prose chunking. |
| **CodeChunkerMS** | Indentation + regex heuristic chunker for non-Python code. |
| **CodeGrapherMS** | Scans a Python directory via AST, extracts symbol nodes (classes, functions) and call-relationship edges. Returns a `{nodes, edges}` graph. This is the **structural** surface — maps to the `structural_bridge` interaction mode. |
| **NeuralServiceMS** | Ollama interface: `neural_embed(text)` for embeddings, `neural_infer(prompt)` for generation. Could provide a third embedding lane beside the deterministic and sentence-transformer paths. |
| **IngestEngineMS** | Full RAG pipeline: read -> chunk -> embed (Ollama) -> weave graph (SynapseWeaver extracts Python+JS imports as edges). Generator-based with progress tracking. |
| **RefineryServiceMS** | "The Night Shift": processes RAW files into semantic chunks, parallel-embeds them, weaves import-resolution edges with weighted confidence (resolved=1.0, unresolved=0.25). |
| **CartridgeServiceMS** | SQLite hub with 8 tables: manifest, directories, files, chunks, vec_items (sqlite-vec), graph_nodes, graph_edges, logs. UNCF v1.0 format. This is a single-file knowledge database. |
| **SearchEngineMS** | Hybrid vector + keyword (BM25) search on SQLite. `search(db, "lexical analysis", limit=10)` returns ranked results. Could serve as a secondary recall surface for the Emitter's bag queries. |
| **VectorFactoryMS** | FAISS/Chroma index factory. |

## Concrete use cases for the Emitter

### 1. Secondary recall surface for bag queries
```
The Emitter's bag currently uses content_fts + ann_search on the Cold Artifact.
SearchEngineMS provides hybrid search (vector + BM25) on a Cartridge DB.
If you ingest the same corpus into a Cartridge, you get a second recall lane:

  search(cartridge_db, "lexical analysis", limit=12)
  -> ranked results from hybrid vector+keyword scoring
  -> compare against the bag's current FTS-only recall
```

### 2. Code graph for structural surface validation
```
CodeGrapherMS extracts Python symbol + call graphs via AST:

  scan_code_graph("/path/to/corpus")
  -> {nodes: [{id: "file::MyClass", type: "class", line: 10, calls: ["func_a"]}],
      edges: [{source: "file::MyClass", target: "file::func_a", type: "calls"}]}

This maps directly to the structural surface. You could compare
CodeGrapher's edges against the Emitter's structural_bridge relations.
```

### 3. AST-based chunk cross-validation
```
The Splitter uses CST/PEG for Python chunking.
PythonChunkerMS uses stdlib AST independently:

  chunk_python(source_code)
  -> [{name: "MyClass", type: "class", start_line: 10, end_line: 45, content: "..."}]

Compare chunk boundaries to see if the Splitter and PythonChunker agree.
Disagreements may indicate structural surface signal the Splitter is missing.
```

### 4. Corpus cartridge for builder-side inspection
```
Ingest a corpus into a Cartridge for offline exploration:

  1. tree = scan_directory("/path/to/corpus")
  2. files = flatten_tree(tree)
  3. ingest_files(files, model_name="nomic-embed-text")
  4. refine_pending(batch_size=50)
  5. search(cartridge_db, "memory graph", limit=10)
```

### 5. Ollama embedding as a third lane
```
NeuralServiceMS talks to Ollama on localhost:11434:

  neural_embed("Lexical analysis describes how tokens are formed.")
  -> [0.012, -0.045, 0.089, ...]  # embedding vector

This could serve as a third embedding provider beside
the deterministic BPE/SVD path and sentence-transformers.
```

## 5-Surface mapping reference

| Surface | KCB service that touches it |
|---------|-----------------------------|
| **Grammatical** | ChunkingRouterMS (file-type routing is a grammatical signal), PythonChunkerMS (AST node types) |
| **Structural** | CodeGrapherMS (call graph = structural edges), ScoutMS (directory tree = structural hierarchy) |
| **Statistical** | IngestEngineMS (co-occurrence via SynapseWeaver), SearchEngineMS (BM25 term frequency) |
| **Semantic** | NeuralServiceMS (Ollama embeddings), VectorFactoryMS (FAISS/Chroma indices), CartridgeServiceMS (sqlite-vec search) |
| **Verbatim** | VerbatimStore-adjacent: CartridgeServiceMS stores raw file content; TextChunkerMS preserves exact text boundaries |

## Files

| File | Purpose |
|------|---------|
| `app.py` | Entry point. `python app.py` for headless run, `--health` for diagnostics. |
| `backend.py` | `BackendRuntime` — service registry with full `SERVICE_SPECS` including all endpoint schemas. |
| `mcp_server.py` | FastMCP stdio server. 27 tools. `python mcp_server.py` to launch. |
| `settings.json` | Path config. `canonical_import_root` must point to the AgenticToolboxBuilder project root. |
| `app_manifest.json` | Stamp manifest (11 services). |
| `.stamper_lock.json` | Integrity lockfile with file CIDs. |

## Running

```bash
# Headless health check
python app.py --health

# MCP server (stdio transport)
python mcp_server.py

# Programmatic usage
from backend import BackendRuntime
rt = BackendRuntime()
chunker = rt.get_service("PythonChunkerMS")
chunks = chunker.chunk("def hello():\n    print('hi')\n")
```

## MCP tools (27)

**Meta**: `list_services`, `app_health`
**Scout**: `scan_directory`, `flatten_tree`
**Chunking**: `chunk_file`, `chunk_python`, `chunk_by_chars`, `chunk_by_lines`, `chunk_by_paragraphs`, `chunk_code_file`
**CodeGrapher**: `scan_code_graph`
**Neural/Ollama**: `neural_check_connection`, `neural_get_models`, `neural_embed`, `neural_infer`, `neural_update_models`
**IngestEngine**: `ingest_files`
**Refinery**: `refine_pending`
**Cartridge**: `cartridge_status`, `cartridge_directory_tree`, `cartridge_search`
**SearchEngine**: `search`
**VectorFactory**: `create_vector_store`

## Requirements

- Python 3.10+
- `fastmcp` (for MCP server only)
- `requests` (for ScoutMS web crawl + Ollama HTTP)
- Optional: `bs4` (web crawl), `sqlite_vec` (vector search), `numpy`, `faiss`, `chromadb`

## Important

- `settings.json` contains `canonical_import_root` pointing to the parent project. If you move this folder, update that path.
- Ollama must be running on `localhost:11434` for NeuralServiceMS / IngestEngineMS embedding features.
- This is `module_ref` mode — services import from `library/` in the parent project, not vendored copies.
