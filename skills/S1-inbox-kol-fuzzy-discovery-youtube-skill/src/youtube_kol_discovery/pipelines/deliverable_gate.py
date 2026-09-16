from __future__ import annotations

from dataclasses import dataclass

from youtube_kol_discovery.io_utils import safe_text


@dataclass(frozen=True)
class DeliverableGateDecision:
    allowed: bool
    reason: str


def _risk_flags(row: dict[str, str]) -> list[str]:
    raw = safe_text(row.get("account_risk_flags"))
    if not raw:
        return []
    return [part.strip() for part in raw.split("|") if part.strip()]


def deliverable_gate_decision(row: dict[str, str]) -> DeliverableGateDecision:
    final_decision = safe_text(row.get("final_decision")).lower()
    llm_entity_type = safe_text(row.get("llm_entity_type")).lower()
    llm_decision = safe_text(row.get("llm_decision")).lower()
    llm_review_status = safe_text(row.get("llm_review_status")).lower()

    if not llm_entity_type or not llm_decision:
        return DeliverableGateDecision(False, "blocked_llm_missing")
    if llm_decision == "drop":
        return DeliverableGateDecision(False, "blocked_llm_drop")
    if llm_review_status != "auto_resolved":
        return DeliverableGateDecision(False, "blocked_pending_llm_review")
    if final_decision != "keep":
        return DeliverableGateDecision(False, f"blocked_final_decision:{final_decision or 'missing'}")
    return DeliverableGateDecision(True, "allowed_keep")
