from __future__ import annotations

import argparse
import re
from pathlib import Path

from youtube_kol_discovery.io_utils import (
    YOUTUBE_L2_FLEX_FIELDS,
    YOUTUBE_L2_REQUIRED_FIELDS,
    read_csv,
    safe_text,
    workbench_dir,
    write_csv,
    write_json,
)
from youtube_kol_discovery.pipelines.llm_entity_screen import screen_entity
from youtube_kol_discovery.pipelines.run_s2_hygiene_filter import _sanitize_email


DEFAULT_BIG_FOLLOWERS_THRESHOLD = 300_000
DEFAULT_HUGE_FOLLOWERS_THRESHOLD = 1_000_000
DEFAULT_ORG_KEYWORDS = {
    "academy",
    "agency",
    "capital",
    "collective",
    "company",
    "consultancy",
    "foundation",
    "fund",
    "group",
    "institute",
    "labs",
    "media",
    "network",
    "official",
    "podcast",
    "school",
    "solutions",
    "studio",
    "team",
    "ventures",
}
PERSON_BRAND_HINTS = {
    "creator",
    "founder",
    "host",
    "investor",
    "recruiter",
    "realtor",
    "teacher",
}


def build_candidate_artifact(rows, model_results, validation):
    """Adapter to the shared S1 candidate contract.

    Deterministic script decisions + LLM screen results are already in the
    reviewed rows; this packages the surviving candidate set as an approval
    artifact for the Console. LLM output cannot alter API facts or platform
    identity here — those stay with the deterministic columns.
    """
    try:
        from rockbase.llm_stage_contracts import build_candidate_artifact as _build
    except ImportError:  # pragma: no cover - standalone CLI path
        import sys as _sys
        _root = Path(__file__).resolve().parents[5]
        if str(_root) not in _sys.path:
            _sys.path.insert(0, str(_root))
        from rockbase.llm_stage_contracts import build_candidate_artifact as _build
    return _build(rows, model_results, validation)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run YouTube Layer3 review with script gate + LLM-review flags.")
    parser.add_argument("--input-csv", required=True, help="Path to youtube_kol_L2_enriched_*.csv")
    parser.add_argument("--output-dir", default="", help="Optional output directory override.")
    parser.add_argument("--run-date", default="", help="Optional run date override.")
    parser.add_argument("--batch", default="batch_from_l2", help="Batch label in output file names.")
    parser.add_argument("--big-followers-threshold", type=int, default=DEFAULT_BIG_FOLLOWERS_THRESHOLD)
    parser.add_argument("--huge-followers-threshold", type=int, default=DEFAULT_HUGE_FOLLOWERS_THRESHOLD)
    return parser.parse_args()


def _to_int(value: str | int | None) -> int:
    text = re.sub(r"[^0-9]", "", str(value or ""))
    return int(text) if text else 0


def _org_keyword_hits(text: str) -> list[str]:
    lowered = text.lower()
    return sorted(keyword for keyword in DEFAULT_ORG_KEYWORDS if keyword in lowered)


def _person_brand_hits(text: str) -> list[str]:
    lowered = text.lower()
    return sorted(keyword for keyword in PERSON_BRAND_HINTS if keyword in lowered)


def _decision_source(row: dict[str, str]) -> str:
    return safe_text(row.get("recommended_action")) or "review"


def evaluate_l3_row(
    row: dict[str, str],
    *,
    big_followers_threshold: int = DEFAULT_BIG_FOLLOWERS_THRESHOLD,
    huge_followers_threshold: int = DEFAULT_HUGE_FOLLOWERS_THRESHOLD,
) -> dict[str, str]:
    reviewed = dict(row)
    followers_count = _to_int(row.get("followers_count"))
    base_action = _decision_source(row)
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
    clean_email, email_reason = _sanitize_email(
        safe_text(row.get("contact_value") or row.get("联系方式") or row.get("email"))
    )

    risk_flags: list[str] = []
    if followers_count >= huge_followers_threshold:
        risk_flags.append("huge_account")
    elif followers_count >= big_followers_threshold:
        risk_flags.append("big_account")
    if org_hits:
        risk_flags.extend(f"org_keyword:{keyword}" for keyword in org_hits)
    if person_hits:
        risk_flags.extend(f"person_brand:{keyword}" for keyword in person_hits)
    if email_reason and email_reason != "empty_email":
        risk_flags.append(f"dirty_contact:{email_reason}")
    if not clean_email:
        risk_flags.append("contact_missing")

    script_decision = base_action if base_action in {"keep", "review", "drop"} else "review"
    if email_reason and email_reason != "empty_email":
        script_decision = "drop"
        reviewed["decision_reason"] = f"script_drop: dirty contact ({email_reason})"
    else:
        reviewed["decision_reason"] = reviewed.get("decision_reason") or f"script_{script_decision}"

    llm_screen = screen_entity(reviewed)
    llm_decision = llm_screen["llm_decision"]
    llm_confidence = llm_screen["llm_confidence"]
    llm_entity_type = llm_screen["llm_entity_type"]
    llm_rationale = llm_screen["llm_rationale"]
    llm_review_status = llm_screen["llm_review_status"]
    needs_llm_review = llm_screen["needs_llm_review"]
    final_decision = llm_decision
    if email_reason and email_reason != "empty_email":
        final_decision = "drop"
        reviewed["decision_reason"] = f"script_drop: dirty contact ({email_reason})"
    else:
        reviewed["decision_reason"] = llm_rationale

    reviewed["clean_email"] = clean_email
    reviewed["account_risk_flags"] = " | ".join(risk_flags)
    reviewed["needs_llm_review"] = needs_llm_review
    reviewed["llm_review_status"] = llm_review_status
    reviewed["llm_entity_type"] = llm_entity_type
    reviewed["llm_confidence"] = llm_confidence
    reviewed["llm_decision"] = llm_decision
    reviewed["script_decision"] = script_decision
    reviewed["final_decision"] = final_decision
    return reviewed


def main() -> int:
    args = _parse_args()
    input_csv = Path(args.input_csv).expanduser().resolve()
    rows = read_csv(input_csv)
    run_date = args.run_date or input_csv.stem.rsplit("_", 1)[-1]
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else workbench_dir(run_date)
    output_dir.mkdir(parents=True, exist_ok=True)

    reviewed_rows = [
        evaluate_l3_row(
            row,
            big_followers_threshold=args.big_followers_threshold,
            huge_followers_threshold=args.huge_followers_threshold,
        )
        for row in rows
    ]
    shortlist_rows = [row for row in reviewed_rows if row.get("final_decision") == "keep"]

    suffix = f"_{args.batch}_{run_date}" if args.batch else f"_{run_date}"
    reviewed_csv = output_dir / f"youtube_kol_L3_reviewed{suffix}.csv"
    shortlist_csv = output_dir / f"youtube_kol_L3_shortlist{suffix}.csv"
    runlog_json = output_dir / f"youtube_kol_L3_runlog{suffix}.json"

    preferred = (
        YOUTUBE_L2_REQUIRED_FIELDS
        + YOUTUBE_L2_FLEX_FIELDS
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
    write_csv(reviewed_csv, reviewed_rows, preferred_fields=preferred)
    write_csv(shortlist_csv, shortlist_rows, preferred_fields=preferred)
    write_json(
        runlog_json,
        {
            "source_l2_csv": str(input_csv),
            "counts": {
                "input_rows": len(rows),
                "shortlist_rows": len(shortlist_rows),
                "needs_llm_review_rows": sum(1 for row in reviewed_rows if row.get("needs_llm_review") == "yes"),
                "drop_rows": sum(1 for row in reviewed_rows if row.get("final_decision") == "drop"),
            },
            "notes": [
                "L3 now uses LLM entity screening as the final keep/drop decision.",
                "Rows with final_decision=drop do not enter S2.",
            ],
        },
    )
    print(shortlist_csv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
