from __future__ import annotations

import csv
import json
import os
import re
from pathlib import Path
from typing import Any


GLOBAL_ENV = Path(
    "${ROCKBASE_HOME}/Library/Mobile Documents/iCloud~md~obsidian/Documents/My Vault/000 🟢 AG-Global/🟢 API/SECRTE_API_Key.env"
)
_ENV_REF_RE = re.compile(r"\$\{([^}]+)\}")
WORKBENCH_PLATFORM_NAME = "TikTok"


TIKTOK_L1_REQUIRED_FIELDS = [
    "platform",
    "row_type",
    "creator_handle",
    "display_name",
    "content_title",
    "theme_text",
    "content_url",
    "view_count",
    "like_count",
    "comment_count",
    "matched_query_name",
    "matched_query_text",
    "matched_queries",
    "matched_content_count",
    "max_views",
    "max_likes",
    "max_comments",
    "sample_contents",
    "top_content_url",
    "source_content_ids",
    "provider_source",
    "discovery_route",
    "content_tags_or_hashtags",
    "l2_eligible",
    "l2_skip_reason",
]

TIKTOK_L1_FLEX_FIELDS = [
    "content_id",
    "author_unique_id",
    "author_id",
    "nickname",
    "sec_uid",
    "create_time",
    "share_count",
    "collect_count",
    "music_title",
    "region",
    "is_ad",
    "aweme_type",
    "cover_url",
    "duration",
    "session_required",
    "proxy_required",
]

TIKTOK_L2_REQUIRED_FIELDS = [
    "platform",
    "creator_handle",
    "display_name",
    "matched_queries",
    "matched_content_count",
    "max_views",
    "max_likes",
    "max_comments",
    "sample_contents",
    "top_content_url",
    "source_content_ids",
    "provider_source",
    "discovery_route",
    "content_tags_or_hashtags",
    "账号类目标签__平台抓取",
    "bio",
    "followers_count",
    "following_count",
    "statuses_count",
    "verified",
    "profile_url",
    "external_links",
    "contact_signals",
    "contact_value",
    "contact_note",
    "email_source_url",
    "contact_page_crawl_status",
    "contact_page_checked_urls",
    "enrichment_provider",
    "enrichment_status",
    "enrichment_error",
    "topic_match_score",
    "profile_match_score",
    "activity_score",
    "contactability_score",
    "overall_score",
    "recommended_action",
    "decision_reason",
    "country_inferred",
    "country_confidence",
    "primary_language",
    "language_mix",
]

TIKTOK_L2_FLEX_FIELDS = [
    "author_unique_id",
    "author_id",
    "nickname",
    "sec_uid",
    "view_count",
    "like_count",
    "comment_count",
    "content_title",
    "theme_text",
    "content_url",
    "bio_link",
    "bio_link_host",
    "likes_count",
    "layer2_eligible",
    "layer2_skip_reason",
]


def safe_text(value: Any) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()


def load_simple_env(env_path: Path) -> dict[str, str]:
    def expand_refs(raw_value: str, current: dict[str, str]) -> str:
        def replace(match: re.Match[str]) -> str:
            key = match.group(1).strip()
            return current.get(key, match.group(0))

        return _ENV_REF_RE.sub(replace, raw_value)

    def unquote(value: str) -> str:
        text = value.strip()
        if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
            return text[1:-1]
        return text

    data: dict[str, str] = {}
    if not env_path.exists():
        raise FileNotFoundError(f"Missing env file: {env_path}")
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = unquote(expand_refs(value.strip(), data))
    return data


def skill_dir() -> Path:
    return Path(__file__).resolve().parents[2]


def ensure_project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if parent.name == ".agent":
            continue
        if (parent / "workbench").is_dir() and (parent / "Agency").is_dir():
            return parent
    raise FileNotFoundError("Could not locate project root containing workbench/")


def skill_local_env_path() -> Path:
    override = os.environ.get("TIKTOK_KOL_LOCAL_ENV_PATH")
    if override:
        return Path(override).expanduser().resolve()
    return skill_dir() / ".env.local"


def shared_env_path() -> Path:
    override = os.environ.get("TIKTOK_KOL_SHARED_ENV_PATH") or os.environ.get("SKILL_ENV_PATH")
    if override:
        return Path(override).expanduser().resolve()
    local_ref = skill_dir() / ".env.runtime"
    if local_ref.exists():
        return local_ref
    return GLOBAL_ENV


def load_skill_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    shared = shared_env_path()
    if shared.exists():
        merged.update(load_simple_env(shared))
    local = skill_local_env_path()
    if local.exists():
        merged.update(load_simple_env(local))
    return merged


def get_env_value(*names: str) -> str:
    for env_name in names:
        value = os.getenv(env_name)
        if value:
            return value.strip()
    env = load_skill_env()
    for env_name in names:
        value = env.get(env_name)
        if value:
            return value.strip()
    return ""


def truthy_env(name: str, default: bool = False) -> bool:
    value = get_env_value(name)
    if not value:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def order_fieldnames(rows: list[dict[str, Any]], preferred_fields: list[str] | None = None) -> list[str]:
    preferred_fields = preferred_fields or []
    fieldnames: list[str] = []
    seen: set[str] = set()
    available = {key for row in rows for key in row.keys()}

    for key in preferred_fields:
        if key in available and key not in seen:
            seen.add(key)
            fieldnames.append(key)

    for row in rows:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)

    return fieldnames


def write_csv(path: Path, rows: list[dict[str, Any]], *, preferred_fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8-sig")
        return
    fieldnames = order_fieldnames(rows, preferred_fields)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def workbench_dir(run_date: str) -> Path:
    out_dir = ensure_project_root() / "workbench" / run_date / WORKBENCH_PLATFORM_NAME
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def skill_docs_dir() -> Path:
    out_dir = skill_dir() / "docs"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir
