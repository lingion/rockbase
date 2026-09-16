#!/usr/bin/env python3
import argparse
import csv
import json
import subprocess
from pathlib import Path
from typing import Dict, List


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run full-thread fetch + attachment extraction in chunks for threads listed in a recovery preview CSV."
    )
    parser.add_argument("--master", required=True, help="Path to the V3 replied master CSV.")
    parser.add_argument("--preview-csv", required=True, help="Path to recovery preview CSV.")
    parser.add_argument("--output-dir", required=True, help="Output directory for chunked results.")
    parser.add_argument("--chunk-size", type=int, default=25, help="Thread count per chunk.")
    parser.add_argument("--max-threads", type=int, default=0, help="Optional cap on unique thread count. 0 means all.")
    parser.add_argument("--token", default="", help="Optional Gmail OAuth token path.")
    return parser.parse_args()


def read_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def chunk_list(items: List[str], size: int) -> List[List[str]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def main() -> None:
    args = parse_args()
    preview_csv = Path(args.preview_csv)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = read_rows(preview_csv)
    thread_ids: List[str] = []
    seen = set()
    for row in rows:
        thread_id = (row.get("Reply_Thread_ID") or row.get("thread_id") or "").strip()
        if not thread_id or thread_id in seen:
            continue
        seen.add(thread_id)
        thread_ids.append(thread_id)
    if args.max_threads and args.max_threads > 0:
        thread_ids = thread_ids[: args.max_threads]

    chunk_size = max(1, args.chunk_size)
    chunks = chunk_list(thread_ids, chunk_size)

    all_summaries: List[Dict[str, object]] = []
    total_attachment_messages = 0
    total_downloaded = 0
    total_extracted = 0
    failed_chunks = 0

    runner = Path(__file__).with_name("run_attachment_pipeline_from_preview.py")

    for idx, chunk in enumerate(chunks, start=1):
        chunk_dir = output_dir / f"chunk_{idx:03d}"
        chunk_dir.mkdir(parents=True, exist_ok=True)
        chunk_ids_path = chunk_dir / "thread_ids.json"
        chunk_ids_path.write_text(json.dumps(chunk, ensure_ascii=False, indent=2), encoding="utf-8")

        chunk_preview_path = chunk_dir / "chunk_preview.csv"
        with chunk_preview_path.open("w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=["Reply_Thread_ID"])
            writer.writeheader()
            writer.writerows({"Reply_Thread_ID": t} for t in chunk)

        cmd = [
            "python3",
            str(runner),
            "--master",
            args.master,
            "--preview-csv",
            str(chunk_preview_path),
            "--output-dir",
            str(chunk_dir / "pipeline"),
            "--limit",
            str(len(chunk)),
        ]
        if args.token:
            cmd.extend(["--token", args.token])
        proc = subprocess.run(cmd, capture_output=True, text=True)

        summary_path = chunk_dir / "pipeline" / "attachment_pipeline_summary.json"
        summary: Dict[str, object] = {
            "chunk_index": idx,
            "threads_requested": len(chunk),
            "returncode": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
            "summary_path": str(summary_path.resolve()) if summary_path.exists() else "",
        }

        if summary_path.exists():
            try:
                pipeline_summary = json.loads(summary_path.read_text(encoding="utf-8"))
                summary["pipeline_summary"] = pipeline_summary
                fetch_stdout = pipeline_summary.get("fetch_stdout") or ""
                extract_stdout = pipeline_summary.get("extract_stdout") or ""
                try:
                    fetch_json = json.loads(fetch_stdout) if fetch_stdout else {}
                except Exception:
                    fetch_json = {}
                try:
                    extract_json = json.loads(extract_stdout) if extract_stdout else {}
                except Exception:
                    extract_json = {}
                total_attachment_messages += int(fetch_json.get("attachment_messages", 0) or 0)
                total_downloaded += int(extract_json.get("downloaded_count", 0) or 0)
                total_extracted += int(extract_json.get("extracted_count", 0) or 0)
            except Exception as exc:
                summary["summary_parse_error"] = str(exc)
        else:
            failed_chunks += 1

        all_summaries.append(summary)

    combined_summary = {
        "preview_csv": str(preview_csv.resolve()),
        "unique_threads_total": len(thread_ids),
        "chunk_size": chunk_size,
        "chunks_total": len(chunks),
        "failed_chunks": failed_chunks,
        "total_attachment_messages": total_attachment_messages,
        "total_downloaded": total_downloaded,
        "total_extracted": total_extracted,
        "chunks": all_summaries,
    }
    summary_path = output_dir / "chunked_attachment_pipeline_summary.json"
    summary_path.write_text(json.dumps(combined_summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(combined_summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
