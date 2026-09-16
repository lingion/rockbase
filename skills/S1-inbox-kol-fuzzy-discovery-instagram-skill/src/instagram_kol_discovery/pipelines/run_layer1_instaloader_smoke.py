from __future__ import annotations

import json
from pathlib import Path

import instaloader

from instagram_kol_discovery.io_utils import get_env_value, instagram_cookie_dict, skill_dir, workbench_dir, write_json


def _load_best_session(loader: instaloader.Instaloader) -> str:
    username = get_env_value("INSTAGRAM_USERNAME") or "cookie_import"
    session_file = skill_dir() / ".instaloader" / f"session-{username}"
    if session_file.exists():
        with session_file.open("rb") as handle:
            loader.context.load_session_from_file(username, handle)
        return loader.test_login() or username
    cookies = instagram_cookie_dict()
    if cookies:
        loader.context.load_session(username, cookies)
        return loader.test_login() or username
    return ""


def main() -> None:
    run_date = "2026-04-10"
    output_dir = workbench_dir(run_date)
    runlog_path = output_dir / f"instagram_accio_instaloader_smoke_{run_date}.json"
    payload: dict[str, object] = {
        "query": "accio",
        "tests": [],
    }

    loader = instaloader.Instaloader(
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
        quiet=True,
    )
    logged_in_as = _load_best_session(loader)
    payload["logged_in_as"] = logged_in_as

    try:
        hashtag = instaloader.Hashtag.from_name(loader.context, "accio")
        posts = list(hashtag.get_posts())
        payload["tests"].append({"route": "hashtag", "status": "success", "count": len(posts)})
    except Exception as exc:
        payload["tests"].append({"route": "hashtag", "status": "error", "error_type": type(exc).__name__, "error": str(exc)})

    for username in ["thevarunmayya", "jawahirkhalifa", "alibaba.com_official"]:
        try:
            profile = instaloader.Profile.from_username(loader.context, username)
            payload["tests"].append(
                {
                    "route": "profile",
                    "username": username,
                    "status": "success",
                    "followers": profile.followers,
                    "full_name": profile.full_name,
                }
            )
        except Exception as exc:
            payload["tests"].append(
                {
                    "route": "profile",
                    "username": username,
                    "status": "error",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )

    write_json(runlog_path, payload)
    print(runlog_path)


if __name__ == "__main__":
    main()
