from __future__ import annotations

import argparse
import re
from pathlib import Path

from tiktok_kol_discovery.io_utils import (
    TIKTOK_L2_FLEX_FIELDS,
    TIKTOK_L2_REQUIRED_FIELDS,
    read_csv,
    safe_text,
    workbench_dir,
    write_csv,
    write_json,
)


DEFAULT_BIG_FOLLOWERS_THRESHOLD = 300_000
DEFAULT_HUGE_FOLLOWERS_THRESHOLD = 1_000_000
DEFAULT_ORG_KEYWORDS = {
    "academy",
    "agency",
    "brand",
    "collective",
    "company",
    "ecom",
    "group",
    "media",
    "official",
    "shop",
    "solutions",
    "studio",
    "supplier",
    "team",
    "wholesale",
}
PERSON_BRAND_HINTS = {
    "agent",
    "broker",
    "coach",
    "consultant",
    "creator",
    "educator",
    "founder",
    "host",
    "investor",
    "realtor",
    "recruiter",
    "teacher",
}
FIT_KEYWORDS = {
    "ai",
    "audience",
    "build",
    "builder",
    "claude code",
    "content",
    "content creator",
    "creator",
    "design",
    "developer",
    "digital planner",
    "filmmaker",
    "marketing",
    "productivity",
    "research",
    "seo",
    "social media",
    "software",
    "tech",
    "ugc",
    "workflow",
    "youtube",
}
ANTI_FIT_KEYWORDS = {
    "beauty",
    "dance",
    "fashion",
    "frugal",
    "gamer",
    "golf",
    "humor",
    "lifestyle",
    "mom",
    "petite fashion",
}
DEFAULT_BLOCKED_EMAIL_DOMAINS = {
    "amazon.com",
    "cal.com",
    "companyco.com",
    "skool.com",
    "sentry.io",
    "wixpress.com",
}
IMAGE_SUFFIXES = {"avif", "gif", "jpeg", "jpg", "png", "svg", "webp"}
EMAIL_RE = re.compile(r"^[A-Z0-9][A-Z0-9._%+-]*@[A-Z0-9.-]+\.[A-Z]{2,}$", re.I)


def _to_int(value: str) -> int:
    try:
        return int(str(value or "0").replace(",", "").strip())
    except ValueError:
        return 0


def _to_float(value: str) -> float:
    try:
        return float(str(value or "0").replace(",", "").strip())
    except ValueError:
        return 0.0


def _org_keyword_hits(text: str) -> list[str]:
    lowered = text.lower()
    return sorted(keyword for keyword in DEFAULT_ORG_KEYWORDS if keyword in lowered)


def _person_brand_hits(text: str) -> list[str]:
    lowered = text.lower()
    return sorted(keyword for keyword in PERSON_BRAND_HINTS if keyword in lowered)


def _sanitize_email(raw_email: str) -> tuple[str, str]:
    text = safe_text(raw_email).replace("mailto:", "").strip()
    text = re.sub(r"^[^A-Za-z0-9]+", "", text)
    text = text.split("?", 1)[0].strip()
    if not text:
        return "", "empty_email"
    if not EMAIL_RE.fullmatch(text):
        return "", "invalid_format"
    domain = text.split("@", 1)[1].lower()
    suffix = domain.rsplit(".", 1)[-1]
    if suffix in IMAGE_SUFFIXES:
        return "", f"image_suffix_domain:{suffix}"
    if domain in DEFAULT_BLOCKED_EMAIL_DOMAINS or domain.endswith(".sentry.io"):
        return "", f"blocked_domain:{domain}"
    return text, ""


def _keyword_hits(text: str, keywords: set[str]) -> list[str]:
    lowered = text.lower()
    return sorted(keyword for keyword in keywords if keyword in lowered)


def _base_decision_from_row(row: dict[str, str], *, min_followers: int) -> tuple[str, str]:
    followers = _to_int(row.get("followers_count", ""))
    overall = _to_float(row.get("overall_score", ""))
    topic = _to_float(row.get("topic_match_score", ""))
    contactability = _to_float(row.get("contactability_score", ""))
    has_email = bool((row.get("contact_value") or "").strip())

    if followers >= min_followers and overall >= 60 and topic >= 50:
        return "keep", "L3 复核通过：粉丝、主题和活跃度均达标"
    if followers >= min_followers and overall >= 48:
        return "review", "L3 复核：粉丝达标，但综合分仍建议人工判断"
    if has_email and overall >= 50 and contactability >= 55:
        return "review", "L3 复核：已有联系方式，可保留观察"
    if followers <= 0:
        return "review", "L3 复核：粉丝缺失，需人工确认"
    return "drop", "L3 复核：未达到正式 shortlist 标准"


def _auto_resolve_review(
    *,
    base_action: str,
    min_followers: int,
    followers_count: int,
    org_hits: list[str],
    person_hits: list[str],
    email_reason: str,
) -> tuple[str, str, str]:
    if email_reason and email_reason != "empty_email":
        return "drop", "auto_resolved", f"auto_drop: dirty contact ({email_reason})"
    if followers_count >= DEFAULT_HUGE_FOLLOWERS_THRESHOLD and org_hits:
        return "drop", "auto_resolved", "auto_drop: huge account with org signals"
    if len(org_hits) >= 2 and not person_hits:
        return "drop", "auto_resolved", "auto_drop: multiple org signals without person evidence"
    if {"official", "company", "team"} & set(org_hits):
        if not person_hits:
            return "drop", "auto_resolved", "auto_drop: strong org signal without person evidence"
    if followers_count >= DEFAULT_BIG_FOLLOWERS_THRESHOLD and person_hits and base_action == "keep":
        return "keep", "auto_resolved", "auto_keep: big personal-brand creator still fits campaign"
    if base_action == "drop":
        return "drop", "auto_resolved", "auto_drop: inherited low-fit decision"
    if followers_count < min_followers:
        return "review", "auto_resolved", "auto_review: person-brand evidence found but follower gate not met"
    if person_hits and not org_hits and base_action == "keep":
        return "keep", "auto_resolved", "auto_keep: person-brand evidence outweighs ambiguity"
    return "review", "pending", "manual_review: unresolved org-or-size ambiguity"


def evaluate_l3_row(
    row: dict[str, str],
    *,
    min_followers: int,
    big_followers_threshold: int = DEFAULT_BIG_FOLLOWERS_THRESHOLD,
    huge_followers_threshold: int = DEFAULT_HUGE_FOLLOWERS_THRESHOLD,
) -> dict[str, str]:
    reviewed = dict(row)
    base_action, base_reason = _base_decision_from_row(row, min_followers=min_followers)
    followers_count = _to_int(row.get("followers_count", ""))
    text = " ".join(
        [
            safe_text(row.get("display_name")),
            safe_text(row.get("bio")),
            safe_text(row.get("external_links")),
            safe_text(row.get("contact_signals")),
        ]
    )
    org_hits = _org_keyword_hits(text)
    person_hits = _person_brand_hits(text)
    fit_hits = _keyword_hits(text, FIT_KEYWORDS)
    anti_fit_hits = _keyword_hits(text, ANTI_FIT_KEYWORDS)
    clean_email, email_reason = _sanitize_email(safe_text(row.get("contact_value")))
    overall_score = _to_float(row.get("overall_score", ""))
    topic_score = _to_float(row.get("topic_match_score", ""))

    risk_flags: list[str] = []
    if followers_count >= huge_followers_threshold:
        risk_flags.append("huge_account")
    elif followers_count >= big_followers_threshold:
        risk_flags.append("big_account")
    if org_hits:
        risk_flags.extend(f"org_keyword:{keyword}" for keyword in org_hits)
    if person_hits:
        risk_flags.extend(f"person_brand:{keyword}" for keyword in person_hits)
    if fit_hits:
        risk_flags.extend(f"fit_keyword:{keyword}" for keyword in fit_hits[:6])
    if anti_fit_hits:
        risk_flags.extend(f"anti_fit:{keyword}" for keyword in anti_fit_hits[:4])
    if email_reason and email_reason != "empty_email":
        risk_flags.append(f"dirty_contact:{email_reason}")
    if not clean_email:
        risk_flags.append("contact_missing")

    script_decision = base_action if base_action in {"keep", "review", "drop"} else "review"
    needs_llm_review = "no"
    llm_review_status = "not_needed"
    llm_decision = ""
    llm_confidence = ""
    llm_entity_type = ""
    decision_reason = base_reason

    if email_reason and email_reason != "empty_email":
        script_decision = "drop"
        decision_reason = f"script_drop: dirty contact ({email_reason})"
    elif "huge_account" in risk_flags or any(flag.startswith("org_keyword:") for flag in risk_flags):
        script_decision = "review"
        needs_llm_review = "yes"
        llm_review_status = "pending"
        decision_reason = "script_review: org-or-size ambiguity requires creator-type review"
    elif "big_account" in risk_flags and script_decision == "keep":
        script_decision = "review"
        needs_llm_review = "yes"
        llm_review_status = "pending"
        decision_reason = "script_review: oversized account requires creator-fit review"
    elif (
        script_decision == "review"
        and followers_count >= min_followers
        and not org_hits
        and "big_account" not in risk_flags
        and "huge_account" not in risk_flags
        and len(fit_hits) >= 2
        and not anti_fit_hits
        and (clean_email or overall_score >= 64 or topic_score >= 43)
    ):
        script_decision = "keep"
        decision_reason = "script_keep: niche-fit creator with strong workflow/content signals"
    elif (
        script_decision == "review"
        and followers_count >= min_followers
        and "big_account" in risk_flags
        and followers_count <= 350000
        and person_hits
        and len(fit_hits) >= 2
        and not org_hits
        and not anti_fit_hits
        and clean_email
        and overall_score >= 60
    ):
        script_decision = "keep"
        decision_reason = "script_keep: big but still creator-led and niche-relevant"

    final_decision = script_decision
    if needs_llm_review == "yes":
        final_decision, llm_review_status, decision_reason = _auto_resolve_review(
            base_action=base_action,
            min_followers=min_followers,
            followers_count=followers_count,
            org_hits=org_hits,
            person_hits=person_hits,
            email_reason=email_reason,
        )
        llm_decision = final_decision
        llm_confidence = "medium"
        if org_hits and not person_hits:
            llm_entity_type = "org_or_media"
        elif person_hits and org_hits:
            llm_entity_type = "personal_brand_with_org_signals"
        elif person_hits:
            llm_entity_type = "person_led_creator"
        else:
            llm_entity_type = "ambiguous"

    reviewed["clean_email"] = clean_email
    reviewed["account_risk_flags"] = " | ".join(risk_flags)
    reviewed["needs_llm_review"] = needs_llm_review
    reviewed["llm_review_status"] = llm_review_status
    reviewed["llm_entity_type"] = llm_entity_type
    reviewed["llm_confidence"] = llm_confidence
    reviewed["llm_decision"] = llm_decision
    reviewed["script_decision"] = script_decision
    reviewed["recommended_action"] = final_decision
    reviewed["final_decision"] = final_decision
    reviewed["decision_reason"] = decision_reason
    return reviewed


def main() -> None:
    parser = argparse.ArgumentParser(description="Run TikTok L3 selection from existing L2 CSV.")
    parser.add_argument("--input-csv", required=True, help="Path to TikTok L2 enriched CSV.")
    parser.add_argument("--output-dir", default="", help="Optional output directory override.")
    parser.add_argument("--run-date", default="", help="Run date for output naming.")
    parser.add_argument("--batch", default="batch1", help="Batch name.")
    parser.add_argument("--followers-gate", type=int, default=3000, help="Follower threshold for keep.")
    parser.add_argument("--big-followers-threshold", type=int, default=DEFAULT_BIG_FOLLOWERS_THRESHOLD)
    parser.add_argument("--huge-followers-threshold", type=int, default=DEFAULT_HUGE_FOLLOWERS_THRESHOLD)
    args = parser.parse_args()

    input_csv = Path(args.input_csv).expanduser().resolve()
    rows = read_csv(input_csv)
    run_date = args.run_date or input_csv.stem.rsplit("_", 1)[-1]
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else workbench_dir(run_date)
    output_dir.mkdir(parents=True, exist_ok=True)

    reviewed = [
        evaluate_l3_row(
            row,
            min_followers=args.followers_gate,
            big_followers_threshold=args.big_followers_threshold,
            huge_followers_threshold=args.huge_followers_threshold,
        )
        for row in rows
    ]

    reviewed.sort(key=lambda row: (-_to_int(row.get("followers_count", "")), -_to_int(row.get("max_views", ""))))
    shortlist = [row for row in reviewed if row.get("recommended_action") in {"keep", "review"}]

    batch_suffix = f"_{args.batch}_{run_date}" if args.batch else f"_{run_date}"
    reviewed_csv = output_dir / f"tiktok_kol_L3_reviewed{batch_suffix}.csv"
    shortlist_csv = output_dir / f"tiktok_kol_L3_shortlist{batch_suffix}.csv"
    runlog_json = output_dir / f"tiktok_kol_L3_runlog{batch_suffix}.json"

    preferred = (
        TIKTOK_L2_REQUIRED_FIELDS
        + TIKTOK_L2_FLEX_FIELDS
        + [
            "clean_email",
            "account_risk_flags",
            "needs_llm_review",
            "llm_review_status",
            "llm_entity_type",
            "llm_confidence",
            "llm_decision",
            "script_decision",
            "final_decision",
        ]
    )
    write_csv(reviewed_csv, reviewed, preferred_fields=preferred)
    write_csv(shortlist_csv, shortlist, preferred_fields=preferred)
    write_json(
        runlog_json,
        {
            "source_l2_csv": str(input_csv),
            "counts": {
                "input_rows": len(rows),
                "keep": sum(1 for row in reviewed if row.get("recommended_action") == "keep"),
                "review": sum(1 for row in reviewed if row.get("recommended_action") == "review"),
                "drop": sum(1 for row in reviewed if row.get("recommended_action") == "drop"),
                "shortlist": len(shortlist),
                "needs_llm_review_rows": sum(1 for row in reviewed if row.get("needs_llm_review") == "yes"),
            },
            "notes": [
                "L3 now gates obvious org/media signals and oversized accounts before S2.",
                "Rows with needs_llm_review=yes should receive a manual entity-type check before outreach.",
            ],
        },
    )
    print(shortlist_csv)


if __name__ == "__main__":
    main()
