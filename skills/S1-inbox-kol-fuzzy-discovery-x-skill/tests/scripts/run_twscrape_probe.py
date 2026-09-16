from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from common_env import load_simple_env, tests_root


SCRIPT = """\
import asyncio
import json
from contextlib import aclosing
from twscrape import API

DB_PATH = r"{db_path}"
COOKIES = "auth_token={auth_token}; ct0={ct0}"
QUERY = '"OpenClaw" (AI OR "AI agents" OR automation OR "developer tools") lang:en'

async def main():
    api = API(DB_PATH)
    await api.pool.add_account("layer1_probe", "x", "<YOUR_ACCOUNT_EMAIL>", "x", cookies=COOKIES)
    user = await api.user_by_login("OpenAI")
    out = {{"probe_user": user.username if user else None, "probe_user_id": user.id if user else None}}
    async with aclosing(api.search(QUERY, limit=20)) as gen:
        tweets = []
        async for tw in gen:
            tweets.append({{
                "id": tw.id,
                "username": getattr(tw.user, "username", None),
                "likes": getattr(tw, "likeCount", None),
                "text": getattr(tw, "rawContent", "")[:280],
            }})
            if len(tweets) >= 5:
                break
    out["tweets"] = tweets
    print(json.dumps(out, ensure_ascii=False))

asyncio.run(main())
"""


def _stringify(data: str | bytes | None) -> str:
    if data is None:
        return ""
    if isinstance(data, bytes):
        return data.decode("utf-8", errors="replace")
    return data


def main() -> int:
    root = tests_root()
    env = load_simple_env(root / ".env.layer1.local")
    results_path = root / "results" / "twscrape_probe.json"
    db_path = root / "results" / "twscrape_accounts.db"
    runtime_path = root / "scripts" / "_twscrape_runtime.py"
    runtime_path.write_text(
        SCRIPT.format(
            db_path=db_path,
            auth_token=env["X_AUTH_TOKEN"],
            ct0=env["X_CT0"],
        ),
        encoding="utf-8",
    )
    try:
        proc = subprocess.run(
            [sys.executable, str(runtime_path)],
            capture_output=True,
            text=True,
            timeout=45,
        )
        returncode = proc.returncode
        stdout_preview = proc.stdout[:4000]
        stderr_preview = proc.stderr[:4000]
        timeout_hit = False
    except subprocess.TimeoutExpired as exc:
        returncode = 124
        stdout_preview = _stringify(exc.stdout)[:4000]
        stderr_preview = _stringify(exc.stderr)[:4000]
        timeout_hit = True
    payload = {
        "provider": "twscrape",
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "db_path": str(db_path),
        "runtime_path": str(runtime_path),
        "returncode": returncode,
        "timeout_hit": timeout_hit,
        "stdout_preview": stdout_preview,
        "stderr_preview": stderr_preview,
    }
    results_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(results_path)
    return returncode


if __name__ == "__main__":
    raise SystemExit(main())
