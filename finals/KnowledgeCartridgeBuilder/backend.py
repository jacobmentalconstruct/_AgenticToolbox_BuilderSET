import importlib
import json
import os
import sys
from pathlib import Path

# --- Bootstrap: ensure vendor/library is importable ---
_APP_DIR = Path(__file__).resolve().parent
_settings_boot = json.loads((_APP_DIR / "settings.json").read_text(encoding="utf-8"))
for _p in [_settings_boot.get("canonical_import_root", "")] + list(_settings_boot.get("compat_paths", [])):
    if not _p:
        continue
    _resolved = str(_APP_DIR / _p) if not os.path.isabs(_p) else _p
    if _resolved not in sys.path:
        sys.path.insert(0, _resolved)

SERVICE_SPECS = [{'service_id': 'service_3249e5d2f2a3d94b7da0115c', 'class_name': 'CartridgeServiceMS', 'service_name': 'CartridgeServiceMS', 'module_import': 'library.microservices.storage._CartridgeServiceMS', 'description': 'The Source of Truth. Manages the Unified Neural Cartridge Format (UNCF v1.0).', 'tags': ['storage', 'database', 'RAG'], 'capabilities': ['sqlite', 'vector-search', 'graph-storage'], 'manager_layer': '', 'registry_name': 'CartridgeServiceMS', 'is_ui': False, 'endpoints': [{'method_name': 'get_directory_tree', 'inputs_json': '{"root": "str"}', 'outputs_json': '{"tree": "dict"}', 'description': 'Builds a nested directory tree structure for UI navigation or context mapping.', 'tags_json': '["vfs", "navigation"]', 'mode': 'sync'}, {'method_name': 'get_health', 'inputs_json': '{}', 'outputs_json': '{"status": "str", "uptime": "float"}', 'description': 'Standardized health check for service status.', 'tags_json': '["diagnostic", "health"]', 'mode': 'sync'}, {'method_name': 'get_status_flags', 'inputs_json': '{}', 'outputs_json': '{"cartridge_health": "str", "ingest_complete": "bool", "refine_complete": "bool"}', 'description': 'Returns key manifest status flags (ingest/refine status and health) in a single call.', 'tags_json': '["status", "health"]', 'mode': 'sync'}, {'method_name': 'search_embeddings', 'inputs_json': '{"limit": "int", "query_vector": "list"}', 'outputs_json': '{"results": "list"}', 'description': 'Performs semantic vector search using sqlite-vec against the cartridge chunks.', 'tags_json': '["search", "vector"]', 'mode': 'sync'}]}, {'service_id': 'service_4a68cc9ec98b2002b0ce2040', 'class_name': 'ChunkingRouterMS', 'service_name': 'ChunkingRouterMS', 'module_import': 'library.microservices.structure._ChunkingRouterMS', 'description': 'The Dispatcher: Routes files to specialized chunkers based on extension (AST for Python, Recursive for Prose).', 'tags': ['orchestration', 'chunking', 'nlp'], 'capabilities': ['routing', 'text-processing'], 'manager_layer': '', 'registry_name': 'ChunkingRouterMS', 'is_ui': False, 'endpoints': [{'method_name': 'chunk_file', 'inputs_json': '{"filename": "str", "max_size": "int", "overlap": "int", "text": "str"}', 'outputs_json': '{"chunks": "list"}', 'description': 'Routes text to the appropriate specialist. Returns a list of CodeChunk objects or raw strings.', 'tags_json': '["routing", "chunking"]', 'mode': 'sync'}, {'method_name': 'get_health', 'inputs_json': '{}', 'outputs_json': '{"status": "str", "uptime": "float"}', 'description': 'Standardized health check for service status.', 'tags_json': '["diagnostic", "health"]', 'mode': 'sync'}]}, {'service_id': 'service_d5220cb6f7951a9cc37dcef5', 'class_name': 'CodeChunkerMS', 'service_name': 'CodeChunker', 'module_import': 'library.microservices.structure._CodeChunkerMS', 'description': 'Splits code into semantic blocks (Classes, Functions) using indentation and regex heuristics.', 'tags': ['parsing', 'chunking', 'code'], 'capabilities': ['filesystem:read'], 'manager_layer': '', 'registry_name': 'CodeChunker', 'is_ui': False, 'endpoints': [{'method_name': 'chunk_file', 'inputs_json': '{"file_path": "str", "max_chars": "int"}', 'outputs_json': '{"chunks": "List[Dict]"}', 'description': 'Reads a file and breaks it into logical blocks based on indentation.', 'tags_json': '["parsing", "chunking"]', 'mode': 'sync'}, {'method_name': 'get_health', 'inputs_json': '{}', 'outputs_json': '{"status": "str", "uptime": "float"}', 'description': 'Standardized health check for service status.', 'tags_json': '["diagnostic", "health"]', 'mode': 'sync'}]}, {'service_id': 'service_f50d72a0519f74a57279de24', 'class_name': 'CodeGrapherMS', 'service_name': 'CodeGrapher', 'module_import': 'library.microservices.relation._CodeGrapherMS', 'description': 'Parses Python code to extract symbols (nodes) and call relationships (edges).', 'tags': ['parsing', 'graph', 'analysis'], 'capabilities': ['filesystem:read'], 'manager_layer': '', 'registry_name': 'CodeGrapher', 'is_ui': False, 'endpoints': [{'method_name': 'get_health', 'inputs_json': '{}', 'outputs_json': '{"status": "str", "uptime": "float"}', 'description': 'Standardized health check for service status.', 'tags_json': '["diagnostic", "health"]', 'mode': 'sync'}, {'method_name': 'scan_directory', 'inputs_json': '{"root_path": "str"}', 'outputs_json': '{"graph_data": "Dict[str, Any]"}', 'description': 'Recursively scans a directory for .py files and builds the graph.', 'tags_json': '["parsing", "graph"]', 'mode': 'sync'}]}, {'service_id': 'service_5d51cf3c8f2bb55ea91bd93f', 'class_name': 'IngestEngineMS', 'service_name': 'IngestEngine', 'module_import': 'library.microservices.pipeline._IngestEngineMS', 'description': 'Reads files, chunks text, fetches embeddings, and weaves graph edges.', 'tags': ['ingest', 'rag', 'parsing', 'embedding'], 'capabilities': ['filesystem:read', 'network:outbound', 'db:sqlite'], 'manager_layer': '', 'registry_name': 'IngestEngine', 'is_ui': False, 'endpoints': [{'method_name': 'get_health', 'inputs_json': '{}', 'outputs_json': '{"status": "str", "uptime": "float"}', 'description': 'Standardized health check for service status.', 'tags_json': '["diagnostic", "health"]', 'mode': 'sync'}, {'method_name': 'process_files', 'inputs_json': '{"file_paths": "List[str]", "model_name": "str"}', 'outputs_json': '{"status": "IngestStatus"}', 'description': 'Processes a list of files, ingesting them into the knowledge graph.', 'tags_json': '["ingest", "processing"]', 'mode': 'generator'}]}, {'service_id': 'service_edfe016bf079afcce7111c4a', 'class_name': 'NeuralServiceMS', 'service_name': 'NeuralService', 'module_import': 'library.microservices.core._NeuralServiceMS', 'description': 'The Brain Interface: Orchestrates local AI operations via Ollama.', 'tags': ['ai', 'neural', 'inference', 'ollama'], 'capabilities': ['text-generation', 'embeddings', 'parallel-processing'], 'manager_layer': '', 'registry_name': 'NeuralService', 'is_ui': False, 'endpoints': [{'method_name': 'check_connection', 'inputs_json': '{}', 'outputs_json': '{"is_alive": "bool"}', 'description': 'Pings Ollama to verify connectivity.', 'tags_json': '["health", "read"]', 'mode': 'sync'}, {'method_name': 'get_available_models', 'inputs_json': '{}', 'outputs_json': '{"models": "List[str]"}', 'description': 'Fetches a list of available models from the local Ollama instance.', 'tags_json': '["ai", "read"]', 'mode': 'sync'}, {'method_name': 'get_embedding', 'inputs_json': '{"text": "str"}', 'outputs_json': '{"embedding": "list"}', 'description': 'Generates a vector embedding for the provided text.', 'tags_json': '["nlp", "vector", "ai"]', 'mode': 'sync'}, {'method_name': 'get_health', 'inputs_json': '{}', 'outputs_json': '{"status": "str", "uptime": "float"}', 'description': 'Standardized health check for service status.', 'tags_json': '["diagnostic", "health"]', 'mode': 'sync'}, {'method_name': 'request_inference', 'inputs_json': '{"format_json": "bool", "prompt": "str", "tier": "str"}', 'outputs_json': '{"response": "str"}', 'description': 'Requests synchronous text generation from a local LLM.', 'tags_json': '["llm", "inference"]', 'mode': 'sync'}, {'method_name': 'update_models', 'inputs_json': '{"embed_model": "str", "fast_model": "str", "smart_model": "str"}', 'outputs_json': '{"status": "str"}', 'description': 'Updates the active model configurations on the fly.', 'tags_json': '["config", "write"]', 'mode': 'sync'}]}, {'service_id': 'service_fc77e047a03d25e6bc2ad9a3', 'class_name': 'PythonChunkerMS', 'service_name': 'PythonChunker', 'module_import': 'library.microservices.structure._PythonChunkerMS', 'description': 'The Python Surgeon: Specialist in Abstract Syntax Tree (AST) parsing for Python source code.', 'tags': ['chunking', 'python', 'ast'], 'capabilities': ['python-ast'], 'manager_layer': '', 'registry_name': 'PythonChunker', 'is_ui': False, 'endpoints': [{'method_name': 'chunk', 'inputs_json': '{"content": "str"}', 'outputs_json': '{"chunks": "List[Dict]"}', 'description': 'Primary entry point for high-fidelity Python-specific AST chunking.', 'tags_json': '["processing", "python"]', 'mode': 'sync'}, {'method_name': 'get_health', 'inputs_json': '{}', 'outputs_json': '{"specialty": "str", "status": "str", "uptime": "float"}', 'description': 'Standardized health check for the Python specialist service.', 'tags_json': '["diagnostic", "health"]', 'mode': 'sync'}]}, {'service_id': 'service_981116e21369431c5bba1de3', 'class_name': 'RefineryServiceMS', 'service_name': 'RefineryService', 'module_import': 'library.microservices.relation._RefineryServiceMS', 'description': "The Night Shift: Processes 'RAW' files into semantic chunks and weaves them into a knowledge graph.", 'tags': ['processing', 'refinery', 'graph', 'RAG'], 'capabilities': ['smart-chunking', 'graph-weaving', 'parallel-embedding'], 'manager_layer': '', 'registry_name': 'RefineryService', 'is_ui': False, 'endpoints': [{'method_name': 'get_health', 'inputs_json': '{}', 'outputs_json': '{"cartridge_health": "str", "status": "str", "uptime": "float"}', 'description': 'Standardized health check to verify the operational state of the Refinery service.', 'tags_json': '["diagnostic", "health"]', 'mode': 'sync'}, {'method_name': 'process_pending', 'inputs_json': '{"batch_size": "int"}', 'outputs_json': '{"processed_count": "int"}', 'description': "Polls the database for files with 'RAW' status and processes them into chunks and graph nodes.", 'tags_json': '["pipeline", "batch"]', 'mode': 'sync'}]}, {'service_id': 'service_7812394e0b7e1a32c3f38e31', 'class_name': 'ScoutMS', 'service_name': 'Scout', 'module_import': 'library.microservices.core._ScoutMS', 'description': 'The Scout: A depth-aware utility for recursively walking local file systems or crawling websites.', 'tags': ['utility', 'scanner', 'crawler'], 'capabilities': ['filesystem:read', 'web:crawl'], 'manager_layer': '', 'registry_name': 'Scout', 'is_ui': False, 'endpoints': [{'method_name': 'flatten_tree', 'inputs_json': '{"tree_node": "dict"}', 'outputs_json': '{"file_list": "list"}', 'description': 'Flattens a hierarchical tree node structure into a simple list of paths.', 'tags_json': '["utility", "processing"]', 'mode': 'sync'}, {'method_name': 'get_health', 'inputs_json': '{}', 'outputs_json': '{"status": "str", "uptime": "float"}', 'description': 'Standardized health check for service status.', 'tags_json': '["diagnostic", "health"]', 'mode': 'sync'}, {'method_name': 'scan_directory', 'inputs_json': '{"root_path": "str", "web_depth": "int"}', 'outputs_json': '{"tree": "dict"}', 'description': 'Main entry point to perform a recursive scan of a directory or a web crawl.', 'tags_json': '["discovery", "recursive"]', 'mode': 'sync'}]}, {'service_id': 'service_6d90bbb63f12b1e5119d5bbd', 'class_name': 'SearchEngineMS', 'service_name': 'SearchEngine', 'module_import': 'library.microservices.meaning._SearchEngineMS', 'description': 'The Oracle: Performs Hybrid Search (Vector Similarity + Keyword Matching) on SQLite databases.', 'tags': ['search', 'vector', 'hybrid', 'rag'], 'capabilities': ['db:sqlite', 'network:outbound', 'compute'], 'manager_layer': '', 'registry_name': 'SearchEngine', 'is_ui': False, 'endpoints': [{'method_name': 'get_health', 'inputs_json': '{}', 'outputs_json': '{"status": "str", "uptime": "float"}', 'description': 'Standardized health check for service status.', 'tags_json': '["diagnostic", "health"]', 'mode': 'sync'}, {'method_name': 'search', 'inputs_json': '{"db_path": "str", "limit": "int", "query": "str"}', 'outputs_json': '{"results": "List[Dict]"}', 'description': 'Main entry point. Returns a list of results sorted by relevance (RRF).', 'tags_json': '["search", "query"]', 'mode': 'sync'}]}, {'service_id': 'service_2631a8a51a886ef5a9d44e52', 'class_name': 'TextChunkerMS', 'service_name': 'TextChunker', 'module_import': 'library.microservices.structure._TextChunkerMS', 'description': 'Splits text into chunks using various strategies (chars, lines).', 'tags': ['chunking', 'nlp', 'rag'], 'capabilities': ['compute'], 'manager_layer': '', 'registry_name': 'TextChunker', 'is_ui': False, 'endpoints': [{'method_name': 'chunk_by_chars', 'inputs_json': '{"chunk_overlap": "int", "chunk_size": "int", "text": "str"}', 'outputs_json': '{"chunks": "List[str]"}', 'description': 'Standard sliding window split by character count.', 'tags_json': '["chunking", "chars"]', 'mode': 'sync'}, {'method_name': 'chunk_by_lines', 'inputs_json': '{"max_chars": "int", "max_lines": "int", "text": "str"}', 'outputs_json': '{"chunks": "List[Dict]"}', 'description': 'Line-preserving chunker, best for code.', 'tags_json': '["chunking", "lines", "code"]', 'mode': 'sync'}, {'method_name': 'chunk_by_paragraphs', 'inputs_json': '{"overlap_paragraphs": "int", "target_chars": "int", "text": "str"}', 'outputs_json': '{"chunks": "List[str]"}', 'description': 'Prose-aware paragraph chunking with overlap between windows.', 'tags_json': '["chunking", "prose", "paragraphs"]', 'mode': 'sync'}, {'method_name': 'get_health', 'inputs_json': '{}', 'outputs_json': '{"status": "str", "uptime": "float"}', 'description': 'Standardized health check for service status.', 'tags_json': '["diagnostic", "health"]', 'mode': 'sync'}]}, {'service_id': 'service_804ffa5ab110ec8015d224c4', 'class_name': 'VectorFactoryMS', 'service_name': 'VectorFactory', 'module_import': 'library.microservices.meaning._VectorFactoryMS', 'description': 'Factory for creating VectorStore instances (FAISS, Chroma).', 'tags': ['vector', 'factory', 'db'], 'capabilities': ['filesystem:read', 'filesystem:write'], 'manager_layer': '', 'registry_name': 'VectorFactory', 'is_ui': False, 'endpoints': [{'method_name': 'create', 'inputs_json': '{"backend": "str", "config": "Dict"}', 'outputs_json': '{"store": "VectorStore"}', 'description': 'Creates and returns a configured VectorStore instance.', 'tags_json': '["vector", "create"]', 'mode': 'sync'}, {'method_name': 'get_health', 'inputs_json': '{}', 'outputs_json': '{"status": "str", "uptime": "float"}', 'description': 'Standardized health check for service status.', 'tags_json': '["diagnostic", "health"]', 'mode': 'sync'}]}]

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
            if config:
                try:
                    instance = cls(**config)
                except TypeError:
                    instance = cls()
            else:
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
