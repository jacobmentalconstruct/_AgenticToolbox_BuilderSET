import argparse
import json
import os
import sys
from pathlib import Path


def _bootstrap():
    app_dir = Path(__file__).resolve().parent
    settings = json.loads((app_dir / "settings.json").read_text(encoding="utf-8"))
    paths = [settings.get("canonical_import_root", "")] + list(settings.get("compat_paths", []))
    for candidate in paths:
        if not candidate:
            continue
        resolved = str(app_dir / candidate) if not os.path.isabs(candidate) else candidate
        if resolved not in sys.path:
            sys.path.insert(0, resolved)
    return settings


SETTINGS = _bootstrap()

from backend import BackendRuntime
from ui import launch_ui, run_headless


def main(argv=None):
    parser = argparse.ArgumentParser(description="Stamped app entry point")
    parser.add_argument("--health", action="store_true", help="Print health JSON and exit")
    parser.add_argument("--no-ui", action="store_true", help="Run without launching the Tkinter UI")
    args = parser.parse_args(argv)
    runtime = BackendRuntime()
    if args.health:
        print(json.dumps(runtime.health(), indent=2))
        return 0
    if args.no_ui or SETTINGS.get("ui_pack") == "headless_pack":
        print(json.dumps(run_headless(runtime), indent=2))
        return 0
    launch_ui(runtime)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
