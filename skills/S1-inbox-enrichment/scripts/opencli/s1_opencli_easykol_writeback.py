#!/usr/bin/env python3
import argparse
import csv
import json
from pathlib import Path

from internal.extractors.common import (
    DEFAULT_SESSION_BY_PLATFORM,
    finalize_note,
    get_extractor_js,
    normalize_platform,
    parse_rows_spec,
)
from internal.session_runtime import OpenCliEasykolRuntime


def load_rows(csv_path: Path, target_rows: set[int]) -> list[dict]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        items = []
        for i, row in enumerate(reader, start=2):
            if target_rows and i not in target_rows:
                continue
            row["__row"] = i
            items.append(row)
        return items


def auto_select_rows(csv_path: Path) -> list[int]:
    rows = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, start=2):
            contact = (row.get("联系方式") or "").strip()
            note = (row.get("联系方式备注") or "").strip()
            url = (row.get("账号链接") or "").strip()
            if url and not contact and note not in {"EasyKOL获取", "EasyKOL无法获取"}:
                rows.append(i)
    return rows


def write_review(workbench_dir: Path, slug: str, results: list[dict], max_wait: int, poll: int) -> tuple[Path, Path]:
    workbench_dir.mkdir(parents=True, exist_ok=True)
    json_path = workbench_dir / f"{slug}.json"
    md_path = workbench_dir / f"{slug}.md"
    json_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    md_lines = [
        f"processed: {len(results)}",
        f"max_wait_seconds: {max_wait}",
        f"poll_seconds: {poll}",
    ]
    for item in results:
        md_lines.append(
            f"- row {item['row']}: {item['name']} | {item['status']} | {item['email']} | {item['note']} | elapsed={item['elapsedSeconds']}s"
        )
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    return json_path, md_path


def apply_writeback(csv_path: Path, results: list[dict]) -> None:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    header = rows[0]
    contact_idx = header.index("联系方式")
    note_idx = header.index("联系方式备注")
    results_by_row = {item["row"]: item for item in results}
    for row_no, row in enumerate(rows[1:], start=2):
        item = results_by_row.get(row_no)
        if not item:
            continue
        if item["status"] == "hit":
            row[contact_idx] = item["email"]
            row[note_idx] = "EasyKOL获取"
        elif item["status"] == "no_email":
            row[contact_idx] = ""
            row[note_idx] = "EasyKOL无法获取"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        csv.writer(f).writerows(rows)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv-path", required=True)
    parser.add_argument("--platform", required=True, choices=["youtube", "tiktok", "instagram"])
    parser.add_argument("--rows", default="")
    parser.add_argument("--slug", required=True)
    parser.add_argument("--workbench-dir", required=True)
    parser.add_argument("--session", default="")
    parser.add_argument("--max-wait-seconds", type=int, default=25)
    parser.add_argument("--poll-seconds", type=int, default=3)
    parser.add_argument("--write", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    platform = normalize_platform(args.platform)
    csv_path = Path(args.csv_path).resolve()
    workbench_dir = Path(args.workbench_dir).resolve()
    session = args.session or DEFAULT_SESSION_BY_PLATFORM[platform]

    target_rows = set(parse_rows_spec(args.rows)) if args.rows else set(auto_select_rows(csv_path))
    rows = load_rows(csv_path, target_rows)
    js = get_extractor_js(platform)
    runtime = OpenCliEasykolRuntime(
        session=session,
        probe_js=js,
        max_wait_seconds=args.max_wait_seconds,
        poll_seconds=args.poll_seconds,
    )

    results = []
    for row in rows:
        final, attempts = runtime.probe_row((row["账号链接"] or "").strip())
        final["note"] = finalize_note(final["status"], final["note"])
        results.append(
            {
                "row": row["__row"],
                "name": (row["频道/作者名称"] or "").strip(),
                "url": (row["账号链接"] or "").strip(),
                "status": final["status"],
                "email": final["email"],
                "note": final["note"],
                "hostFound": final["hostFound"],
                "sectionFound": final["sectionFound"],
                "sectionText": final["sectionText"],
                "elapsedSeconds": final["elapsedSeconds"],
                "attempts": attempts,
            }
        )

    if args.write:
        apply_writeback(csv_path, results)

    json_path, md_path = write_review(workbench_dir, args.slug, results, args.max_wait_seconds, args.poll_seconds)
    print(
        json.dumps(
            {
                "csv_path": str(csv_path),
                "write": args.write,
                "json_path": str(json_path),
                "md_path": str(md_path),
                "results": [{k: v for k, v in item.items() if k != "attempts"} for item in results],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
