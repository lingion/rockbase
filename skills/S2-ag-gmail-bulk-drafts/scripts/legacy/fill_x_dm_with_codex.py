#!/usr/bin/env python3
"""
LLM-driven filler for X cold outreach CSV columns.

Design:
- One stable engine script.
- Per-run workflow copy lives in a JSON config file, usually under workbench/{YYYY-MM-DD}/.
- The config controls prompt wording, allowed variants, defaults, and body assembly.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import tempfile
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

SCRIPT_DIR = Path(__file__).resolve().parent
SHARED_DIR = SCRIPT_DIR.parent / "shared"
if str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))


MODEL_DEFAULT = "gpt-5.4-mini"
MAX_WORKERS_HARD_CAP = 3
DEFAULT_BATCH_SIZE = 12
DEFAULT_TIMEOUT_SECONDS = 180

CONTROL_FIELDS = [
    "DM_Angle",
    "DM_Open_Variant",
    "DM_Context_Variant",
    "DM_Intent_Variant",
    "DM_CTA_Variant",
    "reason",
]

MAIL_GROUP_FIELDS = [
    "Mail1_Greeting_Name",
    "Mail1_Hook",
    "Mail1_Subject",
    "Mail1_Content V1",
    "Mail1_Content V2",
]

DEFAULT_ALLOWED_ANGLES = [
    "builder",
    "founder",
    "operator",
    "educator",
    "researcher",
    "automation",
    "creator-tools",
    "ai-generalist",
]

ANGLE_ALIASES = {
    "creator": "creator-tools",
    "creators": "creator-tools",
    "creator_tool": "creator-tools",
    "creator_tools": "creator-tools",
    "research": "researcher",
    "ops": "operator",
}

DEFAULT_CONFIG = {
    "workflow_name": "P3.1 Launch / Early Access",
    "mail_body_version": "3.1",
    "subject_template": "{display_name} x {workflow_name}",
    "prompt_context": "Mail1_Content V1 will be assembled by code from the approved workflow config, so do not rewrite the full body.",
    "extra_prompt_rules": [
        "Choose only from the allowed values below.",
        "Use the approved workflow structure and choose the best-fitting angle.",
    ],
    "allowed_angles": DEFAULT_ALLOWED_ANGLES,
    "templates": {
        "DM_Open_Variant": {
            "annabel_growth_agency": "This is Annabel — I run a growth agency helping AI products scale on X and other platforms.",
            "annabel_quick_note": "Quick note — I’m Annabel, and I help AI products grow through creator and social distribution on X and other platforms.",
            "annabel_rockbase_intro": "I’m Annabel from Rockbase Agency, where we help AI products reach the right creator audiences on X and beyond.",
        },
        "DM_Context_Variant": {
            "mail1_hook": "{hook}",
            "hook_reason_bridge": "The reason I wanted to reach out is simple: {hook_lower}",
            "hook_audience_bridge": "What stood out to me is that {hook_lower}",
        },
        "DM_Intent_Variant": {
            "launch_early_access": (
                "I'd love to put a new product on your radar: a cloud phone built for OpenClaw — giving AI agents "
                "an always-on mobile environment to run apps, automate tasks, and interact with the mobile ecosystem "
                "24/7, no physical device needed.\n\n"
                "Here's the exciting part —Next week we're about to launch and handpicking a tiny group of top creators "
                "for exclusive early access before it goes public. 🚀 You'd be among the very first to try it and share "
                "your genuine take with your audience. We're only extending this to creators we truly believe in — and "
                "you're one of them.\n\n"
                "Beyond this launch, we work with multiple AI products planning long-term partnerships with consistent "
                "campaigns. I'd love to build a stable, preferential partnership with you across all of them."
            ),
            "launch_creator_group": (
                "We’re putting together a small creator group around a cloud phone built for OpenClaw — giving AI agents "
                "an always-on mobile environment to run apps, automate tasks, and interact with the mobile ecosystem 24/7 "
                "without needing a physical device.\n\n"
                "The immediate focus is early access before launch next week, so I thought it could be especially relevant "
                "to bring to you now.\n\n"
                "If there’s a fit, we also work with multiple AI products on recurring campaigns and long-term partnerships."
            ),
            "launch_relevance_first": (
                "The reason I wanted to put this on your radar is that we’re about to launch a cloud phone for OpenClaw — "
                "an always-on mobile environment that lets AI agents run apps, automate tasks, and stay active 24/7.\n\n"
                "We’re sharing it first with a small number of creators ahead of the public rollout next week.\n\n"
                "Beyond this one launch, we often support AI products that want stable creator relationships across "
                "multiple campaigns."
            ),
        },
        "DM_CTA_Variant": {
            "reply_here_whatsapp": "Drop me a line here or on WhatsApp: [+1(515)4518184] — would love to chat! 🙌",
        },
    },
    "defaults": {
        "DM_Open_Variant": "annabel_growth_agency",
        "DM_Context_Variant": "mail1_hook",
        "DM_Intent_Variant": "launch_early_access",
        "DM_CTA_Variant": "reply_here_whatsapp",
    },
    "variant_strategy": {
        "founder": [
            {"DM_Open_Variant": "annabel_growth_agency", "DM_Context_Variant": "mail1_hook", "DM_Intent_Variant": "launch_relevance_first", "DM_CTA_Variant": "reply_here_whatsapp"},
            {"DM_Open_Variant": "annabel_quick_note", "DM_Context_Variant": "hook_reason_bridge", "DM_Intent_Variant": "launch_creator_group", "DM_CTA_Variant": "reply_here_whatsapp"},
            {"DM_Open_Variant": "annabel_rockbase_intro", "DM_Context_Variant": "mail1_hook", "DM_Intent_Variant": "launch_early_access", "DM_CTA_Variant": "reply_here_whatsapp"},
        ],
        "builder": [
            {"DM_Open_Variant": "annabel_quick_note", "DM_Context_Variant": "hook_reason_bridge", "DM_Intent_Variant": "launch_relevance_first", "DM_CTA_Variant": "reply_here_whatsapp"},
            {"DM_Open_Variant": "annabel_growth_agency", "DM_Context_Variant": "mail1_hook", "DM_Intent_Variant": "launch_creator_group", "DM_CTA_Variant": "reply_here_whatsapp"},
            {"DM_Open_Variant": "annabel_rockbase_intro", "DM_Context_Variant": "hook_reason_bridge", "DM_Intent_Variant": "launch_early_access", "DM_CTA_Variant": "reply_here_whatsapp"},
        ],
        "operator": [
            {"DM_Open_Variant": "annabel_rockbase_intro", "DM_Context_Variant": "mail1_hook", "DM_Intent_Variant": "launch_creator_group", "DM_CTA_Variant": "reply_here_whatsapp"},
            {"DM_Open_Variant": "annabel_growth_agency", "DM_Context_Variant": "hook_reason_bridge", "DM_Intent_Variant": "launch_relevance_first", "DM_CTA_Variant": "reply_here_whatsapp"},
            {"DM_Open_Variant": "annabel_quick_note", "DM_Context_Variant": "mail1_hook", "DM_Intent_Variant": "launch_early_access", "DM_CTA_Variant": "reply_here_whatsapp"},
        ],
        "educator": [
            {"DM_Open_Variant": "annabel_quick_note", "DM_Context_Variant": "hook_reason_bridge", "DM_Intent_Variant": "launch_creator_group", "DM_CTA_Variant": "reply_here_whatsapp"},
            {"DM_Open_Variant": "annabel_growth_agency", "DM_Context_Variant": "mail1_hook", "DM_Intent_Variant": "launch_relevance_first", "DM_CTA_Variant": "reply_here_whatsapp"},
            {"DM_Open_Variant": "annabel_rockbase_intro", "DM_Context_Variant": "hook_reason_bridge", "DM_Intent_Variant": "launch_early_access", "DM_CTA_Variant": "reply_here_whatsapp"},
        ],
        "researcher": [
            {"DM_Open_Variant": "annabel_growth_agency", "DM_Context_Variant": "hook_reason_bridge", "DM_Intent_Variant": "launch_early_access", "DM_CTA_Variant": "reply_here_whatsapp"},
            {"DM_Open_Variant": "annabel_rockbase_intro", "DM_Context_Variant": "mail1_hook", "DM_Intent_Variant": "launch_relevance_first", "DM_CTA_Variant": "reply_here_whatsapp"},
            {"DM_Open_Variant": "annabel_quick_note", "DM_Context_Variant": "hook_reason_bridge", "DM_Intent_Variant": "launch_creator_group", "DM_CTA_Variant": "reply_here_whatsapp"},
        ],
        "automation": [
            {"DM_Open_Variant": "annabel_rockbase_intro", "DM_Context_Variant": "hook_reason_bridge", "DM_Intent_Variant": "launch_relevance_first", "DM_CTA_Variant": "reply_here_whatsapp"},
            {"DM_Open_Variant": "annabel_quick_note", "DM_Context_Variant": "mail1_hook", "DM_Intent_Variant": "launch_creator_group", "DM_CTA_Variant": "reply_here_whatsapp"},
            {"DM_Open_Variant": "annabel_growth_agency", "DM_Context_Variant": "hook_reason_bridge", "DM_Intent_Variant": "launch_early_access", "DM_CTA_Variant": "reply_here_whatsapp"},
        ],
        "creator-tools": [
            {"DM_Open_Variant": "annabel_quick_note", "DM_Context_Variant": "hook_reason_bridge", "DM_Intent_Variant": "launch_creator_group", "DM_CTA_Variant": "reply_here_whatsapp"},
            {"DM_Open_Variant": "annabel_growth_agency", "DM_Context_Variant": "mail1_hook", "DM_Intent_Variant": "launch_relevance_first", "DM_CTA_Variant": "reply_here_whatsapp"},
            {"DM_Open_Variant": "annabel_rockbase_intro", "DM_Context_Variant": "hook_reason_bridge", "DM_Intent_Variant": "launch_early_access", "DM_CTA_Variant": "reply_here_whatsapp"},
        ],
        "ai-generalist": [
            {"DM_Open_Variant": "annabel_growth_agency", "DM_Context_Variant": "mail1_hook", "DM_Intent_Variant": "launch_early_access", "DM_CTA_Variant": "reply_here_whatsapp"},
            {"DM_Open_Variant": "annabel_quick_note", "DM_Context_Variant": "hook_reason_bridge", "DM_Intent_Variant": "launch_relevance_first", "DM_CTA_Variant": "reply_here_whatsapp"},
            {"DM_Open_Variant": "annabel_rockbase_intro", "DM_Context_Variant": "mail1_hook", "DM_Intent_Variant": "launch_creator_group", "DM_CTA_Variant": "reply_here_whatsapp"},
        ],
    },
}


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


def normalize_choice(value: str, aliases: Dict[str, str] | None = None, *, collapse_underscores: bool = False) -> str:
    normalized = normalize_text(value)
    if not normalized:
        return normalized
    key = normalized.lower().replace("_", "-") if collapse_underscores else normalized.lower()
    if aliases and key in aliases:
        return aliases[key]
    return key if collapse_underscores or normalized.lower() == normalized else normalized


def deep_copy_jsonable(value):
    return json.loads(json.dumps(value, ensure_ascii=False))


def load_workflow_config(path: Path | None) -> Dict[str, object]:
    config = deep_copy_jsonable(DEFAULT_CONFIG)
    if path is None:
        return config
    loaded = json.loads(path.read_text(encoding="utf-8"))
    for key in ("workflow_name", "mail_body_version", "prompt_context", "extra_prompt_rules", "allowed_angles"):
        if key in loaded:
            config[key] = loaded[key]
    for key in ("templates", "defaults", "variant_strategy"):
        if key in loaded:
            config[key] = loaded[key]
    return config


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
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start_positions = [pos for pos in (text.find("{"), text.find("[")) if pos != -1]
        if not start_positions:
            raise
        start = min(start_positions)
        return json.loads(text[start:])


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
    for field in ("Mail1_Greeting_Name", "Mail1_Hook", "Mail1_Content V1"):
        if field not in names:
            names.append(field)
    for row in rows:
        for field in CONTROL_FIELDS + ["Mail1_Greeting_Name", "Mail1_Hook", "Mail1_Content V1"]:
            row.setdefault(field, "")
    return names


def build_body(row_fields: Dict[str, str], workflow_config: Dict[str, object]) -> str:
    templates = workflow_config["templates"]
    defaults = workflow_config["defaults"]
    greeting_name = normalize_text(row_fields["Mail1_Greeting_Name"])
    hook = normalize_text(row_fields["Mail1_Hook"])
    hook_lower = lower_first(hook)
    open_key = normalize_text(row_fields["DM_Open_Variant"]) or defaults["DM_Open_Variant"]
    context_key = normalize_text(row_fields["DM_Context_Variant"]) or defaults["DM_Context_Variant"]
    intent_key = normalize_text(row_fields["DM_Intent_Variant"]) or defaults["DM_Intent_Variant"]
    cta_key = normalize_text(row_fields["DM_CTA_Variant"]) or defaults["DM_CTA_Variant"]

    open_line = templates["DM_Open_Variant"][open_key]
    context_line = templates["DM_Context_Variant"][context_key].format(hook=hook, hook_lower=hook_lower)
    intent_block = templates["DM_Intent_Variant"][intent_key]
    cta_line = templates["DM_CTA_Variant"][cta_key]

    return (
        f"Hi {greeting_name},\n\n"
        f"{open_line} {context_line}\n\n"
        f"{intent_block}\n\n"
        f"{cta_line}"
    )


def build_subject(row_fields: Dict[str, str], workflow_config: Dict[str, object]) -> str:
    template = normalize_text(str(workflow_config.get("subject_template", ""))) or "{display_name} x {workflow_name}"
    display_name = normalize_text(row_fields.get("频道/作者名称", "")) or normalize_text(row_fields.get("Mail1_Greeting_Name", "")) or "Creator"
    workflow_name = normalize_text(str(workflow_config.get("workflow_name", ""))) or "Rockbase collaboration"
    return template.format(display_name=display_name, workflow_name=workflow_name)


def infer_angle(row: Dict[str, str]) -> str:
    primary = " ".join(
        normalize_text(row.get(field, "")).lower()
        for field in ("账号类目标签", "账号简介", "账号简介__平台抓取", "Recommendation")
    )
    hook_text = normalize_text(row.get("Mail1_Hook", "")).lower()
    keyword_map = [
        ("educator", ["educational", "tutorial", "teaching", "explainer", "teaching background", "education"]),
        ("automation", ["automation", "workflow", "n8n", "agent workflows", "automate"]),
        ("operator", ["operations", "growth", "marketing", "business execution", "e-commerce", "dtc"]),
        ("researcher", ["research", "science", "biomed", "robotics", "real-world systems"]),
        ("creator-tools", ["creator", "design", "visuals", "no-code", "tools", "practical product usage"]),
        ("builder", ["builder", "dev tools", "coding", "software creation", "developer tools"]),
        ("founder", ["founder", "startup", "building", "build", "ceo"]),
    ]
    for angle, keywords in keyword_map:
        if any(keyword in primary for keyword in keywords):
            return angle
    for angle, keywords in keyword_map:
        if any(keyword in hook_text for keyword in keywords):
            return angle
    return "ai-generalist"


def build_reason(row: Dict[str, str], angle: str) -> str:
    account = normalize_text(row.get("频道/作者名称", "")) or normalize_text(row.get("账号ID", ""))
    hook = normalize_text(row.get("Mail1_Hook", ""))
    if hook:
        return f"{account} mapped to {angle} based on the existing hook and profile context."
    return f"{account} mapped to {angle} using existing row metadata."


def choose_variants(row: Dict[str, str], angle: str, workflow_config: Dict[str, object]) -> Dict[str, str]:
    identity = normalize_text(row.get("账号ID", "")) or normalize_text(row.get("频道/作者名称", ""))
    variants_by_angle = workflow_config["variant_strategy"]
    default_variants = variants_by_angle.get("ai-generalist", [])
    options = variants_by_angle.get(angle, default_variants)
    if not options:
        raise ValueError(f"Missing variant strategy for angle={angle}")
    bucket = int(hashlib.sha256(identity.encode("utf-8")).hexdigest(), 16) % len(options)
    chosen = dict(options[bucket])
    for field, default_value in workflow_config["defaults"].items():
        chosen.setdefault(field, default_value)
    return chosen


def upgrade_from_existing_fields(row: Dict[str, str], workflow_config: Dict[str, object]) -> Dict[str, str]:
    greeting = normalize_text(row.get("Mail1_Greeting_Name", ""))
    hook = normalize_text(row.get("Mail1_Hook", ""))
    angle = infer_angle(row)
    variants = choose_variants(row, angle, workflow_config)
    return {
        "Mail1_Greeting_Name": greeting,
        "Mail1_Hook": hook,
        "DM_Angle": angle,
        "DM_Open_Variant": variants["DM_Open_Variant"],
        "DM_Context_Variant": variants["DM_Context_Variant"],
        "DM_Intent_Variant": variants["DM_Intent_Variant"],
        "DM_CTA_Variant": variants["DM_CTA_Variant"],
        "reason": build_reason(row, angle),
    }


def select_targets(rows: Sequence[Dict[str, str]], start_row: int, limit: int | None, overwrite: bool) -> List[TargetRow]:
    targets: List[TargetRow] = []
    for idx, row in enumerate(rows):
        sheet_row_number = idx + 2
        if sheet_row_number < start_row:
            continue
        if not overwrite:
            already_done = any(
                normalize_text(row.get(field, ""))
                for field in ("Mail1_Greeting_Name", "Mail1_Hook", "Mail1_Content V1")
            )
            if already_done:
                continue
        targets.append(TargetRow(sheet_row_number=sheet_row_number, row_index=idx, data=row))
        if limit is not None and len(targets) >= limit:
            break
    return targets


def batch_rows(rows: Sequence[TargetRow], batch_size: int) -> List[List[TargetRow]]:
    return [list(rows[i : i + batch_size]) for i in range(0, len(rows), batch_size)]


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
    templates = workflow_config["templates"]
    extra_rules = "\n".join(f"- {rule}" for rule in workflow_config.get("extra_prompt_rules", []))
    return f"""You are filling structured fields for Rockbase's X cold outreach sheet.

You must decide these semantic fields per row:
1. Mail1_Greeting_Name
2. Mail1_Hook
3. DM_Angle
4. DM_Open_Variant
5. DM_Context_Variant
6. DM_Intent_Variant
7. DM_CTA_Variant
8. reason

{workflow_config.get("prompt_context", "").strip()}

Task constraints:
- Use only the supplied row data.
- Do not browse the web.
- Do not invent facts like specific tweets, videos, or collaborations that are not present in the row.
- Greeting rule:
  - If it is clearly a real person, use the most natural short first-name form.
  - If it is clearly a brand/channel/organization, use "Name Team".
  - If it is a handle-like personal brand, keep the brand/handle form without forcing "Team".
  - Remove emoji, titles, and decorative suffixes from greetings.
- Hook rule:
  - Exactly one sentence.
  - Professional, concrete, lightly personalized.
  - Explain why this creator is a fit for this outreach.
  - Around 14-28 words is ideal.
  - Must be supportable from the provided row data.
  - Do not mention specific posts/videos unless they are explicitly given in the row data.
- Language:
  - Write Greeting Name naturally based on the account identity.
  - Write Hook in English to match the approved frozen body.
{extra_rules}

Allowed values:
- DM_Angle:
{format_allowed_values(workflow_config.get("allowed_angles", DEFAULT_ALLOWED_ANGLES))}
- DM_Open_Variant:
{format_allowed_values(list(templates["DM_Open_Variant"].keys()))}
- DM_Context_Variant:
{format_allowed_values(list(templates["DM_Context_Variant"].keys()))}
- DM_Intent_Variant:
{format_allowed_values(list(templates["DM_Intent_Variant"].keys()))}
- DM_CTA_Variant:
{format_allowed_values(list(templates["DM_CTA_Variant"].keys()))}

Return JSON only, matching the provided schema.

Rows:
{prompt_rows_payload(batch)}
"""


def run_codex_batch(
    batch: Sequence[TargetRow],
    cwd: Path,
    model: str,
    codex_bin: str,
    workflow_config: Dict[str, object],
    timeout_seconds: int,
) -> Dict[int, Dict[str, str]]:
    prompt = build_prompt(batch, workflow_config)
    with tempfile.TemporaryDirectory(prefix="codex_fill_") as tmpdir:
        output_path = Path(tmpdir) / "output.json"
        cmd = [
            codex_bin,
            "exec",
            "--skip-git-repo-check",
            "--sandbox",
            "read-only",
            "--model",
            model,
            "--output-last-message",
            str(output_path),
            "-C",
            str(cwd),
            "--",
            prompt,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_seconds)
        if proc.returncode != 0:
            raise RuntimeError(
                f"codex exec failed ({proc.returncode})\nSTDOUT:\n{proc.stdout[-4000:]}\nSTDERR:\n{proc.stderr[-4000:]}"
            )
        raw = output_path.read_text(encoding="utf-8").strip()
        data = parse_json_payload(raw)

    if isinstance(data, list):
        data = {"rows": data}

    by_row_number: Dict[int, Dict[str, str]] = {}
    for item in data.get("rows", []):
        row_number = int(item["sheet_row_number"])
        by_row_number[row_number] = {
            "Mail1_Greeting_Name": normalize_text(item["Mail1_Greeting_Name"]),
            "Mail1_Hook": normalize_text(item["Mail1_Hook"]),
            "DM_Angle": normalize_choice(item["DM_Angle"], ANGLE_ALIASES, collapse_underscores=True),
            "DM_Open_Variant": normalize_choice(item["DM_Open_Variant"]),
            "DM_Context_Variant": normalize_choice(item["DM_Context_Variant"]),
            "DM_Intent_Variant": normalize_choice(item["DM_Intent_Variant"]),
            "DM_CTA_Variant": normalize_choice(item["DM_CTA_Variant"]),
            "reason": normalize_text(item["reason"]),
        }
    return by_row_number


def validate_batch_result(
    batch: Sequence[TargetRow],
    results: Dict[int, Dict[str, str]],
    workflow_config: Dict[str, object],
) -> None:
    templates = workflow_config["templates"]
    expected = {item.sheet_row_number for item in batch}
    actual = set(results.keys())
    if expected != actual:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ValueError(f"batch row mismatch. missing={missing} extra={extra}")
    for row_number, item in results.items():
        greeting = item["Mail1_Greeting_Name"]
        hook = item["Mail1_Hook"]
        if not greeting:
            raise ValueError(f"row {row_number}: empty Mail1_Greeting_Name")
        if not hook or "\n" in hook:
            raise ValueError(f"row {row_number}: invalid Mail1_Hook")
        if len(hook.split()) < 6:
            raise ValueError(f"row {row_number}: hook too short")
        for field, allowed in (
            ("DM_Open_Variant", set(templates["DM_Open_Variant"].keys())),
            ("DM_Context_Variant", set(templates["DM_Context_Variant"].keys())),
            ("DM_Intent_Variant", set(templates["DM_Intent_Variant"].keys())),
            ("DM_CTA_Variant", set(templates["DM_CTA_Variant"].keys())),
        ):
            if item[field] not in allowed:
                raise ValueError(f"row {row_number}: invalid {field}={item[field]}")
        if item["DM_Angle"] not in workflow_config.get("allowed_angles", DEFAULT_ALLOWED_ANGLES):
            raise ValueError(f"row {row_number}: invalid DM_Angle={item['DM_Angle']}")


def write_audit_csv(path: Path, items: Sequence[Dict[str, str]]) -> None:
    fieldnames = [
        "sheet_row_number",
        "账号ID",
        "频道/作者名称",
        "DM_Angle",
        "DM_Open_Variant",
        "DM_Context_Variant",
        "DM_Intent_Variant",
        "DM_CTA_Variant",
        "Mail1_Greeting_Name",
        "Mail1_Hook",
        "reason",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for item in items:
            writer.writerow({k: item.get(k, "") for k in fieldnames})


def main() -> None:
    parser = argparse.ArgumentParser(description="Fill X cold outreach columns with Codex as the semantic engine.")
    parser.add_argument("--input", required=True, help="Source CSV path to update in place.")
    parser.add_argument("--config", default="", help="Optional workflow JSON config. If omitted, the built-in default config is used.")
    parser.add_argument("--model", default=MODEL_DEFAULT, help=f"Codex model to use. Default: {MODEL_DEFAULT}")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE, help=f"Rows per Codex call. Default: {DEFAULT_BATCH_SIZE}")
    parser.add_argument("--max-workers", type=int, default=MAX_WORKERS_HARD_CAP, help=f"Concurrent Codex workers. Hard cap: {MAX_WORKERS_HARD_CAP}")
    parser.add_argument("--start-row", type=int, default=2, help="Start from this sheet row number (header is row 1).")
    parser.add_argument("--limit", type=int, default=None, help="Optional max number of source rows to process.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite rows even if target columns already have values.")
    parser.add_argument(
        "--upgrade-from-existing",
        action="store_true",
        help="Reuse existing Mail1_Greeting_Name/Mail1_Hook to populate new DM control fields and rebuild Mail1_Content V1 without calling Codex.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Run Codex and write audit only, without writing back CSV.")
    parser.add_argument("--codex-bin", default="codex", help="Codex CLI binary path.")
    parser.add_argument("--audit-dir", default="", help="Optional directory for audit files. Defaults to input sibling or provided path.")
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS, help=f"Per Codex batch timeout. Default: {DEFAULT_TIMEOUT_SECONDS}")
    args = parser.parse_args()

    max_workers = min(max(args.max_workers, 1), MAX_WORKERS_HARD_CAP)
    input_path = Path(args.input).expanduser().resolve()
    config_path = Path(args.config).expanduser().resolve() if args.config else None
    cwd = input_path.parent
    audit_dir = Path(args.audit_dir).expanduser().resolve() if args.audit_dir else cwd
    audit_dir.mkdir(parents=True, exist_ok=True)
    workflow_config = load_workflow_config(config_path)

    fieldnames, rows = read_csv(input_path)
    fieldnames = ensure_workflow_columns(fieldnames, rows)

    targets = select_targets(rows, start_row=args.start_row, limit=args.limit, overwrite=args.overwrite)
    if not targets:
        print(
            json.dumps(
                {
                    "input": str(input_path),
                    "config": str(config_path) if config_path else "",
                    "selected_rows": 0,
                    "written_rows": 0,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    results_by_row: Dict[int, Dict[str, str]] = {}
    errors: List[Dict[str, str]] = []

    if args.upgrade_from_existing:
        batches = [targets]
        for target in targets:
            result = upgrade_from_existing_fields(rows[target.row_index], workflow_config)
            if not result["Mail1_Greeting_Name"] or not result["Mail1_Hook"]:
                errors.append(
                    {
                        "sheet_row_numbers": str(target.sheet_row_number),
                        "error": "Missing existing Mail1_Greeting_Name or Mail1_Hook for upgrade-from-existing mode",
                    }
                )
            else:
                results_by_row[target.sheet_row_number] = result
    else:
        batches = batch_rows(targets, max(1, args.batch_size))
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            future_map = {
                pool.submit(
                    run_codex_batch,
                    batch,
                    cwd,
                    args.model,
                    args.codex_bin,
                    workflow_config,
                    args.timeout_seconds,
                ): batch
                for batch in batches
            }
            for future in as_completed(future_map):
                batch = future_map[future]
                try:
                    result = future.result()
                    validate_batch_result(batch, result, workflow_config)
                    results_by_row.update(result)
                except Exception as exc:
                    errors.append(
                        {
                            "sheet_row_numbers": ",".join(str(item.sheet_row_number) for item in batch),
                            "error": str(exc),
                        }
                    )

    if errors:
        error_path = audit_dir / f"{input_path.stem}_llm_fill_errors.json"
        error_path.write_text(json.dumps(errors, ensure_ascii=False, indent=2), encoding="utf-8")
        raise RuntimeError(f"Encountered {len(errors)} failed batch(es). See {error_path}")

    audit_items: List[Dict[str, str]] = []
    for target in targets:
        result = results_by_row[target.sheet_row_number]
        for field in [
            "Mail1_Greeting_Name",
            "Mail1_Hook",
            "DM_Angle",
            "DM_Open_Variant",
            "DM_Context_Variant",
            "DM_Intent_Variant",
            "DM_CTA_Variant",
            "reason",
        ]:
            rows[target.row_index][field] = result.get(field, "")
        rows[target.row_index]["Mail1_Subject"] = build_subject(rows[target.row_index], workflow_config)
        rows[target.row_index]["Mail1_Content V1"] = build_body(rows[target.row_index], workflow_config)
        audit_items.append(
            {
                "sheet_row_number": str(target.sheet_row_number),
                "账号ID": target.data.get("账号ID", ""),
                "频道/作者名称": target.data.get("频道/作者名称", ""),
                "DM_Angle": result["DM_Angle"],
                "DM_Open_Variant": result["DM_Open_Variant"],
                "DM_Context_Variant": result["DM_Context_Variant"],
                "DM_Intent_Variant": result["DM_Intent_Variant"],
                "DM_CTA_Variant": result["DM_CTA_Variant"],
                "Mail1_Greeting_Name": result["Mail1_Greeting_Name"],
                "Mail1_Hook": result["Mail1_Hook"],
                "reason": result.get("reason", ""),
            }
        )

    audit_path = audit_dir / f"{input_path.stem}_llm_fill_audit.csv"
    write_audit_csv(audit_path, audit_items)
    if not args.dry_run:
        write_csv(input_path, fieldnames, rows)

    summary = {
        "input": str(input_path),
        "config": str(config_path) if config_path else "",
        "workflow_name": workflow_config.get("workflow_name", ""),
        "selected_rows": len(targets),
        "batch_count": len(batches),
        "max_workers": max_workers,
        "model": args.model,
        "dry_run": args.dry_run,
        "written_rows": 0 if args.dry_run else len(targets),
        "audit_csv": str(audit_path),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
