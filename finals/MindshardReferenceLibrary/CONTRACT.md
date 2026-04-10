# Contract

## Purpose

MindshardReferenceLibrary is an explicit external reference surface for agents. It is not prompt-memory storage and it is not session-local library duplication.

## Provider Contract

Normalized request:

- `request_id`
- `strategy_hint`
- `logical_path`
- `media_type`
- `extension`
- `content_hash`
- `text_path`
- `blob_path`
- `max_chars`
- `overlap_chars`
- `metadata`

Normalized result:

- `provider_id`
- `provider_kind`
- `provider_version`
- `strategy_used`
- `status`
- `warnings`
- `sections`

Normalized section:

- `section_id`
- `parent_section_id`
- `ordinal`
- `depth`
- `section_kind`
- `anchor_path`
- `title`
- `summary`
- `exact_text`
- `char_start`
- `char_end`
- `source_span`
- `metadata`

Provider adapters may return a fully structured dict-shaped result, but section payloads must be coercible into the normalized `ProviderSection` schema before store import proceeds.

## Selection Order

1. Tree-splitter provider for supported code/script/markup
2. Prose/document provider for readable prose-like files
3. Fallback chunker for readable text
4. Blob import for unsupported binaries

If the optional tree-sitter runtime is unavailable, the tree provider may be disabled and the package falls through to the next valid strategy.
Built-in provider manifests are reconciled to the packaged defaults at startup so stale persisted entrypoints or stale tree-sitter enablement do not become the active runtime contract.

## Tool Semantics

- `library_import`
  - imports into the global store
  - may also attach to a project when `attach=true`
- `library_refresh`
  - never mutates old revisions
  - always creates a new revision record
- `library_list_roots`
  - defaults to attached scope
  - attached scope requires `project_path`
  - requires `scope=global` for whole-library browse without a project attachment context
- `library_list_children`
  - defaults to attached scope
  - attached scope requires `project_path`
- `library_search`
  - defaults to attached scope
  - attached scope requires `project_path`
  - requires `scope=global` for whole-library search
- `library_get_detail`
  - defaults to attached scope
  - attached scope requires `project_path`
- `library_list_revisions`
  - defaults to attached scope
  - attached scope requires `project_path`
- `library_read_excerpt`
  - defaults to attached scope
  - attached scope requires `project_path`
  - resolves excerpt from the library first
  - then records usage/cache/evidence with a stable `operation_id`

## Idempotency

Cross-store work is ordered and duplicate-safe, not distributed ACID.

- Library writes are ACID inside the library SQLite store
- Session usage/cache writes are `INSERT OR IGNORE` by `operation_id`
- Evidence writes are duplicate-safe by `operation_id`
- Retrying `library_read_excerpt` with the same resolved excerpt shape reuses the same `operation_id`

## Historical Stability

- Node IDs stay stable across rename and move
- Revision IDs are immutable
- Archive is a tombstone, not hard delete
- Old session references remain resolvable by `revision_id`
- The packaged tool must remain self-contained and must not runtime-import from the parent Mindshard app repo
