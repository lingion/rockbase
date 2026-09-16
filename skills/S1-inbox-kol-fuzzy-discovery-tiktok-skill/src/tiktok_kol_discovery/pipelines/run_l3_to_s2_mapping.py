from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from tiktok_kol_discovery.io_utils import read_csv, safe_text, workbench_dir, write_csv, write_json


S2_COLUMNS = [
    "分区",
    "备注",
    "提报人",
    "账号ID",
    "频道/作者名称",
    "平台",
    "多平台标记",
    "账号链接",
    "语言",
    "博主国家",
    "粉丝数",
    "账号类目标签",
    "账号类目标签__平台抓取",
    "置顶最高播放",
    "近期10条均播",
    "近10条平均ER（按曝光）",
    "近10条平均ER（按粉丝）",
    "rate（USD$)报价",
    "原价",
    "账号简介",
    "账号简介__平台抓取",
    "Sample Content",
    "Latest Activity Proof",
    "粉丝受众",
    "粉丝性别",
    "粉丝年龄",
    "联系方式",
    "联系方式备注",
    "外链__平台抓取",
    "Recommendation",
    "Mail1发出状态",
    "Mail1_Hook",
    "Mail1_Greeting_Name",
    "Mail1_Subject",
    "Mail1_Content V1",
    "Mail1_Content V2",
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Map TikTok Layer2/L3 shortlist CSV into S2 Cold Outreach CSV.")
    parser.add_argument("--input-csv", required=True, help="Path to tiktok_kol_L2_shortlist_*.csv or L3 shortlist CSV")
    parser.add_argument("--run-date", required=True, help="Output date folder under workbench/YYYY-MM-DD")
    parser.add_argument("--batch", default="batch1", help="Batch name, e.g. batch1")
    parser.add_argument("--followers-gate", type=int, default=3000, help="Hard follower floor for S2 export.")
    parser.add_argument("--mirror-to-deliverables", dest="mirror_to_deliverables", action="store_true", default=False)
    parser.add_argument("--no-mirror-to-deliverables", dest="mirror_to_deliverables", action="store_false")
    return parser.parse_args()


def _format_sample_content(row: dict[str, str]) -> str:
    top_url = safe_text(row.get("top_content_url"))
    sample_contents = safe_text(row.get("sample_contents"))
    if top_url and sample_contents:
        return f"{top_url} - {sample_contents}"
    return top_url or sample_contents


def _to_int(value: str) -> int:
    try:
        return int(str(value or "0").replace(",", "").strip())
    except ValueError:
        return 0


def _map_row(row: dict[str, str]) -> dict[str, str]:
    return {
        "分区": "",
        "备注": "",
        "提报人": "",
        "账号ID": safe_text(row.get("creator_handle")),
        "频道/作者名称": safe_text(row.get("display_name")),
        "平台": "TikTok",
        "多平台标记": "",
        "账号链接": safe_text(row.get("profile_url")),
        "语言": safe_text(row.get("primary_language")),
        "博主国家": safe_text(row.get("country_inferred")),
        "粉丝数": safe_text(row.get("followers_count")),
        "账号类目标签": "",
        "账号类目标签__平台抓取": safe_text(row.get("content_tags_or_hashtags")),
        "置顶最高播放": safe_text(row.get("max_views")),
        "近期10条均播": "",
        "近10条平均ER（按曝光）": "",
        "近10条平均ER（按粉丝）": "",
        "rate（USD$)报价": "",
        "原价": "",
        "账号简介": "",
        "账号简介__平台抓取": safe_text(row.get("bio")),
        "Sample Content": _format_sample_content(row),
        "Latest Activity Proof": safe_text(row.get("top_content_url")),
        "粉丝受众": "",
        "粉丝性别": "",
        "粉丝年龄": "",
        "联系方式": safe_text(row.get("contact_value")),
        "联系方式备注": safe_text(row.get("contact_note")),
        "外链__平台抓取": safe_text(row.get("external_links")),
        "Recommendation": safe_text(row.get("decision_reason")) or safe_text(row.get("recommended_action")),
        "Mail1发出状态": "",
        "Mail1_Hook": "",
        "Mail1_Greeting_Name": "",
        "Mail1_Subject": "",
        "Mail1_Content V1": "",
        "Mail1_Content V2": "",
    }


def _followers_sort_key(row: dict[str, str]) -> tuple[int, str]:
    return (-_to_int(row.get("粉丝数")), safe_text(row.get("账号ID")))


def _row_meets_s2_followers_gate(row: dict[str, str], *, followers_gate: int) -> bool:
    return _to_int(row.get("followers_count")) >= followers_gate


def _row_is_org_like(row: dict[str, str]) -> bool:
    llm_entity_type = safe_text(row.get("llm_entity_type"))
    llm_decision = safe_text(row.get("llm_decision"))
    risk_flags = safe_text(row.get("account_risk_flags"))
    final_decision = safe_text(row.get("final_decision"))

    if llm_entity_type == "org_or_media":
        return True
    if llm_decision == "drop" and "org_keyword:" in risk_flags:
        return True
    if "org_keyword:" in risk_flags and final_decision != "keep":
        return True
    return False


def _deliverables_dir(skill_root: Path) -> Path:
    return skill_root / "deliverables"


def _deliverable_filename(run_date: str, batch: str) -> str:
    return f"【S2_cold】{run_date}_tiktok_kol_S2_{batch}.csv"


def main() -> int:
    args = _parse_args()
    input_csv = Path(args.input_csv).expanduser().resolve()
    shortlist_rows = read_csv(input_csv)
    shortlisted = [
        row
        for row in shortlist_rows
        if (safe_text(row.get("recommended_action")) in {"keep", "review"} or "recommended_action" not in row)
        and _row_meets_s2_followers_gate(row, followers_gate=args.followers_gate)
        and not _row_is_org_like(row)
    ]
    mapped_rows = [_map_row(row) for row in shortlisted]
    mapped_rows.sort(key=_followers_sort_key)

    wb_dir = workbench_dir(args.run_date)
    skill_root = Path(__file__).resolve().parents[3]
    wb_csv = wb_dir / f"tiktok_kol_S2_cold_{args.batch}_{args.run_date}.csv"
    write_csv(wb_csv, mapped_rows, preferred_fields=S2_COLUMNS)

    if args.mirror_to_deliverables:
        deliverables_dir = _deliverables_dir(skill_root) / args.run_date
        deliverables_dir.mkdir(parents=True, exist_ok=True)
        deliverable_csv = deliverables_dir / _deliverable_filename(args.run_date, args.batch)
        shutil.copy2(wb_csv, deliverable_csv)
        write_json(
            wb_dir / f"tiktok_kol_S2_cold_{args.batch}_{args.run_date}.json",
            {
                "input_csv": str(input_csv),
                "output_csv": str(wb_csv),
                "deliverable_csv": str(deliverable_csv),
                "rows": len(mapped_rows),
            },
        )
    else:
        write_json(
            wb_dir / f"tiktok_kol_S2_cold_{args.batch}_{args.run_date}.json",
            {
                "input_csv": str(input_csv),
                "output_csv": str(wb_csv),
                "deliverable_csv": "",
                "rows": len(mapped_rows),
            },
        )
    print(wb_csv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
