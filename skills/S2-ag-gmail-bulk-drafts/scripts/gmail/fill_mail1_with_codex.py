#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Any, Dict, Iterable, List, Optional, Sequence

SCRIPT_DIR = Path(__file__).parent
SHARED_DIR = SCRIPT_DIR.parent / "shared"
REFERENCE_DIR = SCRIPT_DIR.parent.parent / "references"
if str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))

from common import clean_recipient_value

try:
    # OpenAI SDK >=1 is the only LLM dependency; base_url may point at any
    # OpenAI-compatible endpoint (OpenAI, Anthropic-via-proxy, internal gateway).
    from openai import OpenAI
except ImportError as exc:  # pragma: no cover - import guard
    raise SystemExit(
        "openai SDK is required. Install with `pip install 'openai>=1,<4'` or `pip install 'rockbase-skills[llm]'`."
    ) from exc


MODEL_DEFAULT = "gpt-4o-mini"
DEFAULT_BASE_URL = "https://api.openai.com/v1"
MAX_WORKERS_HARD_CAP = 3
DEFAULT_BATCH_SIZE = 12
DEFAULT_TIMEOUT_SECONDS = 180
DEFAULT_CONFIG_PATH = REFERENCE_DIR / "cold_mail_workflow_config.json"

CONTROL_FIELDS = [
    "Mail1_Mode",
    "Mail1_Variant",
    "Mail1_Reason",
]

MAIL_GROUP_FIELDS = [
    "Mail1_Greeting_Name",
    "Mail1_Hook",
    "Mail1_Subject",
    "Mail1_Content V1",
    "Mail1_Content V2",
]

BRAND_NORMALIZATIONS = [
    (re.compile(r"\bAully\s*Hub\b", re.I), "AllyHub"),
    (re.compile(r"\bAullyHub\b", re.I), "AllyHub"),
    (re.compile(r"\bAlly\s*Hub\b", re.I), "AllyHub"),
]


@dataclass
class TargetRow:
    sheet_row_number: int
    row_index: int
    data: Dict[str, str]


def normalize_text(value: str) -> str:
    return (value or "").replace("\r\n", "\n").replace("\r", "\n").strip()


def lower_first(text: str) -> str:
    value = normalize_text(text)
    if not value:
        return value
    return value[:1].lower() + value[1:]


def deep_copy_jsonable(value):
    return json.loads(json.dumps(value, ensure_ascii=False))


def normalize_brand_names(text: str) -> str:
    value = text or ""
    for pattern, replacement in BRAND_NORMALIZATIONS:
        value = pattern.sub(replacement, value)
    return value


def load_workflow_config(path: Path | None) -> Dict[str, object]:
    config_path = path or DEFAULT_CONFIG_PATH
    return json.loads(config_path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> tuple[List[str], List[Dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = list(reader.fieldnames or [])
        rows = [{k: (v or "") for k, v in row.items()} for row in reader]
    return fieldnames, rows


def write_csv(path: Path, fieldnames: Sequence[str], rows: Iterable[Dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fieldnames))
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def parse_json_payload(raw: str):
    text = (raw or "").strip()
    if not text:
        raise ValueError("empty model output")
    decoder = json.JSONDecoder()
    try:
        parsed, _ = decoder.raw_decode(text)
        return parsed
    except json.JSONDecodeError:
        pass
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Be tolerant of common LLM JSON formatting slips like trailing commas.
        cleaned = re.sub(r",(\s*[}\]])", r"\1", text)
        try:
            parsed, _ = decoder.raw_decode(cleaned)
            return parsed
        except json.JSONDecodeError:
            pass
        if cleaned != text:
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError:
                pass
        start_positions = [pos for pos in (text.find("{"), text.find("[")) if pos != -1]
        if not start_positions:
            raise
        start = min(start_positions)
        sliced = text[start:]
        try:
            return json.loads(sliced)
        except json.JSONDecodeError:
            pass
        try:
            # Ignore trailing junk after the JSON value (e.g. a closing code fence).
            parsed, _ = decoder.raw_decode(sliced)
            return parsed
        except json.JSONDecodeError:
            cleaned_sliced = re.sub(r",(\s*[}\]])", r"\1", sliced)
            return json.loads(cleaned_sliced)


def ensure_workflow_columns(fieldnames: Sequence[str], rows: Sequence[Dict[str, str]]) -> List[str]:
    names = list(fieldnames)
    existing_controls = [field for field in CONTROL_FIELDS if field in names]
    for field in existing_controls:
        names.remove(field)
    existing_mail_positions = [names.index(field) for field in MAIL_GROUP_FIELDS if field in names]
    insert_at = min(existing_mail_positions) if existing_mail_positions else len(names)
    for field in CONTROL_FIELDS:
        names.insert(insert_at, field)
        insert_at += 1
    for field in CONTROL_FIELDS + MAIL_GROUP_FIELDS:
        if field not in names:
            names.append(field)
    for row in rows:
        for field in CONTROL_FIELDS + MAIL_GROUP_FIELDS:
            row.setdefault(field, "")
    return names


def infer_has_email(row: Dict[str, str]) -> bool:
    raw_candidates = [
        normalize_text(row.get("clean_email", "")),
        normalize_text(row.get("联系方式", "")),
    ]
    return any(clean_recipient_value(candidate) for candidate in raw_candidates if candidate)


def row_is_eligible(row: Dict[str, str]) -> bool:
    status = normalize_text(row.get("Mail1发出状态", "")).lower()
    if status in {"drafted", "sent", "skip_same_contact"}:
        return False
    if normalize_text(row.get("manual_clean_decision", "")).lower() == "drop":
        return False
    if normalize_text(row.get("email_qc_flag", "")).lower() in {"dirty", "invalid", "suspect"}:
        return False
    return infer_has_email(row)


def select_targets(rows: Sequence[Dict[str, str]], start_row: int, limit: int | None, overwrite: bool) -> List[TargetRow]:
    targets: List[TargetRow] = []
    for idx, row in enumerate(rows):
        sheet_row_number = idx + 2
        if sheet_row_number < start_row:
            continue
        if not row_is_eligible(row):
            continue
        if not overwrite:
            already_done = all(
                normalize_text(row.get(field, ""))
                for field in ("Mail1_Greeting_Name", "Mail1_Hook", "Mail1_Subject", "Mail1_Content V1")
            )
            if already_done:
                continue
        targets.append(TargetRow(sheet_row_number=sheet_row_number, row_index=idx, data=row))
        if limit is not None and len(targets) >= limit:
            break
    return targets


def prompt_rows_payload(batch: Sequence[TargetRow]) -> str:
    items = []
    keep_fields = [
        "账号ID",
        "频道/作者名称",
        "平台",
        "语言",
        "账号类目标签",
        "账号简介",
        "账号简介__平台抓取",
        "Recommendation",
        "联系方式",
        "clean_email",
    ]
    for item in batch:
        payload = {"sheet_row_number": item.sheet_row_number}
        for field in keep_fields:
            payload[field] = item.data.get(field, "")
        items.append(payload)
    return json.dumps(items, ensure_ascii=False, indent=2)


def format_allowed_values(values: Sequence[str]) -> str:
    return "\n".join(f"  - {value}" for value in values)


def build_prompt(batch: Sequence[TargetRow], workflow_config: Dict[str, object]) -> str:
    extra_rules = "\n".join(f"- {rule}" for rule in workflow_config.get("extra_prompt_rules", []))
    allowed_variants = workflow_config.get("allowed_variants", [])
    return f"""You are filling structured Mail1 fields for CoreStar Gmail cold outreach.

You must decide these semantic fields per row:
1. Mail1_Greeting_Name
2. Mail1_Hook
3. Mail1_Variant
4. Mail1_Reason

{workflow_config.get("prompt_context", "").strip()}

Task constraints:
- Use only the supplied row data.
- Do not browse the web.
- Do not invent facts like specific videos, collaborations, or audience data not present in the row.
- Greeting rule:
  - If it is clearly a real person, use the most natural short first-name form.
  - If it is clearly a brand/channel/organization, use "Name Team".
  - If it is a handle-like personal brand, keep the brand/handle form without forcing "Team".
  - Remove emoji, titles, and decorative suffixes from greetings.
- Hook rule:
  - Exactly one sentence.
  - Professional, concrete, lightly personalized.
  - Explain why this creator is a fit for AI / tech brand outreach.
  - Around 14-30 words is ideal.
  - Must be supportable from the provided row data.
- Variant rule:
  - Choose the best-fitting Mail1_Variant from the allowed list.
  - Use softer variants when fit is weaker or when the first ask should be media kit first.
  - Use direct variants only when fit evidence is already strong.
- Reason rule:
  - One short sentence explaining the greeting decision and variant choice.
  - Keep it audit-friendly, not verbose.
- Language:
  - Write Greeting Name naturally based on the account identity.
  - Write Hook and Reason in English to match the email copy.
{extra_rules}

Allowed values:
- Mail1_Variant:
{format_allowed_values(allowed_variants)}

Return JSON only, matching the provided schema.

Rows:
{prompt_rows_payload(batch)}
"""


def build_llm_client(api_key: str, base_url: str, timeout_seconds: float):
    """Create the OpenAI-compatible client. `base_url` decides the actual vendor."""
    return OpenAI(api_key=api_key, base_url=base_url, timeout=timeout_seconds)


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 2:
            # drop opening ``` / ```json and closing ```
            return "\n".join(lines[1:-1]).strip()
    return stripped


def run_llm_batch(
    batch: Sequence[TargetRow],
    client: Any,
    model: str,
    workflow_config: Dict[str, object],
    temperature: float = 0.0,
) -> Dict[int, Dict[str, str]]:
    prompt = build_prompt(batch, workflow_config)
    response = client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=[
            {
                "role": "system",
                "content": "You are a structured-data filler. Return JSON only, no prose, no markdown.",
            },
            {"role": "user", "content": prompt},
        ],
    )
    raw = _strip_code_fence(response.choices[0].message.content or "")
    data = parse_json_payload(raw)

    if isinstance(data, list):
        data = {"rows": data}

    by_row_number: Dict[int, Dict[str, str]] = {}
    for item in data.get("rows", []):
        row_number = int(item["sheet_row_number"])
        variant = normalize_text(item["Mail1_Variant"]) or workflow_config["defaults"]["mail_variant"]
        by_row_number[row_number] = {
            "Mail1_Greeting_Name": normalize_brand_names(normalize_text(item["Mail1_Greeting_Name"])),
            "Mail1_Hook": normalize_brand_names(normalize_text(item["Mail1_Hook"])),
            "Mail1_Variant": variant,
            "Mail1_Reason": normalize_brand_names(normalize_text(item["Mail1_Reason"])),
        }
    validate_batch_result(batch, by_row_number, workflow_config)
    return by_row_number


def validate_batch_result(
    batch: Sequence[TargetRow],
    results: Dict[int, Dict[str, str]],
    workflow_config: Dict[str, object],
) -> None:
    allowed_variants = set(workflow_config.get("allowed_variants", []))
    expected = {item.sheet_row_number for item in batch}
    actual = set(results.keys())
    if expected != actual:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ValueError(f"batch row mismatch. missing={missing} extra={extra}")
    for row_number, item in results.items():
        greeting = item["Mail1_Greeting_Name"]
        hook = item["Mail1_Hook"]
        reason = item["Mail1_Reason"]
        if not greeting:
            raise ValueError(f"row {row_number}: empty Mail1_Greeting_Name")
        if not hook or "\n" in hook or len(hook.split()) < 6:
            raise ValueError(f"row {row_number}: invalid Mail1_Hook")
        if not reason:
            raise ValueError(f"row {row_number}: empty Mail1_Reason")
        if item["Mail1_Variant"] not in allowed_variants:
            raise ValueError(f"row {row_number}: invalid Mail1_Variant={item['Mail1_Variant']}")


def build_subject(row_fields: Dict[str, str], workflow_config: Dict[str, object]) -> str:
    templates = workflow_config["templates"]
    variants = workflow_config["variants"]
    variant_name = normalize_text(row_fields.get("Mail1_Variant", "")) or workflow_config["defaults"]["mail_variant"]
    subject_key = variants[variant_name]["subject_pattern"]
    subject_template = workflow_config["subject_patterns"][subject_key]
    display_name = normalize_text(row_fields.get("频道/作者名称", "")) or normalize_text(row_fields.get("Mail1_Greeting_Name", "")) or "Creator"
    display_name = display_name.removesuffix(" Team")
    return normalize_brand_names(subject_template.format(display_name=display_name))


def build_ask_block(ask_intro: str, items: Sequence[str]) -> str:
    lines = [ask_intro, ""]
    lines.extend(f"- {item}" for item in items)
    return "\n".join(lines)


def build_body(row_fields: Dict[str, str], workflow_config: Dict[str, object], *, variant_name: str | None = None) -> str:
    templates = workflow_config["templates"]
    variants = workflow_config["variants"]
    variant = variant_name or normalize_text(row_fields.get("Mail1_Variant", "")) or workflow_config["defaults"]["mail_variant"]
    config = variants[variant]

    greeting_name = normalize_text(row_fields["Mail1_Greeting_Name"])
    sender_intro = templates["sender_intro"][config["sender_intro"]]
    credibility = templates["credibility_block"][config["credibility_block"]]
    hook = normalize_text(row_fields["Mail1_Hook"])
    variant_body = templates["variant_body"][config["variant_body"]]
    ask_intro = templates["ask_intro"][config["ask_intro"]]
    ask_items = templates["ask_items"][config["ask_items"]]
    ask_block = build_ask_block(ask_intro, ask_items)
    closing = templates["closing"][config["closing"]]
    signature = templates["signature"][config["signature"]]

    return normalize_brand_names(
        (
        f"Hi {greeting_name},\n\n"
        f"{sender_intro}\n\n"
        f"{credibility}\n\n"
        f"{hook}\n\n"
        f"{variant_body}\n\n"
        f"{ask_block}\n\n"
        f"{closing}\n\n"
        f"{signature}"
        )
    )


def build_body_v2(row_fields: Dict[str, str], workflow_config: Dict[str, object]) -> str:
    variant = normalize_text(row_fields.get("Mail1_Variant", "")) or workflow_config["defaults"]["mail_variant"]
    fallback_variant = "B1_creator_specific_soft" if variant.startswith("A") else variant
    return build_body(row_fields, workflow_config, variant_name=fallback_variant)


_MAIL1_ARTIFACT_KEYS = ("Mail1_Greeting_Name", "Mail1_Hook", "Mail1_Reason", "Mail1_Variant")
_MAIL1_BODY_LIMIT = 8000
_MAIL1_REDACTIONS = (
    # clean_email and any look-alike contact columns never enter the artifact;
    # the Console decision refers to the row by sheet_row_number only.
    "clean_email", "email", "contact_email", "phone", "wechat", "telegram",
)


def build_mail1_artifact(
    row: Dict[str, str],
    generated: Dict[str, str],
    validation: Dict[str, object],
) -> Dict[str, object]:
    """Bound, redact, and freeze one Mail1 draft for Console approval.

    Only the four LLM-authored Mail1_* keys survive into the payload; every
    other key the model may have produced (recipients, send mode, execute
    flags, link policies) is dropped here, so a rogue model response cannot
    change recipient or send policy. Contact columns are stripped before
    anything leaves the process. ``pending_action`` is deterministic: it is
    ``manual_review`` when validation failed or required fields are missing,
    otherwise ``await_console_decision``.
    """
    errors = list(validation.get("errors") or []) if isinstance(validation, dict) else []
    picked = {key: normalize_text(generated.get(key, "")) for key in _MAIL1_ARTIFACT_KEYS}
    missing = [key for key in _MAIL1_ARTIFACT_KEYS if not picked[key]]
    body_text = None
    if all(picked.values()):
        try:
            body_text = build_body({**row, **generated}, {}, variant_name=picked["Mail1_Variant"])
        except Exception:  # noqa: BLE001 - body is best-effort, validation drives the decision
            body_text = None
    ok = bool(validation.get("ok")) and not missing and errors == []
    pending = "await_console_decision" if ok else "manual_review"
    return {
        "stage": "s2.mail1",
        "payload": {
            "greeting": picked["Mail1_Greeting_Name"],
            "hook": picked["Mail1_Hook"],
            "reason": picked["Mail1_Reason"],
            "variant": picked["Mail1_Variant"],
            "body": (body_text or "")[:_MAIL1_BODY_LIMIT],
            "validation": {"ok": ok, "errors": errors, "warnings": list(validation.get("warnings") or [])},
            "pending_action": pending,
        },
        "validation": {"ok": ok, "errors": errors,
                       "warnings": [f"missing:{key}" for key in missing]},
    }


def write_audit_csv(path: Path, items: Sequence[Dict[str, str]]) -> None:
    fieldnames = [
        "sheet_row_number",
        "账号ID",
        "频道/作者名称",
        "Mail1_Mode",
        "Mail1_Variant",
        "Mail1_Greeting_Name",
        "Mail1_Hook",
        "Mail1_Subject",
        "Mail1_Reason",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for item in items:
            writer.writerow({k: item.get(k, "") for k in fieldnames})


def batch_rows(rows: Sequence[TargetRow], batch_size: int) -> List[List[TargetRow]]:
    return [list(rows[i : i + batch_size]) for i in range(0, len(rows), batch_size)]


def _build_argparser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fill Gmail Mail1 outreach columns with an OpenAI-compatible LLM as the semantic engine.")
    parser.add_argument("--input", required=True, help="Source CSV path to update in place.")
    parser.add_argument("--config", default="", help="Optional workflow JSON config. If omitted, the built-in default config is used.")
    parser.add_argument("--model", default=MODEL_DEFAULT, help=f"LLM model name. Default: {MODEL_DEFAULT}")
    parser.add_argument("--api-key", default="", help="LLM API key. Falls back to OPENAI_API_KEY env if omitted.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help=f"OpenAI-compatible base URL. Default: {DEFAULT_BASE_URL}")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE, help=f"Rows per LLM call. Default: {DEFAULT_BATCH_SIZE}")
    parser.add_argument("--max-workers", type=int, default=MAX_WORKERS_HARD_CAP, help=f"Concurrent LLM workers. Hard cap: {MAX_WORKERS_HARD_CAP}")
    parser.add_argument("--start-row", type=int, default=2, help="Start from this sheet row number (header is row 1).")
    parser.add_argument("--limit", type=int, default=None, help="Optional max number of source rows to process.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite rows even if target columns already have values.")
    parser.add_argument("--dry-run", action="store_true", help="Run LLM and write audit only, without writing back CSV.")
    parser.add_argument("--audit-dir", default="", help="Optional directory for audit files. Defaults to input sibling or provided path.")
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS, help=f"LLM client timeout. Default: {DEFAULT_TIMEOUT_SECONDS}")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_argparser()
    args = parser.parse_args(argv)

    import os

    api_key = args.api_key or os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        parser.error("--api-key or OPENAI_API_KEY env is required")

    max_workers = min(max(args.max_workers, 1), MAX_WORKERS_HARD_CAP)
    input_path = Path(args.input).expanduser()
    config_path = Path(args.config).expanduser() if args.config else DEFAULT_CONFIG_PATH
    cwd = input_path.parent
    audit_dir = Path(args.audit_dir).expanduser() if args.audit_dir else cwd
    audit_dir.mkdir(parents=True, exist_ok=True)
    workflow_config = load_workflow_config(config_path)

    client = build_llm_client(api_key, args.base_url, args.timeout_seconds)

    fieldnames, rows = read_csv(input_path)
    fieldnames = ensure_workflow_columns(fieldnames, rows)
    targets = select_targets(rows, start_row=args.start_row, limit=args.limit, overwrite=args.overwrite)
    if not targets:
        print(json.dumps({
            "input": str(input_path),
            "config": str(config_path),
            "selected_rows": 0,
            "written_rows": 0
        }, ensure_ascii=False, indent=2))
        return 0

    batches = batch_rows(targets, max(1, args.batch_size))
    results_by_row: Dict[int, Dict[str, str]] = {}
    errors: List[Dict[str, str]] = []

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_map = {
            pool.submit(
                run_llm_batch,
                batch,
                client,
                args.model,
                workflow_config,
            ): batch
            for batch in batches
        }
        for future in as_completed(future_map):
            batch = future_map[future]
            try:
                result = future.result()  # run_llm_batch already validated
                results_by_row.update(result)
            except Exception as exc:
                errors.append({
                    "sheet_row_numbers": ",".join(str(item.sheet_row_number) for item in batch),
                    "error": str(exc),
                })

    if errors:
        error_path = audit_dir / f"{input_path.stem}_mail1_fill_errors.json"
        error_path.write_text(json.dumps(errors, ensure_ascii=False, indent=2), encoding="utf-8")
        raise RuntimeError(f"Encountered {len(errors)} failed batch(es). See {error_path}")

    audit_items: List[Dict[str, str]] = []
    for target in targets:
        result = results_by_row[target.sheet_row_number]
        variant_name = result["Mail1_Variant"]
        rows[target.row_index]["Mail1_Greeting_Name"] = result["Mail1_Greeting_Name"]
        rows[target.row_index]["Mail1_Hook"] = result["Mail1_Hook"]
        rows[target.row_index]["Mail1_Variant"] = variant_name
        rows[target.row_index]["Mail1_Mode"] = workflow_config["variants"][variant_name]["mail_mode"]
        rows[target.row_index]["Mail1_Reason"] = result["Mail1_Reason"]
        rows[target.row_index]["Mail1_Subject"] = build_subject(rows[target.row_index], workflow_config)
        rows[target.row_index]["Mail1_Content V1"] = build_body(rows[target.row_index], workflow_config)
        rows[target.row_index]["Mail1_Content V2"] = build_body_v2(rows[target.row_index], workflow_config)
        audit_items.append({
            "sheet_row_number": str(target.sheet_row_number),
            "账号ID": target.data.get("账号ID", ""),
            "频道/作者名称": target.data.get("频道/作者名称", ""),
            "Mail1_Mode": rows[target.row_index]["Mail1_Mode"],
            "Mail1_Variant": variant_name,
            "Mail1_Greeting_Name": result["Mail1_Greeting_Name"],
            "Mail1_Hook": result["Mail1_Hook"],
            "Mail1_Subject": rows[target.row_index]["Mail1_Subject"],
            "Mail1_Reason": result["Mail1_Reason"],
        })

    audit_path = audit_dir / f"{input_path.stem}_mail1_fill_audit.csv"
    write_audit_csv(audit_path, audit_items)
    if not args.dry_run:
        write_csv(input_path, fieldnames, rows)

    summary = {
        "input": str(input_path),
        "config": str(config_path),
        "workflow_name": workflow_config.get("workflow_name", ""),
        "selected_rows": len(targets),
        "batch_count": len(batches),
        "max_workers": max_workers,
        "model": args.model,
        "dry_run": args.dry_run,
        "written_rows": 0 if args.dry_run else len(targets),
        "audit_csv": str(audit_path),
        "base_url": args.base_url,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
