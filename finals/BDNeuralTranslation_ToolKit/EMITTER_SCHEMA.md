# BDNeuralTranslationSUITE Emitter — Schema Reference

This document captures the exact schema, field names, and surface definitions from the Emitter as of 2026-03-30. Use this to understand how CASStack and KnowledgeCartridgeBuilder map to the Emitter's data structures.

---

## Cold Artifact SQLite Schema

The Emitter writes a single SQLite database (the "Cold Artifact"). Default path: `./cold_anatomy.db`.

### content_nodes

Deduplicated content. One row per unique hunk text.

```sql
CREATE TABLE IF NOT EXISTS content_nodes (
    hunk_id          TEXT    PRIMARY KEY,   -- SHA256(f"{node_kind}:{content}")
    node_kind        TEXT    NOT NULL,      -- e.g. "md_heading", "function_definition"
    content          TEXT    NOT NULL,      -- raw hunk text
    attention_weight REAL    NOT NULL DEFAULT 1.0,
    static_mass      INTEGER NOT NULL DEFAULT 0
);
```

### occurrence_nodes

One row per occurrence of content in a specific document at a specific structural position.

```sql
CREATE TABLE IF NOT EXISTS occurrence_nodes (
    occurrence_id   TEXT PRIMARY KEY,   -- SHA256(f"{origin_id}:{structural_path}:{sibling_index}:{hunk_id}")
    hunk_id         TEXT NOT NULL,      -- FK to content_nodes
    origin_id       TEXT NOT NULL,      -- source document, e.g. "memory://lexical_analysis.txt"
    structural_path TEXT NOT NULL DEFAULT '',  -- e.g. "doc/h1_lexical_analysis/p1"
    vector_blob     BLOB               -- embedding vector (optional)
);
```

### relations

Scored connections between occurrence pairs. Each carries a 5-surface routing profile.

```sql
CREATE TABLE IF NOT EXISTS relations (
    source_occ_id      TEXT NOT NULL,
    op                 TEXT NOT NULL,      -- "pull" or "precedes"
    target_occ_id      TEXT NOT NULL,
    weight             REAL NOT NULL,      -- connection_strength from Nucleus
    routing_profile    TEXT NOT NULL DEFAULT '{}',   -- JSON: {"grammatical": 0.3, "structural": 0.8, ...}
    interaction_mode   TEXT NOT NULL DEFAULT '',      -- e.g. "structural_bridge", "multi_surface"
    interaction_vector TEXT NOT NULL DEFAULT '[]',    -- JSON: [S_gram, S_struct, S_stat, S_sem, S_verb]
    PRIMARY KEY (source_occ_id, op, target_occ_id)
);
```

### inhibit_edges

Suppression edges between token pairs.

```sql
CREATE TABLE IF NOT EXISTS inhibit_edges (
    token_a TEXT NOT NULL,
    token_b TEXT NOT NULL,
    weight  REAL NOT NULL,
    PRIMARY KEY (token_a, token_b)
);
```

### content_fts (FTS5 virtual table)

Full-text search over content_nodes. Used by the FTS fallback in GraphAssembler.

```sql
CREATE VIRTUAL TABLE IF NOT EXISTS content_fts USING fts5(
    content,
    content=content_nodes,
    content_rowid=rowid
);
```

Auto-synced via triggers on INSERT/UPDATE/DELETE to content_nodes.

---

## The 5 Neuronal Surfaces

Surface order (array index):

| Index | Surface | Label |
|-------|---------|-------|
| 0 | **grammatical** | Node-kind similarity. Are both hunks the same grammatical type? |
| 1 | **structural** | Position in document/code hierarchy. Shared structural context. |
| 2 | **statistical** | Co-occurrence, term frequency, distributional signals. |
| 3 | **semantic** | Embedding cosine similarity. Meaning-level closeness. |
| 4 | **verbatim** | Exact or near-exact text overlap. |

### routing_profile

JSON object on each relation. Values sum to 1.0. Shows which surface contributed most to the connection.

```json
{
    "grammatical": 0.35,
    "structural": 0.25,
    "statistical": 0.20,
    "semantic": 0.15,
    "verbatim": 0.05
}
```

### interaction_vector

JSON array of raw similarity scores per surface (NOT normalized):

```json
[0.7, 0.9, 0.3, 0.5, 0.0]
```

Order: `[grammatical, structural, statistical, semantic, verbatim]`

### interaction_mode labels

Derived from the dominant surface:

| Dominant Surface | interaction_mode |
|-----------------|-----------------|
| grammatical | `grammatical_dominant` |
| structural | `structural_bridge` |
| statistical | `statistical_echo` |
| semantic | `semantic_resonance` |
| (no dominant) | `multi_surface` |

### interaction_mode → op mapping

| interaction_mode | op in relations table |
|-----------------|----------------------|
| `grammatical_dominant` | `pull` |
| `structural_bridge` | `pull` |
| `statistical_echo` | `precedes` |
| `semantic_resonance` | `pull` |
| `multi_surface` | `pull` |

---

## HyperHunk Fields

The unit of content flowing through the pipeline. Created by the Splitter, consumed by the Emitter.

### Identity (computed on __post_init__)

- `hunk_id: str` — `SHA256(f"{node_kind}:{content}")`
- `occurrence_id: str` — `SHA256(f"{origin_id}:{structural_path}:{sibling_index}:{hunk_id}")`

### Required fields

| Field | Type | Example |
|-------|------|---------|
| `content` | str | `"2. Lexical analysis"` |
| `origin_id` | str | `"memory://lexical_analysis.txt"` |
| `layer_type` | str | `"CST"`, `"code_layer"`, `"markdown_layer"` |
| `node_kind` | str | `"md_heading"`, `"function_definition"`, `"md_paragraph"` |

### Structural/DAG fields

| Field | Type | Default |
|-------|------|---------|
| `structural_path` | str | `""` |
| `sibling_index` | int | `0` |
| `parent_occurrence_id` | Optional[str] | `None` |
| `prev_sibling_occurrence_id` | Optional[str] | `None` |

### Document structure fields

| Field | Type | Default |
|-------|------|---------|
| `heading_trail` | List[str] | `[]` |
| `cross_refs` | List[str] | `[]` |
| `normalized_cross_refs` | List[str] | `[]` |
| `reference_kinds` | List[str] | `[]` |
| `list_role` | str | `""` |
| `list_depth` | int | `0` |
| `reference_confidence` | float | `0.0` |

### Code structure fields

| Field | Type | Default |
|-------|------|---------|
| `scope_stack` | List[str] | `[]` |
| `scope_docstrings` | Dict[str, str] | `{}` |
| `base_classes` | List[str] | `[]` |
| `decorators` | List[str] | `[]` |
| `import_context` | List[str] | `[]` |

### Metrics

| Field | Type | Default |
|-------|------|---------|
| `token_count` | int | `0` |
| `document_position` | float | `0.0` |
| `sibling_count` | int | `0` |
| `context_window` | str | `""` |
| `split_reason` | str | `""` |

### Emitter extension

| Field | Type | Default |
|-------|------|---------|
| `embedding` | Optional[List[float]] | `None` |

---

## GraphAssembler — Candidate Selection Pipeline

The GraphAssembler ingests HyperHunks one at a time and pairs each incoming hunk with candidates for Nucleus evaluation.

### Constructor parameters

```python
GraphAssembler(
    db_path,
    nucleus,                            # BootstrapNucleus instance
    embed_provider=None,                # optional embedding provider
    window_size=50,                     # sliding window width
    reference_candidate_limit=0,        # anchor registry budget (0=disabled)
    anchor_common_term_threshold=5,     # suppress terms seen > N times
    fts_candidate_limit=0,              # FTS fallback budget (0=disabled)
    fts_fallback_thin_threshold=2,      # fire FTS when cross-doc anchors < this
)
```

### Candidate selection order

For each incoming hunk:

1. **Sliding window** — the most recent `window_size` hunks. Always active.
2. **Anchor registry** — if `reference_candidate_limit > 0`:
   - Extracts anchor tokens from hunk's `heading_trail` and `normalized_cross_refs`
   - Looks up registered anchors (headings, list targets, references)
   - Ranks by: matched token count (desc), cross-document (desc), weight (desc), occurrence count (asc), ingest sequence (desc)
   - Returns top `reference_candidate_limit` candidates
   - Anchor weights: heading=3, list_target=2, reference=1
3. **FTS fallback** — if `fts_candidate_limit > 0` AND anchor cross-doc count < `fts_fallback_thin_threshold`:
   - Builds FTS query by lexicalizing `normalized_cross_refs` and `heading_trail` slugs
   - Queries `content_fts` via FTS5 MATCH
   - Resolves hits to cached HyperHunk objects (only hits from current ingest session)
   - Prefers cross-document hits
   - Returns up to `fts_candidate_limit` candidates

### Stats output

```python
assembler.stats() -> {
    "training_pairs": int,
    "fts_fallback_fires": int,
    "fts_raw_hits": int,
    "fts_selected": int,
    "fts_selected_cross_doc": int,
    "content_nodes": int,
    "occurrence_nodes": int,
    "relations": int,
    "inhibit_edges": int,
}
```

### CLI flags for candidate selection

```
--window-size N                    (default: 50)
--reference-candidate-limit N      (default: 0, disabled)
--fts-candidate-limit N            (default: 0, disabled)
--fts-fallback-thin-threshold N    (default: 2)
```

---

## Nucleus Evaluation

The BootstrapNucleus scores each (hunk_A, hunk_B) pair across all 5 surfaces.

### NucleusResult fields

```python
NucleusResult(
    connection_strength: float,        # weighted sum: Σ(W_i · S_i)
    routing_profile: Dict[str, float], # normalized: which surface contributed most
    interaction_type: str,             # label from dominant surface
    interaction_vector: List[float],   # raw [S_gram, S_struct, S_stat, S_sem, S_verb]
    above_threshold: bool,             # connection_strength >= edge_threshold
)
```

### Default tuning profile

```python
edge_threshold = 0.3
dominance_threshold = 0.40
surface_fractions = {
    "grammatical": 0.35,
    "structural": 0.25,
    "statistical": 0.20,
    "semantic": 0.15,
    "verbatim": 0.05,
}
```

### Grammatical match profile (default weights)

```python
exact_code_kind = 1.0
exact_heading_kind = 0.7
exact_structured_prose_kind = 0.532
exact_generic_prose_kind = 0.305
exact_fragment_kind = 0.2
family_code_kind = 0.5
family_prose_kind = 0.1
family_fragment_kind = 0.05
```

---

## Structural Edge Routing

Fixed profile for edges generated from HyperHunk structural relations (parent/child, sibling):

```python
routing_profile = {"structural": 1.0, "grammatical": 0.0, "statistical": 0.0, "semantic": 0.0, "verbatim": 0.0}
interaction_vector = [0.0, 1.0, 0.0, 0.0, 0.0]
```
