from __future__ import annotations

import argparse
import csv
import importlib.util
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
HELPER_PATH = BASE_DIR / "fill_x_account_category_and_bio.py"


def load_helper_module():
    spec = importlib.util.spec_from_file_location("fill_x_account_category_and_bio", HELPER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


helper = load_helper_module()
CATEGORY_POOL = helper.CATEGORY_POOL
clean_text = helper.clean_text
infer_categories = helper.infer_categories
format_categories = helper.format_categories


CATEGORY_TO_SECTION = {
    "AI工具": "AI Productivity",
    "AI教程": "AI Education",
    "AI资讯": "AI Education",
    "AI生产力": "AI Productivity",
    "AI自动化": "AI Productivity",
    "AI办公效率": "AI Productivity",
    "AI商业增长": "AI Business",
    "AI创业": "AI Business",
    "AI设计创意": "AI Creator",
    "AI视频创作": "AI Creator",
    "AI编程开发": "AI Builder",
    "AI产品测评": "AI Review",
    "科技资讯": "Tech Review",
    "技术解析": "Tech Review",
    "软件工具": "Tech Review",
    "SaaS评测": "Tech Review",
    "消费科技": "Tech Review",
    "数码硬件": "Tech Review",
    "摄影器材": "Tech Review",
    "视频剪辑": "Creator Workflow",
    "教育学习": "Learning & Work",
    "学习方法": "Learning & Work",
    "知识管理": "Learning & Work",
    "职场成长": "Learning & Work",
    "团队协作": "Learning & Work",
    "商业运营": "Business & Finance",
    "投资人": "Business & Finance",
    "网赚副业": "Business & Finance",
    "加密Web3": "Business & Finance",
    "生活方式": "Creator Lifestyle",
    "自媒体运营": "Creator Workflow",
    "游戏内容": "Creator Lifestyle",
    "数据分析": "Specialist Track",
    "法律学习": "Specialist Track",
    "DIY创客": "Creator Workflow",
    "口播表达": "Creator Workflow",
    "金融投资": "Business & Finance",
    "网络安全": "Specialist Track",
    "喜剧娱乐": "Creator Lifestyle",
}


CATEGORY_TO_TOPICS = {
    "AI工具": ["AI_Tools"],
    "AI教程": ["AI_Tools", "Education"],
    "AI资讯": ["AI_Tools", "General_Tech"],
    "AI生产力": ["AI_Tools", "Productivity"],
    "AI自动化": ["AI_Tools", "Productivity", "Office_Workflow"],
    "AI办公效率": ["AI_Tools", "Office_Workflow", "Productivity"],
    "AI商业增长": ["AI_Tools", "Founder_Operations"],
    "AI创业": ["AI_Tools", "Founder_Operations"],
    "AI设计创意": ["AI_Tools", "Content_Creation"],
    "AI视频创作": ["AI_Tools", "Video_Creation", "Content_Creation"],
    "AI编程开发": ["Developer_AI", "AI_Tools"],
    "AI产品测评": ["AI_Tools", "SaaS_Review"],
    "科技资讯": ["General_Tech"],
    "技术解析": ["General_Tech"],
    "软件工具": ["SaaS_Review", "Productivity"],
    "SaaS评测": ["SaaS_Review"],
    "消费科技": ["General_Tech", "Hardware_Gadgets"],
    "数码硬件": ["Hardware_Gadgets"],
    "摄影器材": ["Filming_Camera", "Hardware_Gadgets"],
    "视频剪辑": ["Video_Creation", "Content_Creation"],
    "教育学习": ["Education"],
    "学习方法": ["Study_Hacks", "Education"],
    "知识管理": ["Knowledge_Management", "Productivity"],
    "职场成长": ["Career_Development"],
    "团队协作": ["Team_Collaboration", "Office_Workflow"],
    "商业运营": ["Founder_Operations"],
    "投资人": ["Founder_Operations"],
    "网赚副业": ["Make_Money_Online"],
    "加密Web3": ["Crypto_Web3"],
    "生活方式": ["Lifestyle_Student"],
    "自媒体运营": ["Content_Creation"],
    "游戏内容": ["Content_Creation"],
    "数据分析": ["Knowledge_Management", "General_Tech"],
    "法律学习": ["Education"],
    "DIY创客": ["Hardware_Gadgets", "Content_Creation"],
    "口播表达": ["Content_Creation"],
    "金融投资": ["Founder_Operations"],
    "网络安全": ["Developer_AI", "General_Tech"],
    "喜剧娱乐": ["Content_Creation"],
}


def add_tag(bucket: list[str], value: str, limit: int) -> None:
    if value and value not in bucket and len(bucket) < limit:
        bucket.append(value)


def join_tags(values: list[str]) -> str:
    return "|".join(values)


def parse_existing_categories(raw: str) -> list[str]:
    parts = [x.strip() for x in str(raw or "").split("/") if x.strip()]
    if parts and all(p in CATEGORY_POOL for p in parts):
        return parts[:2]
    return []


def extract_price_value(text: str) -> float | None:
    text = str(text or "")
    m = re.search(r"\$?\s*([0-9]{2,6}(?:,[0-9]{3})*(?:\.[0-9]+)?)", text)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except Exception:
        return None


def has_any(text: str, keywords: list[str]) -> bool:
    return any(k in text for k in keywords)


def choose_categories(row: dict[str, str]) -> list[str]:
    existing = parse_existing_categories(row.get("账号类目标签", ""))
    if existing:
        return existing

    bio = str(row.get("账号简介", "") or "")
    raw_bio = str(row.get("账号简介__平台抓取", "") or "")
    raw_cat = str(row.get("账号类目标签__平台抓取", "") or "")
    categories = infer_categories(f"{bio} {raw_bio}", raw_cat)
    return categories[:2]


def derive_topics(text: str, categories: list[str]) -> list[str]:
    topics: list[str] = []
    for category in categories:
        for topic in CATEGORY_TO_TOPICS.get(category, []):
            add_tag(topics, topic, 4)

    if has_any(text, ["agent", "api", "developer", "coding", "code", "编程", "开发"]):
        add_tag(topics, "Developer_AI", 4)
    if has_any(text, ["tutorial", "how to", "guide", "step", "教程", "教学", "指南"]):
        add_tag(topics, "Education", 4)
    if has_any(text, ["workflow", "efficiency", "productivity", "office", "效率", "工作流", "协作"]):
        add_tag(topics, "Productivity", 4)
    if has_any(text, ["review", "compare", "comparison", "评测", "测评", "软件工具"]):
        add_tag(topics, "SaaS_Review", 4)
    if has_any(text, ["creator", "design", "video", "剪辑", "创作", "reels"]):
        add_tag(topics, "Content_Creation", 4)
    if has_any(text, ["tech", "technology", "科技", "数码", "gadgets", "hardware"]):
        add_tag(topics, "General_Tech", 4)
    return topics


def derive_scenarios(text: str, topics: list[str]) -> list[str]:
    scenarios: list[str] = []
    if has_any(text, ["tutorial", "how to", "guide", "step", "教程", "教学", "指南"]):
        add_tag(scenarios, "Tutorial_Explainer", 4)
    if has_any(text, ["screen", "record", "demo", "tool", "app", "software", "录屏", "演示", "工具"]):
        add_tag(scenarios, "Screen_Record_Friendly", 4)
        add_tag(scenarios, "Web_Demo", 4)
    if has_any(text, ["before", "after", "compare", "review", "评测", "对比"]):
        add_tag(scenarios, "Before_After_Comparison", 4)
    if has_any(text, ["meeting", "team", "collaboration", "协作", "会议"]):
        add_tag(scenarios, "Meeting_Workflow", 4)
        add_tag(scenarios, "Team_Project_Collaboration", 4)
    if has_any(text, ["student", "study", "exam", "校园", "备考", "学生"]):
        add_tag(scenarios, "Student_Use_Case", 4)
    if has_any(text, ["creator", "design", "editing", "剪辑", "创作", "camera"]):
        add_tag(scenarios, "Creator_Workflow", 4)
    if has_any(text, ["research", "summary", "knowledge", "知识库", "研究", "总结"]):
        add_tag(scenarios, "Knowledge_Base", 4)
        add_tag(scenarios, "Research_Summary", 4)
    if "Founder_Operations" in topics:
        add_tag(scenarios, "Executive_Use_Case", 4)
    return scenarios


def derive_audience(text: str, topics: list[str]) -> list[str]:
    audience: list[str] = []
    if has_any(text, ["student", "study", "campus", "exam", "学生", "备考"]):
        add_tag(audience, "Students", 3)
    if has_any(text, ["founder", "ceo", "builder", "startup", "business", "创业"]):
        add_tag(audience, "Founders", 3)
    if has_any(text, ["manager", "executive", "leader", "team", "管理", "高管"]):
        add_tag(audience, "Managers", 3)
    if has_any(text, ["creator", "design", "video", "content", "创作者", "博主"]):
        add_tag(audience, "Creators", 3)
    if has_any(text, ["developer", "engineer", "api", "coding", "程序", "开发"]):
        add_tag(audience, "Developers", 3)
    if has_any(text, ["teacher", "education", "classroom", "教师", "教育"]):
        add_tag(audience, "Educators", 3)
    if has_any(text, ["research", "scientist", "benchmark", "研究"]):
        add_tag(audience, "Researchers", 3)
    if not audience:
        if "Hardware_Gadgets" in topics:
            add_tag(audience, "General_Consumers", 3)
        else:
            add_tag(audience, "Knowledge_Workers", 3)
    return audience


def derive_narrative(text: str, topics: list[str]) -> list[str]:
    narrative: list[str] = []
    if has_any(text, ["tutorial", "how to", "step", "教程", "教学"]):
        add_tag(narrative, "Tutorial_Step_By_Step", 3)
    if has_any(text, ["review", "compare", "comparison", "评测", "对比"]):
        add_tag(narrative, "Review_Comparison", 3)
    if has_any(text, ["solve", "problem", "workflow", "效率", "工作流"]):
        add_tag(narrative, "Problem_Solution", 3)
    if has_any(text, ["thought", "insight", "opinion", "strategy", "观点", "策略"]):
        add_tag(narrative, "Thought_Leadership", 3)
    if has_any(text, ["expert", "consultant", "founder", "导师", "顾问"]):
        add_tag(narrative, "Authority_Expert", 3)
    if has_any(text, ["demo", "hands-on", "实测", "演示"]):
        add_tag(narrative, "Hands_On_Demo", 3)
    if not narrative:
        add_tag(narrative, "Peer_Sharing", 3)
    return narrative


def derive_platform_fit(platform: str, multi: str) -> list[str]:
    tags: list[str] = []
    platform = str(platform or "")
    multi = str(multi or "")
    if platform == "YouTube":
        add_tag(tags, "YouTube_Longform", 2)
    elif platform == "TikTok":
        add_tag(tags, "TikTok_Shortform", 2)
    elif platform == "Instagram":
        add_tag(tags, "Instagram_Reels", 2)
    elif platform == "X":
        add_tag(tags, "X_Opinion", 2)
    if multi.strip():
        add_tag(tags, "Multi_Platform", 2)
    return tags


def derive_market(language: str, country: str) -> list[str]:
    tags: list[str] = []
    language = str(language or "")
    country = str(country or "")
    if "英语" in language:
        add_tag(tags, "English_Market", 3)
    if "多语言" in language or "/" in language:
        add_tag(tags, "Multilingual_Market", 3)
    if "阿拉伯" in language or country in {"阿联酋", "沙特阿拉伯"}:
        add_tag(tags, "MENA_Arabic", 3)
    if country in {"美国", "英国", "加拿大", "澳大利亚"}:
        add_tag(tags, "US_UK_CA_AU", 3)
    if country in {"印度", "巴基斯坦"}:
        add_tag(tags, "India_Pakistan", 3)
    if country in {"法国", "德国", "意大利", "西班牙", "荷兰", "瑞典", "波兰"}:
        add_tag(tags, "EU_Mix", 3)
    return tags


def derive_commercial(row: dict[str, str], topics: list[str], scenarios: list[str], evidence_text: str) -> list[str]:
    tags: list[str] = []
    price = extract_price_value(row.get("rate（USD$)报价", "") or row.get("原价", ""))
    if price is not None:
        if price <= 500:
            add_tag(tags, "Budget_Friendly", 3)
        elif price <= 3000:
            add_tag(tags, "Mid_Tier_Efficient", 3)
        else:
            add_tag(tags, "Premium_Priced", 3)
    else:
        add_tag(tags, "Low_Data_Visibility", 3)

    if row.get("联系方式", "") or row.get("联系方式备注", ""):
        add_tag(tags, "Likely_Open_To_Brief", 3)
    if "SaaS_Review" in topics or "AI_Tools" in topics or "Content_Creation" in topics:
        add_tag(tags, "Likely_Good_For_Affiliate", 3)
    if "Before_After_Comparison" in scenarios or "Hands_On_Demo" in derive_narrative(evidence_text, topics):
        add_tag(tags, "Good_For_Whitelisting", 3)
    return tags


def derive_risk(text: str, topics: list[str]) -> list[str]:
    tags: list[str] = []
    if "Hardware_Gadgets" in topics:
        add_tag(tags, "Too_Hardware_Heavy", 3)
    if "Filming_Camera" in topics:
        add_tag(tags, "Too_Filming_Heavy", 3)
    if "Video_Creation" in topics:
        add_tag(tags, "Too_Video_Creation_Heavy", 3)
    if "Make_Money_Online" in topics:
        add_tag(tags, "Too_MMO_Heavy", 3)
    if "Developer_AI" in topics and "AI_Tools" not in topics:
        add_tag(tags, "Too_Developer_Heavy", 3)
    if "Crypto_Web3" in topics:
        add_tag(tags, "Crypto_Risk", 3)
    if has_any(text, ["funny", "meme", "entertainment", "joke", "搞笑", "娱乐"]):
        add_tag(tags, "Entertainment_Only", 3)
    return tags


def derive_confidence(row: dict[str, str], categories: list[str]) -> str:
    bio = str(row.get("账号简介", "") or "").strip()
    raw_bio = str(row.get("账号简介__平台抓取", "") or "").strip()
    raw_cat = str(row.get("账号类目标签__平台抓取", "") or "").strip()
    if categories and raw_bio and raw_cat:
        return "A_Explicit"
    if categories and (bio or raw_bio or raw_cat):
        return "B_Inferred"
    return "C_Weak"


def process_csv(path: Path) -> None:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames or []

    for row in rows:
        evidence_text = " || ".join(
            [
                clean_text(str(row.get("账号简介", "") or "")),
                clean_text(str(row.get("账号简介__平台抓取", "") or "")),
                clean_text(str(row.get("账号类目标签__平台抓取", "") or "")),
            ]
        ).lower()
        categories = choose_categories(row)
        category_text = format_categories(categories)
        topics = derive_topics(evidence_text, categories)
        scenarios = derive_scenarios(evidence_text, topics)
        audience = derive_audience(evidence_text, topics)
        narrative = derive_narrative(evidence_text, topics)
        platform_fit = derive_platform_fit(row.get("平台", ""), row.get("多平台标记", ""))
        market = derive_market(row.get("语言", ""), row.get("博主国家", ""))
        commercial = derive_commercial(row, topics, scenarios, evidence_text)
        risk = derive_risk(evidence_text, topics)
        confidence = derive_confidence(row, categories)

        if confidence == "C_Weak":
            add_tag(risk, "Low_Data_Integrity", 3)
        if row.get("平台", "") == "":
            add_tag(risk, "No_Page", 3)

        section = CATEGORY_TO_SECTION.get(categories[0], "Specialist Track") if categories else ""

        row["账号类目标签"] = category_text
        row["Tag_Section"] = section
        row["tag_topics"] = join_tags(topics)
        row["tag_scenarios"] = join_tags(scenarios)
        row["tag_audience"] = join_tags(audience)
        row["tag_narrative"] = join_tags(narrative)
        row["tag_platform_fit"] = join_tags(platform_fit)
        row["tag_market"] = join_tags(market)
        row["tag_commercial"] = join_tags(commercial)
        row["tag_risk"] = join_tags(risk)
        row["tag_confidence"] = confidence

    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"UPDATED {path.name}: {len(rows)} rows")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_paths", nargs="+")
    args = parser.parse_args()
    for item in args.csv_paths:
        process_csv(Path(item))


if __name__ == "__main__":
    main()
