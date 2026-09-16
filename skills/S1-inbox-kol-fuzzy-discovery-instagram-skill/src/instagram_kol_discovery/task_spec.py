from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class SearchQuery:
    name: str
    query: str
    limit: int


@dataclass(slots=True)
class InstagramLayer1Config:
    run_date: str
    min_content_views_for_l2: int
    min_followers_for_l3: int
    default_limit: int


def load_task_spec(path_str: str) -> tuple[dict[str, Any], Path]:
    path = Path(path_str).expanduser().resolve()
    spec = json.loads(path.read_text(encoding="utf-8"))
    return spec, path


def task_spec_to_config(spec: dict[str, Any], *, run_date: str | None = None) -> InstagramLayer1Config:
    return InstagramLayer1Config(
        run_date=run_date or str(spec.get("run_date") or datetime.now().strftime("%Y-%m-%d")),
        min_content_views_for_l2=int(spec.get("min_content_views_for_l2") or 2000),
        min_followers_for_l3=int(spec.get("min_followers_for_l3") or 2000),
        default_limit=int(spec.get("limit_per_query") or 10),
    )


def build_search_queries_from_spec(spec: dict[str, Any]) -> list[SearchQuery]:
    queries: list[SearchQuery] = []
    raw_queries = spec.get("search_queries") or spec.get("queries") or []
    default_limit = int(spec.get("limit_per_query") or 10)

    for index, item in enumerate(raw_queries, start=1):
        if isinstance(item, str):
            query = item.strip()
            if query:
                queries.append(SearchQuery(name=f"q{index}", query=query, limit=default_limit))
            continue
        if isinstance(item, dict):
            query = str(item.get("query") or item.get("text") or "").strip()
            if not query:
                continue
            name = str(item.get("name") or f"q{index}").strip()
            limit = int(item.get("limit") or default_limit)
            queries.append(SearchQuery(name=name, query=query, limit=limit))
    return queries
