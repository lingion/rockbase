#!/usr/bin/env python3
"""Deprecated compatibility entrypoint.

Use:
- prepare_reply_jobs.py
- sample_reply_drafts.py
- bulk_reply_drafts.py
"""

from pathlib import Path
import sys


def main() -> None:
    script_dir = Path(__file__).resolve().parent
    msg = "\n".join(
        [
            "This entrypoint is deprecated.",
            "Use the manifest workflow instead:",
            f"- {script_dir / 'prepare_reply_jobs.py'}",
            f"- {script_dir / 'sample_reply_drafts.py'}",
            f"- {script_dir / 'bulk_reply_drafts.py'}",
        ]
    )
    sys.stderr.write(msg + "\n")
    raise SystemExit(1)


if __name__ == "__main__":
    main()
