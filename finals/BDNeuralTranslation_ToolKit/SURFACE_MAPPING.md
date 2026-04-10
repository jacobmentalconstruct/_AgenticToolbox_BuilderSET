# Surface Mapping — How CASStack and KCB Map to the 5 Surfaces

This document maps each service in both tools to the Emitter's 5 neuronal surfaces, with concrete integration points showing which Emitter schema fields each service can read, write, or augment.

---

## CASStack → Emitter Surface Mapping

### Blake3HashMS → Verbatim Surface

**What it does**: SHA3-256 content hashing. `hash_content(str) -> cid`

**Emitter integration point**: `content_nodes.hunk_id` is `SHA256(f"{node_kind}:{content}")`. Blake3HashMS computes a parallel CID on raw content alone. Two hunks with identical `content` but different `node_kind` get different `hunk_id` values in the Emitter but the same Blake3 CID — this isolates pure verbatim identity from grammatical tagging.

**Use case**: Dedup hunks across corpora before they enter the Emitter. If `hash_content(hunk.content)` matches an existing CID, the content is already known.

### VerbatimStoreMS → Verbatim Surface

**What it does**: Deduplicated line storage with FTS5.

**Emitter integration point**: Mirrors `content_fts` in the Cold Artifact. Both use FTS5, both index raw text content. VerbatimStoreMS stores individual lines by CID; the Emitter stores hunk content indexed by rowid.

**Use case**: Build a parallel verbatim index outside the Cold Artifact. `fts_search(db, "lexical analysis")` returns matching lines with CIDs. Cross-reference results against `content_fts` to find content the Emitter has seen vs. content it hasn't.

### MerkleRootMS → Structural Surface

**What it does**: Builds Merkle trees from ordered CID leaves. Diffs two trees.

**Emitter integration point**: After a probe run, hash every `occurrence_nodes.occurrence_id` as a leaf. `build_tree(leaves)` gives a single root hash representing the probe's graph state. `diff_trees(probe_N_leaves, probe_N+1_leaves)` shows exactly which occurrences were added/removed between probes.

**Use case**: Probe snapshot versioning. Track graph evolution across probe runs without storing full DB copies.

### TemporalChainMS → Structural Surface

**What it does**: Append-only chain of Merkle roots with named snapshots.

**Emitter integration point**: `commit(db, leaves, "probe_014")` after each probe. `get_chain(db)` returns version history. `get_snapshot(db, "probe_012")` retrieves a checkpoint.

**Use case**: Audit trail. "What did the graph look like at probe 012?" without needing a separate DB per probe.

### PropertyGraphMS → All Surfaces

**What it does**: SQLite property graph. Typed nodes + edges with JSON property bags.

**Emitter integration point**: Can store the same data as `relations` but with richer property bags. Example:

```python
upsert_node(db, occurrence_id, "occurrence", {
    "origin_id": "lexical_analysis.txt",
    "node_kind": "md_heading",
    "routing_profile": '{"grammatical": 0.3, "structural": 0.8, ...}',
    "interaction_vector": "[0.3, 0.8, 0.1, 0.5, 0.0]"
})

upsert_edge(db, occ_a, occ_b, "pull", {
    "weight": "0.72",
    "interaction_mode": "structural_bridge"
})
```

**Use case**: Secondary graph storage for surface-level exploration. Query patterns the Cold Artifact doesn't support directly: `find_by_property(db, "interaction_mode", "structural_bridge")` → all structural_bridge relations.

### IdentityAnchorMS → Manifold (cross-surface)

**What it does**: Anchors an artifact across storage, meaning, and relation layers.

**Emitter integration point**: Anchor an occurrence across all layers:

```python
anchor(db, occurrence_id, {
    "layer_storage_cid": blake3_cid,
    "layer_content_hunk_id": hunk_id,
    "layer_relation_edge_count": str(edge_count)
}, {
    "origin_id": "lexical_analysis.txt",
    "node_kind": "md_heading"
})
```

**Use case**: Cross-layer identity. "Given this CID, what occurrence does it map to, and how many relations does it have?"

### CrossLayerResolverMS → Manifold (cross-surface)

**What it does**: `resolve(db, artifact_id)` → presence across all layers.

**Emitter integration point**: One-call check: "Does this artifact exist in verbatim storage, in the property graph, and in the identity anchors?"

---

## KnowledgeCartridgeBuilder → Emitter Surface Mapping

### PythonChunkerMS → Grammatical Surface

**What it does**: AST-based Python chunking. Returns function/class boundaries with exact line ranges.

**Emitter integration point**: The Splitter uses CST/PEG for Python chunking, producing HyperHunks with `node_kind` like `function_definition`, `class_definition`. PythonChunkerMS uses stdlib `ast` independently. Compare chunk boundaries:

```
Splitter chunk: node_kind="function_definition", structural_path="module/MyClass/method_a"
PythonChunker:  name="method_a", type="function", start_line=10, end_line=25
```

Disagreements indicate structural signal the Splitter may be missing.

### ChunkingRouterMS → Grammatical Surface

**What it does**: Routes text to the right chunker by file extension.

**Emitter integration point**: The routing decision (`.py` → AST, `.md` → paragraph, `.js` → indentation) is itself a grammatical signal. The Emitter's `layer_type` field (`"CST"`, `"markdown_layer"`, `"code_layer"`) encodes the same decision. Cross-validate: does ChunkingRouterMS agree with the Splitter's layer_type assignment for the same file?

### CodeGrapherMS → Structural Surface

**What it does**: Scans Python files via AST, extracts symbol nodes and call-relationship edges.

**Emitter integration point**: Returns `{nodes, edges}` where edges are `{source, target, type: "calls"}`. This maps directly to `relations` with `interaction_mode = "structural_bridge"`. Compare CodeGrapher's call edges against the Emitter's structural_bridge relations to validate the structural surface.

```
CodeGrapher edge: {source: "file::MyClass", target: "file::func_a", type: "calls"}
Emitter relation: source_occ_id → target_occ_id, op="pull", interaction_mode="structural_bridge"
```

### ScoutMS → Structural Surface

**What it does**: Recursive directory scan → file tree.

**Emitter integration point**: `scan_directory(root)` returns a tree structure that maps to the Emitter's `structural_path` hierarchy. The tree `doc/h1_lexical_analysis/p1` in structural_path mirrors the directory structure Scout discovers.

### TextChunkerMS → Grammatical + Verbatim Surfaces

**What it does**: Three chunking strategies — chars (sliding window), lines (code-friendly), paragraphs (prose-aware).

**Emitter integration point**: The Splitter produces HyperHunks with `split_reason` and `token_count`. TextChunkerMS provides independent chunk boundaries. Cross-validate:

- `chunk_by_paragraphs` boundaries vs. Splitter's markdown paragraph hunks
- `chunk_by_lines` boundaries vs. Splitter's code block hunks
- Exact text preservation (`content` field) validates the verbatim surface

### NeuralServiceMS → Semantic Surface

**What it does**: Ollama interface for embeddings and inference.

**Emitter integration point**: `occurrence_nodes.vector_blob` stores embeddings. The Emitter supports `--embedder auto|deterministic|sentence-transformers|none`. NeuralServiceMS provides a fourth option via Ollama:

```python
neural_embed("Lexical analysis describes how tokens are formed.")
-> [0.012, -0.045, 0.089, ...]  # can be stored as vector_blob
```

### SearchEngineMS → Statistical + Semantic Surfaces

**What it does**: Hybrid vector + keyword (BM25) search on SQLite.

**Emitter integration point**: The Emitter's bag queries use `content_fts` (FTS5) and optional ANN search. SearchEngineMS provides a parallel recall lane with RRF (Reciprocal Rank Fusion) scoring that combines vector similarity (semantic) with keyword frequency (statistical).

### IngestEngineMS → All Surfaces (pipeline)

**What it does**: Full RAG pipeline: read → chunk → embed → weave graph.

**Emitter integration point**: Parallel pipeline that could ingest the same corpus into a Cartridge (UNCF v1.0 SQLite). Requires Ollama.

### CartridgeServiceMS → Semantic + Verbatim Surfaces

**What it does**: SQLite hub with 8 tables (UNCF v1.0). Stores manifest, directories, files, chunks, vec_items, graph_nodes, graph_edges, logs.

**Emitter integration point**: A Cartridge is a single-file knowledge database. If you ingest the same corpus into both a Cartridge and the Cold Artifact, you get two independent representations to cross-validate.

### RefineryServiceMS → Statistical Surface

**What it does**: Batch processes RAW files into semantic chunks with import-resolution graph edges (resolved=1.0 confidence, unresolved=0.25).

**Emitter integration point**: The weighted confidence scores parallel the Emitter's `relations.weight`. Import resolution edges map to `interaction_mode = "structural_bridge"` in the Emitter.

### VectorFactoryMS → Semantic Surface

**What it does**: FAISS/Chroma index factory.

**Emitter integration point**: Could index `occurrence_nodes.vector_blob` vectors into a FAISS index for fast ANN search outside the Cold Artifact.

---

## Summary Table

| Surface | CASStack services | KCB services |
|---------|------------------|-------------|
| **Grammatical** | — | ChunkingRouterMS, PythonChunkerMS |
| **Structural** | MerkleRootMS, TemporalChainMS | CodeGrapherMS, ScoutMS |
| **Statistical** | — | SearchEngineMS (BM25), RefineryServiceMS |
| **Semantic** | — | NeuralServiceMS, SearchEngineMS (vector), CartridgeServiceMS, VectorFactoryMS |
| **Verbatim** | Blake3HashMS, VerbatimStoreMS | TextChunkerMS |
| **Cross-surface** | PropertyGraphMS, IdentityAnchorMS, CrossLayerResolverMS | IngestEngineMS (full pipeline) |
