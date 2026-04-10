from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
SETTINGS = json.loads((APP_DIR / "settings.json").read_text(encoding="utf-8"))
for candidate in [SETTINGS.get("canonical_import_root", "")] + list(SETTINGS.get("compat_paths", [])):
    if not candidate:
        continue
    resolved = str(APP_DIR / candidate) if not os.path.isabs(candidate) else candidate
    if resolved not in sys.path:
        sys.path.insert(0, resolved)

SERVICE_SPECS = [
    {
        "service_id": "service_mindshard_reference_library_001",
        "class_name": "MindshardReferenceLibraryService",
        "service_name": "MindshardReferenceLibrary",
        "module_import": "lib.reference_service",
        "description": "Global reference library with CAS-backed dedupe, immutable revisions, and agent tools.",
        "endpoints": [
            {"method_name": "library_manifest", "description": "Return package and library metadata."},
            {"method_name": "get_health", "description": "Return runtime health and counts."},
            {"method_name": "library_import", "description": "Import a file or directory into the global library."},
            {"method_name": "library_refresh", "description": "Refresh a document node from its source path."},
            {"method_name": "library_archive", "description": "Archive a node subtree without deleting history."},
            {"method_name": "library_rename", "description": "Rename a node while preserving IDs."},
            {"method_name": "library_move", "description": "Move a node under a new parent group."},
            {"method_name": "library_attach", "description": "Attach a library root to a project."},
            {"method_name": "library_detach", "description": "Detach a library root from a project."},
            {"method_name": "library_list_roots", "description": "List attached roots by default. Provide project_path for attached scope or scope='global' for whole-library browse."},
            {"method_name": "library_list_children", "description": "List children for one node. Attached scope requires project_path unless scope='global' is used."},
            {"method_name": "library_search", "description": "Search attached or global library content. Attached scope requires project_path."},
            {"method_name": "library_get_detail", "description": "Read node and revision detail. Attached scope requires project_path unless scope='global' is used."},
            {"method_name": "library_list_revisions", "description": "List immutable revisions for a node. Attached scope requires project_path unless scope='global' is used."},
            {"method_name": "library_read_excerpt", "description": "Resolve an exact excerpt and record usage. Attached scope requires project_path unless scope='global' is used."},
            {"method_name": "library_export", "description": "Export a node subtree to JSON."},
        ],
    }
]


class BackendRuntime:
    def __init__(self) -> None:
        self.app_dir = APP_DIR
        self.settings = SETTINGS
        self._instances: dict[str, object] = {}

    def list_services(self) -> list[dict]:
        return list(SERVICE_SPECS)

    def _find_spec(self, name: str) -> dict:
        target = str(name).strip()
        for spec in SERVICE_SPECS:
            if target in {spec["class_name"], spec["service_name"], spec["service_id"]}:
                return spec
        raise KeyError(name)

    def get_service(self, name: str, config: dict | None = None):
        spec = self._find_spec(name)
        cache_key = spec["class_name"]
        if config is None and cache_key in self._instances:
            return self._instances[cache_key]
        module = importlib.import_module(spec["module_import"])
        cls = getattr(module, spec["class_name"])
        try:
            instance = cls(config or {})
        except TypeError:
            instance = cls()
        if config is None:
            self._instances[cache_key] = instance
        return instance

    def call(self, service_name: str, endpoint: str, **kwargs):
        service = self.get_service(service_name, config=kwargs.pop("_config", None))
        fn = getattr(service, endpoint)
        return fn(**kwargs)

    def health(self) -> dict:
        report = {"instantiated": {}, "deferred": []}
        for spec in SERVICE_SPECS:
            if spec["class_name"] in self._instances:
                service = self._instances[spec["class_name"]]
                try:
                    report["instantiated"][spec["class_name"]] = service.get_health()
                except Exception as exc:
                    report["instantiated"][spec["class_name"]] = {"status": "error", "error": str(exc)}
            else:
                report["deferred"].append(spec["class_name"])
        return report

    def shutdown(self) -> None:
        for service in list(self._instances.values()):
            closer = getattr(service, "shutdown", None)
            if callable(closer):
                closer()
