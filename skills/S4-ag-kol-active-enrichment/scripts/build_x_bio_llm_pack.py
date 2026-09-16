from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

SYSTEM_PROMPT = """你是 Rockbase 的 KOL 资产分析助手。你的任务是为 X 账号生成一条中文内部简介，用于后续定位、筛选和产品匹配。

要求：
- 必须优先基于提供的原始证据
- 允许在不冲突时使用你对稳定知名人物的高置信常识
- 不要复制平台 bio
- 不要写成官样文章或模板句
- 不要夸张吹捧
- 输出必须是一句话中文
- 重点回答：
  - 这个人是谁
  - 主要讲什么
  - 更偏什么表达方式
  - 为什么对 Rockbase 的产品匹配有价值
- 如果证据弱，就保守写，不要脑补
"""


def build_user_prompt(row: dict[str, str]) -> str:
    return f"""请基于以下证据，为该 X 账号生成一条 `账号简介`。

字段：
- 账号ID：{row.get('账号ID', '')}
- 名称：{row.get('频道/作者名称', '')}
- 平台 bio：{row.get('账号简介__平台抓取', '')}
- 平台类目：{row.get('账号类目标签__平台抓取', '')}
- 外链：{row.get('外链__平台抓取', '')}
- 最新活动：{row.get('Latest Activity Proof', '')}
- 当前内部标签：{row.get('账号类目标签', '')}

输出要求：
1. 只输出 JSON
2. JSON 字段必须包含：
   - `账号ID`
   - `账号简介`
   - `confidence`
   - `evidence_used`
3. `账号简介` 只写一句中文
4. 长度尽量控制在 22-48 字
5. 禁止模板化低信息密度表达
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
    review_blocks: list[str] = ["# X Bio LLM Review Pack", "", "## System Prompt", "", SYSTEM_PROMPT, ""]

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
                "账号简介__平台抓取": row.get("账号简介__平台抓取", ""),
                "账号类目标签__平台抓取": row.get("账号类目标签__平台抓取", ""),
                "外链__平台抓取": row.get("外链__平台抓取", ""),
                "Latest Activity Proof": row.get("Latest Activity Proof", ""),
                "账号类目标签": row.get("账号类目标签", ""),
            },
        }
        jsonl_lines.append(json.dumps(item, ensure_ascii=False))

        review_blocks.extend(
            [
                f"## Row {idx} {account_id}",
                "",
                f"- 名称：{row.get('频道/作者名称', '')}",
                f"- 平台 bio：{row.get('账号简介__平台抓取', '')}",
                f"- 平台类目：{row.get('账号类目标签__平台抓取', '')}",
                f"- 外链：{row.get('外链__平台抓取', '')}",
                f"- 最新活动：{row.get('Latest Activity Proof', '')}",
                f"- 当前内部标签：{row.get('账号类目标签', '')}",
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
