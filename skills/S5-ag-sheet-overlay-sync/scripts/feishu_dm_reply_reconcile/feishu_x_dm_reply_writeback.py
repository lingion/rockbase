#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path


SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from feishu_x_target_config import get_x_target_defaults


def main() -> None:
    defaults = get_x_target_defaults()
    script_path = Path(__file__).with_name("feishu_mark_dm_replied_from_screenshots.py")
    incoming_args = sys.argv[1:]

    has_target_url = any(arg == "--target-url" or arg.startswith("--target-url=") for arg in incoming_args)
    has_sheet_id = any(arg == "--sheet-id" or arg.startswith("--sheet-id=") for arg in incoming_args)
    has_sheet_title = any(arg == "--sheet-title" or arg.startswith("--sheet-title=") for arg in incoming_args)

    cmd = [
        sys.executable,
        str(script_path),
        *( [] if has_target_url else ["--target-url", defaults["target_url"]] ),
        *( [] if has_sheet_id else ["--sheet-id", defaults["sheet_id"]] ),
        *( [] if has_sheet_title else ["--sheet-title", defaults["sheet_title"]] ),
        *incoming_args,
    ]
    result = subprocess.run(cmd)
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
