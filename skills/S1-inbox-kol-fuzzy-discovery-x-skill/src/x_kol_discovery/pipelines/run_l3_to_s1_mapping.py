from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from email.utils import parsedate_to_datetime

from x_kol_discovery.io_utils import read_csv, safe_text, write_csv, write_json


S1_COLUMNS = [
    "备注",
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
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Map Layer3 shortlist CSV into S1 Inbox CSV.")
    parser.add_argument("--input-csv", required=True, help="Path to x_kol_L3_shortlist_batchN_YYYY-MM-DD.csv")
    parser.add_argument("--run-date", required=True, help="Date folder under workbench/YYYY-MM-DD")
    parser.add_argument("--batch", default="batch1", help="Batch name, e.g. batch1")
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
    for piece in raw.replace("||", "|").split("|"):
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
    if " + " in raw or "来源" in raw or "结果" in raw:
        return raw
    return f"来源: {raw} | 结果: 已记录"


def _format_timestamp(value: str) -> str:
    raw = safe_text(value)
    if not raw:
        return ""
    try:
        return parsedate_to_datetime(raw).strftime("%Y-%m-%d")
    except Exception:
        if len(raw) >= 10 and raw[4] == "-" and raw[7] == "-":
            return raw[:10]
        return raw


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


def _map_row(row: dict[str, str]) -> dict[str, str]:
    username = safe_text(row.get("username"))
    account_id = f"@{username}" if username and not username.startswith("@") else username
    return {
        "备注": "",
        "账号ID": account_id,
        "频道/作者名称": safe_text(row.get("display_name")),
        "平台": "X",
        "多平台标记": "",
        "账号链接": safe_text(row.get("profile_url")),
        "语言": _normalize_language(row.get("primary_language", "")),
        "博主国家": _normalize_country(row.get("country_inferred", "")),
        "粉丝数": safe_text(row.get("followers_count")),
        "账号类目标签": "",
        "账号类目标签__平台抓取": "",
        "置顶最高播放": "",
        "近期10条均播": "",
        "近10条平均ER（按曝光）": "",
        "近10条平均ER（按粉丝）": "",
        "rate（USD$)报价": "",
        "原价": "",
        "账号简介": "",
        "账号简介__平台抓取": safe_text(row.get("bio")),
        "Sample Content": _format_sample_content(row),
        "Latest Activity Proof": "",
        "粉丝受众": "",
        "粉丝性别": "",
        "粉丝年龄": "",
        "联系方式": safe_text(row.get("contact_value")),
        "联系方式备注": _normalize_contact_note(row.get("contact_note", "")),
        "外链__平台抓取": _normalize_links(row.get("external_links", "")),
        "Recommendation": "",
    }


def main() -> int:
    args = _parse_args()
    input_csv = Path(args.input_csv).expanduser().resolve()
    out_dir = input_csv.parent
    print(f"📍 Routing to: {out_dir}")

    rows = read_csv(input_csv)
    mapped = [_map_row(row) for row in rows]

    out_csv = out_dir / f"x_kol_S1_inbox_{args.batch}_{args.run_date}.csv"
    write_csv(out_csv, mapped if mapped else [{col: "" for col in S1_COLUMNS}])
    if not mapped:
        out_csv.write_text(",".join(S1_COLUMNS) + "\n", encoding="utf-8-sig")

    write_json(
        out_dir / f"x_kol_S1_inbox_mapping_runlog_{args.batch}_{args.run_date}.json",
        {
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "source_l3_csv": str(input_csv),
            "rows_written": len(mapped),
            "columns": S1_COLUMNS,
        },
    )
    (out_dir / f"x_kol_S1_inbox_mapping_audit_{args.batch}_{args.run_date}.md").write_text(
        "\n".join(
            [
                f"# L3 to S1 Mapping Audit {args.batch} {args.run_date}",
                "",
                f"- source: `{input_csv.name}`",
                f"- rows written: `{len(mapped)}`",
                "- business-conservative mapping applied",
            ]
        ),
        encoding="utf-8",
    )
    print(out_csv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
