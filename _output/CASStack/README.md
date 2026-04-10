# CASStack — Content-Addressed Storage for the 5-Surface Model

## What this is

A headless app built from 7 microservices that provides content-addressed storage, deduplication, Merkle-tree versioning, a property graph, identity anchoring, and cross-layer resolution. All backed by SQLite. Zero external dependencies beyond Python stdlib.

It ships with an MCP server (`mcp_server.py`) exposing 24 tools over stdio transport.

## How it maps to the BDNeuralTranslation 5-surface model

The Emitter's Cold Artifact stores occurrence nodes, content nodes, and relations scored across 5 neuronal surfaces: **grammatical, structural, statistical, semantic, verbatim**. Each relation carries a `routing_profile` (surface weights) and an `interaction_vector` ([S_g, S_str, S_stat, S_sem, S_verb]).

CASStack gives you a content-addressed layer underneath or beside that:

| CASStack Service | What it does for the Emitter |
|-----------------|------------------------------|
| **Blake3HashMS** | CID every hunk by content. Two hunks with identical text = same CID = free dedup without running the scorer. Use `hash_content(hunk.content)` at ingest. |
| **VerbatimStoreMS** | Deduplicated line-level storage with FTS5 search. `write_lines(db, [line1, line2, ...])` returns ordered CIDs. `fts_search(db, "lexical analysis")` finds matching lines. This is the same FTS shape as `content_fts` in the Cold Artifact. |
| **MerkleRootMS** | Version a probe's graph state as a single root hash. Hash all occurrence CIDs as leaves, `build_tree(leaves)` gives you one root. `diff_trees(probe_012_leaves, probe_013_leaves)` shows exactly what changed between probes. |
| **TemporalChainMS** | Append-only chain of Merkle roots. `commit(db, leaves, "probe_014")` after each probe run. `get_chain(db)` returns the full version history. `get_snapshot(db, "probe_013")` retrieves a named checkpoint. |
| **PropertyGraphMS** | Typed nodes + edges with JSON property bags. Could store surface-level metadata alongside the Cold Artifact. Example: `upsert_node(db, "occ_xyz", "occurrence", {"routing_profile": {...}, "surfaces": [0.3, 0.8, 0.1, 0.5, 0.0]})`. |
| **IdentityAnchorMS** | Cross-layer identity. Anchor an artifact across storage (CID), meaning (chunk), and relation (graph edge) layers. `anchor(db, "occ_xyz", {"layer_storage_cid": "abc123", "layer_relation_edge_count": "47"}, {"origin_id": "lexical_analysis.txt"})`. |
| **CrossLayerResolverMS** | "Does this artifact exist in storage, meaning, and relation layers?" One call: `resolve(db, "abc123")` returns a presence dict. |

## Concrete use cases for the Emitter

### 1. Probe snapshot versioning
```
After each probe run:
  1. Hash every hunk content -> list of CIDs
  2. build_tree(cids) -> Merkle root
  3. chain_commit(db, cids, "probe_014") -> versioned snapshot
  4. diff_trees(probe_013_cids, probe_014_cids) -> exact delta
```

### 2. Hunk deduplication across corpora
```
For each hunk:
  1. cid = hash_content(hunk.content)
  2. write_lines(db, [hunk.content]) -> INSERT OR IGNORE
  3. Same content from two corpora? Stored once, referenced by CID.
```

### 3. Surface-aware property graph
```
Store 5-surface metadata beside the Cold Artifact:
  upsert_node(db, occurrence_id, "occurrence", {
      "origin_id": "lexical_analysis.txt",
      "node_kind": "md_heading",
      "routing_profile": {"grammatical": 0.3, "structural": 0.8, ...},
      "interaction_vector": [0.3, 0.8, 0.1, 0.5, 0.0]
  })
  upsert_edge(db, occ_a, occ_b, "pull", {
      "weight": 0.72,
      "interaction_mode": "structural_bridge"
  })
```

## Files

| File | Purpose |
|------|---------|
| `app.py` | Entry point. `python app.py` for headless run, `--health` for diagnostics. |
| `backend.py` | `BackendRuntime` — service registry with `get_service()`, `call()`, `health()`. |
| `mcp_server.py` | FastMCP stdio server. 24 tools. `python mcp_server.py` to launch. |
| `settings.json` | Path config. `canonical_import_root` must point to the AgenticToolboxBuilder project root. |
| `app_manifest.json` | Stamp manifest (7 services, 3 manager layers). |
| `.stamper_lock.json` | Integrity lockfile with file CIDs. |

## Running

```bash
# Headless health check
python app.py --health

# MCP server (stdio transport, for Claude Code or .mcp.json)
python mcp_server.py

# Programmatic usage
from backend import BackendRuntime
rt = BackendRuntime()
hasher = rt.get_service("Blake3HashMS")
cid = hasher.hash_content("2. Lexical analysis")
```

## MCP tools (24)

**Meta**: `list_services`, `app_health`
**Blake3Hash**: `hash_content`, `combine_cids`
**VerbatimStore**: `write_lines`, `read_line`, `reconstruct`, `fts_search`
**MerkleRoot**: `build_tree`, `diff_trees`, `inclusion_proof`
**TemporalChain**: `chain_commit`, `get_chain`, `get_snapshot`
**PropertyGraph**: `upsert_node`, `upsert_edge`, `get_node`, `get_neighbors`, `find_by_property`
**IdentityAnchor**: `anchor`, `get_anchor`, `resolve_by_property`
**CrossLayerResolver**: `resolve`

## Requirements

- Python 3.10+
- `fastmcp` (for MCP server only)
- No other external dependencies. Pure stdlib + SQLite.

## Important

- `settings.json` contains `canonical_import_root` pointing to the parent project. If you move this folder, update that path.
- All storage is SQLite. No external databases.
- This is `module_ref` mode — services import from `library/` in the parent project, not vendored copies.
