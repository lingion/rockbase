"""Audit source files for server-hostile path assumptions."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Sequence

TEXT_SUFFIXES = {".py", ".sh", ".toml", ".yaml", ".yml", ".json"}
EXCLUDED_PARTS = {".git", ".venv", "__pycache__", "site-packages", "tests"}
EXCLUDED_FILES = {"scripts/audit_server_paths.py", "scripts/check_release.py"}
PATTERNS = {
    "ROCKBASE_HOME": re.compile(r"\$\{ROCKBASE_HOME\}"),
    "cwd_assumption": re.compile(r"Path\.cwd\(\)|os\.getcwd\(\)|getcwd\b"),
    "pythonpath_injection": re.compile(r"sys\.path\.insert|PYTHONPATH"),
    "macos_absolute_path": re.compile(r"/Users/[^/\s'\"]+"),
    "windows_absolute_path": re.compile(r"[A-Za-z]:\\\\Users\\"),
}


def audit_tree(root: Path) -> dict:
    counts = {name: {"count": 0, "files": []} for name in PATTERNS}
    scanned = 0
    hard: set[str] = set()
    for path in sorted(root.rglob("*")):
        if EXCLUDED_PARTS.intersection(path.parts):
            continue
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        scanned += 1
        text = path.read_text(encoding="utf-8", errors="replace")
        relative = str(path.relative_to(root))
        if relative in EXCLUDED_FILES:
            scanned -= 1
            continue
        for name, pattern in PATTERNS.items():
            hits = len(pattern.findall(text))
            if hits:
                counts[name]["count"] += hits
                counts[name]["files"].append(relative)
                if name in {"macos_absolute_path", "windows_absolute_path"}:
                    hard.add(relative)
    return {
        "root": str(root),
        "scanned_files": scanned,
        "hard_blockers": sorted(hard),
        "categories": counts,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    report = audit_tree(args.root)
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 2 if report["hard_blockers"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
