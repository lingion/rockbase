"""Stage-level contracts for semantic LLM output.

LLMs may suggest labels, relevance, and explanations. This module owns the
stable approval boundary: allow-lists, deterministic validation, bounded
payloads, versioned approvals, and the preview/apply distinction.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

MAX_ARTIFACT_ITEMS = 500
MAX_TEXT = 2_000
MIN_CONFIDENCE = 0.75

S1_FIELDS = frozenset({
    "row_key", "platform", "handle", "author_name", "url", "entity_type",
    "relevance", "confidence", "reason", "api_status", "candidate_status",
})
S4_LABEL_FIELDS = frozenset({
    "账号类目标签", "Tag_Section", "tag_topics", "tag_scenarios", "tag_audience",
    "tag_narrative", "tag_platform_fit", "tag_market", "tag_commercial",
    "tag_risk", "tag_confidence",
})
S4_EVIDENCE_FIELDS = frozenset({"source", "field", "quote", "url", "reason"})


def _text(value: Any, limit: int = MAX_TEXT) -> str:
    return str(value or "").strip()[:limit]


def _validation(validation: Mapping[str, Any] | None) -> dict[str, Any]:
    validation = validation if isinstance(validation, Mapping) else {}
    return {
        "ok": bool(validation.get("ok", False)),
        "errors": [_text(x, 256) for x in list(validation.get("errors") or [])[:100]],
        "warnings": [_text(x, 256) for x in list(validation.get("warnings") or [])[:100]],
    }


def _confidence(value: Any) -> float:
    try:
        return round(max(0.0, min(1.0, float(value))), 3)
    except (TypeError, ValueError):
        return 0.0


def _safe_key(row: Mapping[str, Any], index: int) -> str:
    for key in ("row_key", "账号ID", "id", "key", "handle"):
        value = _text(row.get(key), 128)
        if value:
            return value
    return f"row-{index}"


def build_candidate_artifact(rows: Sequence[Mapping[str, Any]], model_results: Sequence[Mapping[str, Any]], validation: Mapping[str, Any]) -> dict[str, Any]:
    """Create an S1 candidate artifact; model fields cannot alter API facts."""
    rows_by_key = {_safe_key(row, index): row for index, row in enumerate(rows) if isinstance(row, Mapping)}
    candidates: list[dict[str, Any]] = []
    warnings = list(_validation(validation)["warnings"])
    for index, result in enumerate(list(model_results or [])[:MAX_ARTIFACT_ITEMS]):
        if not isinstance(result, Mapping):
            warnings.append(f"invalid:model_result:{index}")
            continue
        key = _text(result.get("row_key") or result.get("账号ID") or result.get("handle"), 128)
        row = rows_by_key.get(key)
        if row is None:
            warnings.append(f"unknown:row_key:{key or index}")
            continue
        api_status = _text(row.get("api_status") or row.get("status") or result.get("api_status"), 64)
        platform = _text(row.get("platform") or row.get("平台") or result.get("platform"), 64)
        url = _text(row.get("url") or row.get("账号链接") or result.get("url"), 512)
        hard_errors: list[str] = []
        if not platform:
            hard_errors.append("missing:platform")
        if not url:
            hard_errors.append("missing:url")
        if api_status.lower() in {"failed", "error", "404", "api_failed", "request_error"}:
            hard_errors.append(f"api:{api_status}")
        item = {
            "row_key": key,
            "platform": platform,
            "handle": _text(row.get("handle") or row.get("账号ID") or result.get("handle"), 256),
            "author_name": _text(row.get("author_name") or row.get("频道/作者名称") or result.get("author_name"), 256),
            "url": url,
            "api_status": api_status,
            "entity_type": _text(result.get("entity_type"), 64),
            "relevance": _text(result.get("relevance"), 64),
            "confidence": _confidence(result.get("confidence")),
            "reason": _text(result.get("reason") or result.get("rationale")),
            "candidate_status": "manual_review" if hard_errors or _confidence(result.get("confidence")) < MIN_CONFIDENCE else "candidate",
            "constraints": hard_errors,
        }
        candidates.append({key: value for key, value in item.items() if key in S1_FIELDS or key == "constraints"})
    errors = _validation(validation)["errors"]
    ok = _validation(validation)["ok"] and not errors
    if not ok:
        pending = "manual_review"
    elif any(item["candidate_status"] == "manual_review" for item in candidates):
        pending = "manual_review"
    else:
        pending = "await_console_decision"
    return {
        "stage": "s1.candidates",
        "payload": {"candidates": candidates, "counts": {"input": len(rows), "candidates": len(candidates), "manual_review": sum(x["candidate_status"] == "manual_review" for x in candidates)}, "pending_action": pending},
        "validation": {**_validation(validation), "warnings": warnings},
    }


def build_enrichment_artifact(row_key: str, suggestions: Mapping[str, Any], evidence: Sequence[Mapping[str, Any]], validation: Mapping[str, Any]) -> dict[str, Any]:
    """Allow-list S4 labels and retain bounded evidence for review."""
    labels = {}
    for key in S4_LABEL_FIELDS:
        if key in suggestions:
            labels[key] = _text(suggestions[key])
    safe_evidence = []
    for item in list(evidence or [])[:100]:
        if not isinstance(item, Mapping):
            continue
        safe_evidence.append({key: _text(item.get(key)) for key in S4_EVIDENCE_FIELDS if item.get(key) is not None})
    valid = _validation(validation)
    confidence = _confidence(suggestions.get("tag_confidence"))
    if confidence < MIN_CONFIDENCE:
        valid["warnings"].append("low-confidence")
    pending = "await_console_decision" if valid["ok"] and confidence >= MIN_CONFIDENCE else "manual_review"
    return {"stage": "s4.enrichment", "payload": {"row_key": _text(row_key, 128), "suggestions": labels, "evidence": safe_evidence, "pending_action": pending}, "validation": valid}


def _artifact_digest(artifact_id: str, version: int) -> str:
    return hashlib.sha256(f"{artifact_id}:{version}".encode()).hexdigest()


def apply_approved_artifact(artifact_id: str, version: int, target: Mapping[str, Any], *, execute: bool = False) -> dict[str, Any]:
    """Apply only an explicitly approved, current artifact supplied by target.

    ``target`` is the persisted artifact/approval record. This function never
    treats a model payload as approval and never performs writes unless the
    caller explicitly sets ``execute=True``.
    """
    if not isinstance(target, Mapping):
        return {"ok": False, "status": "rejected", "reason": "missing-artifact"}
    if _text(target.get("artifact_id"), 128) != _text(artifact_id, 128):
        return {"ok": False, "status": "rejected", "reason": "artifact-id-mismatch"}
    try:
        stored_version = int(target.get("version"))
    except (TypeError, ValueError):
        stored_version = 0
    if stored_version != int(version):
        return {"ok": False, "status": "rejected", "reason": "stale-artifact"}
    if target.get("approved") is not True:
        return {"ok": False, "status": "rejected", "reason": "not-approved"}
    if not execute:
        return {"ok": True, "status": "preview", "artifact_id": artifact_id, "version": version, "writes": 0}
    return {"ok": True, "status": "applied", "artifact_id": artifact_id, "version": version, "writes": int(target.get("write_count", 0) or 0), "artifact_hash": target.get("content_hash") or _artifact_digest(artifact_id, version)}


__all__ = ["build_candidate_artifact", "build_enrichment_artifact", "apply_approved_artifact", "MIN_CONFIDENCE"]
