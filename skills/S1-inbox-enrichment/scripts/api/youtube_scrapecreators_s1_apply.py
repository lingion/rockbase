from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply YouTube ScrapeCreators export back to S1 existing columns only.")
    parser.add_argument("--csv", required=True, help="Target S1 CSV")
    parser.add_argument("--json", required=True, help="Raw JSON exported by youtube_channel_batch_export.py")
    parser.add_argument("--mode", choices=["preview", "apply"], default="preview")
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    return parser.parse_args()


def clean_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def normalize_handle(value: object) -> str:
    text = clean_text(value).strip("，,;；|/ ")
    if not text:
        return ""
    if not text.startswith("@"):
        text = "@" + text.lstrip("@")
    text = re.sub(r"[^@A-Za-z0-9._\-\u0080-\uFFFF]", "", text)
    return "" if text == "@" else text


def is_standard_handle(value: object) -> bool:
    return bool(re.fullmatch(r"@[A-Za-z0-9._\-\u0080-\uFFFF]+", clean_text(value)))


def extract_handle_from_url(platform: str, url: object) -> str:
    text = clean_text(url)
    if not text:
        return ""
    patterns = {
        "YouTube": r"youtube\.com/(@[A-Za-z0-9._\-\u0080-\uFFFF]+)",
        "TikTok": r"tiktok\.com/(@[A-Za-z0-9._\-\u0080-\uFFFF]+)",
        "Instagram": r"instagram\.com/([A-Za-z0-9._\-\u0080-\uFFFF]+)",
    }
    match = re.search(patterns[platform], text, re.I)
    if not match:
        return ""
    token = match.group(1)
    return normalize_handle(token if token.startswith("@") else f"@{token}")


def clean_author_name(value: object, handle: object = "", blocked_tokens: list[str] | None = None) -> str:
    text = clean_text(value)
    if not text:
        return ""
    lower = text.lower()
    bare_handle = clean_text(handle).lstrip("@").lower()
    blocked = {
        "follow",
        "message",
        "following",
        "followers",
        "posts",
        "likes",
        "videos",
        "subscribers",
        "see more from",
        "sign up for instagram",
        "log in",
        "also from meta",
        "something went wrong",
        "no bio yet.",
    }
    if blocked_tokens:
        blocked.update(token.lower() for token in blocked_tokens)
    if lower in blocked:
        return ""
    if text.startswith("@"):
        return ""
    if "@" in text or re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", text, re.I):
        return ""
    if any(token in lower for token in ["followers", "following", "posts", "likes", "videos", "subscribers"]):
        return ""
    if bare_handle and lower.lstrip("@") == bare_handle:
        return ""
    if re.fullmatch(r"[\d\s.,KMBkmb]+", text):
        return ""
    return text.strip(" -|:")


def pick_identity(payload: dict, platform: str, current_handle: object, current_name: object, url: object) -> tuple[str, str]:
    api_handle = normalize_handle(payload.get("handle"))
    api_name = clean_author_name(payload.get("name"), api_handle or current_handle, ["youtube"])
    url_handle = extract_handle_from_url(platform, url)
    best_handle = api_handle or url_handle or normalize_handle(current_handle)
    best_name = api_name or clean_author_name(current_name, best_handle, ["youtube"])
    return best_handle, best_name


def merge_links(existing: object, api_links: object) -> str:
    merged: list[str] = []
    for candidate in [existing, api_links]:
        if isinstance(candidate, list):
            items = candidate
        else:
            items = re.split(r"[\n|]+", clean_text(candidate))
        for item in items:
            link = clean_text(item)
            if not link:
                continue
            if link not in merged:
                merged.append(link)
    return "\n".join(merged)


def detect_cross_platforms(main_platform: str, links_text: object) -> str:
    platform_order = ["YouTube", "TikTok", "Instagram", "X"]
    patterns = {
        "YouTube": ["youtube.com", "youtu.be"],
        "TikTok": ["tiktok.com"],
        "Instagram": ["instagram.com"],
        "X": ["x.com", "twitter.com"],
    }
    text = clean_text(links_text).lower()
    if not text:
        return ""
    hits: list[str] = []
    for platform in platform_order:
        if platform == main_platform:
            continue
        if any(pattern in text for pattern in patterns[platform]):
            hits.append(platform)
    return "/".join(hits)


def normalize_followers(payload: dict) -> str:
    text = clean_text(payload.get("subscriberCountText"))
    if text:
        return re.sub(r"\s+subscribers?$", "", text, flags=re.I).strip()
    count = payload.get("subscriberCount")
    if isinstance(count, (int, float)):
        value = float(count)
        if value >= 1_000_000:
            return f"{value / 1_000_000:.2f}".rstrip("0").rstrip(".") + "M"
        if value >= 1_000:
            return f"{value / 1_000:.1f}".rstrip("0").rstrip(".") + "K"
        return str(int(value))
    return ""


def infer_language(payload: dict) -> tuple[str, str]:
    source = " ".join(
        [
            clean_text(payload.get("description")),
            clean_text(payload.get("tags")),
            " ".join(payload.get("links") or []),
        ]
    ).lower()
    if not source:
        return "", ""
    if re.search(r"[\u4e00-\u9fff]", source):
        return "中文", "bio/tags 出现中文"
    if re.search(r"[\u3040-\u30ff]", source):
        return "日语", "bio/tags 出现日文"
    if re.search(r"[\u0600-\u06ff]", source):
        return "阿拉伯语", "bio/tags 出现阿文"
    if any(token in source for token in ["bonjour", "france", "français", "francais"]):
        return "法语", "bio/tags 出现法语信号"
    if any(token in source for token in ["hola", "españ", "espan", "latino"]):
        return "西班牙语", "bio/tags 出现西语信号"
    return "英语", "bio/tags 默认英语信号"


def infer_country(payload: dict) -> tuple[str, str]:
    text = clean_text(payload.get("description"))
    low = text.lower()
    padded = f" {low} "
    rules = [
        ("英国", [" uk ", "based in the uk", "from the uk", "london", "british", "england", "🇬🇧"]),
        ("美国", [" usa ", "united states", "california", "new york", "texas", "🇺🇸"]),
        ("加拿大", ["canada", "toronto", "vancouver", "🇨🇦"]),
        ("澳大利亚", ["australia", "sydney", "melbourne", "🇦🇺"]),
    ]
    for country, signals in rules:
        if any(signal in padded or signal in low for signal in signals):
            return country, f"description 命中 {country} 信号"
    return "", ""


def backup_path(csv_path: Path, date_str: str) -> Path:
    root = csv_path.resolve().parents[2]
    backup_dir = root / "Agency" / "list-bak" / date_str
    backup_dir.mkdir(parents=True, exist_ok=True)
    path = backup_dir / f"{csv_path.stem}_bak_{datetime.now().strftime('%H%M%S')}{csv_path.suffix}"
    shutil.copy2(csv_path, path)
    return path


def is_usable_payload(item: dict) -> bool:
    payload = item.get("payload")
    if item.get("http_status") != 200 or not isinstance(payload, dict):
        return False
    if not payload.get("success"):
        return False
    if payload.get("accountDoesNotExist") or payload.get("errorStatus") == 404:
        return False
    return True


def main() -> None:
    args = parse_args()
    csv_path = Path(args.csv).expanduser().resolve()
    json_path = Path(args.json).expanduser().resolve()
    df = pd.read_csv(csv_path, encoding="utf-8-sig").astype(object)
    report = json.loads(json_path.read_text(encoding="utf-8"))

    changes: list[dict] = []
    stats = {
        "rows_seen": 0,
        "rows_matched": 0,
        "handle_updated": 0,
        "name_updated": 0,
        "followers_updated": 0,
        "bio_platform_updated": 0,
        "links_platform_updated": 0,
        "cross_platform_updated": 0,
        "tags_platform_updated": 0,
        "contact_updated": 0,
        "contact_note_updated": 0,
        "language_filled": 0,
        "country_filled": 0,
    }

    for item in report.get("items", []):
        stats["rows_seen"] += 1
        row_no = int(item.get("row"))
        idx = row_no - 1
        if idx < 0 or idx >= len(df):
            continue
        if not is_usable_payload(item):
            continue
        payload = item.get("payload") or {}
        stats["rows_matched"] += 1

        row_changes: dict[str, dict[str, str]] = {}

        best_handle, best_name = pick_identity(
            payload,
            "YouTube",
            df.at[idx, "账号ID"],
            df.at[idx, "频道/作者名称"],
            df.at[idx, "账号链接"],
        )
        if best_handle and (
            not is_standard_handle(df.at[idx, "账号ID"])
            or clean_text(df.at[idx, "账号ID"]) != best_handle and clean_text(df.at[idx, "账号ID"]).startswith("UC")
        ):
            row_changes["账号ID"] = {"from": clean_text(df.at[idx, "账号ID"]), "to": best_handle}
            df.at[idx, "账号ID"] = best_handle
            stats["handle_updated"] += 1
        if clean_text(df.at[idx, "频道/作者名称"]) and not best_name:
            row_changes["频道/作者名称"] = {"from": clean_text(df.at[idx, "频道/作者名称"]), "to": ""}
            df.at[idx, "频道/作者名称"] = ""
            stats["name_updated"] += 1
        elif best_name and clean_text(df.at[idx, "频道/作者名称"]) != best_name:
            row_changes["频道/作者名称"] = {"from": clean_text(df.at[idx, "频道/作者名称"]), "to": best_name}
            df.at[idx, "频道/作者名称"] = best_name
            stats["name_updated"] += 1

        followers = normalize_followers(payload)
        if followers and clean_text(df.at[idx, "粉丝数"]) != followers:
            row_changes["粉丝数"] = {"from": clean_text(df.at[idx, "粉丝数"]), "to": followers}
            df.at[idx, "粉丝数"] = followers
            stats["followers_updated"] += 1

        description = clean_text(payload.get("description"))
        if description and clean_text(df.at[idx, "账号简介__平台抓取"]) != description:
            row_changes["账号简介__平台抓取"] = {
                "from": clean_text(df.at[idx, "账号简介__平台抓取"])[:120],
                "to": description[:120],
            }
            df.at[idx, "账号简介__平台抓取"] = description
            stats["bio_platform_updated"] += 1

        tags = clean_text(payload.get("tags"))
        if tags and clean_text(df.at[idx, "账号类目标签__平台抓取"]) != tags:
            row_changes["账号类目标签__平台抓取"] = {
                "from": clean_text(df.at[idx, "账号类目标签__平台抓取"]),
                "to": tags,
            }
            df.at[idx, "账号类目标签__平台抓取"] = tags
            stats["tags_platform_updated"] += 1

        merged_links = merge_links(df.at[idx, "外链__平台抓取"], payload.get("links"))
        if merged_links and clean_text(df.at[idx, "外链__平台抓取"]) != merged_links:
            row_changes["外链__平台抓取"] = {
                "from": clean_text(df.at[idx, "外链__平台抓取"]),
                "to": merged_links,
            }
            df.at[idx, "外链__平台抓取"] = merged_links
            stats["links_platform_updated"] += 1

        cross_platforms = detect_cross_platforms(clean_text(df.at[idx, "平台"]), merged_links or df.at[idx, "外链__平台抓取"])
        if cross_platforms and clean_text(df.at[idx, "多平台标记"]) != cross_platforms:
            row_changes["多平台标记"] = {
                "from": clean_text(df.at[idx, "多平台标记"]),
                "to": cross_platforms,
            }
            df.at[idx, "多平台标记"] = cross_platforms
            stats["cross_platform_updated"] += 1

        email = clean_text(payload.get("email"))
        if not email and description:
            match = re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", description, re.I)
            email = match.group(0) if match else ""
        if email and clean_text(df.at[idx, "联系方式"]).lower() != email.lower():
            row_changes["联系方式"] = {"from": clean_text(df.at[idx, "联系方式"]), "to": email}
            df.at[idx, "联系方式"] = email
            stats["contact_updated"] += 1

            note = "ScrapeCreators API"
            if clean_text(payload.get("email")):
                note += " 直出邮箱"
            else:
                note += " description 正则提取"
            if clean_text(df.at[idx, "联系方式备注"]) != note:
                row_changes["联系方式备注"] = {"from": clean_text(df.at[idx, "联系方式备注"]), "to": note}
                df.at[idx, "联系方式备注"] = note
                stats["contact_note_updated"] += 1

        if not clean_text(df.at[idx, "语言"]):
            language, reason = infer_language(payload)
            if language:
                row_changes["语言"] = {"from": "", "to": language, "reason": reason}
                df.at[idx, "语言"] = language
                stats["language_filled"] += 1

        if not clean_text(df.at[idx, "博主国家"]):
            country, reason = infer_country(payload)
            if country:
                row_changes["博主国家"] = {"from": "", "to": country, "reason": reason}
                df.at[idx, "博主国家"] = country
                stats["country_filled"] += 1

        changes.append(
            {
                "row": row_no,
                "handle": clean_text(df.at[idx, "账号ID"]),
                "url": clean_text(df.at[idx, "账号链接"]),
                "changes": row_changes,
            }
        )

    backup = ""
    if args.mode == "apply":
        backup = str(backup_path(csv_path, args.date))
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    print(
        json.dumps(
            {
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "csv_path": str(csv_path),
                "json_path": str(json_path),
                "mode": args.mode,
                "backup_path": backup,
                "stats": stats,
                "changes": changes,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
