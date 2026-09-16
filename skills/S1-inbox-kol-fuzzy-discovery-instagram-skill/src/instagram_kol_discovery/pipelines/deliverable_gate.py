from __future__ import annotations

from dataclasses import dataclass

from instagram_kol_discovery.io_utils import safe_text


ORG_KEYWORDS = (
    " official",
    " agency",
    " studio",
    " media",
    " company",
    " brand",
    " store",
    " shop",
    " collective",
    " magazine",
    " news",
    " newsroom",
    " community",
    " foundation",
    " organization",
    " organisation",
    " team",
)

ORG_TOKENS = {
    "official",
    "agency",
    "studio",
    "media",
    "company",
    "brand",
    "store",
    "shop",
    "magazine",
    "news",
    "newsroom",
    "community",
    "foundation",
    "team",
}

PERSON_SIGNALS = (
    " i ",
    " my ",
    " me ",
    " founder",
    " creator",
    " coach",
    " consultant",
    " speaker",
    " author",
    " investor",
    " mom",
    " dad",
    " public figure",
    " host",
    " realtor",
    " agent",
    " entrepreneur",
    " educator",
    " teacher",
)


@dataclass(frozen=True)
class DeliverableGateDecision:
    allowed: bool
    reason: str


def _text_blob(row: dict[str, str]) -> str:
    handle = safe_text(row.get("creator_handle") or row.get("账号ID")).lower().lstrip("@")
    display_name = safe_text(row.get("display_name") or row.get("频道/作者名称")).lower()
    category_name = safe_text(row.get("category_name") or row.get("账号类目标签")).lower()
    bio = safe_text(row.get("bio") or row.get("账号简介__平台抓取")).lower()
    external_links = safe_text(row.get("external_links") or row.get("外链__平台抓取")).lower()
    return f" {handle} {display_name} {category_name} {bio} {external_links} "


def _has_person_signal(text: str) -> bool:
    return any(signal in text for signal in PERSON_SIGNALS)


def _org_keyword_reason(text: str) -> str:
    for keyword in ORG_KEYWORDS:
        if keyword in text:
            return f"blocked_org_keyword:{keyword.strip()}"
    for token in ORG_TOKENS:
        if text.strip().startswith(token + " "):
            return f"blocked_org_keyword:{token}"
    return ""


def deliverable_gate_decision(row: dict[str, str]) -> DeliverableGateDecision:
    recommended_action = safe_text(row.get("recommended_action") or row.get("Recommendation")).lower()
    if recommended_action and recommended_action not in {"keep", "review"}:
        return DeliverableGateDecision(False, f"blocked_recommended_action:{recommended_action}")

    text = _text_blob(row)

    if "official account" in text or "brand partnerships" in text or "managed by" in text:
        return DeliverableGateDecision(False, "blocked_explicit_org_phrase")

    org_reason = _org_keyword_reason(text)
    if org_reason and not _has_person_signal(text):
        return DeliverableGateDecision(False, org_reason)

    return DeliverableGateDecision(True, "allowed_creator")
