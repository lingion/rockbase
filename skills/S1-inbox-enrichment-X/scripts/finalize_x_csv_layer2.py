from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from load_env import default_workbench_dir


ORG_KEYWORDS = (
    "news",
    "newsletter",
    "media",
    "journal",
    "report",
    "magazine",
    "blog",
    "labs",
    "lab",
    "research",
    "institute",
    "foundation",
    "company",
    "platform",
    "framework",
    "university",
    "academy",
)

CATEGORY_KEYWORDS = (
    "journalism",
    "news",
    "newsletter",
    "media",
    "education",
    "research",
    "agency",
)


def normalize_handle(value: str) -> str:
    return str(value or "").strip().lstrip("@").lower()


def load_manifest_map(out_dir: Path) -> dict[str, dict]:
    handle_map: dict[str, dict] = {}
    for manifest_file in sorted(out_dir.glob("x_api_manifest_*.json")):
        items = json.loads(manifest_file.read_text(encoding="utf-8"))
        for item in items:
            handle = normalize_handle(item.get("handle", ""))
            if handle:
                handle_map[handle] = item
    return handle_map


def build_retry_queue(df: pd.DataFrame, manifest_map: dict[str, dict]) -> dict[str, list[dict[str, str]]]:
    queue = {
        "account_not_exist": [],
        "empty": [],
        "network_error": [],
        "bad_payload": [],
        "unresolved_other": [],
    }
    for _, row in df.iterrows():
        handle = normalize_handle(row.get("账号ID", ""))
        note = str("" if pd.isna(row.get("备注", "")) else row.get("备注", ""))
        item = manifest_map.get(handle, {})
        result_type = str(item.get("result_type") or "").strip()
        message = str(item.get("message") or "").strip()
        payload = {
            "handle": handle,
            "name": str("" if pd.isna(row.get("频道/作者名称", "")) else row.get("频道/作者名称", "")),
            "note": note,
            "result_type": result_type,
            "message": message,
        }
        if result_type == "account_not_exist":
            queue["account_not_exist"].append(payload)
        elif result_type == "empty":
            queue["empty"].append(payload)
        elif result_type == "network_error":
            queue["network_error"].append(payload)
        elif result_type == "bad_payload":
            queue["bad_payload"].append(payload)
        elif "unresolved" in note:
            queue["unresolved_other"].append(payload)
    return queue


def load_response_message(json_path: Path) -> str:
    try:
        payload = json.loads(json_path.read_text(encoding="utf-8"))
    except Exception:
        return ""
    response_json = payload.get("response_json") or {}
    return str(response_json.get("message") or "").strip()


def note_tokens(value: str) -> list[str]:
    tokens = []
    text = "" if pd.isna(value) else str(value or "")
    for part in text.split("|"):
        token = part.strip()
        if token and token.lower() != "nan" and token != "CREAO raw import":
            tokens.append(token)
    return tokens


def merge_notes(existing: str, flags: list[str]) -> str:
    merged = []
    for token in note_tokens(existing):
        if token not in merged:
            merged.append(token)
    for flag in flags:
        if flag not in merged:
            merged.append(flag)
    return " | ".join(merged)


def is_media_institution(row: pd.Series) -> bool:
    category = str(row.get("账号类目标签__平台抓取", "") or "").strip().lower()
    name = str(row.get("频道/作者名称", "") or "").strip().lower()
    handle = normalize_handle(row.get("账号ID", ""))

    if any(keyword in category for keyword in CATEGORY_KEYWORDS):
        return True

    text = " ".join([name, handle])
    if any(keyword in text for keyword in ORG_KEYWORDS):
        return True

    return False


def is_404(manifest_item: dict | None) -> bool:
    if not manifest_item:
        return False
    if int(manifest_item.get("status_code", 0) or 0) == 404:
        return True
    json_path = Path(str(manifest_item.get("file", "")))
    message = load_response_message(json_path).lower()
    return "account doesn't exist" in message or "account doesnt exist" in message


def is_unresolved(row: pd.Series, manifest_item: dict | None) -> bool:
    latest_raw = row.get("Latest Activity Proof", "")
    latest = "" if pd.isna(latest_raw) else str(latest_raw or "").strip()
    contact_raw = row.get("联系方式备注", "")
    contact_note = "" if pd.isna(contact_raw) else str(contact_raw or "").strip()
    if latest:
        return False
    if "API 无 tweets" in contact_note:
        return True
    if manifest_item and int(manifest_item.get("tweet_count", 0) or 0) == 0:
        return True
    if manifest_item is None:
        return True
    return False


def sort_rank(note: str) -> int:
    tokens = set(note_tokens(note))
    unresolved = "unresolved" in tokens
    media = "media/institution" in tokens
    code404 = "404" in tokens
    if unresolved and media:
        return 4
    if unresolved:
        return 3
    if code404:
        return 2
    if media:
        return 1
    return 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--mode", choices=["preview", "apply"], default="preview")
    parser.add_argument("--workbench-date", default="")
    args = parser.parse_args()

    csv_path = args.csv.resolve()
    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    out_dir = default_workbench_dir(args.workbench_date or None)
    manifest_map = load_manifest_map(out_dir)

    notes = []
    cleaned_contact_notes = []
    for _, row in df.iterrows():
        handle = normalize_handle(row.get("账号ID", ""))
        item = manifest_map.get(handle)
        flags = []
        if is_media_institution(row):
            flags.append("media/institution")
        if is_404(item):
            flags.append("404")
        if is_unresolved(row, item):
            flags.append("unresolved")
        notes.append(merge_notes(row.get("备注", ""), flags))
        cleaned_contact_notes.append(" | ".join(note_tokens(row.get("联系方式备注", ""))))

    df["备注"] = notes
    if "联系方式备注" in df.columns:
        df["联系方式备注"] = cleaned_contact_notes
    df["_sort_rank"] = df["备注"].map(sort_rank)
    df["_sort_handle"] = df["账号ID"].fillna("").astype(str).str.lower()
    df = df.sort_values(by=["_sort_rank", "_sort_handle"], kind="stable").drop(columns=["_sort_rank", "_sort_handle"])

    retry_queue = build_retry_queue(df, manifest_map)
    retry_queue_path = out_dir / f"x_retry_queue_{csv_path.stem}.json"
    retry_queue_path.write_text(json.dumps(retry_queue, ensure_ascii=False, indent=2), encoding="utf-8")

    target = csv_path if args.mode == "apply" else csv_path.with_name(csv_path.stem + ".final.preview.csv")
    df.to_csv(target, index=False, encoding="utf-8-sig")
    print(
        json.dumps(
            {"mode": args.mode, "output": str(target), "retry_queue": str(retry_queue_path)},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
