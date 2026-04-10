# CASStack

Content-addressed storage, deduplication, Merkle-tree versioning, property graph, identity anchoring, and cross-layer resolution. All backed by SQLite. Static-vendored. No external dependencies beyond Python stdlib.

## Packaging

This is a **static-vendored** standalone app. All microservice source code lives in `vendor/library/`. It does not depend on any parent project or external import root. You can unzip it anywhere and run it.

## What is here

```
app.py              Entry point. python app.py --health
backend.py          BackendRuntime — service registry, call() dispatch
mcp_server.py       FastMCP stdio server, 24 tools
settings.json       Relative paths to vendor/. No machine-specific paths.
app_manifest.json   Service list metadata
vendor/library/     All vendored microservice source
```

## Services (7)

| Service | What it does |
|---------|-------------|
| **Blake3HashMS** | SHA3-256 content hashing (CID). Deterministic. `hash_content(str) -> cid` |
| **VerbatimStoreMS** | Deduplicated line storage with FTS5. `write_lines`, `read_line`, `fts_search` |
| **MerkleRootMS** | Merkle tree from CID leaves. `build_tree`, `diff_trees`, `inclusion_proof` |
| **TemporalChainMS** | Append-only chain of Merkle roots. `commit`, `get_chain`, `get_snapshot` |
| **PropertyGraphMS** | SQLite property graph. Nodes + edges with JSON props. `upsert_node`, `upsert_edge`, `get_neighbors`, `find_by_property` |
| **IdentityAnchorMS** | Cross-layer identity anchoring. `anchor`, `get_anchor`, `resolve_by_property` |
| **CrossLayerResolverMS** | Multi-layer presence check. `resolve(db, artifact_id)` |

## External dependencies

- **Python 3.10+** (required)
- **fastmcp** (only if using `mcp_server.py`)
- Nothing else. Pure stdlib + SQLite.

## How to use

```python
from backend import BackendRuntime
rt = BackendRuntime()

# Hash content
cid = rt.call("Blake3HashMS", "hash_content", content="some text")

# Store and search lines
result = rt.call("VerbatimStoreMS", "write_lines", db_path="store.db", lines=["line one", "line two"])
hits = rt.call("VerbatimStoreMS", "fts_search", db_path="store.db", query="line")

# Property graph
rt.call("PropertyGraphMS", "upsert_node", db_path="store.db", node_id="n1", node_type="chunk", props={"weight": "0.8"})
rt.call("PropertyGraphMS", "upsert_edge", db_path="store.db", src="n1", dst="n2", edge_type="relates", props={})
```

## MCP tools (24)

`list_services`, `app_health`, `hash_content`, `combine_cids`, `write_lines`, `read_line`, `reconstruct`, `fts_search`, `build_tree`, `diff_trees`, `inclusion_proof`, `chain_commit`, `get_chain`, `get_snapshot`, `upsert_node`, `upsert_edge`, `get_node`, `get_neighbors`, `find_by_property`, `anchor`, `get_anchor`, `resolve_by_property`, `resolve`

## Safe to use for

- Content deduplication via CID
- Versioning snapshots of any ordered content set
- SQLite-backed property graph storage
- FTS5 full-text search over stored lines
- Builder-side reference tooling

## Not safe to assume

- This is a reference/utility app, not a production data layer
- No encryption, no auth, no multi-writer concurrency beyond SQLite defaults
- Blake3HashMS uses SHA3-256 as a stdlib stand-in, not actual BLAKE3
