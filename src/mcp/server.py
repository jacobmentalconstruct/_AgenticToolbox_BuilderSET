"""MCP server for the AgenticToolboxBuilder.

Exposes the same operations as the UI — one surface, two consoles.
Tools are organized into three groups:
  - Catalog: browse, search, describe services
  - Stamper: stamp apps from templates/manifests, verify, inspect
  - Sandbox: stamp → apply → validate → promote pipeline
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

# Ensure project root is importable
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastmcp import FastMCP

from library.app_factory import (
    CatalogBuilder,
    LibraryQueryService,
    AppStamper,
)
from library.app_factory.sandbox import SandboxWorkflow
from library.app_factory.models import AppBlueprintManifest

mcp = FastMCP("AgenticToolboxBuilder")


def _query() -> LibraryQueryService:
    return LibraryQueryService()


def _fmt(obj: object) -> str:
    return json.dumps(obj, indent=2, default=str)


# ---------------------------------------------------------------------------
# Catalog: browse and query
# ---------------------------------------------------------------------------


@mcp.tool
def build_catalog() -> str:
    """Build or refresh the library catalog (SQLite index of all microservices).

    Run this first if the catalog is stale or missing. Returns build stats
    including service count, endpoint count, and dependency count.
    """
    report = CatalogBuilder().build()
    return _fmt(report)


@mcp.tool
def list_layers() -> str:
    """List all microservice layers in the catalog.

    Layers group services by functional domain: core, db, ui, storage,
    structure, meaning, relation, observability, pipeline, reference, etc.
    """
    return _fmt(_query().list_layers())


@mcp.tool
def list_services(layer: Optional[str] = None) -> str:
    """List all services in the catalog, optionally filtered by layer.

    Each service entry includes: class_name, service_name, version, layer,
    description, tags, and import_key. Use describe_service for full details.

    Args:
        layer: Optional layer name to filter by (e.g. 'core', 'ui', 'storage')
    """
    return _fmt(_query().list_services(layer=layer))


@mcp.tool
def describe_service(identifier: str) -> str:
    """Get full details for a single service including endpoints and dependencies.

    Args:
        identifier: Service class_name (e.g. 'FingerprintScannerMS') or service_name
    """
    result = _query().describe_service(identifier)
    if result is None:
        return json.dumps({"error": f"Service '{identifier}' not found"})
    return _fmt(result)


@mcp.tool
def show_dependencies(identifier: str) -> str:
    """Show dependency buckets for a service: code, runtime, and external.

    Args:
        identifier: Service class_name or service_name
    """
    result = _query().show_dependencies(identifier)
    if result is None:
        return json.dumps({"error": f"Service '{identifier}' not found"})
    return _fmt(result)


@mcp.tool
def list_templates() -> str:
    """List all built-in app starter templates.

    Templates are pre-configured manifests for common app shapes:
    headless_scanner, ui_explorer_workbench, semantic_pipeline_tool,
    storage_layer_lab, manifold_layer_lab.
    """
    return _fmt(_query().list_templates())


@mcp.tool
def recommend_blueprint(
    services: str,
    destination: str = "",
    name: str = "",
    vendor_mode: str = "module_ref",
) -> str:
    """Generate a recommended app blueprint manifest from selected services.

    The recommender resolves dependencies, selects the right UI pack,
    and produces a ready-to-stamp manifest.

    Args:
        services: Comma-separated service class names (e.g. 'FingerprintScannerMS,ScoutMS')
        destination: Target directory for the stamped app
        name: App display name
        vendor_mode: 'module_ref' (dev, imports from library) or 'static' (copies files)
    """
    service_list = [s.strip() for s in services.split(",") if s.strip()]
    result = _query().recommend_blueprint(
        selected_services=service_list,
        destination=destination,
        name=name,
        vendor_mode=vendor_mode,
    )
    return _fmt(result)


# ---------------------------------------------------------------------------
# Stamper: stamp, inspect, verify, restamp
# ---------------------------------------------------------------------------


@mcp.tool
def stamp_template(
    template_id: str,
    destination: str,
    name: str = "",
    vendor_mode: str = "",
) -> str:
    """Stamp a new app from a built-in template.

    Creates a complete app directory with app.py, backend.py, ui.py,
    settings.json, and lockfile.

    Args:
        template_id: Template name (headless_scanner, ui_explorer_workbench, etc.)
        destination: Directory path where the app will be created
        name: Optional display name for the app
        vendor_mode: 'module_ref' or 'static' (defaults to template's default)
    """
    manifest = _query().template_blueprint(
        template_id,
        destination=destination,
        name=name or None,
        vendor_mode=vendor_mode or None,
    )
    report = AppStamper().stamp(manifest)
    return _fmt(report)


@mcp.tool
def stamp_manifest(manifest_json: str) -> str:
    """Stamp a new app from a full manifest JSON string.

    Use recommend_blueprint to generate a manifest, then pass it here.

    Args:
        manifest_json: Complete AppBlueprintManifest as a JSON string
    """
    manifest = AppBlueprintManifest.from_dict(json.loads(manifest_json))
    report = AppStamper().stamp(manifest)
    return _fmt(report)


@mcp.tool
def inspect_app(app_dir: str) -> str:
    """Inspect a stamped app for drift and restamp readiness.

    Checks whether generated files match the lockfile, whether the
    manifest is still valid, and whether library artifacts have drifted.

    Args:
        app_dir: Path to the stamped app directory
    """
    report = AppStamper().inspect_app(Path(app_dir))
    return _fmt(report)


@mcp.tool
def verify_app(app_dir: str) -> str:
    """Verify integrity of a stamped app against its lockfile.

    Returns ok=true if all locked files match their recorded hashes.

    Args:
        app_dir: Path to the stamped app directory
    """
    report = AppStamper().verify_app_integrity(Path(app_dir))
    return _fmt(report)


@mcp.tool
def restamp_app(
    app_dir: str,
    destination: str = "",
    name: str = "",
    vendor_mode: str = "",
) -> str:
    """Restamp an existing app from its app_manifest.json.

    Preserves ui_schema.json and user settings while regenerating
    all bootstrap code and lockfiles.

    Args:
        app_dir: Path to the existing stamped app
        destination: Optional new destination (default: restamp in place)
        name: Optional new app name
        vendor_mode: Optional override ('module_ref' or 'static')
    """
    report = AppStamper().restamp_existing_app(
        Path(app_dir),
        destination=destination or None,
        name=name or None,
        vendor_mode=vendor_mode or None,
    )
    return _fmt(report)


@mcp.tool
def upgrade_report(app_dir: str) -> str:
    """Compare a stamped app's lockfile against current catalog resolution.

    Shows what would change if you restamped: new services, removed
    services, version changes, dependency changes.

    Args:
        app_dir: Path to the stamped app directory
    """
    report = AppStamper().upgrade_report(Path(app_dir))
    return _fmt(report)


# ---------------------------------------------------------------------------
# Sandbox: stamp → apply → validate → promote
# ---------------------------------------------------------------------------


@mcp.tool
def sandbox_stamp(
    run_id: str,
    template_id: str = "",
    manifest_path: str = "",
    name: str = "",
    vendor_mode: str = "",
    force: bool = False,
) -> str:
    """Create a sandbox workspace and stamp a base app into it.

    The sandbox provides an isolated stamp → patch → validate → promote
    workflow. Exactly one of template_id or manifest_path is required.

    Args:
        run_id: Workspace identifier (e.g. 'my_experiment_20260329')
        template_id: Built-in template to stamp (e.g. 'headless_scanner')
        manifest_path: Path to a manifest JSON file (alternative to template_id)
        name: Optional app display name
        vendor_mode: 'module_ref' or 'static'
        force: If True, delete and recreate existing workspace
    """
    report = SandboxWorkflow().sandbox_stamp(
        run_id=run_id,
        template_id=template_id or None,
        manifest_path=manifest_path or None,
        name=name or None,
        vendor_mode=vendor_mode or None,
        force=force,
    )
    return _fmt(report)


@mcp.tool
def sandbox_apply(
    workspace: str,
    patch_manifests: str = "",
) -> str:
    """Apply patch manifests to a sandbox workspace.

    Patches transform the base-stamped app. After applying, run
    sandbox_validate to check the result.

    Args:
        workspace: Sandbox workspace directory path
        patch_manifests: Comma-separated paths to patch manifest JSON files (optional)
    """
    patches = [p.strip() for p in patch_manifests.split(",") if p.strip()] if patch_manifests else []
    report = SandboxWorkflow().sandbox_apply(workspace, patch_manifests=patches)
    return _fmt(report)


@mcp.tool
def sandbox_validate(workspace: str) -> str:
    """Validate a sandbox workspace after patching.

    Runs compile check, health check, and integrity check on the
    working/ directory.

    Args:
        workspace: Sandbox workspace directory path
    """
    report = SandboxWorkflow().sandbox_validate(workspace)
    return _fmt(report)


@mcp.tool
def sandbox_promote(
    workspace: str,
    destination: str,
    force: bool = False,
) -> str:
    """Promote a validated sandbox workspace to a final destination.

    Copies working/ to the destination directory after validation passes.

    Args:
        workspace: Sandbox workspace directory path
        destination: Final app destination directory
        force: If True, replace existing destination
    """
    report = SandboxWorkflow().sandbox_promote(workspace, destination, force=force)
    return _fmt(report)


if __name__ == "__main__":
    mcp.run()
