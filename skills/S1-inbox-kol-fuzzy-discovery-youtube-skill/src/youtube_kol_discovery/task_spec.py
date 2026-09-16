from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from youtube_kol_discovery.config import Layer1RunConfig, SearchQuery


def load_task_spec(spec_path: str) -> tuple[dict[str, Any], Path]:
    path = Path(spec_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Missing spec file: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Spec must be an object: {path}")
    return payload, path


def task_spec_to_config(spec: dict[str, Any], *, run_date: str | None = None) -> Layer1RunConfig:
    country_values = spec.get("country_include") or ["US"]
    language_values = spec.get("language_include") or ["en"]
    return Layer1RunConfig(
        task_name=str(spec.get("task_name") or "youtube_kol_discovery"),
        platform=str(spec.get("platform") or "youtube"),
        topic_query=str(spec.get("topic_query") or ""),
        l1_mode=str(spec.get("l1_mode") or "dual_channel"),
        search_first=bool(spec.get("search_first", True)),
        enable_discover_supplement=bool(spec.get("enable_discover_supplement", False)),
        shortlist_target=int(spec.get("shortlist_target") or 50),
        min_content_views_for_l2=int(spec.get("min_content_views_for_l2") or 1000),
        language=str(language_values[0] if language_values else "en").strip().lower() or "en",
        country=str(country_values[0] if country_values else "US").strip().upper() or "US",
        run_date=run_date or str(spec.get("run_date") or "2026-04-10"),
        search_limit_per_query=int(spec.get("search_limit_per_query") or 20),
        discover_limit=int(spec.get("discover_limit") or 20),
    )


def build_search_queries_from_spec(spec: dict[str, Any]) -> list[SearchQuery]:
    explicit = spec.get("search_queries") or []
    queries: list[SearchQuery] = []
    if isinstance(explicit, list):
        for index, item in enumerate(explicit, start=1):
            if not isinstance(item, dict):
                continue
            query_text = str(item.get("query") or "").strip()
            if not query_text:
                continue
            queries.append(
                SearchQuery(
                    name=str(item.get("name") or f"query_{index}").strip() or f"query_{index}",
                    query=query_text,
                    limit=int(item.get("limit") or spec.get("search_limit_per_query") or 20),
                )
            )
    if queries:
        return queries

    topic = str(spec.get("topic_query") or "").strip()
    if not topic:
        raise ValueError("Spec requires topic_query or explicit search_queries.")
    limit = int(spec.get("search_limit_per_query") or 20)
    role_keywords = spec.get("role_keywords") or ["builder", "founder", "creator", "engineer"]
    content_keywords = spec.get("content_keywords") or ["tutorial", "explained", "course", "demo"]
    workflow_keywords = spec.get("workflow_keywords") or ["workflow", "automation", "use case", "tools"]
    build_keywords = spec.get("build_keywords") or ["build", "building", "stack", "agent"]

    def _norm(values: Any) -> list[str]:
        if not isinstance(values, list):
            return []
        return [str(item).strip() for item in values if str(item).strip()]

    role_keywords = _norm(role_keywords)
    content_keywords = _norm(content_keywords)
    workflow_keywords = _norm(workflow_keywords)
    build_keywords = _norm(build_keywords)

    result: list[SearchQuery] = []
    result.append(SearchQuery(name="topic_core", query=f"{topic} tutorial", limit=limit))
    for keyword in role_keywords:
        result.append(SearchQuery(name=f"role_{keyword.replace(' ', '_')}", query=f"{topic} {keyword}", limit=limit))
    for keyword in content_keywords:
        result.append(SearchQuery(name=f"content_{keyword.replace(' ', '_')}", query=f"{topic} {keyword}", limit=limit))
    for keyword in workflow_keywords:
        result.append(SearchQuery(name=f"workflow_{keyword.replace(' ', '_')}", query=f"{topic} {keyword}", limit=limit))
    for keyword in build_keywords:
        result.append(SearchQuery(name=f"build_{keyword.replace(' ', '_')}", query=f"{topic} {keyword}", limit=limit))
    return result
