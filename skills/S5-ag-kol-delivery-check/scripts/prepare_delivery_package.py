from __future__ import annotations

import argparse
import csv
import glob
import json
import re
import shutil
from datetime import datetime
from pathlib import Path


PLATFORM_ORDER = {"YouTube": 1, "TikTok": 2, "Instagram": 3, "X": 4}
PARTITION_ORDER = {"": 1, "Part1": 1, "掉出": 2, "Part2": 3}
LANGUAGE_MAP = {
    "english": "英语",
    "eng": "英语",
    "spanish": "西班牙语",
    "portuguese": "葡萄牙语",
    "japanese": "日语",
    "korean": "韩语",
    "arabic": "阿拉伯语",
    "italian": "意大利语",
    "german": "德语",
    "chinese": "中文",
}
COUNTRY_MAP = {
    "united states": "美国",
    "usa": "美国",
    "us": "美国",
    "united kingdom": "英国",
    "uk": "英国",
    "england": "英国",
    "canada": "加拿大",
    "australia": "澳大利亚",
    "sweden": "瑞典",
    "france": "法国",
    "india": "印度",
    "indonesia": "印尼",
    "peru": "秘鲁",
    "malaysia": "马来西亚",
    "philippines": "菲律宾",
    "morocco": "摩洛哥",
    "bangladesh": "孟加拉国",
    "egypt": "埃及",
    "south africa": "南非",
    "kenya": "肯尼亚",
    "nigeria": "尼日利亚",
    "pakistan": "巴基斯坦",
    "brazil": "巴西",
    "germany": "德国",
    "italy": "意大利",
    "japan": "日本",
    "portugal": "葡萄牙",
    "south korea": "韩国",
}
DEFAULT_UPLOAD_KEEP_COLUMNS = [
    "分区",
    "提报备注",
    "提报时间",
    "提报人",
    "账号ID",
    "频道/作者名称",
    "平台",
    "账号链接",
    "语言",
    "博主国家",
    "粉丝数",
    "账号类目标签",
    "置顶最高播放",
    "近期10条均播",
    "rate（USD$)报价",
    "原价",
    "报价标准化",
    "报价原文",
    "账号简介",
    "粉丝受众",
    "粉丝性别",
    "粉丝年龄",
]


def normalize_text_key(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip()).lower()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare a KOL delivery package from a working CSV.")
    parser.add_argument("--mode", choices=["phase2", "phase3", "full"], default="phase2")
    parser.add_argument("--source-csv", required=True)
    parser.add_argument("--schema-baseline-csv")
    parser.add_argument("--project-name", required=True)
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--reporter", default="跃")
    parser.add_argument("--confirm-phase3", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        return list(reader.fieldnames or []), rows


def write_csv(path: Path, headers: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def ensure_headers_cover_rows(headers: list[str], rows: list[dict[str, str]]) -> list[str]:
    extended = list(headers)
    seen = set(extended)
    for row in rows:
        for key in row.keys():
            if key not in seen:
                extended.append(key)
                seen.add(key)
    return extended


def ensure_backup(source_csv: Path, date_str: str) -> Path:
    root = source_csv.parents[1] / "Agency" / "list-bak" / date_str
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%H%M%S")
    backup_path = root / f"{source_csv.name}_bak_{stamp}.csv"
    shutil.copy2(source_csv, backup_path)
    return backup_path


def list_backup_candidates(source_csv: Path, date_str: str) -> list[Path]:
    backup_dir = source_csv.parents[1] / "Agency" / "list-bak" / date_str
    same_day = sorted(backup_dir.glob(f"{source_csv.name}_bak_*.csv"))
    historical = sorted(source_csv.parents[1].glob(f"Agency/list-bak/*/{source_csv.name}_bak_*.csv"))
    seen: set[str] = set()
    ordered: list[Path] = []
    ordered_candidates = list(reversed(same_day)) + list(reversed(historical))
    for path in ordered_candidates:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        ordered.append(path)
    return ordered


def normalize_language(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    return LANGUAGE_MAP.get(text.lower(), text)


def normalize_country(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    return COUNTRY_MAP.get(text.lower(), text)


def parse_compact_number(text: str) -> float | None:
    raw = (text or "").strip().replace(",", "")
    if not raw or raw.lower() == "none":
        return None
    m = re.search(r"(\d+(?:\.\d+)?)\s*([kKmMbB]?)", raw)
    if not m:
        return None
    num = float(m.group(1))
    unit = m.group(2).lower()
    if unit == "k":
        num *= 1_000
    elif unit == "m":
        num *= 1_000_000
    elif unit == "b":
        num *= 1_000_000_000
    return num


def format_fans(text: str) -> str:
    num = parse_compact_number(text)
    if num is None:
        return text.strip() if text else ""
    if num >= 1_000_000:
        value = num / 1_000_000
        return f"{value:.1f}M".replace(".0M", "M")
    if num >= 1_000:
        value = num / 1_000
        return f"{value:.1f}K".replace(".0K", "K")
    return str(int(round(num)))


def format_thousand_or_none(text: str) -> str:
    num = parse_compact_number(text)
    if num is None:
        return "None"
    return f"{int(round(num)):,}"


def format_price(text: str) -> str:
    raw = (text or "").strip()
    if not raw:
        return ""
    if re.search(r"[A-Za-z一-龥]", raw) and not re.fullmatch(r"\$?\s*\d[\d,]*(?:\.\d+)?", raw):
        return raw
    m = re.fullmatch(r"\$?\s*(\d[\d,]*)(?:\.0+)?", raw)
    if not m:
        return raw
    amount = int(m.group(1).replace(",", ""))
    return f"${amount:,}"


def numeric_sort_value(row: dict[str, str]) -> float:
    for key in ["rate（USD$)报价", "原价"]:
        raw = row.get(key, "")
        m = re.fullmatch(r"\$?\s*(\d[\d,]*)", (raw or "").strip())
        if m:
            return float(m.group(1).replace(",", ""))
    return -1.0


def has_question_mark(headers: list[str], row: dict[str, str]) -> bool:
    for col in headers[:3]:
        value = row.get(col, "")
        if "?" in value or "？" in value:
            return True
    return False


def audit_change(audits: list[dict], audit_type: str, account_id: str, before: str, after: str, **extra: str) -> None:
    audits.append(
        {
            "type": audit_type,
            "account_id": account_id,
            "before": before,
            "after": after,
            **extra,
        }
    )


def detect_suspicious_numeric_change(account_id: str, field: str, before: str, after: str) -> list[dict]:
    findings: list[dict] = []
    before_text = (before or "").strip()
    after_text = (after or "").strip()
    before_num = parse_compact_number(before_text)
    after_num = parse_compact_number(after_text)
    if before_text and after_text == "None":
        findings.append(
            {
                "type": "unparsed-to-none",
                "account_id": account_id,
                "field": field,
                "before": before_text,
                "after": after_text,
            }
        )
        return findings
    if before_num is None or after_num is None:
        return findings
    if any(unit in before_text.lower() for unit in ["k", "m", "b"]) and after_num < 100:
        findings.append(
            {
                "type": "unit-loss-risk",
                "account_id": account_id,
                "field": field,
                "before": before_text,
                "after": after_text,
            }
        )
    ratio = max(before_num, after_num) / max(min(before_num, after_num), 1)
    if ratio >= 50 and before_num >= 1_000:
        findings.append(
            {
                "type": "large-scale-change",
                "account_id": account_id,
                "field": field,
                "before": before_text,
                "after": after_text,
            }
        )
    return findings


def build_row_lookup(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    lookup: dict[tuple[str, str], dict[str, str]] = {}
    for row in rows:
        account_id = normalize_text_key(row.get("账号ID", ""))
        channel_name = normalize_text_key(row.get("频道/作者名称", ""))
        lookup[(account_id, channel_name)] = row
    return lookup


def normalize_partition(value: str) -> str:
    text = (value or "").strip()
    lowered = text.lower()
    if lowered == "part1":
        return "Part1"
    if lowered == "part2":
        return "Part2"
    if text == "掉出":
        return "掉出"
    return text


def normalize_main_rows(headers: list[str], rows: list[dict[str, str]], date_str: str, reporter: str) -> tuple[list[dict[str, str]], list[dict]]:
    audits: list[dict] = []
    peak_col = "置顶最高播放" if "置顶最高播放" in headers else "置顶最高单条播放量" if "置顶最高单条播放量" in headers else ""

    for row in rows:
        account_id = row.get("账号ID", "")
        if "分区" in row:
            row["分区"] = normalize_partition(row.get("分区", ""))
        row["提报时间"] = date_str
        row["提报人"] = reporter
        if "语言" in row:
            before = row["语言"]
            row["语言"] = normalize_language(row["语言"])
            if before != row["语言"]:
                audit_change(audits, "normalized-language", account_id, before, row["语言"])
        if "博主国家" in row:
            before = row["博主国家"]
            row["博主国家"] = normalize_country(row["博主国家"])
            if before != row["博主国家"]:
                audit_change(audits, "normalized-country", account_id, before, row["博主国家"])
        if "粉丝数" in row:
            before = row["粉丝数"]
            row["粉丝数"] = format_fans(row["粉丝数"])
            if before != row["粉丝数"]:
                audit_change(audits, "normalized-fans", account_id, before, row["粉丝数"])
        if peak_col:
            before = row.get(peak_col, "")
            row[peak_col] = format_thousand_or_none(before)
            if before != row[peak_col]:
                audit_change(audits, "normalized-peak", account_id, before, row[peak_col], field=peak_col)
                audits.extend(detect_suspicious_numeric_change(account_id, peak_col, before, row[peak_col]))
        if "近期10条均播" in row:
            before = row["近期10条均播"]
            row["近期10条均播"] = format_thousand_or_none(before)
            if before != row["近期10条均播"]:
                audit_change(audits, "normalized-avg-views", account_id, before, row["近期10条均播"], field="近期10条均播")
                audits.extend(detect_suspicious_numeric_change(account_id, "近期10条均播", before, row["近期10条均播"]))
        for key in ["rate（USD$)报价", "原价"]:
            if key in row:
                before = row[key]
                row[key] = format_price(row[key])
                if before != row[key]:
                    audit_change(audits, f"normalized-{key}", account_id, before, row[key], field=key)
                audits.extend(detect_suspicious_numeric_change(account_id, key, before, row[key]))
    return rows, audits


def sort_main_rows(headers: list[str], rows: list[dict[str, str]]) -> list[dict[str, str]]:
    question_rows = [row for row in rows if has_question_mark(headers, row)]
    core_rows = [row for row in rows if not has_question_mark(headers, row)]
    core_rows.sort(
        key=lambda row: (
            PARTITION_ORDER.get((row.get("分区", "") or "").strip(), 9),
            PLATFORM_ORDER.get((row.get("平台", "") or "").strip(), 9),
            -numeric_sort_value(row),
            (row.get("频道/作者名称", "") or "").strip().lower(),
            (row.get("账号ID", "") or "").strip().lower(),
        )
    )
    if not question_rows:
        return core_rows
    blank_row = {header: "" for header in headers}
    return core_rows + [blank_row.copy() for _ in range(3)] + question_rows


def build_upload_headers(source_headers: list[str], baseline_headers: list[str], has_x_platform: bool) -> list[str]:
    keep = [header for header in baseline_headers if header in source_headers]
    if has_x_platform:
        for extra in ["Sample Content", "Latest Activity Proof"]:
            if extra in source_headers and extra not in keep:
                keep.append(extra)
    return keep


def build_upload_name(source_csv: Path, project_name: str, date_str: str) -> str:
    prefix_match = re.match(r"(P\d+(?:\.\d+)?)", source_csv.name)
    prefix = prefix_match.group(1) if prefix_match else "P4"
    normalized_date = date_str.replace("-", "")
    return f"{prefix}【KOL】{project_name}_Influencer_List_Rockbase_{normalized_date}.csv"


def build_upload_rows(rows: list[dict[str, str]], keep_headers: list[str]) -> list[dict[str, str]]:
    upload_rows = []
    for row in rows:
        partition = (row.get("分区", "") or "").strip()
        if partition == "Part2":
            continue
        upload_rows.append({header: row.get(header, "") for header in keep_headers})
    upload_rows.sort(
        key=lambda row: (
            PARTITION_ORDER.get((row.get("分区", "") or "").strip(), 9),
            PLATFORM_ORDER.get((row.get("平台", "") or "").strip(), 9),
            -numeric_sort_value(row),
            (row.get("频道/作者名称", "") or "").strip().lower(),
            (row.get("账号ID", "") or "").strip().lower(),
        )
    )
    return upload_rows


def compare_against_backup(original_rows: list[dict[str, str]], normalized_rows: list[dict[str, str]], headers: list[str]) -> list[dict]:
    audits: list[dict] = []
    original_lookup = build_row_lookup(original_rows)
    tracked_fields = [
        "粉丝数",
        "置顶最高播放",
        "置顶最高单条播放量",
        "近期10条均播",
        "rate（USD$)报价",
        "原价",
        "语言",
        "博主国家",
    ]
    for row in normalized_rows:
        key = (
            normalize_text_key(row.get("账号ID", "")),
            normalize_text_key(row.get("频道/作者名称", "")),
        )
        original = original_lookup.get(key)
        if not original:
            continue
        account_id = row.get("账号ID", "")
        for field in tracked_fields:
            if field not in headers:
                continue
            before = original.get(field, "")
            after = row.get(field, "")
            if before == after:
                continue
            if field in {"语言", "博主国家"}:
                if before and after and len(after) <= 1:
                    audits.append(
                        {
                            "type": "suspicious-short-normalized-text",
                            "account_id": account_id,
                            "field": field,
                            "before": before,
                            "after": after,
                        }
                    )
                continue
            audits.extend(detect_suspicious_numeric_change(account_id, field, before, after))
    return audits


def is_numeric_field(field: str) -> bool:
    return field in {"粉丝数", "置顶最高播放", "置顶最高单条播放量", "近期10条均播", "rate（USD$)报价", "原价"}


def choose_repair_value(field: str, current_value: str, candidates: list[str]) -> tuple[str | None, str]:
    cleaned = [(candidate or "").strip() for candidate in candidates if (candidate or "").strip()]
    if not cleaned:
        return None, "no-backup-candidate"
    frequency: dict[str, int] = {}
    for candidate in cleaned:
        frequency[candidate] = frequency.get(candidate, 0) + 1
    ranked = sorted(frequency.items(), key=lambda item: (-item[1], item[0]))
    top_value, top_count = ranked[0]
    current_num = parse_compact_number(current_value)
    top_num = parse_compact_number(top_value)

    if top_count >= 2:
        return top_value, "backup-majority"
    if is_numeric_field(field) and current_num is not None and top_num is not None:
        ratio = max(current_num, top_num) / max(min(current_num, top_num), 1)
        if ratio >= 50:
            return top_value, "backup-scale-correction"
        if field == "粉丝数" and current_num < 1000 <= top_num:
            return top_value, "backup-fans-unit-correction"
        if field in {"置顶最高播放", "置顶最高单条播放量", "近期10条均播"} and current_num < 1000 <= top_num:
            return top_value, "backup-views-unit-correction"
    if len(ranked) == 1:
        return top_value, "single-backup-candidate"
    return None, "conflicting-backup-candidates"


def repair_from_backup_chain(
    source_csv: Path,
    date_str: str,
    headers: list[str],
    rows: list[dict[str, str]],
    audits: list[dict],
) -> tuple[list[dict[str, str]], list[dict], list[dict]]:
    repairable_fields = [
        "粉丝数",
        "置顶最高播放",
        "置顶最高单条播放量",
        "近期10条均播",
        "rate（USD$)报价",
        "原价",
    ]
    backup_paths = list_backup_candidates(source_csv, date_str)
    backup_maps: list[dict[tuple[str, str], dict[str, str]]] = []
    for path in backup_paths:
        try:
            _, backup_rows = read_csv(path)
        except Exception:
            continue
        backup_maps.append(build_row_lookup(backup_rows))

    resolutions: list[dict] = []
    unresolved: list[dict] = []
    row_lookup = build_row_lookup(rows)
    suspicious_items = [
        audit for audit in audits if audit.get("type") in {"unit-loss-risk", "large-scale-change", "unparsed-to-none"}
    ]
    seen_pairs: set[tuple[str, str]] = set()

    for item in suspicious_items:
        account_id = item.get("account_id", "")
        field = item.get("field", "")
        if not account_id or field not in repairable_fields:
            continue
        matching_row = None
        for key, row in row_lookup.items():
            if key[0] == normalize_text_key(account_id):
                matching_row = row
                row_key = key
                break
        if matching_row is None:
            continue
        pair_key = (account_id, field)
        if pair_key in seen_pairs:
            continue
        seen_pairs.add(pair_key)

        candidates: list[str] = []
        for backup_map in backup_maps:
            backup_row = backup_map.get(row_key)
            if backup_row is not None:
                candidates.append(backup_row.get(field, ""))

        replacement, reason = choose_repair_value(field, matching_row.get(field, ""), candidates)
        if replacement is None or replacement == matching_row.get(field, ""):
            unresolved.append(
                {
                    "account_id": account_id,
                    "field": field,
                    "current": matching_row.get(field, ""),
                    "backup_candidates": [candidate for candidate in candidates if candidate],
                    "reason": reason,
                }
            )
            continue

        before = matching_row.get(field, "")
        matching_row[field] = replacement
        resolutions.append(
            {
                "account_id": account_id,
                "field": field,
                "before": before,
                "after": replacement,
                "reason": reason,
                "backup_candidates": [candidate for candidate in candidates if candidate],
            }
        )

    return rows, resolutions, unresolved


def main() -> None:
    args = parse_args()
    source_csv = Path(args.source_csv)
    source_headers, source_rows = read_csv(source_csv)

    if args.mode in {"phase3", "full"} and not args.confirm_phase3 and not args.dry_run:
        raise SystemExit("Phase 3 requires explicit confirmation: rerun with --confirm-phase3")

    baseline_headers = DEFAULT_UPLOAD_KEEP_COLUMNS
    if args.schema_baseline_csv:
        baseline_headers, _ = read_csv(Path(args.schema_baseline_csv))

    backup_path = ensure_backup(source_csv, args.date) if not args.dry_run else None
    original_rows = [row.copy() for row in source_rows]
    audits: list[dict] = []

    if args.mode in {"phase2", "full"}:
        normalized_rows, audits = normalize_main_rows(source_headers, source_rows, args.date, args.reporter)
        normalized_rows = sort_main_rows(source_headers, normalized_rows)
        audits.extend(compare_against_backup(original_rows, normalized_rows, source_headers))
        normalized_rows, repaired_items, unresolved_items = repair_from_backup_chain(source_csv, args.date, source_headers, normalized_rows, audits)
    else:
        normalized_rows = source_rows
        repaired_items = []
        unresolved_items = []

    duplicate_account_ids = len([1 for idx, row in enumerate(normalized_rows) if (row.get("账号ID", "") or "").strip() and (row.get("账号ID", "") or "").strip() in {(r.get("账号ID", "") or "").strip() for r in normalized_rows[:idx]}])
    duplicate_names = len([1 for idx, row in enumerate(normalized_rows) if (row.get("频道/作者名称", "") or "").strip() and (row.get("频道/作者名称", "") or "").strip() in {(r.get("频道/作者名称", "") or "").strip() for r in normalized_rows[:idx]}])
    has_x_platform = any((row.get("平台", "") or "").strip() == "X" for row in normalized_rows)
    keep_headers = build_upload_headers(source_headers, baseline_headers, has_x_platform)
    dropped_headers = [header for header in source_headers if header not in keep_headers]
    upload_rows: list[dict[str, str]] = []
    upload_path = None
    if args.mode in {"phase3", "full"}:
        upload_rows = build_upload_rows(normalized_rows, keep_headers)
        upload_name = build_upload_name(source_csv, args.project_name, args.date)
        upload_path = source_csv.parent / upload_name

    stamp = datetime.now().strftime("%H%M%S")
    preview_json = source_csv.parent / f"delivery_preview_{stamp}.json"
    preview_md = source_csv.parent / f"delivery_preview_{stamp}.md"
    dirty_json = source_csv.parent / f"dirty_value_audit_{stamp}.json"
    resolution_json = source_csv.parent / f"dirty_value_resolution_{stamp}.json"

    summary = {
        "source_csv": str(source_csv),
        "backup_path": str(backup_path) if backup_path else "",
        "mode": args.mode,
        "upload_path": str(upload_path) if upload_path else "",
        "rows_in_source": len(original_rows),
        "rows_in_upload": len(upload_rows),
        "kept_headers": keep_headers,
        "dropped_headers": dropped_headers,
        "has_x_platform": has_x_platform,
        "duplicate_account_ids": duplicate_account_ids,
        "duplicate_names": duplicate_names,
        "dirty_value_count": len(audits),
        "repaired_count": len(repaired_items),
        "unresolved_count": len(unresolved_items),
    }

    preview_md.write_text(
        "\n".join(
            [
                "# Delivery Preview",
                "",
                f"- Mode: `{args.mode}`",
                f"- Source: `{source_csv}`",
                f"- Upload copy: `{upload_path}`" if upload_path else "- Upload copy: not generated in this mode",
                f"- Rows in source: {len(original_rows)}",
                f"- Rows in upload: {len(upload_rows)}",
                f"- Has X platform: {has_x_platform}",
                f"- Duplicate account IDs: {duplicate_account_ids}",
                f"- Duplicate names: {duplicate_names}",
                f"- Dirty value audit count: {len(audits)}",
                f"- Repaired suspicious values: {len(repaired_items)}",
                f"- Remaining unresolved values: {len(unresolved_items)}",
                "",
                "## Kept Headers",
                *[f"- `{header}`" for header in keep_headers],
                "",
                "## Dropped Headers",
                *([f"- `{header}`" for header in dropped_headers] if dropped_headers else ["- None"]),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    preview_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    dirty_json.write_text(json.dumps({"source_csv": str(source_csv), "audits": audits}, ensure_ascii=False, indent=2), encoding="utf-8")
    resolution_json.write_text(
        json.dumps(
            {
                "source_csv": str(source_csv),
                "repaired_items": repaired_items,
                "unresolved_items": unresolved_items,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    if not args.dry_run:
        if args.mode in {"phase2", "full"}:
            source_headers = ensure_headers_cover_rows(source_headers, normalized_rows)
            write_csv(source_csv, source_headers, normalized_rows)
        if args.mode in {"phase3", "full"} and upload_path is not None:
            write_csv(upload_path, keep_headers, upload_rows)

    print(
        json.dumps(
            {
                **summary,
                "preview_json": str(preview_json),
                "preview_md": str(preview_md),
                "dirty_value_audit": str(dirty_json),
                "dirty_value_resolution": str(resolution_json),
                "dry_run": args.dry_run,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
