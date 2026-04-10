import importlib
import json
from pathlib import Path

SERVICE_SPECS = [{'service_id': 'service_5d51cf3c8f2bb55ea91bd93f', 'class_name': 'IngestEngineMS', 'service_name': 'IngestEngine', 'module_import': 'library.microservices.pipeline._IngestEngineMS', 'description': 'Reads files, chunks text, fetches embeddings, and weaves graph edges.', 'tags': ['ingest', 'rag', 'parsing', 'embedding'], 'capabilities': ['filesystem:read', 'network:outbound', 'db:sqlite'], 'manager_layer': '', 'registry_name': 'IngestEngine', 'is_ui': False, 'endpoints': [{'method_name': 'get_health', 'inputs_json': '{}', 'outputs_json': '{"status": "str", "uptime": "float"}', 'description': 'Standardized health check for service status.', 'tags_json': '["diagnostic", "health"]', 'mode': 'sync'}, {'method_name': 'process_files', 'inputs_json': '{"file_paths": "List[str]", "model_name": "str"}', 'outputs_json': '{"status": "IngestStatus"}', 'description': 'Processes a list of files, ingesting them into the knowledge graph.', 'tags_json': '["ingest", "processing"]', 'mode': 'generator'}]}, {'service_id': 'service_2a64ef8660e5764a7bf5a363', 'class_name': 'SemanticChunkerMS', 'service_name': 'SemanticChunker', 'module_import': 'library.microservices.pipeline._SemanticChunkerMS', 'description': 'The Surgeon: Intelligent Code Splitter that parses source code into logical semantic units (Classes, Functions) using AST.', 'tags': ['utility', 'nlp', 'parser'], 'capabilities': ['python-ast', 'semantic-chunking'], 'manager_layer': '', 'registry_name': 'SemanticChunker', 'is_ui': False, 'endpoints': [{'method_name': 'chunk_file', 'inputs_json': '{"content": "str", "filename": "str"}', 'outputs_json': '{"chunks": "List[Dict]"}', 'description': 'Main entry point to split a file into semantic chunks based on its extension and content.', 'tags_json': '["processing", "chunking"]', 'mode': 'sync'}, {'method_name': 'get_health', 'inputs_json': '{}', 'outputs_json': '{"status": "str", "uptime": "float"}', 'description': 'Standardized health check for service status.', 'tags_json': '["diagnostic", "health"]', 'mode': 'sync'}]}]

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
