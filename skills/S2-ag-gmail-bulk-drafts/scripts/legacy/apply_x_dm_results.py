#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
import sys
from typing import Dict, List, Sequence

SCRIPT_DIR = Path(__file__).resolve().parent
SHARED_DIR = SCRIPT_DIR.parent / "shared"
if str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))

from common import read_csv_rows, write_csv_rows


def build_content(greeting_name: str, hook: str) -> str:
    return (
        f"Hi {greeting_name},\n\n"
        f"This is Annabel — I run a growth agency helping AI products scale on X and other platforms. {hook}\n"
        " I'd love to put a new product on your radar: a cloud phone built for OpenClaw — giving AI agents an always-on mobile environment to run apps, automate tasks, and interact with the mobile ecosystem 24/7, no physical device needed.\n\n\n"
        "Here's the exciting part —Next week we're about to launch and handpicking a tiny group of top creators for exclusive early access before it goes public. 🚀 You'd be among the very first to try it and share your genuine take with your audience. We're only extending this to creators we truly believe in — and you're one of them.\n\n\n"
        "Beyond this launch, we work with multiple AI products planning long-term partnerships with consistent campaigns. I'd love to build a stable, preferential partnership with you across all of them.\n\n\n"
        "Drop me a line here or on WhatsApp: [+1(515)4518184] — would love to chat! 🙌"
    )


def ensure_hook_column(fieldnames: Sequence[str], rows: List[Dict[str, str]]) -> List[str]:
    names = list(fieldnames)
    if "Mail1_Hook" in names:
        return names
    if "Mail1_Greeting_Name" in names:
        names.insert(names.index("Mail1_Greeting_Name"), "Mail1_Hook")
    else:
        names.append("Mail1_Hook")
    for row in rows:
        row.setdefault("Mail1_Hook", "")
    return names


def load_results(paths: Sequence[str]) -> Dict[int, Dict[str, str]]:
    merged: Dict[int, Dict[str, str]] = {}
    for raw_path in paths:
        path = Path(raw_path)
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError(f"{path} must contain a JSON array.")
        for item in data:
            row_number = int(item["row_number"])
            greeting_name = str(item["Mail1_Greeting_Name"]).strip()
            hook = str(item["Mail1_Hook"]).strip()
            content = str(item.get("Mail1_Content V1", "")).strip() or build_content(greeting_name, hook)
            merged[row_number] = {
                "Mail1_Greeting_Name": greeting_name,
                "Mail1_Hook": hook,
                "Mail1_Content V1": content,
            }
    return merged


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply generated X DM LLM results back to a CSV.")
    parser.add_argument("--input", required=True, help="Source CSV path.")
    parser.add_argument("--output", default="", help="Optional output CSV path. Default overwrites input.")
    parser.add_argument("--results", nargs="+", required=True, help="One or more JSON files produced by LLM generation.")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output) if args.output else input_path
    fieldnames, rows = read_csv_rows(input_path)
    fieldnames = ensure_hook_column(fieldnames, rows)
    results = load_results(args.results)

    updated = 0
    for row_number, row in enumerate(rows, start=1):
        payload = results.get(row_number)
        if not payload:
            continue
        row["Mail1_Greeting_Name"] = payload["Mail1_Greeting_Name"]
        row["Mail1_Hook"] = payload["Mail1_Hook"]
        row["Mail1_Content V1"] = payload["Mail1_Content V1"]
        updated += 1

    write_csv_rows(output_path, fieldnames, rows)
    print(
        json.dumps(
            {
                "input": str(input_path),
                "output": str(output_path),
                "rows_updated": updated,
                "result_files": list(args.results),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
