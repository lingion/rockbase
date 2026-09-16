from __future__ import annotations

from pathlib import Path
from typing import Any

from x_kol_discovery.config import Layer1RunConfig
from x_kol_discovery.io_utils import agency_list_master_dir, backup_csv_if_exists, read_csv, safe_text, write_csv
DISCOVERY_MASTER_COLUMNS = [
    "platform",
    "username",
    "display_name",
    "profile_url",
    "first_seen_date",
    "last_seen_date",
    "first_seen_batch",
    "last_seen_batch",
    "best_max_views_seen",
    "best_top_tweet_url",
    "latest_matched_queries",
    "times_seen_after_views_gate",
    "last_layer2_provider",
    "last_followers_count",
    "last_following_count",
    "last_statuses_count",
    "last_verified",
    "last_blue_verified",
    "last_bio",
    "last_location_raw",
    "last_external_links",
    "last_contact_value",
    "last_contact_note",
    "last_enriched_at",
    "master_status",
]


def discovery_master_path() -> Path:
    return agency_list_master_dir() / "x_kol_discovery_master.csv"


def _to_int(value: Any) -> int:
    try:
        return int(str(value or "0").replace(",", "").strip())
    except ValueError:
        return 0


def load_discovery_master(path: Path | None = None) -> tuple[dict[str, dict[str, str]], Path]:
    target = path or discovery_master_path()
    if not target.exists():
        return {}, target
    rows = read_csv(target)
    mapping = {safe_text(row.get("username")).lower(): row for row in rows if safe_text(row.get("username"))}
    return mapping, target


def route_candidates_with_discovery_master(
    candidates: list[dict[str, Any]],
    config: Layer1RunConfig,
    *,
    batch_name: str,
    master_path: Path | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], Path]:
    if not config.discovery_master_enabled:
        return candidates, [], [], master_path or discovery_master_path()

    master_by_username, resolved_path = load_discovery_master(master_path)
    to_enrich: list[dict[str, Any]] = []
    blocked_rows: list[dict[str, Any]] = []
    meta: list[dict[str, Any]] = []

    for candidate in candidates:
        username = safe_text(candidate.get("username")).lower()
        if not username:
            continue
        master_row = master_by_username.get(username)
        if not master_row:
            to_enrich.append(candidate)
            meta.append(
                {
                    "username": username,
                    "status": "new_candidate",
                    "reason": "not_in_master",
                    "batch_name": batch_name,
                    "max_views": safe_text(candidate.get("max_views")),
                    "profile_url": safe_text(candidate.get("profile_url")),
                }
            )
            continue
        blocked_rows.append(candidate)
        meta.append(
            {
                "username": username,
                "status": "blocked_by_master",
                "reason": "already_in_master",
                "batch_name": batch_name,
                "max_views": safe_text(candidate.get("max_views")),
                "profile_url": safe_text(candidate.get("profile_url")),
            }
        )

    return to_enrich, blocked_rows, meta, resolved_path


def _master_row_for_candidate(
    candidate: dict[str, Any],
    *,
    existing: dict[str, str] | None,
    enriched_row: dict[str, Any] | None,
    batch_name: str,
    run_date: str,
) -> dict[str, str]:
    existing = existing or {}
    enriched_row = enriched_row or {}
    best_views = max(_to_int(existing.get("best_max_views_seen")), _to_int(candidate.get("max_views")))
    current_top_tweet = safe_text(candidate.get("top_tweet_url"))
    best_top_tweet = safe_text(existing.get("best_top_tweet_url"))
    if _to_int(candidate.get("max_views")) >= _to_int(existing.get("best_max_views_seen")) and current_top_tweet:
        best_top_tweet = current_top_tweet

    row = {column: safe_text(existing.get(column)) for column in DISCOVERY_MASTER_COLUMNS}
    row.update(
        {
            "platform": "X",
            "username": safe_text(candidate.get("username")).lower(),
            "display_name": safe_text(enriched_row.get("display_name")) or safe_text(existing.get("display_name")) or safe_text(candidate.get("display_name")),
            "profile_url": safe_text(enriched_row.get("profile_url")) or safe_text(existing.get("profile_url")) or f"https://x.com/{safe_text(candidate.get('username')).lower()}",
            "first_seen_date": safe_text(existing.get("first_seen_date")) or run_date,
            "last_seen_date": run_date,
            "first_seen_batch": safe_text(existing.get("first_seen_batch")) or batch_name,
            "last_seen_batch": batch_name,
            "best_max_views_seen": str(best_views),
            "best_top_tweet_url": best_top_tweet,
            "latest_matched_queries": safe_text(candidate.get("matched_queries")),
            "times_seen_after_views_gate": str(_to_int(existing.get("times_seen_after_views_gate")) + 1),
            "master_status": "active",
        }
    )
    if enriched_row:
        row.update(
            {
                "last_layer2_provider": safe_text(enriched_row.get("enrichment_provider")),
                "last_followers_count": safe_text(enriched_row.get("followers_count")),
                "last_following_count": safe_text(enriched_row.get("following_count")),
                "last_statuses_count": safe_text(enriched_row.get("statuses_count")),
                "last_verified": safe_text(enriched_row.get("verified")),
                "last_blue_verified": safe_text(enriched_row.get("blue_verified")),
                "last_bio": safe_text(enriched_row.get("bio")),
                "last_location_raw": safe_text(enriched_row.get("location_raw")),
                "last_external_links": safe_text(enriched_row.get("external_links")),
                "last_contact_value": safe_text(enriched_row.get("contact_value")),
                "last_contact_note": safe_text(enriched_row.get("contact_note")),
                "last_enriched_at": run_date,
            }
        )
    return row


def persist_discovery_master(
    *,
    eligible_candidates: list[dict[str, Any]],
    fresh_enriched_rows: list[dict[str, Any]],
    reused_rows: list[dict[str, Any]],
    config: Layer1RunConfig,
    batch_name: str,
    master_path: Path | None = None,
) -> tuple[Path, Path | None]:
    resolved_path = master_path or discovery_master_path()
    if not config.discovery_master_enabled:
        return resolved_path, None
    master_by_username, resolved_path = load_discovery_master(resolved_path)
    fresh_by_username = {safe_text(row.get("username")).lower(): row for row in fresh_enriched_rows}
    reused_by_username = {safe_text(row.get("username")).lower(): row for row in reused_rows}

    for candidate in eligible_candidates:
        username = safe_text(candidate.get("username")).lower()
        if not username:
            continue
        enriched_row = fresh_by_username.get(username) or reused_by_username.get(username)
        master_by_username[username] = _master_row_for_candidate(
            candidate,
            existing=master_by_username.get(username),
            enriched_row=enriched_row,
            batch_name=batch_name,
            run_date=config.run_date,
        )

    ordered_rows = [
        {column: safe_text(row.get(column)) for column in DISCOVERY_MASTER_COLUMNS}
        for _, row in sorted(master_by_username.items(), key=lambda item: item[0])
    ]
    backup_path = backup_csv_if_exists(resolved_path, config.run_date)
    write_csv(resolved_path, ordered_rows)
    return resolved_path, backup_path
