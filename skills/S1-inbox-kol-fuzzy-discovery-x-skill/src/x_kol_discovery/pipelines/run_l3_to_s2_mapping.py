from __future__ import annotations

import argparse
import shutil
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

from x_kol_discovery.io_utils import read_csv, safe_text, workbench_dir, write_csv, write_json
from x_kol_discovery.task_spec import load_task_spec, task_spec_to_config


S2_COLUMNS = [
    "分区",
    "备注",
    "提报人",
    "账号ID",
    "频道/作者名称",
    "平台",
    "多平台标记",
    "账号链接",
    "语言",
    "博主国家",
    "粉丝数",
    "账号类目标签",
    "账号类目标签__平台抓取",
    "置顶最高播放",
    "近期10条均播",
    "近10条平均ER（按曝光）",
    "近10条平均ER（按粉丝）",
    "rate（USD$)报价",
    "原价",
    "账号简介",
    "账号简介__平台抓取",
    "Sample Content",
    "Latest Activity Proof",
    "粉丝受众",
    "粉丝性别",
    "粉丝年龄",
    "联系方式",
    "联系方式备注",
    "外链__平台抓取",
    "Recommendation",
    "Mail1发出状态",
    "Mail1_Hook",
    "Mail1_Greeting_Name",
    "Mail1_Subject",
    "Mail1_Content V1",
    "Mail1_Content V2",
]


LANGUAGE_MAP = {
    "en": "英语",
    "english": "英语",
    "zh": "中文",
    "zh-cn": "中文",
    "zh-tw": "中文",
    "chinese": "中文",
    "ja": "日语",
    "japanese": "日语",
    "ko": "韩语",
    "korean": "韩语",
    "fr": "法语",
    "french": "法语",
    "de": "德语",
    "german": "德语",
    "es": "西班牙语",
    "spanish": "西班牙语",
    "pt": "葡萄牙语",
    "portuguese": "葡萄牙语",
}


COUNTRY_MAP = {
    "US": "美国",
    "USA": "美国",
    "UNITED STATES": "美国",
    "GB": "英国",
    "UK": "英国",
    "UNITED KINGDOM": "英国",
    "CA": "加拿大",
    "CANADA": "加拿大",
    "AU": "澳大利亚",
    "AUSTRALIA": "澳大利亚",
    "IN": "印度",
    "INDIA": "印度",
    "SG": "新加坡",
    "SINGAPORE": "新加坡",
    "MX": "墨西哥",
    "MEXICO": "墨西哥",
    "EG": "埃及",
    "EGYPT": "埃及",
    "PK": "巴基斯坦",
    "PAKISTAN": "巴基斯坦",
    "CN": "中国",
    "CHINA": "中国",
    "BR": "巴西",
    "BRAZIL": "巴西",
    "IT": "意大利",
    "ITALY": "意大利",
    "VN": "越南",
    "VIETNAM": "越南",
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Map Layer3 shortlist CSV into S2 Cold Outreach CSV.")
    parser.add_argument("--input-csv", required=True, help="Path to x_kol_L3_shortlist_batchN_YYYY-MM-DD.csv")
    parser.add_argument("--run-date", required=True, help="Output date folder under workbench/YYYY-MM-DD")
    parser.add_argument("--batch", default="batch1", help="Batch name, e.g. batch1")
    parser.add_argument("--layer2-csv", default="", help="Optional x_kol_L2_enriched_batchN_YYYY-MM-DD.csv path for backfilling contact/links")
    parser.add_argument("--layer1-csv", default="", help="Optional x_kol_L1_candidates_batchN_YYYY-MM-DD.csv path for enforcing max_views gate")
    parser.add_argument("--spec", default="", help="Optional task spec (.json/.yaml). When provided, inherited Layer2 views gate comes from spec.")
    parser.add_argument(
        "--mirror-to-skill",
        dest="mirror_to_skill",
        action="store_true",
        default=False,
        help="Mirror the S2 CSV into the skill deliverables folder. Default: disabled.",
    )
    parser.add_argument(
        "--no-mirror-to-skill",
        dest="mirror_to_skill",
        action="store_false",
        help="Disable mirroring the S2 CSV into the skill deliverables folder.",
    )
    parser.add_argument("--deliver-full-copy", action="store_true", help="When mirroring to skill, keep the full S2 instead of the default netnew-only deliverable.")
    return parser.parse_args()


def _normalize_language(value: str) -> str:
    raw = safe_text(value)
    if not raw:
        return ""
    return LANGUAGE_MAP.get(raw.lower(), raw)


def _normalize_country(value: str) -> str:
    raw = safe_text(value)
    if not raw:
        return ""
    return COUNTRY_MAP.get(raw.upper(), raw)


def _normalize_links(value: str) -> str:
    raw = safe_text(value)
    if not raw:
        return ""
    items: list[str] = []
    seen: set[str] = set()
    for piece in raw.replace("\n", "|").replace("||", "|").split("|"):
        candidate = safe_text(piece)
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        items.append(candidate)
    return " | ".join(items)


def _normalize_contact_note(value: str) -> str:
    raw = safe_text(value)
    if not raw:
        return ""
    if "来源" in raw and "结果" in raw:
        return raw
    return f"来源: {raw} | 结果: 已记录"


def _compact_post_text(value: str, limit: int = 180) -> str:
    text = safe_text(value)
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _format_sample_content(row: dict[str, str]) -> str:
    url_part = safe_text(row.get("top_tweet_url"))
    text_part = _compact_post_text(row.get("top_tweet_text") or row.get("sample_posts"))
    parts = [part for part in [url_part, text_part] if part]
    return " - ".join(parts)


def _resolve_layer2_csv(input_csv: Path, explicit: str) -> Path | None:
    if explicit:
        candidate = Path(explicit).expanduser().resolve()
        return candidate if candidate.exists() else None
    name = input_csv.name.replace("x_kol_L3_shortlist_", "x_kol_L2_enriched_")
    candidate = input_csv.parent / name
    return candidate if candidate.exists() else None


def _resolve_layer1_csv(input_csv: Path, explicit: str) -> Path | None:
    if explicit:
        candidate = Path(explicit).expanduser().resolve()
        return candidate if candidate.exists() else None
    name = input_csv.name.replace("x_kol_L3_shortlist_", "x_kol_L1_candidates_")
    candidate = input_csv.parent / name
    return candidate if candidate.exists() else None


def _layer2_map(layer2_csv: Path | None) -> tuple[dict[str, dict[str, str]], str]:
    if not layer2_csv:
        return {}, ""
    rows = read_csv(layer2_csv)
    mapping = {safe_text(row.get("username")).lower(): row for row in rows if safe_text(row.get("username"))}
    return mapping, str(layer2_csv)


def _layer1_map(layer1_csv: Path | None) -> tuple[dict[str, dict[str, str]], str]:
    if not layer1_csv:
        return {}, ""
    rows = read_csv(layer1_csv)
    mapping = {safe_text(row.get("username")).lower(): row for row in rows if safe_text(row.get("username"))}
    return mapping, str(layer1_csv)


def _to_int(value: str) -> int:
    try:
        return int(str(value or "0").replace(",", "").strip())
    except ValueError:
        return 0


def _map_row(row: dict[str, str], layer2_row: dict[str, str] | None = None) -> dict[str, str]:
    layer2_row = layer2_row or {}
    username = safe_text(row.get("username"))
    account_id = f"@{username}" if username and not username.startswith("@") else username
    display_name = safe_text(layer2_row.get("display_name")) or safe_text(row.get("display_name"))
    profile_url = safe_text(layer2_row.get("profile_url")) or safe_text(row.get("profile_url"))
    followers_count = safe_text(layer2_row.get("followers_count")) or safe_text(row.get("followers_count"))
    bio = safe_text(layer2_row.get("bio")) or safe_text(row.get("bio"))
    contact_value = safe_text(layer2_row.get("contact_value")) or safe_text(row.get("contact_value"))
    contact_note = safe_text(layer2_row.get("contact_note")) or safe_text(row.get("contact_note"))
    external_links = safe_text(layer2_row.get("external_links")) or safe_text(row.get("external_links"))
    return {
        "分区": "",
        "备注": "",
        "提报人": "",
        "账号ID": account_id,
        "频道/作者名称": display_name,
        "平台": "X",
        "多平台标记": "",
        "账号链接": profile_url,
        "语言": _normalize_language(row.get("primary_language", "")),
        "博主国家": _normalize_country(row.get("country_inferred", "")),
        "粉丝数": followers_count,
        "账号类目标签": "",
        "账号类目标签__平台抓取": "",
        "置顶最高播放": "",
        "近期10条均播": "",
        "近10条平均ER（按曝光）": "",
        "近10条平均ER（按粉丝）": "",
        "rate（USD$)报价": "",
        "原价": "",
        "账号简介": "",
        "账号简介__平台抓取": bio,
        "Sample Content": _format_sample_content(row),
        "Latest Activity Proof": "",
        "粉丝受众": "",
        "粉丝性别": "",
        "粉丝年龄": "",
        "联系方式": contact_value,
        "联系方式备注": _normalize_contact_note(contact_note),
        "外链__平台抓取": _normalize_links(external_links),
        "Recommendation": "",
        "Mail1发出状态": "",
        "Mail1_Hook": "",
        "Mail1_Greeting_Name": "",
        "Mail1_Subject": "",
        "Mail1_Content V1": "",
        "Mail1_Content V2": "",
    }


def _deliverables_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "deliverables"


def _followers_sort_key(row: dict[str, str]) -> tuple[int, str]:
    return (-_to_int(row.get("粉丝数")), safe_text(row.get("账号ID")))


def _deliverable_filename(run_date: str, batch: str) -> str:
    return f"【S2_cold】{run_date}_x_kol_S2_{batch}.csv"


def _deliverable_netnew_filename(run_date: str, batch: str) -> str:
    return f"【S2_cold】{run_date}_x_kol_S2_{batch}_netnew.csv"


def _normalize_account_id(value: str) -> str:
    return safe_text(value).lower().lstrip("@")


def _existing_deliverable_account_ids(deliverables_root: Path, *, exclude_path: Path | None = None) -> set[str]:
    account_ids: set[str] = set()
    for path in sorted(deliverables_root.rglob("【S2_cold】*.csv")):
        if exclude_path and path.resolve() == exclude_path.resolve():
            continue
        for row in read_csv(path):
            account_id = _normalize_account_id(row.get("账号ID", ""))
            if account_id:
                account_ids.add(account_id)
    return account_ids


def main() -> int:
    args = _parse_args()
    input_csv = Path(args.input_csv).expanduser().resolve()
    out_dir = workbench_dir(args.run_date)
    print(f"📍 Routing to: {out_dir}")
    spec_path = ""
    layer2_min_max_views = 5000
    if args.spec:
        spec_payload, resolved_spec_path = load_task_spec(args.spec)
        spec_path = str(resolved_spec_path)
        layer2_min_max_views = task_spec_to_config(spec_payload, run_date=args.run_date).layer2_min_max_views

    layer2_csv = _resolve_layer2_csv(input_csv, args.layer2_csv)
    layer2_by_username, layer2_source = _layer2_map(layer2_csv)
    layer1_csv = _resolve_layer1_csv(input_csv, args.layer1_csv)
    layer1_by_username, layer1_source = _layer1_map(layer1_csv)
    rows = read_csv(input_csv)
    mapped = []
    gated_out_by_views = 0
    for row in rows:
        username = safe_text(row.get("username")).lower()
        layer1_row = layer1_by_username.get(username)
        if layer1_row and _to_int(layer1_row.get("max_views")) < layer2_min_max_views:
            gated_out_by_views += 1
            continue
        mapped.append(_map_row(row, layer2_by_username.get(username)))
    mapped.sort(key=_followers_sort_key)

    out_csv = out_dir / f"x_kol_S2_cold_{args.batch}_{args.run_date}.csv"
    write_csv(out_csv, mapped if mapped else [{col: "" for col in S2_COLUMNS}])
    if not mapped:
        out_csv.write_text(",".join(S2_COLUMNS) + "\n", encoding="utf-8-sig")

    runlog = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source_l3_csv": str(input_csv),
        "source_l2_csv": layer2_source,
        "source_l1_csv": layer1_source,
        "spec_path": spec_path,
        "layer2_min_max_views_threshold": layer2_min_max_views,
        "rows_gated_out_by_views": gated_out_by_views,
        "rows_written": len(mapped),
        "columns": S2_COLUMNS,
    }
    (out_dir / f"x_kol_S2_mapping_audit_{args.batch}_{args.run_date}.md").write_text(
        "\n".join(
            [
                f"# L3 to S2 Mapping Audit {args.batch} {args.run_date}",
                "",
                f"- source_l3: `{input_csv.name}`",
                f"- source_l2: `{Path(layer2_source).name if layer2_source else ''}`",
                f"- source_l1: `{Path(layer1_source).name if layer1_source else ''}`",
                f"- inherited views gate: `max_views >= {layer2_min_max_views}`",
                f"- gated out by views: `{gated_out_by_views}`",
                f"- rows written: `{len(mapped)}`",
                "- business-conservative mapping applied",
                "- Mail1 fields intentionally left blank for later LLM fill",
            ]
        ),
        encoding="utf-8",
    )

    if args.mirror_to_skill:
        deliverable_dir = _deliverables_dir() / args.run_date
        deliverable_dir.mkdir(parents=True, exist_ok=True)
        if not args.deliver_full_copy:
            deliverable_path = deliverable_dir / _deliverable_netnew_filename(args.run_date, args.batch)
            prior_account_ids = _existing_deliverable_account_ids(_deliverables_dir(), exclude_path=deliverable_path)
            deliverable_rows = [row for row in mapped if _normalize_account_id(row.get("账号ID", "")) not in prior_account_ids]
            write_csv(deliverable_path, deliverable_rows if deliverable_rows else [{col: "" for col in S2_COLUMNS}])
            if not deliverable_rows:
                deliverable_path.write_text(",".join(S2_COLUMNS) + "\n", encoding="utf-8-sig")
            runlog["deliverable_mode"] = "netnew_only"
            runlog["deliverable_rows_written"] = len(deliverable_rows)
            runlog["deliverable_path"] = str(deliverable_path)
        else:
            deliverable_path = deliverable_dir / _deliverable_filename(args.run_date, args.batch)
            shutil.copy2(out_csv, deliverable_path)
            runlog["deliverable_mode"] = "full_copy"
            runlog["deliverable_rows_written"] = len(mapped)
            runlog["deliverable_path"] = str(deliverable_path)

    write_json(out_dir / f"x_kol_S2_mapping_runlog_{args.batch}_{args.run_date}.json", runlog)
    print(out_csv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
