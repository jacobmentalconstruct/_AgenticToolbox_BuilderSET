from __future__ import annotations

import json
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock


TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

from lib.reference_service import MindshardReferenceLibraryService
from lib.reference_sessions import EvidenceShelfStore, SessionStore
from src.core.reference_library.provider_contracts import ProviderRequest, ProviderSection
from src.core.reference_library.providers import ProviderRegistry
from src.core.reference_library.store import ReferenceLibraryStore


def _tree_runtime_available() -> bool:
    try:
        import tree_sitter_language_pack  # noqa: F401
    except Exception:
        return False
    return True


def _build_world(root: Path) -> dict[str, object]:
    source_dir = root / "source"
    project_dir = root / "project"
    library_root = root / "library"
    source_dir.mkdir()
    project_dir.mkdir()

    source_file = source_dir / "notes.md"
    source_file.write_text(
        "# Heading\n\nMindshard reference excerpt text for testing.\n",
        encoding="utf-8",
    )

    service = MindshardReferenceLibraryService(
        {"reference_library_root": str(library_root)}
    )
    imported = service.library_import(
        str(source_file),
        project_path=str(project_dir),
        attach=True,
    )

    session_db_path = project_dir / ".mindshard" / "sessions" / "sessions.db"
    evidence_db_path = project_dir / ".mindshard" / "evidence" / "evidence.sqlite3"
    session_store = SessionStore(session_db_path)
    evidence_store = EvidenceShelfStore(evidence_db_path)
    return {
        "service": service,
        "project_dir": project_dir,
        "imported": imported,
        "session_store": session_store,
        "evidence_store": evidence_store,
    }


class ReferenceLibraryStandaloneTests(unittest.TestCase):
    def test_import_search_and_idempotent_excerpt_reads(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ref_lib_tool_") as temp_root:
            world = _build_world(Path(temp_root))
            service = world["service"]
            project_dir = world["project_dir"]
            imported = world["imported"]
            session_store = world["session_store"]
            evidence_store = world["evidence_store"]

            roots = service.library_list_roots(project_path=str(project_dir))
            self.assertEqual(len(roots["children"]), 1)
            self.assertTrue(roots["children"][0]["attachment"]["attached"])

            hits = service.library_search(
                "reference excerpt",
                project_path=str(project_dir),
            )
            self.assertEqual(len(hits["results"]), 1)
            self.assertEqual(hits["results"][0]["scope"], "attached")

            first = service.library_read_excerpt(
                node_id=imported["node"]["node_id"],
                revision_id=imported["revision"]["revision_id"],
                section_id=imported["sections"][0]["section_id"],
                project_path=str(project_dir),
                session_db_path=str(session_store.db_path),
                session_id="session_smoke",
            )
            second = service.library_read_excerpt(
                node_id=imported["node"]["node_id"],
                revision_id=imported["revision"]["revision_id"],
                section_id=imported["sections"][0]["section_id"],
                project_path=str(project_dir),
                session_db_path=str(session_store.db_path),
                session_id="session_smoke",
            )

            self.assertTrue(first["usage_recorded"])
            self.assertTrue(first["cache_recorded"])
            self.assertTrue(first["evidence_mirrored"])
            self.assertFalse(second["usage_recorded"])
            self.assertFalse(second["cache_recorded"])
            self.assertFalse(second["evidence_mirrored"])
            self.assertEqual(first["operation_id"], second["operation_id"])
            expected_strategy = "tree_splitter" if _tree_runtime_available() else "peg_document"
            self.assertEqual(first["provenance"]["strategy_used"], expected_strategy)

            self.assertEqual(len(session_store.list_library_usage()), 1)
            self.assertEqual(len(session_store.list_library_excerpt_cache()), 1)
            self.assertEqual(evidence_store.count(), 1)

    def test_scope_defaults_to_attached(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ref_lib_tool_") as temp_root:
            temp_root_path = Path(temp_root)
            source_dir = temp_root_path / "source"
            project_dir = temp_root_path / "project"
            library_root = temp_root_path / "library"
            source_dir.mkdir()
            project_dir.mkdir()

            attached_file = source_dir / "attached.md"
            unattached_file = source_dir / "unattached.md"
            attached_file.write_text("# Attached\n\nvisible\n", encoding="utf-8")
            unattached_file.write_text("# Unattached\n\nhidden\n", encoding="utf-8")

            service = MindshardReferenceLibraryService(
                {"reference_library_root": str(library_root)}
            )
            attached = service.library_import(
                str(attached_file),
                project_path=str(project_dir),
                attach=True,
            )
            unattached = service.library_import(
                str(unattached_file),
                project_path=str(project_dir),
                attach=False,
            )

            roots = service.library_list_roots(project_path=str(project_dir))
            self.assertEqual(
                [row["node_id"] for row in roots["children"]],
                [attached["node"]["node_id"]],
            )

            global_roots = service.library_list_roots(
                scope="global",
                project_path=str(project_dir),
            )
            self.assertEqual(
                {row["node_id"] for row in global_roots["children"]},
                {attached["node"]["node_id"], unattached["node"]["node_id"]},
            )

            with self.assertRaises(PermissionError):
                service.library_get_detail(
                    unattached["node"]["node_id"],
                    project_path=str(project_dir),
                )

    def test_provider_selection_covers_tree_peg_and_fallback(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ref_lib_tool_") as temp_root:
            temp_root_path = Path(temp_root)
            source_dir = temp_root_path / "source"
            library_root = temp_root_path / "library"
            source_dir.mkdir()

            files = {
                "code.ts": "export function greet(name: string) { return `hi ${name}`; }\n",
                "notes.md": "# Heading\n\nParagraph.\n\n## Nested\nMore text.\n",
                "plain.txt": "Plain paragraph one.\n\nPlain paragraph two.\n",
                "events.log": "2026-04-05 12:00:00 started\n2026-04-05 12:01:00 finished\n",
            }
            for name, content in files.items():
                (source_dir / name).write_text(content, encoding="utf-8")

            service = MindshardReferenceLibraryService(
                {"reference_library_root": str(library_root)}
            )

            ts_import = service.library_import(str(source_dir / "code.ts"))
            md_import = service.library_import(str(source_dir / "notes.md"))
            txt_import = service.library_import(str(source_dir / "plain.txt"))
            log_import = service.library_import(str(source_dir / "events.log"))

            self.assertTrue(ts_import["sections"])
            self.assertIn(
                ts_import["revision"]["provider_id"],
                {"tree_sitter_reference_provider", "readable_text_fallback_provider"},
            )

            if _tree_runtime_available():
                self.assertEqual(ts_import["revision"]["strategy_used"], "tree_splitter")
                self.assertEqual(
                    ts_import["revision"]["provider_id"],
                    "tree_sitter_reference_provider",
                )
                self.assertEqual(md_import["revision"]["strategy_used"], "tree_splitter")
                self.assertEqual(
                    md_import["revision"]["provider_id"],
                    "tree_sitter_reference_provider",
                )
            else:
                self.assertEqual(ts_import["revision"]["strategy_used"], "fallback_chunker")
                self.assertEqual(
                    ts_import["revision"]["provider_id"],
                    "readable_text_fallback_provider",
                )
                self.assertEqual(md_import["revision"]["strategy_used"], "peg_document")
                self.assertEqual(
                    md_import["revision"]["provider_id"],
                    "prose_document_provider",
                )
            self.assertTrue(md_import["sections"])

            self.assertEqual(txt_import["revision"]["strategy_used"], "peg_document")
            self.assertEqual(
                txt_import["revision"]["provider_id"],
                "prose_document_provider",
            )
            self.assertTrue(txt_import["sections"])

            self.assertEqual(log_import["revision"]["strategy_used"], "fallback_chunker")
            self.assertEqual(
                log_import["revision"]["provider_id"],
                "readable_text_fallback_provider",
            )
            self.assertTrue(log_import["sections"])

    def test_dict_result_provider_sections_are_coerced_and_importable(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ref_lib_tool_") as temp_root:
            temp_root_path = Path(temp_root)
            module_root = temp_root_path / "providers"
            module_root.mkdir()
            sys.path.insert(0, str(module_root))
            try:
                (module_root / "fake_provider.py").write_text(
                    textwrap.dedent(
                        """
                        def parse(request, text):
                            return {
                                "provider_id": "custom_dict_provider",
                                "provider_kind": "microservice_provider",
                                "provider_version": "1.0.0",
                                "strategy_used": "peg_document",
                                "status": "ok",
                                "warnings": [],
                                "sections": [
                                    {
                                        "section_id": f"{request.request_id}:section:1",
                                        "parent_section_id": None,
                                        "ordinal": 1,
                                        "depth": 1,
                                        "section_kind": "document_section",
                                        "anchor_path": "prose/1",
                                        "title": "Section 1",
                                        "summary": "Body summary",
                                        "exact_text": text,
                                        "char_start": 0,
                                        "char_end": len(text),
                                        "source_span": {"kind": "whole_document"},
                                        "metadata": {"logical_path": request.logical_path},
                                    }
                                ],
                            }
                        """
                    ).strip(),
                    encoding="utf-8",
                )

                manifest_path = temp_root_path / "providers_manifest.json"
                manifest_path.write_text(
                    json.dumps(
                        {
                            "providers": [
                                {
                                    "provider_id": "custom_dict_provider",
                                    "schema_version": "1.0",
                                    "provider_kind": "microservice_provider",
                                    "strategy": "peg_document",
                                    "priority": 99,
                                    "entrypoint": "fake_provider:parse",
                                    "supported_extensions": [".txt"],
                                    "supported_media_types": ["text/plain"],
                                    "healthcheck": "",
                                    "timeout_sec": 20,
                                    "enabled": True,
                                    "version": "1.0.0",
                                }
                            ]
                        }
                    ),
                    encoding="utf-8",
                )

                registry = ProviderRegistry(manifest_path=manifest_path)
                request = ProviderRequest(
                    request_id="request_test",
                    strategy_hint="peg_document",
                    logical_path="docs/example.txt",
                    media_type="text/plain",
                    extension=".txt",
                    content_hash="hash",
                    text_path=None,
                    blob_path=None,
                    max_chars=1200,
                    overlap_chars=120,
                    metadata={},
                )
                provider = registry.select(request, readable_text=True)
                self.assertIsNotNone(provider)
                result = provider.parse(request, "Paragraph one.\n\nParagraph two.\n")
                self.assertEqual(result.provider_id, "custom_dict_provider")
                self.assertIsInstance(result.sections[0], ProviderSection)

                library_root = temp_root_path / "library"
                library_root.mkdir()
                (library_root / "providers_manifest.json").write_text(
                    manifest_path.read_text(encoding="utf-8"),
                    encoding="utf-8",
                )
                store = ReferenceLibraryStore(root_dir=library_root)
                source_file = temp_root_path / "example.txt"
                source_file.write_text(
                    "Paragraph one.\n\nParagraph two.\n",
                    encoding="utf-8",
                )
                imported = store.import_path(str(source_file), title="Example")
                self.assertEqual(
                    imported["revision"]["provider_id"],
                    "custom_dict_provider",
                )
                self.assertTrue(imported["sections"])
            finally:
                sys.path.remove(str(module_root))

    def test_builtin_provider_manifest_reconciles_to_current_defaults(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ref_lib_tool_") as temp_root:
            temp_root_path = Path(temp_root)
            manifest_path = temp_root_path / "providers_manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "providers": [
                            {
                                "provider_id": "tree_sitter_reference_provider",
                                "schema_version": "0.9",
                                "provider_kind": "microservice_provider",
                                "strategy": "tree_splitter",
                                "priority": 1,
                                "entrypoint": "legacy.module:parse",
                                "supported_extensions": [".legacy"],
                                "supported_media_types": ["text/legacy"],
                                "healthcheck": "legacy.module:health",
                                "timeout_sec": 5,
                                "enabled": False,
                                "version": "0.0.1",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            with mock.patch(
                "src.core.reference_library.providers._tree_sitter_runtime_available",
                return_value=True,
            ):
                registry = ProviderRegistry(manifest_path=manifest_path)

            manifests = {row["provider_id"]: row for row in registry.manifests()}
            tree_manifest = manifests["tree_sitter_reference_provider"]
            self.assertTrue(tree_manifest["enabled"])
            self.assertEqual(tree_manifest["entrypoint"], "src.core.reference_library.adapters.reference_tree_sitter_provider:ReferenceTreeSitterProvider.parse")
            self.assertIn(".md", tree_manifest["supported_extensions"])
            self.assertIn("python_ast_provider", manifests)
            self.assertIn("prose_document_provider", manifests)
            self.assertIn("readable_text_fallback_provider", manifests)

    def test_runtime_boundary_stays_inside_tool_package(self) -> None:
        modules = {
            "backend": __import__("backend"),
            "lib.reference_service": __import__("lib.reference_service", fromlist=["*"]),
            "src.core.reference_library.service": __import__(
                "src.core.reference_library.service",
                fromlist=["*"],
            ),
            "src.core.reference_library.store": __import__(
                "src.core.reference_library.store",
                fromlist=["*"],
            ),
            "src.core.reference_library.providers": __import__(
                "src.core.reference_library.providers",
                fromlist=["*"],
            ),
        }
        for module in modules.values():
            module_path = Path(module.__file__).resolve()
            self.assertTrue(str(module_path).startswith(str(TOOL_ROOT)))
            self.assertNotIn("_MindshardAGENT", str(module_path))

        forbidden_markers = [
            "_MindshardAGENT",
            "src.core.sessions",
            "src.core.agent",
            "src.mcp.server",
            "project_command_handler",
        ]
        for path in TOOL_ROOT.rglob("*.py"):
            if "tests" in path.parts:
                continue
            text = path.read_text(encoding="utf-8")
            for marker in forbidden_markers:
                self.assertNotIn(marker, text, msg=f"{path} contains forbidden marker {marker}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
