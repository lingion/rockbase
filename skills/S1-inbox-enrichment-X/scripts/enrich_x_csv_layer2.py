from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re

import pandas as pd

from load_env import default_workbench_dir

RECENT_METRICS_CUTOFF_DATE = "2026-01-01"


def normalize_handle(value: str) -> str:
    return str(value or "").strip().lstrip("@").lower()


def clean_text(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value or "").strip()
    return "" if text.lower() == "nan" else text


def compact_number(value: int | float | None) -> str:
    if value is None or pd.isna(value):
        return ""
    value = float(value)
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}".rstrip("0").rstrip(".") + "M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}".rstrip("0").rstrip(".") + "K"
    return str(int(value))


def thousand_int(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return ""
    return f"{int(round(float(value))):,}"


def pct_1(value: float | None) -> str:
    if value is None or pd.isna(value):
        return ""
    return f"{value * 100:.1f}%"


def standardize_error_note(raw_error: str) -> str:
    text = str(raw_error or "").strip()
    lowered = text.lower()
    if not text:
        return "Bad payload"
    if "proxyerror" in lowered or "connection" in lowered or "timeout" in lowered:
        return "Network error"
    return "Bad payload"


def is_reply(tweet: dict) -> bool:
    legacy = tweet.get("legacy") or {}
    return any(
        legacy.get(k)
        for k in ("in_reply_to_status_id_str", "in_reply_to_user_id_str", "in_reply_to_screen_name")
    )


def is_retweet(tweet: dict) -> bool:
    legacy = tweet.get("legacy") or {}
    text = str(legacy.get("full_text") or "")
    return text.startswith("RT @") or "retweeted_status_result" in tweet


def is_quote_tweet(tweet: dict) -> bool:
    legacy = tweet.get("legacy") or {}
    return bool(legacy.get("is_quote_status")) or "quoted_status_result" in tweet


def parse_lang(tweets: list[dict]) -> str:
    counts: dict[str, int] = {}
    for tweet in tweets:
        lang = (tweet.get("legacy") or {}).get("lang")
        if lang:
            counts[lang] = counts.get(lang, 0) + 1
    if not counts:
        return ""
    total = sum(counts.values())
    top_lang, top_count = max(counts.items(), key=lambda x: x[1])
    if top_lang == "zh" and top_count / total >= 0.6:
        return "中文"
    if top_lang == "en" and top_count / total >= 0.6:
        return "English"
    if {"zh", "en"}.issubset(counts):
        return "中英双语"
    return top_lang


def infer_external_url(user_legacy: dict) -> str:
    entities = user_legacy.get("entities") or {}
    url_block = entities.get("url") or {}
    urls = url_block.get("urls") or []
    if urls:
        return urls[0].get("expanded_url") or urls[0].get("url") or ""
    return user_legacy.get("url") or ""


def summarize_text(text: str, limit: int = 80) -> str:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    text = re.sub(r"https?://\S+", "", text).strip()
    if not text:
        return "Posted on X"
    if len(text) > limit:
        text = text[: limit - 3].rstrip() + "..."
    return f"Posted: {text}"


def build_latest_activity_proof(tweet: dict) -> str:
    legacy = tweet.get("legacy") or {}
    created_at = legacy.get("created_at")
    text = legacy.get("full_text") or ""
    try:
        dt = datetime.strptime(created_at, "%a %b %d %H:%M:%S %z %Y")
        date_str = dt.strftime("%Y-%m-%d")
    except Exception:
        date_str = ""
    summary = summarize_text(text)
    return f"【{date_str}】{summary}" if date_str else summary


def tweet_sort_key(tweet: dict) -> datetime:
    created_at = (tweet.get("legacy") or {}).get("created_at")
    try:
        return datetime.strptime(created_at, "%a %b %d %H:%M:%S %z %Y")
    except Exception:
        return datetime.min.replace(tzinfo=None)


def analyze_latest_activity(originals: list[dict], tweets: list[dict]) -> tuple[str, list[str]]:
    notes: list[str] = []
    source = originals if originals else tweets
    if not source:
        return "", notes

    ranked = sorted(source, key=tweet_sort_key, reverse=True)
    latest = ranked[0]
    proof = build_latest_activity_proof(latest)

    latest_dt = tweet_sort_key(latest)
    now_utc = datetime.now(timezone.utc)
    if latest_dt != datetime.min.replace(tzinfo=None):
        if latest_dt.tzinfo is None:
            latest_dt = latest_dt.replace(tzinfo=timezone.utc)
        age_days = (now_utc - latest_dt).days
        if latest_dt > now_utc:
            notes.append("Latest proof future-dated from API")
        elif age_days >= 365:
            notes.append(f"Latest proof stale snapshot ({age_days}d old)")

    # The API payload does not expose a reliable pinned marker.
    # When the freshest original tweet is very old, flag low confidence so the row
    # can be re-verified via browser workflow instead of being trusted blindly.
    if proof and "Latest proof stale snapshot" in " | ".join(notes):
        notes.append("Need browser recheck for non-pinned latest post")

    return proof, notes


def load_handle_manifest_map(out_dir: Path) -> dict[str, Path]:
    manifest_files = sorted(out_dir.glob("x_api_manifest_*.json"))
    if not manifest_files:
        raise FileNotFoundError(f"未在 {out_dir} 找到 x_api_manifest_*.json")

    handle_to_file: dict[str, Path] = {}
    for manifest_file in manifest_files:
        items = json.loads(manifest_file.read_text(encoding="utf-8"))
        for item in items:
            handle = normalize_handle(item.get("handle", ""))
            file_path = item.get("file", "")
            if handle and file_path:
                handle_to_file[handle] = Path(file_path)
    return handle_to_file


@dataclass
class Metrics:
    followers: str = ""
    avg_views_10: str = ""
    avg_er_view_10: str = ""
    avg_er_followers_10: str = ""
    language: str = ""
    name: str = ""
    bio: str = ""
    profile_url: str = ""
    external_url: str = ""
    latest_activity_proof: str = ""
    note: str = ""
    recent_metrics_ready: bool = False


def extract_metrics(json_path: Path) -> Metrics:
    raw = json.loads(json_path.read_text(encoding="utf-8"))
    data = raw.get("response_json")
    if not isinstance(data, dict):
        return Metrics(note=standardize_error_note(raw.get("error") or "API payload missing response_json"))
    message = str(data.get("message") or "").strip()
    tweets = data.get("tweets") or []
    if not tweets:
        if "account doesn't exist" in message.lower() or "account doesnt exist" in message.lower():
            return Metrics(note="Account doesn't exist")
        return Metrics(note="API no tweets")

    first = tweets[0]
    user_legacy = ((((first.get("core") or {}).get("user_results") or {}).get("result")) or {}).get("legacy") or {}
    followers_count = user_legacy.get("followers_count")

    originals = [t for t in tweets if not is_reply(t) and not is_retweet(t)]
    originals.sort(key=tweet_sort_key, reverse=True)
    standalone_originals = [t for t in originals if not is_quote_tweet(t)]
    sample = standalone_originals[:10]

    view_values = []
    er_view_values = []
    er_follow_values = []
    for tweet in sample:
        legacy = tweet.get("legacy") or {}
        views_obj = tweet.get("views") or {}
        views_count = views_obj.get("count")
        views_num = int(views_count) if str(views_count).isdigit() else None
        interactions = sum(int(legacy.get(k) or 0) for k in ("favorite_count", "reply_count", "retweet_count", "quote_count"))
        if views_num and views_num > 0:
            view_values.append(views_num)
            er_view_values.append(interactions / views_num)
        if followers_count and followers_count > 0:
            er_follow_values.append(interactions / followers_count)

    note = ""
    if len(sample) < 10:
        note = f"Original sample < 10 ({len(sample)})"

    latest_activity_proof, latest_notes = analyze_latest_activity(originals, tweets)
    if latest_notes:
        note = " | ".join(x for x in [note, *latest_notes] if x)

    latest_date = ""
    m = re.search(r"【(\d{4}-\d{2}-\d{2})】", latest_activity_proof)
    if m:
        latest_date = m.group(1)
    if latest_date and latest_date < RECENT_METRICS_CUTOFF_DATE:
        note = " | ".join(
            x for x in [note, f"Recent-10 metrics cleared: latest activity before {RECENT_METRICS_CUTOFF_DATE}"] if x
        )
        view_values = []
        er_view_values = []
        er_follow_values = []

    return Metrics(
        followers=compact_number(followers_count),
        avg_views_10=thousand_int(sum(view_values) / len(view_values)) if view_values else "",
        avg_er_view_10=pct_1(sum(er_view_values) / len(er_view_values)) if er_view_values else "",
        avg_er_followers_10=pct_1(sum(er_follow_values) / len(er_follow_values)) if er_follow_values else "",
        language=parse_lang(sample),
        name=str(user_legacy.get("name") or ""),
        bio=str(user_legacy.get("description") or ""),
        profile_url=f"https://x.com/{user_legacy.get('screen_name')}" if user_legacy.get("screen_name") else "",
        external_url=infer_external_url(user_legacy),
        latest_activity_proof=latest_activity_proof,
        note=note,
        recent_metrics_ready=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--mode", choices=["preview", "apply"], default="preview")
    parser.add_argument("--workbench-date", default="")
    args = parser.parse_args()

    df = pd.read_csv(args.csv, encoding="utf-8-sig")
    writable_cols = [
        "频道/作者名称",
        "账号链接",
        "语言",
        "粉丝数",
        "账号简介__平台抓取",
        "Latest Activity Proof",
        "外链__平台抓取",
        "近期10条均播",
        "近10条平均ER（按曝光）",
        "近10条平均ER（按粉丝）",
        "联系方式备注",
    ]
    for col in writable_cols:
        if col in df.columns:
            df[col] = df[col].astype("object")
    out_dir = default_workbench_dir(args.workbench_date or None)
    handle_to_file = load_handle_manifest_map(out_dir)

    for idx, row in df.iterrows():
        handle = normalize_handle(row.get("账号ID", ""))
        json_path = handle_to_file.get(handle)
        if not json_path or not json_path.exists():
            continue
        metrics = extract_metrics(json_path)
        if metrics.name:
            df.at[idx, "频道/作者名称"] = metrics.name
        if metrics.profile_url:
            df.at[idx, "账号链接"] = metrics.profile_url
        if metrics.language:
            df.at[idx, "语言"] = metrics.language
        if metrics.followers:
            df.at[idx, "粉丝数"] = metrics.followers
        if metrics.bio:
            df.at[idx, "账号简介__平台抓取"] = metrics.bio
        if "Latest Activity Proof" in df.columns and metrics.latest_activity_proof:
            df.at[idx, "Latest Activity Proof"] = metrics.latest_activity_proof
        if metrics.external_url:
            df.at[idx, "外链__平台抓取"] = metrics.external_url
        if metrics.recent_metrics_ready:
            if "近期10条均播" in df.columns:
                df.at[idx, "近期10条均播"] = metrics.avg_views_10
            if "近10条平均ER（按曝光）" in df.columns:
                df.at[idx, "近10条平均ER（按曝光）"] = metrics.avg_er_view_10
            if "近10条平均ER（按粉丝）" in df.columns:
                df.at[idx, "近10条平均ER（按粉丝）"] = metrics.avg_er_followers_10
        if metrics.note:
            current = clean_text(row.get("联系方式备注", ""))
            df.at[idx, "联系方式备注"] = " | ".join(x for x in [current, metrics.note] if x)

    target = args.csv if args.mode == "apply" else args.csv.with_name(args.csv.stem + ".preview.csv")
    df.to_csv(target, index=False, encoding="utf-8-sig")
    print(json.dumps({"mode": args.mode, "output": str(target)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
