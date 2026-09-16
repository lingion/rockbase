from __future__ import annotations

import argparse
import re
from pathlib import Path

from youtube_kol_discovery.io_utils import read_csv, safe_text, workbench_dir, write_csv, write_json
from youtube_kol_discovery.pipelines.deliverable_gate import deliverable_gate_decision


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


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Map YouTube Layer3/L2 shortlist CSV into S2 Cold Outreach CSV.")
    parser.add_argument("--input-csv", required=True, help="Path to youtube_kol_L3_shortlist_*.csv or youtube_kol_L2_shortlist_*.csv")
    parser.add_argument("--run-date", required=True, help="Output date folder under workbench/YYYY-MM-DD")
    parser.add_argument("--batch", default="batch1", help="Batch name, e.g. batch1")
    return parser.parse_args(argv)


def _normalize_language(value: str) -> str:
    text = safe_text(value).lower()
    if not text:
        return ""
    return LANGUAGE_MAP.get(text, safe_text(value))


def _normalize_country(value: str) -> str:
    text = safe_text(value).upper()
    if not text:
        return ""
    return COUNTRY_MAP.get(text, safe_text(value))


def _normalize_contact_note(value: str) -> str:
    return safe_text(value)


def _normalize_links(value: str) -> str:
    return safe_text(value)


def _format_sample_content(row: dict[str, str]) -> str:
    top_url = safe_text(row.get("top_content_url"))
    top_title = safe_text(row.get("top_content_title")) or safe_text(row.get("content_title"))
    sample_contents = safe_text(row.get("sample_contents"))
    if top_url and top_title:
        return f"{top_url} - {top_title}"
    if top_url and sample_contents:
        return f"{top_url} - {sample_contents}"
    return top_url or top_title or sample_contents


def _to_int(value: str) -> int:
    try:
        return int(str(value or "0").replace(",", "").strip())
    except ValueError:
        return 0


def _youtube_handle(row: dict[str, str]) -> str:
    direct_handle = safe_text(row.get("scrapecreators_handle"))
    if direct_handle.startswith("@"):
        return direct_handle

    profile_url = safe_text(row.get("profile_url"))
    match = re.search(r"youtube\.com/(@[^/?#]+)", profile_url, re.I)
    if match:
        return match.group(1)

    return ""


def _youtube_profile_url(row: dict[str, str]) -> str:
    handle = _youtube_handle(row)
    if handle:
        return f"https://www.youtube.com/{handle}"
    return safe_text(row.get("profile_url"))


def _clean_display_name(row: dict[str, str]) -> str:
    display_name = safe_text(row.get("display_name"))
    if not display_name:
        return ""

    cleaned = re.sub(r"\s+", " ", display_name).strip()
    public_handle = _youtube_handle(row).lstrip("@").strip()
    if not public_handle:
        return cleaned

    parts = [part.strip() for part in re.split(r"\s*[|｜]\s*", cleaned) if part.strip()]
    if len(parts) < 2:
        return cleaned

    normalized_handle = public_handle.lower().replace(" ", "")
    handle_like_parts = [
        part for part in parts if part.lower().replace(" ", "") == normalized_handle
    ]
    if not handle_like_parts:
        return cleaned

    non_handle_parts = [
        part for part in parts if part.lower().replace(" ", "") != normalized_handle
    ]
    return non_handle_parts[0] if non_handle_parts else cleaned


def _map_row(row: dict[str, str]) -> dict[str, str]:
    creator_handle = safe_text(row.get("creator_handle"))
    display_name = _clean_display_name(row)
    public_handle = _youtube_handle(row)
    profile_url = _youtube_profile_url(row)
    followers_count = safe_text(row.get("followers_count"))
    bio = safe_text(row.get("bio"))
    contact_value = safe_text(row.get("contact_value"))
    contact_note = safe_text(row.get("contact_note"))
    external_links = safe_text(row.get("external_links"))
    return {
        "分区": "",
        "备注": "",
        "提报人": "",
        "账号ID": public_handle or creator_handle,
        "频道/作者名称": display_name,
        "平台": "YouTube",
        "多平台标记": "",
        "账号链接": profile_url,
        "语言": _normalize_language(row.get("primary_language", "")),
        "博主国家": _normalize_country(row.get("country_inferred", "")),
        "粉丝数": followers_count,
        "账号类目标签": "",
        "账号类目标签__平台抓取": safe_text(row.get("content_tags_or_hashtags")),
        "置顶最高播放": safe_text(row.get("max_views")),
        "近期10条均播": "",
        "近10条平均ER（按曝光）": "",
        "近10条平均ER（按粉丝）": "",
        "rate（USD$)报价": "",
        "原价": "",
        "账号简介": "",
        "账号简介__平台抓取": bio,
        "Sample Content": _format_sample_content(row),
        "Latest Activity Proof": safe_text(row.get("top_content_url")),
        "粉丝受众": "",
        "粉丝性别": "",
        "粉丝年龄": "",
        "联系方式": contact_value,
        "联系方式备注": _normalize_contact_note(contact_note),
        "外链__平台抓取": _normalize_links(external_links),
        "Recommendation": safe_text(row.get("decision_reason")) or safe_text(row.get("recommended_action")),
        "Mail1发出状态": "",
        "Mail1_Hook": "",
        "Mail1_Greeting_Name": "",
        "Mail1_Subject": "",
        "Mail1_Content V1": "",
        "Mail1_Content V2": "",
        "llm_entity_type": safe_text(row.get("llm_entity_type")),
        "llm_decision": safe_text(row.get("llm_decision")),
        "llm_confidence": safe_text(row.get("llm_confidence")),
        "llm_rationale": safe_text(row.get("llm_rationale")),
        "llm_review_status": safe_text(row.get("llm_review_status")),
        "needs_llm_review": safe_text(row.get("needs_llm_review")),
        "final_decision": safe_text(row.get("final_decision")),
    }


def _followers_sort_key(row: dict[str, str]) -> tuple[int, str]:
    has_email = 1 if safe_text(row.get("联系方式")) else 0
    return (-has_email, -_to_int(row.get("粉丝数")), safe_text(row.get("账号ID")))


def main() -> int:
    args = _parse_args()
    input_csv = Path(args.input_csv).expanduser().resolve()
    shortlist_rows = read_csv(input_csv)
    shortlisted: list[dict[str, str]] = []
    blocked_rows: list[dict[str, str]] = []
    for row in shortlist_rows:
        if "recommended_action" not in row and "final_decision" not in row and "script_decision" not in row:
            shortlisted.append(row)
            continue
        decision = deliverable_gate_decision(row)
        if decision.allowed:
            shortlisted.append(row)
        else:
            blocked_rows.append(
                {
                    "creator_handle": safe_text(row.get("creator_handle")),
                    "display_name": safe_text(row.get("display_name")),
                    "blocked_reason": decision.reason,
                }
            )
    mapped_rows = [_map_row(row) for row in shortlisted]
    mapped_rows.sort(key=_followers_sort_key)

    wb_dir = workbench_dir(args.run_date)
    wb_csv = wb_dir / f"youtube_kol_S2_cold_{args.batch}_{args.run_date}.csv"
    runlog_json = wb_dir / f"youtube_kol_S2_mapping_runlog_{args.batch}_{args.run_date}.json"

    write_csv(wb_csv, mapped_rows, preferred_fields=S2_COLUMNS)

    write_json(
        runlog_json,
        {
            "source_shortlist_csv": str(input_csv),
            "workbench_csv": str(wb_csv),
            "counts": {
                "input_rows": len(shortlist_rows),
                "mapped_rows": len(mapped_rows),
                "blocked_rows": len(blocked_rows),
            },
            "blocked_rows": blocked_rows,
            "notes": [
                "Mail1 fields are intentionally created at S2 base mapping and left blank.",
                "Mail1 content fill should happen after S2 merge / DM fill workflow.",
                "Batch-level S2 outputs stay in workbench only; deliverables keeps merged final only.",
                "Deliverable gate blocks review/org/media risk rows from entering S2 by default.",
            ],
        },
    )
    print(wb_csv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
