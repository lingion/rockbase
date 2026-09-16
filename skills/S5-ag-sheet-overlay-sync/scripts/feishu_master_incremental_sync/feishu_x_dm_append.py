#!/usr/bin/env python3
import argparse
import subprocess
import sys
from pathlib import Path


SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from feishu_x_target_config import get_x_target_defaults


def main() -> None:
    parser = argparse.ArgumentParser(description="Append local X DM rows into the default Feishu X master.")
    parser.add_argument("--source-csv", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--mode", choices=["dry-run", "apply"], default="dry-run")
    parser.add_argument("--target-url", default="")
    parser.add_argument("--sheet-id", default="")
    parser.add_argument("--sheet-title", default="")
    args = parser.parse_args()

    defaults = get_x_target_defaults()
    script_path = Path(__file__).with_name("feishu_master_incremental_sync.py")

    cmd = [
        sys.executable,
        str(script_path),
        "--source-csv",
        args.source_csv,
        "--target-url",
        args.target_url or defaults["target_url"],
        "--sheet-id",
        args.sheet_id or defaults["sheet_id"],
        "--sheet-title",
        args.sheet_title or defaults["sheet_title"],
        "--mode",
        args.mode,
        "--output-dir",
        args.output_dir,
    ]
    result = subprocess.run(cmd)
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
