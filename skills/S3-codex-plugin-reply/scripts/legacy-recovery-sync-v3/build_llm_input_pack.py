#!/usr/bin/env python3
import argparse
import csv
import json
import re
from pathlib import Path
from typing import Dict, List


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build per-contact V3 LLM input packs from a V3 sample CSV.")
    parser.add_argument("--sample-csv", required=True, help="Path to V3 sample CSV.")
    parser.add_argument("--output-dir", required=True, help="Directory for markdown packs and batch jsonl.")
    parser.add_argument("--trusted-ocr-csv", help="Optional OCR trusted price candidates CSV.")
    return parser.parse_args()


def read_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def build_trusted_ocr_map(path: Path | None) -> Dict[str, List[Dict[str, str]]]:
    if not path or not path.exists():
        return {}
    rows = read_rows(path)
    mapping: Dict[str, List[Dict[str, str]]] = {}
    for row in rows:
        email = (row.get("from_email") or "").strip().lower()
        if not email:
            continue
        mapping.setdefault(email, []).append(row)
    return mapping


def slug(text: str) -> str:
    text = (text or "").strip()
    text = re.sub(r"[^A-Za-z0-9@_-]+", "-", text)
    return text.strip("-") or "unknown"


def block(value: str) -> str:
    value = (value or "").strip()
    return value if value else "(empty)"


def task_prompt() -> str:
    return (
        "Read all reply blocks and trusted attachment pricing evidence carefully.\n"
        "Fill exactly these 4 outputs:\n"
        "1. 多平台标记\n"
        "2. latest_price_raw\n"
        "3. latest_price_normalized\n"
        "4. latest_price_basis\n\n"
        "Rules:\n"
        "- 多平台标记: infer all platforms involved in the current effective price and output them in a stable format like YouTube|TikTok|Instagram.\n"
        "- latest_price_raw: keep the creator's original price wording as much as possible.\n"
        "- latest_price_normalized: normalize into structured multiline pricing with standard currency symbol and thousands separators.\n"
        "- latest_price_basis: briefly state which reply blocks were used and whether attachments were referenced.\n"
        "- If trusted OCR attachment pricing evidence exists, you may use it as supporting evidence, but do not let analytics screenshots override clearer email pricing.\n"
        "- If evidence is insufficient, stay conservative and leave fields blank when needed.\n"
    )


def main() -> None:
    args = parse_args()
    rows = read_rows(Path(args.sample_csv))
    trusted_ocr_map = build_trusted_ocr_map(Path(args.trusted_ocr_csv)) if args.trusted_ocr_csv else {}
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    jsonl_path = output_dir / "batch_input.jsonl"
    readme_path = output_dir / "README.md"
    readme_lines = [
        "---",
        "tags:",
        "  - social-agency",
        "  - s3-replyops",
        "  - v3",
        "  - llm-input",
        "date: 2026-03-26",
        "status: draft",
        "---",
        "",
        "# S3 V3 LLM Input Pack",
        "",
        "Artifacts:",
        "- `batch_input.jsonl`",
        "- `*.md` one pack per contact",
        "",
    ]
    jsonl_lines: List[str] = []

    for idx, row in enumerate(rows, start=1):
        account_id = row.get("账号ID", "")
        creator_name = row.get("频道/作者名称", "")
        filename = f"{idx:02d}_{slug(account_id or creator_name)}.md"
        md_path = output_dir / filename
        prompt = task_prompt()
        payload = {
            "sample_id": f"sample_{idx:02d}",
            "source_tag": row.get("Source_Tag", ""),
            "account_id": account_id,
            "creator_name": creator_name,
            "platform": row.get("平台", ""),
            "profile_url": row.get("账号链接", ""),
            "language": row.get("语言", ""),
            "reply_contact_email": row.get("Reply_Contact_Email", ""),
            "mail1_reply_block": row.get("mail1_reply_block", ""),
            "mail2_reply_block": row.get("mail2_reply_block", ""),
            "mail3_reply_block": row.get("mail3_reply_block", ""),
            "mail4_reply_block": row.get("mail4_reply_block", ""),
            "mail5_reply_block": row.get("mail5_reply_block", ""),
            "trusted_attachment_price_evidence": [
                {
                    "filename": item.get("filename", ""),
                    "price_raw": item.get("price_raw", ""),
                    "price_normalized": item.get("price_normalized", ""),
                    "price_confidence": item.get("price_confidence", ""),
                    "ocr_quality": item.get("ocr_quality", ""),
                    "text_preview_clean": item.get("text_preview_clean", ""),
                }
                for item in trusted_ocr_map.get((row.get("Reply_Contact_Email", "") or "").strip().lower(), [])
            ],
            "reply_thread_id": row.get("Reply_Thread_ID", ""),
            "latest_inbound_message_id": row.get("Latest_Inbound_Message_ID", ""),
        }
        attachment_lines = payload["trusted_attachment_price_evidence"]
        md_path.write_text(
            "\n".join(
                [
                    "---",
                    "tags:",
                    "  - social-agency",
                    "  - s3-replyops",
                    "  - v3",
                    "  - llm-input",
                    "date: 2026-03-26",
                    "status: draft",
                    "---",
                    "",
                    f"# {creator_name or account_id}",
                    "",
                    "## Identity",
                    "",
                    f"- Account ID: `{account_id}`",
                    f"- Creator Name: `{creator_name}`",
                    f"- Platform: `{row.get('平台', '')}`",
                    f"- Reply Contact Email: `{row.get('Reply_Contact_Email', '')}`",
                    "",
                    "## Reply Blocks",
                    "",
                    "### mail1_reply_block",
                    "",
                    "```text",
                    block(row.get("mail1_reply_block", "")),
                    "```",
                    "",
                    "### mail2_reply_block",
                    "",
                    "```text",
                    block(row.get("mail2_reply_block", "")),
                    "```",
                    "",
                    "### mail3_reply_block",
                    "",
                    "```text",
                    block(row.get("mail3_reply_block", "")),
                    "```",
                    "",
                    "### mail4_reply_block",
                    "",
                    "```text",
                    block(row.get("mail4_reply_block", "")),
                    "```",
                    "",
                    "### mail5_reply_block",
                    "",
                    "```text",
                    block(row.get("mail5_reply_block", "")),
                    "```",
                    "",
                    "## Trusted Attachment Pricing Evidence",
                    "",
                    "```json",
                    json.dumps(attachment_lines, ensure_ascii=False, indent=2) if attachment_lines else "[]",
                    "```",
                    "",
                    "## Task",
                    "",
                    "```text",
                    prompt,
                    "```",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        readme_lines.append(f"- `{filename}`: `{creator_name}` / `{account_id}`")
        jsonl_lines.append(
            json.dumps(
                {
                    "custom_id": f"sample_{idx:02d}",
                    "metadata": {
                        "account_id": account_id,
                        "creator_name": creator_name,
                        "platform": row.get("平台", ""),
                        "reply_contact_email": row.get("Reply_Contact_Email", ""),
                    },
                    "input": payload,
                    "task_prompt": prompt,
                },
                ensure_ascii=False,
            )
        )

    readme_path.write_text("\n".join(readme_lines) + "\n", encoding="utf-8")
    jsonl_path.write_text("\n".join(jsonl_lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
