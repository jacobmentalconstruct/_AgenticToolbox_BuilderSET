# AgenticToolboxBuilder

Layered microservice library and app-stamping toolkit, structured for agent-first workflows.

## Architecture

```
src/app.py                     <- single entry point + app state registry
  |
  +-- src/ui/main_gui.py       <- UI orchestrator (user's console)
  +-- src/mcp/main_mcp_ui.py   <- MCP orchestrator (Claude's console)
  +-- src/core/main_engine.py  <- headless engine orchestrator
```

Orchestrators own their domains and never import each other. Cross-orchestrator
communication flows through `AppStateRegistry` as structured state packets.

The MCP and UI surfaces expose the **same functions** — one surface, two consoles.

## Quick Start

```bat
setup_env.bat
python src/app.py ui
```

## Entry Points

| Command | What it does |
|---------|-------------|
| `python src/app.py ui` | Launch Tkinter librarian UI |
| `python src/app.py mcp` | Launch MCP server (not yet implemented) |
| `python src/app.py core` | Launch headless engine (not yet implemented) |
| `python src/app.py catalog` | Build/refresh the catalog |

## Library

The canonical microservice library lives under `library/` with ~97 services
across 11 layers. The catalog (`library/catalog/catalog.db`) is a derived
index built by static analysis.

Legacy CLI still works: `python -m library.app_factory --help`

## Project Layout

```
src/              Application code (orchestrators + subdomains)
library/          Canonical microservice library (source of truth)
assets/           Static assets (icons, images)
_design-docs/     Design notes and smoke test outputs
_sandbox/         Sandbox workspace for stamp/patch/validate/promote
_archives/        Archived legacy files and curation tools
```

## Subdomain Nesting

Each orchestrator can grow subdomains as needed:

```
src/ui/
  _microservices/   UI-specific microservice adapters
  _packages/        UI packages
  _modules/         UI modules
```

## Key Principles

- **Symmetry**: MCP tools and UI expose the same functions
- **Isolation**: Orchestrators never reach into each other's domain
- **State packets**: Cross-domain communication via AppStateRegistry
- **CAS-ready**: Microservice pattern enables content-addressed deduplication
- **Single domain**: Components own exactly one piece of logic
