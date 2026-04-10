# MindshardReferenceLibrary

Standalone reference-library tool for MindshardAGENT. It keeps imported reference material outside normal long-term memory, stores immutable revisions in a global library, and exposes explicit browse/search/read tools instead of auto-injecting content into prompts.

This package is self-contained and static-vendored. It does not runtime-import code from the parent Mindshard app repo.

## What Is Here

```text
app.py
backend.py
mcp_server.py
settings.json
app_manifest.json
tool_manifest.json
CONTRACT.md
VENDORING.md
smoke_test.py
src/core/reference_library/
lib/
tests/
vendor/library/
examples/
```

## Core Behavior

- Global canonical store at `~/.mindshard_reference_library/`
- Immutable document revisions
- Nested hierarchy with `group`, `document`, and `blob` nodes
- Attached-scope browse, search, and read by default
- Explicit `scope="global"` for whole-library browse/search/read
- Attached-scope browse/read requires `project_path` in the standalone tool surface
- Session usage and excerpt caching without copying the full library into session state
- Evidence mirroring for exact revision-pinned excerpts
- Content-addressed payload storage to keep repeated imports cheap

## Provider Adapters

The package uses a manifest-driven adapter registry and a normalized provider contract:

- `python_ast_provider`
  - tree-split Python chunking
- `tree_sitter_reference_provider`
  - syntax-aware splitting for supported code/script/markup when the `tree_sitter_language_pack` runtime is available
- `prose_document_provider`
  - prose/document chunking for plain text and prose-like files
- `readable_text_fallback_provider`
  - overlapping line-window fallback for readable text

Unsupported binaries are imported as blobs with metadata only.

## Tool Surface

- `library_manifest`
- `library_import`
- `library_refresh`
- `library_archive`
- `library_rename`
- `library_move`
- `library_attach`
- `library_detach`
- `library_list_roots`
- `library_list_children`
- `library_search`
- `library_get_detail`
- `library_list_revisions`
- `library_read_excerpt`
- `library_export`

The MCP server exposes the same tool names and semantics.

## Storage Layout

Global library root:

```text
~/.mindshard_reference_library/
  library_manifest.json
  providers_manifest.json
  library_index.sqlite3
  operations.jsonl
  content/
    text/
    blobs/
  records/
    nodes/
    revisions/
    temporal_chain.sqlite3
  exports/
```

Project-local attachment truth:

```text
.mindshard/state/reference_library_attachments.json
```

Session-local truth:

- `library_usage`
- `library_excerpt_cache`

## Verification

Run the standalone smoke test:

```powershell
python smoke_test.py
```

Run the regression suite:

```powershell
python -m unittest discover -s tests -v
```

Check health:

```powershell
python app.py --health
```

Start MCP:

```powershell
python mcp_server.py
```

## Python Example

```python
from backend import BackendRuntime

rt = BackendRuntime()

imported = rt.call(
    "MindshardReferenceLibrary",
    "library_import",
    source_path="C:/docs/reference-folder",
    project_path="C:/work/my-project",
    attach=True,
    attachment_context={"reason": "bootstrap"},
)

roots = rt.call(
    "MindshardReferenceLibrary",
    "library_list_roots",
    project_path="C:/work/my-project",
)

hits = rt.call(
    "MindshardReferenceLibrary",
    "library_search",
    query="adapter registry",
    project_path="C:/work/my-project",
)
```

## Notes

- `library_search` is intentionally conservative: attached scope is the default.
- `library_read_excerpt` records exact provenance by `revision_id`, not just current node state.
- If the tree-sitter runtime is unavailable, the package degrades to prose and fallback chunking instead of failing import entirely.
- Built-in provider manifests are reconciled to the current packaged entrypoints and runtime availability at startup.
- This v1 package is headless. Build a UI client later over the same contracts if needed.
