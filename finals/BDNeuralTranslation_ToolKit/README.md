# BDNeuralTranslation ToolKit

Two standalone Python tool apps for use alongside BDNeuralTranslationSUITE's Emitter pipeline.

## Contents

```
README.md                  This file
DEV_LOG.md                 Evolution history: stamp → vendor → fix → verify
EMITTER_SCHEMA.md          Cold Artifact SQL schema, HyperHunk fields, surface definitions,
                           Nucleus evaluation, GraphAssembler candidate selection pipeline
SURFACE_MAPPING.md         How each service in both tools maps to the Emitter's 5 neuronal
                           surfaces, with concrete integration points and schema field references
CASStack.zip               7 services, 24 MCP tools — content-addressed storage
KnowledgeCartridgeBuilder.zip  11 services, 27 MCP tools — ingest-chunk-embed-search pipeline
```

## Quick start

Extract either .zip anywhere. No parent project needed.

```python
# CASStack
from backend import BackendRuntime
rt = BackendRuntime()
cid = rt.call("Blake3HashMS", "hash_content", content="2. Lexical analysis")
rt.call("VerbatimStoreMS", "write_lines", db_path="store.db", lines=["line one"])
rt.call("PropertyGraphMS", "upsert_node", db_path="store.db", node_id="occ_1", node_type="occurrence", props={"surface": "structural"})

# KnowledgeCartridgeBuilder
from backend import BackendRuntime
rt = BackendRuntime()
chunks = rt.call("PythonChunker", "chunk", content="def hello():\n    print('hi')\n")
graph = rt.call("CodeGrapher", "scan_directory", root_path="/path/to/code")
```

## Requirements

- Python 3.10+
- `fastmcp` — only if using MCP servers
- `requests` — only for KCB's ScoutMS web crawl and Ollama calls
- Optional: `sqlite_vec`, `numpy`, `faiss`, `chromadb`, `bs4`

CASStack has zero external dependencies beyond Python stdlib.

## Read order

1. **EMITTER_SCHEMA.md** — understand the Cold Artifact tables and surface model first
2. **SURFACE_MAPPING.md** — see how each tool service maps to specific Emitter fields
3. **DEV_LOG.md** — understand packaging decisions and known limitations
