from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
KNOWN_BIO_OVERRIDES_PATH = BASE_DIR / "references" / "account_bio_known_entity_overrides.json"

CATEGORY_POOL = {
    "AI工具",
    "AI教程",
    "AI资讯",
    "AI生产力",
    "AI自动化",
    "AI办公效率",
    "AI商业增长",
    "AI创业",
    "AI设计创意",
    "AI视频创作",
    "AI编程开发",
    "AI产品测评",
    "科技资讯",
    "技术解析",
    "软件工具",
    "SaaS评测",
    "消费科技",
    "数码硬件",
    "摄影器材",
    "视频剪辑",
    "教育学习",
    "学习方法",
    "知识管理",
    "职场成长",
    "团队协作",
    "商业运营",
    "投资人",
    "网赚副业",
    "加密Web3",
    "生活方式",
    "自媒体运营",
    "游戏内容",
    "数据分析",
    "法律学习",
    "DIY创客",
    "口播表达",
    "金融投资",
    "网络安全",
    "喜剧娱乐",
}


def clean_text(text: str) -> str:
    text = text or ""
    text = re.sub(r"https?://\S+|www\.\S+|t\.co/\S+", " ", text)
    text = re.sub(r"\S+@\S+", " ", text)
    text = re.sub(r"[@#]\w+", " ", text)
    text = text.replace("\n", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def has_any(text: str, keywords: list[str]) -> bool:
    return any(k in text for k in keywords)


def load_known_bio_overrides() -> dict[str, str]:
    if not KNOWN_BIO_OVERRIDES_PATH.exists():
        return {}
    try:
        data = json.loads(KNOWN_BIO_OVERRIDES_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k).strip().lower().lstrip("@"): str(v).strip() for k, v in data.items() if str(v).strip()}


def infer_categories(raw_bio: str, raw_cat: str) -> list[str]:
    bio = clean_text(raw_bio).lower()
    weak = clean_text(raw_cat).lower()
    text = f"{bio} || {weak}"
    categories: list[str] = []

    def add(label: str) -> None:
        if label in CATEGORY_POOL and label not in categories and len(categories) < 2:
            categories.append(label)

    ai_signal = has_any(
        text,
        [
            "ai",
            "aigc",
            "chatgpt",
            "gpt",
            "llm",
            "agent",
            "model",
            "genai",
            "machine learning",
            "ml",
            "人工智能",
            "生成式",
            "大模型",
            "智能体",
        ],
    )
    founder_signal = has_any(text, ["founder", "ceo", "startup", "builder", "building", "build in public", "创业"])
    investor_signal = has_any(text, ["investor", "vc", "angel", "venture", "venture capitalist", "venture partner", "投资"])
    engineer_signal = has_any(
        text,
        ["engineer", "developer", "coding", "code", "api", "ml engineer", "research engineer", "程序", "开发", "编程"],
    )
    research_signal = has_any(
        text, ["research", "researcher", "scientist", "evaluation", "eval", "benchmark", "open science", "研究"]
    )
    growth_signal = has_any(
        text,
        [
            "growth",
            "marketing",
            "marketer",
            "scale",
            "monetiz",
            "revenue",
            "brand",
            "go to market",
            "增长",
            "营销",
            "变现",
            "商业",
        ],
    ) or ("business" in text and has_any(text, ["scale", "market", "marketing", "startup", "product"]))
    tutorial_signal = has_any(
        text, ["tutorial", "how to", "guide", "teaching", "teach", "explained", "lesson", "learn", "教程", "教学", "指南"]
    )
    review_signal = has_any(
        text, ["review", "reviews", "gadgets", "consumer", "ar/vr", "hardware", "device", "smartphone", "评测", "测评"]
    )
    creator_signal = has_any(
        text, ["creator", "content creator", "newsletter", "media", "audience", "posts", "podcast", "自媒体", "博主", "创作者"]
    )
    weak_only = len(clean_text(raw_bio)) < 18
    company_signal = has_any(
        text, ["we are", "company", "labs", "platform", "assistant", "frontier ai", "community building", "official", "官方"]
    )

    if investor_signal:
        add("投资人")
    if has_any(text, ["crypto", "web3", "blockchain", "defi", "nft", "token", "bitcoin", "ethereum"]):
        add("加密Web3")
    if has_any(text, ["security", "cyber", "infosec", "threat", "privacy", "安全", "网络安全"]):
        add("网络安全")
    if has_any(text, ["data science", "data analyst", "analytics", "evaluation", "eval", "benchmark", "数据分析"]) or (
        research_signal and not company_signal
    ):
        add("数据分析")
    if has_any(text, ["law", "legal", "policy", "ethics", "governance", "regulation", "法学", "法律", "合规"]):
        add("法律学习")
    if founder_signal and ai_signal:
        add("AI创业")
    if growth_signal and ai_signal and not weak_only:
        add("AI商业增长")
    if engineer_signal and ai_signal:
        add("AI编程开发")
    if tutorial_signal:
        add("AI教程" if ai_signal else "教育学习")
    if has_any(text, ["productivity", "workflow", "meeting", "notes", "note-taking", "knowledge", "pkm", "office", "效率", "办公", "工作流"]):
        add("AI办公效率" if ai_signal else "知识管理")
    if has_any(text, ["automation", "agent", "n8n", "zapier", "自动化", "智能体"]) and ai_signal:
        add("AI自动化")
    if has_any(text, ["design", "creative", "image", "art", "midjourney", "visual", "canva", "avatar", "设计", "视觉", "绘图"]):
        add("AI设计创意" if ai_signal or has_any(text, ["midjourney", "image generator", "数字人"]) else "自媒体运营")
    if has_any(text, ["video", "editing", "editor", "filmmaking", "youtube", "视频", "剪辑"]) and has_any(
        text, ["ai", "generative", "avatar", "text to video", "video generation", "数字人", "文生视频"]
    ):
        add("AI视频创作")
    if review_signal:
        if ai_signal or has_any(text, ["consumer ai"]):
            add("AI产品测评")
        else:
            add("消费科技")
    if has_any(text, ["news", "analyst", "observer", "commentary", "thought leadership", "insights", "trends", "critic", "资讯", "趋势", "观察"]):
        add("AI资讯" if ai_signal else "科技资讯")
    if creator_signal:
        if has_any(text, ["tool", "tools", "app", "apps", "platform", "product", "工具", "产品"]) and ai_signal:
            add("AI工具")
        elif not ai_signal:
            add("自媒体运营")

    # Non-AI / generic X coverage
    if has_any(text, ["wellness", "traveller", "travel", "lifestyle", "solo traveller", "生活方式", "旅行"]):
        add("生活方式")
    if has_any(text, ["game", "gaming", "esports"]):
        add("游戏内容")
    if has_any(text, ["amazon seller", "fba", "ecom", "e-commerce", "运营", "seller"]):
        add("商业运营")
    if has_any(text, ["coach", "speaker", "commentary", "host", "pod"]):
        add("口播表达")
    if has_any(text, ["finance", "investing", "stock", "macro"]):
        add("金融投资")

    # X-specific corrections
    if company_signal and ai_signal and has_any(text, ["assistant", "platform", "tools", "apps", "frontier ai", "community", "company"]):
        categories = [c for c in categories if c != "数据分析"]
        add("AI工具")
    if founder_signal and not ai_signal and not investor_signal and not engineer_signal:
        categories = [c for c in categories if c != "AI创业"]
    if investor_signal and "投资人" not in categories:
        add("投资人")
    if investor_signal and "AI创业" in categories and not founder_signal:
        categories = [c for c in categories if c != "AI创业"]
    if not ai_signal and "AI商业增长" in categories:
        categories = [c for c in categories if c != "AI商业增长"]
    if weak_only and categories == ["AI工具"]:
        categories = ["AI资讯"] if has_any(weak, ["critic", "academic", "research"]) else categories

    if not categories:
        if has_any(weak, ["engineer", "developer", "ml engineer", "ai engineer", "开发", "编程"]):
            add("AI编程开发" if has_any(weak, ["ai", "ml", "llm"]) else "软件工具")
        elif has_any(weak, ["founder", "product", "builder", "创业"]):
            add("AI创业" if has_any(weak, ["ai", "product"]) else "商业运营")
        elif has_any(weak, ["security", "cyber"]):
            add("网络安全")
        elif has_any(weak, ["academic", "critic", "research"]):
            add("AI资讯" if has_any(weak, ["ai"]) else "科技资讯")
        elif has_any(weak, ["consumer ai", "gadgets", "tech", "科技"]):
            add("AI产品测评" if has_any(weak, ["ai"]) else "消费科技")
        elif has_any(weak, ["investor", "venture", "angel", "vc"]):
            add("投资人")
        elif has_any(weak, ["creator", "content", "博主"]):
            add("AI工具" if has_any(weak, ["ai"]) else "自媒体运营")
        elif has_any(weak, ["ai", "工具"]):
            add("AI工具")

    if not categories:
        add("AI工具" if ai_signal else "科技资讯")

    if len(categories) == 2 and "AI" in categories[1] and "AI" not in categories[0]:
        categories = [categories[1], categories[0]]

    return categories[:2]


def infer_identity(raw_bio: str, categories: list[str]) -> str:
    bio = clean_text(raw_bio).lower()
    if has_any(bio, ["journalist", "reporter", "editor"]):
        return "科技记者"
    if categories and categories[0] == "投资人":
        return "投资人"
    if has_any(bio, ["investor", "vc", "angel", "venture"]):
        return "投资人"
    if has_any(bio, ["professor", "academic", "research scientist", "researcher", "scientist", "研究员", "教授"]):
        return "研究者"
    if has_any(bio, ["founder", "ceo", "cofounder", "builder", "startup", "创业"]):
        return "创业者"
    if has_any(bio, ["indie hacker", "indie dev", "solo founder", "solo builder"]):
        return "独立开发者"
    if has_any(bio, ["engineer", "developer", "programmer", "ml engineer", "research engineer", "开发", "编程"]):
        return "开发者"
    if has_any(bio, ["writer", "newsletter", "author", "columnist"]):
        return "作者"
    if has_any(bio, ["creator", "youtuber", "content creator", "podcaster", "博主", "创作者"]):
        return "创作者"
    if has_any(bio, ["security", "privacy", "infosec", "cyber"]):
        return "安全研究者"
    if has_any(bio, ["official", "labs", "company", "platform", "team", "community", "we "]):
        return "机构账号"
    if categories and categories[0] in {"消费科技", "数码硬件", "AI产品测评", "SaaS评测"}:
        return "测评型账号"
    if categories and categories[0] in {"AI资讯", "科技资讯", "技术解析"}:
        return "观察型账号"
    return "AI从业者"


def infer_topic_phrase(categories: list[str]) -> str:
    primary = categories[0] if categories else "AI工具"
    mapping = {
        "AI工具": "AI 工具与产品应用",
        "AI教程": "AI 工具教学与上手方法",
        "AI资讯": "AI 趋势、产品动态与行业观点",
        "AI生产力": "AI 提效与工作流优化",
        "AI自动化": "AI 自动化与 agent 工作流",
        "AI办公效率": "AI 办公提效与知识工作流",
        "AI商业增长": "AI 产品增长、营销与商业落地",
        "AI创业": "AI 创业、产品构建与创始人视角",
        "AI设计创意": "AI 视觉生成与创意工具",
        "AI视频创作": "AI 视频生成与内容生产",
        "AI编程开发": "AI 编程、agent 与开发者工具",
        "AI产品测评": "AI 产品体验与功能评测",
        "科技资讯": "科技动态与产品观察",
        "技术解析": "技术原理与趋势解读",
        "软件工具": "软件工具与应用效率",
        "SaaS评测": "SaaS 工具测评与选型",
        "消费科技": "消费科技与数码产品体验",
        "数码硬件": "数码硬件与设备体验",
        "摄影器材": "摄影器材与拍摄工具",
        "视频剪辑": "视频剪辑与内容制作",
        "教育学习": "教育学习与知识分享",
        "学习方法": "学习方法与知识吸收",
        "知识管理": "知识管理与信息整理",
        "职场成长": "职业发展与职场成长",
        "团队协作": "团队协作与工作配合",
        "商业运营": "商业运营与增长方法",
        "投资人": "投资判断、赛道观察与创业趋势",
        "网赚副业": "副业增长与变现路径",
        "加密Web3": "加密与 Web3 相关内容",
        "数据分析": "数据分析与模型评估",
        "网络安全": "安全、隐私与风险议题",
        "金融投资": "金融与投资观察",
        "法律学习": "法律、政策与合规议题",
        "生活方式": "生活方式与日常表达",
        "自媒体运营": "自媒体运营与内容增长",
        "游戏内容": "游戏与互动娱乐内容",
        "DIY创客": "DIY 创作与动手实践",
        "口播表达": "观点输出与口播表达",
        "喜剧娱乐": "娱乐化表达与轻松内容",
    }
    return mapping.get(primary, "科技动态与产品观察")


def infer_style_phrase(raw_bio: str, categories: list[str]) -> str:
    bio = clean_text(raw_bio).lower()
    if has_any(bio, ["tutorial", "how to", "guide", "teach", "lessons", "explained", "教程", "教学"]):
        return "教程拆解"
    if has_any(bio, ["review", "reviews", "gadget", "consumer", "hands-on", "评测", "测评"]):
        return "体验评测"
    if has_any(bio, ["insights", "opinion", "commentary", "thought", "critic", "analysis", "观点", "评论", "分析"]):
        return "观点解读"
    if has_any(bio, ["founder", "scale", "launch", "growth", "market", "增长", "营销"]):
        return "业务实战"
    if has_any(bio, ["engineer", "developer", "api", "agent", "builder", "open source", "开发", "编程"]):
        return "技术实践"
    if categories and categories[0] in {"AI视频创作", "AI设计创意", "自媒体运营"}:
        return "创作演示"
    if categories and categories[0] in {"AI资讯", "科技资讯", "技术解析"}:
        return "趋势观察"
    return "工具分享"


def infer_matching_phrase(raw_bio: str, categories: list[str]) -> str:
    bio = clean_text(raw_bio).lower()
    primary = categories[0] if categories else ""
    if primary in {"AI产品测评", "消费科技", "SaaS评测"}:
        return "适合产品测评与功能种草"
    if primary in {"AI教程", "AI办公效率", "AI自动化", "AI编程开发"}:
        return "适合工具教育与使用场景展示"
    if primary in {"AI商业增长", "商业运营", "投资人", "AI创业"}:
        return "适合创业、增长与产品叙事类产品"
    if primary in {"AI视频创作", "AI设计创意"}:
        return "适合创意工具与内容工作流类产品"
    if has_any(bio, ["newsletter", "podcast", "media", "journalist", "reporter"]):
        return "适合趋势解读与话题传播"
    return ""


def extract_raw_anchor(raw_bio: str) -> str:
    bio = clean_text(raw_bio)
    lowered = bio.lower()
    mapping = [
        (["newsletter"], "newsletter"),
        (["podcast", "podcaster"], "播客"),
        (["open source"], "开源"),
        (["indie hacker", "indie dev"], "独立开发"),
        (["professor"], "学术研究"),
        (["journalist", "reporter", "editor"], "科技媒体"),
        (["founder", "cofounder", "ceo"], "创业"),
        (["investor", "vc", "angel"], "投资"),
        (["engineer", "developer"], "开发"),
        (["researcher", "research scientist", "scientist"], "研究"),
    ]
    for keys, label in mapping:
        if has_any(lowered, keys):
            return label
    return ""


def build_bio(handle: str, raw_bio: str, raw_cat: str, categories: list[str], known_overrides: dict[str, str]) -> str:
    normalized = str(handle or "").strip().lower().lstrip("@")
    if normalized in known_overrides:
        return known_overrides[normalized]

    identity = infer_identity(raw_bio, categories)
    topic = infer_topic_phrase(categories)
    style = infer_style_phrase(raw_bio, categories)
    matching = infer_matching_phrase(raw_bio, categories)
    raw_anchor = extract_raw_anchor(raw_bio or raw_cat)
    raw_clean = clean_text(raw_bio)
    weak_only = len(raw_clean) < 18

    if weak_only:
        if raw_anchor:
            return f"{identity}，主要讨论{topic}，原始信号更接近{raw_anchor}。"
        return f"{identity}，主要讨论{topic}。"
    else:
        variants = [
            f"{identity}，主要分享{topic}，内容偏{style}。",
            f"{identity}，长期讨论{topic}，表达上更偏{style}。",
            f"{identity}，核心内容是{topic}，常见表达方式是{style}。",
        ]
        if matching:
            variants.append(f"{identity}，主要分享{topic}，内容偏{style}，{matching}。")
    idx = int(hashlib.md5(handle.encode("utf-8")).hexdigest(), 16) % len(variants)
    text = variants[idx]
    if len(text) > 55:
        text = f"{identity}，主要分享{topic}，内容偏{style}。"
    return text


def format_categories(categories: list[str]) -> str:
    return "/".join(categories[:2])


def process_csv(path: Path) -> None:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames or []

    known_overrides = load_known_bio_overrides()

    for row in rows:
        raw_bio = row.get("账号简介__平台抓取", "") or ""
        raw_cat = row.get("账号类目标签__平台抓取", "") or ""
        handle = row.get("账号ID", "") or row.get("频道/作者名称", "") or ""
        categories = infer_categories(raw_bio, raw_cat)
        bio = build_bio(handle, raw_bio, raw_cat, categories, known_overrides)
        row["账号类目标签"] = format_categories(categories)
        row["账号简介"] = bio

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
