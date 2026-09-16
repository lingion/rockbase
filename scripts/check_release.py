#!/usr/bin/env python3
"""Offline structural, syntax, and high-confidence secret checks for this release."""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".csv", ".json", ".md", ".py", ".toml", ".txt", ".yaml", ".yml"}
SKIP_FILES = {Path(__file__).resolve(), ROOT / "RELEASE_AUDIT.md"}
SAFE_EMAIL_SUFFIXES = ("@example.invalid", ".example.invalid")

CHECKS = {
    "macOS personal absolute path": re.compile(r"/Users/[^/\s]+/"),
    "Windows personal absolute path": re.compile(r"[A-Za-z]:\\\\Users\\\\[^\\\s]+\\\\"),
    "private key block": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "Google API key shape": re.compile(r"AIza[0-9A-Za-z_-]{30,}"),
    "Google OAuth access token shape": re.compile(r"ya29\.[0-9A-Za-z_-]{20,}"),
    "Google refresh token shape": re.compile(r"1//[0-9A-Za-z_-]{20,}"),
}
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def iter_files():
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        if any(part in {".git", ".pytest_cache", "__pycache__", ".venv"} for part in path.parts):
            continue
        yield path


def main() -> int:
    failures: list[str] = []
    files = list(iter_files())
    symlinks = [path for path in ROOT.rglob("*") if path.is_symlink()]
    if symlinks:
        failures.append(f"symlinks found: {len(symlinks)}")

    skill_dirs = sorted(path.parent for path in (ROOT / "skills").glob("*/SKILL.md"))
    missing_readmes = [path for path in skill_dirs if not (path / "README.md").is_file()]
    if missing_readmes:
        failures.append(f"skill README missing: {len(missing_readmes)}")

    python_count = 0
    for path in files:
        if path.suffix == ".py":
            python_count += 1
            try:
                ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except (SyntaxError, UnicodeDecodeError) as exc:
                failures.append(f"Python syntax/encoding: {path.relative_to(ROOT)}: {exc}")
        if path in SKIP_FILES or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for label, pattern in CHECKS.items():
            if pattern.search(content):
                failures.append(f"{label}: {path.relative_to(ROOT)}")
        unsafe_emails = [email for email in EMAIL.findall(content) if not email.lower().endswith(SAFE_EMAIL_SUFFIXES)]
        if unsafe_emails:
            failures.append(f"non-example email: {path.relative_to(ROOT)}")

    forbidden_names = []
    for path in files:
        name = path.name.lower()
        if name == ".env.example":
            continue
        if name.startswith(".env") or name in {"token.json", "credentials.json", "cookies.json"}:
            forbidden_names.append(path.relative_to(ROOT))
        elif name.startswith("client_secret") and path.suffix.lower() == ".json":
            forbidden_names.append(path.relative_to(ROOT))
        elif path.suffix.lower() in {".key", ".p12", ".pem"}:
            forbidden_names.append(path.relative_to(ROOT))
    if forbidden_names:
        failures.append(f"sensitive filenames: {len(forbidden_names)}")

    print(f"files={len(files)} skills={len(skill_dirs)} python={python_count}")
    if failures:
        print("FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("PASS: structure, Python syntax, personal-path, email, and high-confidence secret checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
