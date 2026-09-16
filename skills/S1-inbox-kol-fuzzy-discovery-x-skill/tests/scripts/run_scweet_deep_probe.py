from __future__ import annotations

import json
import subprocess
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from common_env import load_simple_env, tests_root


def main() -> int:
    root = tests_root()
    env_path = root / ".env.layer1.local"
    env_data = load_simple_env(env_path)
    results_path = root / "results" / "scweet_deep_probe.json"

    query = '"OpenClaw" (AI OR "AI agents" OR automation OR "developer tools")'
    cmd = [
        "scweet",
        "--auth-token",
        env_data["X_AUTH_TOKEN"],
        "search",
        query,
        "--lang",
        "en",
        "--limit",
        "60",
        "--pretty",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)

    summary: dict[str, object] = {
        "provider": "scweet",
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "query": query,
        "command": " ".join(cmd),
        "returncode": proc.returncode,
        "stderr_preview": proc.stderr[:4000],
        "stdout_preview": proc.stdout[:4000],
    }

    if proc.returncode == 0 and proc.stdout.strip():
        try:
            rows = json.loads(proc.stdout)
        except json.JSONDecodeError:
            rows = []
        by_user: dict[str, dict[str, object]] = defaultdict(
            lambda: {"tweet_count": 0, "max_likes": 0, "max_retweets": 0, "sample_text": ""}
        )
        for row in rows:
            user = row.get("user", {}).get("screen_name") or "unknown"
            likes = row.get("likes") or 0
            retweets = row.get("retweets") or 0
            slot = by_user[user]
            slot["tweet_count"] = int(slot["tweet_count"]) + 1
            slot["max_likes"] = max(int(slot["max_likes"]), int(likes))
            slot["max_retweets"] = max(int(slot["max_retweets"]), int(retweets))
            if not slot["sample_text"]:
                slot["sample_text"] = (row.get("text") or "")[:220]

        hot_users = [
            {"username": username, **data}
            for username, data in by_user.items()
            if int(data["max_likes"]) >= 10 or int(data["max_retweets"]) >= 3
        ]
        hot_users.sort(key=lambda x: (x["max_likes"], x["max_retweets"], x["tweet_count"]), reverse=True)
        summary["result_count"] = len(rows)
        summary["unique_user_count"] = len(by_user)
        summary["hot_user_candidates"] = hot_users[:20]
    results_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(results_path)
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
