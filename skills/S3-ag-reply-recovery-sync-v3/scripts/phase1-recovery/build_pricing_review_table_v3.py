#!/usr/bin/env python3
import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from translation_utils import english_for_logic, table_safe_text


PRICE_RE = re.compile(
    r"(?i)(?:"
    r"(US?\$|USD|EUR|€|£|GBP|\$)\s*(\d{1,3}(?:[.,\d]{0,12})?)"
    r"|"
    r"(\d{1,3}(?:[.,\d]{0,12})?)\s*(US?\$|USD|EUR|€|£|GBP|\$|dollars?|d[oó]lares?|euros?)"
    r")"
)
PLATFORM_ORDER = ["YT", "YT-short", "TT", "INS", "X"]
TEMPLATE_NAME_MAP = {
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build compact pricing review table v3.")
    parser.add_argument("--messages-csv", required=True)
    parser.add_argument("--attachments-report-csv", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--output-json", required=True)
    return parser.parse_args()


def read_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_rows(path: Path, rows: Iterable[Dict[str, str]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def clean_text(text: str) -> str:
    text = (text or "").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def short_text(text: str, limit: int = 500) -> str:
    text = re.sub(r"\s+", " ", clean_text(text))
    return text[: limit - 3] + "..." if len(text) > limit else text


def split_lines(text: str) -> List[str]:
    text = clean_text(text)
    lines = []
    for raw in re.split(r"[\n•]+", text):
        line = re.sub(r"\s+", " ", raw).strip(" -\t")
        if line:
            lines.append(line)
    return lines


def currency_symbol(token: str) -> str:
    token = token.upper().replace(" ", "")
    if token in {"EUR", "EURO", "EUROS"} or "€" in token:
        return "€"
    if "£" in token or "GBP" in token:
        return "£"
    return "$"


def normalize_amount_token(raw_amount: str) -> str:
    text = (raw_amount or "").strip().replace(" ", "")
    if not text:
        return ""
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "." in text:
        parts = text.split(".")
        if len(parts) > 1 and all(part.isdigit() for part in parts):
            if all(len(part) == 3 for part in parts[1:]):
                text = "".join(parts)
    elif "," in text:
        parts = text.split(",")
        if len(parts) > 1 and all(part.isdigit() for part in parts):
            if all(len(part) == 3 for part in parts[1:]):
                text = "".join(parts)

    if "." in text:
        number = float(text)
        if number.is_integer():
            return f"{int(number):,}"
        return f"{number:,.2f}".rstrip("0").rstrip(".")
    try:
        return f"{int(text):,}"
    except ValueError:
        return text


def canonicalize_price_mentions_in_text(text: str) -> str:
    def repl(match: re.Match) -> str:
        if match.group(1) and match.group(2):
            token = match.group(1)
            amount = match.group(2)
        else:
            token = match.group(4)
            amount = match.group(3)
        return f"{currency_symbol(token)}{normalize_amount_token(amount)}"

    return PRICE_RE.sub(repl, text or "")


def normalize_platforms(line: str) -> List[str]:
    low = f" {line.lower()} "
    found = []
    if any(k in low for k in ["short", "shorts", "reel", "reels", "vídeo curto", "video curto", "short form", "socials"]):
        found.append("YT-short")
    if any(k in low for k in ["youtube", "yt", "video", "vídeo", "vidéo", "channel", "interview"]) and "YT-short" not in found:
        found.append("YT")
    if "tiktok" in low or " tt " in low:
        found.append("TT")
    if any(k in low for k in ["instagram", "insta", "ig", "reel", "reels"]):
        found.append("INS")
    if any(k in low for k in ["twitter", "x.com", " tweet", " x "]):
        found.append("X")
    return found or ["YT"]


def detect_kind(line: str) -> str:
    low = line.lower()
    if any(k in low for k in ["integration", "integrated", "segment", "mid-roll", "mid roll"]):
        return "integration"
    if any(
        k in low
        for k in [
            "dedicated",
            "dedicado",
            "review",
            "promotional video",
            "sponsored unboxing",
            "interview",
            "full-length sponsored video",
            "vídeo dedicado",
            "video dedicado",
            "dedicated video",
            "dedicated short",
            "dedicated long",
            "long video",
            "vídeo longo",
            "video longo",
            "short video",
            "reel",
            "youtube shorts",
            "standalone",
        ]
    ):
        return "dedicated"
    if any(k in low for k in ["package", "bundle", "p1", "p2", "p3", "combo"]):
        return "other"
    if any(k in low for k in ["youtube", "tiktok", "instagram", "short", "video", "vídeo", "vidéo", "reel"]):
        return "dedicated"
    return "other"


def is_bundle(line: str) -> bool:
    low = line.lower()
    return any(k in low for k in ["bundle", "package", "buy 2", "3x", "month", "all monthly content"])


def has_channel_and_price(line: str) -> bool:
    low = line.lower()
    has_price = bool(PRICE_RE.search(line))
    has_channel = any(
        token in low
        for token in [
            "youtube",
            "yt",
            "tiktok",
            "instagram",
            "ig",
            "twitter",
            "x ",
            "x.com",
            "video",
            "integration",
            "dedicated",
            "reel",
            "short",
            "story",
            "post",
            "bundle",
            "package",
            "cross-post",
            "cross post",
        ]
    )
    return has_price and has_channel


def extract_priced_lines(text: str) -> List[Dict[str, str]]:
    items = []
    for line in split_lines(text):
        if not has_channel_and_price(line):
            continue
        matches = list(PRICE_RE.finditer(line))
        if not matches:
            continue
        prices = []
        for match in matches:
            if match.group(1) and match.group(2):
                token = match.group(1)
                amount = match.group(2)
            else:
                token = match.group(4)
                amount = match.group(3)
            prices.append(f"{currency_symbol(token)}{normalize_amount_token(amount)}")
        items.append(
            {
                "line": line,
                "prices": prices,
                "platforms": normalize_platforms(line),
                "kind": detect_kind(line),
                "bundle": is_bundle(line),
            }
        )
    return items


def aggregate_attachments(rows: List[Dict[str, str]]) -> Dict[str, List[Dict[str, str]]]:
    grouped: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row.get("message_id", "")].append(row)
    return grouped


def infer_main_platform(platform_value: str) -> str:
    low = (platform_value or "").lower()
    if "youtube" in low:
        return "YT"
    if "tiktok" in low:
        return "TT"
    if "instagram" in low:
        return "INS"
    if low in {"x", "twitter"} or "x/" in low:
        return "X"
    return "YT"


def build_matrix(items: List[Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    matrix = {p: {"dedicated": "-", "integration": "-"} for p in PLATFORM_ORDER}
    for item in items:
        if item["kind"] not in {"dedicated", "integration"}:
            continue
        if not item["prices"]:
            continue
        value = item["prices"][0]
        for platform in item["platforms"]:
            if platform in matrix and matrix[platform][item["kind"]] == "-":
                matrix[platform][item["kind"]] = value
    return matrix


def main_rate_for_platform(matrix: Dict[str, Dict[str, str]], main_platform: str) -> str:
    return matrix.get(main_platform, {}).get("dedicated", "-")


def attachment_excerpt(attachments: List[Dict[str, str]]) -> str:
    parts = []
    for attachment in attachments:
        text_file = attachment.get("text_file", "")
        if not text_file or not Path(text_file).exists():
            continue
        text = english_for_logic(Path(text_file).read_text(encoding="utf-8", errors="replace"))
        for item in extract_priced_lines(text)[:8]:
            parts.append(item["line"])
    return "\n".join(parts[:16])


def fallback_reply_excerpt(body_text: str) -> str:
    text = clean_text(body_text)
    if not text:
        return ""
    lines = []
    for raw in text.splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if not line:
            continue
        if line.startswith(">") or line.lower().startswith(("on ", "le ", "em ", "vào ", "于")):
            continue
        lines.append(line)
        if len(" ".join(lines)) >= 220:
            break
    excerpt = short_text(" ".join(lines), limit=220)
    return excerpt if excerpt and has_channel_and_price(excerpt) else ""


def format_price(token: str) -> str:
    token = token.replace("US$", "$").strip()
    match = re.match(r"^([€£$])(.+)$", token)
    if not match:
        return token
    symbol, amount = match.groups()
    return f"{symbol}{normalize_amount_token(amount)}"


def render_structured_pricing(items: List[Dict[str, str]]) -> str:
    bucket: Dict[str, List[str]] = defaultdict(list)
    for item in items:
        if not item["prices"]:
            continue
        raw_price = format_price(item["prices"][0])
        line = item["line"]
        low = line.lower()
        platforms = item["platforms"]
        kind = item["kind"]
        bundle = item["bundle"]

        if bundle or len(platforms) > 1:
            bucket["Bundle Package"].append(short_text(canonicalize_price_mentions_in_text(line), limit=180))
            continue

        platform = platforms[0]
        if platform == "YT-short":
            bucket["YouTube Shorts"].append(f"dedicated {raw_price}")
            continue

        if platform == "YT":
            if kind == "dedicated":
                bucket["YouTube"].append(f"dedicated {raw_price}")
            elif kind == "integration":
                bucket["YouTube"].append(f"integration {raw_price}")
            continue

        if platform == "TT":
            if kind in {"dedicated", "other"} or "video" in low or "post" in low or "short" in low:
                bucket["TikTok"].append(f"dedicated {raw_price}")
            elif kind == "integration":
                bucket["TikTok"].append(f"integration {raw_price}")
            continue

        if platform == "INS":
            if "story" in low:
                bucket["Instagram"].append(f"story {raw_price}")
            elif "post" in low or "carousel" in low:
                bucket["Instagram"].append(f"post {raw_price}")
            elif kind == "integration":
                bucket["Instagram"].append(f"integration {raw_price}")
            else:
                bucket["Instagram"].append(f"dedicated {raw_price}")
            continue

        if platform == "X":
            if kind == "integration":
                bucket["X / Twitter"].append(f"integration {raw_price}")
            else:
                bucket["X / Twitter"].append(f"dedicated {raw_price}")

    lines = []
    for label in ["Bundle Package", "YouTube", "YouTube Shorts", "TikTok", "Instagram", "X / Twitter"]:
        values = bucket.get(label, [])
        values = list(dict.fromkeys(values))
        if not values:
            continue
        lines.append(f"{label}: {' | '.join(values)}")
    return "\n".join(lines)


def attachment_pricing_evidence(attachments: List[Dict[str, str]]) -> str:
    parts = []
    for attachment in attachments:
        text_file = attachment.get("text_file", "")
        if not text_file or not Path(text_file).exists():
            continue
        text = english_for_logic(Path(text_file).read_text(encoding="utf-8", errors="replace"))
        for item in extract_priced_lines(text)[:8]:
            parts.append(f"{attachment.get('filename', '')}: {item['line']}")
    deduped = list(dict.fromkeys(parts))
    return "\n".join(deduped[:16])


def has_any(text: str, keywords: List[str]) -> bool:
    low = (text or "").lower()
    return any(keyword in low for keyword in keywords)


def detect_reply_intent(body_text: str, attachments: List[Dict[str, str]], all_items: List[Dict[str, str]], attachment_evidence: str) -> str:
    low = (body_text or "").lower()
    if has_any(
        low,
        [
            "not interested",
            "no interested",
            "no thanks",
            "not a fit",
            "not the right fit",
            "we'll pass",
            "i'll pass",
            "cannot take this on",
            "can't take this on",
            "not accepting sponsored",
            "not taking sponsorship",
            "not doing sponsorships",
        ],
    ):
        return "decline"
    if all_items:
        return "quoted_discounted" if has_any(low, ["discount", "discounted", "introductory", "special rate", "first collaboration rate", "first collab rate"]) else "quoted"
    if has_any(low, ["budget", "offer", "what's your budget", "what is your budget", "your rate range"]):
        return "ask_budget_first"
    if has_any(
        low,
        [
            "send me more details",
            "send more details",
            "share the brief",
            "send the brief",
            "campaign details",
            "more information",
            "verify",
            "verification",
            "what brand",
            "which brand",
            "what is the brand",
        ],
    ):
        return "brief_gate"
    if attachment_evidence or attachments:
        return "details_no_price"
    if has_any(
        low,
        [
            "interested",
            "happy to collaborate",
            "would love to",
            "keen to",
            "sounds great",
            "open to",
            "let me know",
            "would be happy",
            "happy to discuss",
        ],
    ):
        return "interested_no_price"
    return "manual_review"


def suggest_template(reply_intent: str) -> Dict[str, str]:
    mapping = {
        "quoted": ("RQ1", "high", "pricing detected with channel/form evidence"),
        "quoted_discounted": ("RQ3", "high", "pricing detected and reply mentions discounted / introductory rate"),
        "ask_budget_first": ("RI3", "high", "creator asks for our budget or offer before quoting"),
        "brief_gate": ("RI4", "medium", "creator wants brief / campaign details / verification before full quoting"),
        "details_no_price": ("RI2", "medium", "attachments or details shared but no stable quoted rate detected"),
        "interested_no_price": ("RI1", "medium", "positive interest signal without usable pricing"),
        "decline": ("RX1", "high", "clear decline or no-fit signal"),
        "manual_review": ("RX2", "low", "intent remains mixed or insufficiently structured"),
    }
    code, confidence, reason = mapping.get(reply_intent, ("RX2", "low", "intent remains mixed or insufficiently structured"))
    return {
        "template_code": code,
        "template_name": TEMPLATE_NAME_MAP[code],
        "template_confidence": confidence,
        "template_reason": reason,
        "auto_template_ready": "yes" if code != "RX2" else "no",
    }


def main() -> None:
    args = parse_args()
    messages = read_rows(Path(args.messages_csv))
    attachment_rows = read_rows(Path(args.attachments_report_csv))
    by_message = aggregate_attachments(attachment_rows)

    out_rows = []
    for row in messages:
        raw_body_text = clean_text(row.get("body_text", ""))
        logic_body_text = english_for_logic(raw_body_text)
        body_items = extract_priced_lines(logic_body_text)
        attachments = by_message.get(row.get("message_id", ""), [])
        attachment_items = []
        for attachment in attachments:
            text_file = attachment.get("text_file", "")
            if text_file and Path(text_file).exists():
                attachment_text = Path(text_file).read_text(encoding="utf-8", errors="replace")
                attachment_items.extend(extract_priced_lines(english_for_logic(attachment_text)))

        all_items = body_items + attachment_items
        matrix = build_matrix(all_items)
        main_platform = infer_main_platform(row.get("平台", ""))
        main_dedicated_rate = main_rate_for_platform(matrix, main_platform)
        if main_dedicated_rate == "-":
            main_dedicated_rate = ""

        attachment_evidence = attachment_pricing_evidence(attachments)
        pricing_excerpt_lines = [item["line"] for item in body_items[:4]]
        if attachment_evidence:
            pricing_excerpt_lines.append(attachment_evidence)
        elif attachments:
            attach_excerpt = attachment_excerpt(attachments)
            if attach_excerpt:
                pricing_excerpt_lines.append(attach_excerpt)
        if not pricing_excerpt_lines:
            fallback_excerpt = fallback_reply_excerpt(logic_body_text)
            if fallback_excerpt:
                pricing_excerpt_lines.append(fallback_excerpt)

        comprehensive_text = render_structured_pricing(all_items)
        reply_intent = detect_reply_intent(logic_body_text, attachments, all_items, attachment_evidence)
        template_signal = suggest_template(reply_intent)
        pricing_source_scope = "mixed" if body_items and attachment_evidence else ("body" if body_items else ("attachment" if attachment_evidence else "none"))
        needs_manual_review = "yes" if template_signal["template_code"] == "RX2" else "no"

        out_rows.append(
            {
                "账号ID": row.get("账号ID", ""),
                "频道/作者名称": row.get("频道/作者名称", ""),
                "平台": row.get("平台", ""),
                "from_email": row.get("from_email", ""),
                "subject": table_safe_text(row.get("subject", "")),
                "reply_at": row.get("reply_at", ""),
                "main_dedicated_rate": main_dedicated_rate,
                "综合报价": table_safe_text(comprehensive_text),
                "价格原文摘录": table_safe_text("\n".join(pricing_excerpt_lines[:8])),
                "附件渠道价格原文": table_safe_text(attachment_evidence),
                "pricing_source_scope": pricing_source_scope,
                "reply_intent": reply_intent,
                "template_code_suggestion": template_signal["template_code"],
                "template_name_suggestion": template_signal["template_name"],
                "template_confidence": template_signal["template_confidence"],
                "template_reason": template_signal["template_reason"],
                "auto_template_ready": template_signal["auto_template_ready"],
                "attachment_names": row.get("attachment_names", ""),
                "needs_manual_review": needs_manual_review,
                "body_file": row.get("body_file", ""),
            }
        )

    fieldnames = [
        "账号ID",
        "频道/作者名称",
        "平台",
        "from_email",
        "subject",
        "reply_at",
        "main_dedicated_rate",
        "综合报价",
        "价格原文摘录",
        "附件渠道价格原文",
        "pricing_source_scope",
        "reply_intent",
        "template_code_suggestion",
        "template_name_suggestion",
        "template_confidence",
        "template_reason",
        "auto_template_ready",
        "attachment_names",
        "needs_manual_review",
        "body_file",
    ]
    write_rows(Path(args.output_csv), out_rows, fieldnames)
    summary = {
        "rows": len(out_rows),
        "rows_with_main_dedicated_rate": sum(1 for row in out_rows if row["main_dedicated_rate"]),
        "rows_auto_template_ready": sum(1 for row in out_rows if row["auto_template_ready"] == "yes"),
        "output_csv": str(Path(args.output_csv).resolve()),
    }
    Path(args.output_json).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
