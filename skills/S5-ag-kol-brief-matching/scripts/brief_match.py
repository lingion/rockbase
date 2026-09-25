"""KOL brief → master-row semantic matching.

The LLM is consulted only to explain and rank rows that survived the
deterministic filter. The model is forbidden from injecting a row that
was excluded by hard exclusions; any model-suggested row outside the
candidate set is dropped, and any low-confidence result is forced into
manual_review.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping

# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


@dataclass
class MatchResult:
    row_key: str
    semantic_reason: str = ""
    confidence: float = 0.0
    constraints: str = ""
    manual_review: bool = False
    matched_keys: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "row_key": self.row_key,
            "semantic_reason": self.semantic_reason,
            "confidence": round(max(0.0, min(1.0, float(self.confidence))), 3),
            "constraints": self.constraints,
            "manual_review": bool(self.manual_review),
            "matched_keys": list(self.matched_keys),
        }


@dataclass
class _Requirement:
    axis: str
    value: str

    @classmethod
    def parse(cls, raw: str) -> "_Requirement | None":
        if not isinstance(raw, str) or ":" not in raw:
            return None
        axis, value = raw.split(":", 1)
        axis = axis.strip()
        value = value.strip()
        if not axis or not value:
            return None
        return cls(axis=axis, value=value)


# Axes the deterministic filter actually inspects. Anything else falls
# through to the soft-must-have bucket.
_HARD_PLATFORM_AXES = {
    "preferred_platform",
    "preferred_market",
}
_HARD_AVOID_AXES = {
    "must_avoid",
    "avoid",
    "exclude",
}
_TAG_AXES = {
    "tag_topics",
    "tag_scenarios",
    "tag_audience",
    "tag_platform_fit",
    "tag_market",
    "tag_risk",
    "tag_narrative",
}

_REVIEW_THRESHOLD = 0.75


# ---------------------------------------------------------------------------
# Brief parsing
# ---------------------------------------------------------------------------


def _parse_brief(brief: Mapping[str, Any]) -> tuple[list[_Requirement], list[_Requirement], list[_Requirement], list[_Requirement], list[_Requirement], str]:
    must_have: list[_Requirement] = []
    for raw in _as_list(brief.get("must_have")):
        req = _Requirement.parse(raw)
        if req is not None:
            must_have.append(req)
    should_have: list[_Requirement] = []
    for raw in _as_list(brief.get("should_have")):
        req = _Requirement.parse(raw)
        if req is not None:
            should_have.append(req)
    must_avoid: list[_Requirement] = []
    for raw in _as_list(brief.get("must_avoid")):
        req = _Requirement.parse(raw)
        if req is not None:
            must_avoid.append(req)
    preferred_platform: list[_Requirement] = []
    for raw in _as_list(brief.get("preferred_platform")):
        req = _Requirement.parse(raw)
        if req is not None:
            preferred_platform.append(req)
    preferred_market: list[_Requirement] = []
    for raw in _as_list(brief.get("preferred_market")):
        req = _Requirement.parse(raw)
        if req is not None:
            preferred_market.append(req)
    narrative = ""
    narr = brief.get("narrative_need")
    if isinstance(narr, str):
        narrative = narr.strip()
    return must_have, should_have, must_avoid, preferred_platform, preferred_market, narrative


def _as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return [value]
    return [value]


# ---------------------------------------------------------------------------
# Row identity + tag access
# ---------------------------------------------------------------------------


def _row_key(row: Mapping[str, Any], fallback: str) -> str:
    for key in ("row_key", "id", "key"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    handle = row.get("账号ID") or row.get("handle")
    if isinstance(handle, str) and handle.strip():
        return handle.strip()
    return fallback


def _row_tag_value(row: Mapping[str, Any], axis: str) -> str:
    if axis in row:
        return str(row.get(axis) or "")
    if axis in _TAG_AXES:
        return str(row.get(axis) or "")
    return ""


def _row_tags_blob(row: Mapping[str, Any]) -> str:
    parts: list[str] = []
    for axis in _TAG_AXES:
        value = _row_tag_value(row, axis)
        if value:
            parts.append(value)
    return " / ".join(parts)


# ---------------------------------------------------------------------------
# Deterministic filter
# ---------------------------------------------------------------------------


def _normalize_for_match(value: str) -> str:
    return value.strip().lower()


def _row_has_value(row: Mapping[str, Any], axis: str, needle: str) -> bool:
    needle_norm = _normalize_for_match(needle)
    if not needle_norm:
        return False
    candidates: list[str] = []
    if axis in _HARD_PLATFORM_AXES:
        # Maps preferred_platform/preferred_market onto the row's tag columns.
        if axis == "preferred_platform":
            candidates.append(_row_tag_value(row, "tag_platform_fit"))
            candidates.append(str(row.get("账号平台") or ""))
            candidates.append(str(row.get("platform") or ""))
        else:
            candidates.append(_row_tag_value(row, "tag_market"))
            candidates.append(str(row.get("账号地区") or ""))
            candidates.append(str(row.get("market") or ""))
    else:
        candidates.append(_row_tag_value(row, axis))
    blob = " / ".join(c for c in candidates if c)
    if not blob:
        return False
    return needle_norm in _normalize_for_match(blob)


def _row_avoid_violation(row: Mapping[str, Any], must_avoid: list[_Requirement]) -> bool:
    for req in must_avoid:
        if _row_has_value(row, req.axis, req.value):
            return True
        # ``must_avoid: risk:political`` matches the tag_risk column.
        if req.axis == "risk":
            if _normalize_for_match(req.value) in _normalize_for_match(_row_tag_value(row, "tag_risk")):
                return True
    return False


def _row_passed_hard_exclusions(row: Mapping[str, Any], must_avoid: list[_Requirement]) -> bool:
    if _row_avoid_violation(row, must_avoid):
        return False
    return True


# ---------------------------------------------------------------------------
# Scoring (deterministic, with optional LLM re-ranking)
# ---------------------------------------------------------------------------


def _deterministic_score(
    row: Mapping[str, Any],
    must_have: list[_Requirement],
    should_have: list[_Requirement],
    preferred_platform: list[_Requirement],
    preferred_market: list[_Requirement],
    narrative: str,
) -> tuple[float, list[str]]:
    matched: list[str] = []
    score = 0.0
    for req in must_have:
        if _row_has_value(row, req.axis, req.value):
            score += 3.0
            matched.append(f"must:{req.axis}={req.value}")
    for req in should_have:
        if _row_has_value(row, req.axis, req.value):
            score += 1.5
            matched.append(f"should:{req.axis}={req.value}")
    for req in preferred_platform:
        if _row_has_value(row, "preferred_platform", req.value):
            score += 1.0
            matched.append(f"platform={req.value}")
    for req in preferred_market:
        if _row_has_value(row, "preferred_market", req.value):
            score += 1.0
            matched.append(f"market={req.value}")
    if narrative:
        blob = _normalize_for_match(_row_tags_blob(row))
        if _normalize_for_match(narrative) in blob:
            score += 0.5
            matched.append(f"narrative={narrative}")
    # Normalize to [0,1]. 7 must-have hits would already be extreme; cap there.
    score = max(0.0, min(1.0, score / 7.0))
    return score, matched


def _rank_with_llm(
    candidates: list[MatchResult],
    brief: Mapping[str, Any],
    client: Any,
) -> list[MatchResult]:
    """Run the LLM re-rank. Drops any model row outside the deterministic set."""
    if not candidates:
        return []
    candidate_keys = {c.row_key for c in candidates}
    ranker = getattr(client, "rank", None)
    if not callable(ranker):
        return candidates
    try:
        model_results = ranker(candidates, brief) or []
    except Exception:
        # LLM failure: fall back to deterministic ordering, mark manual review.
        for c in candidates:
            c.manual_review = True
            c.semantic_reason = (c.semantic_reason + "; llm-error").strip("; ")
        return candidates
    safe: list[MatchResult] = []
    seen: set[str] = set()
    for item in model_results:
        if not isinstance(item, MatchResult):
            continue
        if item.row_key not in candidate_keys:
            # The model tried to inject a row outside the deterministic set.
            continue
        if item.row_key in seen:
            continue
        seen.add(item.row_key)
        safe.append(item)
    # Append any deterministic candidates the model omitted (deterministic
    # coverage must never be lost because the LLM is silent).
    for c in candidates:
        if c.row_key not in seen:
            safe.append(c)
    return safe


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------


def match_brief_to_master(
    brief: Mapping[str, Any],
    rows: Iterable[Mapping[str, Any]],
    client: Any = None,
) -> list[MatchResult]:
    """Return deterministic MatchResults; optionally re-ranked by ``client``.

    ``client.rank(candidates, brief)`` must return a list of ``MatchResult``.
    Rows the model references that are not in the deterministic candidate
    set are dropped; rows it omits are preserved from the deterministic set;
    rows with ``confidence < _REVIEW_THRESHOLD`` are forced to manual_review.
    """
    must_have, should_have, must_avoid, preferred_platform, preferred_market, narrative = _parse_brief(brief)
    results: list[MatchResult] = []
    for idx, row in enumerate(rows):
        if not isinstance(row, Mapping):
            continue
        if not _row_passed_hard_exclusions(row, must_avoid):
            continue
        score, matched = _deterministic_score(
            row,
            must_have,
            should_have,
            preferred_platform,
            preferred_market,
            narrative,
        )
        # Hard must-haves: if must_have lists exist, every item must hit
        # (else the row is excluded even if it scored on other axes).
        if must_have:
            all_hit = all(_row_has_value(row, req.axis, req.value) for req in must_have)
            if not all_hit:
                continue
        results.append(
            MatchResult(
                row_key=_row_key(row, fallback=f"row-{idx}"),
                semantic_reason="deterministic",
                confidence=score,
                constraints="must_have+should_have+avoid+narrative",
                manual_review=False,
                matched_keys=matched,
            )
        )

    if client is not None:
        results = _rank_with_llm(results, brief, client)

    for result in results:
        if result.confidence < _REVIEW_THRESHOLD:
            result.manual_review = True
    return results


__all__ = ["MatchResult", "match_brief_to_master"]