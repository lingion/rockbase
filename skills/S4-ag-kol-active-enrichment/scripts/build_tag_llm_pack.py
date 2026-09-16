from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

SYSTEM_PROMPT = """你是 Rockbase 的 KOL 标签系统助手。你的任务是为账号生成 S4 阶段可复用的分类结果，用于后续筛选、匹配和客户推荐。

要求：
- 必须优先基于提供的证据做判断
- `账号类目标签` 必须使用受控标签池，不允许自由发明
- `账号类目标签` 优先输出单标签；只有确有必要时才输出双标签
- 如果双标签中包含 AI 标签，则 AI 标签必须前置
- `tag_*` 必须是稳定、可筛选、可复用的系统标签
- 证据弱时保守写，并降低置信度
- 只输出 JSON，不输出解释性散文
"""


def build_user_prompt(row: dict[str, str]) -> str:
    return f"""请基于以下证据，为该账号生成 S4 的 `账号类目标签` 与 `tag system` 字段。

字段：
- 账号ID：{row.get('账号ID', '')}
- 名称：{row.get('频道/作者名称', '')}
- 平台：{row.get('平台', '')}
- 当前账号简介：{row.get('账号简介', '')}
- 平台 bio：{row.get('账号简介__平台抓取', '')}
- 平台类目：{row.get('账号类目标签__平台抓取', '')}
- 外链：{row.get('外链__平台抓取', '')}
- 当前 Tag_Section：{row.get('Tag_Section', '')}
- 当前 tag_topics：{row.get('tag_topics', '')}

输出要求：
1. 只输出 JSON
2. JSON 字段必须包含：
   - `账号ID`
   - `账号类目标签`
   - `Tag_Section`
   - `tag_topics`
   - `tag_scenarios`
   - `tag_audience`
   - `tag_narrative`
   - `tag_platform_fit`
   - `tag_market`
   - `tag_commercial`
   - `tag_risk`
   - `tag_confidence`
   - `confidence`
   - `evidence_used`
3. `账号类目标签` 必须符合正式标签池规则
4. 如果证据不足，允许部分字段保守留空，但不得乱写
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--out-jsonl", required=True, type=Path)
    parser.add_argument("--out-review-md", required=True, type=Path)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--start-row", type=int, default=2)
    args = parser.parse_args()

    with args.csv.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    selected = rows[max(args.start_row - 2, 0) :]
    if args.limit > 0:
        selected = selected[: args.limit]

    args.out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    args.out_review_md.parent.mkdir(parents=True, exist_ok=True)

    jsonl_lines: list[str] = []
    review_blocks: list[str] = ["# S4 Tag LLM Review Pack", "", "## System Prompt", "", SYSTEM_PROMPT, ""]

    for idx, row in enumerate(selected, start=args.start_row):
        account_id = str(row.get("账号ID", "") or "").strip()
        item = {
            "custom_id": account_id or f"row_{idx}",
            "system_prompt": SYSTEM_PROMPT,
            "user_prompt": build_user_prompt(row),
            "evidence": {
                "row_number": idx,
                "账号ID": row.get("账号ID", ""),
                "频道/作者名称": row.get("频道/作者名称", ""),
                "平台": row.get("平台", ""),
                "账号简介": row.get("账号简介", ""),
                "账号简介__平台抓取": row.get("账号简介__平台抓取", ""),
                "账号类目标签__平台抓取": row.get("账号类目标签__平台抓取", ""),
                "外链__平台抓取": row.get("外链__平台抓取", ""),
                "Tag_Section": row.get("Tag_Section", ""),
                "tag_topics": row.get("tag_topics", ""),
            },
        }
        jsonl_lines.append(json.dumps(item, ensure_ascii=False))

        review_blocks.extend(
            [
                f"## Row {idx} {account_id}",
                "",
                f"- 名称：{row.get('频道/作者名称', '')}",
                f"- 平台：{row.get('平台', '')}",
                f"- 当前账号简介：{row.get('账号简介', '')}",
                f"- 平台 bio：{row.get('账号简介__平台抓取', '')}",
                f"- 平台类目：{row.get('账号类目标签__平台抓取', '')}",
                f"- 外链：{row.get('外链__平台抓取', '')}",
                "",
                "```text",
                build_user_prompt(row),
                "```",
                "",
            ]
        )

    args.out_jsonl.write_text("\n".join(jsonl_lines) + ("\n" if jsonl_lines else ""), encoding="utf-8")
    args.out_review_md.write_text("\n".join(review_blocks), encoding="utf-8")
    print(json.dumps({"rows": len(selected), "jsonl": str(args.out_jsonl), "review_md": str(args.out_review_md)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
