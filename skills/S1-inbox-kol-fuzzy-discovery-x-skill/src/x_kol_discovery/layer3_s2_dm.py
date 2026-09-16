from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from x_kol_discovery.io_utils import backup_csv_if_exists, read_csv, safe_text, write_csv


DM_FILL_REQUIRED_COLUMNS = [
    "Mail1_Hook",
    "Mail1_Greeting_Name",
    "Mail1_Subject",
    "Mail1_Content V1",
    "Mail1_Content V2",
]


DEFAULT_WORKFLOW_CONFIG: dict[str, str] = {
    "workflow_name": "OpenClaw early access",
    "mail_body_version": "legacy",
    "subject_template": "{display_name} x OpenClaw early access",
    "subject_template_en": "{display_name} x OpenClaw early access",
    "subject_template_zh": "{display_name}｜合作沟通",
    "body_template": """Hi {greeting_name},

This is Annabel — I run a growth agency helping AI products scale on X and other platforms. {hook}

I'd love to put a new product on your radar: a cloud phone built for OpenClaw — giving AI agents an always-on mobile environment to run apps, automate tasks, and interact with the mobile ecosystem 24/7, no physical device needed.


Here's the exciting part — next week we're about to launch and handpicking a tiny group of top creators for exclusive early access before it goes public. 🚀 You'd be among the very first to try it and share your genuine take with your audience. We're only extending this to creators we truly believe in — and you're one of them.


Beyond this launch, we work with multiple AI products planning long-term partnerships with consistent campaigns. I'd love to build a stable, preferential partnership with you across all of them.


Drop me a line here or on WhatsApp: [+1(515)4518184] — would love to chat! 🙌""",
    "body_template_en": """Hi {greeting_name},

This is Annabel — I run a growth agency helping AI products scale on X and other platforms. {hook}

I'd love to put a new product on your radar: a cloud phone built for OpenClaw — giving AI agents an always-on mobile environment to run apps, automate tasks, and interact with the mobile ecosystem 24/7, no physical device needed.


Here's the exciting part — next week we're about to launch and handpicking a tiny group of top creators for exclusive early access before it goes public. 🚀 You'd be among the very first to try it and share your genuine take with your audience. We're only extending this to creators we truly believe in — and you're one of them.


Beyond this launch, we work with multiple AI products planning long-term partnerships with consistent campaigns. I'd love to build a stable, preferential partnership with you across all of them.


Drop me a line here or on WhatsApp: [+1(515)4518184] — would love to chat! 🙌""",
    "body_template_zh": """{greeting_name}，你好：

我是 Annabel，来自 Rockbase。我们长期帮助 AI 产品和合适的创作者建立合作。之所以联系你，是因为{hook}

最近我们在推进一款 AI 产品的合作沟通。它的核心能力，是为 AI Agent 提供一个可长期在线运行的云端手机环境，让移动端应用和工作流可以在没有实体设备的情况下持续执行。

目前我们正在小范围接触一批匹配度高的创作者，想优先沟通是否有进一步合作的可能。

如果你方便的话，想先请你发我以下信息：
- 你目前主要在运营的社媒账号链接
- 最新的 media kit / 数据包
- 各平台当前合作报价，尤其是 dedicated 和 integration 的价格

如果你更习惯用 WhatsApp，也可以直接联系我：+1(515)4518184。""",
}


HOOK_GUIDANCE = [
    "One sentence only.",
    "Explain why this creator is a fit.",
    "Ground it only in category, handle, display name, and bio fields already present in the row.",
    "Keep it specific, believable, and concise.",
    "Do not invent a specific post, video, thread, or metric you did not read.",
]


GREETING_GUIDANCE = [
    "Real person: use the most natural first-name style greeting.",
    "Brand, org, media, channel, or company account: append Team.",
    "Personal handle-like brands can stay as-is.",
    "Do not keep role descriptions, emoji, or extra suffix text in the greeting.",
]


def ensure_dm_columns(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    for row in rows:
        for column in DM_FILL_REQUIRED_COLUMNS:
            row.setdefault(column, "")
    return rows


def should_fill_row(row: dict[str, str], overwrite_existing: bool) -> bool:
    if overwrite_existing:
        return True
    return not (
        safe_text(row.get("Mail1_Greeting_Name"))
        and safe_text(row.get("Mail1_Hook"))
        and safe_text(row.get("Mail1_Content V1"))
    )


def load_workflow_config(path: Path | None) -> dict[str, str]:
    config = dict(DEFAULT_WORKFLOW_CONFIG)
    if path is None:
        return config
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("workflow config must be a JSON object")
    for key in (
        "workflow_name",
        "mail_body_version",
        "subject_template",
        "subject_template_en",
        "subject_template_zh",
        "body_template",
        "body_template_en",
        "body_template_zh",
    ):
        value = loaded.get(key)
        if isinstance(value, str) and value.strip():
            config[key] = value
    return config


def resolve_language_route(row: dict[str, str]) -> str:
    language = safe_text(row.get("语言")).lower()
    if language.startswith("中文"):
        return "zh"
    return "en"


def build_subject(display_name: str, workflow_config: dict[str, str] | None = None, language_route: str = "en") -> str:
    workflow = workflow_config or DEFAULT_WORKFLOW_CONFIG
    subject_name = safe_text(display_name)
    if not subject_name:
        subject_name = "Creator"
    if language_route == "zh":
        template = safe_text(workflow.get("subject_template_zh")) or safe_text(workflow.get("subject_template"))
    else:
        template = safe_text(workflow.get("subject_template_en")) or safe_text(workflow.get("subject_template"))
    if not template:
        template = DEFAULT_WORKFLOW_CONFIG["subject_template"]
    return template.format(
        display_name=subject_name,
        workflow_name=safe_text(workflow.get("workflow_name")) or DEFAULT_WORKFLOW_CONFIG["workflow_name"],
    )


def render_mail1_content(
    greeting_name: str,
    hook: str,
    workflow_config: dict[str, str] | None = None,
    language_route: str = "en",
) -> str:
    workflow = workflow_config or DEFAULT_WORKFLOW_CONFIG
    if language_route == "zh":
        raw_template = workflow.get("body_template_zh") or workflow.get("body_template")
    else:
        raw_template = workflow.get("body_template_en") or workflow.get("body_template")
    template = str(raw_template) if raw_template else DEFAULT_WORKFLOW_CONFIG["body_template"]
    return template.format(
        greeting_name=safe_text(greeting_name),
        hook=safe_text(hook),
    )


def build_manifest_row(row_number: int, row: dict[str, str], workflow_config: dict[str, str] | None = None) -> dict[str, Any]:
    workflow = workflow_config or DEFAULT_WORKFLOW_CONFIG
    language_route = resolve_language_route(row)
    return {
        "row_number": row_number,
        "账号ID": safe_text(row.get("账号ID")),
        "频道/作者名称": safe_text(row.get("频道/作者名称")),
        "语言": safe_text(row.get("语言")),
        "账号类目标签": safe_text(row.get("账号类目标签")),
        "账号简介": safe_text(row.get("账号简介")),
        "账号简介__平台抓取": safe_text(row.get("账号简介__平台抓取")),
        "existing_Mail1_Greeting_Name": safe_text(row.get("Mail1_Greeting_Name")),
        "existing_Mail1_Hook": safe_text(row.get("Mail1_Hook")),
        "existing_Mail1_Content V1": safe_text(row.get("Mail1_Content V1")),
        "llm_tasks": {
            "Mail1_Greeting_Name": GREETING_GUIDANCE,
            "Mail1_Hook": HOOK_GUIDANCE,
        },
        "language_route_rule": "If `语言` is 中文, write Chinese DM. For English and all other languages, write English DM.",
        "language_route": language_route,
        "workflow_name": safe_text(workflow.get("workflow_name")),
        "body_rule": "Mail1_Content V1 must use the configured body template with only greeting_name and hook substituted.",
    }


def build_conversation_manifest(
    rows: list[dict[str, str]],
    *,
    input_csv: Path,
    workflow_config: dict[str, str] | None = None,
    start_row: int = 1,
    end_row: int = 0,
    limit: int = 0,
    overwrite_existing: bool = False,
) -> dict[str, Any]:
    workflow = workflow_config or DEFAULT_WORKFLOW_CONFIG
    selected: list[dict[str, Any]] = []
    picked = 0
    for index, row in enumerate(rows, start=1):
        if index < start_row:
            continue
        if end_row and index > end_row:
            continue
        if not should_fill_row(row, overwrite_existing):
            continue
        selected.append(build_manifest_row(index, row, workflow))
        picked += 1
        if limit and picked >= limit:
            break
    return {
        "mode": "conversation_llm",
        "input_csv": str(input_csv),
        "workflow_name": safe_text(workflow.get("workflow_name")),
        "mail_body_version": safe_text(workflow.get("mail_body_version")),
        "rows_selected": len(selected),
        "rows": selected,
        "configured_body_template": workflow.get("body_template", DEFAULT_WORKFLOW_CONFIG["body_template"]),
    }


def load_fills_json(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and "rows" in payload:
        payload = payload["rows"]
    if not isinstance(payload, list):
        raise ValueError("fills json must be a list or a dict containing a rows list")
    normalized: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError("each fill entry must be an object")
        row_number = int(item.get("row_number") or 0)
        if row_number <= 0:
            raise ValueError("each fill entry must include a positive row_number")
        normalized.append(item)
    return normalized


def apply_dm_fills(
    *,
    input_csv: Path,
    fills: list[dict[str, Any]],
    run_date: str,
    workflow_config: dict[str, str] | None = None,
    output_csv: Path | None = None,
    overwrite_existing: bool = False,
) -> dict[str, Any]:
    workflow = workflow_config or DEFAULT_WORKFLOW_CONFIG
    rows = ensure_dm_columns(read_csv(input_csv))
    backup_path = backup_csv_if_exists(input_csv, run_date) if output_csv is None or output_csv == input_csv else None
    fill_map = {int(item["row_number"]): item for item in fills}
    rows_updated = 0
    for index, row in enumerate(rows, start=1):
        item = fill_map.get(index)
        if not item:
            continue
        if not should_fill_row(row, overwrite_existing):
            continue
        greeting_name = safe_text(item.get("Mail1_Greeting_Name"))
        hook = safe_text(item.get("Mail1_Hook"))
        if not greeting_name or not hook:
            raise ValueError(f"row {index} is missing Mail1_Greeting_Name or Mail1_Hook")
        language_route = resolve_language_route(row)
        row["Mail1_Greeting_Name"] = greeting_name
        row["Mail1_Hook"] = hook
        row["Mail1_Subject"] = safe_text(item.get("Mail1_Subject")) or build_subject(
            safe_text(row.get("频道/作者名称")) or greeting_name,
            workflow,
            language_route=language_route,
        )
        row["Mail1_Content V1"] = safe_text(item.get("Mail1_Content V1")) or render_mail1_content(
            greeting_name,
            hook,
            workflow,
            language_route=language_route,
        )
        if "Mail1_Content V2" in item:
            row["Mail1_Content V2"] = safe_text(item.get("Mail1_Content V2"))
        rows_updated += 1
    destination = output_csv or input_csv
    write_csv(destination, rows)
    return {
        "input_csv": str(input_csv),
        "output_csv": str(destination),
        "rows_updated": rows_updated,
        "backup_path": str(backup_path) if backup_path else "",
    }
