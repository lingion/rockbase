from __future__ import annotations

from pathlib import Path
from typing import Any

from instagram_kol_discovery.io_utils import read_csv, safe_text, skill_docs_dir, write_csv


DISCOVERY_MASTER_COLUMNS = [
    "platform",
    "creator_handle",
    "display_name",
    "profile_url",
    "first_seen_date",
    "last_seen_date",
    "first_seen_batch",
    "last_seen_batch",
    "best_max_views_seen",
    "best_top_content_url",
    "latest_matched_queries",
    "times_seen_after_views_gate",
    "last_layer2_provider",
    "last_followers_count",
    "last_following_count",
    "last_statuses_count",
    "last_verified",
    "last_bio",
    "last_external_links",
    "last_contact_signals",
    "last_contact_value",
    "last_contact_note",
    "last_enriched_at",
    "master_status",
]


def discovery_master_path() -> Path:
    return skill_docs_dir() / "instagram_kol_discovery_master.csv"


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
    mapping = {safe_text(row.get("creator_handle")).lower(): row for row in rows if safe_text(row.get("creator_handle"))}
    return mapping, target


def route_candidates_with_discovery_master(
    candidates: list[dict[str, Any]],
    *,
    batch_name: str,
    enabled: bool = True,
    master_path: Path | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], Path]:
    resolved_path = master_path or discovery_master_path()
    if not enabled:
        return candidates, [], [], resolved_path

    master_by_handle, resolved_path = load_discovery_master(resolved_path)
    to_enrich: list[dict[str, Any]] = []
    blocked_rows: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []

    for candidate in candidates:
        creator_handle = safe_text(candidate.get("creator_handle")).lower()
        if not creator_handle:
            continue
        master_row = master_by_handle.get(creator_handle)
        status = "new_candidate" if not master_row else "blocked_by_master"
        audit_rows.append(
            {
                "creator_handle": creator_handle,
                "display_name": safe_text(candidate.get("display_name")),
                "status": status,
                "reason": "not_in_master" if not master_row else "already_in_master",
                "batch_name": batch_name,
                "max_views": safe_text(candidate.get("max_views")),
                "top_content_url": safe_text(candidate.get("top_content_url")),
            }
        )
        if not master_row:
            to_enrich.append(candidate)
        else:
            blocked_rows.append(candidate)

    return to_enrich, blocked_rows, audit_rows, resolved_path


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
    current_top_content = safe_text(candidate.get("top_content_url"))
    best_top_content = safe_text(existing.get("best_top_content_url"))
    if _to_int(candidate.get("max_views")) >= _to_int(existing.get("best_max_views_seen")) and current_top_content:
        best_top_content = current_top_content

    row = {column: safe_text(existing.get(column)) for column in DISCOVERY_MASTER_COLUMNS}
    row.update(
        {
            "platform": "instagram",
            "creator_handle": safe_text(candidate.get("creator_handle")),
            "display_name": safe_text(enriched_row.get("display_name")) or safe_text(candidate.get("display_name")),
            "profile_url": safe_text(enriched_row.get("profile_url")) or f"https://www.instagram.com/{safe_text(candidate.get('creator_handle'))}/",
            "first_seen_date": safe_text(existing.get("first_seen_date")) or run_date,
            "last_seen_date": run_date,
            "first_seen_batch": safe_text(existing.get("first_seen_batch")) or batch_name,
            "last_seen_batch": batch_name,
            "best_max_views_seen": str(best_views),
            "best_top_content_url": best_top_content,
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
                "last_bio": safe_text(enriched_row.get("bio")),
                "last_external_links": safe_text(enriched_row.get("external_links")),
                "last_contact_signals": safe_text(enriched_row.get("contact_signals")),
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
    batch_name: str,
    run_date: str,
    enabled: bool = True,
    master_path: Path | None = None,
) -> Path:
    resolved_path = master_path or discovery_master_path()
    if not enabled:
        return resolved_path
    master_by_handle, resolved_path = load_discovery_master(resolved_path)
    fresh_by_handle = {safe_text(row.get("creator_handle")).lower(): row for row in fresh_enriched_rows}

    for candidate in eligible_candidates:
        creator_handle = safe_text(candidate.get("creator_handle")).lower()
        if not creator_handle:
            continue
        enriched_row = fresh_by_handle.get(creator_handle)
        if not enriched_row:
            continue
        master_by_handle[creator_handle] = _master_row_for_candidate(
            candidate,
            existing=master_by_handle.get(creator_handle),
            enriched_row=enriched_row,
            batch_name=batch_name,
            run_date=run_date,
        )

    ordered_rows = [
        {column: safe_text(row.get(column)) for column in DISCOVERY_MASTER_COLUMNS}
        for _, row in sorted(master_by_handle.items(), key=lambda item: item[0])
    ]
    write_csv(resolved_path, ordered_rows, preferred_fields=DISCOVERY_MASTER_COLUMNS)
    return resolved_path
