#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path
import sys
from typing import Dict, List, Sequence

SCRIPT_DIR = Path(__file__).resolve().parent
SHARED_DIR = SCRIPT_DIR.parent / "shared"
if str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))

from openai import OpenAI

from common import read_csv_rows, write_csv_rows


SYSTEM_PROMPT = """You generate outreach fields for X DM campaigns.

You must produce JSON with exactly these keys:
- Mail1_Greeting_Name
- Mail1_Hook
- Mail1_Content V1

Rules:
- Use LLM judgment, not string-only cleanup.
- Mail1_Greeting_Name:
  - Real person: use the most natural first-name style greeting.
  - Brand / org / media / channel: append Team.
  - Chinese creator nicknames usually stay as-is.
  - If the visible identity is a personal handle-like brand, keep it as-is.
- Mail1_Hook:
  - One sentence only.
  - Explain why this creator is a fit.
  - Ground it in the provided category / bio only.
  - Keep it concise and believable.
- Mail1_Content V1:
  - Preserve the approved fixed structure.
  - Only personalize the greeting and hook.
  - Keep the paragraph breaks exactly as shown.
  - Do not add or remove sections.
  - Do not add signature lines.
  - Output plain text with real newlines.
"""


USER_PROMPT_TEMPLATE = """Generate the three fields for this creator.

Creator data:
- row_number: {row_number}
- account_id: {account_id}
- display_name: {display_name}
- language: {language}
- category: {category}
- internal_bio: {internal_bio}
- raw_bio: {raw_bio}

Approved fixed body structure:
Hi {{Mail1_Greeting_Name}},

This is Annabel — I run a growth agency helping AI products scale on X and other platforms. {{Mail1_Hook}}
 I'd love to put a new product on your radar: a cloud phone built for OpenClaw — giving AI agents an always-on mobile environment to run apps, automate tasks, and interact with the mobile ecosystem 24/7, no physical device needed.


Here's the exciting part —Next week we're about to launch and handpicking a tiny group of top creators for exclusive early access before it goes public. 🚀 You'd be among the very first to try it and share your genuine take with your audience. We're only extending this to creators we truly believe in — and you're one of them.


Beyond this launch, we work with multiple AI products planning long-term partnerships with consistent campaigns. I'd love to build a stable, preferential partnership with you across all of them.


Drop me a line here or on WhatsApp: [+1(515)4518184] — would love to chat! 🙌

Return JSON only.
"""


def ensure_hook_column(fieldnames: Sequence[str], rows: List[Dict[str, str]]) -> List[str]:
    names = list(fieldnames)
    if "Mail1_Hook" in names:
        return names
    if "Mail1_Greeting_Name" in names:
        idx = names.index("Mail1_Greeting_Name")
        names.insert(idx, "Mail1_Hook")
    else:
        names.append("Mail1_Hook")
    for row in rows:
        row.setdefault("Mail1_Hook", "")
    return names


def should_fill_row(row: Dict[str, str], overwrite: bool) -> bool:
    if overwrite:
        return True
    return not (
        row.get("Mail1_Greeting_Name", "").strip()
        and row.get("Mail1_Hook", "").strip()
        and row.get("Mail1_Content V1", "").strip()
    )


def build_user_prompt(row_number: int, row: Dict[str, str]) -> str:
    return USER_PROMPT_TEMPLATE.format(
        row_number=row_number,
        account_id=row.get("账号ID", "").strip(),
        display_name=row.get("频道/作者名称", "").strip(),
        language=row.get("语言", "").strip(),
        category=row.get("账号类目标签", "").strip(),
        internal_bio=row.get("账号简介", "").strip(),
        raw_bio=row.get("账号简介__平台抓取", "").strip(),
    )


def build_manifest_row(row_number: int, row: Dict[str, str]) -> Dict[str, str]:
    return {
        "row_number": row_number,
        "账号ID": row.get("账号ID", "").strip(),
        "频道/作者名称": row.get("频道/作者名称", "").strip(),
        "语言": row.get("语言", "").strip(),
        "账号类目标签": row.get("账号类目标签", "").strip(),
        "账号简介": row.get("账号简介", "").strip(),
        "账号简介__平台抓取": row.get("账号简介__平台抓取", "").strip(),
        "existing_Mail1_Greeting_Name": row.get("Mail1_Greeting_Name", "").strip(),
        "existing_Mail1_Hook": row.get("Mail1_Hook", "").strip(),
        "existing_Mail1_Content V1": row.get("Mail1_Content V1", "").strip(),
        "user_prompt": build_user_prompt(row_number, row),
    }


def call_model(client: OpenAI, model: str, user_prompt: str) -> Dict[str, str]:
    response = client.responses.create(
        model=model,
        reasoning={"effort": "low"},
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )
    payload = json.loads(response.output_text)
    for key in ["Mail1_Greeting_Name", "Mail1_Hook", "Mail1_Content V1"]:
        if key not in payload or not isinstance(payload[key], str) or not payload[key].strip():
            raise ValueError(f"Model output missing valid key: {key}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Fill or prepare X DM outreach fields.")
    parser.add_argument("--input", required=True, help="Source CSV to read and update.")
    parser.add_argument("--output", default="", help="Optional output CSV path. Default: overwrite input.")
    parser.add_argument(
        "--provider",
        choices=["conversation_llm", "openai_api"],
        default="conversation_llm",
        help="Default is conversation_llm: prepare a manifest for in-chat filling without requiring an API key.",
    )
    parser.add_argument("--model", default="gpt-5.4-mini", help="OpenAI model name.")
    parser.add_argument("--api-key", default=os.environ.get("OPENAI_API_KEY", ""), help="OpenAI API key. Only required when --provider openai_api.")
    parser.add_argument("--manifest-out", default="", help="Optional JSON path for conversation_llm mode.")
    parser.add_argument("--start-row", type=int, default=1, help="1-based data-row start, inclusive.")
    parser.add_argument("--end-row", type=int, default=0, help="1-based data-row end, inclusive. 0 means all.")
    parser.add_argument("--limit", type=int, default=0, help="Optional max number of rows to fill after filtering.")
    parser.add_argument("--overwrite-existing", action="store_true", help="Overwrite already-filled fields.")
    parser.add_argument("--dry-run", action="store_true", help="Generate preview JSON without writing CSV.")
    args = parser.parse_args()

    if args.provider == "openai_api" and not args.api_key:
        raise SystemExit("Missing OpenAI API key. Pass --api-key or set OPENAI_API_KEY when --provider openai_api is used.")

    input_path = Path(args.input)
    output_path = Path(args.output) if args.output else input_path
    fieldnames, rows = read_csv_rows(input_path)
    fieldnames = ensure_hook_column(fieldnames, rows)

    client = OpenAI(api_key=args.api_key) if args.provider == "openai_api" else None

    generated = []
    manifest_rows = []
    filled_count = 0
    for index, row in enumerate(rows, start=1):
        if index < args.start_row:
            continue
        if args.end_row and index > args.end_row:
            continue
        if not should_fill_row(row, args.overwrite_existing):
            continue
        if args.provider == "openai_api":
            payload = call_model(client, args.model, build_user_prompt(index, row))
            row["Mail1_Greeting_Name"] = payload["Mail1_Greeting_Name"].strip()
            row["Mail1_Hook"] = payload["Mail1_Hook"].strip()
            row["Mail1_Content V1"] = payload["Mail1_Content V1"].strip()
            generated.append(
                {
                    "row_number": index,
                    "账号ID": row.get("账号ID", ""),
                    "频道/作者名称": row.get("频道/作者名称", ""),
                    "Mail1_Greeting_Name": row["Mail1_Greeting_Name"],
                    "Mail1_Hook": row["Mail1_Hook"],
                }
            )
        else:
            manifest_rows.append(build_manifest_row(index, row))
        filled_count += 1
        if args.limit and filled_count >= args.limit:
            break

    if args.provider == "conversation_llm":
        payload = {
            "mode": "conversation_llm",
            "input": str(input_path),
            "rows_selected": filled_count,
            "rows": manifest_rows,
        }
        if args.manifest_out:
            manifest_path = Path(args.manifest_out)
            manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps({"mode": "conversation_llm", "manifest_out": str(manifest_path), "rows_selected": filled_count}, ensure_ascii=False, indent=2))
            return
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    if args.dry_run:
        print(json.dumps(generated, ensure_ascii=False, indent=2))
        return

    write_csv_rows(output_path, fieldnames, rows)
    print(
        json.dumps(
            {
                "input": str(input_path),
                "output": str(output_path),
                "rows_filled": filled_count,
                "start_row": args.start_row,
                "end_row": args.end_row,
                "limit": args.limit,
                "model": args.model,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
