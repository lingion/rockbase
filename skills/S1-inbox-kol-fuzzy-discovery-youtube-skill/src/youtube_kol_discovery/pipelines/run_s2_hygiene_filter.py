from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import unquote

from youtube_kol_discovery.io_utils import read_csv, safe_text, workbench_date_dir, write_csv, write_json


DEFAULT_BLOCKED_EMAIL_DOMAINS = {
    "amazon.com",
    "cal.com",
    "companyco.com",
    "skool.com",
    "sentry.io",
    "wixpress.com",
}

DEFAULT_SUSPECT_ORG_KEYWORDS = [
    "academy",
    "company",
    "finance",
    "highlights",
    "leaders",
    "media",
    "news",
    "podcast",
    "school",
    "show",
    "skills",
    "solutions",
    "training",
    "university",
]

IMAGE_SUFFIXES = {"avif", "gif", "jpeg", "jpg", "png", "svg", "webp"}
EMAIL_RE = re.compile(r"^[A-Z0-9][A-Z0-9._%+-]*@[A-Z0-9.-]+\.[A-Z]{2,}$", re.I)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Conservative S2 hygiene filter for YouTube outreach lists. Drops obvious org rows and dirty emails, audits softer org suspicions."
    )
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--run-date", required=True)
    parser.add_argument("--output-csv", default="")
    parser.add_argument("--reviewed-csv", default="")
    parser.add_argument("--audit-json", default="")
    parser.add_argument("--org-channel-id", action="append", default=[], help="Explicit channel_id values to drop.")
    parser.add_argument("--org-handle", action="append", default=[], help="Explicit public handles to drop.")
    parser.add_argument("--org-name", action="append", default=[], help="Explicit display names to drop.")
    parser.add_argument(
        "--remove-suspected-orgs",
        action="store_true",
        help="Also drop keyword-suspected org rows. Default is audit-only for suspected rows.",
    )
    return parser.parse_args()

def _clean_text(value: str) -> str:
    return safe_text(value).strip()


def _normalize_identity(value: str) -> str:
    text = _clean_text(value).lower()
    if text.startswith("@"):
        return text
    return f"@{text}" if text else ""


def _display_name(row: dict[str, str]) -> str:
    return _clean_text(row.get("display_name") or row.get("频道/作者名称"))


def _profile_url(row: dict[str, str]) -> str:
    return _clean_text(row.get("profile_url") or row.get("账号链接"))


def _channel_id(row: dict[str, str]) -> str:
    return _clean_text(row.get("channel_id") or row.get("creator_handle"))


def _public_handle(row: dict[str, str]) -> str:
    for key in ("scrapecreators_handle", "账号ID"):
        value = _clean_text(row.get(key))
        if value.startswith("@"):
            return value
    profile_url = _profile_url(row)
    match = re.search(r"youtube\.com/(@[^/?#]+)", profile_url, re.I)
    return match.group(1) if match else ""


def _pick_email(row: dict[str, str]) -> str:
    return _clean_text(row.get("email") or row.get("联系方式") or row.get("contact_value"))


def _sanitize_email(raw_email: str) -> tuple[str, str]:
    text = unquote(_clean_text(raw_email)).replace("mailto:", "").strip()
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


def _suspect_org_reason(row: dict[str, str]) -> str:
    text = " ".join(
        [
            _public_handle(row),
            _display_name(row),
            _clean_text(row.get("bio") or row.get("账号简介__平台抓取")),
            _clean_text(row.get("external_links") or row.get("外链__平台抓取")),
        ]
    ).lower()
    for keyword in DEFAULT_SUSPECT_ORG_KEYWORDS:
        if keyword in text:
            return f"suspect_keyword:{keyword}"
    return ""


def evaluate_row(
    row: dict[str, str],
    *,
    explicit_org_channel_ids: set[str],
    explicit_org_handles: set[str],
    explicit_org_names: set[str],
    remove_suspected_orgs: bool,
) -> dict[str, str]:
    reviewed = dict(row)
    display_name = _display_name(row)
    channel_id = _channel_id(row)
    public_handle = _public_handle(row)
    raw_email = _pick_email(row)
    clean_email, email_reason = _sanitize_email(raw_email)

    decision = "keep"
    reason = "kept: passes explicit org + dirty-email gates"
    email_qc_flag = reviewed.get("email_qc_flag") or "ok"

    if channel_id and channel_id in explicit_org_channel_ids:
        decision = "drop"
        reason = "dropped: explicit org channel_id"
    elif public_handle and _normalize_identity(public_handle) in explicit_org_handles:
        decision = "drop"
        reason = "dropped: explicit org handle"
    elif display_name and display_name.lower() in explicit_org_names:
        decision = "drop"
        reason = "dropped: explicit org display name"
    elif email_reason and email_reason != "empty_email":
        decision = "drop"
        reason = f"dropped: dirty contact ({email_reason})"
        email_qc_flag = "invalid"
    else:
        suspicion = _suspect_org_reason(row)
        if suspicion:
            if remove_suspected_orgs:
                decision = "drop"
                reason = f"dropped: {suspicion}"
            else:
                reason = f"kept_with_audit: {suspicion}"
        elif email_reason == "empty_email":
            reason = "kept_without_contact: missing email"
            email_qc_flag = "missing"

    reviewed["clean_email"] = clean_email
    reviewed["manual_clean_decision"] = decision
    reviewed["manual_clean_reason"] = reason
    reviewed["email_qc_flag"] = email_qc_flag

    if decision == "drop":
        reviewed["email_qc_flag"] = "invalid"
        reviewed["email"] = ""
        if "mail1" in reviewed:
            reviewed["mail1"] = ""
        if "联系方式" in reviewed:
            reviewed["联系方式"] = ""
    else:
        if "email" in reviewed:
            reviewed["email"] = clean_email
        if "mail1" in reviewed:
            reviewed["mail1"] = clean_email
        if "联系方式" in reviewed:
            reviewed["联系方式"] = clean_email

    return reviewed


def main() -> int:
    args = _parse_args()
    input_csv = Path(args.input_csv).expanduser().resolve()
    rows = read_csv(input_csv)

    workbench_root = workbench_date_dir(args.run_date)
    reviewed_csv = Path(args.reviewed_csv).expanduser().resolve() if args.reviewed_csv else workbench_root / f"{input_csv.stem}_manual_clean_reviewed.csv"
    output_csv = Path(args.output_csv).expanduser().resolve() if args.output_csv else workbench_root / f"{input_csv.stem}_manual_clean_final.csv"
    audit_json = Path(args.audit_json).expanduser().resolve() if args.audit_json else workbench_root / f"{input_csv.stem}_manual_clean_audit.json"

    explicit_org_channel_ids = {_clean_text(v) for v in args.org_channel_id if _clean_text(v)}
    explicit_org_handles = {_normalize_identity(v) for v in args.org_handle if _normalize_identity(v)}
    explicit_org_names = {_clean_text(v).lower() for v in args.org_name if _clean_text(v)}

    reviewed_rows: list[dict[str, str]] = []
    kept_rows: list[dict[str, str]] = []
    dropped_rows_detail: list[dict[str, str]] = []
    suspected_org_rows_detail: list[dict[str, str]] = []
    repaired_emails_detail: list[dict[str, str]] = []

    for row in rows:
        display_name = _display_name(row)
        channel_id = _channel_id(row)
        public_handle = _public_handle(row)
        raw_email = _pick_email(row)
        clean_email, _email_reason = _sanitize_email(raw_email)
        suspicion = _suspect_org_reason(row)

        reviewed = evaluate_row(
            row,
            explicit_org_channel_ids=explicit_org_channel_ids,
            explicit_org_handles=explicit_org_handles,
            explicit_org_names=explicit_org_names,
            remove_suspected_orgs=args.remove_suspected_orgs,
        )
        decision = reviewed["manual_clean_decision"]
        reason = reviewed["manual_clean_reason"]

        if suspicion:
            suspected_org_rows_detail.append(
                {
                    "channel_id": channel_id,
                    "public_handle": public_handle,
                    "display_name": display_name,
                    "email": clean_email,
                    "reason": suspicion,
                }
            )

        if raw_email and clean_email and raw_email != clean_email:
            repaired_emails_detail.append(
                {
                    "channel_id": channel_id,
                    "display_name": display_name,
                    "before": raw_email,
                    "after": clean_email,
                }
            )

        if decision == "drop":
            dropped_rows_detail.append(
                {
                    "channel_id": channel_id,
                    "public_handle": public_handle,
                    "display_name": display_name,
                    "email": raw_email,
                    "reason": reason,
                }
            )
        else:
            kept_rows.append(reviewed)

        reviewed_rows.append(reviewed)

    reviewed_fieldnames = list(reviewed_rows[0].keys()) if reviewed_rows else []
    kept_fieldnames = list(kept_rows[0].keys()) if kept_rows else reviewed_fieldnames
    write_csv(reviewed_csv, reviewed_rows, preferred_fields=reviewed_fieldnames)
    write_csv(output_csv, kept_rows, preferred_fields=kept_fieldnames)
    write_json(
        audit_json,
        {
            "input_csv": str(input_csv),
            "reviewed_csv": str(reviewed_csv),
            "output_csv": str(output_csv),
            "raw_rows": len(rows),
            "kept_rows": len(kept_rows),
            "dropped_rows": len(dropped_rows_detail),
            "suspected_org_rows": len(suspected_org_rows_detail),
            "repaired_email_rows": len(repaired_emails_detail),
            "remove_suspected_orgs": args.remove_suspected_orgs,
            "explicit_org_channel_ids": sorted(explicit_org_channel_ids),
            "explicit_org_handles": sorted(explicit_org_handles),
            "explicit_org_names": sorted(explicit_org_names),
            "dropped_rows_detail": dropped_rows_detail,
            "suspected_org_rows_detail": suspected_org_rows_detail,
            "repaired_emails_detail": repaired_emails_detail,
        },
    )
    print(
        json.dumps(
            {
                "reviewed_csv": str(reviewed_csv),
                "output_csv": str(output_csv),
                "audit_json": str(audit_json),
                "kept_rows": len(kept_rows),
                "dropped_rows": len(dropped_rows_detail),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
