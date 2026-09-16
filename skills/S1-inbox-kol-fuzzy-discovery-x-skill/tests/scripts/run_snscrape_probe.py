from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime

from common_env import tests_root


def main() -> int:
    root = tests_root()
    results_path = root / "results" / "snscrape_probe.json"
    query = '"OpenClaw" (AI OR "AI agents" OR automation OR "developer tools") lang:en'
    cmd = [
        "snscrape",
        "--jsonl",
        "--max-results",
        "20",
        "twitter-search",
        query,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    payload = {
        "provider": "snscrape",
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "query": query,
        "command": " ".join(cmd),
        "returncode": proc.returncode,
        "stdout_preview": proc.stdout[:4000],
        "stderr_preview": proc.stderr[:4000],
    }
    results_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(results_path)
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
