from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from x_kol_discovery.config import Layer1RunConfig, SearchQuery


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("YAML spec requires PyYAML; use .json spec instead.") from exc
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"Spec must be a mapping object: {path}")
    return payload


def load_task_spec(spec_path: str) -> tuple[dict[str, Any], Path]:
    path = Path(spec_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Missing spec file: {path}")
    if path.suffix.lower() in {".yaml", ".yml"}:
        payload = _load_yaml(path)
    else:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"Spec must be a mapping object: {path}")
    return payload, path


def _first_language(spec: dict[str, Any]) -> str:
    values = spec.get("language_include") or []
    if isinstance(values, list) and values:
        return str(values[0]).strip().lower()
    return str(spec.get("language") or "en").strip().lower() or "en"


def _list_of_text(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return [str(item).strip() for item in values if str(item).strip()]


def _text_list_or_default(spec: dict[str, Any], key: str, default: list[str]) -> list[str]:
    values = _list_of_text(spec.get(key))
    return values if values else default


def task_spec_to_config(
    spec: dict[str, Any],
    *,
    run_date: str | None = None,
    shortlist_target: int | None = None,
) -> Layer1RunConfig:
    layer2 = spec.get("layer2") or {}
    layer3 = spec.get("layer3") or {}
    return Layer1RunConfig(
        task_name=str(spec.get("task_name") or "x_kol_task"),
        topic_query=str(spec.get("topic_query") or spec.get("topic") or ""),
        layer1_provider=str((spec.get("layer1") or {}).get("provider") or spec.get("layer1_provider") or "scweet"),
        since=str(spec.get("since") or "2026-03-01"),
        until=str(spec.get("until") or "2026-03-31"),
        shortlist_target=shortlist_target or int(spec.get("shortlist_target") or 100),
        min_followers_for_keep=int(
            spec.get("min_followers_for_keep")
            or layer3.get("min_followers_for_keep")
            or layer3.get("min_followers")
            or 1000
        ),
        layer3_min_followers=int(layer3.get("min_followers") or spec.get("layer3_min_followers") or 1000),
        layer2_min_max_views=int(layer2.get("min_max_views") or spec.get("layer2_min_max_views") or 5000),
        layer2_provider=str(layer2.get("provider") or spec.get("layer2_provider") or "scrapecreators_twitter_profile"),
        layer2_enrichment_chunk_size=int(
            layer2.get("chunk_size")
            or spec.get("layer2_enrichment_chunk_size")
            or 30
        ),
        discovery_master_enabled=bool(spec.get("discovery_master_enabled", True)),
        discovery_master_refresh_days=int(spec.get("discovery_master_refresh_days") or 7),
        query_registry_enabled=bool(spec.get("query_registry_enabled", True)),
        language=_first_language(spec),
        run_date=run_date or str(spec.get("run_date") or "2026-03-31"),
    )


def build_search_queries_from_spec(spec: dict[str, Any], *, query_variant: str = "default") -> list[SearchQuery]:
    explicit_queries = spec.get("search_queries") or []
    search_query_mode = str(spec.get("search_query_mode") or "prefer_explicit").strip().lower()
    should_use_explicit = search_query_mode != "prefer_generated"
    if should_use_explicit and isinstance(explicit_queries, list) and explicit_queries:
        built: list[SearchQuery] = []
        for idx, item in enumerate(explicit_queries, start=1):
            if isinstance(item, dict):
                query_text = str(item.get("query") or "").strip()
                query_name = str(item.get("name") or f"query_{idx}").strip() or f"query_{idx}"
                query_limit = int(item.get("limit") or spec.get("result_limit") or 90)
            else:
                query_text = str(item).strip()
                query_name = f"query_{idx}"
                query_limit = int(spec.get("result_limit") or 90)
            if query_text:
                built.append(SearchQuery(name=query_name, query=query_text, limit=query_limit))
        if built:
            return built

    topic = str(spec.get("topic_query") or spec.get("topic") or "").strip()
    if not topic:
        raise ValueError("Spec requires topic_query/topic or explicit search_queries.")

    quoted_topic = topic if topic.startswith('"') else f'"{topic}"'
    result_limit = int(spec.get("result_limit") or 90)
    exclude_keywords = _text_list_or_default(spec, "exclude_keywords", ["crypto", "trader", "airdrop"])
    role_keywords = _text_list_or_default(spec, "role_keywords", ["builder", "founder", "engineer", "researcher", "creator"])
    content_keywords = _text_list_or_default(spec, "content_keywords", ["tutorial", "demo", "review", "usecase", "walkthrough"])
    product_keywords = _text_list_or_default(spec, "product_keywords", ["startup", "SaaS", "product", "team", "launch"])
    workflow_keywords = _text_list_or_default(spec, "workflow_keywords", ["workflow", "productivity", "coding", "devtools", "build"])
    agentic_keywords = _text_list_or_default(spec, "agentic_keywords", ["agentic", "copilot", "copilots", "assistant", "assistants", "operators"])
    topic_keywords = _text_list_or_default(spec, "topic_keywords", ["AI", "AI agents", "automation", "developer tools"])
    stack_keywords = _text_list_or_default(spec, "stack_keywords", ["cursor", "claude", "gpt", "terminal", "ide"])
    shipping_keywords = _text_list_or_default(spec, "shipping_keywords", ["shipping", "shipped", "building", "maker", "stack"])
    discourse_keywords = _text_list_or_default(spec, "discourse_keywords", ["thoughts", "trying", "tested", "thread", "discussion"])

    negative_clause = " ".join(f"-{value}" for value in exclude_keywords if value)

    def clause(values: list[str]) -> str:
        return " OR ".join(values)

    if query_variant == "batch3_alt":
        return [
            SearchQuery(name="topic_stack", query=f"{quoted_topic} ({clause(stack_keywords)}) {negative_clause}".strip(), limit=result_limit),
            SearchQuery(name="topic_shipping", query=f"{quoted_topic} ({clause(shipping_keywords)}) {negative_clause}".strip(), limit=result_limit),
            SearchQuery(name="topic_discourse", query=f"{quoted_topic} ({clause(discourse_keywords)}) {negative_clause}".strip(), limit=result_limit),
        ]

    return [
        SearchQuery(name="topic_core", query=f"{quoted_topic} ({clause(topic_keywords)}) {negative_clause}".strip(), limit=result_limit),
        SearchQuery(name="topic_workflow", query=f"{quoted_topic} ({clause(workflow_keywords)}) {negative_clause}".strip(), limit=result_limit),
        SearchQuery(name="topic_roles", query=f"{quoted_topic} ({clause(role_keywords)}) {negative_clause}".strip(), limit=result_limit),
        SearchQuery(name="topic_content", query=f"{quoted_topic} ({clause(content_keywords)}) {negative_clause}".strip(), limit=result_limit),
        SearchQuery(name="topic_product", query=f"{quoted_topic} ({clause(product_keywords)}) {negative_clause}".strip(), limit=result_limit),
        SearchQuery(name="topic_agentic", query=f"{quoted_topic} ({clause(agentic_keywords)}) {negative_clause}".strip(), limit=result_limit),
    ]
