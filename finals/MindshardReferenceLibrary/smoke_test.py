from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


def build_fixture(root: Path) -> tuple[Path, Path]:
    source_dir = root / "source"
    project_dir = root / "project"
    source_dir.mkdir(parents=True, exist_ok=True)
    project_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / "README.md").write_text(
        "# Reference Notes\n\nMindshard keeps external references in a global library.\n\nThe agent can search attached roots first.\n",
        encoding="utf-8",
    )
    (source_dir / "worker.py").write_text(
        'def greet(name: str) -> str:\n    """Return a short greeting."""\n    return f"hello {name}"\n',
        encoding="utf-8",
    )
    (source_dir / "blob.bin").write_bytes(b"\x00\x01\x02\x03binary")
    return source_dir, project_dir


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="mindshard_reference_library_") as temp_root:
        root = Path(temp_root)
        library_root = root / "library"
        os.environ["MINDSHARD_REFERENCE_LIBRARY_ROOT"] = str(library_root)
        source_dir, project_dir = build_fixture(root)
        session_db = root / "session.sqlite3"

        from backend import BackendRuntime

        runtime = BackendRuntime()
        imported = runtime.call(
            "MindshardReferenceLibrary",
            "library_import",
            source_path=str(source_dir),
            project_path=str(project_dir),
            attach=True,
            attachment_context={"reason": "smoke_test"},
        )

        root_node_id = imported["node"]["node_id"]
        roots = runtime.call(
            "MindshardReferenceLibrary",
            "library_list_roots",
            project_path=str(project_dir),
        )
        children = runtime.call(
            "MindshardReferenceLibrary",
            "library_list_children",
            node_id=root_node_id,
            project_path=str(project_dir),
        )
        search = runtime.call(
            "MindshardReferenceLibrary",
            "library_search",
            query="global library",
            project_path=str(project_dir),
        )

        first_hit = search["results"][0]
        excerpt = runtime.call(
            "MindshardReferenceLibrary",
            "library_read_excerpt",
            node_id=first_hit["node_id"],
            revision_id=first_hit["revision_id"],
            section_id=first_hit["section_id"],
            scope="attached",
            project_path=str(project_dir),
            session_db_path=str(session_db),
            session_id="session_smoke",
            attachment_context={"reason": "smoke_test"},
        )

        detail = runtime.call(
            "MindshardReferenceLibrary",
            "library_get_detail",
            node_id=first_hit["node_id"],
            project_path=str(project_dir),
        )
        revisions = runtime.call(
            "MindshardReferenceLibrary",
            "library_list_revisions",
            node_id=first_hit["node_id"],
            project_path=str(project_dir),
        )
        exported = runtime.call(
            "MindshardReferenceLibrary",
            "library_export",
            node_id=root_node_id,
        )
        summary = {
            "root_node_id": root_node_id,
            "root_count": len(roots["children"]),
            "child_count": len(children["children"]),
            "search_hits": len(search["results"]),
            "excerpt_operation_id": excerpt["operation_id"],
            "selected_revision": (
                detail["selected_revision"]["revision_id"]
                if detail["selected_revision"]
                else None
            ),
            "revision_count": revisions["revision_count"],
            "export_path": exported["export_path"],
            "library_root": str(library_root),
        }
        print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
