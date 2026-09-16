from __future__ import annotations

import argparse
import json
from pathlib import Path

import instaloader


def main() -> None:
    parser = argparse.ArgumentParser(description="Import browser-exported Instagram cookies into an Instaloader session file.")
    parser.add_argument("--cookies-json", required=True, help="Path to exported browser cookies JSON.")
    parser.add_argument("--username", required=True, help="Instagram username for session naming.")
    parser.add_argument("--session-dir", required=True, help="Directory to store the Instaloader session file.")
    args = parser.parse_args()

    cookies_path = Path(args.cookies_json).expanduser().resolve()
    session_dir = Path(args.session_dir).expanduser().resolve()
    session_dir.mkdir(parents=True, exist_ok=True)

    payload = json.loads(cookies_path.read_text(encoding="utf-8"))
    cookie_dict = {item["name"]: item["value"] for item in payload if item.get("name") and item.get("value") is not None}

    loader = instaloader.Instaloader(download_pictures=False, download_videos=False, quiet=True)
    loader.context.load_session(args.username, cookie_dict)
    detected = loader.test_login()
    if not detected:
        raise RuntimeError("Cookie import failed: test_login returned no username.")

    session_file = session_dir / f"session-{detected}"
    with session_file.open("wb") as handle:
        loader.context.save_session_to_file(handle)

    print(session_file)


if __name__ == "__main__":
    main()
