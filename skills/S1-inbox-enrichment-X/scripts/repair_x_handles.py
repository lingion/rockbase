from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

from load_env import default_workbench_dir


DEFAULT_REPAIRS = {
    "@alaborobot": "@alliekmiller",
    "@muaborobot": "@MushtaqBilalPhD",
    "@jiaborobot": "@DrJimFan",
    "@anaborobot": "@AnthropicAI",
    "@aborobot_replit": "@amasad",
    "@huaborobot": "@huggingface",
}


def clean_notes(text: str) -> str:
    value = str(text or "")
    value = re.sub(r"(?:\s*\|\s*)?API 无 tweets", "", value)
    value = re.sub(r"\s*\|\s*\|\s*", " | ", value)
    return value.strip(" |")


def load_repairs(mapping_path: Path | None) -> dict[str, str]:
    if not mapping_path:
        return DEFAULT_REPAIRS.copy()
    data = json.loads(mapping_path.read_text(encoding="utf-8"))
    return {str(k): str(v) for k, v in data.items()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--mapping-json", type=Path)
    parser.add_argument("--workbench-date", default="")
    args = parser.parse_args()

    repairs = load_repairs(args.mapping_json)
    out_dir = default_workbench_dir(args.workbench_date or None)
    out_dir.mkdir(parents=True, exist_ok=True)

    with args.csv.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
        fieldnames = list(rows[0].keys()) if rows else []

    audit_rows = []
    changed = 0
    for row in rows:
        old_handle = str(row.get("账号ID") or "").strip()
        new_handle = repairs.get(old_handle)
        if not new_handle:
            continue
        row["账号ID"] = new_handle
        notes = clean_notes(row.get("联系方式备注", ""))
        repair_note = f"Handle repaired {old_handle} -> {new_handle}"
        row["联系方式备注"] = " | ".join(x for x in [notes, repair_note] if x)
        audit_rows.append(
            {
                "old_handle": old_handle,
                "new_handle": new_handle,
                "name": row.get("频道/作者名称", ""),
            }
        )
        changed += 1

    with args.csv.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    audit_path = out_dir / "x_handle_repairs_applied_en_batch1.json"
    audit_path.write_text(json.dumps(audit_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"changed": changed, "audit_path": str(audit_path)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
