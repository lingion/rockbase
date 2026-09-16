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
WORKBENCH_PLATFORM_NAME = "YouTube"


YOUTUBE_L1_REQUIRED_FIELDS = [
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

YOUTUBE_L1_FLEX_FIELDS = [
    "content_id",
    "channel_id",
    "channel_title",
    "top_content_title",
    "creator_max_views",
    "creator_top_content_url",
]

YOUTUBE_L2_REQUIRED_FIELDS = [
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
    "bio",
    "followers_count",
    "following_count",
    "statuses_count",
    "verified",
    "profile_url",
    "账号分类_平台抓取",
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
    "overall_score",
    "recommended_action",
    "decision_reason",
]

YOUTUBE_L2_FLEX_FIELDS = [
    "channel_id",
    "channel_title",
    "top_content_title",
    "theme_text",
    "video_count",
    "scrapecreators_status",
    "scrapecreators_handle",
    "scrapecreators_tags",
    "scrapecreators_keywords",
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


def skill_real_dir() -> Path:
    return Path(__file__).resolve().parents[2]


def _candidate_project_roots() -> list[Path]:
    candidates: list[Path] = []
    seen: set[Path] = set()

    def add_path(path: Path) -> None:
        for candidate in [path, *path.parents]:
            normalized = candidate.parent if candidate.name == ".agent" else candidate
            if normalized not in seen:
                seen.add(normalized)
                candidates.append(normalized)

    add_path(Path.cwd().resolve())
    add_path(Path(__file__).resolve())
    return candidates


def _looks_like_project_root(path: Path) -> bool:
    return (path / "workbench").is_dir() and (path / "AGENTS.md").is_file()


def skill_dir() -> Path:
    root = ensure_project_root()
    public_path = root / "⚪ skills" / skill_real_dir().name
    return public_path if public_path.exists() else skill_real_dir()


def ensure_project_root() -> Path:
    for candidate in _candidate_project_roots():
        if _looks_like_project_root(candidate):
            return candidate
    for candidate in _candidate_project_roots():
        if (candidate / "workbench").is_dir():
            return candidate
    raise FileNotFoundError("Could not locate project root containing workbench/")


def skill_env_path() -> Path:
    override = os.environ.get("YOUTUBE_KOL_SKILL_ENV_PATH") or os.environ.get("SKILL_ENV_PATH")
    if override:
        return Path(override).expanduser().resolve()
    return skill_dir() / ".env"


def load_skill_env() -> dict[str, str]:
    candidates = [skill_env_path(), GLOBAL_ENV]
    for path in candidates:
        if path.exists():
            return load_simple_env(path)
    return {}


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


def skill_docs_dir() -> Path:
    out_dir = skill_dir() / "docs"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def workbench_date_dir(run_date: str) -> Path:
    out_dir = ensure_project_root() / "workbench" / run_date
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def workbench_dir(run_date: str) -> Path:
    out_dir = workbench_date_dir(run_date) / WORKBENCH_PLATFORM_NAME
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def backup_csv_if_exists(path: Path, run_date: str) -> Path | None:
    return None


def content_rows_to_csv_rows(rows: list[dict[str, Any]], *, min_views_for_l2: int) -> list[dict[str, Any]]:
    csv_rows: list[dict[str, Any]] = []
    for row in rows:
        view_count = int(row.get("view_count") or 0)
        csv_rows.append(
            {
                "platform": "youtube",
                "row_type": "content",
                "content_id": safe_text(row.get("video_id")),
                "content_title": safe_text(row.get("title")),
                "theme_text": safe_text(row.get("title")),
                "matched_query_name": safe_text(row.get("query_name")),
                "matched_query_text": safe_text(row.get("query_text")),
                "creator_handle": safe_text(row.get("channel_id")) or safe_text(row.get("channel_title")),
                "display_name": safe_text(row.get("channel_title")),
                "channel_id": safe_text(row.get("channel_id")),
                "channel_title": safe_text(row.get("channel_title")),
                "view_count": view_count,
                "like_count": int(row.get("like_count") or 0),
                "comment_count": int(row.get("comment_count") or 0),
                "content_url": safe_text(row.get("url")),
                "provider_source": safe_text(row.get("provider")),
                "discovery_route": safe_text(row.get("discovery_route")),
                "content_tags_or_hashtags": " | ".join(row.get("tags") or []),
                "l2_eligible": "yes" if view_count >= min_views_for_l2 else "no",
                "l2_skip_reason": "" if view_count >= min_views_for_l2 else f"views_below_{min_views_for_l2}",
                "matched_content_count": 1,
                "creator_max_views": view_count,
                "creator_top_content_url": safe_text(row.get("url")),
            }
        )
    csv_rows.sort(key=lambda item: (-int(item["view_count"]), item["content_id"]))
    return csv_rows
