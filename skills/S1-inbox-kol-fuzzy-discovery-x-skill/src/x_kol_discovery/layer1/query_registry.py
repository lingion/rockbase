from __future__ import annotations

from hashlib import sha1
from pathlib import Path
from typing import Any

from x_kol_discovery.config import SearchQuery
from x_kol_discovery.io_utils import agency_list_master_dir, backup_csv_if_exists, read_csv, safe_text, write_csv


QUERY_REGISTRY_COLUMNS = [
    "run_date",
    "batch_name",
    "query_variant",
    "query_name",
    "query_text",
    "query_limit",
    "query_fingerprint",
    "status",
    "result_count",
]


def query_registry_path() -> Path:
    return agency_list_master_dir() / "x_kol_query_registry.csv"


def _fingerprint(*, run_date: str, query_variant: str, query: SearchQuery) -> str:
    payload = "|".join(
        [
            safe_text(run_date),
            safe_text(query_variant),
            safe_text(query.name),
            safe_text(query.query),
            str(query.limit),
        ]
    )
    return sha1(payload.encode("utf-8")).hexdigest()[:16]


def load_query_registry(path: Path | None = None) -> tuple[dict[str, dict[str, str]], Path]:
    target = path or query_registry_path()
    if not target.exists():
        return {}, target
    rows = read_csv(target)
    return {safe_text(row.get("query_fingerprint")): row for row in rows if safe_text(row.get("query_fingerprint"))}, target


def route_queries_with_registry(
    search_queries: list[SearchQuery],
    *,
    run_date: str,
    batch_name: str,
    query_variant: str,
    registry_path: Path | None = None,
    enabled: bool = True,
) -> tuple[list[SearchQuery], list[dict[str, str]], Path]:
    if not enabled:
        return search_queries, [], registry_path or query_registry_path()

    registry_by_fingerprint, resolved_path = load_query_registry(registry_path)
    to_run: list[SearchQuery] = []
    blocked: list[dict[str, str]] = []

    for query in search_queries:
        fingerprint = _fingerprint(run_date=run_date, query_variant=query_variant, query=query)
        existing = registry_by_fingerprint.get(fingerprint)
        if existing and safe_text(existing.get("run_date")) == run_date:
            blocked.append(
                {
                    "run_date": run_date,
                    "batch_name": batch_name,
                    "query_variant": query_variant,
                    "query_name": query.name,
                    "query_text": query.query,
                    "query_limit": str(query.limit),
                    "query_fingerprint": fingerprint,
                    "status": "blocked_same_day_duplicate",
                    "result_count": safe_text(existing.get("result_count")),
                }
            )
            continue
        to_run.append(query)

    return to_run, blocked, resolved_path


def persist_query_registry(
    *,
    executed_queries: list[SearchQuery],
    search_meta: list[dict[str, Any]],
    run_date: str,
    batch_name: str,
    query_variant: str,
    registry_path: Path | None = None,
    enabled: bool = True,
) -> tuple[Path, Path | None]:
    resolved_path = registry_path or query_registry_path()
    if not enabled:
        return resolved_path, None

    registry_by_fingerprint, resolved_path = load_query_registry(resolved_path)
    meta_by_name = {safe_text(item.get("query_name")): item for item in search_meta}

    for query in executed_queries:
        fingerprint = _fingerprint(run_date=run_date, query_variant=query_variant, query=query)
        run_meta = meta_by_name.get(query.name, {})
        registry_by_fingerprint[fingerprint] = {
            "run_date": run_date,
            "batch_name": batch_name,
            "query_variant": query_variant,
            "query_name": query.name,
            "query_text": query.query,
            "query_limit": str(query.limit),
            "query_fingerprint": fingerprint,
            "status": "executed",
            "result_count": str(run_meta.get("rows_count") or run_meta.get("result_count") or 0),
        }

    ordered_rows = [
        {column: safe_text(row.get(column)) for column in QUERY_REGISTRY_COLUMNS}
        for _, row in sorted(registry_by_fingerprint.items(), key=lambda item: (safe_text(item[1].get("run_date")), safe_text(item[1].get("query_name")), item[0]))
    ]
    backup_path = backup_csv_if_exists(resolved_path, run_date)
    write_csv(resolved_path, ordered_rows)
    return resolved_path, backup_path
