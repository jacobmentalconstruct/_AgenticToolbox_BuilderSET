import importlib
import json
from pathlib import Path

SERVICE_SPECS = [{'service_id': 'service_829049b9857400f42a4f7e01', 'class_name': 'Blake3HashMS', 'service_name': 'Blake3HashMS', 'module_import': 'library.microservices.grouped.storage_group', 'description': 'Produces BLAKE3-compatible content IDs for verbatim content. Uses SHA3-256 as stdlib stand-in; swap for blake3 package when available.', 'tags': ['storage', 'hash', 'cid', 'blake3'], 'capabilities': ['compute'], 'manager_layer': 'storage', 'registry_name': 'Blake3HashMS', 'is_ui': False, 'endpoints': [{'method_name': 'combine_cids', 'inputs_json': '{"cids": "list"}', 'outputs_json': '{"root": "str"}', 'description': 'Combine ordered list of leaf CIDs into a single root hash.', 'tags_json': '["hash", "merkle"]', 'mode': 'sync'}, {'method_name': 'get_health', 'inputs_json': '{}', 'outputs_json': '{"blake3_native": "bool", "status": "str", "uptime": "float"}', 'description': 'Health check.', 'tags_json': '["diagnostic", "health"]', 'mode': 'sync'}, {'method_name': 'hash_bytes', 'inputs_json': '{"blob": "bytes"}', 'outputs_json': '{"cid": "str"}', 'description': 'Hash raw bytes and return hex CID.', 'tags_json': '["hash", "cid"]', 'mode': 'sync'}, {'method_name': 'hash_content', 'inputs_json': '{"content": "str"}', 'outputs_json': '{"cid": "str"}', 'description': 'Hash a string and return hex CID.', 'tags_json': '["hash", "cid"]', 'mode': 'sync'}]}, {'service_id': 'service_f720f8d229f084047159443f', 'class_name': 'CrossLayerResolverMS', 'service_name': 'CrossLayerResolverMS', 'module_import': 'library.microservices.grouped.meaning_relation_observability_manifold_groups', 'description': 'Given a CID or node_id, fetch its presence and data across all available layers.', 'tags': ['manifold', 'cross-layer', 'resolver'], 'capabilities': ['db:read'], 'manager_layer': 'manifold', 'registry_name': 'CrossLayerResolverMS', 'is_ui': False, 'endpoints': [{'method_name': 'get_health', 'inputs_json': '{}', 'outputs_json': '{"status": "str", "uptime": "float"}', 'description': 'Health check.', 'tags_json': '["diagnostic", "health"]', 'mode': 'sync'}, {'method_name': 'resolve', 'inputs_json': '{"artifact_id": "str", "db_path": "str"}', 'outputs_json': '{"presence": "dict"}', 'description': 'Check and return artifact presence across all layers.', 'tags_json': '["resolver", "cross-layer"]', 'mode': 'sync'}]}, {'service_id': 'service_8db39fc00a6b5f1801c93d8b', 'class_name': 'IdentityAnchorMS', 'service_name': 'IdentityAnchorMS', 'module_import': 'library.microservices.grouped.meaning_relation_observability_manifold_groups', 'description': 'Computes and assigns stable identity positions to artifacts. Anchors cross-layer identity using property graph.', 'tags': ['relation', 'identity', 'anchor', 'property-graph'], 'capabilities': ['compute', 'db:read', 'db:write'], 'manager_layer': 'relation', 'registry_name': 'IdentityAnchorMS', 'is_ui': False, 'endpoints': [{'method_name': 'anchor', 'inputs_json': '{"artifact_id": "str", "db_path": "str", "layer_refs": "dict", "stable_props": "dict"}', 'outputs_json': '{"anchor_id": "str"}', 'description': 'Anchor an artifact by registering its presence across layers as named properties on a pg node.', 'tags_json': '["identity", "anchor"]', 'mode': 'sync'}, {'method_name': 'get_anchor', 'inputs_json': '{"artifact_id": "str", "db_path": "str"}', 'outputs_json': '{"anchor": "dict"}', 'description': 'Retrieve the full identity anchor for an artifact.', 'tags_json': '["identity", "read"]', 'mode': 'sync'}, {'method_name': 'get_health', 'inputs_json': '{}', 'outputs_json': '{"status": "str", "uptime": "float"}', 'description': 'Health check.', 'tags_json': '["diagnostic", "health"]', 'mode': 'sync'}, {'method_name': 'resolve_by_property', 'inputs_json': '{"db_path": "str", "prop_key": "str", "prop_value": "str"}', 'outputs_json': '{"matches": "list"}', 'description': 'Resolve identity by searching anchors for a property match.', 'tags_json': '["identity", "resolve"]', 'mode': 'sync'}]}, {'service_id': 'service_628939b28469c9c912f2e88a', 'class_name': 'MerkleRootMS', 'service_name': 'MerkleRootMS', 'module_import': 'library.microservices.grouped.storage_group', 'description': 'Builds, verifies, and diffs Merkle trees from ordered CID leaf lists.', 'tags': ['storage', 'merkle', 'tree', 'diff'], 'capabilities': ['compute'], 'manager_layer': 'storage', 'registry_name': 'MerkleRootMS', 'is_ui': False, 'endpoints': [{'method_name': 'build_tree', 'inputs_json': '{"leaves": "list"}', 'outputs_json': '{"levels": "list", "root": "str"}', 'description': 'Build Merkle tree from leaf CIDs, return root and all levels.', 'tags_json': '["merkle", "build"]', 'mode': 'sync'}, {'method_name': 'diff_trees', 'inputs_json': '{"leaves_a": "list", "leaves_b": "list"}', 'outputs_json': '{"added": "list", "removed": "list", "root_changed": "bool"}', 'description': 'Diff two leaf sets, return added/removed CIDs and whether root changed.', 'tags_json': '["merkle", "diff"]', 'mode': 'sync'}, {'method_name': 'get_health', 'inputs_json': '{}', 'outputs_json': '{"status": "str", "uptime": "float"}', 'description': 'Health check.', 'tags_json': '["diagnostic", "health"]', 'mode': 'sync'}, {'method_name': 'inclusion_proof', 'inputs_json': '{"leaf": "str", "leaves": "list"}', 'outputs_json': '{"proof": "list", "root": "str"}', 'description': 'Generate inclusion proof for a leaf in the tree.', 'tags_json': '["merkle", "proof"]', 'mode': 'sync'}]}, {'service_id': 'service_452f888c23a133940fb93d7f', 'class_name': 'PropertyGraphMS', 'service_name': 'PropertyGraphMS', 'module_import': 'library.microservices.grouped.meaning_relation_observability_manifold_groups', 'description': 'SQLite-backed property graph. Nodes and edges carry named attribute dicts. Foundation for identity anchoring.', 'tags': ['relation', 'property-graph', 'identity', 'graph'], 'capabilities': ['db:read', 'db:write'], 'manager_layer': 'relation', 'registry_name': 'PropertyGraphMS', 'is_ui': False, 'endpoints': [{'method_name': 'find_by_property', 'inputs_json': '{"db_path": "str", "prop_key": "str", "prop_value": "str"}', 'outputs_json': '{"nodes": "list"}', 'description': 'Find nodes where a named property matches a value.', 'tags_json': '["pg", "query"]', 'mode': 'sync'}, {'method_name': 'get_health', 'inputs_json': '{}', 'outputs_json': '{"status": "str", "uptime": "float"}', 'description': 'Health check.', 'tags_json': '["diagnostic", "health"]', 'mode': 'sync'}, {'method_name': 'get_neighbors', 'inputs_json': '{"db_path": "str", "edge_type": "str", "node_id": "str"}', 'outputs_json': '{"neighbors": "list"}', 'description': 'Get neighbors filtered by edge type.', 'tags_json': '["pg", "query"]', 'mode': 'sync'}, {'method_name': 'get_node', 'inputs_json': '{"db_path": "str", "node_id": "str"}', 'outputs_json': '{"node": "dict"}', 'description': 'Fetch a node with its properties.', 'tags_json': '["pg", "read"]', 'mode': 'sync'}, {'method_name': 'upsert_edge', 'inputs_json': '{"db_path": "str", "dst": "str", "edge_type": "str", "props": "dict", "src": "str"}', 'outputs_json': '{"edge_id": "str"}', 'description': 'Upsert a typed edge with properties.', 'tags_json': '["pg", "write"]', 'mode': 'sync'}, {'method_name': 'upsert_node', 'inputs_json': '{"db_path": "str", "node_id": "str", "node_type": "str", "props": "dict"}', 'outputs_json': '{"ok": "bool"}', 'description': 'Upsert a node with named properties.', 'tags_json': '["pg", "write"]', 'mode': 'sync'}]}, {'service_id': 'service_e24bf011e643f1068156b0f0', 'class_name': 'TemporalChainMS', 'service_name': 'TemporalChainMS', 'module_import': 'library.microservices.grouped.storage_group', 'description': 'Append-only Merkle root chain. Each commit links to previous root, enabling diff, snapshot, and audit.', 'tags': ['storage', 'temporal', 'merkle', 'versioning'], 'capabilities': ['db:read', 'db:write'], 'manager_layer': 'storage', 'registry_name': 'TemporalChainMS', 'is_ui': False, 'endpoints': [{'method_name': 'commit', 'inputs_json': '{"db_path": "str", "label": "str", "leaves": "list"}', 'outputs_json': '{"root": "str", "seq": "int"}', 'description': 'Commit a new set of leaves as a chained Merkle root.', 'tags_json': '["temporal", "commit"]', 'mode': 'sync'}, {'method_name': 'get_chain', 'inputs_json': '{"db_path": "str"}', 'outputs_json': '{"chain": "list"}', 'description': 'Return full commit chain in order.', 'tags_json': '["temporal", "history"]', 'mode': 'sync'}, {'method_name': 'get_health', 'inputs_json': '{}', 'outputs_json': '{"status": "str", "uptime": "float"}', 'description': 'Health check.', 'tags_json': '["diagnostic", "health"]', 'mode': 'sync'}, {'method_name': 'get_snapshot', 'inputs_json': '{"db_path": "str", "label": "str"}', 'outputs_json': '{"entry": "dict"}', 'description': 'Look up a named snapshot by label.', 'tags_json': '["temporal", "snapshot"]', 'mode': 'sync'}]}, {'service_id': 'service_b7063b11525b9b507e874440', 'class_name': 'VerbatimStoreMS', 'service_name': 'VerbatimStoreMS', 'module_import': 'library.microservices.grouped.storage_group', 'description': 'Write, read, and deduplicate verbatim lines by CID. Reconstruct text from span references.', 'tags': ['storage', 'verbatim', 'cid', 'db'], 'capabilities': ['db:read', 'db:write'], 'manager_layer': 'storage', 'registry_name': 'VerbatimStoreMS', 'is_ui': False, 'endpoints': [{'method_name': 'fts_search', 'inputs_json': '{"db_path": "str", "limit": "int", "query": "str"}', 'outputs_json': '{"results": "list"}', 'description': 'FTS search over verbatim line content.', 'tags_json': '["verbatim", "search"]', 'mode': 'sync'}, {'method_name': 'get_health', 'inputs_json': '{}', 'outputs_json': '{"status": "str", "uptime": "float"}', 'description': 'Health check.', 'tags_json': '["diagnostic", "health"]', 'mode': 'sync'}, {'method_name': 'read_line', 'inputs_json': '{"cid": "str", "db_path": "str"}', 'outputs_json': '{"content": "str"}', 'description': 'Read a single line by CID.', 'tags_json': '["verbatim", "read"]', 'mode': 'sync'}, {'method_name': 'reconstruct', 'inputs_json': '{"cids": "list", "db_path": "str"}', 'outputs_json': '{"lines": "list"}', 'description': 'Reconstruct ordered text from a list of CIDs.', 'tags_json': '["verbatim", "reconstruct"]', 'mode': 'sync'}, {'method_name': 'write_lines', 'inputs_json': '{"db_path": "str", "lines": "list"}', 'outputs_json': '{"cids": "list", "written": "int"}', 'description': 'Write deduplicated lines, return ordered CIDs.', 'tags_json': '["verbatim", "write"]', 'mode': 'sync'}]}]

class BackendRuntime:
    def __init__(self):
        self.app_dir = Path(__file__).resolve().parent
        self.settings = json.loads((self.app_dir / "settings.json").read_text(encoding="utf-8"))
        self._instances = {}
        self._hub = None
        self._hub_error = ""
        if any(spec.get("manager_layer") for spec in SERVICE_SPECS):
            try:
                from library.orchestrators import LayerHub
                self._hub = LayerHub()
            except Exception as exc:
                self._hub_error = str(exc)

    def list_services(self):
        return list(SERVICE_SPECS)

    def _find_spec(self, name):
        target = str(name).strip()
        for spec in SERVICE_SPECS:
            if target in {spec["class_name"], spec["service_name"], spec["service_id"]}:
                return spec
        return None

    def get_service(self, name, config=None):
        spec = self._find_spec(name)
        if spec is None:
            raise KeyError(name)
        cache_key = spec["class_name"]
        if config is None and cache_key in self._instances:
            return self._instances[cache_key]
        if spec.get("manager_layer") and self._hub is not None:
            manager = self._hub.get_manager(spec["manager_layer"])
            if manager is not None:
                service = manager.get(spec["registry_name"]) or manager.get(spec["class_name"])
                if service is not None:
                    self._instances[cache_key] = service
                    return service
        module = importlib.import_module(spec["module_import"])
        cls = getattr(module, spec["class_name"])
        try:
            instance = cls(config or {})
        except TypeError:
            instance = cls()
        if config is None:
            self._instances[cache_key] = instance
        return instance

    def call(self, service_name, endpoint, **kwargs):
        service = self.get_service(service_name, config=kwargs.pop("_config", None))
        fn = getattr(service, endpoint)
        return fn(**kwargs)

    def health(self):
        report = {"instantiated": {}, "deferred": [], "manager_hub_error": self._hub_error}
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

    def shutdown(self):
        for service in list(self._instances.values()):
            closer = getattr(service, "shutdown", None)
            if callable(closer):
                closer()
