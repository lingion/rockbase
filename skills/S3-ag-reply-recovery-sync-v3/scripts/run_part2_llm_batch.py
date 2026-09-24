#!/usr/bin/env python3
import argparse
import csv
import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

from openai import OpenAI


SYSTEM_PROMPT = """You analyze influencer email reply histories for pricing.
Return only valid JSON with exactly these keys:
- 多平台标记
- latest_price_raw
- latest_price_normalized
- latest_price_basis
- confidence
- notes

Rules:
- 多平台标记: infer all platforms involved in the current effective price and output a stable pipe-delimited format. Use this exact platform order when present: YouTube|TikTok|Instagram|Threads|RedNote. Leave blank if unclear.
- latest_price_raw: keep the creator's original wording and original currency/number style as much as possible. If the current effective price is formed by an earlier complete quote plus a later partial correction, latest_price_raw may include the key correction wording instead of only the final short fragment.
- latest_price_normalized: normalize into a multiline structured pricing format. Use standard currency symbols and thousands separators. This field must represent the current effective price after merging earlier complete quotes with later corrections.
- latest_price_normalized may include both the current effective price and a regular/original reference price, but they must be explicitly distinguished. Use [effective] for the current effective price and [regular/original reference] for the reference price. Never leave a second price unlabeled.
- latest_price_basis: compact evidence note like mail1_reply_block + mail2_reply_block | attachment_used=yes
- When trusted_attachment_price_evidence is provided, treat it as trusted OCR evidence. Use it only as support for pricing, not as a replacement for clearer email wording.
- Do not let analytics screenshots, audience screenshots, or metric screenshots override clearer pricing from email or rate-card attachments.
- If trusted_attachment_price_evidence contains amounts but does not explicitly label platform/form mapping, do NOT invent mappings like TikTok dedicated, Instagram story, or YouTube integration.
- For unlabeled OCR attachment amounts, you may output them only as:
  · Bundle Package: $2,000
  · Unmapped Attachment Pricing: $1,450 | $1,950 | $300
- Only map attachment prices to a specific platform/form when the attachment text clearly provides that mapping.
- If evidence is insufficient, stay conservative. Do not invent platform/form mappings.
- If reply content is not English or Simplified Chinese, prefer understanding through Chinese translation, but preserve original wording in latest_price_raw where possible.
- latest_price_normalized must use only lines starting with "· ".
- If there is a bundle/package, place that line first.
- latest_price_normalized should look like:
  · Bundle Package: TikTok + Instagram Cross-post: $2,000
  · YouTube: dedicated $500 | integration $350
  · YouTube Shorts: dedicated $300
  · TikTok: dedicated $800 | integration $500
  · Instagram: dedicated $600 | reel $450 | story $200
- If both effective and reference prices are kept, use formats like:
  · YouTube: dedicated $850 [effective] | dedicated $1,000 [regular/original reference]
  · Instagram: reel $425 [effective] | reel $500 [regular/original reference]
- Do not use bullet styles like "-", numbered lists, or slash summaries.
- Do not rewrite latest_price_raw into normalized style.
- When later replies partially revise an earlier complete price list, apply the later revision only to the affected item(s) and keep the unaffected items from the earlier quote.
- Do not assume that the final short reply replaces the entire earlier price list unless it explicitly does so.
- Prefer reconstructing one coherent current price state across mail1_reply_block ~ mailN_reply_block instead of copying only the latest sentence.
"""


REPAIR_PROMPT = """Fix the JSON output so it follows the required schema and formatting rules exactly.
Return only valid JSON with exactly these keys:
- 多平台标记
- latest_price_raw
- latest_price_normalized
- latest_price_basis
- confidence
- notes

Formatting rules:
- 多平台标记 must use stable platform order: YouTube|TikTok|Instagram|Threads|RedNote
- latest_price_raw keeps original creator wording
- latest_price_normalized uses only lines beginning with "· "
- If bundle exists, bundle line goes first
- latest_price_basis format should stay compact like mail1_reply_block + mail2_reply_block | attachment_used=yes
- If later replies partially revise earlier pricing, keep unaffected earlier items and update only the revised items.
- If both effective and reference prices are present, require explicit tags: [effective] and [regular/original reference]
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run V3 Part2 LLM batch against DashScope OpenAI-compatible endpoint.")
    parser.add_argument("--input-jsonl", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--sleep-seconds", type=float, default=1.2)
    parser.add_argument("--max-retries", type=int, default=3)
    return parser.parse_args()


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items


def _balanced_object(text: str) -> str:
    """Extract the first complete JSON object without regex overreach."""
    start = text.find("{")
    if start < 0:
        raise ValueError("No JSON object found in model output")
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
    raise ValueError("Unterminated JSON object in model output")


def _remove_trailing_commas(text: str) -> str:
    """Remove commas immediately before } or ] outside JSON strings."""
    out: list[str] = []
    in_string = False
    escaped = False
    index = 0
    while index < len(text):
        char = text[index]
        if in_string:
            out.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            out.append(char)
            index += 1
            continue
        if char == ",":
            lookahead = index + 1
            while lookahead < len(text) and text[lookahead].isspace():
                lookahead += 1
            if lookahead < len(text) and text[lookahead] in "}]":
                index += 1
                continue
        out.append(char)
        index += 1
    return "".join(out)


def extract_json(text: str) -> Dict[str, Any]:
    text = (text or "").strip()
    if not text:
        return {}
    candidates = [text]
    try:
        candidates.append(_balanced_object(text))
    except ValueError:
        pass
    last_error: json.JSONDecodeError | None = None
    for candidate in candidates:
        try:
            value = json.loads(candidate)
            if isinstance(value, dict):
                return value
        except json.JSONDecodeError as error:
            last_error = error
        try:
            value = json.loads(_remove_trailing_commas(candidate))
            if isinstance(value, dict):
                return value
        except json.JSONDecodeError as error:
            last_error = error
    raise ValueError(f"No valid JSON object found in model output: {last_error}")


def normalize_result(payload: Dict[str, Any]) -> Dict[str, str]:
    return {
        "多平台标记": str(payload.get("多平台标记", "") or "").strip(),
        "latest_price_raw": str(payload.get("latest_price_raw", "") or "").strip(),
        "latest_price_normalized": str(payload.get("latest_price_normalized", "") or "").strip(),
        "latest_price_basis": str(payload.get("latest_price_basis", "") or "").strip(),
        "confidence": str(payload.get("confidence", "") or "").strip(),
        "notes": str(payload.get("notes", "") or "").strip(),
    }


def normalize_platform_marker(text: str) -> str:
    order = ["YouTube", "TikTok", "Instagram", "Threads", "RedNote"]
    aliases = {
        "youtube": "YouTube",
        "yt": "YouTube",
        "youtube shorts": "YouTube",
        "shorts": "YouTube",
        "tiktok": "TikTok",
        "tt": "TikTok",
        "instagram": "Instagram",
        "ig": "Instagram",
        "insta": "Instagram",
        "threads": "Threads",
        "rednote": "RedNote",
        "xiaohongshu": "RedNote",
    }
    raw = [part.strip() for part in (text or "").split("|") if part.strip()]
    found = []
    for part in raw:
        norm = aliases.get(part.lower(), part)
        if norm not in found and norm in order:
            found.append(norm)
    return "|".join([item for item in order if item in found])


def normalize_basis(text: str) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip())
    return text


def validate_result(parsed: Dict[str, str]) -> List[str]:
    issues: List[str] = []
    allowed_keys = {"多平台标记", "latest_price_raw", "latest_price_normalized", "latest_price_basis", "confidence", "notes"}
    missing = [key for key in allowed_keys if key not in parsed]
    if missing:
        issues.append("missing_keys:" + ",".join(missing))

    normalized = parsed.get("latest_price_normalized", "")
    if normalized:
        bad_lines = [line for line in normalized.splitlines() if line.strip() and not line.startswith("· ")]
        if bad_lines:
            issues.append("normalized_bad_prefix")

    platform_marker = parsed.get("多平台标记", "")
    if platform_marker and platform_marker != normalize_platform_marker(platform_marker):
        issues.append("platform_order_invalid")

    basis = parsed.get("latest_price_basis", "")
    if basis and "attachment_used=" not in basis:
        issues.append("basis_missing_attachment_flag")

    return issues


def build_user_prompt(item: Dict[str, Any]) -> str:
    return json.dumps(item.get("input", {}), ensure_ascii=False, indent=2)


def repair_once(client: OpenAI, model: str, raw_content: str) -> Tuple[str, Dict[str, str]]:
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        messages=[
            {"role": "system", "content": REPAIR_PROMPT},
            {"role": "user", "content": raw_content},
        ],
    )
    content = response.choices[0].message.content or ""
    parsed = normalize_result(extract_json(content))
    return content, parsed


def request_once(client: OpenAI, model: str, item: Dict[str, Any]) -> Tuple[str, Dict[str, str]]:
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(item)},
        ],
    )
    content = response.choices[0].message.content or ""
    parsed = normalize_result(extract_json(content))
    parsed["多平台标记"] = normalize_platform_marker(parsed.get("多平台标记", ""))
    parsed["latest_price_basis"] = normalize_basis(parsed.get("latest_price_basis", ""))
    return content, parsed


def write_csv(path: Path, rows: List[Dict[str, str]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    client = OpenAI(api_key=args.api_key, base_url=args.base_url)
    items = read_jsonl(Path(args.input_jsonl))[: args.limit]
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_jsonl_path = output_dir / f"{args.model}_raw.jsonl"
    csv_path = output_dir / f"{args.model}_results.csv"
    summary_path = output_dir / f"{args.model}_summary.md"

    result_rows: List[Dict[str, str]] = []
    raw_lines: List[str] = []

    for idx, item in enumerate(items, start=1):
        custom_id = item.get("custom_id", f"item_{idx:02d}")
        metadata = item.get("metadata", {})
        last_error = ""
        content = ""
        parsed: Dict[str, str] = {}
        repair_content = ""  # retained for raw-output compatibility; never model-filled
        for attempt in range(1, args.max_retries + 1):
            try:
                content, parsed = request_once(client, args.model, item)
                issues = validate_result(parsed)
                # Syntax repair is local in extract_json. Remaining issues are
                # semantic/schema failures: retry the original constrained
                # request, but never spend a second model call on repair.
                last_error = "validation_failed:" + "|".join(issues) if issues else ""
                if not issues or attempt == args.max_retries:
                    break
            except Exception as exc:
                last_error = str(exc)
                if attempt == args.max_retries:
                    break
                time.sleep(args.sleep_seconds * attempt)
        raw_lines.append(
            json.dumps(
                {
                    "custom_id": custom_id,
                    "metadata": metadata,
                    "model": args.model,
                    "raw_content": content,
                    "repair_content": repair_content,
                    "parsed": parsed,
                    "error": last_error,
                },
                ensure_ascii=False,
            )
        )
        result_rows.append(
            {
                "custom_id": custom_id,
                "account_id": str(metadata.get("account_id", "")),
                "creator_name": str(metadata.get("creator_name", "")),
                "platform": str(metadata.get("platform", "")),
                "多平台标记": parsed.get("多平台标记", ""),
                "latest_price_raw": parsed.get("latest_price_raw", ""),
                "latest_price_normalized": parsed.get("latest_price_normalized", ""),
                "latest_price_basis": parsed.get("latest_price_basis", ""),
                "confidence": parsed.get("confidence", ""),
                "notes": parsed.get("notes", ""),
                "error": last_error,
            }
        )
        time.sleep(args.sleep_seconds)

    raw_jsonl_path.write_text("\n".join(raw_lines) + "\n", encoding="utf-8")
    write_csv(
        csv_path,
        result_rows,
        [
            "custom_id",
            "account_id",
            "creator_name",
            "platform",
            "多平台标记",
            "latest_price_raw",
            "latest_price_normalized",
            "latest_price_basis",
            "confidence",
            "notes",
            "error",
        ],
    )
    summary_lines = [
        "---",
        "tags:",
        "  - social-agency",
        "  - s3-replyops",
        "  - v3",
        "  - llm-run",
        "date: 2026-03-26",
        "status: draft",
        "---",
        "",
        f"# Part2 LLM Run Summary - {args.model}",
        "",
        f"- Model: `{args.model}`",
        f"- Rows: `{len(result_rows)}`",
        f"- Errors: `{sum(1 for row in result_rows if row['error'])}`",
        "",
    ]
    for row in result_rows:
        summary_lines.extend(
            [
                f"## {row['creator_name']} / {row['account_id']}",
                "",
                f"- 多平台标记: `{row['多平台标记']}`",
                f"- latest_price_raw: `{row['latest_price_raw']}`",
                f"- latest_price_basis: `{row['latest_price_basis']}`",
                f"- confidence: `{row['confidence']}`",
                f"- error: `{row['error']}`",
                "",
                "```text",
                row["latest_price_normalized"] or "(blank)",
                "```",
                "",
            ]
        )
    summary_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
