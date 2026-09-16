from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from common_env import load_simple_env, tests_root


def main() -> int:
    root = tests_root()
    env_path = root / ".env.layer1.local"
    env_data = load_simple_env(env_path)

    query = '"OpenClaw" (AI OR "AI agents" OR automation OR "developer tools")'
    results_path = root / "results" / "scweet_probe.json"

    cmd = [
        sys.executable,
        "-m",
        "Scweet.cli",
        "--auth-token",
        env_data["X_AUTH_TOKEN"],
        "search",
        query,
        "--lang",
        "en",
        "--limit",
        "20",
        "--pretty",
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True)

    payload = {
        "provider": "scweet",
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "query": query,
        "command": " ".join(cmd[:-1]) + " [stdout]",
        "returncode": proc.returncode,
        "stdout_preview": proc.stdout[:4000],
        "stderr_preview": proc.stderr[:4000],
    }
    results_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(results_path)
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
