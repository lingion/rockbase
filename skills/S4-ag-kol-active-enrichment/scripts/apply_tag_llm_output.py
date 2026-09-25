from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
from datetime import datetime
from pathlib import Path

TARGET_FIELDS = [
    "账号类目标签",
    "Tag_Section",
    "tag_topics",
    "tag_scenarios",
    "tag_audience",
    "tag_narrative",
    "tag_platform_fit",
    "tag_market",
    "tag_commercial",
    "tag_risk",
    "tag_confidence",
]


def _load_contracts():
    try:
        from rockbase import llm_stage_contracts as _contracts
    except ImportError:  # pragma: no cover - standalone CLI path
        import sys as _sys
        _root = Path(__file__).resolve().parents[4]
        if str(_root) not in _sys.path:
            _sys.path.insert(0, str(_root))
        from rockbase import llm_stage_contracts as _contracts
    return _contracts


def build_enrichment_artifact(row_key, suggestions, evidence, validation):
    """Adapter to the shared S4 enrichment contract (allow-listed labels)."""
    return _load_contracts().build_enrichment_artifact(row_key, suggestions, evidence, validation)


def apply_approved_artifact(artifact_id, version, target, *, execute=False):
    """Apply an enrichment only when the target record is an approved,
    current artifact version. execute=False is always a dry preview."""
    return _load_contracts().apply_approved_artifact(artifact_id, version, target, execute=execute)


def extract_json(text: str) -> dict | None:
    text = str(text or "").strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        pass
    m = re.search(r"```json\s*(\{.*?\})\s*```", text, flags=re.S)
    if m:
        try:
            parsed = json.loads(m.group(1))
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None
    return None


def make_backup(csv_path: Path, root: Path) -> str:
    bak_dir = root / "Agency/list-bak" / datetime.now().strftime("%Y-%m-%d")
    bak_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%H%M%S")
    bak_path = bak_dir / f"{csv_path.name}_bak_{ts}.csv"
    shutil.copy2(csv_path, bak_path)
    return str(bak_path.relative_to(root))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--llm-output-jsonl", required=True, type=Path)
    args = parser.parse_args()

    root = args.csv.resolve().parents[2]
    backup_rel = make_backup(args.csv, root)

    with args.csv.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames or []

    outputs: dict[str, dict] = {}
    for line in args.llm_output_jsonl.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        outer = extract_json(line) or {}
        payload = outer
        if "raw_content" in outer:
            payload = extract_json(str(outer.get("raw_content", ""))) or {}
        account_id = str(payload.get("账号ID", "") or outer.get("custom_id", "")).strip()
        if account_id:
            outputs[account_id] = payload

    changed = 0
    for row in rows:
        account_id = str(row.get("账号ID", "") or "").strip()
        payload = outputs.get(account_id)
        if not payload:
            continue

        row_changed = False
        for field in TARGET_FIELDS:
            if field not in fieldnames:
                continue
            new_val = str(payload.get(field, "") or "").strip()
            old_val = str(row.get(field, "") or "").strip()
            if new_val != old_val:
                row[field] = new_val
                row_changed = True
        if row_changed:
            changed += 1

    with args.csv.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(json.dumps({"backup": backup_rel, "changed_rows": changed, "csv": str(args.csv)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
