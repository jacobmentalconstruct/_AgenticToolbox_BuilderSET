# Dev Log — BDNeuralTranslation ToolKit

## What this package is

Two static-vendored Python tool apps packaged for use alongside BDNeuralTranslationSUITE. Each is a standalone .zip with all source vendored inside. Neither requires the parent AgenticToolboxBuilderSET project to run.

- **CASStack.zip** — 7 services, 24 MCP tools. Content-addressed storage, dedup, Merkle versioning, property graph, identity anchoring.
- **KnowledgeCartridgeBuilder.zip** — 11 services, 27 MCP tools. Ingest-chunk-embed-refine-search RAG pipeline.

## Evolution timeline

### Phase 1: Service selection and initial stamp

Both apps were stamped from the AgenticToolboxBuilderSET microservice library (~97 services). Service selection was driven by mapping to the Emitter's 5 neuronal surfaces:

**CASStack** was selected for:
- Hunk deduplication via content-addressed hashing (verbatim surface)
- Probe snapshot versioning via Merkle trees (structural surface)
- Surface-aware property graph storage (all surfaces)
- Cross-layer identity resolution (manifold)

**KnowledgeCartridgeBuilder** was selected for:
- Secondary recall surface for the Emitter's bag queries (statistical/semantic)
- AST-based chunk cross-validation against the Splitter (grammatical/structural)
- Code graph extraction for structural surface validation (structural)
- Ollama embedding as a third embedding lane (semantic)

Both were initially stamped in `module_ref` mode (wrapper apps importing from the parent project's `library/` directory). This was identified as non-portable.

### Phase 2: Static vendoring

Both apps were restamped in `vendor_mode: "static"`, which copies all microservice source code into `vendor/library/` inside each app directory. This made them self-contained.

### Phase 3: Bootstrap and runtime fixes

The static builds didn't run out of the box. Fixes applied:

1. **`backend.py` sys.path bootstrap** — `backend.py` had no path setup. Added the same `settings.json`-driven bootstrap that `app.py` and `mcp_server.py` use, so `from backend import BackendRuntime` works as a standalone entry point.

2. **VerbatimStoreMS schema init** (CASStack only) — The `_open()` method connected to SQLite but didn't create tables. Added `CREATE TABLE IF NOT EXISTS verbatim_lines` and `CREATE VIRTUAL TABLE IF NOT EXISTS fts_lines USING fts5(...)` to `_open()`.

3. **FTS sync on write** (CASStack only) — `write_lines()` inserted into `verbatim_lines` but not `fts_lines`. Added FTS insert alongside the main table write so `fts_search()` returns results.

4. **Constructor dispatch** (KCB only) — `BackendRuntime.get_service()` tried `cls(config_dict)` then `cls()`. CartridgeServiceMS takes `db_path` as a positional string arg. Added `cls(**config)` fallback to handle keyword-arg constructor patterns.

5. **BaseService logging stubs** (KCB only) — CartridgeServiceMS calls `self.log_info()` inherited from BaseService, but the vendored BaseService didn't have it. Added `log_info`, `log_warning`, `log_error` as no-op stubs.

### Phase 4: Path decontamination

All config files had hardcoded machine-specific absolute paths from the stamp machine:

- `settings.json` — absolute paths to `C:\Users\...\finals\CASStack\vendor`
- `.env` — absolute PYTHONPATH entries
- `pyrightconfig.json` — absolute extraPaths entries
- `app_manifest.json` — absolute destination path
- `.stamper_lock.json` — absolute source/target paths from build

**Fixed:**
- `settings.json` → relative paths (`vendor`, `vendor/library`, etc.)
- `.env` → relative PYTHONPATH
- `pyrightconfig.json` → relative extraPaths
- `app_manifest.json` → removed `destination` key
- `.stamper_lock.json` → deleted (build provenance artifact, not needed at runtime)
- `app.py`, `backend.py`, `mcp_server.py` → bootstrap resolves relative paths against `Path(__file__).resolve().parent`

### Phase 5: Verification

- **End-to-end service tests**: All 7 CASStack services and all 11 KCB services called through `BackendRuntime.call()` with real data.
- **Portability test**: Both zips extracted to `%TEMP%` and ran successfully from there.
- **Machine path scan**: grep for `C:\Users`, `_AgenticToolboxBuilder`, `_LivePROJECTS` across all non-binary files — zero hits.
- **AST import verification**: All Python files parsed, all import chains resolve (optional deps like `blake3`, `fastmcp`, `sqlite_vec` gracefully degrade via try/except).
- **python_risk_scan**: CASStack = 0 findings. KCB = 9 pre-existing vendor code style issues (bare_except, blocking_call), none packaging-related.

## Known limitations

- CASStack's Blake3HashMS uses `hashlib.sha3_256` as a stdlib stand-in, not actual BLAKE3.
- KCB's NeuralServiceMS, IngestEngineMS, and RefineryServiceMS require Ollama running on `localhost:11434`.
- KCB's CartridgeServiceMS and SearchEngineMS vector search requires the `sqlite_vec` C extension.
- Neither app has auth, encryption, or multi-writer concurrency beyond SQLite defaults.

## Product-fit assessment

- **CASStack**: Honest standalone utility/reference app. Useful for builder-side dedup, versioning, and property graph exploration. Could augment the Emitter's Cold Artifact as a secondary storage layer.
- **KnowledgeCartridgeBuilder**: Correctly packaged but over-scoped for BDNeuralTranslationSUITE Phase 1. Should be treated as optional builder-side tooling for corpus exploration and chunk cross-validation, not as an integration target.
