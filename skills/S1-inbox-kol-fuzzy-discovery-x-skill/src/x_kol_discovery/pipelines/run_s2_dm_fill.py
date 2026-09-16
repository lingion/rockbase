from __future__ import annotations

import argparse
import json
from pathlib import Path

from x_kol_discovery.io_utils import read_csv, workbench_dir, write_json
from x_kol_discovery.layer3_s2_dm import apply_dm_fills, build_conversation_manifest, load_fills_json, load_workflow_config


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate or apply Mail1 DM fills for S2 cold outreach CSVs.")
    parser.add_argument("--input-csv", required=True, help="Path to S2 cold CSV.")
    parser.add_argument("--run-date", required=True, help="Run date used for workbench routing and backups.")
    parser.add_argument("--mode", choices=["conversation_llm", "apply_json"], default="conversation_llm")
    parser.add_argument("--manifest-out", default="", help="Optional manifest JSON path for conversation_llm mode.")
    parser.add_argument("--fills-json", default="", help="JSON file containing row_number + Greeting/Hook fills.")
    parser.add_argument("--output-csv", default="", help="Optional output CSV. Default: write back to input.")
    parser.add_argument(
        "--workflow-config",
        default="",
        help="Optional workflow JSON config. Use this for 3.2/3.3 style body changes instead of editing code.",
    )
    parser.add_argument("--start-row", type=int, default=1)
    parser.add_argument("--end-row", type=int, default=0)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--overwrite-existing", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    input_csv = Path(args.input_csv).expanduser().resolve()
    out_dir = workbench_dir(args.run_date)
    workflow_config = load_workflow_config(Path(args.workflow_config).expanduser().resolve()) if args.workflow_config else None
    print(f"📍 Routing to: {out_dir}")
    if args.mode == "conversation_llm":
        rows = read_csv(input_csv)
        manifest = build_conversation_manifest(
            rows,
            input_csv=input_csv,
            workflow_config=workflow_config,
            start_row=args.start_row,
            end_row=args.end_row,
            limit=args.limit,
            overwrite_existing=args.overwrite_existing,
        )
        manifest_path = Path(args.manifest_out).expanduser().resolve() if args.manifest_out else out_dir / (
            f"{input_csv.stem}_dm_fill_manifest_{args.run_date}.json"
        )
        write_json(manifest_path, manifest)
        print(json.dumps({"mode": "conversation_llm", "manifest_out": str(manifest_path), "rows_selected": manifest["rows_selected"]}, ensure_ascii=False, indent=2))
        return 0

    if not args.fills_json:
        raise SystemExit("--fills-json is required when --mode apply_json")
    fills = load_fills_json(Path(args.fills_json).expanduser().resolve())
    output_csv = Path(args.output_csv).expanduser().resolve() if args.output_csv else None
    result = apply_dm_fills(
        input_csv=input_csv,
        fills=fills,
        run_date=args.run_date,
        workflow_config=workflow_config,
        output_csv=output_csv,
        overwrite_existing=args.overwrite_existing,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
