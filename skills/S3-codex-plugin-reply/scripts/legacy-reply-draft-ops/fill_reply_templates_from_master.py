#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd


TEMPLATE_BODIES = {
    "RQ1": """Hi,

Thank you for sharing your rates and the additional details.

We do see a strong fit with the types of AI / tech campaigns we are currently reviewing. For first-time collaborations, our clients usually begin with tighter test budgets before expanding into larger placements.

If there is any flexibility for an initial agency test, we would be glad to review:
- your best dedicated rate
- your best integration rate
- any first-collaboration or agency rate you may be open to

Once we complete this round of internal review, we will follow up with the most relevant creators for confirmed briefs.

Best regards,
Annabel
Rockbase Agency
""",
    "RQ2": """Hi,

Thank you, that is very helpful.

I’ve noted this on my side and will keep it in our current review.

If there’s a strong fit for the next round, I’ll follow up with the relevant campaign context and next step.

Best regards,
Annabel
Rockbase Agency
""",
    "RQ3": """Hi,

Thank you, that is very helpful.

I’ve noted this on my side and will keep it in our current review.

If there’s a strong fit for the next round, I’ll follow up with the relevant campaign context and next step.

Best regards,
Annabel
Rockbase Agency
""",
    "RI1": """Hi,

Thank you for your interest.

To help us assess fit internally, could you please share your current rates for:
- a dedicated video
- a sponsored integration
- any other format you would recommend for a first collaboration

Once we complete this round of evaluation, we will follow up with the most relevant creators for confirmed briefs.

Best regards,
Annabel
Rockbase Agency
""",
    "RI2": """Hi,

Thank you for sending the additional details. We’ve received them on our side.

To help us continue the review efficiently, could you also share your current rates for the formats you would recommend for a first collaboration, especially:
- dedicated video
- sponsored integration
- short-form placement, if applicable

Once we complete this review round, we will follow up with the best-fitting creators for confirmed opportunities.

Best regards,
Annabel
Rockbase Agency
""",
    "RI3": """Hi,

Thank you for your reply.

Budget can vary depending on format, deliverables, and campaign fit, so at this stage we are first mapping creator rates before locking final allocations.

If possible, please share your standard starting rates for:
- a dedicated video
- a sponsored integration
- short-form placement, if applicable

That will help us assess fit internally and decide whether to move forward with a more detailed brief.

Best regards,
Annabel
Rockbase Agency
""",
    "RI4": """Hi,

Thank you for your reply, and that makes complete sense.

For now, I’d prefer not to send over partial materials too early while we’re still narrowing campaigns internally. I think it would be more useful to come back to you once I have a clearer fit and more concrete context to share.

If useful for our internal review in the meantime, you’re also very welcome to share your current rates for the formats you’d usually recommend.

I really appreciate your time, and I hope we get the chance to pick this up again when the right brief comes through.

Best regards,
Annabel
Rockbase Agency
""",
}

TEMPLATE_NAMES = {
    "RQ1": "quoted_send_details",
    "RQ2": "quoted_accept_standard",
    "RQ3": "quoted_accept_discounted",
    "RI1": "interested_request_rate",
    "RI2": "interested_send_details_no_price",
    "RI3": "ask_budget_first",
    "RI4": "verification_or_brief_gate",
    "RX1": "no_reply_decline",
    "RX2": "manual_review_required",
}

PRICE_RE = re.compile(r"(?i)(?:US?\$|USD|EUR|€|£|GBP|\$)\s*\d|(?:\d{2,6}(?:[.,]\d{3})*\s*(?:US?\$|USD|EUR|€|£|GBP|\$|dollars?|d[oó]lares?|euros?|pounds?|ドル))")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fill Mail2/Mail3 template suggestions and bodies from replied master.")
    parser.add_argument("--source-csv", required=True)
    parser.add_argument("--review-csv", required=True)
    parser.add_argument("--summary-json", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args()


def clean_reply_text(text: str) -> str:
    text = (text or "").replace("\r", "\n")
    text = re.split(r"\n(?:On .+wrote:|>+|Em .*escreveu:|Il giorno .*ha scritto:)", text, maxsplit=1)[0]
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def short_text(text: str, limit: int = 260) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip())
    return text[: limit - 3] + "..." if len(text) > limit else text


def has_any(text: str, keywords: List[str]) -> bool:
    low = (text or "").lower()
    return any(keyword in low for keyword in keywords)


def normalize_pricing_excerpt(text: str) -> str:
    text = (text or "").strip()
    if not text or text.startswith("[No explicit pricing]"):
        return ""
    stripped = re.sub(r"\(Bundle Package\): -.*", "", text, flags=re.S).strip()
    if "dedicated - | integration -" in stripped:
        return ""
    return stripped


def has_usable_pricing(row: pd.Series, reply_text: str) -> bool:
    fields = [
        normalize_pricing_excerpt(str(row.get("Reply_Pricing_Excerpt", "") or "")),
        normalize_pricing_excerpt(str(row.get("Reply_Comprehensive_Pricing", "") or "")),
        str(row.get("Reply_Main_Dedicated_Rate", "") or "").strip(),
    ]
    if any(fields) or bool(PRICE_RE.search(reply_text or "")):
        return True
    low = (reply_text or "").lower()
    plain_numeric_quote = re.search(r"\b(?:charge|rate|price|cost|valor|cobramos?)\b[^\n]{0,40}\b(\d{3,6})\b", low)
    has_format_hint = any(token in low for token in ["dedicated", "integration", "video", "vídeo", "youtube", "short", "reel"])
    return bool(plain_numeric_quote and has_format_hint)


def infer_cohort(row: pd.Series) -> Tuple[str, str, str]:
    stage = str(row.get("Pipeline_Stage", "") or "").strip()
    if stage == "M1_3_Replied_Review" and str(row.get("Mail1_Reply", "") or "").strip():
        return "mail2", "Mail1_Reply", "Mail2"
    if stage == "M2_3_Replied_Review" and str(row.get("Mail2_Reply", "") or "").strip():
        return "mail3", "Mail2_Reply", "Mail3"
    return "", "", ""


def detect_intent(row: pd.Series, reply_text: str) -> Tuple[str, str]:
    text = reply_text.lower()
    pricing = has_usable_pricing(row, reply_text)
    has_details = has_any(
        text,
        ["media kit", "mediakit", "rate card", "ratecard", "attached", "attachment", "beacons.ai", "kit overview", "sponsorship menu", "drive.google.com"],
    )
    if has_any(
        text,
        [
            "not interested",
            "no thanks",
            "not a fit",
            "we'll pass",
            "i'll pass",
            "leave me alone",
            "don't promote",
            "do not promote",
            "cannot support",
            "can't support",
            "not accepting",
        ],
    ):
        return "RX1", "clear decline / no-fit wording"
    if has_any(
        text,
        [
            "what is your budget",
            "what's your budget",
            "within your budget",
            "share your budget",
            "could you share your budget",
            "what is your offer",
            "what's your offer",
            "share your offer",
            "budget for this collaboration",
            "budget for this campaign",
        ],
    ):
        return "RI3", "asks our budget / offer first"
    if has_any(
        text,
        [
            "campaign brief",
            "send the brief",
            "share the brief",
            "specific project briefs",
            "more details",
            "campaign details",
            "company details",
            "business registration",
            "tax number",
            "official company id",
            "official company email",
            "official rockbase agency email",
            "email me from your official",
            "official email",
            "email address",
            "correo oficial",
            "official brand",
            "email us with your agency's email",
            "verify",
            "verification",
            "what brand",
            "which brand",
        ],
    ):
        return ("RI4", "asks for brief / verification / company details before proceeding")
    if pricing and has_any(text, ["discount", "discounted", "special discount", "special rate", "test rate", "first collaboration", "introductory"]):
        return "RQ3", "quoted discounted / introductory rate"
    if pricing:
        return "RQ1", "usable pricing detected"
    if has_details:
        return "RI2", "details or media kit shared without stable pricing"
    if has_any(text, ["sounds good", "looks good", "works for me", "happy to move forward"]):
        return "RI1", "positive acknowledgement without pricing details"
    if has_any(text, ["interested", "happy to collaborate", "would love", "open to", "sounds great", "looking forward", "keen to"]):
        return "RI1", "positive interest without usable pricing"
    return "RX2", "insufficient structure to auto-map safely"


def build_template_value(code: str) -> str:
    return f"{code} | {TEMPLATE_NAMES[code]}"


def generate_body(code: str) -> str:
    return TEMPLATE_BODIES.get(code, "")


def can_write_fields(current_template: str, current_body: str) -> bool:
    current_template = (current_template or "").strip()
    current_body = (current_body or "").strip()
    if not current_template and not current_body:
        return True
    known_template_values = {build_template_value(code) for code in TEMPLATE_NAMES}
    known_bodies = {body.strip() for body in TEMPLATE_BODIES.values()}
    template_known = not current_template or current_template in known_template_values
    body_known = not current_body or current_body in known_bodies
    if current_template in known_template_values:
        return True
    return template_known and body_known


def main() -> None:
    args = parse_args()
    source_csv = Path(args.source_csv)
    df = pd.read_csv(source_csv, encoding="utf-8-sig", dtype=str).fillna("")

    review_rows: List[Dict[str, str]] = []
    applied = 0
    manual = 0
    skipped = 0

    for idx, row in df.iterrows():
        wave, source_field, target_prefix = infer_cohort(row)
        if not wave:
            continue
        template_field = f"{target_prefix}_Reply_Template"
        body_field = f"{target_prefix}_Body_Final"
        reply_text = clean_reply_text(str(row.get(source_field, "") or ""))
        if not reply_text:
            skipped += 1
            continue

        code, reason = detect_intent(row, reply_text)
        template_value = build_template_value(code)
        body_value = generate_body(code)
        auto_ready = "yes" if code not in {"RX1", "RX2"} else "no"
        if code == "RX2":
            manual += 1

        review_rows.append(
            {
                "row_index_1based": str(idx + 2),
                "账号ID": str(row.get("账号ID", "")),
                "频道/作者名称": str(row.get("频道/作者名称", "")),
                "Pipeline_Stage": str(row.get("Pipeline_Stage", "")),
                "Reply_Stage": str(row.get("Reply_Stage", "")),
                "target_wave": wave,
                "template_field": template_field,
                "body_field": body_field,
                "template_suggestion": template_value,
                "auto_ready": auto_ready,
                "reason": reason,
                "Reply_Pricing_Excerpt": str(row.get("Reply_Pricing_Excerpt", "")),
                "Reply_Comprehensive_Pricing": str(row.get("Reply_Comprehensive_Pricing", "")),
                "reply_preview": short_text(reply_text, limit=400),
            }
        )

        if not args.apply:
            continue
        if code in {"RX1", "RX2"}:
            continue
        if not str(row.get("Reply_Thread_ID", "")).strip() or not str(row.get("Reply_Last_Message_ID", "")).strip() or not str(row.get("Reply_Contact_Email", "")).strip():
            continue
        if not can_write_fields(str(row.get(template_field, "")), str(row.get(body_field, ""))):
            continue

        df.at[idx, template_field] = template_value
        df.at[idx, body_field] = body_value
        applied += 1

    review_df = pd.DataFrame(review_rows)
    review_df.to_csv(args.review_csv, index=False, encoding="utf-8-sig")

    df.to_csv(args.output_csv, index=False, encoding="utf-8-sig")

    summary = {
        "cohort_rows": len(review_rows),
        "applied_rows": applied,
        "manual_review_rows": manual,
        "skipped_rows": skipped,
        "review_csv": str(Path(args.review_csv).resolve()),
        "output_csv": str(Path(args.output_csv).resolve()),
        "apply": args.apply,
    }
    Path(args.summary_json).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
