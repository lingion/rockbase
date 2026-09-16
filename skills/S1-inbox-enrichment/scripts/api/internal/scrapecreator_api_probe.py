from __future__ import annotations

import argparse
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pandas as pd
import requests


ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / "env"

YOUTUBE_ENDPOINT = "https://api.scrapecreators.com/v1/youtube/channel"
TIKTOK_ENDPOINT = "https://api.scrapecreators.com/v1/tiktok/profile"
INSTAGRAM_ENDPOINT = "https://api.scrapecreators.com/v1/instagram/profile"

PLATFORMS = ("YouTube", "TikTok", "Instagram")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe ScrapeCreators API on S1 samples and optionally apply conservative updates.")
    parser.add_argument("--csv-path", required=True)
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--samples-per-platform", type=int, default=3)
    parser.add_argument("--delay-seconds", type=float, default=0.8)
    parser.add_argument("--timeout-seconds", type=int, default=45)
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args()


def load_env_file(path: Path) -> dict[str, str]:
    env_vars: dict[str, str] = {}
    if not path.exists():
        return env_vars
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env_vars[key.strip()] = value.strip().strip('"').strip("'")
    return env_vars


def clean_text(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def canonicalize_url(value: Any) -> str:
    text = clean_text(value)
    if not text:
        return ""
    if not text.startswith("http"):
        return text.rstrip("/")
    parsed = urlparse(text)
    path = re.sub(r"/+", "/", parsed.path or "/").rstrip("/")
    for suffix in ("/videos", "/video", "/reels", "/reel", "/shorts", "/search"):
        if path.lower().endswith(suffix):
            path = path[: -len(suffix)].rstrip("/")
    path = path or "/"
    return f"{parsed.scheme}://{parsed.netloc}{path}".rstrip("/")


def extract_handle(url: str, fallback: str = "") -> str:
    if fallback and not fallback.startswith("http"):
        if re.fullmatch(r"UC[0-9A-Za-z_-]+", fallback):
            return fallback
        return "@" + fallback.lstrip("@")
    normalized = canonicalize_url(url or fallback)
    if not normalized.startswith("http"):
        return ""
    parsed = urlparse(normalized)
    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if not parts:
        return ""
    if parts[0].lower() in {"channel", "c", "user"} and len(parts) > 1:
        val = parts[1].strip()
        return val if parts[0].lower() == "channel" else "@" + val.lstrip("@")
    return "@" + parts[-1].lstrip("@")


def format_followers(count: Any, text: Any) -> str:
    text_value = clean_text(text)
    if text_value:
        return text_value
    if count in (None, ""):
        return ""
    try:
        num = float(count)
    except Exception:
        return clean_text(count)
    if num >= 1_000_000:
        val = num / 1_000_000
        return f"{val:.1f}M".replace(".0M", "M")
    if num >= 1_000:
        val = num / 1_000
        return f"{val:.1f}K".replace(".0K", "K")
    return str(int(num))


def merge_links(existing: str, incoming: list[str]) -> str:
    values: list[str] = []
    seen: set[str] = set()
    for candidate in [part.strip() for part in clean_text(existing).split(" | ") if part.strip()] + incoming:
        normalized = clean_text(candidate)
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        values.append(normalized)
    return " | ".join(values)


def select_samples(df: pd.DataFrame, per_platform: int) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for platform in PLATFORMS:
        subset = df[df["平台"].astype(str).str.lower() == platform.lower()].copy()
        subset = subset[subset["账号链接"].fillna("").astype(str).str.strip() != ""]
        if platform == "YouTube":
            subset = subset[subset["账号链接"].astype(str).str.contains("youtube.com|youtu.be", case=False, regex=True)]
        elif platform == "TikTok":
            subset = subset[subset["账号链接"].astype(str).str.contains("tiktok.com", case=False, regex=True)]
        elif platform == "Instagram":
            subset = subset[subset["账号链接"].astype(str).str.contains("instagram.com", case=False, regex=True)]
        count = 0
        for idx, row in subset.iterrows():
            selected.append(
                {
                    "row_index": idx,
                    "row_no": idx + 2,
                    "platform": platform,
                    "name": clean_text(row.get("频道/作者名称")),
                    "handle": clean_text(row.get("账号ID")),
                    "url": canonicalize_url(row.get("账号链接")),
                }
            )
            count += 1
            if count >= per_platform:
                break
    return selected


def fetch_payload(session: requests.Session, platform: str, url: str, handle: str, timeout: int) -> tuple[int, dict[str, Any]]:
    if platform == "YouTube":
        response = session.get(YOUTUBE_ENDPOINT, params={"url": url}, timeout=timeout)
    elif platform == "TikTok":
        response = session.get(TIKTOK_ENDPOINT, params={"handle": handle.lstrip("@")}, timeout=timeout)
    elif platform == "Instagram":
        response = session.get(INSTAGRAM_ENDPOINT, params={"handle": handle.lstrip("@")}, timeout=timeout)
    else:
        raise ValueError(f"Unsupported platform: {platform}")
    payload = response.json() if response.headers.get("content-type", "").startswith("application/json") else {"raw_text": response.text[:2000]}
    return response.status_code, payload


def extract_api_fields(platform: str, payload: dict[str, Any]) -> dict[str, Any]:
    if platform == "YouTube":
        description = clean_text(payload.get("description"))
        return {
            "api_handle": extract_handle(clean_text(payload.get("handle"))),
            "api_name": clean_text(payload.get("name")),
            "api_followers": format_followers(payload.get("subscriberCount"), payload.get("subscriberCountText")),
            "api_bio": description,
            "api_contact": clean_text(payload.get("email")) or extract_email(description),
            "api_contact_note": "ScrapeCreators API email" if clean_text(payload.get("email")) else ("ScrapeCreators API description regex" if extract_email(description) else ""),
            "api_links": [clean_text(item.get("url")) if isinstance(item, dict) else clean_text(item) for item in (payload.get("links") or []) if clean_text(item.get("url") if isinstance(item, dict) else item)],
            "api_category": "",
        }
    user = payload.get("user") if isinstance(payload.get("user"), dict) else payload
    if platform == "TikTok":
        bio = clean_text(user.get("signature"))
        return {
            "api_handle": extract_handle("", clean_text(user.get("uniqueId")) or clean_text(user.get("username"))),
            "api_name": clean_text(user.get("nickname")),
            "api_followers": format_followers(user.get("followerCount"), ""),
            "api_bio": bio,
            "api_contact": clean_text(user.get("email")) or extract_email(bio),
            "api_contact_note": "ScrapeCreators API email" if clean_text(user.get("email")) else ("ScrapeCreators bio regex" if extract_email(bio) else ""),
            "api_links": [clean_text(item.get("link")) if isinstance(item, dict) else clean_text(item) for item in (user.get("bioLink") or user.get("bioLinks") or []) if clean_text(item.get("link") if isinstance(item, dict) else item)],
            "api_category": clean_text(user.get("commerceUserInfo", {}).get("category")) if isinstance(user.get("commerceUserInfo"), dict) else "",
        }
    biography = clean_text(user.get("biography"))
    links = []
    for item in (user.get("bio_links") or []):
        if isinstance(item, dict):
            value = clean_text(item.get("url") or item.get("link"))
        else:
            value = clean_text(item)
        if value:
            links.append(value)
    external_url = clean_text(user.get("external_url"))
    if external_url:
        links.append(external_url)
    return {
        "api_handle": extract_handle("", clean_text(user.get("username"))),
        "api_name": clean_text(user.get("full_name")),
        "api_followers": format_followers(user.get("follower_count"), ""),
        "api_bio": biography,
        "api_contact": clean_text(user.get("public_email")) or extract_email(biography),
        "api_contact_note": "ScrapeCreators API email" if clean_text(user.get("public_email")) else ("ScrapeCreators bio regex" if extract_email(biography) else ""),
        "api_links": links,
        "api_category": clean_text(user.get("category_name")),
    }


def extract_email(text: str) -> str:
    match = re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", text or "", re.I)
    return match.group(0) if match else ""


def should_overwrite_name(current: str, api_value: str) -> bool:
    if not api_value:
        return False
    if not current:
        return True
    if current.startswith("@") and api_value != current:
        return True
    return len(api_value) > len(current) + 3


def should_overwrite_bio(current: str, api_value: str) -> bool:
    if not api_value:
        return False
    if not current:
        return True
    return len(api_value) > len(current) * 1.2


def should_overwrite_followers(current: str, api_value: str) -> bool:
    if not api_value:
        return False
    if not current:
        return True
    return current != api_value


def apply_updates(df: pd.DataFrame, sample: dict[str, Any], extracted: dict[str, Any]) -> dict[str, Any]:
    idx = sample["row_index"]
    changes: dict[str, Any] = {}

    current_handle = clean_text(df.at[idx, "账号ID"])
    api_handle = clean_text(extracted["api_handle"])
    if api_handle and (not current_handle or current_handle != api_handle):
        df.at[idx, "账号ID"] = api_handle
        changes["账号ID"] = api_handle

    current_name = clean_text(df.at[idx, "频道/作者名称"])
    api_name = clean_text(extracted["api_name"])
    if should_overwrite_name(current_name, api_name):
        df.at[idx, "频道/作者名称"] = api_name
        changes["频道/作者名称"] = api_name

    current_followers = clean_text(df.at[idx, "粉丝数"])
    api_followers = clean_text(extracted["api_followers"])
    if should_overwrite_followers(current_followers, api_followers):
        df.at[idx, "粉丝数"] = api_followers
        changes["粉丝数"] = api_followers

    current_bio = clean_text(df.at[idx, "账号简介__平台抓取"])
    api_bio = clean_text(extracted["api_bio"])
    if should_overwrite_bio(current_bio, api_bio):
        df.at[idx, "账号简介__平台抓取"] = api_bio
        changes["账号简介__平台抓取"] = api_bio[:160]

    current_contact = clean_text(df.at[idx, "联系方式"])
    api_contact = clean_text(extracted["api_contact"])
    if api_contact and (not current_contact or not extract_email(current_contact) or current_contact.lower() != api_contact.lower()):
        df.at[idx, "联系方式"] = api_contact
        changes["联系方式"] = api_contact
        note = clean_text(extracted["api_contact_note"])
        if note:
            df.at[idx, "联系方式备注"] = note
            changes["联系方式备注"] = note

    current_links = clean_text(df.at[idx, "外链__平台抓取"])
    merged_links = merge_links(current_links, extracted["api_links"])
    if merged_links and merged_links != current_links:
        df.at[idx, "外链__平台抓取"] = merged_links
        changes["外链__平台抓取"] = merged_links[:160]

    current_category = clean_text(df.at[idx, "账号类目标签__平台抓取"])
    api_category = clean_text(extracted["api_category"])
    if api_category and (not current_category or len(api_category) > len(current_category)):
        df.at[idx, "账号类目标签__平台抓取"] = api_category
        changes["账号类目标签__平台抓取"] = api_category

    return changes


def main() -> None:
    args = parse_args()
    env = load_env_file(ENV_PATH)
    api_key = env.get("SCRAPECREATORS_API_KEY") or os.getenv("SCRAPECREATORS_API_KEY", "")
    if not api_key:
        raise RuntimeError(f"SCRAPECREATORS_API_KEY not found in {ENV_PATH}")

    csv_path = Path(args.csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(csv_path)

    project_root = csv_path.resolve().parents[2]
    workbench_root = project_root / "workbench"
    print(f"📍 Routing to: {workbench_root / args.date}")
    df = pd.read_csv(csv_path)
    samples = select_samples(df, args.samples_per_platform)

    session = requests.Session()
    session.headers.update({"x-api-key": api_key})

    workbench_dir = workbench_root / args.date
    workbench_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%H%M%S")
    raw_path = workbench_dir / f"scrapecreator_s1_probe_{timestamp}_raw.json"
    summary_path = workbench_dir / f"scrapecreator_s1_probe_{timestamp}_summary.json"
    apply_path = workbench_dir / f"scrapecreator_s1_probe_{timestamp}_apply.json"

    raw_items: list[dict[str, Any]] = []
    summary_items: list[dict[str, Any]] = []
    apply_items: list[dict[str, Any]] = []

    for i, sample in enumerate(samples):
        handle = extract_handle(sample["url"], sample["handle"])
        sample["handle"] = handle
        status, payload = fetch_payload(session, sample["platform"], sample["url"], handle, args.timeout_seconds)
        extracted = extract_api_fields(sample["platform"], payload if isinstance(payload, dict) else {})
        raw_items.append(
            {
                "sample": sample,
                "http_status": status,
                "payload": payload,
            }
        )
        summary_items.append(
            {
                "sample": sample,
                "http_status": status,
                "extracted": extracted,
                "top_level_keys": sorted(list(payload.keys())) if isinstance(payload, dict) else [],
                "user_keys": sorted(list(payload.get("user", {}).keys())) if isinstance(payload, dict) and isinstance(payload.get("user"), dict) else [],
            }
        )
        if args.apply:
            changes = apply_updates(df, sample, extracted)
            apply_items.append({"sample": sample, "changes": changes})
        if i < len(samples) - 1:
            time.sleep(args.delay_seconds)

    raw_path.write_text(json.dumps({"timestamp": datetime.now().isoformat(timespec="seconds"), "items": raw_items}, ensure_ascii=False, indent=2), encoding="utf-8")
    summary_path.write_text(json.dumps({"timestamp": datetime.now().isoformat(timespec="seconds"), "items": summary_items}, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.apply:
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        apply_path.write_text(json.dumps({"timestamp": datetime.now().isoformat(timespec="seconds"), "items": apply_items}, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "samples": len(samples),
                "raw_path": str(raw_path),
                "summary_path": str(summary_path),
                "apply_path": str(apply_path) if args.apply else "",
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
