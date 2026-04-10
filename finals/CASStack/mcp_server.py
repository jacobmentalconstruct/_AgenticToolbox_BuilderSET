"""Auto-generated MCP server for CASStack.

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

mcp = FastMCP("CASStack")
_runtime = BackendRuntime()


def _fmt(obj: object) -> str:
    """JSON-serialize any result for MCP transport."""
    return json.dumps(obj, indent=2, default=str)


# ---------------------------------------------------------------------------
# Build one MCP tool per service endpoint, straight from SERVICE_SPECS
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


# --- Blake3HashMS tools ---

@mcp.tool
def hash_content(content: str) -> str:
    """Hash a string and return its hex CID (BLAKE3 / SHA3-256)."""
    result = _runtime.call("Blake3HashMS", "hash_content", content=content)
    return _fmt(result)


@mcp.tool
def combine_cids(cids: str) -> str:
    """Combine ordered CID list into a single root hash. Pass cids as JSON array string."""
    cid_list = json.loads(cids) if isinstance(cids, str) else cids
    result = _runtime.call("Blake3HashMS", "combine_cids", cids=cid_list)
    return _fmt(result)


# --- VerbatimStoreMS tools ---

@mcp.tool
def write_lines(db_path: str, lines: str) -> str:
    """Write deduplicated lines to verbatim store. lines = JSON array of strings. Returns ordered CIDs."""
    line_list = json.loads(lines) if isinstance(lines, str) else lines
    result = _runtime.call("VerbatimStoreMS", "write_lines", db_path=db_path, lines=line_list)
    return _fmt(result)


@mcp.tool
def read_line(db_path: str, cid: str) -> str:
    """Read a single verbatim line by its CID."""
    result = _runtime.call("VerbatimStoreMS", "read_line", db_path=db_path, cid=cid)
    return _fmt(result)


@mcp.tool
def reconstruct(db_path: str, cids: str) -> str:
    """Reconstruct ordered text from a JSON array of CIDs."""
    cid_list = json.loads(cids) if isinstance(cids, str) else cids
    result = _runtime.call("VerbatimStoreMS", "reconstruct", db_path=db_path, cids=cid_list)
    return _fmt(result)


@mcp.tool
def fts_search(db_path: str, query: str, limit: int = 10) -> str:
    """Full-text search over verbatim line content."""
    result = _runtime.call("VerbatimStoreMS", "fts_search", db_path=db_path, query=query, limit=limit)
    return _fmt(result)


# --- MerkleRootMS tools ---

@mcp.tool
def build_tree(leaves: str) -> str:
    """Build Merkle tree from JSON array of leaf CIDs. Returns root + all levels."""
    leaf_list = json.loads(leaves) if isinstance(leaves, str) else leaves
    result = _runtime.call("MerkleRootMS", "build_tree", leaves=leaf_list)
    return _fmt(result)


@mcp.tool
def diff_trees(leaves_a: str, leaves_b: str) -> str:
    """Diff two Merkle trees. Both args are JSON arrays of leaf CIDs."""
    a = json.loads(leaves_a) if isinstance(leaves_a, str) else leaves_a
    b = json.loads(leaves_b) if isinstance(leaves_b, str) else leaves_b
    result = _runtime.call("MerkleRootMS", "diff_trees", leaves_a=a, leaves_b=b)
    return _fmt(result)


@mcp.tool
def inclusion_proof(leaf: str, leaves: str) -> str:
    """Generate inclusion proof that a leaf CID is in the tree. leaves = JSON array."""
    leaf_list = json.loads(leaves) if isinstance(leaves, str) else leaves
    result = _runtime.call("MerkleRootMS", "inclusion_proof", leaf=leaf, leaves=leaf_list)
    return _fmt(result)


# --- TemporalChainMS tools ---

@mcp.tool
def chain_commit(db_path: str, leaves: str, label: str = "") -> str:
    """Commit a new set of leaf CIDs as a chained Merkle root. leaves = JSON array."""
    leaf_list = json.loads(leaves) if isinstance(leaves, str) else leaves
    result = _runtime.call("TemporalChainMS", "commit", db_path=db_path, leaves=leaf_list, label=label)
    return _fmt(result)


@mcp.tool
def get_chain(db_path: str) -> str:
    """Return full commit chain history in order."""
    result = _runtime.call("TemporalChainMS", "get_chain", db_path=db_path)
    return _fmt(result)


@mcp.tool
def get_snapshot(db_path: str, label: str) -> str:
    """Look up a named snapshot by label."""
    result = _runtime.call("TemporalChainMS", "get_snapshot", db_path=db_path, label=label)
    return _fmt(result)


# --- PropertyGraphMS tools ---

@mcp.tool
def upsert_node(db_path: str, node_id: str, node_type: str, props: str = "{}") -> str:
    """Create or update a property graph node. props = JSON object."""
    props_dict = json.loads(props) if isinstance(props, str) else props
    result = _runtime.call("PropertyGraphMS", "upsert_node", db_path=db_path, node_id=node_id, node_type=node_type, props=props_dict)
    return _fmt(result)


@mcp.tool
def upsert_edge(db_path: str, src: str, dst: str, edge_type: str, props: str = "{}") -> str:
    """Create or update a typed edge with properties. props = JSON object."""
    props_dict = json.loads(props) if isinstance(props, str) else props
    result = _runtime.call("PropertyGraphMS", "upsert_edge", db_path=db_path, src=src, dst=dst, edge_type=edge_type, props=props_dict)
    return _fmt(result)


@mcp.tool
def get_node(db_path: str, node_id: str) -> str:
    """Fetch a property graph node with its properties."""
    result = _runtime.call("PropertyGraphMS", "get_node", db_path=db_path, node_id=node_id)
    return _fmt(result)


@mcp.tool
def get_neighbors(db_path: str, node_id: str, edge_type: str = "") -> str:
    """Get neighbors of a node, optionally filtered by edge type."""
    result = _runtime.call("PropertyGraphMS", "get_neighbors", db_path=db_path, node_id=node_id, edge_type=edge_type)
    return _fmt(result)


@mcp.tool
def find_by_property(db_path: str, prop_key: str, prop_value: str) -> str:
    """Find property graph nodes where a named property matches a value."""
    result = _runtime.call("PropertyGraphMS", "find_by_property", db_path=db_path, prop_key=prop_key, prop_value=prop_value)
    return _fmt(result)


# --- IdentityAnchorMS tools ---

@mcp.tool
def anchor(db_path: str, artifact_id: str, layer_refs: str = "{}", stable_props: str = "{}") -> str:
    """Register an artifact's cross-layer identity anchor. layer_refs and stable_props = JSON objects."""
    refs = json.loads(layer_refs) if isinstance(layer_refs, str) else layer_refs
    props = json.loads(stable_props) if isinstance(stable_props, str) else stable_props
    result = _runtime.call("IdentityAnchorMS", "anchor", db_path=db_path, artifact_id=artifact_id, layer_refs=refs, stable_props=props)
    return _fmt(result)


@mcp.tool
def get_anchor(db_path: str, artifact_id: str) -> str:
    """Retrieve the full identity anchor for an artifact."""
    result = _runtime.call("IdentityAnchorMS", "get_anchor", db_path=db_path, artifact_id=artifact_id)
    return _fmt(result)


@mcp.tool
def resolve_by_property(db_path: str, prop_key: str, prop_value: str) -> str:
    """Resolve identity by searching anchors for a property match."""
    result = _runtime.call("IdentityAnchorMS", "resolve_by_property", db_path=db_path, prop_key=prop_key, prop_value=prop_value)
    return _fmt(result)


# --- CrossLayerResolverMS tools ---

@mcp.tool
def resolve(db_path: str, artifact_id: str) -> str:
    """Check artifact presence across all layers (storage, meaning, relation, identity, semantic)."""
    result = _runtime.call("CrossLayerResolverMS", "resolve", db_path=db_path, artifact_id=artifact_id)
    return _fmt(result)


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    mcp.run()
