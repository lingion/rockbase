#!/usr/bin/env python3
import argparse
import csv
import json
import shutil
from pathlib import Path
from typing import Dict, List


DATE_TAG = "2026-03-16"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build canonical batch folders for reply recovery workbench.")
    parser.add_argument("--workbench-dir", required=True, help="Path to rockbase-gmail-reply-recovery root.")
    return parser.parse_args()


def read_csv_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_json(path: Path, payload: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def copy_file(src: Path, dst: Path, manifest: List[Dict[str, str]]) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    manifest.append({"source": str(src), "target": str(dst), "mode": "copy"})


def copy_tree(src: Path, dst: Path, manifest: List[Dict[str, str]]) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    manifest.append({"source": str(src), "target": str(dst), "mode": "copytree"})


def rewrite_summary_paths(path: Path, replacements: Dict[str, str]) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    changed = False
    for key, value in list(payload.items()):
        if isinstance(value, str) and value in replacements:
            payload[key] = replacements[value]
            changed = True
    if changed:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_thread_ids_from_messages(messages_csv: Path, output_json: Path) -> None:
    rows = read_csv_rows(messages_csv)
    thread_ids = []
    seen = set()
    for row in rows:
        thread_id = (row.get("thread_id") or "").strip()
        if thread_id and thread_id not in seen:
            seen.add(thread_id)
            thread_ids.append(thread_id)
    output_json.write_text(json.dumps(thread_ids, ensure_ascii=False, indent=2), encoding="utf-8")


def rewrite_batch3_summary(summary_path: Path, batch_dir: Path) -> None:
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    replacements = {
        "output_csv": batch_dir / f"{DATE_TAG}_batch-003_full_messages.csv",
        "output_jsonl": batch_dir / f"{DATE_TAG}_batch-003_full_messages.jsonl",
        "attachments_csv": batch_dir / f"{DATE_TAG}_batch-003_attachment_inventory.csv",
    }
    for key, value in replacements.items():
        if key in payload:
            payload[key] = str(value.resolve())
    summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    args = parse_args()
    workbench = Path(args.workbench_dir).resolve()
    validation_dir = workbench / "01-validation"
    review_dir = workbench / "02-review-ready"
    manifest_rows: List[Dict[str, str]] = []
    summary_rewrites: List[str] = []

    batches = {
        "batch-001": {
            "legacy_dir": validation_dir / "first20-full",
            "legacy_thread_ids": None,
            "legacy_review_csv": review_dir / "rockbase_gmail_reply_review_table_first20_v3.csv",
            "legacy_review_summary": review_dir / "rockbase_gmail_reply_review_table_first20_v3_summary.json",
        },
        "batch-002": {
            "legacy_dir": validation_dir / "next20-full",
            "legacy_thread_ids": validation_dir / "thread_ids_21_40.json",
            "legacy_review_csv": review_dir / "rockbase_gmail_reply_review_table_next20_v3.csv",
            "legacy_review_summary": review_dir / "rockbase_gmail_reply_review_table_next20_v3_summary.json",
        },
    }

    for batch_name, cfg in batches.items():
        batch_dir = validation_dir / f"{DATE_TAG}_{batch_name}"
        copy_tree(cfg["legacy_dir"], batch_dir, manifest_rows)

        rename_map = {
            batch_dir / "reply_batch_full_first20.csv": batch_dir / f"{DATE_TAG}_{batch_name}_full_messages.csv",
            batch_dir / "reply_batch_full_first20.jsonl": batch_dir / f"{DATE_TAG}_{batch_name}_full_messages.jsonl",
            batch_dir / "reply_batch_full_first20_summary.json": batch_dir / f"{DATE_TAG}_{batch_name}_full_fetch_summary.json",
            batch_dir / "reply_batch_attachments_first20.csv": batch_dir / f"{DATE_TAG}_{batch_name}_attachment_inventory.csv",
            batch_dir / "attachment_extraction_report.csv": batch_dir / f"{DATE_TAG}_{batch_name}_attachment_extraction_report.csv",
            batch_dir / "attachment_extraction_summary.json": batch_dir / f"{DATE_TAG}_{batch_name}_attachment_extraction_summary.json",
            batch_dir / "rockbase_gmail_reply_review_table_first20.csv": batch_dir / f"{DATE_TAG}_{batch_name}_review_table.csv",
            batch_dir / "rockbase_gmail_reply_review_table_first20_summary.json": batch_dir / f"{DATE_TAG}_{batch_name}_review_table_summary.json",
        }
        for src, dst in rename_map.items():
            if src.exists():
                if dst.exists():
                    dst.unlink()
                src.rename(dst)
                manifest_rows.append({"source": str(src), "target": str(dst), "mode": "rename_in_copy"})

        full_messages = batch_dir / f"{DATE_TAG}_{batch_name}_full_messages.csv"
        thread_ids_path = batch_dir / f"{DATE_TAG}_{batch_name}_thread_ids.json"
        if cfg["legacy_thread_ids"] and cfg["legacy_thread_ids"].exists():
            copy_file(cfg["legacy_thread_ids"], thread_ids_path, manifest_rows)
        else:
            build_thread_ids_from_messages(full_messages, thread_ids_path)
            manifest_rows.append({"source": str(full_messages), "target": str(thread_ids_path), "mode": "derived_thread_ids"})

        full_fetch_summary = batch_dir / f"{DATE_TAG}_{batch_name}_full_fetch_summary.json"
        attachment_summary = batch_dir / f"{DATE_TAG}_{batch_name}_attachment_extraction_summary.json"
        replacements = {
            str((cfg["legacy_dir"] / "reply_batch_full_first20.csv").resolve()): str(full_messages.resolve()),
            str((cfg["legacy_dir"] / "reply_batch_full_first20.jsonl").resolve()): str((batch_dir / f"{DATE_TAG}_{batch_name}_full_messages.jsonl").resolve()),
            str((cfg["legacy_dir"] / "reply_batch_attachments_first20.csv").resolve()): str((batch_dir / f"{DATE_TAG}_{batch_name}_attachment_inventory.csv").resolve()),
            str((cfg["legacy_dir"] / "attachment_extraction_report.csv").resolve()): str((batch_dir / f"{DATE_TAG}_{batch_name}_attachment_extraction_report.csv").resolve()),
        }
        if full_fetch_summary.exists():
            rewrite_summary_paths(full_fetch_summary, replacements)
            summary_rewrites.append(str(full_fetch_summary))
        if attachment_summary.exists():
            rewrite_summary_paths(attachment_summary, replacements)
            summary_rewrites.append(str(attachment_summary))

        canonical_review_csv = review_dir / f"{DATE_TAG}_{batch_name}_review_table_v3.csv"
        canonical_review_summary = review_dir / f"{DATE_TAG}_{batch_name}_review_table_v3_summary.json"
        copy_file(cfg["legacy_review_csv"], canonical_review_csv, manifest_rows)
        copy_file(cfg["legacy_review_summary"], canonical_review_summary, manifest_rows)
        rewrite_summary_paths(
            canonical_review_summary,
            {str(cfg["legacy_review_csv"].resolve()): str(canonical_review_csv.resolve())},
        )
        summary_rewrites.append(str(canonical_review_summary))

    batch3_dir = validation_dir / f"{DATE_TAG}_batch-003"
    batch3_dir.mkdir(parents=True, exist_ok=True)
    batch3_files = [
        validation_dir / f"{DATE_TAG}_batch-003_full_messages.csv",
        validation_dir / f"{DATE_TAG}_batch-003_full_messages.jsonl",
        validation_dir / f"{DATE_TAG}_batch-003_full_fetch_summary.json",
        validation_dir / f"{DATE_TAG}_batch-003_attachment_inventory.csv",
        validation_dir / f"{DATE_TAG}_batch-003_thread_ids.json",
    ]
    for src in batch3_files:
        if src.exists():
            copy_file(src, batch3_dir / src.name, manifest_rows)

    batch3_bodies_src = validation_dir / "bodies"
    batch3_bodies_dst = batch3_dir / "bodies"
    if batch3_bodies_src.exists():
        copy_tree(batch3_bodies_src, batch3_bodies_dst, manifest_rows)
    else:
        batch3_bodies_dst.mkdir(parents=True, exist_ok=True)

    for subdir in [batch3_dir / "attachments", batch3_dir / "attachments" / "raw", batch3_dir / "attachments" / "text"]:
        subdir.mkdir(parents=True, exist_ok=True)

    batch3_summary = batch3_dir / f"{DATE_TAG}_batch-003_full_fetch_summary.json"
    if batch3_summary.exists():
        rewrite_batch3_summary(batch3_summary, batch3_dir)
        summary_rewrites.append(str(batch3_summary))

    manifest_payload = {
        "date": DATE_TAG,
        "batches": {
            "batch-001": {
                "status": "completed",
                "canonical_validation_dir": str((validation_dir / f"{DATE_TAG}_batch-001").resolve()),
                "canonical_review_csv": str((review_dir / f"{DATE_TAG}_batch-001_review_table_v3.csv").resolve()),
            },
            "batch-002": {
                "status": "completed",
                "canonical_validation_dir": str((validation_dir / f"{DATE_TAG}_batch-002").resolve()),
                "canonical_review_csv": str((review_dir / f"{DATE_TAG}_batch-002_review_table_v3.csv").resolve()),
            },
            "batch-003": {
                "status": "interrupted_after_full_fetch",
                "canonical_validation_dir": str(batch3_dir.resolve()),
                "resume_from": "attachment_extraction",
            },
        },
        "operations": manifest_rows,
        "summary_files_rewritten": summary_rewrites,
    }
    write_json(validation_dir / f"{DATE_TAG}_batch_manifest.json", manifest_payload)
    print(json.dumps(manifest_payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
